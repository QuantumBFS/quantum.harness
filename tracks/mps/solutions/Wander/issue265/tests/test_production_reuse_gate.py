from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from src.production_reuse_gate import (
    resolve_dataset_path,
    validate_reuse,
)
from src.research_dataset import (
    ResearchDataset,
    file_sha256,
    save_research_dataset,
)
from src.tenpy_research_backend import canonical_job_sha256


ROOT = Path(__file__).resolve().parents[1]
BASE_MANIFEST = json.loads(
    (ROOT / "results_research_program" / "manifest.json").read_text()
)
V2 = json.loads(
    (ROOT / "results_research_program" / "production_manifest_v2.json").read_text()
)


def _fixture(tmp_path: Path) -> dict[str, object]:
    target = next(
        job
        for job in V2["jobs"]
        if job["job_id"] == "amp_mu005_up__production_a__v2"
    )
    source = next(
        job
        for job in BASE_MANIFEST["jobs"]
        if job["job_id"] == "amp_mu005_up__convergence__fine"
    )
    effective = {
        "L": 512,
        "dt": 0.0125,
        "chi_max": 1024,
        "truncation_cutoff": 1e-11,
        "t_max": 200.0,
        "output_dt": 0.2,
        "steps_per_output": 16,
        "output_count": 1000,
    }
    x = np.linspace(-255.5, 255.5, 8)
    t = np.linspace(0.0, 200.0, 1001)
    u = np.zeros((t.size, x.size))
    metadata = {
        "schema_version": 1,
        "hamiltonian": "test",
        "delta": 1.0,
        "J": 1.0,
        "J2": 0.0,
        "temperature": "infinite",
        "mu": 0.05,
        "orientation": 1,
        "profile": "tanh",
        "width": 2.0,
        "background_m": 0.0,
        "L": 512,
        "boundary_condition": "open",
        "algorithm": "test",
        "time_step": 0.0125,
        "chi_max": 1024,
        "truncation_cutoff": 1e-11,
        "discarded_weight_max": 0.0,
        "source_commit": "test",
        "raw_sha256": canonical_job_sha256(source, effective),
        "preprocessing": "none",
        "job_id": source["job_id"],
    }
    path = tmp_path / "fine.npz"
    save_research_dataset(
        ResearchDataset(
            condition_id=target["condition_id"],
            x=x,
            t=t,
            u=u,
            m=u.copy(),
            current=np.zeros((t.size, x.size - 1)),
            czz=u.copy(),
            fcs_gamma=np.asarray([-0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6]),
            fcs_logZ=np.zeros((t.size, 7), dtype=complex),
            metadata=metadata,
        ),
        path,
    )
    summary = {
        "status": "complete",
        "job_id": source["job_id"],
        "effective_numerics": effective,
    }
    validation = {
        "records": [
            {
                "job_id": source["job_id"],
                "status": "valid",
                "file_sha256": file_sha256(path),
            }
        ]
    }
    return {
        "target": target,
        "path": path,
        "summary": summary,
        "validation": validation,
        "audit": {"status": "accepted"},
    }


def test_reuse_accepts_only_exact_validated_fine_dataset(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    attestation = validate_reuse(
        fixture["target"],
        base_manifest=BASE_MANIFEST,
        dataset_path=fixture["path"],
        run_summary=fixture["summary"],
        dataset_validation=fixture["validation"],
        convergence_audit=fixture["audit"],
    )
    assert attestation.status == "accepted"
    resolved = resolve_dataset_path(
        fixture["target"],
        reuse_attestations={
            fixture["target"]["job_id"]: attestation,
        },
    )
    assert resolved == Path(fixture["path"]).resolve()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda f: f.update(audit={"status": "pending"}), "not accepted"),
        (
            lambda f: f["summary"].update(job_id="wrong"),
            "source job ID mismatch",
        ),
        (
            lambda f: f["summary"]["effective_numerics"].update(L=384),
            "effective numerics mismatch",
        ),
        (
            lambda f: f.update(validation={"records": []}),
            "dataset validation",
        ),
    ],
)
def test_reuse_fails_closed(
    tmp_path: Path,
    mutation,
    message: str,
) -> None:
    fixture = _fixture(tmp_path)
    mutation(fixture)
    with pytest.raises(ValueError, match=message):
        validate_reuse(
            fixture["target"],
            base_manifest=BASE_MANIFEST,
            dataset_path=fixture["path"],
            run_summary=fixture["summary"],
            dataset_validation=fixture["validation"],
            convergence_audit=fixture["audit"],
        )


def test_execute_row_resolves_own_output() -> None:
    execute = next(
        job for job in V2["jobs"] if job["execution_mode"] == "execute"
    )
    assert resolve_dataset_path(execute, reuse_attestations={}) == Path(
        execute["output_path"]
    )
