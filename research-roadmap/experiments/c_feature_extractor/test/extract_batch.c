/**
 * @file extract_batch.c
 * @brief Batch feature extraction for comparison with Python
 *
 * Reads WAV files and outputs features to CSV for divergence analysis.
 *
 * Usage:
 *   ./extract_features <input_dir> <output_csv>
 *
 * Example:
 *   ./extract_features ../daic_woz_extracted/ ../results/c_features.csv
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <sys/stat.h>
#include "feature_extractor.h"

/* Simple WAV header structure */
typedef struct {
    char riff[4];           /* "RIFF" */
    uint32_t file_size;
    char wave[4];           /* "WAVE" */
    char fmt[4];            /* "fmt " */
    uint32_t fmt_size;
    uint16_t format;        /* 1 = PCM */
    uint16_t channels;
    uint32_t sample_rate;
    uint32_t byte_rate;
    uint16_t block_align;
    uint16_t bits_per_sample;
    char data[4];           /* "data" */
    uint32_t data_size;
} wav_header_t;

/* Load WAV file (16-bit PCM only) */
static int16_t* load_wav(const char* path, size_t* num_samples, int* sample_rate) {
    FILE* fp = fopen(path, "rb");
    if (!fp) {
        fprintf(stderr, "Cannot open: %s\n", path);
        return NULL;
    }

    wav_header_t header;
    if (fread(&header, sizeof(header), 1, fp) != 1) {
        fprintf(stderr, "Cannot read header: %s\n", path);
        fclose(fp);
        return NULL;
    }

    /* Validate header */
    if (strncmp(header.riff, "RIFF", 4) != 0 ||
        strncmp(header.wave, "WAVE", 4) != 0) {
        fprintf(stderr, "Invalid WAV: %s\n", path);
        fclose(fp);
        return NULL;
    }

    if (header.format != 1 || header.bits_per_sample != 16) {
        fprintf(stderr, "Unsupported format (need 16-bit PCM): %s\n", path);
        fclose(fp);
        return NULL;
    }

    /* Skip to data chunk if needed */
    /* Note: This is simplified, real WAV may have extra chunks */

    *sample_rate = header.sample_rate;
    *num_samples = header.data_size / (header.bits_per_sample / 8) / header.channels;

    /* Allocate buffer */
    int16_t* audio = (int16_t*)malloc(*num_samples * sizeof(int16_t));
    if (!audio) {
        fclose(fp);
        return NULL;
    }

    /* Read samples */
    if (header.channels == 1) {
        /* Mono */
        fread(audio, sizeof(int16_t), *num_samples, fp);
    } else {
        /* Stereo: take left channel */
        for (size_t i = 0; i < *num_samples; i++) {
            int16_t left, right;
            fread(&left, sizeof(int16_t), 1, fp);
            fread(&right, sizeof(int16_t), 1, fp);
            audio[i] = left;
        }
    }

    fclose(fp);
    return audio;
}

/* Find audio file in session directory */
static int find_audio_file(const char* session_dir, char* audio_path, size_t path_size) {
    DIR* dir = opendir(session_dir);
    if (!dir) return -1;

    struct dirent* entry;
    while ((entry = readdir(dir)) != NULL) {
        if (strstr(entry->d_name, "_AUDIO.wav") != NULL) {
            snprintf(audio_path, path_size, "%s/%s", session_dir, entry->d_name);
            closedir(dir);
            return 0;
        }
    }

    closedir(dir);
    return -1;
}

int main(int argc, char* argv[]) {
    if (argc < 3) {
        fprintf(stderr, "Usage: %s <input_dir> <output_csv>\n", argv[0]);
        fprintf(stderr, "Example: %s ../daic_woz_extracted/ ../results/c_features.csv\n", argv[0]);
        return 1;
    }

    const char* input_dir = argv[1];
    const char* output_csv = argv[2];

    /* Open output file */
    FILE* out = fopen(output_csv, "w");
    if (!out) {
        fprintf(stderr, "Cannot create: %s\n", output_csv);
        return 1;
    }

    /* Write CSV header */
    fprintf(out, "session_id,f0_mean_hz,f0_std_hz,f0_range_hz,pause_ratio,voiced_ratio,"
                 "energy_std,energy_mean,jitter,jitter_rap,shimmer,shimmer_apq3,"
                 "hnr_mean,snr,duration_sec,frame_count,voiced_frames\n");

    /* Initialize extractor */
    extractor_config_t config = EXTRACTOR_CONFIG_DEFAULT;
    extractor_ctx_t* ctx = extractor_init(&config);
    if (!ctx) {
        fprintf(stderr, "Failed to initialize extractor\n");
        fclose(out);
        return 1;
    }

    /* Iterate over session directories */
    DIR* dir = opendir(input_dir);
    if (!dir) {
        fprintf(stderr, "Cannot open: %s\n", input_dir);
        extractor_free(ctx);
        fclose(out);
        return 1;
    }

    int processed = 0;
    int errors = 0;

    struct dirent* entry;
    while ((entry = readdir(dir)) != NULL) {
        /* Skip . and .. */
        if (entry->d_name[0] == '.') continue;

        /* Build session path */
        char session_path[512];
        snprintf(session_path, sizeof(session_path), "%s/%s", input_dir, entry->d_name);

        /* Check if directory */
        struct stat st;
        if (stat(session_path, &st) != 0 || !S_ISDIR(st.st_mode)) continue;

        /* Find audio file */
        char audio_path[512];
        if (find_audio_file(session_path, audio_path, sizeof(audio_path)) != 0) {
            /* Try nested directory */
            char nested_path[512];
            snprintf(nested_path, sizeof(nested_path), "%s/%s", session_path, entry->d_name);
            if (find_audio_file(nested_path, audio_path, sizeof(audio_path)) != 0) {
                fprintf(stderr, "[%s] No audio file found\n", entry->d_name);
                errors++;
                continue;
            }
        }

        /* Load audio */
        size_t num_samples;
        int sample_rate;
        int16_t* audio = load_wav(audio_path, &num_samples, &sample_rate);
        if (!audio) {
            errors++;
            continue;
        }

        /* Resample if needed (simple skip/duplicate - not ideal) */
        if (sample_rate != config.sample_rate) {
            fprintf(stderr, "[%s] Sample rate mismatch: %d vs %d\n",
                    entry->d_name, sample_rate, config.sample_rate);
        }

        /* Extract features */
        features_t features;
        int ret = extractor_process(ctx, audio, num_samples, &features);
        free(audio);

        if (ret != 0) {
            fprintf(stderr, "[%s] Extraction failed\n", entry->d_name);
            errors++;
            continue;
        }

        /* Write to CSV */
        fprintf(out, "%s,%.3f,%.3f,%.3f,%.4f,%.4f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.2f,%.2f,%.2f,%d,%d\n",
                entry->d_name,
                features.f0_mean,
                features.f0_std,
                features.f0_range,
                features.pause_ratio,
                features.voiced_ratio,
                features.energy_std,
                features.energy_mean,
                features.jitter,
                features.jitter_rap,
                features.shimmer,
                features.shimmer_apq3,
                features.hnr_mean,
                features.snr,
                features.duration_sec,
                features.frame_count,
                features.voiced_frames);

        processed++;
        printf("[%d] %s: F0=%.1f Hz, jitter=%.4f, HNR=%.1f dB\n",
               processed, entry->d_name, features.f0_mean, features.jitter, features.hnr_mean);
    }

    closedir(dir);
    extractor_free(ctx);
    fclose(out);

    printf("\n=== Summary ===\n");
    printf("Processed: %d\n", processed);
    printf("Errors: %d\n", errors);
    printf("Output: %s\n", output_csv);

    return (errors > 0) ? 1 : 0;
}
