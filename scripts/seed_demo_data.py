#!/usr/bin/env python3
"""
Demo Data Seeder for iotsensing_demo database.

This script deletes the existing iotsensing_demo database and seeds it with
"Golden Data" - realistic depression symptom patterns for showcase purposes.

Usage:
    python scripts/seed_demo_data.py

    # Or with custom parameters:
    python scripts/seed_demo_data.py --days 60 --user-id 999
"""

import argparse
import random
from datetime import datetime, timedelta
from typing import Optional

from pymongo import MongoClient
import numpy as np


# DSM-5 Depression Indicators
INDICATORS = [
    "1_depressed_mood",
    "2_loss_of_interest",
    "3_significant_weight_changes",
    "4_insomnia_hypersomnia",
    "5_psychomotor_retardation_agitation",
    "6_fatigue_loss_of_energy",
    "7_feelings_of_worthlessness_guilt",
    "8_diminished_ability_to_think_or_concentrate",
    "9_recurrent_thoughts_of_death_or_being_suicidal",
]

CORE_INDICATORS = ["1_depressed_mood", "2_loss_of_interest"]

# Acoustic metrics that map to indicators
ACOUSTIC_METRICS = [
    "mean_f0",
    "std_f0",
    "f0_range",
    "jitter_local",
    "shimmer_local",
    "hnr",
    "speech_rate",
    "pause_ratio",
    "energy_mean",
    "energy_std",
    "formant_f1_mean",
    "formant_f2_mean",
    "mfcc_1_mean",
    "mfcc_2_mean",
    "spectral_centroid",
    "spectral_rolloff",
    "zero_crossing_rate",
    "articulation_rate",
    "phonation_ratio",
    "intensity_mean",
]


def generate_depression_progression(
    days: int = 30,
    pattern: str = "gradual_onset"
) -> list[float]:
    """
    Generate a realistic depression severity progression over time.

    Patterns:
    - gradual_onset: Slowly increasing severity
    - episodic: Fluctuating with depressive episodes
    - recovery: High severity decreasing over time
    - stable_moderate: Consistent moderate depression
    """
    if pattern == "gradual_onset":
        # Start low, gradually increase with some noise
        base = np.linspace(0.2, 0.75, days)
        noise = np.random.normal(0, 0.05, days)
        return np.clip(base + noise, 0, 1).tolist()

    elif pattern == "episodic":
        # Fluctuating pattern with episodes
        base = 0.4 + 0.3 * np.sin(np.linspace(0, 3 * np.pi, days))
        noise = np.random.normal(0, 0.08, days)
        return np.clip(base + noise, 0, 1).tolist()

    elif pattern == "recovery":
        # Starting high, showing improvement
        base = np.linspace(0.8, 0.35, days)
        noise = np.random.normal(0, 0.06, days)
        return np.clip(base + noise, 0, 1).tolist()

    elif pattern == "stable_moderate":
        # Consistent moderate depression
        base = np.full(days, 0.55)
        noise = np.random.normal(0, 0.1, days)
        return np.clip(base + noise, 0, 1).tolist()

    else:
        raise ValueError(f"Unknown pattern: {pattern}")


def generate_indicator_scores(
    base_severity: float,
    day_index: int,
    total_days: int
) -> dict[str, float]:
    """
    Generate indicator scores based on overall severity.

    Core symptoms (1, 2) are always more prominent.
    Other symptoms vary with some correlation to severity.
    """
    scores = {}

    for indicator in INDICATORS:
        if indicator in CORE_INDICATORS:
            # Core symptoms track severity closely
            base = base_severity * random.uniform(0.9, 1.1)
        elif indicator == "9_recurrent_thoughts_of_death_or_being_suicidal":
            # This indicator only appears at high severity
            if base_severity > 0.7:
                base = (base_severity - 0.5) * random.uniform(0.6, 1.0)
            else:
                base = random.uniform(0, 0.15)
        else:
            # Other symptoms vary more independently
            correlation = random.uniform(0.5, 0.9)
            base = base_severity * correlation + random.uniform(-0.1, 0.1)

        scores[indicator] = max(0.0, min(1.0, base))

    return scores


def check_mdd_signal(indicator_scores: dict[str, float], threshold: float = 0.5) -> bool:
    """
    Check if MDD criteria are met:
    - At least 5 indicators above threshold
    - At least one core symptom (1 or 2) above threshold
    """
    active_count = sum(1 for v in indicator_scores.values() if v >= threshold)
    core_active = any(
        indicator_scores.get(ind, 0) >= threshold
        for ind in CORE_INDICATORS
    )
    return active_count >= 5 and core_active


def generate_acoustic_metrics(
    indicator_scores: dict[str, float],
    base_severity: float
) -> dict[str, float]:
    """
    Generate realistic acoustic metrics correlated with depression severity.

    Depression typically shows:
    - Lower mean F0 (fundamental frequency)
    - Reduced F0 variability
    - Higher jitter/shimmer
    - Lower HNR
    - Slower speech rate
    - More pauses
    - Lower energy
    """
    metrics = {}

    # F0 metrics (depression = lower, less variable)
    metrics["mean_f0"] = 180 - (base_severity * 50) + random.gauss(0, 10)
    metrics["std_f0"] = 40 - (base_severity * 20) + random.gauss(0, 5)
    metrics["f0_range"] = 100 - (base_severity * 40) + random.gauss(0, 10)

    # Voice quality (depression = higher jitter/shimmer, lower HNR)
    metrics["jitter_local"] = 0.01 + (base_severity * 0.02) + random.gauss(0, 0.003)
    metrics["shimmer_local"] = 0.03 + (base_severity * 0.04) + random.gauss(0, 0.01)
    metrics["hnr"] = 20 - (base_severity * 8) + random.gauss(0, 2)

    # Temporal metrics (depression = slower, more pauses)
    metrics["speech_rate"] = 4.5 - (base_severity * 1.5) + random.gauss(0, 0.3)
    metrics["pause_ratio"] = 0.15 + (base_severity * 0.2) + random.gauss(0, 0.03)
    metrics["articulation_rate"] = 5.0 - (base_severity * 1.2) + random.gauss(0, 0.4)
    metrics["phonation_ratio"] = 0.7 - (base_severity * 0.15) + random.gauss(0, 0.05)

    # Energy metrics (depression = lower energy)
    metrics["energy_mean"] = 0.5 - (base_severity * 0.2) + random.gauss(0, 0.05)
    metrics["energy_std"] = 0.15 - (base_severity * 0.05) + random.gauss(0, 0.02)
    metrics["intensity_mean"] = 65 - (base_severity * 10) + random.gauss(0, 3)

    # Formants (slight changes with depression)
    metrics["formant_f1_mean"] = 500 + random.gauss(0, 30)
    metrics["formant_f2_mean"] = 1500 + random.gauss(0, 50)

    # MFCCs (abstract features)
    metrics["mfcc_1_mean"] = -5 + (base_severity * 2) + random.gauss(0, 1)
    metrics["mfcc_2_mean"] = 3 - (base_severity * 1) + random.gauss(0, 0.5)

    # Spectral features
    metrics["spectral_centroid"] = 2000 - (base_severity * 300) + random.gauss(0, 100)
    metrics["spectral_rolloff"] = 4000 - (base_severity * 500) + random.gauss(0, 200)
    metrics["zero_crossing_rate"] = 0.05 + random.gauss(0, 0.01)

    return metrics


def generate_phq9_submission(
    indicator_scores: dict[str, float],
    timestamp: datetime
) -> dict:
    """Generate a PHQ-9 submission correlated with indicator scores."""

    # Map indicators to PHQ-9 questions
    indicator_to_question = {
        "2_loss_of_interest": "q1",
        "1_depressed_mood": "q2",
        "4_insomnia_hypersomnia": "q3",
        "6_fatigue_loss_of_energy": "q4",
        "3_significant_weight_changes": "q5",
        "7_feelings_of_worthlessness_guilt": "q6",
        "8_diminished_ability_to_think_or_concentrate": "q7",
        "5_psychomotor_retardation_agitation": "q8",
        "9_recurrent_thoughts_of_death_or_being_suicidal": "q9",
    }

    raw_scores = {}
    phq9_scores = {}

    for indicator, question in indicator_to_question.items():
        score = indicator_scores.get(indicator, 0)
        # Convert 0-1 score to 0-3 PHQ-9 scale with some noise
        phq_value = int(round(score * 3 + random.uniform(-0.3, 0.3)))
        phq_value = max(0, min(3, phq_value))
        raw_scores[question] = phq_value
        phq9_scores[indicator] = phq_value

    total_score = sum(raw_scores.values())

    # Determine severity
    if total_score <= 4:
        severity = "Minimal"
    elif total_score <= 9:
        severity = "Mild"
    elif total_score <= 14:
        severity = "Moderate"
    elif total_score <= 19:
        severity = "Moderately Severe"
    else:
        severity = "Severe"

    # Functional impact correlates with total score
    if total_score <= 9:
        impact_score = random.choice([0, 1])
    elif total_score <= 14:
        impact_score = random.choice([1, 2])
    else:
        impact_score = random.choice([2, 3])

    impact_labels = [
        "Not difficult at all",
        "Somewhat difficult",
        "Very difficult",
        "Extremely difficult"
    ]

    return {
        "user_id": "demo_user",
        "phq9_scores": phq9_scores,
        "raw_scores": raw_scores,
        "total_score": total_score,
        "severity": severity,
        "functional_impact": {
            "score": impact_score,
            "label": impact_labels[impact_score]
        },
        "timestamp": timestamp,
        "system_mode": "demo",
    }


def seed_demo_database(
    mongo_uri: str = "mongodb://localhost:27017",
    days: int = 30,
    user_id: str = "demo_user",
    pattern: str = "gradual_onset",
    samples_per_day: int = 10,
    verbose: bool = True
):
    """
    Seed the iotsensing_demo database with golden demo data.

    Args:
        mongo_uri: MongoDB connection URI
        days: Number of days of data to generate
        user_id: Demo user ID
        pattern: Depression progression pattern
        samples_per_day: Number of raw metric samples per day
        verbose: Print progress messages
    """
    client = MongoClient(mongo_uri)
    db_name = "iotsensing_demo"

    # Step 1: Drop existing demo database
    if verbose:
        print(f"Dropping existing {db_name} database...")
    client.drop_database(db_name)

    db = client[db_name]

    # Step 2: Generate severity progression
    if verbose:
        print(f"Generating {days}-day depression progression ({pattern})...")
    severities = generate_depression_progression(days, pattern)

    # Step 3: Generate data for each day
    end_date = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=days)

    raw_metrics = []
    aggregated_metrics = []
    contextual_metrics = []
    indicator_scores_list = []
    phq9_submissions = []

    if verbose:
        print("Generating daily data...")

    for day_idx in range(days):
        current_date = start_date + timedelta(days=day_idx)
        severity = severities[day_idx]

        # Generate indicator scores for this day
        day_indicators = generate_indicator_scores(severity, day_idx, days)
        mdd_signal = check_mdd_signal(day_indicators)

        # Generate raw metrics (multiple samples per day)
        daily_raw = []
        for sample_idx in range(samples_per_day):
            sample_time = current_date + timedelta(
                hours=random.randint(8, 22),
                minutes=random.randint(0, 59)
            )

            acoustic = generate_acoustic_metrics(day_indicators, severity)

            for metric_name, metric_value in acoustic.items():
                raw_metrics.append({
                    "user_id": user_id,
                    "metric_name": metric_name,
                    "metric_value": metric_value,
                    "timestamp": sample_time,
                    "system_mode": "demo",
                })
                daily_raw.append((metric_name, metric_value))

        # Generate aggregated metrics (daily average)
        metric_values = {}
        for name, value in daily_raw:
            if name not in metric_values:
                metric_values[name] = []
            metric_values[name].append(value)

        for metric_name, values in metric_values.items():
            aggregated_metrics.append({
                "user_id": user_id,
                "metric_name": metric_name,
                "metric_value": np.mean(values),
                "timestamp": current_date,
                "system_mode": "demo",
            })

        # Generate contextual metrics (EMA-smoothed)
        # Use exponential moving average simulation
        alpha = 0.3  # EMA smoothing factor
        for metric_name, values in metric_values.items():
            # Simulate EMA smoothing
            ema_value = np.mean(values)
            if day_idx > 0:
                # Blend with previous (simulated)
                prev_severity = severities[day_idx - 1]
                prev_acoustic = generate_acoustic_metrics({}, prev_severity)
                if metric_name in prev_acoustic:
                    ema_value = alpha * ema_value + (1 - alpha) * prev_acoustic[metric_name]

            contextual_metrics.append({
                "user_id": user_id,
                "metric_name": metric_name,
                "metric_value": ema_value,
                "timestamp": current_date,
                "context_window": "7d",
                "smoothing_alpha": alpha,
                "system_mode": "demo",
            })

        # Generate indicator scores
        indicator_scores_list.append({
            "user_id": user_id,
            "indicator_scores": day_indicators,
            "mdd_signal": mdd_signal,
            "timestamp": current_date,
            "system_mode": "demo",
        })

        # Generate PHQ-9 submission (weekly, on Sundays)
        if current_date.weekday() == 6:  # Sunday
            phq9 = generate_phq9_submission(day_indicators, current_date)
            phq9["user_id"] = user_id
            phq9_submissions.append(phq9)

    # Step 4: Insert all data
    if verbose:
        print(f"Inserting {len(raw_metrics)} raw_metrics...")
    if raw_metrics:
        db["raw_metrics"].insert_many(raw_metrics)

    if verbose:
        print(f"Inserting {len(aggregated_metrics)} aggregated_metrics...")
    if aggregated_metrics:
        db["aggregated_metrics"].insert_many(aggregated_metrics)

    if verbose:
        print(f"Inserting {len(contextual_metrics)} contextual_metrics...")
    if contextual_metrics:
        db["contextual_metrics"].insert_many(contextual_metrics)

    if verbose:
        print(f"Inserting {len(indicator_scores_list)} indicator_scores...")
    if indicator_scores_list:
        db["indicator_scores"].insert_many(indicator_scores_list)

    if verbose:
        print(f"Inserting {len(phq9_submissions)} phq9_submissions...")
    if phq9_submissions:
        db["phq9_submissions"].insert_many(phq9_submissions)

    # Step 5: Create baseline
    baseline = {
        "user_id": user_id,
        "schema_version": 2,
        "context_partitions": {
            "default": {
                metric: {
                    "mean": np.mean([m["metric_value"] for m in raw_metrics if m["metric_name"] == metric]),
                    "std": np.std([m["metric_value"] for m in raw_metrics if m["metric_name"] == metric]),
                    "count": len([m for m in raw_metrics if m["metric_name"] == metric]),
                }
                for metric in ACOUSTIC_METRICS
            }
        },
        "timestamp": datetime.utcnow(),
        "system_mode": "demo",
    }

    if verbose:
        print("Inserting baseline...")
    db["baseline"].insert_one(baseline)

    # Step 6: Create indexes
    if verbose:
        print("Creating indexes...")
    for collection in ["raw_metrics", "aggregated_metrics", "contextual_metrics", "indicator_scores"]:
        db[collection].create_index([("user_id", 1), ("timestamp", -1)])
    db["phq9_submissions"].create_index([("user_id", 1), ("timestamp", -1)])
    db["baseline"].create_index([("user_id", 1)])

    # Summary
    if verbose:
        print("\n" + "=" * 50)
        print("Demo data seeding complete!")
        print("=" * 50)
        print(f"Database: {db_name}")
        print(f"User ID: {user_id}")
        print(f"Days of data: {days}")
        print(f"Pattern: {pattern}")
        print(f"Raw metrics: {len(raw_metrics)}")
        print(f"Aggregated metrics: {len(aggregated_metrics)}")
        print(f"Contextual metrics: {len(contextual_metrics)}")
        print(f"Indicator scores: {len(indicator_scores_list)}")
        print(f"PHQ-9 submissions: {len(phq9_submissions)}")

        # Show MDD signal days
        mdd_days = sum(1 for r in indicator_scores_list if r["mdd_signal"])
        print(f"Days with MDD signal: {mdd_days}/{days}")
        print("=" * 50)

    client.close()
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Seed the iotsensing_demo database with golden demo data."
    )
    parser.add_argument(
        "--mongo-uri",
        default="mongodb://localhost:27017",
        help="MongoDB connection URI (default: mongodb://localhost:27017)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days of data to generate (default: 30)"
    )
    parser.add_argument(
        "--user-id",
        default="demo_user",
        help="Demo user ID (default: demo_user)"
    )
    parser.add_argument(
        "--pattern",
        choices=["gradual_onset", "episodic", "recovery", "stable_moderate"],
        default="gradual_onset",
        help="Depression progression pattern (default: gradual_onset)"
    )
    parser.add_argument(
        "--samples-per-day",
        type=int,
        default=10,
        help="Raw metric samples per day (default: 10)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress messages"
    )

    args = parser.parse_args()

    seed_demo_database(
        mongo_uri=args.mongo_uri,
        days=args.days,
        user_id=args.user_id,
        pattern=args.pattern,
        samples_per_day=args.samples_per_day,
        verbose=not args.quiet
    )


if __name__ == "__main__":
    main()
