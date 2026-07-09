// mqtt_sender.c — speech-segment publisher for the plug-and-play offload path.
#include "transport/mqtt_sender.h"
#include "net/mqtt_client.h"
#include "audio/audio_buffer.h"
#include "audio/audio_quality.h"
#include "features/edge_features.h"
#include "config/audio_config.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "mbedtls/base64.h"
#include <string.h>
#include <sys/time.h>

static const char *TAG = "mqtt_sender";

// One utterance segment per message. 8 s @ 16 kHz mono s16 = 256 KB PCM (~342 KB base64);
// staged in PSRAM, well under the broker's 4 MB message_size_limit (PR #87).
#define SEG_MAX_BYTES (16000 * 2 * 8)

static mqtt_sender_stats_t s_stats;

void mqtt_sender_get_stats(mqtt_sender_stats_t *out) { *out = s_stats; }

static double now_unix(void) {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (double)tv.tv_sec + (double)tv.tv_usec / 1e6;
}

static void fill_meta(app_ctx_t *ctx, np_payload_meta_t *m) {
    memset(m, 0, sizeof(*m));
    m->user_id = ctx->prov.user_id;                 // <=0 => server-side recognition
    m->board_id = ctx->node_id;
    m->environment_name = ctx->prov.environment[0] ? ctx->prov.environment : "unassigned";
    m->system_mode = "live";                        // server overrides with the ENROLLED mode
    m->timestamp = now_unix();
    m->sample_rate = 16000;
    m->doa_azimuth = ctx->latest_doa;               // INT16_MIN when no XVF3800
}

static void publish_segment(app_ctx_t *ctx, const uint8_t *pcm, size_t pcm_len,
                            unsigned char *b64, size_t b64_cap) {
    np_payload_meta_t meta;
    fill_meta(ctx, &meta);

    char *json = NULL;
    if (ctx->assignment.mode == NP_MODE_FEATURES) {
        // Feature mode: only the ASSIGNED allow-listed metrics leave the node -- no audio
        // at all. (The server's gap-filler skips the matching extractors; PR #82/#87.)
        uint32_t mask = 0;
        for (int i = 0; ctx->assignment.features[i]; i++) {
            if (!strcmp(ctx->assignment.features[i], NP_FEAT_SNR)) mask |= EF_SNR;
            else if (!strcmp(ctx->assignment.features[i], NP_FEAT_SPECTRAL_FLATNESS)) mask |= EF_SPECTRAL_FLATNESS;
            else if (!strcmp(ctx->assignment.features[i], NP_FEAT_TEMPORAL_MODULATION)) mask |= EF_TEMPORAL_MODULATION;
            else if (!strcmp(ctx->assignment.features[i], NP_FEAT_SPECTRAL_MODULATION)) mask |= EF_SPECTRAL_MODULATION;
        }
        edge_features_t f = {0};
        edge_features_compute((const int16_t *)pcm, (int)(pcm_len / 2),
                              /*noise_floor=*/0.0f, mask, &f);
        size_t k = 0;
        if (f.has_snr)               { meta.feature_names[k] = NP_FEAT_SNR;                 meta.feature_values[k++] = f.snr; }
        if (f.has_spectral_flatness) { meta.feature_names[k] = NP_FEAT_SPECTRAL_FLATNESS;   meta.feature_values[k++] = f.spectral_flatness; }
        if (f.has_temporal_modulation) { meta.feature_names[k] = NP_FEAT_TEMPORAL_MODULATION; meta.feature_values[k++] = f.temporal_modulation; }
        if (f.has_spectral_modulation) { meta.feature_names[k] = NP_FEAT_SPECTRAL_MODULATION; meta.feature_values[k++] = f.spectral_modulation; }
        meta.feature_count = k;
        json = np_build_audio_payload_json(NULL, &meta);
    } else {
        // Segments mode (default): base64 the VAD-gated utterance.
        size_t b64_len = 0;
        if (mbedtls_base64_encode(b64, b64_cap, &b64_len, pcm, pcm_len) != 0) {
            ESP_LOGE(TAG, "base64 overflow (%u bytes pcm)", (unsigned)pcm_len);
            s_stats.segments_dropped++;
            return;
        }
        b64[b64_len] = '\0';
        json = np_build_audio_payload_json((const char *)b64, &meta);
    }
    if (!json) { s_stats.segments_dropped++; return; }

    char topic[96];
    np_topic_voice(&meta, topic, sizeof(topic));
    // QoS1, no retain: an utterance is delivered at-least-once; the server-side handlers
    // are idempotent per (timestamp, board_id).
    if (mqtt_client_publish(topic, json, strlen(json), 1, false)) {
        s_stats.segments_published++;
    } else {
        s_stats.publish_failures++;
    }
    free(json);
}

static void sender_task(void *arg) {
    app_ctx_t *ctx = (app_ctx_t *)arg;

    uint8_t *pcm = heap_caps_malloc(SEG_MAX_BYTES, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    size_t b64_cap = (SEG_MAX_BYTES / 3 + 2) * 4 + 4;
    unsigned char *b64 = heap_caps_malloc(b64_cap, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!pcm || !b64) {
        ESP_LOGE(TAG, "PSRAM alloc failed; sender disabled");
        vTaskDelete(NULL);
        return;
    }

    audio_quality_metrics_t metrics;
    size_t got = 0;
    for (;;) {
        if (audio_buffer_read_speech(pcm, SEG_MAX_BYTES, &got, &metrics,
                                     pdMS_TO_TICKS(1000)) != ESP_OK || got == 0) {
            continue;  // no speech in the last second
        }
        if (ctx->muted || !ctx->assignment.valid || !mqtt_client_is_connected()) {
            // Muted (participant pressed the privacy button) / not negotiated / offline:
            // drop. The ring buffer keeps absorbing upstream; privacy over completeness --
            // we never spool voice to flash, and NOTHING leaves the node while muted.
            s_stats.segments_dropped++;
            continue;
        }
        publish_segment(ctx, pcm, got, b64, b64_cap);
    }
}

void mqtt_sender_start(app_ctx_t *ctx) {
    xTaskCreatePinnedToCore(sender_task, "mqtt_sender", 8192, ctx, 8, NULL, 1);
}
