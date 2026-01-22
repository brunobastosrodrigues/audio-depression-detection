#!/usr/bin/env python3
"""
Download full DAIC-WOZ dataset (189 sessions).
Sessions 300-492 excluding 342, 394, 398, 460.

Usage:
    python3 download_daic_woz_full.py --username YOUR_USER --password YOUR_PASS

Or set environment variables:
    export DAIC_USERNAME=your_username
    export DAIC_PASSWORD=your_password
    python3 download_daic_woz_full.py
"""

import os
import sys
import argparse
import requests
from zipfile import ZipFile
from io import BytesIO
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time


# All sessions in DAIC-WOZ
ALL_SESSIONS = list(range(300, 493))
EXCLUDED = [342, 394, 398, 460]
VALID_SESSIONS = [s for s in ALL_SESSIONS if s not in EXCLUDED]

OUTPUT_DIR = Path(__file__).parent.parent / "experiments" / "daic_woz_extracted"


def download_session(session_id: int, username: str, password: str, output_dir: Path) -> tuple:
    """Download a single session. Returns (session_id, success, message)."""
    # Use simple numeric folder name to match existing data structure
    session_folder = output_dir / str(session_id)

    # Skip if already downloaded (check both naming conventions)
    if session_folder.exists() and any(session_folder.iterdir()):
        return (session_id, True, "Already exists")
    alt_folder = output_dir / f"{session_id}_P"
    if alt_folder.exists() and any(alt_folder.iterdir()):
        return (session_id, True, "Already exists")

    url = f"https://dcapswoz.ict.usc.edu/wwwdaicwoz/{session_id}_P.zip"

    try:
        response = requests.get(url, auth=(username, password), timeout=300)

        if response.status_code == 401:
            return (session_id, False, "Authentication failed")
        elif response.status_code == 404:
            return (session_id, False, "Not found")
        elif response.status_code != 200:
            return (session_id, False, f"HTTP {response.status_code}")

        # Extract ZIP to temp location, then move contents
        zfile = ZipFile(BytesIO(response.content))
        session_folder.mkdir(parents=True, exist_ok=True)

        # Extract directly - files are in {session_id}_P/ inside the zip
        zfile.extractall(session_folder)

        # Move files from nested {session_id}_P folder to session_folder if needed
        nested = session_folder / f"{session_id}_P"
        if nested.exists():
            for item in nested.iterdir():
                item.rename(session_folder / item.name)
            nested.rmdir()

        return (session_id, True, "Downloaded")

    except requests.exceptions.Timeout:
        return (session_id, False, "Timeout")
    except Exception as e:
        return (session_id, False, str(e)[:50])


def main():
    parser = argparse.ArgumentParser(description="Download DAIC-WOZ dataset")
    parser.add_argument("--username", default=os.environ.get("DAIC_USERNAME"),
                        help="DAIC-WOZ username (or set DAIC_USERNAME env var)")
    parser.add_argument("--password", default=os.environ.get("DAIC_PASSWORD"),
                        help="DAIC-WOZ password (or set DAIC_PASSWORD env var)")
    parser.add_argument("--workers", type=int, default=4,
                        help="Parallel download workers (default: 4)")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR,
                        help="Output directory")
    args = parser.parse_args()

    if not args.username or not args.password:
        print("ERROR: Credentials required!")
        print("  Option 1: python3 download_daic_woz_full.py --username USER --password PASS")
        print("  Option 2: export DAIC_USERNAME=user && export DAIC_PASSWORD=pass")
        sys.exit(1)

    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"DAIC-WOZ Full Download")
    print(f"=" * 60)
    print(f"Total sessions: {len(VALID_SESSIONS)}")
    print(f"Output directory: {output_dir}")
    print(f"Parallel workers: {args.workers}")
    print()

    # Check existing
    existing = [s for s in VALID_SESSIONS if (output_dir / f"{s}_P").exists()]
    missing = [s for s in VALID_SESSIONS if s not in existing]

    print(f"Already downloaded: {len(existing)}")
    print(f"Missing (to download): {len(missing)}")
    print()

    if not missing:
        print("All sessions already downloaded!")
        return 0

    # Test credentials with first session
    print("Testing credentials...")
    test_id, success, msg = download_session(missing[0], args.username, args.password, output_dir)
    if not success and msg == "Authentication failed":
        print(f"ERROR: Authentication failed. Check your username/password.")
        sys.exit(1)
    elif success:
        print(f"  Session {test_id}: {msg}")
        missing = missing[1:]  # Remove from list since we downloaded it

    if not missing:
        print("\nAll sessions downloaded!")
        return 0

    # Download remaining in parallel
    print(f"\nDownloading {len(missing)} sessions...")

    downloaded = len(existing) + 1  # +1 for test session
    failed = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(download_session, sid, args.username, args.password, output_dir): sid
            for sid in missing
        }

        for future in as_completed(futures):
            sid, success, msg = future.result()
            if success:
                downloaded += 1
                print(f"  [{downloaded}/{len(VALID_SESSIONS)}] Session {sid}: {msg}")
            else:
                failed.append((sid, msg))
                print(f"  [FAILED] Session {sid}: {msg}")

    print()
    print(f"=" * 60)
    print(f"Download complete!")
    print(f"  Successful: {downloaded}/{len(VALID_SESSIONS)}")
    print(f"  Failed: {len(failed)}")

    if failed:
        print(f"\nFailed sessions:")
        for sid, msg in failed:
            print(f"  - {sid}: {msg}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
