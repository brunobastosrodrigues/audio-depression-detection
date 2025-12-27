import numpy as np

def get_rms_energy_range(rms_series):
    """
    Compute rms energy range using manual RMS series
    """
    if rms_series is None or len(rms_series) == 0:
        return 0.0
    return float(np.max(rms_series) - np.min(rms_series))


def get_rms_energy_std(rms_series):
    """
    Compute rms energy standard deviation using manual RMS series
    """
    if rms_series is None or len(rms_series) == 0:
        return 0.0
    return float(np.std(rms_series))
