import json
from datetime import datetime, timedelta
from pymongo import MongoClient
from typing import List
from core.models.IndicatorScoreRecord import IndicatorScoreRecord
from core.mapping.ConfigManager import ConfigManager
import os

class BaselineManager:
    def __init__(self):
        mongo_uri = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
        self.client = MongoClient(mongo_uri)
        self.db = self.client["iotsensing"]
        self.collection_baseline = self.db["baseline"]
        self.collection_indicator_scores = self.db["indicator_scores"]

        self.config_manager = ConfigManager()

        self.population_baseline = self._load_json_file(
            "core/baseline/population_baseline.json"
        )

        # Load default config initially, but we should use config_manager.get_config(user_id) when needed
        self.config = self.config_manager._default_config
        self.day_adder = 1

    def _load_json_file(self, path):
        if not os.path.exists(path):
             # Try relative to analysis_layer root
             path = os.path.join("analysis_layer", path)

        with open(path, "r") as f:
            return json.load(f)

    def _get_context_key(self, timestamp_dt):
        """
        Map a timestamp to a context partition key.

        Context keys:
        - 'morning': 06:00 to 11:59
        - 'evening': 18:00 to 23:59
        - 'general': all other times or when timestamp is unavailable

        Args:
            timestamp_dt: A datetime object or ISO format string

        Returns:
            str: One of 'morning', 'evening', or 'general'
        """
        if not timestamp_dt:
            return "general"

        # Ensure we have a datetime object
        if isinstance(timestamp_dt, str):
            try:
                timestamp_dt = datetime.fromisoformat(str(timestamp_dt))
            except ValueError:
                return "general"

        hour = timestamp_dt.hour
        if 6 <= hour < 12:
            return "morning"
        elif 18 <= hour <= 23:
            return "evening"
        else:
            return "general"

    def get_population_baseline(self, metric_name=None):
        if metric_name:
            return self.population_baseline.get(metric_name)
        return self.population_baseline

    def get_user_baseline(self, user_id, metric_name=None, timestamp=None):
        """
        Retrieves baseline for a user.

        If 'timestamp' is provided, attempts to fetch the time-specific baseline
        (morning/evening) based on circadian context. Falls back to 'general' if
        the time-specific partition is unavailable or empty.

        Args:
            user_id: The user's ID
            metric_name: Optional specific metric to retrieve
            timestamp: Optional timestamp for context-aware retrieval

        Returns:
            dict or metric value: The baseline metrics or a specific metric value
        """
        latest_doc = self.collection_baseline.find_one(
            {"user_id": user_id}, sort=[("timestamp", -1)]
        )

        if not latest_doc:
            # Cold start: Return population baseline
            if metric_name:
                return self.get_population_baseline(metric_name)
            return self.population_baseline

        # --- Handle Schema V1 (Legacy) ---
        if latest_doc.get("schema_version", 1) < 2:
            user_metrics = latest_doc.get("metrics", {})

        # --- Handle Schema V2 (Context-Aware) ---
        else:
            partitions = latest_doc.get("context_partitions", {})
            target_context = self._get_context_key(timestamp)

            # Try target context, then fallback to general
            context_data = partitions.get(target_context, {}).get("metrics", {})
            if not context_data:
                context_data = partitions.get("general", {}).get("metrics", {})

            user_metrics = context_data

        # --- Return logic ---
        if metric_name:
            return user_metrics.get(
                metric_name, self.get_population_baseline(metric_name)
            )

        # Merge user baselines with any missing population baselines
        merged = self.get_population_baseline().copy()
        merged.update(user_metrics)
        return merged

    def get_indicator_scores(self, user_id: int) -> IndicatorScoreRecord:

        latest_doc = self.collection_indicator_scores.find_one(
            {"user_id": user_id}, sort=[("timestamp", -1)]
        )

        if not latest_doc or "indicator_scores" not in latest_doc:
            print(f"No DSM-5 scores found for user {user_id}.")
            return None

        return IndicatorScoreRecord(
            user_id=latest_doc["user_id"],
            timestamp=latest_doc["timestamp"],
            indicator_scores=latest_doc["indicator_scores"],
        )

    def finetune_baseline(
        self, user_id, phq9_scores, total_score, functional_impact, timestamp
    ):
        """
        Fine-tune the baseline for a user based on PHQ-9 feedback.

        Updates both the context-specific partition (morning/evening) and the
        general partition in V2 schema format.

        Args:
            user_id: The user's ID
            phq9_scores: Dictionary of PHQ-9 indicator scores
            total_score: Total PHQ-9 score
            functional_impact: Functional impact rating
            timestamp: Timestamp of the assessment
        """
        # Get baseline for the specific context
        old_baseline = self.get_user_baseline(user_id, timestamp=timestamp)
        user_indicator_score_record = self.get_indicator_scores(user_id)
        user_indicator_scores = (
            user_indicator_score_record.indicator_scores
            if user_indicator_score_record
            else {}
        )

        if not user_indicator_scores:
            print(
                f"No indicator scores available for user {user_id}. Cannot finetune baseline."
            )
            return

        # Use user-specific config
        user_config = self.config_manager.get_config(user_id)
        baseline_adjustments = {}

        for indicator, actual_score in phq9_scores.items():
            predicted_score = user_indicator_scores.get(indicator)
            if predicted_score is None:
                continue

            error = actual_score - predicted_score

            # Check if indicator exists in config
            if indicator not in user_config:
                continue

            for metric, props in user_config[indicator]["metrics"].items():
                direction = props["direction"]
                weight = props["weight"]

                baseline = old_baseline.get(metric)
                if not baseline:
                    continue

                mean = baseline["mean"]
                std = baseline["std"]

                if direction == "positive":
                    direction_factor = 1
                elif direction == "negative":
                    direction_factor = -1
                else:
                    direction_factor = 1

                learning_rate = 0.2

                adjustment = error * std * learning_rate * direction_factor * weight

                if metric not in baseline_adjustments:
                    baseline_adjustments[metric] = {
                        "adjustments": [],
                        "mean": mean,
                        "std": std,
                    }

                baseline_adjustments[metric]["adjustments"].append(adjustment)

        if not baseline_adjustments:
            print(f"No baseline updates performed.")
            return

        updated_baselines = {}
        for metric, data in baseline_adjustments.items():
            avg_adjustment = sum(data["adjustments"]) / len(data["adjustments"])
            new_mean = data["mean"] + avg_adjustment
            updated_baselines[metric] = {
                "mean": new_mean,
                "std": data["std"],
            }

        complete_baseline = old_baseline.copy()
        complete_baseline.update(updated_baselines)

        # Determine context key for this timestamp
        context_key = self._get_context_key(timestamp)

        # Get existing document to preserve other partitions
        existing_doc = self.collection_baseline.find_one(
            {"user_id": user_id}, sort=[("timestamp", -1)]
        )

        # Build context partitions
        if existing_doc and existing_doc.get("schema_version", 1) >= 2:
            # Preserve existing partitions
            partitions = existing_doc.get("context_partitions", {}).copy()
        else:
            # Initialize new partitions structure
            partitions = {
                "general": {
                    "description": "Fallback baseline derived from all data",
                    "metrics": {}
                },
                "morning": {
                    "description": "06:00 to 12:00",
                    "metrics": {}
                },
                "evening": {
                    "description": "18:00 to 24:00",
                    "metrics": {}
                }
            }

        # Update the target context partition
        if context_key not in partitions:
            partitions[context_key] = {"metrics": {}}
        partitions[context_key]["metrics"] = complete_baseline

        # Also update general partition with the merged data
        general_metrics = partitions.get("general", {}).get("metrics", {}).copy()
        general_metrics.update(updated_baselines)
        partitions["general"]["metrics"] = general_metrics

        # Build V2 document
        updated_doc = {
            "user_id": user_id,
            "timestamp": timestamp,
            "schema_version": 2,
            "context_partitions": partitions,
        }

        self.collection_baseline.replace_one(
            {"user_id": user_id, "timestamp": timestamp},
            updated_doc,
            upsert=True,
        )

        print(f"Finetuned baseline for user {user_id} (context: {context_key})")
