# System Architecture: Zero-Cloud Hierarchical Edge Processing

## Design Principles

1. **Zero Cloud:** No data leaves the household under any circumstance
2. **Privacy by Design:** Raw audio never transmitted - only compressed features
3. **Graceful Degradation:** System works even if Pi 5 is offline (edge-only mode)
4. **Commodity Hardware:** All components available off-the-shelf

## Three-Tier Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           HOUSEHOLD BOUNDARY                                 │
│                        (No data crosses this line)                          │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      TIER 1: EDGE DEVICES                           │   │
│  │                                                                     │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │ ReSpeaker #1 │  │ ReSpeaker #2 │  │ ReSpeaker #3 │  ...         │   │
│  │  │   (Kitchen)  │  │  (Bedroom)   │  │  (Office)    │              │   │
│  │  │              │  │              │  │              │              │   │
│  │  │ ESP32-S3     │  │ ESP32-S3     │  │ ESP32-S3     │              │   │
│  │  │ - VAD        │  │ - VAD        │  │ - VAD        │              │   │
│  │  │ - MFCC (INT8)│  │ - MFCC (INT8)│  │ - MFCC (INT8)│              │   │
│  │  │ - F0 (INT8)  │  │ - F0 (INT8)  │  │ - F0 (INT8)  │              │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │   │
│  │         │                 │                 │                       │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  XVF3800 #1  │  │  XVF3800 #2  │  │  XVF3800 #3  │  ...         │   │
│  │  │  (Living)    │  │   (Study)    │  │   (Hall)     │              │   │
│  │  │              │  │              │  │              │              │   │
│  │  │ XMOS DSP:    │  │ XMOS DSP:    │  │ XMOS DSP:    │              │   │
│  │  │ - AEC        │  │ - AEC        │  │ - AEC        │              │   │
│  │  │ - Beamform   │  │ - Beamform   │  │ - Beamform   │              │   │
│  │  │ - DoA (360°) │  │ - DoA (360°) │  │ - DoA (360°) │              │   │
│  │  │ ESP32-S3:    │  │ ESP32-S3:    │  │ ESP32-S3:    │              │   │
│  │  │ - MFCC+F0    │  │ - MFCC+F0    │  │ - MFCC+F0    │              │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │   │
│  │         │                 │                 │                       │   │
│  └─────────┼─────────────────┼─────────────────┼───────────────────────┘   │
│            │                 │                 │                           │
│            │    WiFi/MQTT (features only, ~200 bytes/utterance)            │
│            │                 │                 │                           │
│  ┌─────────▼─────────────────▼─────────────────▼───────────────────────┐   │
│  │                      TIER 2: HOME HUB                               │   │
│  │                      Raspberry Pi 5 (8GB)                           │   │
│  │                                                                     │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │                    Processing Pipeline                       │   │   │
│  │  │                                                             │   │   │
│  │  │  [Edge Features] → [Feature Completion] → [Speaker Verify]  │   │   │
│  │  │         │                   │                    │          │   │   │
│  │  │         ▼                   ▼                    ▼          │   │   │
│  │  │  [Jitter/Shimmer]   [HNR/CPP]        [D-vector Match]       │   │   │
│  │  │  [Spectral feat]    [Formants]       [Context Class]        │   │   │
│  │  │         │                   │                    │          │   │   │
│  │  │         └───────────────────┼────────────────────┘          │   │   │
│  │  │                             ▼                               │   │   │
│  │  │                    [Feature Fusion]                         │   │   │
│  │  │                             │                               │   │   │
│  │  │                             ▼                               │   │   │
│  │  │                    [Temporal Modeling]                      │   │   │
│  │  │                    (EMA + Spike Dampening)                  │   │   │
│  │  │                             │                               │   │   │
│  │  │                             ▼                               │   │   │
│  │  │                    [DSM-5 Indicator Scoring]                │   │   │
│  │  │                             │                               │   │   │
│  │  │                             ▼                               │   │   │
│  │  │                    [Local Dashboard]                        │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                     │   │
│  │  Storage: Local MongoDB (encrypted at rest)                        │   │
│  │  Dashboard: Local Streamlit (http://raspberrypi.local:8084)        │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ✗ NO EXTERNAL CONNECTION
```

## Data Flow

### What Stays on Edge (ESP32-S3)
- Raw PCM audio (16kHz, 16-bit)
- Intermediate DSP buffers
- Full waveform data

### What Leaves Edge → Home Hub (WiFi/MQTT)
- Compressed features only (~200 bytes per 5-second utterance):
  - 13 MFCCs (INT8) = 13 bytes
  - F0 statistics (mean, std, range) = 12 bytes
  - Energy statistics = 8 bytes
  - VAD confidence = 4 bytes
  - Board ID + timestamp = 16 bytes
  - XVF3800 only: DoA angle = 4 bytes

### What Stays on Home Hub (Pi 5)
- All feature data
- Speaker embeddings
- Indicator scores
- Dashboard data

### What Leaves Household
- **NOTHING** - by design

## Feature Partitioning Strategy

| Feature | Compute Location | Rationale |
|---------|-----------------|-----------|
| **VAD** | Edge (ESP32) | Silero VAD runs in ~8ms on ESP32-S3 |
| **MFCC (13 coef)** | Edge (ESP32) | Well-supported by TFLite Micro, INT8 viable |
| **F0 (pitch)** | Edge (ESP32) | YIN algorithm implementable in fixed-point |
| **Energy/RMS** | Edge (ESP32) | Trivial computation |
| **AEC/Beamforming** | Edge (XVF3800 only) | Hardware DSP on XMOS |
| **DoA** | Edge (XVF3800 only) | Hardware DSP on XMOS |
| **Jitter/Shimmer** | Home Hub (Pi 5) | Requires precise F0 tracking, float32 |
| **HNR/CPP** | Home Hub (Pi 5) | Spectral analysis, float32 |
| **Formants** | Home Hub (Pi 5) | LPC analysis, computationally heavy |
| **D-vector (speaker)** | Home Hub (Pi 5) | Resemblyzer model, ~50MB |
| **Temporal Modeling** | Home Hub (Pi 5) | EMA aggregation, database queries |
| **DSM-5 Scoring** | Home Hub (Pi 5) | Rule-based, lightweight |

## Latency Budget

| Stage | Target | Location |
|-------|--------|----------|
| Audio capture | 5000ms | Edge (chunk size) |
| VAD filtering | <50ms | Edge |
| Edge feature extraction | <100ms | Edge |
| WiFi transmission | <20ms | Network |
| Hub feature completion | <200ms | Pi 5 |
| Speaker verification | <100ms | Pi 5 |
| Temporal aggregation | <50ms | Pi 5 |
| **Total E2E** | **<5500ms** | - |

## Privacy Guarantees

### Formal Claims

1. **Audio Non-Transmission:** Raw PCM audio never leaves the ESP32-S3 memory space
2. **Feature Irreversibility:** MFCC + F0 statistics cannot reconstruct intelligible speech
3. **Local Storage:** All persistent data encrypted at rest on Pi 5
4. **No Network Egress:** Pi 5 has no internet connection (air-gapped or firewall blocked)

### Attack Surface Analysis

| Attack Vector | Mitigation |
|---------------|------------|
| WiFi sniffing | Features only, not audio; optional WPA3 encryption |
| Pi 5 compromise | Full disk encryption, no internet access |
| Physical access | Device authentication, encrypted storage |
| Side-channel | Features too compressed for reconstruction |

## Comparison: Current vs Target Architecture

| Aspect | Current (Cloud) | Target (Zero-Cloud) |
|--------|-----------------|---------------------|
| Raw audio transmission | To server | Never leaves ESP32 |
| Feature extraction | Server | Split: Edge + Pi 5 |
| Speaker verification | Server | Pi 5 |
| Database | Cloud MongoDB | Local MongoDB on Pi 5 |
| Dashboard | Cloud Streamlit | Local Streamlit on Pi 5 |
| Internet dependency | Required | None |
| Privacy | Heuristic | Formal guarantees |

## Hardware Requirements

### Raspberry Pi 5 (Home Hub)
- Model: Raspberry Pi 5 8GB
- Storage: 128GB+ microSD or NVMe SSD (recommended)
- Cooling: Active cooling required for sustained ML inference
- Network: WiFi 6 or Ethernet (local network only)
- Power: Official 27W USB-C power supply

### ESP32-S3 Boards
- Memory: 512KB SRAM + 8MB PSRAM minimum
- Flash: 16MB for firmware + TFLite models
- Microphone: I2S digital MEMS (onboard)

### Network
- Local WiFi router (no internet uplink required)
- MQTT broker on Pi 5 (Mosquitto)
- mDNS for device discovery

## Software Stack

### Edge (ESP32-S3)
- ESP-IDF 5.x
- TensorFlow Lite Micro
- Edge Impulse runtime (optional)
- MQTT client (PubSubClient)

### Home Hub (Pi 5)
- Raspberry Pi OS (64-bit)
- Python 3.11+
- Docker + Docker Compose
- MongoDB 7.x
- Mosquitto MQTT broker
- FastAPI services
- Streamlit dashboard

## Migration Path

### Phase 1: Pi 5 as Drop-in Server Replacement
- Move current Docker stack to Pi 5
- Validate performance with current architecture
- Benchmark: feature extraction latency, memory usage

### Phase 2: Edge Feature Offloading
- Implement MFCC + F0 on ESP32-S3
- Modify voice_metrics_service to accept edge features
- Validate feature accuracy vs server extraction

### Phase 3: Full Zero-Cloud
- Remove all cloud dependencies
- Air-gap Pi 5 or firewall block egress
- Implement local-only dashboard authentication
