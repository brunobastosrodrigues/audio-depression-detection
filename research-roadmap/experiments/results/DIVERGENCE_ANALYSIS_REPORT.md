# Feature Degradation Analysis: Python vs C Implementation

## Executive Summary

**Date:** 2026-01-21
**Dataset:** DAIC-WOZ (89 sessions)
**Comparison:** Python/Praat vs C/YIN feature extraction

### Key Findings

| Feature | MAPE | Pearson r | Status | Root Cause |
|---------|------|-----------|--------|------------|
| F0 Mean | 5.61% | 0.977 | MARGINAL | Algorithm differences (Praat AC vs YIN) |
| F0 Std | 28.43% | 0.625 | FAIL | Voicing detection sensitivity |
| Pause Ratio | 14.27% | 0.492 | FAIL | VAD approach (F0-based vs energy-based) |
| Voiced Ratio | 58.39% | 0.492 | FAIL | Same as pause ratio |

**Overall Verdict:** F0 mean is robust to implementation, but VAD and F0 variability are highly sensitive.

---

## Detailed Analysis

### 1. F0 Mean (MARGINAL - 5.61% MAPE)

**Finding:** F0 mean shows excellent correlation (r=0.977) but slight bias (+4.4 Hz for C).

**Technical Details:**
- Python: Praat autocorrelation with voicing_threshold=0.45
- C: YIN algorithm with CMNDF threshold=0.1
- Both use parabolic interpolation for sub-sample accuracy

**Interpretation:**
The fundamental frequency estimation is robust to algorithm choice. The 5.61% MAPE is close to our 5% target and likely acceptable for clinical applications. The correlation of 0.977 indicates the relative ranking of speakers is preserved.

**Bias Direction:** C/YIN reports slightly higher F0 values (+4.4 Hz on average). This could be due to YIN's tendency to occasionally estimate at half-period (octave error) which would double F0.

### 2. F0 Standard Deviation (FAIL - 28.43% MAPE)

**Finding:** Significant divergence in pitch variability measurement.

**Technical Details:**
- Python mean F0 std: 39.7 Hz
- C mean F0 std: 28.7 Hz
- Bias: Python reports -11.0 Hz higher variability

**Root Cause:**
The Python implementation detects more voiced frames (18.9% voiced ratio) compared to C (10.1% voiced ratio). More voiced frames means:
1. More F0 values in the calculation
2. Potentially more extreme values captured
3. Higher computed standard deviation

**Interpretation:**
F0 std is highly sensitive to voicing detection threshold. This is a **critical finding** - clinical researchers using F0 variability as a depression biomarker need to be aware that this metric is algorithm-dependent.

### 3. VAD/Voicing Detection (FAIL - 14-58% MAPE)

**Finding:** Fundamental algorithmic difference in how voicing is determined.

**Algorithm Comparison:**

| Aspect | Python (Praat) | C (Edge) |
|--------|---------------|----------|
| Primary Signal | F0-based | Energy-based |
| Voicing Criterion | Pitch detected (F0 > 0) | RMS > -40 dB AND YIN F0 > 0 |
| Frame Size | 10ms hop | 512 samples (32ms) at 10ms hop |
| Sensitivity | More sensitive | More conservative |

**Voiced Ratio Statistics:**
- Python: 18.9% ± varies
- C: 10.1% ± varies
- C detects ~8.8 percentage points fewer voiced frames

**Interpretation:**
This is the most significant divergence. The C implementation is more conservative, classifying more frames as "pauses." For depression detection:
- Increased pause ratio is a biomarker for depression
- A systematically different measurement could bias clinical interpretations
- **Calibration is essential** when comparing across implementations

---

## Research Implications

### 1. Robust Features for Edge Deployment
F0 mean is the most robust feature for edge deployment, with <6% MAPE and near-perfect correlation. This should be prioritized in resource-constrained systems.

### 2. Sensitive Features Requiring Calibration
- F0 std and pause/voiced ratios require calibration when deploying on edge
- A simple linear correction (based on bias) could improve agreement
- Alternatively, train separate models for edge vs cloud features

### 3. Depression Detection Impact
The voiced_ratio difference (Python 18.9% vs C 10.1%) means:
- Edge features will systematically show "more pauses"
- Classification models trained on Python features will be miscalibrated on edge
- **Recommendation:** Train edge-specific models or apply feature normalization

---

## Ablation Study Recommendations

Based on these findings, we recommend the following ablation studies:

1. **VAD Threshold Sweep:** Test C implementation with thresholds from -50dB to -30dB
2. **YIN Threshold Sweep:** Test CMNDF thresholds from 0.05 to 0.2
3. **Frame Size Impact:** Compare 256, 512, 1024 sample frames
4. **Combined F0+Energy VAD:** Implement Python's F0-based voicing in C

---

## Raw Statistics

### Python Features (N=89)
```
f0_mean_hz:     139.2 Hz (mean)
f0_std_hz:       39.7 Hz
pause_ratio:      0.811
voiced_ratio:     0.189
```

### C Features (N=89)
```
f0_mean_hz:     143.6 Hz (mean)
f0_std_hz:       28.7 Hz
pause_ratio:      0.899
voiced_ratio:     0.101
```

### Bias Summary
```
f0_mean:      C is +4.4 Hz higher
f0_std:       C is -11.0 Hz lower
pause_ratio:  C is +0.088 higher (more pauses detected)
voiced_ratio: C is -0.088 lower
```

---

## Conclusion

This analysis quantifies the **feature degradation** when moving from Python/cloud to C/edge implementation. The key insight is that F0 mean is robust (acceptable for deployment), but temporal features like pause ratio and F0 variability require careful calibration.

For the research contribution, this provides empirical evidence for:
1. Which features can be reliably extracted on edge devices
2. The magnitude of calibration required for sensitive features
3. Design recommendations for edge acoustic analysis pipelines

---

## Files

- Python features: `results/python_features.csv`
- C features: `results/c_features.csv`
- Divergence metrics: `results/divergence_report.json`
- This report: `results/DIVERGENCE_ANALYSIS_REPORT.md`
