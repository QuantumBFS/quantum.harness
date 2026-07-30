from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

from vmcrg_ref.issue28_protocol import (
    GaugeReferenceSpec,
    TERMINAL_CLASSIFICATIONS,
    canonical_operator_basis_record,
    create_gauge_reference,
    load_issue28_protocol,
    operator_basis_sha256,
)
from vmcrg_ref.neural_energy import D4EvenLocalMLP


PROTOCOL = Path("config/issue28_easy_v1.json")


def test_protocol_locks_physics_rounds_and_zero_linear_branch() -> None:
    protocol = load_issue28_protocol(PROTOCOL)
    assert protocol.physical.length == 45
    assert protocol.physical.coupling == 0.436
    assert protocol.physical.block_size == 3
    assert protocol.formal_rounds == 5
    assert len(protocol.formal_bundles) == 5
    np.testing.assert_array_equal(
        protocol.pure_linear_bias,
        np.zeros(13, dtype=np.float64),
    )
    assert protocol.neural.architecture == "D4EvenLocalMLP"
    assert protocol.neural.radius == 3
    assert protocol.neural.hidden == 32
    assert protocol.neural.feature_mode == "multiscale"
    assert protocol.ui_language == "zh-CN"
    assert protocol.terminal_classifications == TERMINAL_CLASSIFICATIONS


@pytest.mark.parametrize(
    ("section", "key", "replacement", "message"),
    [
        ("neural", "hidden", 31, "neural architecture"),
        ("gates", "tau_linear_noninferiority_upper", 1.2, "scientific gates"),
        ("objective", "minimum_bar_overlap", 0.04, "objective protocol"),
    ],
)
def test_protocol_rejects_changes_to_frozen_scientific_contract(
    tmp_path: Path,
    section: str,
    key: str,
    replacement: object,
    message: str,
) -> None:
    value = json.loads(PROTOCOL.read_text(encoding="ascii"))
    value[section][key] = replacement
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(value), encoding="ascii")
    with pytest.raises(ValueError, match=message):
        load_issue28_protocol(path)


def test_loaded_protocol_cannot_mutate_zero_branch_or_seed_streams() -> None:
    protocol = load_issue28_protocol(PROTOCOL)
    with pytest.raises(ValueError, match="read-only"):
        protocol.pure_linear_bias[0] = 1.0
    with pytest.raises(TypeError):
        protocol.formal_bundles[0].streams["validation"] = protocol.gauge.seed
    with pytest.raises(TypeError):
        protocol.gates["confidence_level"] = 0.90


def test_protocol_rejects_ui_or_terminal_classification_changes(tmp_path: Path) -> None:
    value = json.loads(PROTOCOL.read_text(encoding="ascii"))
    value["ui_language"] = "en-US"
    value["terminal_classifications"] = ["SUCCESS"]
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(value), encoding="ascii")
    with pytest.raises(ValueError, match="language|terminal classifications"):
        load_issue28_protocol(path)


def test_formal_bundle_streams_are_globally_unique_and_complete() -> None:
    protocol = load_issue28_protocol(PROTOCOL)
    records = [
        (stream.entropy, stream.spawn_key)
        for bundle in protocol.formal_bundles
        for stream in bundle.streams.values()
    ]
    assert len(records) == 5 * len(protocol.required_streams)
    assert len(records) == len(set(records))
    for bundle in protocol.formal_bundles:
        assert set(bundle.streams) == set(protocol.required_streams)


def test_protocol_rejects_duplicate_rng_stream(tmp_path: Path) -> None:
    value = json.loads(PROTOCOL.read_text(encoding="ascii"))
    first = value["formal_seed_bundles"][0]["streams"]
    first["autocorrelation"] = first["validation"].copy()
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(value), encoding="ascii")
    with pytest.raises(ValueError, match="duplicate RNG stream"):
        load_issue28_protocol(path)


def test_operator_basis_record_has_stable_hash_and_normalization() -> None:
    record = canonical_operator_basis_record()
    assert len(record["operators"]) == 13
    assert record["length"] == 15
    assert record["sign_convention"] == "S_shape=-sum_products"
    assert record["operators"][0]["vertices"] == [[0, 0], [1, 0]]
    assert record["operators"][0]["instances_per_site"] == 2
    assert len(operator_basis_sha256()) == 64
    assert operator_basis_sha256() == load_issue28_protocol(PROTOCOL).operator_basis_sha256


def test_gauge_reference_is_deterministic_and_hash_verified(tmp_path: Path) -> None:
    protocol = load_issue28_protocol(PROTOCOL)
    small = replace(
        protocol,
        gauge=GaugeReferenceSpec(
            length=5,
            configurations=4,
            dtype="int8",
            byte_order="|",
            seed=protocol.gauge.seed,
        ),
    )
    first = create_gauge_reference(small, tmp_path / "first")
    second = create_gauge_reference(small, tmp_path / "second")
    assert first["raw_array_sha256"] == second["raw_array_sha256"]
    assert first["shape"] == [4, 5, 5]
    with np.load(tmp_path / "first" / "gauge_reference.npz", allow_pickle=False) as archive:
        spins = archive["spins"]
    assert spins.dtype == np.int8
    assert np.all((spins == -1) | (spins == 1))


def test_neural_parameter_payload_is_detached_from_model() -> None:
    model = D4EvenLocalMLP.random(3, 4, 17, feature_mode="multiscale")
    payload = model.parameter_payload()
    payload["weight_out"][0] = 99.0
    assert model.weight_out[0] != 99.0
    assert int(payload["radius"]) == 3
    assert str(payload["feature_mode"]) == "multiscale"


def test_protocol_api_is_available_from_package_root() -> None:
    import vmcrg_ref

    assert vmcrg_ref.load_issue28_protocol is load_issue28_protocol
    assert vmcrg_ref.operator_basis_sha256 is operator_basis_sha256
