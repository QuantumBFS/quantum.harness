from __future__ import annotations

from dataclasses import replace
import json
import math
import os
from pathlib import Path
import subprocess

import numpy as np
import pytest

from scripts.hard_goal_science_pilot_cell import build_parser as build_cell_parser
from vmcrg_ref.artifacts import canonical_json_bytes
from spinglass3d.backend import BackendCase
from spinglass3d.equilibration import (
    EquilibrationReport,
    EquilibrationThresholds,
)
from spinglass3d.jax_backend import JaxParallelTemperingBackend
from spinglass3d.rg import block_majority_3d
from spinglass3d.science_pilot import (
    CALIBRATION_COMPLETE,
    CORRECTNESS_FAILURE,
    PILOT_NEEDS_EXTENSION,
    PILOT_PASS,
    REPRESENTATION_NOT_RUN,
    ObservationHistory,
    PTDiagnostics,
    SciencePilotProgress,
    SciencePilotSpec,
    build_equilibration_records,
    build_one_rg_evidence,
    build_science_manifest,
    classify_science_pilot,
    load_science_checkpoint,
    load_science_pilot_cell,
    measure_pt_snapshot,
    run_observation_block,
    run_science_pilot,
    save_science_checkpoint,
)
from spinglass3d.workflow import build_pilot_run_spec, load_stage6_config


TRACK = Path(__file__).resolve().parents[1]
CONFIG = TRACK / "config" / "hard_goal" / "stage6_pilot_v1.toml"


def _thresholds() -> EquilibrationThresholds:
    return EquilibrationThresholds(
        swap_bottleneck=0.0,
        swap_target_min=0.0,
        swap_target_max=1.0,
        min_round_trips=1,
        max_rhat=10.0,
        min_ess=1.0,
        bin_sigma=1.0e6,
        max_thermal_error_fraction=1.0,
        min_chains=4,
    )


def _spec(**changes: object) -> SciencePilotSpec:
    values: dict[str, object] = {
        "cell_id": "L03-J0000",
        "length": 3,
        "temperatures": (2.0, 1.5, 1.1, 0.9),
        "chain_pairs": 4,
        "calibration_sweeps": 2,
        "equilibration_initial_sweeps": 32,
        "equilibration_multiplier": 2,
        "equilibration_maximum_sweeps": 64,
        "measurement_sweeps": 4,
        "equilibration_cadence": 1,
        "measurement_cadence": 1,
        "j_seed": 2026073198,
        "thresholds": _thresholds(),
        "templates": ("cube", "cross"),
        "rg_levels": 1,
        "source_hashes": {"test": "a" * 64},
    }
    values.update(changes)
    return SciencePilotSpec(**values)


def _backend(seed: int = 2026073199) -> JaxParallelTemperingBackend:
    pytest.importorskip("jax")
    case = BackendCase.random(
        length=3,
        temperatures=4,
        samples=1,
        walkers=8,
        seed=seed,
    )
    return JaxParallelTemperingBackend(case)


def _constant_history(spec: SciencePilotSpec) -> ObservationHistory:
    history = ObservationHistory.empty(
        temperature_count=len(spec.temperatures),
        chain_pairs=spec.chain_pairs,
    )
    base = np.ones((len(spec.temperatures), spec.chain_pairs), dtype=np.float64)
    for sweep in range(1, 33):
        history.append(
            sweep,
            {
                "energy": -base,
                "q": np.zeros_like(base),
                "q2": 0.25 * base,
                "q4": 0.0625 * base,
                "qk2_x": 0.1 * base,
                "qk2_y": 0.1 * base,
                "qk2_z": 0.1 * base,
            },
        )
    return history


def test_science_spec_hashes_every_schedule_and_forbids_second_rg() -> None:
    spec = _spec()
    assert spec.calibration_sweeps == 2
    assert spec.equilibration_initial_sweeps == 32
    assert spec.measurement_sweeps == 4
    assert spec.measurement_cadence == 1
    assert spec.rg_levels == 1
    assert len(spec.sha256) == 64
    assert replace(spec, measurement_cadence=2).sha256 != spec.sha256
    assert replace(spec, thresholds=replace(spec.thresholds, min_ess=2.0)).sha256 != spec.sha256
    with pytest.raises(ValueError, match="one RG"):
        _spec(rg_levels=2)


def test_run_spec_loader_builds_a_hash_bound_science_cell(tmp_path: Path) -> None:
    run_spec = build_pilot_run_spec(load_stage6_config(CONFIG), "science-load")
    path = tmp_path / "run_spec.json"
    path.write_text(json.dumps(run_spec, sort_keys=True) + "\n", encoding="ascii")
    spec, output = load_science_pilot_cell(
        path,
        "1",
        track_root=TRACK,
        repo_root=TRACK.parents[2],
        measurement_cadence=4,
    )
    assert spec.cell_id == "L12-J0000"
    assert spec.calibration_sweeps == 4096
    assert spec.equilibration_initial_sweeps == 8192
    assert spec.equilibration_maximum_sweeps == 1_048_576
    assert spec.measurement_sweeps == 8192
    assert spec.equilibration_cadence == 4
    assert spec.measurement_cadence == 4
    assert spec.rg_levels == 1
    assert set(spec.source_hashes) >= {
        "src/spinglass3d/science_pilot.py",
        "scripts/hard_goal_science_pilot_cell.py",
        "jobs/hard_goal_science_pilot.slurm",
    }
    assert output == (
        TRACK.parents[2]
        / "results"
        / "hard_goal"
        / "science-load"
        / "science-cells"
        / "L12-J0000"
    )


def test_jax_measurement_records_every_temperature_and_replica_pair() -> None:
    backend = _backend()
    snapshot = measure_pt_snapshot(backend)
    assert set(snapshot) == {
        "energy",
        "q",
        "q2",
        "q4",
        "qk2_x",
        "qk2_y",
        "qk2_z",
    }
    assert all(value.shape == (4, 4) for value in snapshot.values())
    np.testing.assert_allclose(snapshot["q2"], snapshot["q"] ** 2, atol=0.0, rtol=0.0)
    np.testing.assert_allclose(snapshot["q4"], snapshot["q"] ** 4, atol=0.0, rtol=0.0)
    assert all(np.all(snapshot[name] >= 0.0) for name in ("qk2_x", "qk2_y", "qk2_z"))


def test_equilibration_records_retain_all_fail_closed_diagnostics() -> None:
    spec = _spec()
    history = _constant_history(spec)
    diagnostics = PTDiagnostics(
        edge_attempts=np.full(3, 20, dtype=np.int64),
        edge_accepts=np.full(3, 6, dtype=np.int64),
        round_trips=np.full((8, 4), 2, dtype=np.int64),
        round_trip_phase=np.full((8, 4), 2, dtype=np.int8),
        time_since_endpoint=np.zeros((8, 4), dtype=np.int64),
    )
    records, reports = build_equilibration_records(
        spec,
        history,
        diagnostics,
        elapsed_seconds=8.0,
        extension_count=1,
    )
    assert len(records) == len(reports) == 4
    assert all(record.extension_count == 1 for record in records)
    assert all(record.tmax_forgetting_passed for record in records)
    assert all(set(record.observables) == {
        "energy", "q2", "q4", "chi0", "chik_x", "chik_y", "chik_z"
    } for record in records)
    assert all(report.passed for report in reports)
    components = reports[0].components
    assert components["extension_count"] == 1
    assert components["tmax_forgetting_passed"] is True
    assert len(components["energy"]["log_bins"]) == 3
    assert components["energy"]["rhat"] == pytest.approx(1.0)
    assert components["energy"]["minimum_ess"] == pytest.approx(32.0)


def test_one_rg_evidence_matches_majority_and_contains_cube_cross_tokens() -> None:
    spec = _spec()
    backend = _backend(2026073200)
    evidence = build_one_rg_evidence(spec, backend)
    fields = backend.overlap_fields()[0]
    assert evidence["q_prime"].shape == (4, 4, 1, 1, 1)
    np.testing.assert_array_equal(
        evidence["q_prime"][0, 0],
        block_majority_3d(fields[0, 0]),
    )
    assert evidence["tokens_cube"].shape == (4, 4, 1, 13)
    assert evidence["tokens_cross"].shape == (4, 4, 1, 19)


def test_science_checkpoint_restores_sampler_history_counters_and_rng(
    tmp_path: Path,
) -> None:
    spec = _spec()
    source = _backend(2026073201)
    progress = SciencePilotProgress.initial(spec)
    progress.phase = "equilibration"
    run_observation_block(source, progress, phase="equilibration", sweeps=2)
    checkpoint = tmp_path / "checkpoint"
    save_science_checkpoint(source, progress, checkpoint, spec_sha256=spec.sha256)

    restored = _backend(2026073201)
    restored_progress = load_science_checkpoint(
        restored,
        checkpoint,
        expected_spec_sha256=spec.sha256,
    )
    assert restored_progress.phase == "equilibration"
    assert restored_progress.equilibration_completed == 2
    assert restored_progress.equilibration_history.count == 2

    run_observation_block(source, progress, phase="equilibration", sweeps=2)
    run_observation_block(restored, restored_progress, phase="equilibration", sweeps=2)
    np.testing.assert_array_equal(restored.spins, source.spins)
    np.testing.assert_array_equal(restored.replica_ids, source.replica_ids)
    np.testing.assert_array_equal(restored.round_trips, source.round_trips)
    for name, values in progress.equilibration_history.arrays().items():
        np.testing.assert_array_equal(
            restored_progress.equilibration_history.arrays()[name],
            values,
        )


def test_manifest_classification_is_scientific_and_representation_stays_not_run() -> None:
    spec = _spec()
    progress = SciencePilotProgress.initial(spec)
    passed = EquilibrationReport(
        j_id="J@T0",
        passed=True,
        failed_gates=(),
        components={},
    )
    failed = passed.with_failure("round_trips")
    assert classify_science_pilot("calibration", ()) == CALIBRATION_COMPLETE
    assert classify_science_pilot("equilibration", (failed,)) == PILOT_NEEDS_EXTENSION
    assert classify_science_pilot("complete", (passed,)) == PILOT_PASS
    assert classify_science_pilot("complete", (passed,), correctness_failure=True) == CORRECTNESS_FAILURE
    manifest = build_science_manifest(
        spec,
        progress,
        classification=PILOT_PASS,
        reports=(passed,),
        artifact_hashes={"history.npz": "b" * 64},
    )
    assert manifest["classification"] == PILOT_PASS
    assert manifest["tc_evidence"] is False
    assert manifest["second_rg_enabled"] is False
    assert manifest["representation_comparison"] == REPRESENTATION_NOT_RUN


def test_failed_infinite_rhat_remains_serializable_extension_evidence() -> None:
    failed = EquilibrationReport(
        j_id="J@T0",
        passed=False,
        failed_gates=("energy:rhat",),
        components={"energy": {"rhat": math.inf}},
    )
    manifest = build_science_manifest(
        _spec(),
        SciencePilotProgress.initial(_spec()),
        classification=PILOT_NEEDS_EXTENSION,
        reports=(failed,),
        artifact_hashes={},
    )
    assert manifest["equilibration"]["passed"] is False
    assert manifest["equilibration"]["reports"][0]["components"]["energy"][
        "rhat"
    ] == "Infinity"
    canonical_json_bytes(manifest)


def test_calibration_only_status_is_resumable_and_existing_output_is_immutable(
    tmp_path: Path,
) -> None:
    jax = pytest.importorskip("jax")
    spec = _spec()
    output = tmp_path / "science-cell"
    manifest = run_science_pilot(
        spec,
        output,
        required_platform=jax.default_backend(),
        checkpoint_every=1,
        calibration_only=True,
    )
    assert manifest["classification"] == CALIBRATION_COMPLETE
    assert manifest["tc_evidence"] is False
    work = tmp_path / ".science-cell.science-work"
    assert not output.exists()
    assert (work / "status.json").is_file()
    assert (work / "checkpoints").is_dir()
    assert len(tuple((work / "checkpoints").glob("checkpoint-*"))) <= 2

    output.mkdir()
    (output / "manifest.json").write_text("{}\n", encoding="ascii")
    with pytest.raises(FileExistsError, match="overwrite"):
        run_science_pilot(
            spec,
            output,
            required_platform=jax.default_backend(),
            checkpoint_every=1,
            resume=True,
        )


def test_science_cell_cli_and_profile_neutral_wrapper_forward_resume(
    tmp_path: Path,
) -> None:
    args = build_cell_parser().parse_args(
        [
            "--run-spec", str(tmp_path / "run.json"),
            "--selector", "7",
            "--require-platform", "cpu",
            "--checkpoint-every", "8",
            "--measurement-cadence", "2",
            "--resume",
            "--calibration-only",
        ]
    )
    assert args.resume is True
    assert args.calibration_only is True

    run_spec = tmp_path / "run.json"
    run_spec.write_text("{}\n", encoding="ascii")
    environment = {
        **os.environ,
        "HARNESS_RUN_SPEC": str(run_spec),
        "HARNESS_CELL_SELECTOR": "7",
        "HARNESS_TRACK_ROOT": str(TRACK),
        "HARNESS_PYTHON": "/bin/echo",
        "HARNESS_REQUIRED_PLATFORM": "cpu",
        "HARNESS_CHECKPOINT_EVERY": "8",
        "HARNESS_MEASUREMENT_CADENCE": "2",
        "HG3D_RESUME": "1",
        "HG3D_CALIBRATION_ONLY": "1",
    }
    completed = subprocess.run(
        ["bash", str(TRACK / "jobs" / "hard_goal_science_pilot.slurm")],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert completed.returncode == 0, completed.stderr
    assert "-u" in completed.stdout
    assert "hard_goal_science_pilot_cell.py" in completed.stdout
    assert "--selector 7" in completed.stdout
    assert "--resume" in completed.stdout
    assert "--calibration-only" in completed.stdout
