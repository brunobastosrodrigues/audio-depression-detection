# ESP32-S3 Edge Firmware Specification

## Overview

This document specifies the firmware for ESP32-S3 devices (ReSpeaker Lite and XVF3800) that perform on-device feature extraction in the zero-cloud architecture.

---

## Firmware Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     ESP32-S3 Firmware                           │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Audio Input  │  │  Processing  │  │     Output           │  │
│  │              │  │              │  │                      │  │
│  │  I2S Driver  │→ │  VAD        │→ │  MQTT Publisher      │  │
│  │  Ring Buffer │  │  MFCC       │  │  (features only)     │  │
│  │              │  │  F0         │  │                      │  │
│  │  [XVF3800:   │  │  Energy     │  │  WiFi Manager        │  │
│  │   DSP Input] │  │  ZCR        │  │  OTA Updates         │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    TFLite Micro Runtime                  │  │
│  │  - VAD model (~40KB)                                     │  │
│  │  - MFCC preprocessing (~30KB)                            │  │
│  │  - F0 extraction (algorithmic, no model)                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Memory Layout

### ESP32-S3 Memory Map
```
Internal SRAM (512KB):
├── System/FreeRTOS:     ~100KB
├── WiFi/BT Stack:       ~80KB
├── Audio Ring Buffer:   ~80KB (5 seconds @ 16kHz)
├── TFLite Arena:        ~100KB
├── Feature Buffers:     ~50KB
├── MQTT Client:         ~30KB
└── Application:         ~72KB

External PSRAM (8MB):
├── Extended Audio:      ~2MB (for longer buffers if needed)
├── Model Weights:       ~500KB
├── Scratch Memory:      ~500KB
└── Available:           ~5MB
```

---

## Feature Extraction Pipeline

### Stage 1: Audio Capture
```c
// Configuration
#define SAMPLE_RATE     16000
#define BITS_PER_SAMPLE 16
#define CHUNK_DURATION  5000  // ms
#define CHUNK_SAMPLES   (SAMPLE_RATE * CHUNK_DURATION / 1000)  // 80000

// Ring buffer for continuous capture
static int16_t audio_ring_buffer[CHUNK_SAMPLES];
static volatile size_t write_index = 0;

// I2S configuration for MEMS microphone
i2s_config_t i2s_config = {
    .mode = I2S_MODE_MASTER | I2S_MODE_RX,
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 1024,
};
```

### Stage 2: Voice Activity Detection (VAD)
```c
// VAD configuration
#define VAD_FRAME_SIZE      512     // 32ms @ 16kHz
#define VAD_THRESHOLD       0.5f
#define VAD_MIN_SPEECH_MS   500     // Minimum speech duration

typedef struct {
    TfLiteTensor* input;
    TfLiteTensor* output;
    float threshold;
    int consecutive_speech_frames;
    int consecutive_silence_frames;
} VADState;

// VAD inference
bool vad_is_speech(VADState* state, const int16_t* frame) {
    // Normalize to float [-1, 1]
    for (int i = 0; i < VAD_FRAME_SIZE; i++) {
        state->input->data.f[i] = frame[i] / 32768.0f;
    }

    // Run inference
    TfLiteStatus status = interpreter->Invoke();
    float confidence = state->output->data.f[0];

    // Apply threshold with hysteresis
    if (confidence > state->threshold) {
        state->consecutive_speech_frames++;
        state->consecutive_silence_frames = 0;
    } else {
        state->consecutive_silence_frames++;
        state->consecutive_speech_frames = 0;
    }

    // Require minimum consecutive frames
    return state->consecutive_speech_frames >= (VAD_MIN_SPEECH_MS / 32);
}
```

### Stage 3: MFCC Extraction
```c
// MFCC configuration
#define MFCC_NUM_COEFFS     13
#define MFCC_FRAME_SIZE     400     // 25ms @ 16kHz
#define MFCC_FRAME_STEP     160     // 10ms @ 16kHz
#define MFCC_NUM_FILTERS    40
#define MFCC_FFT_SIZE       512

typedef struct {
    float mfcc_mean[MFCC_NUM_COEFFS];
    float mfcc_std[MFCC_NUM_COEFFS];
    int frame_count;
} MFCCStats;

// Extract MFCC from audio chunk
void extract_mfcc(const int16_t* audio, size_t num_samples, MFCCStats* stats) {
    float frame_mfcc[MFCC_NUM_COEFFS];
    float sum[MFCC_NUM_COEFFS] = {0};
    float sum_sq[MFCC_NUM_COEFFS] = {0};
    int frame_count = 0;

    // Process frames
    for (size_t i = 0; i + MFCC_FRAME_SIZE <= num_samples; i += MFCC_FRAME_STEP) {
        // Apply window, FFT, mel filterbank, DCT (using TFLite or custom)
        compute_single_frame_mfcc(&audio[i], frame_mfcc);

        // Accumulate statistics
        for (int j = 0; j < MFCC_NUM_COEFFS; j++) {
            sum[j] += frame_mfcc[j];
            sum_sq[j] += frame_mfcc[j] * frame_mfcc[j];
        }
        frame_count++;
    }

    // Compute mean and std
    for (int j = 0; j < MFCC_NUM_COEFFS; j++) {
        stats->mfcc_mean[j] = sum[j] / frame_count;
        float variance = (sum_sq[j] / frame_count) - (stats->mfcc_mean[j] * stats->mfcc_mean[j]);
        stats->mfcc_std[j] = sqrtf(fmaxf(variance, 1e-6f));
    }
    stats->frame_count = frame_count;
}
```

### Stage 4: F0 (Pitch) Extraction
```c
// F0 configuration using autocorrelation
#define F0_MIN_HZ       50
#define F0_MAX_HZ       500
#define F0_FRAME_SIZE   800     // 50ms @ 16kHz

typedef struct {
    float f0_mean;
    float f0_std;
    float f0_min;
    float f0_max;
    int voiced_frames;
    int total_frames;
} F0Stats;

// Simple autocorrelation-based F0
float estimate_f0_frame(const int16_t* frame) {
    int min_lag = SAMPLE_RATE / F0_MAX_HZ;  // ~32 samples
    int max_lag = SAMPLE_RATE / F0_MIN_HZ;  // ~320 samples

    float max_corr = 0;
    int best_lag = 0;

    // Compute autocorrelation
    for (int lag = min_lag; lag <= max_lag; lag++) {
        float corr = 0;
        for (int i = 0; i < F0_FRAME_SIZE - lag; i++) {
            corr += frame[i] * frame[i + lag];
        }
        if (corr > max_corr) {
            max_corr = corr;
            best_lag = lag;
        }
    }

    // Voicing decision: correlation peak must be significant
    float zero_lag_corr = 0;
    for (int i = 0; i < F0_FRAME_SIZE; i++) {
        zero_lag_corr += frame[i] * frame[i];
    }

    if (max_corr / zero_lag_corr < 0.3f) {
        return 0;  // Unvoiced
    }

    return (float)SAMPLE_RATE / best_lag;
}

// Extract F0 statistics from chunk
void extract_f0(const int16_t* audio, size_t num_samples, F0Stats* stats) {
    float f0_values[500];  // Max frames
    int voiced_count = 0;

    for (size_t i = 0; i + F0_FRAME_SIZE <= num_samples; i += F0_FRAME_SIZE / 2) {
        float f0 = estimate_f0_frame(&audio[i]);
        if (f0 > 0) {
            f0_values[voiced_count++] = f0;
        }
        stats->total_frames++;
    }

    if (voiced_count == 0) {
        stats->f0_mean = 0;
        stats->f0_std = 0;
        stats->f0_min = 0;
        stats->f0_max = 0;
        stats->voiced_frames = 0;
        return;
    }

    // Compute statistics
    float sum = 0, sum_sq = 0;
    float min_f0 = f0_values[0], max_f0 = f0_values[0];

    for (int i = 0; i < voiced_count; i++) {
        sum += f0_values[i];
        sum_sq += f0_values[i] * f0_values[i];
        if (f0_values[i] < min_f0) min_f0 = f0_values[i];
        if (f0_values[i] > max_f0) max_f0 = f0_values[i];
    }

    stats->f0_mean = sum / voiced_count;
    stats->f0_std = sqrtf((sum_sq / voiced_count) - (stats->f0_mean * stats->f0_mean));
    stats->f0_min = min_f0;
    stats->f0_max = max_f0;
    stats->voiced_frames = voiced_count;
}
```

### Stage 5: Energy Features
```c
typedef struct {
    float rms_mean;
    float rms_std;
    float zcr_mean;  // Zero-crossing rate
} EnergyStats;

void extract_energy(const int16_t* audio, size_t num_samples, EnergyStats* stats) {
    float rms_sum = 0, rms_sum_sq = 0;
    float zcr_sum = 0;
    int frame_count = 0;

    for (size_t i = 0; i + 1600 <= num_samples; i += 800) {  // 100ms frames, 50ms hop
        // RMS
        float sq_sum = 0;
        for (int j = 0; j < 1600; j++) {
            float sample = audio[i + j] / 32768.0f;
            sq_sum += sample * sample;
        }
        float rms = sqrtf(sq_sum / 1600);
        rms_sum += rms;
        rms_sum_sq += rms * rms;

        // ZCR
        int crossings = 0;
        for (int j = 1; j < 1600; j++) {
            if ((audio[i + j - 1] > 0) != (audio[i + j] > 0)) {
                crossings++;
            }
        }
        zcr_sum += (float)crossings / 1600;

        frame_count++;
    }

    stats->rms_mean = rms_sum / frame_count;
    stats->rms_std = sqrtf((rms_sum_sq / frame_count) - (stats->rms_mean * stats->rms_mean));
    stats->zcr_mean = zcr_sum / frame_count;
}
```

---

## MQTT Message Format

### Feature Payload (MessagePack or JSON)
```c
typedef struct __attribute__((packed)) {
    // Header (16 bytes)
    uint8_t  board_id[6];       // MAC address
    uint32_t timestamp;         // Unix timestamp
    uint16_t chunk_duration_ms; // 5000
    uint16_t sample_rate;       // 16000

    // VAD (4 bytes)
    float    vad_confidence;

    // MFCC (104 bytes = 13 * 8)
    float    mfcc_mean[13];
    float    mfcc_std[13];

    // F0 (20 bytes)
    float    f0_mean;
    float    f0_std;
    float    f0_min;
    float    f0_max;
    float    f0_voiced_ratio;

    // Energy (12 bytes)
    float    rms_mean;
    float    rms_std;
    float    zcr_mean;

    // XVF3800 only (8 bytes)
    float    doa_angle;         // 0-360 degrees
    float    doa_confidence;

    // Total: ~164 bytes (vs 160KB raw audio = ~1000x compression)
} FeaturePayload;

// MQTT topic
// ihearyou/features/{board_mac}
```

### Publishing Features
```c
void publish_features(const FeaturePayload* payload) {
    char topic[64];
    snprintf(topic, sizeof(topic), "ihearyou/features/%02x%02x%02x%02x%02x%02x",
             payload->board_id[0], payload->board_id[1], payload->board_id[2],
             payload->board_id[3], payload->board_id[4], payload->board_id[5]);

    // Serialize to MessagePack (more compact) or JSON
    uint8_t buffer[256];
    size_t len = msgpack_serialize(payload, buffer, sizeof(buffer));

    esp_mqtt_client_publish(mqtt_client, topic, (char*)buffer, len, 1, 0);
}
```

---

## Main Application Loop

```c
void app_main(void) {
    // Initialize
    ESP_ERROR_CHECK(nvs_flash_init());
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    // Connect to WiFi
    wifi_init_sta();

    // Initialize audio
    i2s_init();

    // Initialize TFLite
    tflite_init();

    // Initialize MQTT
    mqtt_init();

    // Get board ID (MAC address)
    uint8_t board_id[6];
    esp_wifi_get_mac(WIFI_IF_STA, board_id);

    // Processing state
    VADState vad_state;
    vad_init(&vad_state);

    int16_t audio_chunk[CHUNK_SAMPLES];
    FeaturePayload payload;

    while (1) {
        // 1. Capture 5 seconds of audio
        size_t bytes_read = 0;
        i2s_read(I2S_NUM_0, audio_chunk, sizeof(audio_chunk), &bytes_read, portMAX_DELAY);

        // 2. Run VAD on chunk
        bool has_speech = false;
        for (size_t i = 0; i + VAD_FRAME_SIZE <= CHUNK_SAMPLES; i += VAD_FRAME_SIZE) {
            if (vad_is_speech(&vad_state, &audio_chunk[i])) {
                has_speech = true;
                break;  // Found speech, process chunk
            }
        }

        if (!has_speech) {
            // No speech detected, skip processing
            ESP_LOGI(TAG, "No speech detected, skipping");
            continue;
        }

        // 3. Extract features
        MFCCStats mfcc_stats;
        extract_mfcc(audio_chunk, CHUNK_SAMPLES, &mfcc_stats);

        F0Stats f0_stats;
        extract_f0(audio_chunk, CHUNK_SAMPLES, &f0_stats);

        EnergyStats energy_stats;
        extract_energy(audio_chunk, CHUNK_SAMPLES, &energy_stats);

        // 4. Build payload
        memcpy(payload.board_id, board_id, 6);
        payload.timestamp = (uint32_t)time(NULL);
        payload.chunk_duration_ms = CHUNK_DURATION;
        payload.sample_rate = SAMPLE_RATE;

        memcpy(payload.mfcc_mean, mfcc_stats.mfcc_mean, sizeof(payload.mfcc_mean));
        memcpy(payload.mfcc_std, mfcc_stats.mfcc_std, sizeof(payload.mfcc_std));

        payload.f0_mean = f0_stats.f0_mean;
        payload.f0_std = f0_stats.f0_std;
        payload.f0_min = f0_stats.f0_min;
        payload.f0_max = f0_stats.f0_max;
        payload.f0_voiced_ratio = (float)f0_stats.voiced_frames / f0_stats.total_frames;

        payload.rms_mean = energy_stats.rms_mean;
        payload.rms_std = energy_stats.rms_std;
        payload.zcr_mean = energy_stats.zcr_mean;

        // 5. Publish (no raw audio!)
        publish_features(&payload);

        ESP_LOGI(TAG, "Published features: F0=%.1fHz, RMS=%.4f", payload.f0_mean, payload.rms_mean);
    }
}
```

---

## XVF3800-Specific Additions

```c
// XVF3800 provides pre-processed audio via I2S
// Plus additional data via I2C/SPI

typedef struct {
    float doa_angle;        // 0-360 degrees
    float doa_confidence;   // 0-1
    uint8_t active_beam;    // 0=scanning, 1-2=focused
} XVF3800Status;

// Read XVF3800 status registers
void xvf3800_get_status(XVF3800Status* status) {
    // Read via I2C
    uint8_t data[8];
    i2c_master_read_from_device(I2C_NUM_0, XVF3800_I2C_ADDR, data, sizeof(data), 1000);

    status->doa_angle = ((data[0] << 8) | data[1]) / 100.0f;
    status->doa_confidence = data[2] / 255.0f;
    status->active_beam = data[3];
}

// In main loop, add:
if (board_type == BOARD_XVF3800) {
    XVF3800Status xvf_status;
    xvf3800_get_status(&xvf_status);
    payload.doa_angle = xvf_status.doa_angle;
    payload.doa_confidence = xvf_status.doa_confidence;
}
```

---

## Build Configuration

### sdkconfig (ESP-IDF)
```ini
# Memory
CONFIG_ESP32S3_SPIRAM_SUPPORT=y
CONFIG_SPIRAM_MODE_OCT=y
CONFIG_SPIRAM_SPEED_80M=y

# WiFi
CONFIG_ESP_WIFI_STATIC_RX_BUFFER_NUM=10
CONFIG_ESP_WIFI_DYNAMIC_RX_BUFFER_NUM=32

# FreeRTOS
CONFIG_FREERTOS_HZ=1000

# TFLite
CONFIG_TFLITE_MICRO_ENABLE=y
```

### CMakeLists.txt
```cmake
idf_component_register(
    SRCS
        "main.c"
        "audio.c"
        "vad.c"
        "mfcc.c"
        "f0.c"
        "energy.c"
        "mqtt.c"
        "wifi.c"
    INCLUDE_DIRS
        "include"
    REQUIRES
        driver
        esp_wifi
        mqtt
        nvs_flash
        tflite-micro
)
```

---

## Testing

### Unit Tests (On Host)
```bash
# Test MFCC extraction accuracy
cd test/
python test_mfcc_accuracy.py --reference librosa --firmware firmware_mfcc

# Test F0 extraction accuracy
python test_f0_accuracy.py --reference praat --firmware firmware_f0
```

### Integration Tests (On Device)
```bash
# Flash and test
idf.py build flash monitor

# Send test audio via TCP
python send_test_audio.py --device 192.168.1.20 --audio test.wav

# Verify MQTT output
mosquitto_sub -t "ihearyou/features/#" -v
```

---

## Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Audio capture | Real-time | No dropped samples |
| VAD latency | <15ms per frame | ESP timer |
| MFCC extraction | <50ms per chunk | ESP timer |
| F0 extraction | <30ms per chunk | ESP timer |
| Energy features | <5ms per chunk | ESP timer |
| Total processing | <100ms per 5s chunk | ESP timer |
| Memory usage | <400KB SRAM | heap_caps_get_info |
| Power consumption | <1W active | Multimeter |
