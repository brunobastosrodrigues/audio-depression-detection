import json
import base64
from adapters.inbound.handlers.Handler import Handler


class ComputeMetricsHandler(Handler):
    def __init__(self, use_case):
        self.use_case = use_case

    def __call__(self, topic, payload):
        try:
            data = json.loads(payload.decode())
            audio_b64 = data.get("data") or ""
            audio_bytes = base64.b64decode(audio_b64)

            # The audio extractors require real audio. The features-only transport (data="",
            # provided_features set) is not yet wired as a no-audio ingestion path, so handle
            # it explicitly rather than crash-dropping it in the generic except below.
            if not audio_bytes:
                if data.get("provided_features"):
                    print(f"[{topic}] features-only payload (no audio) not yet supported; dropping")
                else:
                    print(f"[{topic}] empty audio payload; dropping")
                return

            # Extract metadata from payload (optional fields)
            metadata = {
                "board_id": data.get("board_id"),
                "user_id": data.get("user_id"),
                "environment_id": data.get("environment_id"),
                "environment_name": data.get("environment_name"),
                "source_topic": topic,
                "system_mode": data.get("system_mode", "live"),  # Default to live
                "quality_metrics": data.get("quality_metrics"),
                # Edge-offload: metrics the node computed on-device (gap-filler skips these).
                "provided_features": data.get("provided_features"),
                "node_capabilities_version": data.get("node_capabilities_version"),
            }

            self.use_case.execute(audio_bytes, metadata=metadata)
        except Exception as e:
            print(f"Error in ComputeMetricsHandler for topic '{topic}':", e)
