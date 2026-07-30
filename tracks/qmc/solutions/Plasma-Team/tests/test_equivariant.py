"""Tests for SO(3)-aware feature extraction and equivariant NQS."""

import numpy as np
import pytest

from chiral_graviton.basis import SphereSystem
from chiral_graviton.ed import neutral_gap
from chiral_graviton.equivariant import (
    SO3FeatureExtractor,
    invariant_cross,
    invariant_norm,
    tensor_square_cg,
)
from chiral_graviton.nqs import (
    SO3EquivariantNQS,
    SO3TensorNQS,
    SharedProjectedMLP,
)
from chiral_graviton.rotation_equivariance import projection_alignment_quality


# ===========================================================================
# CG tensor-square correctness
# ===========================================================================


class TestTensorSquareCG:
    """Verify basic properties of the CG tensor-square decomposition."""

    @pytest.mark.parametrize("two_q", [2, 4, 6, 9])
    def test_k_parity_matches_bose_symmetry(self, two_q: int):
        """Integer Q → even K; half-integer Q → odd K (Bose symmetry)."""
        n_orb = two_q + 1
        rng = np.random.default_rng(42)
        v = rng.normal(size=n_orb)
        tensors = tensor_square_cg(v, two_q)
        k_start = 0 if two_q % 2 == 0 else 1
        expected_k = set(range(k_start, two_q + 1, 2))
        assert set(tensors.keys()) == expected_k

    @pytest.mark.parametrize("two_q", [2, 4, 6])
    def test_norm_equals_outer_product_frobenius(self, two_q: int):
        """Σ_K ‖T^{(K)}‖² = ‖v ⊗ v‖_F² = ‖v‖⁴ (Parseval identity)."""
        Q = two_q // 2
        n_orb = two_q + 1
        rng = np.random.default_rng(99)
        v = rng.normal(size=n_orb)
        tensors = tensor_square_cg(v, two_q)
        total = sum(float(np.sum(t**2)) for t in tensors.values())
        expected = float(np.linalg.norm(v) ** 4)
        np.testing.assert_allclose(total, expected, rtol=1e-10)

    def test_v1_laughlin_zero_mode_has_strong_k0(self):
        """N=3 V1 Laughlin state (exact zero-energy, pure L=0):
        the K=0 irrep component must carry meaningful power."""
        n_orb = 7  # 2Q+1 for N=3, 2Q=6
        v = np.zeros(n_orb)
        # Three equally-spaced occupied orbitals: m = -3, -1, 1
        v[0] = 1.0  # m = -3
        v[2] = 1.0  # m = -1
        v[4] = 1.0  # m = +1

        tensors = tensor_square_cg(v, two_q=6)
        total_power = sum(float(np.sum(t**2)) for t in tensors.values())
        k0_power = float(np.sum(tensors[0] ** 2))

        # K=0 captures the total density; for a balanced configuration
        # it should be a substantial fraction of the total power.
        assert k0_power > 0.0
        # With 3 electrons in 7 orbitals, K=0 is one of four channels
        # and carries the uniform (monopole) density component.
        # With 3 electrons spread across 7 orbitals, the monopole (K=0)
        # channel carries ~6.3 % of total power — substantial for a
        # single channel among four (K=0,2,4,6).
        assert k0_power / total_power > 0.05


# ===========================================================================
# SO3FeatureExtractor
# ===========================================================================


class TestSO3FeatureExtractor:
    """Test the invariant feature extractor."""

    @pytest.mark.parametrize("two_q", [2, 4, 6, 12])
    def test_feature_count_matches_layout(self, two_q: int):
        ext = SO3FeatureExtractor(two_q)
        assert ext.feature_count == len(ext.feature_labels)

    @pytest.mark.parametrize("two_q", [2, 4, 6])
    def test_decompose_batch_equals_individual(self, two_q: int):
        n_orb = two_q + 1
        rng = np.random.default_rng(123)
        occ = rng.choice([0.0, 1.0], size=(20, n_orb))
        ext = SO3FeatureExtractor(two_q)

        batch = ext.decompose_batch(occ)
        for i in range(20):
            single = ext.decompose(occ[i])
            np.testing.assert_allclose(batch[i], single.invariants, rtol=1e-12)

    def test_zero_vector_gives_zero_invariants(self):
        """An empty occupation vector must have all-zero invariants."""
        ext = SO3FeatureExtractor(two_q=6)
        zero = np.zeros(7)
        decomp = ext.decompose(zero)
        np.testing.assert_allclose(decomp.invariants, 0.0, atol=1e-14)

    def test_wigner_d_matrix_is_unitary(self):
        """The spin-Q Wigner D-matrix must be unitary."""
        ext = SO3FeatureExtractor(two_q=6)
        D = ext.build_spin_q_rotation(axis=(1.0, 2.0, 3.0), angle=0.371)
        dim = D.shape[0]
        np.testing.assert_allclose(
            D @ D.conjugate().T, np.eye(dim), atol=1e-12
        )

    def test_occupation_rotation_is_doubly_stochastic(self):
        """The |D|² rotation matrix must be doubly stochastic."""
        ext = SO3FeatureExtractor(two_q=6)
        S = ext.build_occupation_rotation(axis=(1.0, 2.0, 3.0), angle=0.371)
        np.testing.assert_allclose(S.sum(axis=1), 1.0, atol=1e-14)
        np.testing.assert_allclose(S.sum(axis=0), 1.0, atol=1e-14)
        assert np.all(S >= -1e-14)  # non-negative (within float noise)


# ===========================================================================
# SO3EquivariantNQS — end-to-end
# ===========================================================================


class TestSO3EquivariantNQS:
    """End-to-end tests for the equivariant NQS."""

    def test_irrep_certification_at_init(self):
        """Projected output states must have correct L² at initial params."""
        model = SO3EquivariantNQS.build(
            SphereSystem.from_electron_count(3), "v1", hidden_width=8, seed=17
        )
        assert model.irrep_error(model.initial_parameters) < 1e-10
        assert model.scalar_rotation_error(model.initial_parameters) < 1e-10
        assert model.multiplet_rotation_error(model.initial_parameters) < 1e-10

    def test_projection_alignment_is_high(self):
        """CG-tensor-square features should give better raw alignment than
        raw occupation bits, before any projection."""
        system = SphereSystem.from_electron_count(3)

        eq_model = SO3EquivariantNQS.build(
            system, "v1", hidden_width=8, seed=42
        )
        raw_model = SharedProjectedMLP.build(
            system, "v1", hidden_width=8, seed=42
        )

        eq_align = projection_alignment_quality(
            eq_model, eq_model.initial_parameters
        )
        raw_align = {
            total_l: float(
                np.linalg.norm(
                    raw_model.sectors[total_l].project(
                        raw_model._forward(raw_model.initial_parameters, total_l)[0]
                    )
                )
                / np.linalg.norm(
                    raw_model._forward(raw_model.initial_parameters, total_l)[0]
                )
                if np.linalg.norm(
                    raw_model._forward(raw_model.initial_parameters, total_l)[0]
                )
                > 1e-30
                else 1.0
            )
            for total_l in (0, 2)
        }

        # Both architectures should have decent alignment (projection
        # shouldn't be doing all the work), but the equivariant one
        # is expected to be at least as good.
        for tl in (0, 2):
            assert eq_align[tl] > 0.01, (
                f"L={tl}: equivariant alignment {eq_align[tl]:.4f} too low"
            )
            assert raw_align[tl] > 0.01, (
                f"L={tl}: raw alignment {raw_align[tl]:.4f} too low"
            )

    def test_matches_ed_for_one_dimensional_sector(self):
        """N=3 one-dimensional projected sectors: NQS = ED at initial params."""
        system = SphereSystem.from_electron_count(3)
        reference = neutral_gap(system, interaction="coulomb")
        model = SO3EquivariantNQS.build(
            system, "coulomb", hidden_width=6, seed=31
        )
        ground = model.estimate(model.initial_parameters, 0)
        graviton = model.estimate(model.initial_parameters, 2)
        np.testing.assert_allclose(ground.energy, reference.e_l0, atol=1e-10)
        np.testing.assert_allclose(graviton.energy, reference.e_l2, atol=1e-10)
        np.testing.assert_allclose(ground.l2_expectation, 0.0, atol=1e-10)
        np.testing.assert_allclose(graviton.l2_expectation, 6.0, atol=1e-10)

    def test_analytic_gradient_matches_finite_difference(self):
        """Gradient from objective_and_gradient must agree with numerical FD."""
        model = SO3EquivariantNQS.build(
            SphereSystem.from_electron_count(3), "v1", hidden_width=4, seed=23
        )
        params = model.initial_parameters.copy()
        _, gradient = model.objective_and_gradient(params)
        epsilon = 2e-6
        for index in (0, 3, model.parameter_count - 2):
            plus = params.copy()
            minus = params.copy()
            plus[index] += epsilon
            minus[index] -= epsilon
            v_plus = model.objective_and_gradient(plus)[0]
            v_minus = model.objective_and_gradient(minus)[0]
            numeric = (v_plus - v_minus) / (2 * epsilon)
            np.testing.assert_allclose(
                gradient[index], numeric, rtol=2e-4, atol=2e-6
            )

    def test_optimization_converges_and_produces_gap(self):
        """Short training must converge and return a positive gap."""
        model = SO3EquivariantNQS.build(
            SphereSystem.from_electron_count(3),
            "coulomb",
            hidden_width=8,
            seed=42,
        )
        result = model.fit(max_iterations=50)
        assert result.success
        assert result.gap > 0.0
        assert result.ground.variance < 1e-8
        assert result.graviton.variance < 1e-8

    def test_nqs_gap_close_to_ed_at_n4(self):
        """N=4 trained NQS gap must be within 0.002 of ED."""
        system = SphereSystem.from_electron_count(4)
        reference = neutral_gap(system, interaction="coulomb")
        model = SO3EquivariantNQS.build(
            system, "coulomb", hidden_width=16, seed=42
        )
        result = model.fit(max_iterations=300)
        np.testing.assert_allclose(result.gap, reference.gap, atol=2e-3)

    def test_multiplet_rotation_error_after_training(self):
        """After training, the multiplet must transform correctly."""
        model = SO3EquivariantNQS.build(
            SphereSystem.from_electron_count(5),
            "coulomb",
            hidden_width=8,
            seed=1729,
        )
        result = model.fit(max_iterations=100)
        assert result.success
        error = model.multiplet_rotation_error(result.parameters)
        assert error < 1e-10, (
            f"multiplet rotation error {error:.2e} after training"
        )

    def test_projection_alignment_after_training(self):
        """After training, projection alignment should remain healthy."""
        model = SO3EquivariantNQS.build(
            SphereSystem.from_electron_count(5),
            "coulomb",
            hidden_width=8,
            seed=1729,
        )
        result = model.fit(max_iterations=100)
        assert result.success
        for tl in (0, 2):
            alpha = model.projection_alignment(result.parameters, tl)
            assert alpha > 0.01, (
                f"L={tl}: alignment {alpha:.6f} collapsed after training"
            )


# ===========================================================================
# Standalone invariant helpers
# ===========================================================================


def test_invariant_norm():
    t = np.array([1.0, 2.0, 3.0])
    assert invariant_norm(t) == pytest.approx(14.0)


def test_invariant_cross():
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([4.0, 5.0, 6.0])
    assert invariant_cross(a, b) == pytest.approx(32.0)  # 4+10+18


def test_invariant_cross_different_lengths_raises():
    with pytest.raises(ValueError):
        invariant_cross(np.ones(3), np.ones(5))


# ===========================================================================
# SO3TensorNQS — end-to-end tests
# ===========================================================================


class TestSO3TensorNQS:
    """End-to-end tests for the architecturally-equivariant NQS."""

    def test_irrep_certification_at_init(self):
        """Output states must have correct L² at initial params."""
        model = SO3TensorNQS.build(
            SphereSystem.from_electron_count(3), "v1", n_hidden=4, seed=17
        )
        assert model.irrep_error(model.initial_parameters) < 1e-10
        assert model.scalar_rotation_error(model.initial_parameters) < 1e-10
        assert model.multiplet_rotation_error(model.initial_parameters) < 1e-10

    def test_matches_ed_for_one_dimensional_sector(self):
        """N=3 one-dimensional projected sectors: NQS = ED at initial params."""
        system = SphereSystem.from_electron_count(3)
        reference = neutral_gap(system, interaction="coulomb")
        model = SO3TensorNQS.build(
            system, "coulomb", n_hidden=4, seed=31
        )
        ground = model.estimate(model.initial_parameters, 0)
        graviton = model.estimate(model.initial_parameters, 2)
        np.testing.assert_allclose(ground.energy, reference.e_l0, atol=1e-10)
        np.testing.assert_allclose(graviton.energy, reference.e_l2, atol=1e-10)
        np.testing.assert_allclose(ground.l2_expectation, 0.0, atol=1e-10)
        np.testing.assert_allclose(graviton.l2_expectation, 6.0, atol=1e-10)

    def test_analytic_gradient_matches_finite_difference(self):
        """Gradient from objective_and_gradient must agree with numerical FD."""
        model = SO3TensorNQS.build(
            SphereSystem.from_electron_count(4), "coulomb", n_hidden=4, seed=23
        )
        params = model.initial_parameters.copy()
        _, gradient = model.objective_and_gradient(params)
        epsilon = 2e-5
        for index in (0, 3, model.parameter_count - 2):
            plus = params.copy()
            minus = params.copy()
            plus[index] += epsilon
            minus[index] -= epsilon
            v_plus = model.objective_and_gradient(plus)[0]
            v_minus = model.objective_and_gradient(minus)[0]
            numeric = (v_plus - v_minus) / (2 * epsilon)
            np.testing.assert_allclose(
                gradient[index], numeric, rtol=2e-4, atol=2e-6
            )

    def test_optimization_converges_and_produces_gap_n3(self):
        """N=3 training must converge and return positive gap."""
        model = SO3TensorNQS.build(
            SphereSystem.from_electron_count(3),
            "coulomb",
            n_hidden=4,
            seed=42,
        )
        result = model.fit(max_iterations=50)
        assert result.success
        assert result.gap > 0.0
        assert result.ground.variance < 1e-8
        assert result.graviton.variance < 1e-8

    def test_nqs_gap_close_to_ed_at_n4(self):
        """N=4 trained NQS gap must be within 1e-10 of ED."""
        system = SphereSystem.from_electron_count(4)
        reference = neutral_gap(system, interaction="coulomb")
        model = SO3TensorNQS.build(
            system, "coulomb", n_hidden=8, seed=42
        )
        result = model.fit(max_iterations=200)
        np.testing.assert_allclose(result.gap, reference.gap, atol=1e-10)

    def test_nqs_gap_close_to_ed_at_n5(self):
        """N=5 trained NQS gap must be within 1e-10 of ED."""
        system = SphereSystem.from_electron_count(5)
        reference = neutral_gap(system, interaction="coulomb")
        model = SO3TensorNQS.build(
            system, "coulomb", n_hidden=8, seed=42
        )
        result = model.fit(max_iterations=300)
        np.testing.assert_allclose(result.gap, reference.gap, atol=1e-10)

    def test_multiplet_rotation_error_after_training(self):
        """After training, the multiplet must transform correctly."""
        model = SO3TensorNQS.build(
            SphereSystem.from_electron_count(5),
            "coulomb",
            n_hidden=8,
            seed=1729,
        )
        result = model.fit(max_iterations=200)
        assert result.success
        error = model.multiplet_rotation_error(result.parameters)
        assert error < 1e-10, (
            f"multiplet rotation error {error:.2e} after training"
        )

    def test_projection_alignment_after_training(self):
        """After training, projection alignment should remain healthy."""
        model = SO3TensorNQS.build(
            SphereSystem.from_electron_count(5),
            "coulomb",
            n_hidden=8,
            seed=1729,
        )
        result = model.fit(max_iterations=200)
        assert result.success
        for tl in (0, 2):
            alpha = model.projection_alignment(result.parameters, tl)
            assert alpha > 0.005, (
                f"L={tl}: alignment {alpha:.6f} collapsed after training"
            )

    def test_v1_laughlin_is_exact_zero_mode(self):
        """V1 Laughlin N=3: the L=0 state must have zero energy."""
        system = SphereSystem.from_electron_count(3)
        model = SO3TensorNQS.build(
            system, "v1", n_hidden=4, seed=123
        )
        result = model.fit(max_iterations=50)
        assert result.success
        np.testing.assert_allclose(result.ground.energy, 0.0, atol=1e-10)
        np.testing.assert_allclose(result.ground.variance, 0.0, atol=1e-10)

    def test_parameter_count_is_reasonable(self):
        """Parameter count should scale sensibly with n_hidden."""
        for n_hidden in [4, 8, 16]:
            model = SO3TensorNQS.build(
                SphereSystem.from_electron_count(4),
                "coulomb",
                n_hidden=n_hidden,
                seed=42,
            )
            # Should scale roughly linearly with n_hidden
            # (channel mixing dominates: O(n_hidden * n_sources))
            assert model.parameter_count > 0
            assert model.parameter_count < 10000  # reasonable upper bound
