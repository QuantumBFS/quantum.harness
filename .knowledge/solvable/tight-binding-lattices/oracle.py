"""Tight-binding lattices oracle: H = -t * (nearest-neighbor adjacency), t=1
default, four 2D lattices selectable via `--lattice`.

Bloch Hamiltonians are written in *reduced* crystal-momentum coordinates
`u = k . a1`, `v = k . a2` (each ranging over one full 2pi period), where
`a1, a2` are the lattice's primitive Bravais vectors. Every Bloch matrix
entry here is, by construction, a function of `u, v` only (never of `kx, ky`
directly), so a uniform grid `u, v in [0, 2pi)` is *exactly* one Brillouin
zone for every lattice below - no basis-dependent BZ shape/inversion code is
needed. All eigenvalues are obtained by numerical diagonalization of the
Bloch matrix (`np.linalg.eigvalsh`, vectorized over the whole grid), not by
hand-substituting closed-form dispersions, so the reported bandwidth /
flat-band / DOS numbers are cross-checked against - not merely asserted to
equal - the closed forms written out in ORACLE.md.

Lattices (primitive vectors in units where the shortest bond length is set
by the hopping range; only their *directions/ratios* matter since only
u = k.a1, v = k.a2 ever appear):

  square:     a1=(1,0), a2=(0,1); 1 site/cell.
              H(u,v) = -2t(cos u + cos v).
  honeycomb:  a1, a2 the triangular Bravais vectors at 60 deg; 2 sites/cell
              (A at cell origin, B displaced so A-B bonds live at
              cell-vectors 0, -a1, -a2). f(u,v) = 1 + e^{iu} + e^{iv};
              H(u,v) = [[0, -t f],[-t f*, 0]], eps = +-t|f|.
  kagome:     same a1,a2 as honeycomb; 3 sites/cell (A,B,C at 0, a1/2, a2/2).
              x=cos(u/2), y=cos(v/2), z=cos((v-u)/2);
              H(u,v) = -2t [[0,x,y],[x,0,z],[y,z,0]].
  lieb:       a1=(1,0), a2=(0,1); 3 sites/cell (A corner at 0, B edge-center
              at a1/2, C edge-center at a2/2; only A-B and A-C bonds).
              hAB=-t(1+e^{-iu}), hAC=-t(1+e^{-iv});
              H(u,v) = [[0,hAB,hAC],[hAB*,0,0],[hAC*,0,0]].

Flat-band detection: for each sorted-eigenvalue slot (band index after
per-k ascending sort), compute its spread (max-min) over the whole grid; a
slot with spread below a generous tolerance is reported as the flat band
(the actual reported `flat_band_flatness` is the true numeric spread, always
at floating-point-roundoff level for the lattices that do have one - see
self_test).
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402

_N_BANDS = {"square": 1, "honeycomb": 2, "kagome": 3, "lieb": 3}
_FLAT_TOL = 1e-6  # detection threshold; reported flatness is the true spread


def bloch(lattice, U, V, t=1.0):
    """Bloch Hamiltonian, batched over arrays U, V of reduced momenta (u,v).

    Returns an array of shape U.shape + (n_bands, n_bands).
    """
    shape = np.broadcast(U, V).shape
    U = np.broadcast_to(U, shape)
    V = np.broadcast_to(V, shape)
    if lattice == "square":
        H = np.zeros(shape + (1, 1), dtype=complex)
        H[..., 0, 0] = -2 * t * (np.cos(U) + np.cos(V))
        return H
    if lattice == "honeycomb":
        f = 1 + np.exp(1j * U) + np.exp(1j * V)
        H = np.zeros(shape + (2, 2), dtype=complex)
        H[..., 0, 1] = -t * f
        H[..., 1, 0] = -t * np.conj(f)
        return H
    if lattice == "kagome":
        x = np.cos(U / 2)
        y = np.cos(V / 2)
        z = np.cos((V - U) / 2)
        H = np.zeros(shape + (3, 3), dtype=complex)
        H[..., 0, 1] = H[..., 1, 0] = -2 * t * x
        H[..., 0, 2] = H[..., 2, 0] = -2 * t * y
        H[..., 1, 2] = H[..., 2, 1] = -2 * t * z
        return H
    if lattice == "lieb":
        hAB = -t * (1 + np.exp(-1j * U))
        hAC = -t * (1 + np.exp(-1j * V))
        H = np.zeros(shape + (3, 3), dtype=complex)
        H[..., 0, 1] = hAB
        H[..., 1, 0] = np.conj(hAB)
        H[..., 0, 2] = hAC
        H[..., 2, 0] = np.conj(hAC)
        return H
    raise ValueError(f"unknown lattice {lattice!r}; choose square|honeycomb|kagome|lieb")


def _dirac_K():
    """Analytic Dirac-point location in reduced coords: solves
    1 + e^{iu} + e^{iv} = 0 via {0, u, v} = {0, 2pi/3, 4pi/3} (cube roots of
    unity sum to zero)."""
    return 2 * np.pi / 3, 4 * np.pi / 3


def compute(lattice="square", t=1.0, nk=200):
    """Tight-binding band-structure oracle for one of four 2D lattices."""
    n_bands = _N_BANDS.get(lattice)
    if n_bands is None:
        raise ValueError(f"unknown lattice {lattice!r}; choose square|honeycomb|kagome|lieb")

    us = np.linspace(0.0, 2.0 * np.pi, nk, endpoint=False)
    vs = np.linspace(0.0, 2.0 * np.pi, nk, endpoint=False)
    U, V = np.meshgrid(us, vs, indexing="ij")
    H = bloch(lattice, U, V, t)
    evals = np.linalg.eigvalsh(H)  # shape (nk, nk, n_bands), ascending per k
    flat = evals.reshape(-1, n_bands)

    bandwidth = float(flat.max() - flat.min())

    flat_band_energy = float("nan")
    flat_band_flatness = float("nan")
    for b in range(n_bands):
        spread = float(flat[:, b].max() - flat[:, b].min())
        if spread < _FLAT_TOL:
            flat_band_energy = float(flat[:, b].mean())
            flat_band_flatness = spread
            break

    hist, edges = np.histogram(flat.ravel(), bins=400)
    peak = int(np.argmax(hist))
    dos_van_hove = float(0.5 * (edges[peak] + edges[peak + 1]))

    dirac_point_gap = float("nan")
    if lattice == "honeycomb":
        Ku, Kv = _dirac_K()
        HK = bloch(lattice, np.array(Ku), np.array(Kv), t)
        eK = np.linalg.eigvalsh(HK)
        dirac_point_gap = float(eK[-1] - eK[0])

    return {
        "n_bands": n_bands,
        "bandwidth": bandwidth,
        "flat_band_energy": flat_band_energy,
        "flat_band_flatness": flat_band_flatness,
        "dos_van_hove": dos_van_hove,
        "dirac_point_gap": dirac_point_gap,
    }


def self_test():
    assert abs(compute(lattice="square")["bandwidth"] - 8.0) < 1e-12
    assert compute(lattice="honeycomb")["dirac_point_gap"] < 1e-12
    k = compute(lattice="kagome")
    assert abs(k["flat_band_energy"] - 2.0) < 1e-10 and k["flat_band_flatness"] < 1e-10
    assert abs(compute(lattice="lieb")["flat_band_energy"]) < 1e-12
    # honeycomb / square have no flat band
    assert np.isnan(compute(lattice="honeycomb")["flat_band_energy"])
    assert np.isnan(compute(lattice="square")["flat_band_energy"])
    # n_bands sanity
    assert compute(lattice="square")["n_bands"] == 1
    assert compute(lattice="honeycomb")["n_bands"] == 2
    assert compute(lattice="kagome")["n_bands"] == 3
    assert compute(lattice="lieb")["n_bands"] == 3


if __name__ == "__main__":
    oracle_main(compute, {"lattice": (str, "square"), "t": (float, 1.0), "nk": (int, 200)})
