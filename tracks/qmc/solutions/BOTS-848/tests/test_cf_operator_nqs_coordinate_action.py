from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from scalable_v1.routes.cf_operator_nqs import coordinate_action
from scalable_v1.routes.cf_operator_nqs import jets, pair_casimir
from scalable_v1.routes.cf_operator_nqs.coordinate_action import (
    CoordinateActionNumericalError,
    apply_pair_dot,
    evaluate_seed_and_actions,
)
from scalable_v1.routes.cf_operator_nqs.jets import PairJet
from scalable_v1.routes.cf_operator_nqs.pair_casimir import (
    pair_casimir_decomposition,
)
from scalable_v1.routes.cf_operator_nqs.seeds import (
    JKCFSeedFamily,
    polynomial_seed_amplitude,
)


def _normalized_non_node_spinors(
    *, seed: int, batch: int, n_electrons: int
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    values = rng.normal(size=(batch, n_electrons, 2)) + 1.0j * rng.normal(
        size=(batch, n_electrons, 2)
    )
    return values / np.linalg.norm(values, axis=-1, keepdims=True)


@pytest.mark.parametrize(("l", "m"), ((0, 0), (2, -2), (2, 0), (2, 2)))
@pytest.mark.parametrize("ell", (2, 3))
def test_coordinate_scalar_action_has_exact_n2_eigenvalue(
    l: int, m: int, ell: int
) -> None:
    family = JKCFSeedFamily(n_electrons=2, two_q=3)
    state = family.state(l=l, m=m)
    configs = _normalized_non_node_spinors(seed=848, batch=4, n_electrons=2)

    seed_values, actions = evaluate_seed_and_actions(state, configs, ells=(ell,))

    decomposition = pair_casimir_decomposition(two_q=3, ell=ell)
    q = 1.5
    x_l = 0.5 * (l * (l + 1) - 2.0 * q * (q + 1.0))
    expected = (
        2.0 * decomposition.self_scalar
        + decomposition.evaluate_scalar(x_l)
    )
    np.testing.assert_allclose(
        actions[:, 0],
        expected * seed_values,
        rtol=1.0e-10,
        atol=1.0e-11,
    )


def test_pair_dot_matches_explicit_monomial_action() -> None:
    values = (0.8 + 0.1j, -0.3 + 0.2j, 0.7 - 0.2j, 0.4 + 0.3j)
    coordinates = tuple(
        PairJet.variable(value, axis=axis)
        for axis, value in enumerate(values)
    )
    u_i, v_i, u_j, v_j = coordinates
    value = u_i**2 * v_i * u_j * v_j**2

    actual = apply_pair_dot(value, coordinates).constant_term

    ui, vi, uj, vj = values
    base = ui**2 * vi * uj * vj**2
    expected = (
        0.25 * (2 - 1) * (1 - 2) * base
        + 0.5 * 1 * 1 * ui**3 * uj**0 * vj**3
        + 0.5 * 2 * 2 * ui * vi**2 * uj**2 * vj
    )
    np.testing.assert_allclose(actual, expected, rtol=2.0e-14, atol=2.0e-14)


def test_all_five_m_components_share_finite_coordinate_action() -> None:
    family = JKCFSeedFamily(n_electrons=6, two_q=15)
    configs = _normalized_non_node_spinors(seed=3848, batch=2, n_electrons=6)

    for state in family.generate_multiplet().values():
        seed_values, actions = evaluate_seed_and_actions(state, configs)
        assert seed_values.shape == (2,)
        assert actions.shape == (2, 3)
        assert np.all(np.isfinite(seed_values))
        assert np.all(np.isfinite(actions))


def test_coordinate_action_rejects_nonfinite_configs() -> None:
    family = JKCFSeedFamily(n_electrons=2, two_q=3)
    configs = _normalized_non_node_spinors(seed=848, batch=1, n_electrons=2)
    configs[0, 0, 0] = np.nan

    with pytest.raises(CoordinateActionNumericalError, match="finite"):
        evaluate_seed_and_actions(family.ground_state(), configs)


def test_ring_generic_seed_polynomial_matches_existing_complex_path() -> None:
    family = JKCFSeedFamily(n_electrons=6, two_q=15)
    configs = _normalized_non_node_spinors(seed=1848, batch=3, n_electrons=6)
    for state in (family.ground_state(), family.reduced_l2_state()):
        expected = state.amplitude(configs)
        actual = np.asarray(
            [
                polynomial_seed_amplitude(
                    state,
                    config,
                    lambda matrix: np.linalg.det(
                        np.asarray(matrix, dtype=np.complex128)
                    ),
                )
                for config in configs
            ]
        )
        np.testing.assert_allclose(actual, expected, rtol=2.0e-12, atol=1.0e-300)


def _symbolic_pair_dot(expression: object, variables: tuple[object, ...]) -> object:
    import sympy as sp

    u_i, v_i, u_j, v_j = variables
    jzi = sp.Rational(1, 2) * (
        u_i * sp.diff(expression, u_i) - v_i * sp.diff(expression, v_i)
    )
    zz = sp.Rational(1, 2) * (
        u_j * sp.diff(jzi, u_j) - v_j * sp.diff(jzi, v_j)
    )
    plus_minus = v_j * sp.diff(u_i * sp.diff(expression, v_i), u_j)
    minus_plus = u_j * sp.diff(v_i * sp.diff(expression, u_i), v_j)
    return zz + sp.Rational(1, 2) * (plus_minus + minus_plus)


def test_pair_jet_action_matches_independent_symbolic_reference() -> None:
    import sympy as sp

    family = JKCFSeedFamily(n_electrons=2, two_q=3)
    state = family.reduced_l2_state()
    variables = sp.symbols("u_i v_i u_j v_j")
    expression = polynomial_seed_amplitude(
        state,
        ((variables[0], variables[1]), (variables[2], variables[3])),
        lambda matrix: sp.Matrix(matrix).det(),
    )
    decomposition = pair_casimir_decomposition(two_q=3, ell=2)
    scaled_powers = [expression]
    for _ in range(decomposition.degree):
        scaled_powers.append(
            _symbolic_pair_dot(scaled_powers[-1], variables)
            / decomposition.scale
        )
    symbolic_action = 2.0 * decomposition.self_scalar * expression + sum(
        coefficient * power
        for coefficient, power in zip(
            decomposition.coefficients,
            scaled_powers,
            strict=True,
        )
    )
    substitutions = dict(
        zip(
            variables,
            (
                sp.Rational(3, 5),
                sp.Rational(4, 5),
                sp.Rational(5, 13),
                sp.Rational(12, 13),
            ),
            strict=True,
        )
    )
    configs = np.asarray(
        [[[(3 / 5), (4 / 5)], [(5 / 13), (12 / 13)]]],
        dtype=np.complex128,
    )

    _, actual = evaluate_seed_and_actions(state, configs, ells=(2,))
    expected = complex(sp.N(symbolic_action.subs(substitutions), 30))

    np.testing.assert_allclose(actual[0, 0], expected, rtol=1.0e-10, atol=1.0e-11)


@pytest.mark.parametrize("l", (0, 2))
def test_operator_dressing_is_not_only_global_normalization(l: int) -> None:
    family = JKCFSeedFamily(n_electrons=6, two_q=15)
    state = family.state(l=l, m=0)
    configs = _normalized_non_node_spinors(
        seed=2848 + l,
        batch=8,
        n_electrons=6,
    )

    seed_values, actions = evaluate_seed_and_actions(state, configs)

    matrix = np.column_stack((seed_values, actions))
    singular_values = np.linalg.svd(matrix, compute_uv=False)
    assert singular_values[1] / singular_values[0] >= 1.0e-8


def test_coordinate_action_runtime_has_no_ed_import() -> None:
    runtime = (
        Path(coordinate_action.__file__),
        Path(pair_casimir.__file__),
        Path(jets.__file__),
    )
    imported: set[str] = set()
    for module_path in runtime:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)
    assert not any(
        module == "benchmark_v0" or module.startswith("benchmark_v0.")
        for module in imported
    )
