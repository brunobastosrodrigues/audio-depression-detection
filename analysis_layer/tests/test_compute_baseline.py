"""Tests for per-user baseline computation from ingested raw metrics."""
from datetime import datetime
from unittest.mock import MagicMock

import numpy as np

from core.services.compute_baseline import compute_baseline_partitions
from core.baseline.BaselineManager import BaselineManager


def rec(metric, value, hour=14):
    return {"metric_name": metric, "metric_value": value, "timestamp": datetime(2026, 1, 1, hour, 0)}


def test_general_stats_over_all_records():
    recs = [rec("f0_avg", v, hour=14) for v in [10, 20, 30]]  # 14h -> general only
    p = compute_baseline_partitions(recs, min_samples=3)
    s = p["general"]["metrics"]["f0_avg"]
    assert s["count"] == 3
    assert s["mean"] == 20.0
    assert abs(s["std"] - float(np.std([10, 20, 30]))) < 1e-9
    assert p["morning"]["metrics"] == {}
    assert p["evening"]["metrics"] == {}


def test_circadian_partitioning():
    recs = [rec("f0_avg", v, hour=8) for v in [1, 2, 3]] + [rec("f0_avg", v, hour=20) for v in [100, 200, 300]]
    p = compute_baseline_partitions(recs, min_samples=3)
    assert p["morning"]["metrics"]["f0_avg"]["mean"] == 2.0
    assert p["evening"]["metrics"]["f0_avg"]["mean"] == 200.0
    assert p["general"]["metrics"]["f0_avg"]["count"] == 6  # all records


def test_min_samples_gate_excludes_sparse_metric():
    recs = [rec("f0_avg", v) for v in [1, 2]]  # 2 < 3
    p = compute_baseline_partitions(recs, min_samples=3)
    assert p["general"]["metrics"] == {}


def test_skips_nonfinite_and_nonnumeric():
    recs = [rec("f0_avg", v) for v in [1, 2, 3]] + [
        rec("f0_avg", float("nan")), rec("f0_avg", "abc"), rec("f0_avg", None)
    ]
    p = compute_baseline_partitions(recs, min_samples=3)
    assert p["general"]["metrics"]["f0_avg"]["count"] == 3


def test_string_timestamp_parsed_into_partition():
    recs = [{"metric_name": "f0_avg", "metric_value": v, "timestamp": "2026-01-01T08:00:00"} for v in [1, 2, 3]]
    p = compute_baseline_partitions(recs, min_samples=3)
    assert p["morning"]["metrics"]["f0_avg"]["count"] == 3


# --- compute_and_store_baseline (BaselineManager method) ---

def _bm():
    bm = BaselineManager.__new__(BaselineManager)
    bm.client = MagicMock()
    bm.population_baseline = {}
    return bm


def test_compute_and_store_writes_v2_doc():
    bm = _bm()
    raw = MagicMock()
    raw.find.return_value = [rec("f0_avg", v, hour=14) for v in range(10)]
    base_coll = MagicMock()
    bm._db = lambda system_mode=None: {"raw_metrics": raw}
    bm._baseline_collection = lambda system_mode=None: base_coll

    res = bm.compute_and_store_baseline(1, system_mode="live", min_samples=5)

    assert "f0_avg" in res["general"]["metrics"]
    assert base_coll.replace_one.called
    filt, doc = base_coll.replace_one.call_args[0][:2]
    assert filt == {"user_id": 1, "source": "computed_from_data"}
    assert doc["schema_version"] == 2
    assert doc["context_partitions"]["general"]["metrics"]["f0_avg"]["count"] == 10


def test_compute_and_store_insufficient_returns_none_and_no_write():
    bm = _bm()
    raw = MagicMock()
    raw.find.return_value = [rec("f0_avg", 1, hour=14)]  # 1 sample < min
    base_coll = MagicMock()
    bm._db = lambda system_mode=None: {"raw_metrics": raw}
    bm._baseline_collection = lambda system_mode=None: base_coll

    assert bm.compute_and_store_baseline(1, min_samples=5) is None
    assert not base_coll.replace_one.called
