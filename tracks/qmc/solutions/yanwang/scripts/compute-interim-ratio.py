#!/usr/bin/env python3
"""Compute a conservative, explicitly non-final #148 interim ratio."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def finite(value: Any, message: str) -> float:
    require(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value)),
        message,
    )
    return float(value)


def load_triangle_primary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(payload.get("schema_version") == "yanwang148.fit.v2", "triangle-schema")
    require(payload.get("lattice") == "triangular", "triangle-lattice")
    require(payload.get("classification") == "primary", "triangle-primary")
    require(payload.get("accepted") is True, "triangle-rejected")
    estimates = payload.get("parameters", {}).get("estimates", {})
    return {
        "fit_id": payload["fit_id"],
        "hc": finite(estimates.get("hc"), "triangle-hc"),
        "sigma_stat": finite(
            estimates.get("hc_sigma_stat"),
            "triangle-hc-stat",
        ),
        "p_value": finite(
            payload.get("diagnostics", {}).get("p_value"),
            "triangle-p-value",
        ),
        "input_manifest_sha256": payload.get("input_manifest_sha256"),
    }


def load_triangle_systematic(path: Path, primary_hc: float) -> dict[str, Any]:
    rows = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            hc = finite(float(row["hc"]), f"triangle-variant-hc:{row['fit_id']}")
            rows.append(
                {
                    "fit_id": row["fit_id"],
                    "classification": row["classification"],
                    "hc": hc,
                    "shift": hc - primary_hc,
                    "p_value": finite(
                        float(row["p_value"]),
                        f"triangle-variant-p:{row['fit_id']}",
                    ),
                    "central_rejection_reasons": [
                        reason
                        for reason in row["rejection_reasons"].split(";")
                        if reason
                        not in {
                            "",
                            "bootstrap-failure-fraction",
                            "incomplete-bootstrap-attempts",
                            "insufficient-bootstrap-successes",
                        }
                    ],
                }
            )
    require(len(rows) == 23, "triangle-central-fit-count")
    primary_rows = [
        row for row in rows if row["classification"] == "primary"
    ]
    require(len(primary_rows) == 1, "triangle-central-primary-count")
    envelope_row = max(rows, key=lambda row: abs(row["shift"]))
    return {
        "fit_count": len(rows),
        "rule": (
            "maximum absolute central hc shift over all 23 preregistered "
            "fits, without value-based discards"
        ),
        "sigma_sys": abs(envelope_row["shift"]),
        "envelope_fit_id": envelope_row["fit_id"],
        "envelope_fit_hc": envelope_row["hc"],
        "rows": sorted(
            rows,
            key=lambda row: abs(row["shift"]),
            reverse=True,
        ),
    }


def load_honeycomb(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(
        payload.get("schema_version")
        == "yanwang148.lattice-baseline-summary.v1",
        "honeycomb-schema",
    )
    require(payload.get("lattice") == "honeycomb", "honeycomb-lattice")
    primary = payload.get("primary_fit", {})
    require(primary.get("accepted") is True, "honeycomb-rejected")
    return {
        "fit_id": primary["fit_id"],
        "hc": finite(primary.get("hc"), "honeycomb-hc"),
        "sigma_stat": finite(
            primary.get("statistical_uncertainty"),
            "honeycomb-hc-stat",
        ),
        "sigma_sys": finite(
            primary.get("systematic_uncertainty"),
            "honeycomb-hc-sys",
        ),
        "p_value": finite(primary.get("p_value"), "honeycomb-p-value"),
        "pilot_promotion_gate": (
            payload.get("gates", {}).get("pilot_promotion") is True
        ),
    }


def load_independent(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(
        payload.get("schema_version")
        == "yanwang148.independent-pilot-summary.v1",
        "independent-schema",
    )
    lattices = payload["lattices"]
    triangle = lattices["triangular"]
    honeycomb = lattices["honeycomb"]
    ratio = finite(triangle["hc"], "independent-triangle") / finite(
        honeycomb["hc"],
        "independent-honeycomb",
    )
    return {
        "implementation_id": payload.get("implementation_id"),
        "ratio": ratio,
        "delta_sqrt5": ratio - math.sqrt(5.0),
        "data_class": payload.get("data_class"),
        "production_result": payload.get("production_result"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--triangle-primary-fit", required=True, type=Path)
    parser.add_argument("--triangle-central-robustness", required=True, type=Path)
    parser.add_argument("--honeycomb-summary", required=True, type=Path)
    parser.add_argument("--independent-summary", required=True, type=Path)
    parser.add_argument("--triangle-job-id", required=True)
    parser.add_argument("--central-job-id", required=True)
    parser.add_argument("--triangle-bootstrap-resamples", required=True, type=int)
    parser.add_argument(
        "--triangle-crossing-gate",
        required=True,
        choices=("passed", "failed"),
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    require(not args.out.exists(), "output-exists")
    require(
        args.triangle_bootstrap_resamples >= 100000,
        "triangle-bootstrap-count",
    )

    triangle = load_triangle_primary(args.triangle_primary_fit)
    triangle_systematic = load_triangle_systematic(
        args.triangle_central_robustness,
        triangle["hc"],
    )
    triangle["sigma_sys"] = triangle_systematic["sigma_sys"]
    honeycomb = load_honeycomb(args.honeycomb_summary)

    ratio = triangle["hc"] / honeycomb["hc"]
    sigma_stat = ratio * math.hypot(
        triangle["sigma_stat"] / triangle["hc"],
        honeycomb["sigma_stat"] / honeycomb["hc"],
    )
    triangle_ratio_sys = (
        ratio * triangle["sigma_sys"] / triangle["hc"]
    )
    honeycomb_ratio_sys = (
        ratio * honeycomb["sigma_sys"] / honeycomb["hc"]
    )
    sigma_sys = math.hypot(triangle_ratio_sys, honeycomb_ratio_sys)
    sigma_total = math.hypot(sigma_stat, sigma_sys)
    delta = ratio - math.sqrt(5.0)

    result = {
        "schema_version": "yanwang148.interim-ratio.v1",
        "data_class": "baseline-plus-central-robustness",
        "eligible_for_final_verdict": False,
        "verdict": "inconclusive",
        "verdict_reason": (
            "The conservative total uncertainty misses the preregistered "
            "1.2e-5 target, the triangular adjacent-crossing gate failed, "
            "and these are baseline rather than final-production data."
        ),
        "lattices": {
            "triangular": triangle,
            "honeycomb": honeycomb,
        },
        "triangle_systematic_envelope": triangle_systematic,
        "ratio": ratio,
        "sqrt5": math.sqrt(5.0),
        "delta_sqrt5": delta,
        "sigma_stat": sigma_stat,
        "sigma_sys": sigma_sys,
        "sigma_total": sigma_total,
        "z_abs": abs(delta) / sigma_total,
        "systematic_components": {
            "triangular": triangle_ratio_sys,
            "honeycomb": honeycomb_ratio_sys,
            "combination": "independent-lattice quadrature",
        },
        "gates": {
            "triangle_primary_fit": True,
            "triangle_100k_bootstrap": True,
            "triangle_crossing": args.triangle_crossing_gate == "passed",
            "triangle_full_variant_bootstrap": False,
            "honeycomb_primary_fit": True,
            "honeycomb_pilot_promotion": honeycomb[
                "pilot_promotion_gate"
            ],
            "target_sigma_R_le_1_2e_5": sigma_total <= 1.2e-5,
            "final_production_data": False,
        },
        "independent_route": load_independent(args.independent_summary),
        "scheduler": {
            "triangle_primary_job_id": args.triangle_job_id,
            "triangle_central_robustness_job_id": args.central_job_id,
        },
        "inputs": {
            "triangle_primary_fit": {
                "path": str(args.triangle_primary_fit),
                "sha256": sha256(args.triangle_primary_fit),
            },
            "triangle_central_robustness": {
                "path": str(args.triangle_central_robustness),
                "sha256": sha256(args.triangle_central_robustness),
            },
            "honeycomb_summary": {
                "path": str(args.honeycomb_summary),
                "sha256": sha256(args.honeycomb_summary),
            },
            "independent_summary": {
                "path": str(args.independent_summary),
                "sha256": sha256(args.independent_summary),
            },
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
