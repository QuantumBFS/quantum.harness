from __future__ import annotations

import jax
import jax.numpy as jnp
import numpy as np
import optax
import pytest
from flax import serialization
from scipy.linalg import expm

import challenge15
from challenge15.angular import angular_operators
from challenge15.fermions import DeterminantBasis
from challenge15.model import (
    ModelConfig,
    ProjectedPfaffianNQS,
    embed_adam_state,
    embed_rank,
    gated_carrier,
    scaled_complex_sum,
)
from challenge15.monopole import raw_north_lll_polynomials
from challenge15.projector import ProjectionGrid
from challenge15.spec import SphereSpec


def _random_spinors(particles: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    spinors = rng.normal(size=(particles, 2)) + 1j * rng.normal(
        size=(particles, 2)
    )
    return spinors / np.linalg.norm(spinors, axis=-1, keepdims=True)


def _larger_grid(spec: SphereSpec, target_l: int) -> ProjectionGrid:
    n_alpha = 2 * spec.l_max + 3
    n_beta = (spec.l_max + target_l + 2) // 2 + 2
    alpha_nodes = np.arange(n_alpha, dtype=np.float64) * (2 * np.pi / n_alpha)
    alpha_weights = np.full(n_alpha, 2 * np.pi / n_alpha, dtype=np.complex128)
    beta_nodes, beta_weights = np.polynomial.legendre.leggauss(n_beta)
    arrays = (
        alpha_nodes,
        alpha_weights,
        np.asarray(beta_nodes, dtype=np.float64),
        np.asarray(beta_weights, dtype=np.complex128),
    )
    for array in arrays:
        array.setflags(write=False)
    return ProjectionGrid(*arrays, target_l=target_l, l_max=spec.l_max)


def _determinant_row(spec: SphereSpec, spinors: np.ndarray) -> np.ndarray:
    basis = DeterminantBasis.with_two_m(spec, 0)
    orbitals = np.asarray(raw_north_lll_polynomials(spinors, spec))
    values = []
    for state in basis.states:
        occupied = [
            orbital
            for orbital in range(spec.orbital_count)
            if state & (1 << orbital)
        ]
        values.append(np.linalg.det(orbitals[:, occupied]))
    return np.asarray(values, dtype=np.complex128)


def test_model_interfaces_are_publicly_exported():
    assert challenge15.ModelConfig is ModelConfig
    assert challenge15.ProjectedPfaffianNQS is ProjectedPfaffianNQS
    assert challenge15.embed_rank is embed_rank
    assert challenge15.embed_adam_state is embed_adam_state
    assert challenge15.gated_carrier is gated_carrier


def test_one_parameter_tree_serves_both_sectors():
    model = ProjectedPfaffianNQS(ModelConfig(rank=2, hidden_width=16, depth=2))
    spec = SphereSpec(2)
    points = jnp.asarray(_random_spinors(2, 1))
    variables = model.init(jax.random.key(0), spec, points, target_l=0)
    value_l0 = model.apply(variables, spec, points, target_l=0)
    value_l2 = model.apply(variables, spec, points, target_l=2)
    assert jnp.isfinite(value_l0)
    assert jnp.isfinite(value_l2)
    assert set(variables) == {"params"}
    assert "parameters_l0" not in variables["params"]
    assert "parameters_l2" not in variables["params"]
    assert not any("head" in path.lower() for path, _ in _flatten(variables["params"]))


def _exact_multiplicity(spec: SphereSpec, target_l: int) -> int:
    basis = DeterminantBasis.with_two_m(spec, 0)
    eigenvalues = np.linalg.eigvalsh(
        angular_operators(basis, return_l2_only=True)
    )
    return int(
        np.count_nonzero(
            np.isclose(eigenvalues, target_l * (target_l + 1), atol=1e-10)
        )
    )


@pytest.mark.parametrize("particles", [2, 3, 4])
@pytest.mark.parametrize("rank", [2, 3])
def test_parameter_tree_axes_follow_only_declared_shared_shapes(particles, rank):
    config = ModelConfig(
        rank=rank,
        hidden_width=17,
        depth=2,
        token_width=7,
        fourier_order=5,
    )
    spec = SphereSpec(particles)
    points = jnp.asarray(_random_spinors(particles, 20 + particles + rank))
    params = ProjectedPfaffianNQS(config).init(
        jax.random.key(1), spec, points, target_l=0
    )["params"]
    leaves = dict(_flatten(params))

    assert leaves["carrier_tokens"].shape == (config.rank, config.token_width)
    assert leaves["carrier_gates"].shape == (config.rank, 2)
    input_width = 1 + 2 * config.fourier_order + 2 + config.token_width
    expected_shapes = {
        "carrier_tokens": (rank, config.token_width),
        "carrier_gates": (rank, 2),
        "shared_input/kernel": (input_width, config.hidden_width),
        "shared_input/bias": (config.hidden_width,),
        "shared_residual_0/kernel": (config.hidden_width, config.hidden_width),
        "shared_residual_0/bias": (config.hidden_width,),
        "shared_residual_1/kernel": (config.hidden_width, config.hidden_width),
        "shared_residual_1/bias": (config.hidden_width,),
        "shared_reduced_output/kernel": (config.hidden_width, 2),
        "shared_reduced_output/bias": (2,),
    }
    assert {path: leaf.shape for path, leaf in leaves.items()} == expected_shapes

    determinant_count = DeterminantBasis.with_two_m(spec, 0).dimension
    multiplicities = {_exact_multiplicity(spec, target_l) for target_l in (0, 2)}
    forbidden = {determinant_count, *multiplicities}
    explicitly_shared = {
        config.hidden_width,
        config.token_width,
        input_width,
        2,  # two real components of every shared complex output/gate
    }
    for path, shape in expected_shapes.items():
        for axis in shape:
            if axis in forbidden:
                if path in {"carrier_tokens", "carrier_gates"} and axis == rank:
                    continue
                assert axis in explicitly_shared
                assert path in {
                    "carrier_gates",
                    "shared_reduced_output/kernel",
                    "shared_reduced_output/bias",
                }
    assert not any("determinant" in path or "multiplicity" in path for path in leaves)


def _flatten(tree, prefix=""):
    for key, value in tree.items():
        path = f"{prefix}/{key}" if prefix else key
        if hasattr(value, "items"):
            yield from _flatten(value, path)
        else:
            yield path, np.asarray(value)


@pytest.mark.parametrize("seed", [2, 13])
@pytest.mark.parametrize("target_l", [0, 2])
@pytest.mark.parametrize("multiplet", [False, True])
def test_rank_embedding_preserves_old_outputs_and_bytes_exactly(
    seed, target_l, multiplet
):
    spec = SphereSpec(2)
    points = jnp.asarray(_random_spinors(2, 30 + seed))
    small = ProjectedPfaffianNQS(ModelConfig(rank=2, hidden_width=16, depth=2))
    variables = small.init(jax.random.key(seed), spec, points, target_l=target_l)
    old_leaves = dict(_flatten(variables["params"]))
    if multiplet:
        old_value = small.apply_multiplet(variables, spec, points, target_l)
    else:
        old_value = small.apply(variables, spec, points, target_l=target_l)

    expanded = embed_rank(
        variables, old_rank=2, new_rank=4, key=jax.random.key(99)
    )
    large = ProjectedPfaffianNQS(ModelConfig(rank=4, hidden_width=16, depth=2))
    if multiplet:
        new_value = large.apply_multiplet(expanded, spec, points, target_l)
        for m in old_value:
            np.testing.assert_array_equal(old_value[m], new_value[m])
    else:
        np.testing.assert_array_equal(
            old_value, large.apply(expanded, spec, points, target_l=target_l)
        )

    new_leaves = dict(_flatten(expanded["params"]))
    for path, old_leaf in old_leaves.items():
        new_leaf = new_leaves[path]
        retained = new_leaf[:2] if path in {"carrier_tokens", "carrier_gates"} else new_leaf
        assert retained.tobytes() == old_leaf.tobytes()
    np.testing.assert_array_equal(
        new_leaves["carrier_gates"][2:],
        np.zeros((2, 2), dtype=new_leaves["carrier_gates"].dtype),
    )
    assert serialization.to_bytes(expanded) == serialization.to_bytes(
        embed_rank(variables, 2, 4, key=jax.random.key(99))
    )


def test_rank_embedding_accepts_params_subtree_and_requires_key():
    spec = SphereSpec(2)
    points = jnp.asarray(_random_spinors(2, 44))
    params = ProjectedPfaffianNQS(ModelConfig(rank=2)).init(
        jax.random.key(4), spec, points, target_l=0
    )["params"]
    expanded = embed_rank(params, 2, 3, key=jax.random.key(5))
    assert expanded["carrier_tokens"].shape[0] == 3
    with pytest.raises(TypeError, match="key"):
        embed_rank(params, 2, 3)


def test_rank_embedding_validates_growth_and_declared_rank():
    spec = SphereSpec(2)
    points = jnp.asarray(_random_spinors(2, 4))
    variables = ProjectedPfaffianNQS(ModelConfig(rank=2)).init(
        jax.random.key(3), spec, points, target_l=0
    )
    with pytest.raises(ValueError, match="new_rank"):
        embed_rank(variables, 2, 2, key=jax.random.key(0))
    with pytest.raises(ValueError, match="old_rank"):
        embed_rank(variables, 3, 4, key=jax.random.key(0))


def test_gated_carrier_has_explicit_nonfinite_forward_and_gradient_semantics():
    zero = jnp.asarray(0.0 + 0.0j, dtype=jnp.complex128)
    nonfinite = jnp.asarray(np.inf + 1j * np.nan, dtype=jnp.complex128)
    inactive, inactive_tangent = jax.jvp(
        lambda gate: gated_carrier(gate, nonfinite),
        (zero,),
        (jnp.asarray(1.0 + 0.0j),),
    )
    np.testing.assert_array_equal(inactive, zero)
    np.testing.assert_array_equal(inactive_tangent, zero)

    finite_carrier = jnp.asarray(0.7 - 0.4j)
    _, activation_tangent = jax.jvp(
        lambda gate: gated_carrier(gate, finite_carrier),
        (zero,),
        (jnp.asarray(1.0 + 0.0j),),
    )
    np.testing.assert_array_equal(activation_tangent, finite_carrier)
    _, carrier_tangent = jax.jvp(
        lambda carrier: gated_carrier(zero, carrier),
        (finite_carrier,),
        (jnp.asarray(1.0 + 0.0j),),
    )
    np.testing.assert_array_equal(carrier_tangent, zero)

    active, active_tangent = jax.jvp(
        lambda gate: gated_carrier(gate, nonfinite),
        (jnp.asarray(1.0 + 0.0j),),
        (jnp.asarray(1.0 + 0.0j),),
    )
    assert not bool(jnp.isfinite(active))
    assert not bool(jnp.isfinite(active_tangent))


def test_scaled_complex_sum_survives_extreme_scale_and_cancellation():
    large = jnp.asarray(
        [1e300 + 1e300j, -1e300 - 1e300j], dtype=jnp.complex128
    )
    tiny = jnp.asarray([1e-300j, 2e-300j], dtype=jnp.complex128)
    cancellation = jnp.asarray([1e16 + 0j, 1 + 0j, -1e16 + 0j])

    assert scaled_complex_sum(large) == 0
    assert scaled_complex_sum(tiny).imag == pytest.approx(3e-300)
    assert scaled_complex_sum(cancellation).real == pytest.approx(1.0)


@pytest.mark.parametrize("multiplet", [False, True])
def test_model_paths_isolate_inactive_nonfinite_carrier_but_expose_active_one(
    multiplet,
):
    spec = SphereSpec(2)
    points = jnp.asarray(_random_spinors(2, 52))
    model = ProjectedPfaffianNQS(ModelConfig(rank=2, hidden_width=8, depth=1))
    variables = model.init(jax.random.key(8), spec, points, target_l=2)
    bad = jax.tree.map(lambda value: value, variables)
    bad["params"]["carrier_tokens"] = bad["params"]["carrier_tokens"].at[1, 0].set(
        jnp.nan
    )
    bad["params"]["carrier_gates"] = bad["params"]["carrier_gates"].at[1].set(0.0)

    def evaluate(candidate):
        if multiplet:
            values = model.apply_multiplet(candidate, spec, points, 2)
            return jnp.stack(tuple(values.values()))
        return model.apply(candidate, spec, points, target_l=2)[None]

    inactive_values = evaluate(bad)
    assert bool(jnp.all(jnp.isfinite(inactive_values)))
    gate_gradient = jax.grad(
        lambda gates: jnp.sum(
            jnp.abs(
                evaluate(
                    {
                        "params": {
                            **bad["params"],
                            "carrier_gates": gates,
                        }
                    }
                )
            )
            ** 2
        )
    )(bad["params"]["carrier_gates"])
    assert bool(jnp.all(jnp.isfinite(gate_gradient)))

    active = {
        "params": {
            **bad["params"],
            "carrier_gates": bad["params"]["carrier_gates"].at[1, 0].set(1.0),
        }
    }
    assert not bool(jnp.all(jnp.isfinite(evaluate(active))))
    active_gradient = jax.grad(
        lambda gates: jnp.sum(
            jnp.abs(
                evaluate(
                    {
                        "params": {
                            **active["params"],
                            "carrier_gates": gates,
                        }
                    }
                )
            )
            ** 2
        )
    )(active["params"]["carrier_gates"])
    assert not bool(jnp.all(jnp.isfinite(active_gradient)))


def test_adam_state_embedding_preserves_history_and_supports_update():
    spec = SphereSpec(2)
    points = jnp.asarray(_random_spinors(2, 61))
    model = ProjectedPfaffianNQS(ModelConfig(rank=2, hidden_width=8, depth=1))
    params = model.init(jax.random.key(9), spec, points, target_l=0)["params"]
    optimizer = optax.adam(1e-3)
    state = optimizer.init(params)
    gradients = jax.tree.map(lambda value: jnp.ones_like(value), params)
    _, state = optimizer.update(gradients, state, params)

    expanded_params = embed_rank(params, 2, 4, key=jax.random.key(62))
    expanded_state = embed_adam_state(
        state, expanded_params, old_rank=2, new_rank=4
    )
    assert np.asarray(expanded_state[0].count).tobytes() == np.asarray(
        state[0].count
    ).tobytes()
    for moment_name in ("mu", "nu"):
        old_moment = dict(_flatten(getattr(state[0], moment_name)))
        new_moment = dict(_flatten(getattr(expanded_state[0], moment_name)))
        for path, old_leaf in old_moment.items():
            retained = (
                new_moment[path][:2]
                if path in {"carrier_tokens", "carrier_gates"}
                else new_moment[path]
            )
            assert retained.tobytes() == old_leaf.tobytes()
        np.testing.assert_array_equal(
            new_moment["carrier_tokens"][2:],
            np.zeros_like(new_moment["carrier_tokens"][2:]),
        )
        np.testing.assert_array_equal(
            new_moment["carrier_gates"][2:],
            np.zeros_like(new_moment["carrier_gates"][2:]),
        )

    expanded_gradients = jax.tree.map(
        lambda value: jnp.ones_like(value), expanded_params
    )
    updates, next_state = optimizer.update(
        expanded_gradients, expanded_state, expanded_params
    )
    updated_params = optax.apply_updates(expanded_params, updates)
    assert jax.tree.structure(updated_params) == jax.tree.structure(expanded_params)
    assert next_state[0].mu["carrier_tokens"].shape == (4, 8)


def test_adam_state_rank_exemption_is_restricted_to_carrier_paths():
    spec = SphereSpec(2)
    points = jnp.asarray(_random_spinors(2, 63))
    model = ProjectedPfaffianNQS(
        ModelConfig(rank=2, hidden_width=2, depth=0, token_width=3)
    )
    params = model.init(jax.random.key(10), spec, points, target_l=0)["params"]
    state = optax.adam(1e-3).init(params)
    expanded = embed_rank(params, 2, 4, key=jax.random.key(64))
    expanded["shared_input"]["bias"] = jnp.zeros(4, dtype=jnp.float64)

    with pytest.raises(ValueError, match="non-rank Adam moment shape"):
        embed_adam_state(state, expanded, old_rank=2, new_rank=4)


@pytest.mark.parametrize("seed", [7, 19])
@pytest.mark.parametrize("target_l", [0, 2])
def test_projected_model_obeys_exchange_chart_and_degree(seed, target_l):
    spec = SphereSpec(2)
    spinors = _random_spinors(2, 100 + seed)
    model = ProjectedPfaffianNQS(ModelConfig(rank=2, hidden_width=12, depth=1))
    variables = model.init(jax.random.key(seed), spec, spinors, target_l=target_l)
    value = model.apply(variables, spec, spinors, target_l=target_l)

    exchanged = spinors[::-1].copy()
    np.testing.assert_allclose(
        model.apply(variables, spec, exchanged, target_l=target_l),
        -value,
        rtol=2e-11,
        atol=2e-12,
    )

    phases = np.exp(1j * np.asarray([0.27, -0.41]))
    chart_changed = phases[:, None] * spinors
    np.testing.assert_allclose(
        model.apply(variables, spec, chart_changed, target_l=target_l),
        np.prod(phases**spec.two_q) * value,
        rtol=3e-11,
        atol=3e-12,
    )

    scale = 1.2 - 0.17j
    scaled = spinors.copy()
    scaled[0] *= scale
    np.testing.assert_allclose(
        model.apply(variables, spec, scaled, target_l=target_l),
        scale**spec.two_q * value,
        rtol=3e-11,
        atol=3e-12,
    )


@pytest.mark.parametrize("seed", [11, 23])
@pytest.mark.parametrize("target_l", [0, 2])
def test_model_is_exact_l2_eigenstate_and_quadrature_stable(seed, target_l):
    spec = SphereSpec(2)
    points = tuple(_random_spinors(2, 200 + seed + offset) for offset in range(4))
    model = ProjectedPfaffianNQS(ModelConfig(rank=2, hidden_width=12, depth=1))
    variables = model.init(jax.random.key(seed), spec, points[0], target_l=target_l)

    evaluation = np.stack([_determinant_row(spec, point) for point in points])
    values = np.asarray(
        [model.apply(variables, spec, point, target_l=target_l) for point in points]
    )
    coefficients, _, rank, _ = np.linalg.lstsq(evaluation, values, rcond=1e-12)
    assert rank == DeterminantBasis.with_two_m(spec, 0).dimension
    l2 = angular_operators(
        DeterminantBasis.with_two_m(spec, 0), return_l2_only=True
    )
    np.testing.assert_allclose(
        l2 @ coefficients,
        target_l * (target_l + 1) * coefficients,
        rtol=2e-9,
        atol=2e-10,
    )

    minimal = model.apply(variables, spec, points[0], target_l=target_l)
    larger = model.apply(
        variables,
        spec,
        points[0],
        target_l=target_l,
        grid=_larger_grid(spec, target_l),
    )
    np.testing.assert_allclose(larger, minimal, rtol=3e-11, atol=3e-12)


@pytest.mark.parametrize("seed", [31, 47])
@pytest.mark.parametrize("target_l", [0, 2])
def test_multiplet_obeys_finite_rotation_without_m_specific_parameters(
    seed, target_l
):
    spec = SphereSpec(2)
    spinors = _random_spinors(2, 300 + seed)
    model = ProjectedPfaffianNQS(ModelConfig(rank=2, hidden_width=12, depth=1))
    variables = model.init(
        jax.random.key(seed), spec, spinors, target_l=target_l
    )

    axis = np.asarray([0.3, -0.4, 0.5])
    axis /= np.linalg.norm(axis)
    angle = 0.61
    pauli = np.asarray(
        [
            [[0, 1], [1, 0]],
            [[0, -1j], [1j, 0]],
            [[1, 0], [0, -1]],
        ],
        dtype=np.complex128,
    )
    rotation = expm(-0.5j * angle * np.einsum("a,aij->ij", axis, pauli))
    rotated = np.einsum("ab,ib->ia", rotation.conj().T, spinors)
    values = np.asarray(
        tuple(
            model.apply_multiplet(
                variables, spec, spinors, target_l
            ).values()
        )
    )
    rotated_values = np.asarray(
        tuple(
            model.apply_multiplet(
                variables, spec, rotated, target_l
            ).values()
        )
    )

    m_values = np.arange(-target_l, target_l + 1)
    jz = np.diag(m_values)
    jp = np.zeros((m_values.size, m_values.size), dtype=np.complex128)
    for column, m in enumerate(m_values[:-1]):
        jp[column + 1, column] = np.sqrt(
            target_l * (target_l + 1) - m * (m + 1)
        )
    representation = expm(
        -1j
        * angle
        * (
            axis[0] * (jp + jp.conj().T) / 2
            + axis[1] * (jp - jp.conj().T) / (2j)
            + axis[2] * jz
        )
    )
    np.testing.assert_allclose(
        rotated_values,
        representation.conj().T @ values,
        rtol=2e-10,
        atol=2e-11,
    )
    assert not any(
        "m_" in path.lower() or "component" in path.lower()
        for path, _ in _flatten(variables["params"])
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"rank": 0},
        {"hidden_width": 0},
        {"depth": -1},
        {"token_width": 0},
        {"fourier_order": 0},
        {"block_size": 0},
    ],
)
def test_model_config_rejects_invalid_values(kwargs):
    with pytest.raises(ValueError):
        ModelConfig(**kwargs)
