import pandas as pd
from typing import List, Dict
from core.models.AnalyzedMetricRecord import AnalyzedMetricRecord
from core.models.IndicatorScoreRecord import IndicatorScoreRecord
import json
import math
from collections import OrderedDict, defaultdict

from core.mapping.ConfigManager import ConfigManager
from core.services.explanation_generator import generate_all_explanations

def derive_indicator_scores(
    user_id: int,
    records: List[AnalyzedMetricRecord],
    repository,
    mapping_path: str = "core/mapping/config.json", # kept for backward compatibility if any
    config_manager: ConfigManager = None
) -> List[IndicatorScoreRecord]:
    if not records:
        return []

    # Write the score records with the user_id type stored in the data (from the analyzed
    # records) rather than the REST string param, keeping indicator_scores consistent with
    # raw/aggregated/contextual/analyzed instead of relying on downstream type coercion.
    resolved_user_id = getattr(records[0], "user_id", user_id)

    if config_manager:
        mapping_config = config_manager.get_config(user_id)
    else:
        # Fallback to loading from file if no manager provided
        # Or instantiate one? Instantiating one is safer.
        try:
             cm = ConfigManager()
             mapping_config = cm.get_config(user_id)
        except Exception:
             with open(mapping_path, "r") as f:
                mapping_config = json.load(f)

    # Group records by (date, system_mode) to keep data isolated
    records_by_date_mode = defaultdict(list)
    for record in records:
        record_date = record.timestamp
        system_mode = getattr(record, 'system_mode', None) or 'live'
        records_by_date_mode[(record_date, system_mode)].append(record)
    records_by_date_mode = OrderedDict(
        sorted(records_by_date_mode.items(), key=lambda item: item[0])
    )

    all_scores = []

    # Get the latest previous smoothed scores from repository for EMA initialization
    # Eq 4: S_bar(t) = (1-alpha)*S(t) + alpha*S_bar(t-1)
    latest_score_doc = repository.get_latest_indicator_score(user_id)

    # Initialize previous_smoothed_scores
    if latest_score_doc:
        # Assuming the repository stores the latest *smoothed* scores in "indicator_scores"
        previous_smoothed_scores = latest_score_doc.get("indicator_scores", {})
    else:
        # Default 0.0 for initial state if no history
        previous_smoothed_scores = {indicator: 0.0 for indicator in mapping_config.keys()}

    # Ensure all indicators exist in previous_smoothed_scores
    for indicator in mapping_config.keys():
        if indicator not in previous_smoothed_scores or previous_smoothed_scores[indicator] is None:
            previous_smoothed_scores[indicator] = 0.0

    # Determine if user is in "Learning Mode" (7-14 days)
    # We need to know when the user started.
    # We can try to get the first record date from repository.
    # If not available, we assume this is the first day or we can't determine.
    # If the user has history, we check the duration.

    first_record_date = None
    if hasattr(repository, 'get_first_indicator_score_date'):
        first_record_date = repository.get_first_indicator_score_date(user_id)

    # If no history, this batch might contain the first day.
    if not first_record_date and records:
        # Assuming sorted by date, use the first one.
        # Note: records_by_date_mode is ordered.
        first_record_date = list(records_by_date_mode.keys())[0][0]

    # Calculate default alpha for 14-day EMA
    # Alpha (smoothing) = 2 / (N + 1)
    # Alpha (persistence) = 1 - Alpha (smoothing)
    EMA_WINDOW_DAYS = 14
    DEFAULT_ALPHA = 1.0 - (2.0 / (EMA_WINDOW_DAYS + 1.0))

    # We iterate through the new records day by day, grouped by system_mode
    for (record_date, system_mode), daily_records in records_by_date_mode.items():
        # Check if in learning period
        learning_period_days = 14
        in_learning_mode = False
        if first_record_date:
            # handle both datetime and string dates if necessary, usually strings in ISO
            # assuming record_date is compatible type with first_record_date or converted
            from datetime import datetime

            # Simple helper to parse if string
            def to_dt(d):
                if isinstance(d, str):
                    try:
                        return datetime.fromisoformat(d)
                    except ValueError:
                         return None
                return d

            d_current = to_dt(record_date)
            d_start = to_dt(first_record_date)

            if d_current and d_start:
                delta = d_current - d_start
                if delta.days < learning_period_days:
                    in_learning_mode = True
        else:
            # If we can't determine start date, and we are processing data,
            # safe to assume we might be in learning mode if this is the very first batch?
            # Or assume NOT in learning mode to avoid blocking indefinitely?
            # Given the requirement "Do not attempt detection on Day 1", let's err on side of caution?
            # But if first_record_date is None, it means no history. So this IS Day 1.
            in_learning_mode = True


        analyzed_value = {r.metric_name: r.analyzed_value for r in daily_records}

        current_smoothed_scores = {}
        binary_scores = {}

        for indicator, details in mapping_config.items():
            # Calculate Instantaneous Score S_i(t)
            # S_i(t) = sum(W_{i,m})
            # Equation 3: Directional Transformation

            # S_i(t) is the weighted *average* of the directional clipped z-scores
            # (Eq. 3) of the metrics that are actually available this window. Using a
            # weighted average (normalized by the summed weight of available metrics)
            # instead of a raw sum keeps S_i(t) bounded to roughly [-tau, tau], so the
            # severity_threshold (a small 0-1-scale value, e.g. 0.5) is comparable
            # across indicators regardless of how many metrics they have. Missing or
            # non-finite metrics are excluded from both numerator and denominator
            # rather than diluting the score toward baseline.
            weighted_sum = 0.0
            weight_total = 0.0

            for metric, props in details.get("metrics", {}).items():
                weight = props.get("weight", 0)
                if weight == 0:
                    continue

                if metric not in analyzed_value:
                    continue  # metric not measured this window -> unavailable

                z_hat = analyzed_value[metric]
                if z_hat is None or (
                    isinstance(z_hat, float) and (math.isnan(z_hat) or math.isinf(z_hat))
                ):
                    continue  # undefined standardization -> unavailable

                direction = props.get("direction", "positive")

                # Eq 3: directional transformation
                if direction == "negative":
                    w_im = -z_hat
                elif direction == "both" or direction == "anomaly":
                    w_im = abs(z_hat)
                else:  # "positive" (default)
                    w_im = z_hat

                weighted_sum += w_im * weight
                weight_total += weight

            s_i_t = weighted_sum / weight_total if weight_total > 0 else 0.0

            # Equation 4: Temporal Persistence (EMA)
            # S_bar(t) = (1 - alpha) * S_i(t) + alpha * S_bar(t-1)
            alpha = details.get("smoothing_factor", DEFAULT_ALPHA)
            s_bar_prev = previous_smoothed_scores.get(indicator, 0.0)

            s_bar_t = (1 - alpha) * s_i_t + alpha * s_bar_prev
            current_smoothed_scores[indicator] = s_bar_t

            # Equation 5: Indicator Binarization
            # B_i(t) = 1 if S_bar(t) >= theta_i else 0
            theta = details.get("severity_threshold", 0.5)
            binary_scores[indicator] = 1 if s_bar_t >= theta else 0

        # Update previous for next iteration
        previous_smoothed_scores = current_smoothed_scores.copy()

        # Equation 6: Diagnostic Logic
        # MDD_Signal = (Sum(B_j) >= 5) AND (B_1 = 1 OR B_2 = 1)
        # Note: Indicators in config are keys like "1_depressed_mood", "2_loss_of_interest".
        # We need to robustly identify "1" and "2".

        active_count = sum(binary_scores.values())

        # Find B1 and B2 status
        # We rely on the keys starting with "1_" and "2_" or exact matching known keys.
        # The config keys provided earlier are: "1_depressed_mood", "2_loss_of_interest".
        b1 = 0
        b2 = 0
        for key, val in binary_scores.items():
            if key.startswith("1_"):
                b1 = val
            elif key.startswith("2_"):
                b2 = val

        mdd_signal = (active_count >= 5) and (b1 == 1 or b2 == 1)

        # In Learning Mode, we do not signal MDD.
        if in_learning_mode:
            mdd_signal = False
            # Also suppress individual binary indicators to avoid "7/9 active" scares during calibration
            binary_scores = {k: 0 for k in binary_scores}

        # Generate XAI explanations for each indicator
        explanations = generate_all_explanations(
            mapping_config=mapping_config,
            analyzed_values=analyzed_value,
            indicator_scores=current_smoothed_scores,
        )

        all_scores.append(
            IndicatorScoreRecord(
                user_id=resolved_user_id,
                timestamp=record_date,
                indicator_scores=current_smoothed_scores,
                mdd_signal=mdd_signal,
                binary_scores=binary_scores,
                system_mode=system_mode,
                explanations=explanations,
            )
        )

    return all_scores
