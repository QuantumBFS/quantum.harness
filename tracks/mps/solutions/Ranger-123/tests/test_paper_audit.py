from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from floquet_if_manybody.paper_extension import audit_paper_results


def _evidence() -> list[dict[str, Any]]:
    common = {
        "coarse_fingerprint": "a" * 64,
        "refined_fingerprint": "b" * 64,
        "state_residual": 1e-3,
        "correlation_residual": 2e-3,
        "heat_residual": 3e-3,
        "passed": True,
        "coarse_bond_dimension": 10,
        "refined_bond_dimension": 12,
        "coarse_phase_samples": 3,
        "refined_phase_samples": 3,
    }
    return [
        {
            **common,
            "parameter": "epsrel",
            "coarse_value": 3e-7,
            "refined_value": 1e-7,
            "coarse_steps_per_period": 60,
            "refined_steps_per_period": 60,
            "coarse_tolerance": 3e-7,
            "refined_tolerance": 1e-7,
        },
        {
            **common,
            "parameter": "epsrel",
            "coarse_value": 3e-7,
            "refined_value": 1e-7,
            "coarse_steps_per_period": 90,
            "refined_steps_per_period": 90,
            "coarse_tolerance": 3e-7,
            "refined_tolerance": 1e-7,
        },
        {
            **common,
            "parameter": "steps_per_period",
            "coarse_value": 60,
            "refined_value": 90,
            "coarse_steps_per_period": 60,
            "refined_steps_per_period": 90,
            "coarse_tolerance": 1e-7,
            "refined_tolerance": 1e-7,
        },
        {
            **common,
            "parameter": "phase_samples",
            "coarse_value": 3,
            "refined_value": 15,
            "coarse_steps_per_period": 90,
            "refined_steps_per_period": 90,
            "coarse_tolerance": 1e-7,
            "refined_tolerance": 1e-7,
            "refined_phase_samples": 15,
        },
    ]


def _diagnostics() -> dict[str, float]:
    return {
        "fixed_point_residual": 1e-5,
        "trace_error": 1e-5,
        "hermiticity_error": 1e-5,
        "connected_tail_amplitude": 1e-3,
        "minimum_density_eigenvalue": 0.0,
    }


def _write_manifests(directory: Path) -> None:
    n3_points = [
        {
            "sector": sector,
            "model": {"j": j},
            "adaptive_status": "converged",
            "adaptive_converged": True,
            "diagnostics": _diagnostics(),
            "evidence": _evidence(),
        }
        for sector in ("even", "odd")
        for j in (0.25, 0.5, 1.0)
    ]
    error_points = [
        {
            "alpha": alpha,
            "drive_ratio": ratio,
            "status": "converged",
            "metrics": {
                "trace_distance": 0.1,
                "correlation": 0.2,
                "heat": 0.3,
            },
            "convergence_evidence": _evidence(),
        }
        for alpha in (0.025, 0.05, 0.1)
        for ratio in (0.75, 1.0, 1.25)
    ]
    model_points = [
        {
            "variant": variant,
            "adaptive_status": "converged",
            "adaptive_converged": True,
            "diagnostics": _diagnostics(),
            "evidence": _evidence(),
        }
        for variant in ("bounded", "bounded_ct", "kac", "kac_ct")
    ]
    payloads = {
        "n3_heat_manifest.json": {
            "exact_backend": "uniform_tempo",
            "converged": True,
            "points": n3_points,
            "odd_cross_j_relative_max_difference": 0.0,
        },
        "error_map_manifest.json": {
            "exact_backend": "uniform_tempo",
            "converged": True,
            "points": error_points,
        },
        "model_comparison_manifest.json": {
            "exact_backend": "uniform_tempo",
            "complete": True,
            "locally_complete": True,
            "converged": True,
            "points": model_points,
        },
    }
    for name, payload in payloads.items():
        (directory / name).write_text(json.dumps(payload), encoding="utf-8")


def test_paper_audit_requires_nested_convergence_and_all_points(
    tmp_path: Path,
) -> None:
    _write_manifests(tmp_path)
    passed, failures = audit_paper_results(tmp_path)
    assert passed
    assert failures == []

    path = tmp_path / "n3_heat_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["points"][0]["evidence"] = payload["points"][0]["evidence"][1:]
    path.write_text(json.dumps(payload), encoding="utf-8")
    passed, failures = audit_paper_results(tmp_path)
    assert not passed
    assert any("both timestep grids" in failure for failure in failures)


def test_paper_audit_accepts_explicit_kac_timestep_resource_ceiling(
    tmp_path: Path,
) -> None:
    _write_manifests(tmp_path)
    path = tmp_path / "model_comparison_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["converged"] = False
    for point in payload["points"]:
        if not point["variant"].startswith("kac_"):
            continue
        point["adaptive_status"] = "resource_ceiling"
        point["adaptive_converged"] = False
        point["failed_parameter"] = "steps_per_period"
        point["evidence"] = [
            item for item in point["evidence"] if item["parameter"] == "epsrel"
        ][:1]
    path.write_text(json.dumps(payload), encoding="utf-8")
    passed, failures = audit_paper_results(tmp_path)
    assert passed
    assert failures == []
