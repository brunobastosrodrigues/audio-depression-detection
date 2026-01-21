#!/usr/bin/env python3
"""
Divergence Analysis: Python vs C Feature Extraction

Compares features extracted by Python (parselmouth) and C (YIN) implementations
to quantify accuracy loss from edge constraints.
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats


def load_features(csv_path: str) -> pd.DataFrame:
    """Load features from CSV."""
    df = pd.read_csv(csv_path)
    df['session_id'] = df['session_id'].astype(str)
    return df.set_index('session_id')


def compute_divergence(python_df: pd.DataFrame, c_df: pd.DataFrame) -> dict:
    """Compute divergence metrics between Python and C features."""

    # Find common sessions
    common = python_df.index.intersection(c_df.index)
    print(f"Common sessions: {len(common)}")

    py = python_df.loc[common]
    c = c_df.loc[common]

    # Features to compare
    features = ['f0_mean_hz', 'f0_std_hz', 'pause_ratio', 'voiced_ratio']

    results = {}

    for feat in features:
        if feat not in py.columns or feat not in c.columns:
            continue

        py_vals = py[feat].values
        c_vals = c[feat].values

        # Filter out zeros for MAPE (avoid division by zero)
        mask = np.abs(py_vals) > 0.001

        if np.sum(mask) < 5:
            results[feat] = {'error': 'Insufficient non-zero values'}
            continue

        py_nz = py_vals[mask]
        c_nz = c_vals[mask]

        # MAPE (Mean Absolute Percentage Error)
        mape = np.mean(np.abs(py_nz - c_nz) / np.abs(py_nz)) * 100

        # MAE (Mean Absolute Error)
        mae = np.mean(np.abs(py_vals - c_vals))

        # Pearson correlation
        r, p_value = stats.pearsonr(py_vals, c_vals)

        # Bias (mean difference)
        bias = np.mean(c_vals - py_vals)

        results[feat] = {
            'mape': float(mape),
            'mae': float(mae),
            'pearson_r': float(r),
            'p_value': float(p_value),
            'bias': float(bias),
            'python_mean': float(np.mean(py_vals)),
            'c_mean': float(np.mean(c_vals)),
            'n_samples': int(len(py_vals)),
        }

    return results


def print_report(results: dict):
    """Print divergence report."""
    print("\n" + "=" * 70)
    print("DIVERGENCE ANALYSIS: Python (Praat) vs C (YIN)")
    print("=" * 70)

    print(f"\n{'Feature':<15} {'MAPE':<10} {'MAE':<12} {'Pearson r':<12} {'Bias':<12} {'Status'}")
    print("-" * 70)

    all_pass = True
    for feat, data in results.items():
        if 'error' in data:
            print(f"{feat:<15} {data['error']}")
            continue

        mape = data['mape']
        mae = data['mae']
        r = data['pearson_r']
        bias = data['bias']

        # Status check
        if mape < 5 and r > 0.9:
            status = "✓ PASS"
        elif mape < 10 and r > 0.8:
            status = "~ MARGINAL"
            all_pass = False
        else:
            status = "✗ FAIL"
            all_pass = False

        print(f"{feat:<15} {mape:>8.2f}%  {mae:>10.3f}  {r:>10.4f}    {bias:>+10.3f}  {status}")

    print("-" * 70)

    # Overall verdict
    print(f"\nOverall: {'✓ ALL FEATURES PASS <5% MAPE' if all_pass else '⚠ SOME FEATURES NEED IMPROVEMENT'}")

    # Detailed breakdown
    print("\n" + "=" * 70)
    print("DETAILED STATISTICS")
    print("=" * 70)

    for feat, data in results.items():
        if 'error' in data:
            continue
        print(f"\n{feat}:")
        print(f"  Python mean: {data['python_mean']:.3f}")
        print(f"  C mean:      {data['c_mean']:.3f}")
        print(f"  Bias:        {data['bias']:+.3f} ({'C higher' if data['bias'] > 0 else 'Python higher'})")
        print(f"  Correlation: r = {data['pearson_r']:.4f} (p = {data['p_value']:.2e})")
        print(f"  Samples:     {data['n_samples']}")


def main():
    results_dir = Path(__file__).parent / "results"

    python_csv = results_dir / "python_features.csv"
    c_csv = results_dir / "c_features.csv"

    if not python_csv.exists():
        print(f"Python features not found: {python_csv}")
        return

    if not c_csv.exists():
        print(f"C features not found: {c_csv}")
        return

    # Load features
    print("Loading Python features...")
    python_df = load_features(str(python_csv))
    print(f"  {len(python_df)} sessions")

    print("Loading C features...")
    c_df = load_features(str(c_csv))
    print(f"  {len(c_df)} sessions")

    # Compute divergence
    results = compute_divergence(python_df, c_df)

    # Print report
    print_report(results)

    # Save results
    output_path = results_dir / "divergence_report.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved detailed results to: {output_path}")


if __name__ == "__main__":
    main()
