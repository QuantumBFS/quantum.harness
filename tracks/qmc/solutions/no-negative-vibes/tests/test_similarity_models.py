from __future__ import annotations

from itertools import combinations, product

import numpy as np
from scipy.linalg import expm

from oracle.similarity_models import (
    build_star_to_chain_impurity_mwe,
    determinant_history_weight,
    pseudo_hermitian_orbit,
    similarity_history,
    stark_similarity_model,
    star_to_chain_hirsch_branch,
    star_to_chain_hirsch_history,
    tensor_square_similarity_history,
)


def _all_minors(matrix: np.ndarray) -> tuple[float, ...]:
    size = matrix.shape[0]
    return tuple(
        float(np.linalg.det(matrix[np.ix_(rows, columns)]))
        for order in range(1, size + 1)
        for rows in combinations(range(size), order)
        for columns in combinations(range(size), order)
    )


def test_fixed_similarity_preserves_every_history_weight() -> None:
    factors = (
        np.asarray([[1.2, 0.3], [-0.4, 0.9]]),
        np.asarray([[0.8, -0.7], [0.2, 1.4]]),
        np.asarray([[1.1, 0.5], [0.6, 0.7]]),
    )
    similarity = np.asarray([[1.0, 0.4], [-0.2, 1.3]])
    history = similarity_history(factors, similarity)

    assert history.conjugacy_residual < 1e-12
    assert abs(history.original_weight - history.transformed_weight) < 1e-12
    assert (
        abs(
            determinant_history_weight(factors)
            - history.original_weight
        )
        < 1e-12
    )


def test_pseudo_hermitian_metric_is_positive_and_exact() -> None:
    partner = np.asarray(
        [
            [0.2, 1.0, 0.0],
            [1.0, -0.3, 0.7],
            [0.0, 0.7, 0.9],
        ]
    )
    similarity = expm(
        np.asarray(
            [
                [0.0, 0.5, -0.1],
                [0.0, 0.0, 0.3],
                [0.0, 0.0, 0.0],
            ]
        )
    )
    orbit = pseudo_hermitian_orbit(partner, similarity)

    assert orbit.similarity_residual < 1e-12
    assert orbit.pseudo_hermiticity_residual < 1e-12
    assert np.min(np.linalg.eigvalsh(orbit.metric)) > 0.0
    assert np.linalg.norm(
        orbit.nonhermitian_hamiltonian
        - orbit.nonhermitian_hamiltonian.conj().T
    ) > 0.1
    assert np.allclose(
        np.sort(np.linalg.eigvalsh(partner)),
        np.sort(np.linalg.eigvals(orbit.nonhermitian_hamiltonian).real),
        atol=1e-12,
    )


def test_arbitrary_lifted_similarity_preserves_tensor_square_positivity() -> None:
    bases = (
        expm(np.asarray([[0.2, 0.4], [0.4, -0.1]])),
        expm(np.asarray([[-0.3, 0.6], [0.6, 0.5]])),
        expm(np.asarray([[0.7, -0.2], [-0.2, -0.4]])),
    )
    lifted_similarity = expm(
        np.asarray(
            [
                [0.0, 0.3, 0.0, -0.2],
                [0.0, 0.0, 0.4, 0.0],
                [0.0, 0.0, 0.0, 0.5],
                [0.0, 0.0, 0.0, 0.0],
            ]
        )
    )
    history = tensor_square_similarity_history(
        bases,
        lifted_similarity,
    )

    assert history.conjugacy_residual < 1e-11
    assert history.original_weight.real > 0.0
    assert abs(history.original_weight.imag) < 1e-12
    assert abs(history.original_weight - history.transformed_weight) < 1e-10


def test_nilpotent_similarity_gives_exact_local_one_way_chain() -> None:
    model = stark_similarity_model(
        dimension=6,
        level_spacing=1.7,
        shear=0.8,
    )
    hamiltonian = model.orbit.nonhermitian_hamiltonian

    assert np.allclose(
        hamiltonian,
        model.expected_local_hamiltonian,
        atol=1e-12,
    )
    assert model.orbit.pseudo_hermiticity_residual < 1e-11
    assert np.min(np.linalg.eigvalsh(model.orbit.metric)) > 0.0
    assert np.count_nonzero(np.abs(hamiltonian) > 1e-12) == 10
    assert np.count_nonzero(np.abs(model.orbit.metric) > 1e-12) > 30


def test_dense_fourier_partner_is_a_nonunique_description() -> None:
    direct = stark_similarity_model(
        dimension=7,
        level_spacing=1.2,
        shear=0.6,
    )
    fourier = stark_similarity_model(
        dimension=7,
        level_spacing=1.2,
        shear=0.6,
        fourier_partner=True,
    )

    assert np.allclose(
        direct.orbit.nonhermitian_hamiltonian,
        fourier.orbit.nonhermitian_hamiltonian,
        atol=1e-12,
    )
    assert np.allclose(direct.orbit.metric, fourier.orbit.metric, atol=1e-12)
    assert np.count_nonzero(
        np.abs(fourier.orbit.hermitian_partner) > 1e-12
    ) == 49
    assert np.count_nonzero(
        np.abs(direct.orbit.hermitian_partner) > 1e-12
    ) == 6


def test_fixed_star_to_chain_mwe_is_dense_and_preserves_impurity() -> None:
    model = build_star_to_chain_impurity_mwe()
    transform = model.chain_to_star
    expected_star = np.asarray(
        [
            [0.0, -0.5773502692, -0.5773502692, -0.5773502692],
            [-0.5773502692, -0.1662740910, -0.0666666667, -0.3468551350],
            [-0.5773502692, -0.0666666667, 1.8329407570, -0.3864781957],
            [-0.5773502692, -0.3468551350, -0.3864781957, 1.1333333333],
        ]
    )

    assert np.allclose(transform.T @ transform, np.eye(4), atol=1e-12)
    assert np.allclose(transform[:, 0], [1.0, 0.0, 0.0, 0.0])
    assert np.allclose(
        transform @ model.impurity_projector @ transform.T,
        model.impurity_projector,
        atol=1e-12,
    )
    assert np.allclose(model.star_hamiltonian, expected_star, atol=1e-9)
    assert np.allclose(
        transform.T @ model.star_hamiltonian @ transform,
        model.chain_hamiltonian,
        atol=1e-12,
    )
    assert np.count_nonzero(np.abs(model.star_hamiltonian) > 1e-12) == 15
    assert np.all(
        np.diag(model.chain_hamiltonian, k=1) < 0.0
    )


def test_hirsch_branches_are_tn_in_chain_basis() -> None:
    model = build_star_to_chain_impurity_mwe()

    assert np.isclose(
        np.cosh(model.hirsch_lambda),
        np.exp(model.time_step * model.interaction / 2.0),
        atol=1e-14,
    )
    for spin, field in product((-1, 1), repeat=2):
        chain_branch = star_to_chain_hirsch_branch(
            model,
            field=field,
            spin=spin,
        )
        star_branch = star_to_chain_hirsch_branch(
            model,
            field=field,
            spin=spin,
            basis="star",
        )

        assert min(_all_minors(chain_branch)) > -1e-12
        assert np.allclose(
            star_branch,
            model.chain_to_star @ chain_branch @ model.chain_to_star.T,
            atol=1e-12,
        )


def test_all_short_hirsch_histories_remain_tn_and_basis_invariant() -> None:
    model = build_star_to_chain_impurity_mwe()

    for depth in range(1, 5):
        for fields in product((-1, 1), repeat=depth):
            for spin in (-1, 1):
                chain_product = np.eye(4)
                for field in fields:
                    chain_product @= star_to_chain_hirsch_branch(
                        model,
                        field=field,
                        spin=spin,
                    )
                history = star_to_chain_hirsch_history(
                    model,
                    fields,
                    spin=spin,
                )

                assert min(_all_minors(chain_product)) > -2e-10
                assert history.original_weight.real >= 1.0 - 2e-10
                assert abs(history.original_weight.imag) < 1e-12
                assert history.conjugacy_residual < 1e-11
                assert (
                    abs(
                        history.original_weight
                        - history.transformed_weight
                    )
                    < 1e-10
                )
