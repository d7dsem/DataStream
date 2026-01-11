import sys
print(f"====> Running: {sys.executable}")

import argparse
import numpy as np
from pathlib import Path

#!/usr/bin/env python3



def generate_binary_file(filepath: str, size_mb: int):
    """
    Generate binary file with int16 data
    
    Args:
        filepath: output file path
        size_mb: desired file size in megabytes
    """
    # Calculate number of int16 values needed
    # int16 = 2 bytes
    bytes_total = size_mb * 1024 * 1024
    num_values = bytes_total // 2
    
    # Generate random int16 data
    data = np.random.randint(-32768, 32767, size=num_values, dtype=np.int16)
    
    # Write to file
    with open(filepath, 'wb') as f:
        data.tofile(f)
    
    actual_size = num_values * 2 / (1024 * 1024)
    print(f"Generated: {filepath}")
    print(f"Size: {actual_size:.2f} MB ({num_values} int16 values)")


def main(args:argparse.Namespace):
    
    # Determine final filepath
    if args.filepath:
        filepath = args.filepath
    elif args.dirpath:
        # Auto-generate filename
        filename = f"test_data_{args.size_mb}mb.bin"
        filepath = Path(args.dirpath) / filename
    else:
        print("Error: either --filepath or --dirpath must be specified", file=sys.stderr)
        sys.exit(1)
        
    if args.size_mb <= 0:
        print("Error: size must be positive", file=sys.stderr)
        sys.exit(1)
    
    generate_binary_file(filepath, args.size_mb)


if __name__ == '__main__':
    
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description='Generate binary file with int16 data')
        parser.add_argument('-f', '--filepath', help='Output file path')
        parser.add_argument('-d', '--dirpath', help='Output dir path')
        parser.add_argument('-s','--size-mb', type=int, help='Desired file size in MB (int)')

        args = parser.parse_args()
    else:
        # create default
        size_mb = 120
        fp = f"./test_data_{size_mb}mb.bin"
        args = argparse.Namespace(
            filepath=fp,
            size_mb=size_mb
        )

    main(args)