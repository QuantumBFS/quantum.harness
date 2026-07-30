from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import subprocess

import numpy as np
import pytest

import large_lattice_protocol as protocol


META = Path(__file__).with_name("large_lattice_run.json")


def confirmed_meta() -> dict:
    return json.loads(META.read_text(encoding="utf-8"))


def small_execution() -> dict:
    value = deepcopy(protocol.DEFAULT_EXECUTION)
    value["g1"].update(
        steps=20, warmup=4, measure_every=2,
        checkpoint_every=10, rebuild_every=4,
    )
    value["production"].update(
        steps=24, warmup=4, measure_every=2,
        checkpoint_every=12, rebuild_every=4,
    )
    return value


def write_meta(path: Path, value: dict) -> None:
    protocol.write_json(path, value)


def passing_gate_payload(name: str) -> dict:
    if name == "G0":
        return {"status": "PASS", "tests_exit_code": 0}
    if name in {"G1", "G2", "G3"}:
        stage, count = {
            "G1": ("g1", 8),
            "G2": ("pilot", 3),
            "G3": ("full", 20),
        }[name]
        payload = {
            "status": "PASS",
            "stage": stage,
            "cells": {
                f"cell-{item}": {"pass": True}
                for item in range(count)
            },
            "chain_cells_pass": True,
            "all_cells_pass": True,
        }
        if name == "G2":
            payload["kernel_benchmark"] = {"pass": True}
            payload["resource_gate"] = {"pass": True}
        return payload
    if name == "G4":
        return {
            "status": "PASS",
            "stage": "provenance",
            "chains": [
                {
                    "slurm_job_id": f"job-{item}",
                    "array_task_id": str(item),
                }
                for item in range(112)
            ],
            "distinct_slurm_array_tasks": 112,
            "checks": {"source_snapshot": True, "environment": True},
        }
    raise AssertionError(name)


def test_pending_and_physics_drift_are_rejected() -> None:
    pending = confirmed_meta()
    pending["document_type"] = "preregistered_large_lattice_run_draft"
    pending["status"] = "proposed_pending_single_setup_ratification"
    pending["ratification"]["status"] = "pending"
    with pytest.raises(protocol.ProtocolError):
        protocol.validate_meta(pending)
    drift = confirmed_meta()
    drift["model"]["local_parameters"]["kappa"] = 0.021
    with pytest.raises(protocol.ProtocolError, match="kappa"):
        protocol.validate_meta(drift)
    measurement_drift = confirmed_meta()
    measurement_drift["measurement_protocol"]["momenta"]["qmin"].append([1, 1])
    with pytest.raises(protocol.ProtocolError, match="qmin"):
        protocol.validate_meta(measurement_drift)


def test_strict_json_rejects_nonfinite(tmp_path: Path) -> None:
    with pytest.raises(protocol.ProtocolError, match="finite"):
        protocol.canonical_bytes({"bad": math.nan})
    bad = tmp_path / "bad.json"
    bad.write_text('{"bad": NaN}\n', encoding="utf-8")
    with pytest.raises(protocol.ProtocolError, match="finite"):
        protocol.load_json(bad)


def test_materialization_cardinality_hashes_and_frozen_manifests(
    tmp_path: Path,
) -> None:
    meta_path = tmp_path / "confirmed.json"
    write_meta(meta_path, confirmed_meta())
    root = tmp_path / "materialized"
    index = protocol.materialize(
        meta_path, root, small_execution()
    )
    assert index["counts"] == {
        "g1_chains": 32,
        "production_chains": 80,
        "pilot_chains": 12,
        "full_remaining_chains": 68,
    }
    assert len(index["entries"]) == 112
    assert not (root / "COMPLETE").exists()
    assert protocol.verify_materialization(root) == index

    production = [
        entry for entry in index["entries"]
        if entry["stage"] == "production"
        and entry["L"] == 6
        and entry["beta_index"] == 2
    ]
    assert len(production) == 4
    assert [entry["seed"] for entry in production] == [
        121060020, 121060021, 121060022, 121060023
    ]
    manifests = [
        protocol.load_json(root / entry["manifest"])
        for entry in production
    ]
    assert [item["monte_carlo"]["initialization"] for item in manifests] == [
        {"mode": "cold", "initial_order": 0},
        {"mode": "cold", "initial_order": 0},
        {"mode": "hot", "initial_order": 72},
        {"mode": "hot", "initial_order": 72},
    ]
    first = manifests[0]
    assert first["model"] == {
        "epsilon": "1/100",
        "kappa": "1/50",
        "vertex_strength": "1/4",
        "g_A": "1/4",
        "g_B": "1/4",
        "beta": "2",
    }
    measurements = first["measurements"]
    assert len(measurements["displacements"]) == 36
    assert measurements["momenta"] == [
        [0, 0], [1, 0], [0, 1],
        [3, 0], [0, 3], [3, 3],
        [2, 4], [4, 2],
    ]
    labels = measurements["momentum_labels"]
    assert labels["Gamma"] == [0, 0]
    assert labels["qmin"] == [[1, 0], [0, 1]]
    assert labels["M_points"] == {
        "condition": "L even",
        "indices": [[3, 0], [0, 3], [3, 3]],
    }
    assert labels["K_points"] == {
        "condition": "L%3==0",
        "indices": [[2, 4], [4, 2]],
    }
    assert labels["K_note"] == "two exact K points included"

    def manifest_for(size: int) -> dict:
        return next(
            protocol.load_json(root / entry["manifest"])
            for entry in index["entries"]
            if entry["stage"] == "production"
            and entry["L"] == size
            and entry["beta_index"] == 0
            and entry["chain_id"] == 0
        )

    l4 = manifest_for(4)
    assert len(l4["measurements"]["displacements"]) == 16
    assert l4["measurements"]["momenta"] == [
        [0, 0], [1, 0], [0, 1],
        [2, 0], [0, 2], [2, 2],
    ]
    assert l4["measurements"]["momentum_labels"]["K_points"]["indices"] == []
    assert l4["measurements"]["momentum_labels"]["K_note"] == (
        "K points omitted because L%3!=0"
    )

    l16 = manifest_for(16)
    assert len(l16["measurements"]["displacements"]) == 256
    assert l16["measurements"]["momenta"] == [
        [0, 0], [1, 0], [0, 1],
        [8, 0], [0, 8], [8, 8],
    ]
    assert l16["measurements"]["momentum_labels"]["K_points"]["indices"] == []

    assert "#SBATCH --array=0-31%8" in (
        root / "slurm" / "run_g1_array.sbatch"
    ).read_text(encoding="utf-8")
    submit = (
        root / "slurm" / "submit_after_live_cluster_check.sh"
    ).read_text(encoding="utf-8")
    assert submit.count("afterok:") == 8
    assert "sinfo" in submit and "squeue" in submit


def test_manifest_tamper_is_detected(tmp_path: Path) -> None:
    meta_path = tmp_path / "confirmed.json"
    write_meta(meta_path, confirmed_meta())
    root = tmp_path / "materialized"
    index = protocol.materialize(
        meta_path, root, small_execution()
    )
    manifest = root / index["entries"][0]["manifest"]
    manifest.write_text(
        manifest.read_text(encoding="utf-8") + " ",
        encoding="utf-8",
    )
    with pytest.raises(protocol.ProtocolError, match="manifest hash"):
        protocol.verify_materialization(root)


def test_ips_and_rank_split_diagnostics_are_finite() -> None:
    constant = [np.ones(32) for _ in range(4)]
    result = protocol.multi_chain_diagnostics(constant)
    assert result["split_r_hat"] == pytest.approx(1.0)
    assert result["bulk_ess"] == pytest.approx(128.0)
    assert result["tail_ess"] == pytest.approx(128.0)
    assert result["tau_int_by_original_chain"] == pytest.approx(
        [0.5] * 4
    )

    rng = np.random.default_rng(121)
    chains = [rng.normal(size=256) for _ in range(4)]
    noisy = protocol.multi_chain_diagnostics(chains)
    assert math.isfinite(noisy["split_r_hat"])
    assert 0.9 <= noisy["split_r_hat"] <= 1.1
    assert 0 < noisy["bulk_ess"] <= 1024
    assert 0 < noisy["tail_ess"] <= 1024


def fake_result(offset: float) -> dict:
    length = 64
    phase = np.linspace(0.0, 4.0 * np.pi, length, endpoint=False)
    order = 10.0 + np.sin(phase + offset)
    density = 0.5 + 0.01 * np.cos(phase + offset)
    number = 4.0 * density
    number2 = number * number + 0.25
    energy = -0.2 + 0.01 * np.sin(phase + offset)
    traces = {
        "order": order.tolist(),
        "energy_density": energy.tolist(),
        "particle_number": number.tolist(),
        "particle_number_squared": number2.tolist(),
        "particle_density": density.tolist(),
        "particle_density_squared": (
            number2 / 16.0
        ).tolist(),
    }
    return {
        "observables": {
            "count": length,
            "primary_traces": traces,
            "momentum": {},
        },
        "counters": {
            "moves": {
                "insert": {"attempted": 100, "accepted": 50},
                "delete": {"attempted": 100, "accepted": 50},
                "rotate_left_to_right": {
                    "attempted": 0, "accepted": 0
                },
                "rotate_right_to_left": {
                    "attempted": 0, "accepted": 0
                },
            },
            "zero_weight_rejections": 0,
            "determinant_failures": {"zero": 0, "negative": 0},
        },
        "rebuild_diagnostics": [
            {
                "delta_logdet": 1.0e-12,
                "relative_T_drift_inf": 1.0e-12,
                "relative_Q_drift_inf": 1.0e-12,
                "fast_inverse_residual_inf": 1.0e-12,
                "rebuilt_inverse_residual_inf": 1.0e-12,
            }
        ],
    }


def test_cell_merge_acceptance_rebuild_and_observables() -> None:
    thresholds = {
        "r_hat_max": 2.0,
        "bulk_ess_min": 1,
        "tail_ess_min": 1,
        "fast_vs_rebuild_relative_error_max": 1.0e-9,
        "inverse_residual_max": 1.0e-8,
    }
    results = [
        fake_result(0.0),
        fake_result(0.2),
        fake_result(0.4),
        fake_result(0.6),
    ]
    summary = protocol.summarize_cell(
        results, beta=1.0, n_sites=4,
        thresholds=thresholds, acceptance_range=(0.2, 0.7),
    )
    assert summary["acceptance"]["rate"] == pytest.approx(0.5)
    assert summary["acceptance"]["pass"]
    assert summary["rebuild"]["pass"]
    assert summary["positivity"]["pass"]
    assert math.isfinite(summary["compressibility"])
    assert summary["pass"]


def test_only_outer_all_pass_protocol_writes_complete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meta_path = tmp_path / "confirmed.json"
    write_meta(meta_path, confirmed_meta())
    root = tmp_path / "materialized"
    protocol.materialize(meta_path, root, small_execution())

    with pytest.raises(protocol.ProtocolError):
        protocol.write_protocol_complete(root)

    for gate in ("G0", "G1", "G2", "G3", "G4"):
        protocol._gate(root, gate, passing_gate_payload(gate))
    complete = protocol.write_protocol_complete(root)
    assert complete["status"] == "complete"
    assert (root / "COMPLETE").is_file()
    with pytest.raises(protocol.ProtocolError, match="overwrite"):
        protocol.write_protocol_complete(root)

    monkeypatch.setattr(
        protocol, "audit",
        lambda root, stage, write_complete=False: {
            "status": "INCONCLUSIVE"
        },
    )
    assert protocol.main([
        "audit", "--root", str(root), "--stage", "pilot"
    ]) == 2
    monkeypatch.setattr(
        protocol, "audit",
        lambda root, stage, write_complete=False: {"status": "PASS"},
    )
    assert protocol.main([
        "audit", "--root", str(root), "--stage", "g1"
    ]) == 0

def test_materialization_freezes_environment_and_restart_wrapper(
    tmp_path: Path,
) -> None:
    meta_path = tmp_path / "confirmed.json"
    write_meta(meta_path, confirmed_meta())
    root = tmp_path / "materialized"
    index = protocol.materialize(meta_path, root, small_execution())
    environment = index["environment"]
    assert Path(environment["python_executable"]).is_absolute()
    assert Path(environment["python_executable"]).resolve() == Path(
        sys.executable
    ).resolve()
    assert environment["python_version"]
    assert environment["numpy_version"]
    assert environment["scipy_version"]
    assert index["source_snapshot"]["git_commit"]

    script = (root / "slurm" / "run_g1_array.sbatch").read_text(
        encoding="utf-8"
    )
    assert environment["python_executable"] in script
    assert "CHAIN_COMPLETE" in script
    assert "--resume" in script
    assert '>>"$output/runner.stdout"' in script


def test_materialization_rejects_cardinality_path_and_tsv_tamper(
    tmp_path: Path,
) -> None:
    meta_path = tmp_path / "confirmed.json"
    write_meta(meta_path, confirmed_meta())
    for number, (mutation, match) in enumerate((
        (lambda index: index["entries"].pop(), "entries"),
        (
            lambda index: index["entries"][0].__setitem__(
                "manifest", "../escape.json"
            ),
            "entries",
        ),
    )):
        root = tmp_path / f"materialized-{number}"
        protocol.materialize(meta_path, root, small_execution())
        index = protocol.load_json(root / "index.json")
        mutation(index)
        protocol.write_json(root / "index.json", index)
        (root / "index.sha256").write_text(
            f"{protocol.sha_file(root / 'index.json')}  index.json\n",
            encoding="ascii",
        )
        with pytest.raises(protocol.ProtocolError, match=match):
            protocol.verify_materialization(root)

    root = tmp_path / "materialized-tsv"
    protocol.materialize(meta_path, root, small_execution())
    (root / "g1_tasks.tsv").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(protocol.ProtocolError, match="g1_tasks.tsv"):
        protocol.verify_materialization(root)


def test_positivity_uses_real_determinant_failure_counters() -> None:
    thresholds = {
        "r_hat_max": 2.0,
        "bulk_ess_min": 1,
        "tail_ess_min": 1,
        "fast_vs_rebuild_relative_error_max": 1.0e-9,
        "inverse_residual_max": 1.0e-8,
    }
    results = [fake_result(value) for value in (0.0, 0.2, 0.4, 0.6)]
    results[2]["counters"]["determinant_failures"]["negative"] = 1
    summary = protocol.summarize_cell(
        results,
        beta=1.0,
        n_sites=4,
        thresholds=thresholds,
        acceptance_range=(0.2, 0.7),
    )
    assert summary["positivity"]["negative_sign_count"] == 1
    assert not summary["positivity"]["pass"]
    assert not summary["pass"]


def _write_chain_fixture(root: Path, entry: dict) -> dict:
    manifest = protocol.load_json(root / entry["manifest"])
    result = {
        "schema_version": 1,
        "status": "run_complete_unvalidated",
        "scope": "single_chain_execution_only",
        "algorithm_id": protocol.CORE_ALGORITHM_ID,
        "manifest_sha256": entry["manifest_sha256"],
        "completed_steps": manifest["monte_carlo"]["steps"],
        "geometry": {"n_sites": entry["N"]},
        "model": manifest["model"],
        "initialization": entry["initialization"],
        "measurements": manifest["measurements"],
        "observables": {"count": 1},
        "execution_environment": {},
    }
    output = root / entry["output"]
    output.mkdir(parents=True, exist_ok=True)
    protocol.write_json(output / "result.json", result)
    protocol.write_json(
        output / "CHAIN_COMPLETE",
        {
            "schema_version": 1,
            "status": "run_complete_unvalidated",
            "scope": "single_chain_execution_only",
            "algorithm_id": protocol.CORE_ALGORITHM_ID,
            "manifest_sha256": entry["manifest_sha256"],
            "result_json_sha256": protocol.sha_file(output / "result.json"),
            "completed_steps": manifest["monte_carlo"]["steps"],
        },
    )
    return result


def test_load_chain_accepts_bound_chain_complete_and_rejects_drift(
    tmp_path: Path,
) -> None:
    meta_path = tmp_path / "confirmed.json"
    write_meta(meta_path, confirmed_meta())
    root = tmp_path / "materialized"
    index = protocol.materialize(meta_path, root, small_execution())
    entry = index["entries"][0]
    expected = _write_chain_fixture(root, entry)
    assert protocol._load_chain(root, entry) == expected

    done_path = root / entry["output"] / "CHAIN_COMPLETE"
    done = protocol.load_json(done_path)
    done["algorithm_id"] = "wrong"
    protocol.write_json(done_path, done)
    with pytest.raises(protocol.ProtocolError, match="algorithm"):
        protocol._load_chain(root, entry)


def test_gate_dependency_is_bound_to_current_index_and_meta(
    tmp_path: Path,
) -> None:
    meta_path = tmp_path / "confirmed.json"
    write_meta(meta_path, confirmed_meta())
    root = tmp_path / "materialized"
    protocol.materialize(meta_path, root, small_execution())
    protocol._gate(root, "G0", passing_gate_payload("G0"))
    gate_path = root / "gates" / "G0.json"
    gate = protocol.load_json(gate_path)
    gate["index_sha256"] = "0" * 64
    protocol.write_json(gate_path, gate)
    with pytest.raises(protocol.ProtocolError, match="index"):
        protocol._require_gate(root, "G0")


def test_compare_ed_includes_all_real_space_displacements() -> None:
    results = [fake_result(value) for value in (0.0, 0.2, 0.4, 0.6)]
    for result in results:
        result["observables"]["real_space_green"] = {
            "0,0": {
                "one_body": {
                    "mean": [0.5, 0.0],
                    "naive_stderr_abs": 0.01,
                }
            },
            "1,0": {
                "one_body": {
                    "mean": [0.1, 0.0],
                    "naive_stderr_abs": 0.01,
                }
            },
        }
    cell = protocol.summarize_cell(
        results,
        beta=1.0,
        n_sites=4,
        thresholds={
            "r_hat_max": 2.0,
            "bulk_ess_min": 1,
            "tail_ess_min": 1,
            "fast_vs_rebuild_relative_error_max": 1.0e-9,
            "inverse_residual_max": 1.0e-8,
        },
        acceptance_range=(0.2, 0.7),
    )
    exact = {
        "observables": {
            "scalar": {
                "energy_density": cell["scalar"]["energy_density"]["mean"],
                "particle_density": cell["scalar"]["particle_density"]["mean"],
                "compressibility": cell["compressibility"],
            },
            "momentum": {},
            "real_space_green": {
                "0,0": [0.5, 0.0],
                "1,0": [0.1, 0.0],
            },
        }
    }
    compared = protocol.compare_ed(cell, exact, 8.0)
    assert set(compared["real_space_green"]) == {"0,0", "1,0"}
    assert compared["pass"]

def test_cli_materialize_and_validate_smoke(tmp_path: Path) -> None:
    root = tmp_path / "cli-materialized"
    script = Path(protocol.__file__).resolve()
    command = [
        sys.executable, str(script), "materialize",
        "--meta", str(META), "--output", str(root),
        "--g1-steps", "20", "--g1-warmup", "4",
        "--g1-measure-every", "2", "--g1-checkpoint-every", "10",
        "--g1-rebuild-every", "4",
        "--production-steps", "24", "--production-warmup", "4",
        "--production-measure-every", "2",
        "--production-checkpoint-every", "12",
        "--production-rebuild-every", "4",
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    validated = subprocess.run(
        [sys.executable, str(script), "validate", "--root", str(root)],
        check=False, capture_output=True, text=True,
    )
    assert validated.returncode == 0, validated.stderr
    assert protocol.verify_materialization(root)["protocol_id"] == protocol.PROTOCOL_ID


def test_verify_rejects_current_source_snapshot_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    meta_path = tmp_path / "confirmed.json"
    write_meta(meta_path, confirmed_meta())
    root = tmp_path / "materialized"
    index = protocol.materialize(meta_path, root, small_execution())
    drift = deepcopy(index["source_snapshot"])
    drift["tracked_files_sha256"] = dict(drift["tracked_files_sha256"])
    drift["tracked_files_sha256"]["large_lattice_ctqmc.py"] = "0" * 64
    monkeypatch.setattr(protocol, "source_snapshot", lambda: drift)
    with pytest.raises(protocol.ProtocolError, match="current source"):
        protocol.verify_materialization(root)

def _write_benchmark_fixture(root: Path, index: dict) -> dict:
    manifest = protocol.load_json(root / index["kernel_benchmark"]["manifest"])
    cases = []
    for size in (4, 8, 12, 16):
        n_sites = size * size
        latency = {}
        for move in ("insert", "delete"):
            rank = n_sites * 100
            dense = rank * 3
            latency[move] = {
                "rank3": {"median_ns": rank, "minimum_ns": rank,
                          "maximum_ns": rank, "samples_ns": [rank] * 9},
                "full_word_rebuild": {
                    "median_ns": dense, "minimum_ns": dense,
                    "maximum_ns": dense, "samples_ns": [dense] * 9},
                "speedup_dense_over_rank3": 3.0,
            }
        cases.append({
            "L": size, "N": n_sites, "latency": latency,
            "correctness": {"pass": True},
            "fallback_count": {"insert": 0, "delete": 0},
        })
    sources = index["source_snapshot"]["tracked_files_sha256"]
    report = {
        "schema_version": 1,
        "algorithm_id": protocol.BENCHMARK_ALGORITHM_ID,
        "status": "benchmark_complete_unvalidated",
        "parameters": manifest["parameters"],
        "environment": {
            "python_executable": index["environment"]["python_executable"],
            "numpy_version": index["environment"]["numpy_version"],
            "scipy_version": index["environment"]["scipy_version"],
        },
        "single_thread_blas": {
            "set_before_numpy_import": True,
            "environment": {"OPENBLAS_NUM_THREADS": "1"},
        },
        "provenance": {
            "source_commit": index["source_snapshot"]["git_commit"],
            "benchmark_source_sha256":
                sources["large_lattice_kernel_benchmark.py"],
            "ctqmc_source_sha256": sources["large_lattice_ctqmc.py"],
        },
        "cases": cases,
        "overall_correctness_pass": True,
        "total_fallback_count": {"insert": 0, "delete": 0},
    }
    benchmark_dir = root / "benchmark"
    benchmark_dir.mkdir()
    protocol.write_json(benchmark_dir / "kernel_benchmark.json", report)
    (benchmark_dir / "resource.tsv").write_text(
        "elapsed_seconds\t1.0\nmax_rss_kb\t1024\n", encoding="utf-8"
    )
    for name in ("runner.stdout", "runner.stderr", "preflight.log"):
        (benchmark_dir / name).write_text("ok\n", encoding="utf-8")
    return report


def test_kernel_benchmark_gate_passes_and_detects_tamper(tmp_path: Path) -> None:
    meta_path = tmp_path / "confirmed.json"
    write_meta(meta_path, confirmed_meta())
    root = tmp_path / "materialized"
    index = protocol.materialize(meta_path, root, small_execution())
    report = _write_benchmark_fixture(root, index)
    assert protocol.validate_kernel_benchmark(root, index)["pass"]

    report["provenance"]["benchmark_source_sha256"] = "0" * 64
    protocol.write_json(root / "benchmark" / "kernel_benchmark.json", report)
    with pytest.raises(protocol.ProtocolError, match="source hash"):
        protocol.validate_kernel_benchmark(root, index)

    report["provenance"]["benchmark_source_sha256"] = index[
        "source_snapshot"
    ]["tracked_files_sha256"]["large_lattice_kernel_benchmark.py"]
    case = next(item for item in report["cases"] if item["N"] == 144)
    timing = case["latency"]["insert"]
    timing["full_word_rebuild"]["median_ns"] = (
        timing["rank3"]["median_ns"] * 1.5
    )
    timing["full_word_rebuild"]["samples_ns"] = [
        timing["full_word_rebuild"]["median_ns"]
    ] * 9
    timing["speedup_dense_over_rank3"] = 1.5
    protocol.write_json(root / "benchmark" / "kernel_benchmark.json", report)
    checked = protocol.validate_kernel_benchmark(root, index)
    assert not checked["speedup_pass"]
    assert not checked["pass"]


def _resign_index(root: Path, index: dict) -> None:
    protocol.write_json(root / "index.json", index)
    (root / "index.sha256").write_text(
        f"{protocol.sha_file(root / 'index.json')}  index.json\n",
        encoding="ascii",
    )


def test_generated_artifact_keyset_and_regeneration_resist_resigning(
    tmp_path: Path,
) -> None:
    meta_path = tmp_path / "confirmed.json"
    write_meta(meta_path, confirmed_meta())

    missing_root = tmp_path / "missing-key"
    protocol.materialize(meta_path, missing_root, small_execution())
    missing_index = protocol.load_json(missing_root / "index.json")
    del missing_index["generated_artifact_sha256"][
        "slurm/run_g1_array.sbatch"
    ]
    _resign_index(missing_root, missing_index)
    with pytest.raises(protocol.ProtocolError, match="key set"):
        protocol.verify_materialization(missing_root)

    changed_root = tmp_path / "changed-script"
    protocol.materialize(meta_path, changed_root, small_execution())
    script_path = changed_root / "slurm" / "run_g1_array.sbatch"
    script_path.write_text(
        script_path.read_text(encoding="utf-8") + "# forged\n",
        encoding="utf-8",
    )
    changed_index = protocol.load_json(changed_root / "index.json")
    changed_index["generated_artifact_sha256"][
        "slurm/run_g1_array.sbatch"
    ] = protocol.sha_file(script_path)
    _resign_index(changed_root, changed_index)
    with pytest.raises(protocol.ProtocolError, match="artifact content"):
        protocol.verify_materialization(changed_root)


def test_array_preflight_rejects_malicious_tsv_before_side_effect(
    tmp_path: Path,
) -> None:
    meta_path = tmp_path / "confirmed.json"
    write_meta(meta_path, confirmed_meta())
    root = tmp_path / "materialized"
    protocol.materialize(meta_path, root, small_execution())
    table = root / "g1_tasks.tsv"
    lines = table.read_text(encoding="utf-8").splitlines()
    fields = lines[1].split("\t")
    fields[-1] = "../escaped-output"
    lines[1] = "\t".join(fields)
    table.write_text("\n".join(lines) + "\n", encoding="utf-8")
    escaped = root.parent / "escaped-output"

    result = subprocess.run(
        ["bash", str(root / "slurm" / "run_g1_array.sbatch")],
        env={**os.environ, "SLURM_ARRAY_TASK_ID": "0"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert not escaped.exists()


def test_forged_gate_and_stale_complete_are_rejected(tmp_path: Path) -> None:
    meta_path = tmp_path / "confirmed.json"
    write_meta(meta_path, confirmed_meta())
    forged_root = tmp_path / "forged"
    protocol.materialize(meta_path, forged_root, small_execution())
    protocol._gate(
        forged_root,
        "G1",
        {"status": "PASS", "stage": "g1", "cells": {}},
    )
    with pytest.raises(protocol.ProtocolError, match="cell cardinality"):
        protocol._require_gate(forged_root, "G1")

    complete_root = tmp_path / "complete"
    protocol.materialize(meta_path, complete_root, small_execution())
    for gate in ("G0", "G1", "G2", "G3", "G4"):
        protocol._gate(
            complete_root, gate, passing_gate_payload(gate)
        )
    protocol.write_protocol_complete(complete_root)
    with pytest.raises(protocol.ProtocolError, match="immutable"):
        protocol._gate(
            complete_root, "G0", passing_gate_payload("G0")
        )

    gate_path = complete_root / "gates" / "G1.json"
    stale_gate = protocol.load_json(gate_path)
    stale_gate["cells"]["cell-0"]["pass"] = False
    protocol.write_json(gate_path, stale_gate)
    with pytest.raises(protocol.ProtocolError, match="cell evidence"):
        protocol.verify_materialization(complete_root)


@pytest.mark.parametrize("value", [None, "", " ", "none", -1, True])
def test_slurm_id_normalization_rejects_missing_or_nondecimal(value: object) -> None:
    assert protocol._normalize_slurm_id(value) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, "0"), (121, "121"), ("0", "0"), ("00121", "00121")],
)
def test_slurm_id_normalization_accepts_nonnegative_decimal(
    value: object, expected: str,
) -> None:
    assert protocol._normalize_slurm_id(value) == expected


def _materialized_complete_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, dict]:
    meta_path = tmp_path / "confirmed.json"
    write_meta(meta_path, confirmed_meta())
    root = tmp_path / "materialized"
    index = protocol.materialize(meta_path, root, small_execution())

    benchmark_output = root / index["kernel_benchmark"]["output"]
    benchmark_output.parent.mkdir(parents=True, exist_ok=True)
    benchmark_output.write_bytes(b"benchmark-evidence\n")

    def fake_validate_kernel(root_arg: Path, index_arg: dict) -> dict:
        output = Path(root_arg) / index_arg["kernel_benchmark"]["output"]
        return {
            "pass": True,
            "output_sha256": protocol.sha_file(output),
        }

    monkeypatch.setattr(
        protocol, "validate_kernel_benchmark", fake_validate_kernel
    )
    benchmark = fake_validate_kernel(root, index)

    protocol._gate(root, "G0", passing_gate_payload("G0"))
    g1_ids = sorted({
        entry["cell_id"] for entry in index["entries"]
        if entry["stage"] == "g1"
    })
    g1_cells = {}
    for cell_id in g1_ids:
        exact = root / "exact" / "g1" / f"{cell_id}.json"
        exact.parent.mkdir(parents=True, exist_ok=True)
        exact.write_bytes(f"exact:{cell_id}\n".encode())
        g1_cells[cell_id] = {
            "pass": True,
            "exact_ed_sha256": protocol.sha_file(exact),
        }
    protocol._gate(root, "G1", {
        "status": "PASS",
        "stage": "g1",
        "cells": g1_cells,
        "chain_cells_pass": True,
        "all_cells_pass": True,
    })

    pilot_ids = sorted({
        entry["cell_id"] for entry in index["entries"]
        if entry["stage"] == "production" and entry["pilot"]
    })
    protocol._gate(root, "G2", {
        "status": "PASS",
        "stage": "pilot",
        "cells": {
            cell_id: {"pass": True} for cell_id in pilot_ids
        },
        "chain_cells_pass": True,
        "all_cells_pass": True,
        "kernel_benchmark": benchmark,
        "resource_gate": {"pass": True},
    })
    full_ids = sorted({
        entry["cell_id"] for entry in index["entries"]
        if entry["stage"] == "production"
    })
    protocol._gate(root, "G3", {
        "status": "PASS",
        "stage": "full",
        "cells": {
            cell_id: {"pass": True} for cell_id in full_ids
        },
        "chain_cells_pass": True,
        "all_cells_pass": True,
    })

    chains = []
    for task, entry in enumerate(index["entries"]):
        output = root / entry["output"]
        output.mkdir(parents=True, exist_ok=True)
        for filename in (
            "result.json", "CHAIN_COMPLETE", "runner.stdout",
            "runner.stderr", "preflight.log", "resource.tsv",
        ):
            (output / filename).write_bytes(
                f"{entry['stage']}:{entry['cell_id']}:{entry['chain_id']}:{filename}\n".encode()
            )
        chains.append({
            "stage": entry["stage"],
            "cell_id": entry["cell_id"],
            "chain_id": entry["chain_id"],
            "result_sha256": protocol.sha_file(output / "result.json"),
            "chain_complete_sha256": protocol.sha_file(
                output / "CHAIN_COMPLETE"
            ),
            "runner_stdout_sha256": protocol.sha_file(
                output / "runner.stdout"
            ),
            "runner_stderr_sha256": protocol.sha_file(
                output / "runner.stderr"
            ),
            "preflight_sha256": protocol.sha_file(
                output / "preflight.log"
            ),
            "resource": {
                "sha256": protocol.sha_file(output / "resource.tsv")
            },
            "slurm_job_id": str(task),
            "array_task_id": str(task),
        })
    protocol._gate(root, "G4", {
        "status": "PASS",
        "stage": "provenance",
        "checks": {"source_snapshot": True, "environment": True},
        "chains": chains,
        "distinct_slurm_array_tasks": 112,
    })
    protocol.write_protocol_complete(root)
    assert protocol.verify_materialization(root) == index
    return root, index


def test_complete_revalidation_detects_chain_result_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, index = _materialized_complete_evidence(tmp_path, monkeypatch)
    result = root / index["entries"][0]["output"] / "result.json"
    result.write_bytes(result.read_bytes() + b"tampered")
    with pytest.raises(protocol.ProtocolError, match="chain evidence drift"):
        protocol.verify_materialization(root)


def test_complete_revalidation_detects_ed_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _ = _materialized_complete_evidence(tmp_path, monkeypatch)
    exact = root / "exact" / "g1" / "L2-b0.json"
    exact.write_bytes(exact.read_bytes() + b"tampered")
    with pytest.raises(protocol.ProtocolError, match="ED evidence drift"):
        protocol.verify_materialization(root)


def test_complete_revalidation_detects_benchmark_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, index = _materialized_complete_evidence(tmp_path, monkeypatch)
    output = root / index["kernel_benchmark"]["output"]
    output.write_bytes(output.read_bytes() + b"tampered")
    with pytest.raises(
        protocol.ProtocolError, match="benchmark evidence drift"
    ):
        protocol.verify_materialization(root)
