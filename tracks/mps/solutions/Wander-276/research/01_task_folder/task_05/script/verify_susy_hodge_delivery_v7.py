#!/usr/bin/env python3
"""Fail-closed scientific and provenance audit for SUSY/Hodge v7."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analyze_susy_hodge_geometric_eth_v7 import (
    N14_INFERENCE_JSON,
    N14_PREDICTION_JSON,
    N14_PREDICTION_NPZ,
    N14_PREDICTION_SEAL,
    N14_SAFE_JSON,
    N14_UNSEALED_JSON,
    select_frozen_branch,
)
from generate_susy_hodge_controls_v7 import OUTPUT_JSON as CONTROLS_JSON
from merge_susy_hodge_pilot_v7 import (
    OUTPUT_JSON as PILOT_BANK_JSON,
    OUTPUT_NPZ as PILOT_BANK_NPZ,
)
from make_susy_hodge_figure_v7 import (
    FIGURE_PDF,
    FIGURE_PNG,
    MANIFEST_JSON as FIGURE_MANIFEST,
    REPORT_MD,
)
from run_susy_hodge_geometric_eth_v7 import _atomic_json, sha256


SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT_JSON = SCRIPT_ROOT / "output" / "susy_hodge_delivery_audit_v7.json"
FORBIDDEN_SAFE_TOKENS = ("r4", "four_point", "connected")


def _load(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _passed(payload: dict[str, Any] | None) -> bool:
    return bool(
        payload
        and payload.get("version") == "v7"
        and payload.get("passed")
        and all(payload.get("checks", {}).values())
    )


def _matches_hash(path: Path, expected: object) -> bool:
    try:
        return isinstance(expected, str) and sha256(path) == expected
    except (FileNotFoundError, OSError):
        return False


def _seal_hash(source: Path, seal: Path) -> str | None:
    try:
        fields = Path(seal).read_text(encoding="utf-8").strip().split()
    except (FileNotFoundError, OSError):
        return None
    if len(fields) != 2 or fields[1] != Path(source).name:
        return None
    return fields[0] if _matches_hash(source, fields[0]) else None


def _safe_serialization(path: Path) -> bool:
    try:
        serialized = Path(path).read_text(encoding="utf-8").lower()
    except (FileNotFoundError, OSError):
        return False
    return not any(token in serialized for token in FORBIDDEN_SAFE_TOKENS)


def _timestamp_order(
    prediction: dict[str, Any] | None,
    unsealed: dict[str, Any] | None,
) -> bool:
    try:
        prediction_time = datetime.fromisoformat(str(prediction["generated_utc"]))
        unsealed_time = datetime.fromisoformat(str(unsealed["unsealed_utc"]))
    except (KeyError, TypeError, ValueError):
        return False
    return unsealed_time > prediction_time


def _exact_grid(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    expected = {
        (N, sector, panel)
        for N in (8, 10, 12)
        for sector in ("central", "adjacent")
        for panel in ("sparse", "isotropic")
    }
    try:
        observed = {
            (int(item["N"]), str(item["sector"]), str(item["panel_kind"]))
            for item in payload["groups"]
        }
    except (KeyError, TypeError, ValueError):
        return False
    return observed == expected


def _primary_pair(payload: dict[str, Any] | None, key: str) -> bool:
    if not payload:
        return False
    try:
        observed = {
            (int(item["N"]), str(item["sector"]), str(item["panel_kind"]))
            for item in payload[key]
        }
    except (KeyError, TypeError, ValueError):
        return False
    return observed == {(14, "central", "sparse"), (14, "adjacent", "sparse")}


def _recomputed_branch(inference: dict[str, Any] | None) -> str | None:
    if not inference:
        return None
    try:
        records = inference["primary_pair"]
        collapsed = all(bool(item["collapsed_covered"]) for item in records)
        hodge = all(bool(item["hodge_covered"]) for item in records)
        structured = bool(inference.get("structured_indistinguishable", False))
        resolved = bool(
            inference.get("checks", {}).get("registered_branch_resolved", False)
        )
    except (KeyError, TypeError):
        return None
    return select_frozen_branch(collapsed, hodge, structured, resolved)


def _figure_hashes(
    manifest: dict[str, Any] | None,
    *,
    pilot_json: Path,
    inference_json: Path,
    figure_pdf: Path,
    figure_png: Path,
    report_md: Path,
) -> bool:
    if not manifest:
        return False
    inputs = manifest.get("inputs", {})
    outputs = manifest.get("outputs", {})
    return all(
        (
            _matches_hash(
                pilot_json, inputs.get(Path(pilot_json).name)
            ),
            _matches_hash(
                inference_json, inputs.get(Path(inference_json).name)
            ),
            _matches_hash(
                figure_pdf, outputs.get(Path(figure_pdf).name)
            ),
            _matches_hash(
                figure_png, outputs.get(Path(figure_png).name)
            ),
            _matches_hash(
                report_md, outputs.get(Path(report_md).name)
            ),
        )
    )


def verify_delivery(
    *,
    pilot_json: Path = PILOT_BANK_JSON,
    pilot_npz: Path = PILOT_BANK_NPZ,
    safe_json: Path = N14_SAFE_JSON,
    prediction_json: Path = N14_PREDICTION_JSON,
    prediction_npz: Path = N14_PREDICTION_NPZ,
    prediction_seal: Path = N14_PREDICTION_SEAL,
    unsealed_json: Path = N14_UNSEALED_JSON,
    inference_json: Path = N14_INFERENCE_JSON,
    controls_json: Path = CONTROLS_JSON,
    figure_manifest: Path = FIGURE_MANIFEST,
    figure_pdf: Path = FIGURE_PDF,
    figure_png: Path = FIGURE_PNG,
    report_md: Path = REPORT_MD,
    output_json: Path = OUTPUT_JSON,
) -> dict[str, Any]:
    """Audit every compact artifact and return checks instead of trusting prose."""

    paths = {
        "pilot_json": Path(pilot_json),
        "pilot_npz": Path(pilot_npz),
        "safe_json": Path(safe_json),
        "prediction_json": Path(prediction_json),
        "prediction_npz": Path(prediction_npz),
        "prediction_seal": Path(prediction_seal),
        "unsealed_json": Path(unsealed_json),
        "inference_json": Path(inference_json),
        "controls_json": Path(controls_json),
        "figure_manifest": Path(figure_manifest),
        "figure_pdf": Path(figure_pdf),
        "figure_png": Path(figure_png),
        "report_md": Path(report_md),
    }
    pilot = _load(paths["pilot_json"])
    safe = _load(paths["safe_json"])
    prediction = _load(paths["prediction_json"])
    unsealed = _load(paths["unsealed_json"])
    inference = _load(paths["inference_json"])
    controls = _load(paths["controls_json"])
    figure = _load(paths["figure_manifest"])
    seal_hash = _seal_hash(paths["prediction_json"], paths["prediction_seal"])
    recomputed_branch = _recomputed_branch(inference)
    try:
        report_text = paths["report_md"].read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        report_text = ""
    checks = {
        "all_required_files_exist": all(path.is_file() for path in paths.values()),
        "pilot_passed": _passed(pilot),
        "complete_pilot_grid": _exact_grid(pilot),
        "pilot_array_hash": bool(pilot)
        and _matches_hash(paths["pilot_npz"], pilot.get("arrays_sha256")),
        "safe_covariates_passed": bool(safe) and bool(safe.get("passed")),
        "safe_covariates_have_no_outcome_leakage": _safe_serialization(
            paths["safe_json"]
        ),
        "prediction_passed": _passed(prediction),
        "complete_prediction_primary_pair": _primary_pair(prediction, "primary_pair"),
        "prediction_array_hash": bool(prediction)
        and _matches_hash(
            paths["prediction_npz"], prediction.get("prediction_arrays_sha256")
        ),
        "prediction_safe_covariate_hash": bool(prediction)
        and _matches_hash(paths["safe_json"], prediction.get("safe_covariates_sha256")),
        "prediction_has_no_outcome_leakage": _safe_serialization(
            paths["prediction_json"]
        ),
        "valid_prediction_seal": seal_hash is not None,
        "unsealed_passed": _passed(unsealed),
        "prediction_precedes_unseal": _timestamp_order(prediction, unsealed),
        "unsealed_references_prediction": bool(unsealed)
        and seal_hash is not None
        and unsealed.get("prediction_sha256") == seal_hash,
        "inference_passed": _passed(inference),
        "complete_inference_primary_pair": _primary_pair(inference, "primary_pair"),
        "inference_references_prediction": bool(inference)
        and seal_hash is not None
        and inference.get("prediction_sha256") == seal_hash,
        "selected_branch_recomputed": bool(inference)
        and recomputed_branch == inference.get("selected_branch"),
        "analytic_controls_passed": _passed(controls),
        "curvature_atom_control": bool(controls)
        and bool(controls.get("checks", {}).get("N6_curvature_atoms")),
        "one_sided_control": bool(controls)
        and bool(controls.get("checks", {}).get("one_sided_exact_regression")),
        "figure_manifest_passed": _passed(figure),
        "figure_and_report_hashes": _figure_hashes(
            figure,
            pilot_json=paths["pilot_json"],
            inference_json=paths["inference_json"],
            figure_pdf=paths["figure_pdf"],
            figure_png=paths["figure_png"],
            report_md=paths["report_md"],
        ),
        "figure_branch_matches_inference": bool(figure and inference)
        and figure.get("selected_branch") == inference.get("selected_branch"),
        "report_has_claim_boundary_and_sources": bool(inference)
        and "## Established" in report_text
        and "## Not established" in report_text
        and "](https://" in report_text
        and str(inference.get("selected_branch")) in report_text,
    }
    payload = {
        "version": "v7",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "selected_branch": inference.get("selected_branch") if inference else None,
        "recomputed_branch": recomputed_branch,
        "prediction_sha256": seal_hash,
        "artifact_hashes": {
            key: sha256(path) for key, path in paths.items() if path.is_file()
        },
        "checks": checks,
        "passed": all(checks.values()),
    }
    _atomic_json(output_json, payload)
    return payload


def main() -> None:
    payload = verify_delivery()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
