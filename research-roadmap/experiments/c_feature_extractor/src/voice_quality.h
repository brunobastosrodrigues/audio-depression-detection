/**
 * @file voice_quality.h
 * @brief Voice quality metrics: Jitter, Shimmer, HNR, SNR
 *
 * These metrics assess voice quality and perturbation, which are
 * clinically relevant for depression detection.
 *
 * References:
 * - Jitter/Shimmer: Teixeira et al. (2013) "Vocal Acoustic Analysis"
 * - HNR: de Krom (1993) "A cepstrum-based technique for HNR"
 */

#ifndef VOICE_QUALITY_H
#define VOICE_QUALITY_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Voice quality metrics computed per utterance
 */
typedef struct {
    float jitter_local;     /**< Local jitter (relative F0 perturbation) */
    float jitter_rap;       /**< Relative average perturbation */
    float shimmer_local;    /**< Local shimmer (amplitude perturbation) */
    float shimmer_apq3;     /**< 3-point amplitude perturbation quotient */
    float hnr_mean;         /**< Mean Harmonics-to-Noise Ratio (dB) */
    float snr;              /**< Signal-to-Noise Ratio (dB) */
} voice_quality_t;

/**
 * @brief Compute local jitter from F0 contour
 *
 * Jitter is the cycle-to-cycle variation in fundamental frequency.
 * Formula: jitter_local = mean(|F0[i] - F0[i-1]|) / mean(F0)
 *
 * @param f0_values Array of F0 values (Hz) for voiced frames
 * @param count Number of F0 values
 * @return Local jitter as a ratio (typically 0.001 - 0.05)
 */
float compute_jitter_local(const float* f0_values, int count);

/**
 * @brief Compute RAP (Relative Average Perturbation)
 *
 * 3-point jitter: smoothed version using 3-point window.
 * Formula: RAP = mean(|F0[i] - mean(F0[i-1], F0[i], F0[i+1])|) / mean(F0)
 *
 * @param f0_values Array of F0 values (Hz)
 * @param count Number of F0 values
 * @return RAP as a ratio
 */
float compute_jitter_rap(const float* f0_values, int count);

/**
 * @brief Compute local shimmer from amplitude contour
 *
 * Shimmer is the cycle-to-cycle variation in amplitude.
 * Formula: shimmer_local = mean(|A[i] - A[i-1]|) / mean(A)
 *
 * @param amplitudes Array of peak amplitudes for voiced frames
 * @param count Number of amplitude values
 * @return Local shimmer as a ratio (typically 0.01 - 0.1)
 */
float compute_shimmer_local(const float* amplitudes, int count);

/**
 * @brief Compute APQ3 (3-point Amplitude Perturbation Quotient)
 *
 * Smoothed shimmer using 3-point window.
 *
 * @param amplitudes Array of peak amplitudes
 * @param count Number of amplitude values
 * @return APQ3 as a ratio
 */
float compute_shimmer_apq3(const float* amplitudes, int count);

/**
 * @brief Compute HNR for a single frame using autocorrelation
 *
 * HNR measures the ratio of periodic (harmonic) to aperiodic (noise) energy.
 * Higher HNR = clearer voice, lower HNR = breathier/hoarser voice.
 *
 * @param frame Audio frame (INT16)
 * @param frame_size Number of samples
 * @param f0 Estimated F0 for this frame (Hz)
 * @param sample_rate Sample rate (Hz)
 * @return HNR in dB (typically 0-40 dB for speech)
 */
float compute_hnr_frame(
    const int16_t* frame,
    int frame_size,
    float f0,
    int sample_rate
);

/**
 * @brief Compute SNR from speech and noise RMS
 *
 * @param speech_rms RMS energy of voiced frames
 * @param noise_rms RMS energy of unvoiced frames (noise floor)
 * @return SNR in dB
 */
float compute_snr(float speech_rms, float noise_rms);

/**
 * @brief Extract peak amplitude from a frame at pitch period
 *
 * Used for shimmer computation - extracts the peak amplitude
 * within each pitch period.
 *
 * @param frame Audio frame (INT16)
 * @param frame_size Number of samples
 * @param f0 Estimated F0 for this frame (Hz)
 * @param sample_rate Sample rate (Hz)
 * @return Peak amplitude (normalized 0-1)
 */
float extract_frame_amplitude(
    const int16_t* frame,
    int frame_size,
    float f0,
    int sample_rate
);

#ifdef __cplusplus
}
#endif

#endif /* VOICE_QUALITY_H */
