import numpy as np
import librosa
from resemblyzer import VoiceEncoder
from collections import deque
import logging
from typing import Optional, Dict, List

class SceneResolver:
    def __init__(self, user_repository):
        print("Initializing SceneResolver...")
        self.encoder = VoiceEncoder()
        self.repository = user_repository
        self.user_embeddings_cache = {}
        
        # Context buffer: Dictionary mapping user_id -> deque of last N classifications
        # 60 seconds window. Assuming 5s chunks -> 12 items.
        self.context_buffers = {} 
        self.BUFFER_SIZE = 12 
        
        # Thresholds
        self.SIMILARITY_THRESHOLD_HIGH = 0.70 # Relaxed slightly for real-world conditions
        self.SIMILARITY_THRESHOLD_LOW = 0.55 
        
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

    def _detect_mechanical_activity(self, audio_np):
        """
        Simple heuristic to detect typing/mechanical clicks.
        High spectral flatness + high onset strength + low HNR (harmonic-to-noise ratio).
        """
        try:
            # 1. Spectral Flatness (Noise/Clicks are flatter than tone)
            flatness = librosa.feature.spectral_flatness(y=audio_np)[0]
            avg_flatness = np.mean(flatness)
            
            # 2. Onset Strength (Percussive events)
            onset_env = librosa.onset.onset_strength(y=audio_np)
            avg_onset = np.mean(onset_env)

            # 3. Harmonic-to-Noise Ratio (HNR) Check
            # Separate harmonic and percussive components
            y_harm, y_perc = librosa.effects.hpss(audio_np)
            e_harm = np.mean(y_harm**2)
            e_noise = np.mean(y_perc**2)
            
            if e_noise < 1e-9:
                hnr = 100
            else:
                hnr = 10 * np.log10(e_harm / e_noise)

            # Heuristic thresholds (tuned for typing-like sounds)
            # Typing: High onset (percussive), Low HNR (noisy/percussive), High Flatness
            if avg_flatness > 0.3 and avg_onset > 1.0 and hnr < 20:
                return True
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
            # User request: "Default to Solo"
            return {
                "decision": "process", 
                "classification": "unverified", 
                "context": "solo_activity", # Defaulting to Solo as requested
                "similarity": 0.0
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
                "similarity": 0.0
            }

        # 3. Compute Similarity (Cosine)
        similarity = np.dot(ref_emb, curr_emb) / (np.linalg.norm(ref_emb) * np.linalg.norm(curr_emb))
        
        # 4. Classify
        classification = "unknown"
        if similarity >= self.SIMILARITY_THRESHOLD_HIGH:
            classification = "target_user"
        elif similarity < self.SIMILARITY_THRESHOLD_LOW:
            # Check for mechanical noise (Typing) if it's not the user
            if self._detect_mechanical_activity(audio_np):
                classification = "mechanical_activity"
            else:
                classification = "background_noise"
        else:
            classification = "uncertain"

        # 5. Update Context
        if user_id not in self.context_buffers:
            self.context_buffers[user_id] = deque(maxlen=self.BUFFER_SIZE)
        
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
            
            if target_ratio > 0.5: # Majority matches user
                context = "solo_activity"
            elif noise_ratio > 0.6: # Mostly noise/unknown
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
            "context": context
        }
