from __future__ import annotations

from pathlib import Path


def exact_fci_energy(path: str | Path) -> float:
    """Return the exact energy for a small FCIDUMP using PySCF FCI."""

    from pyscf import fci
    from pyscf.tools import fcidump

    integrals = fcidump.read(str(path))
    norb = int(integrals["NORB"])
    nelec = int(integrals["NELEC"])
    ms2 = int(integrals["MS2"])
    if (nelec + ms2) % 2 or (nelec - ms2) % 2:
        raise ValueError("NELEC and MS2 do not define integral spin populations")
    populations = ((nelec + ms2) // 2, (nelec - ms2) // 2)
    energy, _ = fci.direct_spin1.kernel(
        integrals["H1"],
        integrals["H2"],
        norb,
        populations,
        ecore=float(integrals["ECORE"]),
    )
    return float(energy)
