# Firmware Task: Privacy-Preserving Feature Extraction Pipeline

**Context:** To comply with IRB requirements, no raw audio can be stored or transmitted from the edge device. All feature extraction must occur on-device.

## 1. Core Requirements

1.  **On-Device Feature Extraction:** All paralinguistic features must be computed on the ESP32-S3 before any data transmission.
2.  **No Raw Audio Transmission:** The firmware must not send any raw or recoverable audio data.
3.  **Strict Buffer Limits:** Audio buffers must not exceed 10 seconds of continuous audio.
4.  **Secure Memory Wipe:** After feature extraction, the audio buffer in RAM must be securely wiped (e.g., zeroed out).
5.  **Data Integrity:** A SHA-256 hash of the raw audio buffer must be computed and included in the data packet to verify integrity and for potential deduplication by the receiver.

## 2. Data Structure Definition

A new data packet, `privacy_packet_t`, will be used for all data transmission.

```c
// See privacy_packet.h for the formal definition

typedef struct {
    // Placeholder for the actual feature data structure
    // This will be defined based on the output of the feature
    // extraction library (e.g., OpenSMILE, custom DSP).
    features_t features;

    // Unix timestamp (UTC) of when the audio capture started.
    uint32_t timestamp;

    // Unique identifier of the capturing device (e.g., MAC address).
    uint8_t device_id[16];

    // SHA-256 hash of the raw audio buffer from which features were extracted.
    uint8_t audio_hash[32];

    // A unique ID for the current session or device boot cycle.
    uint8_t session_id[16];

} privacy_packet_t;
```

## 3. Implementation Steps

### Task 3.1: Audio Buffering

-   Implement a circular buffer or a double-buffering scheme to capture audio from the microphone (e.g., via I2S).
-   The buffer size must be calculated to hold a maximum of 10 seconds of audio at the required sample rate and bit depth (e.g., 16kHz, 16-bit mono).
-   Trigger the feature extraction process when the buffer is full or a VAD (Voice Activity Detection) endpoint is detected.

### Task 3.2: Feature Extraction

-   Integrate the selected feature extraction library (e.g., a lightweight version of OpenSMILE, or custom spectral/cepstral feature extractors).
-   Pass the filled audio buffer to the feature extraction function.
-   Store the extracted features in the `features_t` struct.

### Task 3.3: SHA-256 Hashing

-   Before wiping the buffer, compute the SHA-256 hash of the entire raw audio buffer.
-   Use a standard library implementation of SHA-256 suitable for embedded devices (e.g., from mbedTLS or the ESP-IDF).
-   Store the resulting 32-byte hash in the `audio_hash` field of the `privacy_packet_t`.

### Task 3.4: Secure Memory Wipe

-   Immediately after the feature extraction and hashing are complete, securely clear the audio buffer from memory.
-   A `memset(buffer, 0, buffer_size)` is the minimum requirement. For stricter security, consider more advanced memory wiping techniques if available.

### Task 3.5: Packet Assembly and Transmission

-   Assemble the `privacy_packet_t` with the extracted features, timestamp, device ID, audio hash, and session ID.
-   Serialize the packet for transmission (e.g., using Protocol Buffers, or a simple binary format).
-   Transmit the serialized packet over the network (e.g., via MQTT over Wi-Fi).

## 4. Verification Plan

-   **Unit Test:** Write a test function that:
    1.  Fills a buffer with known audio data.
    2.  Calls the feature extraction and hashing functions.
    3.  Asserts that the feature output is as expected.
    4.  Asserts that the SHA-256 hash matches a pre-computed value.
    5.  Asserts that the audio buffer is zeroed out after the wipe.
-   **Integration Test:** Run the full pipeline on the device and monitor the MQTT broker to inspect the transmitted `privacy_packet_t` for correctness and completeness. Verify that no raw audio is present in the payload.
