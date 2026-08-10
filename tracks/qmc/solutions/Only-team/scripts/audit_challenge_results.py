#!/usr/bin/env python3
"""Audit completed transverse-field Ising challenge scan cells."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import tomllib
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import fmean
from typing import Any, Sequence


EXPECTED_BINS = 32
EXPECTED_RANKS = 32
HASH_PATHS = {
    "bins.csv": Path("qmc/bins.csv"),
    "metadata.toml": Path("qmc/metadata.toml"),
    "results.csv": Path("qmc/results.csv"),
    "config.toml": Path("config.toml"),
    "cell_context.json": Path("cell_context.json"),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sem(values: Sequence[float]) -> float:
    count = len(values)
    if count < 2:
        return math.nan
    mean = fmean(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (count * (count - 1)))


def half_chain_z(values: Sequence[float]) -> float:
    """Return the first-half/second-half difference in combined SEM units."""
    midpoint = len(values) // 2
    if midpoint < 2 or len(values) - midpoint < 2:
        return math.nan
    first = values[:midpoint]
    second = values[midpoint:]
    difference = abs(fmean(first) - fmean(second))
    denominator = math.hypot(_sem(first), _sem(second))
    if denominator == 0.0:
        return 0.0 if difference == 0.0 else math.inf
    return difference / denominator


def _close(left: Any, right: Any) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)
    return left == right


@dataclass
class CellRecord:
    run_id: str
    cell_id: str
    cell_dir: Path
    lattice: str
    L: int
    hTrfd: float
    FixedDltau: float
    Dltau: float
    LTrot: int
    nprocs: int
    nWarm: int
    NmBin: int
    NSwep: int
    NmMeaConfg: int
    m2: float
    m2_error: float
    binder_Q: float
    binder_Q_error: float
    scan_kind: str
    bins: list[dict[str, float]]
    bin_count: int
    rank_seed_count: int
    distinct_rank_seed_count: int
    hashes_valid: bool
    z_m2: float
    z_Q: float
    quality_status: str
    quality_reasons: list[str] = field(default_factory=list)
    quality_diagnostics: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.run_id}/{self.cell_id}"

    @property
    def parameter_key(self) -> tuple[str, int, float, float, float]:
        return (self.lattice, self.L, self.hTrfd, self.FixedDltau, self.Dltau)

    def audit_row(self) -> dict[str, Any]:
        row = asdict(self)
        row.pop("cell_dir")
        row.pop("bins")
        row["issues"] = ";".join(self.issues)
        return row


@dataclass(frozen=True)
class QualityDecision:
    accepted: bool
    reasons: list[str]
    diagnostics: list[str]


def evaluate_quality(cell: Any) -> QualityDecision:
    """Apply the declared post-run quality gates to one audited cell."""
    reasons: list[str] = []
    diagnostics: list[str] = []
    if cell.issues:
        reasons.append("integrity_audit")
    if not math.isfinite(cell.z_m2) or cell.z_m2 > 3.0:
        reasons.append("z_m2>3")
    if not math.isfinite(cell.z_Q) or cell.z_Q > 3.0:
        reasons.append("z_Q>3")
    if (
        cell.lattice == "triangular"
        and cell.L >= 40
        and cell.binder_Q_error > 1.0e-4
    ):
        reasons.append("triangular_L>=40_binder_Q_error>1e-4")
    if cell.lattice == "honeycomb" and cell.L in (28, 32):
        diagnostics.append("honeycomb_L28_or_L32_binder_Q_error")
    return QualityDecision(
        accepted=not reasons,
        reasons=reasons,
        diagnostics=diagnostics,
    )


@dataclass
class AuditReport:
    records: list[CellRecord]
    missing_cells: list[str]
    duplicate_parameter_cells: list[list[str]]

    @property
    def total_cells(self) -> int:
        return len(self.records)

    @property
    def unique_parameter_cells(self) -> int:
        return len({record.parameter_key for record in self.records})

    @property
    def failed_cells(self) -> list[str]:
        return [record.label for record in self.records if record.issues]

    @property
    def warning_cells(self) -> list[str]:
        return [
            record.label
            for record in self.records
            if not record.issues and record.quality_status != "pass"
        ]

    def summary(self) -> dict[str, Any]:
        return {
            "total_cells": self.total_cells,
            "unique_parameter_cells": self.unique_parameter_cells,
            "failed_cells": self.failed_cells,
            "missing_cells": self.missing_cells,
            "duplicate_parameter_cells": self.duplicate_parameter_cells,
            "warning_cells": self.warning_cells,
            "quality_status_counts": {
                status: sum(record.quality_status == status for record in self.records)
                for status in sorted({record.quality_status for record in self.records})
            },
        }

    def write_csv(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [record.audit_row() for record in self.records]
        if not rows:
            raise ValueError("cannot write an empty audit")
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "summary": self.summary(),
            "cells": [record.audit_row() for record in self.records],
        }
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )

    def write_quality_outputs(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        columns = [
            "run_id",
            "cell_id",
            "lattice",
            "L",
            "hTrfd",
            "FixedDltau",
            "Dltau",
            "binder_Q_error",
            "z_m2",
            "z_Q",
            "accepted",
            "reasons",
            "diagnostics",
        ]
        with (output_dir / "quality_gates.csv").open(
            "w", newline="", encoding="utf-8"
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            for record in self.records:
                writer.writerow(
                    {
                        "run_id": record.run_id,
                        "cell_id": record.cell_id,
                        "lattice": record.lattice,
                        "L": record.L,
                        "hTrfd": format(record.hTrfd, ".17g"),
                        "FixedDltau": format(record.FixedDltau, ".17g"),
                        "Dltau": format(record.Dltau, ".17g"),
                        "binder_Q_error": format(record.binder_Q_error, ".17g"),
                        "z_m2": format(record.z_m2, ".17g"),
                        "z_Q": format(record.z_Q, ".17g"),
                        "accepted": str(not record.quality_reasons).lower(),
                        "reasons": ";".join(record.quality_reasons),
                        "diagnostics": ";".join(record.quality_diagnostics),
                    }
                )
        candidates = []
        for record in self.records:
            if not record.quality_reasons:
                continue
            target_sweeps = None
            if "triangular_L>=40_binder_Q_error>1e-4" in record.quality_reasons:
                target_sweeps = math.ceil(
                    record.NSwep * (record.binder_Q_error / 1.0e-4) ** 2
                )
            candidates.append(
                {
                    "run_id": record.run_id,
                    "cell_id": record.cell_id,
                    "lattice": record.lattice,
                    "L": record.L,
                    "hTrfd": record.hTrfd,
                    "FixedDltau": record.FixedDltau,
                    "Dltau": record.Dltau,
                    "NSwep": record.NSwep,
                    "binder_Q_error": record.binder_Q_error,
                    "z_m2": record.z_m2,
                    "z_Q": record.z_Q,
                    "reasons": record.quality_reasons,
                    "estimated_NSwep_for_1e-4": target_sweeps,
                }
            )
        payload = {
            "candidate_count": len(candidates),
            "automatic_submission": False,
            "note": (
                "Candidates require a scientific decision before selection; "
                "raw outputs remain unchanged."
            ),
            "candidates": candidates,
        }
        (output_dir / "rerun_candidates.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )


def _read_bins(path: Path, issues: list[str]) -> list[dict[str, float]]:
    bins: list[dict[str, float]] = []
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            bin_number = int(row["bin"])
            parsed = {
                "bin": bin_number,
                "m2_bin": float(row["m2_bin"]),
                "m4_bin": float(row["m4_bin"]),
                "Q_bin": float(row["Q_bin"]),
            }
            if not all(math.isfinite(parsed[key]) for key in ("m2_bin", "m4_bin", "Q_bin")):
                issues.append(f"nonfinite_bin:{bin_number}")
            elif parsed["m4_bin"] <= 0.0 or not math.isclose(
                parsed["Q_bin"],
                parsed["m2_bin"] ** 2 / parsed["m4_bin"],
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                issues.append(f"binder_formula_bin:{bin_number}")
            bins.append(parsed)
    return bins


def load_cell(cell_dir: Path) -> CellRecord:
    """Load and audit one completed cell without modifying it."""
    manifest = json.loads((cell_dir / "manifest.json").read_text(encoding="utf-8"))
    with (cell_dir / "qmc" / "metadata.toml").open("rb") as stream:
        metadata = tomllib.load(stream)
    issues: list[str] = []
    if manifest.get("state") != "success":
        issues.append(f"state:{manifest.get('state')}")

    declared_hashes = manifest.get("hashes", {})
    for name, relative_path in HASH_PATHS.items():
        path = cell_dir / relative_path
        if not path.is_file():
            issues.append(f"missing_file:{name}")
        elif declared_hashes.get(name) != _sha256(path):
            issues.append(f"hash_mismatch:{name}")
    hashes_valid = not any(
        issue.startswith(("hash_mismatch:", "missing_file:")) for issue in issues
    )

    actual = manifest["actual_parameters"]
    metadata_actual = metadata["actual_parameters"]
    if set(actual) != set(metadata_actual) or any(
        not _close(actual[key], metadata_actual.get(key)) for key in actual
    ):
        issues.append("actual_parameters_mismatch")

    settings = manifest["settings"]
    for name, expected in (("J1", -1.0), ("J2", 0.0), ("nLocal", 1), ("nWolff", 5)):
        if not _close(actual.get(name), expected):
            issues.append(f"{name}:{actual.get(name)}")
        if name in settings and not _close(settings.get(name), expected):
            issues.append(f"setting_{name}:{settings.get(name)}")

    params = manifest.get("params", {})
    lattice = str(actual["lattice"])
    size = int(params.get("L", actual["NumL1"]))
    field_value = float(params.get("hTrfd", actual["hTrfd"]))
    requested_dt = float(params.get("FixedDltau", actual["FixedDltau"]))
    actual_dt = float(actual["Dltau"])
    ltrot = int(actual["LTrot"])
    beta = float(actual["BetaT"])
    if not math.isclose(beta, size / field_value, rel_tol=1e-12, abs_tol=1e-12):
        issues.append("BetaT_rule")
    if not math.isclose(actual_dt, beta / ltrot, rel_tol=1e-12, abs_tol=1e-12):
        issues.append("Dltau_rule")
    if int(actual["NumL1"]) != size or int(actual["NumL2"]) != size:
        issues.append("size_mismatch")

    bins = _read_bins(cell_dir / "qmc" / "bins.csv", issues)
    if len(bins) != EXPECTED_BINS:
        issues.append(f"bin_count:{len(bins)}")
    bin_numbers = [int(row["bin"]) for row in bins]
    if bin_numbers != list(range(1, EXPECTED_BINS + 1)):
        issues.append("bin_sequence")

    seeds = [str(seed) for seed in metadata["runtime"].get("rank_seeds", [])]
    rank_seed_count = len(seeds)
    distinct_rank_seed_count = len(set(seeds))
    if rank_seed_count != EXPECTED_RANKS:
        issues.append(f"rank_seed_count:{rank_seed_count}")
    if distinct_rank_seed_count != EXPECTED_RANKS:
        issues.append(f"distinct_rank_seed_count:{distinct_rank_seed_count}")

    m2_bins = [row["m2_bin"] for row in bins]
    q_bins = [row["Q_bin"] for row in bins]
    z_m2 = half_chain_z(m2_bins)
    z_q = half_chain_z(q_bins)
    observables = manifest["observables"]
    binder_error = float(observables["binder_Q_error"])
    quality_input = type(
        "_QualityInput",
        (),
        {
            "issues": issues,
            "z_m2": z_m2,
            "z_Q": z_q,
            "lattice": lattice,
            "L": size,
            "binder_Q_error": binder_error,
        },
    )()
    quality = evaluate_quality(quality_input)
    quality_status = "pass" if quality.accepted else "candidate"

    return CellRecord(
        run_id=str(manifest["run_id"]),
        cell_id=str(manifest["cell_id"]),
        cell_dir=cell_dir,
        lattice=lattice,
        L=size,
        hTrfd=field_value,
        FixedDltau=requested_dt,
        Dltau=actual_dt,
        LTrot=ltrot,
        nprocs=int(manifest["runtime"]["mpi_size"]),
        nWarm=int(metadata["sampling"]["nWarm"]),
        NmBin=int(metadata["sampling"]["NmBin"]),
        NSwep=int(metadata["sampling"]["NSwep"]),
        NmMeaConfg=int(metadata["sampling"]["NmMeaConfg"]),
        m2=float(observables["m2"]),
        m2_error=float(observables["m2_error"]),
        binder_Q=float(observables["binder_Q"]),
        binder_Q_error=binder_error,
        scan_kind=str(params.get("scan_kind", "extreme")),
        bins=bins,
        bin_count=len(bins),
        rank_seed_count=rank_seed_count,
        distinct_rank_seed_count=distinct_rank_seed_count,
        hashes_valid=hashes_valid,
        z_m2=z_m2,
        z_Q=z_q,
        quality_status=quality_status,
        quality_reasons=quality.reasons,
        quality_diagnostics=quality.diagnostics,
        issues=issues,
    )


def audit_runs(run_dirs: Sequence[Path]) -> AuditReport:
    records: list[CellRecord] = []
    expected: set[str] = set()
    for run_dir in run_dirs:
        spec_path = run_dir / "run_spec.json"
        if spec_path.is_file():
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            expected.update(
                f"{run_dir.name}/{cell['cell_id']}" for cell in spec.get("cells", [])
            )
        cells_dir = run_dir / "cells"
        for cell_dir in sorted(cells_dir.glob("cell-*")):
            if (cell_dir / "manifest.json").is_file():
                records.append(load_cell(cell_dir))

    records.sort(key=lambda record: (record.run_id, record.cell_id))
    found = {record.label for record in records}
    grouped: dict[tuple[str, int, float, float, float], list[str]] = defaultdict(list)
    for record in records:
        grouped[record.parameter_key].append(record.label)
    duplicates = sorted(sorted(labels) for labels in grouped.values() if len(labels) > 1)
    return AuditReport(
        records=records,
        missing_cells=sorted(expected - found),
        duplicate_parameter_cells=duplicates,
    )


def write_selection(report: AuditReport, path: Path) -> dict[str, Any]:
    """Freeze the user-ratified all-cell selection for downstream analysis."""
    if report.failed_cells or report.missing_cells or report.duplicate_parameter_cells:
        raise ValueError("cannot select cells from a failed integrity audit")
    cells = []
    sensitivity_exclusions = []
    for record in sorted(report.records, key=lambda item: item.parameter_key):
        cells.append(
            {
                "run_id": record.run_id,
                "cell_id": record.cell_id,
                "lattice": record.lattice,
                "L": record.L,
                "hTrfd": record.hTrfd,
                "FixedDltau": record.FixedDltau,
                "Dltau": record.Dltau,
                "quality_override": bool(record.quality_reasons),
                "quality_reasons": record.quality_reasons,
            }
        )
        if any(reason.startswith("z_") for reason in record.quality_reasons):
            sensitivity_exclusions.append(record.label)
    canonical = json.dumps(cells, sort_keys=True, separators=(",", ":")).encode()
    payload = {
        "schema_version": 1,
        "decision": "keep_all_integrity_valid_cells",
        "decision_status": "user_ratified",
        "selected_cell_count": len(cells),
        "quality_override_count": sum(cell["quality_override"] for cell in cells),
        "sensitivity_exclusions": sensitivity_exclusions,
        "selection_payload_sha256": hashlib.sha256(canonical).hexdigest(),
        "cells": cells,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", action="append", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--write-ratified-selection", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = audit_runs(args.run_dir)
    report.write_csv(args.output_dir / "audit.csv")
    report.write_json(args.output_dir / "audit.json")
    report.write_quality_outputs(args.output_dir)
    if args.write_ratified_selection:
        write_selection(report, args.output_dir / "accepted_cells.json")
    print(json.dumps(report.summary(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
