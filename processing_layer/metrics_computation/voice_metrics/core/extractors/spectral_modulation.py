import numpy as np

from core.extractors.spectro_utils import log_melspectrogram


def get_spectral_modulation(audio_np, sample_rate, log_S=None):
    """
    Computes the spectral modulation energy around ~2 cycles/octave
    Optimized with vectorization for better performance. `log_S` may be a precomputed
    log-mel spectrogram (shared with temporal_modulation) to avoid recomputing the STFT.
    """
    if log_S is None:
        log_S = log_melspectrogram(audio_np, sample_rate)

    # Vectorized zero-mean operation per frequency bin (axis=0 centers each time frame's spectrum)
    log_S_centered = log_S - np.mean(log_S, axis=0, keepdims=True)
    
    # Vectorized FFT along frequency axis for all time frames
    fft_result = np.fft.fft(log_S_centered, axis=0)
    power = np.abs(fft_result) ** 2
    
    # Compute freqs once (same for all frames)
    freqs = np.fft.fftfreq(log_S.shape[0], d=1)  # unit = bins
    
    # Find target bin once (same for all frames)
    # Assumption: log-mel spacing → ~1 bin per 0.1 oct, so 2 cyc/oct ~ bin 20
    target_bin = np.argmin(np.abs(freqs - 2))
    
    # Extract modulation energy at target bin across all frames
    spec_mod_power = power[target_bin, :]

    return float(np.mean(spec_mod_power))
