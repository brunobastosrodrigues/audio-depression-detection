// provisioning.c — SoftAP/BLE Wi-Fi provisioning + NVS persistence (skeleton).
// SDK: wifi_provisioning (scheme_softap or scheme_ble), nvs_flash. See design doc §2/§8.
#include "provisioning/provisioning.h"
#include <string.h>
#include <stdio.h>
#include "esp_log.h"
#include "nvs.h"
// #include "wifi_provisioning/manager.h"
// #include "wifi_provisioning/scheme_softap.h"

static const char *TAG = "prov";
static const char *NS = "ihy_prov";

bool provisioning_load(prov_config_t *out) {
    memset(out, 0, sizeof(*out));
    nvs_handle_t h;
    if (nvs_open(NS, NVS_READONLY, &h) != ESP_OK) return false;
    size_t n = sizeof(out->wifi_ssid);
    bool ok = nvs_get_str(h, "ssid", out->wifi_ssid, &n) == ESP_OK && out->wifi_ssid[0];
    if (ok) {
        n = sizeof(out->wifi_pass);  nvs_get_str(h, "pass", out->wifi_pass, &n);
        n = sizeof(out->mqtt_user);  nvs_get_str(h, "muser", out->mqtt_user, &n);
        n = sizeof(out->mqtt_pass);  nvs_get_str(h, "mpass", out->mqtt_pass, &n);
        n = sizeof(out->broker_host); nvs_get_str(h, "broker", out->broker_host, &n);
        int32_t v = 0;
        if (nvs_get_i32(h, "bport", &v) == ESP_OK) out->broker_port = v;
        if (nvs_get_i32(h, "uid", &v) == ESP_OK)   out->user_id = v;
        n = sizeof(out->environment); nvs_get_str(h, "env", out->environment, &n);
    }
    nvs_close(h);
    return ok;
}

bool provisioning_save(const prov_config_t *c) {
    nvs_handle_t h;
    if (nvs_open(NS, NVS_READWRITE, &h) != ESP_OK) return false;
    nvs_set_str(h, "ssid", c->wifi_ssid);   nvs_set_str(h, "pass", c->wifi_pass);
    nvs_set_str(h, "muser", c->mqtt_user);  nvs_set_str(h, "mpass", c->mqtt_pass);
    nvs_set_str(h, "broker", c->broker_host); nvs_set_i32(h, "bport", c->broker_port);
    nvs_set_i32(h, "uid", c->user_id);      nvs_set_str(h, "env", c->environment);
    bool ok = nvs_commit(h) == ESP_OK;
    nvs_close(h);
    return ok;
}

void provisioning_erase(void) {
    nvs_handle_t h;
    if (nvs_open(NS, NVS_READWRITE, &h) == ESP_OK) { nvs_erase_all(h); nvs_commit(h); nvs_close(h); }
}

bool provisioning_run_portal(prov_config_t *out, int timeout_s) {
    ESP_LOGI(TAG, "SoftAP portal IHearYou-Setup-XXXX (timeout=%ds)", timeout_s);
    // TODO(wifi_provisioning): wifi_prov_mgr_init(scheme_softap); start with a service name
    //   derived from MAC; register a custom endpoint to also collect mqtt_user/mqtt_pass/uid/env;
    //   on WIFI_PROV_CRED_RECV fill *out; on success persist and return true.
    //   A captive-portal page (or the ESP BLE/SoftAP provisioning apps) drives the UX.
    (void)out; (void)timeout_s;
    return false;  // stub
}

void provisioning_check_factory_reset(void) {
    // TODO: poll GPIO0; if held >=5s -> provisioning_erase() + esp_restart().
}
