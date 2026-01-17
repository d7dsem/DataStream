#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <chrono>
#include <iostream>

#include "../data-stream/file_reader.hpp"

using SteadyClock = std::chrono::steady_clock;

static void bench_one(const char* label,
                      const std::string& path,
                      size_t chunk_sz,
                      size_t stdio_buf_sz)
{
    FileReader reader(path, chunk_sz, 0, stdio_buf_sz);

    std::vector<uint8_t> buf(chunk_sz);

    uint64_t total = 0;
    auto t0 = SteadyClock::now();

    for (;;) {
        size_t n = reader.read_into(buf.data());
        total += n;
        if (n < chunk_sz)
            break; // EOF
    }

    auto t1 = SteadyClock::now();
    std::chrono::duration<double> dt = t1 - t0;

    double mib = (double)total / (1024.0 * 1024.0);
    double mbps = mib / dt.count();

    std::cout << label << "\n"
              << "  file: " << path << "\n"
              << "  bytes_read: " << total << "\n"
              << "  chunk_sz: " << chunk_sz << "\n"
              << "  stdio_buf_sz: " << stdio_buf_sz << "\n"
              << "  time_s: " << dt.count() << "\n"
              << "  throughput_MiB_s: " << mbps << "\n\n";
}

int main(int argc, char** argv)
{
    if (argc != 3) {
        std::cerr << "Usage: " << argv[0] << " <file_8k> <file_4m>\n";
        return 2;
    }
    const size_t M = 1024 * 1024;
    const size_t SZ1 = 4 * M;
    const size_t SZ2 = 16 * M;
    std::string lbl1 = "RUN A chunk mb " + std::to_string(SZ1/M);
    std::string lbl2 = "RUN B  chunk mb " + std::to_string(SZ2/M);
    bench_one(lbl1.c_str(), argv[1], SZ1, SZ1);
    bench_one(lbl2.c_str(), argv[2], SZ2, SZ2);

    return 0;
}
