#!/usr/bin/env python3
"""Compute the explicitly non-production #148 baseline ratio.

This script is intentionally separate from final-ratio-gate.py.  It consumes
the two completed single-lattice baseline summaries only after their fits have
finished, propagates statistical uncertainty, and builds a conservative
systematic envelope from the Cartesian product of all accepted frozen fit
variants.  A baseline result can never emit a final confirmed/refuted verdict.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any


SUMMARY_SCHEMA = "yanwang148.lattice-baseline-summary.v1"
OUTPUT_SCHEMA = "yanwang148.baseline-ratio.v1"
INDEPENDENT_SCHEMA = "yanwang148.independent-pilot-summary.v1"
LATTICES = ("triangular", "honeycomb")


class RatioInputError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RatioInputError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def finite_positive(value: Any, path: str) -> float:
    require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"{path}:expected-number",
    )
    number = float(value)
    require(
        math.isfinite(number) and number > 0.0,
        f"{path}:expected-finite-positive",
    )
    return number


def load_summary(path: Path, lattice: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(
        payload.get("schema_version") == SUMMARY_SCHEMA,
        f"{lattice}:summary-schema",
    )
    require(payload.get("lattice") == lattice, f"{lattice}:wrong-lattice")
    require(payload.get("data_class") == "baseline", f"{lattice}:not-baseline")
    require(
        payload.get("production_result") is False,
        f"{lattice}:production-result-refused",
    )
    primary = payload.get("primary_fit")
    require(isinstance(primary, dict), f"{lattice}:missing-primary")
    require(primary.get("accepted") is True, f"{lattice}:primary-rejected")
    return {
        "path": str(path),
        "sha256": sha256(path),
        "run_id": payload.get("run_id"),
        "value": finite_positive(primary.get("hc"), f"{lattice}.hc"),
        "sigma_stat": finite_positive(
            primary.get("statistical_uncertainty"),
            f"{lattice}.sigma_stat",
        ),
        "sigma_sys": finite_positive(
            primary.get("systematic_uncertainty"),
            f"{lattice}.sigma_sys",
        ),
        "technical_gate": payload.get("gates", {}).get("technical") is True,
        "primary_gate": payload.get("gates", {}).get("primary_fit") is True,
        "pilot_promotion_gate": (
            payload.get("gates", {}).get("pilot_promotion") is True
        ),
    }


def load_variants(path: Path, lattice: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"fit_id", "classification", "accepted", "hc"}
        require(
            reader.fieldnames is not None
            and required.issubset(reader.fieldnames),
            f"{lattice}:robustness-columns",
        )
        for index, row in enumerate(reader, start=2):
            accepted_text = row["accepted"].strip().lower()
            require(
                accepted_text in {"true", "false"},
                f"{lattice}:row-{index}:accepted",
            )
            if accepted_text == "true":
                rows.append(
                    {
                        "fit_id": row["fit_id"],
                        "classification": row["classification"],
                        "value": finite_positive(
                            float(row["hc"]),
                            f"{lattice}:row-{index}:hc",
                        ),
                    }
                )
    require(rows, f"{lattice}:no-accepted-fits")
    require(
        sum(row["classification"] == "primary" for row in rows) == 1,
        f"{lattice}:primary-roster",
    )
    require(
        len({row["fit_id"] for row in rows}) == len(rows),
        f"{lattice}:duplicate-fit-id",
    )
    return rows


def load_independent(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(
        payload.get("schema_version") == INDEPENDENT_SCHEMA,
        "independent:summary-schema",
    )
    require(
        payload.get("data_class") == "pilot-scaling"
        and payload.get("production_result") is False,
        "independent:not-pilot",
    )
    require(
        payload.get("bootstrap_resamples", 0) >= 100000,
        "independent:bootstrap-count",
    )
    require(
        payload.get("bootstrap_successes")
        == {"honeycomb": 100000, "triangular": 100000},
        "independent:bootstrap-successes",
    )
    lattices = payload.get("lattices")
    require(isinstance(lattices, dict), "independent:missing-lattices")
    result = {
        "path": str(path),
        "sha256": sha256(path),
        "implementation_id": payload.get("implementation_id"),
        "production_result": False,
        "lattices": {},
    }
    for lattice in LATTICES:
        block = lattices.get(lattice)
        require(isinstance(block, dict), f"independent:{lattice}:missing")
        result["lattices"][lattice] = {
            "value": finite_positive(block.get("hc"), f"independent:{lattice}:hc"),
            "sigma_stat": finite_positive(
                block.get("statistical_uncertainty"),
                f"independent:{lattice}:sigma_stat",
            ),
            "sigma_sys": finite_positive(
                block.get("systematic_uncertainty"),
                f"independent:{lattice}:sigma_sys",
            ),
            "p_value": finite_positive(
                block.get("p_value"),
                f"independent:{lattice}:p_value",
            ),
        }
    return result


def cross_method_check(
    triangle: dict[str, Any],
    honeycomb: dict[str, Any],
    independent: dict[str, Any],
) -> dict[str, Any]:
    rows = {}
    for lattice, primary in (
        ("triangular", triangle),
        ("honeycomb", honeycomb),
    ):
        alternate = independent["lattices"][lattice]
        primary_total = math.hypot(primary["sigma_stat"], primary["sigma_sys"])
        alternate_total = math.hypot(
            alternate["sigma_stat"],
            alternate["sigma_sys"],
        )
        combined = math.hypot(primary_total, alternate_total)
        delta = primary["value"] - alternate["value"]
        rows[lattice] = {
            "primary": primary["value"],
            "independent": alternate["value"],
            "delta": delta,
            "primary_sigma_total": primary_total,
            "independent_sigma_total": alternate_total,
            "combined_sigma": combined,
            "z_combined": abs(delta) / combined,
            "passed_2sigma": abs(delta) <= 2.0 * combined,
        }
    independent_ratio = (
        independent["lattices"]["triangular"]["value"]
        / independent["lattices"]["honeycomb"]["value"]
    )
    independent_ratio_stat = independent_ratio * math.sqrt(
        (
            independent["lattices"]["triangular"]["sigma_stat"]
            / independent["lattices"]["triangular"]["value"]
        )
        ** 2
        + (
            independent["lattices"]["honeycomb"]["sigma_stat"]
            / independent["lattices"]["honeycomb"]["value"]
        )
        ** 2
    )
    independent_ratio_sys = independent_ratio * math.sqrt(
        (
            independent["lattices"]["triangular"]["sigma_sys"]
            / independent["lattices"]["triangular"]["value"]
        )
        ** 2
        + (
            independent["lattices"]["honeycomb"]["sigma_sys"]
            / independent["lattices"]["honeycomb"]["value"]
        )
        ** 2
    )
    primary_ratio = triangle["value"] / honeycomb["value"]
    primary_delta = primary_ratio - math.sqrt(5.0)
    independent_delta = independent_ratio - math.sqrt(5.0)
    return {
        "implementation_id": independent["implementation_id"],
        "production_result": False,
        "lattices": rows,
        "passed_2sigma_both_lattices": all(
            row["passed_2sigma"] for row in rows.values()
        ),
        "ratio": independent_ratio,
        "ratio_sigma_stat": independent_ratio_stat,
        "ratio_sigma_sys_approximate": independent_ratio_sys,
        "ratio_sigma_total_approximate": math.hypot(
            independent_ratio_stat,
            independent_ratio_sys,
        ),
        "delta_sqrt5": independent_delta,
        "same_delta_sign": (
            primary_delta == 0.0
            or independent_delta == 0.0
            or math.copysign(1.0, primary_delta)
            == math.copysign(1.0, independent_delta)
        ),
        "note": (
            "Independent-route systematic ratio uncertainty is a conservative "
            "delta-method approximation from its two single-lattice envelopes."
        ),
    }


def compute(
    triangle: dict[str, Any],
    honeycomb: dict[str, Any],
    triangle_variants: list[dict[str, Any]],
    honeycomb_variants: list[dict[str, Any]],
    independent: dict[str, Any],
) -> dict[str, Any]:
    ratio = triangle["value"] / honeycomb["value"]
    sigma_stat = ratio * math.sqrt(
        (triangle["sigma_stat"] / triangle["value"]) ** 2
        + (honeycomb["sigma_stat"] / honeycomb["value"]) ** 2
    )
    combinations = []
    for tri in triangle_variants:
        for hon in honeycomb_variants:
            candidate = tri["value"] / hon["value"]
            combinations.append(
                {
                    "triangular_fit_id": tri["fit_id"],
                    "honeycomb_fit_id": hon["fit_id"],
                    "ratio": candidate,
                    "absolute_shift_from_primary": abs(candidate - ratio),
                }
            )
    require(combinations, "empty-systematic-product")
    sigma_sys = max(row["absolute_shift_from_primary"] for row in combinations)
    sigma_total = math.hypot(sigma_stat, sigma_sys)
    delta = ratio - math.sqrt(5.0)
    z_abs = abs(delta) / sigma_total if sigma_total > 0.0 else math.inf
    technical_ready = all(
        (
            triangle["technical_gate"],
            triangle["primary_gate"],
            honeycomb["technical_gate"],
            honeycomb["primary_gate"],
        )
    )
    production_ready = all(
        (
            technical_ready,
            triangle["pilot_promotion_gate"],
            honeycomb["pilot_promotion_gate"],
        )
    )
    cross_method = cross_method_check(triangle, honeycomb, independent)
    return {
        "schema_version": OUTPUT_SCHEMA,
        "data_class": "baseline",
        "eligible_for_final_verdict": False,
        "verdict": "inconclusive",
        "verdict_reason": (
            "Baseline-only data cannot trigger the preregistered final verdict; "
            "at least one pilot-promotion gate is also false."
            if not production_ready
            else "Baseline-only data cannot trigger the preregistered final verdict."
        ),
        "lattices": {
            "triangular": triangle,
            "honeycomb": honeycomb,
        },
        "ratio": ratio,
        "sqrt5": math.sqrt(5.0),
        "delta_sqrt5": delta,
        "sigma_stat": sigma_stat,
        "sigma_sys": sigma_sys,
        "sigma_total": sigma_total,
        "z_abs_baseline_only": z_abs,
        "systematic_rule": (
            "maximum absolute ratio shift over the Cartesian product of all "
            "accepted frozen single-lattice fit variants"
        ),
        "accepted_variant_combination_count": len(combinations),
        "accepted_variant_combinations": combinations,
        "cross_method_check": cross_method,
        "gates": {
            "technical_ready": technical_ready,
            "pilot_promotion_ready": production_ready,
            "target_sigma_R_le_1_2e_5": sigma_total <= 1.2e-5,
            "final_production_data": False,
            "independent_route_passed_2sigma": cross_method[
                "passed_2sigma_both_lattices"
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--triangle-summary", required=True, type=Path)
    parser.add_argument("--triangle-robustness", required=True, type=Path)
    parser.add_argument("--honeycomb-summary", required=True, type=Path)
    parser.add_argument("--honeycomb-robustness", required=True, type=Path)
    parser.add_argument("--independent-summary", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    require(not args.out.exists(), "output-exists")
    triangle = load_summary(args.triangle_summary.resolve(), "triangular")
    honeycomb = load_summary(args.honeycomb_summary.resolve(), "honeycomb")
    result = compute(
        triangle,
        honeycomb,
        load_variants(args.triangle_robustness.resolve(), "triangular"),
        load_variants(args.honeycomb_robustness.resolve(), "honeycomb"),
        load_independent(args.independent_summary.resolve()),
    )
    result["inputs"] = {
        "triangle_summary": {
            "path": str(args.triangle_summary),
            "sha256": sha256(args.triangle_summary),
        },
        "triangle_robustness": {
            "path": str(args.triangle_robustness),
            "sha256": sha256(args.triangle_robustness),
        },
        "honeycomb_summary": {
            "path": str(args.honeycomb_summary),
            "sha256": sha256(args.honeycomb_summary),
        },
        "honeycomb_robustness": {
            "path": str(args.honeycomb_robustness),
            "sha256": sha256(args.honeycomb_robustness),
        },
        "independent_summary": {
            "path": str(args.independent_summary),
            "sha256": sha256(args.independent_summary),
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
