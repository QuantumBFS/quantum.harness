from __future__ import annotations

import hashlib
from types import SimpleNamespace

import numpy as np
import pytest

import challenge15.cli as cli
from challenge15.artifacts import publish_json_atomic, verify_artifact
from challenge15.production_schema import validate_envelope
from challenge15.provenance import (
    response_provenance,
    validate_response_provenance,
)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _response_inputs(tmp_path, *, nqs=False, cache=False):
    paths = {}
    for name in ("fixture", "configuration"):
        path = tmp_path / f"{name}.json"
        path.write_bytes(f"{name}-bytes".encode())
        paths[f"{name}_path"] = path
    oracle_name = "oracle_cache" if cache else "oracle_artifact"
    oracle = tmp_path / f"{oracle_name}.json"
    oracle.write_bytes(f"{oracle_name}-bytes".encode())
    paths[f"{oracle_name}_path"] = oracle
    if nqs:
        for name in ("nqs_generation", "nqs_checkpoint"):
            path = tmp_path / f"{name}.json"
            path.write_bytes(f"{name}-bytes".encode())
            paths[f"{name}_path"] = path
    return paths


@pytest.mark.parametrize("cache", [False, True])
def test_chiral_response_provenance_hashes_fixture_oracle_config_and_code(
    tmp_path,
    cache,
):
    paths = _response_inputs(tmp_path, cache=cache)
    provenance = response_provenance(**paths)

    assert provenance["input_sha256"]["fixture"] == _sha(paths["fixture_path"])
    assert provenance["input_sha256"]["configuration"] == _sha(
        paths["configuration_path"]
    )
    selected = "oracle_cache" if cache else "oracle_artifact"
    other = "oracle_artifact" if cache else "oracle_cache"
    assert provenance["input_sha256"][selected] == _sha(
        paths[f"{selected}_path"]
    )
    assert provenance["input_sha256"][other] is None
    assert provenance["execution_fingerprint"]["digest"]
    validate_response_provenance(provenance, **paths)


def test_chiral_response_provenance_binds_optional_nqs_generation_and_checkpoint(
    tmp_path,
):
    paths = _response_inputs(tmp_path, nqs=True)
    provenance = response_provenance(**paths)

    assert provenance["input_sha256"]["nqs_generation"] == _sha(
        paths["nqs_generation_path"]
    )
    assert provenance["input_sha256"]["nqs_checkpoint"] == _sha(
        paths["nqs_checkpoint_path"]
    )
    validate_response_provenance(provenance, **paths)


@pytest.mark.parametrize(
    "tamper",
    [
        "fixture_path",
        "oracle_artifact_path",
        "configuration_path",
        "nqs_generation_path",
        "nqs_checkpoint_path",
    ],
)
def test_chiral_response_provenance_rejects_tampered_input_artifacts(
    tmp_path,
    tamper,
):
    paths = _response_inputs(tmp_path, nqs=True)
    provenance = response_provenance(**paths)
    paths[tamper].write_bytes(paths[tamper].read_bytes() + b"-tampered")

    with pytest.raises(ValueError, match="provenance"):
        validate_response_provenance(provenance, **paths)


def test_chiral_response_provenance_rejects_partial_or_ambiguous_inputs(tmp_path):
    paths = _response_inputs(tmp_path)
    cache = tmp_path / "cache.json"
    cache.write_bytes(b"cache")
    with pytest.raises(ValueError, match="exactly one"):
        response_provenance(**paths, oracle_cache_path=cache)

    generation = tmp_path / "generation.json"
    generation.write_bytes(b"generation")
    with pytest.raises(ValueError, match="together"):
        response_provenance(**paths, nqs_generation_path=generation)


def _spectrum(particles):
    def channel(scale):
        member_weights = (0.6 * scale, 0.4 * scale)
        return SimpleNamespace(
            component_weights={component: 0.2 * scale for component in range(-2, 3)},
            poles=(
                SimpleNamespace(
                    energy=0.5,
                    degeneracy=2,
                    member_indices=(0, 1),
                    member_weights=member_weights,
                    weight=sum(member_weights),
                ),
            ),
            total_weight=scale,
            direct_sum_weight=scale,
            recovered_fraction=1.0,
            lowest_weight=scale,
            pole_fraction=1.0,
        )

    return SimpleNamespace(
        particles=particles,
        orientation=1,
        channels={"+": channel(1.0), "-": channel(2.0)},
        delta_weight=1.0,
        contrast=1.0 / 3.0,
        contrast_floor=1e-14,
        tensor_commutator_residual_max=0.0,
        adjoint_residual=0.0,
        reversal_residual_max=0.0,
        eigenpair_residual_max=0.0,
        initial_coefficient_sha256=None,
        oracle_cache_sha256="7" * 64,
    )


@pytest.mark.parametrize(
    "arguments",
    [
        ["response", "--output", "out"],
        ["response", "--particles", "2", "--oracle", "oracle", "--output", "out"],
        ["response", "--oracle", "oracle", "--checkpoint", "checkpoint", "--output", "out"],
        ["response", "--oracle", "oracle", "--generation", "generation", "--checkpoint", "checkpoint", "--rank", "1", "--seed", "2", "--output", "out"],
        ["response", "--oracle", "oracle", "--rank", "1", "--seed", "2", "--output", "out"],
        ["response", "--oracle", "oracle", "--checkpoint", "checkpoint", "--rank", "1", "--output", "out"],
        ["response", "--oracle", "oracle", "--checkpoint", "checkpoint", "--rank", "1", "--seed", "2", "--output", "out"],
    ],
)
def test_response_cli_rejects_ambiguous_modes_and_partial_checkpoint_triplets(arguments):
    with pytest.raises(SystemExit):
        cli.main(arguments)


@pytest.mark.parametrize("particles", [1, 9])
def test_response_cli_rejects_out_of_range_exact_sizes(tmp_path, particles):
    with pytest.raises(SystemExit):
        cli.main(
            [
                "response",
                "--particles",
                str(particles),
                "--output",
                str(tmp_path),
            ]
        )
    assert not (tmp_path / "response.json").exists()


def test_response_cli_mocked_n8_routes_through_exact_size_api_and_publishes(
    tmp_path, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        cli,
        "exact_chiral_spectrum_for_size",
        lambda particles: calls.append(particles) or _spectrum(particles),
    )

    assert cli.main(
        ["response", "--particles", "8", "--output", str(tmp_path)]
    ) == 0

    assert calls == [8]
    artifact = tmp_path / "response.json"
    payload = verify_artifact(artifact)
    assert validate_envelope(
        {"schema": "challenge15.chiral-response.v1", "payload": payload,
         "payload_sha256": cli.payload_sha256(payload)},
        "challenge15.chiral-response.v1",
    ) == payload
    assert payload["particles"] == 8
    assert payload["input_sha256"]["oracle_cache"] == "7" * 64
    assert payload["configuration"]["oracle_sha256"] == "7" * 64
    assert payload["input_identities"]["oracle"] == {
        "identity_role": "oracle",
        "artifact_schema": "challenge15.oracle-cache.v2",
        "sha256": "7" * 64,
    }
    assert set(payload["channels"]) == {"+", "-"}
    assert not list(tmp_path.glob("*.partial"))


def test_response_cli_oracle_reuse_loads_verified_cache_without_solving(
    tmp_path, monkeypatch
):
    oracle_path = tmp_path / "oracle.json"
    publish_json_atomic(oracle_path, {"schema": "challenge15.cli-oracle.v1"})
    output = tmp_path / "output"
    restored = SimpleNamespace(spec=SimpleNamespace(particles=8))
    calls = []
    monkeypatch.setattr(
        cli,
        "_load_response_oracle",
        lambda path: calls.append(("load", path)) or restored,
    )
    monkeypatch.setattr(
        cli,
        "solve_target_sectors",
        lambda spec: pytest.fail("oracle reuse must not solve"),
    )
    monkeypatch.setattr(
        cli,
        "solve_required_target_sectors_sparse",
        lambda spec: pytest.fail("oracle reuse must not solve"),
    )
    monkeypatch.setattr(
        cli,
        "_response_spectrum_from_oracle",
        lambda oracle: calls.append(("contract", oracle)) or _spectrum(8),
    )

    assert cli.main(
        ["response", "--oracle", str(oracle_path), "--output", str(output)]
    ) == 0
    assert calls == [("load", oracle_path), ("contract", restored)]
    assert verify_artifact(output / "response.json")["particles"] == 8


def test_response_cli_rejects_invalid_existing_output_without_residue(
    tmp_path, monkeypatch
):
    destination = tmp_path / "response.json"
    destination.write_text("not-json", encoding="utf-8")
    monkeypatch.setattr(
        cli, "exact_chiral_spectrum_for_size", lambda particles: _spectrum(particles)
    )

    with pytest.raises(SystemExit):
        cli.main(
            ["response", "--particles", "2", "--output", str(tmp_path)]
        )

    assert destination.read_text(encoding="utf-8") == "not-json"
    assert not list(tmp_path.glob("*.partial"))
    assert not list(tmp_path.glob("*.backup"))


def test_response_cli_fails_gates_before_publication(tmp_path, monkeypatch):
    failed = _spectrum(2)
    failed.tensor_commutator_residual_max = 2e-10
    monkeypatch.setattr(
        cli, "exact_chiral_spectrum_for_size", lambda particles: failed
    )

    with pytest.raises(SystemExit):
        cli.main(
            ["response", "--particles", "2", "--output", str(tmp_path)]
        )

    assert list(tmp_path.iterdir()) == []


def test_response_cli_mixed_mode_selects_identity_and_restores_parameters(
    tmp_path, monkeypatch
):
    oracle_path = tmp_path / "oracle.json"
    checkpoint_path = tmp_path / "checkpoint.json"
    generation_path = tmp_path / "generation.json"
    oracle_path.write_bytes(b"oracle-input")
    checkpoint_path.write_bytes(b"checkpoint-input")
    generation_path.write_bytes(b"generation-input")
    output = tmp_path / "output"
    sector = SimpleNamespace(
        isometry=np.asarray([[1.0 + 0.0j]]),
        eigenvectors=np.asarray([[1.0 + 0.0j]]),
    )
    oracle = SimpleNamespace(
        spec=SimpleNamespace(particles=2),
        exact_sector=lambda target_l: sector,
    )
    checkpoint = {
        "configuration": {"particles": 2},
        "records": [
            {"rank": 1, "seed": 3, "parameter_sha256": "a" * 64},
            {"rank": 2, "seed": 7, "parameter_sha256": "b" * 64},
        ],
    }
    selected = checkpoint["records"][1]
    initial = SimpleNamespace(coefficients=np.asarray([1.0 + 0.0j]))
    spectrum = _spectrum(2)
    spectrum.initial_coefficient_sha256 = "c" * 64
    calls = []
    monkeypatch.setattr(cli, "_load_response_oracle", lambda path: oracle)
    monkeypatch.setattr(
        cli,
        "_load_response_generation",
        lambda path, **identity: {
            "rank": 2,
            "seed": 7,
            "parameter_sha256": "b" * 64,
        },
    )
    monkeypatch.setattr(cli, "_validate_checkpoint", lambda path: checkpoint)
    monkeypatch.setattr(
        cli,
        "_restore_parameters",
        lambda spec, configuration, record: (
            calls.append(("restore", record)) or {"params": "restored"}
        ),
    )
    monkeypatch.setattr(
        cli,
        "nqs_determinant_state",
        lambda spec, parameters, restored_oracle, **kwargs: (
            calls.append(("state", parameters, kwargs)) or initial
        ),
    )
    monkeypatch.setattr(cli, "_response_families", lambda spec: {"families": True})
    monkeypatch.setattr(
        cli,
        "nqs_mixed_chiral_spectrum",
        lambda restored_oracle, families, state: spectrum,
    )

    assert cli.main(
        [
            "response",
            "--oracle",
            str(oracle_path),
            "--checkpoint",
            str(checkpoint_path),
            "--generation",
            str(generation_path),
            "--rank",
            "2",
            "--seed",
            "7",
            "--output",
            str(output),
        ]
    ) == 0

    assert calls[0] == ("restore", selected)
    assert calls[1][2] == {"target_l": 0, "determinant_block": 256}
    payload = verify_artifact(output / "response.json")
    assert payload["initial_state"]["kind"] == "nqs-determinant"
    assert payload["initial_state"]["coefficient_sha256"] == "c" * 64
    assert payload["input_sha256"]["nqs_checkpoint"] == _sha(checkpoint_path)
    assert payload["input_sha256"]["nqs_generation"] == _sha(generation_path)
    assert payload["input_sha256"]["parameter"] == "b" * 64
    assert payload["initial_state"] == {
        "kind": "nqs-determinant",
        "coefficient_sha256": "c" * 64,
        "estimator_scope": (
            "exact-finite-Hilbert-contraction-with-exact-ED-L2-finals"
        ),
        "rank": 2,
        "seed": 7,
        "checkpoint_sha256": _sha(checkpoint_path),
        "checkpoint_record_sha256": cli.payload_sha256(selected),
        "generation_sha256": _sha(generation_path),
        "parameter_sha256": "b" * 64,
        "determinant_block": 256,
        "exact_ground_overlap": 1.0,
    }


@pytest.mark.parametrize(
    "field,value",
    [("rank", 3), ("seed", 8), ("parameter_sha256", "9" * 64)],
)
def test_response_generation_must_match_checkpoint_identity(
    tmp_path, monkeypatch, field, value
):
    generation = {
        "rank": 2,
        "seed": 7,
        "parameter_sha256": "b" * 64,
    }
    generation[field] = value
    monkeypatch.setattr(cli, "validate_envelope", lambda path, schema: generation)

    with pytest.raises(ValueError, match="generation identity"):
        cli._load_response_generation(
            tmp_path / "generation.json",
            rank=2,
            seed=7,
            parameter_sha256="b" * 64,
        )


def test_response_cli_post_publication_schema_failure_restores_prior_bytes(
    tmp_path, monkeypatch
):
    destination = tmp_path / "response.json"
    monkeypatch.setattr(
        cli, "exact_chiral_spectrum_for_size", lambda particles: _spectrum(particles)
    )
    assert cli.main(
        ["response", "--particles", "2", "--output", str(tmp_path)]
    ) == 0
    previous_bytes = destination.read_bytes()
    original = cli._verify_response_artifact

    def fail_destination(path):
        payload = original(path)
        if path == destination:
            raise ValueError("injected response schema readback failure")
        return payload

    monkeypatch.setattr(cli, "_verify_response_artifact", fail_destination)
    with pytest.raises(SystemExit):
        cli.main(
            ["response", "--particles", "2", "--output", str(tmp_path)]
        )

    assert destination.read_bytes() == previous_bytes
    assert not list(tmp_path.glob("*.partial"))
    assert not list(tmp_path.glob("*.backup"))


def test_response_cli_rejects_tampered_oracle_before_contraction(
    tmp_path, monkeypatch
):
    oracle_path = tmp_path / "oracle.json"
    oracle_path.write_text('{"tampered":true}', encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "_response_spectrum_from_oracle",
        lambda oracle: pytest.fail("tampered oracle must not be contracted"),
    )

    with pytest.raises(SystemExit):
        cli.main(
            [
                "response",
                "--oracle",
                str(oracle_path),
                "--output",
                str(tmp_path / "output"),
            ]
        )

    assert not (tmp_path / "output").exists()
