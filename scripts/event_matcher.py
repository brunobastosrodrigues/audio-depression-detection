#!/usr/bin/env python3
"""
event_matcher.py — Acoustic-event grouping and best-capture election.

PROBLEM: multiple boards often capture the *same* acoustic event within a
short window.  Treating each segment as an independent observation inflates
segment counts (double-counting / pseudoreplication).  This module groups
co-captured segments into a single acoustic_event and elects a single
canonical capture, removing the pseudoreplication before any downstream
reliability analysis.

Core API
--------
group_events(segments, window_s=EVENT_WINDOW_S) -> list[dict]

    segments  – list of dicts, each with:
        board_id    str
        timestamp   datetime (timezone-aware or naive; compared by total seconds)
        snr         float or None
        env_rms     float or None
        features    dict (opaque; not used here)

    Returns list of event dicts:
        event_id            int (0-indexed, sorted by t0)
        t0                  datetime  (timestamp of the earliest segment)
        member_board_ids    list[str] (sorted, unique)
        canonical_board_id  str       (elected: max snr -> max env_rms -> earliest)
        n_captures          int

Constraint: segments from the SAME board are NEVER merged, even if they fall
within the window.  This preserves within-board temporal resolution and
prevents silent data loss.

Main script usage
-----------------
python3 scripts/event_matcher.py [--since HOURS]

Env vars (loaded from .env if present):
    MONGO_USER          (default: iotsensing)
    MONGO_PASS          (default: "")
    MONGO_HOST          (default: 127.0.0.1)
    MONGO_PORT          (default: 27017)
    EVENT_WINDOW_S      grouping window in seconds (default: 1.5)
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_WINDOW_S = 1.5

def _window_s() -> float:
    """Read EVENT_WINDOW_S from environment (fall back to 1.5 s)."""
    try:
        return float(os.environ.get("EVENT_WINDOW_S", _DEFAULT_WINDOW_S))
    except ValueError:
        return _DEFAULT_WINDOW_S

EVENT_WINDOW_S: float = _window_s()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_utc_naive(ts: datetime) -> datetime:
    """Convert any datetime to a UTC-naive datetime for arithmetic."""
    if ts.tzinfo is not None:
        ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
    return ts


def _elapsed_s(a: datetime, b: datetime) -> float:
    """Absolute seconds between two datetimes (handles tz-aware/naive mix)."""
    return abs((_to_utc_naive(a) - _to_utc_naive(b)).total_seconds())


def _elect_canonical(members: list[dict]) -> str:
    """
    Choose the best-quality segment from a list of member dicts.

    Priority:
        1. Highest snr  (None treated as -∞)
        2. Highest env_rms (None treated as -∞) — tie-break
        3. Earliest timestamp — final tie-break
    """
    def _key(seg: dict):
        snr     = seg.get("snr")    if seg.get("snr")     is not None else float("-inf")
        rms     = seg.get("env_rms") if seg.get("env_rms") is not None else float("-inf")
        ts      = _to_utc_naive(seg["timestamp"])
        return (snr, rms, -ts.timestamp())   # negate timestamp → earlier wins

    best = max(members, key=_key)
    return best["board_id"]


# ---------------------------------------------------------------------------
# Core grouping algorithm
# ---------------------------------------------------------------------------

def group_events(
    segments: list[dict[str, Any]],
    window_s: float | None = None,
) -> list[dict[str, Any]]:
    """
    Group segments from DIFFERENT boards into acoustic events.

    Algorithm:
        Sort by timestamp.  For each segment try to extend an OPEN event:
            - The event's latest-seen timestamp is within window_s of this segment.
            - This board_id is NOT already represented in the event.
        If no suitable open event exists, open a new one.
        An event is closed (no longer a candidate) once its time span exceeds
        window_s even for the most recent segment.

    Segments from the same board are never merged — they always start a new
    event or remain isolated, even when temporally close.

    Parameters
    ----------
    segments : list[dict]
        Each dict must have: board_id (str), timestamp (datetime),
        snr (float|None), env_rms (float|None), features (dict).
    window_s : float, optional
        Co-capture grouping window in seconds.  Defaults to EVENT_WINDOW_S
        (environment variable or 1.5 s).

    Returns
    -------
    list[dict]
        One dict per acoustic event, sorted by t0.
    """
    if window_s is None:
        window_s = EVENT_WINDOW_S

    if not segments:
        return []

    # Sort a copy by timestamp
    sorted_segs = sorted(segments, key=lambda s: _to_utc_naive(s["timestamp"]))

    # Each open event: {"members": [seg, ...], "board_ids": set, "latest_ts": datetime}
    open_events: list[dict] = []
    closed_events: list[dict] = []

    for seg in sorted_segs:
        seg_ts = _to_utc_naive(seg["timestamp"])
        placed = False

        for ev in open_events:
            # Gap from this event's latest member to current segment
            gap = (seg_ts - _to_utc_naive(ev["latest_ts"])).total_seconds()
            if gap > window_s:
                # Event too old — will be pruned below; skip
                continue
            if seg["board_id"] in ev["board_ids"]:
                # Same-board constraint: never merge
                continue
            # This segment belongs to this event
            ev["members"].append(seg)
            ev["board_ids"].add(seg["board_id"])
            ev["latest_ts"] = seg["timestamp"]  # keep original for t0 calc
            placed = True
            break

        if not placed:
            open_events.append({
                "members": [seg],
                "board_ids": {seg["board_id"]},
                "latest_ts": seg["timestamp"],
            })

        # Prune events that can no longer receive new segments
        still_open = []
        for ev in open_events:
            if (seg_ts - _to_utc_naive(ev["latest_ts"])).total_seconds() <= window_s:
                still_open.append(ev)
            else:
                closed_events.append(ev)
        open_events = still_open

    closed_events.extend(open_events)  # close remaining

    # Build output, sorted by t0
    result = []
    for idx, ev in enumerate(sorted(
        closed_events,
        key=lambda e: _to_utc_naive(e["members"][0]["timestamp"]),
    )):
        members = ev["members"]
        t0 = min(m["timestamp"] for m in members)
        result.append({
            "event_id":           idx,
            "t0":                 t0,
            "member_board_ids":   sorted({m["board_id"] for m in members}),
            "canonical_board_id": _elect_canonical(members),
            "n_captures":         len(members),
        })

    return result


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> bool:
    """
    Synthetic test suite.  Prints PASS/FAIL per assertion.
    Returns True only if all assertions pass.
    """
    from datetime import datetime, timezone

    BASE = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    def ts(offset_s: float) -> datetime:
        return BASE + timedelta(seconds=offset_s)

    # -----------------------------------------------------------------------
    # Build synthetic corpus
    # -----------------------------------------------------------------------
    #
    # Three SHARED events (each heard by multiple boards within <1.5 s):
    #   Event A  @ t=0     : boards b1(snr=15), b2(snr=20), b3(snr=10)  — canon = b2
    #   Event B  @ t=100   : boards b1(snr=None), b4(snr=5), b5(snr=5)  — tie on snr
    #                          b4 env_rms=0.3, b5 env_rms=0.5            — canon = b5
    #   Event C  @ t=200   : boards b2(snr=8), b3(snr=8), b4(snr=8)    — tie on snr+rms
    #                          b3 earliest                                — canon = b3
    #
    # Five ISOLATED single-board segments (no partner within window):
    #   iso1..iso5: each at t=50, 150, 250, 350, 450 from distinct boards
    #
    # One SAME-BOARD pair (b1 at t=500 and t=500.2): must NOT merge.
    # -----------------------------------------------------------------------

    segments = [
        # Event A
        {"board_id": "b1", "timestamp": ts(0.0),  "snr": 15.0, "env_rms": 0.1, "features": {}},
        {"board_id": "b2", "timestamp": ts(0.5),  "snr": 20.0, "env_rms": 0.2, "features": {}},
        {"board_id": "b3", "timestamp": ts(1.0),  "snr": 10.0, "env_rms": 0.3, "features": {}},
        # Event B (snr tie; env_rms decides)
        {"board_id": "b1", "timestamp": ts(100.0), "snr": None, "env_rms": None,  "features": {}},
        {"board_id": "b4", "timestamp": ts(100.3), "snr":  5.0, "env_rms": 0.3,   "features": {}},
        {"board_id": "b5", "timestamp": ts(100.6), "snr":  5.0, "env_rms": 0.5,   "features": {}},
        # Event C (snr + rms all tied; earliest decides = b2 at t=200.0)
        {"board_id": "b2", "timestamp": ts(200.0), "snr": 8.0, "env_rms": 0.4, "features": {}},
        {"board_id": "b3", "timestamp": ts(200.2), "snr": 8.0, "env_rms": 0.4, "features": {}},
        {"board_id": "b4", "timestamp": ts(200.8), "snr": 8.0, "env_rms": 0.4, "features": {}},
        # Isolated segments
        {"board_id": "b6",  "timestamp": ts( 50.0), "snr": 12.0, "env_rms": 0.2, "features": {}},
        {"board_id": "b7",  "timestamp": ts(150.0), "snr":  7.0, "env_rms": 0.1, "features": {}},
        {"board_id": "b8",  "timestamp": ts(250.0), "snr":  9.0, "env_rms": 0.2, "features": {}},
        {"board_id": "b9",  "timestamp": ts(350.0), "snr":  6.0, "env_rms": 0.1, "features": {}},
        {"board_id": "b10", "timestamp": ts(450.0), "snr": 11.0, "env_rms": 0.3, "features": {}},
        # Same-board pair (must NOT merge)
        {"board_id": "b1", "timestamp": ts(500.0), "snr": 14.0, "env_rms": 0.2, "features": {}},
        {"board_id": "b1", "timestamp": ts(500.2), "snr": 16.0, "env_rms": 0.3, "features": {}},
    ]

    events = group_events(segments, window_s=1.5)

    all_pass = True
    checks = []

    def check(label: str, cond: bool):
        nonlocal all_pass
        status = "PASS" if cond else "FAIL"
        if not cond:
            all_pass = False
        checks.append((status, label))

    # --- Total event count ---
    # 3 shared + 5 isolated + 2 same-board = 10 events
    check("Total event count == 10", len(events) == 10)

    # Map events by member_board_ids tuple for easier lookup
    by_members: dict[tuple, dict] = {
        tuple(sorted(e["member_board_ids"])): e for e in events
    }

    # --- Event A ---
    ev_a = by_members.get(("b1", "b2", "b3"))
    check("Event A exists (boards b1,b2,b3)", ev_a is not None)
    if ev_a:
        check("Event A canonical = b2 (highest snr=20)", ev_a["canonical_board_id"] == "b2")
        check("Event A n_captures == 3", ev_a["n_captures"] == 3)

    # --- Event B ---
    ev_b = by_members.get(("b1", "b4", "b5"))
    check("Event B exists (boards b1,b4,b5)", ev_b is not None)
    if ev_b:
        # b1 snr=None (-inf), b4 snr=5 env_rms=0.3, b5 snr=5 env_rms=0.5 → b5 wins
        check("Event B canonical = b5 (highest env_rms on snr tie)", ev_b["canonical_board_id"] == "b5")
        check("Event B n_captures == 3", ev_b["n_captures"] == 3)

    # --- Event C ---
    ev_c = by_members.get(("b2", "b3", "b4"))
    check("Event C exists (boards b2,b3,b4)", ev_c is not None)
    if ev_c:
        # All tied on snr+rms; earliest = b2 @ t=200.0
        check("Event C canonical = b2 (earliest on full tie)", ev_c["canonical_board_id"] == "b2")
        check("Event C n_captures == 3", ev_c["n_captures"] == 3)

    # --- Isolated segments (each is its own event) ---
    iso_boards = {"b6", "b7", "b8", "b9", "b10"}
    for b in iso_boards:
        key = (b,)
        ev = by_members.get(key)
        check(f"Isolated board {b} is its own event", ev is not None and ev["n_captures"] == 1)

    # --- Same-board pair stays separate ---
    # b1 appears at t=500 and t=500.2 — two distinct events
    b1_events = [e for e in events if e["member_board_ids"] == ["b1"]]
    check("Same-board b1 pair → 2 separate events (not merged)", len(b1_events) == 2)

    # --- Print results ---
    print("\n=== event_matcher self-test ===")
    for status, label in checks:
        print(f"  [{status}] {label}")
    overall = "ALL PASS" if all_pass else "SOME ASSERTIONS FAILED"
    print(f"\n  Result: {overall}\n")

    return all_pass


# ---------------------------------------------------------------------------
# Main — dedup ratio from MongoDB
# ---------------------------------------------------------------------------

def _load_dotenv():
    """Minimal .env loader (no extra deps required)."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env_path = os.path.normpath(env_path)
    if not os.path.exists(env_path):
        return
    with open(env_path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def main():
    _load_dotenv()

    parser = argparse.ArgumentParser(
        description="Report acoustic-event dedup ratio from MongoDB raw_metrics."
    )
    parser.add_argument(
        "--since",
        type=float,
        default=24.0,
        metavar="HOURS",
        help="Look-back window in hours (default: 24)",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run synthetic self-test and exit",
    )
    args = parser.parse_args()

    if args.self_test:
        ok = _self_test()
        sys.exit(0 if ok else 1)

    # Always print self-test banner so the caller can verify correctness
    ok = _self_test()
    if not ok:
        print("ERROR: self-test failed — aborting live query.", file=sys.stderr)
        sys.exit(1)

    # --- MongoDB query ---
    try:
        from pymongo import MongoClient
    except ImportError:
        print("pymongo not installed; cannot query MongoDB.", file=sys.stderr)
        sys.exit(1)

    user  = os.environ.get("MONGO_USER", "iotsensing")
    pw    = os.environ.get("MONGO_PASS", "")
    host  = os.environ.get("MONGO_HOST", "127.0.0.1")
    port  = int(os.environ.get("MONGO_PORT", 27017))

    if pw:
        uri = f"mongodb://{user}:{pw}@{host}:{port}/"
    else:
        uri = f"mongodb://{host}:{port}/"

    since_dt = datetime.now(timezone.utc) - timedelta(hours=args.since)

    try:
        client = MongoClient(uri, authSource="admin", serverSelectionTimeoutMS=5000)
        col = client["iotsensing_live"]["raw_metrics"]
        docs = list(col.find(
            {"timestamp": {"$gte": since_dt}},
            {"board_id": 1, "timestamp": 1, "snr": 1, "env_rms": 1, "_id": 0},
        ))
    except Exception as exc:
        print(f"MongoDB error: {exc}", file=sys.stderr)
        sys.exit(1)

    if not docs:
        print(
            f"\nDEDUP REPORT  (last {args.since:.0f} h)\n"
            "  Collection iotsensing_live.raw_metrics is EMPTY or has no documents\n"
            "  in the requested window.\n"
            "  NOTE: live validation is pending until enrollment + VAD are fixed\n"
            "        and real co-captured speech is being stored.\n"
            "  DEDUP RATIO: N/A (no data)\n"
        )
        return

    # Convert docs to segment dicts
    segments = []
    for d in docs:
        ts = d.get("timestamp")
        if ts is None:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        segments.append({
            "board_id": d.get("board_id", "unknown"),
            "timestamp": ts,
            "snr":       d.get("snr"),
            "env_rms":   d.get("env_rms"),
            "features":  {},
        })

    n_segments = len(segments)
    events = group_events(segments)
    n_events = len(events)

    dedup_ratio = 1.0 - (n_events / n_segments) if n_segments > 0 else 0.0

    print(
        f"\nDEDUP REPORT  (last {args.since:.0f} h)\n"
        f"  Segments queried  : {n_segments}\n"
        f"  Acoustic events   : {n_events}\n"
        f"  DEDUP RATIO       : {dedup_ratio:.3f}  "
        f"(= 1 - {n_events}/{n_segments})\n"
        f"  Interpretation    : {dedup_ratio*100:.1f}% of segments are cross-board\n"
        f"                      duplicates of events already counted.\n"
    )
    if dedup_ratio == 0.0 and n_segments > 0:
        print(
            "  NOTE: ratio=0 means no co-captures detected — either boards\n"
            "        are not yet capturing simultaneously or EVENT_WINDOW_S\n"
            "        is too narrow.  Live validation pending real co-captured speech.\n"
        )


if __name__ == "__main__":
    main()
