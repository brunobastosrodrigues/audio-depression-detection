"""Regression test for the F0 extractor's opensmile column name.

eGeMAPSv02's F0 LLD column is `F0semitoneFrom27.5Hz_sma3nz`. The code previously
read a non-existent `F0semitone_sma3nz`, raising KeyError that the service swallowed
-> F0 (the central depression marker) was silently 0.0 in production.

Audio is near-silence so the librosa pyin branch contributes nothing and the test
isolates the OpenSMILE-column path.
"""
import numpy as np
import pandas as pd

from core.extractors.f0 import get_f0_dynamic, semitone_to_hz


def test_f0_reads_real_opensmile_column():
    semitones = [33.0, 36.0, 39.0]  # ~185, 220, 262 Hz
    lld = pd.DataFrame({"F0semitoneFrom27.5Hz_sma3nz": pd.Series(semitones, dtype=float)})
    audio = np.zeros(int(0.3 * 16000), dtype=np.float32)  # silence -> pyin empty

    out = get_f0_dynamic(lld, audio, 16000)

    expected_mean = float(np.mean([semitone_to_hz(s) for s in semitones]))
    assert out["f0_avg"] > 100.0
    assert abs(out["f0_avg"] - expected_mean) < 1e-6
