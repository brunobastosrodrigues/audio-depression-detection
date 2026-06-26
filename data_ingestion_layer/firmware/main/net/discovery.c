// discovery.c — mDNS sink discovery with NVS/Kconfig fallback (skeleton).
// SDK: components/mdns (add "mdns" to REQUIRES). See design doc §3.
#include "net/discovery.h"
#include <string.h>
#include <stdio.h>
#include "esp_log.h"
// #include "mdns.h"

static const char *TAG = "discovery";

bool discovery_find_sink(int timeout_ms, const char *fallback_host, int fallback_port,
                         discovery_result_t *out) {
    memset(out, 0, sizeof(*out));
    // TODO(mdns): mdns_init() once at boot; then:
    //   mdns_result_t *r = NULL;
    //   mdns_query_ptr(DISCOVERY_SERVICE, DISCOVERY_PROTO, timeout_ms, 10, &r);
    //   pick first responder; out->host = ip, out->port = r->port,
    //   out->tls = TXT "tls"=="1"; out->from_mdns = true; mdns_query_results_free(r);
    // Below is the fallback path used when mDNS yields nothing:
    if (fallback_host && fallback_host[0]) {
        strncpy(out->host, fallback_host, sizeof(out->host) - 1);
        out->port = fallback_port > 0 ? fallback_port : 1883;
        out->from_mdns = false;
        ESP_LOGW(TAG, "mDNS empty; using stored/compiled broker %s:%d", out->host, out->port);
        return true;
    }
#ifdef CONFIG_SERVER_HOST
    strncpy(out->host, CONFIG_SERVER_HOST, sizeof(out->host) - 1);
    out->port = 1883;
    return true;
#else
    return false;
#endif
}
