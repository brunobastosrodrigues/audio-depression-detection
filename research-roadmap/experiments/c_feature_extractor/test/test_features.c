/**
 * @file test_features.c
 * @brief Unit tests for feature extractor
 */

#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include "feature_extractor.h"

#define SAMPLE_RATE 16000
#define TEST_DURATION_SEC 5
#define NUM_SAMPLES (SAMPLE_RATE * TEST_DURATION_SEC)

/* Generate sine wave for testing */
static void generate_sine(int16_t* buffer, size_t num_samples, float freq_hz, float amplitude) {
    for (size_t i = 0; i < num_samples; i++) {
        float t = (float)i / SAMPLE_RATE;
        float value = amplitude * sinf(2.0f * M_PI * freq_hz * t);
        buffer[i] = (int16_t)(value * 32767.0f);
    }
}

/* Generate silence */
static void generate_silence(int16_t* buffer, size_t num_samples) {
    memset(buffer, 0, num_samples * sizeof(int16_t));
}

/* Test: Basic initialization and cleanup */
static int test_init_cleanup(void) {
    printf("Test: init/cleanup... ");

    extractor_ctx_t* ctx = extractor_init(NULL);
    if (!ctx) {
        printf("FAILED (init returned NULL)\n");
        return 1;
    }

    extractor_free(ctx);
    printf("PASSED\n");
    return 0;
}

/* Test: Memory estimate */
static int test_memory_estimate(void) {
    printf("Test: memory estimate... ");

    size_t mem = extractor_memory_estimate(NULL);
    printf("estimated %zu bytes... ", mem);

    /* With amplitude buffer, limit is now ~85KB */
    if (mem > 100000) {
        printf("FAILED (exceeds 100KB limit)\n");
        return 1;
    }

    printf("PASSED\n");
    return 0;
}

/* Test: Pure sine wave should have stable F0 */
static int test_sine_f0(void) {
    printf("Test: sine wave F0... ");

    int16_t* audio = (int16_t*)malloc(NUM_SAMPLES * sizeof(int16_t));
    if (!audio) {
        printf("FAILED (malloc)\n");
        return 1;
    }

    /* Generate 200 Hz sine wave */
    float test_freq = 200.0f;
    generate_sine(audio, NUM_SAMPLES, test_freq, 0.8f);

    extractor_ctx_t* ctx = extractor_init(NULL);
    if (!ctx) {
        free(audio);
        printf("FAILED (init)\n");
        return 1;
    }

    features_t features;
    int ret = extractor_process(ctx, audio, NUM_SAMPLES, &features);

    extractor_free(ctx);
    free(audio);

    if (ret != 0) {
        printf("FAILED (process returned %d)\n", ret);
        return 1;
    }

    /* F0 should be close to test frequency */
    float f0_error = fabsf(features.f0_mean - test_freq);
    printf("F0=%.1f Hz (expected %.1f, error=%.1f)... ", features.f0_mean, test_freq, f0_error);

    if (f0_error > 10.0f) {
        printf("FAILED (F0 error too large)\n");
        return 1;
    }

    /* F0 std should be low for pure sine */
    if (features.f0_std > 20.0f) {
        printf("FAILED (F0 std=%.1f too high)\n", features.f0_std);
        return 1;
    }

    printf("PASSED\n");
    return 0;
}

/* Test: Silence should be unvoiced */
static int test_silence(void) {
    printf("Test: silence detection... ");

    int16_t* audio = (int16_t*)malloc(NUM_SAMPLES * sizeof(int16_t));
    if (!audio) {
        printf("FAILED (malloc)\n");
        return 1;
    }

    generate_silence(audio, NUM_SAMPLES);

    extractor_ctx_t* ctx = extractor_init(NULL);
    if (!ctx) {
        free(audio);
        printf("FAILED (init)\n");
        return 1;
    }

    features_t features;
    int ret = extractor_process(ctx, audio, NUM_SAMPLES, &features);

    extractor_free(ctx);
    free(audio);

    if (ret != 0) {
        printf("FAILED (process returned %d)\n", ret);
        return 1;
    }

    printf("pause_ratio=%.2f... ", features.pause_ratio);

    /* Silence should have very high pause ratio */
    if (features.pause_ratio < 0.95f) {
        printf("FAILED (pause_ratio too low)\n");
        return 1;
    }

    printf("PASSED\n");
    return 0;
}

/* Test: Mixed signal (speech-like) */
static int test_mixed_signal(void) {
    printf("Test: mixed signal... ");

    int16_t* audio = (int16_t*)malloc(NUM_SAMPLES * sizeof(int16_t));
    if (!audio) {
        printf("FAILED (malloc)\n");
        return 1;
    }

    /* Generate alternating voiced/unvoiced */
    size_t voiced_samples = SAMPLE_RATE;  /* 1 second */
    size_t silent_samples = SAMPLE_RATE;  /* 1 second */

    size_t offset = 0;
    while (offset < NUM_SAMPLES) {
        /* Voiced segment (150 Hz) */
        size_t len = (offset + voiced_samples <= NUM_SAMPLES) ? voiced_samples : (NUM_SAMPLES - offset);
        generate_sine(audio + offset, len, 150.0f, 0.7f);
        offset += len;

        if (offset >= NUM_SAMPLES) break;

        /* Silent segment */
        len = (offset + silent_samples <= NUM_SAMPLES) ? silent_samples : (NUM_SAMPLES - offset);
        generate_silence(audio + offset, len);
        offset += len;
    }

    extractor_ctx_t* ctx = extractor_init(NULL);
    if (!ctx) {
        free(audio);
        printf("FAILED (init)\n");
        return 1;
    }

    features_t features;
    int ret = extractor_process(ctx, audio, NUM_SAMPLES, &features);

    extractor_free(ctx);
    free(audio);

    if (ret != 0) {
        printf("FAILED (process returned %d)\n", ret);
        return 1;
    }

    printf("pause=%.2f, voiced=%.2f, F0=%.1f... ",
           features.pause_ratio, features.voiced_ratio, features.f0_mean);

    /* Should have roughly 50/50 voiced/unvoiced */
    if (features.pause_ratio < 0.3f || features.pause_ratio > 0.7f) {
        printf("FAILED (unexpected pause_ratio)\n");
        return 1;
    }

    printf("PASSED\n");
    return 0;
}

/* Test: Voice quality metrics on pure sine */
static int test_voice_quality_sine(void) {
    printf("Test: voice quality (sine)... ");

    int16_t* audio = (int16_t*)malloc(NUM_SAMPLES * sizeof(int16_t));
    if (!audio) {
        printf("FAILED (malloc)\n");
        return 1;
    }

    /* Pure 200 Hz sine - should have very low jitter/shimmer, high HNR */
    generate_sine(audio, NUM_SAMPLES, 200.0f, 0.8f);

    extractor_ctx_t* ctx = extractor_init(NULL);
    if (!ctx) {
        free(audio);
        printf("FAILED (init)\n");
        return 1;
    }

    features_t features;
    int ret = extractor_process(ctx, audio, NUM_SAMPLES, &features);

    extractor_free(ctx);
    free(audio);

    if (ret != 0) {
        printf("FAILED (process returned %d)\n", ret);
        return 1;
    }

    printf("\n  jitter=%.4f, shimmer=%.4f, HNR=%.1f dB, SNR=%.1f dB... ",
           features.jitter, features.shimmer, features.hnr_mean, features.snr);

    /* Pure sine should have very low jitter (< 1%) */
    if (features.jitter > 0.01f) {
        printf("FAILED (jitter %.4f > 0.01)\n", features.jitter);
        return 1;
    }

    /* Pure sine should have very low shimmer (< 5%) */
    if (features.shimmer > 0.05f) {
        printf("FAILED (shimmer %.4f > 0.05)\n", features.shimmer);
        return 1;
    }

    /* Pure sine should have high HNR (> 20 dB) */
    if (features.hnr_mean < 20.0f) {
        printf("FAILED (HNR %.1f < 20 dB)\n", features.hnr_mean);
        return 1;
    }

    printf("PASSED\n");
    return 0;
}

/* Test: Voice quality with added noise */
static int test_voice_quality_noisy(void) {
    printf("Test: voice quality (noisy)... ");

    int16_t* audio = (int16_t*)malloc(NUM_SAMPLES * sizeof(int16_t));
    if (!audio) {
        printf("FAILED (malloc)\n");
        return 1;
    }

    /* Generate 200 Hz sine with added noise */
    for (size_t i = 0; i < NUM_SAMPLES; i++) {
        float t = (float)i / SAMPLE_RATE;
        float sine = 0.6f * sinf(2.0f * M_PI * 200.0f * t);
        /* Add random noise (-0.2 to 0.2) */
        float noise = ((float)rand() / RAND_MAX - 0.5f) * 0.4f;
        audio[i] = (int16_t)((sine + noise) * 32767.0f);
    }

    extractor_ctx_t* ctx = extractor_init(NULL);
    if (!ctx) {
        free(audio);
        printf("FAILED (init)\n");
        return 1;
    }

    features_t features;
    int ret = extractor_process(ctx, audio, NUM_SAMPLES, &features);

    extractor_free(ctx);
    free(audio);

    if (ret != 0) {
        printf("FAILED (process returned %d)\n", ret);
        return 1;
    }

    printf("\n  jitter=%.4f, shimmer=%.4f, HNR=%.1f dB, SNR=%.1f dB... ",
           features.jitter, features.shimmer, features.hnr_mean, features.snr);

    /* Noisy signal should have higher jitter than pure sine */
    /* But still detect F0 */
    if (features.f0_mean < 150.0f || features.f0_mean > 250.0f) {
        printf("FAILED (F0 %.1f outside expected range)\n", features.f0_mean);
        return 1;
    }

    /* HNR should be lower than pure sine (noise degrades it) */
    if (features.hnr_mean > 30.0f) {
        printf("FAILED (HNR %.1f too high for noisy signal)\n", features.hnr_mean);
        return 1;
    }

    printf("PASSED\n");
    return 0;
}

/* Test: SNR calculation with mixed voiced/unvoiced */
static int test_snr_calculation(void) {
    printf("Test: SNR calculation... ");

    int16_t* audio = (int16_t*)malloc(NUM_SAMPLES * sizeof(int16_t));
    if (!audio) {
        printf("FAILED (malloc)\n");
        return 1;
    }

    /* First half: loud sine (voiced), second half: quiet noise (unvoiced) */
    size_t half = NUM_SAMPLES / 2;

    /* Loud voiced section */
    generate_sine(audio, half, 150.0f, 0.8f);

    /* Quiet unvoiced section (low amplitude noise) */
    for (size_t i = half; i < NUM_SAMPLES; i++) {
        float noise = ((float)rand() / RAND_MAX - 0.5f) * 0.02f;  /* Very quiet */
        audio[i] = (int16_t)(noise * 32767.0f);
    }

    extractor_ctx_t* ctx = extractor_init(NULL);
    if (!ctx) {
        free(audio);
        printf("FAILED (init)\n");
        return 1;
    }

    features_t features;
    int ret = extractor_process(ctx, audio, NUM_SAMPLES, &features);

    extractor_free(ctx);
    free(audio);

    if (ret != 0) {
        printf("FAILED (process returned %d)\n", ret);
        return 1;
    }

    printf("SNR=%.1f dB... ", features.snr);

    /* SNR is now inverted to match Python (N/S ratio) */
    /* Signal louder than noise should result in NEGATIVE dB */
    if (features.snr > -10.0f) {
        printf("FAILED (Inverted SNR %.1f too high, should be < -10)\n", features.snr);
        return 1;
    }

    printf("PASSED\n");
    return 0;
}

int main(void) {
    printf("=== Feature Extractor Tests (Phase 2: Voice Quality) ===\n\n");

    int failures = 0;

    /* Basic tests */
    failures += test_init_cleanup();
    failures += test_memory_estimate();
    failures += test_sine_f0();
    failures += test_silence();
    failures += test_mixed_signal();

    /* Voice quality tests (Phase 2) */
    printf("\n--- Voice Quality Tests ---\n");
    failures += test_voice_quality_sine();
    failures += test_voice_quality_noisy();
    failures += test_snr_calculation();

    printf("\n=== Results: %d failures ===\n", failures);

    return failures;
}
