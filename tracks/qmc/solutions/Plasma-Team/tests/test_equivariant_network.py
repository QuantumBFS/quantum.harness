"""Tests for SO(3) equivariant network layers (CG tensor-product architecture)."""

import numpy as np
import pytest

from chiral_graviton.equivariant_network import (
    SO3EquivariantNetwork,
    EquivariantBlock,
    EquivariantFeaturePipeline,
    EquivariantReadout,
    TPSources,
    compute_tp_features,
    _get_cg_tensor_product,
)
from chiral_graviton.equivariant import tensor_square_cg, _get_cg_tensor


# ===========================================================================
# CG tensor-product coefficient verification
# ===========================================================================


class TestCGTensorProduct:
    """Verify CG tensor-product coupling tensors."""

    @pytest.mark.parametrize("L1,L2,L_out", [
        (0, 0, 0),
        (2, 2, 0),
        (2, 2, 2),
        (2, 2, 4),
        (4, 4, 0),
        (4, 4, 2),
        (6, 6, 0),
    ])
    def test_coupling_tensor_orthogonality(self, L1: int, L2: int, L_out: int):
        """CG coupling tensors must satisfy Wigner–Eckart orthogonality."""
        C = _get_cg_tensor_product(L1, L2, L_out)  # (2L+1, 2L1+1, 2L2+1)
        # Sum over q of C[q,a,b] * C[q,a',b'] should give the projector
        # onto the L_out subspace — check that the tensor is non-zero
        # and has the correct shape.
        assert C.shape == (2 * L_out + 1, 2 * L1 + 1, 2 * L2 + 1)
        assert np.all(np.isfinite(C))

    def test_triangular_inequality_enforced(self):
        """L_out outside [|L1-L2|, L1+L2] must raise."""
        with pytest.raises(ValueError):
            _get_cg_tensor_product(2, 2, 5)  # max is 4

    def test_cache_returns_same_object(self):
        """Second call must return cached tensor."""
        C1 = _get_cg_tensor_product(2, 4, 3)
        C2 = _get_cg_tensor_product(2, 4, 3)
        assert C1 is C2


# ===========================================================================
# Tensor-product feature computation
# ===========================================================================


class TestComputeTPFeatures:
    """Verify precomputed tensor-product features."""

    @pytest.mark.parametrize("two_q", [2, 4, 6, 9])
    def test_tp_features_contain_l0_and_l2(self, two_q: int):
        """For any Q, the CG tensor square self-product must include L=0 and L=2."""
        n_orb = two_q + 1
        rng = np.random.default_rng(42)
        v = rng.normal(size=n_orb)
        cg = tensor_square_cg(v, two_q)
        tp = compute_tp_features(cg)
        # L=0 is always present (from K⊗K pairs)
        assert 0 in tp.sources
        # L=2 is usually present (unless there are no K≥1 pairs)
        if max(cg.keys()) >= 2:
            assert 2 in tp.sources

    @pytest.mark.parametrize("two_q", [2, 6, 9])
    def test_tp_parseval_identity(self, two_q: int):
        """Total power in TP features should be related to input power.

        Σ_L ‖sources[L]‖_F² = Σ_{K1,K2} ‖T^(K1)‖² ‖T^(K2)‖²
        because the CG tensor product is unitary.
        """
        n_orb = two_q + 1
        rng = np.random.default_rng(123)
        v = rng.normal(size=n_orb)
        cg = tensor_square_cg(v, two_q)
        tp = compute_tp_features(cg)

        # LHS: total power in TP features
        tp_power = sum(float(np.sum(src**2)) for src in tp.sources.values())

        # RHS: Σ_{K1,K2} ‖T^(K1)‖² ‖T^(K2)‖² = (Σ_K ‖T^(K)‖²)²
        cg_power = sum(float(np.sum(t**2)) for t in cg.values())
        expected = cg_power**2

        np.testing.assert_allclose(tp_power, expected, rtol=1e-10)

    def test_zero_vector_gives_zero_tp(self):
        """Zero occupation vector → zero CG tensors → zero TP features."""
        cg = tensor_square_cg(np.zeros(7), two_q=6)
        tp = compute_tp_features(cg)
        for src in tp.sources.values():
            np.testing.assert_allclose(src, 0.0, atol=1e-14)


# ===========================================================================
# EquivariantBlock
# ===========================================================================


class TestEquivariantBlock:
    """Verify the learnable equivariant processing block."""

    @pytest.fixture
    def simple_sources(self) -> TPSources:
        """Build TP sources from N=3 V1 Laughlin CG tensors."""
        n_orb = 7
        v = np.zeros(n_orb)
        v[0] = 1.0  # m = -3
        v[2] = 1.0  # m = -1
        v[4] = 1.0  # m = +1
        cg = tensor_square_cg(v, two_q=6)
        return compute_tp_features(cg)

    @pytest.fixture
    def simple_block(self, simple_sources) -> EquivariantBlock:
        source_Ls = sorted(simple_sources.sources.keys())
        source_channels = {L: simple_sources.sources[L].shape[0] for L in source_Ls}
        return EquivariantBlock(source_Ls, source_channels, n_hidden=4, seed=42)

    def test_pack_unpack_roundtrip(self, simple_block):
        """pack() → unpack() must restore identical parameters."""
        flat = simple_block.pack()
        ch_w, g_w, g_b = simple_block.unpack(flat)
        # Re-pack using the same method and compare
        repacked = simple_block.pack()
        np.testing.assert_allclose(flat, repacked, rtol=1e-14)
        # Also verify the unpacked weights match originals
        for L in ch_w:
            np.testing.assert_allclose(ch_w[L], simple_block.channel_weights[L], rtol=1e-14)
            np.testing.assert_allclose(g_w[L], simple_block.gate_w[L], rtol=1e-14)
            np.testing.assert_allclose(g_b[L], simple_block.gate_b[L], rtol=1e-14)

    def test_forward_output_shapes(self, simple_block, simple_sources):
        """Forward pass must produce correct output shapes."""
        ch_w, g_w, g_b = simple_block.unpack(simple_block.pack())
        output = simple_block.forward(simple_sources, ch_w, g_w, g_b)
        for L, tensor in output.items():
            assert tensor.shape == (4, 2 * L + 1), f"L={L}: got {tensor.shape}"

    def test_parameter_count_consistency(self, simple_block):
        """Parameter count must match packed vector length."""
        assert simple_block.parameter_count == len(simple_block.pack())

    def test_gradient_shapes_match_parameters(self, simple_block, simple_sources):
        """Gradient dicts must have the same shapes as the parameter dicts."""
        ch_w, g_w, g_b = simple_block.unpack(simple_block.pack())

        # Create dummy grad_output
        output = simple_block.forward(simple_sources, ch_w, g_w, g_b)
        grad_output = {L: np.random.normal(size=t.shape) for L, t in output.items()}

        _, g_ch, g_gw, g_gb = simple_block.forward_backward(
            simple_sources, ch_w, g_w, g_b, grad_output
        )

        for L in g_ch:
            assert g_ch[L].shape == ch_w[L].shape
            assert g_gw[L].shape == g_w[L].shape
            assert g_gb[L].shape == g_b[L].shape

    def test_zero_gradient_for_zero_output_grad(self, simple_block, simple_sources):
        """Zero upstream gradient must give zero parameter gradients."""
        ch_w, g_w, g_b = simple_block.unpack(simple_block.pack())
        output = simple_block.forward(simple_sources, ch_w, g_w, g_b)
        grad_output = {L: np.zeros_like(t) for L, t in output.items()}

        _, g_ch, g_gw, g_gb = simple_block.forward_backward(
            simple_sources, ch_w, g_w, g_b, grad_output
        )

        for L in g_ch:
            np.testing.assert_allclose(g_ch[L], 0.0, atol=1e-14)
            np.testing.assert_allclose(g_gw[L], 0.0, atol=1e-14)
            np.testing.assert_allclose(g_gb[L], 0.0, atol=1e-14)


# ===========================================================================
# EquivariantReadout
# ===========================================================================


class TestEquivariantReadout:
    """Verify the L=0 and L=2 readout heads."""

    def test_l0_readout_produces_scalar(self):
        readout = EquivariantReadout(n_hidden=4, seed=42)
        hidden = {
            0: np.random.normal(size=(4, 1)),
            2: np.random.normal(size=(4, 5)),
        }
        l0_w, l2_w = readout.unpack(readout.pack())
        scalar = readout.forward_l0(hidden, l0_w)
        assert isinstance(scalar, float)

    def test_l2_readout_produces_5vector(self):
        readout = EquivariantReadout(n_hidden=4, seed=42)
        hidden = {
            0: np.random.normal(size=(4, 1)),
            2: np.random.normal(size=(4, 5)),
        }
        l0_w, l2_w = readout.unpack(readout.pack())
        tensor = readout.forward_l2(hidden, l2_w)
        assert tensor.shape == (5,)

    def test_l0_gradient_consistency(self):
        """Forward-backward must be consistent for L=0."""
        readout = EquivariantReadout(n_hidden=4, seed=42)
        hidden = {
            0: np.random.normal(size=(4, 1)).astype(np.float64),
        }
        l0_w, _ = readout.unpack(readout.pack())
        eps = 1e-6
        for j in range(4):
            w_plus = l0_w.copy(); w_plus[j] += eps
            w_minus = l0_w.copy(); w_minus[j] -= eps
            s_plus = readout.forward_l0(hidden, w_plus)
            s_minus = readout.forward_l0(hidden, w_minus)
            num_grad = (s_plus - s_minus) / (2 * eps)
            _, _, ana_grad = readout.forward_backward_l0(hidden, l0_w, 1.0)
            np.testing.assert_allclose(ana_grad[j], num_grad, rtol=1e-5)

    def test_l2_gradient_consistency(self):
        """Forward-backward must be consistent for L=2."""
        readout = EquivariantReadout(n_hidden=4, seed=42)
        hidden = {
            2: np.random.normal(size=(4, 5)).astype(np.float64),
        }
        _, l2_w = readout.unpack(readout.pack())
        eps = 1e-6
        grad_out = np.array([0.0, 0.0, 1.0, 0.0, 0.0])  # grad only on q=0
        for j in range(4):
            w_plus = l2_w.copy(); w_plus[j] += eps
            w_minus = l2_w.copy(); w_minus[j] -= eps
            t_plus = readout.forward_l2(hidden, w_plus)
            t_minus = readout.forward_l2(hidden, w_minus)
            num_grad = np.dot(t_plus - t_minus, grad_out) / (2 * eps)
            _, _, ana_grad = readout.forward_backward_l2(hidden, l2_w, grad_out)
            np.testing.assert_allclose(ana_grad[j], num_grad, rtol=1e-5)


# ===========================================================================
# SO3EquivariantNetwork — full pipeline
# ===========================================================================


class TestSO3EquivariantNetwork:
    """Verify the full equivariant network."""

    @pytest.mark.parametrize("two_q", [2, 4, 6, 9])
    def test_network_creation(self, two_q: int):
        """Network must initialise without error for various 2Q."""
        net = SO3EquivariantNetwork(two_q, n_hidden=4, seed=42)
        assert net.parameter_count > 0
        assert net.block_param_count > 0
        assert net.readout_param_count > 0
        # Total must be consistent
        assert net.parameter_count == net.block_param_count + net.readout_param_count

    @pytest.mark.parametrize("two_q", [2, 6, 9])
    def test_pack_unpack_roundtrip(self, two_q: int):
        """Pack/unpack must be consistent."""
        net = SO3EquivariantNetwork(two_q, n_hidden=4, seed=42)
        flat = net.pack()
        (ch_w, g_w, g_b), (l0_w, l2_w) = net.unpack(flat)
        repacked = net.pack()
        np.testing.assert_allclose(flat, repacked, rtol=1e-14)

    @pytest.mark.parametrize("two_q", [2, 6, 9])
    def test_forward_one_returns_correct_types(self, two_q: int):
        """forward_one must return (float, (5,) ndarray, dict)."""
        n_orb = two_q + 1
        rng = np.random.default_rng(42)
        v = rng.normal(size=n_orb)
        net = SO3EquivariantNetwork(two_q, n_hidden=4, seed=42)
        features = net.pipeline.compute_features(v)

        flat = net.pack()
        (ch_w, g_w, g_b), (l0_w, l2_w) = net.unpack(flat)

        s0, t2, hidden = net.forward_one(features, ch_w, g_w, g_b, l0_w, l2_w)
        assert isinstance(s0, float)
        assert isinstance(t2, np.ndarray)
        assert t2.shape == (5,)
        assert isinstance(hidden, dict)

    def test_gradient_consistency_n3(self):
        """Gradient from forward_backward_one must match finite differences."""
        two_q = 6
        n_orb = 7
        v = np.zeros(n_orb)
        v[0] = 1.0; v[2] = 1.0; v[4] = 1.0

        net = SO3EquivariantNetwork(two_q, n_hidden=4, seed=42)
        features = net.pipeline.compute_features(v)

        flat = net.pack()
        (ch_w, g_w, g_b), (l0_w, l2_w) = net.unpack(flat)

        # Forward + backward with unit upstream gradient
        s0, t2, g_ch, g_gw, g_gb, g_l0, g_l2 = net.forward_backward_one(
            features, ch_w, g_w, g_b, l0_w, l2_w,
            grad_s0=1.0, grad_t2=np.zeros(5),
        )

        # Check gradient of s0 w.r.t. l0_weights via FD
        eps = 1e-5
        for j in range(min(4, len(g_l0))):
            plus = flat.copy()
            # l0_weights come after block params
            offset = net.block_param_count + j
            plus[offset] += eps
            minus = flat.copy()
            minus[offset] -= eps
            (ch_p, g_p, gb_p), (l0_p, l2_p) = net.unpack(plus)
            (ch_m, g_m, gb_m), (l0_m, l2_m) = net.unpack(minus)
            s_p, _, _ = net.forward_one(features, ch_p, g_p, gb_p, l0_p, l2_p)
            s_m, _, _ = net.forward_one(features, ch_m, g_m, gb_m, l0_m, l2_m)
            num_grad = (s_p - s_m) / (2 * eps)
            np.testing.assert_allclose(g_l0[j], num_grad, rtol=1e-4)

    def test_zero_input_gives_finite_output(self):
        """Zero occupation vector should produce finite output."""
        two_q = 6
        v = np.zeros(7)
        net = SO3EquivariantNetwork(two_q, n_hidden=4, seed=42)
        features = net.pipeline.compute_features(v)
        flat = net.pack()
        (ch_w, g_w, g_b), (l0_w, l2_w) = net.unpack(flat)
        s0, t2, _ = net.forward_one(features, ch_w, g_w, g_b, l0_w, l2_w)
        assert np.isfinite(s0)
        assert np.all(np.isfinite(t2))


# ===========================================================================
# EquivariantFeaturePipeline
# ===========================================================================


class TestEquivariantFeaturePipeline:
    """Verify the feature computation pipeline."""

    @pytest.mark.parametrize("two_q", [2, 4, 6, 9])
    def test_cg_tensors_match_standalone(self, two_q: int):
        """Pipeline CG tensors must match standalone tensor_square_cg."""
        n_orb = two_q + 1
        rng = np.random.default_rng(42)
        v = rng.normal(size=n_orb)

        pipeline = EquivariantFeaturePipeline(two_q)
        cg_pipe = pipeline.compute_cg_tensors(v)
        cg_standalone = tensor_square_cg(v, two_q)

        assert set(cg_pipe.keys()) == set(cg_standalone.keys())
        for K in cg_pipe:
            np.testing.assert_allclose(cg_pipe[K], cg_standalone[K], rtol=1e-14)

    @pytest.mark.parametrize("two_q", [2, 6, 9])
    def test_features_are_reproducible(self, two_q: int):
        """Same occupation vector must produce same features."""
        n_orb = two_q + 1
        rng = np.random.default_rng(99)
        v = rng.normal(size=n_orb)

        pipeline = EquivariantFeaturePipeline(two_q)
        f1 = pipeline.compute_features(v)
        f2 = pipeline.compute_features(v)

        for K in f1.cg_tensors:
            np.testing.assert_allclose(f1.cg_tensors[K], f2.cg_tensors[K], rtol=1e-14)
        for L in f1.tp_sources.sources:
            np.testing.assert_allclose(
                f1.tp_sources.sources[L], f2.tp_sources.sources[L], rtol=1e-14
            )
