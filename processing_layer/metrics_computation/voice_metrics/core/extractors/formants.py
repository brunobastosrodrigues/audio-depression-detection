"""
Formant Extractor with Dynamic Behavioral Metrics

Formants are resonant frequencies of the vocal tract. F1 and F2 are
particularly important for vowel quality and articulation precision.

Dynamic Metrics Rationale:
- formant_cv: Variability in formant frequencies (articulation precision)
- formant_std: Instability in vocal tract configuration
- formant_entropy: Predictability of articulatory patterns

Clinical Relevance:
- Reduced formant variability: Less precise articulation (psychomotor)
- Lower formant frequencies: Potential indicator of fatigue
- F2 transition speed is measured separately for articulatory dynamics

Note: This module currently extracts F1 frequencies using the eGeMAPS
F2frequency field (which corresponds to the second formant in OpenSMILE).
The naming is preserved for backward compatibility with existing mappings.
"""

import numpy as np
from core.extractors.dynamic_metrics_utils import (
    compute_coefficient_of_variation,
    compute_interquartile_range,
    compute_entropy,
)


def _extract_formant_series(features_LLD) -> np.ndarray:
    """
    Extract formant frequency series from OpenSMILE features.

    Returns:
        numpy array of formant frequency values
    """
    formant_series = features_LLD.filter(like="F2frequency_sma3nz", axis=1)

    if formant_series.empty:
        return np.array([])

    # Flatten to 1D array and remove zeros/NaNs
    values = formant_series.values.flatten()
    values = values[~np.isnan(values)]
    values = values[values > 0]  # Remove unvoiced frames

    return values


def get_formant_dynamic(features_LLD) -> dict:
    """
    Compute all formant dynamic behavioral metrics in a single pass.

    This is the Phase 1 "Silent Expansion" function that returns a
    dictionary of metrics for flattening into the database.

    Returns:
        Dictionary with keys:
        - formant_f1_frequencies_mean: Mean formant frequency (legacy)
        - formant_f1_std: Standard deviation (NEW)
        - formant_f1_cv: Coefficient of variation (NEW)
        - formant_f1_iqr: Interquartile range (NEW)
        - formant_f1_entropy: Normalized entropy (NEW)
    """
    formant_series = _extract_formant_series(features_LLD)

    if len(formant_series) == 0:
        return {
            "formant_f1_frequencies_mean": 0.0,
            "formant_f1_std": 0.0,
            "formant_f1_cv": 0.0,
            "formant_f1_iqr": 0.0,
            "formant_f1_entropy": 0.0,
        }

    return {
        "formant_f1_frequencies_mean": float(np.mean(formant_series)),  # Legacy
        "formant_f1_std": float(np.std(formant_series)),                # NEW
        "formant_f1_cv": compute_coefficient_of_variation(formant_series),   # NEW
        "formant_f1_iqr": compute_interquartile_range(formant_series),       # NEW
        "formant_f1_entropy": compute_entropy(formant_series),               # NEW
    }


# ============================================================================
# LEGACY FUNCTION (Preserved for backward compatibility)
# ============================================================================

def get_formant_f1_frequencies(features_LLD):
    """
    Compute the formant frequencies using openSMILE.
    LEGACY: Use get_formant_dynamic() for new implementations.
    """
    formant_series = _extract_formant_series(features_LLD)
    return float(np.mean(formant_series)) if len(formant_series) > 0 else 0.0
