# Current System State (Baseline - January 2026)

This document captures the stable state of the IHearYou system before the zero-cloud architecture migration.

## Version Information
- **Commit:** 2cb51b7 (docs: add TESS dataset attribution and license information)
- **Date:** January 2026
- **Branch:** main
- **Status:** Stable, production-ready for current architecture

---

## Current Architecture: Server-Based

```
┌─────────────────────────────────────────────────────────────────┐
│                     CURRENT ARCHITECTURE                        │
│                                                                 │
│  Edge Devices (ESP32-S3)          Server (Cloud/Local)         │
│  ┌─────────────────────┐          ┌─────────────────────────┐  │
│  │ ReSpeaker Lite      │          │ Docker Compose Stack    │  │
│  │ - Audio capture     │──TCP────▶│                         │  │
│  │ - Raw PCM streaming │          │ - ReSpeaker Service     │  │
│  │                     │          │ - Voice Metrics         │  │
│  └─────────────────────┘          │ - Temporal Modeling     │  │
│                                   │ - Analysis Layer        │  │
│                                   │ - Dashboard             │  │
│                                   │ - MongoDB               │  │
│                                   │ - MQTT Broker           │  │
│                                   └─────────────────────────┘  │
│                                                                 │
│  Note: ALL processing happens on server                        │
│  Edge devices only capture and stream raw audio                │
└─────────────────────────────────────────────────────────────────┘
```

---

## System Components

### 1. Data Ingestion Layer
- **Service:** `respeaker_service.py`
- **Port:** 8010 (TCP)
- **Function:**
  - Receives raw PCM audio from ReSpeaker boards
  - Applies Silero VAD (server-side)
  - Publishes to MQTT

### 2. Voice Metrics Service
- **Function:**
  - Scene analysis (speaker verification via D-vectors)
  - Feature extraction (25+ paralinguistic features)
  - OpenSMILE eGeMAPS + custom extractors
- **Output:** `raw_metrics` collection

### 3. Temporal Context Modeling
- **Port:** 8082
- **Function:**
  - Daily aggregation
  - EMA smoothing (α=0.13, 14-day effective window)
  - Spike dampening
- **Output:** `contextual_metrics` collection

### 4. Analysis Layer
- **Port:** 8083
- **Function:**
  - Z-score normalization
  - DSM-5 indicator mapping
  - XAI explanations
- **Output:** `indicator_scores` collection

### 5. Dashboard
- **Port:** 8084
- **Framework:** Streamlit
- **Pages:** 11 (Home, Overview, Indicators, Trends, Self-Report, Boards, Data Tools, User Management, Scene Forensics, Settings, Research Validation)

---

## Feature Extraction Pipeline (Server-Side)

### Features Currently Extracted (25+)

| Category | Features |
|----------|----------|
| **F0 Dynamics** | f0_avg, f0_std, f0_range, f0_cv, f0_iqr, f0_entropy |
| **HNR Dynamics** | hnr_mean, hnr_std, hnr_cv, hnr_entropy |
| **RMS Energy** | rms_energy_mean, rms_energy_std, rms_energy_cv, rms_energy_iqr, rms_energy_entropy |
| **Formant Dynamics** | formant_f1_mean, formant_f1_std, formant_f1_cv, formant_f1_iqr, formant_f1_entropy |
| **Interaction Dynamics** | silence_ratio, speech_velocity, voiced_ratio, unvoiced_ratio, pause_count, pause_mean, pause_std, pause_max, pause_total_duration |
| **Voice Quality** | jitter, shimmer, snr, spectral_flatness, temporal_modulation, spectral_modulation |
| **Miscellaneous** | voice_onset_time, glottal_pulse_rate, f2_transition_speed |

### Extractors Used
- OpenSMILE (eGeMAPSv02 LLD level)
- Librosa (spectral features)
- Praat-Parselmouth (prosodic analysis)
- Resemblyzer (speaker embeddings)
- Custom extractors

---

## DSM-5 Indicator Mapping

| Indicator | # Features Mapped | Status |
|-----------|-------------------|--------|
| 1. Depressed mood | 12 | ✅ Active |
| 2. Loss of interest | 5+ | ✅ Active |
| 3. Weight changes | 0 | ⚠️ Not acoustically measurable |
| 4. Sleep disturbances | 3 | ✅ Active |
| 5. Psychomotor changes | 10 | ✅ Active |
| 6. Fatigue | 2 | ✅ Active |
| 7. Worthlessness | 0 | ⚠️ Requires content analysis |
| 8. Concentration difficulty | 8 | ✅ Active |
| 9. Thoughts of death | 0 | ⚠️ Requires content analysis |

---

## Performance Characteristics (Current Server)

| Metric | Value |
|--------|-------|
| Feature extraction latency | 300-500ms per 5s chunk |
| Speaker verification | 150-300ms (cold), 50-100ms (cached) |
| End-to-end latency | 500-860ms |
| Concurrent boards | Tested up to 50 |
| Memory usage | ~2GB for voice metrics service |

---

## Database Schema

### Collections (MongoDB)
```
iotsensing_{mode}/
├── raw_metrics          # Per-utterance features (TTL 30 days)
├── aggregated_metrics   # Daily summaries
├── contextual_metrics   # EMA-smoothed with time windows
├── analyzed_metrics     # Z-score normalized
├── indicator_scores     # DSM-5 scores + XAI
├── baseline             # User-specific statistics
├── phq9_submissions     # Self-report history
├── users                # Registration data
├── voice_profiling      # D-vector embeddings
├── boards               # ReSpeaker configuration
├── environments         # Physical locations
├── scene_logs           # Speaker verification decisions
└── audio_quality_metrics # SNR, clipping, dBFS
```

---

## System Modes
- **Live:** Real patient data (`iotsensing_live`)
- **Dataset:** Research validation with TESS (`iotsensing_dataset`)
- **Demo:** Pre-seeded showcase data (`iotsensing_demo`)

---

## Hardware Currently Supported
- ReSpeaker Lite (2-mic + ESP32-S3)
- ReSpeaker 4-mic array
- USB microphones

---

## What This Baseline Does NOT Have
- On-device feature extraction (all server-side)
- Zero-cloud capability (requires server)
- XVF3800 support (not yet integrated)
- Raspberry Pi 5 deployment (not tested)
- Formal privacy guarantees (heuristic only)

---

## Files Changed Since Last Major Release

```
2cb51b7 docs: add TESS dataset attribution and license information
00ebbb5 docs: add screenshots for each system mode to README
d8197c7 Add files via upload
4f55186 fix: remove invalid acoustic metrics for 'Thoughts of Death' indicator
268c732 refactor: make Research Validation more academic, fix mode visibility
```

---

## Migration Notes

When migrating to zero-cloud architecture:

1. **Keep current server code as fallback** - Pi 5 can run same Docker stack
2. **Add edge feature extraction** - New firmware for ESP32-S3
3. **Modify voice_metrics_service** - Accept pre-extracted features from edge
4. **Test thoroughly** - Compare feature accuracy between architectures
5. **Document all changes** - Maintain clear upgrade path

---

## Validation Datasets
- **TESS:** Toronto Emotional Speech Set (sad/happy as depression proxy)
- **DAIC-WOZ:** Pending access (clinical depression interviews)

---

## Known Issues / Technical Debt
1. No unit tests in core business logic
2. Baseline migration v2 undocumented
3. Feature extraction RTF varies (0.70-1.36)
4. Learning mode suppresses signals for first 14 days
5. Paper claims "9 indicators" but 3 are intentionally empty

---

## Contact / Ownership
- Repository: `/home/rodrigues/depression-detection`
- Paper: `/home/rodrigues/IEEE-WiP-PerCom-IHearYou`
- Date documented: January 21, 2026
