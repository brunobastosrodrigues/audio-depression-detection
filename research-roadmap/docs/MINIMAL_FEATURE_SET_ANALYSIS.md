# Minimal Feature Set Analysis for Edge Depression Detection

**Date:** 2026-01-21
**Purpose:** Identify minimal acoustic features for ESP32-S3 implementation

---

## Current Feature Usage Analysis

### Features by Frequency Across DSM-5 Indicators

| Feature | Indicators Used | Count | ESP32 Feasible? |
|---------|-----------------|-------|-----------------|
| **f0_std** | 1, 2, 5, 8 | 4 | YES (YIN algorithm) |
| **jitter** | 1, 2, 5, 8 | 4 | MAYBE (needs F0 first) |
| **shimmer** | 1, 2, 5, 8 | 4 | MAYBE (needs F0 first) |
| **pause_duration** | 1, 5, 8 | 3 | YES (VAD-based) |
| **pause_count** | 1, 5, 8 | 3 | YES (VAD-based) |
| **f0_avg** | 1, 5 | 2 | YES (YIN algorithm) |
| **f0_range** | 2, 8 | 2 | YES (from F0 track) |
| **rate_of_speech** | 1, 5 | 2 | HARD (needs syllable detection) |
| **articulation_rate** | 1, 5 | 2 | HARD (needs syllable detection) |
| **rms_energy_std** | 2, 8 | 2 | YES (trivial) |
| **rms_energy_range** | 2, 8 | 2 | YES (trivial) |
| **spectral_flatness** | 1, 5 | 2 | YES (FFT-based) |
| **f2_transition_speed** | 1, 5 | 2 | HARD (formant tracking) |
| **temporal_modulation** | 4, 6 | 2 | HARD (mel-spectrogram) |
| **spectral_modulation** | 4, 6 | 2 | HARD (mel-spectrogram) |
| formant_f1_frequencies_mean | 1 | 1 | HARD (LPC) |
| snr | 1 | 1 | YES (energy ratio) |
| hnr_mean | 4 | 1 | HARD (autocorrelation) |
| voice_onset_time | 5 | 1 | HARD (burst detection) |
| glottal_pulse_rate | 8 | 1 | HARD (GCI detection) |

---

## Proposed Minimal Feature Set (6 features)

Based on frequency, literature support, and ESP32 feasibility:

### Tier 1: Core (Must Have) - 4 features

| Feature | Rationale | Complexity | Memory Est. |
|---------|-----------|------------|-------------|
| **f0_avg** | Most cited depression marker | Medium (YIN) | ~20KB |
| **f0_std** | Used in 4 indicators | Medium (from F0) | ~1KB |
| **pause_duration** | Psychomotor retardation marker | Low (VAD) | ~5KB |
| **rms_energy_std** | Energy dynamics | Low (RMS) | ~2KB |

### Tier 2: If Resources Allow - 2 features

| Feature | Rationale | Complexity | Memory Est. |
|---------|-----------|------------|-------------|
| **spectral_flatness** | Voice quality proxy | Medium (FFT) | ~10KB |
| **pause_count** | Speech hesitation marker | Low (VAD) | ~1KB |

### Total Estimated: ~40KB (well under 200KB limit)

---

## Feature Implementation Complexity

### Easy (Pure time-domain)
```c
// RMS Energy - O(n), no FFT needed
float rms = 0;
for (int i = 0; i < n; i++) {
    rms += samples[i] * samples[i];
}
rms = sqrt(rms / n);

// Pause detection - thresholding
bool is_pause = rms < PAUSE_THRESHOLD;
```

### Medium (Requires FFT)
```c
// F0 via YIN algorithm - O(n²) but optimizable
// Spectral flatness - needs magnitude spectrum
float flatness = geometric_mean(spectrum) / arithmetic_mean(spectrum);
```

### Hard (Skip for MVP)
- Formant tracking (LPC + root finding)
- Jitter/shimmer (period-synchronous analysis)
- Speech rate (syllable nuclei detection)
- Modulation features (2D spectro-temporal)

---

## Validation Strategy

### Experiment Design

```
1. BASELINE (Python/Pi5)
   - Extract all 6 features using librosa/OpenSMILE
   - Store as reference values

2. EDGE (C/ESP32)
   - Implement same 6 features in C
   - Extract from same audio files

3. COMPARISON
   - Compute feature divergence: |Python - C| / |Python|
   - Target: <5% mean absolute percentage error (MAPE)

4. CLASSIFICATION TEST
   - Train classifier on Python features
   - Test on C features
   - Measure accuracy drop
```

### Success Criteria

| Metric | Target |
|--------|--------|
| Feature divergence (MAPE) | <5% |
| Latency per 5s chunk | <100ms |
| Memory usage | <50KB |
| Classification accuracy drop | <3% |

---

## Implementation Roadmap

### Phase 1: Python Baseline (1 week)
- [ ] Create isolated extractors for 6 features
- [ ] Benchmark on TESS dataset
- [ ] Document exact algorithms used

### Phase 2: C Implementation (2 weeks)
- [ ] Implement RMS energy + pause detection
- [ ] Implement YIN F0 tracker
- [ ] Implement spectral flatness (FFT)
- [ ] Unit tests against Python

### Phase 3: ESP32 Port (1 week)
- [ ] Port to ESP-IDF
- [ ] Optimize for fixed-point (INT16)
- [ ] Measure real latency/memory

### Phase 4: Validation (1 week)
- [ ] Run divergence analysis
- [ ] Classification experiment
- [ ] Write results section

---

## Literature Support

Features chosen align with published depression markers:

1. **F0 (pitch)** - Cummins et al. 2015, Scherer et al. 2013
   - Lower mean F0 in depression
   - Reduced F0 variability

2. **Pause patterns** - Cannizzaro et al. 2004, Mundt et al. 2012
   - Longer pauses
   - More frequent hesitations

3. **Energy dynamics** - Low et al. 2011
   - Reduced energy variation
   - Monotonic speech

4. **Spectral flatness** - Ooi et al. 2014
   - Proxy for voice quality
   - Higher in breathy/weak voice

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| YIN too slow for ESP32 | Use simplified autocorrelation |
| FFT too memory-heavy | Use fixed 256-point FFT |
| Pause threshold varies | Learn threshold from calibration |
| Feature divergence >5% | Accept if classification holds |

---

## Next Steps

1. Wait for state-of-the-art research agent results
2. Validate feature selection against literature
3. Create Python reference implementation
4. Begin C implementation
