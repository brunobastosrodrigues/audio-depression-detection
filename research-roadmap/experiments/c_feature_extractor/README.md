# C Feature Extractor for Depression Detection

Edge-constrained acoustic feature extraction for the Feature Degradation Analysis experiment.

## Purpose

This C implementation extracts the same features as `python_feature_extractor.py` but under MCU constraints:
- INT16 audio samples (not float32)
- Fixed-point friendly algorithms
- Memory budget: <50KB
- Target: ESP32-S3

## Building

```bash
mkdir build && cd build
cmake ..
make
```

## Testing

```bash
# Run unit tests
./test_features

# Check for memory leaks
make memcheck
```

## Batch Extraction

Compare with Python baseline:

```bash
# Extract features from DAIC-WOZ
./extract_features ../daic_woz_extracted/ ../results/c_features.csv

# Python baseline is at: ../results/python_features.csv
```

## Features Extracted

| Feature | Algorithm | Notes |
|---------|-----------|-------|
| F0 mean | YIN | Voiced frames only |
| F0 std | Running statistics | |
| F0 range | min/max tracking | |
| Pause ratio | Energy VAD | RMS threshold |
| Voiced ratio | 1 - pause_ratio | |
| Energy std | Running RMS | |

## API

```c
#include "feature_extractor.h"

// Initialize
extractor_ctx_t* ctx = extractor_init(NULL);

// Process audio
features_t features;
extractor_process(ctx, audio_int16, num_samples, &features);

// Access results
printf("F0 mean: %.1f Hz\n", features.f0_mean);
printf("Pause ratio: %.2f\n", features.pause_ratio);

// Cleanup
extractor_free(ctx);
```

## Files

```
src/
├── feature_extractor.h    # Main API
├── feature_extractor.c    # Implementation
├── yin_f0.h               # YIN pitch tracker
├── yin_f0.c
├── vad.h                  # Voice activity detection
└── vad.c

test/
├── test_features.c        # Unit tests
└── extract_batch.c        # Batch processing
```

## Success Criteria

- [x] Compiles on Linux with gcc
- [ ] Processes 16kHz INT16 audio
- [ ] Memory usage < 50KB
- [ ] MAPE < 5% vs Python baseline
- [ ] Unit tests pass

## TODO for Gemini

1. **Test with real DAIC-WOZ data**
   - Build and run `extract_features` on `../daic_woz_extracted/`
   - Compare output with `../results/python_features.csv`

2. **Optimize YIN if needed**
   - Current implementation is O(n²) for difference function
   - Can optimize to O(n) with running sum

3. **Validate VAD threshold**
   - Current threshold: -40 dB
   - May need adjustment based on DAIC-WOZ data

4. **Port to ESP32**
   - Create ESP-IDF component
   - Use CMSIS-DSP for FFT if adding spectral features
