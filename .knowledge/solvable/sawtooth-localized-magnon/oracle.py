"""Sawtooth-chain localized-magnon oracle (spin-1/2 delta chain, PBC).

H = sum_i [ j1 A_i.A_{i+1} + j2 (A_i.B_i + B_i.A_{i+1}) ] - h sum S^z,
base A_i = site 2i, apex B_i = site 2i+1 (0-based), S = sigma/2 operators.

Exact at the flat-band point j2 = 2*j1: the lowest one-magnon band is exactly
flat at eps = -4*j1, so at h_sat = 4*j1 localized-magnon crystals cost zero
energy — a magnetization jump dM = M_sat/2, a ground-state degeneracy counted
by hard-dimer coverings (Lucas numbers), and residual entropy S/N = ln(phi)/2.
The Monti-Suto point j2 = j1, h = 0 is a DIFFERENT special point (exact
two-fold valence-bond ground state) — do not conflate them (issue #112 trap).

S card: all card quantities scripted. Dense per-sector diagonalization,
so sizes are small (N <= 16; N=12 default covers all anchors in seconds).
"""
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402


def sawtooth_hamiltonian(N, j2=2.0, j1=1.0, h=0.0, n_up=None):
    """Sparse H in the n_up sector (full basis if None). PBC, spin-1/2."""
    basis = [s for s in range(1 << N) if n_up is None or bin(s).count("1") == n_up]
    idx = {s: i for i, s in enumerate(basis)}
    nc = N // 2
    bonds = [((2 * i) % N, (2 * i + 2) % N, j1) for i in range(nc)]
    bonds += [((2 * i) % N, (2 * i + 1) % N, j2) for i in range(nc)]
    bonds += [((2 * i + 1) % N, (2 * i + 2) % N, j2) for i in range(nc)]
    row, col, val = [], [], []

    def sz(s, i):
        return 0.5 if s >> i & 1 else -0.5

    for s in basis:
        diag = -h * sum(sz(s, i) for i in range(N))
        for i, j, J in bonds:
            diag += J * sz(s, i) * sz(s, j)
            if (s >> i & 1) != (s >> j & 1):
                t = s ^ (1 << i) ^ (1 << j)
                if t in idx:
                    row.append(idx[s])
                    col.append(idx[t])
                    val.append(J * 0.5)
        row.append(idx[s])
        col.append(idx[s])
        val.append(diag)
    return sp.csr_matrix((val, (row, col)), shape=(len(basis),) * 2)


def _sector_spectrum(N, j2, j1, h, k):
    return np.linalg.eigvalsh(
        sawtooth_hamiltonian(N, j2=j2, j1=j1, h=h, n_up=N - k).toarray())


def polarized_energy(N, j1, j2, h):
    """Energy of the fully polarized state (N_c j1 + 2 N_c j2 bonds at J/4, minus h N/2)."""
    nc = N // 2
    return (j1 + 2 * j2) * nc / 4 - h * N / 2


def compute(N=12, j2=2.0, j1=1.0, h=4.0):
    """Sawtooth localized-magnon oracle: band edges, ground energy, GS degeneracy at field h."""
    band = _sector_spectrum(N, j2, j1, 0.0, 1)[: N // 2] - polarized_energy(N, j1, j2, 0.0)
    spectra = [_sector_spectrum(N, j2, j1, h, k) for k in range(N // 2 + 1)]
    e_ground = min(w[0] for w in spectra)
    degeneracy = int(sum(np.sum(np.abs(w - e_ground) < 1e-8) for w in spectra))
    return {
        "one_magnon_band_min": float(band.min()),
        "one_magnon_band_max": float(band.max()),
        "e_ground": float(e_ground),
        "gs_degeneracy": degeneracy,
        "entropy_per_site": float(np.log(degeneracy) / N),
    }


def self_test():
    N = 12
    # 1. Flat band at j2 = 2*j1: lowest one-magnon band exactly flat at -4*j1.
    r = compute(N=N, j2=2.0, j1=1.0, h=4.0)
    assert abs(r["one_magnon_band_min"] + 4.0) < 1e-10, r
    assert r["one_magnon_band_max"] - r["one_magnon_band_min"] < 1e-10, r
    # 2. Zero-cost localized magnons: ground energy equals the polarized energy
    #    at h_sat, and the GS degeneracy is Lucas(6) = 18 (hard-dimer count).
    assert abs(r["e_ground"] - polarized_energy(N, 1.0, 2.0, 4.0)) < 1e-10, r
    assert r["gs_degeneracy"] == 18, r
    # 3. Residual entropy S/N = ln(18)/12 = 0.2409 ~ ln(phi)/2 = 0.2406.
    assert abs(r["entropy_per_site"] - 0.2406) < 1e-3, r
    # 4. Jump plateau: at h_sat the sector ground energy is flat for k <= N/4
    #    (hard-dimer constraint) and rises once magnons overlap.
    e = np.array([_sector_spectrum(N, 2.0, 1.0, 4.0, k)[0] for k in range(N // 2 + 1)])
    kf = N // 4
    assert np.allclose(e[: kf + 1], e[0], atol=1e-8), e
    assert all(e[k] - e[0] > 1e-3 for k in range(kf + 1, N // 2 + 1)), e
    # 5. Monti-Suto point j2 = j1, h = 0: exactly 2-fold GS, gapped above.
    w = _sector_spectrum(N, 1.0, 1.0, 0.0, N // 2)
    assert w[1] - w[0] < 1e-10 and w[2] - w[0] > 1e-3, w[:3]
    print("sawtooth-localized-magnon: all self-test anchors pass")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "self-test":
        self_test()
    else:
        oracle_main(compute, {"N": (int, 12), "j2": (float, 2.0),
                              "j1": (float, 1.0), "h": (float, 4.0)})
