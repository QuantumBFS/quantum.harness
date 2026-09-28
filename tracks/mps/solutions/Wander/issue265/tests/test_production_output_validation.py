from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.production_output_validation import validate_production_output
from src.research_dataset import ResearchDataset, save_research_dataset
from src.tenpy_research_backend import (
    canonical_job_sha256,
    output_times,
    resolve_numerics,
    site_coordinates,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads(
    (
        ROOT
        / "results_research_program"
        / "production_manifest_v2.json"
    ).read_text()
)


def _job(*, fcs: bool = True) -> dict:
    return next(
        dict(job)
        for job in MANIFEST["jobs"]
        if job["stage"] == "production_a"
        and job["execution_mode"] == "execute"
        and ("fcs_logZ" in job["observables"]) is fcs
    )


def _write_complete_output(
    tmp_path: Path,
    *,
    job: dict,
) -> Path:
    output = tmp_path / f"{job['job_id']}.npz"
    numerics = resolve_numerics(job)
    if job.get("fcs_gamma") is not None:
        numerics["fcs_gamma"] = [
            float(value) for value in job["fcs_gamma"]
        ]
    t = output_times(numerics)
    x = site_coordinates(numerics["L"])
    m = np.zeros((t.size, x.size))
    observables = list(job["observables"])
    gamma = (
        np.asarray(job["fcs_gamma"], dtype=float)
        if "fcs_logZ" in observables
        else None
    )
    checkpoint = output.with_suffix(output.suffix + ".checkpoint.h5")
    checkpoint.write_bytes(b"checkpoint")
    condition = job["condition"]
    job_hash = canonical_job_sha256(job, numerics)
    dataset = ResearchDataset(
        condition_id=job["condition_id"],
        x=x,
        t=t,
        u=m,
        m=m,
        current=(
            np.zeros((t.size, x.size - 1))
            if "local_spin_current" in observables
            else None
        ),
        czz=(
            np.zeros_like(m) if "czz" in observables else None
        ),
        fcs_gamma=gamma,
        fcs_logZ=(
            np.zeros((t.size, gamma.size), dtype=complex)
            if gamma is not None
            else None
        ),
        metadata={
            "schema_version": 1,
            "hamiltonian": "fixture",
            "delta": condition["delta"],
            "J": 1.0,
            "J2": condition["j2"],
            "temperature": condition["temperature"],
            "mu": condition["mu"],
            "orientation": condition["orientation"],
            "profile": condition["profile"],
            "width": condition["width"],
            "background_m": condition["background_m"],
            "L": numerics["L"],
            "boundary_condition": "open",
            "algorithm": "fixture",
            "time_step": numerics["dt"],
            "chi_max": numerics["chi_max"],
            "truncation_cutoff": numerics["truncation_cutoff"],
            "discarded_weight_max": 0.0,
            "source_commit": "fixture",
            "raw_sha256": job_hash,
            "preprocessing": "none",
            "job_id": job["job_id"],
            "stage": "production_a",
            "smoke_test": False,
            "requested_observables": observables,
            "produced_observables": observables,
            "omitted_observables": [],
            "output_dt": numerics["output_dt"],
            "maximum_chi_observed": 1,
            "discarded_weight_cumulative": 0.0,
            "maximum_total_magnetization_drift": 0.0,
            "checkpoint_path": str(checkpoint),
        },
    )
    save_research_dataset(dataset, output)
    output.with_suffix(".run.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "output": str(output.resolve()),
                "job_id": job["job_id"],
                "smoke": False,
                "effective_numerics": numerics,
                "produced_observables": observables,
                "omitted_observables": [],
                "maximum_total_magnetization_drift": 0.0,
                "maximum_chi_observed": 1,
                "discarded_weight_cumulative": 0.0,
                "fcs_branch_count": (
                    3 if "fcs_logZ" in observables else 0
                ),
                "checkpoint": str(checkpoint),
            }
        )
    )
    return output


def test_complete_output_requires_exact_registered_evidence(
    tmp_path: Path,
) -> None:
    job = _job(fcs=True)
    output = _write_complete_output(tmp_path, job=job)
    report = validate_production_output(job, output)
    assert report["status"] == "valid"
    assert report["errors"] == []
    assert report["dataset_sha256"]
    assert report["run_summary_sha256"]
    assert report["diagnostics"]["time_points"] == 1001
    assert report["diagnostics"]["fcs_conjugacy_max_abs"] == 0.0


def test_missing_registered_observable_is_rejected(
    tmp_path: Path,
) -> None:
    job = _job(fcs=True)
    output = _write_complete_output(tmp_path, job=job)
    with np.load(output, allow_pickle=False) as raw:
        arrays = {
            key: np.asarray(raw[key])
            for key in raw.files
            if key != "current"
        }
    np.savez_compressed(output, **arrays)
    report = validate_production_output(job, output)
    assert report["status"] == "invalid"
    assert "observable_presence_mismatch:local_spin_current" in report["errors"]


def test_wrong_job_hash_and_conservation_drift_are_rejected(
    tmp_path: Path,
) -> None:
    job = _job(fcs=False)
    output = _write_complete_output(tmp_path, job=job)
    with np.load(output, allow_pickle=False) as raw:
        arrays = {key: np.asarray(raw[key]) for key in raw.files}
    metadata = json.loads(str(arrays["metadata_json"].item()))
    metadata["raw_sha256"] = "0" * 64
    arrays["metadata_json"] = np.asarray(json.dumps(metadata))
    arrays["m"] = np.asarray(arrays["m"])
    arrays["m"][-1, 0] = 1e-6
    np.savez_compressed(output, **arrays)
    report = validate_production_output(job, output)
    assert report["status"] == "invalid"
    assert "canonical_job_sha256_mismatch" in report["errors"]
    assert "magnetization_conservation_failed" in report["errors"]


def test_nonempty_checkpoint_is_part_of_completion(
    tmp_path: Path,
) -> None:
    job = _job(fcs=False)
    output = _write_complete_output(tmp_path, job=job)
    output.with_suffix(output.suffix + ".checkpoint.h5").unlink()
    report = validate_production_output(job, output)
    assert report["status"] == "invalid"
    assert "checkpoint_missing_or_empty" in report["errors"]
