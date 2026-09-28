"""Strict builder for the isolated tiered production-v2 data program."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


BASE_MATRIX_SHA256 = (
    "9b6c60f982ac41da5b9ecd926ef30c3ab232ea9f82767e447bd52598037dffed"
)
BASE_MANIFEST_SHA256 = (
    "cfd39d2b8b67f8a812114c3d7a84daba2b12d2c6bf3bbe1433aa03eba837bd52"
)
BASE_RUNNER_SHA256 = (
    "8ddfa943bc6fe044b3537e9b69785c2b741b2d867fa1d83ed39159577f088c16"
)
BASE_BACKEND_SHA256 = (
    "de3fa5377cbfe415b4c0d5dc8368ff297f1ef47f61723ae4dae10a19a688ae94"
)

EXPECTED_NEW_IDS = {
    "response_local_pulse_pos",
    "response_local_pulse_neg",
    "equilibrium_m0",
}
EXPECTED_REUSE = {
    "amp_mu005_up": "amp_mu005_up__convergence__fine",
    "amp_mu005_down": "amp_mu005_down__convergence__fine",
}
EXPECTED_CURRENT_IDS = {
    "amp_mu002_up",
    "amp_mu002_down",
    "amp_mu005_up",
    "amp_mu005_down",
    "amp_mu010_up",
    "amp_mu010_down",
    "amp_mu020_up",
    "amp_mu020_down",
    "shape_double_wall",
    "background_p005_up",
    "response_local_pulse_pos",
    "response_local_pulse_neg",
    "equilibrium_m0",
}
EXPECTED_CZZ_IDS = {
    "amp_mu002_up",
    "amp_mu002_down",
    "amp_mu005_up",
    "amp_mu005_down",
    "amp_mu010_up",
    "amp_mu010_down",
}
EXPECTED_FCS_A = {
    "amp_mu002_up",
    "amp_mu002_down",
    "amp_mu005_up",
    "amp_mu005_down",
    "amp_mu010_up",
    "amp_mu010_down",
    "equilibrium_m0",
}
EXPECTED_FCS_B = {
    "amp_mu005_up",
    "amp_mu005_down",
    "equilibrium_m0",
}
EXPECTED_COUNTS = {
    "condition_count": 34,
    "logical_job_count": 68,
    "production_a_logical": 34,
    "production_a_execute": 32,
    "production_a_reuse": 2,
    "production_a_fcs_logical": 7,
    "production_a_fcs_execute": 5,
    "production_b_logical": 34,
    "production_b_fcs": 3,
}


def sha256_file(path: str | Path) -> str:
    """Return the hexadecimal SHA-256 digest of a file."""

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class ProductionAmendment:
    """Validated immutable description of the tiered production extension."""

    schema_version: int
    approved_at: str
    base_hashes: dict[str, str]
    new_conditions: tuple[dict[str, Any], ...]
    fcs_gamma: tuple[float, ...]
    current_condition_ids: frozenset[str]
    czz_condition_ids: frozenset[str]
    fcs_condition_ids_a: frozenset[str]
    fcs_condition_ids_b: frozenset[str]
    reuse: dict[str, str]
    frozen_counts: dict[str, int]
    sha256: str


def _exact_set(
    raw: Mapping[str, Any],
    key: str,
    expected: set[str],
    label: str,
) -> frozenset[str]:
    values = [str(value) for value in raw[key]]
    if len(values) != len(set(values)) or set(values) != expected:
        raise ValueError(f"{label} must equal the preregistered explicit set")
    return frozenset(values)


def load_production_amendment(path: str | Path) -> ProductionAmendment:
    """Load the approved amendment and reject every unregistered variation."""

    amendment_path = Path(path)
    raw = json.loads(amendment_path.read_text())
    if int(raw.get("schema_version", -1)) != 1:
        raise ValueError("Unsupported production amendment schema")

    base = {str(key): str(value) for key, value in raw["base"].items()}
    expected_base = {
        "matrix_sha256": BASE_MATRIX_SHA256,
        "manifest_sha256": BASE_MANIFEST_SHA256,
        "runner_sha256": BASE_RUNNER_SHA256,
        "backend_sha256": BASE_BACKEND_SHA256,
    }
    if base.get("manifest_sha256") != BASE_MANIFEST_SHA256:
        raise ValueError("base manifest hash differs from the approved value")
    if base != expected_base:
        raise ValueError("base source hashes differ from the approved values")

    conditions = tuple(dict(item) for item in raw["new_conditions"])
    condition_ids = [str(item.get("condition_id")) for item in conditions]
    if len(condition_ids) != len(set(condition_ids)):
        raise ValueError("new condition IDs must be unique")
    if set(condition_ids) != EXPECTED_NEW_IDS:
        raise ValueError("new condition IDs differ from the approved set")
    for condition in conditions:
        condition_id = str(condition["condition_id"])
        if str(condition["role"]) not in {
            "two_mode_response",
            "two_mode_equilibrium",
        }:
            raise ValueError(f"invalid role for {condition_id}")
        if str(condition["profile"]) not in {"gaussian", "uniform_zero"}:
            raise ValueError(f"invalid profile for {condition_id}")
        if float(condition["mu"]) <= 0 or float(condition["width"]) <= 0:
            raise ValueError(f"mu and width must be positive for {condition_id}")
        if int(condition["orientation"]) not in (-1, 1):
            raise ValueError(f"invalid orientation for {condition_id}")
        if abs(float(condition["j2"])) > 1e-15:
            raise ValueError(f"new condition {condition_id} must have J2=0")
        if str(condition["temperature"]) != "infinite":
            raise ValueError(f"new condition {condition_id} must be infinite-T")
    by_id = {str(item["condition_id"]): item for item in conditions}
    if by_id["equilibrium_m0"]["profile"] != "uniform_zero":
        raise ValueError("equilibrium_m0 must use uniform_zero")
    if abs(float(by_id["equilibrium_m0"]["background_m"])) > 1e-15:
        raise ValueError("equilibrium_m0 background must be zero")

    gamma = tuple(float(value) for value in raw["fcs_gamma"])
    if (
        len(gamma) != 7
        or len(set(gamma)) != len(gamma)
        or tuple(sorted(gamma)) != gamma
        or 0.0 not in gamma
        or any(abs(left + right) > 1e-14 for left, right in zip(gamma, reversed(gamma)))
    ):
        raise ValueError("FCS gamma grid must be sorted, unique, symmetric, and include zero")
    if gamma != (-0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6):
        raise ValueError("FCS gamma grid differs from the validated grid")

    policy = raw["observable_policy"]
    current_ids = _exact_set(
        policy,
        "current_condition_ids",
        EXPECTED_CURRENT_IDS,
        "current condition IDs",
    )
    czz_ids = _exact_set(
        policy, "czz_condition_ids", EXPECTED_CZZ_IDS, "czz condition IDs"
    )
    stage_a = raw["production_a"]
    stage_b = raw["production_b"]
    fcs_a = _exact_set(
        stage_a,
        "fcs_condition_ids",
        EXPECTED_FCS_A,
        "production-A FCS condition IDs",
    )
    fcs_b = _exact_set(
        stage_b,
        "fcs_condition_ids",
        EXPECTED_FCS_B,
        "production-B FCS condition IDs",
    )
    reuse = {
        str(key): str(value) for key, value in dict(stage_a["reuse"]).items()
    }
    if reuse != EXPECTED_REUSE:
        raise ValueError("reuse map differs from the preregistered map")
    counts = {
        str(key): int(value)
        for key, value in dict(raw["frozen_counts"]).items()
    }
    if counts != EXPECTED_COUNTS:
        raise ValueError("frozen production counts differ from the approved values")

    return ProductionAmendment(
        schema_version=1,
        approved_at=str(raw["approved_at"]),
        base_hashes=base,
        new_conditions=conditions,
        fcs_gamma=gamma,
        current_condition_ids=current_ids,
        czz_condition_ids=czz_ids,
        fcs_condition_ids_a=fcs_a,
        fcs_condition_ids_b=fcs_b,
        reuse=reuse,
        frozen_counts=counts,
        sha256=sha256_file(amendment_path),
    )


def _observables(
    condition_id: str,
    stage: str,
    amendment: ProductionAmendment,
) -> list[str]:
    values = ["magnetization"]
    if condition_id in amendment.current_condition_ids:
        values.append("local_spin_current")
    if condition_id in amendment.czz_condition_ids:
        values.append("czz")
    fcs_ids = (
        amendment.fcs_condition_ids_a
        if stage == "production_a"
        else amendment.fcs_condition_ids_b
    )
    if condition_id in fcs_ids:
        values.append("fcs_logZ")
    return values


def _summary(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    a = [job for job in jobs if job["stage"] == "production_a"]
    b = [job for job in jobs if job["stage"] == "production_b"]
    return {
        "logical_job_count": len(jobs),
        "production_a_logical": len(a),
        "production_a_execute": sum(
            job["execution_mode"] == "execute" for job in a
        ),
        "production_a_reuse": sum(
            job["execution_mode"] == "reuse" for job in a
        ),
        "production_a_fcs_logical": sum(
            "fcs_logZ" in job["observables"] for job in a
        ),
        "production_a_fcs_execute": sum(
            "fcs_logZ" in job["observables"]
            and job["execution_mode"] == "execute"
            for job in a
        ),
        "production_b_logical": len(b),
        "production_b_fcs": sum(
            "fcs_logZ" in job["observables"] for job in b
        ),
        "submission_performed": False,
    }


def build_production_manifest_v2(
    *,
    base_matrix_path: str | Path,
    base_manifest_path: str | Path,
    amendment_path: str | Path,
    data_root: str | Path,
) -> dict[str, Any]:
    """Build 34 A and 34 B logical rows without mutating the base program."""

    matrix_path = Path(base_matrix_path)
    manifest_path = Path(base_manifest_path)
    matrix_hash_before = sha256_file(matrix_path)
    manifest_hash_before = sha256_file(manifest_path)
    amendment = load_production_amendment(amendment_path)
    if matrix_hash_before != amendment.base_hashes["matrix_sha256"]:
        raise ValueError("base matrix hash does not match the amendment")
    if manifest_hash_before != amendment.base_hashes["manifest_sha256"]:
        raise ValueError("base manifest hash does not match the amendment")

    matrix = json.loads(matrix_path.read_text())
    base_manifest = json.loads(manifest_path.read_text())
    base_conditions = [dict(item) for item in matrix["conditions"]]
    if len(base_conditions) != 31:
        raise ValueError("base matrix must contain exactly 31 conditions")
    conditions = base_conditions + [
        dict(item) for item in amendment.new_conditions
    ]
    condition_ids = [str(item["condition_id"]) for item in conditions]
    if len(condition_ids) != len(set(condition_ids)) != 0:
        raise ValueError("combined production condition IDs are not unique")

    fine_levels = [
        dict(level)
        for level in matrix["convergence_levels"]
        if str(level.get("level")) == "fine"
    ]
    if len(fine_levels) != 1:
        raise ValueError("base matrix must contain one fine numerical level")
    fine = fine_levels[0]
    root = Path(data_root).resolve()
    jobs: list[dict[str, Any]] = []
    for stage, t_max in (("production_a", 200.0), ("production_b", 400.0)):
        for condition in conditions:
            condition = dict(condition)
            condition.setdefault("parameters", {})
            condition_id = str(condition["condition_id"])
            execution_mode = (
                "reuse"
                if stage == "production_a" and condition_id in amendment.reuse
                else "execute"
            )
            observables = _observables(condition_id, stage, amendment)
            job_id = f"{condition_id}__{stage}__v2"
            jobs.append(
                {
                    "job_id": job_id,
                    "condition_id": condition_id,
                    "stage": stage,
                    "resolution_level": "selected_after_convergence",
                    "blinded": stage == "production_b",
                    "t_max": t_max,
                    "output_path": str(
                        root / "raw" / stage / f"{job_id}.npz"
                    ),
                    "condition": condition,
                    "numerics": dict(fine),
                    "observables": observables,
                    "fcs_gamma": (
                        list(amendment.fcs_gamma)
                        if "fcs_logZ" in observables
                        else None
                    ),
                    "execution_mode": execution_mode,
                    "reuse_from_job_id": (
                        amendment.reuse[condition_id]
                        if execution_mode == "reuse"
                        else None
                    ),
                    "depends_on": (
                        [f"{condition_id}__production_a__v2"]
                        if stage == "production_b"
                        else []
                    ),
                }
            )

    summary = _summary(jobs)
    if {
        key: summary[key] for key in EXPECTED_COUNTS if key in summary
    } != {
        key: value
        for key, value in EXPECTED_COUNTS.items()
        if key in summary
    }:
        raise AssertionError("constructed production counts violate the amendment")
    if len(conditions) != amendment.frozen_counts["condition_count"]:
        raise AssertionError("constructed condition count violates the amendment")
    if sha256_file(matrix_path) != matrix_hash_before:
        raise RuntimeError("base matrix changed during production-v2 build")
    if sha256_file(manifest_path) != manifest_hash_before:
        raise RuntimeError("base manifest changed during production-v2 build")

    return {
        "schema_version": 2,
        "created_from_approved_amendment": amendment.approved_at,
        "base": {
            "matrix_path": str(matrix_path.resolve()),
            "matrix_sha256": matrix_hash_before,
            "manifest_path": str(manifest_path.resolve()),
            "manifest_sha256": manifest_hash_before,
            "base_job_count": int(base_manifest["job_count"]),
            "runner_sha256": amendment.base_hashes["runner_sha256"],
            "backend_sha256": amendment.base_hashes["backend_sha256"],
        },
        "amendment": {
            "path": str(Path(amendment_path).resolve()),
            "sha256": amendment.sha256,
        },
        "gates": {
            "production_a": [
                "convergence_audit_accepted",
                "production_v2_source_preflight_pass",
                "J2_compute_node_validation_pass",
            ],
            "production_b": [
                "registered_one_time_unblinding",
                "production_a_validation_selection_frozen",
            ],
        },
        "summary": summary,
        "job_count": len(jobs),
        "jobs": jobs,
    }
