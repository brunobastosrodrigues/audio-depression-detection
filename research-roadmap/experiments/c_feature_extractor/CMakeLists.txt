cmake_minimum_required(VERSION 3.10)
project(depression_feature_extractor C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Compiler flags
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall -Wextra -Werror")
set(CMAKE_C_FLAGS_DEBUG "-g -O0 -DDEBUG")
set(CMAKE_C_FLAGS_RELEASE "-O2 -DNDEBUG")

# Source files
set(SOURCES
    src/feature_extractor.c
    src/yin_f0.c
    src/vad.c
)

# Header files
set(HEADERS
    src/feature_extractor.h
    src/yin_f0.h
    src/vad.h
)

# Library
add_library(feature_extractor STATIC ${SOURCES} ${HEADERS})
target_include_directories(feature_extractor PUBLIC src)

# Math library
target_link_libraries(feature_extractor m)

# Test executable
add_executable(test_features test/test_features.c)
target_link_libraries(test_features feature_extractor m)

# Batch processing executable (for comparing with Python)
add_executable(extract_features test/extract_batch.c)
target_link_libraries(extract_features feature_extractor m)

# Installation
install(TARGETS feature_extractor DESTINATION lib)
install(FILES ${HEADERS} DESTINATION include/feature_extractor)

# Custom target for running tests
add_custom_target(run_tests
    COMMAND ${CMAKE_BINARY_DIR}/test_features
    DEPENDS test_features
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
)

# Memory profiling (requires valgrind)
add_custom_target(memcheck
    COMMAND valgrind --leak-check=full --show-leak-kinds=all ${CMAKE_BINARY_DIR}/test_features
    DEPENDS test_features
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
)

message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "C Compiler: ${CMAKE_C_COMPILER}")
