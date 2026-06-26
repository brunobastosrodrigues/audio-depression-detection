#!/usr/bin/env bash
# Generate mosquitto.passwd from MQTT_USER/MQTT_PASS in .env. Run once, and again whenever
# the MQTT credentials change. Uses the mosquitto image so no local mosquitto_passwd needed.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [ -f .env ] && . ./.env; set +a
: "${MQTT_USER:?set MQTT_USER in .env}"; : "${MQTT_PASS:?set MQTT_PASS in .env}"
docker run --rm -v "$PWD:/work" -w /work eclipse-mosquitto \
  mosquitto_passwd -b -c mosquitto.passwd "$MQTT_USER" "$MQTT_PASS"
echo "Wrote mosquitto.passwd for user '$MQTT_USER'."
