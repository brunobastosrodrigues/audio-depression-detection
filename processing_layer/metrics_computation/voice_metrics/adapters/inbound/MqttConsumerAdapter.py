from ports.ConsumerPort import ConsumerPort
import queue
import threading
import time

class MqttConsumerAdapter(ConsumerPort):
    def __init__(self, mqtt_client):
        self.client = mqtt_client
        self.topic_handlers = {}
        
        # Threaded processing
        self.message_queue = queue.Queue()
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

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
        # Offload processing to the worker thread immediately
        # This keeps the MQTT loop unblocked
        self.message_queue.put((msg.topic, msg.payload))

    def _worker(self):
        """Background thread to process messages from the queue."""
        print("Worker thread started.")
        while self.is_running:
            try:
                # Get message with timeout to allow checking is_running
                try:
                    topic, payload = self.message_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                self._process_message(topic, payload)
                self.message_queue.task_done()
                
            except Exception as e:
                print(f"Error in worker thread: {e}")

    def _process_message(self, topic, payload):
        """Actual message processing logic."""
        try:
            # Collect all matching handlers
            handlers = []

            # Try exact match first
            if topic in self.topic_handlers:
                handlers.extend(self.topic_handlers[topic])

            # Try wildcard matches
            for pattern, pattern_handlers in self.topic_handlers.items():
                if pattern != topic and self._topic_matches(pattern, topic):
                    handlers.extend(pattern_handlers)

            if not handlers:
                print(f"No handlers for topic: {topic}")
                return

            # Remove duplicates while preserving order
            seen = set()
            unique_handlers = []
            for h in handlers:
                if id(h) not in seen:
                    seen.add(id(h))
                    unique_handlers.append(h)

            for handler in unique_handlers:
                handler(topic, payload)
        except Exception as e:
            print("Error processing message:", e)

    def start(self):
        print("Starting MQTT adapter loop")
        self.client.loop_forever()
