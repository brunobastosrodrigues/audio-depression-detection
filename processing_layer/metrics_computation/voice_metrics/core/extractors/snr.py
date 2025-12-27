import numpy as np


def get_snr(audio_signal, rms_series):
    """
    Estimate SNR using manual RMS energy series.
    """
    if rms_series is None or len(rms_series) == 0:
        return 0.0
        
    signal_energy = np.mean(rms_series)
    noise_floor = np.percentile(rms_series, 25) # Use 25th percentile as noise floor proxy
    
    if noise_floor <= 0:
        return 0.0
        
    snr_estimate_db = 10 * np.log10(signal_energy / noise_floor)
    return float(snr_estimate_db)
