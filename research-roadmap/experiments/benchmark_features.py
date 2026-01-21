#!/usr/bin/env python3
"""
Feature Extraction Latency Benchmark

Measures individual feature extraction times to identify:
1. Which features are fast enough for ESP32-S3 edge processing
2. Which features must stay on Pi 5 hub
3. Memory requirements per feature

Usage:
    python benchmark_features.py --audio-dir /path/to/audio --output results/feature_benchmark.json
"""

import argparse
import json
import os
import sys
import time
import tracemalloc
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable
import warnings

warnings.filterwarnings("ignore")

import numpy as np


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder for numpy types."""
    def default(self, obj):
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


# Try to import feature extractors
try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    print("Warning: librosa not available")

try:
    import opensmile
    OPENSMILE_AVAILABLE = True
except ImportError:
    OPENSMILE_AVAILABLE = False
    print("Warning: opensmile not available")

try:
    import parselmouth
    PARSELMOUTH_AVAILABLE = True
except ImportError:
    PARSELMOUTH_AVAILABLE = False
    print("Warning: parselmouth not available")


@dataclass
class FeatureBenchmarkResult:
    """Result of benchmarking a single feature."""
    feature_name: str
    category: str  # "edge_candidate", "hub_only", "unknown"
    mean_latency_ms: float
    std_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p95_latency_ms: float
    memory_peak_kb: float
    samples_tested: int
    edge_feasible: bool  # Can run on ESP32-S3?
    notes: str


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark."""
    sample_rate: int = 16000
    chunk_duration_s: float = 5.0
    num_iterations: int = 20
    warmup_iterations: int = 3
    # ESP32-S3 constraints
    esp32_max_latency_ms: float = 100.0  # Per 5s chunk
    esp32_max_memory_kb: float = 200.0   # Model + buffers


class FeatureExtractor:
    """Base class for feature extractors."""

    def __init__(self, name: str, category: str):
        self.name = name
        self.category = category  # "prosodic", "spectral", "voice_quality", "temporal"

    def extract(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Extract feature from audio. Override in subclass."""
        raise NotImplementedError

    def is_available(self) -> bool:
        """Check if dependencies are available."""
        return True


# ============== FEATURE EXTRACTORS ==============

class MFCCExtractor(FeatureExtractor):
    """MFCC extraction using librosa."""

    def __init__(self, n_mfcc: int = 13):
        super().__init__(f"mfcc_{n_mfcc}", "spectral")
        self.n_mfcc = n_mfcc

    def extract(self, audio: np.ndarray, sr: int) -> np.ndarray:
        mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=self.n_mfcc)
        return np.array([mfcc.mean(axis=1), mfcc.std(axis=1)]).flatten()

    def is_available(self) -> bool:
        return LIBROSA_AVAILABLE


class F0Extractor(FeatureExtractor):
    """Fundamental frequency (pitch) extraction."""

    def __init__(self, method: str = "yin"):
        super().__init__(f"f0_{method}", "prosodic")
        self.method = method

    def extract(self, audio: np.ndarray, sr: int) -> np.ndarray:
        if self.method == "yin":
            f0 = librosa.yin(audio, fmin=50, fmax=500, sr=sr)
        elif self.method == "pyin":
            f0, _, _ = librosa.pyin(audio, fmin=50, fmax=500, sr=sr)
        else:
            f0 = librosa.yin(audio, fmin=50, fmax=500, sr=sr)

        f0_valid = f0[f0 > 0]
        if len(f0_valid) == 0:
            return np.array([0, 0, 0, 0])

        return np.array([
            np.mean(f0_valid),
            np.std(f0_valid),
            np.min(f0_valid),
            np.max(f0_valid)
        ])

    def is_available(self) -> bool:
        return LIBROSA_AVAILABLE


class F0PraatExtractor(FeatureExtractor):
    """F0 extraction using Praat (Parselmouth)."""

    def __init__(self):
        super().__init__("f0_praat", "prosodic")

    def extract(self, audio: np.ndarray, sr: int) -> np.ndarray:
        snd = parselmouth.Sound(audio, sampling_frequency=sr)
        pitch = snd.to_pitch(time_step=0.01, pitch_floor=50, pitch_ceiling=500)
        f0 = pitch.selected_array["frequency"]
        f0_valid = f0[f0 > 0]

        if len(f0_valid) == 0:
            return np.array([0, 0, 0, 0])

        return np.array([
            np.mean(f0_valid),
            np.std(f0_valid),
            np.min(f0_valid),
            np.max(f0_valid)
        ])

    def is_available(self) -> bool:
        return PARSELMOUTH_AVAILABLE


class RMSEnergyExtractor(FeatureExtractor):
    """RMS energy extraction."""

    def __init__(self):
        super().__init__("rms_energy", "prosodic")

    def extract(self, audio: np.ndarray, sr: int) -> np.ndarray:
        rms = librosa.feature.rms(y=audio)[0]
        return np.array([
            np.mean(rms),
            np.std(rms),
            np.min(rms),
            np.max(rms)
        ])

    def is_available(self) -> bool:
        return LIBROSA_AVAILABLE


class ZCRExtractor(FeatureExtractor):
    """Zero-crossing rate extraction."""

    def __init__(self):
        super().__init__("zcr", "temporal")

    def extract(self, audio: np.ndarray, sr: int) -> np.ndarray:
        zcr = librosa.feature.zero_crossing_rate(audio)[0]
        return np.array([np.mean(zcr), np.std(zcr)])

    def is_available(self) -> bool:
        return LIBROSA_AVAILABLE


class SpectralCentroidExtractor(FeatureExtractor):
    """Spectral centroid extraction."""

    def __init__(self):
        super().__init__("spectral_centroid", "spectral")

    def extract(self, audio: np.ndarray, sr: int) -> np.ndarray:
        centroid = librosa.feature.spectral_centroid(y=audio, sr=sr)[0]
        return np.array([np.mean(centroid), np.std(centroid)])

    def is_available(self) -> bool:
        return LIBROSA_AVAILABLE


class SpectralFlatnessExtractor(FeatureExtractor):
    """Spectral flatness extraction."""

    def __init__(self):
        super().__init__("spectral_flatness", "spectral")

    def extract(self, audio: np.ndarray, sr: int) -> np.ndarray:
        flatness = librosa.feature.spectral_flatness(y=audio)[0]
        return np.array([np.mean(flatness), np.std(flatness)])

    def is_available(self) -> bool:
        return LIBROSA_AVAILABLE


class HNRExtractor(FeatureExtractor):
    """Harmonic-to-Noise Ratio using Parselmouth."""

    def __init__(self):
        super().__init__("hnr", "voice_quality")

    def extract(self, audio: np.ndarray, sr: int) -> np.ndarray:
        snd = parselmouth.Sound(audio, sampling_frequency=sr)
        harmonicity = snd.to_harmonicity()
        hnr = harmonicity.values[harmonicity.values != -200]  # Filter silence

        if len(hnr) == 0:
            return np.array([0, 0])

        return np.array([np.mean(hnr), np.std(hnr)])

    def is_available(self) -> bool:
        return PARSELMOUTH_AVAILABLE


class JitterExtractor(FeatureExtractor):
    """Jitter (pitch perturbation) using Parselmouth."""

    def __init__(self):
        super().__init__("jitter", "voice_quality")

    def extract(self, audio: np.ndarray, sr: int) -> np.ndarray:
        snd = parselmouth.Sound(audio, sampling_frequency=sr)
        try:
            point_process = parselmouth.praat.call(
                snd, "To PointProcess (periodic, cc)", 50, 500
            )
            jitter_local = parselmouth.praat.call(
                point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3
            )
            jitter_rap = parselmouth.praat.call(
                point_process, "Get jitter (rap)", 0, 0, 0.0001, 0.02, 1.3
            )
            return np.array([jitter_local, jitter_rap])
        except Exception:
            return np.array([0, 0])

    def is_available(self) -> bool:
        return PARSELMOUTH_AVAILABLE


class ShimmerExtractor(FeatureExtractor):
    """Shimmer (amplitude perturbation) using Parselmouth."""

    def __init__(self):
        super().__init__("shimmer", "voice_quality")

    def extract(self, audio: np.ndarray, sr: int) -> np.ndarray:
        snd = parselmouth.Sound(audio, sampling_frequency=sr)
        try:
            point_process = parselmouth.praat.call(
                snd, "To PointProcess (periodic, cc)", 50, 500
            )
            shimmer_local = parselmouth.praat.call(
                [snd, point_process], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6
            )
            shimmer_apq = parselmouth.praat.call(
                [snd, point_process], "Get shimmer (apq3)", 0, 0, 0.0001, 0.02, 1.3, 1.6
            )
            return np.array([shimmer_local, shimmer_apq])
        except Exception:
            return np.array([0, 0])

    def is_available(self) -> bool:
        return PARSELMOUTH_AVAILABLE


class FormantExtractor(FeatureExtractor):
    """Formant frequencies using Parselmouth."""

    def __init__(self):
        super().__init__("formants", "spectral")

    def extract(self, audio: np.ndarray, sr: int) -> np.ndarray:
        snd = parselmouth.Sound(audio, sampling_frequency=sr)
        formant = snd.to_formant_burg()

        f1_values = []
        f2_values = []

        for t in np.linspace(0, snd.duration, 50):
            f1 = formant.get_value_at_time(1, t)
            f2 = formant.get_value_at_time(2, t)
            if f1 and not np.isnan(f1):
                f1_values.append(f1)
            if f2 and not np.isnan(f2):
                f2_values.append(f2)

        return np.array([
            np.mean(f1_values) if f1_values else 0,
            np.std(f1_values) if f1_values else 0,
            np.mean(f2_values) if f2_values else 0,
            np.std(f2_values) if f2_values else 0,
        ])

    def is_available(self) -> bool:
        return PARSELMOUTH_AVAILABLE


class OpenSMILEExtractor(FeatureExtractor):
    """OpenSMILE eGeMAPS feature set."""

    def __init__(self):
        super().__init__("opensmile_egemaps", "comprehensive")
        if OPENSMILE_AVAILABLE:
            self.smile = opensmile.Smile(
                feature_set=opensmile.FeatureSet.eGeMAPSv02,
                feature_level=opensmile.FeatureLevel.Functionals,
            )

    def extract(self, audio: np.ndarray, sr: int) -> np.ndarray:
        features = self.smile.process_signal(audio, sr)
        return features.values.flatten()

    def is_available(self) -> bool:
        return OPENSMILE_AVAILABLE


# ============== BENCHMARK ENGINE ==============

def get_all_extractors() -> List[FeatureExtractor]:
    """Get all available feature extractors."""
    extractors = [
        # Edge candidates (lightweight)
        MFCCExtractor(n_mfcc=13),
        F0Extractor(method="yin"),
        RMSEnergyExtractor(),
        ZCRExtractor(),
        SpectralCentroidExtractor(),
        SpectralFlatnessExtractor(),

        # Hub candidates (heavier)
        F0Extractor(method="pyin"),
        F0PraatExtractor(),
        HNRExtractor(),
        JitterExtractor(),
        ShimmerExtractor(),
        FormantExtractor(),
        OpenSMILEExtractor(),
    ]

    return [e for e in extractors if e.is_available()]


def generate_test_audio(duration_s: float, sr: int = 16000) -> np.ndarray:
    """Generate synthetic speech-like audio for testing."""
    t = np.linspace(0, duration_s, int(sr * duration_s))
    # Fundamental frequency with vibrato
    f0 = 150 + 10 * np.sin(2 * np.pi * 5 * t)
    # Harmonics
    audio = np.sin(2 * np.pi * f0 * t)
    audio += 0.5 * np.sin(2 * np.pi * 2 * f0 * t)
    audio += 0.25 * np.sin(2 * np.pi * 3 * f0 * t)
    # Add noise
    audio += 0.1 * np.random.randn(len(audio))
    # Normalize
    audio = audio / np.max(np.abs(audio)) * 0.8
    return audio.astype(np.float32)


def load_test_audio(audio_dir: str, max_files: int = 10) -> List[tuple]:
    """Load test audio files from directory."""
    audio_files = []
    audio_dir = Path(audio_dir)

    if not audio_dir.exists():
        print(f"Warning: Audio directory {audio_dir} not found, using synthetic audio")
        return []

    for ext in ["*.wav", "*.mp3", "*.flac"]:
        audio_files.extend(audio_dir.glob(f"**/{ext}"))

    audio_files = audio_files[:max_files]
    loaded = []

    for f in audio_files:
        try:
            audio, sr = librosa.load(f, sr=16000, duration=5.0)
            loaded.append((str(f.name), audio, sr))
        except Exception as e:
            print(f"Failed to load {f}: {e}")

    return loaded


def benchmark_extractor(
    extractor: FeatureExtractor,
    test_audio: List[tuple],
    config: BenchmarkConfig,
) -> FeatureBenchmarkResult:
    """Benchmark a single feature extractor."""
    latencies = []
    memory_peaks = []

    # If no test audio, use synthetic
    if not test_audio:
        test_audio = [
            ("synthetic", generate_test_audio(config.chunk_duration_s, config.sample_rate), config.sample_rate)
        ]

    # Warmup
    for _ in range(config.warmup_iterations):
        for name, audio, sr in test_audio[:1]:
            try:
                extractor.extract(audio, sr)
            except Exception:
                pass

    # Benchmark
    for iteration in range(config.num_iterations):
        for name, audio, sr in test_audio:
            try:
                tracemalloc.start()
                start = time.perf_counter()

                _ = extractor.extract(audio, sr)

                elapsed_ms = (time.perf_counter() - start) * 1000
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()

                latencies.append(elapsed_ms)
                memory_peaks.append(peak / 1024)  # KB

            except Exception as e:
                tracemalloc.stop()
                print(f"  Error in {extractor.name}: {e}")

    if not latencies:
        return FeatureBenchmarkResult(
            feature_name=extractor.name,
            category=extractor.category,
            mean_latency_ms=0,
            std_latency_ms=0,
            min_latency_ms=0,
            max_latency_ms=0,
            p95_latency_ms=0,
            memory_peak_kb=0,
            samples_tested=0,
            edge_feasible=False,
            notes="Extraction failed",
        )

    latencies = np.array(latencies)
    memory_peaks = np.array(memory_peaks)

    mean_latency = np.mean(latencies)
    p95_latency = np.percentile(latencies, 95)
    max_memory = np.max(memory_peaks)

    # Determine edge feasibility
    edge_feasible = (
        p95_latency < config.esp32_max_latency_ms and
        max_memory < config.esp32_max_memory_kb
    )

    notes = ""
    if not edge_feasible:
        if p95_latency >= config.esp32_max_latency_ms:
            notes += f"Too slow for edge ({p95_latency:.1f}ms > {config.esp32_max_latency_ms}ms). "
        if max_memory >= config.esp32_max_memory_kb:
            notes += f"Too much memory ({max_memory:.1f}KB > {config.esp32_max_memory_kb}KB). "

    return FeatureBenchmarkResult(
        feature_name=extractor.name,
        category=extractor.category,
        mean_latency_ms=round(mean_latency, 2),
        std_latency_ms=round(np.std(latencies), 2),
        min_latency_ms=round(np.min(latencies), 2),
        max_latency_ms=round(np.max(latencies), 2),
        p95_latency_ms=round(p95_latency, 2),
        memory_peak_kb=round(max_memory, 2),
        samples_tested=len(latencies),
        edge_feasible=edge_feasible,
        notes=notes.strip(),
    )


def run_benchmark(args: argparse.Namespace) -> dict:
    """Run full benchmark suite."""
    config = BenchmarkConfig(
        num_iterations=args.iterations,
    )

    print("=" * 70)
    print("Feature Extraction Latency Benchmark")
    print("=" * 70)
    print(f"Config: {config.num_iterations} iterations, {config.chunk_duration_s}s chunks")
    print(f"ESP32 limits: {config.esp32_max_latency_ms}ms latency, {config.esp32_max_memory_kb}KB memory")
    print()

    # Load test audio
    test_audio = []
    if args.audio_dir:
        print(f"Loading test audio from {args.audio_dir}...")
        test_audio = load_test_audio(args.audio_dir, max_files=args.max_files)
        print(f"  Loaded {len(test_audio)} files")

    if not test_audio:
        print("Using synthetic audio for testing")
        test_audio = [
            ("synthetic", generate_test_audio(config.chunk_duration_s, config.sample_rate), config.sample_rate)
        ]

    # Get extractors
    extractors = get_all_extractors()
    print(f"\nBenchmarking {len(extractors)} feature extractors...")
    print()

    results = []
    for i, extractor in enumerate(extractors, 1):
        print(f"[{i}/{len(extractors)}] {extractor.name}...", end=" ", flush=True)
        result = benchmark_extractor(extractor, test_audio, config)
        results.append(result)

        status = "✓ EDGE" if result.edge_feasible else "✗ HUB"
        print(f"{status} ({result.mean_latency_ms:.1f}ms, {result.memory_peak_kb:.1f}KB)")

    # Organize results
    edge_features = [r for r in results if r.edge_feasible]
    hub_features = [r for r in results if not r.edge_feasible]

    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    print(f"\n✓ EDGE-FEASIBLE FEATURES ({len(edge_features)}):")
    for r in sorted(edge_features, key=lambda x: x.mean_latency_ms):
        print(f"  {r.feature_name}: {r.mean_latency_ms:.1f}ms, {r.memory_peak_kb:.1f}KB")

    print(f"\n✗ HUB-ONLY FEATURES ({len(hub_features)}):")
    for r in sorted(hub_features, key=lambda x: x.mean_latency_ms):
        print(f"  {r.feature_name}: {r.mean_latency_ms:.1f}ms, {r.memory_peak_kb:.1f}KB")
        if r.notes:
            print(f"    Reason: {r.notes}")

    # Build output
    output = {
        "timestamp": datetime.now().isoformat(),
        "config": asdict(config),
        "test_audio_count": len(test_audio),
        "edge_features": [asdict(r) for r in edge_features],
        "hub_features": [asdict(r) for r in hub_features],
        "summary": {
            "total_features": len(results),
            "edge_feasible": len(edge_features),
            "hub_only": len(hub_features),
            "edge_names": [r.feature_name for r in edge_features],
            "hub_names": [r.feature_name for r in hub_features],
        },
    }

    return output


def main():
    parser = argparse.ArgumentParser(description="Feature Extraction Latency Benchmark")
    parser.add_argument("--audio-dir", type=str, default=None, help="Directory with test audio files")
    parser.add_argument("--max-files", type=int, default=10, help="Max audio files to load")
    parser.add_argument("--iterations", type=int, default=20, help="Benchmark iterations per feature")
    parser.add_argument("--output", type=str, default=None, help="Output JSON file")
    args = parser.parse_args()

    results = run_benchmark(args)

    # Save results
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(__file__).parent / "results" / f"feature_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, cls=NumpyEncoder)

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
