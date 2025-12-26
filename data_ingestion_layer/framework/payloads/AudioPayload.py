from dataclasses import dataclass
from typing import Literal, Optional, Dict, Any


@dataclass
class AudioPayload:
    data: str  # base64-encoded audio data
    timestamp: float
    sample_rate: int
    type: Literal["audio"] = "audio"
    # Board/environment metadata (optional for backward compatibility)
    board_id: Optional[str] = None
    user_id: Optional[int] = None
    environment_id: Optional[str] = None
    environment_name: Optional[str] = None
    quality_metrics: Optional[Dict[str, Any]] = None

    def to_dict(self):
        result = {
            "data": self.data,
            "timestamp": self.timestamp,
            "sample_rate": self.sample_rate,
            "type": self.type,
        }
        # Include metadata fields only if set
        if self.board_id is not None:
            result["board_id"] = self.board_id
        if self.user_id is not None:
            result["user_id"] = self.user_id
        if self.environment_id is not None:
            result["environment_id"] = self.environment_id
        if self.environment_name is not None:
            result["environment_name"] = self.environment_name
        if self.quality_metrics is not None:
            result["quality_metrics"] = self.quality_metrics
        return result
