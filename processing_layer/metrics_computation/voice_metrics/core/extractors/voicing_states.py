import numpy as np
import librosa

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
