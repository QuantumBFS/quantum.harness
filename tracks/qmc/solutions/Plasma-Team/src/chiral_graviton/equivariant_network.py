"""SO(3)-equivariant neural network from CG tensor-product building blocks.

Architecture
------------

The network operates on the CG tensor square of an occupation vector,
which produces genuine SO(3) irreducible spherical tensors :math:`T^{(K)}_q`.
These irreps transform correctly under the spin-K Wigner D-matrix, unlike
the raw occupation numbers (which transform under :math:`|D|^2`, not a group
representation).

From the irreps, we build a network where **every operation preserves SO(3)
representation labels**:

1. **Tensor product** — :math:`T^{(K_1)} \\otimes T^{(K_2)}` decomposed via
   Clebsch–Gordan into new irreps :math:`T^{(L)}`.  This is a fixed (not
   learnable) bilinear operation precomputed once per basis state.

2. **Channel mixing** — learnable linear transformation within each L sector
   that mixes different "channels" (different source pairs producing the
   same L).  Commutes with SO(3) by construction.

3. **Gated nonlinearity** — multiplies each channel by a learned sigmoidal
   function of its own SO(3)-invariant norm.  Preserves irrep labels.

4. **Readout** — extracts the L=0 scalar (ground state) and L=2 rank-2
   tensor (graviton) from the final irreps.

The key guarantee: the network output for L=0 is an SO(3) scalar, and for
L=2 it is the m=2 component of a genuine rank-2 tensor.  This makes the
resulting quantum states architecturally symmetry-respecting.

No external dependencies — uses the same sympy CG coefficients as
``equivariant.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .equivariant import _cg, _get_cg_tensor


# ===========================================================================
# CG tensor-product coefficient cache
# ===========================================================================


_CG_TP_CACHE: dict[tuple[int, int, int], np.ndarray] = {}


def _get_cg_tensor_product(L1: int, L2: int, L_out: int) -> np.ndarray:
    """CG coupling tensor for the tensor product L1 ⊗ L2 → L_out.

    Returns
    -------
    np.ndarray
        Shape ``(2*L_out+1, 2*L1+1, 2*L2+1)``, float64.
        ``C[q, a, b] = ⟨L1, m1(a); L2, m2(b) | L_out, m(q)⟩``
        where m1(a) = L1 - a, m2(b) = L2 - b, m(q) = L_out - q
        (Condon–Shortley descending-m convention).
    """
    key = (L1, L2, L_out)
    if key in _CG_TP_CACHE:
        return _CG_TP_CACHE[key]

    if abs(L1 - L2) > L_out or L_out > L1 + L2:
        raise ValueError(f"L_out={L_out} not in [|{L1}-{L2}|, {L1}+{L2}]")

    C = np.zeros((2 * L_out + 1, 2 * L1 + 1, 2 * L2 + 1), dtype=np.float64)
    for q_idx, q in enumerate(range(-L_out, L_out + 1)):
        for a_idx, a in enumerate(range(-L1, L1 + 1)):
            for b_idx, b in enumerate(range(-L2, L2 + 1)):
                if abs(a + b - q) > 1e-12:
                    continue
                C[q_idx, a_idx, b_idx] = _cg(
                    float(L1), float(a),
                    float(L2), float(b),
                    float(L_out), float(q),
                )
    _CG_TP_CACHE[key] = C
    return C


# ===========================================================================
# Precomputed tensor-product features (fixed per basis state)
# ===========================================================================


@dataclass(frozen=True)
class TPSources:
    """Precomputed tensor-product contributions for one state.

    For each output L, stores the concatenated contributions from all
    (K1, K2) source pairs.  These are fixed given the occupation vector
    and need only be computed once.
    """

    sources: dict[int, np.ndarray]
    """``sources[L]`` has shape ``(n_sources_L, 2L+1)`` — one row per
    (K1, K2) pair that can couple to L."""

    @property
    def output_Ls(self) -> list[int]:
        return sorted(self.sources.keys())


def compute_tp_features(
    cg_tensors: dict[int, np.ndarray],
    max_L_out: int | None = None,
) -> TPSources:
    """Compute all pairwise tensor products of CG tensors for one state.

    Parameters
    ----------
    cg_tensors : dict[int, np.ndarray]
        ``{K: tensor_q}`` from the CG tensor square.  Each value is a 1-D
        array of length ``2K+1`` (single channel).
    max_L_out : int | None
        Maximum output L to compute.  Defaults to ``2 * max(K)``.

    Returns
    -------
    TPSources
    """
    K_values = sorted(cg_tensors.keys())
    if not K_values:
        return TPSources({})

    if max_L_out is None:
        max_L_out = 2 * max(K_values)

    sources: dict[int, list[np.ndarray]] = {}

    for L_out in range(max_L_out + 1):
        contribs: list[np.ndarray] = []
        for K1 in K_values:
            for K2 in K_values:
                if abs(K1 - K2) > L_out or L_out > K1 + K2:
                    continue
                C = _get_cg_tensor_product(K1, K2, L_out)  # (2L+1, 2K1+1, 2K2+1)
                t1 = cg_tensors[K1]  # (2K1+1,)
                t2 = cg_tensors[K2]  # (2K2+1,)
                # result[q] = Σ_{a,b} C[q,a,b] * t1[a] * t2[b]
                contrib = np.einsum("qab,a,b->q", C, t1, t2)
                contribs.append(contrib)
        if contribs:
            sources[L_out] = contribs

    return TPSources(
        {L: np.stack(contribs) for L, contribs in sources.items()}  # type: ignore[arg-type]
    )


# ===========================================================================
# Equivariant block: channel mixing + gate
# ===========================================================================


class EquivariantBlock:
    """One layer of learnable equivariant processing.

    Takes precomputed tensor-product sources (fixed per state) and applies
    channel mixing followed by gated nonlinearity.  Both operations are
    SO(3)-equivariant by construction.
    """

    def __init__(
        self,
        source_Ls: Sequence[int],
        source_channels: dict[int, int],
        n_hidden: int,
        *,
        seed: int = 42,
    ):
        """
        Parameters
        ----------
        source_Ls : list of int
            Which L values have input sources.
        source_channels : dict[int, int]
            Number of input channels (source rows) for each L.
        n_hidden : int
            Number of output channels per L (same for all L).
        seed : int
            Random seed for weight initialisation.
        """
        self.source_Ls = list(source_Ls)
        self.n_hidden = n_hidden

        rng = np.random.default_rng(seed)

        # Channel mixing weights: W_L has shape (n_hidden, n_in_L)
        self.channel_weights: dict[int, np.ndarray] = {}
        # Gate parameters (one scalar weight + one bias per output channel)
        self.gate_w: dict[int, np.ndarray] = {}
        self.gate_b: dict[int, np.ndarray] = {}

        for L in self.source_Ls:
            n_in = source_channels.get(L, 0)
            if n_in == 0:
                continue
            self.channel_weights[L] = rng.normal(
                0, 0.5 / np.sqrt(max(n_in, 1)), (n_hidden, n_in)
            ).astype(np.float64)
            self.gate_w[L] = rng.normal(0, 0.1, (n_hidden,)).astype(np.float64)
            self.gate_b[L] = np.zeros(n_hidden, dtype=np.float64)

    # ------------------------------------------------------------------
    # Parameter packing
    # ------------------------------------------------------------------

    @property
    def parameter_count(self) -> int:
        total = 0
        for L in self.source_Ls:
            if L in self.channel_weights:
                total += self.channel_weights[L].size
                total += self.gate_w[L].size
                total += self.gate_b[L].size
        return total

    def pack(self) -> np.ndarray:
        chunks: list[np.ndarray] = []
        for L in self.source_Ls:
            if L in self.channel_weights:
                chunks.append(self.channel_weights[L].ravel())
                chunks.append(self.gate_w[L].ravel())
                chunks.append(self.gate_b[L].ravel())
        return np.concatenate(chunks) if chunks else np.array([], dtype=np.float64)

    def unpack(
        self, flat: np.ndarray
    ) -> tuple[
        dict[int, np.ndarray], dict[int, np.ndarray], dict[int, np.ndarray]
    ]:
        """Return ``(channel_weights, gate_w, gate_b)``."""
        cursor = 0
        ch_w: dict[int, np.ndarray] = {}
        g_w: dict[int, np.ndarray] = {}
        g_b: dict[int, np.ndarray] = {}
        for L in self.source_Ls:
            if L not in self.channel_weights:
                continue
            w = self.channel_weights[L]
            ch_w[L] = flat[cursor : cursor + w.size].reshape(w.shape).copy()
            cursor += w.size
            g_w[L] = flat[cursor : cursor + self.n_hidden].copy()
            cursor += self.n_hidden
            g_b[L] = flat[cursor : cursor + self.n_hidden].copy()
            cursor += self.n_hidden
        return ch_w, g_w, g_b

    # ------------------------------------------------------------------
    # Forward pass
    # ------------------------------------------------------------------

    def forward(
        self,
        tp_sources: TPSources,
        ch_w: dict[int, np.ndarray],
        g_w: dict[int, np.ndarray],
        g_b: dict[int, np.ndarray],
    ) -> dict[int, np.ndarray]:
        """Compute output irreps from precomputed tensor-product sources.

        Returns
        -------
        dict[int, np.ndarray]
            ``{L: array of shape (n_hidden, 2L+1)}`` — gated hidden irreps.
        """
        output: dict[int, np.ndarray] = {}
        for L in self.source_Ls:
            if L not in tp_sources.sources or L not in ch_w:
                continue
            src = tp_sources.sources[L]  # (n_in, 2L+1)
            # Channel mixing (equivariant: same linear map for each q)
            mixed = ch_w[L] @ src  # (n_hidden, 2L+1)
            # Gate: scale each channel by sigmoid(w * log(1 + norm²) + b)
            norms = np.sum(mixed * mixed, axis=1)  # (n_hidden,)
            gate = _sigmoid(g_w[L] * np.log1p(norms) + g_b[L])
            output[L] = mixed * gate[:, np.newaxis]
        return output

    # ------------------------------------------------------------------
    # Forward + backward (for analytic gradients)
    # ------------------------------------------------------------------

    def forward_backward(
        self,
        tp_sources: TPSources,
        ch_w: dict[int, np.ndarray],
        g_w: dict[int, np.ndarray],
        g_b: dict[int, np.ndarray],
        grad_output: dict[int, np.ndarray],
    ) -> tuple[
        dict[int, np.ndarray],
        dict[int, np.ndarray],
        dict[int, np.ndarray],
        dict[int, np.ndarray],
    ]:
        """Forward pass with backward-mode gradient accumulation.

        Parameters
        ----------
        tp_sources : TPSources
            Fixed tensor-product features for one state.
        ch_w, g_w, g_b : dict
            Unpacked parameters.
        grad_output : dict[int, np.ndarray]
            ``{L: ∂loss/∂output[L]}``, each shape ``(n_hidden, 2L+1)``.

        Returns
        -------
        output : dict[int, np.ndarray]
            Forward activations.
        grad_ch_w : dict[int, np.ndarray]
            Gradient w.r.t. channel weights.
        grad_g_w : dict[int, np.ndarray]
            Gradient w.r.t. gate weights.
        grad_g_b : dict[int, np.ndarray]
            Gradient w.r.t. gate biases.
        """
        output: dict[int, np.ndarray] = {}
        grad_ch_w: dict[int, np.ndarray] = {}
        grad_g_w: dict[int, np.ndarray] = {}
        grad_g_b: dict[int, np.ndarray] = {}

        for L in self.source_Ls:
            if L not in tp_sources.sources or L not in ch_w:
                continue
            src = tp_sources.sources[L]  # (n_in, 2L+1)
            n_in = src.shape[0]

            # --- forward ---
            mixed = ch_w[L] @ src  # (n_hidden, 2L+1)
            norms = np.sum(mixed * mixed, axis=1)  # (n_hidden,)
            gate_arg = g_w[L] * np.log1p(norms) + g_b[L]
            gate = _sigmoid(gate_arg)
            out = mixed * gate[:, np.newaxis]
            output[L] = out

            # --- backward ---
            go = grad_output.get(L)
            if go is None:
                grad_ch_w[L] = np.zeros_like(ch_w[L])
                grad_g_w[L] = np.zeros_like(g_w[L])
                grad_g_b[L] = np.zeros_like(g_b[L])
                continue

            # ∂loss/∂out[j,q] * ∂out/∂mixed[j,q] = go[j,q] * gate[j]
            grad_mixed = go * gate[:, np.newaxis]  # (n_hidden, 2L+1)

            # ∂loss/∂gate[j] = Σ_q go[j,q] * mixed[j,q]
            grad_gate = np.sum(go * mixed, axis=1)  # (n_hidden,)

            # ∂loss/∂(gate_arg[j]) = grad_gate[j] * gate[j] * (1 - gate[j])
            grad_gate_arg = grad_gate * gate * (1.0 - gate)  # (n_hidden,)

            # ∂loss/∂g_w[j] = grad_gate_arg[j] * log1p(norms[j])
            grad_g_w[L] = grad_gate_arg * np.log1p(norms)

            # ∂loss/∂g_b[j] = grad_gate_arg[j]
            grad_g_b[L] = grad_gate_arg.copy()

            # Backprop through gate to norms, then to mixed:
            # ∂loss/∂mixed[j,q] += go[j,q] * (∂gate[j]/∂mixed[j,q])
            # ∂gate[j]/∂mixed[j,q] = gate[j]*(1-gate[j]) * g_w[j] * (2*mixed[j,q])/(1+norm[j])
            # = grad_gate_arg[j] * g_w[j] * 2 * mixed[j,q] / (1 + norm[j])
            factor = grad_gate_arg * g_w[L] * 2.0 / (1.0 + norms)  # (n_hidden,)
            grad_mixed += factor[:, np.newaxis] * mixed

            # ∂loss/∂W[j,i] = Σ_q grad_mixed[j,q] * src[i,q]
            grad_ch_w[L] = grad_mixed @ src.T  # (n_hidden, n_in)

        return output, grad_ch_w, grad_g_w, grad_g_b


def _sigmoid(x: np.ndarray) -> np.ndarray:
    """Numerically stable sigmoid."""
    return np.where(
        x >= 0,
        1.0 / (1.0 + np.exp(-x)),
        np.exp(x) / (1.0 + np.exp(x)),
    )


# ===========================================================================
# Readout: extract L=0 scalar and L=2 tensor from hidden irreps
# ===========================================================================


class EquivariantReadout:
    """Learnable readout from hidden irreps to final amplitudes.

    Extracts:
    - L=0 scalar (for ground-state amplitude)
    - L=2 rank-2 tensor, m=2 component (for graviton amplitude)
    """

    def __init__(
        self,
        n_hidden: int,
        has_L0: bool = True,
        has_L2: bool = True,
        *,
        seed: int = 42,
    ):
        self.has_L0 = has_L0
        self.has_L2 = has_L2
        rng = np.random.default_rng(seed)

        if has_L0:
            # L=0 tensor has shape (n_hidden, 1) — one linear weight per channel
            self.l0_weights = rng.normal(0, 0.5 / np.sqrt(n_hidden), (n_hidden,)).astype(np.float64)
        else:
            self.l0_weights = None

        if has_L2:
            # L=2 tensor has shape (n_hidden, 5) — weights map channels → 5 components
            self.l2_weights = rng.normal(
                0, 0.5 / np.sqrt(n_hidden), (n_hidden,)
            ).astype(np.float64)
        else:
            self.l2_weights = None

    @property
    def parameter_count(self) -> int:
        total = 0
        if self.l0_weights is not None:
            total += self.l0_weights.size
        if self.l2_weights is not None:
            total += self.l2_weights.size
        return total

    def pack(self) -> np.ndarray:
        chunks: list[np.ndarray] = []
        if self.l0_weights is not None:
            chunks.append(self.l0_weights.ravel())
        if self.l2_weights is not None:
            chunks.append(self.l2_weights.ravel())
        return np.concatenate(chunks) if chunks else np.array([], dtype=np.float64)

    def unpack(self, flat: np.ndarray) -> tuple[np.ndarray | None, np.ndarray | None]:
        cursor = 0
        l0_w = None
        l2_w = None
        if self.l0_weights is not None:
            l0_w = flat[cursor : cursor + self.l0_weights.size].copy()
            cursor += self.l0_weights.size
        if self.l2_weights is not None:
            l2_w = flat[cursor : cursor + self.l2_weights.size].copy()
            cursor += self.l2_weights.size
        return l0_w, l2_w

    # ------------------------------------------------------------------
    # Forward
    # ------------------------------------------------------------------

    def forward_l0(
        self, hidden: dict[int, np.ndarray], l0_w: np.ndarray
    ) -> float:
        """Extract L=0 scalar amplitude."""
        if 0 not in hidden or l0_w is None:
            return 0.0
        # hidden[0] has shape (n_hidden, 1)
        return float(np.dot(l0_w, hidden[0][:, 0]))

    def forward_l2(
        self, hidden: dict[int, np.ndarray], l2_w: np.ndarray
    ) -> np.ndarray:
        """Extract L=2 tensor (5 components).  Returns (5,) float64."""
        if 2 not in hidden or l2_w is None:
            return np.zeros(5, dtype=np.float64)
        # hidden[2] has shape (n_hidden, 5)
        # l2_w has shape (n_hidden,)
        return np.sum(hidden[2] * l2_w[:, np.newaxis], axis=0)  # (5,)

    # ------------------------------------------------------------------
    # Forward + backward
    # ------------------------------------------------------------------

    def forward_backward_l0(
        self,
        hidden: dict[int, np.ndarray],
        l0_w: np.ndarray,
        grad_out: float,
    ) -> tuple[float, dict[int, np.ndarray], np.ndarray]:
        """Forward + backward for L=0 readout.

        Returns ``(scalar, grad_hidden, grad_l0_w)``.
        """
        if 0 not in hidden or l0_w is None:
            return 0.0, {}, np.zeros(0)

        h0 = hidden[0]  # (n_hidden, 1)
        scalar = float(np.dot(l0_w, h0[:, 0]))

        # Backward
        grad_hidden: dict[int, np.ndarray] = {}
        # ∂scalar/∂h0[j,0] = l0_w[j] → grad_hidden[0][j,0] = grad_out * l0_w[j]
        grad_hidden[0] = np.zeros_like(h0)
        grad_hidden[0][:, 0] = grad_out * l0_w

        # ∂scalar/∂l0_w[j] = h0[j,0] → grad_l0_w = grad_out * h0[:,0]
        grad_l0_w = grad_out * h0[:, 0]

        return scalar, grad_hidden, grad_l0_w

    def forward_backward_l2(
        self,
        hidden: dict[int, np.ndarray],
        l2_w: np.ndarray,
        grad_out: np.ndarray,  # (5,)
    ) -> tuple[np.ndarray, dict[int, np.ndarray], np.ndarray]:
        """Forward + backward for L=2 readout.

        Returns ``(tensor_5, grad_hidden, grad_l2_w)``.
        ``grad_out`` has shape ``(5,)`` — upstream gradient w.r.t. each
        tensor component.
        """
        if 2 not in hidden or l2_w is None:
            return np.zeros(5), {}, np.zeros(0)

        h2 = hidden[2]  # (n_hidden, 5)
        tensor = np.sum(h2 * l2_w[:, np.newaxis], axis=0)  # (5,)

        # Backward
        grad_hidden: dict[int, np.ndarray] = {}
        # ∂tensor[q]/∂h2[j,q] = l2_w[j] → grad_hidden[2][j,q] = grad_out[q] * l2_w[j]
        grad_hidden[2] = grad_out[np.newaxis, :] * l2_w[:, np.newaxis]  # (n_hidden, 5)

        # ∂tensor[q]/∂l2_w[j] = h2[j,q] → grad_l2_w[j] = Σ_q grad_out[q] * h2[j,q]
        grad_l2_w = h2 @ grad_out  # (n_hidden,)

        return tensor, grad_hidden, grad_l2_w


# ===========================================================================
# Full equivariant feature pipeline (fixed per state → learnable network)
# ===========================================================================


@dataclass(frozen=True)
class EquivariantFeatures:
    """Precomputed features for one Fock basis state.

    These are computed once from the occupation vector and reused
    across all training iterations.
    """

    cg_tensors: dict[int, np.ndarray]
    """Raw CG tensor square: ``{K: (2K+1,) ndarray}``."""

    tp_sources: TPSources
    """Precomputed tensor-product sources for the equivariant block."""


class EquivariantFeaturePipeline:
    """Build and cache equivariant features for a set of Fock basis states."""

    def __init__(self, two_q: int):
        self.two_q = two_q
        self._extractor = _get_cg_tensor(two_q)
        self._K_values = list(self._extractor.k_values)

    @property
    def k_values(self) -> list[int]:
        return self._K_values

    def compute_cg_tensors(
        self, occupation_vector: np.ndarray
    ) -> dict[int, np.ndarray]:
        """Compute CG tensor square for one occupation vector.

        Returns ``{K: (2K+1,) ndarray}`` with one channel per K.
        """
        vec = np.asarray(occupation_vector, dtype=np.float64)
        outer = np.outer(vec, vec)
        tensors: dict[int, np.ndarray] = {}
        for K in self._K_values:
            cg = self._extractor.cg_mats[K]  # (2K+1, n_orb, n_orb)
            t = np.einsum("qab,ab->q", cg, outer)
            tensors[K] = np.asarray(t, dtype=np.float64)
        return tensors

    def compute_features(
        self, occupation_vector: np.ndarray, max_L_out: int | None = None
    ) -> EquivariantFeatures:
        """Compute all fixed features for one occupation vector."""
        cg = self.compute_cg_tensors(occupation_vector)
        tp = compute_tp_features(cg, max_L_out=max_L_out)
        return EquivariantFeatures(cg_tensors=cg, tp_sources=tp)

    def compute_features_batch(
        self,
        occupation_matrix: np.ndarray,
        max_L_out: int | None = None,
    ) -> list[EquivariantFeatures]:
        """Compute features for a batch of occupation vectors."""
        features: list[EquivariantFeatures] = []
        for i in range(occupation_matrix.shape[0]):
            features.append(
                self.compute_features(occupation_matrix[i], max_L_out=max_L_out)
            )
        return features


# ===========================================================================
# Full equivariant network: features → block → readout
# ===========================================================================


class SO3EquivariantNetwork:
    """Complete SO(3)-equivariant network for NQS amplitudes.

    Takes per-state CG tensors → tensor product (fixed) → equivariant
    block (learnable) → readout (learnable).
    """

    def __init__(
        self,
        two_q: int,
        n_hidden: int = 8,
        *,
        seed: int = 42,
    ):
        self.two_q = two_q
        self.n_hidden = n_hidden
        self.pipeline = EquivariantFeaturePipeline(two_q)

        # Determine which L values will have tensor-product sources.
        K_list = self.pipeline.k_values

        # Compute the set of output L values from all (K1, K2) tensor products.
        source_L_set: set[int] = set()
        source_channels: dict[int, int] = {}
        for K1 in K_list:
            for K2 in K_list:
                for L in range(abs(K1 - K2), K1 + K2 + 1):
                    source_L_set.add(L)
                    source_channels[L] = source_channels.get(L, 0) + 1

        source_Ls = sorted(source_L_set)
        self.source_Ls = source_Ls
        self.source_channels = source_channels

        # Build learnable components.
        rng = np.random.default_rng(seed)
        block_seed = int(rng.integers(0, 2**31 - 1))
        readout_seed = int(rng.integers(0, 2**31 - 1))

        self.block = EquivariantBlock(
            source_Ls, source_channels, n_hidden, seed=block_seed
        )
        self.readout = EquivariantReadout(
            n_hidden,
            has_L0=(0 in source_Ls),
            has_L2=(2 in source_Ls),
            seed=readout_seed,
        )

    # ------------------------------------------------------------------
    # Parameter layout
    # ------------------------------------------------------------------

    @property
    def parameter_count(self) -> int:
        return self.block.parameter_count + self.readout.parameter_count

    @property
    def block_param_count(self) -> int:
        return self.block.parameter_count

    @property
    def readout_param_count(self) -> int:
        return self.readout.parameter_count

    def pack(self) -> np.ndarray:
        return np.concatenate([self.block.pack(), self.readout.pack()])

    def unpack(self, flat: np.ndarray):
        """Return ``(block_params, readout_params)`` as unpacked dicts/tuples."""
        b_count = self.block.parameter_count
        block_flat = flat[:b_count]
        readout_flat = flat[b_count:]
        ch_w, g_w, g_b = self.block.unpack(block_flat)
        l0_w, l2_w = self.readout.unpack(readout_flat)
        return (ch_w, g_w, g_b), (l0_w, l2_w)

    # ------------------------------------------------------------------
    # Forward pass (one state)
    # ------------------------------------------------------------------

    def forward_one(
        self,
        features: EquivariantFeatures,
        ch_w: dict[int, np.ndarray],
        g_w: dict[int, np.ndarray],
        g_b: dict[int, np.ndarray],
        l0_w: np.ndarray | None,
        l2_w: np.ndarray | None,
    ) -> tuple[float, np.ndarray, dict[int, np.ndarray]]:
        """Forward pass for one Fock basis state.

        Returns
        -------
        scalar_0 : float
            L=0 amplitude (0.0 if L=0 not available).
        tensor_2 : np.ndarray
            (5,) L=2 tensor (zeros if L=2 not available).
        hidden : dict[int, np.ndarray]
            Hidden irreps (for backward pass).
        """
        hidden = self.block.forward(features.tp_sources, ch_w, g_w, g_b)
        s0 = (
            self.readout.forward_l0(hidden, l0_w)
            if l0_w is not None
            else 0.0
        )
        t2 = (
            self.readout.forward_l2(hidden, l2_w)
            if l2_w is not None
            else np.zeros(5, dtype=np.float64)
        )
        return s0, t2, hidden

    # ------------------------------------------------------------------
    # Forward + backward (one state)
    # ------------------------------------------------------------------

    def forward_backward_one(
        self,
        features: EquivariantFeatures,
        ch_w: dict[int, np.ndarray],
        g_w: dict[int, np.ndarray],
        g_b: dict[int, np.ndarray],
        l0_w: np.ndarray | None,
        l2_w: np.ndarray | None,
        grad_s0: float,
        grad_t2: np.ndarray,
    ) -> tuple[
        float,
        np.ndarray,
        dict[int, np.ndarray],
        dict[int, np.ndarray],
        dict[int, np.ndarray],
        np.ndarray | None,
        np.ndarray | None,
    ]:
        """Forward + backward for one state.

        Parameters
        ----------
        grad_s0 : float
            Upstream gradient w.r.t. L=0 scalar output.
        grad_t2 : np.ndarray
            (5,) upstream gradient w.r.t. L=2 tensor output.

        Returns
        -------
        s0, t2 : forward outputs
        grad_ch_w, grad_g_w, grad_g_b : block parameter gradients
        grad_l0_w, grad_l2_w : readout parameter gradients
        """
        # Forward through block
        hidden, grad_ch_w, grad_g_w, grad_g_b = self.block.forward_backward(
            features.tp_sources, ch_w, g_w, g_b, {}
        )

        # We need to redo the block forward-backward with the hidden→readout grads.
        # Actually, let's do it in the correct order:
        # 1. Block forward (no grad yet)
        # 2. Readout forward + backward (accumulates grad_hidden)
        # 3. Block backward (using grad_hidden)

        # Step 1: Block forward (already have hidden from above, but without grads)
        # Let's just recompute forward cleanly.
        hidden = self.block.forward(features.tp_sources, ch_w, g_w, g_b)

        # Step 2: Readout forward + backward
        grad_hidden_total: dict[int, np.ndarray] = {}
        s0 = 0.0
        t2 = np.zeros(5, dtype=np.float64)
        grad_l0_w: np.ndarray | None = None
        grad_l2_w: np.ndarray | None = None

        if l0_w is not None and 0 in hidden and grad_s0 != 0.0:
            s0, gh0, gl0 = self.readout.forward_backward_l0(hidden, l0_w, grad_s0)
            grad_l0_w = gl0
            for L, g in gh0.items():
                grad_hidden_total[L] = grad_hidden_total.get(L, 0.0) + g  # type: ignore[assignment]

        if l2_w is not None and 2 in hidden and np.any(grad_t2 != 0.0):
            t2, gh2, gl2 = self.readout.forward_backward_l2(hidden, l2_w, grad_t2)
            grad_l2_w = gl2
            for L, g in gh2.items():
                grad_hidden_total[L] = grad_hidden_total.get(L, 0.0) + g  # type: ignore[assignment]

        # Step 3: Block backward with accumulated grad_hidden
        _, grad_ch_w, grad_g_w, grad_g_b = self.block.forward_backward(
            features.tp_sources, ch_w, g_w, g_b, grad_hidden_total
        )

        if grad_l0_w is None:
            grad_l0_w = np.zeros(self.readout.l0_weights.size if self.readout.l0_weights is not None else 0)
        if grad_l2_w is None:
            grad_l2_w = np.zeros(self.readout.l2_weights.size if self.readout.l2_weights is not None else 0)

        return s0, t2, grad_ch_w, grad_g_w, grad_g_b, grad_l0_w, grad_l2_w


# ===========================================================================
# Convenience: build network for a given system
# ===========================================================================


def build_so3_network(
    two_q: int,
    n_hidden: int = 8,
    *,
    seed: int = 42,
) -> SO3EquivariantNetwork:
    """Build an SO(3)-equivariant network for the given monopole strength.

    Parameters
    ----------
    two_q : int
        Twice the monopole strength 2Q.
    n_hidden : int
        Number of hidden channels per L in the equivariant block.
    seed : int
        Random seed for weight initialisation.
    """
    return SO3EquivariantNetwork(two_q, n_hidden, seed=seed)
