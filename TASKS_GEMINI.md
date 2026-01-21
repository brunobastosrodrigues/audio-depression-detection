# Tasks for Gemini

---
## ⚠️ IMMEDIATE ACTION REQUIRED

**START TASK 3 NOW** - C Feature Extractor

The Python baseline is complete (89 sessions processed). Claude is waiting for the C implementation to run the divergence analysis.

**Your first step:**
```bash
cd research-roadmap/experiments/c_feature_extractor
gcc -O2 -Wall -Isrc src/*.c test/test_features.c -o test_features -lm
./test_features
```

The YIN F0 detection is returning 0 for sine waves - debug and fix this first.

---

## Active Tasks

### Task 1: Implement ESP32-S3 Firmware for XVF3800 DoA Reading
**Status:** 🟢 80% Complete - Firmware exists, payload integration pending
**Priority:** High
**Directory:** `data_ingestion_layer/firmware/main/drivers/xvf3800/` (EXISTS)

#### Summary
Create ESP-IDF firmware for ESP32-S3 that reads Direction of Arrival (DoA) data from XVF3800 via I2C and includes it in the MQTT feature payload.

#### Design Document
See: `research-roadmap/docs/XVF3800_INTEGRATION_SKETCH.md` (Section 4: ESP32-S3 Firmware Changes)
See: `research-roadmap/docs/FIRMWARE_SPEC.md`

#### Subtasks

**1. Project Setup** ✅ DONE
- [x] Create `firmware/xvf3800/` directory structure → EXISTS at `data_ingestion_layer/firmware/`
- [x] Initialize ESP-IDF project (CMakeLists.txt, sdkconfig) → Done
- [x] Copy base structure from ReSpeaker firmware if exists → Done

**2. XVF3800 I2C Communication** ✅ DONE
- [x] Create `xvf3800_doa.h` header with structs and function declarations → `drivers/xvf3800/xvf3800.h`
- [x] Create `xvf3800_doa.c` implementation → `drivers/xvf3800/xvf3800.c`:
  - [x] `xvf3800_init()` - Initialize I2C, verify XVF3800 presence
  - [x] `xvf3800_get_status()` - Read DoA angle, confidence, active beam, AEC status
- [ ] Test I2C communication with XVF3800 dev board (NEEDS HARDWARE)

**3. Extended Feature Payload** ⚠️ PENDING
- [ ] Update `FeaturePayload` struct to include:
  - `board_type` (uint8_t: 0=respeaker_lite, 1=xvf3800)
  - `doa_angle` (float: 0-360 degrees)
  - `doa_confidence` (float: 0.0-1.0)
  - `active_beam` (uint8_t: 0=scanning, 1-2=focused)
  - `aec_active` (uint8_t: boolean)
  - `snr_estimate` (float: dB)
- [ ] Update MQTT publish to include new fields

**4. Main Loop Integration**
- [ ] Call `xvf3800_get_status()` after audio capture
- [ ] Populate payload with DoA data
- [ ] Handle case where XVF3800 read fails (use default values)

**5. Testing**
- [ ] Test I2C read timing (should be <10ms)
- [ ] Test DoA values make sense (0-360 range)
- [ ] Test payload size doesn't exceed MQTT limits
- [ ] Test graceful degradation if XVF3800 not responding

#### Technical Notes

**XVF3800 I2C Registers (from datasheet):**
```c
#define XVF3800_I2C_ADDR          0x2C  // Verify in datasheet
#define XVF3800_REG_DOA_ANGLE_H   0x10
#define XVF3800_REG_DOA_ANGLE_L   0x11
#define XVF3800_REG_DOA_CONFIDENCE 0x12
#define XVF3800_REG_ACTIVE_BEAM   0x13
#define XVF3800_REG_AEC_STATUS    0x20
```

**Data Format:**
- DoA angle: 16-bit, 0-36000 representing 0.00-360.00 degrees
- Confidence: 8-bit, 0-255 mapped to 0.0-1.0
- Active beam: 8-bit, 0=scanning, 1-2=focused beams

**ESP-IDF I2C Example:**
```c
esp_err_t xvf3800_get_status(xvf3800_status_t *status) {
    uint8_t data[4];
    esp_err_t ret = i2c_master_read_from_device(
        I2C_NUM_0, XVF3800_I2C_ADDR,
        data, sizeof(data), pdMS_TO_TICKS(50)
    );
    if (ret != ESP_OK) return ret;

    status->doa_angle = ((data[0] << 8) | data[1]) / 100.0f;
    status->doa_confidence = data[2] / 255.0f;
    status->active_beam = data[3];
    return ESP_OK;
}
```

#### Acceptance Criteria
- [ ] Firmware compiles for ESP32-S3 target
- [ ] Successfully reads DoA from XVF3800 via I2C
- [ ] MQTT payload includes DoA metadata
- [ ] Backward compatible (can disable DoA reading via config)
- [ ] Documented in README

---

### Task 2: Benchmark Pi 5 Feature Extraction Performance
**Status:** ✅ COMPLETE (Done by Claude)
**Priority:** Medium
**Directory:** `research-roadmap/experiments/`

#### Summary
Run comprehensive benchmarks of the feature extraction pipeline on the VM (simulating Pi 5) to establish baseline performance metrics.

#### Results
- **Report:** `research-roadmap/experiments/results/BENCHMARK_REPORT.md`
- **Raw data:** `research-roadmap/experiments/results/feature_benchmark_20260121_165918.json`
- **Key finding:** All Python/librosa features exceed ESP32 memory limit (200KB)
- **Recommendation:** Edge features must be C/CMSIS-DSP implementations

#### Subtasks

**1. Prepare Test Data** ✅
- [x] Used synthetic audio (16kHz, 5s chunks)

**2. Benchmark Individual Extractors** ✅
- [x] Measured 7 librosa-based features
- [x] Identified memory as bottleneck (not latency)
- [x] Recorded memory usage per feature

**3. Benchmark Full Pipeline** ⚠️ Partial
- [ ] Test with concurrent streams (not done - single stream only)

**4. Create Report** ✅
- [x] Generated `BENCHMARK_REPORT.md`
- [x] Identified all features as hub-only (memory constraint)
- [x] Recommended C implementations for ESP32 edge

---

### Task 3: Implement C Feature Extractor for ESP32
**Status:** 🔴 START NOW
**Priority:** URGENT - Claude is waiting for this
**Directory:** `research-roadmap/experiments/c_feature_extractor/`

#### Summary
Implement acoustic feature extraction in C with ESP32-S3 constraints. This is part of the Feature Degradation Analysis experiment (Direction 1) to measure accuracy loss when running on edge devices.

#### Context
- **Experiment Protocol:** `research-roadmap/experiments/EXPERIMENT_PROTOCOL.md`
- **Python Baseline:** Claude is implementing `python_feature_extractor.py`
- **DAIC-WOZ Data:** 89 sessions available at `/home/rodrigues/daic-woz/`
- **Extracted Audio:** `research-roadmap/experiments/daic_woz_extracted/*/XXX_AUDIO.wav`

#### Features to Implement

| Feature | Algorithm | Complexity | Notes |
|---------|-----------|------------|-------|
| **F0 mean** | YIN (simplified) | Medium | Autocorrelation-based |
| **F0 std** | Running statistics | Low | Track variance online |
| **F0 range** | Min/max tracking | Low | Simple |
| **Pause ratio** | Energy VAD | Low | RMS threshold |
| **Energy std** | Running RMS std | Low | Frame-by-frame |
| **Spectral flatness** | FFT + geom/arith mean | Medium | 256-point FFT |

#### Constraints (ESP32-S3 Realistic)

```c
// Target constraints
#define SAMPLE_RATE     16000       // Hz
#define FRAME_SIZE      512         // samples (32ms)
#define FFT_SIZE        256         // points
#define MAX_MEMORY      50000       // bytes for feature extraction
#define AUDIO_FORMAT    INT16       // not float32
```

#### Subtasks

**1. Project Setup**
- [ ] Create directory structure:
  ```
  c_feature_extractor/
  ├── CMakeLists.txt
  ├── src/
  │   ├── feature_extractor.c
  │   ├── feature_extractor.h
  │   ├── yin_f0.c
  │   ├── yin_f0.h
  │   ├── vad.c
  │   ├── vad.h
  │   └── fft_wrapper.c
  ├── test/
  │   └── test_features.c
  └── README.md
  ```
- [ ] Set up CMake for Linux testing (not ESP-IDF yet)

**2. Implement Core Features**
- [ ] `vad.c` - Energy-based voice activity detection
  - RMS computation from INT16 samples
  - Adaptive threshold or fixed threshold
  - Return voiced/unvoiced per frame
- [ ] `yin_f0.c` - Simplified YIN pitch tracker
  - Autocorrelation (can use CMSIS-DSP later)
  - Cumulative mean normalized difference
  - Parabolic interpolation for sub-sample accuracy
- [ ] `feature_extractor.c` - Main interface
  - `features_t extract_features(int16_t* audio, size_t len)`
  - Process audio in frames, accumulate statistics

**3. Testing**
- [ ] Create test harness that reads WAV files
- [ ] Compare output to Python baseline (provided by Claude)
- [ ] Target: <5% MAPE on F0 and pause features

**4. Optimization**
- [ ] Profile memory usage
- [ ] Use fixed-point where possible
- [ ] Ensure fits in 50KB

#### API Specification

```c
// feature_extractor.h

typedef struct {
    float f0_mean;      // Hz
    float f0_std;       // Hz
    float f0_range;     // Hz (max - min)
    float pause_ratio;  // 0.0 - 1.0
    float voiced_ratio; // 0.0 - 1.0
    float energy_std;   // Normalized
    int32_t frame_count;
    int32_t voiced_frames;
} features_t;

typedef struct {
    int sample_rate;
    int frame_size;
    float vad_threshold_db;
    float f0_min_hz;
    float f0_max_hz;
} extractor_config_t;

// Initialize with config
int extractor_init(extractor_config_t* config);

// Extract features from audio buffer
// audio: INT16 PCM samples
// len: number of samples
// out: output features
int extract_features(const int16_t* audio, size_t len, features_t* out);

// Cleanup
void extractor_cleanup(void);
```

#### Test Data
- Use first 10 sessions from DAIC-WOZ: 300, 301, 302, ..., 309
- Audio files at: `research-roadmap/experiments/daic_woz_extracted/{id}/{id}_AUDIO.wav`
- Python baseline results will be at: `research-roadmap/experiments/results/python_features.csv`

#### Acceptance Criteria
- [ ] Compiles on Linux with gcc
- [ ] Processes 16kHz INT16 audio
- [ ] Outputs F0, pause_ratio, energy_std
- [ ] Memory usage < 50KB
- [ ] MAPE < 5% vs Python baseline (on same audio)
- [ ] Documented algorithm choices

#### References
- YIN paper: de Cheveigné & Kawahara (2002) "YIN, a fundamental frequency estimator for speech and music"
- CMSIS-DSP: https://arm-software.github.io/CMSIS-DSP/latest/
- ESP-IDF DSP: https://github.com/espressif/esp-dsp

---

## Completed Tasks

### Task 2: Benchmark Pi 5 Feature Extraction Performance ✅
- Completed 2026-01-21 by Claude
- Results: `research-roadmap/experiments/results/BENCHMARK_REPORT.md`

---

## Notes for Gemini

1. **Local execution:** You're running locally, be aware of race conditions with other agents
2. **Locking:** If editing shared files, coordinate or use separate branches
3. **Testing:** Run tests before committing
4. **Commits:** Use conventional commit format
5. **Docker:** The stack is running on this VM - don't restart without coordinating
