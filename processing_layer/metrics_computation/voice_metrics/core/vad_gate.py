"""
Server-side speech gate using webrtcvad (aggressiveness 2).

Computes the fraction of 30 ms frames classified as speech by webrtcvad.
If speech_fraction < VAD_GATE_MIN_SPEECH (default 0.30) the segment is
dropped BEFORE the expensive recognition / metrics pipeline.

Design principles
-----------------
* Fail-open: any exception -> returns (True, None) so a gate bug
  never silences real speech.
* Resamples to 16 kHz (webrtcvad requirement); accepts any source rate.
* Mono only; takes channel-mean for stereo input.
"""

import io
import os

import numpy as np
import soundfile as sf

_MIN_SPEECH_DEFAULT = 0.30
_FRAME_MS = 30          # webrtcvad supports 10/20/30 ms
_TARGET_SR = 16_000     # webrtcvad supports 8/16/32/48 kHz; 16 kHz is standard

try:
    import webrtcvad as _webrtcvad
    _VAD = _webrtcvad.Vad(2)   # aggressiveness 2
    _WEBRTCVAD_OK = True
    print("VAD_GATE init: webrtcvad loaded, aggressiveness=2")
except Exception as _e:
    _WEBRTCVAD_OK = False
    print(f"VAD_GATE init: webrtcvad unavailable ({_e}), gate disabled (fail-open)")


def _resample_to_16k(audio: np.ndarray, sr: int) -> np.ndarray:
    """Integer-ratio resample using scipy; handles common rates exactly."""
    if sr == _TARGET_SR:
        return audio
    from scipy.signal import resample_poly
    import math
    g = math.gcd(sr, _TARGET_SR)
    return resample_poly(audio, _TARGET_SR // g, sr // g).astype(np.float32)


def check(audio_bytes: bytes, board_id=None) -> tuple:
    """
    Gate check for a single audio segment.

    Returns (should_pass: bool, speech_frac: float | None).
      should_pass=True  -> let the segment through (speech or gate error)
      should_pass=False -> drop (noise)

    Logs one line per decision:
      VAD_GATE board=<id> speech_frac=0.XX verdict=pass/drop
      GATE_ERROR board=<id> exc=<message>
    """
    min_speech = float(os.getenv("VAD_GATE_MIN_SPEECH", str(_MIN_SPEECH_DEFAULT)))

    if not _WEBRTCVAD_OK:
        print(f"VAD_GATE board={board_id} speech_frac=N/A verdict=pass (webrtcvad unavailable)")
        return True, None

    try:
        # Decode WAV bytes
        audio_np, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")

        # Mono: average across channels
        if audio_np.ndim > 1:
            audio_np = audio_np.mean(axis=1)

        # Resample to 16 kHz
        audio_np = _resample_to_16k(audio_np, sr)

        # Convert to 16-bit PCM
        audio_int16 = (np.clip(audio_np, -1.0, 1.0) * 32767).astype(np.int16)
        pcm_bytes = audio_int16.tobytes()

        frame_samples = int(_TARGET_SR * _FRAME_MS / 1000)  # 480 samples @ 16kHz/30ms
        frame_bytes = frame_samples * 2                       # 2 bytes per int16

        total_frames = 0
        speech_frames = 0

        for offset in range(0, len(pcm_bytes) - frame_bytes + 1, frame_bytes):
            frame = pcm_bytes[offset:offset + frame_bytes]
            total_frames += 1
            if _VAD.is_speech(frame, _TARGET_SR):
                speech_frames += 1

        if total_frames == 0:
            print(f"VAD_GATE board={board_id} speech_frac=0.00 verdict=drop (empty audio)")
            return False, 0.0

        speech_frac = speech_frames / total_frames
        verdict = "pass" if speech_frac >= min_speech else "drop"
        print(f"VAD_GATE board={board_id} speech_frac={speech_frac:.2f} verdict={verdict}")
        return verdict == "pass", speech_frac

    except Exception as exc:
        print(f"GATE_ERROR board={board_id} exc={exc}")
        return True, None  # fail-open
