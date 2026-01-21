# Hardware Specifications and Capabilities

## Overview

| Device | Qty | Role | Key Capability |
|--------|-----|------|----------------|
| Raspberry Pi 5 | 1 | Home Hub | Heavy ML inference |
| ReSpeaker Lite | 4 | Edge + Capture | Simple features |
| XVF3800 | 4 | Edge + DSP | Advanced audio processing |

---

## Raspberry Pi 5 (Home Hub)

### Specifications
- **CPU:** Quad-core Arm Cortex-A76 @ 2.4GHz
- **RAM:** 8GB LPDDR4X-4267
- **Storage:** microSD or NVMe SSD via PCIe 2.0 x1
- **GPU:** VideoCore VII @ 800MHz
- **WiFi:** 802.11ac dual-band (WiFi 5)
- **Ethernet:** Gigabit
- **Power:** 5V/5A (27W) USB-C

### ML Performance Benchmarks
Based on [Raspberry Pi benchmarks](https://www.raspberrypi.com/news/benchmarking-raspberry-pi-5/) and [TinyML research](https://arxiv.org/html/2509.04721):

| Model | Pi 4 Latency | Pi 5 Estimated | Notes |
|-------|--------------|----------------|-------|
| Keyword Spotting | 1.76ms | ~0.7ms | 2.5x speedup |
| MobileNet V2 | ~50ms | ~20ms | Image classification |
| YOLOv8n (640x640) | N/A | ~83ms (12fps) | With ncnn framework |
| OpenSMILE eGeMAPS | ~300ms | ~120ms | Estimated |
| Resemblyzer D-vector | ~200ms | ~80ms | Estimated |

### Estimated IHearYou Performance on Pi 5
| Component | Current (Server) | Pi 5 Estimated |
|-----------|------------------|----------------|
| Feature extraction (25 features) | 300-500ms | 150-250ms |
| Speaker verification | 150-300ms | 60-120ms |
| Temporal modeling | <50ms | <50ms |
| DSM-5 scoring | <10ms | <10ms |
| **Total per chunk** | 500-860ms | **270-430ms** |

### Recommended Configuration
- **Model:** Raspberry Pi 5 8GB
- **Storage:** 256GB NVMe SSD (Pi 5 NVMe HAT)
- **Cooling:** Active cooler (official or Pimoroni)
- **Power:** Official 27W power supply
- **Case:** With ventilation for sustained load

### Software Stack
```yaml
# docker-compose.yml for Pi 5
services:
  mongodb:
    image: arm64v8/mongo:7
    volumes:
      - ./data/mongodb:/data/db

  mosquitto:
    image: eclipse-mosquitto:2
    ports:
      - "1883:1883"

  voice-metrics:
    build: ./services/voice_metrics
    depends_on: [mongodb, mosquitto]
    deploy:
      resources:
        limits:
          memory: 2G

  analysis-layer:
    build: ./services/analysis_layer
    depends_on: [mongodb]
    deploy:
      resources:
        limits:
          memory: 1G

  dashboard:
    build: ./services/dashboard
    ports:
      - "8084:8084"
```

---

## ReSpeaker Lite (Edge Device)

### Specifications
- **MCU:** ESP32-S3 (dual-core Xtensa LX7 @ 240MHz)
- **Memory:** 512KB SRAM + 8MB PSRAM
- **Flash:** 16MB
- **Microphones:** 2x digital MEMS (I2S)
- **Audio:** 16kHz/16-bit, mono or stereo
- **Connectivity:** WiFi 802.11 b/g/n, Bluetooth 5.0
- **Power:** 5V USB or 3.3V GPIO

### ESP32-S3 Compute Capabilities
Based on [TinyML benchmarks](https://link.springer.com/chapter/10.1007/978-3-031-97907-1_17):

| Metric | Value |
|--------|-------|
| INT8 inference throughput | ~100 inferences/sec |
| Power consumption | 0.66W @ 5V (TinyML active) |
| TFLite Micro model limit | ~500KB (with PSRAM) |
| MFCC extraction (13 coef) | ~30-50ms per second of audio |
| VAD inference | ~8-15ms per frame |

### Target Features for Edge Extraction
| Feature | Complexity | ESP32-S3 Feasibility | Notes |
|---------|------------|---------------------|-------|
| VAD | Low | ✅ Excellent | Silero or WebRTC VAD |
| MFCC (13 coef) | Medium | ✅ Good | INT8 quantized |
| F0 (pitch) mean | Medium | ✅ Good | YIN or autocorrelation |
| F0 std/range | Medium | ⚠️ Moderate | Requires buffering |
| RMS energy | Low | ✅ Excellent | Trivial computation |
| Zero-crossing rate | Low | ✅ Excellent | Trivial computation |
| Spectral centroid | Medium | ⚠️ Moderate | FFT required |

### Memory Budget (ESP32-S3)
```
Total SRAM: 512KB
  - System overhead: ~100KB
  - Audio buffer (5s @ 16kHz): 160KB
  - VAD model: ~40KB
  - MFCC model: ~50KB
  - F0 computation buffer: ~20KB
  - MQTT client: ~30KB
  - Remaining: ~112KB

Total PSRAM: 8MB
  - Extended audio buffer: as needed
  - Model weights: up to 500KB
  - Feature output buffer: ~10KB
```

### Firmware Architecture
```c
// Main loop on ESP32-S3
void app_main() {
    // Initialize
    i2s_init();          // Audio capture
    wifi_init();         // Network
    mqtt_init();         // Communication
    tflite_init();       // ML runtime

    while (1) {
        // Capture 5-second audio chunk
        audio_buffer = capture_audio(5000);

        // On-device processing
        if (vad_detect(audio_buffer)) {
            mfcc = extract_mfcc(audio_buffer);    // 13 coefficients
            f0_stats = extract_f0(audio_buffer);  // mean, std, range
            energy = extract_rms(audio_buffer);

            // Publish features only (no audio)
            mqtt_publish_features(mfcc, f0_stats, energy);
        }

        // ~200 bytes transmitted vs ~160KB raw audio
    }
}
```

---

## XVF3800 (Edge Device + DSP)

### Specifications
- **Voice Processor:** XMOS xcore.ai (VocalFusion XVF3800)
- **MCU:** ESP32-S3 (same as ReSpeaker Lite)
- **Microphones:** 4x digital MEMS (I2S)
- **Audio:** 16kHz or 48kHz, processed output
- **DSP Features:** Hardware-accelerated

### XMOS XVF3800 DSP Capabilities
Based on [XMOS documentation](https://www.xmos.com/xvf3800):

| Feature | Capability |
|---------|------------|
| **Acoustic Echo Cancellation (AEC)** | Removes speaker echo, enables full-duplex |
| **Beamforming** | 3 beams: 1 scanning + 2 focused |
| **Noise Suppression** | Stationary + non-stationary noise |
| **Dereverberation** | Reduces room reflections |
| **Automatic Gain Control** | 60dB dynamic range |
| **Direction of Arrival (DoA)** | 360° coverage, up to 5m range |
| **Sample Rates** | 16kHz or 48kHz I2S |

### Advantages Over ReSpeaker Lite
| Aspect | ReSpeaker Lite | XVF3800 |
|--------|----------------|---------|
| Microphones | 2 | 4 |
| Beamforming | Basic (software) | Advanced (hardware) |
| AEC | None | Hardware |
| Noise suppression | None | Hardware |
| DoA detection | None | 360° hardware |
| Far-field range | ~2m | ~5m |
| Multi-speaker | Poor | 2 focused beams |

### XVF3800 Output to ESP32-S3
The XMOS processor outputs **cleaned, enhanced audio** to the ESP32-S3:
- Echo-cancelled
- Beamformed (focused on speaker)
- Noise-suppressed
- Gain-normalized

This means ESP32-S3 receives **higher quality input** for feature extraction.

### Additional Features Enabled by XVF3800
| Feature | Value | Use Case |
|---------|-------|----------|
| DoA angle | 0-360° | Speaker localization |
| Beam activity | which beam active | Multi-speaker detection |
| Voice activity | from DSP | More reliable VAD |

### Firmware Architecture (XVF3800)
```c
// XVF3800 enhanced pipeline
void app_main() {
    xvf3800_init();      // Initialize XMOS DSP
    i2s_init();          // Audio from XVF3800
    wifi_init();
    mqtt_init();
    tflite_init();

    while (1) {
        // Get DSP-processed audio (already cleaned)
        audio_buffer = capture_audio_from_xvf3800(5000);
        doa_angle = xvf3800_get_doa();

        // VAD likely more reliable due to noise suppression
        if (vad_detect(audio_buffer)) {
            mfcc = extract_mfcc(audio_buffer);
            f0_stats = extract_f0(audio_buffer);
            energy = extract_rms(audio_buffer);

            // Include DoA for spatial tracking
            mqtt_publish_features(mfcc, f0_stats, energy, doa_angle);
        }
    }
}
```

---

## Network Architecture

### Local Network Topology
```
                    [Local WiFi Router]
                    (No internet uplink)
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   [Pi 5 Hub]      [ReSpeaker x4]      [XVF3800 x4]
   192.168.1.10    192.168.1.20-23     192.168.1.30-33
        │
        ├── MQTT Broker (1883)
        ├── MongoDB (27017)
        └── Dashboard (8084)
```

### MQTT Topic Structure
```
ihearyou/
  ├── features/
  │   ├── {board_id}/
  │   │   ├── mfcc        # 13 coefficients
  │   │   ├── f0          # pitch statistics
  │   │   ├── energy      # RMS values
  │   │   └── doa         # XVF3800 only
  │   └── ...
  ├── status/
  │   ├── {board_id}/
  │   │   ├── health      # heartbeat
  │   │   └── battery     # if applicable
  │   └── ...
  └── config/
      └── {board_id}/     # remote configuration
```

### Bandwidth Requirements
| Data Type | Size | Frequency | Bandwidth |
|-----------|------|-----------|-----------|
| Edge features | ~200 bytes | Every 5s (when speaking) | <1 KB/min |
| Status heartbeat | ~50 bytes | Every 30s | <0.1 KB/min |
| **Total per device** | - | - | **<2 KB/min** |

Compare to raw audio: 16kHz × 16-bit = 32 KB/s = **1.92 MB/min**

**Compression ratio: ~1000x**

---

## Power Considerations

### Estimated Power Consumption
| Device | Idle | Active (TinyML) | Peak |
|--------|------|-----------------|------|
| Raspberry Pi 5 | 3W | 8W | 12W |
| ReSpeaker Lite (ESP32-S3) | 0.1W | 0.7W | 1W |
| XVF3800 | 0.3W | 1.2W | 1.5W |

### Total System Power
- Pi 5: ~8W average
- 4x ReSpeaker: ~2.8W average
- 4x XVF3800: ~4.8W average
- **Total: ~16W average**

For battery backup: 100Wh battery = ~6 hours runtime

---

## Bill of Materials

| Item | Qty | Unit Cost | Total |
|------|-----|-----------|-------|
| Raspberry Pi 5 8GB | 1 | $80 | $80 |
| Pi 5 NVMe HAT + 256GB SSD | 1 | $50 | $50 |
| Pi 5 Active Cooler | 1 | $10 | $10 |
| Pi 5 27W Power Supply | 1 | $15 | $15 |
| ReSpeaker Lite | 4 | $15 | $60 |
| XVF3800 Board | 4 | $40 | $160 |
| WiFi Router (basic) | 1 | $30 | $30 |
| microSD cards (32GB) | 4 | $8 | $32 |
| USB cables | 8 | $5 | $40 |
| **Total** | - | - | **~$477** |

This is a complete, deployable system for under $500.
