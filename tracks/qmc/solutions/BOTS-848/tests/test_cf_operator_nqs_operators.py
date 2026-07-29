from __future__ import annotations

import ast
import itertools
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from benchmark_v0.fock_ed import apply_annihilation, apply_creation
from scalable_v1.routes.cf_operator_nqs.projected_density import (
    projected_density_tensor,
)
from scalable_v1.routes.cf_operator_nqs.scalar_operators import (
    build_scalar_operator,
    connected_scalar_action,
)


SOLUTION_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_MODULES = (
    SOLUTION_ROOT
    / "scalable_v1"
    / "routes"
    / "cf_operator_nqs"
    / "projected_density.py",
    SOLUTION_ROOT
    / "scalable_v1"
    / "routes"
    / "cf_operator_nqs"
    / "scalar_operators.py",
)


def _fixed_n_basis(n_electrons: int, two_q: int) -> tuple[int, ...]:
    return tuple(
        sum(1 << orbital for orbital in occupied)
        for occupied in itertools.combinations(range(two_q + 1), n_electrons)
    )


def _second_quantize(one_body: np.ndarray, basis: tuple[int, ...]) -> np.ndarray:
    index = {config: row for row, config in enumerate(basis)}
    matrix = np.zeros((len(basis), len(basis)), dtype=np.complex128)
    for column, source in enumerate(basis):
        for annihilated_orbital in range(one_body.shape[1]):
            annihilated = apply_annihilation(source, annihilated_orbital)
            if annihilated is None:
                continue
            intermediate, sign_1 = annihilated
            for created_orbital in range(one_body.shape[0]):
                coefficient = one_body[created_orbital, annihilated_orbital]
                if coefficient == 0.0:
                    continue
                created = apply_creation(intermediate, created_orbital)
                if created is None:
                    continue
                target, sign_2 = created
                matrix[index[target], column] += coefficient * sign_1 * sign_2
    return matrix


def _many_body_l2(two_q: int, basis: tuple[int, ...]) -> np.ndarray:
    n_orbitals = two_q + 1
    l_plus = np.zeros((n_orbitals, n_orbitals), dtype=np.complex128)
    for orbital in range(two_q):
        l_plus[orbital + 1, orbital] = math.sqrt(
            (two_q - orbital) * (orbital + 1)
        )
    l_minus = l_plus.T.conj()
    l_z = np.diag(
        np.arange(n_orbitals, dtype=float) - 0.5 * two_q
    ).astype(np.complex128)
    total_plus = _second_quantize(l_plus, basis)
    total_minus = _second_quantize(l_minus, basis)
    total_z = _second_quantize(l_z, basis)
    return (
        total_z @ total_z
        + 0.5 * (total_plus @ total_minus + total_minus @ total_plus)
    )


@pytest.mark.parametrize("ell", range(4))
def test_projected_density_tensors_have_hermitian_condon_shortley_phases(
    ell: int,
) -> None:
    tensors = {
        m: projected_density_tensor(two_q=3, ell=ell, m=m)
        for m in range(-ell, ell + 1)
    }

    for m, tensor in tensors.items():
        np.testing.assert_allclose(
            tensor.T.conj(), (-1) ** m * tensors[-m], rtol=0.0, atol=2.0e-15
        )

    if ell == 0:
        np.testing.assert_array_equal(tensors[0], np.eye(4))


@pytest.mark.parametrize("ell", range(1, 4))
def test_projected_density_tensors_obey_rank_ell_ladder_identity(ell: int) -> None:
    l_plus = np.zeros((4, 4), dtype=np.complex128)
    for orbital in range(3):
        l_plus[orbital + 1, orbital] = math.sqrt((3 - orbital) * (orbital + 1))

    for m in range(-ell, ell):
        tensor = projected_density_tensor(two_q=3, ell=ell, m=m)
        raised = projected_density_tensor(two_q=3, ell=ell, m=m + 1)
        commutator = l_plus @ tensor - tensor @ l_plus
        expected = math.sqrt((ell - m) * (ell + m + 1)) * raised
        residual = np.linalg.norm(commutator - expected)
        scale = max(np.linalg.norm(expected), np.finfo(float).tiny)
        assert residual / scale < 1.0e-13


def test_scalar_operator_is_the_exact_signed_density_contraction() -> None:
    two_q = 3
    ell = 2
    basis = _fixed_n_basis(n_electrons=2, two_q=two_q)
    densities = {
        m: _second_quantize(
            projected_density_tensor(two_q=two_q, ell=ell, m=m), basis
        )
        for m in range(-ell, ell + 1)
    }
    expected = sum(
        ((-1) ** m) * densities[m] @ densities[-m]
        for m in range(-ell, ell + 1)
    )

    operator = build_scalar_operator(two_q=two_q, ell=ell)

    np.testing.assert_allclose(operator.matrix, expected, rtol=2.0e-15, atol=2.0e-15)
    assert np.linalg.norm(
        operator.matrix
        - np.trace(operator.matrix) / len(basis) * np.eye(len(basis))
    ) > 1.0


@pytest.mark.parametrize("ell", (1, 2, 3))
def test_scalar_operator_is_hermitian_and_commutes_with_total_l2(ell: int) -> None:
    basis = _fixed_n_basis(n_electrons=2, two_q=3)
    l2 = _many_body_l2(two_q=3, basis=basis)
    operator = build_scalar_operator(two_q=3, ell=ell)

    commutator = operator.matrix @ l2 - l2 @ operator.matrix
    commutator_residual = np.linalg.norm(commutator) / np.linalg.norm(
        operator.matrix
    )
    hermitian_residual = np.linalg.norm(
        operator.matrix - operator.matrix.T.conj()
    ) / np.linalg.norm(operator.matrix)

    assert operator.strict_lll
    assert operator.commutes_with_l2
    assert operator.depth == 1
    assert operator.ell == ell
    assert commutator_residual < 1.0e-12
    assert hermitian_residual < 1.0e-12


class _BitsetState:
    label = "bitset-fixture"
    l = 0
    m = 0

    def sample(self, n_samples: int, seed: int) -> Any:
        raise NotImplementedError

    def logpsi(self, config_batch: Any) -> np.ndarray:
        raise NotImplementedError

    def local_energy(self, config_batch: Any) -> np.ndarray:
        raise NotImplementedError

    def local_l2(self, config_batch: Any) -> np.ndarray:
        raise NotImplementedError


def test_bitset_connected_action_matches_exact_fixture_matrix() -> None:
    basis = _fixed_n_basis(n_electrons=2, two_q=3)
    operator = build_scalar_operator(two_q=3, ell=2)

    connected, weights = operator.connected_action(
        _BitsetState(), np.asarray(basis, dtype=np.int64)
    )

    assert connected.ndim == weights.ndim == 2
    assert connected.shape == weights.shape
    reconstructed = np.zeros_like(operator.matrix)
    index = {config: row for row, config in enumerate(basis)}
    for column in range(len(basis)):
        for target, weight in zip(connected[column], weights[column], strict=True):
            if weight != 0.0:
                reconstructed[index[int(target)], column] += weight
    np.testing.assert_allclose(reconstructed, operator.matrix, rtol=2.0e-15, atol=2.0e-15)


def test_connected_action_has_fixed_lll_polynomial_neighborhood_bound() -> None:
    two_q = 7
    ell = 3
    depth = 2
    source = sum(1 << orbital for orbital in (0, 5))

    connected, weights = connected_scalar_action(
        two_q=two_q, ell=ell, depth=depth, configs=source
    )

    branching_bound = ((2 * ell + 1) * source.bit_count() ** 2) ** depth
    nonzero = weights != 0.0
    assert connected.ndim == weights.ndim == 1
    assert np.count_nonzero(nonzero) <= branching_bound
    assert all(int(config).bit_count() == source.bit_count() for config in connected[nonzero])
    assert all(int(config) >> (two_q + 1) == 0 for config in connected[nonzero])


class _HookState(_BitsetState):
    def __init__(self) -> None:
        self.received: dict[str, Any] | None = None

    def connected_scalar_action(self, **kwargs: Any) -> tuple[object, np.ndarray]:
        self.received = kwargs
        return "coordinate-neighborhood", np.asarray([1.0 + 2.0j])


def test_scalar_operator_delegates_representation_generic_state_hook() -> None:
    state = _HookState()
    configs = np.zeros((2, 2, 2), dtype=np.complex128)
    operator = build_scalar_operator(two_q=3, ell=2, depth=2)

    connected, weights = operator.connected_action(state, configs)

    assert connected == "coordinate-neighborhood"
    np.testing.assert_array_equal(weights, np.asarray([1.0 + 2.0j]))
    assert state.received == {
        "two_q": 3,
        "ell": 2,
        "depth": 2,
        "configs": configs,
    }


def test_spinor_configs_require_a_projected_density_state_hook() -> None:
    configs = np.zeros((2, 2, 2), dtype=np.complex128)
    operator = build_scalar_operator(two_q=3, ell=2)

    with pytest.raises(TypeError, match="state hook"):
        operator.connected_action(_BitsetState(), configs)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"two_q": 0, "ell": 0}, "two_q"),
        ({"two_q": 3.0, "ell": 0}, "two_q"),
        ({"two_q": 3, "ell": -1}, "ell"),
        ({"two_q": 3, "ell": 4}, "ell"),
        ({"two_q": 3, "ell": 2.0}, "ell"),
        ({"two_q": 3, "ell": 2, "depth": 0}, "depth"),
        ({"two_q": 3, "ell": 2, "depth": 1.0}, "depth"),
    ],
)
def test_scalar_operator_rejects_invalid_construction_inputs(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        build_scalar_operator(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("m", (-3, 3, 0.5))
def test_projected_density_rejects_invalid_component(m: float) -> None:
    with pytest.raises((TypeError, ValueError), match="m"):
        projected_density_tensor(two_q=3, ell=2, m=m)  # type: ignore[arg-type]


def test_runtime_operator_modules_do_not_import_ed_implementations() -> None:
    forbidden = {"benchmark_v0.fock_ed", "benchmark_v0.ed_oracle"}
    imported: set[str] = set()
    for module_path in RUNTIME_MODULES:
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)

    assert imported.isdisjoint(forbidden)
