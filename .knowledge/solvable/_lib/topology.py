"""Topological invariants: Fukui-Hatsugai-Suzuki Chern number, 1D winding."""
import numpy as np


def chern(hk, nocc, nk=60):
    ks = np.linspace(0, 2 * np.pi, nk, endpoint=False)
    occ = np.empty((nk, nk), dtype=object)
    for i, kx in enumerate(ks):
        for j, ky in enumerate(ks):
            _, v = np.linalg.eigh(hk(kx, ky))
            occ[i, j] = v[:, :nocc]
    total = 0.0
    for i in range(nk):
        for j in range(nk):
            u1 = np.linalg.det(occ[i, j].conj().T @ occ[(i + 1) % nk, j])
            u2 = np.linalg.det(occ[(i + 1) % nk, j].conj().T @ occ[(i + 1) % nk, (j + 1) % nk])
            u3 = np.linalg.det(occ[(i + 1) % nk, (j + 1) % nk].conj().T @ occ[i, (j + 1) % nk])
            u4 = np.linalg.det(occ[i, (j + 1) % nk].conj().T @ occ[i, j])
            total += np.angle(u1 * u2 * u3 * u4)
    return int(round(total / (2 * np.pi)))


def winding(gk, nk=2001):
    ks = np.linspace(0, 2 * np.pi, nk)
    phase = np.unwrap(np.angle([gk(k) for k in ks]))
    return int(round((phase[-1] - phase[0]) / (2 * np.pi)))
