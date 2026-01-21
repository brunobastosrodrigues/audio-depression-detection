# Tasks for Gemini

## Active Tasks

### Task 1: Implement ESP32-S3 Firmware for XVF3800 DoA Reading
**Status:** 🟡 Ready for work
**Priority:** High
**Directory:** `firmware/xvf3800/` (to be created)

#### Summary
Create ESP-IDF firmware for ESP32-S3 that reads Direction of Arrival (DoA) data from XVF3800 via I2C and includes it in the MQTT feature payload.

#### Design Document
See: `research-roadmap/docs/XVF3800_INTEGRATION_SKETCH.md` (Section 4: ESP32-S3 Firmware Changes)
See: `research-roadmap/docs/FIRMWARE_SPEC.md`

#### Subtasks

**1. Project Setup**
- [ ] Create `firmware/xvf3800/` directory structure
- [ ] Initialize ESP-IDF project (CMakeLists.txt, sdkconfig)
- [ ] Copy base structure from ReSpeaker firmware if exists

**2. XVF3800 I2C Communication**
- [ ] Create `xvf3800_doa.h` header with structs and function declarations
- [ ] Create `xvf3800_doa.c` implementation:
  - [ ] `xvf3800_init()` - Initialize I2C, verify XVF3800 presence
  - [ ] `xvf3800_get_status()` - Read DoA angle, confidence, active beam, AEC status
- [ ] Test I2C communication with XVF3800 dev board

**3. Extended Feature Payload**
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
**Status:** 🟡 Ready for work
**Priority:** Medium
**Directory:** `research-roadmap/experiments/`

#### Summary
Run comprehensive benchmarks of the feature extraction pipeline on the VM (simulating Pi 5) to establish baseline performance metrics.

#### Subtasks

**1. Prepare Test Data**
- [ ] Locate TESS dataset audio files
- [ ] Create 100 sample test set (mixed lengths: 3s, 5s, 10s)
- [ ] Document test set characteristics

**2. Benchmark Individual Extractors**
- [ ] Measure latency for each of 25+ features individually
- [ ] Identify bottleneck features
- [ ] Record memory usage per feature

**3. Benchmark Full Pipeline**
- [ ] Measure end-to-end latency (audio → all features)
- [ ] Test with 1, 2, 4, 8 concurrent streams
- [ ] Record CPU and memory under load

**4. Create Report**
- [ ] Generate `benchmark_results.md` with tables and analysis
- [ ] Identify features that could move to edge
- [ ] Recommend optimizations

#### Acceptance Criteria
- [ ] Benchmark script runs without errors
- [ ] Results saved to `research-roadmap/experiments/results/`
- [ ] Report identifies top 5 slowest features
- [ ] Recommendation for edge vs hub feature partitioning

---

## Completed Tasks

(None yet)

---

## Notes for Gemini

1. **Local execution:** You're running locally, be aware of race conditions with other agents
2. **Locking:** If editing shared files, coordinate or use separate branches
3. **Testing:** Run tests before committing
4. **Commits:** Use conventional commit format
5. **Docker:** The stack is running on this VM - don't restart without coordinating
