# IHearYou Firmware - Main Component CMakeLists.txt
#
# This configures all source files for the main firmware component.

# Define source files based on board type
set(SRCS
    "main.c"
    "hal/hal_audio.c"
    "audio/audio_buffer.c"
    "network/wifi_manager.c"
    "network/tcp_client.c"
    "system/watchdog.c"
)

if(CONFIG_ENABLE_BENCHMARK)
    list(APPEND SRCS "benchmark.c")
endif()

# Add XVF3800 driver for that board variant
if(CONFIG_BOARD_RESPEAKER_XVF3800)
    list(APPEND SRCS
        "drivers/xvf3800/xvf3800.c"
        "drivers/xvf3800/xvf3800_i2c.c"
    )
endif()

# Define include directories
set(INCLUDE_DIRS
    "."
    "config"
    "hal"
    "audio"
    "network"
    "system"
    "drivers"
)

# Register component with ESP-IDF build system
idf_component_register(
    SRCS ${SRCS}
    INCLUDE_DIRS ${INCLUDE_DIRS}
    REQUIRES
        driver
        esp_wifi
        esp_event
        nvs_flash
        lwip
        esp_netif
        esp_timer
        esp_psram
        esp_system
        feature_extractor
)

# Add compiler warnings
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Werror -Wno-unused-function)
