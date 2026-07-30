from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pytest

from scripts.hard_goal_ladder_scan_cell import (
    build_parser as build_cell_parser,
    main as ladder_cell_main,
)
from spinglass3d import ladder_scan
from spinglass3d.ladder_scan import (
    build_ladder_scan_spec,
    load_ladder_scan_cell,
    prepare_ladder_scan,
    run_ladder_scan_cell,
    select_ladder_candidate,
)
from spinglass3d.pilot import (
    CALIBRATION_COMPLETE,
    CalibrationCheckpointParent,
    CalibrationExtensionSpec,
    CalibrationSpec,
)
from vmcrg_ref.artifacts import atomic_write_npz, sha256_file


TRACK = Path(__file__).resolve().parents[1]
REPO = TRACK.parents[2]
SOURCE = (
    TRACK
    / "results"
    / "hard_goal"
    / "stage6-b4-calibration-v2"
    / "cells"
    / "L12-J0000"
    / "manifest.json"
)
SOURCE_SHA256 = "7d6aba56023dde6a54c52cd95550075a34775b9eeb27c8df66f2c0a846c418e3"
JOB = TRACK / "jobs" / "hard_goal_ladder_scan.slurm"


def _copy_source(tmp_path: Path) -> Path:
    destination = tmp_path / "source-cell"
    shutil.copytree(SOURCE.parent, destination)
    return destination / "manifest.json"


def _rewrite_json(path: Path, payload: dict[str, object]) -> str:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="ascii")
    return sha256_file(path)


def _prepared_scan(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    output = tmp_path / "ladder-scan-v1"
    package = prepare_ladder_scan(SOURCE, SOURCE_SHA256, output)
    return output / "run_spec.json", package


def _write_measured_manifest(
    path: Path,
    spec: CalibrationSpec,
    *,
    acceptance: float,
    round_trips_min: int,
    edge_override: tuple[int, float] | None = None,
) -> Path:
    attempts = [100] * (len(spec.temperatures) - 1)
    acceptances = [acceptance] * len(attempts)
    if edge_override is not None:
        acceptances[edge_override[0]] = edge_override[1]
    accepts = [int(round(100 * value)) for value in acceptances]
    exact_acceptance = [value / 100 for value in accepts]
    target_passed = all(0.20 <= value <= 0.50 for value in exact_acceptance)
    payload = {
        "schema_version": 1,
        "stage": "stage6",
        "classification": CALIBRATION_COMPLETE,
        "status": "complete",
        "scope": "stage6-ladder-calibration-only",
        "tc_evidence": False,
        "second_rg_enabled": False,
        "cell_id": spec.cell_id,
        "spec": asdict(spec),
        "spec_sha256": spec.sha256,
        "completed_sweeps": spec.calibration_sweeps,
        "parallel_tempering": {
            "all_edges_attempted": True,
            "edge_attempts": attempts,
            "edge_accepts": accepts,
            "edge_acceptance": exact_acceptance,
            "bottleneck_passed": target_passed,
            "target_band_passed": target_passed,
            "ladder_decision": "PASS" if target_passed else "RECALIBRATE",
            "round_trips_min": round_trips_min,
            "round_trips_max": round_trips_min + 2,
        },
        "artifact_hashes": {},
    }
    path.parent.mkdir(parents=True)
    _rewrite_json(path, payload)
    return path


def _write_extension_manifest(
    root: Path,
    base_package_manifest: Path,
    planned: CalibrationSpec,
    *,
    acceptance: float = 0.30,
    round_trips_min: int = 8,
    changed_base_ladder: bool = False,
    reset_counters: bool = False,
) -> Path:
    temperatures = list(planned.temperatures)
    if changed_base_ladder:
        temperatures[1] -= 1e-6
    source_parent = root / "source-parent"
    parent_checkpoint = source_parent / "checkpoint"
    parent_checkpoint.mkdir(parents=True)
    parent_state = parent_checkpoint / "state.npz"
    temperatures_count = len(planned.temperatures)
    walkers = 2 * planned.chain_pairs

    def write_state(
        path: Path,
        completed: int,
        *,
        trip_minimum: int,
        trip_maximum: int,
    ) -> dict[str, np.ndarray]:
        replica_ids = np.broadcast_to(
            np.arange(temperatures_count, dtype=np.int64)[None, :, None],
            (1, temperatures_count, walkers),
        ).copy()
        tracker_shape = (1, walkers, temperatures_count)
        spins_shape = (
            1,
            temperatures_count,
            walkers,
            planned.length,
            planned.length,
            planned.length,
        )
        edge_indices = np.arange(temperatures_count - 1, dtype=np.int64)
        attempt_rounds = np.where(
            edge_indices % 2 == 0,
            (completed + 1) // 2,
            completed // 2,
        )
        swap_attempts = attempt_rounds * walkers
        swap_accepts = np.rint(swap_attempts * acceptance).astype(np.int64)
        round_trips = np.full(tracker_shape, trip_minimum, dtype=np.int64)
        round_trips.flat[-1] = trip_maximum
        arrays = {
            "spins": np.ones(spins_shape, dtype=np.int8),
            "local_jax_key": np.zeros(2, dtype=np.uint32),
            "local_accepted_changes": np.asarray(0, dtype=np.int64),
            "local_proposed_changes": np.asarray(
                completed * int(np.prod(spins_shape)), dtype=np.int64
            ),
            "swap_key": np.zeros(2, dtype=np.uint32),
            "replica_ids": replica_ids,
            "swap_attempts": swap_attempts,
            "swap_accepts": swap_accepts,
            "sweep_count": np.asarray(completed, dtype=np.int64),
            "round_trip_phase": np.zeros(tracker_shape, dtype=np.int8),
            "round_trips": round_trips,
            "time_since_endpoint": np.zeros(tracker_shape, dtype=np.int64),
        }
        atomic_write_npz(
            path,
            arrays,
        )
        return arrays

    def travel_snapshot(arrays: dict[str, np.ndarray]) -> dict[str, object]:
        phase = arrays["round_trip_phase"]
        trips = arrays["round_trips"]
        timers = arrays["time_since_endpoint"]
        return {
            "phase_counts": {
                str(value): int(np.count_nonzero(phase == value)) for value in range(3)
            },
            "completed_tracker_count": int(np.count_nonzero(trips > 0)),
            "endpoint_timer": {
                "minimum": int(np.min(timers)),
                "maximum": int(np.max(timers)),
                "mean": float(np.mean(timers, dtype=np.float64)),
            },
        }

    parent_arrays = write_state(
        parent_state,
        planned.calibration_sweeps,
        trip_minimum=max(0, round_trips_min // 2),
        trip_maximum=max(0, round_trips_min // 2) + 1,
    )
    parent_metadata = {
        "schema_version": 1,
        "completed_sweeps": planned.calibration_sweeps,
        "spec_sha256": planned.sha256,
        "state_sha256": sha256_file(parent_state),
    }
    _rewrite_json(parent_checkpoint / "metadata.json", parent_metadata)
    parent_manifest = source_parent / "manifest.json"
    _rewrite_json(
        parent_manifest,
        {
            "schema_version": 1,
            "stage": "stage6",
            "classification": CALIBRATION_COMPLETE,
            "status": "complete",
            "scope": "stage6-ladder-calibration-only",
            "tc_evidence": False,
            "second_rg_enabled": False,
            "cell_id": planned.cell_id,
            "spec": asdict(planned),
            "spec_sha256": planned.sha256,
            "completed_sweeps": planned.calibration_sweeps,
            "artifact_hashes": {
                "checkpoint/metadata.json": sha256_file(
                    parent_checkpoint / "metadata.json"
                ),
                "checkpoint/state.npz": sha256_file(parent_state),
            },
        },
    )
    repo_root = root / "repo"
    package_root = repo_root / "results" / "hard_goal" / root.name
    ladder_scan.prepare_ladder_extension(
        parent_manifest,
        base_package_manifest,
        target_completed_sweeps=8192,
        run_id=root.name,
        output=package_root,
    )
    package_run_spec = json.loads(
        (package_root / "run_spec.json").read_text(encoding="ascii")
    )
    extension = CalibrationExtensionSpec.from_payload(
        package_run_spec["cells"][0]["extension_spec"]
    )
    if changed_base_ladder:
        payload = asdict(extension)
        payload["temperatures"] = temperatures
        extension = CalibrationExtensionSpec.from_payload(payload)
    parent = extension.parent
    output = package_root / "cells" / extension.cell_id
    child_checkpoint = output / "checkpoint"
    child_checkpoint.mkdir(parents=True)
    child_state = child_checkpoint / "state.npz"
    child_arrays = write_state(
        child_state,
        extension.target_completed_sweeps,
        trip_minimum=round_trips_min,
        trip_maximum=round_trips_min + 2,
    )
    actual_attempts = child_arrays["swap_attempts"]
    actual_accepts = child_arrays["swap_accepts"]
    parent_attempts = parent_arrays["swap_attempts"]
    parent_accepts = parent_arrays["swap_accepts"]
    window_attempts_array = actual_attempts - parent_attempts
    window_accepts_array = actual_accepts - parent_accepts
    cumulative_attempts_array = (
        window_attempts_array if reset_counters else actual_attempts
    )
    cumulative_accepts_array = (
        window_accepts_array if reset_counters else actual_accepts
    )
    cumulative_attempts = [int(value) for value in cumulative_attempts_array]
    cumulative_accepts = [int(value) for value in cumulative_accepts_array]
    window_attempts = [int(value) for value in window_attempts_array]
    window_accepts = [int(value) for value in window_accepts_array]
    cumulative_acceptance = [
        accepted / attempted
        for accepted, attempted in zip(cumulative_accepts, cumulative_attempts, strict=True)
    ]
    window_acceptance = [
        accepted / attempted
        for accepted, attempted in zip(window_accepts, window_attempts, strict=True)
    ]
    child_metadata = {
        "schema_version": 1,
        "completed_sweeps": extension.target_completed_sweeps,
        "spec_sha256": extension.sha256,
        "state_sha256": sha256_file(child_state),
    }
    _rewrite_json(child_checkpoint / "metadata.json", child_metadata)
    final_checkpoint = output / "checkpoints" / (
        f"sweep-{extension.target_completed_sweeps:09d}"
    )
    shutil.copytree(child_checkpoint, final_checkpoint)
    path = output / "manifest.json"
    spin_proposals = int(
        child_arrays["local_proposed_changes"]
        - parent_arrays["local_proposed_changes"]
    )
    payload = {
        "schema_version": 1,
        "stage": "stage6",
        "phase": "calibration_extension",
        "classification": "CALIBRATION_EXTENSION_COMPLETE",
        "scope": "stage6-ladder-calibration-extension-only",
        "status": "complete",
        "scientific_evidence": False,
        "tc_evidence": False,
        "second_rg_enabled": False,
        "cell_id": extension.cell_id,
        "extension_spec": asdict(extension),
        "extension_spec_sha256": extension.sha256,
        "lineage": {
            "base_cell_id": extension.base_cell_id,
            "base_run_id": extension.base_run_id,
            "base_run_spec_sha256": extension.base_run_spec_sha256,
            "base_package_manifest_sha256": extension.base_package_manifest_sha256,
            "base_calibration_spec_sha256": extension.base_calibration_spec_sha256,
            "parent_cell_id": parent.cell_id,
            "parent_manifest_kind": parent.manifest_kind,
            "parent_manifest_sha256": parent.manifest_sha256,
            "parent_checkpoint_spec_sha256": parent.checkpoint_spec_sha256,
            "parent_checkpoint_metadata_sha256": parent.checkpoint_metadata_sha256,
            "parent_checkpoint_state_sha256": parent.checkpoint_state_sha256,
        },
        "start_completed_sweeps": parent.completed_sweeps,
        "completed_sweeps": extension.target_completed_sweeps,
        "parallel_tempering": {
            "all_edges_attempted": True,
            "edge_attempts": cumulative_attempts,
            "edge_accepts": cumulative_accepts,
            "edge_acceptance": cumulative_acceptance,
            "bottleneck_passed": True,
            "target_band_passed": True,
            "ladder_decision": "PASS",
            "round_trips_min": round_trips_min,
            "round_trips_max": round_trips_min + 2,
            "extension_window": {
                "start_completed_sweeps": parent.completed_sweeps,
                "completed_sweeps": extension.target_completed_sweeps,
                "all_edges_attempted": True,
                "edge_attempts": window_attempts,
                "edge_accepts": window_accepts,
                "edge_acceptance": window_acceptance,
                "target_band_passed": True,
            },
        },
        "travel": {
            "parent": travel_snapshot(parent_arrays),
            "child": travel_snapshot(child_arrays),
        },
        "runtime": {
            "host": "test-host",
            "python": "3.test",
            "jax": "0.test",
            "jaxlib": "0.test",
            "default_backend": "gpu",
            "devices": ["test-gpu"],
            "x64_enabled": True,
            "elapsed_seconds": 1.0,
            "spin_proposals": spin_proposals,
            "spin_proposals_per_second": float(spin_proposals),
            "invocation_spin_proposals": spin_proposals,
            "peak_host_memory_bytes": 1,
            "peak_device_memory_bytes": 1,
            "backend_compile_seconds": 0.0,
            "checkpoint_bytes": 1,
        },
    }
    payload["artifact_hashes"] = {
        str(artifact.relative_to(output)): sha256_file(artifact)
        for artifact in sorted(output.rglob("*"))
        if artifact.is_file() and artifact != path
    }
    _rewrite_json(path, payload)
    return path


def test_v2_proxy_builds_two_predicted_only_monotone_paired_ladders() -> None:
    spec = build_ladder_scan_spec(SOURCE, SOURCE_SHA256, "ladder-scan-v1")

    assert spec["classification"] == "PLANNED"
    assert spec["scientific_evidence"] is False
    assert spec["tc_evidence"] is False
    assert spec["second_rg_enabled"] is False
    assert spec["axes"] == {"target_acceptance": [0.35, 0.40]}
    assert spec["array"] == {"count": 2, "index_origin": 1}
    assert spec["provenance"]["source_manifest_sha256"] == SOURCE_SHA256

    proxy = spec["settings"]["proxy"]
    assert proxy["classification"] == "PREDICTED_ONLY"
    assert proxy["measured_success"] is False
    assert proxy["source_edge_count"] == 47
    assert proxy["ell_total"] == pytest.approx(10.50336447713287, abs=1e-14)
    assert proxy["sigma_ell_total"] == pytest.approx(
        0.021379864560097675, abs=1e-15
    )
    assert set(proxy["formula"]) == {
        "edge_metric",
        "acceptance_uncertainty",
        "edge_metric_uncertainty",
        "total_metric",
        "total_uncertainty",
        "edge_count",
        "interpolation",
    }

    cells = spec["cells"]
    assert [cell["array_index"] for cell in cells] == [1, 2]
    assert [cell["params"]["target_acceptance"] for cell in cells] == [0.35, 0.40]
    assert [len(cell["params"]["temperatures"]) for cell in cells] == [17, 19]
    assert [cell["params"]["prediction"]["edge_count"] for cell in cells] == [16, 18]
    assert [
        (
            cell["params"]["prediction"]["one_sigma_temperature_count_min"],
            cell["params"]["prediction"]["one_sigma_temperature_count_max"],
        )
        for cell in cells
    ] == [(17, 17), (19, 19)]

    paired = ("length", "j_seed", "chain_pairs", "calibration_sweeps")
    assert all(cells[0]["params"][name] == cells[1]["params"][name] for name in paired)
    for cell in cells:
        params = cell["params"]
        betas = np.asarray(params["betas"], dtype=np.float64)
        temperatures = np.asarray(params["temperatures"], dtype=np.float64)
        assert params["prediction"]["classification"] == "PREDICTED_ONLY"
        assert params["prediction"]["measured_success"] is False
        assert betas[0] == 0.5
        assert betas[-1] == 1.25
        assert np.all(np.diff(betas) > 0.0)
        assert np.all(np.diff(temperatures) < 0.0)
        np.testing.assert_allclose(temperatures, 1.0 / betas, rtol=0.0, atol=0.0)


def test_source_manifest_sha256_is_verified_before_planning() -> None:
    with pytest.raises(ValueError, match="manifest SHA-256"):
        build_ladder_scan_spec(SOURCE, "0" * 64, "ladder-scan-v1")


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda payload: payload.__setitem__("classification", "PASS"), "classification"),
        (
            lambda payload: payload["parallel_tempering"].__setitem__(
                "ladder_decision", "PASS"
            ),
            "RECALIBRATE",
        ),
        (
            lambda payload: payload["parallel_tempering"]["edge_acceptance"].pop(),
            "47 edges",
        ),
    ],
)
def test_source_manifest_semantics_fail_closed(
    tmp_path: Path,
    mutation,
    message: str,
) -> None:
    source = _copy_source(tmp_path)
    payload = json.loads(source.read_text(encoding="ascii"))
    mutation(payload)
    digest = _rewrite_json(source, payload)
    with pytest.raises(ValueError, match=message):
        build_ladder_scan_spec(source, digest, "ladder-scan-v1")


def test_source_artifact_inventory_is_rehashed(tmp_path: Path) -> None:
    source = _copy_source(tmp_path)
    checkpoint = source.parent / "checkpoint" / "metadata.json"
    checkpoint.write_text("{}\n", encoding="ascii")
    with pytest.raises(ValueError, match="source artifact hash mismatch"):
        build_ladder_scan_spec(source, sha256_file(source), "ladder-scan-v1")


def test_malformed_source_spec_fails_as_a_validation_error(tmp_path: Path) -> None:
    source = _copy_source(tmp_path)
    payload = json.loads(source.read_text(encoding="ascii"))
    payload["spec"]["source_hashes"] = None
    digest = _rewrite_json(source, payload)
    with pytest.raises(ValueError, match="source spec is invalid"):
        build_ladder_scan_spec(source, digest, "ladder-scan-v1")


def test_prepare_scan_publishes_a_hash_bound_immutable_package(tmp_path: Path) -> None:
    output = tmp_path / "ladder-scan-v1"
    package = prepare_ladder_scan(SOURCE, SOURCE_SHA256, output)

    assert package["classification"] == "PLANNED"
    assert package["scientific_evidence"] is False
    assert package["tc_evidence"] is False
    assert package["second_rg_enabled"] is False
    assert package["cell_count"] == 2
    assert set(package["artifacts"]) == {"run_spec.json"}
    assert package["artifacts"]["run_spec.json"] == sha256_file(
        output / "run_spec.json"
    )
    assert (output / "manifest.json").is_file()

    with pytest.raises(FileExistsError, match="overwrite"):
        prepare_ladder_scan(SOURCE, SOURCE_SHA256, output)
    empty = tmp_path / "already-exists"
    empty.mkdir()
    with pytest.raises(FileExistsError, match="overwrite"):
        prepare_ladder_scan(SOURCE, SOURCE_SHA256, empty)


def test_loader_verifies_package_hash_and_rebuilds_the_run_spec(tmp_path: Path) -> None:
    run_spec_path, _ = _prepared_scan(tmp_path)
    first, output = load_ladder_scan_cell(
        run_spec_path,
        "1",
        track_root=TRACK,
        repo_root=REPO,
    )
    assert isinstance(first, CalibrationSpec)
    assert first.cell_id.endswith("A035")
    assert len(first.temperatures) == 17
    assert first.length == 12
    assert first.j_seed == 6179799987848167288
    assert first.chain_pairs == 4
    assert first.calibration_sweeps == 4096
    assert first.source_hashes["run_spec.json"] == sha256_file(run_spec_path)
    assert output == REPO / "results" / "hard_goal" / "ladder-scan-v1" / "cells" / first.cell_id

    payload = json.loads(run_spec_path.read_text(encoding="ascii"))
    payload["cells"][0]["params"]["target_acceptance"] = 0.36
    _rewrite_json(run_spec_path, payload)
    with pytest.raises(ValueError, match="package hash"):
        load_ladder_scan_cell(
            run_spec_path,
            "1",
            track_root=TRACK,
            repo_root=REPO,
        )

    package_path = run_spec_path.parent / "manifest.json"
    package = json.loads(package_path.read_text(encoding="ascii"))
    package["artifacts"]["run_spec.json"] = sha256_file(run_spec_path)
    _rewrite_json(package_path, package)
    with pytest.raises(ValueError, match="generated scan"):
        load_ladder_scan_cell(
            run_spec_path,
            "1",
            track_root=TRACK,
            repo_root=REPO,
        )


def test_cell_runner_passes_a_real_planned_calibration_spec_to_the_heavy_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_spec_path, _ = _prepared_scan(tmp_path)
    calls: list[tuple[CalibrationSpec, Path, dict[str, object]]] = []

    def fake_calibration(
        spec: CalibrationSpec,
        output: Path,
        **kwargs: object,
    ) -> dict[str, object]:
        calls.append((spec, output, kwargs))
        return {
            "cell_id": spec.cell_id,
            "classification": CALIBRATION_COMPLETE,
            "parallel_tempering": {"ladder_decision": "PASS"},
        }

    monkeypatch.setattr(ladder_scan, "run_ladder_calibration", fake_calibration)
    manifest = run_ladder_scan_cell(
        run_spec_path,
        "2",
        required_platform="gpu",
        checkpoint_every=128,
        resume=True,
        track_root=TRACK,
        repo_root=REPO,
    )

    assert manifest["classification"] == CALIBRATION_COMPLETE
    assert len(calls) == 1
    planned, output, options = calls[0]
    assert type(planned) is CalibrationSpec
    assert planned.cell_id.endswith("A040")
    assert len(planned.temperatures) == 19
    assert output.name == planned.cell_id
    assert options == {
        "required_platform": "gpu",
        "checkpoint_every": 128,
        "resume": True,
    }


def test_cell_cli_dry_run_resolves_an_opaque_scan_cell(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_spec_path, _ = _prepared_scan(tmp_path)
    arguments = [
        "--run-spec",
        str(run_spec_path),
        "--selector",
        "2",
        "--require-platform",
        "gpu",
        "--checkpoint-every",
        "128",
        "--dry-run",
    ]
    parsed = build_cell_parser().parse_args(arguments)
    assert parsed.selector == "2"
    assert parsed.dry_run is True
    assert ladder_cell_main(arguments) == 0
    dry_run = json.loads(capsys.readouterr().out)
    assert dry_run["cell_id"].endswith("A040")
    assert dry_run["temperature_count"] == 19
    assert dry_run["predicted_only"] is True


def test_selector_ranks_passing_measurements_by_round_trips_then_ladder_size(
    tmp_path: Path,
) -> None:
    run_spec_path, _ = _prepared_scan(tmp_path)
    spec35, _ = load_ladder_scan_cell(run_spec_path, "1", track_root=TRACK, repo_root=REPO)
    spec40, _ = load_ladder_scan_cell(run_spec_path, "2", track_root=TRACK, repo_root=REPO)
    measured35 = _write_measured_manifest(
        tmp_path / "measured-35" / "manifest.json",
        spec35,
        acceptance=0.30,
        round_trips_min=4,
    )
    measured40 = _write_measured_manifest(
        tmp_path / "measured-40" / "manifest.json",
        spec40,
        acceptance=0.40,
        round_trips_min=7,
    )

    selection = select_ladder_candidate(run_spec_path, [measured35, measured40])
    assert selection["decision"] == "SELECT"
    assert selection["selected_cell_id"] == spec40.cell_id
    assert selection["selected_temperature_count"] == 19
    assert selection["selected_round_trips_min"] == 7
    assert selection["tc_evidence"] is False
    assert selection["second_rg_enabled"] is False
    assert [record["status"] for record in selection["candidates"]] == [
        "accepted",
        "accepted",
    ]
    assert {record["manifest_sha256"] for record in selection["candidates"]} == {
        sha256_file(measured35),
        sha256_file(measured40),
    }

    tied40 = json.loads(measured40.read_text(encoding="ascii"))
    tied40["parallel_tempering"]["round_trips_min"] = 4
    _rewrite_json(measured40, tied40)
    tied = select_ladder_candidate(run_spec_path, [measured40, measured35])
    assert tied["selected_cell_id"] == spec35.cell_id
    assert tied["selected_temperature_count"] == 17


def test_selector_rejects_zero_round_trips_even_when_every_edge_is_in_band(
    tmp_path: Path,
) -> None:
    run_spec_path, _ = _prepared_scan(tmp_path)
    spec35, _ = load_ladder_scan_cell(
        run_spec_path,
        "1",
        track_root=TRACK,
        repo_root=REPO,
    )
    measured = _write_measured_manifest(
        tmp_path / "measured-35" / "manifest.json",
        spec35,
        acceptance=0.35,
        round_trips_min=0,
    )

    selection = select_ladder_candidate(run_spec_path, [measured])

    assert selection["decision"] == "RECALIBRATE"
    assert selection["selected_cell_id"] is None
    assert selection["candidates"][0]["status"] == "rejected"
    assert "complete round trip" in " ".join(
        selection["candidates"][0]["failures"]
    )


def test_selector_preserves_all_failures_and_recalibrates_when_none_pass(
    tmp_path: Path,
) -> None:
    run_spec_path, _ = _prepared_scan(tmp_path)
    spec35, _ = load_ladder_scan_cell(run_spec_path, "1", track_root=TRACK, repo_root=REPO)
    spec40, _ = load_ladder_scan_cell(run_spec_path, "2", track_root=TRACK, repo_root=REPO)
    measured35 = _write_measured_manifest(
        tmp_path / "measured-35" / "manifest.json",
        spec35,
        acceptance=0.30,
        round_trips_min=8,
        edge_override=(3, 0.51),
    )
    measured40 = _write_measured_manifest(
        tmp_path / "measured-40" / "manifest.json",
        spec40,
        acceptance=0.40,
        round_trips_min=9,
        edge_override=(5, 0.19),
    )

    selection = select_ladder_candidate(run_spec_path, [measured35, measured40])
    assert selection["decision"] == "RECALIBRATE"
    assert selection["selected_cell_id"] is None
    assert [record["status"] for record in selection["candidates"]] == [
        "rejected",
        "rejected",
    ]
    assert all(record["failures"] for record in selection["candidates"])
    assert "outside [0.20, 0.50]" in " ".join(
        failure
        for record in selection["candidates"]
        for failure in record["failures"]
    )


def test_selector_rejects_a_manifest_for_a_different_planned_spec(
    tmp_path: Path,
) -> None:
    run_spec_path, _ = _prepared_scan(tmp_path)
    spec35, _ = load_ladder_scan_cell(run_spec_path, "1", track_root=TRACK, repo_root=REPO)
    measured = _write_measured_manifest(
        tmp_path / "measured" / "manifest.json",
        spec35,
        acceptance=0.30,
        round_trips_min=8,
    )
    payload = json.loads(measured.read_text(encoding="ascii"))
    payload["spec_sha256"] = "0" * 64
    _rewrite_json(measured, payload)

    selection = select_ladder_candidate(run_spec_path, [measured])
    assert selection["decision"] == "RECALIBRATE"
    assert [record["status"] for record in selection["candidates"]] == [
        "rejected",
        "missing",
    ]
    assert "planned CalibrationSpec" in selection["candidates"][0]["failures"][0]


def test_selector_accepts_bound_extension_evidence_for_original_parent_cell(
    tmp_path: Path,
) -> None:
    run_spec_path, _ = _prepared_scan(tmp_path)
    spec35, _ = load_ladder_scan_cell(run_spec_path, "1", track_root=TRACK, repo_root=REPO)
    spec40, _ = load_ladder_scan_cell(run_spec_path, "2", track_root=TRACK, repo_root=REPO)
    extension35 = _write_extension_manifest(
        tmp_path / "extension-35",
        run_spec_path.parent / "manifest.json",
        spec35,
        round_trips_min=9,
    )
    measured40 = _write_measured_manifest(
        tmp_path / "measured-40" / "manifest.json",
        spec40,
        acceptance=0.40,
        round_trips_min=7,
    )

    selection = select_ladder_candidate(
        run_spec_path,
        [extension35, measured40],
        repo_root=tmp_path / "extension-35" / "repo",
    )

    assert selection["decision"] == "SELECT"
    assert selection["selected_cell_id"] == spec35.cell_id
    assert selection["selected_round_trips_min"] == 9
    assert selection["candidates"][0]["status"] == "accepted"
    assert selection["candidates"][0]["evidence_kind"] == "calibration_extension"


def test_selector_reads_historical_scan_after_source_evolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_spec_path, _ = _prepared_scan(tmp_path)
    spec35, _ = load_ladder_scan_cell(run_spec_path, "1", track_root=TRACK, repo_root=REPO)
    measured = _write_measured_manifest(
        tmp_path / "measured" / "manifest.json",
        spec35,
        acceptance=0.35,
        round_trips_min=2,
    )
    original_build = ladder_scan.build_ladder_scan_spec

    def evolved_build(*args: object, **kwargs: object) -> dict[str, object]:
        expected = original_build(*args, **kwargs)
        expected["provenance"]["source_sha256"]["src/spinglass3d/ladder_scan.py"] = (
            "f" * 64
        )
        return expected

    monkeypatch.setattr(ladder_scan, "build_ladder_scan_spec", evolved_build)

    with pytest.raises(ValueError, match="fixed generated scan"):
        load_ladder_scan_cell(run_spec_path, "1", track_root=TRACK, repo_root=REPO)

    selection = select_ladder_candidate(
        run_spec_path,
        [measured],
        track_root=TRACK,
        repo_root=REPO,
    )
    assert selection["decision"] == "SELECT"
    assert selection["selected_cell_id"] == spec35.cell_id


def test_selector_reads_historical_extension_after_source_evolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_spec_path, _ = _prepared_scan(tmp_path)
    spec35, _ = load_ladder_scan_cell(run_spec_path, "1", track_root=TRACK, repo_root=REPO)
    spec40, _ = load_ladder_scan_cell(run_spec_path, "2", track_root=TRACK, repo_root=REPO)
    extension35 = _write_extension_manifest(
        tmp_path / "extension-35",
        run_spec_path.parent / "manifest.json",
        spec35,
        round_trips_min=9,
    )
    measured40 = _write_measured_manifest(
        tmp_path / "measured-40" / "manifest.json",
        spec40,
        acceptance=0.40,
        round_trips_min=7,
    )
    original_sources = ladder_scan._extension_source_hashes

    def evolved_sources(*args: object, **kwargs: object) -> dict[str, str]:
        hashes = original_sources(*args, **kwargs)
        hashes["src/spinglass3d/ladder_scan.py"] = "f" * 64
        return hashes

    monkeypatch.setattr(ladder_scan, "_extension_source_hashes", evolved_sources)
    package_run_spec = extension35.resolve().parents[2] / "run_spec.json"

    with pytest.raises(ValueError, match="current execution sources"):
        ladder_scan.load_ladder_extension_cell(
            package_run_spec,
            extension35.parent.name,
            track_root=TRACK,
            repo_root=tmp_path / "extension-35" / "repo",
        )

    selection = select_ladder_candidate(
        run_spec_path,
        [extension35, measured40],
        track_root=TRACK,
        repo_root=tmp_path / "extension-35" / "repo",
    )
    assert selection["decision"] == "SELECT"
    assert selection["selected_cell_id"] == spec35.cell_id


@pytest.mark.parametrize("failure_kind", ["changed_base_ladder", "reset_counters"])
def test_selector_rejects_extension_with_changed_base_ladder_or_reset_counters(
    tmp_path: Path,
    failure_kind: str,
) -> None:
    run_spec_path, _ = _prepared_scan(tmp_path)
    spec35, _ = load_ladder_scan_cell(run_spec_path, "1", track_root=TRACK, repo_root=REPO)
    extension = _write_extension_manifest(
        tmp_path / failure_kind,
        run_spec_path.parent / "manifest.json",
        spec35,
        changed_base_ladder=failure_kind == "changed_base_ladder",
        reset_counters=failure_kind == "reset_counters",
    )

    selection = select_ladder_candidate(
        run_spec_path,
        [extension],
        repo_root=tmp_path / failure_kind / "repo",
    )

    record = selection["candidates"][0]
    assert selection["decision"] == "RECALIBRATE"
    assert record["status"] == "rejected"
    assert failure_kind.replace("_", " ") in " ".join(record["failures"])


def test_selector_legacy_calibration_behavior_is_unchanged(tmp_path: Path) -> None:
    run_spec_path, _ = _prepared_scan(tmp_path)
    spec35, _ = load_ladder_scan_cell(run_spec_path, "1", track_root=TRACK, repo_root=REPO)
    measured = _write_measured_manifest(
        tmp_path / "legacy" / "manifest.json",
        spec35,
        acceptance=0.30,
        round_trips_min=4,
    )

    selection = select_ladder_candidate(run_spec_path, [measured])

    assert selection["decision"] == "SELECT"
    assert selection["selected_cell_id"] == spec35.cell_id
    assert selection["candidates"][0]["status"] == "accepted"
    assert "evidence_kind" not in selection["candidates"][0]


def test_selector_malformed_extension_window_fails_closed(tmp_path: Path) -> None:
    run_spec_path, _ = _prepared_scan(tmp_path)
    spec35, _ = load_ladder_scan_cell(run_spec_path, "1", track_root=TRACK, repo_root=REPO)
    extension = _write_extension_manifest(
        tmp_path / "malformed-window",
        run_spec_path.parent / "manifest.json",
        spec35,
    )
    payload = json.loads(extension.read_text(encoding="ascii"))
    payload["parallel_tempering"]["extension_window"]["edge_acceptance"] = None
    _rewrite_json(extension, payload)

    selection = select_ladder_candidate(
        run_spec_path,
        [extension],
        repo_root=tmp_path / "malformed-window" / "repo",
    )

    assert selection["decision"] == "RECALIBRATE"
    assert selection["candidates"][0]["status"] == "rejected"
    assert "extension window" in " ".join(selection["candidates"][0]["failures"])


def test_selector_rejects_unbound_extension_evidence(tmp_path: Path) -> None:
    run_spec_path, _ = _prepared_scan(tmp_path)
    spec35, _ = load_ladder_scan_cell(run_spec_path, "1", track_root=TRACK, repo_root=REPO)
    bound = _write_extension_manifest(
        tmp_path / "bound-extension",
        run_spec_path.parent / "manifest.json",
        spec35,
    )
    unbound = tmp_path / "unbound" / "manifest.json"
    shutil.copytree(bound.parent, unbound.parent)

    selection = select_ladder_candidate(
        run_spec_path,
        [unbound],
        repo_root=tmp_path / "bound-extension" / "repo",
    )

    assert selection["decision"] == "RECALIBRATE"
    assert selection["candidates"][0]["status"] == "rejected"
    assert "package" in " ".join(selection["candidates"][0]["failures"])


def test_selector_rejects_hash_consistent_noncheckpoint_state(tmp_path: Path) -> None:
    run_spec_path, _ = _prepared_scan(tmp_path)
    spec35, _ = load_ladder_scan_cell(run_spec_path, "1", track_root=TRACK, repo_root=REPO)
    terminal = _write_extension_manifest(
        tmp_path / "invalid-child-state",
        run_spec_path.parent / "manifest.json",
        spec35,
    )
    state = terminal.parent / "checkpoint" / "state.npz"
    state.write_bytes(b"not an npz checkpoint")
    metadata_path = terminal.parent / "checkpoint" / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="ascii"))
    metadata["state_sha256"] = sha256_file(state)
    _rewrite_json(metadata_path, metadata)
    payload = json.loads(terminal.read_text(encoding="ascii"))
    payload["artifact_hashes"]["checkpoint/metadata.json"] = sha256_file(
        metadata_path
    )
    payload["artifact_hashes"]["checkpoint/state.npz"] = sha256_file(state)
    _rewrite_json(terminal, payload)

    selection = select_ladder_candidate(
        run_spec_path,
        [terminal],
        repo_root=tmp_path / "invalid-child-state" / "repo",
    )

    assert selection["decision"] == "RECALIBRATE"
    assert selection["candidates"][0]["status"] == "rejected"
    assert "checkpoint state" in " ".join(selection["candidates"][0]["failures"])


@pytest.mark.parametrize(
    "tamper",
    [
        "cumulative_counts",
        "window_counts",
        "round_trips",
        "travel",
        "runtime",
        "target_checkpoint",
    ],
)
def test_selector_rejects_extension_manifest_not_bound_to_checkpoint_state(
    tmp_path: Path,
    tamper: str,
) -> None:
    run_spec_path, _ = _prepared_scan(tmp_path)
    spec35, _ = load_ladder_scan_cell(run_spec_path, "1", track_root=TRACK, repo_root=REPO)
    terminal = _write_extension_manifest(
        tmp_path / tamper,
        run_spec_path.parent / "manifest.json",
        spec35,
    )
    payload = json.loads(terminal.read_text(encoding="ascii"))
    parallel = payload["parallel_tempering"]
    if tamper == "cumulative_counts":
        parallel["edge_accepts"][0] += 1
        parallel["edge_acceptance"][0] = (
            parallel["edge_accepts"][0] / parallel["edge_attempts"][0]
        )
    elif tamper == "window_counts":
        window = parallel["extension_window"]
        window["edge_accepts"][0] += 1
        window["edge_acceptance"][0] = (
            window["edge_accepts"][0] / window["edge_attempts"][0]
        )
    elif tamper == "round_trips":
        parallel["round_trips_max"] += 1
    elif tamper == "travel":
        payload["travel"]["child"]["completed_tracker_count"] -= 1
    elif tamper == "runtime":
        del payload["runtime"]
    else:
        shutil.rmtree(terminal.parent / "checkpoints")
        payload["artifact_hashes"] = {
            str(artifact.relative_to(terminal.parent)): sha256_file(artifact)
            for artifact in sorted(terminal.parent.rglob("*"))
            if artifact.is_file() and artifact != terminal
        }
    _rewrite_json(terminal, payload)

    selection = select_ladder_candidate(
        run_spec_path,
        [terminal],
        repo_root=tmp_path / tamper / "repo",
    )

    assert selection["candidates"][0]["status"] == "rejected"


def test_selector_rejects_cpu_extension_runtime_as_scientific_evidence(
    tmp_path: Path,
) -> None:
    run_spec_path, _ = _prepared_scan(tmp_path)
    spec35, _ = load_ladder_scan_cell(run_spec_path, "1", track_root=TRACK, repo_root=REPO)
    terminal = _write_extension_manifest(
        tmp_path / "cpu-runtime",
        run_spec_path.parent / "manifest.json",
        spec35,
    )
    payload = json.loads(terminal.read_text(encoding="ascii"))
    payload["runtime"]["default_backend"] = "cpu"
    _rewrite_json(terminal, payload)

    selection = select_ladder_candidate(
        run_spec_path,
        [terminal],
        repo_root=tmp_path / "cpu-runtime" / "repo",
    )

    assert selection["candidates"][0]["status"] == "rejected"
    assert "local evidence" in " ".join(
        selection["candidates"][0]["failures"]
    ).lower()


def test_selector_accepts_cpu_extension_with_terminal_local_evidence(
    tmp_path: Path,
) -> None:
    run_spec_path, _ = _prepared_scan(tmp_path)
    spec35, _ = load_ladder_scan_cell(
        run_spec_path,
        "1",
        track_root=TRACK,
        repo_root=REPO,
    )
    spec40, _ = load_ladder_scan_cell(
        run_spec_path,
        "2",
        track_root=TRACK,
        repo_root=REPO,
    )
    terminal = _write_extension_manifest(
        tmp_path / "cpu-runtime-with-evidence",
        run_spec_path.parent / "manifest.json",
        spec35,
        round_trips_min=9,
    )
    payload = json.loads(terminal.read_text(encoding="ascii"))
    payload["runtime"]["default_backend"] = "cpu"
    payload["runtime"]["devices"] = ["TFRT_CPU_0"]
    payload["runtime"]["peak_device_memory_bytes"] = 0
    _rewrite_json(terminal, payload)
    coordinator = tmp_path / "cpu-coordinator.json"
    _rewrite_json(
        coordinator,
        {
            "schema_version": 1,
            "classification": "RUN_COMPLETE",
            "completed": ["cell"],
            "failed": [],
            "processes": {"cell": {"return_code": 0}},
            "metadata": {
                "stage": "stage6",
                "execution_policy": "LOCAL_COMPUTE_DEVIATION",
                "remote_execution": False,
            },
        },
    )
    package_root = terminal.resolve().parents[2]
    ladder_scan.write_local_extension_evidence(
        terminal,
        coordinator,
        "cell",
        package_root / "local_execution_evidence.json",
    )
    measured40 = _write_measured_manifest(
        tmp_path / "measured-40" / "manifest.json",
        spec40,
        acceptance=0.40,
        round_trips_min=7,
    )

    selection = select_ladder_candidate(
        run_spec_path,
        [terminal, measured40],
        repo_root=tmp_path / "cpu-runtime-with-evidence" / "repo",
    )

    assert selection["decision"] == "SELECT"
    assert selection["selected_cell_id"] == spec35.cell_id
    assert selection["candidates"][0]["status"] == "accepted"


def test_selector_requires_paired_evidence_before_extension_selection(
    tmp_path: Path,
) -> None:
    run_spec_path, _ = _prepared_scan(tmp_path)
    spec35, _ = load_ladder_scan_cell(run_spec_path, "1", track_root=TRACK, repo_root=REPO)
    extension = _write_extension_manifest(
        tmp_path / "extension-only",
        run_spec_path.parent / "manifest.json",
        spec35,
        round_trips_min=9,
    )

    selection = select_ladder_candidate(
        run_spec_path,
        [extension],
        repo_root=tmp_path / "extension-only" / "repo",
    )

    assert selection["decision"] == "RECALIBRATE"
    assert selection["selected_cell_id"] is None
    assert selection["candidates"][0]["status"] == "accepted"
    assert selection["candidates"][1]["status"] == "missing"


def test_slurm_wrapper_is_nounset_safe_profile_neutral_and_forwards_resume(
    tmp_path: Path,
) -> None:
    missing = subprocess.run(
        ["bash", str(JOB)],
        cwd=TRACK,
        capture_output=True,
        text=True,
        env=os.environ,
    )
    assert missing.returncode != 0
    assert "HARNESS_RUN_SPEC" in missing.stderr

    run_spec = tmp_path / "run_spec.json"
    run_spec.write_text("{}\n", encoding="ascii")
    argument_log = tmp_path / "arguments.txt"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_apptainer = fake_bin / "apptainer"
    fake_apptainer.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$ARGUMENT_LOG\"\nexit 7\n",
        encoding="ascii",
    )
    fake_apptainer.chmod(0o755)
    fake_nvidia_smi = fake_bin / "nvidia-smi"
    fake_nvidia_smi.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
    fake_nvidia_smi.chmod(0o755)
    fake_sha256sum = fake_bin / "sha256sum"
    fake_sha256sum.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in\n"
        "  *.sif) digest=59ebde5239057c558b86ef30ae12f6ffc7a8280e3244120f2dfd6397fa578b6c ;;\n"
        "  *.freeze.txt) digest=61f20c075caf592265e925aa297e7bb23bc1768d625a5781d479d139defcebca ;;\n"
        "  *hg3d-a800-requirements.txt) digest=614dac1c70184b8ddb4a7e9dc50ebd2d6b4399a5a038c43bced5de81b04266f3 ;;\n"
        "  *) exec /usr/bin/sha256sum \"$@\" ;;\n"
        "esac\n"
        "printf '%s  %s\\n' \"$digest\" \"$1\"\n",
        encoding="ascii",
    )
    fake_sha256sum.chmod(0o755)
    system_profile = tmp_path / "profile.sh"
    system_profile.write_text("module() { :; }\n", encoding="ascii")
    home = tmp_path / "home"
    sif = home / "scratch" / "containers" / "python-3.12.11-slim-bookworm.sif"
    sif.parent.mkdir(parents=True)
    sif.touch()
    venv = home / "scratch" / "hg3d-venv-v1"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "python").symlink_to("/bin/true")
    Path(str(venv) + ".freeze.txt").touch()
    base_environment = {
        **os.environ,
        "HARNESS_RUN_SPEC": str(run_spec),
        "SLURM_ARRAY_TASK_ID": "2",
        "SLURM_SUBMIT_DIR": str(REPO),
        "HARNESS_REPO_ROOT": str(REPO),
        "HARNESS_SYSTEM_PROFILE": str(system_profile),
        "HOME": str(home),
        "ARGUMENT_LOG": str(argument_log),
        "PATH": f"{fake_bin}:/usr/bin:/bin",
    }
    without_resume = subprocess.run(
        ["bash", str(JOB)],
        cwd=TRACK,
        capture_output=True,
        text=True,
        env=base_environment,
    )
    assert without_resume.returncode == 7
    arguments = argument_log.read_text(encoding="ascii").splitlines()
    assert arguments[:2] == ["exec", "--nv"]
    assert ["--bind", f"{REPO}:{REPO}"] == arguments[2:4]
    assert ["--pwd", str(TRACK)] == arguments[4:6]
    assert str(sif) in arguments
    assert str(venv / "bin" / "python") in arguments
    command_start = arguments.index("-u")
    assert arguments[command_start:] == [
        "-u",
        "scripts/hard_goal_ladder_scan_cell.py",
        "--run-spec",
        str(run_spec),
        "--selector",
        "2",
        "--require-platform",
        "gpu",
        "--checkpoint-every",
        "256",
    ]

    with_resume = subprocess.run(
        ["bash", str(JOB)],
        cwd=TRACK,
        capture_output=True,
        text=True,
        env={**base_environment, "HARNESS_RESUME": "1"},
    )
    assert with_resume.returncode == 7
    resumed_arguments = argument_log.read_text(encoding="ascii").splitlines()
    resumed_start = resumed_arguments.index("-u")
    assert resumed_arguments[resumed_start:] == [
        *arguments[command_start:],
        "--resume",
    ]

    source = JOB.read_text(encoding="ascii")
    for forbidden in (
        "--partition",
        "--gres",
        "--mem",
        "--time",
        "A800",
        "/home/",
        "/scratch/",
    ):
        assert forbidden not in source
