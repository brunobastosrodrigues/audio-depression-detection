![Depression Detection](https://img.shields.io/badge/%F0%9F%A7%A0-Depression_Detection-blue)
![Signal Processing](https://img.shields.io/badge/%F0%9F%93%88-Signal_Processing-blue)
![Audio Processing](https://img.shields.io/badge/%F0%9F%94%8A-Audio_Processing-blue)

![Python](https://img.shields.io/badge/-Python-green?logo=python&logoColor=white)

![Streamlit](https://img.shields.io/badge/-Streamlit-orange?logo=streamlit&logoColor=white)
![OpenSMILE](https://img.shields.io/badge/-OpenSMILE-orange)
![Librosa](https://img.shields.io/badge/-Librosa-orange)
![Praat-Parselmouth](https://img.shields.io/badge/-Praat--Parselmouth-orange)
![Resemblyzer](https://img.shields.io/badge/-Resemblyzer-orange)
![Silero VAD](https://img.shields.io/badge/-Silero_VAD-orange)

# IHearYou: Audio-Centered Depression Detection

A privacy-preserving, transparent AI system that detects Major Depressive Disorder (MDD) biomarkers in real-time by mapping acoustic features directly to DSM-5 clinical indicators. The prototype was initially developed by Jonas Länzlinger as part of his master thesis at the University of St. Gallen.

## Key Features

 - Privacy-First Architecture: Audio is processed at the edge; only extracted metrics leave the sensor node. No raw speech is stored.
 - "White-Box" Diagnostics: Unlike black-box classifiers, this system maps specific acoustic features (e.g., Jitter, $F_0$) to interpretable DSM-5 symptoms (e.g., Psychomotor Retardation).
 - Real-Time Monitoring: Live dashboard for tracking symptom progression and vocal biomarkers over time.
 - Hardware Agnostic: Supports file injection (.wav) for research and IoT hardware (ReSpeaker Lite with XIAO ESP32S3) for live deployment.
 - Context-Aware Analysis: Uses Temporal Context Modeling (EMA smoothing, daily aggregation) to distinguish fleeting moods from depressive episodes.

## Data Pipeline Overview

The high-level data pipeline is illustrated below. Each step in the pipeline reflects a corresponding stage in the analysis of user data.

![High-level Data Pipeline.](docs/assets/highlevel_data_pipeline.png)

### Data Flow

```
Audio Input → Data Ingestion (VAD filtering) → MQTT
  → Voice Metrics (20+ acoustic features) → raw_metrics (MongoDB)
  → Temporal Context Modeling (daily aggregation + EMA smoothing) → contextual_metrics
  → Analysis Layer (DSM-5 mapping) → indicator_scores
  → Dashboard (visualization) + PHQ-9 Calibration
```

### MQTT Topic Structure

```
voice/{user_id}/{board_id}/{environment_name}
```

### DSM-5 Depression Indicators

The system maps acoustic features to 9 DSM-5 Major Depressive Disorder indicators:

1. Depressed mood
2. Loss of interest
3. Significant weight changes
4. Insomnia/hypersomnia
5. Psychomotor retardation/agitation
6. Fatigue/loss of energy
7. Feelings of worthlessness/guilt
8. Diminished ability to think/concentrate
9. Recurrent thoughts of death

Features are normalized using z-scores against population/user baselines, then mapped to indicators using configurable weights and correlation directions defined in [`config.json`](./analysis_layer/core/mapping/config.json).

### MongoDB Collections

| Collection | Purpose |
|------------|---------|
| `raw_metrics` | Raw audio features per utterance |
| `aggregated_metrics` | Daily aggregated metrics |
| `contextual_metrics` | EMA-smoothed metrics with context windows (morning/evening/general) |
| `indicator_scores` | Computed depression indicator scores |
| `baseline` | User-specific baseline statistics |
| `user_config` | Per-user configuration overrides |
| `phq9_submissions` | PHQ-9 questionnaire responses for calibration |
| `users` | Voice enrollment data (D-vectors for speaker verification) |
| `boards`, `environments` | Multi-board IoT configuration |

## Services Overview

This is an overview of all services defined in the system and how to access them.

| Service Name                      | Container Name                    | Port  | URL / Notes                                    |
| --------------------------------- | --------------------------------- | ----- | ---------------------------------------------- |
| MQTT Broker                       | `mqtt`                            | 1883  | MQTT protocol only                             |
| MongoDB                           | `mongodb`                         | 27017 | MongoDB database                               |
| Mongo Express                     | `mongo-express`                   | 8081  | [http://localhost:8081](http://localhost:8081) |
| Voice Profiling Service           | `voice_profiling`                 | 8000  | [http://localhost:8000](http://localhost:8000) |
| Voice Metrics Service             | `voice_metrics`                   | –     | Internal only (MQTT consumer)                  |
| ReSpeaker Service                 | `respeaker_service`               | 8010  | TCP server for ESP32 board connections         |
| Temporal Context Modeling Service | `temporal_context_modeling_layer` | 8082  | [http://localhost:8082](http://localhost:8082) |
| Analysis Layer                    | `analysis_layer`                  | 8083  | [http://localhost:8083](http://localhost:8083) |
| Dashboard Layer                   | `dashboard_layer`                 | 8084  | [http://localhost:8084](http://localhost:8084) |

## Quick Start

This quick tutorial introduces the core system functionality using the **`VoiceFromFile`** sensor type. This type let's you simulated audio input by streaming data from a `.wav` file.

---

#### 1. Build and start the system:

```bash
docker-compose up --build
```

#### 2. Stream audio from file

-  Navigate to file [**`./data_ingestion_layer/sense.py`**](./data_ingestion_layer/sense.py)

-  Define the filepath to the desired **`.wav`** file.

-  Run [**`./data_ingestion_layer/sense.py`**](./data_ingestion_layer/sense.py)

   ```bash
   python -u "./data_ingestion_layer/sense.py"
   ```

*  Wait until the whole file is processed, and the message "No data detected" is shown in the terminal.

#### 3. Analyze data

-  Open the **Streamlit dashboard** at [`http://localhost:8084`](http://localhost:8084).

-  Select the first user on the left side via the dropdown list.

-  Click "Refresh Analysis" button to trigger the data analysis.

## Running Tests

Tests use Python's unittest framework:

```bash
# Analysis layer tests
cd analysis_layer && python -m unittest tests.test_config_manager
cd analysis_layer && python -m unittest tests.test_calibration_service

# Dashboard layer tests
cd dashboard_layer && python -m unittest tests.test_sankey_adapter

# Board analytics tests (comprehensive)
cd dashboard_layer && python tests/run_board_tests.py

# Run specific board analytics scenario
cd dashboard_layer && python tests/run_board_tests.py --scenario multi_board_comparison

# See all available scenarios
cd dashboard_layer && python tests/run_board_tests.py --list-scenarios
```

### Board Analytics Test Suite

The dashboard layer includes a comprehensive test suite for board analytics with synthetic data generation:

- **Synthetic Data Generator**: Creates realistic test data for multiple boards with various activity patterns
- **Automated Test Runner**: Executes tests with setup, validation, and cleanup
- **Integration Examples**: Demonstrates usage and testing workflows
- **Test Coverage**: CRUD operations, analytics calculations, data deletion, and edge cases

See [dashboard_layer/tests/README.md](./dashboard_layer/tests/README.md) for detailed documentation.

## Technology Stack

**Audio Processing:**
- Librosa - General feature extraction
- OpenSMILE - Acoustic features
- Praat-Parselmouth - Prosodic analysis
- Resemblyzer - Speaker embeddings (D-vectors)
- Silero VAD - Voice activity detection
- PyTorch/TorchAudio 2.5.1

**Backend:**
- Python 3.9-3.11
- FastAPI (REST APIs)
- Streamlit (Dashboard)
- MongoDB (Persistence)
- MQTT/Mosquitto (Message broker)
