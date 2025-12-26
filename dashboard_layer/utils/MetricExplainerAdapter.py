"""
Human-readable explanations for acoustic metrics.
Provides simple and technical descriptions for each feature used in depression detection.
"""

from typing import Optional


class MetricExplainerAdapter:
    """Adapter that provides human-readable explanations for acoustic metrics."""

    METRIC_EXPLANATIONS = {
        # Fundamental frequency (pitch) metrics
        "f0_avg": {
            "name": "Average Pitch",
            "simple": "The typical pitch level of your voice",
            "technical": "Mean fundamental frequency (F0) extracted via autocorrelation method",
            "clinical": "Lower average pitch is often associated with depressed mood and reduced emotional expression",
            "unit": "Hz",
            "direction_meaning": {
                "negative": "Lower pitch than baseline may indicate low mood",
            },
        },
        "f0_std": {
            "name": "Pitch Variation",
            "simple": "How much your voice pitch changes while speaking",
            "technical": "Standard deviation of fundamental frequency (F0)",
            "clinical": "Reduced pitch variation (monotone speech) is associated with depression and emotional blunting",
            "unit": "Hz",
            "direction_meaning": {
                "negative": "Less variation suggests flatter emotional expression",
            },
        },
        "f0_range": {
            "name": "Pitch Range",
            "simple": "The difference between your highest and lowest voice pitch",
            "technical": "Range of fundamental frequency (max F0 - min F0)",
            "clinical": "Narrower pitch range indicates reduced emotional expressivity",
            "unit": "Hz",
            "direction_meaning": {
                "negative": "Narrower range suggests reduced emotional expression",
            },
        },
        # Formant metrics
        "formant_f1_frequencies_mean": {
            "name": "Vowel Quality (F1)",
            "simple": "How you form vowel sounds in speech",
            "technical": "Mean first formant frequency, related to tongue height and jaw opening",
            "clinical": "Changes in formant frequencies can indicate muscle tension or articulatory changes",
            "unit": "Hz",
            "direction_meaning": {
                "positive": "Higher F1 may indicate changes in speech production",
            },
        },
        "f2_transition_speed": {
            "name": "Articulation Speed",
            "simple": "How quickly you move between sounds while speaking",
            "technical": "Rate of change in second formant frequency during speech",
            "clinical": "Slower transitions may indicate psychomotor slowing",
            "unit": "Hz/s",
            "direction_meaning": {
                "negative": "Slower movement between sounds",
            },
        },
        # Voice quality metrics
        "jitter": {
            "name": "Voice Stability (Jitter)",
            "simple": "Small rapid fluctuations in your voice pitch",
            "technical": "Cycle-to-cycle frequency perturbation, measure of pitch instability",
            "clinical": "Higher jitter indicates vocal cord tension or neuromotor control issues, often elevated in depression",
            "unit": "%",
            "direction_meaning": {
                "positive": "More voice instability, may indicate distress",
            },
        },
        "shimmer": {
            "name": "Voice Steadiness (Shimmer)",
            "simple": "Small fluctuations in how loud your voice is",
            "technical": "Cycle-to-cycle amplitude perturbation, measure of loudness instability",
            "clinical": "Higher shimmer suggests reduced vocal cord control, associated with fatigue and depression",
            "unit": "%",
            "direction_meaning": {
                "positive": "Less steady voice amplitude",
            },
        },
        "hnr_mean": {
            "name": "Voice Clarity",
            "simple": "How clear and resonant your voice sounds",
            "technical": "Harmonics-to-Noise Ratio (HNR), measure of voice quality",
            "clinical": "Lower HNR (breathier voice) is associated with fatigue and low energy states",
            "unit": "dB",
            "direction_meaning": {
                "negative": "Less clear, more breathy voice quality",
            },
        },
        # Signal quality
        "snr": {
            "name": "Voice Strength",
            "simple": "How strong and clear your voice is compared to background",
            "technical": "Signal-to-Noise Ratio, voice signal strength relative to noise",
            "clinical": "Lower SNR may indicate softer speech associated with low energy or withdrawal",
            "unit": "dB",
            "direction_meaning": {
                "negative": "Quieter or less projected voice",
            },
        },
        # Energy metrics
        "rms_energy_range": {
            "name": "Volume Range",
            "simple": "The difference between your loudest and quietest speech",
            "technical": "Range of Root Mean Square energy across utterance",
            "clinical": "Reduced dynamic range suggests flattened emotional expression",
            "unit": "dB",
            "direction_meaning": {
                "negative": "Less variation in loudness",
            },
        },
        "rms_energy_std": {
            "name": "Volume Variation",
            "simple": "How much your voice volume changes while speaking",
            "technical": "Standard deviation of RMS energy",
            "clinical": "Lower variation indicates more monotonous, less expressive speech",
            "unit": "dB",
            "direction_meaning": {
                "negative": "More uniform, less dynamic speech",
            },
        },
        # Spectral metrics
        "spectral_flatness": {
            "name": "Voice Tone Quality",
            "simple": "Whether your voice sounds more tonal or more noise-like",
            "technical": "Ratio of geometric to arithmetic mean of power spectrum",
            "clinical": "Higher flatness (more noise-like) may indicate breathy or strained voice",
            "unit": "ratio",
            "direction_meaning": {
                "positive": "More noise-like, less tonal voice quality",
            },
        },
        # Temporal metrics
        "rate_of_speech": {
            "name": "Speaking Speed",
            "simple": "How fast you speak (words per minute)",
            "technical": "Number of syllables or phonemes per unit time",
            "clinical": "Slower speech rate is a common indicator of psychomotor retardation in depression",
            "unit": "syllables/sec",
            "direction_meaning": {
                "negative": "Slower than usual speech",
            },
        },
        "articulation_rate": {
            "name": "Articulation Speed",
            "simple": "How quickly you pronounce words (excluding pauses)",
            "technical": "Speaking rate excluding silent intervals",
            "clinical": "Reduced articulation rate suggests motor slowing or cognitive processing delays",
            "unit": "syllables/sec",
            "direction_meaning": {
                "negative": "Slower word formation",
            },
        },
        "pause_duration": {
            "name": "Pause Length",
            "simple": "How long you pause between phrases",
            "technical": "Average duration of silent intervals during speech",
            "clinical": "Longer pauses may indicate cognitive slowing or difficulty with thought organization",
            "unit": "seconds",
            "direction_meaning": {
                "positive": "Longer pauses between speech segments",
            },
        },
        "pause_count": {
            "name": "Pause Frequency",
            "simple": "How often you pause while speaking",
            "technical": "Number of silent intervals per unit of speech",
            "clinical": "More frequent pauses may reflect cognitive difficulties or fatigue",
            "unit": "count",
            "direction_meaning": {
                "positive": "More frequent pauses during speech",
            },
        },
        "voice_onset_time": {
            "name": "Speech Initiation",
            "simple": "How quickly you start speaking after thinking",
            "technical": "Time from stimulus to voice onset, measure of motor planning",
            "clinical": "Longer onset times suggest psychomotor slowing",
            "unit": "ms",
            "direction_meaning": {
                "positive": "Slower to begin speaking",
            },
        },
        # Modulation metrics
        "temporal_modulation": {
            "name": "Speech Rhythm",
            "simple": "The natural rhythm patterns in your speech",
            "technical": "Temporal modulation spectrum characteristics",
            "clinical": "Abnormal rhythm patterns may indicate disrupted motor control",
            "unit": "index",
            "direction_meaning": {
                "anomaly": "Unusual rhythm patterns detected",
            },
        },
        "spectral_modulation": {
            "name": "Tonal Patterns",
            "simple": "The tonal patterns and variations in your voice",
            "technical": "Spectral modulation characteristics",
            "clinical": "Changes may indicate altered emotional expression or fatigue",
            "unit": "index",
            "direction_meaning": {
                "anomaly": "Unusual tonal patterns detected",
            },
        },
        # Glottal metrics
        "glottal_pulse_rate": {
            "name": "Vocal Cord Activity",
            "simple": "How your vocal cords vibrate during speech",
            "technical": "Rate of glottal pulses during voiced speech",
            "clinical": "Changes may indicate altered vocal cord function or tension",
            "unit": "Hz",
            "direction_meaning": {
                "negative": "Reduced vocal cord activity",
            },
        },
        # OpenSMILE/eGeMAPS features (PSD and voiced segments)
        "psd-4": {
            "name": "Low-frequency Power",
            "simple": "Energy in the lower frequency range of your voice",
            "technical": "Power Spectral Density in 4th frequency band",
            "clinical": "Changes in spectral distribution may reflect emotional state",
            "unit": "dB",
            "direction_meaning": {
                "both": "Deviation from baseline in either direction",
            },
        },
        "psd-5": {
            "name": "Mid-frequency Power",
            "simple": "Energy in the middle frequency range of your voice",
            "technical": "Power Spectral Density in 5th frequency band",
            "clinical": "Spectral changes associated with voice quality variations",
            "unit": "dB",
            "direction_meaning": {
                "both": "Deviation from baseline in either direction",
            },
        },
        "psd-7": {
            "name": "High-frequency Power",
            "simple": "Energy in the higher frequency range of your voice",
            "technical": "Power Spectral Density in 7th frequency band",
            "clinical": "Higher frequency content relates to voice brightness and clarity",
            "unit": "dB",
            "direction_meaning": {
                "both": "Deviation from baseline in either direction",
            },
        },
        "t13": {
            "name": "Temporal Feature T13",
            "simple": "A specific timing pattern in your speech",
            "technical": "Temporal acoustic feature from eGeMAPS feature set",
            "clinical": "Contributes to overall speech pattern analysis",
            "unit": "index",
            "direction_meaning": {
                "positive": "Elevated temporal feature value",
            },
        },
        "voiced16_20": {
            "name": "Voiced Segment Ratio",
            "simple": "Proportion of voiced sounds in your speech",
            "technical": "Ratio of voiced segments in specific frequency bands",
            "clinical": "Lower voicing may indicate reduced vocal engagement",
            "unit": "ratio",
            "direction_meaning": {
                "negative": "Less voiced speech content",
            },
        },
    }

    @classmethod
    def get_explanation(cls, metric_key: str) -> Optional[dict]:
        """Get full explanation dictionary for a metric."""
        return cls.METRIC_EXPLANATIONS.get(metric_key)

    @classmethod
    def get_simple_explanation(cls, metric_key: str) -> str:
        """Get simple patient-friendly explanation."""
        info = cls.METRIC_EXPLANATIONS.get(metric_key, {})
        return info.get("simple", f"Voice measurement: {metric_key}")

    @classmethod
    def get_technical_explanation(cls, metric_key: str) -> str:
        """Get technical/clinical explanation."""
        info = cls.METRIC_EXPLANATIONS.get(metric_key, {})
        return info.get("technical", metric_key)

    @classmethod
    def get_clinical_relevance(cls, metric_key: str) -> str:
        """Get clinical relevance description."""
        info = cls.METRIC_EXPLANATIONS.get(metric_key, {})
        return info.get("clinical", "Acoustic feature used in depression detection")

    @classmethod
    def get_friendly_name(cls, metric_key: str) -> str:
        """Get human-friendly metric name."""
        info = cls.METRIC_EXPLANATIONS.get(metric_key, {})
        return info.get("name", metric_key.replace("_", " ").title())

    @classmethod
    def get_direction_meaning(cls, metric_key: str, direction: str) -> str:
        """Get meaning of a specific direction for a metric."""
        info = cls.METRIC_EXPLANATIONS.get(metric_key, {})
        meanings = info.get("direction_meaning", {})
        return meanings.get(direction, f"{direction.title()} deviation from baseline")

    @classmethod
    def format_tooltip(cls, metric_key: str, include_clinical: bool = True) -> str:
        """Format a complete tooltip for a metric."""
        info = cls.METRIC_EXPLANATIONS.get(metric_key)
        if not info:
            return metric_key

        parts = [
            f"**{info.get('name', metric_key)}**",
            "",
            info.get("simple", ""),
        ]

        if include_clinical and info.get("clinical"):
            parts.extend(["", f"_{info['clinical']}_"])

        return "\n".join(parts)

    @classmethod
    def get_all_metrics(cls) -> list[str]:
        """Get list of all known metric keys."""
        return list(cls.METRIC_EXPLANATIONS.keys())
