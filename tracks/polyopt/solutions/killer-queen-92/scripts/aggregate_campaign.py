#!/usr/bin/env python3
"""Aggregate cell JSON into long-form tables without silently dropping cells."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path


COMMON = (
    "id", "campaign", "geometry", "point", "t", "U", "mu", "nmax", "symmetry",
    "L", "d", "encoding", "basis_family", "kind", "gamma",
)

LEVEL_COMMON = ("geometry", "nmax", "symmetry", "L", "d", "encoding", "basis_family")
LEVEL_DETAILS = (
    "window_sites", "interior_sites", "induced_edges", "hamiltonian_degree",
    "moment_basis_count", "gap_basis_count", "stationarity_basis_count",
    "moment_variable_count", "real_scalar_variable_count", "equality_count",
    "moment_psd_block_count", "gap_psd_block_count", "moment_block_sizes",
    "gap_block_sizes", "moment_block_charges", "gap_block_charges",
    "real_psd_block_sizes", "certificate_coordinate_count",
    "affine_term_count", "estimated_memory_gb",
    "assembly_seconds", "actual_max_rss_gb", "requested_memory_gb", "requested_cpus",
    "production_requested_memory_gb", "production_requested_cpus",
    "model_build_seconds", "model_actual_max_rss_gb", "jump_variable_count",
    "model_build_solver", "model_build_status", "model_build_reason",
)
RECORD_DETAILS = (
    "classification", "raw_status", "solver", "runtime_seconds", "objective",
    "primal_residual", "dual_residual", "min_psd_eigenvalue",
    "certificate_class", "message",
)
CELL_RESOURCE_DETAILS = (
    "cell_wall_seconds", "cell_actual_max_rss_gb", "cell_allocated_cpus",
    "cell_allocated_memory_gb", "cell_slurm_job_id", "cell_slurm_array_job_id",
    "cell_slurm_array_task_id",
)
SCIENTIFIC_CLASSIFICATIONS = frozenset(("FEASIBLE", "EXCLUDED", "UNKNOWN"))


def scientific_classification(value: object) -> str:
    result = str(value if value is not None else "UNKNOWN").upper()
    if result not in SCIENTIFIC_CLASSIFICATIONS:
        raise ValueError(f"invalid scientific classification {result!r}")
    return result


def cell_resource_details(payload: dict[str, object] | None) -> dict[str, object]:
    runner = payload.get("runner", {}) if payload else {}
    return {
        "cell_wall_seconds": runner.get("wall_seconds"),
        "cell_actual_max_rss_gb": runner.get("max_rss_gb"),
        "cell_allocated_cpus": runner.get("allocated_cpus"),
        "cell_allocated_memory_gb": runner.get("allocated_memory_gb"),
        "cell_slurm_job_id": runner.get("slurm_job_id"),
        "cell_slurm_array_job_id": runner.get("slurm_array_job_id"),
        "cell_slurm_array_task_id": runner.get("slurm_array_task_id"),
    }


def atomic_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def base_row(cell: dict[str, object]) -> dict[str, object]:
    row = {key: cell.get(key) for key in COMMON}
    if row.get("basis_family") is not None:
        row["basis_family"] = str(row["basis_family"]).upper()
    return row


def derived_level_details(metadata: dict[str, object]) -> dict[str, object]:
    """Backfill deterministic sizes in records written by older runners."""
    result = dict(metadata)
    if "certificate_coordinate_count" not in result and result.get("real_psd_block_sizes"):
        result["certificate_coordinate_count"] = int(result.get("equality_count", 0)) + sum(
            int(size) * (int(size) + 1) // 2
            for size in result["real_psd_block_sizes"]
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("results/campaign_manifest.json"))
    parser.add_argument("--cells", type=Path, default=Path("results/hierarchy_cells"))
    parser.add_argument("--dry-manifest", type=Path, default=Path("results/dry_level_manifest.json"))
    parser.add_argument("--dry-levels", type=Path, default=Path("results/dry_levels"))
    parser.add_argument("--dry-models", type=Path, default=Path("results/dry_models"))
    parser.add_argument("--output", type=Path, default=Path("results/tables"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    gaps: list[dict[str, object]] = []
    observables: list[dict[str, object]] = []
    levels: dict[tuple[object, ...], dict[str, object]] = {}
    solver_rows: list[dict[str, object]] = []
    certificate_rows: list[dict[str, object]] = []

    if args.dry_manifest.exists():
        dry_manifest = json.loads(args.dry_manifest.read_text())
        for dry_level in dry_manifest["levels"]:
            path = args.dry_levels / f"{dry_level['id']}.json"
            payload = json.loads(path.read_text()) if path.exists() else None
            metadata = derived_level_details(payload.get("level", {})) if payload else {}
            model_path = args.dry_models / f"{dry_level['id']}.json"
            model_payload = json.loads(model_path.read_text()) if model_path.exists() else None
            model_metadata = (
                derived_level_details(model_payload.get("level", {})) if model_payload else {}
            )
            basis_family = str(dry_level["basis_family"]).upper()
            base = {
                "geometry": dry_level["geometry"], "nmax": dry_level["nmax"],
                "symmetry": dry_level["symmetry"], "L": dry_level["L"],
                "d": dry_level["d"], "encoding": dry_level["encoding"],
                "basis_family": basis_family,
            }
            level_key = tuple(base[key] for key in LEVEL_COMMON)
            levels[level_key] = {
                **base,
                **metadata,
                "actual_max_rss_gb": (
                    payload.get("runner", {}).get("max_rss_gb") if payload else None
                ),
                "requested_memory_gb": dry_level["requested_memory_gb"],
                "requested_cpus": dry_level["requested_cpus"],
                "production_requested_memory_gb": dry_level["production_requested_memory_gb"],
                "production_requested_cpus": dry_level["production_requested_cpus"],
                "model_build_seconds": model_metadata.get("model_build_seconds"),
                "model_actual_max_rss_gb": (
                    model_payload.get("runner", {}).get("max_rss_gb") if model_payload else None
                ),
                "jump_variable_count": model_metadata.get("jump_variable_count"),
                "model_build_solver": model_metadata.get("model_build_solver"),
                "model_build_status": (
                    "BUILT" if model_payload and model_payload.get("status") == "COMPLETE"
                    else "ERROR" if model_payload else "UNKNOWN"
                ),
                "model_build_reason": (
                    "" if model_payload and model_payload.get("status") == "COMPLETE"
                    else model_payload.get("reason", "model build did not complete")
                    if model_payload else "model build not run"
                ),
                "assembly_status": (
                    "ASSEMBLED" if payload and payload.get("status") == "COMPLETE"
                    else "ERROR" if payload else "UNKNOWN"
                ),
                "reason": (
                    "" if payload and payload.get("status") == "COMPLETE"
                    else payload.get("reason", "dry assembly did not complete") if payload
                    else "dry level not run"
                ),
            }

    for cell in manifest["cells"]:
        path = args.cells / f"{cell['id']}.json"
        payload = json.loads(path.read_text()) if path.exists() else None
        base = base_row(cell)
        level = derived_level_details(payload.get("level", {})) if payload else {}
        level_key = tuple(base.get(key) for key in LEVEL_COMMON)
        if level_key not in levels or (level and levels[level_key]["assembly_status"] != "ASSEMBLED"):
            levels[level_key] = {
                **{key: base.get(key) for key in LEVEL_COMMON},
                **level,
                "assembly_status": "ASSEMBLED" if level else "UNKNOWN",
                "reason": "" if level else "cell not run",
            }
        reported_level = {**levels[level_key], **level}
        if cell["kind"] == "gap":
            if payload and payload.get("status") == "COMPLETE":
                lower, upper = payload.get("gap_bracket", (None, None))
                history = payload.get("history", [])
                records = [item.get("record", {}) for item in history]
                excluded = [record for record in records if record.get("classification") == "EXCLUDED"]
                upper_record = next(
                    (record for record in reversed(excluded)
                     if upper is not None and record.get("gamma") is not None
                     and abs(float(record["gamma"]) - float(upper)) <= 1e-12),
                    excluded[-1] if excluded else {},
                )
                row = {
                    **base,
                    **reported_level,
                    **cell_resource_details(payload),
                    "classification": scientific_classification(
                        payload.get("classification", "UNKNOWN")
                    ),
                    "gap_lower": lower,
                    "gap_upper": upper,
                    "lower_classification": scientific_classification(
                        payload.get("lower_classification", "UNKNOWN")
                    ),
                    "upper_classification": scientific_classification(
                        payload.get("upper_classification", "UNKNOWN")
                    ),
                    "solver_runtime_seconds": sum(float(record.get("runtime_seconds", 0.0)) for record in records),
                    "upper_raw_status": upper_record.get("raw_status"),
                    "upper_certificate_class": upper_record.get("certificate_class", "NO_CERTIFICATE"),
                    "upper_dual_residual": upper_record.get("dual_residual"),
                    "upper_min_psd_eigenvalue": upper_record.get("min_psd_eigenvalue"),
                    "reason": payload.get("reason", ""),
                }
                gaps.append(row)
                for step, item in enumerate(history):
                    record = item.get("record", {})
                    solver_rows.append({
                        **base, "step": step, "trial_gamma": record.get("gamma"), **record,
                        "classification": scientific_classification(record.get("classification")),
                    })
                    report = record.get("dual_data", {}).get("certificate_report", {})
                    certificate_rows.append({
                        **base, **report, "step": step, "trial_gamma": record.get("gamma"),
                        "classification": scientific_classification(record.get("classification")),
                        "checker_classification": report.get("classification"),
                        "certificate_class": record.get("certificate_class"),
                        "dual_residual": record.get("dual_residual"),
                        "message": record.get("message"),
                        "checker_message": report.get("message"),
                    })
            else:
                gaps.append({
                    **base, **reported_level, **cell_resource_details(payload),
                    "classification": "UNKNOWN", "gap_lower": None, "gap_upper": None,
                    "lower_classification": "UNKNOWN", "upper_classification": "UNKNOWN",
                    "reason": "cell not run" if payload is None else payload.get("status"),
                })
        else:
            indexed = {}
            if payload:
                indexed = {(item["observable"], item["sense"]): item["record"] for item in payload.get("results", [])}
            for observable in ("rho0", "F0", "K0"):
                for sense in ("min", "max"):
                    record = indexed.get((observable, sense))
                    if record:
                        row = {**base, **reported_level, "observable": observable, "sense": sense,
                               **cell_resource_details(payload),
                               "optimum": record.get("objective"), "reason": record.get("message", ""),
                               **{key: record.get(key) for key in RECORD_DETAILS}}
                        row["classification"] = scientific_classification(
                            row.get("classification")
                        )
                        solver_rows.append({
                            **base, "observable": observable, "sense": sense, **record,
                            "classification": scientific_classification(record.get("classification")),
                        })
                        report = record.get("dual_data", {}).get("certificate_report", {})
                        certificate_rows.append({
                            **base, **report, "observable": observable, "sense": sense,
                            "trial_gamma": record.get("gamma"),
                            "classification": scientific_classification(record.get("classification")),
                            "checker_classification": report.get("classification"),
                            "certificate_class": record.get("certificate_class"),
                            "dual_residual": record.get("dual_residual"),
                            "message": record.get("message"),
                            "checker_message": report.get("message"),
                        })
                    else:
                        row = {**base, **reported_level, "observable": observable, "sense": sense,
                               **cell_resource_details(payload),
                               "classification": "UNKNOWN", "optimum": None,
                               "reason": "cell/objective not run", "certificate_class": "NO_CERTIFICATE"}
                    observables.append(row)

    common_fields = list(COMMON)
    level_fields = list(LEVEL_COMMON) + list(LEVEL_DETAILS) + ["assembly_status", "reason"]
    gap_fields = common_fields + list(LEVEL_DETAILS) + list(CELL_RESOURCE_DETAILS) + [
        "classification", "gap_lower", "gap_upper", "lower_classification",
        "upper_classification", "solver_runtime_seconds",
        "upper_raw_status", "upper_certificate_class", "upper_dual_residual",
        "upper_min_psd_eigenvalue", "reason",
    ]
    observable_fields = common_fields + list(LEVEL_DETAILS) + list(CELL_RESOURCE_DETAILS) + ["observable", "sense", "optimum"] + \
        list(RECORD_DETAILS) + ["reason"]
    solver_fields = common_fields + ["step", "trial_gamma", "observable", "sense"] + list(RECORD_DETAILS)
    certificate_fields = common_fields + [
        "step", "trial_gamma", "observable", "sense", "classification",
        "checker_classification", "certificate_class",
        "certificate_kind", "projected", "psd_verified", "affine_verified",
        "margin_verified", "objective_gap_verified", "precision_bits",
        "min_eigenvalue_lower", "max_affine_residual", "farkas_margin_lower",
        "certified_objective", "normalized_objective_gap",
        "dual_residual", "message", "checker_message",
    ]
    atomic_csv(args.output / "hierarchy_gap_results.csv", gap_fields, gaps)
    atomic_csv(args.output / "hierarchy_observable_results.csv", observable_fields, observables)
    atomic_csv(args.output / "hierarchy_level_sizes.csv", level_fields, list(levels.values()))
    atomic_csv(args.output / "hierarchy_solver_records.csv", solver_fields, solver_rows)
    atomic_csv(args.output / "hierarchy_certificate_results.csv", certificate_fields, certificate_rows)
    print(
        f"wrote {len(gaps)} gap rows, {len(observables)} observable rows, "
        f"{len(levels)} level rows, {len(solver_rows)} solver records, and "
        f"{len(certificate_rows)} certificate rows",
        flush=True,
    )


if __name__ == "__main__":
    main()
