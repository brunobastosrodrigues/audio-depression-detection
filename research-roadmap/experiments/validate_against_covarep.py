#!/usr/bin/env python3
"""
Validate Python feature extractor against COVAREP ground truth.

Compares F0 and pause ratio from our Python implementation
with the pre-computed COVAREP features from DAIC-WOZ.
"""

import json
import numpy as np
from pathlib import Path
from scipy import stats


def load_covarep_baseline(path: str) -> dict:
    """Load COVAREP baseline features."""
    with open(path) as f:
        data = json.load(f)
    return {str(d["session_id"]): d for d in data if "error" not in d}


def load_python_features(path: str) -> dict:
    """Load Python-extracted features."""
    with open(path) as f:
        data = json.load(f)
    return {str(d["session_id"]): d for d in data if "error" not in d}


def compare_features(covarep: dict, python: dict) -> dict:
    """Compare features and compute metrics."""
    common_ids = set(covarep.keys()) & set(python.keys())
    print(f"Common sessions: {len(common_ids)}")

    results = {
        "f0_mean": {"covarep": [], "python": []},
        "f0_std": {"covarep": [], "python": []},
        "pause_ratio": {"covarep": [], "python": []},
        "voiced_ratio": {"covarep": [], "python": []},
    }

    for sid in sorted(common_ids):
        cov = covarep[sid]
        py = python[sid]

        # Map field names (COVAREP uses different naming)
        results["f0_mean"]["covarep"].append(cov.get("f0_mean_hz", cov.get("baseline_features", {}).get("f0_mean_hz", 0)))
        results["f0_mean"]["python"].append(py["f0_mean_hz"])

        results["f0_std"]["covarep"].append(cov.get("f0_std_hz", cov.get("baseline_features", {}).get("f0_std_hz", 0)))
        results["f0_std"]["python"].append(py["f0_std_hz"])

        results["pause_ratio"]["covarep"].append(cov.get("pause_ratio", cov.get("baseline_features", {}).get("pause_ratio", 0)))
        results["pause_ratio"]["python"].append(py["pause_ratio"])

        results["voiced_ratio"]["covarep"].append(cov.get("voiced_ratio", cov.get("baseline_features", {}).get("voiced_ratio", 0)))
        results["voiced_ratio"]["python"].append(py["voiced_ratio"])

    return results


def compute_metrics(results: dict):
    """Compute comparison metrics."""
    print("\n=== Validation Results ===")
    print(f"{'Feature':<15} {'MAPE':<10} {'Pearson r':<12} {'Covarep Mean':<15} {'Python Mean':<15}")
    print("-" * 70)

    for feat, data in results.items():
        cov = np.array(data["covarep"])
        py = np.array(data["python"])

        # Filter out zeros for percentage calculation
        mask = cov > 0.001
        if np.sum(mask) < 5:
            print(f"{feat:<15} Insufficient non-zero values")
            continue

        cov_nz = cov[mask]
        py_nz = py[mask]

        # MAPE
        mape = np.mean(np.abs(cov_nz - py_nz) / cov_nz) * 100

        # Pearson correlation
        r, p = stats.pearsonr(cov, py)

        # Means
        cov_mean = np.mean(cov)
        py_mean = np.mean(py)

        print(f"{feat:<15} {mape:>8.2f}%  {r:>10.4f}    {cov_mean:>13.3f}   {py_mean:>13.3f}")


def main():
    results_dir = Path(__file__).parent / "results"

    covarep_path = results_dir / "daic_woz_baseline_features.json"
    python_path = results_dir / "python_features.json"

    if not covarep_path.exists():
        print(f"COVAREP baseline not found: {covarep_path}")
        return

    if not python_path.exists():
        print(f"Python features not found: {python_path}")
        return

    covarep = load_covarep_baseline(str(covarep_path))
    python = load_python_features(str(python_path))

    print(f"COVAREP sessions: {len(covarep)}")
    print(f"Python sessions: {len(python)}")

    results = compare_features(covarep, python)
    compute_metrics(results)


if __name__ == "__main__":
    main()
