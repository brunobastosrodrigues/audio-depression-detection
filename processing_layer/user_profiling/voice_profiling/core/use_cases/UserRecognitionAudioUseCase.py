import numpy as np
from resemblyzer import VoiceEncoder
from audio_utils import wav_bytes_to_np_float32
from ports.UserRepositoryPort import UserRepositoryPort


class UserRecognitionAudioUseCase:
    def __init__(self, repository: UserRepositoryPort, similarity_threshold=0.75):
        self.repository = repository
        self.similarity_threshold = similarity_threshold
        # Adaptive learning constants (optional, but keeping structure if needed later)
        self.MAX_EMBEDDINGS = 20
        self.MAX_SIMILARITY_THRESHOLD_SAVE = 0.95

        self.user_profiles = self.repository.load_all_user_embeddings()
        self.encoder = VoiceEncoder()

    def recognize_user(self, audio_bytes: bytes) -> dict:
        wav, _ = wav_bytes_to_np_float32(audio_bytes)

        # Generate query vector for the short incoming chunk
        query_embedding = np.array(
            self.encoder.embed_utterance(wav).tolist(), dtype=np.float32
        )

        # Compare against known profiles
        matched_user = self._match_user(query_embedding)

        if matched_user:
            # OPTIONAL: Adaptive learning could go here
            # For now, we just recognize the user
            print(f"User {matched_user} recognized.")
            return {"status": "recognized", "user_id": matched_user}
        else:
            # CRITICAL CHANGE: Do NOT create new users.
            # Return None to signal "Ignore this audio"
            print("Unknown speaker detected. Ignoring.")
            return None

    def _match_user(self, embedding):
        """
        Finds the user with the maximum similarity score that exceeds the threshold.
        """
        best_user = None
        max_similarity = -1.0

        for user_id, embeddings in self.user_profiles.items():
            # Calculate max similarity against all embeddings for this user
            sims = [
                np.dot(embedding, e) / (np.linalg.norm(embedding) * np.linalg.norm(e))
                for e in embeddings
            ]

            if not sims:
                continue

            user_max_sim = max(sims)

            if user_max_sim > max_similarity:
                max_similarity = user_max_sim
                best_user = user_id

        # Strict verification: only return if the best match is above threshold
        if max_similarity >= self.similarity_threshold:
            return best_user

        return None

    def _max_similarity(self, embedding, embeddings):
        sims = [
            np.dot(embedding, e) / (np.linalg.norm(embedding) * np.linalg.norm(e))
            for e in embeddings
        ]
        return max(sims)

    def _update_user_profile(self, user_id, embedding):
        profile = self.user_profiles[user_id]
        profile.append(embedding)
        if len(profile) > self.MAX_EMBEDDINGS:
            old_embedding = profile.pop(0)
            self.repository.delete_user_embedding(user_id, old_embedding)
        self.repository.save_user_embedding(user_id, embedding)
