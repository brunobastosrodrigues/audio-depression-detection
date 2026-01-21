#!/usr/bin/env python3
"""
Feature-Clinical Linkage Framework Analysis

Compares C-extracted features against Python reference implementation
to quantify how well the edge implementation preserves clinical validity.

Metrics:
1. Direction Preservation: sign(r_c) == sign(r_python)
2. Effect Size Preservation Ratio: EPR = |d_c| / |d_python|
3. Classification Accuracy Delta: Δ = AUC_python - AUC_c
4. Feature Divergence (MAPE)
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import warnings
warnings.filterwarnings('ignore')


def load_features_with_labels(c_path: str, python_path: str, corpus_path: str):
    """Load C and Python features with depression labels."""
    corpus = Path(corpus_path)

    def get_depression_status(session_id):
        parts = session_id.split('_')
        split = parts[0]
        pid = parts[1]
        label_file = corpus / split / pid / 'new_label.txt'
        if label_file.exists():
            sds = float(label_file.read_text().strip())
            return sds > 53
        return None

    # Load features
    c_df = pd.read_csv(c_path)
    python_df = pd.read_csv(python_path)

    # Add labels
    c_df['is_depressed'] = c_df['session_id'].apply(get_depression_status)
    python_df['is_depressed'] = python_df['session_id'].apply(get_depression_status)

    # Drop unmapped
    c_df = c_df.dropna(subset=['is_depressed'])
    python_df = python_df.dropna(subset=['is_depressed'])

    return c_df, python_df


def compute_effect_size(group1: np.ndarray, group2: np.ndarray) -> float:
    """Compute Cohen's d effect size."""
    n1, n2 = len(group1), len(group2)
    if n1 < 2 or n2 < 2:
        return 0.0

    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    pooled_std = np.sqrt(((n1-1)*var1 + (n2-1)*var2) / (n1+n2-2))

    if pooled_std < 1e-10:
        return 0.0

    return (np.mean(group1) - np.mean(group2)) / pooled_std


def compute_correlation_with_labels(df, feature, label_col='is_depressed'):
    """Compute correlation between feature and depression labels."""
    valid_mask = ~np.isnan(df[feature].values)
    if sum(valid_mask) < 10:
        return 0.0, 1.0

    x = df.loc[valid_mask, feature].values
    y = df.loc[valid_mask, label_col].values.astype(float)

    r, p = stats.pearsonr(x, y)
    return r, p


def compute_direction_preservation(c_df, python_df, features):
    """
    Metric 1: Direction Preservation

    For each feature, check if sign(r_c) == sign(r_python)
    """
    results = []

    for feature in features:
        if feature not in c_df.columns or feature not in python_df.columns:
            continue

        r_c, p_c = compute_correlation_with_labels(c_df, feature)
        r_python, p_python = compute_correlation_with_labels(python_df, feature)

        direction_preserved = np.sign(r_c) == np.sign(r_python)

        results.append({
            'feature': feature,
            'r_c': r_c,
            'r_python': r_python,
            'direction_preserved': direction_preserved,
            'p_c': p_c,
            'p_python': p_python
        })

    return pd.DataFrame(results)


def compute_effect_size_preservation(c_df, python_df, features):
    """
    Metric 2: Effect Size Preservation Ratio

    EPR = |d_c| / |d_python|
    """
    results = []

    c_dep = c_df[c_df['is_depressed'] == True]
    c_nondep = c_df[c_df['is_depressed'] == False]
    py_dep = python_df[python_df['is_depressed'] == True]
    py_nondep = python_df[python_df['is_depressed'] == False]

    for feature in features:
        if feature not in c_df.columns or feature not in python_df.columns:
            continue

        # C effect size
        c_vals_dep = c_dep[feature].dropna().values
        c_vals_nondep = c_nondep[feature].dropna().values
        d_c = compute_effect_size(c_vals_dep, c_vals_nondep)

        # Python effect size
        py_vals_dep = py_dep[feature].dropna().values
        py_vals_nondep = py_nondep[feature].dropna().values
        d_python = compute_effect_size(py_vals_dep, py_vals_nondep)

        # EPR
        if abs(d_python) > 0.01:
            epr = abs(d_c) / abs(d_python)
        else:
            epr = 1.0 if abs(d_c) < 0.01 else float('inf')

        results.append({
            'feature': feature,
            'd_c': d_c,
            'd_python': d_python,
            'epr': epr,
            'epr_acceptable': epr >= 0.7
        })

    return pd.DataFrame(results)


def compute_feature_divergence(c_df, python_df, features):
    """
    Compute MAPE (Mean Absolute Percentage Error) between C and Python features.
    """
    results = []

    # Merge on session_id
    merged = c_df.merge(python_df, on='session_id', suffixes=('_c', '_python'))

    for feature in features:
        c_col = f"{feature}_c"
        py_col = f"{feature}_python"

        if c_col not in merged.columns or py_col not in merged.columns:
            continue

        c_vals = merged[c_col].values
        py_vals = merged[py_col].values

        # Remove invalid values
        valid = ~(np.isnan(c_vals) | np.isnan(py_vals) | (np.abs(py_vals) < 1e-10))
        c_vals = c_vals[valid]
        py_vals = py_vals[valid]

        if len(c_vals) < 10:
            continue

        # MAPE
        mape = np.mean(np.abs((c_vals - py_vals) / py_vals)) * 100

        # Pearson correlation between implementations
        r, _ = stats.pearsonr(c_vals, py_vals)

        results.append({
            'feature': feature,
            'mape': mape,
            'correlation': r,
            'n_samples': len(c_vals)
        })

    return pd.DataFrame(results)


def compute_classification_delta(c_df, python_df, features):
    """
    Metric 3: Classification Accuracy Delta

    Δ = AUC_python - AUC_c
    """
    def get_auc(df, features):
        X = df[features].values
        y = df['is_depressed'].values.astype(int)
        X = np.nan_to_num(X, nan=0)

        clf = Pipeline([
            ('scaler', StandardScaler()),
            ('lr', LogisticRegression(max_iter=1000, class_weight='balanced'))
        ])

        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        scores = cross_val_score(clf, X, y, cv=cv, scoring='roc_auc')
        return scores.mean(), scores.std()

    common_features = [f for f in features if f in c_df.columns and f in python_df.columns]

    auc_c, std_c = get_auc(c_df, common_features)
    auc_python, std_python = get_auc(python_df, common_features)

    delta = auc_python - auc_c

    return {
        'auc_c': auc_c,
        'auc_c_std': std_c,
        'auc_python': auc_python,
        'auc_python_std': std_python,
        'delta': delta,
        'delta_acceptable': abs(delta) < 0.05
    }


def print_linkage_report(direction_df, epr_df, divergence_df, classification):
    """Print formatted linkage framework report."""
    print("\n" + "="*80)
    print("FEATURE-CLINICAL LINKAGE FRAMEWORK REPORT")
    print("="*80)

    # Metric 1: Direction Preservation
    print("\n## Metric 1: Direction Preservation")
    print("sign(r_c) == sign(r_python)")
    print("-" * 70)
    print(f"{'Feature':<15} {'r_c':>10} {'r_python':>10} {'Preserved':>12}")
    print("-" * 70)

    preserved_count = 0
    for _, row in direction_df.iterrows():
        status = "✓" if row['direction_preserved'] else "✗"
        print(f"{row['feature']:<15} {row['r_c']:>+10.3f} {row['r_python']:>+10.3f} {status:>12}")
        if row['direction_preserved']:
            preserved_count += 1

    print("-" * 70)
    print(f"Direction Preserved: {preserved_count}/{len(direction_df)} ({100*preserved_count/len(direction_df):.1f}%)")

    # Metric 2: Effect Size Preservation
    print("\n## Metric 2: Effect Size Preservation Ratio (EPR)")
    print("EPR = |d_c| / |d_python| >= 0.7")
    print("-" * 70)
    print(f"{'Feature':<15} {'d_c':>10} {'d_python':>10} {'EPR':>10} {'Status':>10}")
    print("-" * 70)

    epr_acceptable = 0
    for _, row in epr_df.iterrows():
        status = "✓" if row['epr_acceptable'] else "✗"
        epr_str = f"{row['epr']:.2f}" if row['epr'] < 100 else ">100"
        print(f"{row['feature']:<15} {row['d_c']:>+10.3f} {row['d_python']:>+10.3f} {epr_str:>10} {status:>10}")
        if row['epr_acceptable']:
            epr_acceptable += 1

    print("-" * 70)
    print(f"EPR Acceptable (>=0.7): {epr_acceptable}/{len(epr_df)} ({100*epr_acceptable/len(epr_df):.1f}%)")

    # Metric 3: Feature Divergence
    print("\n## Feature Divergence (MAPE)")
    print("-" * 70)
    print(f"{'Feature':<15} {'MAPE (%)':>12} {'Correlation':>12}")
    print("-" * 70)

    for _, row in divergence_df.sort_values('mape').iterrows():
        print(f"{row['feature']:<15} {row['mape']:>12.1f} {row['correlation']:>12.3f}")

    mean_mape = divergence_df['mape'].mean()
    print("-" * 70)
    print(f"Average MAPE: {mean_mape:.1f}%")

    # Metric 4: Classification Delta
    print("\n## Metric 3: Classification Accuracy Delta")
    print("Δ = AUC_python - AUC_c < 0.05")
    print("-" * 70)
    print(f"AUC (C implementation):      {classification['auc_c']:.3f} ± {classification['auc_c_std']:.3f}")
    print(f"AUC (Python implementation): {classification['auc_python']:.3f} ± {classification['auc_python_std']:.3f}")
    print(f"Delta:                       {classification['delta']:+.3f}")
    status = "✓ ACCEPTABLE" if classification['delta_acceptable'] else "✗ EXCEEDS THRESHOLD"
    print(f"Status:                      {status}")

    # Overall Summary
    print("\n" + "="*80)
    print("OVERALL LINKAGE PRESERVATION SUMMARY")
    print("="*80)

    metrics_passed = 0
    total_metrics = 3

    if preserved_count >= len(direction_df) * 0.7:
        metrics_passed += 1
        print("✓ Direction Preservation: PASSED (>70% features preserved)")
    else:
        print("✗ Direction Preservation: FAILED (<70% features preserved)")

    if epr_acceptable >= len(epr_df) * 0.7:
        metrics_passed += 1
        print("✓ Effect Size Preservation: PASSED (>70% EPR acceptable)")
    else:
        print("✗ Effect Size Preservation: FAILED (<70% EPR acceptable)")

    if classification['delta_acceptable']:
        metrics_passed += 1
        print("✓ Classification Delta: PASSED (Δ < 0.05)")
    else:
        print("✗ Classification Delta: FAILED (Δ >= 0.05)")

    print("-" * 70)
    if metrics_passed == total_metrics:
        verdict = "✓ C IMPLEMENTATION PRESERVES CLINICAL VALIDITY"
    elif metrics_passed >= 2:
        verdict = "~ PARTIAL CLINICAL VALIDITY PRESERVATION"
    else:
        verdict = "✗ CLINICAL VALIDITY CONCERNS"

    print(f"Verdict: {verdict}")
    print("="*80)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Compute linkage preservation metrics")
    parser.add_argument("--c-features", default="results/eatd_c_features.csv")
    parser.add_argument("--python-features", default="results/eatd_python_features.csv")
    parser.add_argument("--corpus", default="../../datasets/eatd-corpus-data/EATD-Corpus")
    parser.add_argument("--output", default="results/linkage_analysis.csv")
    args = parser.parse_args()

    script_dir = Path(__file__).parent

    # Resolve paths
    c_path = (script_dir / args.c_features).resolve()
    python_path = (script_dir / args.python_features).resolve()
    corpus_path = (script_dir / args.corpus).resolve()

    print(f"C features: {c_path}")
    print(f"Python features: {python_path}")
    print(f"Corpus: {corpus_path}")

    # Load data
    c_df, python_df = load_features_with_labels(
        str(c_path), str(python_path), str(corpus_path)
    )

    print(f"\nSamples - C: {len(c_df)}, Python: {len(python_df)}")

    # Define features to compare
    features = ['f0_mean_hz', 'f0_std_hz', 'f0_range_hz', 'pause_ratio',
                'voiced_ratio', 'energy_std', 'jitter', 'shimmer',
                'hnr_mean', 'snr']

    # Compute metrics
    print("\nComputing linkage metrics...")

    direction_df = compute_direction_preservation(c_df, python_df, features)
    epr_df = compute_effect_size_preservation(c_df, python_df, features)
    divergence_df = compute_feature_divergence(c_df, python_df, features)
    classification = compute_classification_delta(c_df, python_df, features)

    # Print report
    print_linkage_report(direction_df, epr_df, divergence_df, classification)

    # Save results
    output_path = script_dir / args.output
    combined = direction_df.merge(epr_df, on='feature').merge(divergence_df, on='feature')
    combined.to_csv(output_path, index=False)
    print(f"\nResults saved to: {output_path}")

    return 0


if __name__ == "__main__":
    exit(main())
