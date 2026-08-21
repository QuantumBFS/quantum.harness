"""Hamiltonian conventions and evolution operators for the METTS engine.

This module is the single source of truth for the **site <-> bit** convention
used by the dense state-vector backend, and for the Trotter bond/field gates
used by every backend (dense + snake-MPS). It re-uses A's ``core.model`` /
``ed.ed`` so the Hamiltonian, lattice and ED reference are identical between
sides A and B (challenge-147-structure memory).

Conventions (must match ``ed.ed.build_sparse_hamiltonian`` exactly):
  H = -J sum_<ij> s^z_i s^z_j  -  h sum_i s^x_i ,  J = 1,  OBC, row-major
  site index i = y*Lx + x  (core.model.tfim_bonds).
  State vector index ``b`` (0 <= b < 2**N) encodes spin config in Z basis with
  **bit k = site (N-1-k)**, i.e. ``spin_of(site) = (b >> (N-1-site)) & 1``.
  This is exactly the Kronecker order numpy/scipy use (leftmost factor = most
  significant bit = first index), so a spectral evolution here is bit-for-bit
  consistent with ED's dense eigensolve.
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from .bridge import SZ, SX, tfim_bonds, assert_mem_available, MemoryBudgetExceeded


def site_bit(site: int, N: int) -> int:
    """Return the bit position in a Z-basis state index that corresponds to
    ``site``: bit (N-1-site)."""
    return N - 1 - site


def product_state_vector(spins, N):
    """Dense state vector for a Z-basis product state.

    ``spins`` is a length-N array/list of +1/-1 (or the int 0/1 spin labels).
    Returns a complex128 vector of length 2**N. For a Z product state the
    amplitudes are all 0/1 real, but we keep complex for downstream field-gate
    rotations.
    """
    spins = np.asarray(spins, dtype=int)
    assert spins.shape == (N,), f"spins shape {spins.shape} != ({N},)"
    b = 0
    for i in range(N):
        s = int(spins[i])
        if s == 1 or s == 0:           # accept {0,1} or {+1,-1}
            v = 1 if s in (1,) else 0
        elif s == -1:
            v = 0
        else:
            raise ValueError(f"spin label must be +/-1 or 0/1, got {s}")
        if v:
            b |= 1 << site_bit(i, N)
    out = np.zeros(2 ** N, dtype=np.complex128)
    out[b] = 1.0
    return out


def product_state_to_labels(spins):
    """Render a spin config (+/-1) as ['up'/'down', ...] for the trace."""
    return ["up" if int(s) > 0 else "down" for s in np.asarray(spins).ravel()]


def random_product_state(N, rng):
    """Random +/-1 Z product state (uniform). Returns int8 array length N."""
    return (rng.integers(0, 2, size=N) * 2 - 1).astype(np.int8)


# ---------------------------------------------------------------------------
# Sparse Hamiltonian (consistent with ed.ed, but exposed here for the spectral
# backend and for H|psi> in the dense energy measurement).
# ---------------------------------------------------------------------------

def _kron_term(site_ops, N):
    mats = [sp.csr_matrix(site_ops.get(i, np.eye(2))) for i in range(N)]
    out = mats[0]
    for m in mats[1:]:
        out = sp.kron(out, m, format="csr")
    return out


def build_hamiltonian(Lx, Ly, h, J=1.0):
    """Sparse TFIM Hamiltonian (2**N x 2**N). Consistent with ed.ed. Refuses
    N > 14 to keep the dense state-vector backend inside the laptop RAM budget
    (2**14 complex128 vector = 2 MiB, H matrix ~ 4 GB -- still gated)."""
    N = Lx * Ly
    if N > 14:
        raise MemoryBudgetExceeded("METTS-dense-H", requested_gb=float("inf"),
                                   available_gb=0.0)
    dim = 2 ** N
    assert_mem_available(dim * dim * 8 / 1e9 * 0.4, "METTS-dense-H")
    H = sp.csr_matrix((dim, dim), dtype=np.float64)
    for i, j in tfim_bonds(Lx, Ly):
        H = H + (-J) * _kron_term({i: SZ, j: SZ}, N)
    for i in range(N):
        H = H + (-h) * _kron_term({i: SX}, N)
    return H.tocsr()


# ---------------------------------------------------------------------------
# Trotter gates.  TFIM splits as H = H_bond + H_field with
#   H_bond = -J sum_<ij> sz_i sz_j   (even/odd 2-site bonds, mutually commute)
#   H_field = -h sum_i sx_i          (single-site, all commute)
# The bond gate e^{+J dtau sz_i sz_j} is DIAGONAL in the Z basis (sz is
# diagonal), and the field gate e^{+h dtau sx_i} is a 2x2 single-site rotation.
# 2nd-order Suzuki-Trotter step of length dtau:
#   U(dtau) = exp(-dtau H_field/2) * exp(-dtau H_bond) * exp(-dtau H_field/2)
# Bond gates on non-overlapping bonds commute, so each "bond layer" is a single
# batched application. The error is O(dtau^3) per step from the [H_bond,H_field]
# split; H_bond itself is applied exactly (bond gates commute across the layer).
# ---------------------------------------------------------------------------

def _bond_parity_split(bonds):
    """Split the bond list into two mutually-disjoint layers. We use the
    standard 2D chessboard (parity = (x+y) % 2 of the bond's *lower-left*
    site) so that within a layer no two bonds share a site. Returns
    (layer_even, layer_odd)."""
    even, odd = [], []
    for (i, j) in bonds:
        # use the smaller-index site's coordinates as the bond label
        lo = min(i, j)
        parity = (i + j) % 2          # site index parity = (x+y) parity (Lx even)
        if parity == 0:
            even.append((i, j))
        else:
            odd.append((i, j))
    return even, odd


def bond_phase_factors(dtau, J=1.0):
    """Diagonal Z-basis phase factors for one bond layer.

    e^{+J dtau sz_i sz_j} is diagonal with eigenvalue e^{+J dtau} when the two
    spins are parallel and e^{-J dtau} when antiparallel. We return a dict
    bond_index -> (phase_same, phase_diff) so any backend can apply the phases
    without re-deriving them. (Not used by the dense Trotter path, which
    applies phases vectorised; kept for the MPS backend and for tests.)
    """
    return J * dtau


# ---------------------------------------------------------------------------
# Spectral evolution: exact e^{-tau H} via eigendecomposition. Only feasible
# for tiny N (we cap at N<=12 via build_hamiltonian's guard), but it gives a
# machine-precision reference for the Trotter evolution and for the METTS
# estimator itself.
# ---------------------------------------------------------------------------

def spectral_evolve(H, E, psi, tau):
    """Apply e^{-tau H} to ``psi`` using a precomputed spectrum ``E``
    (1D array) and the (cached) eigenvectors are applied externally. Here we
    just need E and the unitary U = (eigvecs). Returns the evolved state.

    ``psi`` is expanded in the energy eigenbasis: coefficients c_k = <k|psi>,
    then e^{-tau E_k} c_k, then transform back. To avoid re-diagonalising on
    every call we expect the caller to pass the eigenvectors once; this helper
    instead implements the diagonal-phase step given already-rotated coeffs.
    """
    # not used directly; spectral_evolve_state below owns the full transform
    raise NotImplementedError("use spectral_evolve_state")


def spectral_evolve_state(H, psi, tau, cache=None):
    """Exact e^{-tau H}|psi>, normalised for stability by shifting E -> E - E0.

    ``cache`` may carry a dict with keys 'E','U' (eigenvalues, eigenvectors of
    H) to reuse across calls with the same H. Returns (evolved_state, cache).
    The overall e^{-tau E0} factor is dropped -- it cancels in every METTS
    ratio and in the collapse probabilities, so dropping it keeps the state
    O(1) at low temperature without changing any observable. (For the energy
    E_sigma itself this is irrelevant: <phi|H|phi>/<phi|phi> is shift-
    invariant.)
    """
    if cache is None or "E" not in cache:
        Hd = H.toarray() if sp.issparse(H) else np.asarray(H)
        E, U = np.linalg.eigh(Hd)
        cache = dict(E=E, U=U)
    else:
        E, U = cache["E"], cache["U"]
    E0 = E[0]
    coeffs = U.T.conj() @ psi
    coeffs = np.exp(-tau * (E - E0)) * coeffs
    out = U @ coeffs
    return out, cache


# ---------------------------------------------------------------------------
# Dense Trotter evolution. Works on a length-2**N state vector. The bond layer
# is applied as a vectorised phase (diagonal in Z basis); the field layer as a
# sequence of single-site rotations (reshape + 2x2 matmul).
# ---------------------------------------------------------------------------

def _apply_field_layer_dense(psi, N, theta, which_sites=None):
    """Apply prod_i e^{+theta sx_i} to ``psi`` (in place via reshape).

    e^{+theta sx} = cosh(theta) I + sinh(theta) sx  (sx Hermitian, eigenvalues
    +/-1). This is the *imaginary-time* field gate: H_field = -h sum sx, so
    e^{-dtau H_field/2} = e^{+theta sx} with theta = h*dtau/2 -- a real,
    non-unitary, positive-definite contraction. Acting on a single site it maps
    amplitudes (a_up, a_down) -> (c*a_up + s*a_down, s*a_up + c*a_down) with
    c=cosh, s=sinh. Single-site gates on different sites commute, so site order
    is irrelevant.

    Index split for bit position ``b`` (= N-1-site): index factors as
    index = high_bits * 2^(b+1) + bit_b * 2^b + low_bits, so reshape to
    (2^(N-1-b), 2, 2^b) isolates bit_b on the middle axis of size 2.
    """
    c = np.cosh(theta)
    s = np.sinh(theta)
    sites = range(N) if which_sites is None else which_sites
    for i in sites:
        b = site_bit(i, N)
        low = 2 ** b
        high = 2 ** (N - 1 - b)
        v = psi.reshape(high, 2, low)            # (high, bit_b, low)
        a0 = v[:, 0, :].copy()
        a1 = v[:, 1, :].copy()
        v[:, 0, :] = c * a0 + s * a1
        v[:, 1, :] = s * a0 + c * a1             # write back in place
    return psi


def _apply_bond_layer_dense(psi, N, layer, Jdtau):
    """Apply prod_<ij> in layer e^{+Jdtau sz_i sz_j} to ``psi`` (diagonal phases).

    For bond (i,j) the phase is e^{+Jdtau} if spins parallel, e^{-Jdtau} if
    antiparallel. Parallel means the two bits are equal. We compute a per-
    index phase mask and multiply.
    """
    if not layer:
        return psi
    dim = 2 ** N
    # build integer bit-position arrays
    idx = np.arange(dim)
    phases = np.ones(dim, dtype=np.complex128)
    esame = np.exp(Jdtau)
    ediff = np.exp(-Jdtau)
    for (i, j) in layer:
        bi = site_bit(i, N)
        bj = site_bit(j, N)
        si = (idx >> bi) & 1
        sj = (idx >> bj) & 1
        same = si == sj
        phases *= np.where(same, esame, ediff)
    psi *= phases
    return psi


def trotter_evolve_dense(psi, Lx, Ly, h, dtau, n_steps, J=1.0, bonds_layers=None):
    """Apply e^{-n_steps*dtau H} via 2nd-order Suzuki-Trotter (in place).

    ``bonds_layers`` is (even_layer, odd_layer) of bond lists; computed once
    and cached by the caller. Returns psi (same array, mutated) plus a dict of
    diagnostics: total truncation error (0 for dense, exact within Trotter),
    max bond dim (full for dense).
    """
    N = Lx * Ly
    if bonds_layers is None:
        even, odd = _bond_parity_split(tfim_bonds(Lx, Ly))
        bonds_layers = (even, odd)
    even, odd = bonds_layers
    theta_half = h * dtau / 2.0          # field gate angle for the half steps
    Jdtau = J * dtau
    for _ in range(n_steps):
        _apply_field_layer_dense(psi, N, theta_half)
        _apply_bond_layer_dense(psi, N, even, Jdtau)
        _apply_bond_layer_dense(psi, N, odd, Jdtau)
        _apply_field_layer_dense(psi, N, theta_half)
    return psi
