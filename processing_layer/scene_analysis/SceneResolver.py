import numpy as np
import librosa
from resemblyzer import VoiceEncoder
from collections import deque
import logging
from typing import Optional, Dict, List

from .SceneConfig import SceneConfig

logger = logging.getLogger(__name__)


class SceneResolver:
    def __init__(self, user_repository, config: Optional[SceneConfig] = None):
        print("Initializing SceneResolver...")
        self.encoder = VoiceEncoder()
        self.repository = user_repository
        self.user_embeddings_cache = {}

        # Load configuration (JSON + env overrides)
        self.config = config if config else SceneConfig.load()
        print(f"SceneResolver config loaded: {self.config.config_source}")

        # Context buffer: Dictionary mapping user_id -> deque of last N classifications
        self.context_buffers = {}

        print("SceneResolver initialized.")

    def _get_user_embedding(self, user_id):
        if user_id in self.user_embeddings_cache:
            return self.user_embeddings_cache[user_id]
        
        # Fetch from Repo
        try:
            profiles = self.repository.load_all_user_embeddings()
            if user_id in profiles and profiles[user_id]:
                # Take the most recent embedding (last in list)
                emb = profiles[user_id][-1]
                self.user_embeddings_cache[user_id] = emb
                return emb
        except Exception as e:
            logging.error(f"Error fetching user embedding: {e}")
            
        return None

    def _detect_mechanical_activity(self, audio_np, sr=16000):
        """
        Lightweight heuristic to detect typing/mechanical clicks.
        Uses ZCR + spectral centroid + energy variance instead of expensive HPSS.
        Target latency: ~5ms (vs ~200ms with HPSS)

        Typing/clicks characteristics:
        - High zero-crossing rate (impulsive sounds)
        - High spectral centroid (concentrated high-freq energy)
        - High energy variance (bursty, non-sustained energy)
        """
        try:
            # 1. Zero-crossing rate (impulsive sounds have high ZCR)
            zcr = librosa.feature.zero_crossing_rate(audio_np)[0]
            avg_zcr = np.mean(zcr)

            # 2. Spectral centroid (mechanical clicks have concentrated high-freq energy)
            centroid = librosa.feature.spectral_centroid(y=audio_np, sr=sr)[0]
            avg_centroid = np.mean(centroid)

            # 3. Energy variance (typing has bursty, non-sustained energy)
            rms = librosa.feature.rms(y=audio_np)[0]
            energy_variance = np.var(rms)

            # 4. Spectral flatness (noise/clicks are spectrally flatter than voice)
            flatness = librosa.feature.spectral_flatness(y=audio_np)[0]
            avg_flatness = np.mean(flatness)

            # Heuristic thresholds from config (tuned for typing-like sounds)
            # Typing: high ZCR + high centroid + high energy variance + high flatness
            is_mechanical = (
                avg_zcr > self.config.zcr_threshold and
                avg_centroid > self.config.centroid_threshold_hz and
                energy_variance > self.config.energy_variance_threshold and
                avg_flatness > self.config.flatness_threshold
            )

            return is_mechanical
        except Exception:
            pass
        return False

    def resolve(self, audio_np: np.ndarray, user_id: str) -> Dict:
        """
        Analyze audio chunk and update context.
        Returns decision: 'process' or 'discard', along with context metadata.
        """
        
        # 1. Get Reference
        ref_emb = self._get_user_embedding(user_id)
        if ref_emb is None:
            # Fail Open (Allow) if no enrollment data.
            # CALIBRATION WARNING: Log visible warning for missing enrollment
            logging.warning(
                f"⚠️ CALIBRATION WARNING: User '{user_id}' has no voice enrollment. "
                "Scene verification disabled - all audio treated as 'solo_activity'. "
                "Enroll user voice profile to enable speaker verification."
            )
            return {
                "decision": "process",
                "classification": "unverified",
                "context": "solo_activity",
                "similarity": 0.0,
                "calibration_status": "missing_enrollment"
            }

        # 2. Compute Embedding of incoming chunk
        try:
            # Resemblyzer expects a specific format. audio_np is float32 usually.
            curr_emb = self.encoder.embed_utterance(audio_np)
        except Exception as e:
            logging.error(f"Error generating embedding: {e}")
            return {
                "decision": "discard",
                "classification": "error",
                "context": "error",
                "similarity": 0.0,
                "calibration_status": "enrolled"
            }

        # 3. Compute Similarity (Cosine)
        similarity = np.dot(ref_emb, curr_emb) / (np.linalg.norm(ref_emb) * np.linalg.norm(curr_emb))
        
        # 4. Classify using config thresholds
        classification = "unknown"
        if similarity >= self.config.similarity_threshold_high:
            classification = "target_user"
        elif similarity < self.config.similarity_threshold_low:
            # Check for mechanical noise (Typing) if it's not the user
            if self._detect_mechanical_activity(audio_np):
                classification = "mechanical_activity"
            else:
                classification = "background_noise"
        else:
            classification = "uncertain"

        # 5. Update Context
        if user_id not in self.context_buffers:
            self.context_buffers[user_id] = deque(maxlen=self.config.buffer_size)
        
        self.context_buffers[user_id].append(classification)
        
        # 6. Determine Context
        buffer = self.context_buffers[user_id]
        total = len(buffer)
        target_count = sum(1 for c in buffer if c == "target_user")
        noise_count = sum(1 for c in buffer if c in ["background_noise", "mechanical_activity"])
        
        context = "unknown"
        if total > 0:
            target_ratio = target_count / total
            noise_ratio = noise_count / total

            # Use config thresholds for context classification
            if target_ratio > self.config.solo_activity_ratio:
                context = "solo_activity"
            elif noise_ratio > self.config.background_noise_ratio:
                context = "background_noise_tv"
            else:
                # Mixed bag -> likely interaction
                context = "social_interaction"

        # 7. Decision Gatekeeper
        decision = "discard"
        
        if classification == "target_user":
            decision = "process"
        elif classification == "uncertain" and context == "solo_activity":
             # If we are in a solo context, be more lenient with uncertain chunks
             decision = "process"
        
        # Log transition/context for debugging
        # print(f"User: {user_id} | Sim: {similarity:.2f} | Class: {classification} | Context: {context} -> {decision}")
        
        return {
            "decision": decision,
            "classification": classification,
            "similarity": float(similarity),
            "context": context,
            "calibration_status": "enrolled",
            "config_source": self.config.config_source,
        }

    def get_config_dict(self) -> dict:
        """Return current configuration as dictionary for debugging/dashboard."""
        return self.config.to_dict()
