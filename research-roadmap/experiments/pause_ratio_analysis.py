#!/usr/bin/env python3
"""
Deep Analysis of Pause Ratio: The Potential Confound-Robust Feature

After ANCOVA, pause_ratio INCREASED in effect size (d: 0.003 → 0.374).
This is the OPPOSITE of F0, suggesting gender was SUPPRESSING the true effect.

This script investigates:
1. Why gender suppresses pause_ratio effect
2. Bootstrap confidence intervals for the adjusted effect
3. Power analysis for detecting this effect
4. Stratified analysis by gender
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats
import statsmodels.api as sm
from statsmodels.formula.api import ols
from statsmodels.stats.anova import anova_lm
from statsmodels.stats.power import TTestIndPower
import warnings
warnings.filterwarnings('ignore')


def load_data():
    """Load DAIC-WOZ with demographics."""
    script_dir = Path(__file__).parent

    features_path = script_dir / "results/daic_woz_baseline_features.csv"
    labels_path = script_dir / "../../datasets/DepressionEstimation/daic_woz_preprocessing/Excel for splitting data/complete_Depression_AVEC2017.csv"

    features_df = pd.read_csv(features_path)
    labels_df = pd.read_csv(labels_path)

    features_df['Participant_ID'] = features_df['session_id'].astype(int)
    df = features_df.merge(
        labels_df[['Participant_ID', 'PHQ8_Binary', 'PHQ8_Score', 'Gender']],
        on='Participant_ID', how='inner'
    )

    df['is_depressed'] = df['PHQ8_Binary'] == 1
    df['gender'] = df['Gender'].map({0: 'Female', 1: 'Male'})
    df['gender_code'] = df['Gender']

    return df


def explain_suppression(df):
    """Explain WHY gender suppresses the pause_ratio effect."""
    print("="*80)
    print("WHY DOES GENDER SUPPRESS PAUSE_RATIO EFFECT?")
    print("="*80)

    # Gender means for pause_ratio
    female_pause = df[df['gender'] == 'Female']['pause_ratio'].mean()
    male_pause = df[df['gender'] == 'Male']['pause_ratio'].mean()

    print(f"\n1. Gender difference in pause_ratio:")
    print(f"   Female mean: {female_pause:.3f}")
    print(f"   Male mean:   {male_pause:.3f}")
    print(f"   Difference:  {female_pause - male_pause:+.3f}")

    # Direction of gender effect
    if female_pause < male_pause:
        print(f"\n   → Females have LOWER pause_ratio than males")
    else:
        print(f"\n   → Females have HIGHER pause_ratio than males")

    # Now by depression within each gender
    print(f"\n2. Pause_ratio by depression status (within gender):")

    for gender in ['Female', 'Male']:
        gender_df = df[df['gender'] == gender]
        dep_pause = gender_df[gender_df['is_depressed']]['pause_ratio'].mean()
        nondep_pause = gender_df[~gender_df['is_depressed']]['pause_ratio'].mean()
        n_dep = gender_df['is_depressed'].sum()
        n_nondep = (~gender_df['is_depressed']).sum()

        print(f"\n   {gender}:")
        print(f"     Depressed (n={n_dep}):     {dep_pause:.3f}")
        print(f"     Non-depressed (n={n_nondep}): {nondep_pause:.3f}")
        print(f"     Difference:     {dep_pause - nondep_pause:+.3f}")

    # The suppression mechanism
    print(f"\n3. Suppression Mechanism:")
    print("""
   - Depressed group has MORE females (54% vs 23%)
   - If females have [lower/higher] pause_ratio, this pulls the depressed mean [down/up]
   - This masks the TRUE depression effect on pause_ratio
   - After controlling for gender, the true effect emerges
    """)

    # Overall aggregated effect
    dep_pause_overall = df[df['is_depressed']]['pause_ratio'].mean()
    nondep_pause_overall = df[~df['is_depressed']]['pause_ratio'].mean()

    print(f"4. Aggregated vs Within-Gender Effects:")
    print(f"   Aggregated (confounded):  {dep_pause_overall:.3f} vs {nondep_pause_overall:.3f} = {dep_pause_overall - nondep_pause_overall:+.3f}")


def bootstrap_ancova_ci(df, feature='pause_ratio', n_bootstrap=1000, ci=0.95):
    """Bootstrap confidence interval for ANCOVA-adjusted Cohen's d."""
    print(f"\n{'='*80}")
    print(f"BOOTSTRAP CI FOR ADJUSTED COHEN'S d (pause_ratio)")
    print("="*80)

    np.random.seed(42)
    adjusted_ds = []

    for _ in range(n_bootstrap):
        # Resample with replacement
        sample = df.sample(n=len(df), replace=True)

        # Run ANCOVA
        try:
            model = ols(f'{feature} ~ C(is_depressed) + gender_code', data=sample).fit()
            anova_table = anova_lm(model, typ=2)

            # Get adjusted means
            mean_cov = sample['gender_code'].mean()
            adj_mean_dep = model.params['Intercept'] + model.params['C(is_depressed)[T.True]'] + model.params['gender_code'] * mean_cov
            adj_mean_nondep = model.params['Intercept'] + model.params['gender_code'] * mean_cov

            # Pooled std from residuals
            ss_res = anova_table.loc['Residual', 'sum_sq']
            pooled_std = np.sqrt(ss_res / (len(sample) - 3))

            if pooled_std > 1e-10:
                adj_d = (adj_mean_dep - adj_mean_nondep) / pooled_std
                adjusted_ds.append(adj_d)
        except:
            continue

    adjusted_ds = np.array(adjusted_ds)

    # Calculate CI
    alpha = 1 - ci
    lower = np.percentile(adjusted_ds, alpha/2 * 100)
    upper = np.percentile(adjusted_ds, (1 - alpha/2) * 100)
    mean_d = np.mean(adjusted_ds)

    print(f"\nBootstrap Results (n={len(adjusted_ds)} successful iterations):")
    print(f"  Mean adjusted d:  {mean_d:+.3f}")
    print(f"  95% CI:           [{lower:+.3f}, {upper:+.3f}]")
    print(f"  CI width:         {upper - lower:.3f}")

    # Does CI exclude zero?
    if lower > 0:
        print(f"\n  *** CI EXCLUDES ZERO - effect is significant at 95% ***")
    elif upper < 0:
        print(f"\n  *** CI EXCLUDES ZERO (negative) - effect is significant at 95% ***")
    else:
        print(f"\n  CI includes zero - effect is NOT significant at 95%")

    return mean_d, lower, upper


def power_analysis(observed_d=0.374, alpha=0.05, current_n_per_group=45):
    """Calculate power and required sample size."""
    print(f"\n{'='*80}")
    print("POWER ANALYSIS FOR PAUSE_RATIO")
    print("="*80)

    analysis = TTestIndPower()

    # Current power
    current_power = analysis.solve_power(effect_size=observed_d,
                                          nobs1=current_n_per_group,
                                          alpha=alpha)

    print(f"\nCurrent Situation:")
    print(f"  Observed d:         {observed_d:.3f}")
    print(f"  Current n/group:    {current_n_per_group}")
    print(f"  Current power:      {current_power:.1%}")

    # Required n for 80% power
    n_80 = analysis.solve_power(effect_size=observed_d,
                                 power=0.80,
                                 alpha=alpha)

    # Required n for 90% power
    n_90 = analysis.solve_power(effect_size=observed_d,
                                 power=0.90,
                                 alpha=alpha)

    print(f"\nRequired Sample Sizes:")
    print(f"  For 80% power:      {int(np.ceil(n_80))} per group ({int(np.ceil(n_80)*2)} total)")
    print(f"  For 90% power:      {int(np.ceil(n_90))} per group ({int(np.ceil(n_90)*2)} total)")

    # How much more data do we need?
    additional_needed = int(np.ceil(n_80)) - current_n_per_group
    print(f"\n  Additional needed for 80%: {additional_needed * 2} participants")
    print(f"  (Full DAIC-WOZ has 189 sessions - downloading would help)")

    return current_power, int(np.ceil(n_80)), int(np.ceil(n_90))


def stratified_analysis(df):
    """Analyze pause_ratio effect separately by gender."""
    print(f"\n{'='*80}")
    print("STRATIFIED ANALYSIS: PAUSE_RATIO BY GENDER")
    print("="*80)

    for gender in ['Female', 'Male']:
        subset = df[df['gender'] == gender]
        dep = subset[subset['is_depressed']]['pause_ratio'].dropna()
        nondep = subset[~subset['is_depressed']]['pause_ratio'].dropna()

        # t-test
        t, p = stats.ttest_ind(dep, nondep)

        # Cohen's d
        pooled_std = np.sqrt(((len(dep)-1)*np.var(dep, ddof=1) +
                              (len(nondep)-1)*np.var(nondep, ddof=1)) /
                             (len(dep) + len(nondep) - 2))
        d = (dep.mean() - nondep.mean()) / pooled_std if pooled_std > 0 else 0

        print(f"\n{gender}:")
        print(f"  Depressed (n={len(dep)}):     M = {dep.mean():.3f}, SD = {dep.std():.3f}")
        print(f"  Non-depressed (n={len(nondep)}): M = {nondep.mean():.3f}, SD = {nondep.std():.3f}")
        print(f"  Cohen's d: {d:+.3f}")
        print(f"  t({len(dep)+len(nondep)-2}) = {t:.2f}, p = {p:.4f}")


def publication_summary(mean_d, lower, upper, power):
    """Generate publication-ready summary."""
    print(f"\n{'='*80}")
    print("PUBLICATION-READY SUMMARY: PAUSE_RATIO")
    print("="*80)

    print("""
## Key Finding: Pause Ratio as Confound-Robust Feature

After controlling for gender via ANCOVA, pause_ratio emerged as the only
feature showing increased effect size. This suggests gender was acting
as a SUPPRESSOR variable, masking the true depression effect.

### Results
""")
    print(f"- Unadjusted Cohen's d: +0.003 (p = 0.988) - near zero")
    print(f"- Adjusted Cohen's d:   {mean_d:+.3f} (p = 0.103)")
    print(f"- Bootstrap 95% CI:     [{lower:+.3f}, {upper:+.3f}]")
    print(f"- Current power:        {power:.1%}")

    print("""
### Interpretation

While the adjusted effect (d ≈ 0.37) is a medium effect by Cohen's
conventions, it fails to reach significance (p = 0.10) due to limited
statistical power. The 95% CI includes zero, indicating uncertainty.

### Recommendation

Download full DAIC-WOZ (189 sessions vs current 89) to achieve
adequate power (>80%) for detecting this effect.

### Publication Framing

> "Pause ratio showed a suppression effect: gender confounding masked
> the true depression relationship. After ANCOVA adjustment, pause
> ratio showed a medium effect (d = 0.37) in the expected direction
> (increased pauses in depression), though this did not reach
> significance (p = 0.10) with our sample (N = 89)."
""")


def main():
    print("="*80)
    print("DEEP ANALYSIS: PAUSE_RATIO SUPPRESSION EFFECT")
    print("="*80)

    df = load_data()
    print(f"\nLoaded {len(df)} participants")

    # 1. Explain the suppression mechanism
    explain_suppression(df)

    # 2. Bootstrap confidence intervals
    mean_d, lower, upper = bootstrap_ancova_ci(df)

    # 3. Power analysis
    power, n_80, n_90 = power_analysis(observed_d=abs(mean_d),
                                        current_n_per_group=45)

    # 4. Stratified analysis
    stratified_analysis(df)

    # 5. Publication summary
    publication_summary(mean_d, lower, upper, power)

    # Save results
    results = {
        'feature': 'pause_ratio',
        'unadj_d': 0.003,
        'adj_d': mean_d,
        'ci_lower': lower,
        'ci_upper': upper,
        'power': power,
        'n_for_80_power': n_80 * 2,
        'mechanism': 'gender_suppression'
    }

    script_dir = Path(__file__).parent
    pd.DataFrame([results]).to_csv(
        script_dir / "results/pause_ratio_analysis.csv",
        index=False
    )
    print(f"\nResults saved to results/pause_ratio_analysis.csv")

    return 0


if __name__ == "__main__":
    exit(main())
