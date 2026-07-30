from math import isclose, sqrt

import numpy as np
import pytest

from challenge15.angular import (
    SPARSE_GRAM_TOLERANCE,
    SPARSE_L2_RESIDUAL_TOLERANCE,
    SPARSE_LADDER_TOLERANCE,
    _canonical_projector_basis,
    _canonical_thin_subspace_basis,
    _ladder_coefficient_error,
    angular_operators,
    target_irrep_isometry,
    target_irrep_isometry_sparse,
    verify_ladder_multiplet,
)
from challenge15.fermions import DeterminantBasis
from challenge15.spec import SphereSpec


@pytest.mark.parametrize("particles", [2, 3, 4, 6])
def test_many_body_su2_commutators(particles):
    basis = DeterminantBasis.full(SphereSpec(particles))
    lz, lp, lm = angular_operators(basis)
    scale = max(np.linalg.norm(lz.toarray()), 1.0)
    assert np.linalg.norm((lz @ lp - lp @ lz - lp).toarray()) / scale < 1e-12
    assert np.linalg.norm((lp @ lm - lm @ lp - 2 * lz).toarray()) / scale < 1e-12


@pytest.mark.parametrize("particles,target_l", [(4, 0), (4, 2), (6, 0), (6, 2)])
def test_target_isometry_has_exact_l2(particles, target_l):
    basis = DeterminantBasis.with_two_m(SphereSpec(particles), 0)
    l2 = angular_operators(basis, return_l2_only=True)
    t = target_irrep_isometry(basis, target_l)
    np.testing.assert_allclose(t.conj().T @ t, np.eye(t.shape[1]), atol=1e-12)
    np.testing.assert_allclose(l2 @ t, target_l * (target_l + 1) * t, atol=1e-11)


@pytest.mark.parametrize("target_l", [0, 2])
def test_sparse_target_isometry_cross_checks_dense_small_n(target_l):
    basis = DeterminantBasis.with_two_m(SphereSpec(4), 0)
    dense = target_irrep_isometry(basis, target_l)
    sparse_target = target_irrep_isometry_sparse(basis, target_l)

    np.testing.assert_allclose(
        sparse_target @ sparse_target.conj().T,
        dense @ dense.conj().T,
        atol=1e-11,
    )


def test_sparse_target_isometry_is_bounded_and_avoids_dense_eigh_n6(monkeypatch):
    basis = DeterminantBasis.with_two_m(SphereSpec(6), 0)
    original_eigh = np.linalg.eigh

    def reject_full_dimension_eigh(matrix, *args, **kwargs):
        if matrix.shape == (basis.dimension, basis.dimension):
            raise AssertionError("sparse target path must not call dense D by D eigh")
        return original_eigh(matrix, *args, **kwargs)

    monkeypatch.setattr(
        np.linalg,
        "eigh",
        reject_full_dimension_eigh,
    )
    monkeypatch.setattr(
        "challenge15.angular._canonical_projector_basis",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("sparse path must not construct a dense projector")
        ),
    )
    target, diagnostics = target_irrep_isometry_sparse(
        basis, 2, return_diagnostics=True
    )
    expected_rank = DeterminantBasis.with_two_m(
        basis.spec, 4
    ).dimension - DeterminantBasis.with_two_m(basis.spec, 6).dimension
    l2 = angular_operators(basis, return_l2_only=True)

    assert target.shape == (basis.dimension, expected_rank)
    assert diagnostics["gram_defect"] <= SPARSE_GRAM_TOLERANCE == 1e-12
    assert (
        diagnostics["l2_target_residual"]
        <= SPARSE_L2_RESIDUAL_TOLERANCE
        == 1e-11
    )
    assert (
        diagnostics["ladder_intertwining_residual"]
        <= SPARSE_LADDER_TOLERANCE
        == 1e-11
    )
    assert diagnostics["dense_projector_allocated"] is False
    assert np.linalg.norm(l2 @ target - 6.0 * target) / np.linalg.norm(target) <= 1e-11


def test_thin_canonicalization_is_invariant_under_right_unitary_mixing():
    rng = np.random.default_rng(812)
    thin, _ = np.linalg.qr(
        rng.normal(size=(257, 9)) + 1j * rng.normal(size=(257, 9)),
        mode="reduced",
    )
    mixing, _ = np.linalg.qr(
        rng.normal(size=(9, 9)) + 1j * rng.normal(size=(9, 9))
    )

    canonical, diagnostics = _canonical_thin_subspace_basis(thin)
    mixed, mixed_diagnostics = _canonical_thin_subspace_basis(thin @ mixing)

    np.testing.assert_allclose(mixed, canonical, atol=2e-12, rtol=0.0)
    assert mixed_diagnostics["row_pivots"] == diagnostics["row_pivots"]


@pytest.mark.parametrize("particles", [7, 8])
def test_thin_canonicalization_has_linear_storage_for_production_dimensions(
    particles,
):
    basis = DeterminantBasis.with_two_m(SphereSpec(particles), 0)
    rank = 13
    rng = np.random.default_rng(particles)
    thin, _ = np.linalg.qr(
        rng.normal(size=(basis.dimension, rank)),
        mode="reduced",
    )

    canonical, diagnostics = _canonical_thin_subspace_basis(thin)

    assert canonical.shape == (basis.dimension, rank)
    assert diagnostics["dense_projector_allocated"] is False
    assert diagnostics["workspace_elements_upper_bound"] <= (
        basis.dimension * rank + 4 * rank * rank
    )
    assert diagnostics["workspace_elements_upper_bound"] < basis.dimension**2


@pytest.mark.parametrize(
    ("target_l", "message"),
    [
        (True, "target_l must be a Python integer"),
        (-1, "target_l must be nonnegative"),
        (0.5, "target_l must be a Python integer"),
        (19, "target_l must satisfy 0 <= target_l <= particles \\* two_q / 2"),
    ],
)
def test_target_l_apis_reject_invalid_values(target_l, message):
    basis = DeterminantBasis.with_two_m(SphereSpec(4), 0)
    with pytest.raises(ValueError, match=message):
        target_irrep_isometry(basis, target_l)
    with pytest.raises(ValueError, match=message):
        verify_ladder_multiplet(basis, target_l=target_l, isometry=np.ones((basis.dimension, 1)))


@pytest.mark.parametrize("particles", [4, 6])
def test_fixed_m_dimension_identities_hold(particles):
    spec = SphereSpec(particles)
    multiplicities = []
    reconstructed = 0
    max_two_m = spec.particles * spec.two_q
    for target_l in range(spec.l_max + 1):
        dim_ml = DeterminantBasis.with_two_m(spec, 2 * target_l).dimension
        next_two_m = 2 * (target_l + 1)
        dim_next = (
            DeterminantBasis.with_two_m(spec, next_two_m).dimension
            if next_two_m <= max_two_m
            else 0
        )
        multiplicity = dim_ml - dim_next
        assert multiplicity >= 0
        multiplicities.append(multiplicity)
        reconstructed += (2 * target_l + 1) * multiplicity
    assert reconstructed == spec.full_dimension
    assert any(multiplicity > 0 for multiplicity in multiplicities)


@pytest.mark.slow
@pytest.mark.parametrize("particles", [7, 8])
def test_dimension_identities_smoke_large_systems(particles):
    spec = SphereSpec(particles)
    reconstructed = 0
    max_two_m = spec.particles * spec.two_q
    for target_l in range(spec.l_max + 1):
        dim_ml = DeterminantBasis.with_two_m(spec, 2 * target_l).dimension
        next_two_m = 2 * (target_l + 1)
        dim_next = (
            DeterminantBasis.with_two_m(spec, next_two_m).dimension
            if next_two_m <= max_two_m
            else 0
        )
        reconstructed += (2 * target_l + 1) * (dim_ml - dim_next)
    assert reconstructed == spec.full_dimension


@pytest.mark.parametrize("particles", [4, 6])
def test_verify_l2_ladder_reconstructs_all_five_members(particles):
    basis = DeterminantBasis.with_two_m(SphereSpec(particles), 0)
    isometry = target_irrep_isometry(basis, 2)
    report = verify_ladder_multiplet(basis, target_l=2, isometry=isometry)

    assert report["sector_two_m"] == (-4, -2, 0, 2, 4)
    assert isclose(report["max_norm_error"], 0.0, abs_tol=1e-11)
    assert isclose(report["max_orthogonality_error"], 0.0, abs_tol=1e-11)
    assert report["max_ladder_error"] <= 1e-11
    assert isometry.shape[1] > 0
    assert all(vectors.shape[1] > 0 for vectors in report["vectors"].values())
    assert all(vectors.shape[1] == isometry.shape[1] for vectors in report["vectors"].values())


def test_canonical_projector_basis_is_invariant_under_unitary_mixing():
    basis = DeterminantBasis.with_two_m(SphereSpec(6), 0)
    l2 = angular_operators(basis, return_l2_only=True)
    eigenvalues, eigenvectors = np.linalg.eigh(l2)
    eigenspace = eigenvectors[:, np.abs(eigenvalues - 6.0) <= 1e-10]
    rng = np.random.default_rng(1234)
    raw_unitary = rng.normal(size=(eigenspace.shape[1], eigenspace.shape[1])) + 1j * rng.normal(
        size=(eigenspace.shape[1], eigenspace.shape[1])
    )
    mixed = eigenspace @ np.linalg.qr(raw_unitary)[0]
    canonical = target_irrep_isometry(basis, 2)
    reconstructed = _canonical_projector_basis(mixed @ mixed.conj().T, rank=mixed.shape[1])
    direct = _canonical_projector_basis(eigenspace @ eigenspace.conj().T, rank=eigenspace.shape[1])

    np.testing.assert_allclose(reconstructed.conj().T @ reconstructed, np.eye(reconstructed.shape[1]), atol=1e-12)
    np.testing.assert_allclose(reconstructed, direct, atol=1e-12)
    thin = _canonical_thin_subspace_basis(eigenspace)[0]
    np.testing.assert_allclose(thin, canonical, atol=1e-12)


def test_ladder_error_detects_orthogonal_leakage():
    reference_vectors = np.array(
        [
            [1.0, 0.0],
            [0.0, 1.0],
            [0.0, 0.0],
        ],
        dtype=np.complex128,
    )
    ladder_image = sqrt(6.0) * reference_vectors
    ladder_image[:, 0] += np.array([0.0, 0.0, 1e-3], dtype=np.complex128)

    assert _ladder_coefficient_error(reference_vectors, ladder_image, sqrt(6.0)) > 1e-6
