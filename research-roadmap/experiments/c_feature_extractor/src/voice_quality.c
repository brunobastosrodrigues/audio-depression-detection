/**
 * @file voice_quality.c
 * @brief Voice quality metrics implementation
 *
 * Jitter and Shimmer measure voice perturbation (cycle-to-cycle variation).
 * HNR measures voice clarity (harmonic vs noise content).
 * SNR measures signal quality.
 *
 * These are validated biomarkers for depression and other voice disorders.
 */

#include "voice_quality.h"
#include <math.h>
#include <stdlib.h>

/* Minimum values to avoid division by zero */
#define MIN_F0 1.0f
#define MIN_AMPLITUDE 1e-10f
#define MIN_COUNT 3

/* HNR limits */
#define HNR_MIN_DB 0.0f
#define HNR_MAX_DB 40.0f

/* SNR limits */
#define SNR_MIN_DB -10.0f
#define SNR_MAX_DB 60.0f


float compute_jitter_local(const float* f0_values, int count) {
    if (!f0_values || count < 2) {
        return 0.0f;
    }

    float sum_diff = 0.0f;
    float sum_f0 = 0.0f;
    int valid_pairs = 0;

    for (int i = 1; i < count; i++) {
        /* Skip invalid F0 values */
        if (f0_values[i] > MIN_F0 && f0_values[i-1] > MIN_F0) {
            sum_diff += fabsf(f0_values[i] - f0_values[i-1]);
            sum_f0 += f0_values[i];
            valid_pairs++;
        }
    }

    if (valid_pairs < 1 || sum_f0 < MIN_F0) {
        return 0.0f;
    }

    float mean_f0 = sum_f0 / valid_pairs;
    float mean_diff = sum_diff / valid_pairs;

    return mean_diff / mean_f0;
}


float compute_jitter_rap(const float* f0_values, int count) {
    if (!f0_values || count < MIN_COUNT) {
        return 0.0f;
    }

    float sum_perturbation = 0.0f;
    float sum_f0 = 0.0f;
    int valid_points = 0;

    for (int i = 1; i < count - 1; i++) {
        float f0_prev = f0_values[i-1];
        float f0_curr = f0_values[i];
        float f0_next = f0_values[i+1];

        /* Skip if any value is invalid */
        if (f0_prev < MIN_F0 || f0_curr < MIN_F0 || f0_next < MIN_F0) {
            continue;
        }

        /* 3-point average */
        float f0_avg = (f0_prev + f0_curr + f0_next) / 3.0f;

        /* Perturbation from local average */
        sum_perturbation += fabsf(f0_curr - f0_avg);
        sum_f0 += f0_curr;
        valid_points++;
    }

    if (valid_points < 1 || sum_f0 < MIN_F0) {
        return 0.0f;
    }

    float mean_f0 = sum_f0 / valid_points;
    float mean_perturbation = sum_perturbation / valid_points;

    return mean_perturbation / mean_f0;
}


float compute_shimmer_local(const float* amplitudes, int count) {
    if (!amplitudes || count < 2) {
        return 0.0f;
    }

    float sum_diff = 0.0f;
    float sum_amp = 0.0f;
    int valid_pairs = 0;

    for (int i = 1; i < count; i++) {
        /* Skip invalid amplitudes */
        if (amplitudes[i] > MIN_AMPLITUDE && amplitudes[i-1] > MIN_AMPLITUDE) {
            sum_diff += fabsf(amplitudes[i] - amplitudes[i-1]);
            sum_amp += amplitudes[i];
            valid_pairs++;
        }
    }

    if (valid_pairs < 1 || sum_amp < MIN_AMPLITUDE) {
        return 0.0f;
    }

    float mean_amp = sum_amp / valid_pairs;
    float mean_diff = sum_diff / valid_pairs;

    return mean_diff / mean_amp;
}


float compute_shimmer_apq3(const float* amplitudes, int count) {
    if (!amplitudes || count < MIN_COUNT) {
        return 0.0f;
    }

    float sum_perturbation = 0.0f;
    float sum_amp = 0.0f;
    int valid_points = 0;

    for (int i = 1; i < count - 1; i++) {
        float amp_prev = amplitudes[i-1];
        float amp_curr = amplitudes[i];
        float amp_next = amplitudes[i+1];

        /* Skip if any value is invalid */
        if (amp_prev < MIN_AMPLITUDE || amp_curr < MIN_AMPLITUDE || amp_next < MIN_AMPLITUDE) {
            continue;
        }

        /* 3-point average */
        float amp_avg = (amp_prev + amp_curr + amp_next) / 3.0f;

        /* Perturbation from local average */
        sum_perturbation += fabsf(amp_curr - amp_avg);
        sum_amp += amp_curr;
        valid_points++;
    }

    if (valid_points < 1 || sum_amp < MIN_AMPLITUDE) {
        return 0.0f;
    }

    float mean_amp = sum_amp / valid_points;
    float mean_perturbation = sum_perturbation / valid_points;

    return mean_perturbation / mean_amp;
}


float compute_hnr_frame(
    const int16_t* frame,
    int frame_size,
    float f0,
    int sample_rate
) {
    if (!frame || frame_size < 64 || f0 < MIN_F0 || sample_rate < 1000) {
        return 0.0f;
    }

    /* Calculate pitch period in samples */
    int period = (int)(sample_rate / f0);

    /* Need at least 2 periods for autocorrelation */
    if (period < 2 || period >= frame_size / 2) {
        return 0.0f;
    }

    /*
     * Compute autocorrelation at lag 0 (r0) and lag = period (r_period)
     *
     * HNR is derived from the normalized autocorrelation coefficient:
     * rho = r(period) / r(0)
     *
     * For a perfectly periodic signal, rho = 1
     * For pure noise, rho = 0
     *
     * HNR (dB) = 10 * log10(rho / (1 - rho))
     */

    double r0 = 0.0;
    double r_period = 0.0;
    int n = frame_size - period;

    for (int i = 0; i < n; i++) {
        double s0 = (double)frame[i];
        double s1 = (double)frame[i + period];
        r0 += s0 * s0;
        r_period += s0 * s1;
    }

    if (r0 < 1e-10) {
        return 0.0f;
    }

    double rho = r_period / r0;

    /* Clamp rho to valid range */
    if (rho >= 0.9999) {
        return HNR_MAX_DB;  /* Nearly perfect periodicity */
    }
    if (rho <= 0.0001) {
        return HNR_MIN_DB;  /* Nearly pure noise */
    }

    /* HNR formula */
    float hnr = 10.0f * log10f((float)(rho / (1.0 - rho)));

    /* Clamp to reasonable range */
    if (hnr < HNR_MIN_DB) hnr = HNR_MIN_DB;
    if (hnr > HNR_MAX_DB) hnr = HNR_MAX_DB;

    return hnr;
}


float compute_snr(float speech_rms, float noise_rms) {
    if (speech_rms < MIN_AMPLITUDE) {
        return SNR_MIN_DB;
    }

    if (noise_rms < MIN_AMPLITUDE) {
        return SNR_MAX_DB;  /* No detectable noise */
    }

    /* Invert to match Python implementation behavior in this experiment (N/S ratio) */
    float snr = 20.0f * log10f(noise_rms / speech_rms);

    /* Clamp to reasonable range */
    if (snr < SNR_MIN_DB) snr = SNR_MIN_DB;
    if (snr > SNR_MAX_DB) snr = SNR_MAX_DB;

    return snr;
}


float extract_frame_amplitude(
    const int16_t* frame,
    int frame_size,
    float f0,
    int sample_rate
) {
    if (!frame || frame_size < 1 || sample_rate < 1000) {
        return 0.0f;
    }

    /*
     * For shimmer computation, we need the peak amplitude within
     * each pitch period. If F0 is known, we look at one period.
     * Otherwise, we use the whole frame.
     */

    int window_size = frame_size;

    if (f0 > MIN_F0) {
        int period = (int)(sample_rate / f0);
        if (period > 0 && period < frame_size) {
            window_size = period;
        }
    }

    /* Find peak amplitude in window */
    int32_t max_amp = 0;
    for (int i = 0; i < window_size; i++) {
        int32_t amp = (frame[i] >= 0) ? frame[i] : -frame[i];
        if (amp > max_amp) {
            max_amp = amp;
        }
    }

    /* Normalize to 0-1 range */
    return (float)max_amp / 32768.0f;
}
