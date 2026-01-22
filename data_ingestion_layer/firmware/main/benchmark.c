/**
 * @file benchmark.c
 * @brief Feature extractor performance benchmark
 *
 * @copyright IHearYou Research Project
 */

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "vad.h"
#include "audio_quality.h"
#include <math.h>

#define BENCHMARK_SAMPLES 16000
#define BENCHMARK_ITERATIONS 100

static const char *TAG = "BENCHMARK";

void run_feature_extractor_benchmark(void)
{
    int16_t *test_audio = malloc(BENCHMARK_SAMPLES * sizeof(int16_t));
    if (!test_audio) {
        ESP_LOGE(TAG, "Failed to allocate memory for test audio");
        return;
    }

    // Fill with sine wave
    for (int i = 0; i < BENCHMARK_SAMPLES; i++) {
        test_audio[i] = (int16_t)(sin(2 * M_PI * 440.0 * i / 16000.0) * 16384);
    }

    // Benchmark VAD
    int64_t start_time = esp_timer_get_time();
    for (int i = 0; i < BENCHMARK_ITERATIONS; i++) {
        vad_process(test_audio, BENCHMARK_SAMPLES);
    }
    int64_t end_time = esp_timer_get_time();
    ESP_LOGI(TAG, "VAD benchmark: %lld us per iteration", (end_time - start_time) / BENCHMARK_ITERATIONS);

    // Benchmark audio quality
    audio_quality_metrics_t metrics;
    start_time = esp_timer_get_time();
    for (int i = 0; i < BENCHMARK_ITERATIONS; i++) {
        audio_calculate_quality_metrics(test_audio, BENCHMARK_SAMPLES, &metrics);
    }
    end_time = esp_timer_get_time();
    ESP_LOGI(TAG, "Audio quality benchmark: %lld us per iteration", (end_time - start_time) / BENCHMARK_ITERATIONS);

    free(test_audio);
}
