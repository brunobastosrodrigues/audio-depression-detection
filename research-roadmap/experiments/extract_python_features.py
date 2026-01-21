#!/usr/bin/env python3
"""
Python Feature Extractor for Linkage Framework Validation

Extracts the same features as the C extractor using Python/librosa
for comparison. This establishes the "reference" implementation
for the Feature-Clinical Linkage analysis.

Features extracted:
- F0 (pitch): mean, std, range using librosa pyin
- Pause ratio: using energy-based VAD
- Jitter/Shimmer: local perturbation measures
- HNR: Harmonics-to-Noise Ratio
- SNR: Signal-to-Noise Ratio
- Energy: mean, std
"""

import os
import numpy as np
import pandas as pd
import librosa
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import warnings
warnings.filterwarnings('ignore')


@dataclass
class Participant:
    id: str
    sds_score: float
    is_depressed: bool
    audio_files: List[str]
    split: str


def load_eatd_corpus(corpus_path: str) -> List[Participant]:
    """Load EATD-Corpus participant data."""
    participants = []
    corpus = Path(corpus_path)

    for split in ['train', 'validation']:
        split_path = corpus / split
        if not split_path.exists():
            continue

        for pid_folder in split_path.iterdir():
            if not pid_folder.is_dir():
                continue

            label_file = pid_folder / 'new_label.txt'
            if not label_file.exists():
                continue

            try:
                sds_score = float(label_file.read_text().strip())
            except:
                continue

            audio_files = []
            for emotion in ['positive', 'negative', 'neutral']:
                audio_path = pid_folder / f'{emotion}_out.wav'
                if audio_path.exists():
                    audio_files.append(str(audio_path))

            if not audio_files:
                continue

            participants.append(Participant(
                id=pid_folder.name,
                sds_score=sds_score,
                is_depressed=sds_score > 53,
                audio_files=audio_files,
                split=split
            ))

    return participants


def compute_jitter_local(f0_values: np.ndarray) -> float:
    """Compute local jitter (cycle-to-cycle F0 perturbation)."""
    if len(f0_values) < 2:
        return 0.0

    periods = 1.0 / f0_values
    diffs = np.abs(np.diff(periods))
    mean_period = np.mean(periods)

    if mean_period < 1e-10:
        return 0.0

    return np.mean(diffs) / mean_period


def compute_shimmer_local(amplitudes: np.ndarray) -> float:
    """Compute local shimmer (cycle-to-cycle amplitude perturbation)."""
    if len(amplitudes) < 2:
        return 0.0

    diffs = np.abs(np.diff(amplitudes))
    mean_amp = np.mean(amplitudes)

    if mean_amp < 1e-10:
        return 0.0

    return np.mean(diffs) / mean_amp


def compute_hnr(y: np.ndarray, sr: int, f0: float) -> float:
    """Compute HNR using autocorrelation method."""
    if f0 <= 0 or len(y) < sr // 50:  # Need at least 20ms
        return 0.0

    period = int(sr / f0)
    if period < 2 or period >= len(y):
        return 0.0

    # Autocorrelation
    r0 = np.sum(y[:len(y)-period] ** 2)
    r_period = np.sum(y[:len(y)-period] * y[period:])

    if r0 < 1e-10:
        return 0.0

    rho = r_period / r0
    rho = np.clip(rho, 0.01, 0.99)

    return 10 * np.log10(rho / (1 - rho))


def extract_features_python(audio_path: str) -> dict:
    """Extract acoustic features using Python/librosa."""
    try:
        # Load audio
        y, sr = librosa.load(audio_path, sr=16000)
        duration = len(y) / sr

        # F0 extraction using pyin
        f0, voiced_flag, _ = librosa.pyin(
            y,
            fmin=50,
            fmax=500,
            sr=sr,
            frame_length=2048,
            hop_length=160
        )

        # Filter valid F0 values
        f0_valid = f0[~np.isnan(f0)]

        if len(f0_valid) < 5:
            return None

        # F0 statistics
        f0_mean = np.mean(f0_valid)
        f0_std = np.std(f0_valid)
        f0_range = np.max(f0_valid) - np.min(f0_valid)

        # VAD using energy
        frame_length = int(0.025 * sr)  # 25ms
        hop_length = int(0.010 * sr)    # 10ms

        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
        threshold = np.mean(rms) * 0.5

        voiced_frames = np.sum(rms > threshold)
        total_frames = len(rms)

        voiced_ratio = voiced_frames / total_frames if total_frames > 0 else 0
        pause_ratio = 1 - voiced_ratio

        # Energy statistics
        energy_mean = np.mean(rms)
        energy_std = np.std(rms)

        # Jitter (from F0 values)
        jitter = compute_jitter_local(f0_valid)

        # Shimmer (from frame amplitudes)
        # Extract amplitude at each voiced frame
        amplitudes = []
        for i, voiced in enumerate(voiced_flag):
            if voiced and not np.isnan(f0[i]):
                start = i * 160
                end = min(start + 2048, len(y))
                if end > start:
                    amp = np.sqrt(np.mean(y[start:end] ** 2))
                    amplitudes.append(amp)

        shimmer = compute_shimmer_local(np.array(amplitudes)) if len(amplitudes) > 1 else 0

        # HNR (average over voiced segments)
        hnr_values = []
        for i, voiced in enumerate(voiced_flag):
            if voiced and not np.isnan(f0[i]):
                start = i * 160
                end = min(start + 2048, len(y))
                if end - start > 1000:
                    hnr = compute_hnr(y[start:end], sr, f0[i])
                    if hnr > 0 and hnr < 50:  # Valid range
                        hnr_values.append(hnr)

        hnr_mean = np.mean(hnr_values) if hnr_values else 0

        # SNR (voiced RMS / unvoiced RMS)
        voiced_rms = np.mean(rms[rms > threshold]) if np.any(rms > threshold) else 1e-10
        unvoiced_rms = np.mean(rms[rms <= threshold]) if np.any(rms <= threshold) else 1e-10
        snr = 20 * np.log10(voiced_rms / unvoiced_rms)

        return {
            'f0_mean_hz': f0_mean,
            'f0_std_hz': f0_std,
            'f0_range_hz': f0_range,
            'pause_ratio': pause_ratio,
            'voiced_ratio': voiced_ratio,
            'energy_mean': energy_mean,
            'energy_std': energy_std,
            'jitter': jitter,
            'shimmer': shimmer,
            'hnr_mean': hnr_mean,
            'snr': snr,
            'duration_sec': duration
        }

    except Exception as e:
        print(f"Error processing {audio_path}: {e}")
        return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Extract Python features for linkage validation")
    parser.add_argument("--corpus", default="../../datasets/eatd-corpus-data/EATD-Corpus",
                       help="Path to EATD-Corpus")
    parser.add_argument("--output", default="results/eatd_python_features.csv",
                       help="Output CSV path")
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    corpus_path = (script_dir / args.corpus).resolve()
    output_path = (script_dir / args.output).resolve()

    print(f"Corpus: {corpus_path}")
    print(f"Output: {output_path}")

    # Load participants
    print("\nLoading EATD-Corpus...")
    participants = load_eatd_corpus(str(corpus_path))
    print(f"  {len(participants)} participants")

    # Extract features
    print("\nExtracting Python features...")
    results = []

    total_files = sum(len(p.audio_files) for p in participants)
    processed = 0

    for p in participants:
        for audio_file in p.audio_files:
            processed += 1
            emotion = Path(audio_file).stem.replace('_out', '')
            session_id = f"{p.split}_{p.id}_{emotion}"

            if processed % 50 == 0:
                print(f"  Progress: {processed}/{total_files}")

            features = extract_features_python(audio_file)

            if features:
                features['session_id'] = session_id
                results.append(features)

    # Save results
    df = pd.DataFrame(results)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"\nExtracted {len(df)} samples")
    print(f"Saved to: {output_path}")

    return 0


if __name__ == "__main__":
    exit(main())
