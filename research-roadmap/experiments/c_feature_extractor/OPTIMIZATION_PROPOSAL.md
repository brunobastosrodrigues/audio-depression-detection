# Voice Metrics C Optimization Proposal

## Goal
Replace Python voice_metrics service (1.5GB) with C implementation (~50-100MB) to fit on 4GB Raspberry Pi 5.

## Current vs Proposed Memory

| Component | Python | C |
|-----------|--------|---|
| Feature extraction | 1100 MB | 50 MB |
| VAD | 100 MB (Silero) | 0 MB (energy) |
| Speaker ID | 150 MB (Resemblyzer) | 0 MB (disabled) |
| Runtime overhead | 150 MB | 5 MB |
| **Total** | **1500 MB** | **~55 MB** |

**Reduction: 96%**

---

## Implementation Phases

### Phase 1: Core Features (Already Done)
- [x] YIN F0 estimation
- [x] Energy-based VAD
- [x] RMS energy statistics
- [x] Pause/voiced ratio

**Status:** Complete, tested against Python baseline

### Phase 2: Voice Quality Features (2-3 days)

#### Jitter (F0 perturbation)
```c
// Relative average perturbation of F0
float compute_jitter(float* f0_values, int count) {
    if (count < 2) return 0.0f;

    float sum_diff = 0.0f;
    float sum_f0 = 0.0f;

    for (int i = 1; i < count; i++) {
        sum_diff += fabsf(f0_values[i] - f0_values[i-1]);
        sum_f0 += f0_values[i];
    }

    float mean_f0 = sum_f0 / (count - 1);
    float mean_diff = sum_diff / (count - 1);

    return (mean_f0 > 0) ? (mean_diff / mean_f0) : 0.0f;
}
```

#### Shimmer (amplitude perturbation)
```c
// Relative average perturbation of amplitude
float compute_shimmer(float* amplitudes, int count) {
    if (count < 2) return 0.0f;

    float sum_diff = 0.0f;
    float sum_amp = 0.0f;

    for (int i = 1; i < count; i++) {
        sum_diff += fabsf(amplitudes[i] - amplitudes[i-1]);
        sum_amp += amplitudes[i];
    }

    float mean_amp = sum_amp / (count - 1);
    float mean_diff = sum_diff / (count - 1);

    return (mean_amp > 0) ? (mean_diff / mean_amp) : 0.0f;
}
```

#### HNR (Harmonics-to-Noise Ratio)
```c
// Autocorrelation-based HNR estimation
float compute_hnr(const int16_t* frame, int size, float f0) {
    if (f0 <= 0) return 0.0f;

    int period = (int)(SAMPLE_RATE / f0);
    if (period >= size / 2) return 0.0f;

    // Autocorrelation at pitch period
    float r0 = 0.0f, r_period = 0.0f;
    for (int i = 0; i < size - period; i++) {
        r0 += (float)frame[i] * frame[i];
        r_period += (float)frame[i] * frame[i + period];
    }

    if (r0 <= 0) return 0.0f;

    float rho = r_period / r0;  // Normalized autocorrelation

    // HNR in dB: 10 * log10(rho / (1 - rho))
    if (rho >= 1.0f) return 40.0f;  // Cap at 40 dB
    if (rho <= 0.0f) return 0.0f;

    return 10.0f * log10f(rho / (1.0f - rho + 1e-10f));
}
```

### Phase 3: Spectral Features (3-4 days)

#### SNR (Signal-to-Noise Ratio)
```c
// Estimate SNR from speech vs silence frames
float compute_snr(float speech_rms, float noise_rms) {
    if (noise_rms <= 0) return 40.0f;  // Cap
    return 20.0f * log10f(speech_rms / noise_rms);
}
```

#### Spectral Flatness (requires FFT)
```c
// Wiener entropy: geometric_mean(spectrum) / arithmetic_mean(spectrum)
float compute_spectral_flatness(float* magnitude_spectrum, int size) {
    float log_sum = 0.0f;
    float sum = 0.0f;

    for (int i = 0; i < size; i++) {
        float mag = magnitude_spectrum[i] + 1e-10f;
        log_sum += logf(mag);
        sum += mag;
    }

    float geometric_mean = expf(log_sum / size);
    float arithmetic_mean = sum / size;

    return geometric_mean / (arithmetic_mean + 1e-10f);
}
```

### Phase 4: Skip or Approximate

| Feature | Decision | Rationale |
|---------|----------|-----------|
| formant_f1 | Skip | LPC too complex, low clinical weight |
| spectral_modulation | Approximate | Use simpler spectral centroid |
| voice_onset_time | Skip | Low clinical weight |
| speaker_id | Skip | Requires neural model |

---

## Architecture: Lightweight C Service

```
┌─────────────────────────────────────────────────────────┐
│  voice_metrics_c (new service)                          │
│  ├─ MQTT subscriber (libmosquitto ~1MB)                │
│  ├─ JSON parser (cJSON ~100KB)                         │
│  ├─ Base64 decoder (~10KB)                             │
│  ├─ Feature extractors:                                │
│  │   ├─ yin_f0.c (existing)                            │
│  │   ├─ vad.c (existing)                               │
│  │   ├─ jitter_shimmer.c (new)                         │
│  │   ├─ hnr.c (new)                                    │
│  │   └─ spectral.c (new, uses kiss_fft)                │
│  └─ MongoDB driver (libmongoc ~5MB)                    │
└─────────────────────────────────────────────────────────┘

Memory estimate: 50-80 MB total
```

---

## Build System

```cmake
# CMakeLists.txt for voice_metrics_c
cmake_minimum_required(VERSION 3.10)
project(voice_metrics_c C)

find_package(PkgConfig REQUIRED)
pkg_check_modules(MOSQUITTO REQUIRED libmosquitto)
pkg_check_modules(MONGOC REQUIRED libmongoc-1.0)

add_executable(voice_metrics_c
    src/main.c
    src/mqtt_handler.c
    src/feature_extractor.c
    src/yin_f0.c
    src/vad.c
    src/jitter_shimmer.c
    src/hnr.c
    src/spectral.c
    src/kiss_fft.c
)

target_link_libraries(voice_metrics_c
    ${MOSQUITTO_LIBRARIES}
    ${MONGOC_LIBRARIES}
    m
)
```

---

## Migration Strategy

### Option A: Full Replacement
Replace Python service entirely with C service.
- **Pros:** Maximum memory savings
- **Cons:** Must implement all features, risk of divergence

### Option B: Hybrid (Recommended)
Run lightweight C service for core features, Python for complex features on-demand.
- C service: F0, energy, VAD, jitter, shimmer, HNR, SNR (always-on)
- Python service: Formants, spectral modulation (triggered hourly aggregation)

### Option C: Edge/Hub Split
C runs on ESP32-S3 (edge), Python runs on Pi (hub).
- Already partially implemented with C feature extractor
- Requires firmware update on boards

---

## Effort Estimate

| Phase | Features | Effort | Memory Saved |
|-------|----------|--------|--------------|
| Phase 1 | F0, VAD, RMS | Done | - |
| Phase 2 | Jitter, Shimmer, HNR | 2-3 days | 400 MB (drop OpenSMILE) |
| Phase 3 | SNR, Spectral Flatness | 2-3 days | 100 MB (drop librosa) |
| Phase 4 | MQTT + MongoDB integration | 3-4 days | 500 MB (drop PyTorch) |
| **Total** | | **7-10 days** | **~1.4 GB** |

---

## Validation Plan

1. Run C extractor on DAIC-WOZ (89 sessions)
2. Compare with Python baseline (already have divergence analysis)
3. Target: <10% MAPE for all features
4. Depression classification: <3% accuracy drop

---

## Decision Point

**For 4GB Pi 5 with 8 boards:**

| Option | Memory | Features | Effort |
|--------|--------|----------|--------|
| Python (current) | 1.5 GB | 100% | Done |
| Python (constrained) | 1.0 GB | 70% (no speaker ID) | Config change |
| **C (Phase 2)** | **200 MB** | **85%** | **1 week** |
| C (Phase 3) | 80 MB | 90% | 2 weeks |

**Recommendation:** Phase 2 C implementation gives best ROI - drops PyTorch entirely while keeping clinically-relevant features.
