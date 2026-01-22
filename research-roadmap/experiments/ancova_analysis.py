#!/usr/bin/env python3
"""
ANCOVA Analysis: Controlling for Gender Confound

This script performs Analysis of Covariance (ANCOVA) to properly estimate
the effect of depression on acoustic features while controlling for gender.

Key question: After controlling for gender, is there still a significant
relationship between depression and acoustic features?
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats
import statsmodels.api as sm
from statsmodels.formula.api import ols
from statsmodels.stats.anova import anova_lm
import warnings
warnings.filterwarnings('ignore')


def load_daic_with_demographics():
    """Load DAIC-WOZ features with gender labels."""
    script_dir = Path(__file__).parent

    # Load features
    features_path = script_dir / "results/daic_woz_baseline_features.csv"
    if not features_path.exists():
        print(f"Error: {features_path} not found")
        return None

    features_df = pd.read_csv(features_path)

    # Load labels with demographics
    labels_path = script_dir / "../../datasets/DepressionEstimation/daic_woz_preprocessing/Excel for splitting data/complete_Depression_AVEC2017.csv"
    if not labels_path.exists():
        print(f"Error: {labels_path} not found")
        return None

    labels_df = pd.read_csv(labels_path)

    # Merge
    features_df['Participant_ID'] = features_df['session_id'].astype(int)
    df = features_df.merge(
        labels_df[['Participant_ID', 'PHQ8_Binary', 'PHQ8_Score', 'Gender']],
        on='Participant_ID', how='inner'
    )

    df['is_depressed'] = df['PHQ8_Binary'] == 1
    df['gender'] = df['Gender'].map({0: 'Female', 1: 'Male'})
    df['gender_code'] = df['Gender']  # 0=Female, 1=Male

    return df


def run_ancova(df, feature, group_var='is_depressed', covariate='gender_code'):
    """
    Run ANCOVA for a single feature.

    Model: feature ~ depression + gender

    Returns dict with:
    - F statistic and p-value for depression effect (controlling for gender)
    - Adjusted means for depressed/non-depressed
    - Effect size (partial eta squared)
    """
    # Remove NaN
    subset = df[[feature, group_var, covariate]].dropna()
    if len(subset) < 10:
        return None

    # Fit ANCOVA model
    formula = f'{feature} ~ C({group_var}) + {covariate}'
    try:
        model = ols(formula, data=subset).fit()
        anova_table = anova_lm(model, typ=2)
    except Exception as e:
        print(f"Error fitting ANCOVA for {feature}: {e}")
        return None

    # Extract depression effect (controlling for gender)
    if f'C({group_var})' not in anova_table.index:
        return None

    dep_row = anova_table.loc[f'C({group_var})']
    gender_row = anova_table.loc[covariate]
    residual_row = anova_table.loc['Residual']

    # Partial eta squared for depression effect
    ss_dep = dep_row['sum_sq']
    ss_residual = residual_row['sum_sq']
    partial_eta_sq = ss_dep / (ss_dep + ss_residual)

    # Adjusted means (marginal means controlling for covariate)
    # Using the model to predict at mean covariate value
    mean_covariate = subset[covariate].mean()

    adj_mean_dep = model.params['Intercept'] + model.params[f'C({group_var})[T.True]'] + model.params[covariate] * mean_covariate
    adj_mean_nondep = model.params['Intercept'] + model.params[covariate] * mean_covariate

    # Raw means for comparison
    raw_mean_dep = subset[subset[group_var] == True][feature].mean()
    raw_mean_nondep = subset[subset[group_var] == False][feature].mean()

    # Compute adjusted Cohen's d
    pooled_std = np.sqrt(ss_residual / (len(subset) - 3))  # df = n - 3 for ANCOVA
    if pooled_std > 1e-10:
        adj_cohens_d = (adj_mean_dep - adj_mean_nondep) / pooled_std
    else:
        adj_cohens_d = 0.0

    return {
        'feature': feature,
        'n': len(subset),
        'F_depression': dep_row['F'],
        'p_depression': dep_row['PR(>F)'],
        'F_gender': gender_row['F'],
        'p_gender': gender_row['PR(>F)'],
        'partial_eta_sq': partial_eta_sq,
        'adj_cohens_d': adj_cohens_d,
        'raw_mean_dep': raw_mean_dep,
        'raw_mean_nondep': raw_mean_nondep,
        'adj_mean_dep': adj_mean_dep,
        'adj_mean_nondep': adj_mean_nondep,
        'raw_diff': raw_mean_dep - raw_mean_nondep,
        'adj_diff': adj_mean_dep - adj_mean_nondep,
    }


def run_simple_ttest(df, feature, group_var='is_depressed'):
    """Run simple t-test without controlling for gender (for comparison)."""
    dep = df[df[group_var] == True][feature].dropna()
    nondep = df[df[group_var] == False][feature].dropna()

    if len(dep) < 5 or len(nondep) < 5:
        return None

    t, p = stats.ttest_ind(dep, nondep)

    # Cohen's d
    pooled_std = np.sqrt(((len(dep)-1)*np.var(dep, ddof=1) +
                          (len(nondep)-1)*np.var(nondep, ddof=1)) /
                         (len(dep) + len(nondep) - 2))

    if pooled_std > 1e-10:
        d = (dep.mean() - nondep.mean()) / pooled_std
    else:
        d = 0.0

    return {
        'feature': feature,
        't': t,
        'p': p,
        'cohens_d': d,
        'mean_dep': dep.mean(),
        'mean_nondep': nondep.mean(),
    }


def main():
    print("="*80)
    print("ANCOVA ANALYSIS: CONTROLLING FOR GENDER CONFOUND")
    print("="*80)

    # Load DAIC-WOZ with demographics
    print("\nLoading DAIC-WOZ with demographics...")
    df = load_daic_with_demographics()

    if df is None:
        print("Failed to load data")
        return 1

    print(f"Loaded {len(df)} samples")
    print(f"  Depressed: {df['is_depressed'].sum()}")
    print(f"  Non-depressed: {(~df['is_depressed']).sum()}")
    print(f"  Female: {(df['gender'] == 'Female').sum()}")
    print(f"  Male: {(df['gender'] == 'Male').sum()}")

    # Gender distribution by depression status
    print("\n## Gender Distribution by Depression Status")
    print("-" * 60)

    dep_female = ((df['is_depressed']) & (df['gender'] == 'Female')).sum()
    dep_male = ((df['is_depressed']) & (df['gender'] == 'Male')).sum()
    nondep_female = ((~df['is_depressed']) & (df['gender'] == 'Female')).sum()
    nondep_male = ((~df['is_depressed']) & (df['gender'] == 'Male')).sum()

    print(f"Depressed:     {dep_female} Female ({100*dep_female/(dep_female+dep_male):.1f}%), "
          f"{dep_male} Male ({100*dep_male/(dep_female+dep_male):.1f}%)")
    print(f"Non-depressed: {nondep_female} Female ({100*nondep_female/(nondep_female+nondep_male):.1f}%), "
          f"{nondep_male} Male ({100*nondep_male/(nondep_female+nondep_male):.1f}%)")

    # Chi-square test
    from scipy.stats import chi2_contingency
    chi2, p_chi, _, _ = chi2_contingency([[dep_female, dep_male], [nondep_female, nondep_male]])
    print(f"\nChi-square test for gender imbalance: χ²={chi2:.2f}, p={p_chi:.4f}")

    if p_chi < 0.05:
        print("*** SIGNIFICANT GENDER IMBALANCE - ANCOVA REQUIRED ***")

    # Features to analyze
    features = ['f0_mean_hz', 'f0_std_hz', 'pause_ratio', 'energy_std',
                'jitter', 'shimmer', 'hnr_mean', 'snr']
    features = [f for f in features if f in df.columns]

    # Run analyses
    print("\n" + "="*80)
    print("COMPARISON: UNADJUSTED vs GENDER-ADJUSTED EFFECTS")
    print("="*80)

    print(f"\n{'Feature':<15} {'Unadj d':>10} {'Unadj p':>10} {'Adj d':>10} {'Adj p':>10} {'Change':>10} {'Interpretation':<20}")
    print("-" * 95)

    results = []

    for feature in features:
        # Unadjusted (simple t-test)
        unadj = run_simple_ttest(df, feature)

        # Adjusted (ANCOVA)
        adj = run_ancova(df, feature)

        if unadj is None or adj is None:
            continue

        # Determine interpretation
        unadj_d = unadj['cohens_d']
        adj_d = adj['adj_cohens_d']

        change = adj_d - unadj_d

        if abs(change) < 0.1:
            interpretation = "Stable"
        elif change > 0.1:
            interpretation = "↑ Effect increased"
        elif change < -0.1:
            interpretation = "↓ Effect reduced"

        if np.sign(unadj_d) != np.sign(adj_d) and abs(adj_d) > 0.1:
            interpretation = "⚠ DIRECTION REVERSED"

        print(f"{feature:<15} {unadj_d:>+10.3f} {unadj['p']:>10.4f} {adj_d:>+10.3f} {adj['p_depression']:>10.4f} {change:>+10.3f} {interpretation:<20}")

        results.append({
            'feature': feature,
            'unadj_d': unadj_d,
            'unadj_p': unadj['p'],
            'adj_d': adj_d,
            'adj_p': adj['p_depression'],
            'change': change,
            'interpretation': interpretation,
            'partial_eta_sq': adj['partial_eta_sq'],
            'raw_mean_dep': adj['raw_mean_dep'],
            'raw_mean_nondep': adj['raw_mean_nondep'],
            'adj_mean_dep': adj['adj_mean_dep'],
            'adj_mean_nondep': adj['adj_mean_nondep'],
        })

    # Focus on F0 (the key finding)
    print("\n" + "="*80)
    print("KEY FINDING: F0 AFTER GENDER ADJUSTMENT")
    print("="*80)

    f0_result = next((r for r in results if r['feature'] == 'f0_mean_hz'), None)

    if f0_result:
        print(f"""
Before Gender Adjustment (CONFOUNDED):
  - Depressed F0:     {f0_result['raw_mean_dep']:.1f} Hz
  - Non-depressed F0: {f0_result['raw_mean_nondep']:.1f} Hz
  - Cohen's d:        {f0_result['unadj_d']:+.3f}
  - Direction:        {'HIGHER' if f0_result['unadj_d'] > 0 else 'LOWER'} in depressed

After Gender Adjustment (CORRECTED):
  - Adjusted Dep F0:     {f0_result['adj_mean_dep']:.1f} Hz
  - Adjusted NonDep F0:  {f0_result['adj_mean_nondep']:.1f} Hz
  - Adjusted Cohen's d:  {f0_result['adj_d']:+.3f}
  - Direction:           {'HIGHER' if f0_result['adj_d'] > 0 else 'LOWER'} in depressed
  - p-value:             {f0_result['adj_p']:.4f}

Change: {f0_result['change']:+.3f} ({f0_result['interpretation']})
""")

        if f0_result['interpretation'] == "⚠ DIRECTION REVERSED":
            print("*** SIMPSON'S PARADOX CONFIRMED ***")
            print("The aggregated 'higher F0 in depressed' was entirely due to gender imbalance.")
            print("After controlling for gender, F0 is LOWER in depressed (matches literature).")

    # Summary statistics
    print("\n" + "="*80)
    print("SUMMARY: FEATURES SIGNIFICANT AFTER GENDER ADJUSTMENT")
    print("="*80)

    sig_unadj = sum(1 for r in results if r['unadj_p'] < 0.05)
    sig_adj = sum(1 for r in results if r['adj_p'] < 0.05)

    print(f"\nSignificant (p < 0.05):")
    print(f"  Before adjustment: {sig_unadj}/{len(results)} features")
    print(f"  After adjustment:  {sig_adj}/{len(results)} features")

    print(f"\nFeatures significant after gender adjustment:")
    for r in results:
        if r['adj_p'] < 0.05:
            print(f"  - {r['feature']}: d={r['adj_d']:+.3f}, p={r['adj_p']:.4f}")

    # Save results
    script_dir = Path(__file__).parent
    results_df = pd.DataFrame(results)
    results_df.to_csv(script_dir / "results/ancova_results.csv", index=False)
    print(f"\nResults saved to results/ancova_results.csv")

    # Publication-ready table
    print("\n" + "="*80)
    print("PUBLICATION-READY TABLE")
    print("="*80)
    print("""
Table X: Depression effect on acoustic features before and after controlling for gender (DAIC-WOZ, N=89)

| Feature    | Unadjusted d | Unadjusted p | Adjusted d | Adjusted p | η²p   |
|------------|--------------|--------------|------------|------------|-------|""")

    for r in results:
        sig_unadj = "*" if r['unadj_p'] < 0.05 else ""
        sig_adj = "*" if r['adj_p'] < 0.05 else ""
        print(f"| {r['feature']:<10} | {r['unadj_d']:>+11.3f}{sig_unadj} | {r['unadj_p']:>11.4f} | {r['adj_d']:>+9.3f}{sig_adj} | {r['adj_p']:>9.4f} | {r['partial_eta_sq']:>.4f} |")

    print("""
Note: * p < 0.05. Unadjusted = simple t-test. Adjusted = ANCOVA with gender as covariate.
η²p = partial eta squared (effect size for ANCOVA).
""")

    return 0


if __name__ == "__main__":
    exit(main())
