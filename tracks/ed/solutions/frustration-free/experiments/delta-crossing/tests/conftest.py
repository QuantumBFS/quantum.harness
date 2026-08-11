"""Ensure delta-crossing/src is importable from tests."""
import sys
from pathlib import Path

_PROJECT = Path(__file__).resolve().parent.parent
if str(_PROJECT) not in sys.path:
    sys.path.insert(0, str(_PROJECT))
