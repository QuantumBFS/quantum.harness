import numpy as np

import chiral_graviton.angular_momentum as angular_momentum
from chiral_graviton.angular_momentum import highest_weight_basis
from chiral_graviton.basis import FockBasis, SphereSystem
from chiral_graviton.scalable_nqs import (
    SparseHighestWeightProjector,
    SparseProjectedMLP,
)


def test_sparse_projector_matches_dense_small_system():
    basis = FockBasis(SphereSystem.from_electron_count(4), two_lz=4)
    sparse_projector = SparseHighestWeightProjector(basis)
    dense_basis = highest_weight_basis(basis)
    raw = np.random.default_rng(7).normal(size=basis.dimension)

    actual, certificate = sparse_projector.project_with_certificate(raw)
    expected = dense_basis @ (dense_basis.T @ raw)

    np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-11)
    assert certificate.raising_residual < 2e-10
    assert certificate.l2_excess < 4e-20


def test_sparse_projector_is_idempotent_and_self_adjoint():
    basis = FockBasis(SphereSystem.from_electron_count(5), two_lz=0)
    projector = SparseHighestWeightProjector(basis)
    rng = np.random.default_rng(11)
    left = rng.normal(size=basis.dimension)
    right = rng.normal(size=basis.dimension)
    projected_left = projector.project(left)
    projected_right = projector.project(right)

    np.testing.assert_allclose(
        projector.project(projected_left), projected_left, rtol=1e-10, atol=1e-11
    )
    np.testing.assert_allclose(
        left @ projected_right, projected_left @ right, rtol=1e-10, atol=1e-11
    )
    np.testing.assert_array_equal(projector.project(np.zeros(basis.dimension)), 0.0)


def test_n8_projection_avoids_dense_null_space_and_is_certified(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("dense highest_weight_basis must not be called")

    monkeypatch.setattr(angular_momentum, "highest_weight_basis", fail_if_called)
    system = SphereSystem.from_electron_count(8)
    basis = FockBasis(system, two_lz=4)
    projector = SparseHighestWeightProjector(basis)
    raw = np.random.default_rng(19).normal(size=basis.dimension)
    projected, certificate = projector.project_with_certificate(raw)

    assert basis.dimension == 8439
    assert projector.kernel_dimension == 101
    assert projected.shape == (8439,)
    assert certificate.raising_residual < 2e-10
    assert projector.sparse_storage_bytes < projector.avoided_dense_basis_bytes


def test_sparse_projected_nqs_gradient_matches_finite_difference():
    model = SparseProjectedMLP.build(
        SphereSystem.from_electron_count(4), "v1", hidden_width=4, seed=43
    )
    parameters = model.initial_parameters.copy()
    _, gradient = model.objective_and_gradient(parameters)
    epsilon = 2e-6
    for index in (0, 5, model.parameter_count - 2):
        plus = parameters.copy()
        minus = parameters.copy()
        plus[index] += epsilon
        minus[index] -= epsilon
        numeric = (
            model.objective_and_gradient(plus)[0]
            - model.objective_and_gradient(minus)[0]
        ) / (2.0 * epsilon)
        np.testing.assert_allclose(gradient[index], numeric, rtol=3e-4, atol=3e-6)


def test_sparse_projected_nqs_has_certified_l0_l2_and_sampling_error():
    model = SparseProjectedMLP.build(
        SphereSystem.from_electron_count(3), "coulomb", hidden_width=6, seed=29
    )
    for total_l in (0, 2):
        certificate = model.projection_certificate(model.initial_parameters, total_l)
        estimate = model.estimate(model.initial_parameters, total_l)
        assert certificate.raising_residual < 2e-10
        np.testing.assert_allclose(
            estimate.l2_expectation, total_l * (total_l + 1), atol=1e-10
        )

    sampled = model.sample_energy(
        model.initial_parameters, 2, n_samples=2000, seed=101
    )
    assert sampled.standard_error >= 0.0
    np.testing.assert_allclose(
        sampled.mean, model.estimate(model.initial_parameters, 2).energy, atol=1e-12
    )
