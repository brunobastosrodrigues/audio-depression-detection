import json
import base64
from adapters.inbound.handlers.Handler import Handler


class ComputeMetricsHandler(Handler):
    def __init__(self, use_case):
        self.use_case = use_case

    def __call__(self, topic, payload):
        try:
            data = json.loads(payload.decode())
            audio_b64 = data["data"]
            audio_bytes = base64.b64decode(audio_b64)

            # Extract metadata from payload (optional fields)
            metadata = {
                "board_id": data.get("board_id"),
                "user_id": data.get("user_id"),
                "environment_id": data.get("environment_id"),
                "environment_name": data.get("environment_name"),
                "source_topic": topic,
                "system_mode": data.get("system_mode", "live"),  # Default to live
            }

            self.use_case.execute(audio_bytes, metadata=metadata)
        except Exception as e:
            print(f"Error in ComputeMetricsHandler for topic '{topic}':", e)
