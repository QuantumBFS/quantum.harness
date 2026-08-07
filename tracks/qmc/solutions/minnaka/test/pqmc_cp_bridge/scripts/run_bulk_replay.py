#!/usr/bin/env python3
"""Validate archive provenance and stream selected paths through C++ replay."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
from typing import Iterable

import numpy as np

from path_archive import ArchiveReader


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_orbitals(path: Path) -> np.ndarray:
    with path.open() as handle:
        rows, cols = (int(value) for value in handle.readline().split())
        values = np.loadtxt(handle, dtype=float)
    return np.asarray(values, dtype=float).reshape(rows, cols)


def _site_map(path: Path, sites: int) -> np.ndarray:
    rows = np.loadtxt(path, dtype=int)
    if rows.shape != (sites, 4):
        raise ValueError("site map has unexpected shape")
    order = np.full(sites, -1, dtype=int)
    for alf_one, cpp, x, y in rows:
        if not 1 <= alf_one <= sites or cpp != y * int(math.sqrt(sites)) + x:
            raise ValueError("site map row violates row-major contract")
        order[alf_one - 1] = cpp
    if sorted(order.tolist()) != list(range(sites)):
        raise ValueError("site map is not a bijection")
    return order


def initial_mixed_energy(trial_dir: Path, interaction: float = 4.0) -> float:
    """Return ⟨T|H|I⟩/⟨T|I⟩ in the raw Hubbard convention."""
    i_up_alf = _read_orbitals(trial_dir / "trial_I_up.dat")
    i_dn_alf = _read_orbitals(trial_dir / "trial_I_down.dat")
    t_up_alf = _read_orbitals(trial_dir / "trial_T_up.dat")
    t_dn_alf = _read_orbitals(trial_dir / "trial_T_down.dat")
    sites = i_up_alf.shape[0]
    order = _site_map(trial_dir / "site_map.dat", sites)

    def mapped(value: np.ndarray) -> np.ndarray:
        result = np.empty_like(value)
        result[order, :] = value
        return result

    i_up, i_dn = mapped(i_up_alf), mapped(i_dn_alf)
    t_up, t_dn = mapped(t_up_alf), mapped(t_dn_alf)
    side = int(round(math.sqrt(sites)))
    if side * side != sites:
        raise ValueError("mixed-energy helper requires a square lattice")
    kinetic = np.zeros((sites, sites))
    for y in range(side):
        for x in range(side):
            source = y * side + x
            for nx, ny in (
                ((x + 1) % side, y),
                ((x - 1) % side, y),
                (x, (y + 1) % side),
                (x, (y - 1) % side),
            ):
                target = ny * side + nx
                kinetic[source, target] -= 1.0

    def density(left: np.ndarray, right: np.ndarray) -> np.ndarray:
        return right @ np.linalg.solve(left.T @ right, left.T)

    g_up = density(t_up, i_up)
    g_dn = density(t_dn, i_dn)
    return float(
        np.trace(kinetic @ g_up)
        + np.trace(kinetic @ g_dn)
        + interaction * np.dot(np.diag(g_up), np.diag(g_dn))
    )


def validate_inputs(
    archive_index: Path,
    sample_manifest: Path,
    selected_projection: Path,
    trial_manifest: Path,
) -> tuple[dict, list[dict]]:
    selected = json.loads(selected_projection.read_text())
    trial = json.loads(trial_manifest.read_text())
    index = json.loads(archive_index.read_text())
    entries = index.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("archive index must have nonempty entries")
    selected_hash = sha256(selected_projection)
    trial_hash = sha256(trial_manifest)
    seen_groups: set[tuple[str, int]] = set()
    available: set[int] = set()
    for entry in entries:
        group = (str(entry["ensemble"]), int(entry["chain"]))
        if group in seen_groups:
            raise ValueError(f"duplicate archive group {group}")
        seen_groups.add(group)
        path = Path(entry["path"])
        if not path.is_absolute():
            path = (archive_index.parent / path).resolve()
        reader = ArchiveReader(path)
        header = reader.header
        expected_code = 1 if group[0] == "II" else 2 if group[0] == "TI" else 0
        if (
            expected_code == 0
            or header.ensemble_code != expected_code
            or header.selected_projection_sha256 != selected_hash
            or header.trial_manifest_sha256 != trial_hash
            or header.ltrot != int(selected["ltrot_star"])
        ):
            raise ValueError(f"archive header/contract mismatch: {path}")
        if "header_sha256" in entry:
            with path.open("rb") as handle:
                actual_header_hash = hashlib.sha256(handle.read(256)).hexdigest()
            if actual_header_hash != entry["header_sha256"]:
                raise ValueError(f"archive header hash mismatch: {path}")
        scan = reader.scan()
        if scan.truncated_tail:
            raise ValueError(f"truncated archive: {path}")
        if int(entry.get("records", scan.complete_records)) != scan.complete_records:
            raise ValueError(f"archive record count mismatch: {path}")
        for record in reader.records():
            available.add(record.sample_id)
    requested: set[int] = set()
    with sample_manifest.open(newline="") as handle:
        rows = csv.DictReader(handle)
        if rows.fieldnames != ["sample_id", "ensemble", "chain"]:
            raise ValueError("unexpected sample manifest columns")
        for row in rows:
            sample_id = int(row["sample_id"])
            if sample_id in requested:
                raise ValueError("duplicate requested sample")
            requested.add(sample_id)
    if not requested or not requested <= available:
        raise ValueError("sample manifest contains unavailable IDs")
    if trial.get("trial_right") != "ALF stock free, Delta=0.01":
        raise ValueError("trial manifest does not freeze I=ALF free")
    return selected, entries


def replay_command(
    executable: Path,
    archive_index: Path,
    sample_manifest: Path,
    selected_projection: Path,
    trial_manifest: Path,
    field_order: Path,
    summary_output: Path,
    prefix_output: Path | None,
    reference_energy: float,
    stabilize_every: int,
    summary_only: bool = False,
) -> list[str]:
    if summary_only and prefix_output is not None:
        raise ValueError("summary-only replay cannot write a prefix output")
    if not summary_only and prefix_output is None:
        raise ValueError("prefix output is required unless summary-only")
    command = [
        str(executable),
        "replay-archive",
        "--archive-index", str(archive_index),
        "--sample-manifest", str(sample_manifest),
        "--selected-projection", str(selected_projection),
        "--trial-manifest", str(trial_manifest),
        "--field-order", str(field_order),
        "--summary-output", str(summary_output),
        "--eref-mode", "constant",
        "--eref-value", f"{reference_energy:.17g}",
        "--stabilize-every", str(stabilize_every),
    ]
    if summary_only:
        command.append("--summary-only")
    else:
        command[command.index("--eref-mode"):command.index("--eref-mode")] = [
            "--prefix-output", str(prefix_output),
        ]
    return command


def compare_summaries(paths: Iterable[Path], tolerance: float = 1.0e-9) -> dict:
    tables: list[dict[int, dict[str, str]]] = []
    for path in paths:
        with path.open(newline="") as handle:
            rows = {
                int(row["sample_id"]): row for row in csv.DictReader(handle)
            }
        tables.append(rows)
    if not tables or any(table.keys() != tables[0].keys() for table in tables[1:]):
        raise ValueError("stability summaries have different sample IDs")
    numerical = (
        "logabs_d_ii", "logabs_d_ti",
        "logabs_d_alf_ii", "logabs_d_alf_ti",
        "boundary_cut_log_ratio_ii", "boundary_cut_log_ratio_ti",
        "central_ii_etot",
        "central_ti_etot",
    )
    diagnostic = ("endpoint_i_etot", "endpoint_t_etot")
    categorical = (
        "alive", "first_rejection_kind", "first_rejection_slice",
        "first_rejection_site",
    )
    maximum = 0.0
    maximum_endpoint = 0.0
    ambiguous: list[int] = []
    hard: list[int] = []
    identity_differences: list[float] = []
    for sample_id in sorted(tables[0]):
        reference = tables[0][sample_id]
        bad = False
        hard_bad = False
        for table in tables[1:]:
            row = table[sample_id]
            if any(row[key] != reference[key] for key in categorical):
                bad = True
                hard_bad = True
            for key in numerical:
                left, right = float(reference[key]), float(row[key])
                if math.isnan(left) and math.isnan(right):
                    continue
                difference = abs(left - right)
                maximum = max(maximum, difference)
                if not math.isfinite(difference) or difference > tolerance:
                    bad = True
                    hard_bad = True
            for key in diagnostic:
                left, right = float(reference[key]), float(row[key])
                if math.isnan(left) and math.isnan(right):
                    continue
                difference = abs(left - right)
                maximum_endpoint = max(maximum_endpoint, difference)
            left = float(reference["identity_log_residual"])
            right = float(row["identity_log_residual"])
            if math.isnan(left) and math.isnan(right):
                difference = 0.0
            else:
                difference = abs(left - right)
            identity_differences.append(difference)
            if not math.isfinite(difference) or difference > tolerance:
                bad = True
        if bad:
            ambiguous.append(sample_id)
        if hard_bad:
            hard.append(sample_id)
    ordered_identity = sorted(identity_differences)
    position = 0.99 * (len(ordered_identity) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    fraction = position - lower
    identity_p99 = (
        ordered_identity[lower] * (1.0 - fraction)
        + ordered_identity[upper] * fraction
    )
    numerical_pass = (
        identity_p99 <= tolerance
        and len(ambiguous) / len(tables[0]) <= 0.05
    )
    return {
        "schema_version": 1,
        "tolerance": tolerance,
        "max_abs_difference": maximum,
        "max_endpoint_energy_difference": maximum_endpoint,
        "identity_p99_difference": identity_p99,
        "hard_mismatch_ids": hard,
        "numerically_ambiguous": ambiguous,
        "passed": not hard and numerical_pass,
    }


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    bridge = root / "test/pqmc_cp_bridge"
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-index", type=Path, required=True)
    parser.add_argument("--sample-manifest", type=Path, required=True)
    parser.add_argument(
        "--selected-projection", type=Path,
        default=bridge / "results/selected_projection.json",
    )
    parser.add_argument(
        "--trial-manifest", type=Path,
        default=bridge / "assets/trials/trial_manifest.json",
    )
    parser.add_argument(
        "--field-order", type=Path,
        default=bridge / "contracts/field_order.json",
    )
    parser.add_argument(
        "--executable", type=Path,
        default=root / "test/cpmc_path_audit/build/cpmc_audit",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=bridge / "replay/bulk",
    )
    parser.add_argument(
        "--stabilize-every", type=int, nargs="+", default=[5],
    )
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    if any(value <= 0 for value in args.stabilize_every):
        parser.error("stabilization intervals must be positive")
    selected, _ = validate_inputs(
        args.archive_index, args.sample_manifest,
        args.selected_projection, args.trial_manifest,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reference_energy = initial_mixed_energy(args.trial_manifest.parent)
    summaries: list[Path] = []
    for interval in args.stabilize_every:
        summary = args.output_dir / f"replay_summary_s{interval}.csv"
        prefix = (
            None if args.summary_only
            else args.output_dir / f"replay_prefix_s{interval}.qhpfx"
        )
        command = replay_command(
            args.executable, args.archive_index, args.sample_manifest,
            args.selected_projection, args.trial_manifest,
            args.field_order, summary, prefix, reference_energy, interval,
            summary_only=args.summary_only,
        )
        print(
            f"replay stabilize={interval}, theta={selected['theta_star']}",
            flush=True,
        )
        subprocess.run(command, check=True)
        summaries.append(summary)
        if not args.summary_only and interval != args.stabilize_every[0]:
            assert prefix is not None
            prefix.unlink()
    if len(summaries) > 1:
        validation = compare_summaries(summaries)
        (args.output_dir / "stability_validation.json").write_text(
            json.dumps(validation, indent=2, sort_keys=True) + "\n"
        )
        if not validation["passed"]:
            raise RuntimeError("stabilization consistency check failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
