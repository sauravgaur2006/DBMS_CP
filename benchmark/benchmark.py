"""
Benchmark Engine Entrypoint for Person 4 structure.
Forwards execution to root benchmark.py.
"""
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from benchmark import main

if __name__ == "__main__":
    main()
