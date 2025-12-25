from ports.ConsumerPort import ConsumerPort


class MqttConsumerAdapter(ConsumerPort):
    def __init__(self, mqtt_client):
        self.client = mqtt_client
        self.topic_handlers = {}

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def register_handler(self, topic, handler: callable):
        if topic not in self.topic_handlers:
            self.topic_handlers[topic] = []
            self.client.subscribe(topic)
            print(f"Subscribed to topic: {topic}")
        self.topic_handlers[topic].append(handler)

    def on_connect(self, client, userdata, flags, rc, properties=None):
        print("Connected to MQTT with result code", rc)
        for topic in self.topic_handlers:
            client.subscribe(topic)

    def _topic_matches(self, pattern: str, topic: str) -> bool:
        """Check if topic matches pattern with MQTT wildcards (# and +)."""
        if pattern == topic:
            return True

        # Handle # wildcard (matches any number of levels)
        if "#" in pattern:
            prefix = pattern.split("#")[0]
            return topic.startswith(prefix)

        # Handle + wildcard (matches single level)
        if "+" in pattern:
            pattern_parts = pattern.split("/")
            topic_parts = topic.split("/")
            if len(pattern_parts) != len(topic_parts):
                return False
            for p, t in zip(pattern_parts, topic_parts):
                if p != "+" and p != t:
                    return False
            return True

        return False

    def on_message(self, client, userdata, msg):
        try:
            # Collect all matching handlers
            handlers = []

            # Try exact match first
            if msg.topic in self.topic_handlers:
                handlers.extend(self.topic_handlers[msg.topic])

            # Try wildcard matches
            for pattern, pattern_handlers in self.topic_handlers.items():
                if pattern != msg.topic and self._topic_matches(pattern, msg.topic):
                    handlers.extend(pattern_handlers)

            if not handlers:
                print(f"No handlers for topic: {msg.topic}")
                return

            # Remove duplicates while preserving order
            seen = set()
            unique_handlers = []
            for h in handlers:
                if id(h) not in seen:
                    seen.add(id(h))
                    unique_handlers.append(h)

            for handler in unique_handlers:
                handler(msg.topic, msg.payload)
        except Exception as e:
            print("Error processing message:", e)

    def start(self):
        print("Starting MQTT adapter loop")
        self.client.loop_forever()
