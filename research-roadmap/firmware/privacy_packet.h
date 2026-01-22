#ifndef PRIVACY_PACKET_H
#define PRIVACY_PACKET_H

#include <stdint.h>

// Placeholder for the actual feature data.
// This will be replaced with a concrete definition based on the feature
// extraction library's output. For example, it could contain MFCCs,
// spectral centroid, zero-crossing rate, etc.
typedef struct {
    float mfcc[13];
    float spectral_centroid;
    float zero_crossing_rate;
    // ... other features
} features_t;

/**
 * @brief A data packet designed for privacy-preserving transmission.
 *
 * This structure contains extracted audio features and metadata, but no
 * raw audio. It is designed to be sent from an edge device (e.g., ESP32)
 * to a central hub for further analysis.
 */
typedef struct {
    /**
     * @brief Extracted paralinguistic features from the audio buffer.
     */
    features_t features;

    /**
     * @brief Unix timestamp (UTC) indicating the start of audio capture.
     */
    uint32_t timestamp;

    /**
     * @brief Unique identifier for the capturing device (e.g., MAC address).
     *        A 16-byte array to accommodate various formats like UUIDs.
     */
    uint8_t device_id[16];

    /**
     * @brief SHA-256 hash of the raw audio buffer. Used for data integrity
     *        and deduplication. It proves the data's origin without
     *        exposing the raw audio.
     */
    uint8_t audio_hash[32];

    /**
     * @brief A unique identifier for the current session (e.g., since the
     *        device last booted). Useful for grouping related packets.
     */
    uint8_t session_id[16];

} privacy_packet_t;

#endif // PRIVACY_PACKET_H
