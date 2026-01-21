/**
 * @file yin_f0.h
 * @brief YIN pitch estimation algorithm
 *
 * Simplified implementation of the YIN algorithm for F0 estimation.
 * Reference: de Cheveigné & Kawahara (2002)
 *
 * Optimizations for MCU:
 * - Uses INT16 input directly
 * - Fixed-size buffers
 * - No dynamic allocation in hot path
 */

#ifndef YIN_F0_H
#define YIN_F0_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief YIN configuration
 */
typedef struct {
    int sample_rate;    /**< Sample rate in Hz */
    float f0_min_hz;    /**< Minimum F0 (determines max lag) */
    float f0_max_hz;    /**< Maximum F0 (determines min lag) */
    float threshold;    /**< YIN threshold (default: 0.1) */
} yin_config_t;

/**
 * @brief Default YIN configuration
 */
#define YIN_CONFIG_DEFAULT { \
    .sample_rate = 16000,    \
    .f0_min_hz = 50.0f,      \
    .f0_max_hz = 500.0f,     \
    .threshold = 0.1f        \
}

/**
 * @brief YIN context
 */
typedef struct yin_ctx yin_ctx_t;

/**
 * @brief Initialize YIN pitch estimator
 *
 * @param config Configuration (NULL for defaults)
 * @return Context, or NULL on failure
 */
yin_ctx_t* yin_init(const yin_config_t* config);

/**
 * @brief Estimate F0 for a single frame
 *
 * @param ctx YIN context
 * @param frame Audio frame (INT16 samples)
 * @param frame_size Number of samples in frame
 * @return F0 in Hz, or 0 if unvoiced
 */
float yin_estimate_f0(
    yin_ctx_t* ctx,
    const int16_t* frame,
    size_t frame_size
);

/**
 * @brief Free YIN resources
 *
 * @param ctx YIN context
 */
void yin_free(yin_ctx_t* ctx);

/**
 * @brief Get memory usage estimate
 *
 * @param config Configuration
 * @return Estimated memory usage in bytes
 */
size_t yin_memory_estimate(const yin_config_t* config);

#ifdef __cplusplus
}
#endif

#endif /* YIN_F0_H */
