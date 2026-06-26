from ports.PersistencePort import PersistencePort
from core.services.temporal_context.SpikeDampenedEMA import SpikeDampenedEMA
from core.services.temporal_context.HMM import HMM
import pandas as pd
from datetime import timedelta, datetime
from typing import List
from core.models.ContextualMetricRecord import ContextualMetricRecord


class ComputeContextualMetricsUseCase:
    def __init__(self, repository: PersistencePort):
        self.repository = repository

    def compute(
        self, user_id: str, method: str = "ema"
    ) -> List[ContextualMetricRecord]:

        latest = self.repository.get_latest_contextual_metric_date(user_id)
        start_date = None
        if latest:
            if isinstance(latest, str):
                latest = datetime.fromisoformat(latest)
            start_date = pd.Timestamp(latest)
            # Normalize to naive UTC so the watermark can't mix tz-aware/naive datetimes.
            if start_date.tzinfo is not None:
                start_date = start_date.tz_convert("UTC").tz_localize(None)
            start_date = start_date + pd.Timedelta(days=1)

        # NOTE: the full aggregated history is read intentionally -- the EMA is stateful and
        # needs all prior values for correct smoothing continuity. Reading only the window
        # past start_date would cold-restart the EMA and change results; the right perf fix
        # is to persist the EMA state, not to window the read.
        metrics = self.repository.get_aggregated_metrics(user_id)
        if not metrics:
            return []

        df = pd.DataFrame(metrics)
        # Uniform naive-UTC timestamps (to_dict stores naive; fresh ingestion may be aware).
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_localize(None)

        # Use the user_id type as stored in the data (int for dataset users, strings for
        # live/demo) rather than the REST string param, so contextual_metrics stay
        # type-consistent with raw/aggregated. Otherwise the output is written as a string
        # while raw/aggregated are ints, and the chain only survives because downstream
        # queries coerce types.
        resolved_user_id = df["user_id"].iloc[0] if "user_id" in df.columns and len(df) else user_id
        # pandas yields numpy scalar types (e.g. numpy.int64) that pymongo cannot encode;
        # coerce to a native Python value. String user_ids come back as plain str already.
        if hasattr(resolved_user_id, "item"):
            resolved_user_id = resolved_user_id.item()

        # Handle system_mode - if not present, default to 'live'
        if "system_mode" not in df.columns:
            df["system_mode"] = "live"

        model = SpikeDampenedEMA() if method == "ema" else HMM()

        contextual_records = []

        # Process each system_mode separately to keep data isolated
        for system_mode in df["system_mode"].unique():
            mode_df = df[df["system_mode"] == system_mode]

            daily = mode_df.pivot_table(
                index="timestamp",
                columns="metric_name",
                values="aggregated_value",
                aggfunc="mean",
            )

            for metric in daily.columns:
                # Use only ACTUAL observations. The previous ffill().bfill() invented values
                # across day gaps, which the EMA/HMM then treated as real data, biasing the
                # baseline during absence periods.
                values = daily[metric].dropna()
                if values.empty:
                    continue
                baseline = model.compute(values.tolist())
                dev = abs(values - baseline)

                for timestamp, dev_val, base_val in zip(values.index, dev, baseline):
                    if start_date is None or timestamp >= start_date:
                        contextual_records.append(
                            ContextualMetricRecord(
                                user_id=resolved_user_id,
                                timestamp=timestamp,
                                metric_name=metric,
                                contextual_value=float(base_val),
                                metric_dev=float(dev_val),
                                system_mode=system_mode,
                            )
                        )

        self.repository.save_contextual_metrics(contextual_records)

        return contextual_records
