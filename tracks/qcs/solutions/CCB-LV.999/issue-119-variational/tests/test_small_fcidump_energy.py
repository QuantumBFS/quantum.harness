from __future__ import annotations

import math
from pathlib import Path

from src.exact_check import exact_fci_energy


FIXTURE = Path(__file__).parent / "data" / "hubbard_dimer.FCIDUMP"


def test_hubbard_dimer_exact_energy_from_fcidump() -> None:
    expected = (4.0 - math.sqrt(4.0**2 + 16.0)) / 2.0

    energy = exact_fci_energy(FIXTURE)

    assert abs(energy - expected) < 1.0e-10
