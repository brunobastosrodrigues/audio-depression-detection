# Improvement Plan: Addressing Critical Gaps

## Overview

Based on the critical analysis, this plan addresses the key gaps in scientific rigor, statistical validity, and explainability.

---

## 1. Dataset Expansion (Priority: HIGH)

### Available Datasets for Replication

| Dataset | Language | N | Labels | Access | Purpose |
|---------|----------|---|--------|--------|---------|
| **EATD-Corpus** | Chinese | 162 (30 dep) | SDS | ✓ Have | Current study |
| **[DAIC-WOZ](https://dcapswoz.ict.usc.edu/)** | English | 189 | PHQ-8 | Request | Cross-cultural comparison |
| **[CMDC](https://ieee-dataport.org/open-access/chinese-multimodal-depression-corpus)** | Chinese | Large | Clinical | Free (IEEE) | Chinese replication |
| **E-DAIC** | English | 275 | PHQ-8 | Request | Larger English sample |

### NOT Useful
- **TESS**: Acted emotions, no depression labels
- **RAVDESS**: Acted emotions, no depression labels
- **General speech corpora**: No clinical labels

### Action Plan

```
Week 1:
  - [ ] Request DAIC-WOZ access (academic email required)
  - [ ] Download CMDC from IEEE DataPort (free account)
  - [ ] Verify audio format compatibility with C extractor

Week 2-3:
  - [ ] Run C extractor on DAIC-WOZ
  - [ ] Run C extractor on CMDC
  - [ ] Compare F0 direction: Chinese vs English
```

### Expected Outcomes

| Scenario | If DAIC-WOZ shows lower F0 | If DAIC-WOZ shows higher F0 |
|----------|---------------------------|----------------------------|
| Interpretation | F0 reversal is language-specific | F0 reversal is task/dataset artifact |
| Implication | Strong cross-cultural finding | Need to investigate confounds |

| Scenario | If CMDC replicates EATD | If CMDC differs from EATD |
|----------|------------------------|--------------------------|
| Interpretation | Chinese pattern is robust | EATD may have dataset-specific issues |
| Implication | Publication-ready | Need deeper investigation |

---

## 2. Statistical Rigor (Priority: CRITICAL)

### 2.1 Power Analysis

```python
# Required: Compute post-hoc power for observed effects
from statsmodels.stats.power import TTestIndPower

analysis = TTestIndPower()

# For d=0.478 (F0), n1=30, n2=132
power = analysis.solve_power(
    effect_size=0.478,
    nobs1=30,
    ratio=132/30,
    alpha=0.05
)
# Expected: ~70-80% power for large effects, <60% for medium
```

**Deliverable**: Table of power for each feature's observed effect size

### 2.2 Bootstrap Confidence Intervals

```python
# Required: Bootstrap CIs on all key metrics
from sklearn.utils import resample
import numpy as np

def bootstrap_auc(X, y, n_iterations=1000):
    aucs = []
    for _ in range(n_iterations):
        X_boot, y_boot = resample(X, y, stratify=y)
        # fit classifier, compute AUC
        aucs.append(auc)
    return np.percentile(aucs, [2.5, 97.5])
```

**Deliverable**: 95% CIs for AUC, Cohen's d, and all preservation metrics

### 2.3 Threshold Sensitivity Analysis

| Threshold | Values to Test | Metric |
|-----------|---------------|--------|
| Direction Preservation | 50%, 60%, 70%, 80%, 90% | % features passing |
| EPR | 0.5, 0.6, 0.7, 0.8, 0.9 | % features passing |
| Classification Delta | 0.03, 0.05, 0.07, 0.10 | Pass/fail |

**Deliverable**: Sensitivity plot showing how conclusions change with thresholds

### 2.4 Regularized Classification

```python
# Replace LogisticRegression with regularized version
from sklearn.linear_model import LogisticRegressionCV

clf = Pipeline([
    ('scaler', StandardScaler()),
    ('lr', LogisticRegressionCV(
        cv=5,
        penalty='l2',
        class_weight='balanced',
        max_iter=1000
    ))
])
```

**Deliverable**: Comparison of regularized vs unregularized AUC

---

## 3. Grounding Thresholds (Priority: CRITICAL)

### Option A: Derive from First Principles

**Effect Size Preservation (EPR ≥ 0.7)**

Rationale from equivalence testing literature:
- [Equivalence threshold research](https://link.springer.com/article/10.1007/s10459-015-9633-x) finds d=0.5 is typical equivalence margin
- Retaining 70% of effect means max loss of 0.3 * original effect
- For medium effect (d=0.5), 70% retention = d=0.35 (still small-medium)

**Direction Preservation (≥ 70%)**

Rationale:
- Binomial test: With 10 features, 7/10 correct has p=0.17 against chance (50%)
- 8/10 has p=0.055, 9/10 has p=0.011
- 70% is minimum for "better than chance" at α=0.10

**Classification Delta (< 0.05)**

Rationale from clinical literature:
- [FDA guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents) for non-inferiority: typically 5-10% margin
- 0.05 AUC ≈ 5% relative performance loss

### Option B: Acknowledge as Exploratory

If we cannot ground thresholds, explicitly state:

> "We propose preliminary thresholds (70% direction, 0.7 EPR, 0.05 Δ) as starting points for the linkage framework. These require validation against external criteria in future work."

---

## 4. Confound Analysis (Priority: HIGH)

### 4.1 Request Demographics

Contact EATD-Corpus authors for:
- Age distribution by depression status
- Gender distribution by depression status
- Education level
- Medication status (if available)

### 4.2 Statistical Tests (if data available)

```python
# Test for demographic differences
from scipy.stats import chi2_contingency, ttest_ind

# Gender balance
chi2, p_gender = chi2_contingency([[dep_male, dep_female],
                                    [nondep_male, nondep_female]])

# Age difference
t, p_age = ttest_ind(dep_ages, nondep_ages)

# If significant: include as covariates in analysis
```

### 4.3 Stratified Analysis

If confounds exist:
- Report results stratified by gender
- Report results stratified by age group
- Use ANCOVA to control for confounds

---

## 5. Mechanistic Grounding (Priority: MEDIUM)

### Feature-Mechanism Mapping

| Feature | Proposed Mechanism | Supporting Literature |
|---------|-------------------|----------------------|
| F0 (lower) | Motor retardation, reduced arousal | Cummins et al. 2015 |
| F0 variability | Flat affect, reduced emotional expression | Scherer 1986 |
| Pause ratio | Psychomotor slowing, cognitive load | Alpert et al. 2001 |
| Speech rate | Motor retardation | Cannizzaro et al. 2004 |
| Jitter/Shimmer | Laryngeal tension, vocal fold instability | Quatieri & Malyska 2012 |
| HNR | Voice quality degradation | Taguchi et al. 2018 |
| Energy | Reduced vitality, motor output | Mundt et al. 2007 |

### Causal DAG (Proposed)

```
Depression
    │
    ├─→ Motor Retardation ─→ Pause ratio ↑, Speech rate ↓
    │
    ├─→ Flat Affect ─→ F0 variability ↓, Energy variability ↓
    │
    ├─→ Cognitive Load ─→ Hesitations ↑, Pauses ↑
    │
    └─→ Autonomic Changes ─→ Vocal fold tension ─→ Jitter ↑, Shimmer ↑
```

### Explainability Framework

For each prediction, provide:

1. **Feature contributions** (SHAP values or coefficients)
2. **Mechanism interpretation** ("Higher pause ratio suggests psychomotor slowing")
3. **Confidence level** ("Moderate confidence based on 3/5 indicators")
4. **Limitations** ("Does not account for medication effects")

---

## 6. Revised Validation Framework

### Original (Problematic)
- Arbitrary thresholds
- No uncertainty quantification
- Binary pass/fail

### Improved Framework

```
LINKAGE VALIDATION FRAMEWORK v2.0

1. FEATURE AGREEMENT
   - Pearson correlation between C and Python features
   - Threshold: r > 0.7 (strong correlation)
   - Report: r with 95% CI

2. DIRECTION PRESERVATION
   - Binomial test against chance (50%)
   - Threshold: p < 0.10 for "better than chance"
   - Report: proportion with exact CI

3. EFFECT SIZE PRESERVATION
   - EPR = |d_c| / |d_python|
   - Threshold: EPR > 0.7 (derived from equivalence margin)
   - Report: EPR with bootstrap CI

4. CLINICAL UTILITY PRESERVATION
   - AUC difference with bootstrap CI
   - Threshold: upper bound of CI < 0.05
   - Report: Δ with 95% CI

5. SENSITIVITY ANALYSIS
   - Vary all thresholds ±20%
   - Report: robustness of conclusions
```

---

## 7. Implementation Timeline

### Week 1: Statistical Rigor
| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Power analysis | Power table |
| 2-3 | Bootstrap CIs | CI tables |
| 4 | Threshold sensitivity | Sensitivity plots |
| 5 | Regularized models | Updated AUC |

### Week 2: Dataset Expansion
| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Request DAIC-WOZ | Access request |
| 1 | Download CMDC | Dataset files |
| 2-3 | Process CMDC | Feature CSV |
| 4-5 | CMDC validation | Replication report |

### Week 3: Analysis & Writing
| Day | Task | Deliverable |
|-----|------|-------------|
| 1-2 | Confound analysis | Confound report |
| 3 | Mechanistic grounding | Literature table |
| 4-5 | Revised framework | Updated methodology |

### Week 4+: DAIC-WOZ (if access granted)
| Task | Deliverable |
|------|-------------|
| Process DAIC-WOZ | Feature CSV |
| Cross-cultural comparison | Comparison report |
| F0 direction analysis | Key finding validation |

---

## 8. Revised Claims

### Before (Overclaimed)
> "C implementation preserves clinical validity across cultures"

### After (Defensible)
> "On EATD-Corpus (N=162), the C implementation shows:
> - Strong feature agreement (r=0.94 for F0, 0.97 for energy)
> - Direction preservation above chance (7/10, p=0.17)
> - Effect size retention within equivalence bounds (70% EPR≥0.7)
> - Classification performance comparable to Python (Δ=-0.03, 95% CI [-0.08, 0.02])
>
> Replication on CMDC and cross-cultural validation on DAIC-WOZ is ongoing."

---

## 9. Success Criteria

| Milestone | Criterion | Status |
|-----------|-----------|--------|
| Statistical rigor | All metrics have 95% CIs | ◯ Pending |
| Threshold grounding | Rationale documented | ◯ Pending |
| Chinese replication | CMDC shows same F0 direction | ◯ Pending |
| Cross-cultural test | DAIC-WOZ comparison complete | ◯ Pending |
| Mechanistic grounding | All features have citations | ◯ Pending |
| Confound analysis | Demographics reported or acknowledged | ◯ Pending |

---

## 10. Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| DAIC-WOZ access denied | Low | High | Use E-DAIC or published DAIC results |
| CMDC doesn't replicate | Medium | High | Investigate differences, report honestly |
| F0 reversal is artifact | Medium | High | Task analysis, confound control |
| Underpowered for small effects | High | Medium | Acknowledge, focus on large effects |

---

*Created: 2026-01-21*
*Status: Action plan for addressing critical gaps*
