import pandas as pd
from typing import List
from core.models.AnalyzedMetricRecord import AnalyzedMetricRecord
from core.models.ContextualMetricRecord import ContextualMetricRecord
from core.baseline.BaselineManager import BaselineManager
import math


def analyze_metrics(
    user_id: int,
    records: List[ContextualMetricRecord],
    baseline_manager: BaselineManager,
) -> List[AnalyzedMetricRecord]:
    if not records:
        return []

    df = pd.DataFrame(
        {
            "user_id": [r.user_id for r in records],
            "timestamp": [r.timestamp for r in records],
            "metric_name": [r.metric_name for r in records],
            "contextual_value": [r.contextual_value for r in records],
            "metric_dev": [r.metric_dev for r in records],
            "system_mode": [getattr(r, 'system_mode', None) or 'live' for r in records],
        }
    )

    z_scores = []
    for _, row in df.iterrows():
        metric = row["metric_name"]
        value = row["contextual_value"]
        record_timestamp = row["timestamp"]

        # Fetch baseline specific to this record's timestamp for context-aware retrieval
        user_baseline = baseline_manager.get_user_baseline(
            user_id, timestamp=record_timestamp
        )

        if metric in user_baseline:
            mean = user_baseline[metric]["mean"]
            std = user_baseline[metric]["std"]

            if std is not None and std > 0:
                z = (value - mean) / std
            else:
                z = None
        else:
            z = None

        # Equation 1: Feature Standardization
        # z = (x - mean) / max(std, epsilon)
        if metric in user_baseline:
            mean = user_baseline[metric]["mean"]
            std = user_baseline[metric]["std"]
            epsilon = 1e-6

            if std is not None:
                z = (value - mean) / max(std, epsilon)
            else:
                z = 0.0
        else:
            z = 0.0

        # Equation 2: Robustness via Clipping
        # z_hat = sign(z) * min(|z|, tau)
        # We need to fetch the clipping threshold from config if possible,
        # but analyze_metrics doesn't have access to config easily right now.
        # However, the requirement says "typically set to 3.0".
        # We'll use a default of 3.0 here or check if we can pass it.
        # Access config from baseline_manager if available to get user-specific thresholds
        clipping_threshold = 3.0 # Default

        if hasattr(baseline_manager, 'config_manager'):
            user_config = baseline_manager.config_manager.get_config(user_id)
            # Reverse lookup metric in config
            for indicator_data in user_config.values():
                if "metrics" in indicator_data and metric in indicator_data["metrics"]:
                     metric_config = indicator_data["metrics"][metric]
                     clipping_threshold = metric_config.get("clipping_threshold", 3.0)
                     break
        elif hasattr(baseline_manager, 'config'):
             # Fallback to default config stored in manager
            for indicator_data in baseline_manager.config.values():
                if "metrics" in indicator_data and metric in indicator_data["metrics"]:
                     metric_config = indicator_data["metrics"][metric]
                     clipping_threshold = metric_config.get("clipping_threshold", 3.0)
                     break

        if isinstance(z, (int, float)) and not (math.isnan(z) or math.isinf(z)):
             z_clipped = math.copysign(1, z) * min(abs(z), clipping_threshold)
             z_scores.append(z_clipped)
        else:
            z_scores.append(0.0)

    df["analyzed_value"] = z_scores

    return [
        AnalyzedMetricRecord(
            user_id=row["user_id"],
            timestamp=row["timestamp"],
            metric_name=row["metric_name"],
            analyzed_value=row["analyzed_value"],
            system_mode=row["system_mode"],
        )
        for _, row in df.iterrows()
    ]
