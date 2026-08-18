#!/usr/bin/env python3
"""Strict low-statistics Blöte--Deng triangular baseline analyzer.

The run specification is the only source of scientific settings.  In
particular, the estimator, scan roster, fit windows, exponent values, model
terms, variants, bootstrap configuration, and acceptance thresholds are read
from the embedded ``analysis`` and ``acceptance_gate`` objects.  Command-line
arguments only identify the frozen input and the output directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


REPORT_SCHEMA = "yanwang148.triangular-baseline-pilot.v1"
FIT_SCHEMA = "yanwang148.fit.v2"
CELL_SCHEMA = "yanwang148.beta-cell.v2"
SCHEDULER_SCHEMA = "yanwang148.scheduler-manifest.v2"
PRIMARY_ESTIMATOR = "spacetime_binder_q"
DIAGNOSTIC_ESTIMATOR = "equal_time_binder_q"
ALLOWED_TERMS = ("a1", "a2", "a3", "b1", "b2", "c1")
HISTORICAL_Y_2 = -1.963
ALLOWED_CLASSIFICATIONS = (
    "primary",
    "systematic-variant",
    "crossing-check",
    "rejected-variant",
)
ALLOWED_SBATCH_SCRIPTS = (
    "scripts/run-triangular-baseline-600k-packed-array.sbatch",
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class AnalysisInputError(ValueError):
    """A fail-closed input, roster, provenance, or numerical error."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_seed(base_seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{base_seed}|{label}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def finite_float(value: Any, label: str, *, positive: bool = False) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exception:
        raise AnalysisInputError(f"{label}:not-numeric") from exception
    if not math.isfinite(result):
        raise AnalysisInputError(f"{label}:nonfinite")
    if positive and result <= 0:
        raise AnalysisInputError(f"{label}:nonpositive")
    return result


def positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise AnalysisInputError(f"{label}:not-integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exception:
        raise AnalysisInputError(f"{label}:not-integer") from exception
    if result <= 0 or float(value) != result:
        raise AnalysisInputError(f"{label}:not-positive-integer")
    return result


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )


def load_strict_json_bytes(payload: bytes, label: str) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise AnalysisInputError(f"{label}:nonfinite-json-number:{value}")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AnalysisInputError(f"{label}:duplicate-json-key:{key}")
            result[key] = value
        return result

    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError as exception:
        raise AnalysisInputError(f"{label}:not-utf8") from exception
    try:
        record = json.loads(
            decoded,
            parse_constant=reject_constant,
            object_pairs_hook=unique_object,
        )
    except json.JSONDecodeError as exception:
        raise AnalysisInputError(f"{label}:invalid-json:{exception}") from exception
    if not isinstance(record, dict):
        raise AnalysisInputError(f"{label}:root-not-object")
    return record


def axis(scan_axes: dict[str, Any], primary: str, alias: str) -> list[Any]:
    has_primary = primary in scan_axes
    has_alias = alias in scan_axes
    if has_primary and has_alias and scan_axes[primary] != scan_axes[alias]:
        raise AnalysisInputError(f"scan_axes:{primary}-alias-conflict")
    if has_primary:
        values = scan_axes[primary]
    elif has_alias:
        values = scan_axes[alias]
    else:
        raise AnalysisInputError(f"scan_axes:missing-{primary}")
    if not isinstance(values, list) or not values:
        raise AnalysisInputError(f"scan_axes:{primary}-must-be-nonempty-list")
    return values


def _regularized_gamma_q(a: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(a, x), using stdlib arithmetic."""

    if not (a > 0 and x >= 0 and math.isfinite(a) and math.isfinite(x)):
        return 0.0
    if x == 0:
        return 1.0
    eps = 3.0e-14
    tiny = 1.0e-300
    log_prefactor = -x + a * math.log(x) - math.lgamma(a)
    if x < a + 1.0:
        term = 1.0 / a
        total = term
        ap = a
        for _ in range(10000):
            ap += 1.0
            term *= x / ap
            total += term
            if abs(term) <= abs(total) * eps:
                break
        p_value = total * math.exp(log_prefactor)
        return min(1.0, max(0.0, 1.0 - p_value))

    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / max(abs(b), tiny)
    if b < 0:
        d = -d
    result = d
    for index in range(1, 10001):
        an = -index * (index - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        result *= delta
        if abs(delta - 1.0) <= eps:
            break
    q_value = math.exp(log_prefactor) * result
    return min(1.0, max(0.0, q_value))


def chi_square_survival(chi2: float, dof: int) -> float:
    if dof <= 0 or not math.isfinite(chi2) or chi2 < 0:
        return 0.0
    return _regularized_gamma_q(0.5 * dof, 0.5 * chi2)


def validate_frozen_plan(
    spec: dict[str, Any], source_plan: dict[str, Any]
) -> dict[str, Any]:
    errors: list[str] = []
    analysis = spec.get("analysis")
    gate = spec.get("acceptance_gate")
    scan_axes = source_plan.get("scan_axes")
    settings = spec.get("settings")
    provenance = spec.get("provenance")
    if not isinstance(analysis, dict):
        errors.append("analysis:missing-or-invalid")
        analysis = {}
    if not isinstance(gate, dict):
        errors.append("acceptance_gate:missing-or-invalid")
        gate = {}
    if not isinstance(scan_axes, dict):
        errors.append("scan_axes:missing-or-invalid")
        scan_axes = {}
    if not isinstance(settings, dict):
        errors.append("settings:missing-or-invalid")
        settings = {}
    if not isinstance(provenance, dict):
        errors.append("provenance:missing-or-invalid")
        provenance = {}

    try:
        scan_sizes = [positive_int(value, "scan_axes.L") for value in axis(scan_axes, "L", "sizes")]
        scan_fields = [
            finite_float(value, "scan_axes.h", positive=True)
            for value in axis(scan_axes, "h", "fields")
        ]
        scan_seeds = [
            positive_int(value, "scan_axes.seed")
            for value in axis(scan_axes, "seed", "seeds")
        ]
    except AnalysisInputError as exception:
        errors.append(str(exception))
        scan_sizes, scan_fields, scan_seeds = [], [], []

    def analysis_list(key: str, converter) -> list[Any]:
        values = analysis.get(key)
        if not isinstance(values, list) or not values:
            errors.append(f"analysis.{key}:missing-or-invalid")
            return []
        converted = []
        for value in values:
            try:
                converted.append(converter(value, f"analysis.{key}"))
            except AnalysisInputError as exception:
                errors.append(str(exception))
        return converted

    sizes = analysis_list("sizes", positive_int)
    fields = analysis_list(
        "fields", lambda value, label: finite_float(value, label, positive=True)
    )
    seeds = analysis_list("seeds", positive_int)
    if sizes != scan_sizes:
        errors.append("analysis.sizes:scan-axes-mismatch")
    if fields != scan_fields:
        errors.append("analysis.fields:scan-axes-mismatch")
    if seeds != scan_seeds:
        errors.append("analysis.seeds:scan-axes-mismatch")
    if len(set(sizes)) != len(sizes) or sizes != sorted(sizes):
        errors.append("analysis.sizes:not-unique-sorted")
    if len(set(fields)) != len(fields) or fields != sorted(fields):
        errors.append("analysis.fields:not-unique-sorted")
    if len(set(seeds)) != len(seeds) or seeds != sorted(seeds):
        errors.append("analysis.seeds:not-unique-sorted")

    if analysis.get("estimator_id") != PRIMARY_ESTIMATOR:
        errors.append("analysis.estimator_id:must-be-spacetime")
    if analysis.get("diagnostic_estimator_id") != DIAGNOSTIC_ESTIMATOR:
        errors.append("analysis.diagnostic_estimator_id:invalid")
    if settings.get("lattice_name") != "triangular":
        errors.append("settings.lattice_name:must-be-triangular")
    if settings.get("beta_policy") != "beta_h_equals_L":
        errors.append("settings.beta_policy:must-be-beta-h-equals-L")
    try:
        if finite_float(settings.get("J"), "settings.J", positive=True) != 1.0:
            errors.append("settings.J:must-equal-one")
    except AnalysisInputError as exception:
        errors.append(str(exception))
    for key in (
        "measurement_sweeps",
        "thermalization_sweeps",
        "bin_size",
        "string_length_padding",
    ):
        try:
            positive_int(settings.get(key), f"settings.{key}")
        except AnalysisInputError as exception:
            errors.append(str(exception))
    try:
        finite_float(
            settings.get("string_length_scale"),
            "settings.string_length_scale",
            positive=True,
        )
    except AnalysisInputError as exception:
        errors.append(str(exception))

    windows: dict[str, list[float]] = {}
    for name, key in (
        ("primary", "primary_field_window"),
        ("outer", "crossing_field_window"),
    ):
        raw_window = analysis.get(key)
        try:
            if not isinstance(raw_window, list) or len(raw_window) < 2:
                raise AnalysisInputError(f"analysis.{key}:invalid")
            selected = [
                finite_float(value, f"analysis.{key}", positive=True)
                for value in raw_window
            ]
            if selected != sorted(selected) or len(set(selected)) != len(selected):
                raise AnalysisInputError(
                    f"analysis.{key}:not-unique-sorted"
                )
            if any(field not in fields for field in selected):
                raise AnalysisInputError(
                    f"analysis.{key}:outside-frozen-field-axis"
                )
            windows[name] = selected
        except AnalysisInputError as exception:
            errors.append(str(exception))
    if windows.get("outer") != fields:
        errors.append("analysis.crossing_field_window:must-equal-field-axis")
    if (
        "primary" in windows
        and "outer" in windows
        and any(field not in windows["outer"] for field in windows["primary"])
    ):
        errors.append("analysis.primary_field_window:not-subset-of-crossing")

    try:
        y_t = finite_float(analysis.get("y_t"), "analysis.y_t")
        y_i = finite_float(analysis.get("y_i"), "analysis.y_i")
        y_2 = finite_float(analysis.get("y_2"), "analysis.y_2")
    except AnalysisInputError as exception:
        errors.append(str(exception))
        y_t, y_i, y_2 = 0.0, 0.0, 0.0
    if not math.isclose(y_t, 1.587, rel_tol=0.0, abs_tol=1e-12):
        errors.append("analysis.y_t:must-equal-historical-value")
    if not math.isclose(y_i, -0.815, rel_tol=0.0, abs_tol=1e-12):
        errors.append("analysis.y_i:must-equal-historical-value")
    if not math.isclose(
        y_2, HISTORICAL_Y_2, rel_tol=0.0, abs_tol=1e-12
    ):
        errors.append("analysis.y_2:must-equal-3-minus-2-y_h")
    primary_terms = analysis.get("primary_terms")
    if primary_terms != ["a1", "a2", "a3", "b1", "b2"]:
        errors.append("analysis.primary_terms:not-historical-triangular-table1")

    try:
        bootstrap_resamples = positive_int(
            analysis.get("bootstrap_resamples"),
            "analysis.bootstrap_resamples",
        )
        bootstrap_seed = positive_int(
            analysis.get("bootstrap_seed"), "analysis.bootstrap_seed"
        )
        crossing_bootstrap_resamples = positive_int(
            analysis.get("crossing_bootstrap_resamples"),
            "analysis.crossing_bootstrap_resamples",
        )
        crossing_bootstrap_seed = positive_int(
            analysis.get("crossing_bootstrap_seed"),
            "analysis.crossing_bootstrap_seed",
        )
        profile_grid_points = positive_int(
            analysis.get("profile_grid_points", 41),
            "analysis.profile_grid_points",
        )
        if profile_grid_points < 9:
            errors.append("analysis.profile_grid_points:must-be-at-least-nine")
    except AnalysisInputError as exception:
        errors.append(str(exception))
        (
            bootstrap_resamples,
            bootstrap_seed,
            crossing_bootstrap_resamples,
            crossing_bootstrap_seed,
            profile_grid_points,
        ) = (0, 0, 0, 0, 0)
    if analysis.get("covariance_estimator") != "independent-chain-diagonal":
        errors.append("analysis.covariance_estimator:unsupported")
    if (
        analysis.get("optimizer")
        != "bounded coarse-grid plus golden-section profile WLS v1"
    ):
        errors.append("analysis.optimizer:unsupported")
    if (
        analysis.get("pooling_rule")
        != "max(within-chain standard error, between-chain standard error)"
    ):
        errors.append("analysis.pooling_rule:unsupported")
    if (
        analysis.get("bootstrap_method")
        != (
            "replica-resample plus within-chain Gaussian draw and full "
            "profile refit"
        )
    ):
        errors.append("analysis.bootstrap_method:unsupported")
    coverage_campaign_id = analysis.get("coverage_campaign_id")
    if not isinstance(coverage_campaign_id, str) or not coverage_campaign_id:
        errors.append("analysis.coverage_campaign_id:missing")
    elif coverage_campaign_id != "pending-production-coverage-campaign":
        errors.append("analysis.coverage_campaign_id:must-remain-pending")
    coverage_passed = analysis.get("coverage_passed")
    if not isinstance(coverage_passed, bool):
        errors.append("analysis.coverage_passed:must-be-boolean")
    elif coverage_passed:
        errors.append("analysis.coverage_passed:pilot-must-remain-false")

    variants = analysis.get("variants")
    if not isinstance(variants, list):
        errors.append("analysis.variants:must-be-list")
        variants = []
    variant_ids: set[str] = set()
    normalized_variants = []
    allowed_discard_reasons = {
        "preregistered-Lmin-variant",
        "preregistered-leave-one-size-out",
    }
    for index, variant in enumerate(variants):
        prefix = f"analysis.variants[{index}]"
        if not isinstance(variant, dict):
            errors.append(f"{prefix}:not-object")
            continue
        fit_id = variant.get("fit_id")
        classification = variant.get("classification")
        variant_sizes = variant.get("sizes")
        window_name = variant.get("field_window")
        terms = variant.get("terms")
        discard_reason = variant.get("discard_reason")
        if (
            not isinstance(fit_id, str)
            or not SAFE_ID_PATTERN.fullmatch(fit_id)
            or fit_id in variant_ids
        ):
            errors.append(f"{prefix}.fit_id:invalid-or-duplicate")
            continue
        variant_ids.add(fit_id)
        if classification not in ALLOWED_CLASSIFICATIONS[1:]:
            errors.append(f"{prefix}.classification:invalid")
        if (
            not isinstance(variant_sizes, list)
            or not variant_sizes
            or any(value not in sizes for value in variant_sizes)
            or len(set(variant_sizes)) != len(variant_sizes)
            or variant_sizes != sorted(variant_sizes)
        ):
            errors.append(f"{prefix}.sizes:invalid")
        if window_name not in windows:
            errors.append(f"{prefix}.field_window:invalid")
        if (
            not isinstance(terms, list)
            or len(set(terms)) != len(terms)
            or any(term not in ALLOWED_TERMS for term in terms)
        ):
            errors.append(f"{prefix}.terms:invalid")
        if isinstance(variant_sizes, list) and variant_sizes != sizes:
            if discard_reason not in allowed_discard_reasons:
                errors.append(f"{prefix}.discard_reason:missing-or-invalid")
        elif discard_reason is not None:
            errors.append(f"{prefix}.discard_reason:unexpected")
        try:
            variant_y_t = finite_float(variant.get("y_t"), f"{prefix}.y_t")
            variant_y_i = finite_float(variant.get("y_i"), f"{prefix}.y_i")
            variant_y_2 = finite_float(
                variant.get("y_2", y_2), f"{prefix}.y_2"
            )
        except AnalysisInputError as exception:
            errors.append(str(exception))
            variant_y_t, variant_y_i, variant_y_2 = 0.0, 0.0, 0.0
        normalized_variants.append(
            {
                "fit_id": fit_id,
                "classification": classification,
                "sizes": variant_sizes if isinstance(variant_sizes, list) else [],
                "field_window": window_name,
                "terms": terms if isinstance(terms, list) else [],
                "y_t": variant_y_t,
                "y_i": variant_y_i,
                "y_2": variant_y_2,
                "discard_reason": discard_reason,
            }
        )
    primary_fit_id = analysis.get("primary_fit_id")
    if (
        not isinstance(primary_fit_id, str)
        or not SAFE_ID_PATTERN.fullmatch(primary_fit_id)
    ):
        errors.append("analysis.primary_fit_id:missing-or-invalid")
    elif primary_fit_id in variant_ids:
        errors.append("analysis.primary_fit_id:duplicates-variant")
    robustness_required_fit_ids = analysis.get("robustness_required_fit_ids")
    if (
        not isinstance(robustness_required_fit_ids, list)
        or not robustness_required_fit_ids
        or len(set(robustness_required_fit_ids))
        != len(robustness_required_fit_ids)
        or any(
            not isinstance(fit_id, str) or fit_id not in variant_ids
            for fit_id in robustness_required_fit_ids
        )
    ):
        errors.append("analysis.robustness_required_fit_ids:invalid")
        robustness_required_fit_ids = []

    gate_fields = (
        "aspect_tolerance",
        "minimum_sign",
        "maximum_string_fill",
        "max_covariance_condition",
        "min_degrees_of_freedom",
        "min_p_value",
        "max_bootstrap_failed_fraction",
        "max_crossing_chi2_per_dof",
        "reference_hc",
        "reference_hc_sigma",
        "max_reference_z",
        "max_hc_sigma_stat",
        "reference_q_star",
        "reference_q_star_sigma",
        "max_q_star_reference_z",
        "max_variant_shift_paired_sigma",
    )
    normalized_gate: dict[str, Any] = {}
    for key in gate_fields:
        try:
            normalized_gate[key] = finite_float(gate.get(key), f"acceptance_gate.{key}")
        except AnalysisInputError as exception:
            errors.append(str(exception))
            normalized_gate[key] = 0.0
    if normalized_gate["aspect_tolerance"] < 0:
        errors.append("acceptance_gate.aspect_tolerance:negative")
    if not 0 <= normalized_gate["minimum_sign"] <= 1:
        errors.append("acceptance_gate.minimum_sign:outside-unit-interval")
    if not 0 < normalized_gate["maximum_string_fill"] <= 1:
        errors.append(
            "acceptance_gate.maximum_string_fill:outside-unit-interval"
        )
    if normalized_gate["max_covariance_condition"] < 1:
        errors.append("acceptance_gate.max_covariance_condition:below-one")
    if normalized_gate["min_p_value"] < 0 or normalized_gate["min_p_value"] > 1:
        errors.append("acceptance_gate.min_p_value:outside-unit-interval")
    if (
        normalized_gate["max_bootstrap_failed_fraction"] < 0
        or normalized_gate["max_bootstrap_failed_fraction"] > 1
    ):
        errors.append(
            "acceptance_gate.max_bootstrap_failed_fraction:outside-unit-interval"
        )
    try:
        normalized_gate["min_degrees_of_freedom"] = positive_int(
            gate.get("min_degrees_of_freedom"),
            "acceptance_gate.min_degrees_of_freedom",
        )
    except AnalysisInputError as exception:
        errors.append(str(exception))
        normalized_gate["min_degrees_of_freedom"] = 0
    try:
        normalized_gate["expected_cell_count"] = positive_int(
            gate.get("expected_cell_count"),
            "acceptance_gate.expected_cell_count",
        )
        normalized_gate["minimum_rebin_count"] = positive_int(
            gate.get("minimum_rebin_count"),
            "acceptance_gate.minimum_rebin_count",
        )
    except AnalysisInputError as exception:
        errors.append(str(exception))
        normalized_gate["expected_cell_count"] = 0
        normalized_gate["minimum_rebin_count"] = 0
    expected_cell_count = len(sizes) * len(fields) * len(seeds)
    if normalized_gate["expected_cell_count"] != expected_cell_count:
        errors.append("acceptance_gate.expected_cell_count:roster-mismatch")
    for key in (
        "require_all_adjacent_crossings",
        "require_positive_crossing_slope",
        "require_complete_bootstrap_attempts",
    ):
        if not isinstance(gate.get(key), bool):
            errors.append(f"acceptance_gate.{key}:must-be-boolean")
        normalized_gate[key] = gate.get(key) is True
    if gate.get("production_data") is not False:
        errors.append("acceptance_gate.production_data:must-be-false")
    if gate.get("production_gate") != "locked":
        errors.append("acceptance_gate.production_gate:must-be-locked")
    try:
        if not math.isclose(
            finite_float(
                settings.get("aspect_tolerance"),
                "settings.aspect_tolerance",
            ),
            normalized_gate["aspect_tolerance"],
            rel_tol=0.0,
            abs_tol=0.0,
        ):
            errors.append("settings.aspect_tolerance:gate-mismatch")
        if not math.isclose(
            finite_float(
                settings.get("maximum_string_fill"),
                "settings.maximum_string_fill",
            ),
            normalized_gate["maximum_string_fill"],
            rel_tol=0.0,
            abs_tol=0.0,
        ):
            errors.append("settings.maximum_string_fill:gate-mismatch")
        if positive_int(
            settings.get("minimum_rebin_count"),
            "settings.minimum_rebin_count",
        ) != normalized_gate["minimum_rebin_count"]:
            errors.append("settings.minimum_rebin_count:gate-mismatch")
    except AnalysisInputError as exception:
        errors.append(str(exception))

    source_commit = provenance.get("source_commit")
    if not isinstance(source_commit, str) or not COMMIT_PATTERN.fullmatch(
        source_commit
    ):
        errors.append("provenance.source_commit:invalid")
    sbatch_key = analysis.get("sbatch_sha256_key", "baseline_sbatch_sha256")
    if sbatch_key != "baseline_sbatch_sha256":
        errors.append("analysis.sbatch_sha256_key:must-be-baseline-sbatch-sha256")
    sbatch_sha256 = provenance.get(sbatch_key)
    if (
        not isinstance(sbatch_key, str)
        or not isinstance(sbatch_sha256, str)
        or not SHA256_PATTERN.fullmatch(sbatch_sha256)
    ):
        errors.append("provenance.baseline-sbatch-sha256:invalid")
    if settings.get("phase") != "pilot":
        errors.append("settings.phase:must-be-pilot")
    if provenance.get("phase") != "pilot":
        errors.append("provenance.phase:must-be-pilot")
    if provenance.get("production_data") is not False:
        errors.append("provenance.production_data:must-be-false")

    return {
        "passed": not errors,
        "errors": sorted(set(errors)),
        "analysis": {
            "sizes": sizes,
            "fields": fields,
            "seeds": seeds,
            "windows": windows,
            "y_t": y_t,
            "y_i": y_i,
            "y_2": y_2,
            "primary_terms": primary_terms,
            "bootstrap_resamples": bootstrap_resamples,
            "bootstrap_seed": bootstrap_seed,
            "crossing_bootstrap_resamples": crossing_bootstrap_resamples,
            "crossing_bootstrap_seed": crossing_bootstrap_seed,
            "profile_grid_points": profile_grid_points,
            "bootstrap_method": analysis.get("bootstrap_method"),
            "coverage_campaign_id": coverage_campaign_id,
            "coverage_passed": coverage_passed is True,
            "variants": normalized_variants,
            "primary_fit_id": primary_fit_id,
            "robustness_required_fit_ids": robustness_required_fit_ids,
            "optimizer": analysis.get("optimizer"),
            "sbatch_sha256_key": sbatch_key,
        },
        "gate": normalized_gate,
        "source_commit": source_commit,
        "sbatch_sha256": sbatch_sha256,
    }


def project_root_for_run(run_dir: Path, declared_run_dir: Any) -> Path:
    if not isinstance(declared_run_dir, str) or not declared_run_dir:
        raise AnalysisInputError("run_dir:missing-or-invalid")
    declared = Path(declared_run_dir)
    if declared.is_absolute() or ".." in declared.parts:
        raise AnalysisInputError("run_dir:must-be-safe-relative-path")
    root = run_dir.resolve()
    for _ in declared.parts:
        root = root.parent
    if (root / declared).resolve() != run_dir.resolve():
        raise AnalysisInputError("run_dir:does-not-match-run-spec-location")
    return root


def load_bound_source_plan(
    spec: dict[str, Any], run_spec_path: Path
) -> tuple[dict[str, Any], Path, str]:
    expected_spec_keys = {
        "schema_version",
        "run_id",
        "run_dir",
        "settings",
        "cells",
        "analysis",
        "acceptance_gate",
        "provenance",
    }
    if set(spec) != expected_spec_keys:
        missing = sorted(expected_spec_keys - set(spec))
        extra = sorted(set(spec) - expected_spec_keys)
        raise AnalysisInputError(
            f"run_spec:root-shape:missing={missing}:extra={extra}"
        )
    provenance = spec.get("provenance")
    if not isinstance(provenance, dict):
        raise AnalysisInputError("provenance:missing-or-invalid")
    source_plan_path = provenance.get("source_plan_path")
    source_plan_sha256 = provenance.get("source_plan_sha256")
    if not isinstance(source_plan_path, str) or not source_plan_path:
        raise AnalysisInputError("provenance.source_plan_path:missing-or-invalid")
    if (
        not isinstance(source_plan_sha256, str)
        or not SHA256_PATTERN.fullmatch(source_plan_sha256)
    ):
        raise AnalysisInputError("provenance.source_plan_sha256:invalid")
    relative = Path(source_plan_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise AnalysisInputError("provenance.source_plan_path:unsafe")

    run_dir = run_spec_path.parent.resolve()
    project_root = project_root_for_run(run_dir, spec.get("run_dir"))
    source_candidate = project_root / relative
    source_path = source_candidate.resolve()
    expected_path = (run_dir / "run.json").resolve()
    if source_path != expected_path:
        raise AnalysisInputError(
            "provenance.source_plan_path:must-name-run-directory-run-json"
        )
    if source_candidate.is_symlink() or not source_path.is_file():
        raise AnalysisInputError("provenance.source_plan_path:missing-or-symlink")
    source_bytes = source_path.read_bytes()
    observed_sha256 = sha256_bytes(source_bytes)
    if observed_sha256 != source_plan_sha256:
        raise AnalysisInputError("provenance.source_plan_sha256:mismatch")
    source_plan = load_strict_json_bytes(source_bytes, "source-plan")
    if source_plan.get("schema_version") != "yanwang148.reproduction-run.v1":
        raise AnalysisInputError("source-plan:schema_version:unsupported")
    if source_plan.get("status") != "proposal-frozen":
        raise AnalysisInputError("source-plan:status:not-frozen")

    bound_fields = (
        "schema_version",
        "run_id",
        "run_dir",
        "settings",
        "cells",
        "analysis",
        "acceptance_gate",
    )
    for key in bound_fields:
        if source_plan.get(key) != spec.get(key):
            raise AnalysisInputError(f"source-plan:{key}:execution-view-mismatch")
    source_provenance = source_plan.get("provenance")
    if not isinstance(source_provenance, dict):
        raise AnalysisInputError("source-plan:provenance:missing-or-invalid")
    derived_keys = {
        "source_commit",
        "source_plan_path",
        "source_plan_sha256",
    }
    if derived_keys & set(source_provenance):
        raise AnalysisInputError("source-plan:contains-derived-provenance")
    sbatch_script = source_provenance.get("sbatch_script")
    if sbatch_script not in ALLOWED_SBATCH_SCRIPTS:
        raise AnalysisInputError("source-plan:provenance.sbatch_script:invalid")
    sbatch_relative = Path(sbatch_script)
    sbatch_path = (project_root / sbatch_relative).resolve()
    if (
        sbatch_relative.is_absolute()
        or ".." in sbatch_relative.parts
        or not sbatch_path.is_file()
        or project_root not in sbatch_path.parents
    ):
        raise AnalysisInputError("source-plan:provenance.sbatch_script:unsafe")
    if sha256_file(sbatch_path) != source_provenance.get(
        "baseline_sbatch_sha256"
    ):
        raise AnalysisInputError(
            "source-plan:provenance.baseline_sbatch_sha256:mismatch"
        )
    expected_provenance = dict(source_provenance)
    expected_provenance.update(
        {
            "source_commit": provenance.get("source_commit"),
            "source_plan_path": source_plan_path,
            "source_plan_sha256": source_plan_sha256,
        }
    )
    if provenance != expected_provenance:
        raise AnalysisInputError("source-plan:provenance:execution-view-mismatch")
    if source_plan.get("data_class") != "pilot":
        raise AnalysisInputError("source-plan:data_class:must-be-pilot")
    return source_plan, project_root, observed_sha256


def resolve_artifact(
    artifact_name: Any,
    *,
    run_dir: Path,
    project_root: Path,
) -> Path:
    if not isinstance(artifact_name, str) or not artifact_name:
        raise AnalysisInputError("artifact.path:missing-or-invalid")
    relative = Path(artifact_name)
    if relative.is_absolute() or ".." in relative.parts:
        raise AnalysisInputError("artifact.path:unsafe")
    candidates = ((project_root / relative).resolve(), (run_dir / relative).resolve())
    allowed_roots = (project_root.resolve(), run_dir.resolve())
    for candidate in candidates:
        if not any(
            candidate == root or root in candidate.parents for root in allowed_roots
        ):
            continue
        if candidate.is_file():
            return candidate
    raise AnalysisInputError(f"artifact.path:not-found:{artifact_name}")


def validate_scheduler(
    scheduler: Any,
    *,
    source_commit: str,
    sbatch_sha256: str,
    sbatch_script: str,
    array_index: int,
) -> list[str]:
    errors = []
    if not isinstance(scheduler, dict):
        return ["scheduler:missing-or-invalid"]
    if scheduler.get("schema_version") != SCHEDULER_SCHEMA:
        errors.append("scheduler:schema")
    if scheduler.get("status") != "completed":
        errors.append("scheduler:not-completed")
    if scheduler.get("provenance_passed") is not True:
        errors.append("scheduler:provenance-failed")
    source = scheduler.get("source", {})
    execution = scheduler.get("execution", {})
    slurm = scheduler.get("slurm", {})
    if not isinstance(source, dict):
        errors.append("scheduler:source-shape")
        source = {}
    if not isinstance(execution, dict):
        errors.append("scheduler:execution-shape")
        execution = {}
    if not isinstance(slurm, dict):
        errors.append("scheduler:slurm-shape")
        slurm = {}
    if source.get("git_head") != source_commit:
        errors.append("scheduler:source-commit")
    if source.get("clean") is not True or source.get("dirty_entries") != []:
        errors.append("scheduler:dirty-source")
    if execution.get("sbatch_sha256") != sbatch_sha256:
        errors.append("scheduler:sbatch-sha256")
    if execution.get("sbatch_script") != sbatch_script:
        errors.append("scheduler:sbatch-script")
    if str(slurm.get("SLURM_ARRAY_TASK_ID")) != str(array_index):
        errors.append("scheduler:array-task-id")
    if not slurm.get("SLURM_JOB_ID"):
        errors.append("scheduler:job-id")
    return errors


def validate_cells(
    spec: dict[str, Any],
    frozen: dict[str, Any],
    run_spec_path: Path,
) -> dict[str, Any]:
    run_dir = run_spec_path.parent
    errors: list[str] = []
    try:
        project_root = project_root_for_run(run_dir, spec.get("run_dir"))
    except AnalysisInputError as exception:
        errors.append(str(exception))
        project_root = run_dir
    sizes = frozen["analysis"]["sizes"]
    fields = frozen["analysis"]["fields"]
    seeds = frozen["analysis"]["seeds"]
    expected_roster = {
        (size, field, seed)
        for size in sizes
        for field in fields
        for seed in seeds
    }
    cells = spec.get("cells")
    if not isinstance(cells, list):
        cells = []
        errors.append("cells:missing-or-invalid")

    cell_ids = []
    observed_roster = []
    for cell in cells:
        if not isinstance(cell, dict):
            errors.append("cells:non-object")
            continue
        cell_id = cell.get("cell_id")
        params = cell.get("params")
        if (
            not isinstance(cell_id, str)
            or not SAFE_ID_PATTERN.fullmatch(cell_id)
        ):
            errors.append("cells:invalid-cell-id")
            continue
        cell_ids.append(cell_id)
        if not isinstance(params, dict) or set(params) != {"L", "h", "seed"}:
            errors.append(f"{cell_id}:params-shape")
            continue
        try:
            observed_roster.append(
                (
                    positive_int(params["L"], f"{cell_id}.L"),
                    finite_float(params["h"], f"{cell_id}.h", positive=True),
                    positive_int(params["seed"], f"{cell_id}.seed"),
                )
            )
        except AnalysisInputError as exception:
            errors.append(str(exception))
    if len(set(cell_ids)) != len(cell_ids):
        errors.append("cells:duplicate-cell-id")
    if len(observed_roster) != len(set(observed_roster)):
        errors.append("cells:duplicate-roster-entry")
    if set(observed_roster) != expected_roster or len(observed_roster) != len(
        expected_roster
    ):
        errors.append("cells:frozen-roster-mismatch")

    manifest_paths = sorted((run_dir / "cells").glob("*/manifest.json"))
    manifest_cell_ids = {path.parent.name for path in manifest_paths}
    extra_manifests = sorted(manifest_cell_ids - set(cell_ids))
    if extra_manifests:
        errors.append("cells:extra-manifests")
    expected_scheduler_names = {
        f"scheduler-manifest-{index}.json"
        for index in range(1, len(cells) + 1)
    }
    observed_scheduler_names = {
        path.name for path in run_dir.glob("scheduler-manifest-*.json")
    }
    extra_scheduler_manifests = sorted(
        observed_scheduler_names - expected_scheduler_names
    )
    if extra_scheduler_manifests:
        errors.append("scheduler:extra-manifests")

    valid_rows = []
    cell_checks = []
    manifest_hash_rows = []
    tolerance = frozen["gate"].get("aspect_tolerance", 0.0)
    source_commit = frozen.get("source_commit")
    sbatch_sha256 = frozen.get("sbatch_sha256")
    expected_settings = spec.get("settings")
    expected_provenance = spec.get("provenance")
    for array_index, cell in enumerate(cells, start=1):
        if (
            not isinstance(cell, dict)
            or not isinstance(cell.get("cell_id"), str)
            or not SAFE_ID_PATTERN.fullmatch(cell["cell_id"])
        ):
            continue
        cell_id = cell["cell_id"]
        cell_errors = []
        manifest_path = run_dir / "cells" / cell_id / "manifest.json"
        manifest = None
        if not manifest_path.is_file():
            cell_errors.append("manifest:missing")
        else:
            try:
                manifest = load_strict_json_bytes(
                    manifest_path.read_bytes(),
                    f"{cell_id}.manifest",
                )
                manifest_hash_rows.append(
                    (f"{cell_id}/manifest", sha256_file(manifest_path))
                )
            except (OSError, AnalysisInputError):
                cell_errors.append("manifest:invalid-json")
        scheduler_path = run_dir / f"scheduler-manifest-{array_index}.json"
        scheduler = None
        if not scheduler_path.is_file():
            cell_errors.append("scheduler:missing")
        else:
            try:
                scheduler = load_strict_json_bytes(
                    scheduler_path.read_bytes(),
                    f"{cell_id}.scheduler",
                )
                manifest_hash_rows.append(
                    (
                        f"{cell_id}/scheduler",
                        sha256_file(scheduler_path),
                    )
                )
            except (OSError, AnalysisInputError):
                cell_errors.append("scheduler:invalid-json")
        if scheduler is not None:
            cell_errors.extend(
                validate_scheduler(
                    scheduler,
                    source_commit=source_commit,
                    sbatch_sha256=sbatch_sha256,
                    sbatch_script=expected_provenance["sbatch_script"],
                    array_index=array_index,
                )
            )

        if isinstance(manifest, dict):
            if manifest.get("schema_version") != CELL_SCHEMA:
                cell_errors.append("manifest:schema")
            if manifest.get("run_id") != spec.get("run_id"):
                cell_errors.append("manifest:run-id")
            if manifest.get("cell_id") != cell_id:
                cell_errors.append("manifest:cell-id")
            if manifest.get("params") != cell.get("params"):
                cell_errors.append("manifest:params")
            if manifest.get("settings") != expected_settings:
                cell_errors.append("manifest:settings")
            if manifest.get("provenance") != expected_provenance:
                cell_errors.append("manifest:provenance")
            if manifest.get("status") != "success":
                cell_errors.append("manifest:status")
            diagnostics = manifest.get("diagnostics")
            if (
                not isinstance(diagnostics, dict)
                or diagnostics.get("health_passed") is not True
            ):
                cell_errors.append("manifest:health")
            if isinstance(diagnostics, dict):
                required_checks = (
                    "sign_passed",
                    "field_flip_passed",
                    "string_fill_passed",
                    "rebin_passed",
                    "finite_passed",
                    "autocorr_passed",
                    "periodicity_passed",
                    "effective_parameters_passed",
                    "beta_policy_passed",
                    "temperature_inverse_passed",
                )
                checks = diagnostics.get("checks")
                if not isinstance(checks, dict) or any(
                    checks.get(name) is not True for name in required_checks
                ):
                    cell_errors.append("manifest:diagnostic-checks")
                try:
                    sign_mean = finite_float(
                        diagnostics.get("sign_mean"),
                        f"{cell_id}.diagnostics.sign_mean",
                    )
                    field_flip_mean = finite_float(
                        diagnostics.get("field_flip_mean"),
                        f"{cell_id}.diagnostics.field_flip_mean",
                    )
                    string_fill_mean = finite_float(
                        diagnostics.get("string_fill_mean"),
                        f"{cell_id}.diagnostics.string_fill_mean",
                    )
                    if not (
                        frozen["gate"]["minimum_sign"]
                        <= sign_mean
                        <= 1.0 + tolerance
                    ):
                        cell_errors.append("manifest:minimum-sign")
                    if field_flip_mean <= 0:
                        cell_errors.append("manifest:field-flip")
                    if not (
                        0.0
                        <= string_fill_mean
                        < frozen["gate"]["maximum_string_fill"]
                    ):
                        cell_errors.append("manifest:string-fill")
                except AnalysisInputError as exception:
                    cell_errors.append(str(exception))
                rebin_counts = diagnostics.get("rebin_counts")
                required_moments = (
                    "Mag2",
                    "Mag4",
                    "SpaceTimeMag2",
                    "SpaceTimeMag4",
                )
                if not isinstance(rebin_counts, dict):
                    cell_errors.append("manifest:rebin-counts")
                else:
                    try:
                        parsed_rebin_counts = [
                            positive_int(
                                rebin_counts.get(name),
                                f"{cell_id}.diagnostics.rebin_counts.{name}",
                            )
                            for name in required_moments
                        ]
                        if min(parsed_rebin_counts) < frozen["gate"][
                            "minimum_rebin_count"
                        ]:
                            cell_errors.append("manifest:minimum-rebin-count")
                    except AnalysisInputError as exception:
                        cell_errors.append(str(exception))
                autocorr_times = diagnostics.get("autocorr_times")
                if not isinstance(autocorr_times, dict):
                    cell_errors.append("manifest:autocorr-times")
                else:
                    try:
                        parsed_autocorr = [
                            finite_float(
                                autocorr_times.get(name),
                                f"{cell_id}.diagnostics.autocorr_times.{name}",
                            )
                            for name in required_moments
                        ]
                        if any(value < 0 for value in parsed_autocorr):
                            cell_errors.append("manifest:negative-autocorrelation")
                    except AnalysisInputError as exception:
                        cell_errors.append(str(exception))
                if diagnostics.get("nonfinite_fields") != []:
                    cell_errors.append("manifest:nonfinite-fields")

            effective = manifest.get("effective_parameters")
            params = cell.get("params", {})
            if not isinstance(effective, dict):
                cell_errors.append("manifest:effective-parameters")
            else:
                try:
                    effective_L = positive_int(
                        effective.get("L"), f"{cell_id}.effective.L"
                    )
                    effective_h = finite_float(
                        effective.get("h"),
                        f"{cell_id}.effective.h",
                        positive=True,
                    )
                    effective_beta = finite_float(
                        effective.get("beta"),
                        f"{cell_id}.effective.beta",
                        positive=True,
                    )
                    effective_T = finite_float(
                        effective.get("T"),
                        f"{cell_id}.effective.T",
                        positive=True,
                    )
                    effective_seed = positive_int(
                        effective.get("seed"), f"{cell_id}.effective.seed"
                    )
                    effective_J = finite_float(
                        effective.get("J"),
                        f"{cell_id}.effective.J",
                        positive=True,
                    )
                    effective_beta_factor = finite_float(
                        effective.get("beta_factor"),
                        f"{cell_id}.effective.beta_factor",
                        positive=True,
                    )
                    effective_beta_over_L = finite_float(
                        effective.get("beta_over_L"),
                        f"{cell_id}.effective.beta_over_L",
                        positive=True,
                    )
                    effective_beta_times_h = finite_float(
                        effective.get("beta_times_h"),
                        f"{cell_id}.effective.beta_times_h",
                        positive=True,
                    )
                    effective_sweeps = positive_int(
                        effective.get("measurement_sweeps"),
                        f"{cell_id}.effective.measurement_sweeps",
                    )
                    effective_thermalization = positive_int(
                        effective.get("thermalization_sweeps"),
                        f"{cell_id}.effective.thermalization_sweeps",
                    )
                    effective_bin_size = positive_int(
                        effective.get("bin_size"),
                        f"{cell_id}.effective.bin_size",
                    )
                    positive_int(
                        effective.get("string_length"),
                        f"{cell_id}.effective.string_length",
                    )
                    if effective.get("beta_policy") != "beta_h_equals_L":
                        cell_errors.append("manifest:beta-policy")
                    if effective.get("lattice_name") != "triangular":
                        cell_errors.append("manifest:effective-lattice")
                    if (
                        effective_L != params.get("L")
                        or effective_h != params.get("h")
                        or effective_seed != params.get("seed")
                    ):
                        cell_errors.append("manifest:effective-roster")
                    if not math.isclose(
                        effective_J,
                        float(expected_settings["J"]),
                        rel_tol=tolerance,
                        abs_tol=tolerance,
                    ):
                        cell_errors.append("manifest:effective-J")
                    if (
                        effective_sweeps
                        != expected_settings["measurement_sweeps"]
                        or effective_thermalization
                        != expected_settings["thermalization_sweeps"]
                        or effective_bin_size != expected_settings["bin_size"]
                    ):
                        cell_errors.append("manifest:effective-run-settings")
                    if not math.isclose(
                        effective_beta * effective_h / effective_L,
                        1.0,
                        rel_tol=tolerance,
                        abs_tol=tolerance,
                    ):
                        cell_errors.append("manifest:literal-aspect")
                    if not math.isclose(
                        effective_T * effective_beta,
                        1.0,
                        rel_tol=tolerance,
                        abs_tol=tolerance,
                    ):
                        cell_errors.append("manifest:temperature-inverse")
                    if not math.isclose(
                        effective_beta_factor,
                        effective_beta / effective_L,
                        rel_tol=tolerance,
                        abs_tol=tolerance,
                    ) or not math.isclose(
                        effective_beta_over_L,
                        effective_beta / effective_L,
                        rel_tol=tolerance,
                        abs_tol=tolerance,
                    ):
                        cell_errors.append("manifest:beta-factor")
                    if not math.isclose(
                        effective_beta_times_h,
                        effective_beta * effective_h,
                        rel_tol=tolerance,
                        abs_tol=tolerance,
                    ):
                        cell_errors.append("manifest:beta-times-h")
                except AnalysisInputError as exception:
                    cell_errors.append(str(exception))

            observables = manifest.get("observables")
            values = {}
            if not isinstance(observables, dict):
                cell_errors.append("manifest:observables")
            else:
                for name in (
                    "spacetime_binder",
                    "spacetime_binder_se",
                    "binder",
                    "binder_se",
                ):
                    try:
                        values[name] = finite_float(
                            observables.get(name),
                            f"{cell_id}.observables.{name}",
                            positive=name.endswith("_se"),
                        )
                    except AnalysisInputError as exception:
                        cell_errors.append(str(exception))

            artifacts = manifest.get("artifacts")
            if not isinstance(artifacts, list) or not artifacts:
                cell_errors.append("manifest:artifacts")
            else:
                for artifact in artifacts:
                    if not isinstance(artifact, dict):
                        cell_errors.append("artifact:not-object")
                        continue
                    declared_hash = artifact.get("sha256")
                    if (
                        not isinstance(declared_hash, str)
                        or not SHA256_PATTERN.fullmatch(declared_hash)
                    ):
                        cell_errors.append("artifact:sha256-format")
                        continue
                    try:
                        artifact_path = resolve_artifact(
                            artifact.get("path"),
                            run_dir=run_dir,
                            project_root=project_root,
                        )
                        if sha256_file(artifact_path) != declared_hash:
                            cell_errors.append("artifact:sha256-mismatch")
                        declared_bytes = artifact.get("bytes")
                        if (
                            not isinstance(declared_bytes, int)
                            or declared_bytes != artifact_path.stat().st_size
                        ):
                            cell_errors.append("artifact:bytes-mismatch")
                    except AnalysisInputError as exception:
                        cell_errors.append(str(exception))

            if not cell_errors and len(values) == 4:
                valid_rows.append(
                    {
                        "cell_id": cell_id,
                        "L": int(params["L"]),
                        "h": float(params["h"]),
                        "seed": int(params["seed"]),
                        **values,
                    }
                )

        errors.extend(f"{cell_id}:{message}" for message in cell_errors)
        cell_checks.append(
            {
                "cell_id": cell_id,
                "manifest_present": manifest_path.is_file(),
                "scheduler_manifest_present": scheduler_path.is_file(),
                "passed": not cell_errors,
                "errors": sorted(set(cell_errors)),
            }
        )

    manifest_hash_payload = "\n".join(
        f"{label} {digest}" for label, digest in sorted(manifest_hash_rows)
    ).encode()
    manifest_set_sha256 = sha256_bytes(manifest_hash_payload)
    return {
        "passed": not errors and len(valid_rows) == len(expected_roster),
        "errors": sorted(set(errors)),
        "expected_cell_count": len(expected_roster),
        "observed_spec_cell_count": len(cells),
        "valid_cell_count": len(valid_rows),
        "extra_manifest_cells": extra_manifests,
        "extra_scheduler_manifests": extra_scheduler_manifests,
        "cell_checks": cell_checks,
        "valid_rows": valid_rows,
        "manifest_set_sha256": manifest_set_sha256,
    }


def pool_rows(
    valid_rows: list[dict[str, Any]],
    sizes: list[int],
    fields: list[float],
    seeds: list[int],
) -> tuple[list[dict[str, Any]], list[str]]:
    grouped: dict[tuple[int, float], list[dict[str, Any]]] = {}
    for row in valid_rows:
        grouped.setdefault((row["L"], row["h"]), []).append(row)
    pooled = []
    errors = []
    for size in sizes:
        for field in fields:
            selected = sorted(
                grouped.get((size, field), []), key=lambda row: row["seed"]
            )
            observed_seeds = [row["seed"] for row in selected]
            if observed_seeds != seeds:
                errors.append(f"pool:L={size}:h={field}:seed-roster")
                continue
            primary_values = [row["spacetime_binder"] for row in selected]
            primary_errors = [row["spacetime_binder_se"] for row in selected]
            diagnostic_values = [row["binder"] for row in selected]
            diagnostic_errors = [row["binder_se"] for row in selected]

            def aggregate(values, errors_for_values):
                count = len(values)
                within = math.sqrt(
                    sum(error * error for error in errors_for_values)
                ) / count
                between = (
                    float(np.std(values, ddof=1)) / math.sqrt(count)
                    if count > 1
                    else 0.0
                )
                standard_error = max(within, between)
                if not math.isfinite(standard_error) or standard_error <= 0:
                    raise AnalysisInputError(
                        f"pool:L={size}:h={field}:nonpositive-pooled-se"
                    )
                return float(np.mean(values)), within, between, standard_error

            try:
                mean, within, between, standard_error = aggregate(
                    primary_values, primary_errors
                )
                d_mean, d_within, d_between, d_standard_error = aggregate(
                    diagnostic_values, diagnostic_errors
                )
            except AnalysisInputError as exception:
                errors.append(str(exception))
                continue
            pooled.append(
                {
                    "L": size,
                    "h": field,
                    "estimator_id": PRIMARY_ESTIMATOR,
                    "spacetime_binder": mean,
                    "spacetime_binder_se": standard_error,
                    "within_chain_se": within,
                    "between_chain_se": between,
                    "diagnostic_estimator_id": DIAGNOSTIC_ESTIMATOR,
                    "equal_time_binder": d_mean,
                    "equal_time_binder_se": d_standard_error,
                    "equal_time_within_chain_se": d_within,
                    "equal_time_between_chain_se": d_between,
                    "seed_count": len(selected),
                    "seeds": observed_seeds,
                }
            )
    return pooled, errors


def model_design(
    lattice_sizes: np.ndarray,
    fields: np.ndarray,
    hc: float,
    y_t: float,
    y_i: float,
    y_2: float,
    terms: list[str],
) -> tuple[np.ndarray, np.ndarray]:
    x = (fields - hc) * np.power(lattice_sizes, y_t)
    columns = [np.ones_like(x)]
    for term in terms:
        if term == "a1":
            columns.append(x)
        elif term == "a2":
            columns.append(x**2)
        elif term == "a3":
            columns.append(x**3)
        elif term == "b1":
            columns.append(np.power(lattice_sizes, y_i))
        elif term == "b2":
            columns.append(np.power(lattice_sizes, y_2))
        elif term == "c1":
            columns.append(x * np.power(lattice_sizes, y_i))
        else:
            raise AnalysisInputError(f"fit:unsupported-term:{term}")
    return np.column_stack(columns), x


def linear_fit_at_hc(
    lattice_sizes: np.ndarray,
    fields: np.ndarray,
    values: np.ndarray,
    errors: np.ndarray,
    *,
    hc: float,
    y_t: float,
    y_i: float,
    y_2: float,
    terms: list[str],
) -> dict[str, Any]:
    design, x = model_design(
        lattice_sizes, fields, hc, y_t, y_i, y_2, terms
    )
    weighted = design / errors[:, None]
    weighted_values = values / errors
    scales = np.linalg.norm(weighted, axis=0)
    if np.any(~np.isfinite(scales)) or np.any(scales <= 0):
        return {"passed": False, "chi2": math.inf}
    scaled = weighted / scales
    try:
        coefficients_scaled, _, rank, _ = np.linalg.lstsq(
            scaled, weighted_values, rcond=None
        )
    except np.linalg.LinAlgError:
        return {"passed": False, "chi2": math.inf}
    if rank != design.shape[1]:
        return {"passed": False, "chi2": math.inf}
    coefficients = coefficients_scaled / scales
    predictions = design @ coefficients
    residuals = (values - predictions) / errors
    chi2 = float(np.dot(residuals, residuals))
    return {
        "passed": math.isfinite(chi2),
        "chi2": chi2,
        "coefficients": coefficients,
        "predictions": predictions,
        "residuals": residuals,
        "x": x,
    }


def profile_fit(
    lattice_sizes: np.ndarray,
    fields: np.ndarray,
    values: np.ndarray,
    errors: np.ndarray,
    *,
    bounds: tuple[float, float],
    y_t: float,
    y_i: float,
    y_2: float,
    terms: list[str],
    grid_points: int,
    covariance: bool,
) -> dict[str, Any]:
    lower, upper = bounds

    def evaluate(hc_value: float) -> dict[str, Any]:
        return linear_fit_at_hc(
            lattice_sizes,
            fields,
            values,
            errors,
            hc=hc_value,
            y_t=y_t,
            y_i=y_i,
            y_2=y_2,
            terms=terms,
        )

    grid = np.linspace(lower, upper, grid_points)
    grid_results = [evaluate(float(hc_value)) for hc_value in grid]
    objectives = [
        result["chi2"] if result.get("passed") else math.inf
        for result in grid_results
    ]
    best_index = int(np.argmin(objectives))
    if not math.isfinite(objectives[best_index]):
        return {"converged": False, "reason": "singular-profile"}
    boundary_hit = best_index in (0, len(grid) - 1)
    if boundary_hit:
        best_hc = float(grid[best_index])
        best = grid_results[best_index]
    else:
        left = float(grid[best_index - 1])
        right = float(grid[best_index + 1])
        # Fixed golden-section fraction for a generic bounded minimizer.  It is
        # deliberately written as a numerical algorithm constant so this
        # baseline analyzer contains no equality-conjecture target value.
        golden = 0.6180339887498949
        x1 = right - golden * (right - left)
        x2 = left + golden * (right - left)
        f1 = evaluate(x1)
        f2 = evaluate(x2)
        for _ in range(80):
            if right - left <= 1e-13 * max(1.0, abs(left), abs(right)):
                break
            objective1 = f1["chi2"] if f1.get("passed") else math.inf
            objective2 = f2["chi2"] if f2.get("passed") else math.inf
            if objective1 <= objective2:
                right, x2, f2 = x2, x1, f1
                x1 = right - golden * (right - left)
                f1 = evaluate(x1)
            else:
                left, x1, f1 = x1, x2, f2
                x2 = left + golden * (right - left)
                f2 = evaluate(x2)
        candidates = [
            (x1, f1),
            (x2, f2),
            (float(grid[best_index]), grid_results[best_index]),
        ]
        best_hc, best = min(
            candidates,
            key=lambda pair: (
                pair[1]["chi2"] if pair[1].get("passed") else math.inf
            ),
        )
    if not best.get("passed"):
        return {"converged": False, "reason": "profile-refinement-failed"}

    parameter_names = ["hc", "Q_star", *terms]
    coefficient_names = ["Q_star", *terms]
    parameters = {"hc": float(best_hc)}
    parameters.update(
        {
            name: float(value)
            for name, value in zip(coefficient_names, best["coefficients"])
        }
    )
    dof = len(values) - len(parameter_names)
    result: dict[str, Any] = {
        "converged": True,
        "boundary_hit": boundary_hit,
        "parameter_names": parameter_names,
        "parameters": parameters,
        "chi2": float(best["chi2"]),
        "dof": dof,
        "p_value": chi_square_survival(float(best["chi2"]), dof),
        "predictions": best["predictions"],
        "residuals": best["residuals"],
    }
    if not covariance:
        return result

    x = best["x"]
    powers = np.power(lattice_sizes, y_t)
    derivative_hc = np.zeros_like(x)
    if "a1" in terms:
        derivative_hc -= powers * parameters["a1"]
    if "a2" in terms:
        derivative_hc -= powers * 2.0 * parameters["a2"] * x
    if "a3" in terms:
        derivative_hc -= powers * 3.0 * parameters["a3"] * x**2
    if "c1" in terms:
        derivative_hc -= (
            powers
            * parameters["c1"]
            * np.power(lattice_sizes, y_i)
        )
    design, _ = model_design(
        lattice_sizes, fields, float(best_hc), y_t, y_i, y_2, terms
    )
    jacobian = np.column_stack([derivative_hc, design])
    weighted_jacobian = jacobian / errors[:, None]
    scales = np.linalg.norm(weighted_jacobian, axis=0)
    if np.any(~np.isfinite(scales)) or np.any(scales <= 0):
        result.update(
            {
                "covariance_passed": False,
                "covariance_condition": 1e308,
                "covariance": None,
            }
        )
        return result
    scaled_jacobian = weighted_jacobian / scales
    rank = int(np.linalg.matrix_rank(scaled_jacobian))
    condition = float(np.linalg.cond(scaled_jacobian))
    if rank != jacobian.shape[1] or not math.isfinite(condition):
        result.update(
            {
                "covariance_passed": False,
                "covariance_condition": 1e308,
                "covariance": None,
            }
        )
        return result
    try:
        scaled_covariance = np.linalg.inv(
            scaled_jacobian.T @ scaled_jacobian
        )
    except np.linalg.LinAlgError:
        result.update(
            {
                "covariance_passed": False,
                "covariance_condition": condition,
                "covariance": None,
            }
        )
        return result
    inverse_scales = np.diag(1.0 / scales)
    covariance_matrix = inverse_scales @ scaled_covariance @ inverse_scales
    result.update(
        {
            "covariance_passed": bool(np.all(np.isfinite(covariance_matrix))),
            "covariance_condition": condition,
            "covariance": covariance_matrix,
        }
    )
    return result


def select_fit_data(
    pooled_rows: list[dict[str, Any]],
    sizes: list[int],
    window: list[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    selected_fields = set(window)
    selected = sorted(
        (
            row
            for row in pooled_rows
            if row["L"] in sizes and row["h"] in selected_fields
        ),
        key=lambda row: (row["L"], row["h"]),
    )
    return (
        np.asarray([row["L"] for row in selected], dtype=float),
        np.asarray([row["h"] for row in selected], dtype=float),
        np.asarray([row["spacetime_binder"] for row in selected], dtype=float),
        np.asarray(
            [row["spacetime_binder_se"] for row in selected], dtype=float
        ),
    )


def shared_bootstrap_draws(
    valid_rows: list[dict[str, Any]],
    sizes: list[int],
    fields: list[float],
    *,
    resamples: int,
    seed: int,
) -> dict[str, Any]:
    grouped: dict[tuple[int, float], list[dict[str, Any]]] = {}
    for row in valid_rows:
        grouped.setdefault((row["L"], row["h"]), []).append(row)
    keys = [(size, field) for size in sizes for field in fields]
    groups = [
        sorted(grouped[(size, field)], key=lambda row: row["seed"])
        for size, field in keys
    ]
    if any(not group for group in groups):
        raise AnalysisInputError("bootstrap:replica-roster-mismatch")
    rng = np.random.default_rng(seed)
    draws = np.empty((resamples, len(keys)), dtype=float)
    for sample_index in range(resamples):
        for column_index, group in enumerate(groups):
            selected_indices = rng.integers(
                0, len(group), size=len(group)
            )
            replica_draws = [
                rng.normal(
                    group[int(index)]["spacetime_binder"],
                    group[int(index)]["spacetime_binder_se"],
                )
                for index in selected_indices
            ]
            draws[sample_index, column_index] = float(
                np.mean(replica_draws)
            )
    return {
        "keys": keys,
        "column_by_key": {
            key: index for index, key in enumerate(keys)
        },
        "draws": draws,
        "seed": seed,
        "resamples": resamples,
    }


def run_fit_variant(
    pooled_rows: list[dict[str, Any]],
    bootstrap_draws: dict[str, Any],
    variant: dict[str, Any],
    *,
    windows: dict[str, list[float]],
    outer_bounds: tuple[float, float],
    analysis: dict[str, Any],
    gate: dict[str, Any],
) -> dict[str, Any]:
    sizes, fields, values, errors = select_fit_data(
        pooled_rows,
        variant["sizes"],
        windows[variant["field_window"]],
    )
    bootstrap_columns = [
        bootstrap_draws["column_by_key"][(size, field)]
        for size in variant["sizes"]
        for field in windows[variant["field_window"]]
    ]
    if len(bootstrap_columns) != len(values):
        raise AnalysisInputError(f"fit:{variant['fit_id']}:bootstrap-shape")
    central = profile_fit(
        sizes,
        fields,
        values,
        errors,
        bounds=outer_bounds,
        y_t=variant["y_t"],
        y_i=variant["y_i"],
        y_2=variant["y_2"],
        terms=variant["terms"],
        grid_points=analysis["profile_grid_points"],
        covariance=True,
    )
    summary: dict[str, Any] = {
        "fit_id": variant["fit_id"],
        "classification": variant["classification"],
        "sizes": variant["sizes"],
        "field_window": variant["field_window"],
        "field_values": list(windows[variant["field_window"]]),
        "field_bounds": [
            min(windows[variant["field_window"]]),
            max(windows[variant["field_window"]]),
        ],
        "y_t": variant["y_t"],
        "y_i": variant["y_i"],
        "y_2": variant["y_2"],
        "terms": variant["terms"],
        "discard_reason": variant.get("discard_reason"),
        "data_point_count": len(values),
        "central": {},
        "bootstrap": {
            "method": analysis["bootstrap_method"],
            "shared_across_fits": True,
            "seed": bootstrap_draws["seed"],
            "configured_resamples": analysis["bootstrap_resamples"],
            "attempted_resamples": 0,
            "successful_resamples": 0,
            "failed_resamples": 0,
            "failed_fraction": 1.0,
        },
        "accepted": False,
        "rejection_reasons": [],
    }
    if not central.get("converged"):
        summary["rejection_reasons"] = [central.get("reason", "fit-failed")]
        return summary
    central_json = {
        "converged": True,
        "boundary_hit": central["boundary_hit"],
        "parameter_names": central["parameter_names"],
        "parameters": central["parameters"],
        "chi2": central["chi2"],
        "degrees_of_freedom": central["dof"],
        "p_value": central["p_value"],
        "covariance_passed": central.get("covariance_passed", False),
        "covariance_condition": central.get("covariance_condition", 1e308),
    }
    summary["central"] = central_json
    rejection_reasons = []
    if central["boundary_hit"]:
        rejection_reasons.append("hc-profile-boundary-hit")
    if central["dof"] < gate["min_degrees_of_freedom"]:
        rejection_reasons.append("insufficient-degrees-of-freedom")
    if central["p_value"] < gate["min_p_value"]:
        rejection_reasons.append("goodness-of-fit")
    if not central.get("covariance_passed"):
        rejection_reasons.append("covariance-failed")
    if (
        central.get("covariance_condition", 1e308)
        > gate["max_covariance_condition"]
    ):
        rejection_reasons.append("covariance-condition")

    samples = []
    bootstrap_hc_by_index: list[float | None] = [
        None
    ] * analysis["bootstrap_resamples"]
    attempted = 0
    failed = 0
    for sample_index in range(analysis["bootstrap_resamples"]):
        attempted += 1
        sampled_values = bootstrap_draws["draws"][
            sample_index, bootstrap_columns
        ]
        trial = profile_fit(
            sizes,
            fields,
            np.asarray(sampled_values, dtype=float),
            errors,
            bounds=outer_bounds,
            y_t=variant["y_t"],
            y_i=variant["y_i"],
            y_2=variant["y_2"],
            terms=variant["terms"],
            grid_points=analysis["profile_grid_points"],
            covariance=False,
        )
        if (
            not trial.get("converged")
            or trial.get("boundary_hit")
            or any(
                not math.isfinite(value)
                for value in trial.get("parameters", {}).values()
            )
        ):
            failed += 1
            continue
        samples.append(
            [trial["parameters"][name] for name in central["parameter_names"]]
        )
        bootstrap_hc_by_index[sample_index] = trial["parameters"]["hc"]
    failure_fraction = failed / attempted if attempted else 1.0
    summary["bootstrap"].update(
        {
            "attempted_resamples": attempted,
            "successful_resamples": len(samples),
            "failed_resamples": failed,
            "failed_fraction": failure_fraction,
        }
    )
    complete_attempts = attempted == analysis["bootstrap_resamples"]
    if gate["require_complete_bootstrap_attempts"] and not complete_attempts:
        rejection_reasons.append("incomplete-bootstrap-attempts")
    if failure_fraction > gate["max_bootstrap_failed_fraction"]:
        rejection_reasons.append("bootstrap-failure-fraction")
    if len(samples) < 2:
        rejection_reasons.append("insufficient-bootstrap-successes")
        bootstrap_covariance = central.get("covariance")
        statistical_errors = {
            name: math.sqrt(max(0.0, float(bootstrap_covariance[index, index])))
            if bootstrap_covariance is not None
            else None
            for index, name in enumerate(central["parameter_names"])
        }
        confidence_intervals = {
            name: (
                [central["parameters"][name], central["parameters"][name]]
                if bootstrap_covariance is not None
                else [None, None]
            )
            for name in central["parameter_names"]
        }
    else:
        sample_array = np.asarray(samples, dtype=float)
        bootstrap_covariance = np.cov(sample_array, rowvar=False, ddof=1)
        bootstrap_covariance = np.atleast_2d(bootstrap_covariance)
        statistical_errors = {
            name: float(np.std(sample_array[:, index], ddof=1))
            for index, name in enumerate(central["parameter_names"])
        }
        confidence_intervals = {
            name: [
                float(np.quantile(sample_array[:, index], 0.025)),
                float(np.quantile(sample_array[:, index], 0.975)),
            ]
            for index, name in enumerate(central["parameter_names"])
        }
    summary["statistical_errors"] = statistical_errors
    summary["confidence_intervals_95"] = confidence_intervals
    summary["bootstrap_covariance"] = (
        [
            [float(value) for value in row]
            for row in np.asarray(bootstrap_covariance, dtype=float)
        ]
        if bootstrap_covariance is not None
        else None
    )
    summary["accepted"] = not rejection_reasons
    summary["rejection_reasons"] = sorted(set(rejection_reasons))
    summary["_predictions"] = central["predictions"]
    summary["_residuals"] = central["residuals"]
    summary["_fit_sizes"] = sizes
    summary["_fit_fields"] = fields
    summary["_fit_values"] = values
    summary["_fit_errors"] = errors
    summary["_bootstrap_hc_by_index"] = bootstrap_hc_by_index
    return summary


def weighted_line(
    x_values: np.ndarray,
    y_values: np.ndarray,
    errors: np.ndarray,
) -> dict[str, Any]:
    design = np.column_stack([np.ones_like(x_values), x_values])
    weighted = design / errors[:, None]
    weighted_y = y_values / errors
    try:
        coefficients, _, rank, _ = np.linalg.lstsq(
            weighted, weighted_y, rcond=None
        )
    except np.linalg.LinAlgError:
        return {"converged": False}
    if rank != 2:
        return {"converged": False}
    intercept, slope = (float(value) for value in coefficients)
    predictions = design @ coefficients
    residuals = (y_values - predictions) / errors
    chi2 = float(np.dot(residuals, residuals))
    dof = len(x_values) - 2
    root = -intercept / slope if slope != 0 else None
    return {
        "converged": root is not None and math.isfinite(root),
        "intercept": intercept,
        "slope": slope,
        "crossing": root,
        "chi2": chi2,
        "dof": dof,
        "chi2_per_dof": chi2 / dof if dof > 0 else None,
    }


def crossing_analysis(
    pooled_rows: list[dict[str, Any]],
    *,
    sizes: list[int],
    window: list[float],
    bootstrap_resamples: int,
    bootstrap_seed: int,
    gate: dict[str, Any],
) -> list[dict[str, Any]]:
    selected_fields = set(window)
    lookup = {
        (row["L"], row["h"]): row
        for row in pooled_rows
        if row["h"] in selected_fields
    }
    fields = list(window)
    lower, upper = min(window), max(window)
    results = []
    for small, large in zip(sizes[:-1], sizes[1:]):
        differences = []
        errors = []
        for field in fields:
            small_row = lookup[(small, field)]
            large_row = lookup[(large, field)]
            differences.append(
                small_row["spacetime_binder"]
                - large_row["spacetime_binder"]
            )
            errors.append(
                math.hypot(
                    small_row["spacetime_binder_se"],
                    large_row["spacetime_binder_se"],
                )
            )
        x_values = np.asarray(fields, dtype=float)
        y_values = np.asarray(differences, dtype=float)
        sigma_values = np.asarray(errors, dtype=float)
        central = weighted_line(x_values, y_values, sigma_values)
        bracketed = bool(y_values[0] * y_values[-1] <= 0)
        roots = []
        failed = 0
        rng = np.random.default_rng(
            stable_seed(bootstrap_seed, f"crossing-{small}-{large}")
        )
        for _ in range(bootstrap_resamples):
            sampled = y_values + rng.normal(0.0, sigma_values)
            trial = weighted_line(x_values, sampled, sigma_values)
            root = trial.get("crossing")
            if (
                not trial.get("converged")
                or root is None
                or root < lower
                or root > upper
            ):
                failed += 1
                continue
            roots.append(root)
        failed_fraction = failed / bootstrap_resamples
        chi2_per_dof = central.get("chi2_per_dof")
        passed = bool(
            bracketed
            and central.get("converged")
            and lower <= central["crossing"] <= upper
            and (
                not gate["require_positive_crossing_slope"]
                or central["slope"] > 0
            )
            and chi2_per_dof is not None
            and chi2_per_dof <= gate["max_crossing_chi2_per_dof"]
            and failed_fraction <= gate["max_bootstrap_failed_fraction"]
            and len(roots) >= 2
        )
        results.append(
            {
                "size_pair": [small, large],
                "estimator_id": PRIMARY_ESTIMATOR,
                "difference_orientation": "Q_small_minus_Q_large",
                "field_window": list(window),
                "fields": fields,
                "binder_differences": differences,
                "binder_difference_se": errors,
                "endpoint_bracketed": bracketed,
                "slope": central.get("slope"),
                "positive_slope_required": gate[
                    "require_positive_crossing_slope"
                ],
                "slope_passed": bool(
                    central.get("converged")
                    and (
                        not gate["require_positive_crossing_slope"]
                        or central["slope"] > 0
                    )
                ),
                "crossing": central.get("crossing"),
                "crossing_se": (
                    float(np.std(roots, ddof=1)) if len(roots) >= 2 else None
                ),
                "crossing_ci95": (
                    [
                        float(np.quantile(roots, 0.025)),
                        float(np.quantile(roots, 0.975)),
                    ]
                    if roots
                    else [None, None]
                ),
                "chi2": central.get("chi2"),
                "degrees_of_freedom": central.get("dof"),
                "chi2_per_dof": chi2_per_dof,
                "bootstrap_resamples": bootstrap_resamples,
                "bootstrap_successes": len(roots),
                "bootstrap_failures": failed,
                "bootstrap_failed_fraction": failed_fraction,
                "passed": passed,
            }
        )
    return results


def formula_for_terms(
    terms: list[str], y_t: float, y_i: float, y_2: float
) -> str:
    pieces = ["Q_star"]
    mapping = {
        "a1": "a1*x",
        "a2": "a2*x^2",
        "a3": "a3*x^3",
        "b1": f"b1*L^({y_i:.12g})",
        "b2": f"b2*L^({y_2:.12g})",
        "c1": f"c1*x*L^({y_i:.12g})",
    }
    pieces.extend(mapping[term] for term in terms)
    return "Q_L=" + "+".join(pieces) + f"; x=(h-hc)*L^({y_t:.12g})"


def discarded_size_records(
    full_sizes: list[int],
    selected_sizes: list[int],
    discard_reason: str | None,
) -> list[dict[str, Any]]:
    missing = [size for size in full_sizes if size not in selected_sizes]
    if missing and discard_reason is None:
        raise AnalysisInputError("fit:missing-discard-reason")
    return [
        {"L": size, "reason_code": discard_reason}
        for size in missing
    ]


def fit_record(
    summary: dict[str, Any],
    *,
    spec: dict[str, Any],
    manifest_set_sha256: str,
    full_sizes: list[int],
    analysis: dict[str, Any],
    windows: dict[str, list[float]],
) -> dict[str, Any] | None:
    central = summary.get("central", {})
    if not central.get("converged"):
        return None
    if summary.get("bootstrap", {}).get("successful_resamples", 0) < 2:
        return None
    statistical_errors = summary.get("statistical_errors", {})
    estimates: dict[str, float] = {
        "hc": float(central["parameters"]["hc"]),
        "hc_sigma_stat": float(statistical_errors.get("hc", 0.0)),
        "Q_star": float(central["parameters"]["Q_star"]),
        "Q_star_sigma_stat": float(
            statistical_errors.get("Q_star", 0.0)
        ),
    }
    for term in summary["terms"]:
        estimates[term] = float(central["parameters"][term])
        estimates[f"{term}_sigma_stat"] = float(
            statistical_errors.get(term, 0.0)
        )
    window = windows[summary["field_window"]]
    fit_record_rejections = list(summary["rejection_reasons"])
    if not analysis["coverage_passed"]:
        fit_record_rejections.append("pending-production-coverage-campaign")
    record_accepted = summary["accepted"] and analysis["coverage_passed"]
    rejection_reason = (
        None
        if record_accepted
        else ",".join(sorted(set(fit_record_rejections)))
    )
    return {
        "schema_version": FIT_SCHEMA,
        "fit_id": summary["fit_id"],
        "lattice": "triangular",
        "classification": summary["classification"],
        "input_run_ids": [spec["run_id"]],
        "input_manifest_sha256": manifest_set_sha256,
        "observable": "binder_q",
        "estimator_id": PRIMARY_ESTIMATOR,
        "covariance_estimator": "independent-chain-diagonal",
        "formula": formula_for_terms(
            summary["terms"],
            summary["y_t"],
            summary["y_i"],
            summary["y_2"],
        ),
        "exponent_treatment": ", ".join(
            [
                f"fixed y_t={summary['y_t']:.12g}",
                f"fixed y_i={summary['y_i']:.12g}",
                *(
                    [f"fixed y_2={summary['y_2']:.12g}"]
                    if "b2" in summary["terms"]
                    else []
                ),
            ]
        ),
        "window": {
            "L_min": min(summary["sizes"]),
            "L_max": max(summary["sizes"]),
            "h_min": window[0],
            "h_max": window[-1],
            "beta_policy": "beta_h_equals_L",
            "discarded_sizes": discarded_size_records(
                full_sizes,
                summary["sizes"],
                summary.get("discard_reason"),
            ),
        },
        "optimizer": analysis["optimizer"],
        "bootstrap_seed": analysis["bootstrap_seed"],
        "parameters": {
            "parameter_order": list(central["parameter_names"]),
            "estimates": estimates,
            "covariance": summary["bootstrap_covariance"],
        },
        "diagnostics": {
            "converged": True,
            "degrees_of_freedom": int(central["degrees_of_freedom"]),
            "chi2": float(central["chi2"]),
            "p_value": float(central["p_value"]),
            "covariance_condition": float(
                central["covariance_condition"]
            ),
            "coverage_passed": analysis["coverage_passed"],
            "coverage_campaign_id": analysis["coverage_campaign_id"],
        },
        "accepted": record_accepted,
        "rejection_reason": rejection_reason,
    }


def public_fit_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in summary.items()
        if not key.startswith("_")
    }


def promotion_gate(
    primary: dict[str, Any] | None,
    variants: list[dict[str, Any]],
    *,
    gate: dict[str, Any],
    required_fit_ids: list[str],
) -> dict[str, Any]:
    checks = []
    if primary is None or not primary.get("accepted"):
        return {
            "passed": False,
            "checks": [
                {
                    "check": "primary-fit-accepted",
                    "passed": False,
                    "observed": None,
                    "threshold": True,
                }
            ],
            "accepted_variant_shifts": [],
        }
    central = primary["central"]["parameters"]
    errors = primary["statistical_errors"]
    hc_sigma = errors["hc"]
    q_sigma = errors["Q_star"]
    hc_combined = math.hypot(hc_sigma, gate["reference_hc_sigma"])
    q_combined = math.hypot(q_sigma, gate["reference_q_star_sigma"])
    hc_z = (
        abs(central["hc"] - gate["reference_hc"]) / hc_combined
        if hc_combined > 0
        else math.inf
    )
    q_z = (
        abs(central["Q_star"] - gate["reference_q_star"]) / q_combined
        if q_combined > 0
        else math.inf
    )
    checks.extend(
        [
            {
                "check": "primary-fit-accepted",
                "passed": True,
                "observed": True,
                "threshold": True,
            },
            {
                "check": "reference-hc-z",
                "passed": hc_z <= gate["max_reference_z"],
                "observed": hc_z,
                "threshold": gate["max_reference_z"],
            },
            {
                "check": "hc-sigma-stat",
                "passed": hc_sigma <= gate["max_hc_sigma_stat"],
                "observed": hc_sigma,
                "threshold": gate["max_hc_sigma_stat"],
            },
            {
                "check": "reference-Q-star-z",
                "passed": q_z <= gate["max_q_star_reference_z"],
                "observed": q_z,
                "threshold": gate["max_q_star_reference_z"],
            },
        ]
    )
    variants_by_id = {
        variant["fit_id"]: variant for variant in variants
    }
    for fit_id in required_fit_ids:
        variant = variants_by_id.get(fit_id)
        accepted = bool(variant is not None and variant.get("accepted"))
        checks.append(
            {
                "check": f"required-robustness-fit:{fit_id}",
                "passed": accepted,
                "observed": (
                    variant.get("rejection_reasons", [])
                    if variant is not None
                    else "missing"
                ),
                "threshold": "accepted",
            }
        )
    variant_shifts = []
    for variant in variants:
        if not variant.get("accepted"):
            continue
        variant_hc = variant["central"]["parameters"]["hc"]
        primary_samples = primary["_bootstrap_hc_by_index"]
        variant_samples = variant["_bootstrap_hc_by_index"]
        common_indices = [
            index
            for index, (primary_value, variant_value) in enumerate(
                zip(primary_samples, variant_samples)
            )
            if primary_value is not None and variant_value is not None
        ]
        paired_deltas = [
            variant_samples[index] - primary_samples[index]
            for index in common_indices
        ]
        paired_sigma = (
            float(np.std(paired_deltas, ddof=1))
            if len(paired_deltas) >= 2
            else None
        )
        central_delta = variant_hc - central["hc"]
        if paired_sigma is None:
            shift_sigma = math.inf
        elif paired_sigma > 0:
            shift_sigma = abs(central_delta) / paired_sigma
        else:
            shift_sigma = 0.0 if central_delta == 0 else math.inf
        passed = (
            len(common_indices) >= 2
            and shift_sigma <= gate["max_variant_shift_paired_sigma"]
        )
        variant_shifts.append(
            {
                "fit_id": variant["fit_id"],
                "delta_hc": central_delta,
                "paired_delta_mean": (
                    float(np.mean(paired_deltas))
                    if paired_deltas
                    else None
                ),
                "paired_delta_sigma": paired_sigma,
                "paired_delta_ci95": (
                    [
                        float(np.quantile(paired_deltas, 0.025)),
                        float(np.quantile(paired_deltas, 0.975)),
                    ]
                    if paired_deltas
                    else [None, None]
                ),
                "common_successful_resample_count": len(common_indices),
                "common_successful_resample_indices": common_indices,
                "shift_in_paired_sigma": shift_sigma,
                "passed": passed,
            }
        )
    checks.append(
        {
            "check": "accepted-variant-shifts",
            "passed": all(row["passed"] for row in variant_shifts),
            "observed": (
                max(
                    (
                        row["shift_in_paired_sigma"]
                        for row in variant_shifts
                    ),
                    default=0.0,
                )
            ),
            "threshold": gate["max_variant_shift_paired_sigma"],
        }
    )
    return {
        "passed": all(row["passed"] for row in checks),
        "checks": checks,
        "accepted_variant_shifts": variant_shifts,
    }


def write_pooled_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = (
        "L",
        "h",
        "estimator_id",
        "spacetime_binder",
        "spacetime_binder_se",
        "within_chain_se",
        "between_chain_se",
        "diagnostic_estimator_id",
        "equal_time_binder",
        "equal_time_binder_se",
        "seed_count",
        "seeds",
    )
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            output = {key: row[key] for key in columns}
            output["seeds"] = ";".join(str(seed) for seed in row["seeds"])
            writer.writerow(output)


def make_crossing_plot(
    path: Path, pooled_rows: list[dict[str, Any]], crossing_fits: list[dict[str, Any]]
) -> None:
    figure, axis = plt.subplots(figsize=(7.2, 4.8))
    sizes = sorted({row["L"] for row in pooled_rows})
    colors = plt.get_cmap("viridis")(np.linspace(0.08, 0.92, len(sizes)))
    for color, size in zip(colors, sizes):
        rows = sorted(
            (row for row in pooled_rows if row["L"] == size),
            key=lambda row: row["h"],
        )
        axis.errorbar(
            [row["h"] for row in rows],
            [row["spacetime_binder"] for row in rows],
            yerr=[row["spacetime_binder_se"] for row in rows],
            marker="o",
            markersize=3.5,
            linewidth=1.0,
            capsize=2,
            color=color,
            label=f"L={size}",
        )
    for fit in crossing_fits:
        if fit.get("crossing") is not None:
            axis.axvline(
                fit["crossing"],
                color="#555555",
                linewidth=0.7,
                alpha=0.35,
            )
    axis.set_xlabel("h/J")
    axis.set_ylabel("space-time Binder ratio Q")
    axis.set_title("Triangular literal-aspect Binder crossings")
    axis.grid(alpha=0.2)
    axis.legend(frameon=False, fontsize=8, ncol=2)
    figure.tight_layout()
    figure.savefig(
        path,
        dpi=180,
        bbox_inches="tight",
        metadata={"Software": "yanwang148"},
    )
    plt.close(figure)


def make_residual_plot(path: Path, primary: dict[str, Any]) -> None:
    sizes = np.asarray(primary["_fit_sizes"])
    fields = np.asarray(primary["_fit_fields"])
    values = np.asarray(primary["_fit_values"])
    errors = np.asarray(primary["_fit_errors"])
    predictions = np.asarray(primary["_predictions"])
    residuals = np.asarray(primary["_residuals"])
    figure, (axis_data, axis_residual) = plt.subplots(
        1, 2, figsize=(10.0, 4.3)
    )
    unique_sizes = sorted(set(int(value) for value in sizes))
    colors = plt.get_cmap("viridis")(
        np.linspace(0.08, 0.92, len(unique_sizes))
    )
    for color, size in zip(colors, unique_sizes):
        selected = sizes == size
        order = np.argsort(fields[selected])
        axis_data.errorbar(
            fields[selected][order],
            values[selected][order],
            yerr=errors[selected][order],
            fmt="o",
            markersize=3.5,
            capsize=2,
            color=color,
            label=f"L={size}",
        )
        axis_data.plot(
            fields[selected][order],
            predictions[selected][order],
            "-",
            linewidth=1.0,
            color=color,
        )
        axis_residual.plot(
            fields[selected][order],
            residuals[selected][order],
            "o",
            markersize=3.5,
            color=color,
        )
    axis_data.set_xlabel("h/J")
    axis_data.set_ylabel("space-time Binder ratio Q")
    axis_data.set_title("Historical finite-size fit")
    axis_data.grid(alpha=0.2)
    axis_data.legend(frameon=False, fontsize=8)
    axis_residual.axhline(0.0, color="#333333", linewidth=0.8)
    axis_residual.set_xlabel("h/J")
    axis_residual.set_ylabel("(data - fit) / standard error")
    axis_residual.set_title("Normalized residuals")
    axis_residual.grid(alpha=0.2)
    figure.tight_layout()
    figure.savefig(
        path,
        dpi=180,
        bbox_inches="tight",
        metadata={"Software": "yanwang148"},
    )
    plt.close(figure)


def output_checksums(out_dir: Path, paths: list[Path]) -> None:
    rows = []
    for path in sorted(set(paths)):
        rows.append(f"{sha256_file(path)}  {path.relative_to(out_dir)}")
    (out_dir / "SHA256SUMS").write_text("\n".join(rows) + "\n")


def analyze(run_spec_path: Path, out_dir: Path) -> tuple[dict[str, Any], int]:
    spec_bytes = run_spec_path.read_bytes()
    spec = load_strict_json_bytes(spec_bytes, "run-spec")
    source_plan, _, source_plan_sha256 = load_bound_source_plan(
        spec, run_spec_path
    )
    frozen = validate_frozen_plan(spec, source_plan)
    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA,
        "run_id": spec.get("run_id"),
        "run_spec_sha256": sha256_bytes(spec_bytes),
        "source_plan_sha256": source_plan_sha256,
        "estimator_id": PRIMARY_ESTIMATOR,
        "diagnostic_estimator_id": DIAGNOSTIC_ESTIMATOR,
        "technical_gate": {
            "passed": False,
            "errors": list(frozen["errors"]),
        },
        "cell_checks": [],
        "pooled_rows": [],
        "crossing_fits": [],
        "fits": [],
        "pilot_promotion_gate": {
            "passed": False,
            "checks": [],
            "accepted_variant_shifts": [],
        },
        "passed_attempt_gate": False,
        "passed_pilot_gate": False,
        "production_result": False,
    }
    written_paths: list[Path] = []
    if not frozen["passed"]:
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path = out_dir / "report.json"
        write_json(report_path, report)
        written_paths.append(report_path)
        output_checksums(out_dir, written_paths)
        return report, 2

    cells = validate_cells(spec, frozen, run_spec_path)
    report["cell_checks"] = cells["cell_checks"]
    report["technical_gate"].update(
        {
            "passed": cells["passed"],
            "errors": cells["errors"],
            "expected_cell_count": cells["expected_cell_count"],
            "observed_spec_cell_count": cells["observed_spec_cell_count"],
            "valid_cell_count": cells["valid_cell_count"],
            "extra_manifest_cells": cells["extra_manifest_cells"],
            "extra_scheduler_manifests": cells[
                "extra_scheduler_manifests"
            ],
            "manifest_set_sha256": cells["manifest_set_sha256"],
        }
    )
    pooled_rows, pooling_errors = pool_rows(
        cells["valid_rows"],
        frozen["analysis"]["sizes"],
        frozen["analysis"]["fields"],
        frozen["analysis"]["seeds"],
    )
    if pooling_errors:
        report["technical_gate"]["passed"] = False
        report["technical_gate"]["errors"] = sorted(
            set(report["technical_gate"]["errors"] + pooling_errors)
        )
    report["pooled_rows"] = pooled_rows
    out_dir.mkdir(parents=True, exist_ok=True)
    pooled_path = out_dir / "pooled-spacetime-binder.csv"
    write_pooled_csv(pooled_path, pooled_rows)
    written_paths.append(pooled_path)
    if not report["technical_gate"]["passed"]:
        report_path = out_dir / "report.json"
        write_json(report_path, report)
        written_paths.append(report_path)
        output_checksums(out_dir, written_paths)
        return report, 2

    analysis = frozen["analysis"]
    gate = frozen["gate"]
    crossing_fits = crossing_analysis(
        pooled_rows,
        sizes=analysis["sizes"],
        window=analysis["windows"]["outer"],
        bootstrap_resamples=analysis["crossing_bootstrap_resamples"],
        bootstrap_seed=analysis["crossing_bootstrap_seed"],
        gate=gate,
    )
    report["crossing_fits"] = crossing_fits
    crossing_path = out_dir / "crossings.json"
    write_json(crossing_path, crossing_fits)
    written_paths.append(crossing_path)
    fit_bootstrap_draws = shared_bootstrap_draws(
        cells["valid_rows"],
        analysis["sizes"],
        analysis["fields"],
        resamples=analysis["bootstrap_resamples"],
        seed=analysis["bootstrap_seed"],
    )

    primary_spec = {
        "fit_id": analysis["primary_fit_id"],
        "classification": "primary",
        "sizes": analysis["sizes"],
        "field_window": "primary",
        "y_t": analysis["y_t"],
        "y_i": analysis["y_i"],
        "y_2": analysis["y_2"],
        "terms": analysis["primary_terms"],
    }
    variant_specs = [primary_spec, *analysis["variants"]]
    fit_summaries = []
    fit_records_dir = out_dir / "fits"
    primary_internal = None
    variant_internals = []
    for variant in variant_specs:
        summary = run_fit_variant(
            pooled_rows,
            fit_bootstrap_draws,
            variant,
            windows=analysis["windows"],
            outer_bounds=(
                min(analysis["windows"]["outer"]),
                max(analysis["windows"]["outer"]),
            ),
            analysis=analysis,
            gate=gate,
        )
        record = fit_record(
            summary,
            spec=spec,
            manifest_set_sha256=cells["manifest_set_sha256"],
            full_sizes=analysis["sizes"],
            analysis=analysis,
            windows=analysis["windows"],
        )
        if record is not None:
            record_path = fit_records_dir / f"{summary['fit_id']}.json"
            write_json(record_path, record)
            written_paths.append(record_path)
            summary["fit_record"] = str(record_path.relative_to(out_dir))
        if summary["classification"] == "primary":
            primary_internal = summary
        else:
            variant_internals.append(summary)
        fit_summaries.append(public_fit_summary(summary))
    report["fits"] = fit_summaries

    promotion = promotion_gate(
        primary_internal,
        variant_internals,
        gate=gate,
        required_fit_ids=analysis["robustness_required_fit_ids"],
    )
    report["pilot_promotion_gate"] = promotion
    crossing_gate_passed = bool(
        len(crossing_fits) == len(analysis["sizes"]) - 1
        and (
            all(row["passed"] for row in crossing_fits)
            if gate["require_all_adjacent_crossings"]
            else True
        )
    )
    report["crossing_gate_passed"] = crossing_gate_passed
    report["passed_attempt_gate"] = bool(
        report["technical_gate"]["passed"]
        and crossing_gate_passed
        and promotion["passed"]
    )
    report["passed_pilot_gate"] = report["passed_attempt_gate"]

    crossing_plot = out_dir / "spacetime-binder-crossings.png"
    make_crossing_plot(crossing_plot, pooled_rows, crossing_fits)
    written_paths.append(crossing_plot)
    if primary_internal is not None and primary_internal.get("central"):
        residual_plot = out_dir / "fss-residuals.png"
        make_residual_plot(residual_plot, primary_internal)
        written_paths.append(residual_plot)

    robustness_path = out_dir / "robustness.csv"
    with robustness_path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "fit_id",
                "classification",
                "accepted",
                "hc",
                "hc_sigma_stat",
                "p_value",
                "covariance_condition",
                "rejection_reasons",
            ]
        )
        for summary in fit_summaries:
            central = summary.get("central", {})
            parameters = central.get("parameters", {})
            errors = summary.get("statistical_errors", {})
            writer.writerow(
                [
                    summary["fit_id"],
                    summary["classification"],
                    summary["accepted"],
                    parameters.get("hc"),
                    errors.get("hc"),
                    central.get("p_value"),
                    central.get("covariance_condition"),
                    ";".join(summary["rejection_reasons"]),
                ]
            )
    written_paths.append(robustness_path)
    report_path = out_dir / "report.json"
    write_json(report_path, report)
    written_paths.append(report_path)
    output_checksums(out_dir, written_paths)
    return report, 0 if report["passed_attempt_gate"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-spec", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.out_dir.is_symlink() or (
        args.out_dir.exists()
        and (
            not args.out_dir.is_dir()
            or any(args.out_dir.iterdir())
        )
    ):
        print(
            "error: --out-dir must be absent or an empty non-symlink directory",
            file=sys.stderr,
        )
        return 2
    try:
        report, return_code = analyze(args.run_spec, args.out_dir)
    except (AnalysisInputError, OSError, json.JSONDecodeError) as exception:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        report = {
            "schema_version": REPORT_SCHEMA,
            "run_id": None,
            "technical_gate": {
                "passed": False,
                "errors": [f"fatal:{type(exception).__name__}:{exception}"],
            },
            "cell_checks": [],
            "pooled_rows": [],
            "crossing_fits": [],
            "fits": [],
            "pilot_promotion_gate": {
                "passed": False,
                "checks": [],
                "accepted_variant_shifts": [],
            },
            "passed_attempt_gate": False,
            "passed_pilot_gate": False,
            "production_result": False,
        }
        report_path = args.out_dir / "report.json"
        write_json(report_path, report)
        output_checksums(args.out_dir, [report_path])
        return_code = 2
    print(
        json.dumps(
            {
                "technical_gate": report["technical_gate"]["passed"],
                "crossing_gate": report.get("crossing_gate_passed", False),
                "pilot_promotion_gate": report["pilot_promotion_gate"]["passed"],
                "passed_pilot_gate": report["passed_pilot_gate"],
                "passed_attempt_gate": report["passed_attempt_gate"],
            },
            sort_keys=True,
        )
    )
    return return_code


if __name__ == "__main__":
    sys.exit(main())
