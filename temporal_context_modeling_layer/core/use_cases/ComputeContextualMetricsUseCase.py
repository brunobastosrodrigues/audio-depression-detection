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
            start_date = latest + timedelta(days=1)

        metrics = self.repository.get_aggregated_metrics(user_id)
        if not metrics:
            return []

        df = pd.DataFrame(metrics)

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
                values = daily[metric].ffill().bfill()
                baseline = model.compute(values.tolist())
                dev = abs(values - baseline)

                for timestamp, dev_val, base_val in zip(values.index, dev, baseline):
                    if start_date is None or timestamp >= start_date:
                        contextual_records.append(
                            ContextualMetricRecord(
                                user_id=user_id,
                                timestamp=timestamp,
                                metric_name=metric,
                                contextual_value=float(base_val),
                                metric_dev=float(dev_val),
                                system_mode=system_mode,
                            )
                        )

        self.repository.save_contextual_metrics(contextual_records)

        return contextual_records
