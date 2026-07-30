from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

import pytest

from hg3d_stage6_fixture import write_passing_stage6_pilot
from spinglass3d.production import (
    CellManifest,
    build_production_run_spec,
    cell_spec_sha256,
    run_cell,
)
from spinglass3d.workflow import freeze_production_candidate
from vmcrg_ref.artifacts import canonical_json_bytes, sha256_file


def _write_candidate(
    root: Path,
    *,
    j_counts: dict[str, int] | None = None,
    accelerator: str = "profile-accelerator:1",
) -> Path:
    pilot_path = write_passing_stage6_pilot(
        root,
        j_counts=j_counts,
        accelerator=accelerator,
    )
    candidate_path = root / "production-candidate.json"
    freeze_production_candidate(pilot_path, candidate_path)
    return candidate_path


def _write_run_spec(path: Path, spec: dict[str, object]) -> str:
    path.write_bytes(canonical_json_bytes(spec))
    return sha256_file(path)


def _write_checkpoint(staging: Path, cell: dict[str, object], step: int) -> Path:
    checkpoint = staging / "checkpoints" / f"step-{step:08d}"
    checkpoint.mkdir(parents=True)
    state = checkpoint / "state.json"
    state.write_text(json.dumps({"completed_steps": step}) + "\n", encoding="ascii")
    manifest = {
        "schema_version": 1,
        "cell_id": cell["cell_id"],
        "cell_spec_sha256": cell_spec_sha256(cell),
        "completed_steps": step,
        "hashes": {"state.json": sha256_file(state)},
    }
    (checkpoint / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    return checkpoint


def _write_terminal_staging(
    staging: Path,
    cell: dict[str, object],
    *,
    classification: str,
    completed_j_ids: list[str] | None = None,
    failed_j_ids: list[str] | None = None,
    unequilibrated_j_ids: set[str] | None = None,
) -> None:
    staging.mkdir(parents=True)
    summary = staging / "summary.json"
    diagnostics = staging / "diagnostics.json"
    checkpoint = staging / "checkpoint.json"
    planned = [record["j_id"] for record in cell["params"]["j_records"]]
    completed = planned if completed_j_ids is None else completed_j_ids
    failed = [value for value in planned if value not in completed]
    if failed_j_ids is not None:
        failed = failed_j_ids
    unequilibrated = unequilibrated_j_ids or set()
    summary.write_bytes(
        canonical_json_bytes(
            {
                "schema_version": 1,
                "cell_id": cell["cell_id"],
                "length": cell["params"]["length"],
                "j_ids": completed,
                "observables_by_j": {
                    j_id: {"xi_over_l": 1.25} for j_id in completed
                },
            }
        )
    )
    diagnostics.write_bytes(
        canonical_json_bytes(
            {
                "schema_version": 1,
                "cell_id": cell["cell_id"],
                "j_records": [
                    {
                        "j_id": j_id,
                        "completed": j_id in completed,
                        "equilibrated": j_id in completed and j_id not in unequilibrated,
                        "failed_gates": (
                            []
                            if j_id in completed and j_id not in unequilibrated
                            else ["equilibration"]
                        ),
                    }
                    for j_id in planned
                ],
                "failed_j_ids": failed,
            }
        )
    )
    checkpoint.write_text('{"completed_steps": 16}\n', encoding="ascii")
    hashes = {
        path.name: sha256_file(path)
        for path in (summary, diagnostics, checkpoint)
    }
    manifest = {
        "schema_version": 1,
        "cell_id": cell["cell_id"],
        "cell_spec_sha256": cell_spec_sha256(cell),
        "classification": classification,
        "artifacts": {
            "summary": "summary.json",
            "diagnostics": "diagnostics.json",
            "checkpoint": "checkpoint.json",
        },
        "hashes": hashes,
        "checkpoint": "checkpoint.json",
    }
    (staging / "manifest.json").write_bytes(canonical_json_bytes(manifest))


def _cell_case(
    tmp_path: Path,
    run_id: str,
    *,
    j_counts: dict[str, int] | None = None,
) -> tuple[Path, str, dict[str, object], Path]:
    candidate = _write_candidate(
        tmp_path / "candidate",
        j_counts=j_counts or {"45": 1},
    )
    spec = build_production_run_spec(candidate, run_id)
    run_spec = tmp_path / "run-spec.json"
    approved = _write_run_spec(run_spec, spec)
    return run_spec, approved, spec["cells"][0], tmp_path / "execution"


def _run_cell(
    run_spec: Path,
    approved: str,
    cell: dict[str, object],
    execution_root: Path,
) -> CellManifest:
    return run_cell(
        run_spec,
        cell["cell_id"],
        approved_run_spec_sha256=approved,
        execution_root=execution_root,
    )


def _staging_path(execution_root: Path, cell: dict[str, object]) -> Path:
    return (
        execution_root
        / "results"
        / "hard_goal"
        / "cell-lifecycle"
        / "staging"
        / cell["cell_id"]
    )


def test_temperature_is_not_a_cell_axis_and_every_cell_has_a_full_ladder(
    tmp_path: Path,
) -> None:
    spec = build_production_run_spec(_write_candidate(tmp_path), "hg-prod")
    assert "temperature" not in spec["axes"]
    assert len(spec["cells"]) <= 200
    assert all(len(cell["key"]) == 5 for cell in spec["cells"])
    assert all(len(cell["params"]["temperatures"]) == 4 for cell in spec["cells"])
    assert {cell["params"]["evidence_arm"] for cell in spec["cells"]} == {
        "unbiased_fss",
        "vmcrg_training",
        "neural_validation",
    }
    assert all(
        "temperature" not in cell["params"]
        for cell in spec["cells"]
    )


def test_disorder_and_chain_seeds_are_deterministic_and_arm_separated(
    tmp_path: Path,
) -> None:
    candidate = _write_candidate(tmp_path)
    left = build_production_run_spec(candidate, "left-run")
    right = build_production_run_spec(candidate, "right-run")
    left_seed_records = [
        (
            cell["key"][:4],
            cell["key"][4],
            [record["j_seed"] for record in cell["params"]["j_records"]],
            [record["chain_seeds"] for record in cell["params"]["j_records"]],
        )
        for cell in left["cells"]
    ]
    right_seed_records = [
        (
            cell["key"][:4],
            cell["key"][4],
            [record["j_seed"] for record in cell["params"]["j_records"]],
            [record["chain_seeds"] for record in cell["params"]["j_records"]],
        )
        for cell in right["cells"]
    ]
    assert left_seed_records == right_seed_records

    first_by_arm = {
        cell["params"]["evidence_arm"]: cell["params"]["j_records"][0]
        for cell in left["cells"]
        if cell["params"]["length"] == 12
        and cell["params"]["disorder_batch"] == 0
    }
    assert len({record["j_seed"] for record in first_by_arm.values()}) == 1
    chain_streams = [
        set(record["chain_seeds"])
        for record in first_by_arm.values()
    ]
    assert all(
        left_stream.isdisjoint(right_stream)
        for index, left_stream in enumerate(chain_streams)
        for right_stream in chain_streams[index + 1 :]
    )


def test_candidate_must_be_passed_and_hash_bound_to_its_pilot(tmp_path: Path) -> None:
    candidate = _write_candidate(tmp_path)
    payload = json.loads(candidate.read_text(encoding="ascii"))
    payload["classification"] = "SCIENTIFIC_NEGATIVE"
    candidate.write_bytes(canonical_json_bytes(payload))
    with pytest.raises(ValueError, match="classification.*PASS"):
        build_production_run_spec(candidate, "failed")

    candidate = _write_candidate(tmp_path / "tampered")
    pilot = Path(json.loads(candidate.read_text(encoding="ascii"))["pilot_manifest"])
    pilot.write_text("{}\n", encoding="ascii")
    with pytest.raises(ValueError, match="pilot manifest|Stage 6"):
        build_production_run_spec(candidate, "tampered")


def test_stage7_source_inventory_binds_cli_physics_and_checkpoint_code(
    tmp_path: Path,
) -> None:
    spec = build_production_run_spec(_write_candidate(tmp_path), "source-bound")
    assert set(spec["provenance"]["source_sha256"]) >= {
        "jobs/hard_goal_array.slurm",
        "scripts/hard_goal.py",
        "src/spinglass3d/backend.py",
        "src/spinglass3d/equilibration.py",
        "src/spinglass3d/jax_backend.py",
        "src/spinglass3d/model.py",
        "src/spinglass3d/production.py",
        "src/vmcrg_ref/artifacts.py",
    }


def test_run_cell_rejects_noncanonical_run_spec_even_with_its_current_hash(
    tmp_path: Path,
) -> None:
    candidate = _write_candidate(tmp_path / "candidate", j_counts={"45": 1})
    spec = build_production_run_spec(candidate, "canonical-run")
    spec["cells"][0]["params"]["temperatures"][0] = 1.999
    run_spec = tmp_path / "run-spec.json"
    approved = _write_run_spec(run_spec, spec)
    with pytest.raises(ValueError, match="canonical|candidate-derived"):
        run_cell(
            run_spec,
            spec["cells"][0]["cell_id"],
            approved_run_spec_sha256=approved,
            execution_root=tmp_path,
        )


def test_array_limit_200_is_fail_closed(tmp_path: Path) -> None:
    counts = {str(3 * (index + 1)): 1 for index in range(67)}
    candidate = _write_candidate(tmp_path, j_counts=counts)
    with pytest.raises(ValueError, match="array limit 200"):
        build_production_run_spec(candidate, "oversized")


def test_run_cell_resumes_latest_complete_checkpoint_then_promotes_immutably(
    tmp_path: Path,
) -> None:
    run_spec, approved, cell, execution_root = _cell_case(
        tmp_path,
        "cell-lifecycle",
    )
    staging = _staging_path(execution_root, cell)

    ready = _run_cell(run_spec, approved, cell, execution_root)
    assert isinstance(ready, CellManifest)
    assert ready.classification == "READY"
    assert ready.terminal is False

    checkpoint = _write_checkpoint(staging, cell, 4)
    resume = _run_cell(run_spec, approved, cell, execution_root)
    assert resume.classification == "RESUME_REQUIRED"
    assert resume.resume_checkpoint == str(checkpoint)
    assert resume.completed_steps == 4

    shutil.rmtree(staging)
    _write_terminal_staging(staging, cell, classification="PASS")
    promoted = _run_cell(run_spec, approved, cell, execution_root)
    assert promoted.classification == "PASS"
    assert promoted.terminal is True
    output = execution_root / cell["params"]["output"]
    assert output.is_dir()
    assert not staging.exists()
    receipt = (
        execution_root
        / "results/hard_goal/cell-lifecycle/receipts"
        / f"{cell['cell_id']}.terminal.json"
    )
    assert receipt.is_file()

    repeated = _run_cell(run_spec, approved, cell, execution_root)
    assert repeated == promoted
    (output / "summary.json").write_text("tampered\n", encoding="ascii")
    with pytest.raises(ValueError, match="hash mismatch"):
        _run_cell(run_spec, approved, cell, execution_root)


def test_terminal_failure_is_promoted_once_and_never_automatically_rerun(
    tmp_path: Path,
) -> None:
    run_spec, approved, cell, execution_root = _cell_case(tmp_path, "failed-cell")
    staging = (
        execution_root
        / "results/hard_goal/failed-cell/staging"
        / cell["cell_id"]
    )
    _write_terminal_staging(staging, cell, classification="CORRECTNESS_FAILURE")
    failed = _run_cell(run_spec, approved, cell, execution_root)
    assert failed.classification == "CORRECTNESS_FAILURE"
    assert failed.terminal is True
    assert _run_cell(run_spec, approved, cell, execution_root) == failed


def test_run_cell_rejects_an_output_namespace_outside_the_run_directory(
    tmp_path: Path,
) -> None:
    candidate = _write_candidate(tmp_path / "candidate", j_counts={"45": 1})
    spec = build_production_run_spec(candidate, "escaped-cell")
    spec["cells"][0]["params"]["output"] = str(tmp_path / "outside")
    run_spec = tmp_path / "escaped-run-spec.json"
    approved = _write_run_spec(run_spec, spec)
    with pytest.raises(ValueError, match="canonical|candidate-derived|output namespace"):
        run_cell(
            run_spec,
            spec["cells"][0]["cell_id"],
            approved_run_spec_sha256=approved,
            execution_root=tmp_path,
        )


def test_terminal_receipt_rejects_self_consistent_manifest_reclassification(
    tmp_path: Path,
) -> None:
    run_spec, approved, cell, execution_root = _cell_case(tmp_path, "receipt-terminal")
    staging = (
        execution_root
        / "results/hard_goal/receipt-terminal/staging"
        / cell["cell_id"]
    )
    _write_terminal_staging(staging, cell, classification="CORRECTNESS_FAILURE")
    failed = _run_cell(run_spec, approved, cell, execution_root)
    manifest_path = Path(failed.output) / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="ascii"))
    payload["classification"] = "PASS"
    manifest_path.write_bytes(canonical_json_bytes(payload))
    with pytest.raises(ValueError, match="receipt|anchor|manifest hash"):
        _run_cell(run_spec, approved, cell, execution_root)


def test_checkpoint_receipt_rejects_self_consistent_completed_step_rewrite(
    tmp_path: Path,
) -> None:
    run_spec, approved, cell, execution_root = _cell_case(tmp_path, "receipt-checkpoint")
    staging = (
        execution_root
        / "results/hard_goal/receipt-checkpoint/staging"
        / cell["cell_id"]
    )
    checkpoint = _write_checkpoint(staging, cell, 4)
    first = _run_cell(run_spec, approved, cell, execution_root)
    assert first.completed_steps == 4
    state = checkpoint / "state.json"
    state.write_text('{"completed_steps": 40}\n', encoding="ascii")
    manifest_path = checkpoint / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="ascii"))
    payload["completed_steps"] = 40
    payload["hashes"]["state.json"] = sha256_file(state)
    manifest_path.write_bytes(canonical_json_bytes(payload))
    with pytest.raises(ValueError, match="receipt|anchor|manifest hash"):
        _run_cell(run_spec, approved, cell, execution_root)


@pytest.mark.parametrize(
    "defect",
    ("completion", "equilibration", "failed_ids", "actual_data"),
)
def test_pass_recomputes_per_j_m7_gates(tmp_path: Path, defect: str) -> None:
    run_spec, approved, cell, execution_root = _cell_case(
        tmp_path,
        "m7-gates",
        j_counts={"45": 128},
    )
    staging = (
        execution_root
        / "results/hard_goal/m7-gates/staging"
        / cell["cell_id"]
    )
    planned = [record["j_id"] for record in cell["params"]["j_records"]]
    completed = planned if defect not in {"completion", "failed_ids"} else planned[:1]
    failed = None if defect != "failed_ids" else []
    unequilibrated = {planned[0]} if defect == "equilibration" else set()
    _write_terminal_staging(
        staging,
        cell,
        classification="PASS",
        completed_j_ids=completed,
        failed_j_ids=failed,
        unequilibrated_j_ids=unequilibrated,
    )
    if defect == "actual_data":
        summary = staging / "summary.json"
        payload = json.loads(summary.read_text(encoding="ascii"))
        payload["observables_by_j"].pop(planned[0])
        summary.write_bytes(canonical_json_bytes(payload))
        manifest = json.loads((staging / "manifest.json").read_text(encoding="ascii"))
        manifest["hashes"]["summary.json"] = sha256_file(summary)
        (staging / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    with pytest.raises(ValueError, match="completion|equilibr|failed J|actual|summary"):
        _run_cell(run_spec, approved, cell, execution_root)


def test_run_cell_rejects_symlinked_staging_artifact_and_checkpoint(
    tmp_path: Path,
) -> None:
    for defect in ("staging", "artifact", "checkpoint"):
        case = tmp_path / defect
        run_spec, approved, cell, execution_root = _cell_case(case, f"symlink-{defect}")
        staging = (
            execution_root
            / "results/hard_goal"
            / f"symlink-{defect}"
            / "staging"
            / cell["cell_id"]
        )
        external = case / "external"
        if defect == "staging":
            _write_terminal_staging(external, cell, classification="PASS")
            staging.parent.mkdir(parents=True)
            staging.symlink_to(external, target_is_directory=True)
        elif defect == "artifact":
            _write_terminal_staging(staging, cell, classification="PASS")
            outside = case / "outside-summary.json"
            shutil.copy2(staging / "summary.json", outside)
            (staging / "summary.json").unlink()
            (staging / "summary.json").symlink_to(outside)
        else:
            checkpoint = _write_checkpoint(external, cell, 4)
            staging.mkdir(parents=True)
            checkpoint_root = staging / "checkpoints"
            checkpoint_root.mkdir()
            (checkpoint_root / checkpoint.name).symlink_to(
                checkpoint,
                target_is_directory=True,
            )
        with pytest.raises(ValueError, match="symlink"):
            _run_cell(run_spec, approved, cell, execution_root)


def test_run_cell_rejects_symlinked_run_spec_and_candidate(tmp_path: Path) -> None:
    candidate = _write_candidate(tmp_path / "candidate", j_counts={"45": 1})
    candidate_link = tmp_path / "candidate-link.json"
    candidate_link.symlink_to(candidate)
    with pytest.raises(ValueError, match="symlink"):
        build_production_run_spec(candidate_link, "candidate-link")

    spec = build_production_run_spec(candidate, "run-spec-link")
    real_spec = tmp_path / "real-run-spec.json"
    approved = _write_run_spec(real_spec, spec)
    run_spec_link = tmp_path / "run-spec-link.json"
    run_spec_link.symlink_to(real_spec)
    with pytest.raises(ValueError, match="symlink"):
        run_cell(
            run_spec_link,
            spec["cells"][0]["cell_id"],
            approved_run_spec_sha256=approved,
            execution_root=tmp_path,
        )
