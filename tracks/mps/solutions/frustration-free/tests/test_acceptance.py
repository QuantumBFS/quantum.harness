from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

import pytest
from jsonschema import Draft202012Validator


SOLUTION_DIR = Path(__file__).parents[1]
MODULE_PATH = SOLUTION_DIR / "acceptance.py"
SPEC = importlib.util.spec_from_file_location("challenge_81_acceptance", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
acceptance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acceptance)


def _canonical_json(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _chain_request_fixture(tmp_path):
    fixture = acceptance.acceptance_fixture()
    bath_path = tmp_path / "bath.json"
    bath_artifact = acceptance.bath.write_bath_json(
        bath_path,
        **fixture["bath"],
        frequency_grid=[-1.0, 0.0, 1.0],
    )
    mapping_path = tmp_path / "chain-mapping.json"
    mapping = acceptance.chain.write_chain_mapping_json(
        mapping_path, bath_artifact=bath_artifact
    )
    chain_fixture = acceptance._explicit_chain_fixture(mapping_path.read_bytes())
    return (
        bath_artifact,
        bath_path.read_text(encoding="utf-8"),
        mapping,
        mapping_path.read_bytes(),
        chain_fixture,
    )


def _solver_output(*, input_sha256="a" * 64):
    return {
        "schema_version": acceptance.RUNNER_SCHEMA_VERSION,
        "input_sha256": input_sha256,
        "input_payload_sha256": "b" * 64,
        "solver": {
            "name": "finite_bath_mps",
            "settings": {
                "time_step": 0.02,
                "cutoff": 1.0e-14,
                "maxdim": 256,
                "krylov_expansion_dim": 32,
                "bath_representation": "direct_star",
                "chain_mapping_sha256": None,
            },
        },
        "tau": [0.0, 0.5, 1.0],
        "observables": {
            "n_d": 1.0,
            "double_occupancy": 0.2,
            "G_up": [-0.5, -0.3, -0.5],
            "G_down": [-0.5, -0.3, -0.5],
        },
        "diagnostics": {
            "finite": True,
            "krylov_expansion_dim": 32,
            "bath_representation": "direct_star",
            "chain_mapping_sha256": None,
        },
        "provenance": {
            "runner": "finite_bath_mps_runner",
            "runner_version": "1.0.0",
            "julia_version": "1.11.6",
            "itensors_version": "0.9.30",
            "itensormps_version": "0.4.1",
            "project_toml_sha256": "1" * 64,
            "manifest_toml_sha256": "2" * 64,
            "runner_source_sha256": "3" * 64,
            "checkpoint_source_sha256": "8" * 64,
            "purification_source_sha256": "4" * 64,
            "observables_source_sha256": "5" * 64,
            "model_definition_sha256": "7" * 64,
            "chain_mapping_source_sha256": "9" * 64,
            "bath_artifact_file_sha256": "6" * 64,
            "bath_representation": "direct_star",
            "chain_mapping_sha256": None,
            "krylov_expansion_dim": 32,
            "expansion_policy": "explicit_global_krylov",
        },
    }


def _oracle():
    return {
        "payload": {
            "tau": [0.0, 0.5, 1.0],
            "observables": {
                "occupancy": {"total": 1.0},
                "double_occupancy": 0.2,
                "green_function": {
                    "up": [-0.5, -0.3, -0.5],
                    "down": [-0.5, -0.3, -0.5],
                },
            },
        }
    }


def test_comparison_uses_inclusive_threshold_and_returns_nonpassing_failure():
    output = _solver_output()
    oracle = _oracle()
    oracle["payload"]["observables"]["green_function"]["up"][1] = 0.0
    output["observables"]["G_up"][1] = 1.0e-6

    boundary = acceptance.compare_observables(oracle, output, threshold=1.0e-6)

    assert boundary["passed"] is True
    assert boundary["max_errors"]["G_up"] == pytest.approx(1.0e-6)
    assert boundary["global_max_error"] == pytest.approx(1.0e-6)

    output["observables"]["G_up"][1] = math.nextafter(1.0e-6, math.inf)
    failed = acceptance.compare_observables(oracle, output, threshold=1.0e-6)
    assert failed["passed"] is False
    assert failed["global_max_error"] > 1.0e-6


def test_binding_threshold_rejects_relaxation_and_allows_exact_default(tmp_path):
    assert (
        acceptance._validate_acceptance_threshold(acceptance.DEFAULT_THRESHOLD)
        == 1.0e-6
    )
    with pytest.raises(ValueError, match="must not exceed"):
        acceptance._validate_acceptance_threshold(1.0)
    with pytest.raises(ValueError, match="must not exceed"):
        acceptance.compare_observables(_oracle(), _solver_output(), threshold=1.0)
    with pytest.raises(ValueError, match="must not exceed"):
        acceptance.run_acceptance(output_directory=tmp_path, threshold=1.0)
    with pytest.raises(ValueError, match="must not exceed"):
        acceptance.main(["--threshold", "1"])


def test_convergence_record_documents_nonmonotonicity_and_scope_limit():
    study = acceptance.convergence_study_record()
    timestep_runs = study["controlled_runs"]["time_step"]
    assert timestep_runs == [
        {"time_step": 0.01, "global_max_error": 2.621836803884392e-6},
        {"time_step": 0.02, "global_max_error": 4.631353420214701e-8},
    ]
    assert study["observed_nonmonotonic"] is True
    assert "beta=16" in study["scope_limitation"]
    assert "beta=32" in study["scope_limitation"]
    assert "dedicated convergence investigation" in study["scope_limitation"]


def test_cthyb_scaffold_is_fail_closed_and_smoke_is_unambiguous():
    schema = json.loads(
        (SOLUTION_DIR / "triqs" / "cthyb-production.schema.json").read_text(
            encoding="utf-8"
        )
    )
    example = json.loads(
        (SOLUTION_DIR / "triqs" / "cthyb-production.example.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(example)
    assert example["artifact_type"] == "cthyb_production_configuration"
    assert example["production_ready"] is False
    assert example["scientific_comparison"] is False
    smoke = (SOLUTION_DIR / "triqs" / "smoke_test.py").read_text(encoding="utf-8")
    assert "SMOKE TEST ONLY" in smoke
    assert "NO SCIENTIFIC COMPARISON" in smoke


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda result: result.pop("observables"), "observables"),
        (lambda result: result["observables"].__setitem__("n_d", math.nan), "finite"),
        (lambda result: result.__setitem__("input_sha256", "c" * 64), "input SHA256"),
        (
            lambda result: result["solver"]["settings"].__setitem__(
                "time_step", 0.01
            ),
            "settings",
        ),
        (
            lambda result: result["solver"]["settings"].__setitem__(
                "krylov_expansion_dim", 0
            ),
            "settings",
        ),
        (
            lambda result: result["solver"]["settings"].__setitem__(
                "bath_representation", "chain"
            ),
            "settings",
        ),
        (
            lambda result: result["diagnostics"].__setitem__(
                "chain_mapping_sha256", "c" * 64
            ),
            "geometry",
        ),
        (lambda result: result.__setitem__("tau", [0.0, 1.0]), "tau"),
        (
            lambda result: result["provenance"].__setitem__("unknown", "claim"),
            "provenance",
        ),
    ],
)
def test_solver_output_verification_fails_closed(mutation, match):
    output = _solver_output()
    expected_provenance = copy.deepcopy(output["provenance"])
    mutation(output)

    with pytest.raises((TypeError, ValueError), match=match):
        acceptance.verify_mps_output(
            output,
            expected_input_sha256="a" * 64,
            expected_input_payload_sha256="b" * 64,
            expected_settings={
                "time_step": 0.02,
                "cutoff": 1.0e-14,
                "maxdim": 256,
                "krylov_expansion_dim": 32,
                "bath_representation": "direct_star",
                "chain_mapping_sha256": None,
            },
            expected_tau=[0.0, 0.5, 1.0],
            expected_provenance=expected_provenance,
        )


@pytest.mark.parametrize(
    "raw",
    [
        '{"value":1,"value":2}',
        '{"value":NaN}',
        '{"value":Infinity}',
        '{"value":-Infinity}',
    ],
)
def test_strict_json_boundary_rejects_duplicates_and_nonstandard_constants(raw):
    with pytest.raises(ValueError):
        acceptance.strict_json_loads(raw, name="test boundary")


def test_strict_json_boundary_enforces_size_and_depth_limits():
    oversized = b'"' + b"x" * acceptance.MAX_JSON_BYTES + b'"'
    with pytest.raises(ValueError, match="size|bytes"):
        acceptance.strict_json_loads(oversized, name="oversized")

    nested = "0"
    for _ in range(acceptance.MAX_JSON_DEPTH + 1):
        nested = "[" + nested + "]"
    with pytest.raises(ValueError, match="depth"):
        acceptance.strict_json_loads(nested, name="nested")


def test_mps_request_binds_canonical_path_free_checkpoint_identity():
    fixture = acceptance.acceptance_fixture()
    bath_json = '{"payload":{},"sha256":"' + "a" * 64 + '"}\n'

    request = acceptance._make_mps_request(bath_json, fixture)
    payload = acceptance.strict_json_loads(request["payload_json"])

    assert payload["schema_version"] == 3
    checkpoint = payload["checkpoint"]
    assert checkpoint == {
        "checkpoint_schema": 1,
        "writer_version": "1.0.0",
        "source_hashes": {
            "chain_mapping": acceptance._sha256_file(
                acceptance.CHAIN_MAPPING_SOURCE
            ),
            "checkpoint": acceptance._sha256_file(
                acceptance.JULIA_DIR / "finite_bath_checkpoint.jl"
            ),
            "model_definition": acceptance._sha256_file(
                acceptance.MODEL_DEFINITION
            ),
            "observables": acceptance._sha256_file(
                acceptance.JULIA_OBSERVABLES
            ),
            "purification": acceptance._sha256_file(
                acceptance.JULIA_PURIFICATION
            ),
            "runner": acceptance._sha256_file(acceptance.JULIA_RUNNER),
        },
        "project_toml_sha256": acceptance._sha256_file(
            acceptance.JULIA_DIR / "Project.toml"
        ),
        "manifest_toml_sha256": acceptance._sha256_file(
            acceptance.JULIA_DIR / "Manifest.toml"
        ),
    }
    assert all(
        not Path(value).is_absolute()
        for value in checkpoint.values()
        if isinstance(value, str)
    )
    assert request["payload_json"] == acceptance._request_canonical_text(payload)
    assert request["sha256"] == acceptance._sha256_bytes(
        request["payload_json"].encode("utf-8")
    )


def test_acceptance_request_defaults_to_exact_schema_three_direct_star_geometry():
    fixture = acceptance.acceptance_fixture()
    bath_json = '{"payload":{},"sha256":"' + "a" * 64 + '"}\n'

    request = acceptance._make_mps_request(bath_json, fixture)
    payload = acceptance.strict_json_loads(request["payload_json"])

    assert fixture["solver_settings"]["bath_representation"] == "direct_star"
    assert payload["schema_version"] == 3
    assert set(payload) == {
        "schema_version",
        "bath_artifact_json",
        "bath_artifact_file_sha256",
        "bath_geometry",
        "checkpoint",
        "model",
        "tau",
        "solver_settings",
    }
    assert payload["bath_geometry"] == {
        "representation": "direct_star",
        "chain_mapping_artifact_json": None,
        "chain_mapping_artifact_file_sha256": None,
    }
    assert set(payload["solver_settings"]) == {
        "time_step",
        "cutoff",
        "maxdim",
        "krylov_expansion_dim",
    }


def test_legacy_internal_request_call_defaults_to_direct_star():
    fixture = acceptance.acceptance_fixture()
    fixture["solver_settings"].pop("bath_representation")
    bath_json = '{"payload":{},"sha256":"' + "a" * 64 + '"}\n'

    request = acceptance._make_mps_request(bath_json, fixture)
    payload = acceptance.strict_json_loads(request["payload_json"])

    assert payload["bath_geometry"]["representation"] == "direct_star"
    assert payload["bath_geometry"]["chain_mapping_artifact_json"] is None


def test_explicit_chain_request_binds_canonical_mapping_oracle_and_provenance(
    tmp_path,
):
    bath_artifact, bath_json, mapping, mapping_bytes, fixture = (
        _chain_request_fixture(tmp_path)
    )

    request = acceptance._make_mps_request(bath_json, fixture)
    payload = acceptance.strict_json_loads(request["payload_json"])
    provenance = acceptance.expected_runner_provenance(
        julia_project=SOLUTION_DIR / "julia",
        bath_file_sha256=payload["bath_artifact_file_sha256"],
        bath_representation="chain",
        chain_mapping_sha256=mapping["sha256"],
        krylov_expansion_dim=payload["solver_settings"]["krylov_expansion_dim"],
    )
    oracle = acceptance.ed.make_oracle_artifact(
        bath_artifact=bath_artifact,
        bath_representation="chain",
        chain_mapping_artifact=mapping,
        U=fixture["model"]["U"],
        epsilon_d=fixture["model"]["epsilon_d"],
        mu=fixture["model"]["mu"],
        beta=fixture["model"]["beta"],
        tau=fixture["tau"],
    )

    assert fixture["solver_settings"]["bath_representation"] == "chain"
    assert payload["bath_geometry"] == {
        "representation": "chain",
        "chain_mapping_artifact_json": mapping_bytes.decode("utf-8"),
        "chain_mapping_artifact_file_sha256": hashlib.sha256(
            mapping_bytes
        ).hexdigest(),
    }
    assert acceptance.strict_json_loads(
        payload["bath_geometry"]["chain_mapping_artifact_json"]
    ) == mapping
    assert mapping["sha256"] == hashlib.sha256(
        _canonical_json(mapping["payload"])
    ).hexdigest()
    assert request["sha256"] == hashlib.sha256(
        request["payload_json"].encode("utf-8")
    ).hexdigest()
    assert mapping["payload"]["source_bath_sha256"] == bath_artifact["sha256"]
    assert acceptance._expected_output_settings(payload) == {
        **payload["solver_settings"],
        "bath_representation": "chain",
        "chain_mapping_sha256": mapping["sha256"],
    }
    assert provenance["bath_representation"] == "chain"
    assert provenance["chain_mapping_sha256"] == mapping["sha256"]
    assert provenance["chain_mapping_source_sha256"] == acceptance._sha256_file(
        acceptance.CHAIN_MAPPING_SOURCE
    )
    assert oracle["payload"]["parameters"]["bath_representation"] == "chain"
    assert oracle["payload"]["bath_input_sha256"] == bath_artifact["sha256"]
    assert oracle["payload"]["mapping_input"] == mapping
    assert oracle["payload"]["mapping_input_sha256"] == mapping["sha256"]


@pytest.mark.parametrize(
    "representation,mapping_bytes",
    [
        ("direct_star", b"mapping"),
        ("chain", None),
        ("tree", None),
    ],
)
def test_mps_request_rejects_inconsistent_geometry_combinations(
    representation, mapping_bytes
):
    fixture = acceptance.acceptance_fixture()
    fixture["solver_settings"]["bath_representation"] = representation
    if mapping_bytes is not None:
        fixture["chain_mapping_artifact_bytes"] = mapping_bytes
    bath_json = '{"payload":{},"sha256":"' + "a" * 64 + '"}\n'

    with pytest.raises((TypeError, ValueError), match="representation|mapping"):
        acceptance._make_mps_request(bath_json, fixture)


@pytest.mark.parametrize("tamper", ["noncanonical", "semantic"])
def test_explicit_chain_request_rejects_mapping_tampering(tmp_path, tamper):
    _bath, bath_json, mapping, mapping_bytes, fixture = _chain_request_fixture(
        tmp_path
    )
    if tamper == "noncanonical":
        fixture["chain_mapping_artifact_bytes"] = mapping_bytes + b"\n"
    else:
        corrupted = copy.deepcopy(mapping)
        corrupted["payload"]["chain_onsite"][0] += 0.01
        corrupted["sha256"] = hashlib.sha256(
            _canonical_json(corrupted["payload"])
        ).hexdigest()
        fixture["chain_mapping_artifact_bytes"] = (
            _canonical_json(corrupted) + b"\n"
        )

    with pytest.raises((TypeError, ValueError), match="canonical|mapping|replay"):
        acceptance._make_mps_request(bath_json, fixture)


@pytest.mark.parametrize(
    "name",
    [
        "project_toml_sha256",
        "manifest_toml_sha256",
        "runner_source_sha256",
        "checkpoint_source_sha256",
        "purification_source_sha256",
        "observables_source_sha256",
        "model_definition_sha256",
        "chain_mapping_source_sha256",
        "bath_artifact_file_sha256",
        "chain_mapping_sha256",
    ],
)
def test_provenance_hashes_must_match_python_recomputation(name):
    output = _solver_output()
    expected = copy.deepcopy(output["provenance"])
    output["provenance"][name] = "f" * 64

    with pytest.raises(ValueError, match=name):
        acceptance.verify_mps_output(
            output,
            expected_input_sha256="a" * 64,
            expected_input_payload_sha256="b" * 64,
            expected_settings={
                "time_step": 0.02,
                "cutoff": 1.0e-14,
                "maxdim": 256,
                "krylov_expansion_dim": 32,
                "bath_representation": "direct_star",
                "chain_mapping_sha256": None,
            },
            expected_tau=[0.0, 0.5, 1.0],
            expected_provenance=expected,
        )


def test_expected_runner_provenance_binds_checkpoint_source():
    expected = acceptance.expected_runner_provenance(
        julia_project=SOLUTION_DIR / "julia",
        bath_file_sha256="a" * 64,
        krylov_expansion_dim=32,
    )

    assert expected["checkpoint_source_sha256"] == acceptance._sha256_file(
        acceptance.JULIA_CHECKPOINT
    )
    assert expected["chain_mapping_source_sha256"] == acceptance._sha256_file(
        acceptance.CHAIN_MAPPING_SOURCE
    )
    assert expected["bath_representation"] == "direct_star"
    assert expected["chain_mapping_sha256"] is None


def _tree_bytes(directory):
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def _build_valid_acceptance_stage(root, name):
    stage = root / name
    stage.mkdir(parents=True)
    fixture = acceptance.acceptance_fixture()
    bath_path = stage / "bath.json"
    oracle_path = stage / "ed-oracle.json"
    input_path = stage / "mps-input.json"
    result_path = stage / "mps-result.json"
    artifact_path = stage / "acceptance.json"
    bath_artifact = acceptance.bath.write_bath_json(
        bath_path,
        **fixture["bath"],
        frequency_grid=[-1.0, -0.5, 0.0, 0.5, 1.0],
    )
    bath_json = bath_path.read_text(encoding="utf-8")
    request = acceptance._make_mps_request(bath_json, fixture)
    acceptance.atomic_write_json(input_path, request)
    request_payload = acceptance.strict_json_loads(request["payload_json"])
    model = request_payload["model"]
    tau = request_payload["tau"]
    settings = acceptance._expected_output_settings(request_payload)
    oracle = acceptance.ed.write_oracle_json(
        oracle_path,
        bath_artifact=bath_artifact,
        U=model["U"],
        epsilon_d=model["epsilon_d"],
        mu=model["mu"],
        beta=model["beta"],
        tau=tau,
    )
    oracle_observables = oracle["payload"]["observables"]
    provenance = acceptance.expected_runner_provenance(
        julia_project=SOLUTION_DIR / "julia",
        bath_file_sha256=request_payload["bath_artifact_file_sha256"],
        krylov_expansion_dim=settings["krylov_expansion_dim"],
    )
    solver_output = {
        "schema_version": acceptance.RUNNER_SCHEMA_VERSION,
        "input_sha256": acceptance._sha256_file(input_path),
        "input_payload_sha256": request["sha256"],
        "solver": {"name": "finite_bath_mps", "settings": settings},
        "tau": tau,
        "observables": {
            "n_d": oracle_observables["occupancy"]["total"],
            "double_occupancy": oracle_observables["double_occupancy"],
            "G_up": oracle_observables["green_function"]["up"],
            "G_down": oracle_observables["green_function"]["down"],
        },
        "diagnostics": {
            "finite": True,
            "krylov_expansion_dim": settings["krylov_expansion_dim"],
            "bath_representation": settings["bath_representation"],
            "chain_mapping_sha256": settings["chain_mapping_sha256"],
        },
        "provenance": {
            "runner": "finite_bath_mps_runner",
            "runner_version": "test",
            "julia_version": "test",
            "itensors_version": "test",
            "itensormps_version": "test",
            **provenance,
        },
    }
    acceptance.atomic_write_json(result_path, solver_output)
    comparison = acceptance.compare_observables(oracle, solver_output)
    payload = {
        "schema_version": acceptance.SCHEMA_VERSION,
        "passed": True,
        "comparison_passed": True,
        "ablation_passed": True,
        "threshold": comparison["threshold"],
        "effective_threshold": comparison["threshold"],
        "binding_max_threshold": acceptance.DEFAULT_THRESHOLD,
        "threshold_semantics": comparison["threshold_semantics"],
        "point_errors": comparison["point_errors"],
        "max_errors": comparison["max_errors"],
        "global_max_error": comparison["global_max_error"],
        "ablation": acceptance.compute_ablation_signals(fixture),
        "convergence_study": acceptance.convergence_study_record(),
        "tau": tau,
        "input": {
            "bath_sha256": bath_artifact["sha256"],
            "bath_artifact_file_sha256": request_payload[
                "bath_artifact_file_sha256"
            ],
            "mps_input_sha256": acceptance._sha256_file(input_path),
            "mps_input_payload_sha256": request["sha256"],
            "ed_oracle_sha256": oracle["sha256"],
            "mps_result_file_sha256": acceptance._sha256_file(result_path),
        },
        "model": model,
        "solver_settings": settings,
        "solver_provenance": solver_output["provenance"],
        "provenance": {
            "module": "acceptance",
            "module_version": acceptance.MODULE_VERSION,
            "python_version": acceptance.platform.python_version(),
            "numpy_version": acceptance.bath.np.__version__,
            "ed_module_version": acceptance.ed.MODULE_VERSION,
            "bath_module_version": acceptance.bath.MODULE_VERSION,
        },
    }
    artifact = acceptance._artifact(payload)
    acceptance.atomic_write_json(artifact_path, artifact)
    return stage, artifact


@pytest.mark.parametrize("failure", ["replace", "fsync"])
def test_directory_publication_failure_restores_every_old_byte(
    tmp_path, monkeypatch, failure
):
    destination = tmp_path / "acceptance"
    destination.mkdir()
    (destination / "acceptance.json").write_bytes(b"old acceptance")
    nested = destination / "nested"
    nested.mkdir()
    (nested / "mps-result.json").write_bytes(b"old mps")
    before = _tree_bytes(destination)

    staging = tmp_path / ".acceptance.stage"
    staging.mkdir()
    (staging / "acceptance.json").write_bytes(b"new acceptance")
    (staging / "mps-result.json").write_bytes(b"new mps")

    if failure == "replace":
        real_replace = acceptance.os.replace
        calls = 0

        def fail_second_replace(source, target):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected directory replace failure")
            return real_replace(source, target)

        monkeypatch.setattr(acceptance.os, "replace", fail_second_replace)
        match = "replace"
    else:
        calls = 0

        def fail_first_fsync(_directory):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("injected directory fsync failure")

        monkeypatch.setattr(acceptance, "_fsync_directory", fail_first_fsync)
        match = "fsync"

    with pytest.raises(OSError, match=match):
        acceptance.atomic_publish_directory(staging, destination)

    assert _tree_bytes(destination) == before


def test_versioned_acceptance_publication_is_immutable_and_updates_pointer(
    tmp_path,
):
    root = tmp_path / "acceptance"
    root.mkdir()
    staging, artifact = _build_valid_acceptance_stage(
        root, ".acceptance.stage-test"
    )

    published = acceptance.publish_acceptance_run(
        staging,
        root,
        artifact,
        julia_project=SOLUTION_DIR / "julia",
    )

    assert published == root / "runs" / f"acceptance-{artifact['sha256'][:16]}"
    pointer = json.loads((root / "current.json").read_text(encoding="utf-8"))
    assert pointer == {
        "schema_version": 1,
        "run_id": f"acceptance-{artifact['sha256'][:16]}",
        "acceptance_sha256": artifact["sha256"],
        "completion_sha256": json.loads(
            (published / "completion.json").read_text(encoding="utf-8")
        )["completion_sha256"],
        "relative_path": f"runs/acceptance-{artifact['sha256'][:16]}",
    }
    (root / "current.json").unlink()
    retry_stage, retry_artifact = _build_valid_acceptance_stage(
        root, ".acceptance.stage-retry"
    )
    assert retry_artifact == artifact
    assert (
        acceptance.publish_acceptance_run(
            retry_stage,
            root,
            artifact,
            julia_project=SOLUTION_DIR / "julia",
        )
        == published
    )
    assert (root / "current.json").is_file()
    assert list(root.glob(".acceptance.abandoned-stage-*"))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda run: (run / "mps-result.json").write_bytes(b"corrupt"),
        lambda run: (run / "ed-oracle.json").unlink(),
        lambda run: (run / "bath.json").write_bytes(b"corrupt"),
        lambda run: (run / "mps-input.json").write_bytes(b"corrupt"),
        lambda run: (run / "unexpected.json").write_text("{}", encoding="utf-8"),
        lambda run: (run / "acceptance.json").write_text(
            '{"payload":{},"sha256":"' + "0" * 64 + '"}', encoding="utf-8"
        ),
        lambda run: (run / "completion.json").write_text(
            '{"schema_version":1}', encoding="utf-8"
        ),
    ],
)
def test_existing_acceptance_run_corruption_never_advances_pointer_or_discards_stage(
    tmp_path, mutation
):
    root = tmp_path / "acceptance"
    root.mkdir()
    first_stage, artifact = _build_valid_acceptance_stage(
        root, ".acceptance.stage-first"
    )
    published = acceptance.publish_acceptance_run(
        first_stage,
        root,
        artifact,
        julia_project=SOLUTION_DIR / "julia",
    )
    pointer_before = (root / "current.json").read_bytes()
    mutation(published)
    fresh_stage, fresh_artifact = _build_valid_acceptance_stage(
        root, ".acceptance.stage-fresh"
    )

    with pytest.raises((OSError, TypeError, ValueError)):
        acceptance.publish_acceptance_run(
            fresh_stage,
            root,
            fresh_artifact,
            julia_project=SOLUTION_DIR / "julia",
        )

    assert fresh_stage.is_dir()
    assert (root / "current.json").read_bytes() == pointer_before


def test_acceptance_startup_archives_abandoned_stage(tmp_path):
    root = tmp_path / "acceptance"
    abandoned = root / ".acceptance.stage-dead"
    abandoned.mkdir(parents=True)
    (abandoned / "partial.log").write_text("preserve", encoding="utf-8")

    recovered = acceptance.recover_acceptance_state(root)

    assert len(recovered) == 1
    assert recovered[0].name.startswith(".acceptance.abandoned-stage-")
    assert (recovered[0] / "partial.log").read_text(encoding="utf-8") == "preserve"


def test_zero_exit_without_output_cannot_replay_old_acceptance(tmp_path, monkeypatch):
    destination = tmp_path / "acceptance"
    destination.mkdir()
    (destination / "acceptance.json").write_bytes(b"old accepted bytes")
    (destination / "mps-result.json").write_bytes(b"old solver bytes")
    before = _tree_bytes(destination)
    monkeypatch.setattr(
        acceptance.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0),
    )

    with pytest.raises(ValueError, match="did not create"):
        acceptance.run_acceptance(
            output_directory=destination,
            julia_executable=Path("/bin/true"),
            julia_project=SOLUTION_DIR / "julia",
        )

    assert _tree_bytes(destination) == before


def test_preexisting_mps_output_is_rejected_as_stale(tmp_path):
    output = tmp_path / "mps-result.json"
    output.write_bytes(b"stale")

    with pytest.raises(ValueError, match="pre-existing"):
        acceptance.invoke_julia_runner(
            ["/bin/true"], output_path=output
        )


def test_portable_julia_resolution_uses_env_then_path(tmp_path, monkeypatch):
    executable = tmp_path / "julia"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setenv("JULIA", str(executable))
    assert acceptance.resolve_julia(None) == executable.resolve()

    monkeypatch.delenv("JULIA")
    monkeypatch.setattr(acceptance.shutil, "which", lambda _name: str(executable))
    assert acceptance.resolve_julia(None) == executable.resolve()

    monkeypatch.setattr(acceptance.shutil, "which", lambda _name: None)
    with pytest.raises(FileNotFoundError, match="JULIA"):
        acceptance.resolve_julia(None)


def test_fixture_is_moderate_beta_and_has_nonvacuous_bath_ablation():
    fixture = acceptance.acceptance_fixture()
    beta = fixture["model"]["beta"]
    assert beta == 0.5
    assert fixture["tau"] == [0.0, beta / 4, beta / 2, 3 * beta / 4, beta]
    assert fixture["solver_settings"]["krylov_expansion_dim"] == 32

    signals = acceptance.compute_ablation_signals(fixture)
    assert signals["interior_green_safety_margin"] == (
        acceptance.INTERIOR_GREEN_SIGNAL_MARGIN
    )
    assert signals["passed"] is True
    for name in ("V_zero", "changed_epsilon"):
        variant = signals[name]
        assert set(variant["max_changes"]) == {
            "n_d",
            "double_occupancy",
            "G_up",
            "G_down",
        }
        assert set(variant["interior_green_max_changes"]) == {
            "G_up",
            "G_down",
        }
        assert variant["interior_green_signal"] > (
            acceptance.INTERIOR_GREEN_SIGNAL_MARGIN
        )
        assert variant["passed"] is True


@pytest.mark.skipif(
    os.environ.get("SKIP_CHALLENGE81_ACCEPTANCE") == "1"
    or not (os.environ.get("JULIA") or shutil.which("julia")),
    reason="Julia unavailable or acceptance explicitly opted out",
)
def test_real_julia_acceptance_gate_is_below_one_micro(tmp_path):
    result = acceptance.run_acceptance(
        output_directory=tmp_path,
        julia_executable=acceptance.resolve_julia(None),
        julia_project=SOLUTION_DIR / "julia",
        threshold=1.0e-6,
    )

    assert result["artifact"]["payload"]["passed"] is True
    assert result["artifact"]["payload"]["global_max_error"] <= 1.0e-6
    assert result["artifact"]["payload"]["effective_threshold"] == 1.0e-6
    assert result["artifact"]["payload"]["binding_max_threshold"] == 1.0e-6
    assert result["artifact"]["payload"]["convergence_study"] == (
        acceptance.convergence_study_record()
    )
    assert all(
        error <= 1.0e-6
        for name in ("G_up", "G_down")
        for error in result["artifact"]["payload"]["point_errors"][name]
    )
    published = acceptance.strict_json_loads(
        result["paths"]["acceptance"].read_text(encoding="utf-8"),
        name="acceptance artifact",
    )
    assert published == result["artifact"]
    assert published["payload"]["input"]["bath_sha256"] == (
        acceptance.strict_json_loads(
            result["paths"]["bath"].read_text(encoding="utf-8"),
            name="bath artifact",
        )["sha256"]
    )
    assert all(
        math.isfinite(value)
        for value in published["payload"]["max_errors"].values()
    )
