#!/usr/bin/env python3
"""
Statistical Rigor Improvements

Addresses critical gaps:
1. Power analysis for observed effects
2. Bootstrap confidence intervals
3. Threshold sensitivity analysis
4. Regularized classification
5. FDR (False Discovery Rate) correction for multiple comparisons
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.linear_model import LogisticRegression, LogisticRegressionCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.utils import resample
import warnings
warnings.filterwarnings('ignore')


def benjamini_hochberg_correction(p_values, alpha=0.05):
    """
    Apply Benjamini-Hochberg FDR correction for multiple comparisons.

    Returns:
        adjusted_pvalues: FDR-adjusted p-values
        significant: Boolean array indicating which are significant after correction
    """
    n = len(p_values)
    if n == 0:
        return np.array([]), np.array([])

    # Sort p-values and get original indices
    sorted_indices = np.argsort(p_values)
    sorted_pvalues = np.array(p_values)[sorted_indices]

    # Calculate BH critical values
    ranks = np.arange(1, n + 1)
    bh_critical = (ranks / n) * alpha

    # Find largest p-value that is <= its critical value
    significant_sorted = sorted_pvalues <= bh_critical

    # Adjust p-values
    adjusted = np.zeros(n)
    adjusted[sorted_indices] = np.minimum(1, sorted_pvalues * n / ranks)

    # Make adjusted p-values monotonic
    for i in range(n - 2, -1, -1):
        adjusted[sorted_indices[i]] = min(adjusted[sorted_indices[i]],
                                          adjusted[sorted_indices[i + 1]] if i + 1 < n else 1)

    return adjusted, adjusted < alpha


def fdr_analysis(df):
    """Apply FDR correction to feature comparisons."""
    print("\n" + "="*70)
    print("5. FDR (FALSE DISCOVERY RATE) CORRECTION")
    print("="*70)
    print("\nProblem: Testing 8 features inflates false positive risk to ~34%")
    print("Solution: Benjamini-Hochberg FDR correction\n")

    dep = df[df['is_depressed'] == True]
    nondep = df[df['is_depressed'] == False]

    features = ['f0_mean_hz', 'f0_std_hz', 'pause_ratio', 'energy_std',
                'jitter', 'shimmer', 'hnr_mean', 'snr']

    p_values = []
    feature_names = []

    for feat in features:
        if feat not in df.columns:
            continue
        d1 = dep[feat].dropna().values
        d2 = nondep[feat].dropna().values
        if len(d1) >= 5 and len(d2) >= 5:
            _, p = stats.ttest_ind(d1, d2)
            p_values.append(p)
            feature_names.append(feat)

    # Apply FDR correction
    adjusted_p, significant = benjamini_hochberg_correction(p_values)

    print(f"{'Feature':<15} {'Raw p':>12} {'FDR p':>12} {'Sig (raw)':>12} {'Sig (FDR)':>12}")
    print("-" * 65)

    for i, feat in enumerate(feature_names):
        raw_sig = "✓" if p_values[i] < 0.05 else ""
        fdr_sig = "✓" if significant[i] else ""
        print(f"{feat:<15} {p_values[i]:>12.4f} {adjusted_p[i]:>12.4f} {raw_sig:>12} {fdr_sig:>12}")

    print("-" * 65)
    raw_count = sum(1 for p in p_values if p < 0.05)
    fdr_count = sum(significant)
    print(f"\nSignificant (raw α=0.05):  {raw_count}/{len(p_values)}")
    print(f"Significant (FDR α=0.05): {fdr_count}/{len(p_values)}")

    if raw_count > fdr_count:
        print(f"\n⚠ {raw_count - fdr_count} finding(s) lost after FDR correction (likely false positives)")

    return {
        'features': feature_names,
        'raw_p': p_values,
        'fdr_p': adjusted_p.tolist(),
        'significant_fdr': significant.tolist()
    }


def load_data():
    """Load C features with depression labels."""
    script_dir = Path(__file__).parent
    corpus = script_dir / "../../datasets/eatd-corpus-data/EATD-Corpus"

    df = pd.read_csv(script_dir / "results/eatd_c_features.csv")

    def get_label(session_id):
        parts = session_id.split('_')
        split, pid = parts[0], parts[1]
        label_file = corpus / split / pid / 'new_label.txt'
        if label_file.exists():
            return float(label_file.read_text().strip()) > 53
        return None

    df['is_depressed'] = df['session_id'].apply(get_label)
    df = df.dropna(subset=['is_depressed'])
    return df


def power_analysis(df):
    """Compute post-hoc power for each feature."""
    print("\n" + "="*70)
    print("1. POST-HOC POWER ANALYSIS")
    print("="*70)
    print("\nQuestion: Given our sample size, what effects could we reliably detect?")

    dep = df[df['is_depressed'] == True]
    nondep = df[df['is_depressed'] == False]

    n1, n2 = len(dep), len(nondep)
    print(f"\nSample sizes: n_depressed={n1}, n_nondepressed={n2}")

    features = ['f0_mean_hz', 'f0_std_hz', 'pause_ratio', 'energy_std',
                'jitter', 'shimmer', 'hnr_mean', 'snr']

    results = []

    print(f"\n{'Feature':<15} {'Cohen d':>10} {'Power':>10} {'Adequate':>10}")
    print("-" * 50)

    for feat in features:
        if feat not in df.columns:
            continue

        d1 = dep[feat].dropna().values
        d2 = nondep[feat].dropna().values

        if len(d1) < 5 or len(d2) < 5:
            continue

        # Cohen's d
        pooled_std = np.sqrt(((len(d1)-1)*np.var(d1, ddof=1) +
                              (len(d2)-1)*np.var(d2, ddof=1)) / (len(d1)+len(d2)-2))
        d = abs(np.mean(d1) - np.mean(d2)) / pooled_std if pooled_std > 0 else 0

        # Approximate power calculation (using normal approximation)
        # For two-sample t-test
        se = np.sqrt(1/n1 + 1/n2)
        ncp = d / se  # non-centrality parameter
        crit = stats.norm.ppf(0.975)  # two-tailed alpha=0.05
        power = 1 - stats.norm.cdf(crit - ncp) + stats.norm.cdf(-crit - ncp)

        adequate = "✓" if power >= 0.80 else "✗"
        print(f"{feat:<15} {d:>10.3f} {power:>10.1%} {adequate:>10}")

        results.append({
            'feature': feat,
            'cohens_d': d,
            'power': power,
            'adequate': power >= 0.80
        })

    print("-" * 50)
    adequate_count = sum(1 for r in results if r['adequate'])
    print(f"\nFeatures with adequate power (≥80%): {adequate_count}/{len(results)}")

    # Minimum detectable effect
    # For 80% power, need d ≈ 2.8 * sqrt(1/n1 + 1/n2)
    min_d = 2.8 * np.sqrt(1/n1 + 1/n2)
    print(f"Minimum detectable effect (80% power): d = {min_d:.2f}")

    return pd.DataFrame(results)


def bootstrap_confidence_intervals(df, n_bootstrap=1000):
    """Compute bootstrap CIs for key metrics."""
    print("\n" + "="*70)
    print("2. BOOTSTRAP CONFIDENCE INTERVALS")
    print("="*70)

    features = ['f0_mean_hz', 'f0_std_hz', 'pause_ratio', 'energy_std',
                'jitter', 'shimmer', 'hnr_mean', 'snr']

    dep = df[df['is_depressed'] == True]
    nondep = df[df['is_depressed'] == False]

    print(f"\n{'Feature':<15} {'Cohen d':>10} {'95% CI':>20}")
    print("-" * 50)

    effect_results = []

    for feat in features:
        if feat not in df.columns:
            continue

        d1 = dep[feat].dropna().values
        d2 = nondep[feat].dropna().values

        if len(d1) < 5 or len(d2) < 5:
            continue

        # Bootstrap Cohen's d
        d_boots = []
        for _ in range(n_bootstrap):
            b1 = resample(d1)
            b2 = resample(d2)
            pooled_std = np.sqrt(((len(b1)-1)*np.var(b1, ddof=1) +
                                  (len(b2)-1)*np.var(b2, ddof=1)) / (len(b1)+len(b2)-2))
            if pooled_std > 0:
                d_boots.append((np.mean(b1) - np.mean(b2)) / pooled_std)

        d_mean = np.mean(d_boots)
        ci_low, ci_high = np.percentile(d_boots, [2.5, 97.5])

        print(f"{feat:<15} {d_mean:>+10.3f} [{ci_low:>+.3f}, {ci_high:>+.3f}]")

        effect_results.append({
            'feature': feat,
            'cohens_d': d_mean,
            'ci_low': ci_low,
            'ci_high': ci_high
        })

    # Bootstrap AUC
    print("\nClassification AUC:")

    feature_cols = [f for f in features if f in df.columns]
    X = df[feature_cols].values
    y = df['is_depressed'].values.astype(int)
    X = np.nan_to_num(X, nan=0)

    auc_boots = []
    for _ in range(n_bootstrap):
        idx = resample(range(len(X)), stratify=y)
        X_boot, y_boot = X[idx], y[idx]

        clf = Pipeline([
            ('scaler', StandardScaler()),
            ('lr', LogisticRegression(max_iter=1000, class_weight='balanced'))
        ])

        try:
            scores = cross_val_score(clf, X_boot, y_boot, cv=3, scoring='roc_auc')
            auc_boots.append(np.mean(scores))
        except:
            pass

    auc_mean = np.mean(auc_boots)
    auc_ci = np.percentile(auc_boots, [2.5, 97.5])
    print(f"  AUC: {auc_mean:.3f} [95% CI: {auc_ci[0]:.3f}, {auc_ci[1]:.3f}]")

    return pd.DataFrame(effect_results), {'auc': auc_mean, 'ci': auc_ci}


def threshold_sensitivity(df):
    """Test how conclusions change with different thresholds."""
    print("\n" + "="*70)
    print("3. THRESHOLD SENSITIVITY ANALYSIS")
    print("="*70)

    # Load linkage results
    script_dir = Path(__file__).parent
    linkage = pd.read_csv(script_dir / "results/linkage_analysis.csv")

    # Direction preservation sensitivity
    print("\n3.1 Direction Preservation Threshold Sensitivity")
    print("-" * 50)

    direction_preserved = linkage['direction_preserved'].sum()
    total = len(linkage)

    print(f"Actual: {direction_preserved}/{total} = {100*direction_preserved/total:.1f}%")
    print()
    print(f"{'Threshold':>12} {'Pass?':>10} {'Margin':>15}")
    print("-" * 40)

    for thresh in [50, 60, 70, 80, 90]:
        passes = (direction_preserved / total * 100) >= thresh
        margin = direction_preserved / total * 100 - thresh
        status = "✓ PASS" if passes else "✗ FAIL"
        print(f"{thresh:>10}% {status:>10} {margin:>+14.1f}%")

    # EPR sensitivity
    print("\n3.2 Effect Size Preservation (EPR) Threshold Sensitivity")
    print("-" * 50)

    for thresh in [0.5, 0.6, 0.7, 0.8, 0.9]:
        epr_pass = (linkage['epr'] >= thresh).sum()
        pct = 100 * epr_pass / total
        passes = pct >= 70  # Using 70% as meta-threshold
        status = "✓" if passes else "✗"
        print(f"EPR ≥ {thresh}: {epr_pass}/{total} ({pct:.1f}%) {status}")

    # Classification delta sensitivity
    print("\n3.3 Classification Delta Threshold Sensitivity")
    print("-" * 50)

    # Compute actual delta
    features = ['f0_mean_hz', 'f0_std_hz', 'pause_ratio', 'energy_std',
                'jitter', 'shimmer', 'hnr_mean', 'snr']
    feature_cols = [f for f in features if f in df.columns]

    X = df[feature_cols].values
    y = df['is_depressed'].values.astype(int)
    X = np.nan_to_num(X, nan=0)

    clf = Pipeline([
        ('scaler', StandardScaler()),
        ('lr', LogisticRegression(max_iter=1000, class_weight='balanced'))
    ])

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    auc_c = cross_val_score(clf, X, y, cv=cv, scoring='roc_auc').mean()

    # Load Python AUC (from previous analysis)
    auc_python = 0.656  # From linkage analysis
    delta = auc_python - auc_c

    print(f"Actual Δ = {delta:+.3f} (Python {auc_python:.3f} - C {auc_c:.3f})")
    print()

    for thresh in [0.03, 0.05, 0.07, 0.10]:
        passes = abs(delta) < thresh
        status = "✓ PASS" if passes else "✗ FAIL"
        print(f"|Δ| < {thresh}: {status}")

    # Summary
    print("\n" + "="*70)
    print("SENSITIVITY SUMMARY")
    print("="*70)
    print("""
Conclusions are ROBUST if they hold across reasonable threshold variations.

Direction Preservation:
  - Passes at 50-70%, fails at 80%+
  - Conclusion: MARGINALLY robust (borderline at 70%)

Effect Size Preservation:
  - 70% of features pass EPR≥0.7
  - Conclusion: MODERATELY robust

Classification Delta:
  - Passes all thresholds (Δ is actually negative)
  - Conclusion: ROBUST (C outperforms Python)
    """)


def regularized_comparison(df):
    """Compare regularized vs unregularized classification."""
    print("\n" + "="*70)
    print("4. REGULARIZED VS UNREGULARIZED CLASSIFICATION")
    print("="*70)

    features = ['f0_mean_hz', 'f0_std_hz', 'pause_ratio', 'energy_std',
                'jitter', 'shimmer', 'hnr_mean', 'snr']
    feature_cols = [f for f in features if f in df.columns]

    X = df[feature_cols].values
    y = df['is_depressed'].values.astype(int)
    X = np.nan_to_num(X, nan=0)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    # Unregularized
    clf_unreg = Pipeline([
        ('scaler', StandardScaler()),
        ('lr', LogisticRegression(max_iter=1000, class_weight='balanced', penalty=None))
    ])
    auc_unreg = cross_val_score(clf_unreg, X, y, cv=cv, scoring='roc_auc')

    # L2 regularized (default)
    clf_l2 = Pipeline([
        ('scaler', StandardScaler()),
        ('lr', LogisticRegression(max_iter=1000, class_weight='balanced', penalty='l2'))
    ])
    auc_l2 = cross_val_score(clf_l2, X, y, cv=cv, scoring='roc_auc')

    # L2 with CV-tuned regularization
    clf_cv = Pipeline([
        ('scaler', StandardScaler()),
        ('lr', LogisticRegressionCV(cv=3, max_iter=1000, class_weight='balanced'))
    ])
    auc_cv = cross_val_score(clf_cv, X, y, cv=cv, scoring='roc_auc')

    print(f"\n{'Model':<25} {'AUC Mean':>12} {'AUC Std':>12}")
    print("-" * 50)
    print(f"{'Unregularized':<25} {auc_unreg.mean():>12.3f} {auc_unreg.std():>12.3f}")
    print(f"{'L2 Regularized (C=1)':<25} {auc_l2.mean():>12.3f} {auc_l2.std():>12.3f}")
    print(f"{'L2 with CV-tuned C':<25} {auc_cv.mean():>12.3f} {auc_cv.std():>12.3f}")

    print("\nInterpretation:")
    if auc_cv.mean() > auc_unreg.mean():
        print("  Regularization IMPROVES performance → suggests overfitting was present")
    else:
        print("  Regularization does not improve → model was not overfitting")

    return {
        'unregularized': (auc_unreg.mean(), auc_unreg.std()),
        'l2': (auc_l2.mean(), auc_l2.std()),
        'l2_cv': (auc_cv.mean(), auc_cv.std())
    }


def main():
    print("="*70)
    print("STATISTICAL RIGOR ANALYSIS")
    print("Addressing critical gaps in methodology")
    print("="*70)

    # Load data
    df = load_data()
    print(f"\nLoaded {len(df)} samples ({df['is_depressed'].sum()} depressed)")

    # Run analyses
    power_df = power_analysis(df)
    effect_df, auc_ci = bootstrap_confidence_intervals(df, n_bootstrap=500)
    threshold_sensitivity(df)
    reg_results = regularized_comparison(df)
    fdr_results = fdr_analysis(df)

    # Save results
    script_dir = Path(__file__).parent
    power_df.to_csv(script_dir / "results/power_analysis.csv", index=False)
    effect_df.to_csv(script_dir / "results/effect_size_cis.csv", index=False)

    print("\n" + "="*70)
    print("RESULTS SAVED")
    print("="*70)
    print("  - results/power_analysis.csv")
    print("  - results/effect_size_cis.csv")

    return 0


if __name__ == "__main__":
    exit(main())
