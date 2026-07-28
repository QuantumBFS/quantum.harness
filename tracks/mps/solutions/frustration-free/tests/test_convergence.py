from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import threading
import time

import pytest
from jsonschema import Draft202012Validator


SOLUTION_DIR = Path(__file__).parents[1]
MODULE_PATH = SOLUTION_DIR / "convergence.py"
SPEC = importlib.util.spec_from_file_location("challenge_81_convergence", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
convergence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(convergence)


def test_machine_readable_schema_covers_plan_cell_and_analysis():
    schema = json.loads(
        (SOLUTION_DIR / "convergence.schema.json").read_text(encoding="utf-8")
    )
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert set(schema["$defs"]) >= {
        "convergencePlan",
        "completedCell",
        "convergenceAnalysis",
        "resourceEstimate",
    }
    assert schema["oneOf"] == [
        {"$ref": "#/$defs/convergencePlan"},
        {"$ref": "#/$defs/completedCell"},
        {"$ref": "#/$defs/convergenceAnalysis"},
        {"$ref": "#/$defs/resourceEstimate"},
    ]


def test_slurm_array_wrapper_is_profile_driven_and_one_cell_restartable():
    script = (SOLUTION_DIR / "convergence_slurm_array.sh").read_text(
        encoding="utf-8"
    )
    assert "HARNESS_RUN_SPEC" in script
    assert "HARNESS_RUN_DIR" in script
    assert "HARNESS_RESOURCES" in script
    assert "HARNESS_RESOURCE_ACK" in script
    assert "HARNESS_SOLUTION_DIR" in script
    assert "SLURM_ARRAY_TASK_ID" in script
    assert '${JULIA_PROJECT:?set JULIA_PROJECT' in script
    assert "JULIA_PROJECT:-" not in script
    assert 'run-cell' in script
    assert "--cell-index" in script
    assert "--execution-target cluster" in script
    assert "#SBATCH --partition" not in script
    assert "ssh " not in script


def test_slurm_array_wrapper_uses_explicit_solution_directory_when_spooled(tmp_path):
    solution_dir = tmp_path / "solution"
    solution_dir.mkdir()
    output_path = tmp_path / "arguments.json"
    (solution_dir / "convergence.py").write_text(
        "import json, os, sys\n"
        "with open(os.environ['WRAPPER_ARGUMENTS'], 'w', encoding='utf-8') as stream:\n"
        "    json.dump(sys.argv, stream)\n",
        encoding="utf-8",
    )
    spool_dir = tmp_path / "slurm-spool"
    spool_dir.mkdir()
    wrapper = spool_dir / "job.sh"
    shutil.copy2(SOLUTION_DIR / "convergence_slurm_array.sh", wrapper)
    environment = {
        **os.environ,
        "HARNESS_SOLUTION_DIR": str(solution_dir),
        "HARNESS_RUN_SPEC": "/run/plan.json",
        "HARNESS_RUN_DIR": "/run",
        "HARNESS_RESOURCES": "/run/resources.json",
        "HARNESS_RESOURCE_ACK": "resource-sha256",
        "SLURM_ARRAY_TASK_ID": "7",
        "JULIA_PROJECT": "/runtime/julia",
        "PYTHON": sys.executable,
        "WRAPPER_ARGUMENTS": str(output_path),
    }

    subprocess.run(["bash", str(wrapper)], env=environment, check=True)

    arguments = json.loads(output_path.read_text(encoding="utf-8"))
    assert arguments[0] == str(solution_dir / "convergence.py")
    assert arguments[1:] == [
        "run-cell",
        "--plan",
        "/run/plan.json",
        "--run-directory",
        "/run",
        "--resources",
        "/run/resources.json",
        "--acknowledge-resources",
        "resource-sha256",
        "--cell-index",
        "7",
        "--execution-target",
        "cluster",
        "--julia-project",
        "/runtime/julia",
    ]


def _plan(**overrides):
    settings = {
        "betas": [16.0, 32.0],
        "cutoffs": [1.0e-12],
        "tau_fractions": [0.0, 0.25, 0.5, 0.75, 1.0],
        "stage": "production",
    }
    settings.update(overrides)
    return convergence.make_plan(**settings)


def _solver_result(cell, shift=0.0):
    beta = cell["parameters"]["beta"]
    tau = [beta * fraction for fraction in cell["tau_fractions"]]
    n_d = 1.0 + shift
    green = [
        (
            -(1.0 - n_d / 2.0)
            if point == 0.0
            else -n_d / 2.0
            if point == beta
            else -0.5 + shift
        )
        for point in tau
    ]
    bath_file_sha256 = convergence._sha256(
        convergence._canonical_json(cell["bath_artifact"]) + b"\n"
    )
    branch = [
        {
            "tau": point,
            "spin": spin,
            "insertion": (
                "annihilation" if point == beta else "creation"
            ),
            "branch_status": (
                "endpoint_identity" if point in (0.0, beta) else "finite"
            ),
            "max_link_dimension": 16,
            "maximum_link_dimensions_by_bond": [4, 16, 8],
            "truncation_max_error": 1.0e-13,
            "krylov_all_converged": True,
            "krylov_max_error_estimate": 1.0e-13,
            "krylov_num_operations": 0 if point in (0.0, beta) else 20,
            "krylov_num_iterations": 0 if point in (0.0, beta) else 4,
            "krylov_local_updates": 0 if point in (0.0, beta) else 8,
        }
        for spin in ("up", "dn")
        for point in tau
    ]
    return {
        "schema_version": 1,
        "input_sha256": "a" * 64,
        "input_payload_sha256": "b" * 64,
        "solver": {
            "name": "finite_bath_mps",
            "settings": copy.deepcopy(cell["solver_settings"]),
        },
        "tau": tau,
        "observables": {
            "n_d": n_d,
            "double_occupancy": 0.2 + shift,
            "G_up": green,
            "G_down": green.copy(),
        },
        "diagnostics": {
            "finite": True,
            "profiling": {
                "phase_timings_seconds": {
                    "request_validation": 0.01,
                    "context_and_evolution": 0.9,
                    "result_serialization": 0.02,
                },
                "julia_threads": 2,
                "blas_threads": 1,
                "blas_vendor": "test",
                "julia_version": "test",
                "peak_rss_bytes": 123456,
                "actual_mpo_link_dimensions": [4, 7, 4],
            },
            "krylov_expansion_dim": 0,
            "expansion_policy": "tdvp_only",
            "thermal_max_link_dimension": 16,
            "maximum_link_dimensions_by_bond": [4, 16, 8],
            "thermal": {
                "steps": 2,
                "max_link_dimension": 16,
                "maximum_link_dimensions_by_bond": [4, 16, 8],
                "truncation_max_error": 1.0e-13,
                "krylov_all_converged": True,
                "krylov_max_error_estimate": 1.0e-13,
                "krylov_num_operations": 20,
                "krylov_num_iterations": 4,
                "krylov_local_updates": 8,
            },
            "green_up": [entry for entry in branch if entry["spin"] == "up"],
            "green_down": [entry for entry in branch if entry["spin"] == "dn"],
        },
        "provenance": {
            "runner": "finite_bath_mps_runner",
            "runner_version": "test",
            "julia_version": "test",
            "itensors_version": "test",
            "itensormps_version": "test",
            "active_project_path": str(
                (SOLUTION_DIR / "julia" / "Project.toml").resolve()
            ),
            "manifest_path": str(
                (SOLUTION_DIR / "julia" / "Manifest.toml").resolve()
            ),
            "project_toml_sha256": cell["provenance"][
                "julia_environment_sha256"
            ]["Project.toml"],
            "manifest_toml_sha256": cell["provenance"][
                "julia_environment_sha256"
            ]["Manifest.toml"],
            "runner_source_sha256": cell["provenance"]["source_sha256"][
                "finite_bath_mps_runner.jl"
            ],
            "purification_source_sha256": cell["provenance"]["source_sha256"][
                "finite_bath_purification.jl"
            ],
            "observables_source_sha256": cell["provenance"]["source_sha256"][
                "finite_bath_observables.jl"
            ],
            "model_definition_sha256": cell["provenance"]["source_sha256"][
                "model.json"
            ],
            "bath_artifact_file_sha256": bath_file_sha256,
            "krylov_expansion_dim": 0,
            "expansion_policy": "tdvp_only",
        },
    }


def _complete(cell, shift=0.0):
    return convergence.make_cell_artifact(
        cell=cell,
        solver_output=_solver_result(cell, shift),
        wall_time_seconds=1.25,
        peak_rss_bytes=123456,
        peak_rss_method="test",
    )


def test_initial_plan_is_deterministic_hash_bound_and_tdvp_only():
    first = _plan()
    second = _plan()

    assert first == second
    assert first["plan_sha256"] == convergence.plan_sha256(first)
    assert len(first["cells"]) == 14
    assert {cell["parameters"]["beta"] for cell in first["cells"]} == {16.0, 32.0}
    assert {cell["parameters"]["n_bath"] for cell in first["cells"]} == {
        12,
        24,
        48,
    }
    assert {cell["solver_settings"]["time_step"] for cell in first["cells"]} == {
        0.2,
        0.1,
        0.05,
    }
    assert {cell["solver_settings"]["maxdim"] for cell in first["cells"]} == {
        128,
        256,
        512,
    }
    assert all(
        cell["solver_settings"]["krylov_expansion_dim"] == 0
        for cell in first["cells"]
    )
    assert len({cell["cell_id"] for cell in first["cells"]}) == len(first["cells"])
    assert len({cell["input_sha256"] for cell in first["cells"]}) == len(
        first["cells"]
    )
    assert all(cell["bath_artifact_sha256"] for cell in first["cells"])
    for beta in (16.0, 32.0):
        beta_cells = [
            cell for cell in first["cells"] if cell["parameters"]["beta"] == beta
        ]
        anchor = [
            cell
            for cell in beta_cells
            if cell["parameters"]["n_bath"] == 12
            and cell["solver_settings"]["time_step"] == 0.05
            and cell["solver_settings"]["maxdim"] == 512
        ]
        assert len(anchor) == 1
        assert len(beta_cells) == 7
    assert first["bath_resolution_policy"]["bath_sizes"] == [12, 24, 48]
    assert first["bath_resolution_policy"]["finest_ratio_limit"] == 1.1
    assert first["solver_feasibility"]["n_bath_48"]["chain_mapping_required"] is True
    assert first["artifact_type"] == "convergence_plan"
    assert first["generator"] == {
        "name": "convergence.py",
        "version": convergence.MODULE_VERSION,
    }
    assert first["software_version"] == convergence.SOFTWARE_VERSION
    assert first["run_id"] == f"run-{first['plan_sha256'][:16]}"


def test_pilot_plan_is_staged_and_not_a_production_claim():
    plan = _plan(
        betas=[0.2],
        bath_sizes=[1],
        time_steps=[0.1],
        maxdims=[32],
        stage="pilot",
    )

    assert len(plan["cells"]) == 1
    assert plan["claim_policy"]["production_eligible"] is False
    assert plan["cells"][0]["solver_settings"]["krylov_expansion_dim"] == 0


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"betas": [0.0]}, "beta"),
        ({"bath_sizes": [0]}, "bath"),
        ({"time_steps": [float("nan")]}, "time_step"),
        ({"cutoffs": [-1.0]}, "cutoff"),
        ({"maxdims": [True]}, "maxdim"),
        ({"tau_fractions": [0.0, 1.1]}, "tau"),
    ],
)
def test_plan_validation_fails_closed(kwargs, match):
    with pytest.raises((TypeError, ValueError), match=match):
        _plan(**kwargs)


def test_plan_validation_rejects_production_krylov_expansion():
    plan = _plan()
    plan["cells"][0]["solver_settings"]["krylov_expansion_dim"] = 32
    with pytest.raises(ValueError, match="krylov_expansion_dim|0 was expected"):
        convergence.validate_plan(plan)


def test_execution_rejects_plan_bound_to_stale_sources():
    cell = _plan()["cells"][0]
    cell["provenance"]["source_sha256"]["convergence.py"] = "f" * 64

    with pytest.raises(ValueError, match="source provenance"):
        convergence.validate_execution_environment(
            cell, julia_project=SOLUTION_DIR / "julia"
        )


def test_plan_binds_selected_julia_project_and_all_sources(tmp_path):
    project = tmp_path / "julia"
    project.mkdir()
    shutil.copy(SOLUTION_DIR / "julia" / "Project.toml", project / "Project.toml")
    shutil.copy(SOLUTION_DIR / "julia" / "Manifest.toml", project / "Manifest.toml")
    for name in (
        "finite_bath_mps_runner.jl",
        "finite_bath_observables.jl",
        "finite_bath_purification.jl",
    ):
        (project / name).write_text("# decoy project-local source\n", encoding="utf-8")

    plan = convergence.make_plan(
        betas=[0.2],
        bath_sizes=[1],
        time_steps=[0.1],
        maxdims=[32],
        stage="pilot",
        julia_project=project,
    )

    assert "runtime_absolute_paths" not in plan["execution_environment"]
    assert plan["execution_environment"]["repository_relative_paths"] == {
        "solution": "tracks/mps/solutions/frustration-free",
        "julia_project": "tracks/mps/solutions/frustration-free/julia",
    }
    assert set(plan["execution_environment"]["source_sha256"]) >= {
        "acceptance.py",
        "bath.py",
        "convergence.py",
        "convergence.schema.json",
        "model.json",
        "pyproject.toml",
        "uv.lock",
        "finite_bath_mps_runner.jl",
        "finite_bath_observables.jl",
        "finite_bath_purification.jl",
    }
    assert plan["execution_environment"]["source_sha256"][
        "finite_bath_mps_runner.jl"
    ] == convergence._sha256_file(SOLUTION_DIR / "julia" / "finite_bath_mps_runner.jl")
    portable = tmp_path / "portable-checkout"
    portable.mkdir()
    shutil.copy(project / "Project.toml", portable / "Project.toml")
    shutil.copy(project / "Manifest.toml", portable / "Manifest.toml")
    convergence.validate_execution_environment(
        plan["cells"][0], julia_project=portable
    )
    second = convergence.make_plan(
        betas=[0.2],
        bath_sizes=[1],
        time_steps=[0.1],
        maxdims=[32],
        stage="pilot",
        julia_project=portable,
    )
    assert second == plan
    with pytest.raises(TypeError, match="julia_project"):
        convergence.validate_execution_environment(plan["cells"][0])


def test_completed_cell_is_skipped_but_stale_cell_fails_closed(tmp_path):
    plan = _plan(
        betas=[0.2],
        bath_sizes=[1],
        time_steps=[0.1],
        maxdims=[32],
        stage="pilot",
    )
    calls = []

    def executor(cell, staging):
        calls.append(cell["cell_id"])
        return _solver_result(cell)

    first = convergence.run_cell(
        plan, 0, tmp_path, executor=executor, julia_project=SOLUTION_DIR / "julia"
    )
    second = convergence.run_cell(
        plan, 0, tmp_path, executor=executor, julia_project=SOLUTION_DIR / "julia"
    )

    assert first["action"] == "completed"
    assert second["action"] == "skipped"
    assert calls == [plan["cells"][0]["cell_id"]]

    cell_path = tmp_path / "cells" / plan["cells"][0]["cell_id"] / "cell.json"
    stale = json.loads(cell_path.read_text(encoding="utf-8"))
    stale["input_sha256"] = "f" * 64
    cell_path.write_text(json.dumps(stale), encoding="utf-8")

    with pytest.raises(ValueError, match="stale|invalid|immutable"):
        convergence.run_cell(
            plan,
            0,
            tmp_path,
            executor=executor,
            julia_project=SOLUTION_DIR / "julia",
        )
    assert calls == [plan["cells"][0]["cell_id"]]
    assert set(first["cell"]["artifact_file_sha256"]) == {
        "bath.json",
        "mps-input.json",
        "mps-result.json",
    }
    assert any(
        path.name.startswith(f".{plan['cells'][0]['cell_id']}.superseded-")
        for path in cell_path.parent.parent.iterdir()
    )


def test_execution_rejects_solver_runtime_project_path_mismatch(tmp_path):
    plan = _plan(
        betas=[0.2],
        bath_sizes=[1],
        time_steps=[0.1],
        maxdims=[32],
        stage="pilot",
    )

    def executor(cell, _staging):
        result = _solver_result(cell)
        result["provenance"]["active_project_path"] = "/stale/julia"
        return result

    with pytest.raises(ValueError, match="runtime Julia project"):
        convergence.run_cell(
            plan,
            0,
            tmp_path,
            executor=executor,
            julia_project=SOLUTION_DIR / "julia",
        )


def test_tampered_published_file_fails_closed_and_is_archived(tmp_path):
    plan = _plan(
        betas=[0.2],
        bath_sizes=[1],
        time_steps=[0.1],
        maxdims=[32],
        stage="pilot",
    )
    calls = []

    def executor(cell, _staging):
        calls.append(cell["cell_id"])
        return _solver_result(cell)

    first = convergence.run_cell(
        plan, 0, tmp_path, executor=executor, julia_project=SOLUTION_DIR / "julia"
    )
    cell_root = first["path"]
    (cell_root / "mps-result.json").write_bytes(b"tampered\n")

    with pytest.raises(ValueError, match="stale|invalid|immutable"):
        convergence.run_cell(
            plan,
            0,
            tmp_path,
            executor=executor,
            julia_project=SOLUTION_DIR / "julia",
        )
    assert len(calls) == 1
    assert not cell_root.exists()
    assert any(
        path.name.startswith(f".{plan['cells'][0]['cell_id']}.superseded-")
        for path in cell_root.parent.iterdir()
    )


def test_validate_existing_rejects_superseded_plan_and_resource_versions(tmp_path):
    plan = _plan(
        betas=[0.2],
        bath_sizes=[1],
        time_steps=[0.1],
        maxdims=[32],
        stage="pilot",
    )
    resources = convergence.estimate_plan_resources(plan)
    plan_path = tmp_path / "plan.json"
    resource_path = tmp_path / "resources.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    resource_path.write_text(json.dumps(resources), encoding="utf-8")

    assert convergence.validate_existing(
        plan_path=plan_path, resources_path=resource_path
    )["valid"] is True

    stale = copy.deepcopy(plan)
    stale["generator"]["version"] = "0.0.0"
    stale["plan_sha256"] = convergence.plan_sha256(stale)
    plan_path.write_text(json.dumps(stale), encoding="utf-8")
    with pytest.raises(ValueError, match="generator|version"):
        convergence.validate_existing(
            plan_path=plan_path, resources_path=resource_path
        )


def test_create_plan_run_uses_new_content_addressed_directory(tmp_path):
    plan = _plan(
        betas=[0.2],
        bath_sizes=[1],
        time_steps=[0.1],
        maxdims=[32],
        stage="pilot",
    )

    plan_path = convergence.create_plan_run(tmp_path, plan)

    assert plan_path == tmp_path / plan["run_id"] / "plan.json"
    assert convergence._load_json(plan_path, "plan") == plan
    resources = convergence._load_json(
        plan_path.parent / "resources.json", "resources"
    )
    convergence.validate_resources(resources, plan)
    completion = convergence._load_json(
        plan_path.parent / "completion.json", "completion"
    )
    assert completion["plan_sha256"] == plan["plan_sha256"]
    assert completion["resource_sha256"] == resources["resource_sha256"]
    assert convergence._load_json(tmp_path / "current.json", "pointer") == {
        "schema_version": 1,
        "run_id": plan["run_id"],
        "plan_sha256": plan["plan_sha256"],
        "resource_sha256": resources["resource_sha256"],
        "completion_sha256": completion["completion_sha256"],
        "relative_path": plan["run_id"],
    }
    (tmp_path / "current.json").unlink()
    assert convergence.create_plan_run(tmp_path, plan) == plan_path
    assert (tmp_path / "current.json").is_file()


def test_plan_run_publication_failure_never_exposes_final_directory(
    tmp_path, monkeypatch
):
    plan = _plan(
        betas=[0.2],
        bath_sizes=[1],
        time_steps=[0.1],
        maxdims=[32],
        stage="pilot",
    )
    real_replace = convergence.os.replace

    def fail_publish(source, target):
        if Path(target) == tmp_path / plan["run_id"]:
            raise OSError("injected plan publication failure")
        return real_replace(source, target)

    monkeypatch.setattr(convergence.os, "replace", fail_publish)

    with pytest.raises(OSError, match="publication"):
        convergence.create_plan_run(tmp_path, plan)

    assert not (tmp_path / plan["run_id"]).exists()
    assert not (tmp_path / "current.json").exists()
    assert list(tmp_path.glob(".run.stage-*"))


def test_plan_startup_recovery_archives_abandoned_staging(tmp_path):
    stage = tmp_path / ".run.stage-dead"
    stage.mkdir()
    (stage / "partial").write_text("preserve", encoding="utf-8")

    archived = convergence.recover_plan_publication_state(tmp_path)

    assert len(archived) == 1
    assert archived[0].name.startswith(".run.abandoned-stage-")
    assert (archived[0] / "partial").read_text(encoding="utf-8") == "preserve"


def test_validate_existing_rejects_unexpected_cells_but_reports_archives(tmp_path):
    plan = _plan(
        betas=[0.2],
        bath_sizes=[1],
        time_steps=[0.1],
        maxdims=[32],
        stage="pilot",
    )
    plan_path = convergence.create_plan_run(tmp_path, plan)
    run = plan_path.parent
    cells = run / "cells"
    cells.mkdir()
    archived = cells / f".{plan['cells'][0]['cell_id']}.superseded-old"
    archived.mkdir()

    result = convergence.validate_existing(
        plan_path=plan_path,
        resources_path=run / "resources.json",
        run_directory=run,
    )
    assert result["archived_cells"] == 1

    forged_archive = cells / f".{plan['cells'][0]['cell_id']}.superseded-forged"
    forged_archive.write_text("not an archive directory", encoding="utf-8")
    with pytest.raises(ValueError, match="archive.*directory"):
        convergence.validate_existing(
            plan_path=plan_path,
            resources_path=run / "resources.json",
            run_directory=run,
        )
    forged_archive.unlink()

    (cells / "stale-cell").mkdir()
    with pytest.raises(ValueError, match="unexpected.*cell|stale-cell"):
        convergence.validate_existing(
            plan_path=plan_path,
            resources_path=run / "resources.json",
            run_directory=run,
        )


def _write_completed_cell_tree(run, artifact):
    cell_root = run / "cells" / artifact["cell_id"]
    cell_root.mkdir(parents=True, exist_ok=True)
    for filename in ("bath.json", "mps-input.json", "mps-result.json"):
        payload = f"{artifact['cell_id']}:{filename}\n".encode()
        (cell_root / filename).write_bytes(payload)
        artifact["artifact_file_sha256"][filename] = convergence._sha256(
            payload
        )
    artifact["artifact_sha256"] = convergence._sha256(
        convergence._canonical_json(
            {
                key: value
                for key, value in artifact.items()
                if key != "artifact_sha256"
            }
        )
    )
    (cell_root / "cell.json").write_text(
        json.dumps(artifact), encoding="utf-8"
    )


def _analysis_digest(analysis):
    return convergence._sha256(
        convergence._canonical_json(
            {
                key: value
                for key, value in analysis.items()
                if key != "analysis_sha256"
            }
        )
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "malformed",
        "symlink",
        "wrong_plan",
        "wrong_digest",
        "semantic_forgery",
        "stale_current",
        "malformed_current",
    ],
)
def test_validate_existing_rejects_invalid_analysis_artifacts(tmp_path, mutation):
    plan = _plan(
        betas=[0.2],
        bath_sizes=[1],
        time_steps=[0.1],
        maxdims=[32],
        stage="pilot",
    )
    plan_path = convergence.create_plan_run(tmp_path, plan)
    run = plan_path.parent
    artifact = _complete(plan["cells"][0])
    _write_completed_cell_tree(run, artifact)
    analysis = convergence.analyze_available_cells(plan, [artifact])
    analysis_path = run / "analysis.json"
    analysis_path.write_text(json.dumps(analysis), encoding="utf-8")

    if mutation == "malformed":
        analysis_path.write_text("{", encoding="utf-8")
    elif mutation == "symlink":
        analysis_path.unlink()
        target = tmp_path / "forged-analysis.json"
        target.write_text(json.dumps(analysis), encoding="utf-8")
        analysis_path.symlink_to(target)
    elif mutation == "wrong_plan":
        analysis["plan_sha256"] = "f" * 64
        analysis["analysis_sha256"] = _analysis_digest(analysis)
        analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
    elif mutation == "wrong_digest":
        analysis["analysis_sha256"] = "f" * 64
        analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
    elif mutation == "semantic_forgery":
        analysis["available_cell_count"] += 1
        analysis["analysis_sha256"] = _analysis_digest(analysis)
        analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
    elif mutation == "stale_current":
        pointer_path = tmp_path / "current.json"
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        pointer["completion_sha256"] = "f" * 64
        pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    else:
        (tmp_path / "current.json").write_text("{}", encoding="utf-8")

    with pytest.raises((OSError, TypeError, ValueError)):
        convergence.validate_existing(
            plan_path=plan_path,
            resources_path=run / "resources.json",
            run_directory=run,
        )


def test_validate_existing_accepts_semantically_recomputed_analysis(tmp_path):
    plan = _plan(
        betas=[0.2],
        bath_sizes=[1],
        time_steps=[0.1],
        maxdims=[32],
        stage="pilot",
    )
    plan_path = convergence.create_plan_run(tmp_path, plan)
    run = plan_path.parent
    artifact = _complete(plan["cells"][0])
    _write_completed_cell_tree(run, artifact)
    analysis = convergence.analyze_available_cells(plan, [artifact])
    (run / "analysis.json").write_text(json.dumps(analysis), encoding="utf-8")

    checked = convergence.validate_existing(
        plan_path=plan_path,
        resources_path=run / "resources.json",
        run_directory=run,
    )

    assert checked["analysis"] is True


def test_production_cli_rejects_standalone_plan_export(tmp_path):
    plan = _plan()
    plan_path = tmp_path / "standalone-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    with pytest.raises(ValueError, match="published|bundled|completion"):
        convergence.main(
            [
                "run-cell",
                "--plan",
                str(plan_path),
                "--run-directory",
                str(tmp_path / "run"),
                "--cell-index",
                "0",
                "--julia-project",
                str(SOLUTION_DIR / "julia"),
            ]
        )


def test_atomic_publication_rolls_back_old_cell(tmp_path, monkeypatch):
    destination = tmp_path / "cell"
    destination.mkdir()
    (destination / "cell.json").write_bytes(b"old")
    staging = tmp_path / ".stage"
    staging.mkdir()
    (staging / "cell.json").write_bytes(b"new")
    real_replace = convergence.os.replace
    calls = 0

    def fail_second(source, target):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected publication failure")
        return real_replace(source, target)

    monkeypatch.setattr(convergence.os, "replace", fail_second)
    with pytest.raises(OSError, match="publication"):
        convergence.atomic_publish_directory(staging, destination)
    assert (destination / "cell.json").read_bytes() == b"old"


def test_concurrent_run_cell_executes_and_publishes_once(tmp_path):
    plan = _plan(
        betas=[0.2],
        bath_sizes=[1],
        time_steps=[0.1],
        maxdims=[32],
        stage="pilot",
    )
    calls = []
    barrier = threading.Barrier(2)
    results = []

    def executor(cell, _staging):
        calls.append(cell["cell_id"])
        time.sleep(0.1)
        return _solver_result(cell)

    def worker():
        barrier.wait()
        results.append(
            convergence.run_cell(
                plan,
                0,
                tmp_path,
                executor=executor,
                julia_project=SOLUTION_DIR / "julia",
            )
        )

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert len(calls) == 1
    assert sorted(result["action"] for result in results) == [
        "completed",
        "skipped",
    ]


def test_run_cell_recovers_sigkill_equivalent_abandoned_stage(tmp_path):
    plan = _plan(
        betas=[0.2],
        bath_sizes=[1],
        time_steps=[0.1],
        maxdims=[32],
        stage="pilot",
    )
    cell = plan["cells"][0]
    cells = tmp_path / "cells"
    abandoned = cells / f".{cell['cell_id']}.stage-dead"
    abandoned.mkdir(parents=True)
    (abandoned / "partial.log").write_text("keep for audit", encoding="utf-8")

    convergence.run_cell(
        plan,
        0,
        tmp_path,
        executor=lambda item, _stage: _solver_result(item),
        julia_project=SOLUTION_DIR / "julia",
    )

    recovered = list(cells.glob(f".{cell['cell_id']}.abandoned-*"))
    assert len(recovered) == 1
    assert (recovered[0] / "partial.log").read_text(encoding="utf-8") == (
        "keep for audit"
    )


def test_cell_artifact_records_required_diagnostics_and_rejects_mismatch():
    cell = _plan()["cells"][0]
    artifact = _complete(cell)

    convergence.validate_cell_artifact(artifact, expected_cell=cell)
    assert artifact["resources"]["wall_time_seconds"] == 1.25
    assert artifact["resources"]["peak_rss_bytes"] == 123456
    assert artifact["resources"]["phase_timings_seconds"][
        "context_and_evolution"
    ] == 0.9
    assert artifact["resources"]["thread_settings"] == {
        "julia_threads": 2,
        "blas_threads": 1,
        "blas_vendor": "test",
    }
    assert artifact["resources"]["actual_mpo_link_dimensions"] == [4, 7, 4]
    assert artifact["diagnostics"]["maximum_link_dimensions_by_bond"] == [4, 16, 8]
    assert artifact["solver_settings"]["krylov_expansion_dim"] == 0
    assert artifact["observables"]["n_d"] == 1.0
    assert artifact["tau_fractions"] == [0.0, 0.25, 0.5, 0.75, 1.0]
    assert set(artifact["provenance"]["source_sha256"]) == {
        "acceptance.py",
        "bath.py",
        "convergence.py",
        "convergence.schema.json",
        "model.json",
        "pyproject.toml",
        "uv.lock",
        "finite_bath_mps_runner.jl",
        "finite_bath_observables.jl",
        "finite_bath_purification.jl",
    }

    bad = copy.deepcopy(artifact)
    bad["solver_settings"]["krylov_expansion_dim"] = 32
    with pytest.raises(ValueError, match="krylov_expansion_dim|0 was expected"):
        convergence.validate_cell_artifact(bad, expected_cell=cell)


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda output: output.__setitem__("tau", []), "tau"),
        (lambda output: output["tau"].__setitem__(1, 0.123), "tau"),
        (lambda output: output["observables"].__setitem__("G_up", []), "G_up"),
        (
            lambda output: output["observables"]["G_down"].__setitem__(1, math.nan),
            "finite",
        ),
        (lambda output: output["observables"].__setitem__("n_d", 2.1), "n_d"),
        (
            lambda output: output["observables"].__setitem__(
                "double_occupancy", 0.6
            ),
            "double occupancy",
        ),
        (lambda output: output["observables"]["G_up"].__setitem__(1, 0.1), "G_up"),
        (
            lambda output: output["observables"]["G_down"].__setitem__(0, -0.25),
            "endpoint",
        ),
        (
            lambda output: output["observables"]["G_up"].__setitem__(-1, -0.25),
            "endpoint",
        ),
    ],
)
def test_completed_cell_rejects_invalid_observable_semantics(mutation, match):
    cell = _plan()["cells"][0]
    output = _solver_result(cell)
    mutation(output)

    with pytest.raises((TypeError, ValueError), match=match):
        convergence.make_cell_artifact(
            cell=cell,
            solver_output=output,
            wall_time_seconds=1.0,
            peak_rss_bytes=100,
            peak_rss_method="test",
        )


def test_pair_comparison_rejects_unequal_observable_vectors():
    cell = _plan()["cells"][0]
    left = _complete(cell)
    right = copy.deepcopy(left)
    right["observables"]["G_up"].pop()

    with pytest.raises(ValueError, match="length"):
        convergence._pair_delta(left, right)


@pytest.mark.parametrize(
    "field",
    ["runner_source_sha256", "project_toml_sha256", "bath_artifact_file_sha256"],
)
def test_completed_cell_rejects_solver_provenance_mismatch(field):
    cell = _plan()["cells"][0]
    output = _solver_result(cell)
    output["provenance"][field] = "f" * 64

    with pytest.raises(ValueError, match="provenance"):
        convergence.make_cell_artifact(
            cell=cell,
            solver_output=output,
            wall_time_seconds=1.0,
            peak_rss_bytes=100,
            peak_rss_method="test",
        )


@pytest.mark.parametrize(
    "mutation,match",
    [
        (
            lambda output: output["diagnostics"].__setitem__("thermal", {}),
            "thermal diagnostics",
        ),
        (
            lambda output: output["diagnostics"].__setitem__("green_up", []),
            "Green-branch diagnostics",
        ),
        (
            lambda output: output["diagnostics"]["thermal"].__setitem__(
                "krylov_all_converged", False
            ),
            "Krylov",
        ),
        (
            lambda output: output["diagnostics"]["thermal"].__setitem__(
                "krylov_max_error_estimate", 1.0
            ),
            "Krylov error",
        ),
        (
            lambda output: output["diagnostics"]["green_up"][1].__setitem__(
                "truncation_max_error", 1.0
            ),
            "truncation",
        ),
        (
            lambda output: output["diagnostics"].__setitem__(
                "maximum_link_dimensions_by_bond",
                [4, output["solver"]["settings"]["maxdim"], 8],
            ),
            "maxdim saturation",
        ),
        (
            lambda output: output["diagnostics"]["green_up"][1].__setitem__(
                "spin", "dn"
            ),
            "Green-branch identity",
        ),
        (
            lambda output: output["diagnostics"]["green_down"][1].__setitem__(
                "tau", -1.0
            ),
            "Green-branch identity",
        ),
    ],
)
def test_diagnostics_gate_fails_closed(mutation, match):
    cell = _plan()["cells"][0]
    output = _solver_result(cell)
    mutation(output)
    with pytest.raises(ValueError, match=match):
        convergence.make_cell_artifact(
            cell=cell,
            solver_output=output,
            wall_time_seconds=1.0,
            peak_rss_bytes=100,
            peak_rss_method="test",
        )


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux /proc assertion")
def test_linux_proc_peak_rss_parser_and_unsupported_fallback(tmp_path):
    process = tmp_path / "42"
    process.mkdir()
    (process / "status").write_text(
        "Name:\tjulia\nVmRSS:\t120 kB\nVmHWM:\t456 kB\n",
        encoding="utf-8",
    )
    assert convergence.read_linux_process_peak_rss(
        42, proc_root=tmp_path
    ) == 456 * 1024
    assert convergence.read_linux_process_peak_rss(
        99, proc_root=tmp_path
    ) is None
    assert convergence.process_rss_monitoring_method() == "linux_proc_status_vmhwm"


def test_process_rss_monitoring_is_null_on_unsupported_platform(monkeypatch):
    monkeypatch.setattr(convergence.platform, "system", lambda: "Darwin")
    assert convergence.process_rss_monitoring_method() is None


def test_local_subprocess_timeout_is_enforced(tmp_path):
    output = tmp_path / "result.json"
    with pytest.raises(subprocess.TimeoutExpired):
        convergence.invoke_julia_runner_monitored(
            [
                shutil.which("python3"),
                "-c",
                "import time; time.sleep(2)",
            ],
            output_path=output,
            timeout_seconds=0.05,
            max_rss_bytes=convergence.LOCAL_RSS_LIMIT_BYTES,
        )
    assert not output.exists()


def test_resources_are_hashed_bound_and_required_for_production(tmp_path):
    plan = _plan()
    resources = convergence.estimate_plan_resources(plan)
    convergence.validate_resources(resources, plan)
    assert resources["resource_sha256"] == convergence.resource_sha256(resources)
    assert resources["safety_factors"]["memory"] > 1
    assert resources["safety_factors"]["wall"] > 1

    with pytest.raises(ValueError, match="resources"):
        convergence.run_cell(
            plan,
            0,
            tmp_path,
            executor=lambda cell, _stage: _solver_result(cell),
            julia_project=SOLUTION_DIR / "julia",
        )
    with pytest.raises(ValueError, match="acknowledgment"):
        convergence.run_cell(
            plan,
            0,
            tmp_path,
            executor=lambda cell, _stage: _solver_result(cell),
            julia_project=SOLUTION_DIR / "julia",
            resources=resources,
        )


@pytest.mark.parametrize("execution_target", ["local", "cluster"])
def test_n48_cell_is_refused_without_validated_solver_capability(
    tmp_path, execution_target
):
    plan = _plan()
    resources = convergence.estimate_plan_resources(plan)
    index = next(
        index
        for index, cell in enumerate(plan["cells"])
        if cell["parameters"]["n_bath"] == 48
    )
    calls = []
    with pytest.raises(ValueError, match="solver capability"):
        convergence.run_cell(
            plan,
            index,
            tmp_path,
            executor=lambda cell, _stage: (
                calls.append(cell["cell_id"]),
                _solver_result(cell),
            )[1],
            julia_project=SOLUTION_DIR / "julia",
            resources=resources,
            resource_acknowledgment=resources["resource_sha256"],
            execution_target=execution_target,
        )
    assert calls == []


def test_accidental_full_cluster_array_never_launches_n48(tmp_path):
    plan = _plan()
    resources = convergence.estimate_plan_resources(plan)
    launched = []
    for index, cell in enumerate(plan["cells"]):
        run_root = tmp_path / str(index)
        if cell["parameters"]["n_bath"] == 48:
            with pytest.raises(ValueError, match="solver capability"):
                convergence.run_cell(
                    plan,
                    index,
                    run_root,
                    executor=lambda item, _stage: launched.append(
                        item["parameters"]["n_bath"]
                    )
                    or _solver_result(item),
                    julia_project=SOLUTION_DIR / "julia",
                    resources=resources,
                    resource_acknowledgment=resources["resource_sha256"],
                    execution_target="cluster",
                )
    assert 48 not in launched


def test_validate_plan_schema_first_and_binds_schema_digest(monkeypatch):
    plan = _plan()
    assert plan["execution_environment"]["source_sha256"][
        "convergence.schema.json"
    ] == convergence._sha256_file(SOLUTION_DIR / "convergence.schema.json")
    assert all(
        cell["provenance"]["source_sha256"]["convergence.schema.json"]
        == plan["execution_environment"]["source_sha256"][
            "convergence.schema.json"
        ]
        for cell in plan["cells"]
    )
    malformed = copy.deepcopy(plan)
    malformed["cells"][0]["solver_settings"]["unknown"] = True
    malformed["plan_sha256"] = convergence.plan_sha256(malformed)
    calls = []
    real_validate = convergence.validate_artifact_schema

    def tracked(value, definition):
        calls.append(definition)
        return real_validate(value, definition)

    monkeypatch.setattr(convergence, "validate_artifact_schema", tracked)
    with pytest.raises(ValueError, match="schema"):
        convergence.validate_plan(malformed)
    assert calls == ["convergencePlan"]


def test_schema_is_recursive_and_runtime_validation_rejects_nested_unknown():
    schema = json.loads(
        (SOLUTION_DIR / "convergence.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    plan = _plan()
    convergence.validate_artifact_schema(plan, "convergencePlan")
    malformed = copy.deepcopy(plan)
    malformed["cells"][0]["solver_settings"]["unknown"] = True
    with pytest.raises(ValueError, match="schema"):
        convergence.validate_artifact_schema(malformed, "convergencePlan")


def test_out_of_range_cli_index_reports_once_without_secondary_index_error(
    tmp_path, capsys
):
    plan = _plan(
        betas=[0.2],
        bath_sizes=[1],
        time_steps=[0.1],
        maxdims=[32],
        stage="pilot",
    )
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    exit_code = convergence.main(
        [
            "run-cell",
            "--plan",
            str(plan_path),
            "--run-directory",
            str(tmp_path / "run"),
            "--cell-index",
            "-1",
            "--julia-project",
            str(SOLUTION_DIR / "julia"),
        ]
    )
    output = capsys.readouterr().out
    assert exit_code == 1
    assert output.count("action=failed") == 1
    assert "out of range" in output


def _analysis_cells(nonmonotonic=False):
    plan = _plan(
        betas=[16.0],
        bath_sizes=[4, 6],
        time_steps=[0.2, 0.1, 0.05],
        maxdims=[128, 256, 512],
    )
    artifacts = []
    for cell in plan["cells"]:
        parameters = cell["parameters"]
        settings = cell["solver_settings"]
        bath_error = 2.0e-5 if parameters["n_bath"] == 4 else 0.0
        maxdim_error = {128: 2.0e-5, 256: 5.0e-6, 512: 0.0}[
            settings["maxdim"]
        ]
        if nonmonotonic:
            dt_error = {0.2: 1.0e-5, 0.1: 2.0e-6, 0.05: 8.0e-6}[
                settings["time_step"]
            ]
        else:
            dt_error = {0.2: 1.0e-5, 0.1: 2.0e-6, 0.05: 0.0}[
                settings["time_step"]
            ]
        artifacts.append(_complete(cell, bath_error + maxdim_error + dt_error))
    return plan, artifacts


def test_pairwise_analysis_controls_other_axes_and_passes_named_tolerances():
    plan, artifacts = _analysis_cells()
    report = convergence.analyze_cells(plan, artifacts)

    assert report["pair_counts"] == {"bath_size": 9, "time_step": 12, "maxdim": 12}
    assert all(pair["controlled"] for pairs in report["pairs"].values() for pair in pairs)
    assert set(report["axis_status"]) == {"bath_size", "time_step", "maxdim"}
    assert report["axis_status"]["time_step"]["nonmonotonic"] is False
    assert report["convergence_claim"] is False
    assert "three-level bath resolution policy not established" in report[
        "claim_blockers"
    ]


def test_analysis_rejects_plan_from_a_different_current_checkout(monkeypatch):
    plan, artifacts = _analysis_cells()
    monkeypatch.setattr(
        convergence,
        "_source_hashes",
        lambda _project: {"changed": "0" * 64},
    )

    with pytest.raises(ValueError, match="current checkout"):
        convergence.analyze_cells(plan, artifacts)


def test_nonmonotonic_timestep_blocks_convergence_claim():
    plan, artifacts = _analysis_cells(nonmonotonic=True)
    report = convergence.analyze_cells(plan, artifacts)

    assert report["axis_status"]["time_step"]["nonmonotonic"] is True
    assert report["axis_status"]["time_step"]["passed"] is False
    assert report["convergence_claim"] is False
    assert "non-monotonic" in report["claim_blockers"][0]


def _staged_analysis_cells(nonmonotonic_bath=False):
    plan = _plan()
    artifacts = []
    bath_error = (
        {12: 1.0e-5, 24: 0.0, 48: 8.0e-6}
        if nonmonotonic_bath
        else {12: 2.0e-5, 24: 5.0e-6, 48: 0.0}
    )
    for cell in plan["cells"]:
        settings = cell["solver_settings"]
        shift = bath_error[cell["parameters"]["n_bath"]]
        shift += {0.2: 2.0e-5, 0.1: 5.0e-6, 0.05: 0.0}[
            settings["time_step"]
        ]
        shift += {128: 2.0e-5, 256: 5.0e-6, 512: 0.0}[
            settings["maxdim"]
        ]
        artifacts.append(_complete(cell, shift))
    return plan, artifacts


def test_complete_synthetic_grid_cannot_claim_without_n48_solver_capability():
    plan, artifacts = _staged_analysis_cells()
    report = convergence.analyze_cells(plan, artifacts)

    assert report["pair_counts"] == {
        "bath_size": 4,
        "time_step": 4,
        "maxdim": 4,
    }
    for beta, status in report["bath_resolution"].items():
        assert status["bath_sizes"] == [12, 24, 48]
        assert status["nearest_energy_strictly_decreasing"] is True
        assert status["finest_nearest_energy_over_temperature"] <= 1.1
        assert status["passed"] is True
    assert report["convergence_claim"] is False
    assert any(
        "N_b=48 solver capability" in blocker
        for blocker in report["claim_blockers"]
    )
    assert "validated N_b=48 solver capability" in report["policy"]


def test_nonmonotonic_bath_trend_blocks_convergence_claim():
    plan, artifacts = _staged_analysis_cells(nonmonotonic_bath=True)
    report = convergence.analyze_cells(plan, artifacts)

    assert report["axis_status"]["bath_size"]["nonmonotonic"] is True
    assert report["convergence_claim"] is False
    assert any("non-monotonic bath" in item for item in report["claim_blockers"])


def test_incomplete_analysis_reports_available_calibration_without_claim():
    plan, artifacts = _staged_analysis_cells()
    available = [
        artifact
        for artifact in artifacts
        if artifact["parameters"]["n_bath"] in (12, 24)
    ]

    report = convergence.analyze_available_cells(plan, available)

    assert report["analysis_mode"] == "incomplete_calibration"
    assert report["convergence_claim"] is False
    assert report["available_cell_count"] == 12
    assert len(report["missing_cell_ids"]) == 2
    assert report["pair_counts"] == {
        "bath_size": 2,
        "time_step": 4,
        "maxdim": 4,
    }
    assert report["calibration_telemetry"] == {
        "observed_cell_count": 12,
        "total_wall_time_seconds": 15.0,
        "max_peak_rss_bytes": 123456,
        "peak_rss_unavailable_count": 0,
        "peak_rss_methods": ["test"],
    }
    assert any("N_b=48" in blocker for blocker in report["claim_blockers"])
    assert any("three-level bath" in blocker for blocker in report["claim_blockers"])
    assert any(
        "incomplete calibration" in blocker
        for blocker in report["claim_blockers"]
    )


def test_missing_cell_blocker_describes_actual_non_n48_cell():
    plan, artifacts = _staged_analysis_cells()
    missing_artifact = next(
        artifact
        for artifact in artifacts
        if artifact["parameters"]["n_bath"] == 12
    )
    available = [
        artifact
        for artifact in artifacts
        if artifact["cell_id"] != missing_artifact["cell_id"]
    ]

    report = convergence.analyze_available_cells(plan, available)

    matching = [
        blocker
        for blocker in report["claim_blockers"]
        if missing_artifact["cell_id"] in blocker
    ]
    assert len(matching) == 1
    assert "N_b=12" in matching[0]
    assert "missing N_b=48 cells" not in matching[0]


def test_cli_allow_incomplete_publishes_calibration_report(tmp_path):
    plan, artifacts = _staged_analysis_cells()
    plan_path = convergence.create_plan_run(tmp_path / "runs", plan)
    run_root = plan_path.parent
    for artifact in artifacts:
        if artifact["parameters"]["n_bath"] == 48:
            continue
        cell_root = run_root / "cells" / artifact["cell_id"]
        cell_root.mkdir(parents=True)
        for filename in ("bath.json", "mps-input.json", "mps-result.json"):
            payload = f"{artifact['cell_id']}:{filename}\n".encode()
            (cell_root / filename).write_bytes(payload)
            artifact["artifact_file_sha256"][filename] = convergence._sha256(
                payload
            )
        artifact["artifact_sha256"] = convergence._sha256(
            convergence._canonical_json(
                {
                    key: value
                    for key, value in artifact.items()
                    if key != "artifact_sha256"
                }
            )
        )
        (cell_root / "cell.json").write_text(
            json.dumps(artifact), encoding="utf-8"
        )
    output = tmp_path / "incomplete.json"

    status = convergence.main(
        [
            "analyze",
            "--plan",
            str(plan_path),
            "--run-directory",
            str(run_root),
            "--output",
            str(output),
            "--allow-incomplete",
        ]
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    assert status == 2
    assert report["analysis_mode"] == "incomplete_calibration"
    assert report["convergence_claim"] is False


def test_analysis_requires_complete_valid_cells():
    plan, artifacts = _analysis_cells()
    artifacts.pop()
    with pytest.raises(ValueError, match="missing"):
        convergence.analyze_cells(plan, artifacts)


def test_resource_estimates_are_bounded_explicit_and_cluster_directed():
    plan = _plan()
    estimate = convergence.estimate_plan_resources(plan)

    assert estimate["cell_count"] == 14
    assert estimate["model"]["memory_scaling"] == "O(L * W * maxdim^2)"
    assert estimate["model"]["work_scaling"] == "O(steps * L * W * maxdim^3)"
    assert estimate["recommendation"] == "cluster_array"
    assert estimate["max_estimated_peak_rss_bytes"] > 0
    assert estimate["max_estimated_wall_seconds"] > 600
    assert min(cell["estimated_wall_seconds"] for cell in estimate["cells"]) >= 30
    assert min(
        cell["estimated_peak_rss_bytes"] for cell in estimate["cells"]
    ) >= 512 * 1024**2
    assert estimate["local_limits"] == {
        "wall_seconds": 600,
        "peak_rss_bytes": 16 * 1024**3,
    }
    n48 = [
        cell
        for cell in estimate["cells"]
        if cell["n_bath"] == 48
    ]
    assert len(n48) == 2
    assert all(cell["requires_chain_mapping_optimization"] for cell in n48)
    assert all(cell["execution_permitted"] is False for cell in n48)
    assert estimate["direct_star_mpo_assessment"]["n_bath_48_feasible"] is False


def _julia_available():
    configured = os.environ.get("JULIA")
    return bool(
        (configured and Path(configured).is_file())
        or shutil.which("julia")
    )


@pytest.mark.skipif(
    os.environ.get("SKIP_CHALLENGE81_CONVERGENCE_PILOT") == "1"
    or not _julia_available(),
    reason="Julia unavailable or tiny pilot explicitly opted out",
)
def test_tiny_real_julia_tdvp_only_pilot(tmp_path):
    plan = _plan(
        betas=[0.2],
        bath_sizes=[1],
        time_steps=[0.1],
        maxdims=[32],
        tau_fractions=[0.0, 0.5, 1.0],
        stage="pilot",
    )

    result = convergence.run_cell(
        plan, 0, tmp_path, julia_project=SOLUTION_DIR / "julia"
    )
    cell = result["cell"]

    assert result["action"] == "completed"
    assert cell["solver_settings"]["krylov_expansion_dim"] == 0
    assert cell["diagnostics"]["expansion_policy"] == "tdvp_only"
    assert cell["diagnostics"]["maximum_link_dimensions_by_bond"]
    assert cell["resources"]["wall_time_seconds"] < 600
    if platform.system() == "Linux":
        assert cell["resources"]["peak_rss_bytes"] < 16 * 1024**3
        assert cell["resources"]["peak_rss_method"] == "linux_proc_status_vmhwm"
    else:
        assert cell["resources"]["peak_rss_bytes"] is None
        assert cell["resources"]["peak_rss_method"] is None
