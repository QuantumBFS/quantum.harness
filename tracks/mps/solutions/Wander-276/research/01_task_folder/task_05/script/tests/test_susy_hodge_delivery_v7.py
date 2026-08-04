"""Fail-closed delivery and corruption tests for SUSY/Hodge v7."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from verify_susy_hodge_delivery_v7 import verify_delivery


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _synthetic_delivery(tmp_path: Path) -> dict[str, Path]:
    now = datetime.now(timezone.utc)
    pilot_groups = [
        {
            "N": N,
            "sector": sector,
            "panel_kind": panel,
            "collapsed_covered": False,
            "hodge_covered": False,
        }
        for N in (8, 10, 12)
        for sector in ("central", "adjacent")
        for panel in ("sparse", "isotropic")
    ]
    pilot = tmp_path / "pilot.json"
    pilot_npz = tmp_path / "pilot.npz"
    np.savez_compressed(pilot_npz, values=np.arange(3.0))
    _write_json(
        pilot,
        {
            "version": "v7",
            "groups": pilot_groups,
            "arrays_sha256": _hash(pilot_npz),
            "checks": {"complete": True},
            "passed": True,
        },
    )
    safe = tmp_path / "safe.json"
    _write_json(safe, {"version": "v7", "records": [], "passed": True})
    prediction_npz = tmp_path / "prediction.npz"
    np.savez_compressed(prediction_npz, central=np.arange(4.0))
    primary_prediction = [
        {
            "N": 14,
            "sector": sector,
            "panel_kind": "sparse",
            "realizations": 2,
            "collapsed_interval": [0.10, 0.11, 0.12],
            "hodge_interval": [0.13, 0.14, 0.15],
        }
        for sector in ("central", "adjacent")
    ]
    prediction = tmp_path / "prediction.json"
    _write_json(
        prediction,
        {
            "version": "v7",
            "generated_utc": now.isoformat(),
            "prediction_arrays_file": prediction_npz.name,
            "prediction_arrays_sha256": _hash(prediction_npz),
            "safe_covariates_sha256": _hash(safe),
            "primary_pair": primary_prediction,
            "checks": {"complete": True, "no_outcome_leakage": True},
            "passed": True,
        },
    )
    seal = tmp_path / "prediction.sha256"
    seal.write_text(f"{_hash(prediction)}  {prediction.name}\n", encoding="utf-8")
    unsealed = tmp_path / "unsealed.json"
    _write_json(
        unsealed,
        {
            "version": "v7",
            "prediction_sha256": _hash(prediction),
            "unsealed_utc": (now + timedelta(seconds=1)).isoformat(),
            "checks": {"complete": True},
            "passed": True,
        },
    )
    primary_inference = [
        {
            "N": 14,
            "sector": sector,
            "panel_kind": "sparse",
            "collapsed_covered": False,
            "hodge_covered": False,
            "robust_outside_both": True,
        }
        for sector in ("central", "adjacent")
    ]
    inference = tmp_path / "inference.json"
    _write_json(
        inference,
        {
            "version": "v7",
            "prediction_sha256": _hash(prediction),
            "selected_branch": "cohomological_non_gaussian_class",
            "primary_pair": primary_inference,
            "structured_indistinguishable": False,
            "checks": {"registered_branch_resolved": True},
            "passed": True,
        },
    )
    controls = tmp_path / "controls.json"
    _write_json(
        controls,
        {
            "version": "v7",
            "checks": {
                "N6_curvature_atoms": True,
                "one_sided_exact_regression": True,
            },
            "passed": True,
        },
    )
    pdf = tmp_path / "figure.pdf"
    png = tmp_path / "figure.png"
    report = tmp_path / "report.md"
    pdf.write_bytes(b"%PDF-1.4\nsynthetic\n")
    png.write_bytes(b"synthetic-png")
    report.write_text(
        "## Established\ncohomological_non_gaussian_class\n"
        "## Not established\n[Source](https://example.org)\n",
        encoding="utf-8",
    )
    figure = tmp_path / "figure.json"
    _write_json(
        figure,
        {
            "version": "v7",
            "selected_branch": "cohomological_non_gaussian_class",
            "inputs": {
                pilot.name: _hash(pilot),
                inference.name: _hash(inference),
            },
            "outputs": {
                pdf.name: _hash(pdf),
                png.name: _hash(png),
                report.name: _hash(report),
            },
            "checks": {"complete": True},
            "passed": True,
        },
    )
    return {
        "pilot_json": pilot,
        "pilot_npz": pilot_npz,
        "safe_json": safe,
        "prediction_json": prediction,
        "prediction_npz": prediction_npz,
        "prediction_seal": seal,
        "unsealed_json": unsealed,
        "inference_json": inference,
        "controls_json": controls,
        "figure_manifest": figure,
        "figure_pdf": pdf,
        "figure_png": png,
        "report_md": report,
    }


def test_delivery_passes_then_rejects_seal_and_safe_leakage(tmp_path: Path) -> None:
    paths = _synthetic_delivery(tmp_path)
    output = tmp_path / "audit.json"
    first = verify_delivery(**paths, output_json=output)
    assert first["passed"]
    paths["prediction_seal"].write_text(
        "0" * 64 + f"  {paths['prediction_json'].name}\n",
        encoding="utf-8",
    )
    second = verify_delivery(**paths, output_json=output)
    assert not second["passed"]
    assert not second["checks"]["valid_prediction_seal"]
    paths = _synthetic_delivery(tmp_path)
    leaked = json.loads(paths["prediction_json"].read_text(encoding="utf-8"))
    leaked["R4"] = 0.3
    _write_json(paths["prediction_json"], leaked)
    paths["prediction_seal"].write_text(
        f"{_hash(paths['prediction_json'])}  {paths['prediction_json'].name}\n",
        encoding="utf-8",
    )
    third = verify_delivery(**paths, output_json=output)
    assert not third["passed"]
    assert not third["checks"]["prediction_has_no_outcome_leakage"]
