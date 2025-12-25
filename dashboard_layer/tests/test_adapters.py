import unittest
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path to import utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.SankeyAdapter import SankeyAdapter
from utils.WaterfallAdapter import WaterfallAdapter

# Mock config
MOCK_CONFIG_PATH = "dashboard_layer/tests/mock_config.json"
MOCK_CONFIG_CONTENT = {
    "1_depressed_mood": {
        "metrics": {
            "jitter": {"weight": 1.0, "direction": "positive"},
            "shimmer": {"weight": 0.5, "direction": "positive"}
        },
        "severity_threshold": 0.5
    },
    "2_loss_of_interest": {
        "metrics": {
            "f0_std": {"weight": 1.0, "direction": "negative"}
        },
        "severity_threshold": 0.5
    }
}

class TestAdapters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json
        with open(MOCK_CONFIG_PATH, 'w') as f:
            json.dump(MOCK_CONFIG_CONTENT, f)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(MOCK_CONFIG_PATH):
            os.remove(MOCK_CONFIG_PATH)

    def test_sankey_adapter(self):
        adapter = SankeyAdapter(MOCK_CONFIG_PATH)

        # Create mock data spanning 2 weeks
        # Week 1: Healthy (scores 0.1)
        # Week 2: Depressed Mood (scores 0.8)

        d1 = datetime(2023, 1, 2)
        d2 = datetime(2023, 1, 9)

        records = [
            # Week 1 data
            {
                "timestamp": d1,
                "user_id": "u1",
                "mdd_signal": False,
                "indicator_scores": {"1_depressed_mood": 0.1, "2_loss_of_interest": 0.0}
            },
            {
                "timestamp": d1 + timedelta(days=1),
                "user_id": "u1",
                "mdd_signal": False,
                "indicator_scores": {"1_depressed_mood": 0.1, "2_loss_of_interest": 0.0}
            },
            # Week 2 data (Make sure all records are high)
            {
                "timestamp": d2, # Jan 9
                "user_id": "u1",
                "mdd_signal": False,
                "indicator_scores": {"1_depressed_mood": 0.8, "2_loss_of_interest": 0.2}
            },
            {
                "timestamp": d2 - timedelta(days=1), # Jan 8 (part of week ending Jan 9)
                "user_id": "u1",
                "mdd_signal": False,
                "indicator_scores": {"1_depressed_mood": 0.9, "2_loss_of_interest": 0.2}
            }
        ]

        df = pd.DataFrame(records)

        result = adapter.process(df)

        self.assertIsNotNone(result)

        print("Sankey Labels:", result['node']['label'])

        self.assertEqual(len(result['node']['label']), 2)

        labels = result['node']['label']
        self.assertTrue("Week 1" in labels[0])
        self.assertTrue("Week 2" in labels[1])

        self.assertTrue("Depressed Mood" in labels[1])

        # Check link
        self.assertEqual(len(result['link']['source']), 1)
        self.assertEqual(result['link']['source'][0], 0)
        self.assertEqual(result['link']['target'][0], 1)

    def test_waterfall_adapter(self):
        adapter = WaterfallAdapter(MOCK_CONFIG_PATH)

        # Mock metrics
        metrics = [
            type('obj', (object,), {'metric_name': 'jitter', 'analyzed_value': 0.5}),
            type('obj', (object,), {'metric_name': 'shimmer', 'analyzed_value': 0.2}),
            type('obj', (object,), {'metric_name': 'unused', 'analyzed_value': 1.0})
        ]

        # Test 1_depressed_mood
        # Jitter: 0.5 * 1.0 = 0.5
        # Shimmer: 0.2 * 0.5 = 0.1
        # Total: 0.6

        result = adapter.process("1_depressed_mood", metrics)

        self.assertIsNotNone(result)
        self.assertEqual(result['x'], ['jitter', 'shimmer', 'Total Impact'])
        self.assertEqual(result['y'], [0.5, 0.1, 0.6])

if __name__ == '__main__':
    unittest.main()
