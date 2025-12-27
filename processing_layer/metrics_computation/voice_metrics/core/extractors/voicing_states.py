"""
Voicing States Extractor with Interaction Dynamics Metrics

This module segments audio into voicing states (voiced, unvoiced, silence)
and computes interaction dynamics metrics that are critical for DSM-5
psychomotor assessment.

Voicing States:
- 1 = Voiced (speech with pitch)
- 2 = Unvoiced (speech without pitch, e.g., fricatives)
- 3 = Silence (no speech activity)

Key Interaction Dynamics Metrics:
- silence_ratio: Proportion of silent frames (psychomotor retardation marker)
- speech_velocity: Rate of state transitions (speech fluency)
- pause statistics: Duration and frequency of pauses

Clinical Relevance:
- High silence_ratio: Psychomotor retardation, reduced speech initiation
- Low speech_velocity: Slower, more fragmented speech
- Longer pause durations: Cognitive processing delays
"""

import numpy as np
import librosa
from core.extractors.dynamic_metrics_utils import (
    compute_silence_ratio,
    compute_speech_velocity,
    compute_pause_statistics,
)

RMS_THRESHOLD = 0.01


def classify_voicing_states(audio_np, sample_rate, frame_length=0.04, hop_length=0.01):
    """
    Segments audio into 3 states: 1=voiced, 2=unvoiced, 3=silence
    Optimized with vectorization for better performance
    """
    frame_len = int(frame_length * sample_rate)
    hop_len = int(hop_length * sample_rate)

    rms = librosa.feature.rms(y=audio_np, frame_length=frame_len, hop_length=hop_len)[0]
    pitches, _ = librosa.piptrack(y=audio_np, sr=sample_rate, hop_length=hop_len)

    pitch_present = np.any(pitches > 0, axis=0)

    # Vectorized state assignment using np.where
    # Priority: voiced (1) > unvoiced (2) > silence (3)
    state_sequence = np.where(
        pitch_present,
        1,  # Voiced
        np.where(rms > RMS_THRESHOLD, 2, 3)  # Unvoiced or Silence
    )

    return state_sequence.tolist()


def get_interaction_dynamics(audio_np, sample_rate, frame_length=0.04, hop_length=0.01) -> dict:
    """
    Compute all interaction dynamics metrics in a single pass.

    This is the Phase 1 "Silent Expansion" function for psychomotor
    assessment. These metrics capture the temporal structure of speech
    that correlates with DSM-5 psychomotor retardation/agitation criteria.

    Args:
        audio_np: Audio signal as numpy array
        sample_rate: Sample rate in Hz
        frame_length: Frame length in seconds (default 40ms)
        hop_length: Hop length in seconds (default 10ms)

    Returns:
        Dictionary with keys:
        - silence_ratio: Proportion of silent frames (0.0 to 1.0)
        - speech_velocity: State transitions per second
        - voiced_ratio: Proportion of voiced frames
        - unvoiced_ratio: Proportion of unvoiced frames
        - pause_count_dynamic: Number of pause segments
        - pause_mean_duration: Average pause duration (seconds)
        - pause_std_duration: Std dev of pause durations (seconds)
        - pause_max_duration: Longest pause duration (seconds)
        - pause_total_duration: Total pause time (seconds)
    """
    state_sequence = classify_voicing_states(audio_np, sample_rate, frame_length, hop_length)

    if not state_sequence:
        return {
            "silence_ratio": 0.0,
            "speech_velocity": 0.0,
            "voiced_ratio": 0.0,
            "unvoiced_ratio": 0.0,
            "pause_count_dynamic": 0,
            "pause_mean_duration": 0.0,
            "pause_std_duration": 0.0,
            "pause_max_duration": 0.0,
            "pause_total_duration": 0.0,
        }

    total_frames = len(state_sequence)

    # Compute state ratios
    voiced_count = sum(1 for s in state_sequence if s == 1)
    unvoiced_count = sum(1 for s in state_sequence if s == 2)
    silence_count = sum(1 for s in state_sequence if s == 3)

    # Get pause statistics
    pause_stats = compute_pause_statistics(state_sequence, frame_duration=hop_length)

    return {
        "silence_ratio": float(silence_count / total_frames),
        "speech_velocity": compute_speech_velocity(state_sequence, frame_duration=hop_length),
        "voiced_ratio": float(voiced_count / total_frames),
        "unvoiced_ratio": float(unvoiced_count / total_frames),
        **pause_stats,  # Includes pause_count_dynamic, pause_mean/std/max/total_duration
    }


def compute_transition_probability(state_sequence, from_state, to_state):
    """
    Computes all the transition probabilities based off the state_sequence
    Optimized with vectorization for better performance
    """
    # Convert to numpy array for vectorized operations
    state_arr = np.array(state_sequence)

    # Find transitions from from_state
    from_mask = state_arr[:-1] == from_state
    total_from = np.sum(from_mask)

    if total_from == 0:
        return 0.0

    # Find transitions to to_state
    to_mask = state_arr[1:] == to_state

    # Count transitions from from_state to to_state
    total_transition = np.sum(from_mask & to_mask)

    return total_transition / total_from


def get_t13_voiced_to_silence(audio_np, sample_rate):
    """
    Computes t13: probability of transitioning from voiced to silence
    """
    state_seq = classify_voicing_states(audio_np, sample_rate)
    return compute_transition_probability(state_seq, from_state=1, to_state=3)


def get_voiced_interval_histogram(state_sequence, frame_duration=0.04):
    """
    Returns a histogram of voiced interval lengths (in number of frames)
    """
    intervals = []
    count = 0
    for state in state_sequence:
        if state == 1:  # Voiced
            count += 1
        elif count > 0:
            intervals.append(count)
            count = 0
    if count > 0:  # Final segment
        intervals.append(count)

    return intervals


def compute_voiced16_20_feature(state_sequence):
    """
    Computes Voiced16:20 PDF value: proportion of voiced segments
    that last between 16 and 20 frames (inclusive)
    """
    intervals = get_voiced_interval_histogram(state_sequence)
    total = len(intervals)
    if total == 0:
        return 0.0
    count_16_20 = sum(1 for i in intervals if 16 <= i <= 20)
    return count_16_20 / total
