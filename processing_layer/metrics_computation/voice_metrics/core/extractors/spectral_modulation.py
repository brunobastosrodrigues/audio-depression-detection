import numpy as np
import librosa


def get_spectral_modulation(audio_np, sample_rate):
    """
    Computes the spectral modulation energy around ~2 cycles/octave
    Optimized with vectorization for better performance
    """

    S = librosa.feature.melspectrogram(
        y=audio_np, sr=sample_rate, n_fft=1024, hop_length=256, n_mels=64, fmax=8000
    )
    log_S = librosa.power_to_db(S)

    # Vectorized zero-mean operation
    log_S_centered = log_S - np.mean(log_S, axis=0, keepdims=True)
    
    # Vectorized FFT across all time frames
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
