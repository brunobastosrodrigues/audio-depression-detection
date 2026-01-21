#!/usr/bin/env python3
"""
DAIC-WOZ Dataset Analysis Script

Extracts and analyzes available DAIC-WOZ sessions for depression detection research.
Focuses on COVAREP features which contain clinically-validated depression markers.

Usage:
    python daic_woz_analysis.py --extract      # Extract all zips
    python daic_woz_analysis.py --analyze      # Analyze extracted data
    python daic_woz_analysis.py --baseline     # Create Python feature baseline
"""

import os
import sys
import json
import zipfile
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import numpy as np

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configuration
DAIC_WOZ_DIR = Path("/home/rodrigues/daic-woz")
OUTPUT_DIR = Path(__file__).parent / "daic_woz_extracted"
RESULTS_DIR = Path(__file__).parent / "results"

# COVAREP feature columns (from DAIC-WOZ documentation)
# https://github.com/speechlab-iiith/avec2017/blob/master/features/COVAREP_README.txt
COVAREP_COLUMNS = [
    "F0",           # Fundamental frequency (Hz) - VALIDATED
    "VUV",          # Voiced/Unvoiced flag
    "NAQ",          # Normalized Amplitude Quotient
    "QOQ",          # Quasi-Open Quotient
    "H1H2",         # Difference H1-H2
    "PSP",          # Parabolic Spectral Parameter
    "MDQ",          # Maxima Dispersion Quotient
    "peakSlope",    # Peak slope
    "Rd",           # Rd parameter
    "Rd_conf",      # Rd confidence
    "creak",        # Creak probability
    "MCEP_0", "MCEP_1", "MCEP_2", "MCEP_3", "MCEP_4",
    "MCEP_5", "MCEP_6", "MCEP_7", "MCEP_8", "MCEP_9",
    "MCEP_10", "MCEP_11", "MCEP_12", "MCEP_13", "MCEP_14",
    "MCEP_15", "MCEP_16", "MCEP_17", "MCEP_18", "MCEP_19",
    "MCEP_20", "MCEP_21", "MCEP_22", "MCEP_23", "MCEP_24",
    "HMPDM_0", "HMPDM_1", "HMPDM_2", "HMPDM_3", "HMPDM_4",
    "HMPDM_5", "HMPDM_6", "HMPDM_7", "HMPDM_8", "HMPDM_9",
    "HMPDM_10", "HMPDM_11", "HMPDM_12", "HMPDM_13", "HMPDM_14",
    "HMPDM_15", "HMPDM_16", "HMPDM_17", "HMPDM_18", "HMPDM_19",
    "HMPDM_20", "HMPDM_21", "HMPDM_22", "HMPDM_23", "HMPDM_24",
    "HMPDD_0", "HMPDD_1", "HMPDD_2", "HMPDD_3", "HMPDD_4",
    "HMPDD_5", "HMPDD_6", "HMPDD_7", "HMPDD_8", "HMPDD_9",
    "HMPDD_10", "HMPDD_11", "HMPDD_12",
]

# Features we care about for depression detection
DEPRESSION_FEATURES = {
    "F0": "Fundamental frequency - lower/less variable in depression",
    "NAQ": "Normalized Amplitude Quotient - voice quality",
    "QOQ": "Quasi-Open Quotient - glottal behavior",
    "H1H2": "Spectral tilt - breathiness indicator",
    "creak": "Creaky voice probability",
    "MCEP_0": "Mel-cepstral coefficient 0 (energy-related)",
}


@dataclass
class SessionInfo:
    """Information about a DAIC-WOZ session."""
    session_id: int
    has_audio: bool
    has_covarep: bool
    has_formant: bool
    has_transcript: bool
    audio_duration_sec: Optional[float] = None
    covarep_frames: Optional[int] = None
    zip_size_mb: float = 0.0


@dataclass
class FeatureStats:
    """Statistics for a single feature."""
    name: str
    mean: float
    std: float
    min: float
    max: float
    voiced_ratio: float  # For F0: ratio of voiced frames


def list_available_sessions() -> List[int]:
    """List all available session IDs."""
    sessions = []
    for f in DAIC_WOZ_DIR.glob("*_P.zip"):
        try:
            session_id = int(f.stem.split("_")[0])
            sessions.append(session_id)
        except ValueError:
            continue
    return sorted(sessions)


def get_session_info(session_id: int) -> SessionInfo:
    """Get information about a session from its zip file."""
    zip_path = DAIC_WOZ_DIR / f"{session_id}_P.zip"

    if not zip_path.exists():
        raise FileNotFoundError(f"Session {session_id} not found")

    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)

    with zipfile.ZipFile(zip_path, 'r') as zf:
        names = zf.namelist()

        return SessionInfo(
            session_id=session_id,
            has_audio=f"{session_id}_AUDIO.wav" in names,
            has_covarep=f"{session_id}_COVAREP.csv" in names,
            has_formant=f"{session_id}_FORMANT.csv" in names,
            has_transcript=f"{session_id}_TRANSCRIPT.csv" in names,
            zip_size_mb=zip_size_mb,
        )


def extract_session(session_id: int, output_dir: Path) -> Path:
    """Extract a session's files to output directory."""
    zip_path = DAIC_WOZ_DIR / f"{session_id}_P.zip"
    session_dir = output_dir / str(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zf:
        # Extract only the files we need
        for name in zf.namelist():
            if name.endswith(('.wav', '_COVAREP.csv', '_FORMANT.csv', '_TRANSCRIPT.csv')):
                zf.extract(name, session_dir)

    return session_dir


def load_covarep(session_dir: Path, session_id: int) -> Optional[np.ndarray]:
    """Load COVAREP features from CSV."""
    covarep_path = session_dir / f"{session_id}_COVAREP.csv"

    if not covarep_path.exists():
        # Try inside subdirectory
        covarep_path = session_dir / str(session_id) / f"{session_id}_COVAREP.csv"

    if not covarep_path.exists():
        return None

    try:
        # COVAREP is space-separated, no header
        data = np.loadtxt(covarep_path, delimiter=',')
        return data
    except Exception as e:
        print(f"Error loading COVAREP for {session_id}: {e}")
        return None


def compute_feature_stats(covarep: np.ndarray, feature_idx: int, feature_name: str) -> FeatureStats:
    """Compute statistics for a single feature."""
    feature = covarep[:, feature_idx]

    # Use VUV column (index 1) for voiced/unvoiced detection
    vuv = covarep[:, 1]
    voiced_mask = vuv == 1

    # For F0, compute stats only on voiced frames
    if feature_name == "F0":
        voiced_ratio = np.mean(voiced_mask)
        voiced_feature = feature[voiced_mask]
        if len(voiced_feature) == 0:
            voiced_feature = np.array([0.0])
    else:
        voiced_ratio = np.mean(voiced_mask)
        voiced_feature = feature

    return FeatureStats(
        name=feature_name,
        mean=float(np.mean(voiced_feature)),
        std=float(np.std(voiced_feature)),
        min=float(np.min(voiced_feature)),
        max=float(np.max(voiced_feature)),
        voiced_ratio=voiced_ratio,
    )


def analyze_session(session_dir: Path, session_id: int) -> Dict:
    """Analyze a single session's features."""
    covarep = load_covarep(session_dir, session_id)

    if covarep is None:
        return {"session_id": session_id, "error": "Could not load COVAREP"}

    # Compute stats for depression-relevant features
    feature_stats = {}
    for feat_name, feat_desc in DEPRESSION_FEATURES.items():
        try:
            feat_idx = COVAREP_COLUMNS.index(feat_name)
            stats = compute_feature_stats(covarep, feat_idx, feat_name)
            feature_stats[feat_name] = asdict(stats)
        except (ValueError, IndexError) as e:
            feature_stats[feat_name] = {"error": str(e)}

    # Compute pause features using VUV column (index 1)
    vuv = covarep[:, 1]
    voiced = vuv == 1

    # Count pause segments (consecutive unvoiced frames)
    pause_count = 0
    in_pause = False
    pause_lengths = []
    current_pause = 0

    for v in voiced:
        if not v:
            if not in_pause:
                in_pause = True
                pause_count += 1
                current_pause = 1
            else:
                current_pause += 1
        else:
            if in_pause:
                pause_lengths.append(current_pause)
                in_pause = False
                current_pause = 0

    # COVAREP is at 100 fps (10ms frames)
    frame_duration_ms = 10

    return {
        "session_id": session_id,
        "total_frames": int(covarep.shape[0]),
        "duration_sec": float(covarep.shape[0] * frame_duration_ms / 1000),
        "features": feature_stats,
        "pause_analysis": {
            "pause_count": pause_count,
            "avg_pause_frames": float(np.mean(pause_lengths)) if pause_lengths else 0,
            "avg_pause_ms": float(np.mean(pause_lengths) * frame_duration_ms) if pause_lengths else 0,
            "voiced_ratio": float(np.mean(voiced)),
        }
    }


def extract_baseline_features(session_dir: Path, session_id: int) -> Dict:
    """
    Extract the 6 baseline features we identified for edge deployment.

    Returns features comparable to what we'd compute in C on ESP32.
    """
    covarep = load_covarep(session_dir, session_id)

    if covarep is None:
        return {"session_id": session_id, "error": "Could not load COVAREP"}

    # F0 analysis - use VUV column (index 1) for voiced detection
    f0 = covarep[:, 0]
    vuv = covarep[:, 1]
    voiced_mask = vuv == 1
    voiced_f0 = f0[voiced_mask]

    if len(voiced_f0) < 10:
        return {"session_id": session_id, "error": "Insufficient voiced frames"}

    # 1. F0 mean (Hz)
    f0_mean = float(np.mean(voiced_f0))

    # 2. F0 std (Hz)
    f0_std = float(np.std(voiced_f0))

    # 3. Pause ratio (unvoiced / total)
    pause_ratio = float(1.0 - np.mean(voiced_mask))

    # 4. Voiced ratio (for speech rate proxy)
    voiced_ratio = float(np.mean(voiced_mask))

    # 5. F0 range (max - min in voiced)
    f0_range = float(np.max(voiced_f0) - np.min(voiced_f0))

    # 6. Energy proxy from MCEP_0
    mcep0 = covarep[:, COVAREP_COLUMNS.index("MCEP_0")]
    energy_std = float(np.std(mcep0))

    # Additional features from COVAREP (can't compute jitter/shimmer directly)
    # NAQ and H1H2 are voice quality proxies
    naq = covarep[:, COVAREP_COLUMNS.index("NAQ")]
    h1h2 = covarep[:, COVAREP_COLUMNS.index("H1H2")]

    return {
        "session_id": session_id,
        "baseline_features": {
            "f0_mean_hz": f0_mean,
            "f0_std_hz": f0_std,
            "f0_range_hz": f0_range,
            "pause_ratio": pause_ratio,
            "voiced_ratio": voiced_ratio,
            "energy_std": energy_std,
        },
        "extended_features": {
            "naq_mean": float(np.nanmean(naq)),
            "naq_std": float(np.nanstd(naq)),
            "h1h2_mean": float(np.nanmean(h1h2)),
            "h1h2_std": float(np.nanstd(h1h2)),
        },
        "metadata": {
            "total_frames": int(covarep.shape[0]),
            "voiced_frames": int(np.sum(voiced_mask)),
            "duration_sec": float(covarep.shape[0] * 0.01),  # 10ms frames
        }
    }


def main():
    parser = argparse.ArgumentParser(description="DAIC-WOZ Dataset Analysis")
    parser.add_argument("--extract", action="store_true", help="Extract all zip files")
    parser.add_argument("--analyze", action="store_true", help="Analyze extracted data")
    parser.add_argument("--baseline", action="store_true", help="Create baseline features")
    parser.add_argument("--sessions", type=int, nargs="+", help="Specific sessions to process")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of sessions")
    args = parser.parse_args()

    # Create output directories
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Get available sessions
    all_sessions = list_available_sessions()
    print(f"Found {len(all_sessions)} sessions in {DAIC_WOZ_DIR}")
    print(f"Session range: {min(all_sessions)} - {max(all_sessions)}")

    # Filter sessions
    if args.sessions:
        sessions = [s for s in args.sessions if s in all_sessions]
    else:
        sessions = all_sessions

    if args.limit:
        sessions = sessions[:args.limit]

    # Inventory
    print("\n=== Session Inventory ===")
    inventory = []
    for sid in sessions[:5]:  # Sample first 5
        info = get_session_info(sid)
        inventory.append(asdict(info))
        print(f"  {sid}: audio={info.has_audio}, covarep={info.has_covarep}, "
              f"formant={info.has_formant}, transcript={info.has_transcript}, "
              f"size={info.zip_size_mb:.1f}MB")
    print(f"  ... and {len(sessions) - 5} more")

    # Extract
    if args.extract:
        print(f"\n=== Extracting {len(sessions)} sessions ===")
        for i, sid in enumerate(sessions):
            print(f"  [{i+1}/{len(sessions)}] Extracting {sid}...", end=" ")
            try:
                extract_session(sid, OUTPUT_DIR)
                print("OK")
            except Exception as e:
                print(f"ERROR: {e}")

    # Analyze
    if args.analyze:
        print(f"\n=== Analyzing {len(sessions)} sessions ===")
        analyses = []
        for i, sid in enumerate(sessions):
            session_dir = OUTPUT_DIR / str(sid)
            if not session_dir.exists():
                print(f"  [{i+1}/{len(sessions)}] {sid}: Not extracted, extracting...")
                extract_session(sid, OUTPUT_DIR)

            print(f"  [{i+1}/{len(sessions)}] Analyzing {sid}...", end=" ")
            try:
                analysis = analyze_session(session_dir, sid)
                analyses.append(analysis)
                if "error" not in analysis:
                    print(f"OK ({analysis['duration_sec']:.1f}s, "
                          f"F0={analysis['features']['F0']['mean']:.1f}Hz)")
                else:
                    print(f"ERROR: {analysis['error']}")
            except Exception as e:
                print(f"ERROR: {e}")
                analyses.append({"session_id": sid, "error": str(e)})

        # Save results
        output_file = RESULTS_DIR / "daic_woz_analysis.json"
        with open(output_file, "w") as f:
            json.dump(analyses, f, indent=2)
        print(f"\nSaved analysis to {output_file}")

        # Summary statistics
        valid_analyses = [a for a in analyses if "error" not in a]
        if valid_analyses:
            print(f"\n=== Summary ({len(valid_analyses)} valid sessions) ===")

            # Aggregate F0 statistics
            f0_means = [a["features"]["F0"]["mean"] for a in valid_analyses]
            f0_stds = [a["features"]["F0"]["std"] for a in valid_analyses]
            voiced_ratios = [a["pause_analysis"]["voiced_ratio"] for a in valid_analyses]

            print(f"  F0 mean:     {np.mean(f0_means):.1f} ± {np.std(f0_means):.1f} Hz")
            print(f"  F0 std:      {np.mean(f0_stds):.1f} ± {np.std(f0_stds):.1f} Hz")
            print(f"  Voiced ratio: {np.mean(voiced_ratios):.2f} ± {np.std(voiced_ratios):.2f}")

            durations = [a["duration_sec"] for a in valid_analyses]
            print(f"  Duration:    {np.mean(durations):.1f} ± {np.std(durations):.1f} sec")
            print(f"  Total audio: {sum(durations)/3600:.1f} hours")

    # Baseline features
    if args.baseline:
        print(f"\n=== Extracting Baseline Features ({len(sessions)} sessions) ===")
        baselines = []
        for i, sid in enumerate(sessions):
            session_dir = OUTPUT_DIR / str(sid)
            if not session_dir.exists():
                print(f"  [{i+1}/{len(sessions)}] {sid}: Not extracted, extracting...")
                extract_session(sid, OUTPUT_DIR)

            print(f"  [{i+1}/{len(sessions)}] {sid}...", end=" ")
            try:
                baseline = extract_baseline_features(session_dir, sid)
                baselines.append(baseline)
                if "error" not in baseline:
                    bf = baseline["baseline_features"]
                    print(f"OK (F0={bf['f0_mean_hz']:.1f}Hz, pause={bf['pause_ratio']:.2f})")
                else:
                    print(f"ERROR: {baseline['error']}")
            except Exception as e:
                print(f"ERROR: {e}")
                baselines.append({"session_id": sid, "error": str(e)})

        # Save baseline features
        output_file = RESULTS_DIR / "daic_woz_baseline_features.json"
        with open(output_file, "w") as f:
            json.dump(baselines, f, indent=2)
        print(f"\nSaved baseline features to {output_file}")

        # Create CSV for easy analysis
        valid_baselines = [b for b in baselines if "error" not in b]
        if valid_baselines:
            csv_file = RESULTS_DIR / "daic_woz_baseline_features.csv"
            with open(csv_file, "w") as f:
                # Header
                headers = ["session_id"] + list(valid_baselines[0]["baseline_features"].keys())
                headers += list(valid_baselines[0]["extended_features"].keys())
                f.write(",".join(headers) + "\n")

                # Data
                for b in valid_baselines:
                    row = [str(b["session_id"])]
                    row += [str(v) for v in b["baseline_features"].values()]
                    row += [str(v) for v in b["extended_features"].values()]
                    f.write(",".join(row) + "\n")

            print(f"Saved CSV to {csv_file}")

            # Summary
            print(f"\n=== Baseline Feature Summary ({len(valid_baselines)} sessions) ===")
            for feat_name in valid_baselines[0]["baseline_features"].keys():
                values = [b["baseline_features"][feat_name] for b in valid_baselines]
                print(f"  {feat_name:15s}: {np.mean(values):8.3f} ± {np.std(values):8.3f}")


if __name__ == "__main__":
    main()
