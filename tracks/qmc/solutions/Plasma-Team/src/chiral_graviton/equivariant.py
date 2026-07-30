"""SO(3)-aware neural-network features from orbital occupation vectors.

Core idea
---------

The occupation vector :math:`n_m` (m = -Q, …, Q) is treated as a vector in the
spin-Q representation space.  The symmetric tensor square :math:`n \\otimes n`
is decomposed via Clebsch–Gordan (CG) coupling into irreducible spherical
tensor components :math:`T^{(K)}_q` for K = 0, 2, 4, …, 2Q (only even K
survive because the tensor square is symmetric).

The squared norms of each irrep component and their cross-channel inner
products form a rich, high-dimensional feature set that encodes the
**geometric** structure of each occupation configuration.  Unlike raw
occupation bits, these features capture multi-orbital correlations organised
by angular-momentum channels.

Architectural SO(3) alignment
-----------------------------

Feeding these CG-decomposed features into an MLP (rather than raw occupation
bits) produces raw network outputs that are **naturally closer** to the
correct symmetry sector.  This is quantified by the *projection alignment*:

.. math::

    \\alpha = \\frac{\\|P v_{\\rm raw}\\|}{\\|v_{\\rm raw}\\|}

where :math:`P` is the orthogonal projector onto ``ker(L_+)``.  Higher
:math:`\\alpha` means the architecture needs less correction from the
symmetry projection — the network "understands" the SO(3) structure.

The projection step is retained as a rigorous certification gate: it
guarantees the output state belongs to the correct irrep, regardless of
how well the architecture aligns.

Unlike the original ``SharedProjectedMLP``, which feeds raw occupation bits
into a vanilla MLP, this module makes the *architecture itself*
symmetry-aware, even though the final irrep guarantee still comes from
the projection.

Mathematical details
--------------------

For a vector v in the spin-Q representation, the CG tensor square is:

.. math::

    T^{(K)}_q = \\sum_{m_1,m_2} \\langle Q,m_1; Q,m_2 | K,q \\rangle
                \\, v_{m_1} v_{m_2}

where K = 0, 2, 4, …, 2Q (even only, due to Bose symmetry of the
symmetric tensor product).

Features (order 1 — per-channel norms):

.. math::

    I_K = \\sum_q \\bigl(T^{(K)}_q\\bigr)^2

Features (order 2 — cross-channel couplings):

.. math::

    I_{K_1,K_2} = \\sum_q T^{(K_1)}_q \\, T^{(K_2)}_q \\qquad (K_1 \\neq K_2)

Rotation utilities
------------------

The module includes Wigner D-matrix construction for spin-Q
(``build_spin_q_rotation``) and the physical occupation-vector rotation
via :math:`|D|^2` (``build_occupation_rotation``).  These are used by the
state-level rotation tests in ``rotation_equivariance.py``, not for
feature-level invariance checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np


# ===========================================================================
# Clebsch–Gordan coefficient cache
# ===========================================================================


@lru_cache(maxsize=256)
def _cg(j1: float, m1: float, j2: float, m2: float, j: float, m: float) -> float:
    """Clebsch–Gordan coefficient ⟨j₁,m₁; j₂,m₂ | j,m⟩ (real, float64).

    Uses sympy for exact rational arithmetic.  Accepts both integer and
    half-integer angular momenta (the Haldane sphere produces half-integer
    Q for even electron counts).  In the Condon–Shortley convention the CG
    coefficient is always real.
    """
    from sympy.physics.wigner import clebsch_gordan  # type: ignore[import-untyped]

    c = clebsch_gordan(
        j1, j2, j,
        m1,  # sympy accepts float for half-integer m
        m2,
        m,
    )
    return float(c.evalf()) if hasattr(c, "evalf") else float(c)


# ===========================================================================
# Pre-computed CG coupling tensor (full tensor square)
# ===========================================================================


@dataclass(frozen=True)
class _CGTensorSquare:
    """CG coupling coefficients for the tensor square Q ⊗ Q → K.

    For the **symmetric** tensor square v ⊗ v, the allowed K channels are
    determined by the Bose symmetry of the CG coefficients:

        ⟨Q,a; Q,b | K,q⟩ = (-1)^{2Q−K} ⟨Q,b; Q,a | K,q⟩

    For v_a v_b = v_b v_a (symmetric), we need (-1)^{2Q−K} = +1:
    • integer Q (2Q even) → K must be even: 0, 2, 4, …, 2Q
    • half-integer Q (2Q odd) → K must be odd: 1, 3, 5, …, 2Q

    For each allowed K, stores the matrix C^{(K)}_q of shape (2Q+1, 2Q+1)
    such that for input vector v:

        T^{(K)}_q = v^T @ C^{(K)}_q @ v

    where C^{(K)}_q[a,b] = ⟨Q,a; Q,b | K,q⟩.
    """

    two_q: int
    k_values: tuple[int, ...]
    # cg_mats[K] is a (2K+1, 2Q+1, 2Q+1) float64 array
    cg_mats: dict[int, np.ndarray]

    @classmethod
    def build(cls, two_q: int) -> _CGTensorSquare:
        Q = two_q / 2  # float — supports half-integer Q for even N
        n_orb = two_q + 1
        # Integer Q → even K; half-integer Q → odd K.
        k_start = 0 if two_q % 2 == 0 else 1
        k_values = tuple(range(k_start, two_q + 1, 2))

        cg_mats: dict[int, np.ndarray] = {}
        # np.arange handles half-integer step; range() does not.
        m_range = tuple(float(x) for x in np.arange(-Q, Q + 1.0, 1.0))

        for K in k_values:
            mat = np.zeros((2 * K + 1, n_orb, n_orb), dtype=np.float64)
            for q_idx, q in enumerate(range(-K, K + 1)):
                for a_idx, a in enumerate(m_range):
                    for b_idx, b in enumerate(m_range):
                        if abs((a + b) - q) > 1e-12:
                            continue
                        mat[q_idx, a_idx, b_idx] = _cg(Q, a, Q, b, K, q)
            cg_mats[K] = mat

        return cls(two_q, k_values, cg_mats)


# Global cache: one _CGTensorSquare per two_q value.
_cg_tensor_cache: dict[int, _CGTensorSquare] = {}


def _get_cg_tensor(two_q: int) -> _CGTensorSquare:
    if two_q not in _cg_tensor_cache:
        _cg_tensor_cache[two_q] = _CGTensorSquare.build(two_q)
    return _cg_tensor_cache[two_q]


# ===========================================================================
# Public data types
# ===========================================================================


@dataclass(frozen=True)
class IrrepDecomposition:
    """One configuration decomposed into SO(3) irreducible spherical tensors.

    Attributes
    ----------
    tensors : dict[int, np.ndarray]
        ``tensors[K]`` is a float64 array of length ``2*K+1`` containing
        :math:`T^{(K)}_q` for ``q = -K, ..., K``.  Only even K are present.
    invariants : np.ndarray
        Concatenated SO(3)-invariant features (1-D float64).
    feature_labels : tuple[str, ...]
        Human-readable label for each entry in *invariants*.
    """

    tensors: dict[int, np.ndarray]
    invariants: np.ndarray
    feature_labels: tuple[str, ...]

    @property
    def invariant_count(self) -> int:
        """Total number of SO(3)-invariant scalar features."""
        return len(self.invariants)


# ===========================================================================
# SO(3) feature extractor
# ===========================================================================


class SO3FeatureExtractor:
    """Extract SO(3)-invariant features from occupation-vector configurations.

    Uses the full CG tensor square (not just the diagonal) for expressive,
    symmetry-guaranteed features.

    Parameters
    ----------
    two_q : int
        Twice the monopole strength (2Q).  The orbital shell carries the
        spin-Q representation, dimension ``2Q+1``.
    max_correlation_order : int
        1 = per-channel norms only.
        2 = norms + cross-channel inner products (default).
    """

    def __init__(
        self,
        two_q: int,
        *,
        max_correlation_order: int = 2,
    ) -> None:
        if two_q < 0:
            raise ValueError("two_q must be non-negative")
        if max_correlation_order not in (1, 2):
            raise ValueError("max_correlation_order must be 1 or 2")

        self.two_q = int(two_q)
        self.q_value = two_q / 2  # float — half-integer Q for even N
        self.n_orbitals = two_q + 1
        self.max_correlation_order = max_correlation_order

        # Load pre-computed CG coupling tensors.
        self._cg = _get_cg_tensor(two_q)

        # Build feature layout.
        self.feature_labels: tuple[str, ...] = self._build_labels()

    # ------------------------------------------------------------------
    # Feature layout
    # ------------------------------------------------------------------

    def _build_labels(self) -> tuple[str, ...]:
        labels: list[str] = []
        K_list = self._cg.k_values

        # Norm invariants: I_K = ‖T^{(K)}‖²
        for K in K_list:
            labels.append(f"I_{K}")

        if self.max_correlation_order >= 2:
            # Cross-coupling: I_{K1,K2} = Σ_q T^{(K1)}_q T^{(K2)}_q
            for i, K1 in enumerate(K_list):
                for K2 in K_list[i + 1 :]:
                    labels.append(f"I_{{{K1},{K2}}}")

        return tuple(labels)

    @property
    def feature_count(self) -> int:
        """Total number of SO(3)-invariant features per configuration."""
        return len(self.feature_labels)

    @property
    def k_values(self) -> tuple[int, ...]:
        """Allowed K channels (even for integer Q, odd for half-integer Q)."""
        return self._cg.k_values

    # ------------------------------------------------------------------
    # Single-configuration decomposition
    # ------------------------------------------------------------------

    def decompose(self, occupation_vector: np.ndarray) -> IrrepDecomposition:
        """Decompose one occupation vector into irreps and extract invariants.

        Parameters
        ----------
        occupation_vector : np.ndarray
            Float64 vector of length ``2Q+1``.

        Returns
        -------
        IrrepDecomposition
        """
        vec = np.asarray(occupation_vector, dtype=np.float64)
        if vec.shape != (self.n_orbitals,):
            raise ValueError(
                f"occupation_vector must have length {self.n_orbitals}, "
                f"got {vec.shape[0]}"
            )

        outer = np.outer(vec, vec)  # (n_orb, n_orb)
        tensors: dict[int, np.ndarray] = {}

        for K in self._cg.k_values:
            cg = self._cg.cg_mats[K]  # (2K+1, n_orb, n_orb)
            # einsum: contract cg[q,a,b] * outer[a,b] → t[q]
            t = np.einsum("qab,ab->q", cg, outer)
            tensors[K] = np.asarray(t, dtype=np.float64)

        invariants = self._build_invariants(tensors)
        return IrrepDecomposition(
            tensors=tensors,
            invariants=invariants,
            feature_labels=self.feature_labels,
        )

    # ------------------------------------------------------------------
    # Batch decomposition (for precomputed basis features)
    # ------------------------------------------------------------------

    def decompose_batch(self, occupation_matrix: np.ndarray) -> np.ndarray:
        """Decompose many occupation vectors into invariant features.

        Uses the bilinear form T^{(K)}_q = v^T @ C^{(K)}_q @ v, vectorised
        across all configurations.

        Parameters
        ----------
        occupation_matrix : np.ndarray
            Shape ``(n_configs, 2Q+1)`` float64.

        Returns
        -------
        np.ndarray
            Shape ``(n_configs, feature_count)`` invariant features.
        """
        occ = np.asarray(occupation_matrix, dtype=np.float64)
        if occ.ndim != 2 or occ.shape[1] != self.n_orbitals:
            raise ValueError(
                f"occupation_matrix must be (n, {self.n_orbitals}), "
                f"got {occ.shape}"
            )

        n_configs = occ.shape[0]
        n_feat = self.feature_count
        features = np.zeros((n_configs, n_feat), dtype=np.float64)
        K_list = self._cg.k_values

        # ---- Step 1: compute all tensor components ----
        all_tensors: dict[int, np.ndarray] = {}  # K → (n_configs, 2K+1)

        for K in K_list:
            cg = self._cg.cg_mats[K]  # (2K+1, n_orb, n_orb)
            n_q = 2 * K + 1

            # For each q: T_q = Σ_{a,b} C_q[a,b] n_a n_b
            #            = n @ C_q @ n^T  (scalar per config)
            # Vectorised: T_q = sum((n @ C_q) * n, axis=1)
            t = np.zeros((n_configs, n_q), dtype=np.float64)
            for q_idx in range(n_q):
                c_q = cg[q_idx]  # (n_orb, n_orb)
                temp = occ @ c_q  # (n_configs, n_orb)
                t[:, q_idx] = np.sum(temp * occ, axis=1)
            all_tensors[K] = t

        # ---- Step 2: build invariants ----
        col = 0

        # Norm invariants: I_K = Σ_q (T^{(K)}_q)²
        for K in K_list:
            features[:, col] = np.sum(all_tensors[K] ** 2, axis=1)
            col += 1

        # Cross-coupling invariants: I_{K1,K2} = Σ_q T^{(K1)}_q T^{(K2)}_q
        if self.max_correlation_order >= 2:
            for i, K1 in enumerate(K_list):
                for K2 in K_list[i + 1 :]:
                    # Both tensors have different lengths.
                    # Inner product over the shared q range [-min(K1,K2), min(K1,K2)].
                    K_min = min(K1, K2)
                    # Slice to the central 2*K_min+1 entries.
                    n_q_shared = 2 * K_min + 1
                    offset_1 = K1 - K_min
                    offset_2 = K2 - K_min
                    features[:, col] = np.sum(
                        all_tensors[K1][:, offset_1 : offset_1 + n_q_shared]
                        * all_tensors[K2][:, offset_2 : offset_2 + n_q_shared],
                        axis=1,
                    )
                    col += 1

        return features

    # ------------------------------------------------------------------
    # Invariant builder (from tensor dict)
    # ------------------------------------------------------------------

    def _build_invariants(
        self, tensors: dict[int, np.ndarray]
    ) -> np.ndarray:
        parts: list[np.ndarray] = []
        K_list = self._cg.k_values

        for K in K_list:
            parts.append(np.array([float(np.sum(tensors[K] ** 2))]))

        if self.max_correlation_order >= 2:
            for i, K1 in enumerate(K_list):
                for K2 in K_list[i + 1 :]:
                    K_min = min(K1, K2)
                    n_shared = 2 * K_min + 1
                    o1 = K1 - K_min
                    o2 = K2 - K_min
                    val = float(
                        np.sum(
                            tensors[K1][o1 : o1 + n_shared]
                            * tensors[K2][o2 : o2 + n_shared]
                        )
                    )
                    parts.append(np.array([val]))

        return np.concatenate(parts)

    # ------------------------------------------------------------------
    # Rotation-equivariance verification
    # ------------------------------------------------------------------

    def build_spin_q_rotation(
        self,
        axis: tuple[float, float, float] = (1.0, 2.0, 3.0),
        angle: float = 0.371,
    ) -> np.ndarray:
        """Build the spin-Q Wigner D-matrix for a finite rotation (complex).

        Returns the full complex unitary matrix U = exp(-iθ n̂·J) in the
        |Q,m⟩ basis with m = Q, Q-1, …, -Q (the Condon–Shortley convention).

        For integer Q the D-matrix is *not* purely real in this basis;
        use ``build_occupation_rotation`` for the real |D|² transformation
        appropriate for occupation-number vectors.
        """
        from scipy import linalg

        Q = self.q_value
        dim = self.n_orbitals

        m_vals = np.arange(Q, -Q - 1, -1, dtype=np.float64)
        J_z = np.diag(m_vals)

        raising = np.zeros((dim, dim), dtype=np.complex128)
        for i in range(dim - 1):
            m = Q - i
            raising[i, i + 1] = np.sqrt((Q - m) * (Q + m + 1))
        lowering = raising.conjugate().T

        J_x = 0.5 * (raising + lowering)
        J_y = -0.5j * (raising - lowering)

        axis_arr = np.asarray(axis, dtype=np.float64)
        axis_arr = axis_arr / np.linalg.norm(axis_arr)
        gen = axis_arr[0] * J_x + axis_arr[1] * J_y + axis_arr[2] * J_z

        return linalg.expm(-1j * angle * gen)

    def build_occupation_rotation(
        self,
        axis: tuple[float, float, float] = (1.0, 2.0, 3.0),
        angle: float = 0.371,
    ) -> np.ndarray:
        """Build the real rotation matrix for occupation-vector transformation.

        Under a physical rotation R ∈ SO(3), the occupation numbers n_m
        transform as n' = |D^Q(R)|² n, where |D^Q(R)|²_{m,m'} = |D^Q_{m,m'}(R)|²
        is the element-wise squared modulus of the Wigner D-matrix.

        Returns
        -------
        np.ndarray
            Real (2Q+1)×(2Q+1) matrix of |D^Q_{m,m'}(R)|².
        """
        D = self.build_spin_q_rotation(axis=axis, angle=angle)
        return np.asarray(np.abs(D) ** 2, dtype=np.float64)

    def rotate_occupation_vector(
        self,
        occupation_vector: np.ndarray,
        *,
        axis: tuple[float, float, float] = (1.0, 2.0, 3.0),
        angle: float = 0.371,
    ) -> np.ndarray:
        """Apply the physical occupation-number rotation.

        Uses :math:`n' = |D^Q(R)|^2 n`, the correct transformation for
        occupation numbers under a physical rotation of the orbital basis.

        Returns the rotated vector (same shape as input).
        """
        rotation = self.build_occupation_rotation(axis=axis, angle=angle)
        vec = np.asarray(occupation_vector, dtype=np.float64)
        return rotation @ vec


# ===========================================================================
# Convenience: full tensor square (standalone function)
# ===========================================================================


def tensor_square_cg(
    vector: np.ndarray,
    two_q: int,
) -> dict[int, np.ndarray]:
    """Compute the symmetric CG tensor square of a spin-Q vector.

    T^{(K)}_q = Σ_{m1,m2} ⟨Q,m1; Q,m2 | K,q⟩ v_{m1} v_{m2}

    Allowed K: even for integer Q, odd for half-integer Q
    (dictated by Bose symmetry of the symmetric tensor product).

    Parameters
    ----------
    vector : np.ndarray
        Length ``2Q+1`` float64 vector.
    two_q : int
        Twice the monopole strength.

    Returns
    -------
    dict[int, np.ndarray]
        ``result[K]`` is a float64 array of length ``2K+1``.
    """
    extractor = SO3FeatureExtractor(two_q)
    decomp = extractor.decompose(vector)
    return decomp.tensors


def invariant_norm(tensor: np.ndarray) -> float:
    """SO(3)-invariant squared norm: :math:`\\sum_q (T_q)^2`."""
    return float(np.sum(np.asarray(tensor, dtype=np.float64) ** 2))


def invariant_cross(tensor_a: np.ndarray, tensor_b: np.ndarray) -> float:
    """SO(3)-invariant cross-coupling: :math:`\\sum_q T^{(A)}_q T^{(B)}_q`.

    Tensors must belong to the same K (same length).
    """
    a = np.asarray(tensor_a, dtype=np.float64)
    b = np.asarray(tensor_b, dtype=np.float64)
    if a.shape != b.shape:
        raise ValueError("cross-coupling requires tensors of the same rank")
    return float(np.sum(a * b))
