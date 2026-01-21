/**
 * @file vad.h
 * @brief Energy-based Voice Activity Detection
 *
 * Simple VAD using RMS energy threshold.
 * Designed for low-latency, low-memory operation on MCU.
 */

#ifndef VAD_H
#define VAD_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief VAD configuration
 */
typedef struct {
    float threshold_db;     /**< Energy threshold in dB (default: -40) */
    int hangover_frames;    /**< Frames to hold voiced state (default: 3) */
} vad_config_t;

/**
 * @brief Default VAD configuration
 */
#define VAD_CONFIG_DEFAULT { \
    .threshold_db = -40.0f,  \
    .hangover_frames = 0     \
}

/**
 * @brief VAD result for a frame
 */
typedef struct {
    bool is_voiced;     /**< True if frame is voiced */
    float rms;          /**< RMS energy (linear) */
    float rms_db;       /**< RMS energy in dB */
} vad_result_t;

/**
 * @brief VAD context
 */
typedef struct vad_ctx vad_ctx_t;

/**
 * @brief Initialize VAD
 *
 * @param config Configuration (NULL for defaults)
 * @return Context, or NULL on failure
 */
vad_ctx_t* vad_init(const vad_config_t* config);

/**
 * @brief Process a frame and determine voiced/unvoiced
 *
 * @param ctx VAD context
 * @param frame Audio frame (INT16 samples)
 * @param frame_size Number of samples
 * @param result Output result
 * @return 0 on success, negative on error
 */
int vad_process_frame(
    vad_ctx_t* ctx,
    const int16_t* frame,
    size_t frame_size,
    vad_result_t* result
);

/**
 * @brief Compute RMS energy of a frame
 *
 * Utility function, does not use VAD state.
 *
 * @param frame Audio frame (INT16 samples)
 * @param frame_size Number of samples
 * @return RMS energy (linear, 0.0 to 1.0 normalized)
 */
float vad_compute_rms(const int16_t* frame, size_t frame_size);

/**
 * @brief Convert linear RMS to dB
 *
 * @param rms Linear RMS value
 * @return RMS in dB
 */
float vad_rms_to_db(float rms);

/**
 * @brief Reset VAD state
 *
 * @param ctx VAD context
 */
void vad_reset(vad_ctx_t* ctx);

/**
 * @brief Free VAD resources
 *
 * @param ctx VAD context
 */
void vad_free(vad_ctx_t* ctx);

/**
 * @brief Get memory usage estimate
 *
 * @return Estimated memory usage in bytes
 */
size_t vad_memory_estimate(void);

#ifdef __cplusplus
}
#endif

#endif /* VAD_H */
