from __future__ import annotations

import subprocess
import sys
import textwrap

import jax
import jax.numpy as jnp
import numpy as np
import pytest
from flax.core import freeze, unfreeze

import challenge15
import challenge15.model as model_module
from challenge15.model import BatchedLogAmplitude, ModelConfig, ProjectedPfaffianNQS
from challenge15.spec import SphereSpec


BLOCK_LAYOUTS = ((1, 1), (2, 7), (4, 64))


def _random_spinors(particles: int, count: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    spinors = rng.normal(size=(count, particles, 2)) + 1j * rng.normal(
        size=(count, particles, 2)
    )
    return spinors / np.linalg.norm(spinors, axis=-1, keepdims=True)


def _model_and_variables(rank: int):
    spec = SphereSpec(4)
    model = ProjectedPfaffianNQS(
        ModelConfig(
            rank=rank,
            hidden_width=3,
            depth=0,
            token_width=2,
            fourier_order=1,
        )
    )
    real_walkers = _random_spinors(spec.particles, 3, 100 + rank)
    variables = model.init(jax.random.key(rank), spec, real_walkers[0], target_l=0)
    padded = np.concatenate(
        (
            real_walkers,
            np.full((1, spec.particles, 2), np.nan + 1j * np.nan),
        ),
        axis=0,
    )
    return spec, model, variables, jnp.asarray(padded)


def _safe_log(value):
    finite_nonzero = jnp.isfinite(value) & (value != 0)
    return jnp.where(finite_nonzero, jnp.log(jnp.abs(value)), -jnp.inf) + 1j * jnp.where(
        finite_nonzero, jnp.angle(value), 0.0
    )


def _scalar_logs(model, variables, spec, walkers):
    return jnp.stack(
        [
            jnp.stack(
                [
                    _safe_log(model.apply(variables, spec, walker, target_l=sector))
                    for sector in (0, 2)
                ]
            )
            for walker in walkers
        ]
    )


def _assert_tree_allclose(actual, expected, *, rtol, atol):
    assert jax.tree.structure(actual) == jax.tree.structure(expected)
    for actual_leaf, expected_leaf in zip(
        jax.tree.leaves(actual), jax.tree.leaves(expected), strict=True
    ):
        np.testing.assert_allclose(actual_leaf, expected_leaf, rtol=rtol, atol=atol)


def test_batched_interfaces_are_publicly_exported():
    assert challenge15.BatchedLogAmplitude is BatchedLogAmplitude
    assert hasattr(ProjectedPfaffianNQS, "apply_batched")


@pytest.mark.parametrize("rank", [1, 2])
@pytest.mark.parametrize(("carrier_block", "quadrature_block"), BLOCK_LAYOUTS)
def test_batched_values_match_scalar_path_and_mask_padding(
    rank, carrier_block, quadrature_block
):
    spec, model, variables, walkers = _model_and_variables(rank)
    result = model.apply_batched(
        variables,
        spec,
        walkers,
        sectors=jnp.asarray([0, 2], dtype=jnp.int32),
        valid_walkers=jnp.asarray([True, True, True, False]),
        carrier_block=carrier_block,
        quadrature_block=quadrature_block,
    )

    assert isinstance(result, BatchedLogAmplitude)
    assert result.log_amplitude.shape == (4, 2)
    assert result.log_amplitude.dtype == jnp.complex128
    assert result.finite_nonzero.shape == (4, 2)
    assert result.finite_nonzero.dtype == jnp.bool_
    expected = _scalar_logs(model, variables, spec, walkers[:3])
    np.testing.assert_allclose(
        result.log_amplitude[:3], expected, rtol=2e-9, atol=2e-10
    )
    np.testing.assert_allclose(
        jnp.exp(result.log_amplitude[:3]),
        jnp.exp(expected),
        rtol=2e-9,
        atol=2e-10,
    )
    np.testing.assert_array_equal(result.finite_nonzero[:3], jnp.isfinite(expected))
    np.testing.assert_array_equal(result.finite_nonzero[3], [False, False])
    np.testing.assert_array_equal(result.log_amplitude[3].real, [-jnp.inf, -jnp.inf])
    np.testing.assert_array_equal(result.log_amplitude[3].imag, [0.0, 0.0])
    assert not bool(jnp.any(jnp.isnan(result.log_amplitude)))


@pytest.mark.parametrize("rank", [1, 2])
def test_every_parameter_derivative_matches_scalar_log_amplitude(rank):
    spec, model, variables, walkers = _model_and_variables(rank)
    params = variables["params"]
    valid = jnp.asarray([True, True, True, False])

    def packed_batched(candidate):
        result = model.apply_batched(
            {"params": candidate},
            spec,
            walkers,
            sectors=jnp.asarray([0, 2], dtype=jnp.int32),
            valid_walkers=valid,
            carrier_block=2,
            quadrature_block=7,
        ).log_amplitude[:3]
        return jnp.concatenate((result.real.ravel(), result.imag.ravel()))

    def packed_scalar(candidate):
        result = _scalar_logs(model, {"params": candidate}, spec, walkers[:3])
        return jnp.concatenate((result.real.ravel(), result.imag.ravel()))

    _assert_tree_allclose(
        jax.jacrev(packed_batched)(params),
        jax.jacrev(packed_scalar)(params),
        rtol=2e-7,
        atol=2e-8,
    )


@pytest.mark.parametrize(("carrier_block", "quadrature_block"), BLOCK_LAYOUTS)
def test_chunking_walkers_is_equivalent_and_jittable(carrier_block, quadrature_block):
    spec, model, variables, walkers = _model_and_variables(2)
    sectors = jnp.asarray([0, 2], dtype=jnp.int32)
    valid = jnp.asarray([True, True, True, False])

    def evaluate(points, mask):
        return model.apply_batched(
            variables,
            spec,
            points,
            sectors=sectors,
            valid_walkers=mask,
            carrier_block=carrier_block,
            quadrature_block=quadrature_block,
        )

    whole = jax.jit(evaluate)(walkers, valid)
    chunks = [jax.jit(evaluate)(walkers[start : start + 2], valid[start : start + 2]) for start in (0, 2)]
    np.testing.assert_allclose(
        whole.log_amplitude,
        jnp.concatenate([chunk.log_amplitude for chunk in chunks]),
        rtol=2e-14,
        atol=2e-14,
    )
    np.testing.assert_array_equal(
        whole.finite_nonzero,
        jnp.concatenate([chunk.finite_nonzero for chunk in chunks]),
    )


def test_masked_nan_walker_has_no_parameter_gradient_bias():
    spec, model, variables, walkers = _model_and_variables(2)

    def loss(params, points):
        result = model.apply_batched(
            {"params": params},
            spec,
            points,
            sectors=jnp.asarray([0, 2], dtype=jnp.int32),
            valid_walkers=jnp.asarray([True, True, True, False]),
            carrier_block=2,
            quadrature_block=7,
        )
        return jnp.sum(result.log_amplitude[:3].real)

    with_padding = jax.grad(loss)(variables["params"], walkers)
    finite_padding = walkers.at[3].set(jnp.ones_like(walkers[3]))
    without_nan_padding = jax.grad(loss)(variables["params"], finite_padding)
    _assert_tree_allclose(with_padding, without_nan_padding, rtol=0.0, atol=0.0)
    assert all(bool(jnp.all(jnp.isfinite(leaf))) for leaf in jax.tree.leaves(with_padding))


def test_exact_zero_uses_canonical_log_sentinel_without_nan():
    spec, model, variables, walkers = _model_and_variables(2)
    mutable = unfreeze(variables)
    mutable["params"]["carrier_gates"] = jnp.zeros_like(
        mutable["params"]["carrier_gates"]
    )
    zero_variables = freeze(mutable)
    result = model.apply_batched(
        zero_variables,
        spec,
        walkers,
        sectors=jnp.asarray([0, 2], dtype=jnp.int32),
        valid_walkers=jnp.asarray([True, True, True, False]),
        carrier_block=4,
        quadrature_block=64,
    )
    np.testing.assert_array_equal(result.finite_nonzero, np.zeros((4, 2), dtype=bool))
    np.testing.assert_array_equal(result.log_amplitude.real, -np.inf)
    np.testing.assert_array_equal(result.log_amplitude.imag, 0.0)
    assert not bool(jnp.any(jnp.isnan(result.log_amplitude)))


def test_compiled_batched_contract_rejects_invalid_sector_values():
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import jax
                import jax.numpy as jnp
                import numpy as np
                from challenge15.model import ModelConfig, ProjectedPfaffianNQS
                from challenge15.spec import SphereSpec

                spec = SphereSpec(4)
                model = ProjectedPfaffianNQS(
                    ModelConfig(
                        rank=1,
                        hidden_width=2,
                        depth=0,
                        token_width=1,
                        fourier_order=1,
                    )
                )
                rng = np.random.default_rng(811)
                points = rng.normal(size=(1, 4, 2)) + 1j * rng.normal(
                    size=(1, 4, 2)
                )
                walkers = jnp.asarray(
                    points / np.linalg.norm(points, axis=-1, keepdims=True)
                )
                variables = model.init(
                    jax.random.key(1), spec, walkers[0], target_l=0
                )

                @jax.jit
                def evaluate(sectors):
                    return model.apply_batched(
                        variables,
                        spec,
                        walkers,
                        sectors=sectors,
                        valid_walkers=jnp.asarray([True]),
                        carrier_block=1,
                        quadrature_block=7,
                    ).log_amplitude

                evaluate(jnp.asarray([0, 0], dtype=jnp.int32)).block_until_ready()
                """
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "sectors must contain L=0 and L=2 exactly once" in completed.stderr


def test_principal_phase_maps_negative_real_signed_zero_to_positive_pi():
    negative_cut = jnp.asarray(complex(-1.0, -0.0), dtype=jnp.complex128)
    assert np.signbit(np.asarray(negative_cut).imag)

    phase = jax.jit(model_module._canonical_principal_phase)(negative_cut)

    assert float(phase) == np.pi


def test_reverse_mode_temporary_memory_is_not_scan_length_scaled():
    def compiled_temporary_bytes(particles, rank):
        spec = SphereSpec(particles)
        model = ProjectedPfaffianNQS(
            ModelConfig(
                rank=rank,
                hidden_width=2,
                depth=0,
                token_width=1,
                fourier_order=1,
            )
        )
        walker = jnp.asarray(_random_spinors(particles, 1, 900 + particles))
        variables = model.init(
            jax.random.key(particles), spec, walker[0], target_l=0
        )

        def loss(params):
            result = model.apply_batched(
                {"params": params},
                spec,
                walker,
                sectors=jnp.asarray([0, 2], dtype=jnp.int32),
                valid_walkers=jnp.asarray([True]),
                carrier_block=1,
                quadrature_block=7,
            )
            return jnp.sum(result.log_amplitude.real)

        compiled = jax.jit(jax.grad(loss)).lower(variables["params"]).compile()
        return compiled.memory_analysis().temp_size_in_bytes

    baseline = compiled_temporary_bytes(2, 1)
    more_quadrature_nodes = compiled_temporary_bytes(3, 1)
    more_carrier_blocks = compiled_temporary_bytes(2, 4)
    assert more_quadrature_nodes <= 3 * baseline
    assert more_carrier_blocks <= 3 * baseline


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda args: args.update(spinors=args["spinors"][..., 0]), "spinors"),
        (lambda args: args.update(sectors=jnp.asarray([0], dtype=jnp.int32)), "sectors"),
        (lambda args: args.update(valid_walkers=jnp.ones(3, dtype=bool)), "valid_walkers"),
        (lambda args: args.update(carrier_block=0), "carrier_block"),
        (lambda args: args.update(quadrature_block=True), "quadrature_block"),
    ],
)
def test_batched_contract_rejects_invalid_static_shapes(mutation, message):
    spec, model, variables, walkers = _model_and_variables(1)
    arguments = {
        "spinors": walkers,
        "sectors": jnp.asarray([0, 2], dtype=jnp.int32),
        "valid_walkers": jnp.asarray([True, True, True, False]),
        "carrier_block": 1,
        "quadrature_block": 7,
    }
    mutation(arguments)
    with pytest.raises(ValueError, match=message):
        model.apply_batched(variables, spec, **arguments)
