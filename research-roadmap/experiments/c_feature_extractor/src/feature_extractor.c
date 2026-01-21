/**
 * @file feature_extractor.c
 * @brief Main feature extraction implementation
 *
 * Combines VAD, YIN, and voice quality metrics to extract
 * depression-relevant acoustic features.
 */

#include "feature_extractor.h"
#include "yin_f0.h"
#include "vad.h"
#include "voice_quality.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>

/* Maximum frames we track for statistics */
#define MAX_FRAMES 10000

/* Internal context structure */
struct extractor_ctx {
    extractor_config_t config;
    yin_ctx_t* yin;
    vad_ctx_t* vad;

    /* Running statistics for F0 */
    float* f0_values;       /* Buffer of F0 values for voiced frames */
    int f0_count;           /* Number of F0 values collected */
    int f0_capacity;        /* Capacity of f0_values buffer */

    /* Running statistics for amplitude (for shimmer) */
    float* amplitude_values; /* Buffer of amplitude values for voiced frames */
    int amplitude_count;     /* Number of amplitude values collected */

    /* Running statistics for HNR */
    float hnr_sum;           /* Sum of HNR values */
    int hnr_count;           /* Number of HNR measurements */

    /* Running statistics for energy */
    float energy_sum;
    float energy_sum_sq;
    int energy_count;

    /* Energy for SNR calculation */
    float voiced_energy_sum;
    int voiced_energy_count;
    float unvoiced_energy_sum;
    int unvoiced_energy_count;

    /* Frame counts */
    int total_frames;
    int voiced_frames;
};

extractor_ctx_t* extractor_init(const extractor_config_t* config) {
    extractor_ctx_t* ctx = (extractor_ctx_t*)calloc(1, sizeof(extractor_ctx_t));
    if (!ctx) return NULL;

    /* Apply configuration */
    if (config) {
        ctx->config = *config;
    } else {
        ctx->config = (extractor_config_t)EXTRACTOR_CONFIG_DEFAULT;
    }

    /* Initialize YIN */
    yin_config_t yin_config = {
        .sample_rate = ctx->config.sample_rate,
        .f0_min_hz = ctx->config.f0_min_hz,
        .f0_max_hz = ctx->config.f0_max_hz,
        .threshold = 0.1f
    };
    ctx->yin = yin_init(&yin_config);
    if (!ctx->yin) {
        extractor_free(ctx);
        return NULL;
    }

    /* Initialize VAD */
    vad_config_t vad_config = {
        .threshold_db = ctx->config.vad_threshold_db,
        .hangover_frames = 1
    };
    ctx->vad = vad_init(&vad_config);
    if (!ctx->vad) {
        extractor_free(ctx);
        return NULL;
    }

    /* Allocate F0 buffer */
    ctx->f0_capacity = MAX_FRAMES;
    ctx->f0_values = (float*)calloc(ctx->f0_capacity, sizeof(float));
    if (!ctx->f0_values) {
        extractor_free(ctx);
        return NULL;
    }

    /* Allocate amplitude buffer (for shimmer) */
    ctx->amplitude_values = (float*)calloc(ctx->f0_capacity, sizeof(float));
    if (!ctx->amplitude_values) {
        extractor_free(ctx);
        return NULL;
    }

    extractor_reset(ctx);

    return ctx;
}

void extractor_reset(extractor_ctx_t* ctx) {
    if (!ctx) return;

    ctx->f0_count = 0;
    ctx->amplitude_count = 0;
    ctx->hnr_sum = 0.0f;
    ctx->hnr_count = 0;
    ctx->energy_sum = 0.0f;
    ctx->energy_sum_sq = 0.0f;
    ctx->energy_count = 0;
    ctx->voiced_energy_sum = 0.0f;
    ctx->voiced_energy_count = 0;
    ctx->unvoiced_energy_sum = 0.0f;
    ctx->unvoiced_energy_count = 0;
    ctx->total_frames = 0;
    ctx->voiced_frames = 0;

    if (ctx->vad) vad_reset(ctx->vad);
}

int extractor_process(
    extractor_ctx_t* ctx,
    const int16_t* audio,
    size_t num_samples,
    features_t* out
) {
    if (!ctx || !audio || !out) return -1;

    /* Reset for new audio */
    extractor_reset(ctx);

    int frame_size = ctx->config.frame_size;
    int hop_size = ctx->config.hop_size;

    /* Process frame by frame */
    for (size_t offset = 0; offset + frame_size <= num_samples; offset += hop_size) {
        const int16_t* frame = audio + offset;

        /* VAD */
        vad_result_t vad_result;
        vad_process_frame(ctx->vad, frame, frame_size, &vad_result);

        /* Track energy statistics */
        ctx->energy_sum += vad_result.rms;
        ctx->energy_sum_sq += vad_result.rms * vad_result.rms;
        ctx->energy_count++;

        /* F0 estimation (only on potentially voiced frames) */
        if (vad_result.is_voiced) {
            float f0 = yin_estimate_f0(ctx->yin, frame, frame_size);

            if (f0 > 0) {
                /* Valid F0 - store for jitter calculation */
                if (ctx->f0_count < ctx->f0_capacity) {
                    ctx->f0_values[ctx->f0_count] = f0;

                    /* Extract amplitude for shimmer calculation */
                    float amplitude = extract_frame_amplitude(
                        frame, frame_size, f0, ctx->config.sample_rate
                    );
                    ctx->amplitude_values[ctx->amplitude_count++] = amplitude;

                    /* Compute HNR for this frame */
                    float hnr = compute_hnr_frame(
                        frame, frame_size, f0, ctx->config.sample_rate
                    );
                    if (hnr > 0) {
                        ctx->hnr_sum += hnr;
                        ctx->hnr_count++;
                    }

                    ctx->f0_count++;
                }

                /* Track voiced energy for SNR */
                ctx->voiced_energy_sum += vad_result.rms;
                ctx->voiced_energy_count++;

                ctx->voiced_frames++;
            }
        } else {
            /* Track unvoiced energy for SNR (noise floor) */
            ctx->unvoiced_energy_sum += vad_result.rms;
            ctx->unvoiced_energy_count++;
        }

        ctx->total_frames++;
    }

    /* Compute output features */
    memset(out, 0, sizeof(features_t));

    out->frame_count = ctx->total_frames;
    out->voiced_frames = ctx->voiced_frames;
    out->duration_sec = (float)num_samples / ctx->config.sample_rate;

    /* Voiced/pause ratios */
    if (ctx->total_frames > 0) {
        out->voiced_ratio = (float)ctx->voiced_frames / ctx->total_frames;
        out->pause_ratio = 1.0f - out->voiced_ratio;
    }

    /* Energy statistics */
    if (ctx->energy_count > 0) {
        out->energy_mean = ctx->energy_sum / ctx->energy_count;
        float variance = (ctx->energy_sum_sq / ctx->energy_count) -
                         (out->energy_mean * out->energy_mean);
        out->energy_std = (variance > 0) ? sqrtf(variance) : 0.0f;
    }

    /* F0 statistics (voiced frames only) */
    if (ctx->f0_count > 0) {
        /* Mean */
        float sum = 0.0f;
        float min_f0 = ctx->f0_values[0];
        float max_f0 = ctx->f0_values[0];

        for (int i = 0; i < ctx->f0_count; i++) {
            sum += ctx->f0_values[i];
            if (ctx->f0_values[i] < min_f0) min_f0 = ctx->f0_values[i];
            if (ctx->f0_values[i] > max_f0) max_f0 = ctx->f0_values[i];
        }

        out->f0_mean = sum / ctx->f0_count;
        out->f0_range = max_f0 - min_f0;

        /* Standard deviation */
        float sum_sq_diff = 0.0f;
        for (int i = 0; i < ctx->f0_count; i++) {
            float diff = ctx->f0_values[i] - out->f0_mean;
            sum_sq_diff += diff * diff;
        }
        out->f0_std = sqrtf(sum_sq_diff / ctx->f0_count);

        /* Voice quality metrics (jitter, shimmer) */
        out->jitter = compute_jitter_local(ctx->f0_values, ctx->f0_count);
        out->jitter_rap = compute_jitter_rap(ctx->f0_values, ctx->f0_count);

        if (ctx->amplitude_count > 0) {
            out->shimmer = compute_shimmer_local(
                ctx->amplitude_values, ctx->amplitude_count
            );
            out->shimmer_apq3 = compute_shimmer_apq3(
                ctx->amplitude_values, ctx->amplitude_count
            );
        }
    }

    /* HNR mean */
    if (ctx->hnr_count > 0) {
        out->hnr_mean = ctx->hnr_sum / ctx->hnr_count;
    }

    /* SNR calculation */
    if (ctx->voiced_energy_count > 0 && ctx->unvoiced_energy_count > 0) {
        float voiced_rms = ctx->voiced_energy_sum / ctx->voiced_energy_count;
        float unvoiced_rms = ctx->unvoiced_energy_sum / ctx->unvoiced_energy_count;
        out->snr = compute_snr(voiced_rms, unvoiced_rms);
    } else if (ctx->voiced_energy_count > 0) {
        /* No unvoiced frames - high SNR */
        out->snr = 40.0f;
    }

    return 0;
}

size_t extractor_memory_estimate(const extractor_config_t* config) {
    size_t total = sizeof(extractor_ctx_t);

    /* YIN memory */
    yin_config_t yin_config = YIN_CONFIG_DEFAULT;
    if (config) {
        yin_config.sample_rate = config->sample_rate;
        yin_config.f0_min_hz = config->f0_min_hz;
        yin_config.f0_max_hz = config->f0_max_hz;
    }
    total += yin_memory_estimate(&yin_config);

    /* VAD memory */
    total += vad_memory_estimate();

    /* F0 buffer */
    total += MAX_FRAMES * sizeof(float);

    /* Amplitude buffer (for shimmer) */
    total += MAX_FRAMES * sizeof(float);

    return total;
}

void extractor_free(extractor_ctx_t* ctx) {
    if (!ctx) return;

    if (ctx->yin) yin_free(ctx->yin);
    if (ctx->vad) vad_free(ctx->vad);
    free(ctx->f0_values);
    free(ctx->amplitude_values);
    free(ctx);
}
