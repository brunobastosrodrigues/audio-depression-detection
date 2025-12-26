import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
import os
import sys

# Ensure analysis_layer is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.baseline.BaselineManager import BaselineManager

class TestContextAwareBaseline(unittest.TestCase):
    def setUp(self):
        # Patch MongoClient to use mongomock or MagicMock
        self.mongo_patcher = patch('core.baseline.BaselineManager.MongoClient')
        self.mock_mongo_client_cls = self.mongo_patcher.start()
        self.mock_client = MagicMock()
        self.mock_mongo_client_cls.return_value = self.mock_client

        # Mock database and collections
        self.mock_db = self.mock_client["iotsensing"]
        self.mock_collection_baseline = self.mock_db["baseline"]
        self.mock_collection_indicator_scores = self.mock_db["indicator_scores"]

        # Mock ConfigManager to avoid its initialization issues
        self.config_patcher = patch('core.baseline.BaselineManager.ConfigManager')
        self.mock_config_manager_cls = self.config_patcher.start()
        self.mock_config_manager = self.mock_config_manager_cls.return_value
        self.mock_config_manager.get_config.return_value = {
             "1_depressed_mood": {
                 "metrics": {
                     "f0_avg": {"direction": "negative", "weight": 1.0}
                 }
             }
        }
        self.mock_config_manager._default_config = {}

        self.baseline_manager = BaselineManager()

        # Mock population baseline
        self.baseline_manager.population_baseline = {
            "f0_avg": {"mean": 120.0, "std": 10.0}
        }

    def tearDown(self):
        self.mongo_patcher.stop()
        self.config_patcher.stop()

    def test_context_key_logic(self):
        # Morning: 06:00 to 11:59
        dt_morning = datetime(2023, 10, 27, 8, 0, 0)
        self.assertEqual(self.baseline_manager._get_context_key(dt_morning), "morning")

        dt_morning_edge = datetime(2023, 10, 27, 6, 0, 0)
        self.assertEqual(self.baseline_manager._get_context_key(dt_morning_edge), "morning")

        # Evening: 18:00 to 23:59
        dt_evening = datetime(2023, 10, 27, 20, 0, 0)
        self.assertEqual(self.baseline_manager._get_context_key(dt_evening), "evening")

        dt_evening_edge = datetime(2023, 10, 27, 18, 0, 0)
        self.assertEqual(self.baseline_manager._get_context_key(dt_evening_edge), "evening")

        # General: 12:00 to 17:59, and 00:00 to 05:59
        dt_afternoon = datetime(2023, 10, 27, 14, 0, 0)
        self.assertEqual(self.baseline_manager._get_context_key(dt_afternoon), "general")

        dt_night = datetime(2023, 10, 27, 2, 0, 0)
        self.assertEqual(self.baseline_manager._get_context_key(dt_night), "general")

    def test_get_user_baseline_returns_correct_partition(self):
        user_id = 123

        # Setup mock document in V2 format
        mock_doc = {
            "user_id": user_id,
            "timestamp": "2023-10-27T08:00:00",
            "schema_version": 2,
            "context_partitions": {
                "general": {
                    "metrics": {"f0_avg": {"mean": 120.0, "std": 10.0}}
                },
                "morning": {
                    "metrics": {"f0_avg": {"mean": 110.0, "std": 5.0}}
                },
                "evening": {
                    "metrics": {"f0_avg": {"mean": 130.0, "std": 15.0}}
                }
            }
        }

        self.mock_collection_baseline.find_one.return_value = mock_doc

        # Request with morning timestamp
        morning_baseline = self.baseline_manager.get_user_baseline(
            user_id, timestamp=datetime(2023, 10, 28, 8, 0, 0)
        )
        self.assertEqual(morning_baseline["f0_avg"]["mean"], 110.0)

        # Request with evening timestamp
        evening_baseline = self.baseline_manager.get_user_baseline(
            user_id, timestamp=datetime(2023, 10, 28, 20, 0, 0)
        )
        self.assertEqual(evening_baseline["f0_avg"]["mean"], 130.0)

        # Request with general timestamp
        general_baseline = self.baseline_manager.get_user_baseline(
            user_id, timestamp=datetime(2023, 10, 28, 14, 0, 0)
        )
        self.assertEqual(general_baseline["f0_avg"]["mean"], 120.0)

    def test_finetune_baseline_updates_partition(self):
        user_id = 123
        timestamp = datetime(2023, 10, 27, 8, 0, 0) # Morning

        # Setup mock initial retrieval (Cold Start -> Population Baseline)
        self.mock_collection_baseline.find_one.return_value = None

        # Setup indicator scores
        self.mock_collection_indicator_scores.find_one.return_value = {
            "user_id": user_id,
            "timestamp": timestamp,
            "indicator_scores": {"1_depressed_mood": 0.2}
        }

        # We finetune with actual score 1.0 (Active) vs 0.2 (Passive) -> Error = 0.8
        # f0_avg direction is negative.
        # adjustment = 0.8 * 10.0 * 0.2 * (-1) * 1.0 = -1.6
        # new mean = 120.0 - 1.6 = 118.4

        phq9_scores = {"1_depressed_mood": 1.0}

        self.baseline_manager.finetune_baseline(
            user_id, phq9_scores, 5, "Low", timestamp
        )

        # Verify replace_one was called
        args, kwargs = self.mock_collection_baseline.replace_one.call_args
        query, doc = args

        self.assertEqual(doc["schema_version"], 2)
        partitions = doc["context_partitions"]

        # Verify morning partition is updated
        self.assertIn("morning", partitions)
        self.assertAlmostEqual(partitions["morning"]["metrics"]["f0_avg"]["mean"], 118.4)

        # Verify evening partition exists but empty (or population baseline if copied? code creates empty)
        # Wait, the code:
        # partitions[context_key]["metrics"] = complete_baseline
        # complete_baseline is old_baseline + updates.
        # old_baseline comes from get_user_baseline.
        # If cold start, get_user_baseline returns population baseline.
        # So morning metrics will be population baseline + updates.

        self.assertIn("evening", partitions)
        self.assertEqual(partitions["evening"]["metrics"], {})

        # Verify general partition is updated
        self.assertIn("general", partitions)
        self.assertAlmostEqual(partitions["general"]["metrics"]["f0_avg"]["mean"], 118.4)

if __name__ == '__main__':
    unittest.main()
