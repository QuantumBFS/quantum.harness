"""Fail-closed validation for one completed production-v2 dataset."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from .research_dataset import file_sha256, load_research_dataset
from .tenpy_research_backend import (
    canonical_job_sha256,
    output_times,
    resolve_numerics,
    site_coordinates,
)

MAGNETIZATION_CONSERVATION_TOLERANCE = 1e-10
NUMERICAL_ABSOLUTE_TOLERANCE = 1e-12


def _same_json(left: Any, right: Any) -> bool:
    return json.dumps(
        left,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ) == json.dumps(
        right,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _finite(value: Any) -> bool:
    array = np.asarray(value)
    return bool(
        np.all(np.isfinite(np.real(array)))
        and np.all(np.isfinite(np.imag(array)))
    )


def _expected_numerics(job: Mapping[str, Any]) -> dict[str, Any]:
    numerics = resolve_numerics(job)
    if job.get("fcs_gamma") is not None:
        numerics["fcs_gamma"] = [
            float(value) for value in job["fcs_gamma"]
        ]
    return numerics


def _metadata_matches(
    job: Mapping[str, Any],
    metadata: Mapping[str, Any],
    numerics: Mapping[str, Any],
) -> list[str]:
    condition = dict(job["condition"])
    expected = {
        "delta": condition["delta"],
        "J2": condition["j2"],
        "temperature": condition["temperature"],
        "mu": condition["mu"],
        "orientation": condition["orientation"],
        "profile": condition["profile"],
        "width": condition["width"],
        "background_m": condition["background_m"],
        "L": numerics["L"],
        "time_step": numerics["dt"],
        "chi_max": numerics["chi_max"],
        "truncation_cutoff": numerics["truncation_cutoff"],
        "job_id": job["job_id"],
        "stage": "production_a",
        "smoke_test": False,
    }
    errors: list[str] = []
    for key, value in expected.items():
        observed = metadata.get(key)
        if isinstance(value, float):
            try:
                matches = np.isclose(
                    float(observed),
                    value,
                    rtol=0.0,
                    atol=NUMERICAL_ABSOLUTE_TOLERANCE,
                )
            except (TypeError, ValueError):
                matches = False
        else:
            matches = observed == value
        if not matches:
            errors.append(f"metadata_mismatch:{key}")
    return errors


def validate_production_output(
    job: Mapping[str, Any],
    output: str | Path,
    *,
    conservation_tolerance: float = (
        MAGNETIZATION_CONSERVATION_TOLERANCE
    ),
) -> dict[str, Any]:
    """Validate exact job identity, observables, numerics, FCS, and conservation."""

    path = Path(output)
    summary_path = path.with_suffix(".run.json")
    checkpoint = path.with_suffix(path.suffix + ".checkpoint.h5")
    errors: list[str] = []
    diagnostics: dict[str, Any] = {}
    report: dict[str, Any] = {
        "schema_version": 1,
        "job_id": str(job.get("job_id", "")),
        "output": str(path),
        "status": "invalid",
        "errors": errors,
        "diagnostics": diagnostics,
    }
    if not path.is_file():
        errors.append("dataset_missing")
        report["status"] = "missing"
        return report
    if not summary_path.is_file():
        errors.append("run_summary_missing")
        return report
    if not checkpoint.is_file() or checkpoint.stat().st_size == 0:
        errors.append("checkpoint_missing_or_empty")

    try:
        summary = dict(json.loads(summary_path.read_text()))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        errors.append("run_summary_invalid")
        return report
    try:
        dataset = load_research_dataset(path)
    except (EOFError, KeyError, OSError, ValueError, json.JSONDecodeError):
        errors.append("dataset_invalid")
        return report

    report["dataset_sha256"] = file_sha256(path)
    report["run_summary_sha256"] = file_sha256(summary_path)
    numerics = _expected_numerics(job)
    expected_observables = [str(value) for value in job["observables"]]
    expected_times = output_times(numerics)
    expected_x = site_coordinates(int(numerics["L"]))

    if summary.get("status") != "complete":
        errors.append("run_status_not_complete")
    if summary.get("job_id") != job.get("job_id"):
        errors.append("run_job_id_mismatch")
    try:
        recorded_output = Path(str(summary.get("output", ""))).resolve()
    except (OSError, ValueError):
        recorded_output = Path()
    if recorded_output != path.resolve():
        errors.append("run_output_path_mismatch")
    if summary.get("smoke") is not False:
        errors.append("smoke_output_forbidden")
    if not _same_json(
        summary.get("effective_numerics"),
        numerics,
    ):
        errors.append("effective_numerics_mismatch")
    if summary.get("produced_observables") != expected_observables:
        errors.append("run_observable_set_mismatch")
    if summary.get("omitted_observables") != []:
        errors.append("run_omitted_observables_nonempty")
    if str(summary.get("checkpoint", "")) != str(checkpoint):
        errors.append("run_checkpoint_path_mismatch")

    if dataset.condition_id != job.get("condition_id"):
        errors.append("dataset_condition_id_mismatch")
    if dataset.t.shape != expected_times.shape or not np.allclose(
        dataset.t,
        expected_times,
        rtol=0.0,
        atol=NUMERICAL_ABSOLUTE_TOLERANCE,
    ):
        errors.append("time_grid_mismatch")
    if dataset.x.shape != expected_x.shape or not np.array_equal(
        dataset.x,
        expected_x,
    ):
        errors.append("space_grid_mismatch")
    diagnostics["time_points"] = int(dataset.t.size)
    diagnostics["space_points"] = int(dataset.x.size)

    metadata = dataset.metadata
    errors.extend(_metadata_matches(job, metadata, numerics))
    if metadata.get("requested_observables") != expected_observables:
        errors.append("metadata_requested_observables_mismatch")
    if metadata.get("produced_observables") != expected_observables:
        errors.append("metadata_produced_observables_mismatch")
    if metadata.get("omitted_observables") != []:
        errors.append("metadata_omitted_observables_nonempty")
    if str(metadata.get("checkpoint_path", "")) != str(checkpoint):
        errors.append("metadata_checkpoint_path_mismatch")
    expected_hash = canonical_job_sha256(job, numerics)
    if metadata.get("raw_sha256") != expected_hash:
        errors.append("canonical_job_sha256_mismatch")

    presence = {
        "magnetization": dataset.m is not None,
        "local_spin_current": dataset.current is not None,
        "czz": dataset.czz is not None,
        "fcs_logZ": (
            dataset.fcs_gamma is not None
            and dataset.fcs_logZ is not None
        ),
    }
    for observable, present in presence.items():
        expected = observable in expected_observables
        if present is not expected:
            errors.append(
                f"observable_presence_mismatch:{observable}"
            )
    for name, value in (
        ("m", dataset.m),
        ("current", dataset.current),
        ("czz", dataset.czz),
        ("fcs_logZ", dataset.fcs_logZ),
    ):
        if value is not None and not _finite(value):
            errors.append(f"nonfinite_observable:{name}")

    if dataset.m is not None:
        normalized = (
            np.asarray(dataset.m, dtype=float)
            - float(job["condition"]["background_m"])
        ) / float(job["condition"]["mu"])
        normalization_error = float(
            np.max(np.abs(normalized - dataset.u))
        )
        diagnostics["normalization_max_abs"] = normalization_error
        if normalization_error > NUMERICAL_ABSOLUTE_TOLERANCE:
            errors.append("normalized_field_mismatch")
        totals = np.sum(np.asarray(dataset.m, dtype=float), axis=1)
        drift = float(np.max(np.abs(totals - totals[0])))
        diagnostics["magnetization_drift_max_abs"] = drift
        if drift > float(conservation_tolerance):
            errors.append("magnetization_conservation_failed")
        try:
            reported_drift = float(
                summary["maximum_total_magnetization_drift"]
            )
        except (KeyError, TypeError, ValueError):
            reported_drift = float("nan")
        if (
            not np.isfinite(reported_drift)
            or reported_drift > float(conservation_tolerance)
            or not np.isclose(
                reported_drift,
                drift,
                rtol=0.0,
                atol=NUMERICAL_ABSOLUTE_TOLERANCE,
            )
        ):
            errors.append("reported_magnetization_drift_invalid")

    maximum_chi = summary.get("maximum_chi_observed")
    try:
        maximum_chi_value = int(maximum_chi)
    except (TypeError, ValueError):
        maximum_chi_value = -1
    diagnostics["maximum_chi_observed"] = maximum_chi_value
    if not 1 <= maximum_chi_value <= int(numerics["chi_max"]):
        errors.append("maximum_chi_invalid")
    try:
        discarded = float(summary["discarded_weight_cumulative"])
    except (KeyError, TypeError, ValueError):
        discarded = float("nan")
    diagnostics["discarded_weight_cumulative"] = discarded
    if not np.isfinite(discarded) or discarded < 0.0:
        errors.append("discarded_weight_invalid")

    if "fcs_logZ" in expected_observables:
        gamma = np.asarray(dataset.fcs_gamma, dtype=float)
        logz = np.asarray(dataset.fcs_logZ, dtype=complex)
        expected_gamma = np.asarray(job["fcs_gamma"], dtype=float)
        if not np.array_equal(gamma, expected_gamma):
            errors.append("fcs_gamma_mismatch")
        if logz.shape != (expected_times.size, expected_gamma.size):
            errors.append("fcs_shape_mismatch")
        elif _finite(logz):
            z = np.exp(logz)
            conjugacy = float(
                np.max(np.abs(z - np.conj(z[:, ::-1])))
            )
            zero_indices = np.flatnonzero(
                np.isclose(gamma, 0.0, rtol=0.0, atol=1e-13)
            )
            zero_error = (
                float(np.max(np.abs(z[:, zero_indices[0]] - 1.0)))
                if zero_indices.size == 1
                else float("inf")
            )
            diagnostics["fcs_conjugacy_max_abs"] = conjugacy
            diagnostics["fcs_zero_field_max_abs"] = zero_error
            if conjugacy > NUMERICAL_ABSOLUTE_TOLERANCE:
                errors.append("fcs_conjugacy_failed")
            if zero_error > NUMERICAL_ABSOLUTE_TOLERANCE:
                errors.append("fcs_zero_field_failed")
        expected_branches = int(
            np.sum(
                (expected_gamma > 0.0)
                & ~np.isclose(
                    expected_gamma,
                    0.0,
                    rtol=0.0,
                    atol=1e-13,
                )
            )
        )
        if summary.get("fcs_branch_count") != expected_branches:
            errors.append("fcs_branch_count_mismatch")
    elif summary.get("fcs_branch_count") != 0:
        errors.append("unexpected_fcs_branch")

    report["status"] = "valid" if not errors else "invalid"
    return report
