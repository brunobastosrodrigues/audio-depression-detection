"""
Metrics Computation Service with Dynamic Behavioral Phenotyping

This service orchestrates the extraction of acoustic metrics from audio
signals. It has been upgraded to support Dynamic Acoustic Phenotyping
for DSM-5 depression assessment.

Phase 1: Silent Expansion
- All legacy metrics are preserved for backward compatibility
- New dynamic metrics (CV, IQR, entropy) are added alongside legacy keys
- Interaction dynamics (silence_ratio, speech_velocity) added for psychomotor assessment
- MongoDB continues to receive flattened metric records

New Metric Categories:
1. F0 Dynamics: f0_avg (legacy), f0_std, f0_range, f0_cv, f0_iqr, f0_entropy
2. HNR Dynamics: hnr_mean (legacy), hnr_std, hnr_cv, hnr_iqr, hnr_entropy
3. RMS Dynamics: rms_energy_range (legacy), rms_energy_std (legacy),
                 rms_energy_mean, rms_energy_cv, rms_energy_iqr, rms_energy_entropy
4. Formant Dynamics: formant_f1_frequencies_mean (legacy), formant_f1_std,
                     formant_f1_cv, formant_f1_iqr, formant_f1_entropy
5. Interaction Dynamics: silence_ratio, speech_velocity, voiced_ratio,
                         unvoiced_ratio, pause_count_dynamic, pause_mean_duration,
                         pause_std_duration, pause_max_duration, pause_total_duration
"""

import numpy as np
import os
import librosa
from audio_utils import audio_bytes_to_nparray
from datetime import datetime, timezone, timedelta
import opensmile

# Dynamic extractor functions (Phase 1)
from core.extractors.f0 import get_f0_dynamic
from core.extractors.hnr import get_hnr_dynamic
from core.extractors.rms_energy import get_rms_energy_dynamic
from core.extractors.formants import get_formant_dynamic
from core.extractors.voicing_states import (
    classify_voicing_states,
    get_t13_voiced_to_silence,
    compute_voiced16_20_feature,
    get_interaction_dynamics,
)

# Legacy extractors (still used for some non-upgraded metrics)
from core.extractors.jitter import get_jitter
from core.extractors.shimmer import get_shimmer
from core.extractors.snr import get_snr
from core.extractors.spectral_flatness import get_spectral_flatness
from core.extractors.myprosody_extractors import myprosody_extractors_handler
from core.extractors.temporal_modulation import get_temporal_modulation
from core.extractors.spectral_modulation import get_spectral_modulation
from core.extractors.voice_onset_time import get_vot
from core.extractors.glottal_pulse_rate import get_glottal_pulse_rate
from core.extractors.psd_subbands import get_psd_subbands
from core.extractors.f2_transition_speed import get_f2_transition_speed
from core.extractors.myprosody_extractors import MyprosodyMetrics

from concurrent.futures import ThreadPoolExecutor, as_completed


class MetricsComputationService:
    def __init__(self):
        # SAFETY GUARD: Only enable time simulation if explicitly configured
        self.simulation_mode = os.getenv("SIMULATION_MODE", "false").lower() == "true"
        self.day_counter = 0

        if self.simulation_mode:
            print("⚠️ WARNING: SIMULATION MODE ENABLED. Timestamps will be artificial ⚠️")

        # Initialize OpenSMILE extractor once at startup
        # Optimization: Use a single comprehensive yet lightweight set (eGeMAPSv02)
        print("Initializing OpenSMILE model... this may take a moment.")
        self.smile_extractor = opensmile.Smile(
            feature_set=opensmile.FeatureSet.eGeMAPSv02,
            feature_level=opensmile.FeatureLevel.LowLevelDescriptors,
        )
        print("OpenSMILE model initialized.")

    def compute(self, audio_bytes, user_id, metadata: dict = None) -> list[dict]:
        """
        Compute all acoustic metrics from audio bytes.

        This method has been upgraded for Phase 1 "Silent Expansion":
        - Legacy metrics are preserved for backward compatibility
        - New dynamic metrics are added alongside legacy keys
        - All metrics are flattened into individual records for MongoDB

        Args:
            audio_bytes: Raw audio data
            user_id: User identifier
            metadata: Optional metadata dict with board_id, environment_id, etc.

        Returns:
            Tuple of (acoustic_feature_records, audio_quality_record)
        """
        metadata = metadata or {}

        # Convert audio data into correct format
        audio_np, sample_rate = audio_bytes_to_nparray(audio_bytes)
        audio_np = np.clip(audio_np, -1.0, 1.0)

        # Single OpenSMILE extraction (LLD level)
        # eGeMAPSv02 LLD contains F0, HNR, Jitter, Shimmer, Formants, etc.
        features_LLD = self.smile_extractor.process_signal(audio_np, sample_rate)

        # Manual RMS energy computation (much faster than OpenSMILE)
        # Using 20ms window and 10ms hop to match standard acoustic analysis
        frame_length = int(0.02 * sample_rate)
        hop_length = int(0.01 * sample_rate)
        rms_series = librosa.feature.rms(y=audio_np, frame_length=frame_length, hop_length=hop_length)[0]

        # ----------------------------
        # Extract features (Parallelized)
        # Phase 1: Use new dynamic extractors that return dictionaries
        # ----------------------------

        # Dynamic extractors (return dictionaries)
        dynamic_tasks = [
            ("f0_dynamic", get_f0_dynamic, (features_LLD, audio_np, sample_rate)),
            ("hnr_dynamic", get_hnr_dynamic, (features_LLD,)),
            ("rms_dynamic", get_rms_energy_dynamic, (rms_series,)),
            ("formant_dynamic", get_formant_dynamic, (features_LLD,)),
            ("interaction_dynamics", get_interaction_dynamics, (audio_np, sample_rate)),
        ]

        # Legacy extractors (return single values)
        legacy_tasks = [
            ("jitter", get_jitter, (features_LLD,)),
            ("shimmer", get_shimmer, (features_LLD,)),
            ("snr", get_snr, (audio_np, rms_series)),
            ("spectral_flatness", get_spectral_flatness, (audio_np,)),
            ("temporal_modulation", get_temporal_modulation, (audio_np, sample_rate)),
            ("spectral_modulation", get_spectral_modulation, (audio_np, sample_rate)),
            ("voice_onset_time", get_vot, (audio_np, sample_rate)),
            ("glottal_pulse_rate", get_glottal_pulse_rate, (audio_np, sample_rate)),
            ("psd_subbands", get_psd_subbands, (audio_np, sample_rate)),
            ("t13", get_t13_voiced_to_silence, (audio_np, sample_rate)),
            ("voiced_states", classify_voicing_states, (audio_np, sample_rate)),
            ("f2_transition_speed", get_f2_transition_speed, (audio_np, sample_rate)),
        ]

        all_tasks = dynamic_tasks + legacy_tasks

        # Use ThreadPoolExecutor to run tasks in parallel
        results = {}
        with ThreadPoolExecutor(max_workers=min(len(all_tasks), 8)) as executor:
            future_to_key = {
                executor.submit(fn, *args): key for key, fn, args in all_tasks
            }

            for future in as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    results[key] = future.result()
                except Exception as e:
                    print(f"Error extracting feature {key}: {e}")
                    results[key] = None

        # Post-processing for features that depend on other results
        if results.get("voiced_states") is not None:
            voiced16_20 = compute_voiced16_20_feature(results["voiced_states"])
        else:
            voiced16_20 = 0.0

        # Define which myprosody metrics should be returned
        myprosody_metrics_to_extract = [
            MyprosodyMetrics.RATE_OF_SPEECH,
            MyprosodyMetrics.ARTICULATION_RATE,
            MyprosodyMetrics.PAUSE_COUNT,
            MyprosodyMetrics.PAUSE_DURATION,
        ]

        myprosody_results = myprosody_extractors_handler(
            audio_np, sample_rate, myprosody_metrics_to_extract
        )

        # Helper to safely get result and handle potential None/Errors
        def safe_float(val, default=0.0):
            try:
                if val is None:
                    return default
                if hasattr(val, "values"):  # Handle pandas Series from opensmile
                    return float(val.values[0])
                if isinstance(val, (list, np.ndarray)) and len(val) > 0:
                    return float(val[0])
                return float(val)
            except:
                return default

        # ----------------------------
        # Flatten all metrics into a single dictionary
        # Phase 1: Combine dynamic dict results with legacy single values
        # ----------------------------
        flat_metrics = {}

        # Flatten dynamic extractor results (dictionaries)
        for dynamic_key in ["f0_dynamic", "hnr_dynamic", "rms_dynamic", "formant_dynamic", "interaction_dynamics"]:
            dynamic_result = results.get(dynamic_key)
            if isinstance(dynamic_result, dict):
                for metric_name, metric_value in dynamic_result.items():
                    flat_metrics[metric_name] = safe_float(metric_value)

        # Add legacy single-value metrics
        psd = results.get("psd_subbands", {}) or {}

        flat_metrics.update({
            "jitter": safe_float(results.get("jitter")),
            "shimmer": safe_float(results.get("shimmer")),
            "snr": safe_float(results.get("snr")),
            "spectral_flatness": safe_float(results.get("spectral_flatness")),
            "temporal_modulation": safe_float(results.get("temporal_modulation")),
            "spectral_modulation": safe_float(results.get("spectral_modulation")),
            "voice_onset_time": safe_float(results.get("voice_onset_time")),
            "glottal_pulse_rate": safe_float(results.get("glottal_pulse_rate")),
            "psd-4": safe_float(psd.get("psd-4")),
            "psd-5": safe_float(psd.get("psd-5")),
            "psd-7": safe_float(psd.get("psd-7")),
            "t13": safe_float(results.get("t13")),
            "voiced16_20": safe_float(voiced16_20),
            "f2_transition_speed": safe_float(results.get("f2_transition_speed")),
        })

        # Add myprosody results
        flat_metrics.update(myprosody_results)

        # SAFETY GUARD: Use real-time unless simulation is forced
        if self.simulation_mode:
            timestamp = datetime.now(timezone.utc) + timedelta(days=self.day_counter)
            self.day_counter += 1
        else:
            timestamp = datetime.now(timezone.utc)

        # Prepare acoustic feature records (for raw_metrics collection)
        acoustic_feature_records = []
        for metric_name, metric_value in flat_metrics.items():
            acoustic_feature_records.append({
                "user_id": user_id,
                "timestamp": timestamp,
                "metric_name": metric_name,
                "metric_value": metric_value,
                "origin": "metrics_computation",
                "board_id": metadata.get("board_id"),
                "environment_id": metadata.get("environment_id"),
                "environment_name": metadata.get("environment_name"),
                "system_mode": metadata.get("system_mode", "live"),
            })

        # Prepare audio quality metrics record (for audio_quality_metrics collection)
        audio_quality_record = {
            "user_id": user_id,
            "timestamp": timestamp,
            "metrics_data": metadata.get("quality_metrics", {}),
            "board_id": metadata.get("board_id"),
            "environment_id": metadata.get("environment_id"),
            "environment_name": metadata.get("environment_name"),
            "system_mode": metadata.get("system_mode", "live"),
        }

        return acoustic_feature_records, audio_quality_record
