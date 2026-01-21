/**
 * @file yin_f0.c
 * @brief YIN pitch estimation implementation
 *
 * Simplified YIN algorithm for F0 estimation on MCU.
 *
 * Reference: de Cheveigné, A., & Kawahara, H. (2002).
 * YIN, a fundamental frequency estimator for speech and music.
 * The Journal of the Acoustical Society of America, 111(4), 1917-1930.
 *
 * Algorithm steps:
 * 1. Compute difference function d(tau)
 * 2. Compute cumulative mean normalized difference d'(tau)
 * 3. Apply absolute threshold
 * 4. Parabolic interpolation for sub-sample accuracy
 */

#include "yin_f0.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>

/* Maximum lag (for 50 Hz at 16 kHz = 320 samples) */
#define MAX_LAG 320

/* Internal context structure */
struct yin_ctx {
    yin_config_t config;
    int min_lag;        /* Minimum lag (from f0_max) */
    int max_lag;        /* Maximum lag (from f0_min) */
    float* diff;        /* Difference function buffer */
    float* cmndf;       /* Cumulative mean normalized difference */
};

yin_ctx_t* yin_init(const yin_config_t* config) {
    yin_ctx_t* ctx = (yin_ctx_t*)calloc(1, sizeof(yin_ctx_t));
    if (!ctx) return NULL;

    if (config) {
        ctx->config = *config;
    } else {
        ctx->config = (yin_config_t)YIN_CONFIG_DEFAULT;
    }

    /* Compute lag range */
    ctx->min_lag = (int)(ctx->config.sample_rate / ctx->config.f0_max_hz);
    ctx->max_lag = (int)(ctx->config.sample_rate / ctx->config.f0_min_hz);

    if (ctx->max_lag > MAX_LAG) {
        ctx->max_lag = MAX_LAG;
    }

    /* Allocate buffers */
    ctx->diff = (float*)calloc(ctx->max_lag + 1, sizeof(float));
    ctx->cmndf = (float*)calloc(ctx->max_lag + 1, sizeof(float));

    if (!ctx->diff || !ctx->cmndf) {
        yin_free(ctx);
        return NULL;
    }

    return ctx;
}

/**
 * @brief Compute difference function
 *
 * d(tau) = sum_{j=0}^{W-1} (x[j] - x[j+tau])^2
 */
static void compute_difference(
    const int16_t* frame,
    size_t frame_size,
    int max_lag,
    float* diff
) {
    /* Initialize */
    for (int tau = 0; tau <= max_lag; tau++) {
        diff[tau] = 0.0f;
    }

    /* Compute difference function */
    /* TODO: Optimize with running sum for O(n) complexity */
    int w = (int)frame_size / 2;  /* Integration window */

    for (int tau = 1; tau <= max_lag && tau < w; tau++) {
        float sum = 0.0f;
        for (int j = 0; j < w; j++) {
            float delta = (float)(frame[j] - frame[j + tau]);
            sum += delta * delta;
        }
        diff[tau] = sum;
    }
}

/**
 * @brief Compute cumulative mean normalized difference
 *
 * d'(tau) = d(tau) / ((1/tau) * sum_{j=1}^{tau} d(j))
 * d'(0) = 1
 */
static void compute_cmndf(
    const float* diff,
    int max_lag,
    float* cmndf
) {
    cmndf[0] = 1.0f;

    float running_sum = 0.0f;
    for (int tau = 1; tau <= max_lag; tau++) {
        running_sum += diff[tau];
        if (running_sum > 0.0f) {
            cmndf[tau] = diff[tau] * tau / running_sum;
        } else {
            cmndf[tau] = 1.0f;
        }
    }
}

/**
 * @brief Find best lag using absolute threshold
 *
 * Find the first tau where d'(tau) < threshold
 */
static int find_best_lag(
    const float* cmndf,
    int min_lag,
    int max_lag,
    float threshold
) {
    /* Find first tau below threshold */
    for (int tau = min_lag; tau <= max_lag; tau++) {
        if (cmndf[tau] < threshold) {
            /* Search for local minimum */
            while (tau + 1 <= max_lag && cmndf[tau + 1] < cmndf[tau]) {
                tau++;
            }
            return tau;
        }
    }

    /* No pitch found (unvoiced) */
    return 0;
}

/**
 * @brief Parabolic interpolation for sub-sample accuracy
 */
static float parabolic_interpolation(
    const float* cmndf,
    int tau,
    int max_lag
) {
    if (tau <= 0 || tau >= max_lag) {
        return (float)tau;
    }

    float a = cmndf[tau - 1];
    float b = cmndf[tau];
    float c = cmndf[tau + 1];

    float delta = 0.5f * (a - c) / (a - 2.0f * b + c + 1e-10f);

    return (float)tau + delta;
}

float yin_estimate_f0(
    yin_ctx_t* ctx,
    const int16_t* frame,
    size_t frame_size
) {
    if (!ctx || !frame) {
        return 0.0f;
    }

    /* Compute effective max_lag based on frame size */
    /* Need at least frame_size/2 for integration window */
    int effective_max_lag = (int)frame_size / 2 - 1;
    if (effective_max_lag > ctx->max_lag) {
        effective_max_lag = ctx->max_lag;
    }
    if (effective_max_lag < ctx->min_lag) {
        return 0.0f;  /* Frame too short for any valid pitch */
    }

    /* Step 1: Compute difference function */
    compute_difference(frame, frame_size, effective_max_lag, ctx->diff);

    /* Step 2: Compute cumulative mean normalized difference */
    compute_cmndf(ctx->diff, effective_max_lag, ctx->cmndf);

    /* Step 3: Find best lag with threshold */
    int best_lag = find_best_lag(
        ctx->cmndf,
        ctx->min_lag,
        effective_max_lag,
        ctx->config.threshold
    );

    if (best_lag == 0) {
        return 0.0f;  /* Unvoiced */
    }

    /* Step 4: Parabolic interpolation */
    float refined_lag = parabolic_interpolation(ctx->cmndf, best_lag, effective_max_lag);

    /* Convert lag to frequency */
    float f0 = ctx->config.sample_rate / refined_lag;

    /* Sanity check */
    if (f0 < ctx->config.f0_min_hz || f0 > ctx->config.f0_max_hz) {
        return 0.0f;
    }

    return f0;
}

size_t yin_memory_estimate(const yin_config_t* config) {
    int max_lag = MAX_LAG;
    if (config) {
        max_lag = (int)(config->sample_rate / config->f0_min_hz);
        if (max_lag > MAX_LAG) max_lag = MAX_LAG;
    }

    return sizeof(yin_ctx_t) + 2 * (max_lag + 1) * sizeof(float);
}

void yin_free(yin_ctx_t* ctx) {
    if (ctx) {
        free(ctx->diff);
        free(ctx->cmndf);
        free(ctx);
    }
}
