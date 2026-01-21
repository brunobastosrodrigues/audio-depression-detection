#!/usr/bin/env python3
"""
eGeMAPS Baseline Comparison

Compares our C feature extractor against the eGeMAPS (extended Geneva Minimalistic
Acoustic Parameter Set) baseline used in AVEC challenges.

This provides the baseline comparison required for top-tier publication.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import warnings
warnings.filterwarnings('ignore')

try:
    import opensmile
    OPENSMILE_AVAILABLE = True
except ImportError:
    OPENSMILE_AVAILABLE = False
    print("Warning: opensmile not installed. Run: pip install opensmile")


def extract_egemaps_features(audio_path: Path) -> dict:
    """Extract eGeMAPS features using openSMILE."""
    if not OPENSMILE_AVAILABLE:
        return None

    smile = opensmile.Smile(
        feature_set=opensmile.FeatureSet.eGeMAPSv02,
        feature_level=opensmile.FeatureLevel.Functionals,
    )

    try:
        features = smile.process_file(str(audio_path))
        return features.iloc[0].to_dict()
    except Exception as e:
        print(f"Error processing {audio_path}: {e}")
        return None


def extract_egemaps_from_dataset(corpus_path: Path, output_csv: Path):
    """Extract eGeMAPS features from EATD-Corpus."""
    if not OPENSMILE_AVAILABLE:
        print("opensmile not available")
        return None

    smile = opensmile.Smile(
        feature_set=opensmile.FeatureSet.eGeMAPSv02,
        feature_level=opensmile.FeatureLevel.Functionals,
    )

    results = []

    for split in ['train', 'validation']:
        split_dir = corpus_path / split
        if not split_dir.exists():
            continue

        for pid_dir in sorted(split_dir.iterdir()):
            if not pid_dir.is_dir():
                continue

            pid = pid_dir.name

            # Get label
            label_file = pid_dir / 'new_label.txt'
            if not label_file.exists():
                continue
            sds_score = float(label_file.read_text().strip())
            is_depressed = sds_score > 53

            # Process each audio file
            for audio_file in pid_dir.glob('*.wav'):
                if '_out' in audio_file.name:  # Skip output files
                    continue

                try:
                    features = smile.process_file(str(audio_file))
                    row = features.iloc[0].to_dict()
                    row['session_id'] = f"{split}_{pid}_{audio_file.stem}"
                    row['participant_id'] = pid
                    row['split'] = split
                    row['audio_type'] = audio_file.stem
                    row['sds_score'] = sds_score
                    row['is_depressed'] = is_depressed
                    results.append(row)
                except Exception as e:
                    print(f"Error: {audio_file}: {e}")

    if results:
        df = pd.DataFrame(results)
        df.to_csv(output_csv, index=False)
        print(f"Saved {len(df)} samples to {output_csv}")
        return df
    return None


def load_our_features(csv_path: Path) -> pd.DataFrame:
    """Load our C-extracted features."""
    return pd.read_csv(csv_path)


def compute_classification_auc(features_df: pd.DataFrame, feature_cols: list,
                                label_col: str = 'is_depressed') -> tuple:
    """Compute AUC using logistic regression with cross-validation."""
    X = features_df[feature_cols].values
    y = features_df[label_col].astype(int).values

    # Handle NaN/Inf
    X = np.nan_to_num(X, nan=0, posinf=0, neginf=0)

    # Remove constant features
    valid_cols = np.std(X, axis=0) > 1e-10
    X = X[:, valid_cols]

    if X.shape[1] == 0:
        return 0.5, 0.0

    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('clf', LogisticRegression(max_iter=1000, C=1.0, random_state=42))
    ])

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(pipeline, X, y, cv=cv, scoring='roc_auc')

    return scores.mean(), scores.std()


def compute_effect_sizes(df: pd.DataFrame, features: list, label_col: str = 'is_depressed') -> dict:
    """Compute Cohen's d for each feature."""
    results = {}

    dep = df[df[label_col] == True]
    nondep = df[df[label_col] == False]

    for feat in features:
        if feat not in df.columns:
            continue

        d_vals = dep[feat].dropna().values
        nd_vals = nondep[feat].dropna().values

        if len(d_vals) < 5 or len(nd_vals) < 5:
            continue

        # Cohen's d
        pooled_std = np.sqrt(((len(d_vals)-1)*np.var(d_vals, ddof=1) +
                              (len(nd_vals)-1)*np.var(nd_vals, ddof=1)) /
                             (len(d_vals) + len(nd_vals) - 2))

        if pooled_std > 1e-10:
            d = (np.mean(d_vals) - np.mean(nd_vals)) / pooled_std
        else:
            d = 0.0

        # t-test
        t, p = stats.ttest_ind(d_vals, nd_vals)

        results[feat] = {
            'cohens_d': d,
            'p_value': p,
            'dep_mean': np.mean(d_vals),
            'nondep_mean': np.mean(nd_vals)
        }

    return results


def compare_baselines(egemaps_df: pd.DataFrame, our_df: pd.DataFrame):
    """Compare eGeMAPS baseline with our features."""
    print("\n" + "="*80)
    print("eGeMAPS BASELINE COMPARISON")
    print("="*80)

    # Sample sizes
    print("\n## Dataset Summary")
    print("-" * 60)
    print(f"eGeMAPS samples: {len(egemaps_df)} ({egemaps_df['is_depressed'].sum()} depressed)")
    print(f"Our C features:  {len(our_df)} ({our_df['is_depressed'].sum()} depressed)")

    # Get eGeMAPS feature columns (exclude metadata)
    metadata_cols = ['session_id', 'participant_id', 'split', 'audio_type',
                     'sds_score', 'is_depressed', 'start', 'end']
    egemaps_features = [c for c in egemaps_df.columns if c not in metadata_cols]

    # Our features
    our_features = ['f0_mean_hz', 'f0_std_hz', 'pause_ratio', 'energy_std',
                    'jitter', 'shimmer', 'hnr_mean', 'snr']
    our_features = [f for f in our_features if f in our_df.columns]

    print(f"\neGeMAPS features: {len(egemaps_features)}")
    print(f"Our features: {len(our_features)}")

    # Classification comparison
    print("\n## Classification Performance (5-fold CV)")
    print("-" * 60)

    egemaps_auc, egemaps_std = compute_classification_auc(
        egemaps_df, egemaps_features, 'is_depressed')

    our_auc, our_std = compute_classification_auc(
        our_df, our_features, 'is_depressed')

    print(f"{'Method':<30} {'AUC':>10} {'Std':>10}")
    print("-" * 60)
    print(f"{'eGeMAPS (88 features)':<30} {egemaps_auc:>10.3f} {egemaps_std:>10.3f}")
    print(f"{'Our C features (8 features)':<30} {our_auc:>10.3f} {our_std:>10.3f}")
    print(f"{'Delta (Our - eGeMAPS)':<30} {our_auc - egemaps_auc:>+10.3f}")

    # Efficiency ratio
    efficiency = (our_auc / egemaps_auc) * 100
    feature_ratio = len(our_features) / len(egemaps_features) * 100

    print(f"\n## Efficiency Analysis")
    print("-" * 60)
    print(f"Performance retention: {efficiency:.1f}% of eGeMAPS AUC")
    print(f"Feature reduction:     {feature_ratio:.1f}% of eGeMAPS features ({len(our_features)}/{len(egemaps_features)})")
    print(f"Efficiency ratio:      {efficiency/feature_ratio:.2f}x (performance/features)")

    # Effect size comparison for comparable features
    print("\n## Effect Size Comparison (Comparable Features)")
    print("-" * 80)

    # Map our features to eGeMAPS equivalents
    feature_mapping = {
        'f0_mean_hz': 'F0semitoneFrom27.5Hz_sma3nz_amean',
        'f0_std_hz': 'F0semitoneFrom27.5Hz_sma3nz_stddevNorm',
        'jitter': 'jitterLocal_sma3nz_amean',
        'shimmer': 'shimmerLocaldB_sma3nz_amean',
        'hnr_mean': 'HNRdBACF_sma3nz_amean',
    }

    our_effects = compute_effect_sizes(our_df, our_features)
    egemaps_effects = compute_effect_sizes(egemaps_df, list(feature_mapping.values()))

    print(f"{'Feature':<20} {'Our d':>10} {'eGeMAPS d':>12} {'Difference':>12}")
    print("-" * 60)

    for our_feat, eg_feat in feature_mapping.items():
        if our_feat in our_effects and eg_feat in egemaps_effects:
            our_d = our_effects[our_feat]['cohens_d']
            eg_d = egemaps_effects[eg_feat]['cohens_d']
            diff = our_d - eg_d
            print(f"{our_feat:<20} {our_d:>+10.3f} {eg_d:>+12.3f} {diff:>+12.3f}")

    # Top discriminating eGeMAPS features
    print("\n## Top 10 Discriminating eGeMAPS Features")
    print("-" * 80)

    all_effects = compute_effect_sizes(egemaps_df, egemaps_features)
    sorted_effects = sorted(all_effects.items(), key=lambda x: abs(x[1]['cohens_d']), reverse=True)

    print(f"{'Feature':<50} {'Cohen d':>10} {'p-value':>12}")
    print("-" * 80)
    for feat, stats_dict in sorted_effects[:10]:
        print(f"{feat[:48]:<50} {stats_dict['cohens_d']:>+10.3f} {stats_dict['p_value']:>12.4f}")

    # Summary
    print("\n" + "="*80)
    print("BASELINE COMPARISON SUMMARY")
    print("="*80)

    if our_auc >= egemaps_auc * 0.9:
        verdict = "COMPETITIVE"
        explanation = "Our edge features achieve ≥90% of eGeMAPS performance"
    elif our_auc >= egemaps_auc * 0.8:
        verdict = "ACCEPTABLE"
        explanation = "Our edge features achieve 80-90% of eGeMAPS performance"
    else:
        verdict = "GAP EXISTS"
        explanation = f"Our features achieve {efficiency:.0f}% of eGeMAPS, trade-off for edge constraints"

    print(f"""
Verdict: {verdict}

Key Findings:
1. eGeMAPS (88 features): AUC = {egemaps_auc:.3f}
2. Our C features (8 features): AUC = {our_auc:.3f}
3. {explanation}
4. Feature reduction: {100-feature_ratio:.0f}% fewer features

Publication Framing:
- If competitive: "Our edge-constrained features match eGeMAPS with 9% of the features"
- If acceptable: "We achieve {efficiency:.0f}% of eGeMAPS performance while enabling edge deployment"
- If gap exists: "We trade {100-efficiency:.0f}% accuracy for privacy-preserving edge computation"
""")

    return {
        'egemaps_auc': egemaps_auc,
        'our_auc': our_auc,
        'delta': our_auc - egemaps_auc,
        'efficiency': efficiency,
        'verdict': verdict
    }


def main():
    script_dir = Path(__file__).parent
    corpus_path = script_dir / "../../datasets/eatd-corpus-data/EATD-Corpus"

    # Output paths
    egemaps_csv = script_dir / "results/egemaps_features.csv"
    our_csv = script_dir / "results/eatd_c_features.csv"

    # Check if eGeMAPS features already extracted
    if egemaps_csv.exists():
        print(f"Loading existing eGeMAPS features from {egemaps_csv}")
        egemaps_df = pd.read_csv(egemaps_csv)
    else:
        print("Extracting eGeMAPS features (this may take a few minutes)...")
        egemaps_df = extract_egemaps_from_dataset(corpus_path, egemaps_csv)

        if egemaps_df is None:
            print("Failed to extract eGeMAPS features")
            return 1

    # Load our features
    if not our_csv.exists():
        print(f"Error: Our features not found at {our_csv}")
        print("Run the C feature extractor first.")
        return 1

    our_df = pd.read_csv(our_csv)

    # Add is_depressed column if not present
    if 'is_depressed' not in our_df.columns:
        def get_label(session_id):
            parts = session_id.split('_')
            split, pid = parts[0], parts[1]
            label_file = corpus_path / split / pid / 'new_label.txt'
            if label_file.exists():
                return float(label_file.read_text().strip()) > 53
            return None
        our_df['is_depressed'] = our_df['session_id'].apply(get_label)
        our_df = our_df.dropna(subset=['is_depressed'])

    # Compare baselines
    results = compare_baselines(egemaps_df, our_df)

    # Save comparison results
    results_file = script_dir / "results/egemaps_comparison.json"
    import json
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {results_file}")

    return 0


if __name__ == "__main__":
    exit(main())
