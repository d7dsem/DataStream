#!/usr/bin/env python3
import os
import sys

GiB = 1024 * 1024 * 1024
TAIL = 180
TOTAL = GiB + TAIL
CHUNK = 8 * 1024 * 1024  # 8 MiB

def make_file(path: str, seed: int) -> None:
    rng = os.urandom
    written = 0
    # Для швидкості: пишемо повторювані блоки псевдо-випадкових даних
    # (os.urandom теж ок, але може бути повільніше на деяких системах)
    block = bytes((i + seed) & 0xFF for i in range(256)) * (CHUNK // 256)
    with open(path, "wb", buffering=CHUNK) as f:
        while written + CHUNK <= TOTAL:
            f.write(block)
            written += CHUNK
        tail = TOTAL - written
        if tail:
            f.write(block[:tail])
    if hasattr(os, "sync"):
        os.sync()

def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <file1> <file2>", file=sys.stderr)
        return 2
    f1, f2 = sys.argv[1], sys.argv[2]
    make_file(f1, seed=1)
    make_file(f2, seed=7)
    print(f"Created:\n  {f1}: {TOTAL} bytes\n  {f2}: {TOTAL} bytes")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
