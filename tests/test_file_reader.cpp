#include "../data-stream/file_reader.hpp"
#include <vector>
#include <iostream>

int main(int argc, char* argv[])
{
    // deafults
    std::string f_path = "./test_data.bin"; 
    size_t chunk_sz = 1024*1024*4;  // 4MB chunks
    if (argc>1)
    {
        f_path = argv[1];
        if (argc>2) 
        {
            try {
                chunk_sz = std::stoull(argv[2]);
            } catch (const std::exception& e) {
                std::cerr << "Invalid chunk size " << argv[2] << std::endl;
                return 1;
            }
        }
    }

    try {
        FileReader fr(f_path, chunk_sz);
        
        std::cout << "File: " << fr.get_file_path().string() << "\n";
        std::cout << "Size: " << fr.get_size() << " bytes\n";
        std::cout << "Chunks: " << fr.get_chunk_count() << "\n";
        std::cout << "Chunk size: " << fr.get_chunk_size() << "\n";
        
        std::vector<uint8_t> buffer(chunk_sz);
        
        size_t total_read = 0;
        while (true) {
            size_t rd = fr.read_into(buffer.data());
            if (rd == 0) break;
            
            total_read += rd;
            std::cout << "Read chunk: " << rd << " bytes\n";
            
            // Process buffer here...
        }
        
        std::cout << "Total read: " << total_read << " bytes\n";
        
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << "\n";
        return 1;
    }
    
    return 0;
}