from typing import List
import math

from core.models.AnalyzedMetricRecord import AnalyzedMetricRecord
from core.models.ContextualMetricRecord import ContextualMetricRecord
from core.baseline.BaselineManager import BaselineManager


def _clipping_threshold_for(baseline_manager, user_id, metric) -> float:
    """Look up the per-metric clipping threshold (Eq. 2), defaulting to 3.0."""
    default = 3.0
    config = None
    if hasattr(baseline_manager, "config_manager"):
        config = baseline_manager.config_manager.get_config(user_id)
    elif hasattr(baseline_manager, "config"):
        config = baseline_manager.config
    if not config:
        return default
    for indicator_data in config.values():
        metrics = indicator_data.get("metrics", {}) if isinstance(indicator_data, dict) else {}
        if metric in metrics:
            return metrics[metric].get("clipping_threshold", default)
    return default


def analyze_metrics(
    user_id: int,
    records: List[ContextualMetricRecord],
    baseline_manager: BaselineManager,
) -> List[AnalyzedMetricRecord]:
    """Standardize contextual metrics into clipped z-scores against the user baseline.

    Eq. 1 (standardization): z = (x - mean) / std
    Eq. 2 (robustness):      z_hat = sign(z) * min(|z|, tau)

    A metric is *excluded* from the output when it cannot be standardized -- no
    baseline entry, or a baseline std that is None or <= 0 -- rather than being
    emitted as 0.0. Emitting 0.0 would be read downstream as "exactly at baseline"
    (a real, neutral measurement); excluding it instead lets the scorer and the
    confidence layer treat the metric as genuinely unavailable.
    """
    if not records:
        return []

    results: List[AnalyzedMetricRecord] = []
    for record in records:
        metric = record.metric_name
        value = record.contextual_value
        system_mode = getattr(record, "system_mode", None) or "live"

        user_baseline = baseline_manager.get_user_baseline(
            user_id, timestamp=record.timestamp, system_mode=system_mode
        )

        stats = user_baseline.get(metric) if user_baseline else None
        if not stats:
            continue  # no baseline -> cannot standardize -> exclude

        mean = stats.get("mean")
        std = stats.get("std")
        if mean is None or std is None or std <= 0 or value is None:
            continue  # undefined standardization -> exclude

        z = (value - mean) / std
        if math.isnan(z) or math.isinf(z):
            continue  # non-finite -> exclude

        tau = _clipping_threshold_for(baseline_manager, user_id, metric)
        z_clipped = math.copysign(1, z) * min(abs(z), tau)

        results.append(
            AnalyzedMetricRecord(
                user_id=record.user_id,
                timestamp=record.timestamp,
                metric_name=metric,
                analyzed_value=z_clipped,
                system_mode=system_mode,
            )
        )

    return results
