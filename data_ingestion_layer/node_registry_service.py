"""Node registry service: the server side of the edge capability handshake.

Subscribes to `nodes/+/capabilities` (retained advertisements from ESP32-S3 nodes),
validates + negotiates an assignment, persists both to the `iotsensing.nodes` registry, and
replies on `nodes/{id}/config` (retained) with what the node should compute and send.

Env: MONGO_URL, MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASS.
"""
import os
import json
from datetime import datetime, timezone

from pymongo import MongoClient
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion

from framework.mqtt_auth import apply_mqtt_auth
from framework.node_registry import NodeRegistry, process_capabilities

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://mongodb:27017")
MQTT_HOST = os.environ.get("MQTT_HOST", "mqtt")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))

CAPABILITIES_TOPIC = "nodes/+/capabilities"


def node_id_from_topic(topic: str):
    parts = topic.split("/")
    return parts[1] if len(parts) >= 3 and parts[0] == "nodes" else None


class NodeRegistryService:
    def __init__(self, mongo_url=MONGO_URL, mqtt_host=MQTT_HOST, mqtt_port=MQTT_PORT):
        self.mongo_client = MongoClient(mongo_url)
        # Global (non mode-isolated) registry, like board/system settings.
        self.registry = NodeRegistry(self.mongo_client["iotsensing"]["nodes"])

        self.mqtt_client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
        apply_mqtt_auth(self.mqtt_client)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(mqtt_host, mqtt_port, 60)
        print(f"Node Registry Service initialized (mongo={mongo_url}, mqtt={mqtt_host}:{mqtt_port})")

    def on_connect(self, client, userdata, flags, rc, properties=None):
        print(f"Connected to MQTT broker with result code {rc}")
        client.subscribe(CAPABILITIES_TOPIC)
        print(f"Subscribed to {CAPABILITIES_TOPIC}")

    def on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            # SECURITY: the TOPIC segment is the authoritative node identity (a node may only
            # publish to its own nodes/{id}/... under broker ACLs). Always use it and ignore any
            # node_id in the payload, so a node can't spoof another node's id to overwrite its
            # registry entry or publish a (retained) config to its topic.
            topic_id = node_id_from_topic(msg.topic)
            if not topic_id:
                print(f"Ignoring advert on non-node topic {msg.topic}")
                return
            if data.get("node_id") and data["node_id"] != topic_id:
                print(f"node_id mismatch: payload '{data['node_id']}' != topic '{topic_id}'; using topic")
            data["node_id"] = topic_id

            caps, assignment, problems = process_capabilities(data)
            if problems:
                print(f"Capability advert from '{data.get('node_id', topic_id)}' has issues: {problems}")
            if caps is None:
                print(f"Ignoring invalid capability advert on {msg.topic}")
                return

            self.registry.register(caps, assignment, last_seen=datetime.now(timezone.utc))
            client.publish(
                f"nodes/{caps.node_id}/config",
                json.dumps(assignment.to_dict()),
                retain=True,
            )
            print(f"Registered node '{caps.node_id}' -> assignment mode={assignment.mode} "
                  f"features={assignment.features}")
        except Exception as e:
            print(f"Error handling capability advert on '{msg.topic}':", e)

    def run(self):
        self.mqtt_client.loop_forever()


if __name__ == "__main__":
    NodeRegistryService().run()
