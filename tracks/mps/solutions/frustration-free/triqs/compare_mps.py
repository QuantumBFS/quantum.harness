"""Compare MPS and CT-HYB without merging deterministic and Monte Carlo errors."""

from __future__ import annotations

import math
from pathlib import Path

from artifacts import canonical_json, sha256_bytes, strict_json_load


STUDENT_95_DF3 = 3.182446305284263
AXES = ("bath", "chain", "bond", "time_residual")


def load_mps_error_budget(path: Path) -> dict[str, object]:
    value = strict_json_load(path)
    if not isinstance(value, dict):
        raise ValueError("MPS error budget must be an object")
    _budget(value)
    return value


def load_validated_acceptance(path: Path, julia_project: Path) -> dict[str, object]:
    del julia_project
    value = strict_json_load(path)
    if (
        not isinstance(value, dict)
        or value.get("passed") is not True
        or float(value.get("global_max_error", math.inf)) > 1e-6
        or float(value.get("effective_threshold", math.inf)) > 1e-6
    ):
        raise ValueError("finite-bath MPS-ED acceptance gate failed")
    return value


def _budget(value):
    if not isinstance(value, dict):
        raise ValueError("MPS error budget must be an object")
    for axis in AXES:
        if axis not in value:
            raise ValueError(f"missing MPS error axis: {axis}")
        number = float(value[axis])
        if not math.isfinite(number) or number < 0:
            raise ValueError(f"invalid MPS error axis: {axis}")
    if set(value) != set(AXES):
        raise ValueError("MPS error budget has renamed or extra axes")
    return {axis: float(value[axis]) for axis in AXES}


def _gate(mps_value, cthyb_value, standard_error, components):
    difference = abs(float(mps_value) - float(cthyb_value))
    monte_carlo = STUDENT_95_DF3 * float(standard_error)
    envelope = sum(components.values()) + monte_carlo
    return {
        "mps_value": float(mps_value),
        "cthyb_value": float(cthyb_value),
        "absolute_difference": difference,
        "mps_error_components": components,
        "cthyb_standard_error": float(standard_error),
        "cthyb_student_component": monte_carlo,
        "envelope": envelope,
        "passed": difference <= envelope,
    }


def compare(mps_result, mps_budget, cthyb_summary, acceptance):
    components = _budget(mps_budget)
    if (
        acceptance.get("passed") is not True
        or float(acceptance.get("global_max_error", math.inf)) > 1e-6
        or float(acceptance.get("effective_threshold", math.inf)) > 1e-6
    ):
        raise ValueError("finite-bath acceptance prerequisite failed")
    for key in ("model", "reported_tau", "common_real_frequency_sha256"):
        if mps_result.get(key) != cthyb_summary.get(key):
            raise ValueError(f"MPS/CT-HYB identity mismatch: {key}")
    comparisons = {
        "n_d": _gate(
            mps_result["values"]["n_d"],
            cthyb_summary["values"]["n_d"],
            cthyb_summary["standard_errors"]["n_d"],
            components,
        )
    }
    for spin in ("G_up", "G_down"):
        comparisons[spin] = [
            _gate(mps, cthyb, se, components)
            for mps, cthyb, se in zip(
                mps_result["values"][spin],
                cthyb_summary["values"][spin],
                cthyb_summary["standard_errors"][spin],
                strict=True,
            )
        ]
    passed = all(
        value["passed"] if isinstance(value, dict) else all(point["passed"] for point in value)
        for value in comparisons.values()
    )
    payload = {
        "artifact_type": "mps_cthyb_comparison",
        "schema_version": 2,
        "status": "compatible" if passed else "incompatible",
        "comparisons": comparisons,
    }
    return {"payload": payload, "sha256": sha256_bytes(canonical_json(payload))}


def validate_comparison(artifact: object) -> None:
    if (
        not isinstance(artifact, dict)
        or set(artifact) != {"payload", "sha256"}
        or artifact["sha256"] != sha256_bytes(canonical_json(artifact["payload"]))
        or artifact["payload"].get("artifact_type") != "mps_cthyb_comparison"
        or artifact["payload"].get("schema_version") != 2
    ):
        raise ValueError("comparison artifact is malformed or hash-invalid")
