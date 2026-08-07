from __future__ import annotations

import dataclasses
import json
import math
import os
from pathlib import Path

import jsonschema
import numpy as np
import pytest
import scipy.linalg
from scipy.sparse.linalg import ArpackNoConvergence

import challenge148.ed as ed_module
from challenge148.ed import (
    ThermalObservables,
    build_dense_hamiltonian_oracle,
    build_sparse_hamiltonian,
    exact_thermal_observables,
    sparse_ground_state_observables,
    thermal_observables_payload,
)
from challenge148.lattice import honeycomb_graph, triangular_graph
from challenge148.provenance import canonical_json

_PAULI_X = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.float64)
_PAULI_Z = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=np.float64)
_IDENTITY = np.eye(2, dtype=np.float64)


def _tensor_product(operators: list[np.ndarray]) -> np.ndarray:
    result = operators[0]
    for operator in operators[1:]:
        result = np.kron(result, operator)
    return result


def _single_site_operator(site_count: int, *, site: int, pauli: np.ndarray) -> np.ndarray:
    factors = [
        pauli if axis == site else _IDENTITY for axis in reversed(range(site_count))
    ]
    return _tensor_product(factors)


def _longitudinal_magnetization_operator(site_count: int) -> np.ndarray:
    return sum(
        _single_site_operator(site_count, site=site, pauli=_PAULI_Z)
        for site in range(site_count)
    ) / site_count


def _transverse_magnetization_operator(site_count: int) -> np.ndarray:
    return sum(
        _single_site_operator(site_count, site=site, pauli=_PAULI_X)
        for site in range(site_count)
    ) / site_count


def direct_expm_trace_observables(
    graph, *, coupling: float = 1.0, field: float, beta: float
) -> ThermalObservables:
    hamiltonian = build_dense_hamiltonian_oracle(graph, coupling=coupling, field=field)
    weights = scipy.linalg.expm(-beta * hamiltonian)
    partition = float(np.trace(weights))
    longitudinal = _longitudinal_magnetization_operator(graph.site_count)
    transverse = _transverse_magnetization_operator(graph.site_count)
    m2_operator = longitudinal @ longitudinal
    m4_operator = m2_operator @ m2_operator

    energy = float(np.trace(weights @ hamiltonian) / partition)
    m2 = float(np.trace(weights @ m2_operator) / partition)
    m4 = float(np.trace(weights @ m4_operator) / partition)
    transverse_magnetization = float(np.trace(weights @ transverse) / partition)
    return ThermalObservables(
        beta=beta,
        energy=energy,
        energy_density=energy / graph.site_count,
        transverse_magnetization=transverse_magnetization,
        m2=m2,
        m4=m4,
        binder_ratio=m2**2 / m4,
    )


def load_ed_result_schema() -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    schema_path = root / "schemas" / "ed-result.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_exact_thermal_trace_matches_direct_matrix_exponential():
    graph = honeycomb_graph(2)
    result = exact_thermal_observables(graph, coupling=1.0, field=2.0, beta=0.7)
    expected = direct_expm_trace_observables(graph, field=2.0, beta=0.7)
    assert dataclasses.astuple(result) == pytest.approx(dataclasses.astuple(expected))


def test_binder_ratio_uses_paper_definition():
    result = exact_thermal_observables(
        honeycomb_graph(2), coupling=1.0, field=2.0, beta=0.7
    )
    assert result.binder_ratio == pytest.approx(result.m2**2 / result.m4)


def test_high_temperature_pauli_moments():
    result = exact_thermal_observables(
        honeycomb_graph(2), coupling=1.0, field=2.0, beta=1e-9
    )
    assert result.m2 == pytest.approx(1 / 8, rel=1e-7)
    assert result.m4 == pytest.approx((3 * 8**2 - 2 * 8) / 8**4, rel=1e-7)


@pytest.mark.parametrize("beta", [0.0, -1.0, np.inf, np.nan])
def test_exact_thermal_observables_rejects_non_positive_or_non_finite_beta(beta):
    with pytest.raises(ValueError, match="beta must be a finite positive real number"):
        exact_thermal_observables(honeycomb_graph(2), coupling=1.0, field=2.0, beta=beta)


def test_exact_thermal_observables_rejects_bool_beta():
    with pytest.raises(TypeError, match="beta must be a real number"):
        exact_thermal_observables(honeycomb_graph(2), coupling=1.0, field=2.0, beta=True)


def test_exact_thermal_observables_rejects_large_graph_before_dense_work(monkeypatch):
    def fail_dense(*args, **kwargs):
        raise AssertionError("dense builder ran before site-count guard")

    monkeypatch.setattr(ed_module, "build_dense_hamiltonian_oracle", fail_dense)
    monkeypatch.setattr(ed_module.np.linalg, "eigh", fail_dense)
    with pytest.raises(MemoryError, match="site_count <= 12"):
        exact_thermal_observables(triangular_graph(4), coupling=1.0, field=2.0, beta=0.7)


def test_sparse_ground_state_matches_exact_low_temperature_limit():
    graph = honeycomb_graph(2)
    result = sparse_ground_state_observables(graph, coupling=1.0, field=2.0)
    expected = exact_thermal_observables(graph, coupling=1.0, field=2.0, beta=40.0)
    assert result.beta == math.inf
    assert result.energy == pytest.approx(expected.energy, abs=1e-10)
    assert result.energy_density == pytest.approx(expected.energy_density, abs=1e-10)
    assert result.transverse_magnetization == pytest.approx(
        expected.transverse_magnetization, abs=1e-10
    )
    assert result.m2 == pytest.approx(expected.m2, abs=1e-10)
    assert result.m4 == pytest.approx(expected.m4, abs=1e-10)
    assert result.binder_ratio == pytest.approx(expected.binder_ratio, abs=1e-10)


@pytest.mark.parametrize("field", [0.0, -0.5, np.inf, np.nan])
def test_sparse_ground_state_rejects_non_positive_or_non_finite_field(field):
    with pytest.raises(ValueError, match="field must be a finite positive real number"):
        sparse_ground_state_observables(honeycomb_graph(2), coupling=1.0, field=field)


def test_sparse_ground_state_rejects_bool_field():
    with pytest.raises(TypeError, match="field must be a real number"):
        sparse_ground_state_observables(honeycomb_graph(2), coupling=1.0, field=False)


def test_sparse_ground_state_reports_eigsh_non_convergence(monkeypatch):
    graph = honeycomb_graph(2)
    sparse = build_sparse_hamiltonian(graph, coupling=1.0, field=2.0)

    def fail_eigsh(*args, **kwargs):
        raise ArpackNoConvergence(
            "did not converge",
            np.array([], dtype=np.float64),
            np.empty((sparse.shape[0], 0), dtype=np.float64),
        )

    monkeypatch.setattr(ed_module, "build_sparse_hamiltonian", lambda *args, **kwargs: sparse)
    monkeypatch.setattr(ed_module.scipy.sparse.linalg, "eigsh", fail_eigsh)
    with pytest.raises(ValueError, match="eigsh failed to converge"):
        sparse_ground_state_observables(graph, coupling=1.0, field=2.0)


def test_sparse_ground_state_rejects_non_normalized_eigenvector(monkeypatch):
    graph = honeycomb_graph(2)
    dimension = 2**graph.site_count
    eigenvector = np.ones((dimension, 1), dtype=np.float64)
    original_builder = ed_module.build_sparse_hamiltonian

    monkeypatch.setattr(
        ed_module,
        "build_sparse_hamiltonian",
        lambda *args, **kwargs: original_builder(graph, coupling=1.0, field=2.0),
    )
    monkeypatch.setattr(
        ed_module.scipy.sparse.linalg,
        "eigsh",
        lambda *args, **kwargs: (np.array([-1.0], dtype=np.float64), eigenvector),
    )
    with pytest.raises(ValueError, match="ground-state eigenvector must be normalized"):
        sparse_ground_state_observables(graph, coupling=1.0, field=2.0)


def test_thermal_payload_serializes_ground_state_beta_as_null():
    result = sparse_ground_state_observables(honeycomb_graph(2), coupling=1.0, field=2.0)
    payload = thermal_observables_payload(result)
    assert payload["regime"] == "ground_state"
    assert payload["beta"] is None
    jsonschema.validate(payload, load_ed_result_schema())
    assert canonical_json(payload)


def test_thermal_payload_serializes_finite_temperature_beta():
    result = exact_thermal_observables(
        honeycomb_graph(2), coupling=1.0, field=2.0, beta=0.7
    )
    payload = thermal_observables_payload(result)
    assert payload["regime"] == "finite_temperature"
    assert payload["beta"] == pytest.approx(0.7)
    jsonschema.validate(payload, load_ed_result_schema())


def test_canonical_json_rejects_infinite_beta_payload():
    with pytest.raises(ValueError, match="canonical JSON encodable"):
        canonical_json(
            {
                "regime": "ground_state",
                "beta": math.inf,
                "energy": -1.0,
                "energy_density": -0.125,
                "transverse_magnetization": 0.0,
                "m2": 0.1,
                "m4": 0.01,
                "binder_ratio": 1.0,
            }
        )


@pytest.mark.skipif(
    os.environ.get("CHALLENGE148_RUN_EXPENSIVE_OBSERVABLES") != "1",
    reason="resource-gated sparse characterization",
)
@pytest.mark.parametrize(
    ("graph_builder", "length"),
    [
        pytest.param(triangular_graph, 4, id="triangular_L4"),
        pytest.param(honeycomb_graph, 3, id="honeycomb_L3"),
    ],
)
def test_sparse_ground_state_characterization_graphs(monkeypatch, graph_builder, length):
    def fail_dense(*args, **kwargs):
        raise AssertionError("dense exact-thermal path must stay unused")

    monkeypatch.setattr(ed_module, "build_dense_hamiltonian_oracle", fail_dense)
    monkeypatch.setattr(ed_module.np.linalg, "eigh", fail_dense)

    graph = graph_builder(length)
    result = sparse_ground_state_observables(graph, coupling=1.0, field=2.0)
    assert math.isfinite(result.energy)
    assert math.isfinite(result.energy_density)
    assert math.isfinite(result.transverse_magnetization)
    assert math.isfinite(result.m2)
    assert math.isfinite(result.m4)
    assert math.isfinite(result.binder_ratio)
