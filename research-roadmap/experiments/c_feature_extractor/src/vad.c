/**
 * @file vad.c
 * @brief Energy-based Voice Activity Detection implementation
 *
 * TODO: Implement for Gemini
 */

#include "vad.h"
#include <stdlib.h>
#include <math.h>

/* Internal context structure */
struct vad_ctx {
    vad_config_t config;
    int hangover_counter;
    bool prev_voiced;
};

vad_ctx_t* vad_init(const vad_config_t* config) {
    vad_ctx_t* ctx = (vad_ctx_t*)calloc(1, sizeof(vad_ctx_t));
    if (!ctx) return NULL;

    if (config) {
        ctx->config = *config;
    } else {
        ctx->config = (vad_config_t)VAD_CONFIG_DEFAULT;
    }

    ctx->hangover_counter = 0;
    ctx->prev_voiced = false;

    return ctx;
}

float vad_compute_rms(const int16_t* frame, size_t frame_size) {
    if (!frame || frame_size == 0) return 0.0f;

    /* Compute sum of squares */
    int64_t sum_sq = 0;
    for (size_t i = 0; i < frame_size; i++) {
        int32_t sample = frame[i];
        sum_sq += sample * sample;
    }

    /* RMS normalized to 0.0-1.0 range (INT16 max = 32767) */
    float rms = sqrtf((float)sum_sq / frame_size) / 32768.0f;
    return rms;
}

float vad_rms_to_db(float rms) {
    if (rms < 1e-10f) return -100.0f;
    return 20.0f * log10f(rms);
}

int vad_process_frame(
    vad_ctx_t* ctx,
    const int16_t* frame,
    size_t frame_size,
    vad_result_t* result
) {
    if (!ctx || !frame || !result) return -1;

    /* Compute RMS energy */
    result->rms = vad_compute_rms(frame, frame_size);
    result->rms_db = vad_rms_to_db(result->rms);

    /* Simple threshold-based decision with hangover */
    bool energy_voiced = (result->rms_db > ctx->config.threshold_db);

    if (energy_voiced) {
        ctx->hangover_counter = ctx->config.hangover_frames;
        result->is_voiced = true;
    } else if (ctx->hangover_counter > 0) {
        ctx->hangover_counter--;
        result->is_voiced = true;  /* Hangover period */
    } else {
        result->is_voiced = false;
    }

    ctx->prev_voiced = result->is_voiced;
    return 0;
}

void vad_reset(vad_ctx_t* ctx) {
    if (ctx) {
        ctx->hangover_counter = 0;
        ctx->prev_voiced = false;
    }
}

void vad_free(vad_ctx_t* ctx) {
    free(ctx);
}

size_t vad_memory_estimate(void) {
    return sizeof(struct vad_ctx);
}
