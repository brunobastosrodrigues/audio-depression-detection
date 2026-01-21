"""
SceneResolverV2 - Enhanced Scene Analysis with DoA Fusion

Extends SceneResolver with Direction of Arrival (DoA) fusion for XVF3800 boards.
Combines D-vector speaker verification with spatial location scoring.

Key enhancements over V1:
1. DoA + D-vector fusion for improved speaker identification
2. Location priors based on room and time of day
3. Backward compatible with ReSpeaker Lite (no DoA)
"""

import math
import numpy as np
import logging
from typing import Optional, Dict
from datetime import datetime

from .SceneResolver import SceneResolver
from .SceneConfig import SceneConfig
from .models import AudioChunkMetadata, EnhancedResolveResult, BoardType

logger = logging.getLogger(__name__)


class SceneResolverV2(SceneResolver):
    """
    Enhanced SceneResolver with DoA fusion for XVF3800 boards.

    Inherits all V1 functionality and adds:
    - DoA-based location scoring
    - Fused confidence combining D-vector + DoA
    - Location prior learning

    Usage:
        resolver = SceneResolverV2(user_repository)

        # V1 API (backward compatible)
        result = resolver.resolve(audio_np, user_id)

        # V2 API (with DoA metadata)
        metadata = AudioChunkMetadata.from_mqtt_payload(payload)
        result = resolver.resolve_with_doa(audio_np, user_id, metadata)
    """

    def __init__(self, user_repository, config: Optional[SceneConfig] = None):
        """Initialize SceneResolverV2."""
        super().__init__(user_repository, config)
        print("SceneResolverV2 initialized (DoA fusion enabled)")

        # Location history for adaptive priors
        # {user_id: {room: [(hour, doa_angle), ...]}}
        self._location_history: Dict[str, Dict[str, list]] = {}

    def _compute_location_score(
        self,
        doa_angle: float,
        expected_doa: float,
        std_dev: float
    ) -> float:
        """
        Compute location score using Gaussian falloff.

        How close is the observed DoA to the expected location?

        Args:
            doa_angle: Observed DoA in degrees (0-360)
            expected_doa: Expected DoA in degrees (0-360)
            std_dev: Standard deviation in degrees

        Returns:
            Score from 0.0 to 1.0 (1.0 = perfect match)
        """
        # Calculate angular distance (handle wrap-around at 360)
        diff = abs(doa_angle - expected_doa)
        angular_distance = min(diff, 360 - diff)

        # Gaussian falloff
        score = math.exp(-0.5 * (angular_distance / std_dev) ** 2)
        return score

    def _get_location_prior(
        self,
        room: str,
        hour: int
    ) -> tuple[float, float]:
        """
        Get expected DoA and std_dev for a room at given hour.

        Args:
            room: Room name (e.g., "kitchen", "living_room")
            hour: Hour of day (0-23)

        Returns:
            (expected_doa, std_dev) tuple
        """
        priors = self.config.location_priors

        if room not in priors:
            # No prior for this room - use wide default
            return (180.0, 90.0)

        room_prior = priors[room]
        default_doa = room_prior.get("default_doa", 180)
        default_std = room_prior.get("std_dev", 60)

        # Check time-based overrides
        time_based = room_prior.get("time_based", [])
        for tb in time_based:
            hours = tb.get("hours", [])
            if len(hours) >= 2:
                hour_start, hour_end = hours[0], hours[1]
                if hour_start <= hour <= hour_end:
                    return (tb.get("doa", default_doa), tb.get("std", default_std))

        return (default_doa, default_std)

    def _fuse_dvector_and_doa(
        self,
        dvector_similarity: float,
        doa_angle: float,
        doa_confidence: float,
        room: str,
        hour: int
    ) -> tuple[float, float, str]:
        """
        Fuse D-vector similarity with DoA location score.

        Args:
            dvector_similarity: Cosine similarity from D-vector (0-1)
            doa_angle: Observed DoA in degrees
            doa_confidence: DoA confidence from XVF3800 (0-1)
            room: Room name
            hour: Hour of day

        Returns:
            (fused_confidence, location_score, prior_description)
        """
        fusion_config = self.config.doa_fusion

        # Get expected location
        expected_doa, std_dev = self._get_location_prior(room, hour)

        # Compute location score
        location_score = self._compute_location_score(doa_angle, expected_doa, std_dev)

        # Weight by DoA confidence (poor DoA confidence = less weight)
        effective_doa_weight = fusion_config.doa_weight * doa_confidence

        # Normalize weights
        total_weight = fusion_config.dvector_weight + effective_doa_weight
        norm_dvector_weight = fusion_config.dvector_weight / total_weight
        norm_doa_weight = effective_doa_weight / total_weight

        # Fused confidence
        fused_confidence = (
            norm_dvector_weight * dvector_similarity +
            norm_doa_weight * location_score
        )

        prior_desc = f"{room}@{hour}h: expected={expected_doa:.0f}deg, observed={doa_angle:.0f}deg"

        return (fused_confidence, location_score, prior_desc)

    def _update_location_history(
        self,
        user_id: str,
        room: str,
        hour: int,
        doa_angle: float,
        classification: str
    ):
        """
        Update location history for adaptive priors (future use).

        Only records when classification is 'target_user' to learn
        actual user locations.
        """
        if classification != "target_user":
            return

        if user_id not in self._location_history:
            self._location_history[user_id] = {}

        if room not in self._location_history[user_id]:
            self._location_history[user_id][room] = []

        # Keep last 100 observations per room
        history = self._location_history[user_id][room]
        history.append((hour, doa_angle))
        if len(history) > 100:
            self._location_history[user_id][room] = history[-100:]

    def resolve_with_doa(
        self,
        audio_np: np.ndarray,
        user_id: str,
        metadata: Optional[AudioChunkMetadata] = None
    ) -> EnhancedResolveResult:
        """
        Resolve audio chunk with optional DoA metadata.

        This is the V2 API that supports DoA fusion for XVF3800 boards.
        Falls back to V1 behavior if metadata is None or DoA not available.

        Args:
            audio_np: Audio samples as numpy array
            user_id: User ID to verify against
            metadata: Optional metadata from edge device

        Returns:
            EnhancedResolveResult with DoA fusion data
        """
        # First, run base V1 resolution
        v1_result = self.resolve(audio_np, user_id)

        # If no metadata or no DoA, return V1 result wrapped in V2 format
        if metadata is None or not metadata.has_doa:
            return EnhancedResolveResult(
                decision=v1_result["decision"],
                classification=v1_result["classification"],
                similarity=v1_result["similarity"],
                context=v1_result["context"],
                calibration_status=v1_result["calibration_status"],
                config_source=v1_result["config_source"],
                doa_available=False,
                dvector_weight=self.config.doa_fusion.dvector_weight,
                doa_weight=self.config.doa_fusion.doa_weight,
            )

        # DoA fusion enabled and available
        if not self.config.doa_fusion.enabled:
            # Fusion disabled in config
            return EnhancedResolveResult(
                decision=v1_result["decision"],
                classification=v1_result["classification"],
                similarity=v1_result["similarity"],
                context=v1_result["context"],
                calibration_status=v1_result["calibration_status"],
                config_source=v1_result["config_source"],
                doa_available=True,
                doa_angle=metadata.doa_angle,
                doa_confidence=metadata.doa_confidence,
                dvector_weight=1.0,
                doa_weight=0.0,
            )

        # Check minimum DoA confidence
        if metadata.doa_confidence < self.config.doa_fusion.min_doa_confidence:
            logger.debug(f"DoA confidence {metadata.doa_confidence:.2f} below threshold")
            return EnhancedResolveResult(
                decision=v1_result["decision"],
                classification=v1_result["classification"],
                similarity=v1_result["similarity"],
                context=v1_result["context"],
                calibration_status=v1_result["calibration_status"],
                config_source=v1_result["config_source"],
                doa_available=True,
                doa_angle=metadata.doa_angle,
                doa_confidence=metadata.doa_confidence,
                dvector_weight=1.0,
                doa_weight=0.0,
                location_prior_used="DoA confidence too low",
            )

        # Perform fusion
        hour = datetime.now().hour
        room = metadata.room if metadata.room else "unknown"

        fused_confidence, location_score, prior_desc = self._fuse_dvector_and_doa(
            dvector_similarity=v1_result["similarity"],
            doa_angle=metadata.doa_angle,
            doa_confidence=metadata.doa_confidence,
            room=room,
            hour=hour,
        )

        # Re-evaluate classification based on fused confidence
        classification = v1_result["classification"]
        decision = v1_result["decision"]

        # Key fusion logic: DoA can upgrade uncertain to target_user
        if classification == "uncertain":
            if fused_confidence >= self.config.similarity_threshold_high:
                classification = "target_user"
                decision = "process"
                logger.info(f"DoA fusion upgraded uncertain->target_user (fused={fused_confidence:.2f})")
            elif location_score < 0.3:
                # DoA says speaker is NOT where target user expected
                classification = "background_noise"
                decision = "discard"
                logger.info(f"DoA fusion downgraded uncertain->background (location_score={location_score:.2f})")

        # Update location history for learning
        self._update_location_history(
            user_id, room, hour, metadata.doa_angle, classification
        )

        return EnhancedResolveResult(
            decision=decision,
            classification=classification,
            similarity=v1_result["similarity"],
            context=v1_result["context"],
            calibration_status=v1_result["calibration_status"],
            config_source=v1_result["config_source"],
            doa_available=True,
            doa_angle=metadata.doa_angle,
            doa_confidence=metadata.doa_confidence,
            location_score=location_score,
            fused_confidence=fused_confidence,
            dvector_weight=self.config.doa_fusion.dvector_weight,
            doa_weight=self.config.doa_fusion.doa_weight,
            location_prior_used=prior_desc,
        )

    def resolve(self, audio_np: np.ndarray, user_id: str) -> Dict:
        """
        V1 API compatibility - resolve without DoA.

        This method is unchanged from V1 for backward compatibility.
        Use resolve_with_doa() for V2 features.
        """
        return super().resolve(audio_np, user_id)
