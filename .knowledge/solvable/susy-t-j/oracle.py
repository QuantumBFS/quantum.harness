"""Supersymmetric t-J chain oracle at the SUSY point J = 2t.

H = -t Σ_{⟨ij⟩σ} P(c†_{iσ}c_{jσ}+h.c.)P + J Σ_{⟨ij⟩}(S_i·S_j - ¼ n_i n_j),  P = no double occupancy.

T3 (Bethe ansatz), Tier B, Script P. At J = 2t the chain acquires a graded su(2|1)
supersymmetry (Sutherland 1975; Schlottmann 1987) and is Bethe-ansatz integrable.
The scriptable subset is exact diagonalisation directly in the projected
occupation basis {0,↑,↓}^L (dim 3^L): hopping (fermion signs explicit),
spin-exchange, and the -¼ n_i n_j term. OBC is used so nearest-neighbour hops carry
a trivial +1 sign (validated against hand-computed 2- and 3-site spectra).

SUSY signature (pinned here): the half-filled (N=L) and one-hole (N=L-1) sectors
share many *exact* common eigenvalues at J=2t — supermultiplets related by the odd
supercharge that adds/removes an electron — which all lift at J=1.9t. The
thermodynamic ground energy is tabulated (TBA, not coded); P-scope statement below.
"""
import itertools
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402

SUSY_J = 2.0  # J = 2t supersymmetric point (t = 1)
# Half-filling (n=1) thermodynamic e0: kinetic term fully projected → Heisenberg
# with J=2t plus the -¼ n_i n_j term (=-¼ per bond); e0 = J(¼-ln2) - J/4 = -2 ln2.
E0_HALF_FILLING_THERMO = -2.0 * np.log(2.0)  # ≈ -1.386294, exact (Heisenberg limit)


def _states(L):
    return list(itertools.product((0, 1, 2), repeat=L))  # 0=∅, 1=↑, 2=↓


def tj_hamiltonian(L, t=1.0, J=SUSY_J, pbc=False):
    """Projected t-J Hamiltonian in the 3^L occupation basis (sparse, OBC by default)."""
    states = _states(L)
    index = {s: i for i, s in enumerate(states)}
    D = len(states)
    H = sp.dok_matrix((D, D))
    bonds = [(i, i + 1) for i in range(L - 1)]
    if pbc and L > 2:
        bonds.append((L - 1, 0))
    for si, s in enumerate(states):
        for (i, j) in bonds:
            # --- hopping: move an electron i<->j (target must be empty: projection) ---
            for frm, to in ((i, j), (j, i)):
                if s[frm] != 0 and s[to] == 0:
                    ns = list(s)
                    ns[to] = ns[frm]
                    ns[frm] = 0
                    # fermion sign: annihilate at `frm`, then create at `to`
                    sgn = (-1) ** sum(1 for k in range(frm) if s[k] != 0)
                    tmp = list(s)
                    tmp[frm] = 0
                    sgn *= (-1) ** sum(1 for k in range(to) if tmp[k] != 0)
                    H[index[tuple(ns)], si] += -t * sgn
            # --- J(S_i·S_j - ¼ n_i n_j), only when both sites occupied ---
            if s[i] != 0 and s[j] != 0:
                szi = 0.5 if s[i] == 1 else -0.5
                szj = 0.5 if s[j] == 1 else -0.5
                H[si, si] += J * (szi * szj - 0.25)
                if s[i] != s[j]:                    # ½(S+S- + S-S+): spin swap, sign +1
                    ns = list(s)
                    ns[i], ns[j] = s[j], s[i]
                    H[index[tuple(ns)], si] += J * 0.5
    return H.tocsr(), states


def sector_spectrum(L, N, J=SUSY_J, pbc=False):
    """Sorted eigenvalues of the N-electron sector (dense sub-block)."""
    H, states = tj_hamiltonian(L, 1.0, J, pbc)
    nelec = np.array([sum(1 for x in s if x != 0) for s in states])
    idx = np.where(nelec == N)[0]
    return np.sort(np.linalg.eigvalsh(H[np.ix_(idx, idx)].toarray()))


def n_shared_eigenvalues(spec_a, spec_b, tol=1e-8):
    """Greedy one-to-one count of eigenvalues common to two spectra within tol."""
    used = np.zeros(len(spec_b), bool)
    shared = []
    for x in spec_a:
        for k, y in enumerate(spec_b):
            if not used[k] and abs(x - y) < tol:
                shared.append(0.5 * (x + y))
                used[k] = True
                break
    return shared


def compute(L=6):
    """SUSY t-J (J=2t) ED diagnostics on an L-site OBC chain."""
    half = sector_spectrum(L, L)             # N=L (half filling → Heisenberg, J=2)
    onehole = sector_spectrum(L, L - 1)      # N=L-1 (one hole)
    shared = n_shared_eigenvalues(half, onehole)
    return {
        "susy_point_J_over_t": SUSY_J,
        "e0_halffilling_per_site": half[0] / L,
        "e0_halffilling_thermo": E0_HALF_FILLING_THERMO,
        "n_susy_supermultiplets": len(shared),
        "lowest_supermultiplet_energy": min(shared) if shared else None,
    }


def self_test():
    # anchor 1 (hand-computable 2-site spectrum, J=2, OBC single bond):
    #   N=0: {0}; N=1: {-1,-1,1,1} (bonding/antibonding, one per spin);
    #   N=2: triplet {0,0,0}, singlet {-J}={-2}.  Full: {-2,-1,-1,0,0,0,0,1,1}.
    H2, _ = tj_hamiltonian(2, 1.0, 2.0)
    ev2 = np.sort(np.linalg.eigvalsh(H2.toarray()))
    assert np.allclose(ev2, [-2, -1, -1, 0, 0, 0, 0, 1, 1], atol=1e-9)

    # anchor 2 (fermion-sign check via 2-site sub-spectra, generic J):
    #   the N=2 singlet energy is exactly -J (S·S=-¾, n_i n_j=1 → J(-¾-¼)).
    for J in (1.0, 1.9, 2.0):
        HJ, _ = tj_hamiltonian(2, 1.0, J)
        assert abs(np.min(np.linalg.eigvalsh(HJ.toarray())) - (-J)) < 1e-9

    # anchor 3 (3-site sign structure): the hopping is non-trivial only through the
    #   many-body signs; check the N=1 (single electron, no J) tight-binding triplet
    #   -√2, 0, +√2 appears (open 3-site chain, per spin) in the full spectrum.
    ev3 = sector_spectrum(3, 1, J=2.0)
    assert np.allclose(np.unique(np.round(ev3, 9)),
                       np.round([-np.sqrt(2), 0.0, np.sqrt(2)], 9))

    # anchor 4 (SUSY supermultiplet, THE anchor): at J=2t the half-filled (N=6) and
    #   one-hole (N=5) sectors of the L=6 OBC chain share many exact eigenvalues; the
    #   lowest is E = -(2+√3). At J=1.9t not a single eigenvalue is shared (to 1e-8):
    #   the supermultiplets split.
    half2 = sector_spectrum(6, 6, J=2.0)
    hole2 = sector_spectrum(6, 5, J=2.0)
    shared2 = n_shared_eigenvalues(half2, hole2, tol=1e-8)
    assert len(shared2) >= 20                       # rich supermultiplet structure
    assert abs(min(shared2) - (-(2.0 + np.sqrt(3.0)))) < 1e-8

    half19 = sector_spectrum(6, 6, J=1.9)
    hole19 = sector_spectrum(6, 5, J=1.9)
    assert len(n_shared_eigenvalues(half19, hole19, tol=1e-8)) == 0

    # anchor 5: half-filling reduces to Heisenberg(J=2) + the -¼ n_i n_j term; the
    #   L=6 OBC per-site energy sits above the thermodynamic -2 ln2 (open ends).
    assert half2[0] / 6.0 > E0_HALF_FILLING_THERMO          # finite OBC lies above
    assert half2[0] / 6.0 < E0_HALF_FILLING_THERMO + 0.2    # but within 0.2


if __name__ == "__main__":
    oracle_main(compute, {"L": (int, 6)})
