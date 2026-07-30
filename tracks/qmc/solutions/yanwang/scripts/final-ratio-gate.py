#!/usr/bin/env python3
"""Fail-closed blinding and opening gate for the final #148 ratio.

This controller does not fit lattice data.  It consumes normalized exports
from the separately frozen dedicated-SSE and ALPS/looper analyses, verifies
their complete variant/bootstrap inventories, and applies the preregistered
joint uncertainty and verdict rules.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
from typing import Any


INPUT_SCHEMA = "yanwang148.final-analysis-input.v1"
BLIND_SCHEMA = "yanwang148.final-blind-record.v1"
VERDICT_SCHEMA = "yanwang148.verdict.v1"
EXPECTED_DATA_CLASS = "verdict-production"
MINIMUM_BOOTSTRAP_DRAWS = 50_000
EXPECTED_PREREGISTRATION_SHA256 = (
    "802312daf6d35786531b6d4a011a4980005adb1832bea29f7cf0842969efe673"
)
LATTICES = ("triangular", "honeycomb")
HEX_SHA256_LENGTH = 64
HEX_COMMIT_LENGTH = 40


class GateError(RuntimeError):
    """A fail-closed input, provenance, or gate failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def require_exact_keys(
    value: Any,
    required: set[str],
    *,
    path: str,
    optional: set[str] | None = None,
) -> dict[str, Any]:
    require(isinstance(value, dict), f"{path}: expected object")
    optional = optional or set()
    keys = set(value)
    missing = sorted(required - keys)
    extra = sorted(keys - required - optional)
    require(not missing, f"{path}: missing keys {missing}")
    require(not extra, f"{path}: unexpected keys {extra}")
    return value


def is_hex(value: Any, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def finite_number(value: Any, path: str, *, positive: bool = False) -> float:
    require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"{path}: expected number",
    )
    result = float(value)
    require(math.isfinite(result), f"{path}: non-finite number")
    if positive:
        require(result > 0.0, f"{path}: expected positive number")
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def validate_draws(
    value: Any,
    path: str,
    *,
    expected_draws: int,
) -> list[float | None]:
    require(isinstance(value, list), f"{path}: expected array")
    require(
        len(value) >= expected_draws,
        f"{path}: expected at least {expected_draws} configured bootstrap draws",
    )
    draws: list[float | None] = []
    for index, item in enumerate(value):
        draws.append(
            None
            if item is None
            else finite_number(item, f"{path}[{index}]", positive=True)
        )
    successful = [item for item in draws if item is not None]
    require(
        len(successful) >= expected_draws,
        f"{path}: expected at least {expected_draws} successful bootstrap draws",
    )
    require(
        len(set(successful)) > 1,
        f"{path}: zero bootstrap dispersion is not an uncertainty",
    )
    return draws


def validate_variant(
    value: Any,
    path: str,
    *,
    expected_draws: int,
    primary: bool,
) -> dict[str, Any]:
    row = require_exact_keys(
        value,
        {"id", "accepted", "value", "draws"},
        path=path,
    )
    require(
        isinstance(row["id"], str) and row["id"] and row["id"].replace("-", "").replace("_", "").isalnum(),
        f"{path}.id: unsafe or empty id",
    )
    require(isinstance(row["accepted"], bool), f"{path}.accepted: expected boolean")
    if primary:
        require(row["id"] == "primary", f"{path}.id: primary id must be 'primary'")
        require(row["accepted"] is True, f"{path}: primary fit must be accepted")
    if row["accepted"]:
        central = finite_number(row["value"], f"{path}.value", positive=True)
        draws = validate_draws(
            row["draws"],
            f"{path}.draws",
            expected_draws=expected_draws,
        )
    else:
        require(
            row["value"] is None,
            f"{path}.value: rejected variant must expose no central value",
        )
        require(
            row["draws"] == [],
            f"{path}.draws: rejected variant must expose no bootstrap draws",
        )
        central = None
        draws = []
    return {
        "id": row["id"],
        "accepted": row["accepted"],
        "value": central,
        "draws": draws,
        "configured_draw_count": len(draws),
        "successful_draw_count": sum(item is not None for item in draws),
        "failed_draw_count": sum(item is None for item in draws),
        "minimum_successful_draws": expected_draws,
    }


def validate_estimate(
    value: Any,
    path: str,
    *,
    expected_draws: int,
) -> dict[str, Any]:
    block = require_exact_keys(
        value,
        {
            "passed",
            "run_id",
            "analysis_report_sha256",
            "run_manifest_sha256",
            "environment_sha256",
            "scheduler_inventory_sha256",
            "command",
            "primary",
            "required_variant_ids",
            "variants",
        },
        path=path,
    )
    require(block["passed"] is True, f"{path}.passed: lattice analysis did not pass")
    require(
        isinstance(block["run_id"], str) and block["run_id"],
        f"{path}.run_id: expected nonempty string",
    )
    for key in (
        "analysis_report_sha256",
        "run_manifest_sha256",
        "environment_sha256",
        "scheduler_inventory_sha256",
    ):
        require(
            is_hex(block[key], HEX_SHA256_LENGTH),
            f"{path}.{key}: expected lowercase SHA-256",
        )
    require(
        isinstance(block["command"], str) and block["command"].strip(),
        f"{path}.command: expected nonempty reproducible command",
    )
    primary = validate_variant(
        block["primary"],
        f"{path}.primary",
        expected_draws=expected_draws,
        primary=True,
    )
    required_ids = block["required_variant_ids"]
    require(
        isinstance(required_ids, list)
        and required_ids
        and all(isinstance(item, str) and item for item in required_ids),
        f"{path}.required_variant_ids: expected nonempty string array",
    )
    require(
        len(required_ids) == len(set(required_ids)),
        f"{path}.required_variant_ids: duplicate id",
    )
    variants_raw = block["variants"]
    require(isinstance(variants_raw, list), f"{path}.variants: expected array")
    variants = [
        validate_variant(
            row,
            f"{path}.variants[{index}]",
            expected_draws=expected_draws,
            primary=False,
        )
        for index, row in enumerate(variants_raw)
    ]
    observed_ids = [row["id"] for row in variants]
    require(
        len(observed_ids) == len(set(observed_ids)),
        f"{path}.variants: duplicate id",
    )
    require(
        set(observed_ids) == set(required_ids),
        f"{path}.variants: declared and observed variant ids differ",
    )
    require(
        any(row["accepted"] for row in variants),
        f"{path}.variants: at least one non-primary variant must be accepted",
    )
    for row in variants:
        if row["accepted"]:
            require(
                row["configured_draw_count"]
                == primary["configured_draw_count"],
                f"{path}.variants.{row['id']}: bootstrap indices differ",
            )
    return {
        "passed": True,
        "run_id": block["run_id"],
        "analysis_report_sha256": block["analysis_report_sha256"],
        "run_manifest_sha256": block["run_manifest_sha256"],
        "environment_sha256": block["environment_sha256"],
        "scheduler_inventory_sha256": block[
            "scheduler_inventory_sha256"
        ],
        "command": block["command"],
        "primary": primary,
        "required_variant_ids": list(required_ids),
        "variants": variants,
    }


def validate_route(
    value: Any,
    path: str,
    *,
    expected_route_id: str,
    expected_draws: int,
) -> dict[str, Any]:
    route = require_exact_keys(
        value,
        {"route_id", "implementation_id", "code_sha256", "passed", "lattices"},
        path=path,
    )
    require(
        route["route_id"] == expected_route_id,
        f"{path}.route_id: expected {expected_route_id}",
    )
    require(
        isinstance(route["implementation_id"], str) and route["implementation_id"],
        f"{path}.implementation_id: expected nonempty string",
    )
    require(
        is_hex(route["code_sha256"], HEX_SHA256_LENGTH),
        f"{path}.code_sha256: expected lowercase SHA-256",
    )
    require(route["passed"] is True, f"{path}.passed: route did not pass")
    lattices = require_exact_keys(
        route["lattices"],
        set(LATTICES),
        path=f"{path}.lattices",
    )
    normalized_lattices = {
        lattice: validate_estimate(
            lattices[lattice],
            f"{path}.lattices.{lattice}",
            expected_draws=expected_draws,
        )
        for lattice in LATTICES
    }
    require(
        normalized_lattices["triangular"]["primary"][
            "configured_draw_count"
        ]
        == normalized_lattices["honeycomb"]["primary"][
            "configured_draw_count"
        ],
        f"{path}: lattice bootstrap indices differ",
    )
    return {
        "route_id": route["route_id"],
        "implementation_id": route["implementation_id"],
        "code_sha256": route["code_sha256"],
        "passed": True,
        "lattices": normalized_lattices,
    }


def validate_bundle(
    value: Any,
    *,
    expected_draws: int = MINIMUM_BOOTSTRAP_DRAWS,
) -> dict[str, Any]:
    bundle = require_exact_keys(
        value,
        {
            "schema_version",
            "data_class",
            "production_data",
            "freeze_commit",
            "preregistration_sha256",
            "arithmetic_candidate_sha256",
            "arithmetic_validator_sha256",
            "provenance",
            "primary_route",
            "independent_route",
        },
        path="input",
    )
    require(bundle["schema_version"] == INPUT_SCHEMA, "input: unexpected schema")
    require(bundle["data_class"] == EXPECTED_DATA_CLASS, "input: not verdict production")
    require(bundle["production_data"] is True, "input: production_data must be true")
    require(
        is_hex(bundle["freeze_commit"], HEX_COMMIT_LENGTH),
        "input.freeze_commit: expected full lowercase Git SHA-1",
    )
    require(
        bundle["preregistration_sha256"] == EXPECTED_PREREGISTRATION_SHA256,
        "input.preregistration_sha256: frozen preregistration mismatch",
    )
    require(
        is_hex(bundle["arithmetic_candidate_sha256"], HEX_SHA256_LENGTH),
        "input.arithmetic_candidate_sha256: expected lowercase SHA-256",
    )
    require(
        is_hex(bundle["arithmetic_validator_sha256"], HEX_SHA256_LENGTH),
        "input.arithmetic_validator_sha256: expected lowercase SHA-256",
    )
    provenance = require_exact_keys(
        bundle["provenance"],
        {
            "sqrt5_used_in_selection",
            "ratio_used_in_selection",
            "final_analysis_frozen_before_opening",
        },
        path="input.provenance",
    )
    require(
        provenance["sqrt5_used_in_selection"] is False,
        "input.provenance: sqrt(5) influenced selection",
    )
    require(
        provenance["ratio_used_in_selection"] is False,
        "input.provenance: ratio influenced selection",
    )
    require(
        provenance["final_analysis_frozen_before_opening"] is True,
        "input.provenance: analysis was not frozen before opening",
    )
    primary = validate_route(
        bundle["primary_route"],
        "input.primary_route",
        expected_route_id="primary-sse",
        expected_draws=expected_draws,
    )
    independent = validate_route(
        bundle["independent_route"],
        "input.independent_route",
        expected_route_id="independent-ctqmc",
        expected_draws=expected_draws,
    )
    require(
        primary["implementation_id"] != independent["implementation_id"],
        "input: route implementation ids are not independent",
    )
    require(
        primary["code_sha256"] != independent["code_sha256"],
        "input: route code hashes are identical",
    )
    return {
        "schema_version": INPUT_SCHEMA,
        "data_class": EXPECTED_DATA_CLASS,
        "production_data": True,
        "freeze_commit": bundle["freeze_commit"],
        "preregistration_sha256": bundle["preregistration_sha256"],
        "arithmetic_candidate_sha256": bundle[
            "arithmetic_candidate_sha256"
        ],
        "arithmetic_validator_sha256": bundle["arithmetic_validator_sha256"],
        "provenance": dict(provenance),
        "primary_route": primary,
        "independent_route": independent,
    }


def accepted_rows(estimate: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        estimate["primary"],
        *(row for row in estimate["variants"] if row["accepted"]),
    ]


def uncertainty(estimate: dict[str, Any]) -> dict[str, float]:
    primary = estimate["primary"]
    successful = [item for item in primary["draws"] if item is not None]
    statistical = statistics.stdev(successful)
    systematic = max(
        abs(row["value"] - primary["value"])
        for row in accepted_rows(estimate)
    )
    return {
        "value": primary["value"],
        "sigma_stat": statistical,
        "sigma_sys": systematic,
        "sigma_total": math.hypot(statistical, systematic),
    }


def aligned_ratio_draws(
    triangular: dict[str, Any],
    honeycomb: dict[str, Any],
) -> dict[str, Any]:
    triangular_draws = triangular["draws"]
    honeycomb_draws = honeycomb["draws"]
    require(
        len(triangular_draws) == len(honeycomb_draws),
        "joint bootstrap: lattice draw counts differ",
    )
    draws = []
    failed_indices = []
    for index, (triangular_value, honeycomb_value) in enumerate(
        zip(triangular_draws, honeycomb_draws)
    ):
        if triangular_value is None or honeycomb_value is None:
            failed_indices.append(index)
        else:
            draws.append(triangular_value / honeycomb_value)
    minimum = max(
        triangular["minimum_successful_draws"],
        honeycomb["minimum_successful_draws"],
    )
    require(
        len(draws) >= minimum,
        "joint bootstrap: insufficient index-aligned successful draws",
    )
    require(
        len(set(draws)) > 1,
        "joint bootstrap: zero ratio dispersion is not an uncertainty",
    )
    configured = len(triangular_draws)
    return {
        "draws": draws,
        "configured_count": configured,
        "successful_count": len(draws),
        "failed_count": configured - len(draws),
        "failed_indices": failed_indices,
    }


def route_ratio(route: dict[str, Any]) -> tuple[float, float, dict[str, Any]]:
    triangular = route["lattices"]["triangular"]["primary"]
    honeycomb = route["lattices"]["honeycomb"]["primary"]
    central = triangular["value"] / honeycomb["value"]
    aligned = aligned_ratio_draws(triangular, honeycomb)
    statistical = statistics.stdev(aligned["draws"])
    return central, statistical, {
        key: aligned[key]
        for key in (
            "configured_count",
            "successful_count",
            "failed_count",
            "failed_indices",
        )
    }


def comparison_z(primary: dict[str, float], secondary: dict[str, float]) -> float:
    combined = math.hypot(primary["sigma_total"], secondary["sigma_total"])
    require(combined > 0.0, "cross-method comparison has zero uncertainty")
    return abs(primary["value"] - secondary["value"]) / combined


def sign(value: float) -> int:
    return (value > 0.0) - (value < 0.0)


def candidate_input(
    bundle: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    primary = bundle["primary_route"]
    independent = bundle["independent_route"]
    primary_fields = {
        lattice: uncertainty(primary["lattices"][lattice])
        for lattice in LATTICES
    }
    independent_fields = {
        lattice: uncertainty(independent["lattices"][lattice])
        for lattice in LATTICES
    }
    primary_ratio, ratio_stat, primary_ratio_counts = route_ratio(primary)
    independent_ratio, _, independent_ratio_counts = route_ratio(independent)

    triangular_rows = accepted_rows(primary["lattices"]["triangular"])
    honeycomb_rows = accepted_rows(primary["lattices"]["honeycomb"])
    joint = []
    for triangular, honeycomb in itertools.product(
        triangular_rows,
        honeycomb_rows,
    ):
        aligned = aligned_ratio_draws(triangular, honeycomb)
        draws = aligned["draws"]
        joint.append(
            {
                "fit_id": f"{triangular['id']}__{honeycomb['id']}",
                "ratio": triangular["value"] / honeycomb["value"],
                "sigma_stat": statistics.stdev(draws),
                "bootstrap_configured_count": aligned["configured_count"],
                "bootstrap_successful_count": aligned["successful_count"],
                "bootstrap_failed_count": aligned["failed_count"],
                "bootstrap_failed_indices": aligned["failed_indices"],
            }
        )
    ratio_systematic = max(
        abs(row["ratio"] - primary_ratio)
        for row in joint
    )
    accepted_variants = [
        {
            "fit_id": row["fit_id"],
            "ratio": row["ratio"],
            "sigma_stat": row["sigma_stat"],
            "sigma_sys": ratio_systematic,
            "sigma_total": math.hypot(row["sigma_stat"], ratio_systematic),
            "bootstrap_configured_count": row[
                "bootstrap_configured_count"
            ],
            "bootstrap_successful_count": row[
                "bootstrap_successful_count"
            ],
            "bootstrap_failed_count": row["bootstrap_failed_count"],
            "bootstrap_failed_indices": row["bootstrap_failed_indices"],
        }
        for row in joint
    ]
    triangle_z = comparison_z(
        primary_fields["triangular"],
        independent_fields["triangular"],
    )
    honeycomb_z = comparison_z(
        primary_fields["honeycomb"],
        independent_fields["honeycomb"],
    )
    root5 = math.sqrt(5.0)
    same_delta_sign = (
        sign(primary_ratio - root5) == sign(independent_ratio - root5)
    )
    independence = {
        "passed": (
            independent["passed"]
            and triangle_z <= 2.0
            and honeycomb_z <= 2.0
        ),
        "triangle_z": triangle_z,
        "honeycomb_z": honeycomb_z,
        "same_delta_sign": same_delta_sign,
    }
    compact = {
        "triangle": {
            key: primary_fields["triangular"][key]
            for key in ("value", "sigma_stat", "sigma_sys")
        },
        "honeycomb": {
            key: primary_fields["honeycomb"][key]
            for key in ("value", "sigma_stat", "sigma_sys")
        },
        "ratio_sigma_stat": ratio_stat,
        "accepted_variants": [
            {
                "ratio": row["ratio"],
                "sigma_total": row["sigma_total"],
            }
            for row in accepted_variants
        ],
        "independent_route": {
            "passed": independence["passed"],
            "same_delta_sign": independence["same_delta_sign"],
        },
    }
    detail = {
        "primary_implementation_id": primary["implementation_id"],
        "independent_implementation_id": independent["implementation_id"],
        "primary_fields": primary_fields,
        "independent_fields": independent_fields,
        "primary_ratio": primary_ratio,
        "ratio_bootstrap_counts": primary_ratio_counts,
        "independent_ratio": independent_ratio,
        "independent_ratio_bootstrap_counts": independent_ratio_counts,
        "ratio_sigma_stat": ratio_stat,
        "ratio_sigma_systematic": ratio_systematic,
        "joint_variants": accepted_variants,
        "independence": independence,
    }
    return compact, detail


def solve_candidate(data: dict[str, Any]) -> dict[str, Any]:
    triangle = data["triangle"]
    honeycomb = data["honeycomb"]
    triangle_total = math.hypot(triangle["sigma_stat"], triangle["sigma_sys"])
    honeycomb_total = math.hypot(honeycomb["sigma_stat"], honeycomb["sigma_sys"])
    ratio = triangle["value"] / honeycomb["value"]
    delta = ratio - math.sqrt(5.0)
    ratio_sys = max(
        (abs(item["ratio"] - ratio) for item in data["accepted_variants"]),
        default=0.0,
    )
    ratio_total = math.hypot(data["ratio_sigma_stat"], ratio_sys)
    require(ratio_total > 0.0, "ratio uncertainty is zero")
    z_abs = abs(delta) / ratio_total
    precision = (
        triangle_total <= 1.8e-5
        and honeycomb_total <= 8.0e-6
        and ratio_total <= 1.2e-5
        and data["independent_route"]["passed"]
    )
    robust_against = bool(data["accepted_variants"]) and all(
        abs(item["ratio"] - math.sqrt(5.0)) >= 8.0 * item["sigma_total"]
        for item in data["accepted_variants"]
    )
    robust_survives = bool(data["accepted_variants"]) and all(
        abs(item["ratio"] - math.sqrt(5.0)) <= 2.0 * item["sigma_total"]
        for item in data["accepted_variants"]
    )
    if (
        precision
        and z_abs >= 10.0
        and robust_against
        and data["independent_route"]["same_delta_sign"]
    ):
        verdict = "evidence-against"
    elif precision and z_abs <= 2.0 and robust_survives:
        verdict = "survives-numerical-test"
    else:
        verdict = "inconclusive"
    return {
        "triangle_sigma_total": triangle_total,
        "honeycomb_sigma_total": honeycomb_total,
        "ratio": ratio,
        "delta_sqrt5": delta,
        "ratio_sigma_sys": ratio_sys,
        "ratio_sigma_total": ratio_total,
        "z_abs": z_abs,
        "precision_gate": precision,
        "robust_against": robust_against,
        "robust_survives": robust_survives,
        "verdict": verdict,
    }


def git_state(repo: Path, freeze_commit: str) -> None:
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    require(head == freeze_commit, "repository HEAD differs from frozen commit")
    dirty = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "status",
            "--porcelain",
            "--untracked-files=all",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    require(not dirty, "repository is dirty")


def confined_result_path(path: Path, repo: Path) -> Path:
    resolved = path.resolve()
    result_root = (repo / "results").resolve()
    require(
        resolved != result_root and resolved.is_relative_to(result_root),
        f"output must be a child of {result_root}",
    )
    return resolved


def confined_bundle_path(path: Path, repo: Path) -> Path:
    resolved = path.resolve()
    result_root = (repo / "results").resolve()
    require(
        resolved.is_relative_to(result_root),
        f"sealed input must be under {result_root}",
    )
    return resolved


def require_new_directory(path: Path) -> None:
    require(not path.exists() and not path.is_symlink(), f"refusing to reuse {path}")
    path.mkdir(parents=True)


def inventory(bundle: dict[str, Any]) -> dict[str, Any]:
    output = {}
    for route_key in ("primary_route", "independent_route"):
        route = bundle[route_key]
        output[route_key] = {}
        for lattice in LATTICES:
            estimate = route["lattices"][lattice]
            output[route_key][lattice] = {
                "bootstrap_draw_count": estimate["primary"][
                    "configured_draw_count"
                ],
                "bootstrap_successful_draw_count": estimate["primary"][
                    "successful_draw_count"
                ],
                "bootstrap_failed_draw_count": estimate["primary"][
                    "failed_draw_count"
                ],
                "declared_variant_count": len(estimate["required_variant_ids"]),
                "accepted_variant_count": sum(
                    row["accepted"] for row in estimate["variants"]
                ),
                "analysis_report_digest": estimate[
                    "analysis_report_sha256"
                ],
                "run_manifest_digest": estimate["run_manifest_sha256"],
                "environment_digest": estimate["environment_sha256"],
                "scheduler_inventory_digest": estimate[
                    "scheduler_inventory_sha256"
                ],
            }
    return output


def build_blind_record(
    bundle: dict[str, Any],
    *,
    bundle_sha256: str,
    arithmetic_validator_sha256: str,
    arithmetic_candidate_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": BLIND_SCHEMA,
        "source_freeze_commit": bundle["freeze_commit"],
        "source_freeze_digest": bundle["preregistration_sha256"],
        "bundle_digest": bundle_sha256,
        "arithmetic_candidate_digest": arithmetic_candidate_sha256,
        "arithmetic_validator_digest": arithmetic_validator_sha256,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "route_checks": {
            "input_contract_passed": True,
            "production_class_passed": True,
            "source_freeze_passed": True,
            "quality_gates_passed": True,
            "bootstrap_depth_passed": True,
            "variant_inventory_passed": True,
            "implementation_independence_passed": True,
            "ready_to_open": True,
        },
        "inventory": inventory(bundle),
    }


def validate_blind_record(value: Any) -> dict[str, Any]:
    record = require_exact_keys(
        value,
        {
            "schema_version",
            "source_freeze_commit",
            "source_freeze_digest",
            "bundle_digest",
            "arithmetic_candidate_digest",
            "arithmetic_validator_digest",
            "created_at",
            "route_checks",
            "inventory",
        },
        path="blind",
    )
    require(record["schema_version"] == BLIND_SCHEMA, "blind: unexpected schema")
    require(
        is_hex(record["source_freeze_commit"], HEX_COMMIT_LENGTH),
        "blind.source_freeze_commit: invalid",
    )
    for key in (
        "source_freeze_digest",
        "bundle_digest",
        "arithmetic_candidate_digest",
        "arithmetic_validator_digest",
    ):
        require(is_hex(record[key], HEX_SHA256_LENGTH), f"blind.{key}: invalid")
    checks = require_exact_keys(
        record["route_checks"],
        {
            "input_contract_passed",
            "production_class_passed",
            "source_freeze_passed",
            "quality_gates_passed",
            "bootstrap_depth_passed",
            "variant_inventory_passed",
            "implementation_independence_passed",
            "ready_to_open",
        },
        path="blind.route_checks",
    )
    require(all(value is True for value in checks.values()), "blind: a gate failed")
    inventory_block = require_exact_keys(
        record["inventory"],
        {"primary_route", "independent_route"},
        path="blind.inventory",
    )
    for route in inventory_block.values():
        lattice_block = require_exact_keys(
            route,
            set(LATTICES),
            path="blind.inventory.route",
        )
        for counts in lattice_block.values():
            require_exact_keys(
                counts,
                {
                    "bootstrap_draw_count",
                    "bootstrap_successful_draw_count",
                    "bootstrap_failed_draw_count",
                    "declared_variant_count",
                    "accepted_variant_count",
                    "analysis_report_digest",
                    "run_manifest_digest",
                    "environment_digest",
                    "scheduler_inventory_digest",
                },
                path="blind.inventory.route.lattice",
            )
            require(
                counts["bootstrap_draw_count"] >= MINIMUM_BOOTSTRAP_DRAWS,
                "blind.inventory: bootstrap depth changed",
            )
            require(
                isinstance(counts["bootstrap_successful_draw_count"], int)
                and counts["bootstrap_successful_draw_count"]
                >= MINIMUM_BOOTSTRAP_DRAWS,
                "blind.inventory: successful bootstrap depth changed",
            )
            require(
                isinstance(counts["bootstrap_failed_draw_count"], int)
                and counts["bootstrap_failed_draw_count"] >= 0
                and counts["bootstrap_successful_draw_count"]
                + counts["bootstrap_failed_draw_count"]
                == counts["bootstrap_draw_count"],
                "blind.inventory: bootstrap counts are inconsistent",
            )
            require(
                isinstance(counts["declared_variant_count"], int)
                and counts["declared_variant_count"] >= 1,
                "blind.inventory: invalid declared variant count",
            )
            require(
                isinstance(counts["accepted_variant_count"], int)
                and counts["accepted_variant_count"] >= 1,
                "blind.inventory: invalid accepted variant count",
            )
            for key in (
                "analysis_report_digest",
                "run_manifest_digest",
                "environment_digest",
                "scheduler_inventory_digest",
            ):
                require(
                    is_hex(counts[key], HEX_SHA256_LENGTH),
                    f"blind.inventory: invalid {key}",
                )
    return record


def run_arithmetic_candidate(candidate: Path, input_path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(candidate), str(input_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def compare_arithmetic(
    observed: dict[str, Any],
    expected: dict[str, Any],
    *,
    label: str,
) -> None:
    require(set(observed) == set(expected), f"{label} output keys differ")
    for key, wanted in expected.items():
        actual = observed[key]
        if isinstance(wanted, float):
            require(
                math.isclose(actual, wanted, rel_tol=1e-10, abs_tol=1e-12),
                f"{label} disagrees on {key}",
            )
        else:
            require(actual == wanted, f"{label} disagrees on {key}")


def independent_arithmetic_check(
    repo: Path,
    input_path: Path,
    expected: dict[str, Any],
    candidate_hash: str,
    validator_hash: str,
) -> None:
    candidate = repo / "final-arithmetic" / "candidate.py"
    reference = (
        repo
        / "research"
        / "validator"
        / "reference_candidate"
        / "candidate.py"
    )
    require(candidate.is_file(), "arithmetic candidate is missing")
    require(reference.is_file(), "arithmetic reference validator is missing")
    require(sha256(candidate) == candidate_hash, "arithmetic candidate hash mismatch")
    require(sha256(reference) == validator_hash, "arithmetic validator hash mismatch")
    observed_candidate = run_arithmetic_candidate(candidate, input_path)
    observed_reference = run_arithmetic_candidate(reference, input_path)
    compare_arithmetic(
        observed_candidate,
        expected,
        label="arithmetic candidate",
    )
    compare_arithmetic(
        observed_reference,
        expected,
        label="arithmetic reference validator",
    )
    compare_arithmetic(
        observed_candidate,
        observed_reference,
        label="candidate/reference comparison",
    )


def write_cross_method_csv(path: Path, detail: dict[str, Any]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "lattice",
                "method",
                "observable",
                "value",
                "sigma_total",
                "comparison_z",
                "tag",
            ),
        )
        writer.writeheader()
        for lattice in LATTICES:
            z_key = "triangle_z" if lattice == "triangular" else "honeycomb_z"
            z_score = detail["independence"][z_key]
            tag = "Agreement" if z_score <= 2.0 else "Disagreement"
            for method, key in (
                (detail["primary_implementation_id"], "primary_fields"),
                (
                    detail["independent_implementation_id"],
                    "independent_fields",
                ),
            ):
                estimate = detail[key][lattice]
                writer.writerow(
                    {
                        "lattice": lattice,
                        "method": method,
                        "observable": "critical_field_over_J",
                        "value": f"{estimate['value']:.17g}",
                        "sigma_total": f"{estimate['sigma_total']:.17g}",
                        "comparison_z": f"{z_score:.17g}",
                        "tag": tag,
                    }
                )


def validate_verdict_record(value: Any) -> dict[str, Any]:
    record = require_exact_keys(
        value,
        {
            "schema_version",
            "freeze_commit",
            "opened_at",
            "triangle",
            "honeycomb",
            "ratio",
            "delta_sqrt5",
            "z_sqrt5",
            "independent_route",
            "precision_gate",
            "robustness_gate",
            "verdict",
        },
        path="verdict",
    )
    require(record["schema_version"] == VERDICT_SCHEMA, "verdict: unexpected schema")
    require(
        is_hex(record["freeze_commit"], HEX_COMMIT_LENGTH),
        "verdict.freeze_commit: invalid",
    )
    require(
        isinstance(record["opened_at"], str) and record["opened_at"],
        "verdict.opened_at: invalid",
    )
    for key in ("triangle", "honeycomb", "ratio"):
        estimate = require_exact_keys(
            record[key],
            {"value", "sigma_stat", "sigma_sys", "sigma_total"},
            path=f"verdict.{key}",
        )
        finite_number(estimate["value"], f"verdict.{key}.value", positive=True)
        for uncertainty_key in ("sigma_stat", "sigma_sys", "sigma_total"):
            observed = finite_number(
                estimate[uncertainty_key],
                f"verdict.{key}.{uncertainty_key}",
            )
            require(
                observed >= 0.0,
                f"verdict.{key}.{uncertainty_key}: expected nonnegative",
            )
        require(
            math.isclose(
                estimate["sigma_total"],
                math.hypot(estimate["sigma_stat"], estimate["sigma_sys"]),
                rel_tol=1e-12,
                abs_tol=1e-15,
            ),
            f"verdict.{key}: total uncertainty mismatch",
        )
    finite_number(record["delta_sqrt5"], "verdict.delta_sqrt5")
    finite_number(record["z_sqrt5"], "verdict.z_sqrt5")
    independence = require_exact_keys(
        record["independent_route"],
        {"passed", "triangle_z", "honeycomb_z", "same_delta_sign"},
        path="verdict.independent_route",
    )
    require(
        isinstance(independence["passed"], bool)
        and isinstance(independence["same_delta_sign"], bool),
        "verdict.independent_route: expected Boolean gates",
    )
    for key in ("triangle_z", "honeycomb_z"):
        observed = finite_number(
            independence[key],
            f"verdict.independent_route.{key}",
        )
        require(observed >= 0.0, f"verdict.independent_route.{key}: negative")
    require(
        isinstance(record["precision_gate"], bool)
        and isinstance(record["robustness_gate"], bool),
        "verdict: expected Boolean gates",
    )
    require(
        record["verdict"]
        in {
            "evidence-against",
            "survives-numerical-test",
            "inconclusive",
        },
        "verdict.verdict: invalid class",
    )
    return record


def write_sha256sums(directory: Path) -> None:
    checksum_path = directory / "SHA256SUMS"
    lines = [
        f"{sha256(path)}  {path.name}"
        for path in sorted(directory.iterdir())
        if path.is_file() and path != checksum_path
    ]
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_blind_checksums(blind_path: Path) -> None:
    checksum_path = blind_path.parent / "SHA256SUMS"
    require(checksum_path.is_file(), "blind SHA256SUMS is missing")
    lines = [
        line.strip()
        for line in checksum_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    expected = f"{sha256(blind_path)}  {blind_path.name}"
    require(lines == [expected], "blind SHA256SUMS mismatch")


def blind(args: argparse.Namespace) -> int:
    repo = args.repo.resolve()
    bundle_path = confined_bundle_path(args.bundle, repo)
    out_dir = confined_result_path(args.out_dir, repo)
    raw = load_json(bundle_path)
    bundle = validate_bundle(raw)
    git_state(repo, bundle["freeze_commit"])
    candidate = repo / "research" / "validator" / "reference_candidate" / "candidate.py"
    arithmetic_candidate = repo / "final-arithmetic" / "candidate.py"
    require(candidate.is_file(), "arithmetic validator candidate is missing")
    require(arithmetic_candidate.is_file(), "arithmetic candidate is missing")
    candidate_hash = sha256(candidate)
    arithmetic_candidate_hash = sha256(arithmetic_candidate)
    require(
        candidate_hash == bundle["arithmetic_validator_sha256"],
        "arithmetic validator hash differs from frozen bundle",
    )
    require(
        arithmetic_candidate_hash == bundle["arithmetic_candidate_sha256"],
        "arithmetic candidate hash differs from frozen bundle",
    )
    require_new_directory(out_dir)
    record = build_blind_record(
        bundle,
        bundle_sha256=sha256(bundle_path),
        arithmetic_validator_sha256=candidate_hash,
        arithmetic_candidate_sha256=arithmetic_candidate_hash,
    )
    validate_blind_record(record)
    write_json(out_dir / "blind-record.json", record)
    write_sha256sums(out_dir)
    print("blind gates passed; central values remain sealed")
    return 0


def open_bundle(args: argparse.Namespace) -> int:
    repo = args.repo.resolve()
    bundle_path = confined_bundle_path(args.bundle, repo)
    blind_path = confined_bundle_path(args.blind_record, repo)
    out_dir = confined_result_path(args.out_dir, repo)
    raw = load_json(bundle_path)
    bundle = validate_bundle(raw)
    require(
        args.freeze_commit == bundle["freeze_commit"],
        "--freeze-commit differs from input bundle",
    )
    git_state(repo, args.freeze_commit)
    record = validate_blind_record(load_json(blind_path))
    verify_blind_checksums(blind_path)
    require(
        record["source_freeze_commit"] == args.freeze_commit,
        "blind record freeze commit mismatch",
    )
    require(
        record["bundle_digest"] == sha256(bundle_path),
        "input bundle changed after blind gate",
    )
    require(
        record["source_freeze_digest"]
        == bundle["preregistration_sha256"],
        "preregistration digest changed after blind gate",
    )
    require(
        record["arithmetic_candidate_digest"]
        == bundle["arithmetic_candidate_sha256"],
        "arithmetic candidate changed after blind gate",
    )
    require(
        record["arithmetic_validator_digest"]
        == bundle["arithmetic_validator_sha256"],
        "arithmetic validator changed after blind gate",
    )
    require(
        record["inventory"] == inventory(bundle),
        "blind inventory changed after blind gate",
    )
    require_new_directory(out_dir)
    compact, detail = candidate_input(bundle)
    solved = solve_candidate(compact)
    input_path = out_dir / "verdict-input.json"
    write_json(input_path, compact)
    independent_arithmetic_check(
        repo,
        input_path,
        solved,
        bundle["arithmetic_candidate_sha256"],
        bundle["arithmetic_validator_sha256"],
    )
    triangle = detail["primary_fields"]["triangular"]
    honeycomb = detail["primary_fields"]["honeycomb"]
    ratio = {
        "value": solved["ratio"],
        "sigma_stat": detail["ratio_sigma_stat"],
        "sigma_sys": solved["ratio_sigma_sys"],
        "sigma_total": solved["ratio_sigma_total"],
    }
    verdict = {
        "schema_version": VERDICT_SCHEMA,
        "freeze_commit": args.freeze_commit,
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "triangle": triangle,
        "honeycomb": honeycomb,
        "ratio": ratio,
        "delta_sqrt5": solved["delta_sqrt5"],
        "z_sqrt5": solved["z_abs"],
        "independent_route": detail["independence"],
        "precision_gate": solved["precision_gate"],
        "robustness_gate": (
            solved["robust_against"] or solved["robust_survives"]
        ),
        "verdict": solved["verdict"],
    }
    validate_verdict_record(verdict)
    write_json(out_dir / "verdict.json", verdict)
    write_json(
        out_dir / "joint-robustness.json",
        {
            "systematic_rule": (
                "maximum absolute primary-ratio shift over the Cartesian "
                "product of all accepted predeclared lattice variants"
            ),
            "primary_ratio_bootstrap_counts": detail[
                "ratio_bootstrap_counts"
            ],
            "independent_ratio_bootstrap_counts": detail[
                "independent_ratio_bootstrap_counts"
            ],
            "ratio_sigma_systematic": detail["ratio_sigma_systematic"],
            "joint_variants": detail["joint_variants"],
            "robust_against": solved["robust_against"],
            "robust_survives": solved["robust_survives"],
        },
    )
    write_cross_method_csv(out_dir / "cross-method-check.csv", detail)
    write_sha256sums(out_dir)
    print(f"opened once: verdict={solved['verdict']}")
    return 0


def parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[1]
    result = argparse.ArgumentParser()
    subparsers = result.add_subparsers(dest="command", required=True)

    blind_parser = subparsers.add_parser("blind")
    blind_parser.add_argument("--bundle", type=Path, required=True)
    blind_parser.add_argument("--repo", type=Path, default=root)
    blind_parser.add_argument("--out-dir", type=Path, required=True)
    blind_parser.set_defaults(handler=blind)

    open_parser = subparsers.add_parser("open")
    open_parser.add_argument("--bundle", type=Path, required=True)
    open_parser.add_argument("--blind-record", type=Path, required=True)
    open_parser.add_argument("--freeze-commit", required=True)
    open_parser.add_argument("--repo", type=Path, default=root)
    open_parser.add_argument("--out-dir", type=Path, required=True)
    open_parser.set_defaults(handler=open_bundle)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.handler(args)
    except (
        GateError,
        OSError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"blocked: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
