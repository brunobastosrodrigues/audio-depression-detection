from resemblyzer import VoiceEncoder, preprocess_wav
import numpy as np
from ports.UserRepositoryPort import UserRepositoryPort

class EnrollUserUseCase:
    def __init__(self, repository: UserRepositoryPort):
        self.repository = repository
        self.encoder = VoiceEncoder()

    def execute(self, user_id: str, audio_path: str):
        """
        Generates a reference embedding (d-vector) for a specific user
        from a long audio sample (e.g., 30s reading) and saves it.
        """
        # 1. Preprocess audio (normalize, trim silence)
        wav = preprocess_wav(audio_path)

        # 2. Generate Embedding (256-float vector)
        embedding = self.encoder.embed_utterance(wav)

        # 3. Save to DB (overwrite existing if any)
        # Note: Store as list for JSON serialization compatibility
        self.repository.save_user_embedding(user_id, embedding, overwrite=True)

        return {"status": "enrolled", "user_id": user_id}
