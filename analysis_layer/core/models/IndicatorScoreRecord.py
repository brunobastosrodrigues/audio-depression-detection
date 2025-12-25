from dataclasses import dataclass
from datetime import datetime
from typing import Dict
import pandas as pd


@dataclass
class IndicatorScoreRecord:
    user_id: int
    timestamp: datetime
    indicator_scores: Dict[str, float]
    mdd_signal: bool = False
    binary_scores: Dict[str, int] = None

    def to_dict(self):
        ts = self.timestamp

        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        elif isinstance(ts, pd.Timestamp):
            ts = ts.to_pydatetime()

        if ts is not None:
            ts = ts.replace(tzinfo=None)

        return {
            "user_id": self.user_id,
            "timestamp": ts,
            "indicator_scores": self.indicator_scores,
            "mdd_signal": self.mdd_signal,
            "binary_scores": self.binary_scores or {}
        }
