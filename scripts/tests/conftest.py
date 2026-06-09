"""Make the ``scripts/`` directory importable for the test modules."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
