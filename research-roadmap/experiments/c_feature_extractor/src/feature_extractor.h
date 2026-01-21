/**
 * @file feature_extractor.h
 * @brief Acoustic feature extraction for depression detection on ESP32
 *
 * This module extracts clinically-validated acoustic features from audio
 * under MCU constraints (fixed-point math, limited memory, INT16 samples).
 *
 * Features extracted:
 * - F0 mean (Hz) - using simplified YIN algorithm
 * - F0 std (Hz) - pitch variability
 * - F0 range (Hz) - pitch range (max - min)
 * - Pause ratio - proportion of unvoiced frames
 * - Voiced ratio - proportion of voiced frames
 * - Energy std - energy dynamics (RMS-based)
 *
 * Target: ESP32-S3 with 512KB SRAM + 8MB PSRAM
 * Memory budget: 50KB for feature extraction
 */

#ifndef FEATURE_EXTRACTOR_H
#define FEATURE_EXTRACTOR_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Extracted acoustic features
 */
typedef struct {
    /* F0 (pitch) features */
    float f0_mean;      /**< Mean F0 in Hz (voiced frames only) */
    float f0_std;       /**< Standard deviation of F0 in Hz */
    float f0_range;     /**< F0 range (max - min) in Hz */

    /* Temporal features */
    float pause_ratio;  /**< Ratio of unvoiced frames (0.0 - 1.0) */
    float voiced_ratio; /**< Ratio of voiced frames (0.0 - 1.0) */

    /* Energy features */
    float energy_std;   /**< Standard deviation of RMS energy */
    float energy_mean;  /**< Mean RMS energy (normalized) */

    /* Voice quality features (Phase 2) */
    float jitter;       /**< Local jitter (F0 perturbation ratio) */
    float jitter_rap;   /**< Relative Average Perturbation */
    float shimmer;      /**< Local shimmer (amplitude perturbation ratio) */
    float shimmer_apq3; /**< 3-point Amplitude Perturbation Quotient */
    float hnr_mean;     /**< Mean Harmonics-to-Noise Ratio (dB) */
    float snr;          /**< Signal-to-Noise Ratio (dB) */

    /* Metadata */
    int32_t frame_count;    /**< Total number of frames processed */
    int32_t voiced_frames;  /**< Number of voiced frames */
    float duration_sec;     /**< Audio duration in seconds */
} features_t;

/**
 * @brief Configuration for feature extraction
 */
typedef struct {
    int sample_rate;        /**< Sample rate in Hz (default: 16000) */
    int frame_size;         /**< Frame size in samples (default: 512 = 32ms @ 16kHz) */
    int hop_size;           /**< Hop size in samples (default: 160 = 10ms @ 16kHz) */
    float f0_min_hz;        /**< Minimum F0 in Hz (default: 50) */
    float f0_max_hz;        /**< Maximum F0 in Hz (default: 500) */
    float vad_threshold_db; /**< VAD threshold in dB (default: -40) */
} extractor_config_t;

/**
 * @brief Default configuration
 */
#define EXTRACTOR_CONFIG_DEFAULT { \
    .sample_rate = 16000,          \
    .frame_size = 512,             \
    .hop_size = 160,               \
    .f0_min_hz = 50.0f,            \
    .f0_max_hz = 500.0f,           \
    .vad_threshold_db = -35.0f     \
}

/**
 * @brief Extractor context (opaque)
 */
typedef struct extractor_ctx extractor_ctx_t;

/**
 * @brief Initialize feature extractor
 *
 * Allocates internal buffers and initializes state.
 *
 * @param config Configuration (NULL for defaults)
 * @return Extractor context, or NULL on failure
 */
extractor_ctx_t* extractor_init(const extractor_config_t* config);

/**
 * @brief Extract features from audio buffer
 *
 * Processes INT16 PCM audio and extracts all features.
 * Audio should be mono, 16kHz (or as configured).
 *
 * @param ctx Extractor context
 * @param audio Audio samples (INT16 PCM)
 * @param num_samples Number of samples
 * @param out Output features
 * @return 0 on success, negative on error
 */
int extractor_process(
    extractor_ctx_t* ctx,
    const int16_t* audio,
    size_t num_samples,
    features_t* out
);

/**
 * @brief Reset extractor state
 *
 * Call between processing different audio files.
 *
 * @param ctx Extractor context
 */
void extractor_reset(extractor_ctx_t* ctx);

/**
 * @brief Free extractor resources
 *
 * @param ctx Extractor context
 */
void extractor_free(extractor_ctx_t* ctx);

/**
 * @brief Get memory usage estimate
 *
 * @param config Configuration
 * @return Estimated memory usage in bytes
 */
size_t extractor_memory_estimate(const extractor_config_t* config);

#ifdef __cplusplus
}
#endif

#endif /* FEATURE_EXTRACTOR_H */
