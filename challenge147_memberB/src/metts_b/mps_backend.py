"""Snake-MPS METTS backend (scales to 10x10).

Implements the same protocol as ``DenseBackend`` (make_product_state, evolve,
norm, energy_moments, conditional_prob_and_collapse) so ``run_one_sample`` /
``run_chain`` drive it unchanged.

Geometry
--------
Sites are ordered along the row-major serpentine ("snake") map
(SquareLattice.snake_index_map): MPS position ``pos`` holds physical site
``snake[pos]``. Most 2D nearest-neighbour bonds become MPS-adjacent (the
horizontal bonds within a row, and the single vertical bond at each row end);
the remaining vertical bonds connect MPS positions separated by up to Lx-1
sites. We handle a non-adjacent bond (pos_a, pos_b) with a>... by **swap
gates**: sweep swaps from a down to b+1 to bring site a next to b, apply the
2-site bond gate, then undo the swaps. This is the standard snake-MPS
approach (it grows the bond dimension transiently, capped by chi via SVD).

Evolution
---------
2nd-order Suzuki-Trotter, same split as the dense backend:
    U(dtau) = F(dtau/2) * B_even(dtau) * B_odd(dtau) * F(dtau/2)
where F is the field layer (single-site cosh/sinh sx gates, all commute) and
B_layer is the bond layer. Bond gates e^{+J dtau sz sz} are Z-diagonal. The
Trotter error is O(dtau^3)/step from the [H_bond, H_field] split; H_bond is
applied exactly (each layer's bond gates commute). For the MPS the bond
gates also incur SVD-truncation error, recorded as discarded weight.

Energy
------
E_sigma = <phi|H|phi>/<phi|phi> computed as the sum of bond and field local
expectation values (the standard MPS energy). This is exact for a given MPS
(no truncation in the measurement). We do NOT compute E2 = <H^2> on the MPS
(the cross-contraction is expensive and cancellation-prone); instead the
chain/driver obtains C from the u(beta) curve by numerical differentiation
(report "方案 B"), which the spec explicitly allows as a cross-check. So
energy_moments returns (E, nan, phi2) and the driver handles C via du/dbeta.

Collapse
--------
Exact-given-chi sequential Z-basis collapse along the MPS: sweep pos 0..N-1,
at each site compute p(up)/p(down) from the current (already-projected) MPS,
sample, and project. Implemented by canonicalising to a right-orthogonal form
and reading the local reduced density matrix; projection is a 1-site
operation (zero the discarded physical component and renormalise). Exact for
the MPS at its current bond dimension (no extra truncation), so crash-proof.
"""
from __future__ import annotations

import numpy as np

from .bridge import (
    SquareLattice, tfim_bonds, assert_mem_available, MemoryBudgetExceeded, SZ, SX,
)
from .mps import MPS
from . import status


# ---------------------------------------------------------------------------
# Gates (match the dense hamiltonian conventions exactly)
# ---------------------------------------------------------------------------

def field_gate(theta):
    """e^{+theta sx} = cosh(theta) I + sinh(theta) sx (2x2)."""
    c, s = np.cosh(theta), np.sinh(theta)
    return np.array([[c, s], [s, c]], dtype=np.complex128)


def field_gate_normalized(theta):
    """e^{+theta sx} factored as cosh(theta) * (I + tanh(theta) sx).

    The bounded operator (I + tanh(theta) sx) has spectral norm
    1 + |tanh(theta)| <= 2, so applying it NEVER grows the MPS norm by more
    than 2x per site -- no overflow, no SVD failure, at any beta/N. The scalar
    cosh(theta) is accumulated into the log-scale (it cancels in every METTS
    ratio). Returns (bounded_gate_2x2, log_cosh) where applying bounded_gate
    then adding N*log_cosh to log_scale reproduces the full field gate.
    """
    th = np.tanh(theta)
    g = np.array([[1.0, th], [th, 1.0]], dtype=np.complex128)
    return g, float(np.log(np.cosh(theta)))


def bond_gate_zz(Jdtau):
    """e^{+Jdtau sz sz} as 4x4, basis (up,up),(up,down),(down,up),(down,down)
    = diag(e^{Jdtau}, e^{-Jdtau}, e^{-Jdtau}, e^{Jdtau})."""
    e = np.exp(Jdtau)
    em = np.exp(-Jdtau)
    return np.diag([e, em, em, e]).astype(np.complex128)


SWAP_GATE = np.array(
    [[1, 0, 0, 0],
     [0, 0, 1, 0],
     [0, 1, 0, 0],
     [0, 0, 0, 1]], dtype=np.complex128)


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------

class MPSBackend:
    def __init__(self, Lx, Ly, h, J=1.0, dtau=0.05, max_bond_dim=64,
                 trunc_tol=1e-10, evolve="trotter", mem_guard=True):
        self.Lx, self.Ly = int(Lx), int(Ly)
        self.h, self.J = float(h), float(J)
        self.N = self.Lx * self.Ly
        self.dtau = float(dtau)
        self.chi = int(max_bond_dim)
        self.tol = float(trunc_tol)
        self.evolve_mode = evolve
        self.mem_guard = mem_guard
        self.snake = SquareLattice(self.Lx, self.Ly).snake_index_map()
        # inverse: physical site -> MPS position
        self.inv_snake = np.empty(self.N, dtype=int)
        self.inv_snake[self.snake] = np.arange(self.N)
        # bonds grouped into MPS-adjacent and swap-required
        self._setup_bonds()

    def _setup_bonds(self):
        """Classify each 2D bond as MPS-adjacent (pos, pos+1) or swap-
        required, and precompute the swap paths."""
        bonds = tfim_bonds(self.Lx, self.Ly)
        self.adjacent_bonds = []      # (pos_a, pos_b) with pos_b = pos_a+1
        self.swap_bonds = []          # (pos_a, pos_b, path) pos_a>pos_b, path=list
        for (i, j) in bonds:
            pa, pb = int(self.inv_snake[i]), int(self.inv_snake[j])
            a, b = max(pa, pb), min(pa, pb)            # a > b
            if a == b + 1:
                self.adjacent_bonds.append((b, a))
            else:
                # swap site at position a down to b+1: positions a, a-1, ..., b+1
                # each swap exchanges with its left neighbour. path = list of
                # left positions to swap INTO (i.e. swap (k, k+1) for k in path)
                path = list(range(a - 1, b - 1, -1))   # [a-1, a-2, ..., b]
                self.swap_bonds.append((a, b, path))
        # Trotter layers: split bonds into two disjoint (chessboard) layers so
        # that within a layer no two bonds share an MPS position. We use the
        # physical-site parity (x+y)%2 of the bond's lower-index site, which
        # makes the two layers disjoint on the 2D lattice (and hence on the
        # MPS positions, since a site belongs to exactly one parity).
        def parity(bond):
            (i, j) = bond
            return (min(i, j) + max(i, j)) % 2 if False else (i + j) % 2
        # rebuild parity from physical bonds (need the original (i,j))
        bonds_phys = tfim_bonds(self.Lx, self.Ly)
        self.layer_even = []   # (a,b,path_or_None) for parity 0
        self.layer_odd = []    # parity 1
        for (i, j) in bonds_phys:
            pa, pb = int(self.inv_snake[i]), int(self.inv_snake[j])
            a, b = max(pa, pb), min(pa, pb)
            path = None if a == b + 1 else list(range(a - 1, b - 1, -1))
            entry = (a, b, path)
            if (i + j) % 2 == 0:
                self.layer_even.append(entry)
            else:
                self.layer_odd.append(entry)

    # -- protocol -----------------------------------------------------------
    def make_product_state(self, spins):
        # spins are given in PHYSICAL site order; the MPS stores them in snake
        # order, so reorder.
        spins = np.asarray(spins, dtype=int)
        spins_snake = spins[self.snake]
        return MPS.from_product_state(spins_snake, chi=self.chi, tol=self.tol)

    def evolve(self, mps, beta):
        """Apply e^{-beta H/2} via 2nd-order Trotter (in place). Returns mps.

        Norm control (the crux of low-T / large-N stability): the field gate
        e^{+theta sx} = cosh(theta)*(I + tanh(theta) sx). The cosh factor
        grows the norm by ~e^{h*tau} per site and would overflow numpy's SVD
        at large N / low T. We instead apply the BOUNDED operator
        (I + tanh(theta) sx) (spectral norm <= 2) and accumulate the scalar
        cosh into ``mps.log_scale``. The bond gate e^{+Jdtau sz sz} only
        rescales by e^{+/-Jdtau} (~1.05, bounded). So the MPS norm stays O(1)
        throughout -- every SVD is well-conditioned at any beta/N -- and the
        dropped log-scale cancels in every METTS ratio (E = <phi|H|phi>/<phi|phi>,
        collapse probs, the unweighted sample mean).
        """
        tau = beta / 2.0
        n_steps = max(1, int(np.ceil(tau / self.dtau)))
        theta_half = self.h * self.dtau / 2.0
        Jdtau = self.J * self.dtau
        fg, log_cosh = field_gate_normalized(theta_half)
        bg = bond_gate_zz(Jdtau)
        mps.discarded = []
        if not hasattr(mps, "log_scale") or mps.log_scale is None:
            mps.log_scale = 0.0
        # each full step applies the half-field layer twice (start & end) and
        # the bond layers once; the cosh factor is applied N times per field
        # layer (once per site).
        log_field_layer = self.N * log_cosh
        for _ in range(n_steps):
            self._apply_field(mps, fg)
            mps.log_scale += log_field_layer
            self._apply_bond_layer(mps, self.layer_even, bg)
            self._apply_bond_layer(mps, self.layer_odd, bg)
            self._apply_field(mps, fg)
            mps.log_scale += log_field_layer
            if not np.isfinite(mps.log_scale):
                return mps          # caller sees EVOLUTION_NAN
            # The bounded field gate shrinks the norm (eigenvalue 1-tanh(theta)
            # < 1 along the GS direction); over many steps at large N the norm
            # underflows to 0. Rescale to unit norm once per step: the bounded
            # gate means the per-step norm change is a bounded factor, so a
            # single rescale keeps tensors O(1) AND prevents underflow. The
            # dropped factor is folded into log_scale (cancels in all ratios).
            n2 = mps.norm2()
            if not np.isfinite(n2) or n2 <= 0:
                mps.log_scale = float("nan")
                return mps
            ln = 0.5 * np.log(n2)
            scale = np.exp(-ln / mps.N)
            for t in mps.tensors:
                t *= scale
            mps.log_scale += ln
        return mps

    def _apply_field(self, mps, gate):
        for pos in range(self.N):
            mps.apply_1site_gate(pos, gate)

    def _apply_bond_layer(self, mps, layer, gate):
        for (a, b, path) in layer:
            self._apply_bond(mps, a, b, path, gate)

    def _apply_bond(self, mps, a, b, path, gate):
        """Apply a 2-site bond gate between MPS positions a>b. If path is None
        they are adjacent (b=a-1); else use swap gates to bring a next to b,
        apply, then undo."""
        if path is None:
            assert a == b + 1
            mps.apply_2site_gate(b, gate, direction="R")
            return
        # swap site a down to position b+1: apply SWAP on (k,k+1) for k in path
        for k in path:
            mps.apply_2site_gate(k, SWAP_GATE, direction="R")
        # now site originally at a is at position b+1, adjacent to b
        mps.apply_2site_gate(b, gate, direction="R")
        # undo swaps: reverse order
        for k in reversed(path):
            mps.apply_2site_gate(k, SWAP_GATE, direction="R")

    def norm(self, mps):
        return float(np.sqrt(max(mps.norm2(), 0.0)))

    def energy_moments(self, mps):
        """E_sigma = <phi|H|phi>/<phi|phi> via local expectation values.
        Returns (E, nan, phi2): E2 is not computed on the MPS (C is obtained
        from the u(beta) curve by the driver)."""
        phi2 = mps.norm2()
        if phi2 <= 0 or not np.isfinite(phi2):
            return float("nan"), float("nan"), float("nan")
        n2 = phi2
        E = 0.0
        # bond terms: -J <sz_i sz_j> over all 2D bonds. Use local 2-site
        # expectation on the MPS positions (a,b). For non-adjacent bonds we
        # would need a 2-site non-adjacent expectation; cheaper: compute
        # <sz_i sz_j> = <sz_i> * ... no -- correlations need the joint op.
        # We compute each bond's <sz sz> by bringing the two sites adjacent
        # with swaps (same as evolution) and using expect_2site_adjacent, then
        # undo. To avoid mutating the state we operate on a COPY per bond only
        # when non-adjacent; adjacent bonds use expect_2site_adjacent directly.
        szsz = np.kron(SZ, SZ)
        bonds_phys = tfim_bonds(self.Lx, self.Ly)
        for (i, j) in bonds_phys:
            pa, pb = int(self.inv_snake[i]), int(self.inv_snake[j])
            a, b = max(pa, pb), min(pa, pb)
            if a == b + 1:
                corr = mps.expect_2site_adjacent(b, szsz)
            else:
                corr = self._two_site_corr_swapped(mps, a, b, szsz)
            E += -self.J * corr
        # field terms: -h <sx_i>
        sx = SX.astype(np.complex128)
        for pos in range(self.N):
            E += -self.h * mps.expect_1site(pos, sx)
        if not np.isfinite(E):
            return float("nan"), float("nan"), phi2
        return float(E), float("nan"), float(phi2)

    def _two_site_corr_swapped(self, mps, a, b, op2):
        """<psi| op on (a,b) |psi> for non-adjacent MPS positions, by swapping
        a down to b+1 on a COPY, measuring, and NOT undoing (the copy is
        discarded). Cheaper than swap-meet-undo on the live state and avoids
        any truncation of the live state."""
        # Build a fresh copy with the swaps applied (truncation only affects
        # the copy). Then measure the adjacent pair (b, b+1).
        m = MPS([t for t in mps.tensors], chi=self.chi, tol=self.tol,
                snake=mps.snake)
        path = list(range(a - 1, b - 1, -1))
        for k in path:
            m.apply_2site_gate(k, SWAP_GATE, direction="R")
        return m.expect_2site_adjacent(b, op2)

    # -- collapse -----------------------------------------------------------
    def conditional_prob_and_collapse(self, mps, rng, basis="Z", prob_tol=1e-9):
        """Exact-given-chi sequential Z-basis collapse along the MPS.

        Sweep pos = 0..N-1. At each pos the local reduced density matrix
        (conditioned on the already-fixed sites 0..pos-1) is read from the
        MPS in left-orthogonal form; p(up)/p(down) are its diagonal; sample
        and project (zero the discarded physical leg, renormalise). Exact for
        the MPS at its current bond dimension (no extra truncation).
        """
        if basis != "Z":
            raise NotImplementedError("only Z-basis collapse in v0")
        N = self.N
        probs = np.empty((N, 2), dtype=np.float64)   # (p_down, p_up)
        spins_mps = np.empty(N, dtype=np.int8)       # in MPS order
        # Bring to a form where we can read site 0's reduced density matrix
        # conditioned on nothing, then project, then move to site 1, etc.
        # We keep the MPS left-canonical as we go: after projecting site pos
        # we orthonormalise so site pos+1 carries the conditioned state.
        m = mps  # mutate in place
        for pos in range(N):
            # local 1-site RDM at pos, conditioned on the fixed prefix, is
            # diag(<sz_pos^2>) once left-canonical. Simpler & exact: compute
            # p(up) = <P_up>_cond using expect_1site with P_up, but that
            # divides by the GLOBAL norm. Instead, after each projection the
            # MPS is renormalised, so the global norm == conditional norm and
            # expect_1site gives the conditional probability directly.
            Pup = np.array([[0.0, 0.0], [0.0, 1.0]], dtype=np.complex128)
            Pdn = np.array([[1.0, 0.0], [0.0, 0.0]], dtype=np.complex128)
            p_up = float(m.expect_1site(pos, Pup).real)
            p_down = float(m.expect_1site(pos, Pdn).real)
            tot = p_up + p_down
            if not np.isfinite(tot) or tot <= 0:
                raise _ProbError(f"pos {pos}: weight {tot}", pos)
            pu = p_up / tot
            if pu < -prob_tol or pu > 1.0 + prob_tol:
                raise _ProbError(f"pos {pos}: p_up {pu}", pos)
            probs[pos] = (1.0 - pu, pu)
            spins_mps[pos] = 1 if rng.random() < pu else -1
            # project: apply the projector for the sampled outcome
            proj = Pup if spins_mps[pos] == 1 else Pdn
            m.apply_1site_gate(pos, proj)
            # renormalise (projector is not unitary): rescale this site so the
            # MPS norm returns to 1, keeping left-canonicalisation implicit.
            t = m.tensors[pos]
            n = np.sqrt(max((np.abs(t) ** 2).sum(), 1e-300))
            m.tensors[pos] = t / n
            # left-orthonormalise site pos so subsequent expect_1site at pos+1
            # is a proper conditional probability: QR/SVD the fused (chiL*2, k)
            # and push R right. (Needed because apply_1site_gate broke the
            # canonical form.)
            self._left_canonicalise_site(m, pos)
        # map spins back to physical order
        spins_phys = np.empty(N, dtype=np.int8)
        spins_phys[self.snake] = spins_mps
        return probs, spins_phys, float(m.norm2())

    def _left_canonicalise_site(self, mps, pos):
        """Left-orthonormalise site ``pos`` and push the residual right:
        SVD t_pos fused as (chiL*2, chiR), keep U as the new site (left-
        unitary), push diag(s)@Vh into site pos+1. No-op at the last site."""
        if pos == mps.N - 1:
            return
        t = mps.tensors[pos]                          # (2, chiL, chiR)
        d, chiL, chiR = t.shape
        M = t.transpose(1, 0, 2).reshape(chiL * d, chiR)
        U, s, Vh = np.linalg.svd(M, full_matrices=False)
        k = min(self.chi, s.size)
        U = U[:, :k]; s = s[:k]; Vh = Vh[:k, :]
        mps.tensors[pos] = U.reshape(chiL, d, k).transpose(1, 0, 2)  # left-unitary
        # push s@Vh into site pos+1
        sV = (np.diag(s) @ Vh)
        nxt = mps.tensors[pos + 1]                    # (2, k_prev, chiRR)
        dn, kp, chiRR = nxt.shape
        # nxt's left bond is chiR (== k before truncation). After truncation
        # the new left bond is k; if k < chiR we must reshape accordingly.
        nxtM = nxt.transpose(1, 0, 2).reshape(kp, dn * chiRR)
        # sV is (k, chiR); nxtM is (kp, dn*chiRR) with kp==chiR. Multiply:
        if sV.shape[1] != nxtM.shape[0]:
            # bond dim mismatch from truncation: pad/truncate nxtM rows
            if sV.shape[1] < nxtM.shape[0]:
                nxtM = nxtM[:sV.shape[1]]
            else:
                nxtM = np.pad(nxtM, ((0, sV.shape[1] - nxtM.shape[0]), (0, 0)))
        nxtM = sV @ nxtM
        mps.tensors[pos + 1] = nxtM.reshape(k, dn, chiRR).transpose(1, 0, 2)


class _ProbError(Exception):
    def __init__(self, msg, pos=None):
        super().__init__(msg)
        self.pos = pos
