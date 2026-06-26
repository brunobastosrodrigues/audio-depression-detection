// mqtt_client.c — esp-mqtt wrapper (skeleton). SDK: components/mqtt (add "mqtt" to REQUIRES).
#include "net/mqtt_client.h"
#include <string.h>
#include <stdio.h>
#include "esp_log.h"
// #include "mqtt_client.h"  // esp-mqtt (note: same filename; include via <mqtt_client.h>)

static const char *TAG = "mqtt";
// static esp_mqtt_client_handle_t s_client;
static bool s_connected;
static mqtt_msg_cb_t s_cb;
static void *s_user;

// TODO(esp-mqtt): event handler.
//  MQTT_EVENT_CONNECTED  -> s_connected = true
//  MQTT_EVENT_DISCONNECTED -> s_connected = false  (esp-mqtt auto-reconnects)
//  MQTT_EVENT_DATA -> if (s_cb) s_cb(event->topic, event->data, event->data_len, s_user);

bool mqtt_client_start(const mqtt_client_cfg_t *cfg) {
    s_cb = cfg->on_message; s_user = cfg->user;
    char uri[96];
    snprintf(uri, sizeof(uri), "%s://%s:%d", cfg->tls ? "mqtts" : "mqtt", cfg->host, cfg->port);
    ESP_LOGI(TAG, "connecting %s as %s", uri, cfg->client_id);
    // TODO: esp_mqtt_client_config_t mc = {
    //   .broker.address.uri = uri,
    //   .credentials = { .username = cfg->username, .client_id = cfg->client_id,
    //                    .authentication.password = cfg->password },
    //   .broker.verification.certificate = cfg->tls ? CA_PEM : NULL };
    //   s_client = esp_mqtt_client_init(&mc);
    //   esp_mqtt_client_register_event(s_client, ESP_EVENT_ANY_ID, handler, NULL);
    //   esp_mqtt_client_start(s_client);
    return true;
}

bool mqtt_client_is_connected(void) { return s_connected; }

bool mqtt_client_publish(const char *topic, const char *payload, int len, int qos, bool retain) {
    // TODO: return esp_mqtt_client_publish(s_client, topic, payload, len, qos, retain) >= 0;
    (void)topic; (void)payload; (void)len; (void)qos; (void)retain;
    return s_connected;
}

bool mqtt_client_subscribe(const char *topic, int qos) {
    // TODO: return esp_mqtt_client_subscribe(s_client, topic, qos) >= 0;
    (void)topic; (void)qos; return s_connected;
}

void mqtt_client_stop(void) {
    // TODO: esp_mqtt_client_stop(s_client); esp_mqtt_client_destroy(s_client);
    s_connected = false;
}
