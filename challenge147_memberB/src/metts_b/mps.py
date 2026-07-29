"""Right-canonical MPS along the snake ordering, with the local operations the
METTS MPS backend needs.

Conventions
-----------
* ``tensors[i]`` has shape ``(2, chiL, chiR)`` (physical, left-bond, right-
  bond), complex128. OBC: ``chiL=1`` at i=0, ``chiR=1`` at i=N-1.
* Physical index: 0 = spin down (sz=-1), 1 = spin up (sz=+1). This matches
  ``product_state_vector``'s bit convention so the MPS and dense backends
  describe the *same* product state.
* Right-canonical: after ``right_canonical()``, every tensor A_i satisfies
  sum_s conj(A_i[s]) A_i[s] = I on the right bond, and <psi|psi> = prod of
  the carried singular values' squares (we store the state as Gamma-Lambda
  free, i.e. singular values absorbed; ``norm2`` recomputes explicitly).

The MPS backend is the **snake-MPS** METTS engine (design spec Stage 3 / v0),
the backend that scales to 10x10 (the dense backend caps at N~12). It
implements the same protocol as ``DenseBackend`` so ``run_one_sample`` /
``run_chain`` drive it unchanged.

Crash-safety (challenge hard constraint "prefer lost efficiency over a
crash"):
  * Bond dimension capped at ``chi``; every 2-site gate is SVD-truncated to
    chi with a discarded-weight record. The bond never grows unbounded.
  * Memory guarded before heavy allocs (assert_mem_available); on
    MemoryBudgetExceeded the caller degrades chi.
  * NaN/Inf from any contraction marks the sample EVOLUTION_NAN.
  * Specific heat is computed from the u(beta) CURVE (numerical derivative,
    report "方案 B"), so the MPS backend never needs <H^2> and avoids the
    large-cancellation failure mode of the fluctuation formula.
"""
from __future__ import annotations

import numpy as np

from .bridge import SquareLattice, assert_mem_available, MemoryBudgetExceeded


# ---------------------------------------------------------------------------
# Singular-value truncation of a fused 2-site tensor.
# ---------------------------------------------------------------------------

def svd_truncate(theta, chi, tol=0.0):
    """SVD ``theta`` (shape (rows, cols)) and truncate to rank chi (also by
    cumulative discarded weight tol). Returns (U, s, Vh, discarded_weight, k).

    ``discarded_weight`` = sqrt(sum s_tail^2) / sqrt(sum s_kept^2) (relative
    Schmidt tail), 0 if nothing discarded. k is the kept rank.
    """
    U, s, Vh = np.linalg.svd(theta, full_matrices=False)
    k = min(chi, s.size)
    if tol > 0 and s.size > 1:
        s2 = s ** 2
        tot = s2.sum()
        if tot > 0:
            # shrink k while the discarded tail stays below tol*tot
            for kk in range(k, 0, -1):
                tail = s2[kk:].sum() if kk < s.size else 0.0
                if tail <= tol * tot or kk == 1:
                    k = kk
                    break
    k = max(1, k)
    kept_w = float((s[:k] ** 2).sum()) if k > 0 else 0.0
    tail_w = float((s[k:] ** 2).sum()) if k < s.size else 0.0
    tot = kept_w + tail_w
    # discarded weight = fraction of the Schmidt probability mass dropped,
    # in [0, 1]. (The earlier tail/kept ratio was unbounded and meaningless
    # for a flat spectrum.) 0 = nothing dropped (exact at this chi).
    disc = float(tail_w / tot) if tot > 0 else 0.0
    return U[:, :k], s[:k], Vh[:k, :], disc, k


# ---------------------------------------------------------------------------
# MPS data structure
# ---------------------------------------------------------------------------

class MPS:
    def __init__(self, tensors, chi=None, tol=0.0, snake=None):
        self.tensors = [np.array(t, dtype=np.complex128, copy=True)
                        for t in tensors]
        self.N = len(self.tensors)
        self.chi = chi
        self.tol = tol
        self.discarded = []      # per-gate discarded weights during evolution
        # snake[pos] = physical site at MPS position pos. None = identity
        # (MPS site pos == physical site pos).
        self.snake = (None if snake is None else np.asarray(snake, dtype=int))

    @classmethod
    def from_product_state(cls, spins, chi=64, tol=0.0):
        """Z-basis product-state MPS (bond dim 1). ``spins`` in +/-1."""
        spins = np.asarray(spins, dtype=int)
        N = spins.size
        tensors = []
        for i in range(N):
            t = np.zeros((2, 1, 1), dtype=np.complex128)
            t[1 if spins[i] == 1 else 0, 0, 0] = 1.0   # 1=up, 0=down
            tensors.append(t)
        return cls(tensors, chi=chi, tol=tol)          # already canonical

    @classmethod
    def from_dense_vector(cls, vec, chi=64, tol=0.0, snake=None):
        """Decompose a dense state vector (length 2**N) into an MPS by
        sequential SVD (left-to-right), in **snake order**.

        The MPS site at position ``pos`` represents physical site
        ``snake[pos]`` (row-major serpentine). ``snake`` defaults to the
        identity map (physical order), which is what the dense cross-check
        tests use when they build the MPS directly from a dense vector in
        physical-site axis order.

        The physical leg convention matches product_state_vector: bit k =
        site (N-1-k), i.e. axis 0 of the reshaped vector is site 0. We first
        transpose the reshaped vector's axes into snake order, then sweep.
        Truncates to chi. Singular values are pushed right (left-canonical);
        the final residual is kept on the last site so the input norm is
        preserved exactly (to_vector reconstructs the input to machine
        precision).
        """
        vec = np.asarray(vec, dtype=np.complex128).ravel()
        N = int(round(np.log2(vec.size)))
        psi = vec.reshape([2] * N)                     # axis i = physical site i
        if snake is not None:
            snake = np.asarray(snake, dtype=int)
            psi = np.transpose(psi, snake)             # axis pos -> site snake[pos]
        tensors = []
        chiL = 1
        rest = psi
        for i in range(N):
            last = (i == N - 1)
            rest = rest.reshape(chiL * 2, -1)          # (chiL*2, 2^(N-i-1))
            if last:
                k = rest.shape[1]
                tensors.append(rest.reshape(chiL, 2, k).transpose(1, 0, 2))
                break
            U, s, Vh = np.linalg.svd(rest, full_matrices=False)
            k = min(chi, s.size)
            U = U[:, :k]; s = s[:k]; Vh = Vh[:k, :]
            tensors.append(U.reshape(chiL, 2, k).transpose(1, 0, 2))
            rest = (np.diag(s) @ Vh)
            chiL = k
        return cls(tensors, chi=chi, tol=tol, snake=snake)

    # -- canonicalisation (right-canonical, sweep R->L) --------------------
    def right_canonical(self):
        for i in range(self.N - 1, 0, -1):
            t = self.tensors[i]                         # (2, chiL, chiR)
            d, chiL, chiR = t.shape
            M = t.transpose(1, 0, 2).reshape(chiL, d * chiR)
            U, s, Vh = np.linalg.svd(M, full_matrices=False)
            # site i becomes right-canonical: Vh -> (d, k, chiR)
            self.tensors[i] = Vh.reshape(Vh.shape[0], d, chiR).transpose(1, 0, 2)
            # push U*diag(s) left into site i-1
            Us = (U * s)
            prev = self.tensors[i - 1]                  # (2, chiLp, chiL)
            dp, chiLp, _ = prev.shape
            prevM = prev.transpose(1, 0, 2).reshape(chiLp, 2 * chiL)
            prevM = prevM @ Us
            k = Us.shape[1]
            self.tensors[i - 1] = prevM.reshape(chiLp, dp, k).transpose(1, 0, 2)
        return self

    # -- norm: explicit transfer-matrix contraction ------------------------
    def norm2(self):
        """<psi|psi> via a left-to-right transfer-matrix sweep.

        E starts as the (1,1) identity on the left bond. At each site we fold
        in t and t.conj over the physical leg and the matching bond, producing
        the next E on the right bond. After the last site E is a 1x1 scalar.
        """
        E = np.ones((1, 1), dtype=np.complex128)        # (left_bond, left_bond*)
        for t in self.tensors:                          # (2, chiL, chiR)
            # E_{a,a'} t_{s,a,b} -> M_{a',s,b}; then * conj(t)_{s,a',b'} -> E_{b,b'}
            M = np.tensordot(E, t, axes=([1], [1]))     # (a, s, b)  [a=left residual]
            # we need to also keep the conjugate left index; do it in two clean
            # contractions against t.conj over (physical, left-conj):
            E = np.tensordot(M, t.conj(), axes=([0, 1], [1, 0]))  # (b, b')
        return float(E.real.item())

    def to_vector(self):
        """Dense state vector (length 2**N) by contracting all tensors, in
        **physical site** axis order (inverse snake if set). Only for small N
        (tests / dense cross-check)."""
        full = self.tensors[0]
        for t in self.tensors[1:]:
            full = np.tensordot(full, t, axes=([-1], [1]))
        full = full.reshape([2] * self.N)              # axis pos = MPS pos
        if self.snake is not None:
            inv = np.empty_like(self.snake)
            inv[self.snake] = np.arange(self.N)        # inverse permutation
            full = np.transpose(full, inv)             # axis -> physical site
        return full.reshape(-1)

    # -- environments ------------------------------------------------------
    def left_envs(self, upto):
        """L[k] for k=0..upto: contraction of sites 0..k-1, shape
        (chiR_{k-1}, chiR_{k-1}). L[0] = [[1]]."""
        L = [np.ones((1, 1), dtype=np.complex128)]
        for k in range(upto):
            t = self.tensors[k]
            E = np.tensordot(L[-1], t, axes=([1], [1]))     # (a, s, c)
            L.append(np.tensordot(E, t.conj(), axes=([0, 1], [1, 0])))  # (c, c')
        return L

    def right_envs(self, from_):
        """R[k] for k=from_..N: contraction of sites k..N-1, shape
        (chiL_k, chiL_k) (the LEFT bond of site k). R[N] = [[1]].

        Built right-to-left: starting from the (1,1) right boundary, fold in
        site k by contracting t_k and t_k.conj over the physical leg and the
        RIGHT bond, leaving the LEFT bond as the new env index.
        """
        R = [np.ones((1, 1), dtype=np.complex128)]          # R[N] (right of last)
        for k in range(self.N - 1, from_ - 1, -1):
            t = self.tensors[k]                             # (2, chiL, chiR)
            # E = t_{s,a,b} R_{b,b'} -> (s, a, b'); then * conj(t)_{s,a',b'} over
            # (physical s, right b') -> (a, a') = left bond env
            E = np.tensordot(t, R[-1], axes=([2], [0]))     # (s, a, b')
            R.append(np.tensordot(E, t.conj(), axes=([0, 2], [0, 2])))  # (a, a')
        R.reverse()                                         # index by site k
        return R

    # -- 1-site and 2-site local expectation values ------------------------
    def expect_1site(self, i, op):
        """<psi| op_i |psi> / <psi|psi>, op is 2x2."""
        L = self.left_envs(i)[-1]                           # (chiL, chiL)
        R = self.right_envs(i + 1)[0]                       # (chiR, chiR)
        t = self.tensors[i]                                 # (2, chiL, chiR)
        top = np.tensordot(op, t, axes=([1], [0]))         # (2, chiL, chiR)
        # contract L_{a,a'} t*_{s,a,b} top_{s,a',b'} R_{b,b'}
        E = np.tensordot(L, t.conj(), axes=([1], [1]))      # (a', s, b)
        E = np.tensordot(E, top, axes=([0, 1], [1, 0]))     # (b, b')
        E = np.tensordot(E, R, axes=([0, 1], [0, 1]))
        return float((E / self.norm2()).real)

    def expect_2site_adjacent(self, i, op2):
        """<psi| op_{i,i+1} |psi> / <psi|psi>, op2 is 4x4 in basis
        (s_i, s_{i+1}) = (down,down),(down,up),(up,down),(up,up)."""
        j = i + 1
        L = self.left_envs(i)[-1]                           # (chiL, chiL)
        R = self.right_envs(j + 1)[0]                       # (chiR, chiR)
        ti = self.tensors[i]
        tj = self.tensors[j]
        theta = np.tensordot(ti, tj, axes=([2], [1]))       # (si, chiL, sj, chiR)
        si, chiL, sj, chiR = theta.shape
        op = op2.reshape(si, sj, si, sj)
        top = np.tensordot(op, theta, axes=([2, 3], [0, 2]))  # (si, sj, chiL, chiR)
        # contract L_{a,a'} theta*_{si,a,sj,b} top_{si,a',sj,b'} R_{b,b'}
        # thc: (si, chiL=a, sj, chiR=b); top: (si, sj, chiL=a', chiR=b')
        thc = theta.conj()                                  # (si, chiL, sj, chiR)
        E = np.tensordot(L, thc, axes=([1], [1]))           # (a', si, sj, b)
        # pair E's (a', si, sj) = axes [0,1,2] with top's (chiL, si, sj) = axes [2,0,1]
        E = np.tensordot(E, top, axes=([0, 1, 2], [2, 0, 1]))  # (b, b')
        E = np.tensordot(E, R, axes=([0, 1], [0, 1]))
        return float((E / self.norm2()).real)

    # -- 2-site gate application (Trotter bond gate) -----------------------
    def apply_2site_gate(self, i, gate, direction="R"):
        """Apply a 4x4 gate to adjacent sites (i, i+1), SVD-truncate to chi.

        Fuses theta as (chiL*si, sj*chiR), applies the gate on the physical
        (si,sj) legs, SVDs, truncates, and splits. ``direction`` 'R' absorbs
        the singular values into site i+1 (right-canonical centre at i+1);
        'L' absorbs them into site i. Mutates tensors in place, appends the
        discarded weight to self.discarded, and returns it.
        """
        return self._apply_2site_gate_fused(i, gate, direction)

    def _apply_2site_gate_fused(self, i, gate, direction="R"):
        """Correct 2-site gate: fuse theta as (chiL*si, sj*chiR), apply gate
        on the physical (si,sj) legs by reshaping, SVD, truncate, split."""
        ti = self.tensors[i]                                # (2, chiL, chiR)
        tj = self.tensors[i + 1]                            # (2, chiR, chiRR)
        d = 2
        chiL = ti.shape[1]
        chiRR = tj.shape[2]
        # theta_{(chiL, si), (sj, chiRR)}
        theta = np.tensordot(ti, tj, axes=([2], [1]))       # (si, chiL, sj, chiRR)
        theta = theta.transpose(1, 0, 2, 3).reshape(chiL * d, d * chiRR)
        # apply gate on the physical legs: reshape to (chiL, si, sj, chiRR),
        # apply gate on (si,sj), reshape back.
        th4 = theta.reshape(chiL, d, d, chiRR)
        g = gate.reshape(d, d, d, d)
        th4 = np.tensordot(g, th4, axes=([2, 3], [1, 2]))   # (si, sj, chiL, chiRR)
        th4 = th4.transpose(2, 0, 1, 3).reshape(chiL * d, d * chiRR)
        U, s, Vh, disc, k = svd_truncate(th4, self.chi, self.tol)
        self.discarded.append(disc)
        # site i: U -> (chiL, d, k) -> (d, chiL, k)
        self.tensors[i] = U.reshape(chiL, d, k).transpose(1, 0, 2)
        # site i+1: diag(s) @ Vh -> (k, d, chiRR) -> (d, k, chiRR)
        sv = (np.diag(s) @ Vh).reshape(k, d, chiRR).transpose(1, 0, 2)
        self.tensors[i + 1] = sv
        return disc

    # -- 1-site gate application (field gate) ------------------------------
    def apply_1site_gate(self, i, gate):
        """Apply a 2x2 gate to site i. Preserves bond dim (no SVD needed)."""
        t = self.tensors[i]                                 # (2, chiL, chiR)
        self.tensors[i] = np.tensordot(gate, t, axes=([1], [0]))
        return 0.0
