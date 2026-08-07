from __future__ import annotations

import sys
from pathlib import Path


SOLUTION_ROOT = Path(__file__).resolve().parents[1]
if str(SOLUTION_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLUTION_ROOT))
