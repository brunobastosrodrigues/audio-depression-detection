import numpy as np
import os
import librosa
from audio_utils import audio_bytes_to_nparray
from datetime import datetime, timezone, timedelta
import opensmile
from core.extractors.f0 import get_f0_avg, get_f0_std, get_f0_range
from core.extractors.hnr import get_hnr_mean
from core.extractors.jitter import get_jitter
from core.extractors.shimmer import get_shimmer
from core.extractors.snr import get_snr
from core.extractors.rms_energy import get_rms_energy_range, get_rms_energy_std
from core.extractors.formants import get_formant_f1_frequencies
from core.extractors.spectral_flatness import get_spectral_flatness
from core.extractors.myprosody_extractors import myprosody_extractors_handler
from core.extractors.temporal_modulation import get_temporal_modulation
from core.extractors.spectral_modulation import get_spectral_modulation
from core.extractors.voice_onset_time import get_vot
from core.extractors.glottal_pulse_rate import get_glottal_pulse_rate
from core.extractors.psd_subbands import get_psd_subbands
from core.extractors.voicing_states import (
    classify_voicing_states,
    get_t13_voiced_to_silence,
    compute_voiced16_20_feature,
)
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
        # ----------------------------
        
        # Define tasks for parallel execution
        # Format: (key, function, args)
        feature_tasks = [
            ("f0_avg", get_f0_avg, (features_LLD, audio_np, sample_rate)),
            ("f0_std", get_f0_std, (features_LLD, audio_np, sample_rate)),
            ("f0_range", get_f0_range, (features_LLD, audio_np, sample_rate)),
            ("hnr_mean", get_hnr_mean, (features_LLD,)),
            ("jitter", get_jitter, (features_LLD,)),
            ("shimmer", get_shimmer, (features_LLD,)),
            ("snr", get_snr, (audio_np, rms_series)),
            ("rms_energy_range", get_rms_energy_range, (rms_series,)),
            ("rms_energy_std", get_rms_energy_std, (rms_series,)),
            ("formant_f1_frequencies", get_formant_f1_frequencies, (features_LLD,)),
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

        # Use ThreadPoolExecutor to run tasks in parallel
        results = {}
        with ThreadPoolExecutor(max_workers=min(len(feature_tasks), 8)) as executor:
            future_to_key = {
                executor.submit(fn, *args): key for key, fn, args in feature_tasks
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
                if val is None: return default
                if hasattr(val, "values"): # Handle pandas Series from opensmile
                    return float(val.values[0])
                if isinstance(val, (list, np.ndarray)) and len(val) > 0:
                    return float(val[0])
                return float(val)
            except:
                return default

        # Prepare metrics as a flat dictionary
        psd = results.get("psd_subbands", {}) or {}
        
        flat_metrics = {
            "f0_avg": safe_float(results.get("f0_avg")),
            "f0_std": safe_float(results.get("f0_std")),
            "f0_range": safe_float(results.get("f0_range")),
            "hnr_mean": safe_float(results.get("hnr_mean")),
            "jitter": safe_float(results.get("jitter")),
            "shimmer": safe_float(results.get("shimmer")),
            "snr": safe_float(results.get("snr")),
            "rms_energy_range": safe_float(results.get("rms_energy_range")),
            "rms_energy_std": safe_float(results.get("rms_energy_std")),
            "formant_f1_frequencies_mean": safe_float(results.get("formant_f1_frequencies")),
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
        }

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
            "metrics_data": metadata.get("quality_metrics", {}), # Use 'metrics_data' key for consistency with adapter
            "board_id": metadata.get("board_id"),
            "environment_id": metadata.get("environment_id"),
            "environment_name": metadata.get("environment_name"),
            "system_mode": metadata.get("system_mode", "live"),
        }

        return acoustic_feature_records, audio_quality_record