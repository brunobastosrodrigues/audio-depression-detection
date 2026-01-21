#!/usr/bin/env python3
"""
Clinical Direction Validation for C Feature Extractor

This script validates that the C-extracted features show the same
clinical direction (depressed vs non-depressed) as expected from
the literature.

Ground truth: EATD-Corpus (Chinese depression dataset)
- 162 participants (30 depressed, 132 non-depressed)
- SDS score > 53 = depressed

Expected directions from literature:
- F0 mean: Lower in depressed (reduced prosodic range)
- F0 std: Lower in depressed (monotonous speech)
- Pause ratio: Higher in depressed (psychomotor retardation)
- Jitter: Higher in depressed (voice instability)
- Shimmer: Higher in depressed (voice instability)
- HNR: Lower in depressed (voice quality degradation)
"""

import os
import subprocess
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats
from dataclasses import dataclass
from typing import List, Dict, Tuple


@dataclass
class Participant:
    id: str
    sds_score: float
    is_depressed: bool
    audio_files: List[str]
    split: str  # 'train' or 'validation'


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

            # Read label
            label_file = pid_folder / 'new_label.txt'
            if not label_file.exists():
                continue

            try:
                sds_score = float(label_file.read_text().strip())
            except:
                continue

            # Find audio files (use preprocessed _out.wav)
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


def extract_features_c(audio_path: str, extractor_path: str) -> Dict:
    """Extract features using C extractor (single file mode)."""
    # For now, we'll use a batch approach
    # The C extractor outputs CSV, so we need to process per-file
    pass


def run_c_extractor_batch(participants: List[Participant],
                          extractor_dir: str,
                          output_csv: str) -> pd.DataFrame:
    """
    Run C extractor on all EATD-Corpus audio files.

    Creates a temporary directory structure and runs batch extraction.
    """
    import tempfile
    import shutil

    # Create temp directory with audio files
    with tempfile.TemporaryDirectory() as tmpdir:
        # Copy/link audio files to temp structure
        for p in participants:
            for i, audio_file in enumerate(p.audio_files):
                # Create unique ID: split_participant_emotion (to avoid duplicates)
                emotion = Path(audio_file).stem.replace('_out', '')
                pid = f"{p.split}_{p.id}_{emotion}"

                # Create session folder
                session_dir = Path(tmpdir) / pid
                session_dir.mkdir(exist_ok=True)

                # Link audio file (use symlink for speed)
                dst = session_dir / f"{pid}_AUDIO.wav"
                os.symlink(audio_file, dst)

        # Run C extractor
        extractor = Path(extractor_dir) / 'extract_features'
        if not extractor.exists():
            # Compile if needed
            subprocess.run([
                'gcc', '-O2', '-Wall', '-Isrc',
                'src/feature_extractor.c', 'src/yin_f0.c',
                'src/vad.c', 'src/voice_quality.c',
                'test/extract_batch.c',
                '-o', 'extract_features', '-lm'
            ], cwd=extractor_dir, check=True)

        # Run extraction
        result = subprocess.run(
            [str(extractor), tmpdir, output_csv],
            cwd=extractor_dir,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"Extraction error: {result.stderr}")
            return None

    # Load results
    if Path(output_csv).exists():
        return pd.read_csv(output_csv)
    return None


def compute_effect_size(group1: np.ndarray, group2: np.ndarray) -> float:
    """Compute Cohen's d effect size."""
    n1, n2 = len(group1), len(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)

    # Pooled standard deviation
    pooled_std = np.sqrt(((n1-1)*var1 + (n2-1)*var2) / (n1+n2-2))

    if pooled_std < 1e-10:
        return 0.0

    return (np.mean(group1) - np.mean(group2)) / pooled_std


def analyze_clinical_direction(features_df: pd.DataFrame,
                               participants: List[Participant]) -> pd.DataFrame:
    """
    Analyze whether features show expected clinical direction.

    Returns DataFrame with:
    - Feature name
    - Expected direction
    - Observed direction
    - Effect size (Cohen's d)
    - P-value
    - Match (True/False)
    """
    # Create participant lookup
    pid_to_depressed = {}
    for p in participants:
        for audio in p.audio_files:
            emotion = Path(audio).stem.replace('_out', '')
            pid = f"{p.split}_{p.id}_{emotion}"
            pid_to_depressed[pid] = p.is_depressed

    # Map features to labels
    features_df['session_id'] = features_df['session_id'].astype(str)
    features_df['is_depressed'] = features_df['session_id'].map(pid_to_depressed)

    # Drop unmapped
    features_df = features_df.dropna(subset=['is_depressed'])

    depressed = features_df[features_df['is_depressed'] == True]
    nondepressed = features_df[features_df['is_depressed'] == False]

    print(f"\nSamples: {len(depressed)} depressed, {len(nondepressed)} non-depressed")

    # Expected directions from literature
    expected_directions = {
        'f0_mean_hz': 'lower',      # Reduced prosodic variation
        'f0_std_hz': 'lower',       # Monotonous speech
        'f0_range_hz': 'lower',     # Reduced range
        'pause_ratio': 'higher',    # Psychomotor retardation
        'voiced_ratio': 'lower',    # More pauses
        'jitter': 'higher',         # Voice instability
        'jitter_rap': 'higher',
        'shimmer': 'higher',        # Amplitude perturbation
        'shimmer_apq3': 'higher',
        'hnr_mean': 'lower',        # Degraded voice quality
        'snr': 'lower',             # Potentially lower SNR
        'energy_std': 'lower',      # Reduced energy dynamics
    }

    results = []

    for feature, expected in expected_directions.items():
        if feature not in features_df.columns:
            continue

        dep_vals = depressed[feature].values
        nondep_vals = nondepressed[feature].values

        # Remove NaN
        dep_vals = dep_vals[~np.isnan(dep_vals)]
        nondep_vals = nondep_vals[~np.isnan(nondep_vals)]

        if len(dep_vals) < 5 or len(nondep_vals) < 5:
            continue

        # Statistics
        dep_mean = np.mean(dep_vals)
        nondep_mean = np.mean(nondep_vals)

        # T-test
        t_stat, p_value = stats.ttest_ind(dep_vals, nondep_vals)

        # Effect size
        effect_size = compute_effect_size(dep_vals, nondep_vals)

        # Observed direction
        if dep_mean < nondep_mean:
            observed = 'lower'
        elif dep_mean > nondep_mean:
            observed = 'higher'
        else:
            observed = 'same'

        # Match
        match = observed == expected

        results.append({
            'feature': feature,
            'dep_mean': dep_mean,
            'nondep_mean': nondep_mean,
            'expected': expected,
            'observed': observed,
            'effect_size': effect_size,
            'p_value': p_value,
            'match': match,
            'significant': p_value < 0.05
        })

    return pd.DataFrame(results)


def print_validation_report(results_df: pd.DataFrame):
    """Print formatted validation report."""
    print("\n" + "="*80)
    print("CLINICAL DIRECTION VALIDATION REPORT")
    print("="*80)
    print("\nGround Truth: EATD-Corpus (Chinese depression dataset)")
    print("Method: Compare C-extracted features between depressed vs non-depressed\n")

    print(f"{'Feature':<15} {'Expected':<10} {'Observed':<10} {'Cohen d':>10} {'p-value':>12} {'Match':>8}")
    print("-"*80)

    matches = 0
    significant_matches = 0

    for _, row in results_df.iterrows():
        match_str = "✓" if row['match'] else "✗"
        sig_str = "*" if row['significant'] else ""

        print(f"{row['feature']:<15} {row['expected']:<10} {row['observed']:<10} "
              f"{row['effect_size']:>+10.3f} {row['p_value']:>12.4f} {match_str:>7}{sig_str}")

        if row['match']:
            matches += 1
            if row['significant']:
                significant_matches += 1

    print("-"*80)
    total = len(results_df)
    print(f"\nDirection Match: {matches}/{total} ({100*matches/total:.1f}%)")
    print(f"Significant & Correct: {significant_matches}/{total} ({100*significant_matches/total:.1f}%)")

    # Overall verdict
    if matches >= total * 0.7:
        verdict = "✓ C EXTRACTOR PRESERVES CLINICAL VALIDITY"
    elif matches >= total * 0.5:
        verdict = "~ PARTIAL CLINICAL VALIDITY"
    else:
        verdict = "✗ CLINICAL VALIDITY CONCERNS"

    print(f"\nVerdict: {verdict}")
    print("="*80)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate C extractor clinical direction")
    parser.add_argument("--corpus", default="../../datasets/eatd-corpus-data/EATD-Corpus",
                       help="Path to EATD-Corpus")
    parser.add_argument("--extractor", default="c_feature_extractor",
                       help="Path to C extractor directory")
    parser.add_argument("--output", default="results/eatd_c_features.csv",
                       help="Output CSV path")
    args = parser.parse_args()

    # Resolve paths
    script_dir = Path(__file__).parent
    corpus_path = (script_dir / args.corpus).resolve()
    extractor_path = (script_dir / args.extractor).resolve()
    output_path = (script_dir / args.output).resolve()

    print(f"Corpus: {corpus_path}")
    print(f"Extractor: {extractor_path}")
    print(f"Output: {output_path}")

    # Load participants
    print("\nLoading EATD-Corpus...")
    participants = load_eatd_corpus(str(corpus_path))

    n_depressed = sum(1 for p in participants if p.is_depressed)
    n_nondepressed = len(participants) - n_depressed
    print(f"  {len(participants)} participants: {n_depressed} depressed, {n_nondepressed} non-depressed")

    n_audio = sum(len(p.audio_files) for p in participants)
    print(f"  {n_audio} audio files total")

    # Run C extraction
    print("\nExtracting features with C extractor...")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    features_df = run_c_extractor_batch(participants, str(extractor_path), str(output_path))

    if features_df is None or len(features_df) == 0:
        print("ERROR: Feature extraction failed")
        return 1

    print(f"  Extracted {len(features_df)} samples")

    # Analyze clinical direction
    print("\nAnalyzing clinical direction...")
    results = analyze_clinical_direction(features_df, participants)

    # Print report
    print_validation_report(results)

    # Save results
    results_path = output_path.parent / "clinical_validation_results.csv"
    results.to_csv(results_path, index=False)
    print(f"\nResults saved to: {results_path}")

    return 0


if __name__ == "__main__":
    exit(main())
