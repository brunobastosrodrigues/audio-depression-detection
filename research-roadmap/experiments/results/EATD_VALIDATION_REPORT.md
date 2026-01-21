# EATD-Corpus Validation Report: C Feature Extractor

## Executive Summary

The C feature extractor successfully discriminates between depressed and non-depressed individuals in the EATD-Corpus Chinese dataset, achieving **ROC-AUC of 0.689** with a data-driven classifier. However, several features show **reversed clinical directions** compared to Western literature expectations.

This finding has significant implications for cross-cultural depression detection and represents a potential research contribution.

---

## Dataset

- **EATD-Corpus** (Emotional Audio-Textual Depression Corpus)
- Language: Mandarin Chinese
- Participants: 162 (30 depressed, 132 non-depressed)
- Depression threshold: SDS score > 53
- Task: Emotional recall (positive, negative, neutral experiences)
- Samples: 486 audio recordings (3 per participant)

---

## Clinical Direction Validation Results

### Features with CORRECT Direction (matching Western literature)

| Feature | Expected | Observed | Cohen's d | p-value | Significant |
|---------|----------|----------|-----------|---------|-------------|
| pause_ratio | higher | higher | +0.015 | 0.9005 | No |
| shimmer | higher | higher | +0.172 | 0.1425 | No |
| shimmer_apq3 | higher | higher | +0.109 | 0.3522 | No |
| **snr** | lower | lower | **-0.420** | **0.0004** | **Yes** |
| **energy_std** | lower | lower | **-0.508** | **0.0000** | **Yes** |

### Features with REVERSED Direction

| Feature | Expected | Observed | Cohen's d | p-value | Significant |
|---------|----------|----------|-----------|---------|-------------|
| **f0_mean_hz** | lower | **higher** | **+0.478** | **0.0000** | **Yes** |
| f0_std_hz | lower | higher | +0.108 | 0.3556 | No |
| f0_range_hz | lower | higher | +0.054 | 0.6449 | No |
| voiced_ratio | lower | higher | +0.003 | 0.9810 | No |
| jitter | higher | lower | -0.013 | 0.9139 | No |
| jitter_rap | higher | lower | -0.022 | 0.8523 | No |
| hnr_mean | lower | higher | +0.189 | 0.1060 | No |

### Summary Statistics

- Direction Match: **5/12 (41.7%)**
- Significant & Correct: **2/12 (16.7%)**
- Significant & Reversed: **1/12 (8.3%)**

---

## F0 Reversal Analysis

### Key Finding

Depressed participants show **higher** F0 across all emotion types:

| Emotion | Depressed (n=30) | Non-depressed (n=132) | Difference |
|---------|------------------|----------------------|------------|
| Positive | 183.5 ± 58.9 Hz | 154.3 ± 52.3 Hz | **+29.2 Hz** |
| Negative | 177.2 ± 56.8 Hz | 155.9 ± 45.5 Hz | **+21.3 Hz** |
| Neutral | 177.2 ± 56.9 Hz | 156.2 ± 46.3 Hz | **+20.9 Hz** |

### Possible Explanations

1. **Tonal Language Effect**: Mandarin Chinese uses pitch (F0) to distinguish lexical tones. Depression may manifest differently in tonal vs. non-tonal languages.

2. **Task-Specific Effect**: Emotional recall paradigm differs from clinical interviews. Depressed individuals may show hyperactivation when recalling emotional experiences.

3. **Cultural Expression Norms**: Chinese cultural norms around emotional expression may lead to different acoustic signatures of depression.

4. **Gender/Demographics**: Potential confounds in the dataset composition (not controlled).

---

## Classification Performance

### C-Extracted Features (Data-Driven Approach)

```
5-Fold Stratified Cross-Validation:
  ROC-AUC: 0.689 ± 0.050
  Accuracy: 0.644 ± 0.017

Class Distribution: 90 depressed, 396 non-depressed (18.5% / 81.5%)
```

### Feature Importance (Logistic Regression)

| Feature | Coefficient | Interpretation |
|---------|-------------|----------------|
| f0_mean_hz | **+0.643** | Higher F0 → depressed |
| hnr_mean | +0.389 | Higher HNR → depressed |
| pause_ratio | +0.325 | More pauses → depressed |
| snr | -0.314 | Lower SNR → depressed |
| voiced_ratio | -0.282 | Less voicing → depressed |
| energy_std | -0.281 | Lower dynamics → depressed |
| jitter | -0.206 | Lower jitter → depressed |
| f0_std_hz | -0.165 | Lower F0 variation → depressed |
| shimmer | +0.161 | Higher shimmer → depressed |
| f0_range_hz | +0.060 | (weak contribution) |

---

## Implications for Research

### 1. Cross-Cultural Validity

The assumption that Western-derived acoustic depression markers are universal is **challenged** by these results. This suggests:

- Depression acoustic signatures may be **language-specific** (tonal vs. non-tonal)
- Cultural factors influence **how depression manifests acoustically**
- Validation on diverse populations is **essential** before deployment

### 2. Edge Deployment Strategy

Despite direction reversals, the C extractor:

- Successfully extracts **discriminative** features
- Achieves **reasonable classification performance** (AUC 0.689)
- Requires **data-driven** rather than rule-based approaches

**Recommendation**: Train classifiers on target population data rather than relying on literature-derived direction assumptions.

### 3. Publication Opportunity

The F0 reversal finding is publishable as:

> "Cross-Cultural Acoustic Markers of Depression: Evidence from Mandarin Chinese Emotional Speech"

Or as part of:

> "Validating Edge-Computed Acoustic Biomarkers: A Cross-Lingual Analysis"

---

## Files Generated

- `eatd_c_features.csv` - Raw extracted features (486 samples)
- `clinical_validation_results.csv` - Direction analysis results
- `EATD_VALIDATION_REPORT.md` - This report

---

## Next Steps

1. **Python Baseline**: Extract features using Python/librosa for direct comparison
2. **DAIC-WOZ Validation**: Repeat analysis on English clinical interviews
3. **Cross-Lingual Model**: Test if model trained on English transfers to Chinese
4. **Publication Draft**: Frame findings for INTERSPEECH or IEEE JBHI submission

---

## Technical Notes

- **C Extractor**: YIN F0 + energy VAD + jitter/shimmer/HNR/SNR
- **Memory Footprint**: ~82KB (suitable for ESP32-S3)
- **Audio Format**: 16-bit WAV, preprocessed (*_out.wav files)
- **Extraction Time**: ~486 samples in <30 seconds

---

*Generated: 2026-01-21*
*Dataset: EATD-Corpus (Shen et al., 2022)*
*Extractor: C implementation v2.0 (YIN + voice quality)*
