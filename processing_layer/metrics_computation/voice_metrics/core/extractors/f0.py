import librosa
import numpy as np


def semitone_to_hz(semitones):
    """Convert eGeMAPS semitones (relative to 27.5 Hz) to Hz."""
    return 27.5 * (2 ** (semitones / 12.0))


def get_f0_avg(features_LLD, audio_signal, sr):
    """
    Compute fundamental frequency (F0) average using openSMILE (eGeMAPS) and librosa.
    """

    # openSMILE f0 average computation (eGeMAPS semitones)
    f0_semitones = features_LLD["F0semitone_sma3nz"]
    f0_opensmile = f0_semitones[f0_semitones > 0]
    
    if not f0_opensmile.empty:
        f0_opensmile_hz = semitone_to_hz(f0_opensmile)
        f0_opensmile_mean = f0_opensmile_hz.mean()
    else:
        f0_opensmile_mean = 0

    # librosa f0 average computation
    y = np.array(audio_signal, dtype=np.float32)
    f0, _, _ = librosa.pyin(y, fmin=30, fmax=2000, sr=sr)

    if f0 is not None and np.any(~np.isnan(f0)):
        librosa_mean = np.nanmean(f0)
        return (librosa_mean + f0_opensmile_mean) / 2 if f0_opensmile_mean > 0 else librosa_mean
    else:
        return f0_opensmile_mean


def get_f0_std(features_LLD, audio_signal, sr):
    """
    Compute fundamental frequency (F0) standard deviation using openSMILE (eGeMAPS) and librosa.
    """

    # openSMILE f0 standard deviation computation
    f0_semitones = features_LLD["F0semitone_sma3nz"]
    f0_opensmile = f0_semitones[f0_semitones > 0]
    
    if not f0_opensmile.empty:
        f0_opensmile_hz = semitone_to_hz(f0_opensmile)
        f0_opensmile_std = f0_opensmile_hz.std()
    else:
        f0_opensmile_std = 0

    # librosa f0 standard deviation computation
    y = np.array(audio_signal, dtype=np.float32)
    f0, _, _ = librosa.pyin(y, fmin=30, fmax=2000, sr=sr)

    if f0 is not None and np.any(~np.isnan(f0)):
        librosa_std = np.nanstd(f0)
        return (librosa_std + f0_opensmile_std) / 2 if f0_opensmile_std > 0 else librosa_std
    else:
        return f0_opensmile_std


def get_f0_range(features_LLD, audio_signal, sr):
    """
    Compute fundamental frequency (F0) range using both openSMILE and librosa.
    """

    # openSMILE f0 range
    f0_semitones = features_LLD["F0semitone_sma3nz"]
    f0_opensmile = f0_semitones[f0_semitones > 0]
    
    if not f0_opensmile.empty:
        f0_opensmile_hz = semitone_to_hz(f0_opensmile)
        f0_opensmile_range = f0_opensmile_hz.max() - f0_opensmile_hz.min()
    else:
        f0_opensmile_range = 0

    # librosa f0 range
    y = np.array(audio_signal, dtype=np.float32)
    f0_librosa, _, _ = librosa.pyin(y, fmin=30, fmax=2000, sr=sr)
    f0_librosa = f0_librosa[~np.isnan(f0_librosa)]
    f0_librosa_range = f0_librosa.max() - f0_librosa.min() if f0_librosa.size > 0 else 0

    if f0_librosa.size > 0 and f0_opensmile_range > 0:
        return (f0_opensmile_range + f0_librosa_range) / 2
    elif f0_librosa.size > 0:
        return f0_librosa_range
    else:
        return f0_opensmile_range
