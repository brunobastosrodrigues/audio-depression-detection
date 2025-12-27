# Bugs in Live Mode

The following bugs and issues were identified during the "live mode" execution analysis of `respeaker_service.py`.

## 1. Missing Voice Activity Detection (VAD)
**Description:** The architecture documentation claims that "Data Ingestion (VAD filtering)" occurs before MQTT publishing. However, `respeaker_service.py` (the live ingestion service) does not implement any VAD logic. It streams continuous audio chunks every 5 seconds regardless of content.
**Impact:**
- Significant increase in network bandwidth usage.
- Downstream services receive silence or noise, potentially affecting analysis accuracy or resource consumption.
**Location:** `data_ingestion_layer/respeaker_service.py`

## 2. Missing Dependencies
**Description:** The `data_ingestion_layer/requirements.txt` file is missing several critical packages required for `respeaker_service.py` to run.
**Details:**
- `pymongo`: Required for database connection.
- `mongomock`: Required for mock mode (and imported in the file).
- `soundfile`: Listed twice in `requirements.txt`.
**Location:** `data_ingestion_layer/requirements.txt`

## 3. Deprecated API Usage
**Description:** `respeaker_service.py` uses `datetime.utcnow()`, which is deprecated in recent Python versions.
**Details:** Warning observed in logs: `DeprecationWarning: datetime.datetime.utcnow() is deprecated`.
**Location:** `data_ingestion_layer/respeaker_service.py` lines 164, 198.

## 4. Inefficient Metric Calculation
**Description:** The service calculates RMS twice and performs redundant type conversions.
**Details:**
- Audio is converted to `float32` to calculate RMS for noise floor tracking.
- Audio is then passed to `calculate_audio_metrics` (in `framework/audio_utils.py`), which converts it to `float32` again to calculate RMS and other metrics.
**Location:** `data_ingestion_layer/respeaker_service.py` (lines ~370-385) and `framework/audio_utils.py`.

## 5. Hardcoded Sample Rate
**Description:** `respeaker_service.py` hardcodes `SAMPLE_RATE = 16000`.
**Details:** If a physical board is configured to stream at a different sample rate, the service will misinterpret the data (wrong duration, pitch shift) as there is no sample rate negotiation in the handshake.
**Location:** `data_ingestion_layer/respeaker_service.py`

## 6. PyAudio Installation Complexity
**Description:** `pyaudio` is listed in `requirements.txt` but fails to install without system-level dependencies (`portaudio19-dev`), which are not documented in the quick start or `requirements.txt` (though likely in Dockerfile). This makes local development/testing difficult.

## 7. Noise Floor Initialization Issue
**Description:** When a board connects, the noise floor is initialized based on the first chunk. If the first chunk is silent, the noise floor is low (correct). If the first chunk is loud (speech), the noise floor is set to that high RMS value, resulting in 0dB SNR for that chunk.
**Recommendation:** Implement a calibration phase or persist noise floor data.
