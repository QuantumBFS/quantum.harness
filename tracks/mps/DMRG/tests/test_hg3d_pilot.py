from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
import shutil

import numpy as np
import pytest

from spinglass3d import pilot
from scripts.hard_goal import build_parser as build_hard_goal_parser
from scripts.hard_goal import main as hard_goal_main
from scripts.hard_goal_pt_smoke import run_pt_smoke
from scripts.hard_goal_pilot_cell import build_parser as build_cell_parser
from scripts.hard_goal_pilot_cell import main as pilot_cell_main
from spinglass3d.backend import BackendCase
from spinglass3d.jax_backend import JaxParallelTemperingBackend
from spinglass3d.pilot import (
    CalibrationSpec,
    load_calibration_cell,
    load_pt_checkpoint,
    run_ladder_calibration,
    save_pt_checkpoint,
)
from spinglass3d.workflow import (
    build_pilot_run_spec,
    estimate_pilot_resources,
    load_stage6_config,
    prepare_pilot_run,
)
from vmcrg_ref.artifacts import (
    atomic_write_json,
    atomic_write_npz,
    canonical_json_bytes,
    sha256_file,
)


TRACK = Path(__file__).resolve().parents[1]
CONFIG = TRACK / "config" / "hard_goal" / "stage6_pilot_v1.toml"
SMOKE = TRACK / "results" / "hard_goal" / "stage6-pt-backend-smoke-5314958" / "manifest.json"


def test_stage6_config_locks_the_approved_medium_pilot_matrix() -> None:
    config = load_stage6_config(CONFIG)
    assert config.lengths == (12, 18, 24, 27)
    assert config.j_counts == (64, 32, 16, 8)
    assert config.temperature_min == 0.80
    assert config.temperature_max == 2.00
    assert config.temperature_count == 48
    assert config.temperature_schedule == "linear_beta"
    assert config.chain_pairs == 4
    assert config.templates == ("cube", "cross")
    assert config.routes == ("C", "B")
    assert config.control == "conditioned_linear"
    assert config.chis == (2, 4, 8)
    assert config.calibration_sweeps == 4096
    assert config.maximum_equilibration_sweeps == 1_048_576
    assert config.measurement_sweeps == 8192
    assert config.second_rg is False


def test_pilot_run_spec_keeps_each_temperature_ladder_in_one_cell() -> None:
    spec = build_pilot_run_spec(load_stage6_config(CONFIG), "stage6-pilot-v1")
    cells = spec["cells"]
    assert len(cells) == 120
    counts = {
        length: sum(cell["params"]["length"] == length for cell in cells)
        for length in (12, 18, 24, 27)
    }
    assert counts == {12: 64, 18: 32, 24: 16, 27: 8}
    assert len({cell["cell_id"] for cell in cells}) == len(cells)
    assert all("temperature" not in cell["params"] for cell in cells)
    assert all(len(cell["params"]["temperatures"]) == 48 for cell in cells)
    assert all(cell["params"]["chain_pairs"] == 4 for cell in cells)
    assert all(cell["params"]["rg_levels"] == 1 for cell in cells)
    assert spec["settings"]["comparison"]["chis"] == [2, 4, 8]
    assert set(spec["provenance"]["source_sha256"]) == {
        "jobs/hard_goal_pilot.slurm",
        "scripts/hard_goal_pilot_cell.py",
        "src/spinglass3d/backend.py",
        "src/spinglass3d/jax_backend.py",
        "src/spinglass3d/model.py",
        "src/spinglass3d/pilot.py",
        "src/spinglass3d/workflow.py",
    }
    assert all(
        len(value) == 64
        for value in spec["provenance"]["source_sha256"].values()
    )


def test_resource_estimate_is_bound_to_verified_a800_evidence() -> None:
    config = load_stage6_config(CONFIG)
    estimate = estimate_pilot_resources(config, SMOKE)
    assert estimate["backend_evidence_sha256"]
    assert estimate["backend"] == "gpu"
    assert estimate["device"] == "cuda:0"
    assert estimate["x64_enabled"] is True
    assert estimate["minimum_calibration_proposals"] > 0
    assert estimate["conservative_calibration_seconds"] > 0.0
    assert estimate["maximum_equilibration_seconds"] > estimate["conservative_calibration_seconds"]
    assert set(estimate["per_length"]) == {"12", "18", "24", "27"}
    assert estimate["per_length"]["12"]["cell_count"] == 64
    assert estimate["per_length"]["27"]["calibration_seconds_per_cell"] > estimate["per_length"]["12"]["calibration_seconds_per_cell"]
    assert all(
        record["calibration_request_wall_seconds"] <= 86400
        for record in estimate["per_length"].values()
    )
    assert estimate["total_calibration_accelerator_hours"] > 0.0


def test_resource_estimate_rejects_cpu_fallback(tmp_path: Path) -> None:
    payload = json.loads(SMOKE.read_text(encoding="ascii"))
    payload["runtime"]["default_backend"] = "cpu"
    evidence = tmp_path / "manifest.json"
    evidence.write_text(json.dumps(payload) + "\n", encoding="ascii")
    with pytest.raises(ValueError, match="GPU"):
        estimate_pilot_resources(load_stage6_config(CONFIG), evidence)


def test_prepare_pilot_run_publishes_an_immutable_launch_package(tmp_path: Path) -> None:
    output = tmp_path / "stage6-launch"
    package = prepare_pilot_run(CONFIG, SMOKE, output)
    assert package["classification"] == "PLANNED"
    assert package["scientific_evidence"] is False
    assert package["cell_count"] == 120
    assert (output / "run_spec.json").is_file()
    assert (output / "resource_estimate.json").is_file()
    assert (output / "launch.json").is_file()
    with pytest.raises(FileExistsError, match="overwrite"):
        prepare_pilot_run(CONFIG, SMOKE, output)


def test_pilot_plan_cli_publishes_only_a_launch_package(tmp_path: Path) -> None:
    output = tmp_path / "stage6-cli-launch"
    arguments = [
        "pilot-plan",
        "--config",
        str(CONFIG),
        "--backend-evidence",
        str(SMOKE),
        "--output",
        str(output),
    ]
    args = build_hard_goal_parser().parse_args(arguments)
    assert args.stage == "pilot-plan"
    assert hard_goal_main(arguments) == 0
    launch = json.loads((output / "launch.json").read_text(encoding="ascii"))
    assert launch["classification"] == "PLANNED"
    assert launch["scientific_evidence"] is False


def test_full_ladder_pt_smoke_records_warm_rate_and_swap_edges(tmp_path: Path) -> None:
    jax = pytest.importorskip("jax")
    output = tmp_path / "manifest.json"
    manifest = run_pt_smoke(
        length=3,
        temperature_count=4,
        chain_pairs=2,
        warmup_sweeps=1,
        measured_sweeps=2,
        seed=2026073193,
        required_platform=jax.default_backend(),
        output=output,
    )
    assert manifest["classification"] == "PASS"
    assert manifest["scope"] == "stage6-pt-backend-smoke-only"
    assert manifest["runtime"]["default_backend"] == jax.default_backend()
    assert manifest["benchmark"]["warm_spin_proposals_per_second"] > 0.0
    assert len(manifest["parallel_tempering"]["edge_acceptance"]) == 3
    assert manifest["parallel_tempering"]["overlap_binary"] is True
    with pytest.raises(FileExistsError, match="overwrite"):
        run_pt_smoke(
            length=3,
            temperature_count=4,
            chain_pairs=2,
            warmup_sweeps=1,
            measured_sweeps=1,
            seed=2026073193,
            required_platform=jax.default_backend(),
            output=output,
        )


def test_pt_checkpoint_round_trip_preserves_the_next_trajectory(tmp_path: Path) -> None:
    pytest.importorskip("jax")
    case = BackendCase.random(
        length=3,
        temperatures=4,
        samples=1,
        walkers=4,
        seed=2026073194,
    )
    source = JaxParallelTemperingBackend(case)
    source.run_sweeps(2)
    checkpoint = tmp_path / "checkpoint"
    save_pt_checkpoint(
        source,
        checkpoint,
        completed_sweeps=2,
        spec_sha256="a" * 64,
    )
    restored = JaxParallelTemperingBackend(case)
    completed = load_pt_checkpoint(
        restored,
        checkpoint,
        expected_spec_sha256="a" * 64,
    )
    assert completed == 2
    source.run_sweeps(2)
    restored.run_sweeps(2)
    np.testing.assert_array_equal(restored.spins, source.spins)
    np.testing.assert_array_equal(restored.replica_ids, source.replica_ids)
    np.testing.assert_array_equal(restored.round_trips, source.round_trips)


@pytest.mark.parametrize(
    ("array_name", "replacement"),
    [
        ("local_accepted_changes", np.asarray(0.0, dtype=np.float64)),
        ("local_proposed_changes", np.asarray([1], dtype=np.int64)),
        ("sweep_count", np.asarray(True, dtype=np.bool_)),
    ],
)
def test_pt_checkpoint_rejects_noncanonical_serialized_scalar_before_mutation(
    tmp_path: Path,
    array_name: str,
    replacement: np.ndarray,
) -> None:
    pytest.importorskip("jax")
    case = BackendCase.random(
        length=2,
        temperatures=4,
        samples=1,
        walkers=2,
        seed=2026073201,
    )
    source = JaxParallelTemperingBackend(case)
    source.run_sweeps(2)
    checkpoint = tmp_path / "checkpoint"
    save_pt_checkpoint(
        source,
        checkpoint,
        completed_sweeps=2,
        spec_sha256="e" * 64,
    )
    state_path = checkpoint / "state.npz"
    with np.load(state_path, allow_pickle=False) as archive:
        arrays = {name: archive[name].copy() for name in archive.files}
    arrays[array_name] = replacement
    atomic_write_npz(state_path, arrays)
    metadata_path = checkpoint / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="ascii"))
    metadata["state_sha256"] = sha256_file(state_path)
    atomic_write_json(metadata_path, metadata)
    candidate = JaxParallelTemperingBackend(case)
    before = candidate.checkpoint_state()

    with pytest.raises(ValueError, match="scalar counter"):
        load_pt_checkpoint(
            candidate,
            checkpoint,
            expected_spec_sha256="e" * 64,
        )

    _assert_pt_state_equal(candidate.checkpoint_state(), before)


def test_small_calibration_cell_is_immutable_and_not_tc_evidence(tmp_path: Path) -> None:
    jax = pytest.importorskip("jax")
    spec = CalibrationSpec(
        cell_id="L03-J0000",
        length=3,
        temperatures=(2.0, 1.4, 1.0, 0.8),
        chain_pairs=2,
        calibration_sweeps=4,
        j_seed=2026073195,
        swap_bottleneck=0.0,
        swap_target_minimum=0.0,
        swap_target_maximum=1.0,
        source_hashes={"test": "b" * 64},
    )
    output = tmp_path / "cell"
    manifest = run_ladder_calibration(
        spec,
        output,
        required_platform=jax.default_backend(),
        checkpoint_every=2,
    )
    assert manifest["classification"] == "CALIBRATION_COMPLETE"
    assert manifest["scope"] == "stage6-ladder-calibration-only"
    assert manifest["completed_sweeps"] == 4
    assert manifest["second_rg_enabled"] is False
    assert manifest["tc_evidence"] is False
    assert manifest["parallel_tempering"]["all_edges_attempted"] is True
    assert (output / "checkpoint" / "state.npz").is_file()
    assert (output / "manifest.json").is_file()
    with pytest.raises(FileExistsError, match="overwrite"):
        run_ladder_calibration(
            spec,
            output,
            required_platform=jax.default_backend(),
            checkpoint_every=2,
        )


def test_run_spec_cell_loader_rehashes_fixed_sources(tmp_path: Path) -> None:
    run_spec = build_pilot_run_spec(load_stage6_config(CONFIG), "stage6-load-test")
    path = tmp_path / "run_spec.json"
    path.write_text(json.dumps(run_spec, sort_keys=True) + "\n", encoding="ascii")
    spec, output = load_calibration_cell(
        path,
        "1",
        track_root=TRACK,
        repo_root=TRACK.parents[2],
    )
    assert spec.cell_id == "L12-J0000"
    assert spec.length == 12
    assert len(spec.temperatures) == 48
    assert spec.chain_pairs == 4
    assert spec.calibration_sweeps == 4096
    assert output == TRACK.parents[2] / "results" / "hard_goal" / "stage6-load-test" / "cells" / "L12-J0000"

    run_spec["provenance"]["config_sha256"] = "0" * 64
    path.write_text(json.dumps(run_spec) + "\n", encoding="ascii")
    with pytest.raises(ValueError, match="config hash"):
        load_calibration_cell(
            path,
            "1",
            track_root=TRACK,
            repo_root=TRACK.parents[2],
        )


def test_pilot_cell_cli_dry_run_resolves_one_opaque_cell(tmp_path: Path) -> None:
    run_spec = build_pilot_run_spec(load_stage6_config(CONFIG), "stage6-cli-test")
    path = tmp_path / "run_spec.json"
    path.write_text(json.dumps(run_spec, sort_keys=True) + "\n", encoding="ascii")
    args = build_cell_parser().parse_args(
        [
            "--run-spec",
            str(path),
            "--selector",
            "1",
            "--require-platform",
            "gpu",
            "--checkpoint-every",
            "256",
            "--dry-run",
        ]
    )
    assert args.selector == "1"
    assert args.dry_run is True
    assert pilot_cell_main(
        [
            "--run-spec",
            str(path),
            "--selector",
            "1",
            "--require-platform",
            "gpu",
            "--checkpoint-every",
            "256",
            "--dry-run",
        ]
    ) == 0


def _small_extension(
    tmp_path: Path,
    *,
    target_completed_sweeps: int = 6,
) -> tuple[
    pilot.CalibrationExtensionSpec,
    Path,
    JaxParallelTemperingBackend,
]:
    base = CalibrationSpec(
        cell_id="L02-J0000-A035",
        length=2,
        temperatures=(2.0, 1.5, 1.1, 0.8),
        chain_pairs=1,
        calibration_sweeps=2,
        j_seed=2026073200,
        swap_bottleneck=0.0,
        swap_target_minimum=0.0,
        swap_target_maximum=1.0,
        source_hashes={"base": "a" * 64},
    )
    backend = JaxParallelTemperingBackend(pilot._build_case(base))
    backend.run_sweeps(2)
    parent_root = tmp_path / "parent"
    checkpoint = parent_root / "checkpoint"
    save_pt_checkpoint(
        backend,
        checkpoint,
        completed_sweeps=2,
        spec_sha256=base.sha256,
    )
    manifest_path = parent_root / "manifest.json"
    manifest_path.write_bytes(
        canonical_json_bytes(
            {
                "cell_id": base.cell_id,
                "classification": "CALIBRATION_COMPLETE",
                "completed_sweeps": 2,
            }
        )
    )
    parent = pilot.CalibrationCheckpointParent(
        cell_id=base.cell_id,
        manifest_kind="calibration",
        manifest_sha256=sha256_file(manifest_path),
        checkpoint_spec_sha256=base.sha256,
        checkpoint_metadata_sha256=sha256_file(checkpoint / "metadata.json"),
        checkpoint_state_sha256=sha256_file(checkpoint / "state.npz"),
        completed_sweeps=2,
    )
    extension = pilot.CalibrationExtensionSpec(
        schema_version=1,
        kind="calibration_extension",
        cell_id=f"{base.cell_id}-E{target_completed_sweeps:05d}",
        base_cell_id=base.cell_id,
        base_run_id="small-base-v1",
        base_run_spec_sha256="b" * 64,
        base_package_manifest_sha256="c" * 64,
        base_calibration_spec_sha256=base.sha256,
        length=base.length,
        temperatures=base.temperatures,
        chain_pairs=base.chain_pairs,
        j_seed=base.j_seed,
        swap_bottleneck=base.swap_bottleneck,
        swap_target_minimum=base.swap_target_minimum,
        swap_target_maximum=base.swap_target_maximum,
        parent=parent,
        target_completed_sweeps=target_completed_sweeps,
        source_hashes={"test": "d" * 64},
    )
    return extension, checkpoint, backend


def _assert_pt_state_equal(left: dict[str, object], right: dict[str, object]) -> None:
    assert set(left) == set(right)
    for name, value in left.items():
        if isinstance(value, dict):
            _assert_pt_state_equal(value, right[name])
        elif isinstance(value, np.ndarray):
            np.testing.assert_array_equal(value, right[name])
        else:
            assert value == right[name]


def test_extension_parent_loader_uses_parent_not_child_spec_hash(tmp_path: Path) -> None:
    pytest.importorskip("jax")
    spec, checkpoint, source = _small_extension(tmp_path)
    restored = JaxParallelTemperingBackend(pilot._build_case(spec))

    completed = pilot.load_bound_parent_checkpoint(
        restored,
        checkpoint,
        spec.parent,
    )

    assert completed == spec.parent.completed_sweeps == 2
    assert spec.sha256 != spec.parent.checkpoint_spec_sha256
    _assert_pt_state_equal(restored.checkpoint_state(), source.checkpoint_state())


def test_extension_parent_loader_rejects_file_hash_mismatch_before_backend_mutation(
    tmp_path: Path,
) -> None:
    pytest.importorskip("jax")
    spec, checkpoint, _ = _small_extension(tmp_path)
    candidate = JaxParallelTemperingBackend(pilot._build_case(spec))
    before = candidate.checkpoint_state()
    with (checkpoint / "state.npz").open("ab") as handle:
        handle.write(b"tampered")

    with pytest.raises(ValueError, match="state hash mismatch"):
        pilot.load_bound_parent_checkpoint(candidate, checkpoint, spec.parent)

    _assert_pt_state_equal(candidate.checkpoint_state(), before)


def test_extension_parent_loader_rejects_binding_mismatch_before_backend_mutation(
    tmp_path: Path,
) -> None:
    pytest.importorskip("jax")
    spec, checkpoint, _ = _small_extension(tmp_path)
    candidate = JaxParallelTemperingBackend(pilot._build_case(spec))
    before = candidate.checkpoint_state()
    inconsistent = replace(spec.parent, completed_sweeps=1)

    with pytest.raises(ValueError, match="completed-sweep"):
        pilot.load_bound_parent_checkpoint(candidate, checkpoint, inconsistent)

    _assert_pt_state_equal(candidate.checkpoint_state(), before)


def test_calibration_extension_continues_complete_state_and_counters(
    tmp_path: Path,
) -> None:
    jax = pytest.importorskip("jax")
    spec, checkpoint, _ = _small_extension(tmp_path, target_completed_sweeps=4)
    expected = JaxParallelTemperingBackend(pilot._build_case(spec))
    pilot.load_bound_parent_checkpoint(expected, checkpoint, spec.parent)
    expected.run_sweeps(2)

    output = tmp_path / "child"
    manifest = pilot.run_ladder_calibration_extension(
        spec,
        checkpoint,
        output,
        required_platform=jax.default_backend(),
        checkpoint_every=2,
    )
    restored = JaxParallelTemperingBackend(pilot._build_case(spec))
    assert load_pt_checkpoint(
        restored,
        output / "checkpoint",
        expected_spec_sha256=spec.sha256,
    ) == 4

    _assert_pt_state_equal(restored.checkpoint_state(), expected.checkpoint_state())
    assert manifest["start_completed_sweeps"] == 2
    assert manifest["completed_sweeps"] == 4
    assert manifest["parallel_tempering"]["edge_attempts"] == [
        int(value) for value in expected.swap_attempts
    ]


def test_calibration_extension_resume_matches_uninterrupted_child_trajectory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jax = pytest.importorskip("jax")
    spec, checkpoint, _ = _small_extension(tmp_path, target_completed_sweeps=6)
    interrupted_output = tmp_path / "interrupted"
    original = JaxParallelTemperingBackend.run_sweeps
    calls = 0

    def interrupt_second_chunk(
        backend: JaxParallelTemperingBackend,
        sweeps: int,
        progress_every: int | None = None,
    ) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic interruption")
        original(backend, sweeps, progress_every)

    monkeypatch.setattr(JaxParallelTemperingBackend, "run_sweeps", interrupt_second_chunk)
    with pytest.raises(RuntimeError, match="synthetic interruption"):
        pilot.run_ladder_calibration_extension(
            spec,
            checkpoint,
            interrupted_output,
            required_platform=jax.default_backend(),
            checkpoint_every=2,
        )
    assert not interrupted_output.exists()
    monkeypatch.setattr(JaxParallelTemperingBackend, "run_sweeps", original)

    resumed = pilot.run_ladder_calibration_extension(
        spec,
        checkpoint,
        interrupted_output,
        required_platform=jax.default_backend(),
        checkpoint_every=2,
        resume=True,
    )
    uninterrupted_output = tmp_path / "uninterrupted"
    uninterrupted = pilot.run_ladder_calibration_extension(
        spec,
        checkpoint,
        uninterrupted_output,
        required_platform=jax.default_backend(),
        checkpoint_every=2,
    )
    resumed_backend = JaxParallelTemperingBackend(pilot._build_case(spec))
    direct_backend = JaxParallelTemperingBackend(pilot._build_case(spec))
    load_pt_checkpoint(
        resumed_backend,
        interrupted_output / "checkpoint",
        expected_spec_sha256=spec.sha256,
    )
    load_pt_checkpoint(
        direct_backend,
        uninterrupted_output / "checkpoint",
        expected_spec_sha256=spec.sha256,
    )
    _assert_pt_state_equal(resumed_backend.checkpoint_state(), direct_backend.checkpoint_state())
    assert resumed["completed_sweeps"] == uninterrupted["completed_sweeps"] == 6
    assert resumed["runtime"]["spin_proposals"] == uninterrupted["runtime"][
        "spin_proposals"
    ]


@pytest.mark.parametrize("corrupt_kind", ["directory", "file", "misnamed"])
def test_calibration_extension_resume_rejects_corrupt_newest_child_checkpoint(
    tmp_path: Path,
    corrupt_kind: str,
) -> None:
    jax = pytest.importorskip("jax")
    spec, checkpoint, _ = _small_extension(tmp_path, target_completed_sweeps=6)
    output = tmp_path / "child"
    checkpoint_root = tmp_path / ".child.work" / "checkpoints"
    child = JaxParallelTemperingBackend(pilot._build_case(spec))
    pilot.load_bound_parent_checkpoint(child, checkpoint, spec.parent)
    child.run_sweeps(2)
    save_pt_checkpoint(
        child,
        checkpoint_root / "sweep-000000004",
        completed_sweeps=4,
        spec_sha256=spec.sha256,
    )
    corrupt_newest = checkpoint_root / "sweep-000000005"
    if corrupt_kind == "directory":
        corrupt_newest.mkdir()
        (corrupt_newest / "state.npz").write_bytes(b"incomplete newest checkpoint")
    elif corrupt_kind == "file":
        corrupt_newest.write_bytes(b"checkpoint path is not a directory")
    else:
        shutil.copytree(checkpoint_root / "sweep-000000004", corrupt_newest)

    with pytest.raises(
        (FileNotFoundError, ValueError),
        match="incomplete|directory|name|sweep",
    ):
        pilot.run_ladder_calibration_extension(
            spec,
            checkpoint,
            output,
            required_platform=jax.default_backend(),
            checkpoint_every=2,
            resume=True,
        )

    assert not output.exists()


@pytest.mark.parametrize(
    ("path_kind", "entry_kind"),
    [
        ("work", "symlink"),
        ("work", "file"),
        ("checkpoints", "symlink"),
        ("checkpoints", "file"),
        ("selected", "symlink"),
        ("selected", "file"),
        ("terminal", "symlink"),
        ("terminal", "file"),
    ],
)
def test_calibration_extension_resume_rejects_untrusted_work_paths_before_restore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path_kind: str,
    entry_kind: str,
) -> None:
    jax = pytest.importorskip("jax")
    spec, checkpoint, _ = _small_extension(tmp_path, target_completed_sweeps=6)
    output = tmp_path / "child"
    work = tmp_path / ".child.work"
    outside = tmp_path / "outside"
    outside.mkdir()
    if path_kind == "work":
        target = work
    else:
        work.mkdir()
        if path_kind == "checkpoints":
            target = work / "checkpoints"
        else:
            (work / "checkpoints").mkdir()
            target = (
                work / "checkpoints" / "sweep-000000004"
                if path_kind == "selected"
                else work / "checkpoint"
            )
    if entry_kind == "symlink":
        redirected = outside / path_kind
        redirected.mkdir()
        target.symlink_to(redirected, target_is_directory=True)
    else:
        target.write_bytes(b"not a directory")
    outside_before = sorted(path.relative_to(outside) for path in outside.rglob("*"))

    def forbidden_parent_restore(*args: object, **kwargs: object) -> int:
        raise AssertionError("untrusted child work tree must fail before parent restore")

    monkeypatch.setattr(pilot, "load_bound_parent_checkpoint", forbidden_parent_restore)
    with pytest.raises(ValueError, match="symlink|directory|path|checkpoint"):
        pilot.run_ladder_calibration_extension(
            spec,
            checkpoint,
            output,
            required_platform=jax.default_backend(),
            checkpoint_every=2,
            resume=True,
        )

    assert sorted(path.relative_to(outside) for path in outside.rglob("*")) == outside_before


def test_calibration_extension_resume_recovers_terminal_assembly_interruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jax = pytest.importorskip("jax")
    spec, checkpoint, _ = _small_extension(tmp_path, target_completed_sweeps=4)
    output = tmp_path / "child"
    original_write = pilot.atomic_write_json

    def interrupt_manifest(path: Path, value: object) -> None:
        if Path(path).name == "manifest.json":
            raise RuntimeError("synthetic terminal interruption")
        original_write(path, value)

    monkeypatch.setattr(pilot, "atomic_write_json", interrupt_manifest)
    with pytest.raises(RuntimeError, match="terminal interruption"):
        pilot.run_ladder_calibration_extension(
            spec,
            checkpoint,
            output,
            required_platform=jax.default_backend(),
            checkpoint_every=2,
        )
    assert not output.exists()
    assert (tmp_path / ".child.work" / "checkpoint" / "state.npz").is_file()

    monkeypatch.setattr(pilot, "atomic_write_json", original_write)
    manifest = pilot.run_ladder_calibration_extension(
        spec,
        checkpoint,
        output,
        required_platform=jax.default_backend(),
        checkpoint_every=2,
        resume=True,
    )

    assert manifest["completed_sweeps"] == 4
    assert (output / "manifest.json").is_file()


def test_calibration_extension_manifest_separates_cumulative_and_window_acceptance(
    tmp_path: Path,
) -> None:
    jax = pytest.importorskip("jax")
    spec, checkpoint, parent = _small_extension(tmp_path, target_completed_sweeps=4)
    manifest = pilot.run_ladder_calibration_extension(
        spec,
        checkpoint,
        tmp_path / "child",
        required_platform=jax.default_backend(),
        checkpoint_every=2,
    )
    parallel = manifest["parallel_tempering"]
    window = parallel["extension_window"]

    assert window["start_completed_sweeps"] == 2
    assert window["completed_sweeps"] == 4
    assert window["edge_attempts"] == [
        int(value) for value in np.asarray(parallel["edge_attempts"]) - parent.swap_attempts
    ]
    assert window["edge_accepts"] == [
        int(value) for value in np.asarray(parallel["edge_accepts"]) - parent.swap_accepts
    ]
    assert parallel["ladder_decision"] == "PASS"
    assert window["target_band_passed"] is True


def test_calibration_extension_output_is_atomic_and_never_overwrites_parent(
    tmp_path: Path,
) -> None:
    jax = pytest.importorskip("jax")
    spec, checkpoint, _ = _small_extension(tmp_path, target_completed_sweeps=4)
    parent_hashes = {
        path.name: sha256_file(path)
        for path in checkpoint.iterdir()
        if path.is_file()
    }
    output = tmp_path / "child"
    manifest = pilot.run_ladder_calibration_extension(
        spec,
        checkpoint,
        output,
        required_platform=jax.default_backend(),
        checkpoint_every=2,
    )

    assert manifest["classification"] == "CALIBRATION_EXTENSION_COMPLETE"
    assert (output / "manifest.json").is_file()
    assert parent_hashes == {
        path.name: sha256_file(path)
        for path in checkpoint.iterdir()
        if path.is_file()
    }
    with pytest.raises(FileExistsError, match="overwrite"):
        pilot.run_ladder_calibration_extension(
            spec,
            checkpoint,
            output,
            required_platform=jax.default_backend(),
            checkpoint_every=2,
        )
