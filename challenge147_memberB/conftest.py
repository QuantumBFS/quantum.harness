"""Make ``metts_b`` importable for pytest without an installed package.

Adds ``src/`` to sys.path so ``from metts_b... import ...`` works from the
tests directory. The bridge module additionally puts challenge147stuff/solution
on sys.path for the shared core/ed.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
