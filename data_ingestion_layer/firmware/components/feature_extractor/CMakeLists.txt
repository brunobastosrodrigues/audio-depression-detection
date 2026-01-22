# CMakeLists.txt for feature_extractor component

# List of source files
set(SRCS
    "vad.c"
    "audio_quality.c"
)

# List of include directories
set(INCLUDE_DIRS
    "include"
)

# Register the component
idf_component_register(
    SRCS "${SRCS}"
    INCLUDE_DIRS "${INCLUDE_DIRS}"
    PRIV_REQUIRES main
)
