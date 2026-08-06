from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

import numpy as np
import pytest

from src.batch import (
    PERIODS,
    RealtimePoint,
    T_VALUES,
    U_VALUES,
    load_chern_checkpoint,
    pair_checkpoint_name,
    parameter_points,
    realtime_points,
    realtime_result_name,
    save_chern_checkpoint,
    static_result_name,
)
from src.cluster_workflows import (
    aggregate_complete_results,
    missing_refinement_points,
    missing_realtime_points,
    missing_static_points,
    run_refinement_point,
    run_static_point,
    validate_static_result,
    select_refinement_indices_from_summaries,
)
from src.cluster_workflows import run_realtime_point, validate_realtime_result
from src.diagonalization import EDEngine
from src.model import ModelParameters, RiceMeleHubbardModel
from src.topology import scan_chern


def test_complete_cluster_manifests_and_names_are_deterministic():
    pairs = parameter_points()
    dynamics = realtime_points()

    assert len(U_VALUES) == 41
    assert len(T_VALUES) == 11
    assert len(pairs) == 451
    assert len(dynamics) == 451 * len(PERIODS) == 1353
    assert (pairs[0].index, pairs[0].U, pairs[0].t) == (0, -32.0, 0.5)
    assert (pairs[-1].index, pairs[-1].U, pairs[-1].t) == (450, 32.0, 1.5)
    assert pair_checkpoint_name(pairs[0], 10) == (
        "pair_0000_U_neg32d000000_t_p0d500000_N10.npz"
    )
    assert realtime_result_name(dynamics[0]) == (
        "realtime_0000_pair_0000_U_neg32d000000_t_p0d500000_T_p2d000000.npz"
    )
    assert len({point.key for point in dynamics}) == len(dynamics)


def _write_legacy_checkpoint(path, *, fingerprint=None):
    engine = EDEngine(
        RiceMeleHubbardModel(
            ModelParameters(L=4, t=1.0, U=0.0, N_up=2, N_down=2)
        )
    )
    result = scan_chern(engine, n_theta=5, n_phi=5)
    coordinates = [(theta, phi) for theta in range(5) for phi in range(5)]
    summary = {
        **result.as_dict(),
        "index": 0,
        "L": 4,
        "U": 0.0,
        "t": 1.0,
        "delta0": 0.9,
        "Delta0": 3.0,
    }
    metadata = {
        "schema_version": 2,
        "complete": True,
        "parameters": {
            "L": 4,
            "U": 0.0,
            "t": 1.0,
            "delta0": 0.9,
            "Delta0": 3.0,
            "N_up": 2,
            "N_down": 2,
        },
        "basis_fingerprint": fingerprint
        or hashlib.sha256(engine.basis.states.tobytes()).hexdigest(),
        "basis_dimension": engine.basis.Ns,
        "grid_sizes": [5],
        "vertex_count": 25,
        "summary": summary,
        "grid_summaries": [summary],
    }
    np.savez_compressed(
        path,
        schema_version=np.asarray(2),
        metadata_json=json.dumps(metadata, sort_keys=True),
        theta_numerators=np.asarray([theta for theta, _ in coordinates]),
        theta_denominators=np.full(25, 5),
        phi_numerators=np.asarray([phi for _, phi in coordinates]),
        phi_denominators=np.full(25, 5),
        states=result.states.reshape(25, engine.basis.Ns),
        energies=np.column_stack(
            (
                result.ground_state_energies.ravel(),
                result.first_excited_energies.ravel(),
            )
        ),
        gaps=result.gaps.ravel(),
        hermiticity_errors=result.hermiticity_errors.ravel(),
        residuals=result.residuals.ravel(),
        flux_N5=result.fhs.flux,
        e0_N5=result.ground_state_energies,
        e1_N5=result.first_excited_energies,
    )
    return result


def test_legacy_checkpoint_seeds_all_vertices_without_rediagonalizing(tmp_path):
    path = tmp_path / "legacy.npz"
    expected = _write_legacy_checkpoint(path)
    target = EDEngine(
        RiceMeleHubbardModel(
            ModelParameters(L=4, t=1.0, U=0.0, N_up=2, N_down=2)
        )
    )

    loaded = load_chern_checkpoint(
        path,
        target,
        point=type(parameter_points()[0])(index=0, U=0.0, t=1.0),
        grid_size=5,
    )
    rescanned = scan_chern(target, n_theta=5, n_phi=5)

    assert loaded.vertex_count == 25
    assert target.cached_vertex_count == 25
    assert rescanned.new_diagonalizations == 0
    np.testing.assert_allclose(rescanned.states, expected.states)
    assert rescanned.fhs.chern_raw == pytest.approx(expected.fhs.chern_raw)


def test_legacy_checkpoint_rejects_basis_order_mismatch(tmp_path):
    path = tmp_path / "bad-basis.npz"
    _write_legacy_checkpoint(path, fingerprint="0" * 64)
    target = EDEngine(
        RiceMeleHubbardModel(
            ModelParameters(L=4, t=1.0, U=0.0, N_up=2, N_down=2)
        )
    )

    with pytest.raises(ValueError, match="basis fingerprint"):
        load_chern_checkpoint(
            path,
            target,
            point=type(parameter_points()[0])(index=0, U=0.0, t=1.0),
            grid_size=5,
        )


def test_chern_checkpoint_write_is_atomic_exclusive_and_reloadable(tmp_path):
    point = type(parameter_points()[0])(index=0, U=0.0, t=1.0)
    engine = EDEngine(
        RiceMeleHubbardModel(
            ModelParameters(L=4, t=1.0, U=0.0, N_up=2, N_down=2)
        )
    )
    coarse = scan_chern(engine, n_theta=5, n_phi=5)
    fine = scan_chern(engine, n_theta=10, n_phi=10)
    path = tmp_path / pair_checkpoint_name(point, 10)

    save_chern_checkpoint(path, engine, point=point, results=(coarse, fine))
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        save_chern_checkpoint(path, engine, point=point, results=(coarse, fine))
    assert path.read_bytes() == original

    target = EDEngine(
        RiceMeleHubbardModel(
            ModelParameters(L=4, t=1.0, U=0.0, N_up=2, N_down=2)
        )
    )
    loaded = load_chern_checkpoint(path, target, point=point, grid_size=10)
    rescanned = scan_chern(target, n_theta=10, n_phi=10)
    assert loaded.vertex_count == 100
    assert rescanned.new_diagonalizations == 0
    assert rescanned.minimum_gap == pytest.approx(fine.minimum_gap)
    assert rescanned.fhs.chern_raw == pytest.approx(fine.fhs.chern_raw)


def test_offset_path_checkpoint_cannot_seed_a_centered_path(tmp_path):
    point = type(parameter_points()[0])(index=0, U=0.0, t=1.0)
    offset_engine = EDEngine(
        RiceMeleHubbardModel(
            ModelParameters(
                L=4,
                t=1.0,
                U=0.0,
                N_up=2,
                N_down=2,
                Delta_center=1.5,
            )
        )
    )
    result = scan_chern(offset_engine, n_theta=5, n_phi=5)
    path = tmp_path / "offset.npz"
    save_chern_checkpoint(path, offset_engine, point=point, results=(result,))

    centered_engine = EDEngine(
        RiceMeleHubbardModel(
            ModelParameters(L=4, t=1.0, U=0.0, N_up=2, N_down=2)
        )
    )
    with pytest.raises(ValueError, match="parameters do not match"):
        load_chern_checkpoint(
            path,
            centered_engine,
            point=point,
            grid_size=5,
        )


def test_static_worker_reuses_legacy_chern_for_gap_and_adiabatic_charge(tmp_path):
    point = type(parameter_points()[0])(index=0, U=0.0, t=1.0)
    legacy_dir = tmp_path / "legacy"
    chern_dir = tmp_path / "chern"
    static_dir = tmp_path / "static"
    legacy_dir.mkdir()
    legacy_path = legacy_dir / pair_checkpoint_name(point, 5)
    _write_legacy_checkpoint(legacy_path)

    output = run_static_point(
        point,
        L=4,
        delta0=0.9,
        Delta0=3.0,
        chern_sizes=(5,),
        polarization_points=5,
        chern_dir=chern_dir,
        static_dir=static_dir,
        resume_dirs=(legacy_dir,),
    )
    summary = validate_static_result(output, expected_point=point, expected_L=4)

    assert output.name == static_result_name(point)
    assert summary["C_MB"] == pytest.approx(2.0, abs=1e-10)
    assert summary["Delta_min"] == pytest.approx(3.6, abs=1e-10)
    assert summary["Q_adiabatic"] == pytest.approx(2.0, abs=1e-8)
    assert summary["chern_checkpoint_reused"] is True
    assert Path(summary["chern_checkpoint"]) == legacy_path

    original = output.read_bytes()
    assert run_static_point(
        point,
        L=4,
        delta0=0.9,
        Delta0=3.0,
        chern_sizes=(5,),
        polarization_points=5,
        chern_dir=chern_dir,
        static_dir=static_dir,
        resume_dirs=(legacy_dir,),
    ) == output
    assert output.read_bytes() == original


def test_realtime_worker_uses_static_ground_state_and_converges_steps(tmp_path):
    point = type(parameter_points()[0])(index=0, U=0.0, t=1.0)
    realtime_point = RealtimePoint(index=0, pair=point, period=10.0)
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    legacy_path = legacy_dir / pair_checkpoint_name(point, 5)
    _write_legacy_checkpoint(legacy_path)
    static_path = run_static_point(
        point,
        L=4,
        delta0=0.9,
        Delta0=3.0,
        chern_sizes=(5,),
        polarization_points=5,
        chern_dir=tmp_path / "chern",
        static_dir=tmp_path / "static",
        resume_dirs=(legacy_dir,),
    )

    output = run_realtime_point(
        realtime_point,
        static_path=static_path,
        realtime_dir=tmp_path / "realtime",
        initial_steps=200,
        charge_tolerance=5e-3,
        max_refinements=2,
    )
    summary = validate_realtime_result(
        output,
        expected_point=realtime_point,
        expected_L=4,
    )

    assert summary["Q_real_time"] == pytest.approx(1.9872303616718463, abs=1e-9)
    assert summary["time_steps"] == 400
    assert summary["maximum_norm_error"] < 1e-12
    assert summary["time_step_charge_error"] < 5e-3


def test_refinement_worker_inserts_only_new_grid_vertices(tmp_path):
    point = type(parameter_points()[0])(index=0, U=0.0, t=1.0)
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    legacy_path = legacy_dir / pair_checkpoint_name(point, 5)
    _write_legacy_checkpoint(legacy_path)
    static_path = run_static_point(
        point,
        L=4,
        delta0=0.9,
        Delta0=3.0,
        chern_sizes=(5,),
        polarization_points=5,
        chern_dir=tmp_path / "chern",
        static_dir=tmp_path / "static",
        resume_dirs=(legacy_dir,),
    )

    assert missing_refinement_points(
        tmp_path / "refined",
        (point,),
        static_dir=tmp_path / "static",
        target_grid=10,
        L=4,
    ) == (point,)
    output = run_refinement_point(
        point,
        static_path=static_path,
        refined_dir=tmp_path / "refined",
        target_grid=10,
    )
    target = EDEngine(
        RiceMeleHubbardModel(
            ModelParameters(L=4, t=1.0, U=0.0, N_up=2, N_down=2)
        )
    )
    loaded = load_chern_checkpoint(output, target, point=point, grid_size=10)

    assert loaded.metadata["summary"]["diagonalization_count"] == 75
    assert loaded.metadata["summary"]["C_raw"] == pytest.approx(2.0)
    assert loaded.metadata["summary"]["gap_min"] == pytest.approx(3.6)
    assert missing_refinement_points(
        tmp_path / "refined",
        (point,),
        static_dir=tmp_path / "static",
        target_grid=10,
        L=4,
    ) == ()


def test_refinement_selection_combines_diagnostics_and_chern_neighbors():
    rows = [
        {"index": 0, "U": 0.0, "t": 0.5, "C_MB_integer": 2,
         "Delta_min": 1.0, "minimum_link_overlap": 0.8,
         "maximum_abs_berry_flux": 0.2},
        {"index": 1, "U": 1.0, "t": 0.5, "C_MB_integer": 0,
         "Delta_min": 1.0, "minimum_link_overlap": 0.8,
         "maximum_abs_berry_flux": 0.2},
        {"index": 2, "U": 0.0, "t": 0.6, "C_MB_integer": 2,
         "Delta_min": 0.2, "minimum_link_overlap": 0.8,
         "maximum_abs_berry_flux": 0.2},
        {"index": 3, "U": 1.0, "t": 0.6, "C_MB_integer": 2,
         "Delta_min": 1.0, "minimum_link_overlap": 0.2,
         "maximum_abs_berry_flux": 0.2},
        {"index": 4, "U": 2.0, "t": 0.6, "C_MB_integer": 2,
         "Delta_min": 1.0, "minimum_link_overlap": 0.8,
         "maximum_abs_berry_flux": 0.8},
    ]

    assert select_refinement_indices_from_summaries(rows) == (0, 1, 2, 3, 4)


def test_aggregate_refuses_partial_manifest_and_publishes_complete_one(tmp_path):
    point = type(parameter_points()[0])(index=0, U=0.0, t=1.0)
    realtime_point = RealtimePoint(index=0, pair=point, period=2.0)
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    legacy_path = legacy_dir / pair_checkpoint_name(point, 5)
    _write_legacy_checkpoint(legacy_path)
    static_path = run_static_point(
        point,
        L=4,
        delta0=0.9,
        Delta0=3.0,
        chern_sizes=(5,),
        polarization_points=5,
        chern_dir=tmp_path / "chern",
        static_dir=tmp_path / "static",
        resume_dirs=(legacy_dir,),
    )
    assert missing_static_points(tmp_path / "static", (point,), L=4) == ()
    assert missing_realtime_points(
        tmp_path / "realtime", (realtime_point,), L=4
    ) == (realtime_point,)

    with pytest.raises(ValueError, match="real-time.*missing"):
        aggregate_complete_results(
            static_dir=tmp_path / "static",
            realtime_dir=tmp_path / "realtime",
            refined_dir=tmp_path / "refined",
            output_dir=tmp_path / "aggregate",
            points=(point,),
            dynamics=(realtime_point,),
            refinement_indices=(),
            L=4,
            refined_grid=10,
        )

    run_realtime_point(
        realtime_point,
        static_path=static_path,
        realtime_dir=tmp_path / "realtime",
        initial_steps=40,
        charge_tolerance=2e-2,
        max_refinements=2,
    )
    aggregate = aggregate_complete_results(
        static_dir=tmp_path / "static",
        realtime_dir=tmp_path / "realtime",
        refined_dir=tmp_path / "refined",
        output_dir=tmp_path / "aggregate",
        points=(point,),
        dynamics=(realtime_point,),
        refinement_indices=(),
        L=4,
        refined_grid=10,
    )

    assert (aggregate / "static_summary.csv").is_file()
    assert (aggregate / "realtime_summary.csv").is_file()
    complete = json.loads((aggregate / "run_complete.json").read_text())
    assert complete["static_count"] == 1
    assert complete["realtime_count"] == 1


def test_cluster_worker_cli_emits_manifest_missing_and_static_result(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    script = project_root / "scripts" / "cluster_worker.py"
    python = "/tmp/challenge36-quspin-venv/bin/python"
    manifest = subprocess.run(
        [python, str(script), "manifest", "--kind", "static"],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert len(manifest) == 451
    assert json.loads(manifest[0])["index"] == 0
    assert json.loads(manifest[-1])["index"] == 450

    missing = subprocess.run(
        [
            python,
            str(script),
            "missing",
            "--kind",
            "static",
            "--result-dir",
            str(tmp_path / "empty"),
            "--L",
            "4",
        ],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert missing == manifest

    point = parameter_points()[8]
    assert (point.U, point.t) == (0.0, 0.5)
    task_map = tmp_path / "one.jsonl"
    task_map.write_text(json.dumps(json.loads(manifest[8])) + "\n")
    completed = subprocess.run(
        [
            python,
            str(script),
            "static",
            "--task-map",
            str(task_map),
            "--task-id",
            "0",
            "--L",
            "4",
            "--chern-sizes",
            "5",
            "--polarization-points",
            "5",
            "--chern-dir",
            str(tmp_path / "chern"),
            "--static-dir",
            str(tmp_path / "static"),
        ],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["kind"] == "static"
    assert payload["index"] == 8
    assert Path(payload["output"]).is_file()


def test_cluster_controller_retries_after_failed_sbatch_wait(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    source = tmp_path / "source"
    run_dir = tmp_path / "run"
    fake_bin = tmp_path / "bin"
    source.mkdir()
    fake_bin.mkdir()
    (source / "SOURCE_COMMIT").write_text("test-commit\n")
    (source / "scripts").mkdir()
    (source / "scripts" / "cluster_worker.py").write_text("# fixture\n")
    (source / "cluster").mkdir()
    (source / "cluster" / "worker.slurm").write_text("# fixture\n")

    fake_python = fake_bin / "fake-python"
    fake_python.write_text(
        """#!/bin/bash
set -u
command=$2
shift 2
case "$command" in
  manifest)
    kind=""
    while (($#)); do
      [[ $1 == --kind ]] && kind=$2 && shift 2 || shift
    done
    [[ $kind == static ]] && echo '{"U":-32.0,"index":0,"t":0.5}'
    true
    ;;
  missing)
    kind=""
    while (($#)); do
      [[ $1 == --kind ]] && kind=$2 && shift 2 || shift
    done
    if [[ $kind == static && ! -e $SCAN_RUN_DIR/fake_done ]]; then
      echo '{"U":-32.0,"index":0,"t":0.5}'
    fi
    ;;
  select) ;;
  aggregate)
    mkdir -p "$SCAN_RUN_DIR/aggregate"
    echo '{"complete":true}' > "$SCAN_RUN_DIR/aggregate/run_complete.json"
    echo '{"kind":"aggregate"}'
    ;;
esac
"""
    )
    fake_python.chmod(0o755)
    fake_sbatch = fake_bin / "sbatch"
    fake_sbatch.write_text(
        """#!/bin/bash
set -u
count_file=$SCAN_RUN_DIR/fake_sbatch_count
count=0
[[ -e $count_file ]] && count=$(<"$count_file")
count=$((count + 1))
echo "$count" > "$count_file"
echo "fake-job-$count"
if ((count == 1)); then
  exit 1
fi
touch "$SCAN_RUN_DIR/fake_done"
"""
    )
    fake_sbatch.chmod(0o755)

    environment = {
        **dict(os.environ),
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "SCAN_RUN_DIR": str(run_dir),
        "SCAN_SOURCE_DIR": str(source),
        "SCAN_SOURCE_COMMIT": "test-commit",
        "SCAN_PYTHON": str(fake_python),
        "SCAN_MAX_CONCURRENT": "2",
        "SCAN_CHUNK_SIZE": "2",
    }
    completed = subprocess.run(
        ["bash", str(project_root / "cluster" / "launch.sh")],
        cwd=project_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert (run_dir / "fake_sbatch_count").read_text().strip() == "2"
    status = json.loads((run_dir / "controller_status.json").read_text())
    assert status["state"] == "COMPLETE"
    assert (run_dir / "aggregate" / "run_complete.json").is_file()
    assert "submission_rc=1" in completed.stdout


def test_cluster_controller_does_not_submit_stale_chunks_after_restart(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    source = tmp_path / "source"
    run_dir = tmp_path / "run"
    task_maps = run_dir / "task_maps"
    fake_bin = tmp_path / "bin"
    source.mkdir()
    task_maps.mkdir(parents=True)
    fake_bin.mkdir()
    (source / "SOURCE_COMMIT").write_text("test-commit\n")
    (source / "scripts").mkdir()
    (source / "scripts" / "cluster_worker.py").write_text("# fixture\n")
    (source / "cluster").mkdir()
    (source / "cluster" / "worker.slurm").write_text("# fixture\n")
    stale_chunk = task_maps / "static_attempt_001_chunk_0001.jsonl"
    stale_chunk.write_text('{"U":-24.0,"index":1,"t":0.5}\n')

    fake_python = fake_bin / "fake-python"
    fake_python.write_text(
        """#!/bin/bash
set -u
command=$2
shift 2
case "$command" in
  manifest)
    kind=""
    while (($#)); do
      [[ $1 == --kind ]] && kind=$2 && shift 2 || shift
    done
    if [[ $kind == static ]]; then
      echo '{"U":-32.0,"index":0,"t":0.5}'
      echo '{"U":-24.0,"index":1,"t":0.5}'
    fi
    ;;
  missing)
    kind=""
    while (($#)); do
      [[ $1 == --kind ]] && kind=$2 && shift 2 || shift
    done
    if [[ $kind == static && ! -e $SCAN_RUN_DIR/fake_done ]]; then
      echo '{"U":-32.0,"index":0,"t":0.5}'
    fi
    ;;
  select) ;;
  aggregate)
    mkdir -p "$SCAN_RUN_DIR/aggregate"
    echo '{"complete":true}' > "$SCAN_RUN_DIR/aggregate/run_complete.json"
    echo '{"kind":"aggregate"}'
    ;;
esac
"""
    )
    fake_python.chmod(0o755)
    fake_sbatch = fake_bin / "sbatch"
    fake_sbatch.write_text(
        """#!/bin/bash
set -u
task_map=""
for argument in "$@"; do
  case "$argument" in
    --export=*)
      export_values=${argument#--export=}
      IFS=',' read -ra values <<< "$export_values"
      for value in "${values[@]}"; do
        [[ $value == SCAN_TASK_MAP=* ]] && task_map=${value#SCAN_TASK_MAP=}
      done
      ;;
  esac
done
printf '%s\n' "$(basename "$task_map")" >> "$SCAN_RUN_DIR/submitted_chunks.txt"
touch "$SCAN_RUN_DIR/fake_done"
echo fake-job
"""
    )
    fake_sbatch.chmod(0o755)

    environment = {
        **dict(os.environ),
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "SCAN_RUN_DIR": str(run_dir),
        "SCAN_SOURCE_DIR": str(source),
        "SCAN_SOURCE_COMMIT": "test-commit",
        "SCAN_PYTHON": str(fake_python),
        "SCAN_MAX_CONCURRENT": "2",
        "SCAN_CHUNK_SIZE": "2",
    }
    subprocess.run(
        ["bash", str(project_root / "cluster" / "launch.sh")],
        cwd=project_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert (run_dir / "submitted_chunks.txt").read_text().splitlines() == [
        "static_attempt_001_chunk_0000.jsonl"
    ]
