import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.gap_filler import select_tasks


def _tasks(*keys):
    return [(k, (lambda: None), ()) for k in keys]


def _keys(tasks):
    return [k for k, _, _ in tasks]


def test_no_provided_runs_all():
    kept, results = select_tasks(_tasks("snr", "jitter", "pitch"), {})
    assert _keys(kept) == ["snr", "jitter", "pitch"]
    assert results == {}


def test_skips_provided_single_output():
    kept, results = select_tasks(
        _tasks("snr", "spectral_flatness", "pitch"),
        {"snr": 9.5, "spectral_flatness": 0.3},
    )
    assert _keys(kept) == ["pitch"]                 # only the non-provided extractor remains
    assert results == {"snr": 9.5, "spectral_flatness": 0.3}  # node values seeded


def test_non_skippable_task_never_skipped():
    # pitch is multi-output / not edge-offloadable -> stays even if "pitch" is "provided"
    kept, results = select_tasks(_tasks("pitch"), {"pitch": 123})
    assert _keys(kept) == ["pitch"]
    assert results == {}


def test_unrelated_provided_keeps_task():
    kept, results = select_tasks(_tasks("snr"), {"f0_avg": 200})
    assert _keys(kept) == ["snr"]
    assert results == {}
