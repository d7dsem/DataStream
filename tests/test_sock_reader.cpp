#include "../data-stream/sock_reader.hpp"
#include <vector>
#include <iostream>
#include <iomanip>
#include <cstring>
#include <cstdlib>
#include <csignal>
#include <chrono>
#include <atomic>

// Time infrastructure
using tick_t = std::chrono::steady_clock::time_point;
using duration_t = std::chrono::steady_clock::duration;

std::ostream& operator<<(std::ostream& os, const duration_t& duration) {
    auto secs = std::chrono::duration_cast<std::chrono::seconds>(duration);
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(duration - secs);
    os << secs.count() << "." << std::setfill('0') << std::setw(3) << ms.count() << "s";
    return os;
}

// Signal handling for Ctrl+C
std::atomic<bool> g_shutdown_requested{false};

void signal_handler(int signal) {
    if (signal == SIGINT) {
        g_shutdown_requested.store(true);
    }
}

constexpr int32_t DEFAULT_TIMEOUT_MS = 1000;  // 1 second

void _usage(const char* proga)
{
    std::cout << "Usage: " << proga << " [--addr dev:ip:port] [--sz <pkt_sz_max>] [--dur-sec <sec>] [--raw]"
              << "\n   1) until Ctrl+C: " << proga << " --addr enp3s0:192.168.250.196:9999 --sz 7184" 
              << "\n   2) Fixed dur: " << proga << " --addr lo:127.0.0.1:9999 --dur-sec 1.45"
              << "\n   3) Raw socket: " << proga << " --addr enp3s0:192.168.250.196:9999 --sz 7184 --raw"
              << "\n" 
              << std::endl;
}

void parse_addr(const char* addr, std::string& dev, std::string& ip, uint16_t& port)
{
    std::string full(addr);
    
    size_t first_colon = full.find(':');
    if (first_colon == std::string::npos) {
        throw std::runtime_error("Invalid format: missing first ':'");
    }
    
    size_t second_colon = full.find(':', first_colon + 1);
    if (second_colon == std::string::npos) {
        throw std::runtime_error("Invalid format: missing second ':'");
    }
    
    dev = full.substr(0, first_colon);
    ip = full.substr(first_colon + 1, second_colon - first_colon - 1);
    
    std::string port_str = full.substr(second_colon + 1);
    char* end;
    long port_val = std::strtol(port_str.c_str(), &end, 10);
    
    if (*end != '\0' || port_val < 1 || port_val > 65535) {
        throw std::runtime_error("Invalid port number");
    }
    
    port = static_cast<uint16_t>(port_val);
}

int main(int argc, const char* argv[])
{
    // Setup signal handler
    std::signal(SIGINT, signal_handler);
    
    // defaults
    std::string dev = "lo";
    std::string src_ip = "127.0.0.1"; 
    uint16_t port = 9999;
    bool is_raw = false;
    size_t chunk_sz = 9000;
    double dur_sec = -1.0;  // negative = infinite
    
    // Parse arguments
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--addr") == 0) {
            if (i + 1 >= argc) {
                std::cerr << "Error: --addr requires argument\n";
                _usage(argv[0]);
                return 1;
            }
            try {
                parse_addr(argv[++i], dev, src_ip, port);
            } catch (const std::exception& e) {
                std::cerr << "Invalid addr: " << argv[i] << " (" << e.what() << ")\n";
                _usage(argv[0]);
                return 1;
            }
        }
        else if (std::strcmp(argv[i], "--sz") == 0) {
            if (i + 1 >= argc) {
                std::cerr << "Error: --sz requires argument\n";
                _usage(argv[0]);
                return 1;
            }
            char* end;
            long val = std::strtol(argv[++i], &end, 10);
            if (*end != '\0' || val <= 0) {
                std::cerr << "Invalid size: " << argv[i] << "\n";
                return 1;
            }
            chunk_sz = static_cast<size_t>(val);
        }
        else if (std::strcmp(argv[i], "--dur-sec") == 0) {
            if (i + 1 >= argc) {
                std::cerr << "Error: --dur-sec requires argument\n";
                _usage(argv[0]);
                return 1;
            }
            char* end;
            dur_sec = std::strtod(argv[++i], &end);
            if (*end != '\0' || dur_sec <= 0) {
                std::cerr << "Invalid duration: " << argv[i] << "\n";
                return 1;
            }
        }
        else if (std::strcmp(argv[i], "--raw") == 0) {
            is_raw = true;
        }
        else {
            std::cerr << "Unknown option: " << argv[i] << "\n";
            _usage(argv[0]);
            return 1;
        }
    }
    
    try {
        // Create socket reader
        I_STREAM_READER* reader = create_socket_reader(
            src_ip, port, dev,
            DEFAULT_TIMEOUT_MS,
            chunk_sz,
            is_raw
        );
        
        std::cout << "Starting reader: " << reader->get_type() 
                  << " [" << src_ip << ":" << port << "]"
                  << " chunk_size=" << chunk_sz
                  << " timeout=" << DEFAULT_TIMEOUT_MS << "ms";
        
        if (is_raw) {
            std::cout << " dev=" << dev;
        }
        
        if (dur_sec > 0) {
            std::cout << " duration=" << dur_sec << "s";
        } else {
            std::cout << " (until Ctrl+C)";
        }
        std::cout << "\n" << std::endl;
        
        // Allocate buffer
        std::vector<uint8_t> buffer(chunk_sz);
        
        // Statistics
        size_t total_bytes = 0;
        size_t packet_count = 0;
        size_t timeout_count = 0;
        tick_t last_packet_time = std::chrono::steady_clock::now();
        tick_t start_time = last_packet_time;
        
        // Duration check
        auto duration_limit = std::chrono::duration_cast<duration_t>(
            std::chrono::duration<double>(dur_sec > 0 ? dur_sec : 1e9)
        );
        
        // Main loop
        while (!g_shutdown_requested.load()) {
            // Check duration limit
            if (dur_sec > 0) {
                auto elapsed = std::chrono::steady_clock::now() - start_time;
                if (elapsed >= duration_limit) {
                    std::cout << "\nDuration limit reached (" << elapsed << ")\n";
                    break;
                }
            }
            
            try {
                size_t bytes_read = reader->read_into(buffer.data());
                
                // Packet received
                tick_t now = std::chrono::steady_clock::now();
                auto since_last = now - last_packet_time;
                last_packet_time = now;
                
                total_bytes += bytes_read;
                packet_count++;
                
                std::cout << "[" << (now - start_time) << "] "
                          << "Packet #" << packet_count 
                          << ": " << bytes_read << " bytes"
                          << " (gap: " << since_last << ")"
                          << std::endl;
                
            } catch (const ReadTimeout& e) {
                // Timeout - no traffic
                tick_t now = std::chrono::steady_clock::now();
                auto since_last = now - last_packet_time;
                timeout_count++;
                
                std::cout << "[" << (now - start_time) << "] "
                          << "TIMEOUT #" << timeout_count
                          << " - no traffic for " << since_last
                          << std::endl;
                
                // Continue waiting for traffic
            }
        }
        
        // Final statistics
        tick_t end_time = std::chrono::steady_clock::now();
        auto total_duration = end_time - start_time;
        
        std::cout << "\n=== Session Summary ===" << std::endl;
        std::cout << "Total duration: " << total_duration << std::endl;
        std::cout << "Packets received: " << packet_count << std::endl;
        std::cout << "Total bytes: " << total_bytes << std::endl;
        std::cout << "Timeouts: " << timeout_count << std::endl;
        
        if (packet_count > 0) {
            double avg_packet_size = static_cast<double>(total_bytes) / packet_count;
            std::cout << "Average packet size: " << std::fixed << std::setprecision(1) 
                      << avg_packet_size << " bytes" << std::endl;
            
            auto duration_sec = std::chrono::duration_cast<std::chrono::milliseconds>(total_duration).count() / 1000.0;
            if (duration_sec > 0) {
                double throughput_mbps = (total_bytes * 8.0) / (duration_sec * 1e6);
                std::cout << "Throughput: " << std::fixed << std::setprecision(2) 
                          << throughput_mbps << " Mbps" << std::endl;
            }
        }
        
        // Cleanup
        delete reader;
        
        if (g_shutdown_requested.load()) {
            std::cout << "\nShutdown requested (Ctrl+C)" << std::endl;
        }
        
    } catch (const SocketError& e) {
        std::cerr << "Socket error: " << e.what() << "\n";
        return 1;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << "\n";
        return 1;
    }
    
    return 0;
}