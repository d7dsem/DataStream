# DATA STREAM SORCE

 Допоміжна кроссплатформенна бібліотека, яка наДає уніфікований інтерфейс доступу до даних `size_t I_STREAM_READER::read_into(uint8_t* buff_ptr)`

Джерела даних:
- файл (з вказанням початкового зсуву)
- мережа (Streaming over UDP):
    - regular socket
    - raw socket (Linux only)
    - LibPCAP(NPCP)
- можливо інші джерела, типу rtl-usb

**Streaming over UDP** - це byte stream послідовних блоків payload з можливими gaps. Можливо є sequence numbers або інша мета інфа але це не скоуп цього продукту.

**Особлипвості**
    - Continuous flow (не request-response)
    - Фіксований [максимальний] розмір payload (можливо останній блок менше)
    - [optional] Sequence number в header для детекції втрат
    - [optional] Timestamp metadata


┌─────────────────────────────────┐
│   APPLICATION                   │ <- gap handling, sample alignment etc
│   (protocol semantics)          │
├─────────────────────────────────┤
│   I_STREAM_READER               │ <- delivers bytes
│   read_into(uint8_t*)           │    (file / UDP socket / raw / pcap / rtl-sdr, etc)
└─────────────────────────────────┘

# Instance Deploy 

Factory створює reader з fixed chunk size.


```cpp
// Factory створює reader відповідного типу з fixed chunk size
// Ілюстарція, псевдокод.
template<ReaderType="File:bin">
I_STREAM_READER* DeployReader(CHUNK_SIZE, type_specific_params...);
```

DeployReader<...>(...) = wrapper function, яка на основі runtime parameters інстанціює потрібний конкретний клас і повертає через I_STREAM_READER* interface.


Caller responsibility: 
- allocate buffer >= CHUNK_SIZE
- pass pointer to read_into()

Reader responsibility:
- read up to CHUNK_SIZE bytes
- return actual bytes read (rd <= CHUNK_SIZE)
- never write beyond CHUNK_SIZE

# Error handling model

```cpp

constexpr size_t CHUNK_SIZE = 1024*1024*4;
I_STREAM_READER* reader = DeployReader(CHUNK_SIZE, source_params...)

std::vector<uint8_t> buff;
buff.resize(CHUNK_SIZE);
uint8_t *data=buff.data();
size_t rd;
try{
    rd = reader->read_into(data);
}
catch{
    ...
}
```

## Threading model

Usage: Single-threaded per reader instance.