from __future__ import annotations

import hashlib

import jax
import jax.numpy as jnp
import numpy as np
import optax
from flax import serialization

from challenge15.model import (
    ModelConfig,
    ProjectedPfaffianNQS,
    embed_adam_state,
    embed_rank,
)
from challenge15.pfaffian import pfaffian
from challenge15.production_vmc import (
    ProductionVMCConfig,
    _array_bundle_bytes,
    _array_bundle_from_bytes,
    adam_init,
    adam_update,
    fixed_scientific_schedule,
)
from challenge15.projector import ProjectionGrid
from challenge15.spec import SphereSpec


jax.config.update("jax_enable_x64", True)

EXPECTED_GRID_SHA256 = {
    (2, 0): "d36ee2d62288b4e05a52b6c8c736bebdf2319df0b8f4de0e3b2cfcfc39415c38",
    (2, 2): "61936e07763fafdf314329e4ec7bdbab26e8aecfe3748104009ba3da0294bd2b",
    (3, 0): "796e1a64126b4655649aa95ac4be69ea850af98a6412fa13c4a60cca2a60c909",
    (3, 2): "ed5ba2ae9fd2d8ad36a192acbda61fc8e26f6e6fbaf96a33432b338f3538863e",
    (4, 0): "a6ae1e6c9319ad08aa7de8cffdf3fa2252894eb97f128ce3309fcb5b8e23688c",
    (4, 2): "ef99615ce73bc40702cdfc871329384a3e903a2c26c1b7752ac1fd627ec2675d",
}

EXPECTED_SHA256 = {
    "singular_minor_derivative": "81ad6d54d355bdfacf48cbfc546da9da76a3e9c6196f89574d692d06f0f293e0",
    "jax_rank1_prng": "5b5f5d5c8c938b788b0e06c5c08fc8babb78ea02da479b55a972e7c27fe1a0a2",
    "flax_rank1": "5e26ab411ad8e630ca4d487c4a9928cb464a3a2cae49b457166f93310cfb1177",
    "rank1_prefix": "c6a5a4c22cb709784e827a0e3558594887e0346788b4fcc3dc2580f705082088",
    "rank3_flax": "9a0472e65fd77db135984903c157e0e65149aac2e908d7fadbaa264ac704ea8c",
    "rank_growth_prng": "4b14dab996e34ae17c1a8270c1cd1a87f73a9c1bcd067b5bf1f914a124a69f5b",
    "optax_initial": "6140aee6a5a209152498658212cec58270fa73b4a5a79da1b630c5519cd0cacf",
    "optax_updated": "6baf6d4bd7c530081ce6357cfa9d24166de946c1c14bf467b8abffddf4594b30",
    "optax_embedded": "c743599e6b3532ebe0d27eb68233d5b739ad09462cc8001f0c5e9f15bd4dcb31",
    "functional_adam_initial": "a90de1597244990818a87b4f8759a6b3b84d422eeaee3a56a48d5565603b8070",
    "functional_adam_updated": "c29f337a2885d2b4c565b3bfbc7a59a9c668383517ef6fd4d33c87d5ea625ee1",
    "functional_parameters_updated": "6cb40de92b016ff9fe115f39bfc0cb990547fd68b8be560a8bb1ecce03087711",
    "fixed_schedule": "7bb041336ada537ad6e455cf2b341d6d6fa8d46486ed54b3fe9b670151539fb2",
    "tiny_snapshot": "5c650304121ea6448ad95e1f05c416ef0a1f03e48946bc08542c980b32f307ad",
}

EXPECTED_TINY_SNAPSHOT_HEX = (
    "000000000000001e7b226474797065223a223c633136222c227368617065223a"
    "5b322c325d7d000000000000f43f00000000000004c000000000000000000000"
    "000000000000000000000000084000000000000012400000000000001bc00000"
    "000000002040"
)

EXPECTED_PARAMETER_SHAPES = {
    "carrier_tokens": (1, 2),
    "carrier_gates": (1, 2),
    "shared_input/kernel": (7, 3),
    "shared_input/bias": (3,),
    "shared_residual_0/kernel": (3, 3),
    "shared_residual_0/bias": (3,),
    "shared_reduced_output/kernel": (3, 2),
    "shared_reduced_output/bias": (2,),
}

EXPECTED_SCHEDULE = (
    ("pilot", -1, 0),
    ("burn_in", -1, 0),
    ("thin", 0, 0),
    ("retain", 0, 1),
    ("update", 0, 2),
    ("refresh", 0, 3),
    ("reequilibrate", 0, 4),
    ("checkpoint", 0, 5),
)


def _sha256(encoded: bytes) -> str:
    return hashlib.sha256(encoded).hexdigest()


def _flatten(tree, prefix: str = ""):
    for key, value in tree.items():
        path = f"{prefix}/{key}" if prefix else key
        if hasattr(value, "items"):
            yield from _flatten(value, path)
        else:
            yield path, np.asarray(value)


def _tree_bytes(tree) -> bytes:
    encoded = bytearray()
    for path, value in _flatten(tree):
        contiguous = np.ascontiguousarray(value)
        encoded.extend(path.encode("utf-8"))
        encoded.extend(b"\0")
        encoded.extend(contiguous.dtype.str.encode("ascii"))
        encoded.extend(b"\0")
        encoded.extend(np.asarray(contiguous.shape, dtype="<i8").tobytes())
        encoded.extend(contiguous.tobytes(order="C"))
    return bytes(encoded)


def _functional_adam_bytes(state) -> bytes:
    return (
        int(state.step).to_bytes(8, "little", signed=False)
        + _tree_bytes(state.first_moment)
        + _tree_bytes(state.second_moment)
    )


def _rank1_fixture():
    config = ModelConfig(
        rank=1,
        hidden_width=3,
        depth=1,
        token_width=2,
        fourier_order=1,
        block_size=4,
    )
    spinors = np.asarray(
        [
            [1.0 + 0.0j, 0.0 + 0.0j],
            [0.0 + 0.0j, 1.0 + 0.0j],
        ],
        dtype=np.complex128,
    )
    key = jax.random.key(1729)
    variables = ProjectedPfaffianNQS(config).init(
        key, SphereSpec(2), jnp.asarray(spinors), target_l=0
    )
    return variables


def test_jax_oracle_freezes_singular_minor_and_grid_bytes():
    matrix = jnp.asarray(
        [
            [0, 2 + 3j, 0, 0],
            [-2 - 3j, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
        ],
        dtype=jnp.complex128,
    )
    tangent = jnp.asarray(
        [
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 1],
            [0, 0, -1, 0],
        ],
        dtype=jnp.complex128,
    )

    value, derivative = jax.jvp(pfaffian, (matrix,), (tangent,))

    np.testing.assert_array_equal(value, 0.0 + 0.0j)
    np.testing.assert_allclose(derivative, 2.0 + 3.0j, rtol=2e-12, atol=2e-12)
    assert _sha256(np.asarray(derivative).tobytes()) == (
        EXPECTED_SHA256["singular_minor_derivative"]
    )
    for particles in (2, 3, 4):
        for target_l in (0, 2):
            grid = ProjectionGrid.exact(SphereSpec(particles), target_l)
            encoded = b"".join(
                array.tobytes(order="C")
                for array in (
                    grid.alpha_nodes,
                    grid.alpha_weights,
                    grid.beta_nodes,
                    grid.beta_weights,
                )
            )
            assert _sha256(encoded) == EXPECTED_GRID_SHA256[(particles, target_l)]


def test_jax_oracle_freezes_parameter_layout_flax_and_rank_embedding_bytes():
    key_output = np.asarray(jax.random.normal(jax.random.key(1729), (8,), jnp.float64))
    assert _sha256(key_output.tobytes()) == EXPECTED_SHA256["jax_rank1_prng"]

    variables = _rank1_fixture()
    old_leaves = dict(_flatten(variables["params"]))
    assert {path: value.shape for path, value in old_leaves.items()} == (
        EXPECTED_PARAMETER_SHAPES
    )
    assert _sha256(serialization.to_bytes(variables)) == EXPECTED_SHA256["flax_rank1"]
    assert _sha256(_tree_bytes(variables["params"])) == EXPECTED_SHA256["rank1_prefix"]

    growth_key = jax.random.key(2718)
    growth_output = np.asarray(jax.random.normal(growth_key, (2, 2), jnp.float64))
    assert _sha256(growth_output.tobytes()) == EXPECTED_SHA256["rank_growth_prng"]
    expanded = embed_rank(variables, 1, 3, key=growth_key)
    expanded_leaves = dict(_flatten(expanded["params"]))
    for path, old_value in old_leaves.items():
        retained = (
            expanded_leaves[path][:1]
            if path in {"carrier_tokens", "carrier_gates"}
            else expanded_leaves[path]
        )
        assert retained.tobytes(order="C") == old_value.tobytes(order="C")
    np.testing.assert_array_equal(
        expanded_leaves["carrier_gates"][1:], np.zeros((2, 2), dtype=np.float64)
    )
    assert _sha256(serialization.to_bytes(expanded)) == EXPECTED_SHA256["rank3_flax"]


def test_jax_oracle_freezes_optax_and_functional_adam_bytes():
    variables = _rank1_fixture()
    params = variables["params"]
    optimizer = optax.adam(1e-3)
    optax_state = optimizer.init(params)
    assert _sha256(serialization.to_bytes(optax_state)) == EXPECTED_SHA256["optax_initial"]

    gradients = jax.tree.map(
        lambda value: jnp.asarray(
            np.full(np.asarray(value).shape, 0.125, dtype=np.float64)
        ),
        params,
    )
    _, updated_optax_state = optimizer.update(gradients, optax_state, params)
    assert _sha256(serialization.to_bytes(updated_optax_state)) == (
        EXPECTED_SHA256["optax_updated"]
    )

    expanded_params = embed_rank(params, 1, 3, key=jax.random.key(2718))
    embedded_state = embed_adam_state(
        updated_optax_state, expanded_params, old_rank=1, new_rank=3
    )
    assert _sha256(serialization.to_bytes(embedded_state)) == (
        EXPECTED_SHA256["optax_embedded"]
    )

    functional_params = {
        "a": np.asarray([1.5, -2.0], dtype=np.float64),
        "nested": {"b": np.asarray([[0.25], [3.0]], dtype=np.float64)},
    }
    functional_gradient = {
        "a": np.asarray([0.5, -0.25], dtype=np.float64),
        "nested": {"b": np.asarray([[1.25], [-0.75]], dtype=np.float64)},
    }
    initial = adam_init(functional_params)
    assert _sha256(_functional_adam_bytes(initial)) == (
        EXPECTED_SHA256["functional_adam_initial"]
    )
    updated_params, updated_state = adam_update(
        functional_params,
        functional_gradient,
        initial,
        learning_rate=1e-3,
    )
    assert _sha256(_functional_adam_bytes(updated_state)) == (
        EXPECTED_SHA256["functional_adam_updated"]
    )
    assert _sha256(_tree_bytes(updated_params)) == (
        EXPECTED_SHA256["functional_parameters_updated"]
    )


def test_jax_oracle_freezes_fixed_schedule_and_tiny_snapshot_payload():
    config = ProductionVMCConfig(
        steps=1,
        chains_per_sector=1,
        walkers_per_chain=1,
        pilot_sweeps=1,
        burn_in_sweeps=1,
        draws_per_update=1,
        thinning_sweeps=1,
        reequilibration_sweeps_after_update=1,
        checkpoint_interval_steps=1,
        final_evaluation_chains_per_sector=1,
        final_evaluation_burn_in_sweeps=1,
        final_evaluation_draws_per_chain=1,
        final_evaluation_thinning_sweeps=1,
        walker_microbatch=1,
        carrier_block=1,
        quadrature_block=1,
    )
    schedule = fixed_scientific_schedule(config)
    assert schedule == EXPECTED_SCHEDULE
    schedule_bytes = repr(schedule).encode("ascii")
    assert _sha256(schedule_bytes) == EXPECTED_SHA256["fixed_schedule"]

    snapshot_array = np.asarray(
        [[1.25 - 2.5j, -0.0 + 0.0j], [3.0 + 4.5j, -6.75 + 8.0j]],
        dtype=np.complex128,
    )
    payload = _array_bundle_bytes(snapshot_array)
    assert payload == bytes.fromhex(EXPECTED_TINY_SNAPSHOT_HEX)
    assert _sha256(payload) == EXPECTED_SHA256["tiny_snapshot"]
    np.testing.assert_array_equal(_array_bundle_from_bytes(payload), snapshot_array)
