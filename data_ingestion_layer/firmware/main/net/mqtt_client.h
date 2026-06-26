// mqtt_client.h — thin esp-mqtt wrapper for the offload protocol (auth, reconnect, pub/sub).
//
// Add `mqtt` to main/CMakeLists.txt REQUIRES. Broker comes from discovery; creds from
// provisioning (PR #81 made the broker require auth).
#pragma once
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// Called when a subscribed message arrives (used for nodes/{id}/config).
typedef void (*mqtt_msg_cb_t)(const char *topic, const char *data, size_t len, void *user);

typedef struct {
    char host[64];
    int  port;
    bool tls;              // 8883 + CA pin from flash
    char client_id[40];    // node_id
    char username[33];
    char password[65];
    mqtt_msg_cb_t on_message;
    void *user;
} mqtt_client_cfg_t;

bool mqtt_client_start(const mqtt_client_cfg_t *cfg);  // connects + auto-reconnects
bool mqtt_client_is_connected(void);
// QoS1; retain for capabilities/config/status, false for voice data.
bool mqtt_client_publish(const char *topic, const char *payload, int len, int qos, bool retain);
bool mqtt_client_subscribe(const char *topic, int qos);
void mqtt_client_stop(void);

#ifdef __cplusplus
}
#endif
