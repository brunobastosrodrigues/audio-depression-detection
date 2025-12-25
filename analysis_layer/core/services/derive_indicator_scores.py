import pandas as pd
from typing import List
from core.models.AnalyzedMetricRecord import AnalyzedMetricRecord
from core.models.IndicatorScoreRecord import IndicatorScoreRecord
import json
import math
from collections import OrderedDict, defaultdict


def derive_indicator_scores(
    user_id: int,
    records: List[AnalyzedMetricRecord],
    repository,
    mapping_path: str = "core/mapping/config.json",
) -> List[IndicatorScoreRecord]:
    if not records:
        return []

    with open(mapping_path, "r") as f:
        mapping_config = json.load(f)

    records_by_date = defaultdict(list)
    for record in records:
        record_date = record.timestamp
        records_by_date[record_date].append(record)
    records_by_date = OrderedDict(
        sorted(records_by_date.items(), key=lambda item: item[0])
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

    # We iterate through the new records day by day
    for record_date, daily_records in records_by_date.items():
        analyzed_value = {r.metric_name: r.analyzed_value for r in daily_records}

        current_smoothed_scores = {}
        binary_scores = {}

        for indicator, details in mapping_config.items():
            # Calculate Instantaneous Score S_i(t)
            # S_i(t) = sum(W_{i,m})
            # Equation 3: Directional Transformation

            s_i_t = 0.0

            # If we don't have any metrics for this indicator in this update,
            # should we assume S_i(t) is 0? Or skip?
            # The prompt implies we process the "current time window".
            # If data is missing for a metric, we treat it as 0 contribution (baseline).

            for metric, props in details.get("metrics", {}).items():
                weight = props.get("weight", 0)
                if weight == 0:
                    continue

                direction = props.get("direction", "positive")
                z_hat = analyzed_value.get(metric, 0.0) # Default to 0 (baseline) if missing

                # Eq 3
                w_im = 0.0
                if direction == "positive":
                    w_im = z_hat # Already clipped
                elif direction == "negative":
                    w_im = -z_hat
                elif direction == "both" or direction == "anomaly":
                    w_im = abs(z_hat)

                # Note: The prompt description for Eq 3 says:
                # W_{i,m} is the weighted contribution...
                # Wait, the prompt says W_{i,m} = z_hat (if positive), etc.
                # But typically weighted sum implies multiplying by weight.
                # The prompt text says "Segments are sized by their weighted score".
                # It doesn't explicitly show W * z in Eq 3, but Eq 3 defines W_{i,m}.
                # The text "S_i(t): The instantaneous score ... (sum of all W_{i,m} contributions)"
                # implies S_i(t) = sum(W_{i,m}).
                # But where does the weight from config come in?
                # Usually Weighted Score = Sum(Weight * Score).
                # The config has "weight": 1.0.
                # Let's assume W_{i,m} includes the config weight multiplication.
                # Or W_{i,m} is the transformed value, and S_i(t) is the weighted sum.
                # Given the "Weighted contribution" wording, I will multiply by weight.

                s_i_t += w_im * weight

            # Equation 4: Temporal Persistence (EMA)
            # S_bar(t) = (1 - alpha) * S_i(t) + alpha * S_bar(t-1)
            alpha = details.get("smoothing_factor", 0.99)
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

        all_scores.append(
            IndicatorScoreRecord(
                user_id=user_id,
                timestamp=record_date,
                indicator_scores=current_smoothed_scores,
                mdd_signal=mdd_signal,
                binary_scores=binary_scores
            )
        )

    return all_scores
