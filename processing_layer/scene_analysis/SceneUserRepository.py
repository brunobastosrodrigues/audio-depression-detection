"""
Standalone User Repository for Scene Analysis

This is a simplified adapter that provides read-only access to user voice embeddings
for the SceneResolver. It's self-contained to avoid import dependency issues when
mounted as a volume in the voice_metrics container.
"""

from pymongo import MongoClient
import numpy as np
import os


class SceneUserRepository:
    """Lightweight repository for fetching user voice embeddings."""

    def __init__(self):
        mongo_url = os.getenv("MONGO_URL", "mongodb://mongodb:27017")
        client = MongoClient(mongo_url)
        self.db = client["iotsensing"]
        self.voice_collection = self.db["voice_profiling"]

    def load_all_user_embeddings(self) -> dict:
        """
        Load all user voice embeddings from the database.

        Returns:
            dict: Mapping of user_id -> list of embeddings
        """
        profiles = {}
        for record in self.voice_collection.find():
            uid = record["user_id"]
            emb = np.array(record["embedding"], dtype=np.float32)
            profiles.setdefault(uid, []).append(emb)
        return profiles
