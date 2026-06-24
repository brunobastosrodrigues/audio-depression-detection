"""Tests for voiced/unvoiced/silence classification.

The old classifier marked a frame "voiced" whenever `librosa.piptrack` returned any
nonzero pitch peak, which is true for almost any frame with spectral energy -- so
broadband noise was labelled voiced and the "unvoiced" state was essentially never
reached, corrupting voiced_ratio / unvoiced_ratio / silence_ratio (DSM-5 psychomotor
markers). A correct classifier must separate a periodic tone (voiced) from noise
(unvoiced) from silence.
"""
import numpy as np

from core.extractors.voicing_states import get_interaction_dynamics

SR = 16000
DUR = 1.0


def _tone(freq=150.0, amp=0.5):
    t = np.linspace(0, DUR, int(SR * DUR), endpoint=False)
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _noise(amp=0.3, seed=0):
    rng = np.random.RandomState(seed)
    return (amp * rng.standard_normal(int(SR * DUR))).astype(np.float32)


def _silence():
    return np.zeros(int(SR * DUR), dtype=np.float32)


def test_tone_is_predominantly_voiced():
    d = get_interaction_dynamics(_tone(), SR)
    assert d["voiced_ratio"] > 0.7
    assert d["silence_ratio"] < 0.2


def test_noise_is_not_classified_as_voiced():
    # The headline regression: energetic broadband noise must NOT be "voiced".
    d = get_interaction_dynamics(_noise(), SR)
    assert d["voiced_ratio"] < 0.3
    assert d["unvoiced_ratio"] > 0.5


def test_silence_is_predominantly_silence():
    d = get_interaction_dynamics(_silence(), SR)
    assert d["silence_ratio"] > 0.8
    assert d["voiced_ratio"] < 0.1
