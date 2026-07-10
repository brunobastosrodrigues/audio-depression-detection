"""
Server-side speech gate — hardened three-layer filter.

Layer 1 — webrtcvad (aggressiveness=3, env: VAD_GATE_AGGRESSIVENESS):
    Primary voiced-speech detector.  Drops segments whose fraction of 30 ms
    frames classified as speech is below VAD_GATE_MIN_SPEECH (default 0.30).

Layer 2 — spectral flatness guard (env: VAD_MAX_FLATNESS, default 0.50):
    Wiener entropy in [0,1]: 1 = white noise, 0 = pure tone.
    Broadband noise (white noise) has flatness ~0.56; voiced speech ~0.001-0.05.
    Drops segments whose mean flatness exceeds the threshold.
    Catches noise types that fool webrtcvad (e.g. white-noise floods).

Layer 3 — speech-band energy ratio (env: VAD_MIN_BAND_RATIO, default 0.10):
    Fraction of total FFT power in 80–3 500 Hz (the voiced-speech band).
    Real speech concentrates ≥85 % of its energy in this band.
    Drops segments whose ratio is below the threshold (sub-vocal noise).

A segment PASSES only if ALL three layers permit it (AND logic).

Calibration context (2026-07-10, n=55 live segments):
  · XVF miscalibrated-node noise is TONAL (flatness 0.002–0.024), not broadband.
  · Layer 1 aggressiveness 2→3: catches 4 additional borderline leakers.
  · Layer 2 at default 0.5: catches white-noise-style floods; tonal XVF noise
    is below 0.024 and is handled by the speaker-recognition step downstream.
  · Combined pipeline (VAD gate + speaker recognition): >99 % rejection.

Design principles
-----------------
* Fail-open: any exception → (True, None) so a gate bug never silences speech.
* Resamples to 16 kHz (webrtcvad requirement); accepts any source rate.
* Mono only; takes channel-mean for stereo input.
* All thresholds are env-tunable without container rebuild.
"""

import io
import math
import os

import numpy as np
import soundfile as sf

# ── defaults ────────────────────────────────────────────────────────────────
_MIN_SPEECH_DEFAULT   = 0.30
_AGGRESSIVENESS_DEFAULT = 3
_MAX_FLATNESS_DEFAULT = 0.50   # drop if flatness > this (1.0 = white noise)
_MIN_BAND_RATIO_DEFAULT = 0.10 # drop if speech-band energy fraction < this
_FRAME_MS  = 30                # webrtcvad supports 10/20/30 ms
_TARGET_SR = 16_000            # webrtcvad supports 8/16/32/48 kHz

# ── webrtcvad init ──────────────────────────────────────────────────────────
try:
    import webrtcvad as _webrtcvad
    _AGGRESSIVENESS = int(os.getenv("VAD_GATE_AGGRESSIVENESS",
                                    str(_AGGRESSIVENESS_DEFAULT)))
    _VAD = _webrtcvad.Vad(_AGGRESSIVENESS)
    _WEBRTCVAD_OK = True
    print(f"VAD_GATE init: webrtcvad loaded, aggressiveness={_AGGRESSIVENESS}")
except Exception as _e:
    _WEBRTCVAD_OK = False
    print(f"VAD_GATE init: webrtcvad unavailable ({_e}), gate disabled (fail-open)")


# ── helpers ─────────────────────────────────────────────────────────────────
def _resample_to_16k(audio: np.ndarray, sr: int) -> np.ndarray:
    """Integer-ratio resample; handles common rates exactly."""
    if sr == _TARGET_SR:
        return audio
    from scipy.signal import resample_poly
    g = math.gcd(sr, _TARGET_SR)
    return resample_poly(audio, _TARGET_SR // g, sr // g).astype(np.float32)


def _spectral_flatness(audio_np: np.ndarray) -> float:
    """
    Mean Wiener entropy over librosa frames.
    Returns a value in [0, 1]: near-0 = tonal, near-1 = white noise.
    """
    import librosa
    return float(np.mean(librosa.feature.spectral_flatness(y=audio_np)[0]))


def _band_energy_ratio(audio_np: np.ndarray,
                       sr: int = _TARGET_SR,
                       low: int = 80,
                       high: int = 3500) -> float:
    """
    Fraction of total FFT power in [low, high] Hz (the voiced-speech band).
    Returns 0.0 on silence.
    """
    freqs = np.fft.rfftfreq(len(audio_np), 1.0 / sr)
    power = np.abs(np.fft.rfft(audio_np)) ** 2
    total = float(np.sum(power))
    if total == 0.0:
        return 0.0
    mask = (freqs >= low) & (freqs <= high)
    return float(np.sum(power[mask]) / total)


# ── public API ───────────────────────────────────────────────────────────────
def check(audio_bytes: bytes, board_id=None) -> tuple:
    """
    Gate check for a single audio segment.

    Returns (should_pass: bool, speech_frac: float | None).
      should_pass=True  → let the segment through (speech or gate error)
      should_pass=False → drop (noise)

    Log format:
      VAD_GATE board=<id> speech_frac=X.XX flatness=Y.YYYY \
               band_ratio=Z.ZZZ verdict=pass
      VAD_GATE board=<id> speech_frac=X.XX flatness=Y.YYYY \
               band_ratio=Z.ZZZ verdict=drop:<reason>
      GATE_ERROR board=<id> exc=<message>

    Drop reasons:
      vad           — webrtcvad speech_frac below threshold
      flatness      — mean spectral flatness above VAD_MAX_FLATNESS
      band_ratio    — speech-band energy fraction below VAD_MIN_BAND_RATIO
      empty         — audio contained no complete 30 ms frames
    """
    min_speech = float(os.getenv("VAD_GATE_MIN_SPEECH",   str(_MIN_SPEECH_DEFAULT)))
    max_flat   = float(os.getenv("VAD_MAX_FLATNESS",       str(_MAX_FLATNESS_DEFAULT)))
    min_band   = float(os.getenv("VAD_MIN_BAND_RATIO",     str(_MIN_BAND_RATIO_DEFAULT)))

    if not _WEBRTCVAD_OK:
        print(f"VAD_GATE board={board_id} speech_frac=N/A flatness=N/A "
              f"band_ratio=N/A verdict=pass (webrtcvad unavailable)")
        return True, None

    try:
        # ── decode ───────────────────────────────────────────────────────
        audio_np, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")

        if audio_np.ndim > 1:
            audio_np = audio_np.mean(axis=1)

        audio_np = _resample_to_16k(audio_np, sr)

        # ── Layer 1: webrtcvad ────────────────────────────────────────────
        audio_int16 = (np.clip(audio_np, -1.0, 1.0) * 32767).astype(np.int16)
        pcm_bytes   = audio_int16.tobytes()

        frame_samples = int(_TARGET_SR * _FRAME_MS / 1000)  # 480 @ 16kHz/30ms
        frame_bytes   = frame_samples * 2                    # 2 bytes per int16

        total_frames = speech_frames = 0
        for offset in range(0, len(pcm_bytes) - frame_bytes + 1, frame_bytes):
            frame = pcm_bytes[offset:offset + frame_bytes]
            total_frames += 1
            if _VAD.is_speech(frame, _TARGET_SR):
                speech_frames += 1

        if total_frames == 0:
            print(f"VAD_GATE board={board_id} speech_frac=0.00 flatness=N/A "
                  f"band_ratio=N/A verdict=drop:empty")
            return False, 0.0

        speech_frac = speech_frames / total_frames

        # ── Layer 2: spectral flatness ────────────────────────────────────
        flatness = _spectral_flatness(audio_np)

        # ── Layer 3: speech-band energy ratio ─────────────────────────────
        band_ratio = _band_energy_ratio(audio_np)

        # ── combined verdict ──────────────────────────────────────────────
        reason = None
        if speech_frac < min_speech:
            reason = "vad"
        elif flatness > max_flat:
            reason = f"flatness"
        elif band_ratio < min_band:
            reason = f"band_ratio"

        verdict = f"drop:{reason}" if reason else "pass"
        print(f"VAD_GATE board={board_id} speech_frac={speech_frac:.2f} "
              f"flatness={flatness:.4f} band_ratio={band_ratio:.3f} "
              f"verdict={verdict}")
        return reason is None, speech_frac

    except Exception as exc:
        print(f"GATE_ERROR board={board_id} exc={exc}")
        return True, None  # fail-open
