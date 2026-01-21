# XVF3800 Integration Sketch

## Overview

This document outlines the modifications needed to integrate XVF3800's Direction of Arrival (DoA) and DSP capabilities into the existing SceneResolver.

---

## Architecture Changes

### Current Flow (ReSpeaker Lite)
```
[Raw Audio] → [SceneResolver] → [D-vector only] → [Decision]
```

### Proposed Flow (XVF3800)
```
[XVF3800 DSP] → [Cleaned Audio + DoA] → [Enhanced SceneResolver] → [D-vector + DoA Fusion] → [Decision]
                      │
                      ├── AEC-cleaned audio
                      ├── Beamformed audio
                      ├── DoA angle (0-360°)
                      └── Beam confidence
```

---

## 1. Data Model Changes

### New: AudioChunkMetadata

```python
# processing_layer/scene_analysis/models.py

from dataclasses import dataclass
from typing import Optional
import numpy as np

@dataclass
class AudioChunkMetadata:
    """Metadata accompanying an audio chunk from edge device."""

    # Device identification
    board_id: str
    board_type: str  # "respeaker_lite" | "xvf3800"

    # XVF3800-specific (None for ReSpeaker Lite)
    doa_angle: Optional[float] = None          # 0-360 degrees
    doa_confidence: Optional[float] = None     # 0.0-1.0
    active_beam: Optional[int] = None          # 0=scanning, 1-2=focused

    # Audio quality indicators
    snr_estimate: Optional[float] = None       # dB
    is_aec_active: Optional[bool] = None       # Echo cancellation active

    # Location context (from board registration)
    room: Optional[str] = None                 # "kitchen", "bedroom", etc.
    position: Optional[tuple] = None           # (x, y) in room coordinates


@dataclass
class EnhancedResolveResult:
    """Extended result from SceneResolver with DoA fusion."""

    # Existing fields
    decision: str                    # "process" | "discard"
    classification: str              # "target_user" | "uncertain" | "background_noise" | etc.
    similarity: float                # D-vector cosine similarity
    context: str                     # "solo_activity" | "social_interaction" | "background_noise_tv"
    calibration_status: str          # "enrolled" | "missing_enrollment"

    # New XVF3800 fields
    doa_angle: Optional[float] = None
    doa_confidence: Optional[float] = None
    location_score: Optional[float] = None     # How well DoA matches expected location
    fused_confidence: Optional[float] = None   # Combined D-vector + DoA score

    # Multi-device fusion (when available)
    device_contributions: Optional[dict] = None  # {board_id: weight}
```

---

## 2. SceneConfig Extension

### scene_config.json additions

```json
{
    "_comment": "Scene Analysis Configuration - Extended for XVF3800",
    "_version": "2.0.0",

    "context_window": {
        "buffer_size": 12
    },

    "speaker_verification": {
        "similarity_threshold_high": 0.70,
        "similarity_threshold_low": 0.55
    },

    "doa_fusion": {
        "enabled": true,
        "doa_weight": 0.3,
        "dvector_weight": 0.7,
        "location_prior_enabled": true,
        "angular_tolerance_degrees": 30,
        "_description": "Fuse D-vector similarity with DoA location prior"
    },

    "location_priors": {
        "_description": "Expected DoA angles by room and time of day",
        "kitchen": {
            "morning": {"angle": 45, "std": 30},
            "afternoon": {"angle": 90, "std": 45},
            "evening": {"angle": 45, "std": 30}
        },
        "living_room": {
            "default": {"angle": 180, "std": 60}
        }
    },

    "multi_device": {
        "enabled": false,
        "triangulation_enabled": false,
        "ensemble_dvector": true,
        "snr_weighting": true,
        "_description": "Multi-device fusion settings"
    },

    "hardware_profiles": {
        "respeaker_lite": {
            "similarity_threshold_high": 0.70,
            "similarity_threshold_low": 0.55,
            "has_doa": false,
            "has_aec": false,
            "far_field_range_m": 2.0
        },
        "xvf3800": {
            "similarity_threshold_high": 0.65,
            "similarity_threshold_low": 0.50,
            "has_doa": true,
            "has_aec": true,
            "far_field_range_m": 5.0,
            "doa_accuracy_degrees": 15,
            "_description": "Lower thresholds because DSP provides cleaner audio"
        }
    }
}
```

---

## 3. Enhanced SceneResolver

### SceneResolverV2.py

```python
"""
Enhanced SceneResolver with XVF3800 DoA fusion support.

Key additions:
1. DoA + D-vector fusion for higher confidence identification
2. Location prior learning (where is user typically?)
3. SNR-weighted confidence
4. Multi-device support (future)
"""

import numpy as np
import librosa
from resemblyzer import VoiceEncoder
from collections import deque
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
import logging
import threading
import math
from datetime import datetime, timezone

from .SceneConfig import SceneConfig
from .models import AudioChunkMetadata, EnhancedResolveResult

logger = logging.getLogger(__name__)


class SceneResolverV2:
    """Enhanced SceneResolver with XVF3800 DoA fusion."""

    def __init__(self, user_repository, config: Optional[SceneConfig] = None):
        print("Initializing SceneResolverV2 (XVF3800-aware)...")
        self.encoder = VoiceEncoder()
        self.repository = user_repository
        self.user_embeddings_cache = {}

        # Load configuration
        self.config = config if config else SceneConfig.load()
        print(f"SceneResolverV2 config loaded: {self.config.config_source}")

        # Context buffers (thread-safe)
        self.context_buffers: Dict[str, deque] = {}
        self._context_lock = threading.Lock()
        self._cache_lock = threading.Lock()

        # Location prior tracking (learned from data)
        # Structure: {user_id: {room: {hour: [doa_angles]}}}
        self.location_history: Dict[str, Dict[str, Dict[int, List[float]]]] = {}
        self._location_lock = threading.Lock()

        print("SceneResolverV2 initialized.")

    # ========== D-VECTOR METHODS (unchanged) ==========

    def _get_user_embedding(self, user_id: str) -> Optional[np.ndarray]:
        """Get user embedding with lazy loading (thread-safe)."""
        if user_id in self.user_embeddings_cache:
            return self.user_embeddings_cache[user_id]

        with self._cache_lock:
            if user_id in self.user_embeddings_cache:
                return self.user_embeddings_cache[user_id]

            try:
                emb = self.repository.get_user_embedding(str(user_id))
                if emb is not None:
                    self.user_embeddings_cache[user_id] = emb
                    logger.info(f"Cached embedding for user {user_id}")
                    return emb
            except Exception as e:
                logger.error(f"Error fetching user embedding: {e}")

        return None

    def _compute_dvector_similarity(
        self, audio_np: np.ndarray, ref_emb: np.ndarray
    ) -> Tuple[float, np.ndarray]:
        """Compute D-vector similarity between audio and reference."""
        try:
            curr_emb = self.encoder.embed_utterance(audio_np)
            similarity = np.dot(ref_emb, curr_emb) / (
                np.linalg.norm(ref_emb) * np.linalg.norm(curr_emb)
            )
            return float(similarity), curr_emb
        except Exception as e:
            logger.error(f"Error computing D-vector: {e}")
            return 0.0, None

    # ========== DOA FUSION METHODS (NEW) ==========

    def _get_location_prior(
        self, user_id: str, room: str, hour: int
    ) -> Tuple[float, float]:
        """
        Get expected DoA angle for user in room at given hour.

        Returns:
            (expected_angle, std_deviation) or (None, None) if no prior
        """
        # First check configured priors
        if hasattr(self.config, 'location_priors'):
            priors = self.config.location_priors
            if room in priors:
                room_prior = priors[room]
                # Time-specific or default
                time_key = self._hour_to_period(hour)
                if time_key in room_prior:
                    return room_prior[time_key]["angle"], room_prior[time_key]["std"]
                elif "default" in room_prior:
                    return room_prior["default"]["angle"], room_prior["default"]["std"]

        # Fall back to learned history
        with self._location_lock:
            if user_id in self.location_history:
                user_hist = self.location_history[user_id]
                if room in user_hist and hour in user_hist[room]:
                    angles = user_hist[room][hour]
                    if len(angles) >= 5:  # Need enough samples
                        return np.mean(angles), np.std(angles)

        return None, None

    def _hour_to_period(self, hour: int) -> str:
        """Convert hour to period name."""
        if 6 <= hour < 12:
            return "morning"
        elif 12 <= hour < 18:
            return "afternoon"
        else:
            return "evening"

    def _update_location_history(
        self, user_id: str, room: str, hour: int, doa_angle: float
    ):
        """Update learned location prior with new observation."""
        with self._location_lock:
            if user_id not in self.location_history:
                self.location_history[user_id] = {}
            if room not in self.location_history[user_id]:
                self.location_history[user_id][room] = {}
            if hour not in self.location_history[user_id][room]:
                self.location_history[user_id][room][hour] = []

            # Keep last 100 observations per hour
            history = self.location_history[user_id][room][hour]
            history.append(doa_angle)
            if len(history) > 100:
                history.pop(0)

    def _compute_location_score(
        self,
        doa_angle: float,
        expected_angle: float,
        expected_std: float,
        tolerance: float = 30.0,
    ) -> float:
        """
        Compute how well observed DoA matches expected location.

        Uses angular distance with Gaussian falloff.

        Returns:
            Score between 0.0 (far from expected) and 1.0 (matches expected)
        """
        # Compute angular distance (handle wraparound)
        diff = abs(doa_angle - expected_angle)
        angular_distance = min(diff, 360 - diff)

        # Gaussian falloff based on expected_std
        effective_std = max(expected_std, tolerance)
        score = np.exp(-0.5 * (angular_distance / effective_std) ** 2)

        return float(score)

    def _fuse_dvector_and_doa(
        self,
        dvector_similarity: float,
        doa_angle: Optional[float],
        user_id: str,
        room: Optional[str],
        hour: int,
    ) -> Tuple[float, Optional[float]]:
        """
        Fuse D-vector similarity with DoA location prior.

        Returns:
            (fused_confidence, location_score)
        """
        # If no DoA available, return D-vector only
        if doa_angle is None or room is None:
            return dvector_similarity, None

        # Check if DoA fusion is enabled
        if not getattr(self.config, 'doa_fusion_enabled', True):
            return dvector_similarity, None

        # Get location prior
        expected_angle, expected_std = self._get_location_prior(user_id, room, hour)

        if expected_angle is None:
            # No prior available, use D-vector only but log DoA for learning
            return dvector_similarity, None

        # Compute location score
        location_score = self._compute_location_score(
            doa_angle, expected_angle, expected_std
        )

        # Weighted fusion
        doa_weight = getattr(self.config, 'doa_weight', 0.3)
        dvector_weight = getattr(self.config, 'dvector_weight', 0.7)

        fused = dvector_weight * dvector_similarity + doa_weight * location_score

        logger.debug(
            f"DoA fusion: dvec={dvector_similarity:.2f}, loc={location_score:.2f}, "
            f"fused={fused:.2f} (DoA={doa_angle:.0f}°, expected={expected_angle:.0f}°)"
        )

        return fused, location_score

    # ========== MECHANICAL DETECTION (unchanged) ==========

    def _detect_mechanical_activity(self, audio_np: np.ndarray, sr: int = 16000) -> bool:
        """Lightweight heuristic to detect typing/mechanical clicks."""
        try:
            zcr = np.mean(librosa.feature.zero_crossing_rate(audio_np)[0])
            centroid = np.mean(librosa.feature.spectral_centroid(y=audio_np, sr=sr)[0])
            rms = librosa.feature.rms(y=audio_np)[0]
            energy_variance = np.var(rms)
            flatness = np.mean(librosa.feature.spectral_flatness(y=audio_np)[0])

            return (
                zcr > self.config.zcr_threshold
                and centroid > self.config.centroid_threshold_hz
                and energy_variance > self.config.energy_variance_threshold
                and flatness > self.config.flatness_threshold
            )
        except Exception:
            return False

    # ========== MAIN RESOLVE METHOD (ENHANCED) ==========

    def resolve(
        self,
        audio_np: np.ndarray,
        user_id: str,
        metadata: Optional[AudioChunkMetadata] = None,
    ) -> EnhancedResolveResult:
        """
        Analyze audio chunk with optional XVF3800 metadata.

        Args:
            audio_np: Audio samples as float32 numpy array
            user_id: Target user ID to verify against
            metadata: Optional XVF3800 metadata (DoA, SNR, etc.)

        Returns:
            EnhancedResolveResult with decision and confidence scores
        """
        # Extract metadata fields (with defaults for ReSpeaker Lite)
        doa_angle = metadata.doa_angle if metadata else None
        doa_confidence = metadata.doa_confidence if metadata else None
        room = metadata.room if metadata else None
        board_type = metadata.board_type if metadata else "respeaker_lite"
        current_hour = datetime.now(timezone.utc).hour

        # 1. Get reference embedding
        ref_emb = self._get_user_embedding(user_id)
        if ref_emb is None:
            logger.warning(f"No voice enrollment for user '{user_id}'. Fail-open mode.")
            return EnhancedResolveResult(
                decision="process",
                classification="unverified",
                similarity=0.0,
                context="solo_activity",
                calibration_status="missing_enrollment",
                doa_angle=doa_angle,
                doa_confidence=doa_confidence,
            )

        # 2. Compute D-vector similarity
        dvector_similarity, curr_emb = self._compute_dvector_similarity(audio_np, ref_emb)

        if curr_emb is None:
            return EnhancedResolveResult(
                decision="discard",
                classification="error",
                similarity=0.0,
                context="error",
                calibration_status="enrolled",
            )

        # 3. Fuse with DoA if available (XVF3800)
        fused_confidence, location_score = self._fuse_dvector_and_doa(
            dvector_similarity, doa_angle, user_id, room, current_hour
        )

        # 4. Classification (use fused confidence if available, else D-vector)
        confidence = fused_confidence if fused_confidence else dvector_similarity

        # Adjust thresholds based on hardware profile
        hw_profile = self.config.hardware_profiles.get(board_type, {})
        threshold_high = hw_profile.get(
            "similarity_threshold_high", self.config.similarity_threshold_high
        )
        threshold_low = hw_profile.get(
            "similarity_threshold_low", self.config.similarity_threshold_low
        )

        if confidence >= threshold_high:
            classification = "target_user"
            # Update location history for learning
            if doa_angle is not None and room is not None:
                self._update_location_history(user_id, room, current_hour, doa_angle)
        elif confidence < threshold_low:
            if self._detect_mechanical_activity(audio_np):
                classification = "mechanical_activity"
            else:
                classification = "background_noise"
        else:
            classification = "uncertain"

        # 5. Update context buffer (thread-safe)
        with self._context_lock:
            if user_id not in self.context_buffers:
                self.context_buffers[user_id] = deque(maxlen=self.config.buffer_size)
            self.context_buffers[user_id].append(classification)
            buffer = list(self.context_buffers[user_id])

        # 6. Determine context
        total = len(buffer)
        target_count = sum(1 for c in buffer if c == "target_user")
        noise_count = sum(
            1 for c in buffer if c in ["background_noise", "mechanical_activity"]
        )

        context = "unknown"
        if total > 0:
            target_ratio = target_count / total
            noise_ratio = noise_count / total

            if target_ratio > self.config.solo_activity_ratio:
                context = "solo_activity"
            elif noise_ratio > self.config.background_noise_ratio:
                context = "background_noise_tv"
            else:
                context = "social_interaction"

        # 7. Decision gatekeeper
        if classification == "target_user":
            decision = "process"
        elif classification == "uncertain" and context == "solo_activity":
            decision = "process"
        else:
            decision = "discard"

        return EnhancedResolveResult(
            decision=decision,
            classification=classification,
            similarity=dvector_similarity,
            context=context,
            calibration_status="enrolled",
            doa_angle=doa_angle,
            doa_confidence=doa_confidence,
            location_score=location_score,
            fused_confidence=fused_confidence,
        )


# ========== MULTI-DEVICE FUSION (FUTURE) ==========

class MultiDeviceResolver:
    """
    Fuses results from multiple SceneResolvers across devices.

    Future implementation for triangulation and ensemble D-vector.
    """

    def __init__(self, resolvers: Dict[str, SceneResolverV2]):
        """
        Args:
            resolvers: Mapping of board_id -> SceneResolverV2 instance
        """
        self.resolvers = resolvers
        self.device_positions: Dict[str, Tuple[float, float]] = {}  # board_id -> (x, y)

    def set_device_position(self, board_id: str, x: float, y: float):
        """Set physical position of a device in room coordinates."""
        self.device_positions[board_id] = (x, y)

    def triangulate_speaker(
        self, doa_readings: Dict[str, float]
    ) -> Optional[Tuple[float, float]]:
        """
        Triangulate speaker position from multiple DoA readings.

        Args:
            doa_readings: Mapping of board_id -> DoA angle (degrees)

        Returns:
            (x, y) position estimate, or None if insufficient data
        """
        if len(doa_readings) < 2:
            return None

        # Simple triangulation using two devices
        # TODO: Implement proper multilateration for 3+ devices
        boards = list(doa_readings.keys())
        if boards[0] not in self.device_positions or boards[1] not in self.device_positions:
            return None

        pos1 = self.device_positions[boards[0]]
        pos2 = self.device_positions[boards[1]]
        angle1 = math.radians(doa_readings[boards[0]])
        angle2 = math.radians(doa_readings[boards[1]])

        # Line intersection (simplified 2D)
        # Each device defines a ray: pos + t * direction
        dir1 = (math.cos(angle1), math.sin(angle1))
        dir2 = (math.cos(angle2), math.sin(angle2))

        # Solve for intersection
        denom = dir1[0] * dir2[1] - dir1[1] * dir2[0]
        if abs(denom) < 1e-6:
            return None  # Parallel lines

        dx = pos2[0] - pos1[0]
        dy = pos2[1] - pos1[1]
        t1 = (dx * dir2[1] - dy * dir2[0]) / denom

        x = pos1[0] + t1 * dir1[0]
        y = pos1[1] + t1 * dir1[1]

        return (x, y)

    def ensemble_resolve(
        self,
        audio_chunks: Dict[str, np.ndarray],
        user_id: str,
        metadata_list: Dict[str, AudioChunkMetadata],
    ) -> EnhancedResolveResult:
        """
        Resolve speaker identity using ensemble of devices.

        Args:
            audio_chunks: Mapping of board_id -> audio array
            user_id: Target user to verify
            metadata_list: Mapping of board_id -> metadata

        Returns:
            Fused EnhancedResolveResult
        """
        results: Dict[str, EnhancedResolveResult] = {}
        weights: Dict[str, float] = {}

        # Get result from each device
        for board_id, audio in audio_chunks.items():
            if board_id not in self.resolvers:
                continue

            metadata = metadata_list.get(board_id)
            result = self.resolvers[board_id].resolve(audio, user_id, metadata)
            results[board_id] = result

            # Weight by SNR (if available) or DoA confidence
            if metadata and metadata.snr_estimate:
                weights[board_id] = max(0, metadata.snr_estimate)  # dB, higher is better
            elif result.doa_confidence:
                weights[board_id] = result.doa_confidence
            else:
                weights[board_id] = 1.0

        if not results:
            return EnhancedResolveResult(
                decision="discard",
                classification="error",
                similarity=0.0,
                context="error",
                calibration_status="unknown",
            )

        # Normalize weights
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}

        # Weighted average of similarities
        fused_similarity = sum(
            weights[bid] * results[bid].similarity for bid in results
        )

        # Majority vote for classification
        classifications = [r.classification for r in results.values()]
        classification = max(set(classifications), key=classifications.count)

        # Majority vote for context
        contexts = [r.context for r in results.values()]
        context = max(set(contexts), key=contexts.count)

        # Decision based on fused result
        if classification == "target_user":
            decision = "process"
        elif classification == "uncertain" and context == "solo_activity":
            decision = "process"
        else:
            decision = "discard"

        # Try triangulation
        doa_readings = {
            bid: r.doa_angle
            for bid, r in results.items()
            if r.doa_angle is not None
        }
        speaker_position = self.triangulate_speaker(doa_readings)

        return EnhancedResolveResult(
            decision=decision,
            classification=classification,
            similarity=fused_similarity,
            context=context,
            calibration_status="enrolled",
            fused_confidence=fused_similarity,
            device_contributions=weights,
        )
```

---

## 4. ESP32-S3 Firmware Changes (XVF3800)

### Reading DoA from XVF3800

```c
// xvf3800_doa.h

#ifndef XVF3800_DOA_H
#define XVF3800_DOA_H

#include <stdint.h>
#include <stdbool.h>

// XVF3800 I2C address (check datasheet)
#define XVF3800_I2C_ADDR 0x2C

// Register addresses (from XVF3800 datasheet)
#define XVF3800_REG_DOA_ANGLE_H    0x10
#define XVF3800_REG_DOA_ANGLE_L    0x11
#define XVF3800_REG_DOA_CONFIDENCE 0x12
#define XVF3800_REG_ACTIVE_BEAM    0x13
#define XVF3800_REG_AEC_STATUS     0x20

typedef struct {
    float doa_angle;        // 0-360 degrees
    float doa_confidence;   // 0.0-1.0
    uint8_t active_beam;    // 0=scanning, 1-2=focused
    bool aec_active;        // Echo cancellation status
} xvf3800_status_t;

/**
 * Initialize I2C communication with XVF3800
 */
esp_err_t xvf3800_init(void);

/**
 * Read current DoA and status from XVF3800
 */
esp_err_t xvf3800_get_status(xvf3800_status_t *status);

#endif
```

```c
// xvf3800_doa.c

#include "xvf3800_doa.h"
#include "driver/i2c.h"
#include "esp_log.h"

static const char *TAG = "XVF3800";

esp_err_t xvf3800_init(void) {
    // I2C already initialized for other purposes
    // Just verify XVF3800 responds
    uint8_t data;
    esp_err_t ret = i2c_master_read_from_device(
        I2C_NUM_0, XVF3800_I2C_ADDR, &data, 1, pdMS_TO_TICKS(100)
    );

    if (ret == ESP_OK) {
        ESP_LOGI(TAG, "XVF3800 detected on I2C");
    } else {
        ESP_LOGE(TAG, "XVF3800 not found on I2C");
    }

    return ret;
}

esp_err_t xvf3800_get_status(xvf3800_status_t *status) {
    uint8_t data[6];
    esp_err_t ret;

    // Read DoA angle (16-bit, 0.01 degree resolution)
    ret = i2c_master_read_from_device(
        I2C_NUM_0, XVF3800_I2C_ADDR,
        data, 4, pdMS_TO_TICKS(50)
    );

    if (ret != ESP_OK) {
        return ret;
    }

    // Parse DoA angle (0-36000 representing 0.00-360.00 degrees)
    uint16_t angle_raw = (data[0] << 8) | data[1];
    status->doa_angle = angle_raw / 100.0f;

    // Parse confidence (0-255 -> 0.0-1.0)
    status->doa_confidence = data[2] / 255.0f;

    // Parse active beam
    status->active_beam = data[3];

    // Read AEC status separately
    uint8_t aec_reg;
    ret = i2c_master_read_from_device(
        I2C_NUM_0, XVF3800_I2C_ADDR,
        &aec_reg, 1, pdMS_TO_TICKS(50)
    );

    status->aec_active = (aec_reg & 0x01) != 0;

    return ESP_OK;
}
```

### Updated Feature Payload

```c
// feature_payload.h

typedef struct __attribute__((packed)) {
    // Header
    uint8_t  board_id[6];
    uint32_t timestamp;
    uint16_t chunk_duration_ms;
    uint16_t sample_rate;
    uint8_t  board_type;      // 0=respeaker_lite, 1=xvf3800

    // Audio features
    float    mfcc_mean[13];
    float    mfcc_std[13];
    float    f0_mean;
    float    f0_std;
    float    rms_mean;
    float    rms_std;

    // XVF3800-specific (zeros for ReSpeaker Lite)
    float    doa_angle;       // 0-360 degrees
    float    doa_confidence;  // 0.0-1.0
    uint8_t  active_beam;     // 0=scanning, 1-2=focused
    uint8_t  aec_active;      // 1=AEC engaged
    float    snr_estimate;    // Estimated SNR in dB

} FeaturePayload;
```

---

## 5. Integration with Voice Metrics Service

### Modified MQTT Handler

```python
# ComputeMetricsHandler.py (modifications)

from processing_layer.scene_analysis.models import AudioChunkMetadata

def _extract_metadata(self, payload: dict) -> AudioChunkMetadata:
    """Extract XVF3800 metadata from MQTT payload."""
    return AudioChunkMetadata(
        board_id=payload.get("board_id", "unknown"),
        board_type=payload.get("board_type", "respeaker_lite"),
        doa_angle=payload.get("doa_angle"),
        doa_confidence=payload.get("doa_confidence"),
        active_beam=payload.get("active_beam"),
        snr_estimate=payload.get("snr_estimate"),
        is_aec_active=payload.get("aec_active", False),
        room=self._get_room_for_board(payload.get("board_id")),
    )

def handle(self, payload: dict):
    """Process incoming audio with XVF3800 metadata."""
    # ... existing code ...

    # Extract metadata for SceneResolver
    metadata = self._extract_metadata(payload)

    # Use enhanced resolver
    scene_result = self.scene_resolver.resolve(
        audio_np, user_id, metadata=metadata
    )

    # Log with DoA info
    if scene_result.doa_angle is not None:
        logger.info(
            f"Scene: {scene_result.classification} @ {scene_result.doa_angle:.0f}° "
            f"(fused={scene_result.fused_confidence:.2f})"
        )

    # ... rest of handling ...
```

---

## 6. Migration Path

### Phase 1: Add XVF3800 Support (Non-Breaking)
1. Add `AudioChunkMetadata` model
2. Add `SceneResolverV2` alongside existing `SceneResolver`
3. Update firmware to include DoA in payload (zeros for ReSpeaker)
4. Factory pattern to choose resolver based on board type

### Phase 2: Enable DoA Fusion
1. Configure `doa_fusion.enabled: true`
2. Add location priors for test rooms
3. Monitor location learning over 1 week
4. Tune fusion weights based on accuracy

### Phase 3: Multi-Device Support
1. Enable `multi_device.enabled: true`
2. Register device positions
3. Test triangulation accuracy
4. Implement ensemble D-vector

---

## 7. Testing Strategy

```python
# tests/test_scene_resolver_v2.py

def test_doa_fusion_improves_uncertain():
    """DoA should resolve uncertain D-vector matches."""
    resolver = SceneResolverV2(mock_repo)

    # Simulate uncertain D-vector (0.60) but correct location
    audio = generate_test_audio()
    metadata = AudioChunkMetadata(
        board_id="xvf3800_1",
        board_type="xvf3800",
        doa_angle=45.0,  # Expected location
        doa_confidence=0.9,
        room="kitchen",
    )

    # Configure expected location
    resolver.config.location_priors = {
        "kitchen": {"default": {"angle": 45, "std": 20}}
    }

    result = resolver.resolve(audio, "user_1", metadata)

    # Should be processed due to location match
    assert result.decision == "process"
    assert result.fused_confidence > 0.6  # Boosted by location


def test_wrong_location_rejects():
    """Wrong DoA should reduce confidence."""
    resolver = SceneResolverV2(mock_repo)

    # Uncertain D-vector AND wrong location
    metadata = AudioChunkMetadata(
        board_id="xvf3800_1",
        board_type="xvf3800",
        doa_angle=180.0,  # Wrong location (expected 45)
        doa_confidence=0.9,
        room="kitchen",
    )

    result = resolver.resolve(audio, "user_1", metadata)

    # Should be rejected due to location mismatch
    assert result.decision == "discard"
    assert result.location_score < 0.3
```

---

## Summary

| Component | Changes |
|-----------|---------|
| `models.py` | New `AudioChunkMetadata` and `EnhancedResolveResult` |
| `scene_config.json` | Add `doa_fusion`, `location_priors`, `hardware_profiles` |
| `SceneResolverV2.py` | DoA fusion, location learning, multi-device support |
| ESP32 firmware | Read DoA from XVF3800 via I2C, include in payload |
| MQTT handler | Extract metadata, pass to resolver |
| Tests | Validate fusion improves accuracy |

This design maintains backward compatibility with ReSpeaker Lite while enabling XVF3800's advanced capabilities.
