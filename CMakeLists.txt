cmake_minimum_required(VERSION 3.20)
project(DataStreamABS CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Output directories
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)


# DataStream library (header-only: file_reader + sock_reader)
add_library(data_stream INTERFACE)
target_include_directories(data_stream INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR}/data-stream
)

# Test executables

# File Reader
add_executable(test_file_reader
    tests/test_file_reader.cpp
)
add_executable(bench_file_reader
    tests/bench_fread.cpp
)


target_link_libraries(test_file_reader PRIVATE
    data_stream
)

# Sock Reader
add_executable(test_sock_reader
    tests/test_sock_reader.cpp
)
target_link_libraries(test_sock_reader PRIVATE
    data_stream
)

# Platform-specific libraries for test_sock_reader
if(WIN32)
    # WinSock2 for Windows
    target_link_libraries(test_sock_reader PRIVATE ws2_32)
endif()

if(UNIX)
    # Threads for atomic/signal on Unix
    find_package(Threads REQUIRED)
    target_link_libraries(test_sock_reader PRIVATE Threads::Threads)
endif()

# Fabric test (add when ready)