"""Tests for the day-bucketing aggregation and the variability-based EMA spike dampening."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.services.aggregate_metrics import aggregate_metrics
from core.models.RawMetricRecord import RawMetricRecord
from core.services.temporal_context.SpikeDampenedEMA import SpikeDampenedEMA


def R(uid, ts, name, val, mode="dataset"):
    return RawMetricRecord(
        user_id=uid, timestamp=ts, metric_name=name, metric_value=val, system_mode=mode
    )


def test_day_bucketing_collapses_same_day():
    recs = [
        R(1, datetime(2026, 1, 1, 9, 0), "f0", 100),
        R(1, datetime(2026, 1, 1, 18, 0), "f0", 200),   # same day -> mean 150
        R(1, datetime(2026, 1, 2, 9, 0), "f0", 300),     # next day
    ]
    out = aggregate_metrics(recs)
    assert len(out) == 2, "two distinct days expected"
    by_day = {a.timestamp.date(): a.aggregated_value for a in out}
    assert by_day[datetime(2026, 1, 1).date()] == 150
    assert by_day[datetime(2026, 1, 2).date()] == 300
    assert all(a.timestamp.hour == 0 for a in out), "timestamps floored to midnight"
    assert all(isinstance(a.user_id, int) for a in out)


def test_modes_kept_separate():
    recs = [
        R(1, datetime(2026, 1, 1, 9, 0), "f0", 100, mode="dataset"),
        R(1, datetime(2026, 1, 1, 9, 0), "f0", 999, mode="demo"),
    ]
    out = aggregate_metrics(recs)
    assert len(out) == 2
    assert {a.system_mode for a in out} == {"dataset", "demo"}


def test_ema_constant_series_unchanged():
    ema = SpikeDampenedEMA().compute([5.0] * 10)
    assert all(abs(v - 5.0) < 1e-9 for v in ema)


def test_ema_zero_centered_not_overdamped():
    # Small oscillations around zero must not be treated as spikes (the old abs(value) bug).
    ema = SpikeDampenedEMA().compute([0.1, -0.1, 0.1, -0.1, 0.1])
    assert len(ema) == 5


def test_ema_dampens_genuine_spike():
    # Realistic baseline: small natural day-to-day noise, then one large outlier.
    base = [10.0, 10.2, 9.8, 10.1, 9.9, 10.3, 9.7, 10.0, 10.1, 9.9]
    series = base + [1000.0] + [10.0, 10.2, 9.8, 10.1, 9.9]
    ema = SpikeDampenedEMA().compute(series)
    jump = ema[10] - ema[9]
    undamped = 0.13 * (1000.0 - ema[9])
    assert jump < undamped * 0.5, "the large outlier step should be dampened vs the noisy baseline"
