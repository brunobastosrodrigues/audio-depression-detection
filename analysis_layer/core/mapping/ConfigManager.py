import json
import os
from pymongo import MongoClient
from typing import Dict, Any
from datetime import datetime

class ConfigManager:
    def __init__(self):
        mongo_uri = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
        self.client = MongoClient(mongo_uri)
        self.db = self.client["iotsensing"]
        self.collection_user_config = self.db["user_config"]
        self.default_config_path = "core/mapping/config.json"
        self._default_config = self._load_json_file(self.default_config_path)

    def _load_json_file(self, path) -> Dict[str, Any]:
        # resolving path relative to analysis_layer root if running from there
        # typically the code runs from repo root or analysis_layer root.
        # existing code uses "core/mapping/config.json" assuming execution from analysis_layer?
        # Let's try to be robust.
        if not os.path.exists(path):
            # Try prepending analysis_layer/
            path = os.path.join("analysis_layer", path)

        with open(path, "r") as f:
            return json.load(f)

    def get_config(self, user_id: int) -> Dict[str, Any]:
        """
        Retrieves configuration for a user, merging defaults with user overrides.
        """
        user_config_doc = self.collection_user_config.find_one({"user_id": user_id})

        if not user_config_doc:
            return self._default_config

        # Deep merge user overrides into default config
        merged_config = self._deep_copy(self._default_config)
        user_overrides = user_config_doc.get("config", {})

        self._deep_merge(merged_config, user_overrides)
        return merged_config

    def update_threshold(self, user_id: int, indicator_id: str, new_threshold: float):
        """
        Updates the severity threshold for a specific indicator for a user.
        """
        # Fetch current overrides or create new
        user_config_doc = self.collection_user_config.find_one({"user_id": user_id})
        if user_config_doc:
            config = user_config_doc.get("config", {})
        else:
            config = {}

        if indicator_id not in config:
            config[indicator_id] = {}

        config[indicator_id]["severity_threshold"] = new_threshold

        self.collection_user_config.update_one(
            {"user_id": user_id},
            {"$set": {"config": config, "updated_at": datetime.utcnow().isoformat()}},
            upsert=True
        )

    def update_weight(self, user_id: int, indicator_id: str, metric_name: str, new_weight: float):
        """
        Updates the weight for a specific metric in an indicator.
        """
        user_config_doc = self.collection_user_config.find_one({"user_id": user_id})
        if user_config_doc:
            config = user_config_doc.get("config", {})
        else:
            config = {}

        if indicator_id not in config:
            config[indicator_id] = {}
        if "metrics" not in config[indicator_id]:
            config[indicator_id]["metrics"] = {}
        if metric_name not in config[indicator_id]["metrics"]:
            config[indicator_id]["metrics"][metric_name] = {}

        config[indicator_id]["metrics"][metric_name]["weight"] = new_weight

        self.collection_user_config.update_one(
            {"user_id": user_id},
            {"$set": {"config": config}},
            upsert=True
        )

    def _deep_merge(self, target: Dict, source: Dict):
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value

    def _deep_copy(self, data: Dict) -> Dict:
        return json.loads(json.dumps(data))
