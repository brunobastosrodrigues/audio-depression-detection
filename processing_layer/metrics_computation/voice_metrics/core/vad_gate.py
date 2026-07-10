"""
Server-side speech gate — hardened four-condition filter for XVF tonal noise.

A segment PASSES only if ALL of the following hold:
  (AND-0) webrtcvad(aggressiveness=3) classifies ≥VAD_GATE_MIN_SPEECH fraction
          of 30 ms frames as speech.
  (AND-1) peak_abs_amplitude ≤ VAD_MAX_PEAK          (default 28000)
           — XVF noise CLIPS: int16 peak 28 000–30 500; clean speech stays well
             below saturation.
  (AND-2) fraction of spectral energy below 120 Hz ≤ VAD_MAX_LOWBAND_FRAC
           (default 0.30)
           — mains hum (50/100 Hz) concentrates 11–23 % of its power sub-120 Hz;
             speech energy is spread across formants (typically < 5 % sub-120 Hz).
  (AND-3) spectral flatness ≥ VAD_MIN_FLATNESS        (default 0.05)
           — Wiener entropy in [0,1]: tonal XVF noise has flatness 0.002–0.024
             (near pure tone, FAILS the minimum); real speech 0.10–0.45 (passes).

Drop reasons logged:
  vad       — webrtcvad speech_frac below VAD_GATE_MIN_SPEECH
  peak_sat  — peak int16 amplitude above VAD_MAX_PEAK
  lowband   — sub-120 Hz energy fraction above VAD_MAX_LOWBAND_FRAC
  tonal     — spectral flatness below VAD_MIN_FLATNESS
  empty     — no complete 30 ms frames

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
_MIN_SPEECH_DEFAULT     = 0.30
_AGGRESSIVENESS_DEFAULT = 3
_MAX_PEAK_DEFAULT       = 28_000   # int16 units; drop if peak_abs exceeds this
_MAX_LOWBAND_FRAC_DEFAULT = 0.30   # fraction of energy <120 Hz; drop if above
_MIN_FLATNESS_DEFAULT   = 0.05     # Wiener entropy; drop if flatness below this
_FRAME_MS  = 30                    # webrtcvad supports 10/20/30 ms
_TARGET_SR = 16_000                # webrtcvad supports 8/16/32/48 kHz

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
    Returns a value in [0, 1]: near-0 = pure tone, near-1 = white noise.
    Real speech: ~0.10–0.45.  XVF tonal noise: 0.002–0.024.
    """
    import librosa
    return float(np.mean(librosa.feature.spectral_flatness(y=audio_np)[0]))


def _lowband_energy_frac(audio_np: np.ndarray,
                         sr: int = _TARGET_SR,
                         cutoff_hz: int = 120) -> float:
    """
    Fraction of total FFT power below cutoff_hz.
    Mains hum (50/100 Hz) puts 11–23 % of energy here; speech typically < 5 %.
    Returns 0.0 on silence.
    """
    freqs = np.fft.rfftfreq(len(audio_np), 1.0 / sr)
    power = np.abs(np.fft.rfft(audio_np)) ** 2
    total = float(np.sum(power))
    if total == 0.0:
        return 0.0
    mask = freqs < cutoff_hz
    return float(np.sum(power[mask]) / total)


# ── public API ───────────────────────────────────────────────────────────────
def check(audio_bytes: bytes, board_id=None) -> tuple:
    """
    Gate check for a single audio segment.

    Returns (should_pass: bool, speech_frac: float | None).
      should_pass=True  → let the segment through (speech or gate error)
      should_pass=False → drop (noise)

    Log format:
      VAD_GATE board=<id> speech_frac=X.XX peak=NNNNN \
               lowband_frac=Y.YYY flatness=Z.ZZZZ verdict=pass
      VAD_GATE board=<id> speech_frac=X.XX peak=NNNNN \
               lowband_frac=Y.YYY flatness=Z.ZZZZ verdict=drop:<reason>
      GATE_ERROR board=<id> exc=<message>
    """
    min_speech      = float(os.getenv("VAD_GATE_MIN_SPEECH",
                                      str(_MIN_SPEECH_DEFAULT)))
    max_peak        = int(  os.getenv("VAD_MAX_PEAK",
                                      str(_MAX_PEAK_DEFAULT)))
    max_lowband_frac = float(os.getenv("VAD_MAX_LOWBAND_FRAC",
                                       str(_MAX_LOWBAND_FRAC_DEFAULT)))
    min_flatness    = float(os.getenv("VAD_MIN_FLATNESS",
                                      str(_MIN_FLATNESS_DEFAULT)))

    if not _WEBRTCVAD_OK:
        print(f"VAD_GATE board={board_id} speech_frac=N/A peak=N/A "
              f"lowband_frac=N/A flatness=N/A verdict=pass (webrtcvad unavailable)")
        return True, None

    try:
        # ── decode ───────────────────────────────────────────────────────
        audio_np, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")

        if audio_np.ndim > 1:
            audio_np = audio_np.mean(axis=1)

        audio_np = _resample_to_16k(audio_np, sr)

        # ── convert to int16 for webrtcvad + peak detection ──────────────
        audio_int16 = (np.clip(audio_np, -1.0, 1.0) * 32767).astype(np.int16)
        pcm_bytes   = audio_int16.tobytes()

        # ── Layer 0: webrtcvad ────────────────────────────────────────────
        frame_samples = int(_TARGET_SR * _FRAME_MS / 1000)  # 480 @ 16kHz/30ms
        frame_bytes   = frame_samples * 2                    # 2 bytes per int16

        total_frames = speech_frames = 0
        for offset in range(0, len(pcm_bytes) - frame_bytes + 1, frame_bytes):
            frame = pcm_bytes[offset:offset + frame_bytes]
            total_frames += 1
            if _VAD.is_speech(frame, _TARGET_SR):
                speech_frames += 1

        if total_frames == 0:
            print(f"VAD_GATE board={board_id} speech_frac=0.00 peak=0 "
                  f"lowband_frac=N/A flatness=N/A verdict=drop:empty")
            return False, 0.0

        speech_frac = speech_frames / total_frames

        # ── spectral features (computed once for all three checks) ────────
        peak_abs     = int(np.max(np.abs(audio_int16)))
        lowband_frac = _lowband_energy_frac(audio_np)
        flatness     = _spectral_flatness(audio_np)

        # ── combined verdict: pass only if webrtcvad=speech AND no reject ─
        reason = None
        if speech_frac < min_speech:
            reason = "vad"
        elif peak_abs > max_peak:
            reason = "peak_sat"
        elif lowband_frac > max_lowband_frac:
            reason = "lowband"
        elif flatness < min_flatness:
            reason = "tonal"

        verdict = f"drop:{reason}" if reason else "pass"
        print(f"VAD_GATE board={board_id} speech_frac={speech_frac:.2f} "
              f"peak={peak_abs} lowband_frac={lowband_frac:.3f} "
              f"flatness={flatness:.4f} verdict={verdict}")
        return reason is None, speech_frac

    except Exception as exc:
        print(f"GATE_ERROR board={board_id} exc={exc}")
        return True, None  # fail-open
