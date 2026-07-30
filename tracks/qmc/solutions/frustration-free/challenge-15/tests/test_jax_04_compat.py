from __future__ import annotations

import importlib.util
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import optax
import pytest
from flax import serialization

from challenge15.model import ModelConfig, ProjectedPfaffianNQS, embed_rank
from challenge15.pfaffian import pfaffian
from challenge15.projector import project_m0
from challenge15.spec import SphereSpec


ROOT = Path(__file__).resolve().parents[1]
SMOKE_PATH = ROOT / "production" / "runtime" / "runtime_smoke.py"


def _load_smoke():
    spec = importlib.util.spec_from_file_location("challenge15_runtime_smoke", SMOKE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_candidate_versions_and_x64_cpu_backend():
    smoke = _load_smoke().runtime_smoke("cpu", "cpu", None)
    assert smoke.profile == "cpu"
    assert smoke.backend == "cpu"
    assert smoke.x64_enabled
    assert smoke.source_manifest_sha256 is None
    assert smoke.packages["jax"] == "0.4.38"
    assert smoke.packages["jaxlib"] == "0.4.38"
    assert "challenge15.allowed-runtime.v1" not in smoke.to_json()


@pytest.mark.parametrize(
    ("profile", "expected_backend", "backend", "platforms", "message"),
    [
        ("cpu", "gpu", "gpu", ("gpu",), "cpu profile"),
        ("cpu", "cpu", "cpu", ("cpu", "gpu"), "only CPU"),
        ("cuda12", "cpu", "cpu", ("cpu",), "cuda12 profile"),
        ("cuda12", "gpu", "gpu", ("cpu",), "GPU device"),
        ("cuda12", "gpu", "cpu", ("gpu",), "backend"),
    ],
)
def test_runtime_profile_enforces_backend_and_device_platforms(
    profile, expected_backend, backend, platforms, message
):
    with pytest.raises(RuntimeError, match=message):
        _load_smoke().validate_profile_devices(
            profile, expected_backend, backend, platforms
        )


def test_runtime_cuda_profile_accepts_reported_gpu_device():
    _load_smoke().validate_profile_devices("cuda12", "gpu", "gpu", ("gpu",))


def test_jit_complex128_pfaffian_value_and_jvp():
    matrix = jnp.asarray(
        [[0, 2 + 3j, 0, 0], [-2 - 3j, 0, 0, 0], [0, 0, 0, 5j], [0, 0, -5j, 0]],
        dtype=jnp.complex128,
    )
    tangent = jnp.asarray(
        [[0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
        dtype=jnp.complex128,
    )
    value, derivative = jax.jit(lambda x, dx: jax.jvp(pfaffian, (x,), (dx,)))(
        matrix, tangent
    )
    np.testing.assert_allclose(value, (2 + 3j) * 5j)
    np.testing.assert_allclose(derivative, 5j)
    assert value.dtype == jnp.complex128


def test_projection_model_rank_and_optimizer_serialization():
    spec = SphereSpec(2)
    spinors = jnp.asarray(
        [[1.0, 0.0], [1 / np.sqrt(2), 1j / np.sqrt(2)]],
        dtype=jnp.complex128,
    )
    projected = jax.jit(
        lambda points: project_m0(
            lambda value: value[0, 0] * value[1, 1]
            - value[0, 1] * value[1, 0],
            points,
            spec,
            0,
        )
    )(spinors)
    assert jnp.isfinite(projected)

    model = ProjectedPfaffianNQS(ModelConfig(rank=1, hidden_width=4, depth=0))
    variables = model.init(jax.random.key(0), spec, spinors, target_l=0)
    expanded = embed_rank(variables, 1, 2, key=jax.random.key(1))
    optimizer = optax.adam(1e-3)
    state = optimizer.init(expanded["params"])
    restored = serialization.from_bytes(state, serialization.to_bytes(state))
    assert jax.tree.structure(restored) == jax.tree.structure(state)
