cmake_minimum_required(VERSION 3.20)
project(DataStreamABS CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Output directories
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

# FileReader library (header-only)
add_library(file_reader INTERFACE)

target_include_directories(file_reader INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR}/data-stream
)

# Test executable
add_executable(test_file_reader
    tests/test_file_reader.cpp
)
add_executable(bench_file_reader
    tests/bench_fread.cpp
)


target_link_libraries(test_file_reader PRIVATE
    file_reader
)