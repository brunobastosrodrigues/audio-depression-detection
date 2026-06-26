import pandas as pd
from typing import List
from core.models.RawMetricRecord import RawMetricRecord
from core.models.AggregatedMetricRecord import AggregatedMetricRecord


def aggregate_metrics(records: List[RawMetricRecord]) -> List[AggregatedMetricRecord]:
    if not records:
        return []

    df = pd.DataFrame(
        {
            "user_id": [r.user_id for r in records],
            "timestamp": [r.timestamp for r in records],
            "metric_name": [r.metric_name for r in records],
            "metric_value": [r.metric_value for r in records],
            "system_mode": [r.system_mode for r in records],
        }
    )

    df["metric_value"] = pd.to_numeric(df["metric_value"], errors="coerce")
    df = df.dropna(subset=["metric_value"])

    # Aggregate per DAY: floor the timestamp to the day so multiple utterances on the same
    # day collapse into one daily mean. Previously the groupby keyed on the full
    # (microsecond) timestamp, so every record formed its own group and the "daily mean"
    # was a no-op (output 1:1 with input).
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.floor("D")

    grouped = (
        df.groupby(["user_id", "timestamp", "metric_name", "system_mode"])["metric_value"]
        .mean()
        .reset_index()
    )

    return [
        AggregatedMetricRecord(
            user_id=row["user_id"],
            timestamp=row["timestamp"].to_pydatetime(),
            metric_name=row["metric_name"],
            aggregated_value=float(row["metric_value"]),
            system_mode=row["system_mode"],
        )
        for _, row in grouped.iterrows()
    ]
