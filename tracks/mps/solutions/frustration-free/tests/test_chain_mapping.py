from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


SOLUTION_DIR = Path(__file__).parents[1]


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SOLUTION_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bath = _load_module("chain_mapping_test_bath", "bath.py")
chain = _load_module("chain_mapping", "chain_mapping.py")


def _canonical_json(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def synthetic_star_artifact(epsilon, coupling):
    artifact = bath.make_bath_artifact(
        gamma=0.1,
        bandwidth=1.0,
        n_bath=len(epsilon),
        frequency_grid=[-1.0, 0.0, 1.0],
    )
    artifact = copy.deepcopy(artifact)
    artifact["payload"]["epsilon"] = list(epsilon)
    artifact["payload"]["V"] = list(coupling)
    artifact["payload"]["parameters"]["n_bath"] = len(epsilon)
    artifact["sha256"] = hashlib.sha256(
        _canonical_json(artifact["payload"])
    ).hexdigest()
    return artifact


@pytest.mark.parametrize("n_bath", range(1, 7))
def test_mapping_has_binding_orthogonality_chain_and_coupling_invariants(n_bath):
    star = bath.make_bath_artifact(
        gamma=0.13,
        bandwidth=1.2,
        n_bath=n_bath,
        frequency_grid=[-1.2, 0.0, 1.2],
    )
    mapping = chain.derive_chain_mapping(star)
    payload = mapping["payload"]
    epsilon = np.asarray(star["payload"]["epsilon"])
    coupling = np.asarray(star["payload"]["V"])
    Q = np.asarray(payload["Q"])
    T = Q.T @ np.diag(epsilon) @ Q
    target = np.zeros(n_bath)
    target[0] = np.linalg.norm(coupling)

    assert Q.T @ Q == pytest.approx(np.eye(n_bath), abs=2e-13)
    assert T == pytest.approx(np.triu(np.tril(T, 1), -1), abs=2e-13)
    assert Q.T @ coupling == pytest.approx(target, abs=2e-13)
    assert payload["lambda"] == pytest.approx(np.linalg.norm(coupling))
    assert all(value >= 0.0 for value in payload["chain_hopping"])
    assert chain.verify_chain_mapping_artifact(mapping, star) is None


def test_zero_coupling_is_exact_identity_mapping():
    star = bath.make_bath_artifact(
        gamma=0.0,
        bandwidth=1.0,
        n_bath=6,
        frequency_grid=[-1.0, 0.0, 1.0],
    )
    payload = chain.derive_chain_mapping(star)["payload"]
    assert payload["lambda"] == 0.0
    assert payload["Q"] == np.eye(6).tolist()
    assert payload["chain_onsite"] == star["payload"]["epsilon"]
    assert payload["chain_hopping"] == [0.0] * 5


def test_repeated_energy_breakdown_uses_canonical_deflation(monkeypatch):
    star = synthetic_star_artifact(
        epsilon=[-0.5, -0.5, 0.5, 0.5],
        coupling=[0.5, 0.5, 0.0, 0.0],
    )
    monkeypatch.setattr(chain.bath, "verify_bath_artifact", lambda _artifact: None)

    first = chain.derive_chain_mapping(star)
    second = chain.derive_chain_mapping(star)

    assert first == second
    assert first["payload"]["deflation_boundaries"]
    assert any(
        first["payload"]["chain_hopping"][index] == 0.0
        for index in first["payload"]["deflation_boundaries"]
    )


def test_mapping_requires_a_verified_star_artifact():
    star = bath.make_bath_artifact(
        gamma=0.13,
        bandwidth=1.2,
        n_bath=3,
        frequency_grid=[-1.2, 0.0, 1.2],
    )
    star["payload"]["V"][0] = -1.0

    with pytest.raises(ValueError):
        chain.derive_chain_mapping(star)


def test_writer_emits_canonical_verified_mapping(tmp_path):
    star = bath.make_bath_artifact(
        gamma=0.13,
        bandwidth=1.2,
        n_bath=3,
        frequency_grid=[-1.2, 0.0, 1.2],
    )
    destination = tmp_path / "chain-mapping.json"

    mapping = chain.write_chain_mapping_json(destination, bath_artifact=star)

    assert destination.read_bytes() == _canonical_json(mapping) + b"\n"
    assert chain.verify_chain_mapping_artifact(mapping, star) is None
