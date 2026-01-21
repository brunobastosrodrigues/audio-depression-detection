#!/usr/bin/env python3
"""
Python Reference Feature Extractor for Depression Detection

This module extracts clinically-validated acoustic features from audio files
using standard Python libraries. It serves as the "gold standard" baseline
for the Feature Degradation Analysis experiment.

Features extracted:
1. F0 mean (Hz) - using Praat via parselmouth
2. F0 std (Hz) - pitch variability
3. F0 range (Hz) - pitch range
4. Pause ratio - proportion of unvoiced frames
5. Voiced ratio - proportion of voiced frames
6. Energy std - energy dynamics (RMS-based)

Usage:
    python python_feature_extractor.py --input audio.wav
    python python_feature_extractor.py --batch daic_woz_extracted/ --output results/
"""

import os
import sys
import json
import argparse
import warnings
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Tuple
import numpy as np

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

# Try to import optional dependencies
try:
    import parselmouth
    from parselmouth.praat import call
    HAS_PARSELMOUTH = True
except ImportError:
    HAS_PARSELMOUTH = False
    print("Warning: parselmouth not installed. Using librosa for F0.")

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False


@dataclass
class ExtractorConfig:
    """Configuration for feature extraction."""
    sample_rate: int = 16000
    frame_size_ms: float = 32.0       # Frame size in milliseconds
    hop_size_ms: float = 10.0         # Hop size in milliseconds
    f0_min_hz: float = 50.0           # Minimum F0 for pitch tracking
    f0_max_hz: float = 500.0          # Maximum F0 for pitch tracking
    vad_threshold_db: float = -40.0   # Energy threshold for VAD
    use_praat: bool = True            # Use Praat for F0 (more accurate)


@dataclass
class Features:
    """Extracted acoustic features."""
    f0_mean_hz: float
    f0_std_hz: float
    f0_range_hz: float
    pause_ratio: float
    voiced_ratio: float
    energy_std: float
    energy_mean_db: float

    # Voice quality features (Phase 2)
    jitter: float = 0.0
    jitter_rap: float = 0.0
    shimmer: float = 0.0
    shimmer_apq3: float = 0.0
    hnr_mean: float = 0.0
    snr: float = 0.0

    # Metadata
    duration_sec: float = 0.0
    frame_count: int = 0
    voiced_frames: int = 0
    sample_rate: int = 16000

    # Optional extended features
    f0_median_hz: Optional[float] = None
    f0_q25_hz: Optional[float] = None
    f0_q75_hz: Optional[float] = None


def load_audio(path: str, target_sr: int = 16000) -> Tuple[np.ndarray, int]:
    """Load audio file and resample if needed."""
    if HAS_LIBROSA:
        audio, sr = librosa.load(path, sr=target_sr, mono=True)
        # Convert to int16 range for consistency with C implementation
        # but keep as float for processing
        return audio, sr
    elif HAS_SOUNDFILE:
        audio, sr = sf.read(path)
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)  # Convert to mono
        if sr != target_sr:
            # Simple resampling (not ideal, but works without librosa)
            ratio = target_sr / sr
            new_len = int(len(audio) * ratio)
            audio = np.interp(
                np.linspace(0, len(audio), new_len),
                np.arange(len(audio)),
                audio
            )
            sr = target_sr
        return audio, sr
    else:
        raise ImportError("Need librosa or soundfile to load audio")


def extract_f0_praat(audio: np.ndarray, sr: int, config: ExtractorConfig) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extract F0 using Praat via parselmouth.

    This is the clinical gold standard for pitch tracking.

    Returns:
        f0: Array of F0 values (0 = unvoiced)
        times: Array of time points
    """
    if not HAS_PARSELMOUTH:
        raise ImportError("parselmouth not installed")

    # Create Praat Sound object
    snd = parselmouth.Sound(audio, sampling_frequency=sr)

    # Extract pitch using autocorrelation method (standard for speech)
    pitch = call(snd, "To Pitch (ac)",
                 config.hop_size_ms / 1000,  # time step
                 config.f0_min_hz,            # pitch floor
                 15,                          # max candidates
                 "no",                        # very accurate
                 0.03,                        # silence threshold
                 0.45,                        # voicing threshold
                 0.01,                        # octave cost
                 0.35,                        # octave-jump cost
                 0.14,                        # voiced/unvoiced cost
                 config.f0_max_hz)            # pitch ceiling

    # Get F0 values
    times = pitch.xs()
    f0_values = np.array([pitch.get_value_at_time(t) for t in times])

    # Replace NaN with 0 (unvoiced)
    f0_values = np.nan_to_num(f0_values, nan=0.0)

    return f0_values, times


def extract_voice_quality_praat(audio: np.ndarray, sr: int, config: ExtractorConfig) -> dict:
    """
    Extract voice quality metrics (jitter, shimmer, HNR) using Praat.

    Returns:
        Dictionary with jitter, jitter_rap, shimmer, shimmer_apq3, hnr_mean
    """
    if not HAS_PARSELMOUTH:
        return {
            'jitter': 0.0, 'jitter_rap': 0.0,
            'shimmer': 0.0, 'shimmer_apq3': 0.0,
            'hnr_mean': 0.0
        }

    try:
        snd = parselmouth.Sound(audio, sampling_frequency=sr)

        # Create PointProcess for jitter/shimmer (voiced parts)
        pitch = call(snd, "To Pitch (cc)",
                     0.0,  # time step (auto)
                     config.f0_min_hz,
                     15,  # max candidates
                     "no",  # very accurate
                     0.03,  # silence threshold
                     0.45,  # voicing threshold
                     0.01,  # octave cost
                     0.35,  # octave-jump cost
                     0.14,  # voiced/unvoiced cost
                     config.f0_max_hz)

        point_process = call(snd, "To PointProcess (periodic, cc)",
                            config.f0_min_hz, config.f0_max_hz)

        # Jitter (local) - relative period perturbation
        jitter_local = call(point_process, "Get jitter (local)",
                           0, 0,  # time range (all)
                           0.0001,  # period floor
                           0.02,    # period ceiling
                           1.3)     # max period factor

        # Jitter RAP - relative average perturbation
        jitter_rap = call(point_process, "Get jitter (rap)",
                         0, 0, 0.0001, 0.02, 1.3)

        # Shimmer (local) - relative amplitude perturbation
        shimmer_local = call([snd, point_process], "Get shimmer (local)",
                            0, 0, 0.0001, 0.02, 1.3, 1.6)

        # Shimmer APQ3
        shimmer_apq3 = call([snd, point_process], "Get shimmer (apq3)",
                           0, 0, 0.0001, 0.02, 1.3, 1.6)

        # HNR (Harmonics-to-Noise Ratio)
        harmonicity = call(snd, "To Harmonicity (cc)",
                          0.01,  # time step
                          config.f0_min_hz,
                          0.1,   # silence threshold
                          1.0)   # periods per window

        hnr_mean = call(harmonicity, "Get mean", 0, 0)

        # Handle NaN values
        jitter_local = 0.0 if np.isnan(jitter_local) else jitter_local
        jitter_rap = 0.0 if np.isnan(jitter_rap) else jitter_rap
        shimmer_local = 0.0 if np.isnan(shimmer_local) else shimmer_local
        shimmer_apq3 = 0.0 if np.isnan(shimmer_apq3) else shimmer_apq3
        hnr_mean = 0.0 if np.isnan(hnr_mean) else hnr_mean

        return {
            'jitter': float(jitter_local),
            'jitter_rap': float(jitter_rap),
            'shimmer': float(shimmer_local),
            'shimmer_apq3': float(shimmer_apq3),
            'hnr_mean': float(hnr_mean)
        }

    except Exception as e:
        # Return zeros if extraction fails
        return {
            'jitter': 0.0, 'jitter_rap': 0.0,
            'shimmer': 0.0, 'shimmer_apq3': 0.0,
            'hnr_mean': 0.0
        }


def extract_f0_librosa(audio: np.ndarray, sr: int, config: ExtractorConfig) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extract F0 using librosa's pyin.

    Fallback when parselmouth is not available.
    """
    if not HAS_LIBROSA:
        raise ImportError("librosa not installed")

    frame_length = int(config.frame_size_ms * sr / 1000)
    hop_length = int(config.hop_size_ms * sr / 1000)

    f0, voiced_flag, voiced_probs = librosa.pyin(
        audio,
        fmin=config.f0_min_hz,
        fmax=config.f0_max_hz,
        sr=sr,
        frame_length=frame_length,
        hop_length=hop_length,
    )

    # Replace NaN with 0
    f0 = np.nan_to_num(f0, nan=0.0)

    times = librosa.times_like(f0, sr=sr, hop_length=hop_length)

    return f0, times


def compute_energy(audio: np.ndarray, sr: int, config: ExtractorConfig) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute frame-wise RMS energy.

    Returns:
        rms: RMS energy per frame
        rms_db: RMS in decibels
    """
    frame_length = int(config.frame_size_ms * sr / 1000)
    hop_length = int(config.hop_size_ms * sr / 1000)

    # Compute RMS energy per frame
    n_frames = 1 + (len(audio) - frame_length) // hop_length
    rms = np.zeros(n_frames)

    for i in range(n_frames):
        start = i * hop_length
        end = start + frame_length
        frame = audio[start:end]
        rms[i] = np.sqrt(np.mean(frame ** 2))

    # Convert to dB (avoid log(0))
    rms_db = 20 * np.log10(rms + 1e-10)

    return rms, rms_db


def compute_vad(rms_db: np.ndarray, threshold_db: float) -> np.ndarray:
    """
    Simple energy-based Voice Activity Detection.

    Returns:
        voiced: Boolean array (True = voiced, False = silence/unvoiced)
    """
    return rms_db > threshold_db


def extract_features(
    audio_path: str,
    config: Optional[ExtractorConfig] = None
) -> Features:
    """
    Extract all features from an audio file.

    Args:
        audio_path: Path to audio file (WAV)
        config: Extraction configuration

    Returns:
        Features dataclass with all extracted features
    """
    if config is None:
        config = ExtractorConfig()

    # Load audio
    audio, sr = load_audio(audio_path, config.sample_rate)
    duration_sec = len(audio) / sr

    # Extract F0
    if config.use_praat and HAS_PARSELMOUTH:
        f0, times = extract_f0_praat(audio, sr, config)
    else:
        f0, times = extract_f0_librosa(audio, sr, config)

    # Compute energy
    rms, rms_db = compute_energy(audio, sr, config)

    # VAD from energy
    vad_mask = compute_vad(rms_db, config.vad_threshold_db)

    # Also use F0 for voicing detection
    f0_voiced_mask = f0 > 0

    # Combined voicing: both energy and F0 indicate voiced
    # Align lengths (may differ slightly)
    min_len = min(len(vad_mask), len(f0_voiced_mask))
    vad_mask = vad_mask[:min_len]
    f0_voiced_mask = f0_voiced_mask[:min_len]
    f0 = f0[:min_len]
    rms = rms[:min_len]
    rms_db = rms_db[:min_len]

    # Use F0-based voicing as primary (more reliable for speech)
    voiced_mask = f0_voiced_mask

    # Extract voiced F0 values
    voiced_f0 = f0[voiced_mask]

    if len(voiced_f0) < 10:
        # Not enough voiced frames
        return Features(
            f0_mean_hz=0.0,
            f0_std_hz=0.0,
            f0_range_hz=0.0,
            pause_ratio=1.0,
            voiced_ratio=0.0,
            energy_std=float(np.std(rms)),
            energy_mean_db=float(np.mean(rms_db)),
            duration_sec=duration_sec,
            frame_count=len(f0),
            voiced_frames=0,
            sample_rate=sr,
        )

    # Compute F0 statistics (voiced frames only)
    f0_mean = float(np.mean(voiced_f0))
    f0_std = float(np.std(voiced_f0))
    f0_range = float(np.max(voiced_f0) - np.min(voiced_f0))
    f0_median = float(np.median(voiced_f0))
    f0_q25 = float(np.percentile(voiced_f0, 25))
    f0_q75 = float(np.percentile(voiced_f0, 75))

    # Compute pause/voiced ratios
    voiced_ratio = float(np.mean(voiced_mask))
    pause_ratio = 1.0 - voiced_ratio

    # Compute energy statistics
    energy_std = float(np.std(rms))
    energy_mean_db = float(np.mean(rms_db))

    # Extract voice quality metrics (jitter, shimmer, HNR)
    voice_quality = extract_voice_quality_praat(audio, sr, config)

    # Compute SNR (voiced energy vs unvoiced energy)
    voiced_rms = rms[voiced_mask] if np.any(voiced_mask) else np.array([0])
    unvoiced_rms = rms[~voiced_mask] if np.any(~voiced_mask) else np.array([1e-10])
    mean_voiced = np.mean(voiced_rms) if len(voiced_rms) > 0 else 0
    mean_unvoiced = np.mean(unvoiced_rms) if len(unvoiced_rms) > 0 else 1e-10
    snr = 20 * np.log10(mean_voiced / (mean_unvoiced + 1e-10)) if mean_voiced > 0 else 0.0
    snr = float(np.clip(snr, -10, 60))

    return Features(
        f0_mean_hz=f0_mean,
        f0_std_hz=f0_std,
        f0_range_hz=f0_range,
        pause_ratio=pause_ratio,
        voiced_ratio=voiced_ratio,
        energy_std=energy_std,
        energy_mean_db=energy_mean_db,
        jitter=voice_quality['jitter'],
        jitter_rap=voice_quality['jitter_rap'],
        shimmer=voice_quality['shimmer'],
        shimmer_apq3=voice_quality['shimmer_apq3'],
        hnr_mean=voice_quality['hnr_mean'],
        snr=snr,
        duration_sec=duration_sec,
        frame_count=len(f0),
        voiced_frames=int(np.sum(voiced_mask)),
        sample_rate=sr,
        f0_median_hz=f0_median,
        f0_q25_hz=f0_q25,
        f0_q75_hz=f0_q75,
    )


def process_batch(
    input_dir: str,
    output_dir: str,
    config: Optional[ExtractorConfig] = None,
    limit: Optional[int] = None
) -> List[Dict]:
    """
    Process a batch of DAIC-WOZ sessions.

    Args:
        input_dir: Directory containing extracted sessions (e.g., daic_woz_extracted/)
        output_dir: Directory for output files
        config: Extraction configuration
        limit: Maximum number of sessions to process

    Returns:
        List of feature dictionaries
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if config is None:
        config = ExtractorConfig()

    results = []

    # Find all session directories
    session_dirs = sorted([d for d in input_path.iterdir() if d.is_dir()])

    if limit:
        session_dirs = session_dirs[:limit]

    print(f"Processing {len(session_dirs)} sessions from {input_dir}")

    for i, session_dir in enumerate(session_dirs):
        session_id = session_dir.name

        # Find audio file
        audio_files = list(session_dir.glob("*_AUDIO.wav"))
        if not audio_files:
            audio_files = list(session_dir.glob(f"{session_id}/*_AUDIO.wav"))

        if not audio_files:
            print(f"  [{i+1}/{len(session_dirs)}] {session_id}: No audio file found")
            continue

        audio_path = audio_files[0]

        print(f"  [{i+1}/{len(session_dirs)}] {session_id}...", end=" ", flush=True)

        try:
            features = extract_features(str(audio_path), config)
            result = {
                "session_id": session_id,
                **asdict(features)
            }
            results.append(result)
            print(f"OK (F0={features.f0_mean_hz:.1f}Hz, pause={features.pause_ratio:.2f})")
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                "session_id": session_id,
                "error": str(e)
            })

    # Save results
    json_path = output_path / "python_features.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved JSON to {json_path}")

    # Save CSV
    csv_path = output_path / "python_features.csv"
    valid_results = [r for r in results if "error" not in r]

    if valid_results:
        with open(csv_path, "w") as f:
            # Header
            headers = list(valid_results[0].keys())
            f.write(",".join(headers) + "\n")

            # Data
            for r in valid_results:
                row = [str(r.get(h, "")) for h in headers]
                f.write(",".join(row) + "\n")

        print(f"Saved CSV to {csv_path}")

        # Summary
        print(f"\n=== Feature Summary ({len(valid_results)} sessions) ===")
        for feat in ["f0_mean_hz", "f0_std_hz", "pause_ratio", "energy_std"]:
            values = [r[feat] for r in valid_results if feat in r]
            if values:
                print(f"  {feat:15s}: {np.mean(values):8.3f} ± {np.std(values):8.3f}")

    return results


def compare_with_covarep(
    python_features: Dict,
    covarep_features: Dict
) -> Dict:
    """
    Compare Python-extracted features with COVAREP ground truth.

    Returns divergence metrics.
    """
    metrics = {}

    # F0 comparison
    if "f0_mean_hz" in python_features and "f0_mean_hz" in covarep_features:
        py_f0 = python_features["f0_mean_hz"]
        cov_f0 = covarep_features["f0_mean_hz"]
        if cov_f0 > 0:
            metrics["f0_mean_mape"] = abs(py_f0 - cov_f0) / cov_f0 * 100
            metrics["f0_mean_diff"] = py_f0 - cov_f0

    # Pause ratio comparison
    if "pause_ratio" in python_features and "pause_ratio" in covarep_features:
        py_pause = python_features["pause_ratio"]
        cov_pause = covarep_features["pause_ratio"]
        if cov_pause > 0:
            metrics["pause_ratio_mape"] = abs(py_pause - cov_pause) / cov_pause * 100
            metrics["pause_ratio_diff"] = py_pause - cov_pause

    return metrics


def main():
    parser = argparse.ArgumentParser(description="Python Reference Feature Extractor")
    parser.add_argument("--input", "-i", type=str, help="Single audio file to process")
    parser.add_argument("--batch", "-b", type=str, help="Directory of sessions to process")
    parser.add_argument("--output", "-o", type=str, default="results/", help="Output directory")
    parser.add_argument("--limit", type=int, help="Limit number of sessions")
    parser.add_argument("--no-praat", action="store_true", help="Use librosa instead of Praat")
    args = parser.parse_args()

    config = ExtractorConfig(use_praat=not args.no_praat)

    if args.input:
        # Single file mode
        print(f"Processing: {args.input}")
        features = extract_features(args.input, config)
        print(json.dumps(asdict(features), indent=2))

    elif args.batch:
        # Batch mode
        process_batch(args.batch, args.output, config, args.limit)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
