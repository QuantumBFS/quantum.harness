from __future__ import annotations

import warnings
from pathlib import Path

from src.rhf_check import rhf_energy


FIXTURE = Path(__file__).parent / "data" / "hubbard_dimer.FCIDUMP"


def test_hubbard_dimer_restricted_hartree_fock_energy() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        energy = rhf_energy(FIXTURE)

    assert abs(energy - 0.0) < 1.0e-10
    assert caught == []
