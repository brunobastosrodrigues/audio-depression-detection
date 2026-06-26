// offload_app.c — plug-and-play boot state machine (skeleton).
// See docs/firmware/PLUG_AND_PLAY_OFFLOAD_DESIGN.md. Wires provisioning -> discovery ->
// mqtt -> negotiate -> stream, and applies live config. Hardware/SDK-gated steps marked TODO.
#include "app/offload_app.h"
#include "net/discovery.h"
#include "net/mqtt_client.h"
#include "wifi_manager.h"        // existing
#include "board_config.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include <string.h>

static const char *TAG = "offload_app";

void offload_app_build_capabilities(app_ctx_t *ctx) {
    np_capabilities_t *c = &ctx->caps;
    np_make_node_id(c->node_id, sizeof(c->node_id));
    strncpy(ctx->node_id, c->node_id, sizeof(ctx->node_id));
    c->firmware = NP_FW_VERSION;
#if HAS_XVF3800
    c->hardware = NP_HARDWARE_XVF;
    c->provides.aec = true; c->provides.doa = true; c->provides.beamforming = true;
#else
    c->hardware = NP_HARDWARE_LITE;
#endif
    c->provides.vad = true;                  // energy VAD always available
    c->provides.speaker_gate = false;        // not yet (server recognizes)
    c->psram_mb = 8; c->sample_rate = 16000; c->frame_ms = 20; c->max_payload_bytes = 8192;
    // Advertise only the features this build actually computes (edge_features). Start
    // conservative; expand after on-device validation vs server extractors.
    int i = 0;
#ifdef CONFIG_EDGE_FEATURE_SNR
    c->provides.features[i++] = NP_FEAT_SNR;
#endif
#ifdef CONFIG_EDGE_FEATURE_SPECTRAL_FLATNESS
    c->provides.features[i++] = NP_FEAT_SPECTRAL_FLATNESS;
#endif
    c->provides.features[i] = NULL;
}

void offload_app_on_mqtt(const char *topic, const char *data, size_t len, void *user) {
    app_ctx_t *ctx = (app_ctx_t *)user;
    char cfg_topic[64];
    np_topic_config(ctx->node_id, cfg_topic, sizeof(cfg_topic));
    if (strcmp(topic, cfg_topic) == 0) {
        np_assignment_free(&ctx->assignment);
        if (np_parse_assignment(data, len, &ctx->assignment)) {
            ctx->config_dirty = true;
            ESP_LOGI(TAG, "assignment: mode=%d vad_gated=%d", ctx->assignment.mode,
                     ctx->assignment.vad_gated);
        }
    }
}

static bool connect_and_negotiate(app_ctx_t *ctx) {
    // DISCOVER_SINK: mDNS -> NVS broker -> Kconfig host.
    discovery_result_t sink;
    if (!discovery_find_sink(5000, ctx->prov.broker_host, ctx->prov.broker_port, &sink)) {
        ESP_LOGW(TAG, "no broker found"); return false;
    }
    ESP_LOGI(TAG, "sink %s:%d (mdns=%d)", sink.host, sink.port, sink.from_mdns);
    // Remember the broker for faster next boot (TODO: provisioning_save with updated host).

    // MQTT_CONN
    mqtt_client_cfg_t mc = {0};
    strncpy(mc.host, sink.host, sizeof(mc.host));
    mc.port = sink.port; mc.tls = sink.tls;
    strncpy(mc.client_id, ctx->node_id, sizeof(mc.client_id));
    strncpy(mc.username, ctx->prov.mqtt_user, sizeof(mc.username));
    strncpy(mc.password, ctx->prov.mqtt_pass, sizeof(mc.password));
    mc.on_message = offload_app_on_mqtt; mc.user = ctx;
    if (!mqtt_client_start(&mc)) return false;
    for (int i = 0; i < 50 && !mqtt_client_is_connected(); i++) vTaskDelay(pdMS_TO_TICKS(100));
    if (!mqtt_client_is_connected()) return false;

    // NEGOTIATE: subscribe config, publish capabilities (retained), wait for assignment.
    char t_cfg[64], t_cap[64];
    np_topic_config(ctx->node_id, t_cfg, sizeof(t_cfg));
    np_topic_capabilities(ctx->node_id, t_cap, sizeof(t_cap));
    mqtt_client_subscribe(t_cfg, 1);
    char *adv = np_build_capabilities_json(&ctx->caps);
    mqtt_client_publish(t_cap, adv, strlen(adv), 1, /*retain=*/true);
    free(adv);
    for (int i = 0; i < 100 && !ctx->assignment.valid; i++) vTaskDelay(pdMS_TO_TICKS(100));
    return ctx->assignment.valid;  // server replied with a config
}

static void app_task(void *arg) {
    app_ctx_t *ctx = (app_ctx_t *)arg;
    for (;;) {
        switch (ctx->state) {
        case APP_BOOT:
            if (!provisioning_load(&ctx->prov)) { ctx->state = APP_PROVISIONING; break; }
            ctx->state = APP_WIFI_CONNECT; break;
        case APP_PROVISIONING:
            ESP_LOGI(TAG, "entering provisioning portal");
            provisioning_run_portal(&ctx->prov, /*timeout_s=*/0);  // blocks until creds
            ctx->state = APP_WIFI_CONNECT; break;
        case APP_WIFI_CONNECT:
            // wifi_manager already STA-connects from creds; here ensure creds applied + wait IP.
            // TODO: wifi_manager_set_credentials(ctx->prov.wifi_ssid, ctx->prov.wifi_pass)
            if (wifi_manager_is_connected()) ctx->state = APP_DISCOVER_SINK;
            else vTaskDelay(pdMS_TO_TICKS(500));
            break;
        case APP_DISCOVER_SINK:  // DISCOVER_SINK + MQTT_CONN + NEGOTIATE
            ctx->state = connect_and_negotiate(ctx) ? APP_STREAMING : APP_RECONNECT;
            break;
        case APP_STREAMING:
            // Audio pipeline runs in i2s/vad tasks; the transport router reads ctx->assignment.
            if (!mqtt_client_is_connected()) { ctx->state = APP_RECONNECT; break; }
            if (ctx->config_dirty) { ctx->config_dirty = false; /* re-apply mode live */ }
            vTaskDelay(pdMS_TO_TICKS(500));
            break;
        case APP_RECONNECT:
            ESP_LOGW(TAG, "reconnecting"); mqtt_client_stop();
            vTaskDelay(pdMS_TO_TICKS(2000));
            ctx->state = wifi_manager_is_connected() ? APP_DISCOVER_SINK : APP_WIFI_CONNECT;
            break;
        default: vTaskDelay(pdMS_TO_TICKS(200));
        }
    }
}

void offload_app_start(app_ctx_t *ctx) {
    ctx->state = APP_BOOT;
    ctx->latest_doa = INT16_MIN;
    offload_app_build_capabilities(ctx);
    xTaskCreatePinnedToCore(app_task, "offload_app", 6144, ctx, 9, NULL, 0);
}
