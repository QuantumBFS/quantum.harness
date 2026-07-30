from __future__ import annotations

import math

import numpy as np
import pytest

from scripts.hard_goal_biased_benchmark import build_parser as build_benchmark_parser
from spinglass3d.backend import BackendCase
from spinglass3d.bias import BiasRoute, OverlapBias
from spinglass3d.jax_biased_backend import (
    JaxBiasedPairBackend,
    metropolis_accept,
)
from spinglass3d.linear_bias import LinearFeatureBasis
from spinglass3d.model import EABonds, energy
from spinglass3d.rg import block_majority_3d
from spinglass3d.templates import TemplateEncoder
from spinglass3d.tensor_train import LocalTensorTrain, SymmetricLocalTT


def _bias(
    seed: int,
    *,
    route: BiasRoute = BiasRoute.B_CONDITIONED_TT,
    kind: str = "cube",
    chi: int = 2,
) -> OverlapBias:
    encoder = TemplateEncoder(kind, conditioned=True, rg_level=1)
    tt = SymmetricLocalTT(
        LocalTensorTrain.random(encoder.token_count, chi, seed=seed),
        encoder,
    )
    if route is BiasRoute.C_LINEAR_PLUS_TT:
        return OverlapBias(
            route,
            LinearFeatureBasis.cube_v1(),
            np.array([0.13, -0.09, 0.05, 0.04, -0.03]),
            tt,
        )
    return OverlapBias(route, None, np.empty(0), tt)


def _case(
    seed: int = 2026073202,
    *,
    temperatures: int = 2,
    pairs: int = 1,
    betas: np.ndarray | None = None,
) -> BackendCase:
    source = BackendCase.random(
        length=3,
        temperatures=temperatures,
        samples=1,
        walkers=2 * pairs,
        seed=seed,
    )
    return BackendCase(
        spins=source.spins,
        bonds=source.bonds,
        betas=(
            np.linspace(0.2, 0.9, temperatures, dtype=np.float64)
            if betas is None
            else np.asarray(betas, dtype=np.float64)
        ),
        seed=seed,
    )


def _majority_boundary_case(seed: int, *, betas: np.ndarray | None = None) -> BackendCase:
    source = BackendCase.random(
        length=6,
        temperatures=2,
        samples=1,
        walkers=2,
        seed=seed,
    )
    spins = source.spins.copy()
    overlap = -np.ones((6, 6, 6), dtype=np.int8)
    boundary = overlap[:3, :3, :3].reshape(-1)
    boundary[:14] = 1
    overlap[:3, :3, :3] = boundary.reshape(3, 3, 3)
    selected_betas = (
        np.linspace(0.2, 0.9, 2, dtype=np.float64)
        if betas is None
        else np.asarray(betas, dtype=np.float64)
    )
    for temperature in range(2):
        spins[0, temperature, 0] = 1
        spins[0, temperature, 1] = overlap
    return BackendCase(
        spins=spins,
        bonds=source.bonds,
        betas=selected_betas,
        seed=source.seed,
    )


def _length_case(length: int, seed: int) -> BackendCase:
    source = BackendCase.random(
        length=length,
        temperatures=2,
        samples=1,
        walkers=2,
        seed=seed,
    )
    return BackendCase(
        spins=source.spins,
        bonds=source.bonds,
        betas=np.array([0.2, 0.9], dtype=np.float64),
        seed=source.seed,
    )


def _full_bias_value(
    bias: OverlapBias,
    bonds: EABonds,
    left: np.ndarray,
    right: np.ndarray,
) -> float:
    q_prime = block_majority_3d(
        np.multiply(left, right, dtype=np.int8),
    )
    return bias.value(q_prime, bonds, bias.tt.encoder)


def _full_action(
    bias: OverlapBias,
    bonds: EABonds,
    beta: float,
    left: np.ndarray,
    right: np.ndarray,
) -> float:
    return float(
        beta * (energy(left, bonds) + energy(right, bonds))
        + _full_bias_value(bias, bonds, left, right)
    )


def _numpy_full_recompute_sweep(
    case: BackendCase,
    biases: tuple[OverlapBias, ...],
    orders: np.ndarray,
    uniforms: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    temperatures = case.betas.size
    pairs = case.spins.shape[2] // 2
    length = case.spins.shape[-1]
    n_sites = length**3
    spins = case.spins[0].reshape(
        temperatures,
        pairs,
        2,
        length,
        length,
        length,
    ).transpose(1, 0, 2, 3, 4, 5).copy()
    accepted = np.zeros_like(orders, dtype=bool)
    deltas = np.empty_like(uniforms, dtype=np.float64)
    bonds = EABonds(case.bonds[0])
    for pair in range(pairs):
        for temperature, beta in enumerate(case.betas):
            for step, encoded in enumerate(orders[pair, temperature]):
                replica = int(encoded) // n_sites
                flat_site = int(encoded) % n_sites
                site = tuple(
                    int(value)
                    for value in np.unravel_index(flat_site, (length,) * 3)
                )
                left, right = spins[pair, temperature]
                before = _full_action(
                    biases[temperature],
                    bonds,
                    float(beta),
                    left,
                    right,
                )
                spins[pair, temperature, replica][site] *= -1
                after = _full_action(
                    biases[temperature],
                    bonds,
                    float(beta),
                    spins[pair, temperature, 0],
                    spins[pair, temperature, 1],
                )
                delta = after - before
                take = metropolis_accept(delta, float(uniforms[pair, temperature, step]))
                deltas[pair, temperature, step] = delta
                accepted[pair, temperature, step] = take
                if not take:
                    spins[pair, temperature, replica][site] *= -1
    return spins, deltas, accepted


def _backend(
    case: BackendCase,
    biases: OverlapBias | tuple[OverlapBias, ...],
) -> JaxBiasedPairBackend:
    jax = pytest.importorskip("jax")
    return JaxBiasedPairBackend(
        case,
        biases,
        required_platform=jax.default_backend(),
    )


def test_cached_route_c_action_delta_matches_full_recompute() -> None:
    bias = _bias(2026073203, route=BiasRoute.C_LINEAR_PLUS_TT)
    backend = _backend(_majority_boundary_case(2026073202), bias)
    changed_bias = 0
    for temperature in range(2):
        for replica in range(2):
            for site in np.ndindex((3, 3, 3)):
                cached = backend.cached_local_action_delta(
                    0,
                    temperature,
                    replica,
                    site,
                )
                exact = backend.full_local_action_delta(
                    0,
                    temperature,
                    replica,
                    site,
                )
                assert cached == pytest.approx(exact, abs=2e-11, rel=0.0)
                changed_bias += abs(backend.cached_local_bias_delta(0, temperature, site)) > 1e-13
    assert changed_bias > 0
    backend.assert_cache_consistent()


@pytest.mark.parametrize(("length", "expected_entries"), [(6, 64), (9, 216)])
def test_local_bias_geometry_has_eight_affected_centers_per_coarse_site(
    length: int,
    expected_entries: int,
) -> None:
    backend = _backend(_length_case(length, 2026073300 + length), _bias(2026073310))

    resources = backend.resource_snapshot()

    assert resources["local_bias_centers_per_proposal"] == 8
    assert resources["local_bias_geometry_entries"] == expected_entries


def test_jitted_random_sequential_sweep_matches_numpy_full_recompute() -> None:
    case = _case(2026073204)
    biases = (_bias(2026073205), _bias(2026073206))
    backend = _backend(case, biases)
    n_proposals = 2 * case.spins.shape[-1] ** 3
    rng = np.random.default_rng(2026073207)
    orders = np.asarray(
        [[rng.permutation(n_proposals) for _ in range(case.betas.size)]],
        dtype=np.int32,
    )
    uniforms = rng.uniform(0.01, 0.99, size=orders.shape)
    expected_spins, expected_deltas, expected_accepts = _numpy_full_recompute_sweep(
        case,
        biases,
        orders,
        uniforms,
    )

    result = backend.attempt_local(orders=orders, uniforms=uniforms)

    np.testing.assert_allclose(
        result.delta_action,
        expected_deltas,
        atol=3e-11,
        rtol=0.0,
    )
    np.testing.assert_array_equal(result.accepted, expected_accepts)
    np.testing.assert_array_equal(backend.spins, expected_spins)
    assert result.jitted is True
    backend.assert_cache_consistent()


def test_swap_cross_evaluates_temperature_biases_and_obeys_detailed_balance() -> None:
    case = _case(2026073208, betas=np.array([0.25, 0.95]))
    biases = (_bias(2026073209), _bias(2026073210))
    backend = _backend(case, biases)
    before = backend.spins.copy()
    bonds = EABonds(case.bonds[0])
    energy_0 = energy(before[0, 0, 0], bonds) + energy(before[0, 0, 1], bonds)
    energy_1 = energy(before[0, 1, 0], bonds) + energy(before[0, 1, 1], bonds)
    expected = (
        case.betas[0] * energy_1
        + _full_bias_value(biases[0], bonds, before[0, 1, 0], before[0, 1, 1])
        + case.betas[1] * energy_0
        + _full_bias_value(biases[1], bonds, before[0, 0, 0], before[0, 0, 1])
        - case.betas[0] * energy_0
        - _full_bias_value(biases[0], bonds, before[0, 0, 0], before[0, 0, 1])
        - case.betas[1] * energy_1
        - _full_bias_value(biases[1], bonds, before[0, 1, 0], before[0, 1, 1])
    )
    delta = backend.swap_action_delta(0, 0)
    assert delta == pytest.approx(expected, abs=3e-11, rel=0.0)
    assert math.exp(-delta) == pytest.approx(
        math.exp(
            backend.full_pair_action(0, 0, states=before[0, 0])
            + backend.full_pair_action(0, 1, states=before[0, 1])
            - backend.full_pair_action(0, 0, states=before[0, 1])
            - backend.full_pair_action(0, 1, states=before[0, 0])
        ),
        rel=2e-12,
    )

    accepted = backend.attempt_swaps(
        0,
        uniforms=np.full((1, 1), np.nextafter(0.0, 1.0)),
    )
    assert accepted[0, 0]
    assert backend.swap_action_delta(0, 0) == pytest.approx(-delta, abs=4e-11, rel=0.0)
    backend.assert_cache_consistent()


def test_pair_action_has_all_required_replica_and_q_symmetries() -> None:
    backend = _backend(_case(2026073211), _bias(2026073212))
    pair = backend.spins[0, 0]
    reference = backend.full_pair_action(0, 0, states=pair)
    assert backend.full_pair_action(0, 0, states=pair[::-1]) == pytest.approx(
        reference,
        abs=2e-11,
        rel=0.0,
    )
    assert backend.full_pair_action(0, 0, states=-pair) == pytest.approx(
        reference,
        abs=2e-11,
        rel=0.0,
    )
    single_flip = pair.copy()
    single_flip[0] *= -1
    assert backend.full_pair_action(0, 0, states=single_flip) == pytest.approx(
        reference,
        abs=2e-11,
        rel=0.0,
    )
    assert backend.attempt_global_q_flip(0, 0, replica=0) is True
    backend.assert_cache_consistent()


def test_changed_tt_parameters_change_metropolis_decision_after_explicit_refresh() -> None:
    case = _majority_boundary_case(
        2026073213,
        betas=np.array([0.01, 0.02]),
    )
    bias = _bias(2026073214)
    backend = _backend(case, bias)
    old = {
        (replica, site): backend.cached_local_action_delta(0, 0, replica, site)
        for replica in range(2)
        for site in np.ndindex((3, 3, 3))
    }
    bias.tt.model.cores[0] *= 4.0
    with pytest.raises(RuntimeError, match="stale bias"):
        backend.cached_local_action_delta(0, 0, 0, (0, 0, 0))
    backend.refresh_biases()
    new = {
        key: backend.cached_local_action_delta(0, 0, key[0], key[1])
        for key in old
    }
    candidates = []
    for key in old:
        old_probability = min(1.0, math.exp(-old[key]))
        new_probability = min(1.0, math.exp(-new[key]))
        if abs(old_probability - new_probability) > 1e-7:
            candidates.append((old[key], new[key], 0.5 * (old_probability + new_probability)))
    assert candidates
    old_delta, new_delta, uniform = candidates[0]
    assert metropolis_accept(old_delta, uniform) != metropolis_accept(new_delta, uniform)


def test_checkpoint_restore_reproduces_next_jitted_trajectory() -> None:
    case = _case(2026073215, temperatures=3, pairs=2)
    bias = _bias(2026073216)
    uninterrupted = _backend(case, bias)
    uninterrupted.run_sweeps(1)
    checkpoint = uninterrupted.checkpoint_state()
    resumed = _backend(case, bias)
    resumed.restore_checkpoint_state(checkpoint)

    uninterrupted.run_sweeps(2)
    resumed.run_sweeps(2)

    for name in (
        "spins",
        "energies",
        "block_sums",
        "q_prime",
        "token_codes",
        "bias_values",
        "replica_ids",
        "swap_attempts",
        "swap_accepts",
    ):
        np.testing.assert_array_equal(
            resumed.checkpoint_state()[name],
            uninterrupted.checkpoint_state()[name],
        )
    assert resumed.sweep_count == uninterrupted.sweep_count == 3


def test_checkpoint_restore_rejects_invalid_round_trip_phase() -> None:
    case = _case(2026073311)
    bias = _bias(2026073312)
    corrupt = _backend(case, bias).checkpoint_state()
    corrupt["round_trip_phase"] = corrupt["round_trip_phase"].copy()
    corrupt["round_trip_phase"][0, 0] = 127

    with pytest.raises(ValueError, match="round-trip phase"):
        _backend(case, bias).restore_checkpoint_state(corrupt)


def test_checkpoint_rejects_float_prng_key_before_uint32_coercion() -> None:
    case = _case(2026073527)
    bias = _bias(2026073528)
    backend = _backend(case, bias)
    corrupt = backend.checkpoint_state()
    corrupt["local_key"] = corrupt["local_key"].astype(np.float64)

    with pytest.raises(TypeError, match="RNG.*uint32"):
        backend.restore_checkpoint_state(corrupt)


@pytest.mark.parametrize("counter", [0.5, True])
def test_checkpoint_rejects_noninteger_scalar_counter_before_coercion(
    counter: object,
) -> None:
    case = _case(2026073529)
    bias = _bias(2026073530)
    backend = _backend(case, bias)
    corrupt = backend.checkpoint_state()
    corrupt["sweep_count"] = counter

    with pytest.raises(TypeError, match="counter.*integer"):
        backend.restore_checkpoint_state(corrupt)


@pytest.mark.parametrize("name", ["spins", "q_prime"])
def test_checkpoint_rejects_float_binary_state_before_coercion(name: str) -> None:
    case = _case(2026073531)
    bias = _bias(2026073532)
    backend = _backend(case, bias)
    corrupt = backend.checkpoint_state()
    corrupt[name] = corrupt[name].astype(np.float64)

    with pytest.raises(TypeError, match="binary.*integer"):
        backend.restore_checkpoint_state(corrupt)


def test_checkpoint_rejects_wide_integer_spin_that_wraps_to_binary() -> None:
    case = _case(2026073533)
    bias = _bias(2026073534)
    backend = _backend(case, bias)
    corrupt = backend.checkpoint_state()
    corrupt["spins"] = corrupt["spins"].astype(np.int16)
    corrupt["spins"].flat[0] += 256

    with pytest.raises(ValueError, match="binary.*values"):
        backend.restore_checkpoint_state(corrupt)


def test_backend_rejects_disabled_jit() -> None:
    jax = pytest.importorskip("jax")
    previous = bool(jax.config.jax_disable_jit)
    jax.config.update("jax_disable_jit", True)
    try:
        with pytest.raises(RuntimeError, match="JIT"):
            JaxBiasedPairBackend(
                _case(2026073313),
                _bias(2026073314),
                required_platform=jax.default_backend(),
            )
    finally:
        jax.config.update("jax_disable_jit", previous)


def test_invalid_model_platform_and_stale_checkpoint_fail_closed() -> None:
    jax = pytest.importorskip("jax")
    case = _case(2026073217)
    cross = JaxBiasedPairBackend(
        case,
        _bias(2026073218, kind="cross"),
        required_platform=jax.default_backend(),
    )
    cross.run_sweeps(1)
    cross.assert_cache_consistent()
    with pytest.raises(ValueError, match="rank"):
        JaxBiasedPairBackend(
            case,
            _bias(2026073219, chi=3),
            required_platform=jax.default_backend(),
        )
    nonfinite = _bias(2026073220)
    nonfinite.tt.model.cores[2][0, 0, 0] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        JaxBiasedPairBackend(
            case,
            nonfinite,
            required_platform=jax.default_backend(),
        )
    wrong_platform = "cpu" if jax.default_backend() == "gpu" else "gpu"
    with pytest.raises(RuntimeError, match="required JAX platform"):
        JaxBiasedPairBackend(
            case,
            _bias(2026073221),
            required_platform=wrong_platform,
        )

    backend = _backend(case, _bias(2026073222))
    corrupt = backend.checkpoint_state()
    corrupt["token_codes"] = corrupt["token_codes"].copy()
    corrupt["token_codes"][0, 0, 0] ^= 1
    with pytest.raises(RuntimeError, match="stale cache"):
        _backend(case, _bias(2026073222)).restore_checkpoint_state(corrupt)
    with pytest.raises(ValueError, match="uniform"):
        backend.attempt_swaps(0, uniforms=np.full((1, 1), np.nan))


def test_resource_record_and_benchmark_parser_expose_gpu_boundary() -> None:
    backend = _backend(_case(2026073223), _bias(2026073224))
    backend.run_sweeps(1)
    resources = backend.resource_snapshot()
    assert resources["backend"] == "jax-biased-pair-pt"
    assert resources["float64_enabled"] is True
    assert resources["spin_proposals"] == 2 * 2 * 3**3
    assert resources.get("sweep_count") == backend.sweep_count == 1
    assert resources.get("generation") == backend.checkpoint_state()["generation"]
    assert resources["device"]
    args = build_benchmark_parser().parse_args(
        [
            "--length", "3",
            "--temperatures", "2",
            "--pairs", "1",
            "--sweeps", "1",
            "--route", "C",
            "--chi", "2",
            "--require-platform", "cpu",
            "--output", "/tmp/biased-benchmark.json",
        ]
    )
    assert args.route == "C"
    assert args.chi == 2
