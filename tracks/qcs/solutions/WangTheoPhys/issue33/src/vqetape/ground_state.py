"""Exact free-fermion ground-state oracle for the open TFIM."""

from __future__ import annotations

import numpy as np

from vqetape.spec import TFIMVQESpec


def tfim_bdg_spectrum(spec: TFIMVQESpec) -> np.ndarray:
    """Return the sorted particle-hole-symmetric BdG spectrum."""

    size = spec.nqubits
    normal = np.zeros((size, size), dtype=np.float64)
    pairing = np.zeros((size, size), dtype=np.float64)
    np.fill_diagonal(normal, 2.0 * spec.field)
    for site in range(size - 1):
        normal[site, site + 1] = -spec.coupling
        normal[site + 1, site] = -spec.coupling
        pairing[site, site + 1] = -spec.coupling
        pairing[site + 1, site] = spec.coupling
    bdg = np.block(
        [
            [normal, pairing],
            [-pairing, -normal],
        ]
    )
    return np.linalg.eigvalsh(bdg)


def tfim_ground_energy(spec: TFIMVQESpec) -> float:
    """Return the exact open-chain TFIM ground energy."""

    spectrum = tfim_bdg_spectrum(spec)
    positive_branch = spectrum[spec.nqubits :]
    return -0.5 * float(np.sum(positive_branch))
