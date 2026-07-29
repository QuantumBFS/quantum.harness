from __future__ import annotations

import ast
import itertools
import math
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from benchmark_v0.fock_ed import apply_annihilation, apply_creation
from scalable_v1.routes.cf_operator_nqs import projected_density
from scalable_v1.routes.cf_operator_nqs.projected_density import (
    projected_density_tensor,
)
from scalable_v1.routes.cf_operator_nqs import scalar_operators
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


def _connected_matrix(operator: object, basis: tuple[int, ...]) -> np.ndarray:
    connected, weights = operator.connected_action(  # type: ignore[attr-defined]
        _BitsetState(), np.asarray(basis, dtype=np.int64)
    )
    matrix = np.zeros((len(basis), len(basis)), dtype=np.complex128)
    index = {config: row for row, config in enumerate(basis)}
    for column in range(len(basis)):
        for target, weight in zip(connected[column], weights[column], strict=True):
            if weight != 0.0:
                matrix[index[int(target)], column] += weight
    return matrix


def _exact_racah_density_element(
    *, two_q: int, ell: int, m: int, source: int
) -> float:
    """Independent exact-rational Racah reference for one tensor element."""

    j = 0.5 * two_q
    source_m = source - j
    target_m = source_m + m

    def factorial(value: float) -> int:
        integer = round(value)
        assert math.isclose(value, integer, rel_tol=0.0, abs_tol=1.0e-12)
        return math.factorial(integer)

    prefactor_squared = Fraction(
        round(2.0 * j + 1.0)
        * factorial(j + j - ell)
        * factorial(ell)
        * factorial(ell)
        * factorial(j + target_m)
        * factorial(j - target_m)
        * factorial(j - source_m)
        * factorial(j + source_m)
        * factorial(ell - m)
        * factorial(ell + m),
        factorial(j + ell + j + 1.0),
    )
    k_min = max(0, round(ell - j - source_m), round(j + m - j))
    k_max = min(round(ell), round(j - source_m), round(ell + m))
    racah_sum = sum(
        (
            Fraction(
                (-1) ** k,
                factorial(float(k))
                * factorial(ell - k)
                * factorial(j - source_m - k)
                * factorial(ell + m - k)
                * factorial(source_m - ell + j + k)
                * factorial(-m + k),
            )
            for k in range(k_min, k_max + 1)
        ),
        Fraction(0),
    )
    signed_square = prefactor_squared * racah_sum * racah_sum
    coefficient = math.sqrt(float(signed_square))
    coefficient = math.copysign(coefficient, racah_sum.numerator)
    return math.sqrt(2 * ell + 1) * coefficient


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


@pytest.mark.parametrize(("two_q", "ell"), ((33, 2), (33, 4), (127, 4)))
def test_projected_density_is_stable_at_protocol_and_larger_flux(
    two_q: int, ell: int
) -> None:
    n_orbitals = two_q + 1
    l_plus = np.zeros((n_orbitals, n_orbitals), dtype=np.complex128)
    for orbital in range(two_q):
        l_plus[orbital + 1, orbital] = math.sqrt(
            (two_q - orbital) * (orbital + 1)
        )
    tensors = {
        m: projected_density_tensor(two_q=two_q, ell=ell, m=m)
        for m in range(-ell, ell + 1)
    }

    assert all(np.all(np.isfinite(tensor)) for tensor in tensors.values())
    for m, tensor in tensors.items():
        scale = max(np.linalg.norm(tensor), np.finfo(float).tiny)
        hermitian_residual = np.linalg.norm(
            tensor.T.conj() - (-1) ** m * tensors[-m]
        ) / scale
        assert hermitian_residual < 1.0e-12
        if m < ell:
            expected = math.sqrt((ell - m) * (ell + m + 1)) * tensors[m + 1]
            ladder_residual = np.linalg.norm(
                l_plus @ tensor - tensor @ l_plus - expected
            ) / max(np.linalg.norm(expected), np.finfo(float).tiny)
            assert ladder_residual < 1.0e-12


def test_projected_density_exports_and_enforces_verified_flux_cap() -> None:
    assert projected_density.MAX_PROJECTED_DENSITY_TWO_Q == 127

    with pytest.raises(ValueError, match=r"two_q.*127"):
        projected_density_tensor(two_q=128, ell=2, m=0)


def test_projected_density_cap_has_high_cancellation_reference_and_covariance() -> None:
    two_q = 127
    ell = 63
    source = 63
    tensor_zero = projected_density_tensor(two_q=two_q, ell=ell, m=0)
    tensor_plus = projected_density_tensor(two_q=two_q, ell=ell, m=1)
    tensor_minus = projected_density_tensor(two_q=two_q, ell=ell, m=-1)
    expected_element = _exact_racah_density_element(
        two_q=two_q, ell=ell, m=0, source=source
    )

    np.testing.assert_allclose(
        tensor_zero[source, source], expected_element, rtol=5.0e-14, atol=1.0e-15
    )
    np.testing.assert_allclose(
        tensor_plus.T.conj(), -tensor_minus, rtol=5.0e-14, atol=1.0e-14
    )
    l_plus = np.zeros((two_q + 1, two_q + 1), dtype=np.complex128)
    for orbital in range(two_q):
        l_plus[orbital + 1, orbital] = math.sqrt(
            (two_q - orbital) * (orbital + 1)
        )
    expected_raised = math.sqrt(ell * (ell + 1)) * tensor_plus
    ladder_residual = np.linalg.norm(
        l_plus @ tensor_zero - tensor_zero @ l_plus - expected_raised
    ) / np.linalg.norm(expected_raised)
    assert ladder_residual < 1.0e-12


def test_numpy_integral_inputs_are_accepted_consistently() -> None:
    tensor = projected_density_tensor(
        two_q=np.int64(33), ell=np.int32(4), m=np.int64(0)
    )
    operator = build_scalar_operator(
        two_q=np.int64(21), ell=np.int32(4), depth=np.int64(2)
    )
    connected, weights = connected_scalar_action(
        two_q=np.int64(21),
        ell=np.int32(4),
        depth=np.int64(1),
        configs=np.int64((1 << 0) | (1 << 20)),
    )

    assert tensor.shape == (34, 34)
    assert (operator.two_q, operator.ell, operator.depth) == (21, 4, 2)
    assert connected.dtype == np.int64
    assert weights.dtype == np.complex128


def test_bitset_scalar_backend_rejects_two_q_above_signed_int64_limit() -> None:
    with pytest.raises(ValueError, match=r"two_q.*62"):
        connected_scalar_action(two_q=63, ell=4, configs=1)


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
    matrix = _connected_matrix(operator, basis)

    np.testing.assert_allclose(matrix, expected, rtol=2.0e-15, atol=2.0e-15)
    assert np.linalg.norm(
        matrix - np.trace(matrix) / len(basis) * np.eye(len(basis))
    ) > 1.0


@pytest.mark.parametrize("ell", (1, 2, 3))
def test_scalar_operator_is_hermitian_and_commutes_with_total_l2(ell: int) -> None:
    basis = _fixed_n_basis(n_electrons=2, two_q=3)
    l2 = _many_body_l2(two_q=3, basis=basis)
    operator = build_scalar_operator(two_q=3, ell=ell)
    matrix = _connected_matrix(operator, basis)

    commutator = matrix @ l2 - l2 @ matrix
    commutator_residual = np.linalg.norm(commutator) / np.linalg.norm(matrix)
    hermitian_residual = np.linalg.norm(matrix - matrix.T.conj()) / np.linalg.norm(
        matrix
    )

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


def test_build_scalar_operator_does_not_construct_or_retain_fixture_matrix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_fixture(*args: object, **kwargs: object) -> object:
        pytest.fail("production constructor called an exact-basis fixture helper")

    for helper_name in (
        "_fixture_basis",
        "_fixture_l2",
        "_fixture_scalar_matrix",
        "_second_quantized_fixture",
    ):
        monkeypatch.setattr(
            scalar_operators, helper_name, forbidden_fixture, raising=False
        )

    operator = build_scalar_operator(two_q=21, ell=4)

    assert not hasattr(operator, "matrix")
    assert vars(operator) == {
        "two_q": 21,
        "depth": 1,
        "ell": 4,
        "strict_lll": True,
        "commutes_with_l2": True,
    }


def test_bitset_connected_action_matches_exact_fixture_matrix() -> None:
    basis = _fixed_n_basis(n_electrons=2, two_q=3)
    operator = build_scalar_operator(two_q=3, ell=2)

    connected, weights = operator.connected_action(
        _BitsetState(), np.asarray(basis, dtype=np.int64)
    )

    assert connected.ndim == weights.ndim == 2
    assert connected.shape == weights.shape
    reconstructed = np.zeros((len(basis), len(basis)), dtype=np.complex128)
    index = {config: row for row, config in enumerate(basis)}
    for column in range(len(basis)):
        for target, weight in zip(connected[column], weights[column], strict=True):
            if weight != 0.0:
                reconstructed[index[int(target)], column] += weight
    densities = {
        m: _second_quantize(
            projected_density_tensor(two_q=3, ell=2, m=m), basis
        )
        for m in range(-2, 3)
    }
    expected = sum(
        ((-1) ** m) * densities[m] @ densities[-m] for m in range(-2, 3)
    )
    np.testing.assert_allclose(
        reconstructed,
        expected,
        rtol=2.0e-15,
        atol=2.0e-15,
    )


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

    def connected_scalar_action(self, **kwargs: Any) -> tuple[np.ndarray, np.ndarray]:
        self.received = kwargs
        configs = np.asarray(kwargs["configs"])
        connected = np.repeat(configs[:, np.newaxis, :, :], 3, axis=1)
        weights = np.asarray(
            [[1.0 + 2.0j, 0.5, -0.25j], [0.25, -0.5j, 2.0]],
            dtype=np.complex128,
        )
        return connected, weights


def test_scalar_operator_delegates_representation_generic_state_hook() -> None:
    state = _HookState()
    configs = np.zeros((2, 2, 2), dtype=np.complex128)
    operator = build_scalar_operator(two_q=3, ell=2, depth=2)

    connected, weights = operator.connected_action(state, configs)

    assert isinstance(state, scalar_operators.ConnectedScalarActionProvider)
    assert connected.shape == (2, 3, 2, 2)
    assert weights.shape == (2, 3)
    np.testing.assert_array_equal(connected[:, 0], configs)
    assert state.received == {
        "two_q": 3,
        "ell": 2,
        "depth": 2,
        "configs": configs,
    }


def test_representation_generic_operator_and_coordinate_hook_support_two_q69() -> None:
    state = _HookState()
    configs = np.zeros((2, 2, 2), dtype=np.complex128)
    operator = build_scalar_operator(two_q=69, ell=2)

    connected, weights = operator.connected_action(state, configs)

    assert operator.two_q == 69
    assert connected.shape == (2, 3, 2, 2)
    assert weights.shape == (2, 3)


class _MalformedHookState(_BitsetState):
    def __init__(self, result: object) -> None:
        self.result = result

    def connected_scalar_action(self, **kwargs: Any) -> object:
        return self.result


@pytest.mark.parametrize(
    ("result", "message"),
    [
        ("junk", "pair"),
        (([1], np.ones(1)), "connected.*ndarray"),
        ((np.ones((1, 1)), [1.0]), "weights.*ndarray"),
        ((np.ones((1, 1)), np.asarray(1.0)), "non-scalar"),
        (
            (np.ones((2, 3, 2, 2)), np.ones((2, 4))),
            "leading dimensions",
        ),
        (
            (np.asarray([["junk"]], dtype=object), np.ones((1, 1))),
            "connected.*numeric",
        ),
        (
            (np.ones((1, 1)), np.asarray([["junk"]], dtype=object)),
            "weights.*numeric",
        ),
        ((np.ones((1, 1)), np.asarray([[np.nan]])), "finite"),
        ((np.ones((1, 1)), np.asarray([[np.inf]])), "finite"),
    ],
)
def test_scalar_operator_rejects_malformed_coordinate_hook_results(
    result: object, message: str
) -> None:
    operator = build_scalar_operator(two_q=3, ell=2)

    with pytest.raises((TypeError, ValueError), match=message):
        operator.connected_action(
            _MalformedHookState(result), np.zeros((1, 2, 2), dtype=np.complex128)
        )


def test_coordinate_hook_rejects_input_batch_cardinality_mismatch() -> None:
    operator = build_scalar_operator(two_q=3, ell=2)
    result = (
        np.ones((1, 3, 2, 2), dtype=np.complex128),
        np.ones((1, 3), dtype=np.complex128),
    )

    with pytest.raises(ValueError, match="batch"):
        operator.connected_action(
            _MalformedHookState(result), np.zeros((2, 2, 2), dtype=np.complex128)
        )


def test_coordinate_hook_preserves_single_config_neighborhood_semantics() -> None:
    operator = build_scalar_operator(two_q=69, ell=2)
    configs = np.zeros((2, 2), dtype=np.complex128)
    result = (
        np.ones((3, 2, 2), dtype=np.complex128),
        np.ones(3, dtype=np.complex128),
    )

    connected, weights = operator.connected_action(
        _MalformedHookState(result), configs
    )

    assert connected.shape == (3, 2, 2)
    assert weights.shape == (3,)


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
    imported: set[str] = set()
    for module_path in RUNTIME_MODULES:
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)

    assert not any(
        module == "benchmark_v0" or module.startswith("benchmark_v0.")
        for module in imported
    )
