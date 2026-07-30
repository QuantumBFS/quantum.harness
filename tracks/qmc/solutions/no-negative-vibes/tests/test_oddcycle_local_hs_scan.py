import numpy as np
import sympy as sp
from scipy import optimize

from oracle.oddcycle_local_hs_scan import (
    forbidden_label_indices,
    locality_specs,
    scan_positive_matrix_kernel,
    scan_target_cone,
)
from oracle.oddcycle_local_targets import TargetPoint, first_target_library
from oracle.oddcycle_word_operator import (
    NormalOrderedLabel,
    WordPairColumn,
    normal_ordered_coordinates,
    normal_ordered_labels,
)


def test_ring_edge_locality_does_not_accept_a_three_site_support():
    spec = locality_specs()["ring-edge"]
    labels = normal_ordered_labels(5)
    three_site = NormalOrderedLabel(create=(0, 2), annihilate=(0, 1))
    assert three_site.support == frozenset({0, 1, 2})
    forbidden = {labels[index] for index in forbidden_label_indices(labels, spec)}
    assert three_site in forbidden


def test_ring_arc3_accepts_only_one_contiguous_three_site_arc():
    spec = locality_specs()["ring-arc3"]
    assert spec.allows_support(frozenset({4, 0, 1}))
    assert not spec.allows_support(frozenset({0, 2, 4}))


def test_positive_kernel_scan_distinguishes_feasible_and_infeasible():
    feasible = scan_positive_matrix_kernel(
        np.array([[1.0, -1.0], [0.0, 0.0]])
    )
    assert feasible.status == "numerical-survivor"
    assert np.all(feasible.weights > 0)
    assert np.max(np.abs(np.array([[1.0, -1.0]]) @ feasible.weights)) < 1e-9

    impossible = scan_positive_matrix_kernel(np.array([[1.0, 2.0]]))
    assert impossible.status == "numerically-infeasible"


def _synthetic_column(operator: sp.MatrixBase) -> WordPairColumn:
    return WordPairColumn(
        word=(0,),
        transpose_word=(1,),
        matrix_orbit_key=tuple((0, 1) for _ in range(25)),
        fock_pair=sp.ImmutableSparseMatrix(operator),
        coordinates=normal_ordered_coordinates(operator, 5),
    )


def _target(family: str) -> TargetPoint:
    return next(
        target
        for target in first_target_library()
        if target.family == family
    )


def test_target_cone_scan_matches_exactly_modulo_the_scalar():
    target = _target("ring-frustrated-t-v")
    scalar_shifted_negative_target = sp.ImmutableSparseMatrix(
        -target.hamiltonian + 7 * sp.eye(32)
    )

    result = scan_target_cone(
        (_synthetic_column(scalar_shifted_negative_target),),
        target,
    )

    assert result.status == "numerical-survivor"
    assert result.target_id == target.target_id
    assert result.target_parameters == target.parameters
    assert result.residual is not None and result.residual < 1.0e-9
    assert result.active_indices == (0,)
    assert result.weights is not None
    assert np.allclose(result.weights, [1.0])
    assert result.target_diagonal_gauge_frustrated is True


def test_target_cone_scan_distinguishes_infeasible_and_solver_failure(
    monkeypatch,
):
    target = _target("path-t-v")
    scalar_column = _synthetic_column(sp.eye(32))

    impossible = scan_target_cone((scalar_column,), target)
    assert impossible.status == "numerically-infeasible"
    assert impossible.weights is None
    assert impossible.active_indices == ()

    monkeypatch.setattr(
        "oracle.oddcycle_local_hs_scan.optimize.linprog",
        lambda *args, **kwargs: optimize.OptimizeResult(
            status=4,
            message="synthetic solver failure",
            nit=0,
        ),
    )
    inconclusive = scan_target_cone((scalar_column,), target)
    assert inconclusive.status == "solver-inconclusive"
    assert inconclusive.weights is None
    assert inconclusive.solver_message == "synthetic solver failure"
