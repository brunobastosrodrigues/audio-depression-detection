/**
 * @file board_config.h
 * @brief Board-specific configuration for IHearYou firmware
 *
 * This file contains hardware-specific definitions for:
 * - ReSpeaker Lite (XMOS XU316, 2-mic)
 * - ReSpeaker XVF3800 (4-mic, advanced DSP)
 *
 * @copyright IHearYou Research Project
 */

#ifndef BOARD_CONFIG_H
#define BOARD_CONFIG_H

#include "sdkconfig.h"
#include "driver/gpio.h"

#ifdef __cplusplus
extern "C" {
#endif

// =============================================================================
// Board Type Detection
// =============================================================================

#if defined(CONFIG_BOARD_RESPEAKER_LITE)
    #define BOARD_TYPE_LITE         1
    #define BOARD_TYPE_XVF3800      0
    #define BOARD_NAME              "ReSpeaker Lite"
    #define BOARD_TYPE_STRING       "lite"
#elif defined(CONFIG_BOARD_RESPEAKER_XVF3800)
    #define BOARD_TYPE_LITE         0
    #define BOARD_TYPE_XVF3800      1
    #define BOARD_NAME              "ReSpeaker XVF3800"
    #define BOARD_TYPE_STRING       "xvf3800"
#else
    #error "No board type selected! Configure in menuconfig."
#endif

// =============================================================================
// Common Audio Configuration
// =============================================================================

#define AUDIO_SAMPLE_RATE           16000   // Hz - Required for depression detection
#define AUDIO_BIT_DEPTH             16      // bits
#define AUDIO_CHANNELS              1       // mono
#define AUDIO_BYTES_PER_SAMPLE      2       // int16_t

// Chunk configuration
#ifndef CONFIG_AUDIO_CHUNK_DURATION_S
    #define CONFIG_AUDIO_CHUNK_DURATION_S   5
#endif
#define AUDIO_CHUNK_DURATION_S      CONFIG_AUDIO_CHUNK_DURATION_S
#define AUDIO_CHUNK_SAMPLES         (AUDIO_SAMPLE_RATE * AUDIO_CHUNK_DURATION_S)
#define AUDIO_CHUNK_BYTES           (AUDIO_CHUNK_SAMPLES * AUDIO_BYTES_PER_SAMPLE)

// I2S DMA Configuration
#define I2S_DMA_BUF_COUNT           16      // Number of DMA buffers
#define I2S_DMA_BUF_LEN             512     // Samples per buffer
#define I2S_READ_TIMEOUT_MS         1000    // Timeout for I2S read

// =============================================================================
// ReSpeaker Lite Specific Configuration
// =============================================================================

#if BOARD_TYPE_LITE

// I2S Pins (ESP32 is I2S slave, XU316 is master)
#define I2S_BCK_PIN                 GPIO_NUM_8
#define I2S_WS_PIN                  GPIO_NUM_7
#define I2S_DIN_PIN                 GPIO_NUM_44
#define I2S_DOUT_PIN                GPIO_NUM_NC     // Not used (RX only)
#define I2S_MCLK_PIN                GPIO_NUM_NC     // Not used (slave mode)

// I2S Configuration
#define I2S_ROLE                    I2S_ROLE_SLAVE
#define I2S_BITS_PER_SAMPLE         I2S_DATA_BIT_WIDTH_32BIT
#define I2S_SLOT_MODE               I2S_SLOT_MODE_MONO

// Digital gain (bit shift for amplification from 32-bit to 16-bit)
#define DIGITAL_GAIN_SHIFT          16

// I2C Configuration for TLV320AIC3204 Codec
#define CODEC_I2C_PORT              I2C_NUM_0
#define CODEC_I2C_SDA               GPIO_NUM_5
#define CODEC_I2C_SCL               GPIO_NUM_6
#define CODEC_I2C_ADDR              0x18
#define CODEC_I2C_FREQ_HZ           100000

// Feature flags
#define HAS_DOA_DETECTION           0
#define HAS_HARDWARE_VAD            0
#define HAS_BEAMFORMING             0
#define HAS_DEREVERB                0
#define HAS_DNN_NS                  0

#endif // BOARD_TYPE_LITE

// =============================================================================
// ReSpeaker XVF3800 Specific Configuration
// =============================================================================

#if BOARD_TYPE_XVF3800

// I2S Pins (ESP32 is I2S slave, XVF3800 is master)
#define I2S_BCK_PIN                 GPIO_NUM_8
#define I2S_WS_PIN                  GPIO_NUM_7
#define I2S_DIN_PIN                 GPIO_NUM_43     // RX from XVF3800
#define I2S_DOUT_PIN                GPIO_NUM_44     // TX for reference audio (AEC)
#define I2S_MCLK_PIN                GPIO_NUM_NC     // XVF3800 generates MCLK

// I2S Configuration
#define I2S_ROLE                    I2S_ROLE_SLAVE
#define I2S_BITS_PER_SAMPLE         I2S_DATA_BIT_WIDTH_32BIT
#define I2S_SLOT_MODE               I2S_SLOT_MODE_MONO

// No digital gain needed - XVF3800 has 60dB AGC
#define DIGITAL_GAIN_SHIFT          0

// I2C Configuration for XVF3800 Control
#define XVF3800_I2C_PORT            I2C_NUM_0
#define XVF3800_I2C_SDA             GPIO_NUM_5
#define XVF3800_I2C_SCL             GPIO_NUM_6
#define XVF3800_I2C_ADDR            0x2C
#define XVF3800_I2C_FREQ_HZ         100000  // 100kHz standard mode

// XVF3800 Timing
#define XVF3800_CMD_RESPONSE_DELAY_MS   2   // Min 1ms per XMOS docs
#define XVF3800_I2C_TIMEOUT_MS          100

// GPIO for XVF3800
#define XVF3800_GPI_COUNT           3
#define XVF3800_GPO_COUNT           5

// Feature flags
#define HAS_DOA_DETECTION           1
#define HAS_HARDWARE_VAD            1
#define HAS_BEAMFORMING             1
#define HAS_DEREVERB                1
#define HAS_DNN_NS                  1

// XVF3800 DSP Settings (from Kconfig)
#ifndef CONFIG_XVF3800_AGC_ENABLED
    #define CONFIG_XVF3800_AGC_ENABLED      0
#endif
#ifndef CONFIG_XVF3800_DEREVERB_ENABLED
    #define CONFIG_XVF3800_DEREVERB_ENABLED 1
#endif
#ifndef CONFIG_XVF3800_BEAM_MODE
    #define CONFIG_XVF3800_BEAM_MODE        1   // Adaptive
#endif
#ifndef CONFIG_XVF3800_INCLUDE_DOA
    #define CONFIG_XVF3800_INCLUDE_DOA      1
#endif

#define XVF3800_AGC_ENABLED         CONFIG_XVF3800_AGC_ENABLED
#define XVF3800_DEREVERB_ENABLED    CONFIG_XVF3800_DEREVERB_ENABLED
#define XVF3800_BEAM_MODE           CONFIG_XVF3800_BEAM_MODE
#define XVF3800_INCLUDE_DOA         CONFIG_XVF3800_INCLUDE_DOA

#endif // BOARD_TYPE_XVF3800

// =============================================================================
// VAD Configuration
// =============================================================================

#ifndef CONFIG_VAD_THRESHOLD
    #if BOARD_TYPE_LITE
        #define CONFIG_VAD_THRESHOLD    200
    #else
        #define CONFIG_VAD_THRESHOLD    80
    #endif
#endif

#ifndef CONFIG_VAD_HANGOVER_MS
    #define CONFIG_VAD_HANGOVER_MS      500
#endif

#define VAD_THRESHOLD               ((float)CONFIG_VAD_THRESHOLD)
#define VAD_HANGOVER_MS             CONFIG_VAD_HANGOVER_MS
#define VAD_NOISE_FLOOR_ALPHA       0.01f   // Slow adaptation

// =============================================================================
// Ring Buffer Configuration
// =============================================================================

#ifndef CONFIG_RING_BUFFER_SIZE_KB
    #define CONFIG_RING_BUFFER_SIZE_KB  512
#endif

#define RING_BUFFER_SIZE            (CONFIG_RING_BUFFER_SIZE_KB * 1024)

// Watermarks for flow control
#define RING_BUFFER_HIGH_WATERMARK  (RING_BUFFER_SIZE * 75 / 100)
#define RING_BUFFER_LOW_WATERMARK   (RING_BUFFER_SIZE * 25 / 100)

// =============================================================================
// Network Configuration
// =============================================================================

#ifndef CONFIG_SERVER_PORT
    #define CONFIG_SERVER_PORT          8010
#endif

#ifndef CONFIG_WIFI_MAXIMUM_RETRY
    #define CONFIG_WIFI_MAXIMUM_RETRY   10
#endif

#ifndef CONFIG_RECONNECT_DELAY_MS
    #define CONFIG_RECONNECT_DELAY_MS   1000
#endif

#define SERVER_PORT                 CONFIG_SERVER_PORT
#define WIFI_MAXIMUM_RETRY          CONFIG_WIFI_MAXIMUM_RETRY
#define RECONNECT_DELAY_MS          CONFIG_RECONNECT_DELAY_MS
#define HANDSHAKE_TIMEOUT_MS        5000
#define TCP_CONNECT_TIMEOUT_MS      10000

// =============================================================================
// Task Configuration
// =============================================================================

// Task priorities (higher = more important)
#define TASK_PRIORITY_I2S_CAPTURE   24      // Highest - real-time audio
#define TASK_PRIORITY_VAD           20      // High - audio processing
#define TASK_PRIORITY_QUALITY       15      // Medium - metrics
#define TASK_PRIORITY_TCP_SENDER    10      // Medium - network
#define TASK_PRIORITY_DSP_CONTROL   8       // Lower - configuration
#define TASK_PRIORITY_WIFI          5       // Lowest - management

// Task stack sizes
#define TASK_STACK_I2S_CAPTURE      8192
#define TASK_STACK_VAD              4096
#define TASK_STACK_QUALITY          2048
#define TASK_STACK_TCP_SENDER       8192
#define TASK_STACK_DSP_CONTROL      4096
#define TASK_STACK_WIFI             4096
// ESP_LOGI (vprintf) + esp_wifi_sta_get_ap_info need well over 2048 bytes; the
// telemetry task previously hardcoded 2048 and overflowed at first tick (boot crash-loop
// found at first hardware bring-up, 2026-07-09).
#define TASK_STACK_TELEMETRY        4096

// Task core affinity
#define TASK_CORE_AUDIO             1       // Core 1 for audio (real-time)
#define TASK_CORE_NETWORK           0       // Core 0 for network/protocol

// =============================================================================
// Firmware Version
// =============================================================================

#define FIRMWARE_VERSION_MAJOR      1
#define FIRMWARE_VERSION_MINOR      0
#define FIRMWARE_VERSION_PATCH      0
#define FIRMWARE_VERSION_STRING     "1.0.0"

#ifdef __cplusplus
}
#endif

#endif // BOARD_CONFIG_H
