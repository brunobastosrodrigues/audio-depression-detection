# Research Contribution Framework: Clinical Validity of Edge Acoustic Features

## Core Research Question

> When acoustic features are computed under edge device constraints (integer arithmetic, reduced precision, simplified algorithms), do they preserve the statistical relationships with clinical depression outcomes that have been validated in the literature?

## The Linkage Framework

### Definition
The **Feature-Clinical Linkage** is the statistical relationship between an acoustic feature (e.g., F0 variability) and a clinical outcome (e.g., PHQ-8 depression score). This relationship has been established through decades of psychoacoustic research.

### The Problem
Existing validation studies use Python/MATLAB implementations with:
- Float64 precision
- Sophisticated algorithms (Praat autocorrelation, openSMILE)
- Unlimited memory and compute

Edge devices (ESP32-S3) operate with:
- INT16 samples
- Fixed-point or limited float32
- 50KB memory budget
- Simplified algorithms (YIN instead of Praat)

**Key question:** Does the linkage survive these constraints?

---

## Formal Evaluation Protocol

### Metric 1: Direction Preservation

For each feature F and clinical outcome Y:

```
Let r_python = Pearson(F_python, Y)  # Python/cloud implementation
Let r_c = Pearson(F_c, Y)            # C/edge implementation

Direction Preserved iff:
  sign(r_python) == sign(r_c)
```

**Interpretation:** If F0_std correlates negatively with depression in Python (lower F0_std → more depressed), the C implementation should show the same direction.

### Metric 2: Effect Size Preservation

Using Cohen's d for group comparisons:

```
Let d_python = Cohen_d(F_python | depressed, F_python | non-depressed)
Let d_c = Cohen_d(F_c | depressed, F_c | non-depressed)

Effect Preservation Ratio:
  EPR = |d_c| / |d_python|

Acceptable if:
  EPR > 0.7 (at least 70% of discriminative power retained)
```

### Metric 3: Classification Accuracy Delta

Train identical classifier on both feature sets:

```
Let AUC_python = ROC-AUC using Python features
Let AUC_c = ROC-AUC using C features

Accuracy Delta:
  Δ = AUC_python - AUC_c

Acceptable if:
  Δ < 0.05 (less than 5 percentage points drop)
```

### Metric 4: Feature Degradation vs Clinical Impact

Plot the relationship:

```
                 Clinical Impact (EPR)
                        ^
                   1.0 -|----*----*--------
                        |   F0   pause
                   0.7 -|--------*---------  (acceptable threshold)
                        |       HNR
                   0.5 -|
                        |            *
                   0.0 -|          formant
                        +------------------>
                        0%   10%   20%   30%
                        Feature MAPE (divergence)
```

**Key insight:** Some features may have high divergence (MAPE) but still preserve clinical validity. Others may be sensitive.

---

## Datasets for Validation

### Primary: EATD-Corpus
- 162 participants (30 depressed, 132 non-depressed)
- SDS depression scale (threshold: 53)
- Chinese language (tests cross-cultural validity)
- Available: ✓

### Secondary: DAIC-WOZ (if labels obtained)
- 189 sessions with PHQ-8 scores
- English language
- Clinical interview format
- Labels available: Partial (requires AVEC challenge registration)

### Tertiary: Synthetic validation
- Generate audio with known depression markers
- Verify both implementations detect correctly
- Useful for edge case testing

---

## Expected Contributions

### Contribution 1: Linkage Preservation Evidence
Empirical demonstration that edge-constrained features preserve direction and effect size for clinically-relevant acoustic markers.

### Contribution 2: Feature Sensitivity Analysis
Identification of which features are robust to edge constraints (F0 mean) vs sensitive (formants, spectral features).

### Contribution 3: Deployment Guidelines
Recommendations for which features to prioritize in edge deployment based on:
- Memory cost
- Compute cost
- Clinical validity preservation

### Contribution 4: Open-Source Edge Feature Extractor
C implementation validated for clinical use, suitable for ESP32-S3 deployment.

---

## Statistical Rigor Checklist

- [ ] Multiple datasets (EATD-Corpus + DAIC-WOZ)
- [ ] Cross-validation for classifier evaluation
- [ ] Effect size reporting (not just p-values)
- [ ] Confidence intervals for all metrics
- [ ] Bonferroni correction for multiple comparisons
- [ ] Pre-registration of hypotheses (before running analysis)

---

## Null Hypothesis Formulation

For each feature F:

```
H0: The edge implementation does not preserve clinical validity
    sign(r_c) ≠ sign(r_python) OR |d_c| < 0.7 * |d_python|

H1: The edge implementation preserves clinical validity
    sign(r_c) == sign(r_python) AND |d_c| >= 0.7 * |d_python|
```

Rejection of H0 for a feature indicates it is suitable for edge deployment without loss of clinical validity.

---

## Publication Framing

**Title options:**
1. "Clinical Validity of Edge-Computed Acoustic Biomarkers for Depression Detection"
2. "Preserving the Feature-Clinical Linkage Under Resource Constraints"
3. "From Cloud to Edge: Validating Acoustic Depression Markers on Embedded Systems"

**Target venues:**
- IEEE JBHI (Journal of Biomedical and Health Informatics)
- INTERSPEECH (Speech and Language Processing)
- ACM Health (Digital Health)
- Nature Digital Medicine (if results are strong)

---

## Next Steps

1. Run C extractor on EATD-Corpus ✓
2. Compute direction preservation for all features
3. Compute effect size preservation ratios
4. Train classifier and measure accuracy delta
5. Plot feature degradation vs clinical impact
6. Write up results with confidence intervals
