from ports.UserRepositoryPort import UserRepositoryPort
from pymongo import MongoClient
import numpy as np
from typing import Union, Dict, List
from datetime import datetime


class MongoUserRepositoryAdapter(UserRepositoryPort):
    def __init__(self):
        client = MongoClient("mongodb://mongodb:27017")
        self.db = client["iotsensing"]
        self.collection = self.db["voice_profiling"]
        self.users_collection = self.db["users"]

    def load_all_user_embeddings(self) -> dict:
        profiles = {}
        for record in self.collection.find():
            uid = record["user_id"]
            emb = np.array(record["embedding"], dtype=np.float32)
            profiles.setdefault(uid, []).append(emb)
        return profiles

    def save_user_embedding(
        self, user_id: Union[int, str], embedding: np.ndarray, overwrite: bool = False
    ):
        if overwrite:
            self.collection.delete_many({"user_id": user_id})

        self.collection.insert_one(
            {"user_id": user_id, "embedding": embedding.tolist()}
        )

    def delete_user_embedding(self, user_id: Union[int, str], embedding: np.ndarray):
        target_embedding = embedding.tolist()
        result = self.collection.delete_one(
            {"user_id": user_id, "embedding": target_embedding}
        )

        if result.deleted_count == 0:
            print(f"Warning: No matching embedding found to delete for user {user_id}.")

    def add_user(self, user_profile: Dict) -> bool:
        """
        Add a new user with full profile to the users collection.
        Expected fields: user_id, name, role, voice_embedding, status
        """
        try:
            # Ensure created_at is set
            if "created_at" not in user_profile:
                user_profile["created_at"] = datetime.utcnow().isoformat()
            
            # Ensure status is set
            if "status" not in user_profile:
                user_profile["status"] = "active"
            
            # Insert into users collection
            self.users_collection.insert_one(user_profile)
            
            # Also maintain backward compatibility with voice_profiling collection
            if "voice_embedding" in user_profile:
                self.save_user_embedding(
                    user_profile["user_id"],
                    np.array(user_profile["voice_embedding"]),
                    overwrite=True
                )
            
            return True
        except Exception as e:
            print(f"Error adding user: {e}")
            return False

    def delete_user(self, user_id: Union[int, str]) -> bool:
        """Delete a user and all associated embeddings."""
        try:
            # Delete from users collection
            self.users_collection.delete_one({"user_id": user_id})
            
            # Delete all embeddings from voice_profiling collection
            self.collection.delete_many({"user_id": user_id})
            
            return True
        except Exception as e:
            print(f"Error deleting user: {e}")
            return False

    def get_all_users(self) -> List[Dict]:
        """Get all registered users with their profiles."""
        try:
            users = list(self.users_collection.find({"status": "active"}))
            # Convert ObjectId to string for JSON serialization
            for user in users:
                if "_id" in user:
                    user["_id"] = str(user["_id"])
            return users
        except Exception as e:
            print(f"Error getting users: {e}")
            return []
