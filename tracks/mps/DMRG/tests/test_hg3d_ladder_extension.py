from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pytest

from spinglass3d import ladder_scan
from spinglass3d import pilot
from vmcrg_ref.artifacts import (
    atomic_write_npz,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)


TRACK = Path(__file__).resolve().parents[1]
REPO = TRACK.parents[2]
BASE = TRACK / "results" / "hard_goal" / "stage6-b4-l27-adaptive-v1"
PARENT = BASE / "cells" / "L27-J0000-A035" / "manifest.json"
PACKAGE = BASE / "manifest.json"
SCRIPT = TRACK / "scripts" / "hard_goal_ladder_extension_cell.py"
JOB = TRACK / "jobs" / "hard_goal_ladder_extension.slurm"


def _copy_parent(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "base"
    (root / "cells" / "L27-J0000-A035").mkdir(parents=True)
    shutil.copy2(BASE / "manifest.json", root / "manifest.json")
    shutil.copy2(BASE / "run_spec.json", root / "run_spec.json")
    shutil.copytree(
        PARENT.parent / "checkpoint",
        root / "cells" / "L27-J0000-A035" / "checkpoint",
    )
    shutil.copy2(PARENT, root / "cells" / "L27-J0000-A035" / "manifest.json")
    return root / "cells" / "L27-J0000-A035" / "manifest.json", root / "manifest.json"


def _rewrite(path: Path, payload: dict[str, object]) -> None:
    path.write_bytes(canonical_json_bytes(payload))


def _prepare(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    parent, package = _copy_parent(tmp_path)
    output = tmp_path / "extension-v1"
    result = ladder_scan.prepare_ladder_extension(
        parent,
        package,
        target_completed_sweeps=8192,
        run_id="extension-v1",
        output=output,
    )
    return output, result


def test_local_cpu_extension_requires_hash_bound_coordinator_evidence(
    tmp_path: Path,
) -> None:
    package_root, _ = _prepare(tmp_path)
    terminal = _write_terminal_extension(package_root)
    payload = json.loads(terminal.read_text(encoding="ascii"))
    payload["runtime"]["default_backend"] = "cpu"
    payload["runtime"]["devices"] = ["TFRT_CPU_0"]
    payload["runtime"]["peak_device_memory_bytes"] = 0
    _rewrite(terminal, payload)
    coordinator = tmp_path / "local_coordinator.json"
    _rewrite(
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
    evidence = tmp_path / "local-evidence.json"
    ladder_scan.write_local_extension_evidence(
        terminal,
        coordinator,
        "cell",
        evidence,
    )

    child = tmp_path / "extension-v2"
    package = ladder_scan.prepare_ladder_extension(
        terminal,
        package_root / "manifest.json",
        target_completed_sweeps=16384,
        run_id="extension-v2",
        output=child,
        local_execution_evidence=evidence,
    )

    assert package["classification"] == "PLANNED"
    assert (
        child / "parent/local_execution_evidence.json"
    ).is_file()
    run_spec = json.loads((child / "run_spec.json").read_text(encoding="ascii"))
    assert run_spec["local_execution_evidence"]["sha256"] == sha256_file(evidence)
    loaded, output, _ = ladder_scan.load_ladder_extension_cell(
        child / "run_spec.json",
        "1",
        track_root=TRACK,
        repo_root=tmp_path,
    )
    assert loaded.target_completed_sweeps == 16384
    assert output.name == loaded.cell_id


def _write_terminal_extension(
    package_root: Path,
    *,
    completed_sweeps: int | None = None,
    runner_shaped: bool = True,
) -> Path:
    run_spec = json.loads((package_root / "run_spec.json").read_text(encoding="ascii"))
    spec = pilot.CalibrationExtensionSpec.from_payload(
        run_spec["cells"][0]["extension_spec"]
    )
    completed = spec.target_completed_sweeps if completed_sweeps is None else completed_sweeps
    output = package_root / "cells" / spec.cell_id
    checkpoint = output / "checkpoint"
    checkpoint.mkdir(parents=True)
    state = checkpoint / "state.npz"
    with np.load(
        package_root / "parent" / "checkpoint" / "state.npz",
        allow_pickle=False,
    ) as archive:
        parent_arrays = {name: archive[name].copy() for name in archive.files}
    arrays = {name: value.copy() for name, value in parent_arrays.items()}
    spins = arrays["spins"]
    samples = spins.shape[0]
    walkers = spins.shape[2]
    edge_indices = np.arange(spins.shape[1] - 1, dtype=np.int64)
    arrays["sweep_count"] = np.asarray(completed, dtype=np.int64)
    arrays["local_proposed_changes"] = np.asarray(
        completed * spins.size,
        dtype=np.int64,
    )
    child_attempts = np.where(
        edge_indices % 2 == 0,
        (completed + 1) // 2,
        completed // 2,
    ) * samples * walkers
    parent_attempts = parent_arrays["swap_attempts"]
    window_attempts = child_attempts - parent_attempts
    window_accepts = np.rint(window_attempts * 0.30).astype(np.int64)
    arrays["swap_attempts"] = child_attempts
    arrays["swap_accepts"] = parent_arrays["swap_accepts"] + window_accepts
    arrays["round_trips"] = np.full_like(arrays["round_trips"], 2)
    arrays["round_trips"].flat[-1] = 4
    atomic_write_npz(state, arrays)
    _rewrite(
        checkpoint / "metadata.json",
        {
            "schema_version": 1,
            "completed_sweeps": completed,
            "spec_sha256": spec.sha256,
            "state_sha256": sha256_file(state),
        },
    )
    lineage = {
        "base_cell_id": spec.base_cell_id,
        "base_run_id": spec.base_run_id,
        "base_run_spec_sha256": spec.base_run_spec_sha256,
        "base_package_manifest_sha256": spec.base_package_manifest_sha256,
        "base_calibration_spec_sha256": spec.base_calibration_spec_sha256,
        "parent_cell_id": spec.parent.cell_id,
        "parent_manifest_kind": spec.parent.manifest_kind,
        "parent_manifest_sha256": spec.parent.manifest_sha256,
        "parent_checkpoint_spec_sha256": spec.parent.checkpoint_spec_sha256,
        "parent_checkpoint_metadata_sha256": spec.parent.checkpoint_metadata_sha256,
        "parent_checkpoint_state_sha256": spec.parent.checkpoint_state_sha256,
    }
    manifest = output / "manifest.json"
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
        "cell_id": spec.cell_id,
        "extension_spec": asdict(spec),
        "extension_spec_sha256": spec.sha256,
        "lineage": lineage,
        "start_completed_sweeps": spec.parent.completed_sweeps,
        "completed_sweeps": completed,
    }
    if runner_shaped:
        final_checkpoint = output / "checkpoints" / f"sweep-{completed:09d}"
        shutil.copytree(checkpoint, final_checkpoint)

        def travel_snapshot(values: dict[str, np.ndarray]) -> dict[str, object]:
            phase = values["round_trip_phase"]
            trips = values["round_trips"]
            timers = values["time_since_endpoint"]
            return {
                "phase_counts": {
                    str(value): int(np.count_nonzero(phase == value))
                    for value in range(3)
                },
                "completed_tracker_count": int(np.count_nonzero(trips > 0)),
                "endpoint_timer": {
                    "minimum": int(np.min(timers)),
                    "maximum": int(np.max(timers)),
                    "mean": float(np.mean(timers, dtype=np.float64)),
                },
            }

        child_accepts = arrays["swap_accepts"]
        cumulative_acceptance = child_accepts / child_attempts
        window_acceptance = window_accepts / window_attempts
        cumulative_band = bool(
            np.all(cumulative_acceptance >= spec.swap_target_minimum)
            and np.all(cumulative_acceptance <= spec.swap_target_maximum)
        )
        window_band = bool(
            np.all(window_acceptance >= spec.swap_target_minimum)
            and np.all(window_acceptance <= spec.swap_target_maximum)
        )
        bottleneck = bool(np.min(cumulative_acceptance) >= spec.swap_bottleneck)
        payload["parallel_tempering"] = {
            "all_edges_attempted": bool(np.all(child_attempts > 0)),
            "edge_attempts": [int(value) for value in child_attempts],
            "edge_accepts": [int(value) for value in child_accepts],
            "edge_acceptance": [float(value) for value in cumulative_acceptance],
            "bottleneck_passed": bottleneck,
            "target_band_passed": cumulative_band,
            "ladder_decision": (
                "PASS" if bottleneck and cumulative_band and window_band else "RECALIBRATE"
            ),
            "round_trips_min": int(np.min(arrays["round_trips"])),
            "round_trips_max": int(np.max(arrays["round_trips"])),
            "extension_window": {
                "start_completed_sweeps": spec.parent.completed_sweeps,
                "completed_sweeps": completed,
                "all_edges_attempted": bool(np.all(window_attempts > 0)),
                "edge_attempts": [int(value) for value in window_attempts],
                "edge_accepts": [int(value) for value in window_accepts],
                "edge_acceptance": [float(value) for value in window_acceptance],
                "target_band_passed": window_band,
            },
        }
        payload["travel"] = {
            "parent": travel_snapshot(parent_arrays),
            "child": travel_snapshot(arrays),
        }
        spin_proposals = int(
            arrays["local_proposed_changes"]
            - parent_arrays["local_proposed_changes"]
        )
        payload["runtime"] = {
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
        }
    payload["artifact_hashes"] = {
        str(artifact.relative_to(output)): sha256_file(artifact)
        for artifact in sorted(output.rglob("*"))
        if artifact.is_file() and artifact != manifest
    }
    _rewrite(manifest, payload)
    return manifest


def _refresh_terminal_artifacts(manifest: Path, payload: dict[str, object]) -> None:
    payload["artifact_hashes"] = {
        str(artifact.relative_to(manifest.parent)): sha256_file(artifact)
        for artifact in sorted(manifest.parent.rglob("*"))
        if artifact.is_file() and artifact != manifest
    }
    _rewrite(manifest, payload)


def test_extension_spec_binds_parent_and_preserves_exact_base_ladder() -> None:
    run_spec = ladder_scan.build_ladder_extension_spec(
        PARENT,
        PACKAGE,
        target_completed_sweeps=8192,
        run_id="stage6-b4-l27-a035-extension-v1",
    )

    cell = run_spec["cells"][0]
    spec = pilot.CalibrationExtensionSpec.from_payload(cell["extension_spec"])
    parent_manifest = json.loads(PARENT.read_text(encoding="ascii"))
    parent_checkpoint = json.loads(
        (PARENT.parent / "checkpoint" / "metadata.json").read_text(encoding="ascii")
    )

    assert spec.kind == "calibration_extension"
    assert spec.cell_id == "L27-J0000-A035-E08192"
    assert spec.base_cell_id == "L27-J0000-A035"
    assert spec.base_run_id == "stage6-b4-l27-adaptive-v1"
    assert spec.base_run_spec_sha256 == sha256_file(BASE / "run_spec.json")
    assert spec.base_package_manifest_sha256 == sha256_file(PACKAGE)
    assert spec.base_calibration_spec_sha256 == parent_manifest["spec_sha256"]
    assert spec.temperatures == tuple(parent_manifest["spec"]["temperatures"])
    assert spec.chain_pairs == parent_manifest["spec"]["chain_pairs"]
    assert spec.j_seed == parent_manifest["spec"]["j_seed"]
    assert spec.parent.manifest_kind == "calibration"
    assert spec.parent.manifest_sha256 == sha256_file(PARENT)
    assert spec.parent.checkpoint_spec_sha256 == parent_checkpoint["spec_sha256"]
    assert spec.parent.completed_sweeps == 4096
    assert spec.target_completed_sweeps == 8192
    assert cell["extension_spec_sha256"] == spec.sha256


def test_extension_planning_module_does_not_import_jax() -> None:
    completed = subprocess.run(
        [
            str(REPO / ".venv" / "bin" / "python"),
            "-c",
            (
                "import sys; from spinglass3d import ladder_scan; "
                "raise SystemExit(1 if 'jax' in sys.modules else 0)"
            ),
        ],
        cwd=TRACK,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(TRACK / "src")},
    )
    assert completed.returncode == 0, completed.stderr


def test_extension_planner_consumes_anchored_v1_without_legacy_regeneration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_legacy_regeneration(*args: object, **kwargs: object) -> object:
        raise AssertionError("extension planning must not regenerate the frozen v1 package")

    monkeypatch.setattr(
        ladder_scan,
        "build_ladder_scan_spec",
        forbidden_legacy_regeneration,
    )
    run_spec = ladder_scan.build_ladder_extension_spec(
        PARENT,
        PACKAGE,
        target_completed_sweeps=8192,
        run_id="anchored-v1-consumer",
    )
    spec = pilot.CalibrationExtensionSpec.from_payload(
        run_spec["cells"][0]["extension_spec"]
    )

    assert spec.base_run_spec_sha256 == sha256_file(BASE / "run_spec.json")
    assert spec.base_package_manifest_sha256 == sha256_file(PACKAGE)
    assert spec.parent.manifest_sha256 == sha256_file(PARENT)


def test_chained_extension_requires_complete_package_bound_parent(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first-extension"
    ladder_scan.prepare_ladder_extension(
        PARENT,
        PACKAGE,
        target_completed_sweeps=8192,
        run_id="first-extension",
        output=first,
    )
    terminal = _write_terminal_extension(first)

    second_spec = ladder_scan.build_ladder_extension_spec(
        terminal,
        first / "manifest.json",
        target_completed_sweeps=16384,
        run_id="second-extension",
    )
    child = pilot.CalibrationExtensionSpec.from_payload(
        second_spec["cells"][0]["extension_spec"]
    )
    first_spec = pilot.CalibrationExtensionSpec.from_payload(
        json.loads((first / "run_spec.json").read_text(encoding="ascii"))["cells"][0][
            "extension_spec"
        ]
    )
    assert child.parent.cell_id == first_spec.cell_id
    assert child.parent.checkpoint_spec_sha256 == first_spec.sha256
    assert child.base_package_manifest_sha256 == first_spec.base_package_manifest_sha256

    with pytest.raises(ValueError, match="package|run spec"):
        ladder_scan.build_ladder_extension_spec(
            terminal,
            PACKAGE,
            target_completed_sweeps=16384,
            run_id="mismatched-parent-package",
        )

    incomplete = tmp_path / "incomplete-extension"
    ladder_scan.prepare_ladder_extension(
        PARENT,
        PACKAGE,
        target_completed_sweeps=8192,
        run_id="incomplete-extension",
        output=incomplete,
    )
    incomplete_terminal = _write_terminal_extension(
        incomplete,
        completed_sweeps=8191,
    )
    with pytest.raises(ValueError, match="target|completed"):
        ladder_scan.build_ladder_extension_spec(
            incomplete_terminal,
            incomplete / "manifest.json",
            target_completed_sweeps=16384,
            run_id="reject-incomplete-parent",
        )

    claimed = tmp_path / "scientific-claim-extension"
    ladder_scan.prepare_ladder_extension(
        PARENT,
        PACKAGE,
        target_completed_sweeps=8192,
        run_id="scientific-claim-extension",
        output=claimed,
    )
    claimed_terminal = _write_terminal_extension(claimed)
    claimed_payload = json.loads(claimed_terminal.read_text(encoding="ascii"))
    claimed_payload["scientific_evidence"] = True
    _rewrite(claimed_terminal, claimed_payload)
    with pytest.raises(ValueError, match="scientific|evidence"):
        ladder_scan.build_ladder_extension_spec(
            claimed_terminal,
            claimed / "manifest.json",
            target_completed_sweeps=16384,
            run_id="reject-scientific-parent",
        )


def test_chained_extension_rejects_parent_without_runner_shaped_terminal_evidence(
    tmp_path: Path,
) -> None:
    first = tmp_path / "minimal-parent"
    ladder_scan.prepare_ladder_extension(
        PARENT,
        PACKAGE,
        target_completed_sweeps=8192,
        run_id="minimal-parent",
        output=first,
    )
    terminal = _write_terminal_extension(first, runner_shaped=False)

    with pytest.raises(ValueError, match="terminal|evidence|runtime|travel|checkpoint"):
        ladder_scan.build_ladder_extension_spec(
            terminal,
            first / "manifest.json",
            target_completed_sweeps=16384,
            run_id="reject-minimal-parent",
        )


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
def test_chained_extension_rejects_parent_terminal_not_bound_to_checkpoint_state(
    tmp_path: Path,
    tamper: str,
) -> None:
    first = tmp_path / tamper
    ladder_scan.prepare_ladder_extension(
        PARENT,
        PACKAGE,
        target_completed_sweeps=8192,
        run_id=tamper,
        output=first,
    )
    terminal = _write_terminal_extension(first)
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
        payload["runtime"]["spin_proposals"] += 1
    else:
        shutil.rmtree(terminal.parent / "checkpoints")
        _refresh_terminal_artifacts(terminal, payload)
    if tamper != "target_checkpoint":
        _rewrite(terminal, payload)

    with pytest.raises(ValueError, match="terminal|evidence|counter|travel|runtime|checkpoint"):
        ladder_scan.build_ladder_extension_spec(
            terminal,
            first / "manifest.json",
            target_completed_sweeps=16384,
            run_id=f"reject-{tamper}",
        )


@pytest.mark.parametrize(
    "relative",
    [
        "parent/manifest.json",
        "parent/checkpoint/metadata.json",
        "parent/checkpoint/state.npz",
    ],
)
def test_chained_extension_cross_binds_bundled_parent_artifacts(
    tmp_path: Path,
    relative: str,
) -> None:
    first = tmp_path / "cross-bind-parent"
    ladder_scan.prepare_ladder_extension(
        PARENT,
        PACKAGE,
        target_completed_sweeps=8192,
        run_id="cross-bind-parent",
        output=first,
    )
    terminal = _write_terminal_extension(first)
    artifact = first / relative
    artifact.write_bytes(artifact.read_bytes() + b"\n")
    package_path = first / "manifest.json"
    package = json.loads(package_path.read_text(encoding="ascii"))
    package["artifacts"][relative] = sha256_file(artifact)
    _rewrite(package_path, package)

    with pytest.raises(ValueError, match="parent|lineage|artifact|checkpoint"):
        ladder_scan.build_ladder_extension_spec(
            terminal,
            package_path,
            target_completed_sweeps=16384,
            run_id=f"reject-{Path(relative).name}",
        )


def test_chained_extension_rejects_terminal_from_different_supplying_package(
    tmp_path: Path,
) -> None:
    first = tmp_path / "package-a"
    second = tmp_path / "package-b"
    for package, run_id in ((first, "package-a"), (second, "package-b")):
        ladder_scan.prepare_ladder_extension(
            PARENT,
            PACKAGE,
            target_completed_sweeps=8192,
            run_id=run_id,
            output=package,
        )
    terminal = _write_terminal_extension(first)

    with pytest.raises(ValueError, match="package|output|terminal|path"):
        ladder_scan.build_ladder_extension_spec(
            terminal,
            second / "manifest.json",
            target_completed_sweeps=16384,
            run_id="reject-cross-package-terminal",
        )


def test_prepare_extension_copies_and_hash_binds_parent_checkpoint(tmp_path: Path) -> None:
    parent, package = _copy_parent(tmp_path)
    output = tmp_path / "extension-v1"
    result = ladder_scan.prepare_ladder_extension(
        parent,
        package,
        target_completed_sweeps=8192,
        run_id="extension-v1",
        output=output,
    )

    copied = {
        "parent/manifest.json": parent,
        "parent/checkpoint/metadata.json": parent.parent / "checkpoint" / "metadata.json",
        "parent/checkpoint/state.npz": parent.parent / "checkpoint" / "state.npz",
    }
    assert result["classification"] == "PLANNED"
    assert result["phase"] == "calibration_extension"
    assert result["scientific_evidence"] is False
    assert result["tc_evidence"] is False
    assert result["second_rg_enabled"] is False
    assert set(result["artifacts"]) == {"run_spec.json", *copied}
    for relative, source in copied.items():
        destination = output / relative
        assert destination.read_bytes() == source.read_bytes()
        assert result["artifacts"][relative] == sha256_file(destination)
    assert result["artifacts"]["run_spec.json"] == sha256_file(output / "run_spec.json")


@pytest.mark.parametrize("tamper", ["manifest", "checkpoint"])
def test_prepare_extension_rejects_parent_manifest_or_checkpoint_hash_mismatch(
    tmp_path: Path,
    tamper: str,
) -> None:
    parent, package = _copy_parent(tmp_path)
    if tamper == "manifest":
        payload = json.loads(parent.read_text(encoding="ascii"))
        payload["artifact_hashes"]["checkpoint/metadata.json"] = "0" * 64
        _rewrite(parent, payload)
    else:
        with (parent.parent / "checkpoint" / "state.npz").open("ab") as handle:
            handle.write(b"tampered")

    with pytest.raises(ValueError, match="hash mismatch"):
        ladder_scan.prepare_ladder_extension(
            parent,
            package,
            target_completed_sweeps=8192,
            run_id="extension-v1",
            output=tmp_path / "extension-v1",
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("temperatures", lambda value: [value[0], value[1] - 1e-6, *value[2:]]),
        ("j_seed", lambda value: value + 1),
        ("chain_pairs", lambda value: value + 1),
    ],
)
def test_prepare_extension_rejects_changed_temperature_seed_or_chain_count(
    tmp_path: Path,
    field: str,
    replacement: object,
) -> None:
    parent, package = _copy_parent(tmp_path)
    payload = json.loads(parent.read_text(encoding="ascii"))
    payload["spec"][field] = replacement(payload["spec"][field])  # type: ignore[operator]
    payload["spec_sha256"] = sha256_bytes(canonical_json_bytes(payload["spec"]))
    _rewrite(parent, payload)

    with pytest.raises(ValueError, match="base candidate"):
        ladder_scan.prepare_ladder_extension(
            parent,
            package,
            target_completed_sweeps=8192,
            run_id="extension-v1",
            output=tmp_path / "extension-v1",
        )


def test_prepare_extension_rejects_nonincreasing_target_and_existing_destination(
    tmp_path: Path,
) -> None:
    parent, package = _copy_parent(tmp_path)
    with pytest.raises(ValueError, match="greater than parent"):
        ladder_scan.prepare_ladder_extension(
            parent,
            package,
            target_completed_sweeps=4096,
            run_id="extension-v1",
            output=tmp_path / "extension-v1",
        )

    destination = tmp_path / "already-exists"
    destination.mkdir()
    with pytest.raises(FileExistsError, match="overwrite"):
        ladder_scan.prepare_ladder_extension(
            parent,
            package,
            target_completed_sweeps=8192,
            run_id="extension-v1",
            output=destination,
        )


def test_prepare_extension_rejects_incomplete_first_parent(tmp_path: Path) -> None:
    parent, package = _copy_parent(tmp_path)
    state_path = parent.parent / "checkpoint" / "state.npz"
    with np.load(state_path, allow_pickle=False) as archive:
        arrays = {name: archive[name].copy() for name in archive.files}
    spins = arrays["spins"]
    edge_indices = np.arange(spins.shape[1] - 1, dtype=np.int64)
    completed = 2048
    arrays["sweep_count"] = np.asarray(completed, dtype=np.int64)
    arrays["local_accepted_changes"] = np.asarray(0, dtype=np.int64)
    arrays["local_proposed_changes"] = np.asarray(
        completed * spins.size,
        dtype=np.int64,
    )
    arrays["swap_attempts"] = np.where(
        edge_indices % 2 == 0,
        (completed + 1) // 2,
        completed // 2,
    ) * spins.shape[0] * spins.shape[2]
    arrays["swap_accepts"] = np.zeros_like(arrays["swap_attempts"])
    arrays["round_trips"] = np.zeros_like(arrays["round_trips"])
    arrays["time_since_endpoint"] = np.zeros_like(
        arrays["time_since_endpoint"]
    )
    atomic_write_npz(state_path, arrays)
    metadata_path = parent.parent / "checkpoint" / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="ascii"))
    metadata["completed_sweeps"] = completed
    metadata["state_sha256"] = sha256_file(state_path)
    _rewrite(metadata_path, metadata)
    manifest = json.loads(parent.read_text(encoding="ascii"))
    manifest["completed_sweeps"] = completed
    manifest["artifact_hashes"]["checkpoint/metadata.json"] = sha256_file(
        metadata_path
    )
    manifest["artifact_hashes"]["checkpoint/state.npz"] = sha256_file(state_path)
    _rewrite(parent, manifest)

    with pytest.raises(ValueError, match="declared|budget|4096"):
        ladder_scan.prepare_ladder_extension(
            parent,
            package,
            target_completed_sweeps=8192,
            run_id="reject-incomplete-first-parent",
            output=tmp_path / "extension-v1",
        )


@pytest.mark.parametrize("counter_case", ["local_proposals", "swap_attempts"])
def test_prepare_extension_rejects_hash_consistent_impossible_sweep_counters(
    tmp_path: Path,
    counter_case: str,
) -> None:
    parent, package = _copy_parent(tmp_path)
    state_path = parent.parent / "checkpoint" / "state.npz"
    with np.load(state_path, allow_pickle=False) as archive:
        arrays = {name: archive[name].copy() for name in archive.files}
    if counter_case == "local_proposals":
        arrays["local_accepted_changes"] = np.asarray(0, dtype=np.int64)
        arrays["local_proposed_changes"] = np.asarray(0, dtype=np.int64)
    else:
        arrays["swap_attempts"] = arrays["swap_attempts"] + 2
    atomic_write_npz(state_path, arrays)
    metadata_path = parent.parent / "checkpoint" / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="ascii"))
    metadata["state_sha256"] = sha256_file(state_path)
    _rewrite(metadata_path, metadata)
    manifest = json.loads(parent.read_text(encoding="ascii"))
    manifest["artifact_hashes"]["checkpoint/metadata.json"] = sha256_file(
        metadata_path
    )
    manifest["artifact_hashes"]["checkpoint/state.npz"] = sha256_file(state_path)
    _rewrite(parent, manifest)

    with pytest.raises(ValueError, match="counter|semantics"):
        ladder_scan.prepare_ladder_extension(
            parent,
            package,
            target_completed_sweeps=8192,
            run_id=f"reject-{counter_case}",
            output=tmp_path / f"extension-{counter_case}",
        )


@pytest.mark.parametrize("state_case", ["round_trips", "endpoint_timer"])
def test_prepare_extension_rejects_hash_consistent_impossible_travel_state(
    tmp_path: Path,
    state_case: str,
) -> None:
    parent, package = _copy_parent(tmp_path)
    state_path = parent.parent / "checkpoint" / "state.npz"
    with np.load(state_path, allow_pickle=False) as archive:
        arrays = {name: archive[name].copy() for name in archive.files}
    sweep_count = int(arrays["sweep_count"])
    if state_case == "round_trips":
        temperature_count = arrays["spins"].shape[1]
        arrays["round_trips"].flat[0] = (
            sweep_count // (2 * (temperature_count - 1)) + 1
        )
    else:
        arrays["time_since_endpoint"].flat[0] = sweep_count + 2
    atomic_write_npz(state_path, arrays)
    metadata_path = parent.parent / "checkpoint" / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="ascii"))
    metadata["state_sha256"] = sha256_file(state_path)
    _rewrite(metadata_path, metadata)
    manifest = json.loads(parent.read_text(encoding="ascii"))
    manifest["artifact_hashes"]["checkpoint/metadata.json"] = sha256_file(
        metadata_path
    )
    manifest["artifact_hashes"]["checkpoint/state.npz"] = sha256_file(state_path)
    _rewrite(parent, manifest)

    with pytest.raises(ValueError, match="travel|round.trip|timer|semantics"):
        ladder_scan.prepare_ladder_extension(
            parent,
            package,
            target_completed_sweeps=8192,
            run_id=f"reject-{state_case}",
            output=tmp_path / f"extension-{state_case}",
        )


@pytest.mark.parametrize("schema_version", [True, 1.0])
def test_prepare_extension_rejects_noninteger_checkpoint_metadata_schema(
    tmp_path: Path,
    schema_version: object,
) -> None:
    parent, package = _copy_parent(tmp_path)
    metadata_path = parent.parent / "checkpoint" / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="ascii"))
    metadata["schema_version"] = schema_version
    _rewrite(metadata_path, metadata)
    manifest = json.loads(parent.read_text(encoding="ascii"))
    manifest["artifact_hashes"]["checkpoint/metadata.json"] = sha256_file(
        metadata_path
    )
    _rewrite(parent, manifest)

    with pytest.raises(ValueError, match="metadata|schema"):
        ladder_scan.prepare_ladder_extension(
            parent,
            package,
            target_completed_sweeps=8192,
            run_id="reject-metadata-schema",
            output=tmp_path / "extension-metadata-schema",
        )


def test_extension_loader_rebuilds_spec_and_rejects_tampered_run_package(
    tmp_path: Path,
) -> None:
    output, _ = _prepare(tmp_path)
    run_spec_path = output / "run_spec.json"
    spec, child_output, parent_checkpoint = ladder_scan.load_ladder_extension_cell(
        run_spec_path,
        "1",
        track_root=TRACK,
        repo_root=REPO,
    )
    assert type(spec) is pilot.CalibrationExtensionSpec
    assert child_output == REPO / "results" / "hard_goal" / "extension-v1" / "cells" / spec.cell_id
    assert parent_checkpoint == output / "parent" / "checkpoint"

    run_spec = json.loads(run_spec_path.read_text(encoding="ascii"))
    run_spec["cells"][0]["extension_spec"]["target_completed_sweeps"] = 16384
    _rewrite(run_spec_path, run_spec)
    package_path = output / "manifest.json"
    package = json.loads(package_path.read_text(encoding="ascii"))
    package["artifacts"]["run_spec.json"] = sha256_file(run_spec_path)
    _rewrite(package_path, package)
    with pytest.raises(ValueError, match="rebuild|canonical|spec"):
        ladder_scan.load_ladder_extension_cell(
            run_spec_path,
            "1",
            track_root=TRACK,
            repo_root=REPO,
        )

    physics_output, _ = _prepare(tmp_path / "physics-tamper")
    physics_run_spec_path = physics_output / "run_spec.json"
    physics_run_spec = json.loads(physics_run_spec_path.read_text(encoding="ascii"))
    embedded = physics_run_spec["cells"][0]["extension_spec"]
    embedded["j_seed"] += 1
    changed = pilot.CalibrationExtensionSpec.from_payload(embedded)
    physics_run_spec["cells"][0]["extension_spec_sha256"] = changed.sha256
    _rewrite(physics_run_spec_path, physics_run_spec)
    physics_package_path = physics_output / "manifest.json"
    physics_package = json.loads(physics_package_path.read_text(encoding="ascii"))
    physics_package["artifacts"]["run_spec.json"] = sha256_file(
        physics_run_spec_path
    )
    _rewrite(physics_package_path, physics_package)
    with pytest.raises(ValueError, match="base|parent"):
        ladder_scan.load_ladder_extension_cell(
            physics_run_spec_path,
            "1",
            track_root=TRACK,
            repo_root=REPO,
        )


@pytest.mark.parametrize(
    "tamper",
    [
        "extra_cell",
        "wrong_index",
        "bool_index",
        "extra_field",
        "wrong_output",
        "wrong_run_dir",
    ],
)
def test_extension_loader_requires_exact_single_canonical_cell(
    tmp_path: Path,
    tamper: str,
) -> None:
    output, _ = _prepare(tmp_path)
    run_spec_path = output / "run_spec.json"
    run_spec = json.loads(run_spec_path.read_text(encoding="ascii"))
    if tamper == "extra_cell":
        duplicate = json.loads(json.dumps(run_spec["cells"][0]))
        duplicate["array_index"] = 2
        run_spec["cells"].append(duplicate)
        selector = "2"
    elif tamper == "wrong_index":
        run_spec["cells"][0]["array_index"] = 2
        selector = "2"
    else:
        selector = "1"
        if tamper == "bool_index":
            run_spec["cells"][0]["array_index"] = True
        elif tamper == "extra_field":
            run_spec["cells"][0]["unexpected"] = True
        elif tamper == "wrong_output":
            run_spec["cells"][0]["output"] = (
                "results/hard_goal/extension-v1/cells/wrong-child"
            )
        else:
            run_spec["run_dir"] = "results/hard_goal/wrong-run"
    _rewrite(run_spec_path, run_spec)
    package_path = output / "manifest.json"
    package = json.loads(package_path.read_text(encoding="ascii"))
    package["artifacts"]["run_spec.json"] = sha256_file(run_spec_path)
    _rewrite(package_path, package)

    with pytest.raises(ValueError, match="cell|array|run spec|output|run"):
        ladder_scan.load_ladder_extension_cell(
            run_spec_path,
            selector,
            track_root=TRACK,
            repo_root=REPO,
        )


def test_chained_extension_rejects_parent_package_with_extra_cell(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first-extension"
    ladder_scan.prepare_ladder_extension(
        PARENT,
        PACKAGE,
        target_completed_sweeps=8192,
        run_id="first-extension",
        output=first,
    )
    terminal = _write_terminal_extension(first)
    run_spec_path = first / "run_spec.json"
    run_spec = json.loads(run_spec_path.read_text(encoding="ascii"))
    extra = json.loads(json.dumps(run_spec["cells"][0]))
    extra["array_index"] = 2
    extra["cell_id"] = "unrelated-extra-cell"
    run_spec["cells"].append(extra)
    _rewrite(run_spec_path, run_spec)
    package_path = first / "manifest.json"
    package = json.loads(package_path.read_text(encoding="ascii"))
    package["artifacts"]["run_spec.json"] = sha256_file(run_spec_path)
    _rewrite(package_path, package)

    with pytest.raises(ValueError, match="cell|array|run spec"):
        ladder_scan.build_ladder_extension_spec(
            terminal,
            package_path,
            target_completed_sweeps=16384,
            run_id="reject-extra-parent-cell",
        )


def test_extension_cli_dry_run_reports_parent_child_hash_transition(
    tmp_path: Path,
) -> None:
    output, _ = _prepare(tmp_path)
    completed = subprocess.run(
        [
            str(REPO / ".venv" / "bin" / "python"),
            str(SCRIPT),
            "--run-spec",
            str(output / "run_spec.json"),
            "--selector",
            "1",
            "--require-platform",
            "gpu",
            "--checkpoint-every",
            "256",
            "--dry-run",
        ],
        cwd=TRACK,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(TRACK / "src")},
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["parent_cell_id"] == "L27-J0000-A035"
    assert payload["child_cell_id"] == "L27-J0000-A035-E08192"
    assert payload["parent_spec_sha256"] == "0aa7618fedd373e8d35589b4d29ebee9b88033ecec5da268c81bef7de6af49f6"
    assert payload["child_spec_sha256"] != payload["parent_spec_sha256"]
    assert payload["start_completed_sweeps"] == 4096
    assert payload["target_completed_sweeps"] == 8192
    assert payload["predicted_only"] is True


def test_extension_cell_runner_forwards_only_bundled_parent_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, _ = _prepare(tmp_path)
    calls: list[tuple[object, Path, Path, dict[str, object]]] = []

    def fake_runner(
        spec: object,
        parent_checkpoint: Path,
        child_output: Path,
        **options: object,
    ) -> dict[str, object]:
        calls.append((spec, parent_checkpoint, child_output, options))
        return {"classification": "CALIBRATION_EXTENSION_COMPLETE"}

    monkeypatch.setattr(ladder_scan, "run_ladder_calibration_extension", fake_runner)
    manifest = ladder_scan.run_ladder_extension_cell(
        output / "run_spec.json",
        "1",
        required_platform="gpu",
        checkpoint_every=128,
        resume=True,
        track_root=TRACK,
        repo_root=REPO,
    )

    assert manifest["classification"] == "CALIBRATION_EXTENSION_COMPLETE"
    assert len(calls) == 1
    _, parent_checkpoint, child_output, options = calls[0]
    assert parent_checkpoint == output / "parent" / "checkpoint"
    assert child_output.parent == REPO / "results" / "hard_goal" / "extension-v1" / "cells"
    assert options == {
        "required_platform": "gpu",
        "checkpoint_every": 128,
        "resume": True,
    }


def test_extension_wrapper_is_hash_pinned_profile_neutral_and_forwards_child_resume(
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
    (fake_bin / "apptainer").write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$ARGUMENT_LOG\"\nexit 7\n",
        encoding="ascii",
    )
    (fake_bin / "nvidia-smi").write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
    (fake_bin / "sha256sum").write_text(
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
    for executable in ("apptainer", "nvidia-smi", "sha256sum"):
        (fake_bin / executable).chmod(0o755)
    profile = tmp_path / "profile.sh"
    profile.write_text("module() { :; }\n", encoding="ascii")
    home = tmp_path / "home"
    sif = home / "scratch" / "containers" / "python-3.12.11-slim-bookworm.sif"
    sif.parent.mkdir(parents=True)
    sif.touch()
    venv = home / "scratch" / "hg3d-venv-v1"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "python").symlink_to("/bin/true")
    Path(str(venv) + ".freeze.txt").touch()
    environment = {
        **os.environ,
        "HARNESS_RUN_SPEC": str(run_spec),
        "SLURM_ARRAY_TASK_ID": "1",
        "HARNESS_REPO_ROOT": str(REPO),
        "HARNESS_SYSTEM_PROFILE": str(profile),
        "HOME": str(home),
        "ARGUMENT_LOG": str(argument_log),
        "PATH": f"{fake_bin}:/usr/bin:/bin",
    }
    without_resume = subprocess.run(
        ["bash", str(JOB)],
        cwd=TRACK,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert without_resume.returncode == 7
    arguments = argument_log.read_text(encoding="ascii").splitlines()
    command_start = arguments.index("-u")
    assert arguments[command_start:] == [
        "-u",
        "scripts/hard_goal_ladder_extension_cell.py",
        "--run-spec",
        str(run_spec),
        "--selector",
        "1",
        "--require-platform",
        "gpu",
        "--checkpoint-every",
        "256",
    ]
    resumed = subprocess.run(
        ["bash", str(JOB)],
        cwd=TRACK,
        capture_output=True,
        text=True,
        env={**environment, "HARNESS_RESUME": "1"},
    )
    assert resumed.returncode == 7
    resumed_arguments = argument_log.read_text(encoding="ascii").splitlines()
    assert resumed_arguments[resumed_arguments.index("-u") :] == [
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
        "parent-checkpoint",
    ):
        assert forbidden not in source


def test_extension_cli_fails_closed_on_arbitrary_parent_checkpoint_path(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            str(REPO / ".venv" / "bin" / "python"),
            str(SCRIPT),
            "--run-spec",
            str(tmp_path / "run_spec.json"),
            "--selector",
            "1",
            "--require-platform",
            "gpu",
            "--checkpoint-every",
            "256",
            "--parent-checkpoint",
            str(tmp_path / "arbitrary"),
        ],
        cwd=TRACK,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(TRACK / "src")},
    )
    assert completed.returncode == 2
    assert "unrecognized arguments: --parent-checkpoint" in completed.stderr
