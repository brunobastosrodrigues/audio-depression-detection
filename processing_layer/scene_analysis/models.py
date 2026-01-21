"""
Scene Analysis Data Models

Defines data structures for XVF3800 DoA fusion and enhanced scene resolution.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict
from enum import Enum


class BoardType(Enum):
    """Hardware board type identifier."""
    RESPEAKER_LITE = 0
    XVF3800 = 1
    UNKNOWN = 255


@dataclass
class AudioChunkMetadata:
    """
    Metadata from edge device accompanying audio chunk.

    This is populated from the MQTT/TCP payload sent by ESP32-S3.
    For ReSpeaker Lite, DoA fields will be None.
    """
    # Device identification
    board_type: BoardType = BoardType.UNKNOWN
    board_id: str = ""
    room: str = ""

    # XVF3800 DoA data (None for ReSpeaker Lite)
    doa_angle: Optional[float] = None  # 0-360 degrees
    doa_confidence: Optional[float] = None  # 0.0-1.0

    # XVF3800 beam/AEC data
    active_beam: Optional[int] = None  # 0=scanning, 1-2=focused
    aec_active: Optional[bool] = None

    # Audio quality
    snr_estimate: Optional[float] = None  # dB

    # Timestamp
    timestamp_ms: int = 0

    @property
    def has_doa(self) -> bool:
        """Check if DoA data is available (XVF3800 only)."""
        return (
            self.doa_angle is not None and
            self.doa_confidence is not None and
            self.doa_confidence > 0.1  # Minimum confidence threshold
        )

    @classmethod
    def from_mqtt_payload(cls, payload: dict) -> "AudioChunkMetadata":
        """
        Create metadata from MQTT payload dictionary.

        Expected payload fields:
            - board_type: int (0=respeaker, 1=xvf3800)
            - board_id: str
            - room: str
            - doa_angle: float (optional)
            - doa_confidence: float (optional)
            - active_beam: int (optional)
            - aec_active: bool (optional)
            - snr_estimate: float (optional)
            - timestamp: int (optional)
        """
        board_type_val = payload.get("board_type", 255)
        try:
            board_type = BoardType(board_type_val)
        except ValueError:
            board_type = BoardType.UNKNOWN

        return cls(
            board_type=board_type,
            board_id=payload.get("board_id", ""),
            room=payload.get("room", ""),
            doa_angle=payload.get("doa_angle"),
            doa_confidence=payload.get("doa_confidence"),
            active_beam=payload.get("active_beam"),
            aec_active=payload.get("aec_active"),
            snr_estimate=payload.get("snr_estimate"),
            timestamp_ms=payload.get("timestamp", 0),
        )


@dataclass
class LocationPrior:
    """
    Expected speaker location for a specific room and time.

    Used for DoA-based speaker verification: if user is expected
    at angle X but audio comes from angle Y, confidence is reduced.
    """
    room: str
    hour_start: int  # 0-23
    hour_end: int  # 0-23 (inclusive)
    expected_doa: float  # 0-360 degrees
    std_dev: float = 30.0  # Gaussian std dev in degrees

    def matches_time(self, hour: int) -> bool:
        """Check if current hour falls within this prior's time range."""
        if self.hour_start <= self.hour_end:
            return self.hour_start <= hour <= self.hour_end
        else:
            # Wraps around midnight
            return hour >= self.hour_start or hour <= self.hour_end


@dataclass
class EnhancedResolveResult:
    """
    Enhanced resolution result with DoA fusion data.

    Extends the basic resolve() result with location scoring
    and fused confidence metrics.
    """
    # Basic result (same as SceneResolver)
    decision: str  # "process" or "discard"
    classification: str  # "target_user", "uncertain", "background_noise", etc.
    similarity: float  # D-vector cosine similarity
    context: str  # "solo_activity", "social_interaction", "background_noise_tv"
    calibration_status: str  # "enrolled", "missing_enrollment"
    config_source: str

    # DoA fusion data (new in V2)
    doa_available: bool = False
    doa_angle: Optional[float] = None
    doa_confidence: Optional[float] = None
    location_score: Optional[float] = None  # 0.0-1.0, how well DoA matches expected
    fused_confidence: Optional[float] = None  # Combined d-vector + DoA score

    # Fusion weights used
    dvector_weight: float = 0.7
    doa_weight: float = 0.3

    # Debug info
    location_prior_used: Optional[str] = None  # Description of prior used

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "decision": self.decision,
            "classification": self.classification,
            "similarity": self.similarity,
            "context": self.context,
            "calibration_status": self.calibration_status,
            "config_source": self.config_source,
            "doa_available": self.doa_available,
            "doa_angle": self.doa_angle,
            "doa_confidence": self.doa_confidence,
            "location_score": self.location_score,
            "fused_confidence": self.fused_confidence,
            "dvector_weight": self.dvector_weight,
            "doa_weight": self.doa_weight,
            "location_prior_used": self.location_prior_used,
        }
