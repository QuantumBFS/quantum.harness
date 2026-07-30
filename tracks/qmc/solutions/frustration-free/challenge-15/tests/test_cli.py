from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import challenge15.cli as cli_module
from challenge15.artifacts import publish_json_atomic, verify_artifact
from challenge15.provenance import execution_fingerprint
from challenge15.cli import (
    _checkpoint_coverage,
    _production_acceptance,
    _rank_records,
    _validate_checkpoint,
    configuration_sha256,
    load_compatible_checkpoint,
    main,
)


def test_configuration_hash_is_canonical_and_sensitive():
    first = {"particles": 2, "ranks": [1], "nested": {"b": 2, "a": 1}}
    reordered = {"nested": {"a": 1, "b": 2}, "ranks": [1], "particles": 2}

    assert configuration_sha256(first) == configuration_sha256(reordered)
    assert configuration_sha256(first) != configuration_sha256(
        {**first, "particles": 3}
    )


def test_execution_fingerprint_covers_code_lock_runtime_and_policy():
    fingerprint = execution_fingerprint()

    assert fingerprint["schema"] == "challenge15.execution-fingerprint.v1"
    assert fingerprint["digest"]
    assert fingerprint["source_hashes"]["pyproject.toml"]
    assert fingerprint["source_hashes"]["uv.lock"]
    for package in (
        "jax",
        "jaxlib",
        "flax",
        "optax",
        "numpy",
        "scipy",
        "sympy",
        "h5py",
    ):
        assert fingerprint["runtime"][package]
    assert fingerprint["policy"]["jax_enable_x64"] is True
    assert fingerprint["policy"]["backend"]
    assert fingerprint["policy"]["platform"]


def test_resume_rejects_incompatible_configuration(tmp_path):
    config = {"particles": 2, "ranks": [1], "seeds": [0], "steps": 1}
    checkpoint = tmp_path / "checkpoint.json"
    from challenge15.artifacts import publish_json_atomic

    publish_json_atomic(
        checkpoint,
        {
            "schema": "challenge15.train-checkpoint.v1",
            "configuration": config,
            "configuration_sha256": configuration_sha256(config),
            "completed": [],
            "records": [],
            "execution_fingerprint": execution_fingerprint(),
        },
    )

    assert load_compatible_checkpoint(checkpoint, config)["configuration"] == config
    with pytest.raises(ValueError, match="incompatible resume"):
        load_compatible_checkpoint(checkpoint, {**config, "steps": 2})


def test_oracle_and_verify_commands_publish_provenance_bound_artifact(tmp_path):
    config_path = tmp_path / "oracle.json"
    config_path.write_text(json.dumps({"particles": 2}), encoding="utf-8")
    output = tmp_path / "oracle-output"

    assert main(["oracle", "--config", str(config_path), "--output", str(output)]) == 0
    artifact = output / "result.json"
    payload = verify_artifact(artifact)

    assert payload["command"] == "oracle"
    assert payload["configuration_sha256"] == configuration_sha256({"particles": 2})
    assert payload["runtime_provenance"]["python"]
    assert payload["code_provenance"]["git_revision"]
    assert payload["input_provenance"]["configuration_path_sha256"]
    assert main(["verify", "--artifact", str(artifact)]) == 0
    assert not tuple(Path(output).glob("*.partial"))


def test_rank_doubling_checkpoint_records_nested_warm_start(tmp_path):
    config = {
        "particles": 2,
        "ranks": [1, 2],
        "seeds": [5],
        "steps": 1,
        "batch_size": 1,
        "hidden_width": 4,
        "depth": 0,
        "token_width": 2,
        "fourier_order": 1,
    }
    config_path = tmp_path / "train.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    output = tmp_path / "train-output"

    assert main(["train", "--config", str(config_path), "--output", str(output)]) == 0
    checkpoint = verify_artifact(output / "checkpoint.json")
    lower, upper = checkpoint["records"]

    assert upper["nested_from_rank"] == lower["rank"]
    assert upper["parent_parameter_sha256"] == lower["parameter_sha256"]
    assert upper["rank_growth_prng"]
    assert upper["initial_parameter_sha256"] != lower["parameter_sha256"]


@pytest.fixture(scope="module")
def valid_checkpoint(tmp_path_factory):
    root = tmp_path_factory.mktemp("valid-checkpoint")
    config = {
        "particles": 2,
        "ranks": [1, 2],
        "seeds": [5],
        "steps": 1,
        "batch_size": 1,
        "hidden_width": 4,
        "depth": 0,
        "token_width": 2,
        "fourier_order": 1,
    }
    config_path = root / "train.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    output = root / "output"
    assert main(["train", "--config", str(config_path), "--output", str(output)]) == 0
    return config, output / "checkpoint.json"


def _republish(tmp_path, payload, name="checkpoint.json"):
    path = tmp_path / name
    publish_json_atomic(path, payload)
    return path


def test_checkpoint_recomputes_stored_configuration_digest(
    tmp_path, valid_checkpoint
):
    config, path = valid_checkpoint
    payload = deepcopy(verify_artifact(path))
    payload["configuration"]["steps"] = 2
    tampered = _republish(tmp_path, payload)

    with pytest.raises(ValueError, match="stored configuration SHA256"):
        load_compatible_checkpoint(
            tampered, {**config, "steps": 2}
        )


@pytest.mark.parametrize(
    "field",
    ["parameters_base64", "optimizer_state_base64"],
)
def test_checkpoint_rejects_tampered_serialized_state(
    tmp_path, valid_checkpoint, field
):
    config, path = valid_checkpoint
    payload = deepcopy(verify_artifact(path))
    payload["records"][0][field] = payload["records"][0][field][:-4] + "AAAA"
    tampered = _republish(tmp_path, payload, f"{field}.json")

    with pytest.raises(ValueError, match="SHA256"):
        load_compatible_checkpoint(tampered, config)


@pytest.mark.parametrize("location", ["checkpoint", "record"])
def test_checkpoint_rejects_tampered_execution_fingerprint(
    tmp_path, valid_checkpoint, location
):
    config, path = valid_checkpoint
    payload = deepcopy(verify_artifact(path))
    target = (
        payload["execution_fingerprint"]
        if location == "checkpoint"
        else payload["records"][0]["execution_fingerprint"]
    )
    target["digest"] = "0" * 64
    tampered = _republish(tmp_path, payload, f"{location}.json")

    with pytest.raises(ValueError, match="execution fingerprint"):
        load_compatible_checkpoint(tampered, config)


@pytest.mark.parametrize(
    "tamper",
    [
        "source",
        "python",
        "jax",
        "jaxlib",
        "flax",
        "optax",
        "numpy",
        "scipy",
        "sympy",
        "h5py",
        "policy",
    ],
)
def test_checkpoint_rejects_stale_current_source_or_runtime_fingerprint(
    tmp_path, valid_checkpoint, monkeypatch, tamper
):
    config, path = valid_checkpoint
    stale = deepcopy(execution_fingerprint())
    if tamper == "source":
        stale["source_hashes"]["src/challenge15/model.py"] = "f" * 64
    elif tamper == "policy":
        stale["policy"]["backend"] = "tampered"
    else:
        stale["runtime"][tamper] = "0.0.0-tampered"
    unsigned = {key: value for key, value in stale.items() if key != "digest"}
    stale["digest"] = hashlib.sha256(
        json.dumps(
            unsigned,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    monkeypatch.setattr(cli_module, "execution_fingerprint", lambda: stale)

    with pytest.raises(ValueError, match="stale execution fingerprint"):
        load_compatible_checkpoint(path, config)


def test_checkpoint_rejects_tampered_lineage(tmp_path, valid_checkpoint):
    config, path = valid_checkpoint
    payload = deepcopy(verify_artifact(path))
    payload["records"][1]["parent_parameter_sha256"] = "0" * 64
    tampered = _republish(tmp_path, payload)

    with pytest.raises(ValueError, match="lineage"):
        load_compatible_checkpoint(tampered, config)

    with pytest.raises(SystemExit) as caught:
        main(["verify", "--artifact", str(tampered)])
    assert caught.value.code != 0


def test_checkpoint_rejects_completed_record_inconsistency(
    tmp_path, valid_checkpoint
):
    config, path = valid_checkpoint
    payload = deepcopy(verify_artifact(path))
    payload["completed"] = payload["completed"][:-1]
    tampered = _republish(tmp_path, payload)

    with pytest.raises(ValueError, match="completed"):
        load_compatible_checkpoint(tampered, config)


@pytest.mark.parametrize("mutation", ["duplicate", "unexpected"])
def test_evaluate_rejects_duplicate_or_unexpected_records(
    tmp_path, valid_checkpoint, mutation
):
    _, path = valid_checkpoint
    payload = deepcopy(verify_artifact(path))
    if mutation == "duplicate":
        payload["records"].append(deepcopy(payload["records"][0]))
        payload["completed"].append(payload["completed"][0])
    else:
        payload["records"][0]["seed"] = 999
        payload["completed"][0] = [payload["records"][0]["rank"], 999]
    tampered = _republish(tmp_path, payload)

    with pytest.raises(SystemExit) as caught:
        main(
            [
                "evaluate",
                "--checkpoint",
                str(tampered),
                "--output",
                str(tmp_path / "evaluation"),
            ]
        )
    assert caught.value.code != 0


def _install_exact_mocks(monkeypatch):
    monkeypatch.setattr(
        cli_module,
        "solve_target_sectors",
        lambda _spec: SimpleNamespace(
            energy_l0=1.0,
            energy_l2=1.2,
            gap=0.2,
            m_zero_dimension=1,
        ),
    )
    metrics = SimpleNamespace(
        norm_l0=1.0,
        norm_l2=1.0,
        energy_l0=1.0,
        energy_l2=1.2,
        h_variance_l0=0.0,
        h_variance_l2=0.0,
        overlap_l0=1.0,
        overlap_l2=1.0,
        l2_residual_l0=0.0,
        l2_residual_l2=0.0,
        quadrature_coefficient_relative_change_l0=0.0,
        quadrature_coefficient_relative_change_l2=0.0,
        quadrature_energy_relative_change_l0=0.0,
        quadrature_energy_relative_change_l2=0.0,
        projected_span_rank_l0=1,
        projected_span_rank_l2=1,
        quadrature_orders_l0=((3, 3), (5, 5)),
        quadrature_orders_l2=((3, 3), (5, 5)),
    )
    monkeypatch.setattr(cli_module, "evaluate_exact_nqs", lambda *_args: metrics)


def test_interrupted_four_of_five_evaluation_is_explicitly_pending(
    tmp_path, valid_checkpoint, monkeypatch
):
    _, path = valid_checkpoint
    source = verify_artifact(path)
    record = deepcopy(source["records"][0])
    config = {
        **source["configuration"],
        "ranks": [1],
        "seeds": [0, 1, 2, 3, 4],
    }
    records = []
    for seed in config["seeds"][:-1]:
        candidate = deepcopy(record)
        candidate["seed"] = seed
        records.append(candidate)
    payload = {
        **source,
        "configuration": config,
        "configuration_sha256": configuration_sha256(config),
        "records": records,
        "completed": [[1, seed] for seed in config["seeds"][:-1]],
    }
    interrupted = _republish(tmp_path, payload)
    _install_exact_mocks(monkeypatch)
    output = tmp_path / "evaluation"

    assert main(
        [
            "evaluate",
            "--checkpoint",
            str(interrupted),
            "--output",
            str(output),
        ]
    ) == 0
    evaluation = verify_artifact(output / "evaluation.json")

    assert evaluation["production_accepted"] is False
    assert evaluation["coverage_gate"]["passed"] is False
    assert evaluation["coverage_gate"]["missing"] == [[1, 4]]


def test_complete_four_of_five_seed_gate_can_pass_but_partial_cannot():
    convergence = SimpleNamespace(accepted=True)
    complete = {"passed": True}
    partial = {"passed": False}

    assert _production_acceptance(
        complete,
        convergence,
        configured_seed_count=5,
        passing_seed_count=4,
    )
    assert not _production_acceptance(
        partial,
        convergence,
        configured_seed_count=5,
        passing_seed_count=4,
    )


def test_missing_rank_coverage_is_pending(valid_checkpoint):
    _, path = valid_checkpoint
    payload = deepcopy(verify_artifact(path))
    payload["records"] = payload["records"][:1]
    payload["completed"] = payload["completed"][:1]

    coverage = _checkpoint_coverage(payload)

    assert coverage["passed"] is False
    assert coverage["missing"] == [[2, 5]]


def test_missing_rank_evaluation_cannot_be_accepted(
    tmp_path, valid_checkpoint, monkeypatch
):
    _, path = valid_checkpoint
    payload = deepcopy(verify_artifact(path))
    payload["records"] = payload["records"][:1]
    payload["completed"] = payload["completed"][:1]
    partial = _republish(tmp_path, payload)
    _install_exact_mocks(monkeypatch)
    output = tmp_path / "evaluation"

    assert main(
        [
            "evaluate",
            "--checkpoint",
            str(partial),
            "--output",
            str(output),
        ]
    ) == 0
    evaluation = verify_artifact(output / "evaluation.json")

    assert evaluation["production_accepted"] is False
    assert evaluation["coverage_gate"]["missing"] == [[2, 5]]
    assert evaluation["rank_convergence"]["accepted"] is False


def test_exact_rank_records_use_zero_sigma_and_identical_seed_sets():
    evaluations = [
        {
            "rank": rank,
            "seed": seed,
            "energy_l0": 1.0 + seed * 0.1 + rank * 1e-6,
            "energy_l2": 1.2 + seed * 0.1 + rank * 1e-6,
            "finite_size_l2_gap": 0.2,
            "overlap_l0": 0.999,
            "overlap_l2": 0.999,
        }
        for rank in (1, 2, 4)
        for seed in (0, 1)
    ]

    records = _rank_records(evaluations, [1, 2, 4])

    assert all(record.sigma_diff_l0 == 0 for record in records)
    assert all(record.sigma_diff_l2 == 0 for record in records)
    assert all(record.sigma_diff_gap == 0 for record in records)

    with pytest.raises(ValueError, match="identical paired seed sets"):
        _rank_records(evaluations[:-1], [1, 2, 4])


def test_invalid_cli_invocations_have_nonzero_process_codes(tmp_path):
    import subprocess
    import sys

    completed = subprocess.run(
        [sys.executable, "-m", "challenge15.cli", "evaluate", "--output", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "missing required configuration field: checkpoint" in completed.stderr


def test_training_cli_rejects_acceptance_tolerance_overrides(tmp_path):
    config = {
        "particles": 2,
        "ranks": [1],
        "seeds": [0],
        "steps": 1,
        "energy_tolerance": 1.0,
    }
    config_path = tmp_path / "invalid.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(SystemExit) as caught:
        main(
            [
                "train",
                "--config",
                str(config_path),
                "--output",
                str(tmp_path / "output"),
            ]
        )

    assert caught.value.code != 0


def test_report_recomputes_acceptance_instead_of_trusting_boolean(tmp_path):
    evaluation = {
        "schema": "challenge15.exact-evaluation.v1",
        "production_accepted": True,
        "coverage_gate": {
            "passed": False,
            "expected": [[1, 0]],
            "present": [],
            "missing": [[1, 0]],
        },
        "rank_convergence": {"accepted": True},
        "seed_gate": {"passed": True},
        "evaluations": [],
        "oracle_summary": {"finite_size_l2_gap": 0.2},
    }
    evaluation_path = tmp_path / "evaluation.json"
    publish_json_atomic(evaluation_path, evaluation)
    output = tmp_path / "report"

    with pytest.raises(SystemExit) as caught:
        main(
            [
                "report",
                "--evaluation",
                str(evaluation_path),
                "--output",
                str(output),
            ]
        )
    assert caught.value.code != 0


def test_report_rejects_true_summaries_with_failed_individual_gate(
    tmp_path, valid_checkpoint, monkeypatch
):
    _, checkpoint = valid_checkpoint
    _install_exact_mocks(monkeypatch)
    evaluation_output = tmp_path / "evaluation-output"
    assert main(
        [
            "evaluate",
            "--checkpoint",
            str(checkpoint),
            "--output",
            str(evaluation_output),
        ]
    ) == 0
    evaluation = deepcopy(verify_artifact(evaluation_output / "evaluation.json"))
    evaluation["coverage_gate"]["passed"] = True
    evaluation["rank_convergence"]["accepted"] = True
    evaluation["seed_gate"]["passed"] = True
    evaluation["production_accepted"] = True
    evaluation["evaluations"][0]["gates"]["energy_l0"] = False
    evaluation["evaluations"][0]["accepted"] = True
    forged = _republish(tmp_path, evaluation, "forged-evaluation.json")

    with pytest.raises(SystemExit) as caught:
        main(
            [
                "report",
                "--evaluation",
                str(forged),
                "--output",
                str(tmp_path / "report-output"),
            ]
        )
    assert caught.value.code != 0


def test_cross_size_prerequisite_is_required_and_particle_bound(
    tmp_path, monkeypatch
):
    current = execution_fingerprint()
    assert cli_module._validate_size_prerequisite(6, None, current) is None
    with pytest.raises(ValueError, match="N=6 prerequisite"):
        cli_module._validate_size_prerequisite(7, None, current)
    prerequisite = tmp_path / "n6.json"
    prerequisite.write_text("n6", encoding="utf-8")
    monkeypatch.setattr(
        cli_module,
        "_validate_evaluation_artifact",
        lambda path: (
            {
                "particles": 6,
                "production_accepted": True,
                "execution_fingerprint": current,
            },
            True,
        ),
    )
    linked = cli_module._validate_size_prerequisite(7, prerequisite, current)
    assert linked["particles"] == 6
    assert linked["sha256"] == hashlib.sha256(b"n6").hexdigest()

    with pytest.raises(ValueError, match="particle number"):
        cli_module._validate_size_prerequisite(8, prerequisite, current)


def test_cross_size_manifest_stays_pending_until_n6_n7_n8_validate(
    tmp_path, monkeypatch
):
    current = execution_fingerprint()
    paths = {}
    for particles in (6, 7, 8):
        path = tmp_path / f"n{particles}.json"
        path.write_text(str(particles), encoding="utf-8")
        paths[particles] = path

    def accepted_evaluation(path):
        particles = int(Path(path).stem[1:])
        prerequisite = (
            None
            if particles == 6
            else {
                "particles": particles - 1,
                "sha256": cli_module._file_sha256(paths[particles - 1]),
            }
        )
        return (
            {
                "particles": particles,
                "production_accepted": True,
                "execution_fingerprint": current,
                "size_prerequisite": prerequisite,
            },
            True,
        )

    monkeypatch.setattr(
        cli_module, "_validate_evaluation_artifact", accepted_evaluation
    )
    pending_output = tmp_path / "pending"
    assert main(
        [
            "manifest",
            "--n6",
            str(paths[6]),
            "--n7",
            str(paths[7]),
            "--output",
            str(pending_output),
        ]
    ) == 0
    pending = verify_artifact(pending_output / "manifest.json")
    assert pending["production_accepted_n6_n8"] is False
    assert pending["pending_sizes"] == [8]

    accepted_output = tmp_path / "accepted"
    assert main(
        [
            "manifest",
            "--n6",
            str(paths[6]),
            "--n7",
            str(paths[7]),
            "--n8",
            str(paths[8]),
            "--output",
            str(accepted_output),
        ]
    ) == 0
    accepted = verify_artifact(accepted_output / "manifest.json")
    assert accepted["production_accepted_n6_n8"] is True


def test_cross_size_manifest_rejects_individually_valid_unrelated_chain(
    tmp_path, monkeypatch
):
    current = execution_fingerprint()
    paths = {}
    for name in ("n6", "other-n6", "n7", "n8"):
        path = tmp_path / f"{name}.json"
        path.write_text(name, encoding="utf-8")
        paths[name] = path

    def unrelated_evaluation(path):
        name = Path(path).stem
        particles = 6 if "n6" in name else int(name[1:])
        prerequisite_sha = {
            7: cli_module._file_sha256(paths["other-n6"]),
            8: cli_module._file_sha256(paths["n7"]),
        }.get(particles)
        return (
            {
                "particles": particles,
                "production_accepted": True,
                "execution_fingerprint": current,
                "size_prerequisite": (
                    None
                    if particles == 6
                    else {
                        "particles": particles - 1,
                        "sha256": prerequisite_sha,
                    }
                ),
            },
            True,
        )

    monkeypatch.setattr(
        cli_module, "_validate_evaluation_artifact", unrelated_evaluation
    )
    with pytest.raises(SystemExit) as caught:
        main(
            [
                "manifest",
                "--n6",
                str(paths["n6"]),
                "--n7",
                str(paths["n7"]),
                "--n8",
                str(paths["n8"]),
                "--output",
                str(tmp_path / "output"),
            ]
        )
    assert caught.value.code != 0

    links = {
        f"N={particles}": {
            "particles": particles,
            "path": str(paths[f"n{particles}"]),
            "sha256": cli_module._file_sha256(paths[f"n{particles}"]),
            "execution_fingerprint_digest": current["digest"],
        }
        for particles in (6, 7, 8)
    }
    manifest = {
        "execution_fingerprint": current,
        "links": links,
        "pending_sizes": [],
        "production_accepted_n6_n8": True,
    }
    with pytest.raises(ValueError, match="lineage"):
        cli_module._validate_cross_size_manifest(manifest)


def test_evaluate_reuses_verified_cached_oracle_without_resolving_per_record(
    tmp_path, valid_checkpoint, monkeypatch
):
    _, checkpoint = valid_checkpoint
    oracle_output = tmp_path / "oracle"
    assert main(
        ["oracle", "--particles", "2", "--output", str(oracle_output)]
    ) == 0
    _install_exact_mocks(monkeypatch)
    monkeypatch.setattr(
        cli_module,
        "solve_target_sectors",
        lambda spec: (_ for _ in ()).throw(
            AssertionError("evaluate must not solve an existing oracle")
        ),
    )
    output = tmp_path / "evaluation"
    assert main(
        [
            "evaluate",
            "--checkpoint",
            str(checkpoint),
            "--oracle",
            str(oracle_output / "result.json"),
            "--output",
            str(output),
        ]
    ) == 0
    result = verify_artifact(output / "evaluation.json")
    assert result["cache_telemetry"]["oracle"] == {"hits": 2, "misses": 1}
    assert result["telemetry"]["elapsed_wall_seconds"] > 0
    assert result["telemetry"]["peak_rss_mib"] > 0
    assert result["telemetry"]["backend"]
    assert result["telemetry"]["devices"]
    assert result["telemetry"]["determinant_blocks"] > 0
    assert result["stochastic_vmc_reporting"]["applicable"] is False
    assert result["stochastic_vmc_reporting"]["effective_sample_size"] is None


def test_paired_seed_transition_gate_prevents_cross_seed_cancellation():
    records = []
    for rank, shift in ((1, 0.0), (2, 1e-3), (4, 2e-3)):
        for seed, sign in ((10, 1.0), (11, -1.0)):
            energy_l0 = -1.0 + sign * shift
            energy_l2 = -0.8 + sign * shift
            records.append(
                {
                    "rank": rank,
                    "seed": seed,
                    "energy_l0": energy_l0,
                    "energy_l2": energy_l2,
                    "finite_size_l2_gap": energy_l2 - energy_l0,
                    "overlap_l0": 1.0,
                    "overlap_l2": 1.0,
                }
            )

    gate = cli_module._paired_seed_transition_gate(records, [1, 2, 4])

    assert gate["passed"] is False
    assert all(not item["accepted"] for item in gate["per_seed"])


def test_stochastic_reporting_schema_is_mode_strict():
    exact = {
        "applicable": False,
        "elapsed_wall_seconds": None,
        "peak_rss_mib": None,
        "effective_sample_size": None,
        "split_rhat": None,
        "confidence_interval_95": None,
        "within_seed_variation": None,
        "between_seed_variation": None,
        "ess_per_device_hour": None,
    }
    cli_module._validate_stochastic_reporting(exact, mode="exact")
    forged_exact = {**exact, "effective_sample_size": 100.0}
    with pytest.raises(ValueError, match="exact evaluation"):
        cli_module._validate_stochastic_reporting(forged_exact, mode="exact")

    stochastic = {
        "applicable": True,
        "elapsed_wall_seconds": 12.0,
        "peak_rss_mib": 256.0,
        "effective_sample_size": 400.0,
        "split_rhat": 1.01,
        "confidence_interval_95": [-0.02, 0.03],
        "within_seed_variation": 0.1,
        "between_seed_variation": 0.2,
        "ess_per_device_hour": 1200.0,
    }
    cli_module._validate_stochastic_reporting(stochastic, mode="stochastic")
    missing = dict(stochastic)
    missing.pop("split_rhat")
    with pytest.raises(ValueError, match="fields"):
        cli_module._validate_stochastic_reporting(missing, mode="stochastic")
