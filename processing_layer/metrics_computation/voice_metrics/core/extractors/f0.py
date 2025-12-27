"""
Fundamental Frequency (F0) Extractor with Dynamic Behavioral Metrics

This module extracts F0 (pitch) features using both OpenSMILE (eGeMAPS)
and librosa. It now supports dynamic behavioral metrics for DSM-5
depression phenotyping.

Dynamic Metrics Rationale:
- f0_cv (Coefficient of Variation): Low CV indicates monotone speech,
  a key marker for depressed mood.
- f0_entropy: Low entropy indicates predictable/flat intonation patterns.
- f0_iqr: Robust measure of pitch variability.

Backward Compatibility:
- f0_avg is preserved as the legacy mean value
- f0_std and f0_range are preserved as legacy keys
"""

import librosa
import numpy as np
from core.extractors.dynamic_metrics_utils import (
    compute_coefficient_of_variation,
    compute_interquartile_range,
    compute_entropy,
)


def semitone_to_hz(semitones):
    """Convert eGeMAPS semitones (relative to 27.5 Hz) to Hz."""
    return 27.5 * (2 ** (semitones / 12.0))


def _extract_f0_contour(features_LLD, audio_signal, sr):
    """
    Extract the combined F0 contour from OpenSMILE and librosa.

    Returns:
        Tuple of (f0_opensmile_hz, f0_librosa) arrays
    """
    # OpenSMILE F0 extraction (eGeMAPS semitones)
    f0_semitones = features_LLD["F0semitone_sma3nz"]
    f0_opensmile = f0_semitones[f0_semitones > 0]

    if not f0_opensmile.empty:
        f0_opensmile_hz = semitone_to_hz(f0_opensmile).values
    else:
        f0_opensmile_hz = np.array([])

    # librosa F0 extraction
    y = np.array(audio_signal, dtype=np.float32)
    f0_librosa, _, _ = librosa.pyin(y, fmin=30, fmax=2000, sr=sr)

    if f0_librosa is not None:
        f0_librosa = f0_librosa[~np.isnan(f0_librosa)]
    else:
        f0_librosa = np.array([])

    return f0_opensmile_hz, f0_librosa


def get_f0_dynamic(features_LLD, audio_signal, sr) -> dict:
    """
    Compute all F0 dynamic behavioral metrics in a single pass.

    This is the Phase 1 "Silent Expansion" function that returns a
    dictionary of metrics for flattening into the database.

    Returns:
        Dictionary with keys:
        - f0_avg: Mean F0 (legacy, backward compatible)
        - f0_std: Standard deviation (legacy)
        - f0_range: Max - Min (legacy)
        - f0_cv: Coefficient of variation (NEW - key for monotonicity)
        - f0_iqr: Interquartile range (NEW - robust variability)
        - f0_entropy: Normalized entropy (NEW - predictability)
    """
    f0_opensmile_hz, f0_librosa = _extract_f0_contour(features_LLD, audio_signal, sr)

    # Combine both sources for more robust estimates
    all_f0 = []
    if len(f0_opensmile_hz) > 0:
        all_f0.extend(f0_opensmile_hz.tolist())
    if len(f0_librosa) > 0:
        all_f0.extend(f0_librosa.tolist())

    all_f0 = np.array(all_f0)

    if len(all_f0) == 0:
        return {
            "f0_avg": 0.0,
            "f0_std": 0.0,
            "f0_range": 0.0,
            "f0_cv": 0.0,
            "f0_iqr": 0.0,
            "f0_entropy": 0.0,
        }

    # Compute legacy metrics (averaged between sources for consistency)
    f0_mean = float(np.mean(all_f0))
    f0_std = float(np.std(all_f0))
    f0_range = float(np.max(all_f0) - np.min(all_f0))

    # Compute new dynamic metrics
    f0_cv = compute_coefficient_of_variation(all_f0)
    f0_iqr = compute_interquartile_range(all_f0)
    f0_entropy = compute_entropy(all_f0)

    return {
        "f0_avg": f0_mean,      # Legacy key preserved
        "f0_std": f0_std,       # Legacy key preserved
        "f0_range": f0_range,   # Legacy key preserved
        "f0_cv": f0_cv,         # NEW: Coefficient of variation
        "f0_iqr": f0_iqr,       # NEW: Interquartile range
        "f0_entropy": f0_entropy,  # NEW: Normalized entropy
    }


# ============================================================================
# LEGACY FUNCTIONS (Preserved for backward compatibility)
# These are kept to ensure existing code that calls them directly still works.
# ============================================================================

def get_f0_avg(features_LLD, audio_signal, sr):
    """
    Compute fundamental frequency (F0) average using openSMILE (eGeMAPS) and librosa.
    LEGACY: Use get_f0_dynamic() for new implementations.
    """
    f0_opensmile_hz, f0_librosa = _extract_f0_contour(features_LLD, audio_signal, sr)

    f0_opensmile_mean = float(np.mean(f0_opensmile_hz)) if len(f0_opensmile_hz) > 0 else 0
    librosa_mean = float(np.mean(f0_librosa)) if len(f0_librosa) > 0 else 0

    if librosa_mean > 0 and f0_opensmile_mean > 0:
        return (librosa_mean + f0_opensmile_mean) / 2
    elif librosa_mean > 0:
        return librosa_mean
    else:
        return f0_opensmile_mean


def get_f0_std(features_LLD, audio_signal, sr):
    """
    Compute fundamental frequency (F0) standard deviation.
    LEGACY: Use get_f0_dynamic() for new implementations.
    """
    f0_opensmile_hz, f0_librosa = _extract_f0_contour(features_LLD, audio_signal, sr)

    f0_opensmile_std = float(np.std(f0_opensmile_hz)) if len(f0_opensmile_hz) > 0 else 0
    librosa_std = float(np.std(f0_librosa)) if len(f0_librosa) > 0 else 0

    if librosa_std > 0 and f0_opensmile_std > 0:
        return (librosa_std + f0_opensmile_std) / 2
    elif librosa_std > 0:
        return librosa_std
    else:
        return f0_opensmile_std


def get_f0_range(features_LLD, audio_signal, sr):
    """
    Compute fundamental frequency (F0) range.
    LEGACY: Use get_f0_dynamic() for new implementations.
    """
    f0_opensmile_hz, f0_librosa = _extract_f0_contour(features_LLD, audio_signal, sr)

    f0_opensmile_range = (
        float(np.max(f0_opensmile_hz) - np.min(f0_opensmile_hz))
        if len(f0_opensmile_hz) > 0 else 0
    )
    f0_librosa_range = (
        float(np.max(f0_librosa) - np.min(f0_librosa))
        if len(f0_librosa) > 0 else 0
    )

    if f0_librosa_range > 0 and f0_opensmile_range > 0:
        return (f0_opensmile_range + f0_librosa_range) / 2
    elif f0_librosa_range > 0:
        return f0_librosa_range
    else:
        return f0_opensmile_range
