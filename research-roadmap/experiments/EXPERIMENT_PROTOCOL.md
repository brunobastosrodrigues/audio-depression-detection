# Experiment Protocol: Feature Degradation Analysis

**Research Question:** What is the accuracy cost of edge-constrained acoustic feature extraction for depression detection?

---

## Overview

This experiment quantifies how much acoustic features degrade when computed under MCU constraints (fixed-point arithmetic, reduced precision, simplified algorithms) compared to standard floating-point implementations.

## Hypothesis

> Edge-constrained feature extraction (C/INT16) will achieve <5% Mean Absolute Percentage Error (MAPE) compared to Python/float64 baseline for clinically-validated depression markers.

---

## Features Under Study

| Feature | Clinical Relevance | Python Implementation | C Implementation |
|---------|-------------------|----------------------|------------------|
| **F0 mean** | Lower in depression | librosa.pyin / parselmouth | YIN (simplified) |
| **F0 std** | Reduced variability | numpy.std on F0 track | Running std |
| **F0 range** | Monotonic speech | max - min | Track min/max |
| **Pause ratio** | Increased pauses | Energy-based VAD | RMS threshold |
| **Energy std** | Reduced dynamics | numpy.std on RMS | Running std |
| **Spectral flatness** | Voice quality | librosa.spectral_flatness | FFT-based |

---

## Experimental Design

### Phase 1: Python Baseline (Reference)

Extract features from DAIC-WOZ audio using standard Python libraries.

**Tools:**
- `librosa` for audio loading and spectral features
- `parselmouth` (Praat) for F0 extraction (clinical gold standard)
- `numpy` for statistics

**Output:** `python_features.csv` with per-session features

### Phase 2: C Implementation (Edge-realistic)

Implement same features in C with ESP32 constraints:
- INT16 audio samples (not float32)
- Fixed-point arithmetic where possible
- 256-point FFT (not 2048)
- Simplified YIN for F0

**Output:** `c_features.csv` with per-session features

### Phase 3: Divergence Analysis

Compare Python vs C features:

```
MAPE = mean(|Python - C| / |Python|) × 100%
```

**Success Criteria:**
| Metric | Target |
|--------|--------|
| Per-feature MAPE | < 5% |
| Correlation (Pearson r) | > 0.95 |
| Classification accuracy drop | < 3% |

### Phase 4: Ablation Study

Systematically degrade Python implementation to identify which constraints hurt most:
1. Float64 → Float32 → INT16
2. FFT 2048 → 1024 → 512 → 256
3. Full YIN → Simplified autocorrelation
4. 16kHz → 8kHz sample rate

---

## Dataset

**DAIC-WOZ Subset (Available):**
- 89 sessions (IDs 300-390)
- ~23 hours of audio
- Pre-extracted COVAREP features (for validation)

**Missing (to be obtained):**
- PHQ-8 labels for classification experiment
- Sessions 391-492 for complete benchmark

---

## Implementation Plan

### Step 1: Python Reference Extractor
```python
# python_feature_extractor.py
def extract_features(audio_path):
    # Load audio
    # Extract F0 using parselmouth (Praat)
    # Compute pause ratio from energy VAD
    # Compute energy statistics
    # Return feature dict
```

### Step 2: Validate Against COVAREP
Compare our Python F0 extraction to COVAREP F0 (ground truth).
Target: r > 0.95 correlation.

### Step 3: C Implementation
```c
// feature_extractor.c
typedef struct {
    float f0_mean;
    float f0_std;
    float f0_range;
    float pause_ratio;
    float energy_std;
} features_t;

features_t extract_features(int16_t* audio, size_t len);
```

### Step 4: Cross-validation
Run both extractors on same audio files, compute divergence.

---

## Directory Structure

```
research-roadmap/experiments/
├── EXPERIMENT_PROTOCOL.md          # This file
├── daic_woz_analysis.py            # COVAREP analysis (done)
├── python_feature_extractor.py     # Python baseline
├── c_feature_extractor/            # C implementation
│   ├── src/
│   │   ├── feature_extractor.c
│   │   ├── yin_f0.c
│   │   └── vad.c
│   ├── test/
│   └── CMakeLists.txt
├── divergence_analysis.py          # Compare Python vs C
└── results/
    ├── python_features.csv
    ├── c_features.csv
    └── divergence_report.md
```

---

## Timeline

| Phase | Task | Status |
|-------|------|--------|
| 1a | Extract COVAREP baseline | ✅ Done |
| 1b | Python reference extractor | 🔄 In Progress |
| 1c | Validate against COVAREP | Pending |
| 2 | C implementation | Pending |
| 3 | Divergence analysis | Pending |
| 4 | Ablation study | Pending |
| 5 | Write results | Pending |

---

## Success Metrics

**Primary:** Feature divergence MAPE < 5%

**Secondary:**
- Classification F1 drop < 3% when training on Python, testing on C features
- C implementation fits in 50KB RAM
- C extraction completes in <100ms per 5-second chunk

---

## References

- DAIC-WOZ: https://dcapswoz.ict.usc.edu/
- COVAREP: https://github.com/covarep/covarep
- YIN Algorithm: de Cheveigné & Kawahara (2002)
- Parselmouth: https://parselmouth.readthedocs.io/
