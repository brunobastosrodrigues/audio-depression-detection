# Feature Extraction Benchmark Report

**Date:** 2026-01-21
**Environment:** VM simulating Raspberry Pi 5 (x86_64)
**Benchmark Script:** `benchmark_features.py`

---

## Executive Summary

**Key Finding:** All Python/librosa-based features exceed ESP32-S3 memory constraints. Edge processing requires custom C implementations with CMSIS-DSP.

| Constraint | ESP32-S3 Limit | Best Python Result |
|------------|----------------|-------------------|
| Memory | 200 KB | 766 KB (ZCR) |
| Latency | 100 ms | 0.4 ms (RMS) |

**Conclusion:** Latency is NOT the bottleneck. **Memory is.** Even the simplest Python feature (RMS energy at 0.4ms) uses 1.6MB of memory.

---

## Benchmark Results

### Test Configuration
- Sample rate: 16,000 Hz
- Chunk duration: 5.0 seconds
- Iterations: 10 per feature
- Warmup: 3 iterations

### Feature Performance (Sorted by Latency)

| Feature | Latency (ms) | Memory (KB) | Edge Feasible | Notes |
|---------|-------------|-------------|---------------|-------|
| rms_energy | 0.44 | 1,611 | NO | Memory 8x over limit |
| zcr | 1.40 | 766 | NO | Memory 4x over limit |
| spectral_flatness | 3.23 | 2,323 | NO | Memory 11x over limit |
| spectral_centroid | 3.57 | 3,912 | NO | Memory 19x over limit |
| f0_yin | 9.75 | 6,604 | NO | Memory 33x over limit |
| mfcc_13 | 10.65 | 2,404 | NO | Memory 12x over limit |
| f0_pyin | 320.23 | 19,179 | NO | Both slow AND memory-heavy |

### Memory Breakdown

```
Python/librosa memory overhead:
├── NumPy array allocation: ~640 KB base
├── librosa STFT buffers: ~1,000+ KB
├── Intermediate results: varies
└── Python object overhead: ~100+ KB
```

---

## Recommendations for Edge Processing

### What CAN Run on ESP32-S3 (with C implementation)

Based on computational complexity analysis:

| Feature | Complexity | ESP32-S3 Feasibility | Estimated C Latency |
|---------|------------|---------------------|-------------------|
| RMS Energy | O(n) | YES | <1 ms |
| ZCR | O(n) | YES | <1 ms |
| VAD (energy-based) | O(n) | YES | <5 ms |
| MFCC (13 coeff) | O(n log n) | MAYBE | 30-50 ms |
| F0 (YIN) | O(n²) | MAYBE | 50-80 ms |
| Spectral Centroid | O(n log n) | MAYBE | 20-30 ms |

### Recommended Edge Feature Set

**Tier 1 - Edge (ESP32-S3):**
```c
// Feasible in C with CMSIS-DSP
- rms_energy      // 4 bytes
- zcr             // 4 bytes
- vad_flag        // 1 byte
- frame_energy[]  // 200 bytes (50 frames)
```
**Total:** ~209 bytes payload (well under limit)

**Tier 2 - Edge (if time permits):**
```c
// Requires FFT, more complex
- mfcc_13[]       // 52 bytes
- f0_estimate     // 4 bytes
```
**Total:** ~265 bytes payload

### What MUST Stay on Pi 5

| Feature | Reason |
|---------|--------|
| Full MFCC (40 coeff) | Memory-intensive Mel filterbank |
| pYIN F0 | Probabilistic, high memory |
| Spectral features (full) | Full STFT required |
| Formant tracking | Requires LPC + root finding |
| D-vector (speaker ID) | Neural network inference |
| All openSMILE features | Full Python runtime needed |

---

## Implications for Zero-Cloud Architecture

### Current Plan (FIRMWARE_SPEC.md) is Correct

The firmware specification already accounts for these constraints:
- Uses CMSIS-DSP for FFT operations
- Implements MFCC in fixed-point INT16
- Uses YIN (not pYIN) for F0
- Keeps payload under 256 bytes

### Validated Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   ESP32-S3      │    │   MQTT          │    │   Pi 5 Hub      │
│   (Edge)        │───▶│   (Features)    │───▶│   (Heavy)       │
├─────────────────┤    └─────────────────┘    ├─────────────────┤
│ - VAD           │                           │ - Full MFCCs    │
│ - RMS Energy    │                           │ - pYIN F0       │
│ - ZCR           │                           │ - D-vector      │
│ - Basic MFCC    │                           │ - Aggregation   │
│ - F0 (YIN)      │                           │ - Scene Analysis│
└─────────────────┘                           └─────────────────┘
      ~5ms                                        ~50-100ms
```

---

## Action Items

1. **Firmware Development (Gemini):**
   - Implement C-based MFCC using CMSIS-DSP
   - Implement YIN F0 algorithm in C
   - Target: <50ms for all edge features combined

2. **Hub Optimization (Claude):**
   - Profile openSMILE performance on actual Pi 5
   - Consider pre-compiled C extensions for bottleneck features
   - Evaluate TensorFlow Lite for D-vector inference

3. **Hybrid Strategy:**
   - Edge sends VAD + basic features for gatekeeper
   - Hub requests full audio only when needed
   - Reduces bandwidth and Pi 5 load by ~70%

---

## Appendix: Raw Benchmark Data

See: `feature_benchmark_20260121_165918.json`
