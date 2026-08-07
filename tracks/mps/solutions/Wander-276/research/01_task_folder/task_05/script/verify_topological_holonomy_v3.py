#!/usr/bin/env python3
"""Fail-closed audit for fixed-Chern Wilson-holonomy artifacts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from run_topological_holonomy_v3 import (
    MESH_ALIAS_AUDIT_JSON,
    MESH_ALIAS_AUDIT_NPZ,
    OUTPUT_JSON,
    OUTPUT_NPZ,
    REGISTERED_CONVERGENCE_MESH,
    REGISTERED_CUE_SAMPLES,
    REGISTERED_G,
    REGISTERED_GENERATOR_SEEDS,
    REGISTERED_PRIMARY_MESH,
    REGISTERED_SIZES,
    SCRIPT_ROOT,
    select_topology_branch,
)


OUTPUT_ROOT = SCRIPT_ROOT / "output"
FIGURE_MANIFEST = OUTPUT_ROOT / "figure_manifest_v3.json"
FIGURE_PDF = OUTPUT_ROOT / "figure_7_topological_holonomy_v3.pdf"
FIGURE_PNG = OUTPUT_ROOT / "figure_7_topological_holonomy_v3.png"
AUDIT_JSON = OUTPUT_ROOT / "topological_holonomy_delivery_audit_v3.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_topology_payload(
    payload: dict[str, Any],
) -> dict[str, bool]:
    """Recompute the registered topology gates from serialized metrics."""

    configuration = payload["configuration"]
    sizes = payload["sizes"]
    observed_sizes = [
        (size["N"], size["n_flux"], size["rank"]) for size in sizes
    ]
    expected_chern = {3: 6, 4: 10}
    checks = {
        "registered_sizes": observed_sizes == list(REGISTERED_SIZES),
        "registered_meshes": (
            configuration["primary_mesh"] == REGISTERED_PRIMARY_MESH
            and configuration["convergence_mesh"]
            == REGISTERED_CONVERGENCE_MESH
        ),
        "registered_g_grid": (
            configuration["g_values"] == list(REGISTERED_G)
        ),
        "registered_generator_seeds": (
            configuration["generator_seeds"]
            == list(REGISTERED_GENERATOR_SEEDS)
        ),
        "cue_reference_count": (
            configuration["cue_samples"] == REGISTERED_CUE_SAMPLES
        ),
        "runner_checks": all(payload["checks"].values()),
        "branch_recomputed": (
            payload["result_branch"] == select_topology_branch(payload)
        ),
        "supported_branch": (
            payload["result_branch"] == "fixed_chern_deformed_holonomy"
        ),
        "chern_fixed": all(
            abs(size["base_chern_integer"] - expected_chern[size["N"]])
            < 1e-12
            and max(size["primary_chern_range"])
            - min(size["primary_chern_range"])
            < 1e-8
            and max(size["convergence_endpoint_chern_range"])
            - min(size["convergence_endpoint_chern_range"])
            < 1e-8
            for size in sizes
        ),
        "mesh_agreement": all(
            abs(
                size["base_chern_primary"]
                - size["base_chern_convergence"]
            )
            < 1e-8
            for size in sizes
        ),
        "determinant_trace_agreement": all(
            size["maximum_determinant_trace_difference"] < 1e-8
            for size in sizes
        ),
        "positive_gap_branch_overlap": all(
            size["minimum_external_gap"] > 0.0
            and size["minimum_branch_margin"] > 0.0
            and size["minimum_overlap_singular_value"] > 5e-2
            for size in sizes
        ),
        "exact_isospectral_construction": all(
            size["maximum_energy_spectrum_error"] < 1e-13
            and size["maximum_gap_error"] < 1e-13
            and size["isospectrality_mode"]
            == (
                "exact_coordinate_identity_under_periodic_ambient_"
                "conjugation"
            )
            for size in sizes
        ),
        "gauge_invariance": (
            payload["random_gauge_errors"]["chern_error"] < 1e-9
            and payload["random_gauge_errors"]["wilson_phase_error"]
            < 1e-8
        ),
        "deformed_but_non_cue": all(
            size["holonomy_change_significant"]
            and not size["cue_compatible_at_largest_g"]
            for size in sizes
        ),
    }
    if not all(checks.values()):
        raise AssertionError(f"topology payload audit failed: {checks}")
    return checks


def _array_checks(payload: dict[str, Any]) -> dict[str, bool]:
    configuration = payload["configuration"]
    seeds = len(configuration["generator_seeds"])
    g_count = len(configuration["g_values"])
    checks: dict[str, bool] = {}
    with np.load(OUTPUT_NPZ, allow_pickle=False) as arrays:
        checks["result_npz_hash"] = (
            payload["npz_sha256"] == _sha256(OUTPUT_NPZ)
        )
        for index, size in enumerate(payload["sizes"]):
            rank = size["rank"]
            primary_mesh = size["primary_mesh"]
            convergence_mesh = size["convergence_mesh"]
            checks[f"size_{index}_seed_shapes"] = (
                arrays[f"size_{index}_gap_mean"].shape
                == (seeds, g_count)
                and arrays[f"size_{index}_form_mean"].shape
                == (seeds, g_count, rank)
            )
            checks[f"size_{index}_loop_shapes"] = (
                arrays[f"size_{index}_gap_loops"].shape
                == (seeds, g_count, 2 * primary_mesh)
                and arrays[f"size_{index}_form_loops"].shape
                == (seeds, g_count, 2 * primary_mesh, rank)
                and arrays[f"size_{index}_endpoint_gap_loops"].shape
                == (seeds, 2 * convergence_mesh)
            )
            checks[f"size_{index}_commuting_control"] = (
                arrays[f"size_{index}_commuting_gap"].shape
                == (g_count,)
                and arrays[f"size_{index}_commuting_form"].shape
                == (g_count, rank)
            )
            checks[f"size_{index}_cue_count"] = (
                arrays[f"size_{index}_cue_gap"].shape[0]
                == REGISTERED_CUE_SAMPLES
                and arrays[f"size_{index}_cue_form"].shape
                == (REGISTERED_CUE_SAMPLES, rank)
            )
    return checks


def run_audit() -> dict[str, Any]:
    payload = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
    checks = audit_topology_payload(payload)
    checks.update(_array_checks(payload))
    alias = json.loads(MESH_ALIAS_AUDIT_JSON.read_text(encoding="utf-8"))
    checks.update(
        {
            "alias_artifacts_present": (
                MESH_ALIAS_AUDIT_JSON.exists()
                and MESH_ALIAS_AUDIT_NPZ.exists()
            ),
            "alias_failure_retained": (
                alias["result_branch"] == "topology_mesh_unresolved"
                and alias["checks"]["mesh_chern_integer"] is False
                and alias["checks"]["branch_margin"] is False
                and min(alias["sizes"][1]["primary_chern_range"]) < 9.0
            ),
            "alias_hashes": (
                payload["mesh_alias_audit"]["json_sha256"]
                == _sha256(MESH_ALIAS_AUDIT_JSON)
                and payload["mesh_alias_audit"]["npz_sha256"]
                == _sha256(MESH_ALIAS_AUDIT_NPZ)
            ),
        }
    )
    for relative, expected_hash in payload["checkpoint_hashes"].items():
        checks[f"checkpoint:{relative}"] = (
            _sha256(SCRIPT_ROOT / relative) == expected_hash
        )
    manifest = json.loads(FIGURE_MANIFEST.read_text(encoding="utf-8"))
    figure = manifest["figure_7_topological_holonomy_v3"]
    checks.update(
        {
            "figure_source_json_hash": (
                figure["source_json_sha256"] == _sha256(OUTPUT_JSON)
            ),
            "figure_source_npz_hash": (
                figure["source_npz_sha256"] == _sha256(OUTPUT_NPZ)
            ),
            "figure_pdf_hash": (
                figure["pdf_sha256"] == _sha256(FIGURE_PDF)
            ),
            "figure_png_hash": (
                figure["png_sha256"] == _sha256(FIGURE_PNG)
            ),
        }
    )
    result = {
        "version": "v3",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "passed": all(checks.values()),
        "checks": checks,
        "result_branch": payload["result_branch"],
        "registered_sizes": [
            [size["N"], size["n_flux"], size["rank"]]
            for size in payload["sizes"]
        ],
        "registered_meshes": [
            configuration_mesh
            for configuration_mesh in (
                payload["configuration"]["primary_mesh"],
                payload["configuration"]["convergence_mesh"],
            )
        ],
        "result_sha256": _sha256(OUTPUT_JSON),
        "arrays_sha256": _sha256(OUTPUT_NPZ),
        "alias_audit_sha256": _sha256(MESH_ALIAS_AUDIT_JSON),
        "figure": {
            "pdf": str(FIGURE_PDF.relative_to(SCRIPT_ROOT)),
            "pdf_sha256": _sha256(FIGURE_PDF),
            "png": str(FIGURE_PNG.relative_to(SCRIPT_ROOT)),
            "png_sha256": _sha256(FIGURE_PNG),
        },
    }
    if not result["passed"]:
        raise RuntimeError(f"topology delivery audit failed: {checks}")
    temporary = AUDIT_JSON.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(AUDIT_JSON)
    return result


def main() -> None:
    result = run_audit()
    print(json.dumps(
        {
            "passed": result["passed"],
            "checks": result["checks"],
            "result_branch": result["result_branch"],
        },
        indent=2,
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
