#!/usr/bin/env python3
"""Verify ALF frozen estimators against C++ replay of identical paths."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

from path_archive import ArchiveReader, ArchiveRecord
from prepare_alf_chain import atomic_json
from run_bulk_replay import compare_summaries


def trial_log_shifts(trial_manifest: Path) -> dict[str, float]:
    """Map ALF's normalized boundary determinants to raw trial orbitals."""
    data = json.loads(trial_manifest.read_text())
    overlaps = data.get("spin_overlap_determinants")
    if not isinstance(overlaps, dict) or set(overlaps) != {"up", "down"}:
        raise ValueError("trial manifest lacks spin overlap determinants")
    values = [float(overlaps[spin]) for spin in ("up", "down")]
    if any(not math.isfinite(value) or value <= 0.0 for value in values):
        raise ValueError("trial overlap determinants must be positive")
    return {
        "II": 0.0,
        "TI": sum(math.log(value) for value in values),
    }


def _finite_energy(row: Mapping[str, str], key: str) -> float:
    value = float(row[key])
    if not math.isfinite(value):
        raise ValueError(f"non-finite replay energy {key}")
    return value


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values or not 0.0 <= probability <= 1.0:
        raise ValueError("quantile needs values and probability in [0,1]")
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    fraction = position - lower
    return (
        ordered[lower] * (1.0 - fraction)
        + ordered[upper] * fraction
    )


def validate_rows(
    rows: Sequence[Mapping[str, str]],
    sources: Mapping[int, tuple[str, ArchiveRecord]],
    *,
    energy_tolerance: float = 1.0e-8,
    determinant_tolerance: float = 1.0e-8,
    identity_tolerance: float = 1.0e-9,
) -> dict:
    if not rows or min(
        energy_tolerance, determinant_tolerance, identity_tolerance
    ) <= 0.0:
        raise ValueError("replay validation needs rows and positive tolerances")
    row_ids = [int(row["sample_id"]) for row in rows]
    if len(row_ids) != len(set(row_ids)):
        raise ValueError("duplicate replay sample")
    if set(row_ids) != set(sources):
        raise ValueError("replay/source sample IDs differ")

    maximum_energy = 0.0
    maximum_endpoint_energy = 0.0
    maximum_logd = 0.0
    maximum_identity = 0.0
    failed: dict[int, list[str]] = {}
    ambiguous: dict[int, list[str]] = {}
    energy_residuals: list[float] = []
    identity_residuals: list[float] = []
    for row in rows:
        sample_id = int(row["sample_id"])
        source_ensemble, record = sources[sample_id]
        ensemble = str(row["ensemble"])
        reasons: list[str] = []
        if ensemble != source_ensemble:
            reasons.append("ensemble_mismatch")
        if not record.endpoint_present:
            reasons.append("missing_alf_endpoint")

        central_key = (
            "central_ii_etot" if ensemble == "II" else "central_ti_etot"
        )
        endpoint_key = (
            "endpoint_i_etot" if ensemble == "II" else "endpoint_t_etot"
        )
        sign_key = (
            "sign_d_alf_ii" if ensemble == "II" else "sign_d_alf_ti"
        )
        logd_key = (
            "logabs_d_alf_ii"
            if ensemble == "II"
            else "logabs_d_alf_ti"
        )
        energy_values = {
            key: _finite_energy(row, key)
            for key in (
                "central_ii_ekin", "central_ii_epot", "central_ii_etot",
                "central_ti_ekin", "central_ti_epot", "central_ti_etot",
                "endpoint_i_etot", "endpoint_t_etot",
                "alf_frozen_etot", "alf_endpoint_etot",
            )
        }
        central_residuals = (
            abs(energy_values[central_key] - record.central_etot),
            abs(energy_values["alf_frozen_etot"] - record.central_etot),
            abs(
                energy_values["central_ii_etot"]
                - energy_values["central_ii_ekin"]
                - energy_values["central_ii_epot"]
            ),
            abs(
                energy_values["central_ti_etot"]
                - energy_values["central_ti_ekin"]
                - energy_values["central_ti_epot"]
            ),
        )
        endpoint_residuals = (
            abs(energy_values[endpoint_key] - record.endpoint_etot),
            abs(energy_values["alf_endpoint_etot"] - record.endpoint_etot),
        )
        energy_residual = max(central_residuals)
        endpoint_energy_residual = max(endpoint_residuals)
        maximum_energy = max(maximum_energy, energy_residual)
        maximum_endpoint_energy = max(
            maximum_endpoint_energy, endpoint_energy_residual
        )
        energy_residuals.append(energy_residual)
        if energy_residual >= energy_tolerance:
            ambiguous.setdefault(sample_id, []).append("energy_residual")

        sign = int(row[sign_key])
        logd = float(row[logd_key])
        alf_to_raw_log_shift = float(
            row.get("_alf_to_raw_log_shift", "0")
        )
        if sign != record.endpoint_sign:
            reasons.append("endpoint_sign")
        if math.isfinite(logd) and math.isfinite(record.endpoint_logabs_d):
            logd_residual = abs(
                logd
                - (record.endpoint_logabs_d + alf_to_raw_log_shift)
            )
        elif logd == record.endpoint_logabs_d:
            logd_residual = 0.0
        else:
            logd_residual = math.inf
        maximum_logd = max(maximum_logd, logd_residual)
        if logd_residual >= determinant_tolerance:
            reasons.append("endpoint_logd")

        identity = float(row["identity_log_residual"])
        if int(row["alive"]):
            if not math.isfinite(identity):
                identity = math.inf
            maximum_identity = max(maximum_identity, abs(identity))
            identity_residuals.append(abs(identity))
            if abs(identity) >= identity_tolerance:
                ambiguous.setdefault(sample_id, []).append("alive_identity")
        if reasons:
            failed[sample_id] = reasons

    energy_p95 = _quantile(energy_residuals, 0.95)
    identity_p99 = _quantile(identity_residuals, 0.99)
    ambiguity_fraction = len(ambiguous) / len(rows)
    replay_numerical_pass = (
        energy_p95 < energy_tolerance
        and identity_p99 < identity_tolerance
        and ambiguity_fraction <= 0.05
    )
    return {
        "schema_version": 1,
        "energy_tolerance": energy_tolerance,
        "determinant_tolerance": determinant_tolerance,
        "identity_tolerance": identity_tolerance,
        "samples": len(rows),
        "max_energy_residual": maximum_energy,
        "max_endpoint_energy_residual": maximum_endpoint_energy,
        "max_endpoint_logd_residual": maximum_logd,
        "max_path_logd_residual": maximum_logd,
        "max_alive_identity_residual": maximum_identity,
        "energy_p95_residual": energy_p95,
        "identity_p99_residual": identity_p99,
        "numerical_ambiguity_fraction": ambiguity_fraction,
        "replay_numerical_pass": replay_numerical_pass,
        "failed_sample_ids": sorted(failed),
        "failure_reasons": {
            str(sample_id): failed[sample_id] for sample_id in sorted(failed)
        },
        "numerically_ambiguous_sample_ids": sorted(ambiguous),
        "numerical_ambiguity_reasons": {
            str(sample_id): ambiguous[sample_id]
            for sample_id in sorted(ambiguous)
        },
        "passed": not failed and replay_numerical_pass,
    }


def load_sources(
    archive_index: Path,
    sample_manifest: Path,
) -> tuple[dict[int, tuple[str, ArchiveRecord]], dict[int, tuple[str, int]]]:
    requested: dict[int, tuple[str, int]] = {}
    with sample_manifest.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["sample_id", "ensemble", "chain"]:
            raise ValueError("unexpected sample manifest columns")
        for row in reader:
            sample_id = int(row["sample_id"])
            if sample_id in requested:
                raise ValueError("duplicate requested sample")
            requested[sample_id] = (row["ensemble"], int(row["chain"]))
    index = json.loads(archive_index.read_text())
    sources: dict[int, tuple[str, ArchiveRecord]] = {}
    for entry in index.get("entries", []):
        ensemble = str(entry["ensemble"])
        chain = int(entry["chain"])
        path = Path(entry["path"])
        if not path.is_absolute():
            path = (archive_index.parent / path).resolve()
        for record in ArchiveReader(path).records():
            expected = requested.get(record.sample_id)
            if expected is None:
                continue
            if expected != (ensemble, chain):
                raise ValueError("sample manifest/archive identity mismatch")
            if record.sample_id in sources:
                raise ValueError("sample appears in more than one archive")
            sources[record.sample_id] = (ensemble, record)
    if set(sources) != set(requested):
        raise ValueError("requested sample is absent from archives")
    return sources, requested


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    bridge = root / "test/pqmc_cp_bridge"
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-index", type=Path, required=True)
    parser.add_argument("--sample-manifest", type=Path, required=True)
    parser.add_argument("--summary", type=Path, nargs="+", required=True)
    parser.add_argument(
        "--trial-manifest", type=Path,
        default=bridge / "assets/trials/trial_manifest.json",
    )
    parser.add_argument(
        "--output", type=Path,
        default=bridge / "results/replay_validation.json",
    )
    parser.add_argument(
        "--failure-manifest", type=Path,
        default=bridge / "replay/manifests/replay_failures.csv",
    )
    args = parser.parse_args()

    sources, identities = load_sources(
        args.archive_index, args.sample_manifest
    )
    log_shifts = trial_log_shifts(args.trial_manifest)
    with args.summary[0].open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        ensemble = str(row["ensemble"])
        if ensemble not in log_shifts:
            raise ValueError(f"unknown replay ensemble: {ensemble}")
        row["_alf_to_raw_log_shift"] = repr(log_shifts[ensemble])
    result = validate_rows(rows, sources)
    result["alf_to_raw_log_shift"] = log_shifts
    if len(args.summary) > 1:
        result["stabilization"] = compare_summaries(args.summary)
        result["passed"] = (
            result["passed"] and result["stabilization"]["passed"]
        )
    atomic_json(args.output, result)

    args.failure_manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.failure_manifest.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sample_id", "ensemble", "chain"])
        review_ids = sorted(set(result["failed_sample_ids"]) | set(
            result["numerically_ambiguous_sample_ids"]
        ))
        for sample_id in review_ids:
            writer.writerow([sample_id, *identities[sample_id]])
    print(
        f"replay validation: samples={result['samples']} "
        f"passed={result['passed']}",
        flush=True,
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
