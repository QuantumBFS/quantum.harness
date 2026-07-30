#!/usr/bin/env python3
"""Fail-closed finalizer for the nine-point CPMC-Lab Figure 4(a-c) run."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable


POINTS = ("smoke",) + tuple(f"u{u}" for u in range(9))
PRODUCTION_POINTS = tuple(f"u{u}" for u in range(9))
ANALYTIC_U0 = -18.578624239043
SOURCE_DIR = Path(__file__).resolve().parent
ED_DATA_PATH = SOURCE_DIR / "ed_digitized_fig4.csv"
ED_PROVENANCE_PATH = SOURCE_DIR / "ed_digitized_fig4.provenance.json"


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise RuntimeError(f"{path}: expected a JSON object")
    return value


def finite(value: object, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"{label}: expected a number") from error
    if not math.isfinite(number):
        raise RuntimeError(f"{label}: non-finite value")
    return number


def read_ed_reference(path: Path = ED_DATA_PATH) -> dict[int, dict[str, object]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        raw = list(csv.DictReader(handle))
    if len(raw) != 9:
        raise RuntimeError(f"{path}: expected exactly nine ED rows")
    result: dict[int, dict[str, object]] = {}
    numeric = (
        "total_energy", "total_uncertainty", "potential_energy",
        "potential_uncertainty", "kinetic_energy", "kinetic_uncertainty",
    )
    for row in raw:
        u_value = finite(row.get("U_over_t"), f"{path}: U_over_t")
        u = int(u_value)
        if u_value != u or u not in range(9) or u in result:
            raise RuntimeError(f"{path}: invalid or duplicate U={u_value}")
        for field in numeric:
            row[field] = finite(row.get(field), f"{path}: U={u} {field}")
        if any(float(row[field]) < 0 for field in numeric if field.endswith("uncertainty")):
            raise RuntimeError(f"{path}: U={u} has a negative uncertainty")
        result[u] = row
    if set(result) != set(range(9)):
        raise RuntimeError(f"{path}: U grid must be 0 through 8")
    return result


def ordinary_stderr(values: list[float]) -> float:
    if len(values) < 2:
        raise RuntimeError("at least two samples are required")
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(max(variance, 0.0) / len(values))


def blocking_stderr(values: list[float], size: int) -> float:
    blocks = [
        sum(values[start : start + size]) / size
        for start in range(0, len(values), size)
        if len(values[start : start + size]) == size
    ]
    return ordinary_stderr(blocks) if len(blocks) >= 2 else ordinary_stderr(values)


def autocorrelation_diagnostics(values: list[float]) -> dict[str, float | str]:
    n = len(values)
    mean = sum(values) / n
    centered = [value - mean for value in values]
    variance0 = sum(value * value for value in centered) / n
    # U=0 is analytically deterministic; roundoff-scale variation must not be
    # normalized into a meaningless order-one autocorrelation coefficient.
    roundoff_floor = (1e-12 * max(1.0, abs(mean))) ** 2
    if variance0 <= roundoff_floor:
        lag1, tau_int, ess = 0.0, 0.5, float(n)
    else:
        correlations = [
            sum(centered[i] * centered[i + lag] for i in range(n - lag))
            / ((n - lag) * variance0)
            for lag in range(1, min(n, n // 2 + 1))
        ]
        lag1 = correlations[0]
        positive_sum = 0.0
        for start in range(0, len(correlations) - 1, 2):
            pair_sum = correlations[start] + correlations[start + 1]
            if pair_sum <= 0.0:
                break
            positive_sum += pair_sum
        tau_int = max(0.5, 0.5 + positive_sum)
        ess = min(float(n), n / (2.0 * tau_int))

    batch_values = {size: blocking_stderr(values, size) for size in (2, 5, 10, 15)}
    iid = ordinary_stderr(values)
    midpoint = n // 2
    first, second = values[:midpoint], values[midpoint:]
    denominator = math.hypot(ordinary_stderr(first), ordinary_stderr(second))
    split_z = 0.0 if denominator == 0.0 else abs(
        sum(first) / len(first) - sum(second) / len(second)
    ) / denominator
    selected = max(iid, *batch_values.values())
    warnings: list[str] = []
    if abs(lag1) > 0.2:
        warnings.append("abs(lag1)>0.2")
    if iid and selected / iid > 1.2:
        warnings.append("blocking_se/iid_se>1.2")
    if split_z > 2.0:
        warnings.append("split_half_z>2")
    return {
        "block_mean": mean,
        "iid_stderr": iid,
        "lag1": lag1,
        "tau_int_ips_half_convention": tau_int,
        "effective_sample_size": ess,
        "batch2_stderr": batch_values[2],
        "batch5_stderr": batch_values[5],
        "batch10_stderr": batch_values[10],
        "batch15_stderr": batch_values[15],
        "selected_block_stderr": selected,
        "split_half_z": split_z,
        "warnings": ";".join(warnings),
    }


def read_summary(run_dir: Path, point: str) -> dict[str, object]:
    point_dir = run_dir / "raw" / point
    marker = read_json(point_dir / "DONE.json")
    if marker.get("status") != "complete":
        raise RuntimeError(f"{point}: completion marker is not complete")
    if marker.get("point") != point:
        raise RuntimeError(f"{point}: marker point mismatch")
    if marker.get("accepted") is not True:
        raise RuntimeError(f"{point}: marker did not pass its point-level gate")
    with (point_dir / "summary.csv").open(encoding="utf-8-sig", newline="") as handle:
        summaries = list(csv.DictReader(handle))
    if len(summaries) != 1:
        raise RuntimeError(f"{point}: expected one summary row")
    row: dict[str, object] = summaries[0]
    for field in ("U_over_t", "seed", "energy", "stderr", "wall_seconds"):
        row[field] = finite(row.get(field), f"{point}: {field}")
    row["accepted"] = str(row.get("accepted", "")).strip().lower() in {"1", "true"}
    if row["accepted"] is not True:
        raise RuntimeError(f"{point}: summary did not pass its point-level gate")
    expected_u = 4 if point == "smoke" else int(point[1:])
    if row["U_over_t"] != expected_u or finite(marker.get("U_over_t"), f"{point}: marker U") != expected_u:
        raise RuntimeError(f"{point}: U value mismatch")
    for field in ("seed", "energy", "stderr", "wall_seconds"):
        if abs(float(row[field]) - finite(marker.get(field), f"{point}: marker {field}")) > 1e-10 * max(1.0, abs(float(row[field]))):
            raise RuntimeError(f"{point}: summary and marker {field} disagree")
    mat_file = str(row.get("mat_file", ""))
    if not mat_file or mat_file != str(marker.get("mat_file", "")) or not (point_dir / mat_file).is_file():
        raise RuntimeError(f"{point}: MAT result is missing or inconsistent")
    with (point_dir / "block_energies.csv").open(encoding="utf-8-sig", newline="") as handle:
        block_rows = list(csv.DictReader(handle))
    expected_blocks = 20 if point == "smoke" else 150
    if len(block_rows) != expected_blocks:
        raise RuntimeError(f"{point}: expected {expected_blocks} blocks, found {len(block_rows)}")
    blocks = [finite(item.get("energy"), f"{point}: block energy") for item in block_rows]
    diagnostics = autocorrelation_diagnostics(blocks)
    if abs(float(diagnostics["block_mean"]) - float(row["energy"])) > 1e-10:
        raise RuntimeError(f"{point}: block mean and summary energy disagree")
    if float(row["stderr"]) < 0.0:
        raise RuntimeError(f"{point}: negative reported standard error")
    if float(diagnostics["lag1"]) >= 0.95 or float(diagnostics["effective_sample_size"]) < 10 or float(diagnostics["split_half_z"]) > 6:
        raise RuntimeError(f"{point}: block-series scientific gate failed")
    row["blocks"] = blocks
    row["diagnostics"] = diagnostics
    row["selected_stderr"] = max(float(row["stderr"]), float(diagnostics["selected_block_stderr"]))
    return row


def derivative_weights(nodes: list[int], target: int) -> list[float]:
    weights: list[float] = []
    for i, xi in enumerate(nodes):
        value = 0.0
        for m, xm in enumerate(nodes):
            if m == i:
                continue
            term = 1.0 / (xi - xm)
            for j, xj in enumerate(nodes):
                if j != i and j != m:
                    term *= (target - xj) / (xi - xj)
            value += term
        weights.append(value)
    return weights


def stencil(target: int, width: int) -> tuple[list[int], list[float]]:
    half = width // 2
    start = min(max(target - half, 0), 9 - width)
    nodes = list(range(start, start + width))
    return nodes, derivative_weights(nodes, target)


def linear_error(rows: dict[str, dict[str, object]], nodes: Iterable[int], coefficients: Iterable[float]) -> float:
    return math.sqrt(sum(
        (coefficient * float(rows[f"u{node}"]["selected_stderr"])) ** 2
        for node, coefficient in zip(nodes, coefficients)
    ))


def derive_observables(rows: dict[str, dict[str, object]], ed: dict[int, dict[str, object]]) -> list[dict[str, object]]:
    derived: list[dict[str, object]] = []
    for u in range(9):
        nodes5, weights5 = stencil(u, 5)
        nodes3, weights3 = stencil(u, 3)
        derivative5 = sum(weight * float(rows[f"u{node}"]["energy"]) for node, weight in zip(nodes5, weights5))
        derivative3 = sum(weight * float(rows[f"u{node}"]["energy"]) for node, weight in zip(nodes3, weights3))
        derivative_stat = linear_error(rows, nodes5, weights5)
        derivative_systematic = abs(derivative5 - derivative3)
        derivative_total = math.hypot(derivative_stat, derivative_systematic)
        energy = float(rows[f"u{u}"]["energy"])
        energy_stderr = float(rows[f"u{u}"]["selected_stderr"])
        potential = u * derivative5
        potential_stat = u * derivative_stat
        potential_systematic = u * derivative_systematic
        potential_stderr = math.hypot(potential_stat, potential_systematic)
        kinetic = energy - potential
        kinetic_coefficients = [(1.0 if node == u else 0.0) - u * weight for node, weight in zip(nodes5, weights5)]
        kinetic_stat = linear_error(rows, nodes5, kinetic_coefficients)
        kinetic_systematic = potential_systematic
        kinetic_stderr = math.hypot(kinetic_stat, kinetic_systematic)
        reference = ed[u]
        derived.append({
            "U_over_t": u,
            "five_point_nodes": " ".join(map(str, nodes5)),
            "five_point_weights": " ".join(f"{weight:.12g}" for weight in weights5),
            "three_point_nodes": " ".join(map(str, nodes3)),
            "three_point_weights": " ".join(f"{weight:.12g}" for weight in weights3),
            "energy": energy,
            "energy_reported_stderr": rows[f"u{u}"]["stderr"],
            "energy_selected_stderr": energy_stderr,
            "double_occupancy_total": derivative5,
            "double_occupancy_statistical_stderr": derivative_stat,
            "double_occupancy_fd_systematic": derivative_systematic,
            "double_occupancy_total_uncertainty": derivative_total,
            "potential_energy": potential,
            "potential_statistical_stderr": potential_stat,
            "potential_fd_systematic": potential_systematic,
            "potential_total_uncertainty": potential_stderr,
            "kinetic_energy": kinetic,
            "kinetic_statistical_stderr": kinetic_stat,
            "kinetic_fd_systematic": kinetic_systematic,
            "kinetic_total_uncertainty": kinetic_stderr,
            "ed_total_digitized": reference["total_energy"],
            "ed_total_digitization_uncertainty": reference["total_uncertainty"],
            "total_minus_ed": energy - float(reference["total_energy"]),
            "ed_potential_digitized": reference["potential_energy"],
            "ed_potential_digitization_uncertainty": reference["potential_uncertainty"],
            "potential_minus_ed": potential - float(reference["potential_energy"]),
            "ed_kinetic_digitized": reference["kinetic_energy"],
            "ed_kinetic_digitization_uncertainty": reference["kinetic_uncertainty"],
            "kinetic_minus_ed": kinetic - float(reference["kinetic_energy"]),
        })
    return derived


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def line_path(points: list[tuple[float, float]], sx, sy) -> str:
    return " ".join(("M" if i == 0 else "L") + f" {sx(x):.2f} {sy(y):.2f}" for i, (x, y) in enumerate(points))


def render_panel(path: Path, *, title: str, ylabel: str, y_min: float, y_max: float,
                 y_ticks: list[float], derived: list[dict[str, object]], value_key: str,
                 error_key: str, ed_key: str, ed_error_key: str, inset: bool = False) -> None:
    width, height, left, right, top, bottom = 900, 560, 95, 35, 50, 75
    plot_w, plot_h = width - left - right, height - top - bottom
    sx = lambda x: left + x / 8 * plot_w
    sy = lambda y: top + (y_max - y) / (y_max - y_min) * plot_h
    ours = [(u, float(row[value_key])) for u, row in enumerate(derived)]
    paper = [(u, float(row[ed_key])) for u, row in enumerate(derived)]
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#172033}.axis{stroke:#172033;stroke-width:1.5}.grid{stroke:#dde2eb}.ed{stroke:#4263eb;fill:#fff;stroke-width:2}.cpmc{stroke:#e03131;fill:#fff;stroke-width:2}</style>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-size="20">{title}</text>',
    ]
    for x in range(9):
        px = sx(x)
        pieces.extend([f'<line class="grid" x1="{px}" y1="{top}" x2="{px}" y2="{top+plot_h}"/>', f'<text x="{px}" y="{top+plot_h+28}" text-anchor="middle" font-size="14">{x}</text>'])
    for y in y_ticks:
        py = sy(y)
        pieces.extend([f'<line class="grid" x1="{left}" y1="{py}" x2="{left+plot_w}" y2="{py}"/>', f'<text x="{left-12}" y="{py+5}" text-anchor="end" font-size="14">{y:g}</text>'])
    pieces.extend([
        f'<line class="axis" x1="{left}" y1="{top+plot_h}" x2="{left+plot_w}" y2="{top+plot_h}"/>',
        f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}"/>',
        f'<text x="{left+plot_w/2}" y="{height-20}" text-anchor="middle" font-size="17">Interaction strength U/t</text>',
        f'<text x="24" y="{top+plot_h/2}" text-anchor="middle" font-size="17" transform="rotate(-90 24 {top+plot_h/2})">{ylabel}</text>',
        f'<path d="{line_path(paper, sx, sy)}" fill="none" stroke="#4263eb" stroke-width="2"/>',
        f'<path d="{line_path(ours, sx, sy)}" fill="none" stroke="#e03131" stroke-width="1.2"/>',
    ])
    for u, row in enumerate(derived):
        for value, error, css, offset in ((float(row[ed_key]), float(row[ed_error_key]), "ed", -4.0), (float(row[value_key]), float(row[error_key]), "cpmc", 4.0)):
            px, py, y1, y2 = sx(u) + offset, sy(value), sy(value + error), sy(value - error)
            pieces.extend([f'<line class="{css}" x1="{px}" y1="{y1}" x2="{px}" y2="{y2}"/>', f'<line class="{css}" x1="{px-5}" y1="{y1}" x2="{px+5}" y2="{y1}"/>', f'<line class="{css}" x1="{px-5}" y1="{y2}" x2="{px+5}" y2="{y2}"/>', f'<circle class="{css}" cx="{px}" cy="{py}" r="4"/>'])
    pieces.extend([
        f'<line class="ed" x1="{left+18}" y1="{top+24}" x2="{left+52}" y2="{top+24}"/><text x="{left+62}" y="{top+29}" font-size="14">Digitized paper ED reference</text>',
        f'<line class="cpmc" x1="{left+360}" y1="{top+24}" x2="{left+394}" y2="{top+24}"/><text x="{left+404}" y="{top+29}" font-size="14">CPMC (statistical + systematic)</text>',
    ])
    if inset:
        ix, iy, iw, ih = left + 430, top + 210, 305, 185
        isx = lambda x: ix + x / 8 * iw
        isy = lambda y: iy + (2.3 - y) / 2.3 * ih
        values = [(u, float(derived[u]["double_occupancy_total"])) for u in range(9)]
        pieces.extend([f'<rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" fill="#fff" stroke="#172033"/>', f'<text x="{ix+iw/2}" y="{iy+18}" text-anchor="middle" font-size="13">Total double occupancy dE/dU</text>', f'<path d="{line_path(values, isx, isy)}" fill="none" stroke="#2f9e44"/>'])
        for u, value in values:
            pieces.append(f'<circle cx="{isx(u)}" cy="{isy(value)}" r="3" fill="#2f9e44"/>')
    pieces.append("</svg>")
    path.write_text("\n".join(pieces), encoding="utf-8")


def comparison_match(row: dict[str, object], value: str, error: str, ed_value: str, ed_error: str) -> bool:
    return abs(float(row[value]) - float(row[ed_value])) <= math.hypot(float(row[error]), float(row[ed_error]))


def format_wall(seconds: float) -> str:
    return f"{seconds / 3600:.2f} h" if seconds >= 3600 else f"{seconds / 60:.1f} min"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(run_dir: Path, files: list[Path]) -> None:
    source_files = (
        Path(__file__).resolve(),
        ED_DATA_PATH,
        ED_PROVENANCE_PATH,
        SOURCE_DIR / "cpmc_lab_source_manifest.sha256",
        SOURCE_DIR / "cpmc_lab_source.provenance.json",
        SOURCE_DIR / "run_cpmc_fig4_point.m",
        SOURCE_DIR / "initialization.m",
        SOURCE_DIR / "monitor_and_finalize.ps1",
    )
    payload = {
        "schema_version": 1,
        "algorithm": "sha256",
        "files": {path.relative_to(run_dir).as_posix(): sha256(path) for path in sorted(set(files))},
        "source_files": {
            str(path.relative_to(SOURCE_DIR)): sha256(path)
            for path in source_files
        },
    }
    target = run_dir / "artifact_manifest.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(target)


def update_run_json(run_dir: Path, rows: dict[str, dict[str, object]], derived: list[dict[str, object]], matches: dict[str, bool]) -> Path:
    path = run_dir / "run.json"
    data = read_json(path)
    data["scope"]["label"] = "nine-point reproduction of Figure 4(a-c) with digitized ED comparison"
    data["model"]["couplings"]["$U/t$"] = "0, 1, 2, 3, 4, 5, 6, 7, 8"
    data["method"]["tool"] = "CPMC-Lab archive labeled 2.0 (source banner identifies version 1.0), MATLAB R2025a"
    data["method"]["settings"]["Hellmann-Feynman stencil"] = "five-point h=1; three-point difference reported as systematic uncertainty"
    data["method"]["note"] = (
        "The official package projects a free-electron trial determinant with the constrained-path approximation. "
        "Total energy is a mixed estimator and is not variational. Panels (b,c) use E_V=U dE/dU and E_K=E-E_V. "
        "Cross-U errors are propagated independently; sharing a seed does not establish paired covariance."
    )
    data["actual"] = [{"point": "2-site Table I smoke", "wall": format_wall(float(rows["smoke"]["wall_seconds"])), "memory": "not measured"}] + [
        {"point": f"$U/t={u}$", "wall": format_wall(float(rows[f"u{u}"]["wall_seconds"])), "memory": "not measured"} for u in range(9)
    ]
    data["risks"] = [risk for risk in data.get("risks", []) if "paired-block" not in risk and "same seed" not in risk.lower()]
    new_risks = [
        "All U runs share a seed, but different Hamiltonians do not create a documented paired sample; cross-U covariance is therefore not assumed.",
        "Finite-difference systematic uncertainty is estimated by the absolute difference between local five-point and three-point derivatives.",
        "Block autocorrelation, blocking standard errors, effective sample size, and split-half drift are recorded in mc_diagnostics.csv.",
        "ED curves are digitized paper references, not fresh local ED; values and extraction provenance are committed alongside the finalizer.",
        "Only one production seed and one time-step/walker setting have been completed, so seed and algorithmic sensitivity remain open systematic checks.",
    ]
    for risk in new_risks:
        if risk not in data["risks"]:
            data["risks"].append(risk)
    data["figures"] = [figure for figure in data.get("figures", []) if not str(figure.get("id", "")).startswith("Figure 4(")]
    specs = (
        ("a", "total energy", "energy", "energy_selected_stderr", "ed_total_digitized", "ed_total_digitization_uncertainty", "figs/fig4a_total_energy.svg"),
        ("b", "potential energy", "potential_energy", "potential_total_uncertainty", "ed_potential_digitized", "ed_potential_digitization_uncertainty", "figs/fig4b_potential_double_occupancy.svg"),
        ("c", "kinetic energy", "kinetic_energy", "kinetic_total_uncertainty", "ed_kinetic_digitized", "ed_kinetic_digitization_uncertainty", "figs/fig4c_kinetic.svg"),
    )
    for panel, label, value, error, ed_value, ed_error, figure_path in specs:
        numbers = {f"$U/t={u}$": f"CPMC {float(row[value]):.6f} ± {float(row[error]):.6f}; digitized ED {float(row[ed_value]):.5f} ± {float(row[ed_error]):.5f}; Δ={float(row[value])-float(row[ed_value]):+.5f}" for u, row in enumerate(derived)}
        data["figures"].append({
            "id": f"Figure 4({panel}), full integer grid",
            "paper_image": "figs/paper_fig4.png",
            "plots": f"{label} versus interaction strength",
            "x": "$U/t$", "x_range": "0 through 8 in unit steps", "y": label,
            "observe": {"quantity": label, "normalization": "total energy in units of t", "states": "5 spin-up and 7 spin-down electrons on a 16-site ring"},
            "expected": "Agreement with the digitized finite-ring ED reference within the stated combined uncertainty.",
            "results": {
                "figure": figure_path, "numbers": numbers, "match": "yes" if matches[panel] else "no",
                "why": "All nine points overlap the digitized ED reference within quadrature-combined uncertainties." if matches[panel] else "At least one point fails the combined-uncertainty comparison.",
                "wall": "Uses the same nine production energy runs.",
                "changes": ["Figure 4(a) now uses all nine integer-grid points.", "Panels (b,c) include statistical and three-vs-five-point finite-difference systematic uncertainty.", "ED readback data and provenance are stored as machine-readable source files."],
                "rerun": "python cpmc_lab_fig4/finalize_cpmc_fig4abc.py <run-dir>",
            },
        })
    data["reproducibility"] = {
        "ed_reference": "cpmc_lab_fig4/ed_digitized_fig4.csv",
        "ed_provenance": "cpmc_lab_fig4/ed_digitized_fig4.provenance.json",
        "mc_diagnostics": "mc_diagnostics.csv",
        "checksums": "artifact_manifest.json",
        "finalizer_gate": "all markers and artifacts valid; all three panels match; otherwise nonzero exit and no FINALIZED.txt",
    }
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)
    run_dir = args.run_dir.resolve()
    finalized = run_dir / "FINALIZED.txt"
    if not args.check_only and finalized.exists():
        finalized.unlink()
    ed = read_ed_reference()
    read_json(ED_PROVENANCE_PATH)
    rows = {point: read_summary(run_dir, point) for point in POINTS}
    seeds = {int(float(rows[point]["seed"])) for point in PRODUCTION_POINTS}
    if len(seeds) != 1:
        raise RuntimeError(f"production seed mismatch: {sorted(seeds)}")
    if abs(float(rows["u0"]["energy"]) - ANALYTIC_U0) > 1e-9:
        raise RuntimeError("U=0 analytic quality gate failed")
    diagnostics = [{"point": point, "U_over_t": rows[point]["U_over_t"], "reported_stderr": rows[point]["stderr"], "selected_stderr": rows[point]["selected_stderr"], **dict(rows[point]["diagnostics"])} for point in POINTS]
    derived = derive_observables(rows, ed)
    match_specs = {
        "a": ("energy", "energy_selected_stderr", "ed_total_digitized", "ed_total_digitization_uncertainty"),
        "b": ("potential_energy", "potential_total_uncertainty", "ed_potential_digitized", "ed_potential_digitization_uncertainty"),
        "c": ("kinetic_energy", "kinetic_total_uncertainty", "ed_kinetic_digitized", "ed_kinetic_digitization_uncertainty"),
    }
    matches = {panel: all(comparison_match(row, *spec) for row in derived) for panel, spec in match_specs.items()}
    if not all(matches.values()):
        failed = ", ".join(panel for panel, matched in matches.items() if not matched)
        raise RuntimeError(f"scientific comparison gate failed for panel(s): {failed}")
    if args.check_only:
        print("CPMC_FINALIZER_GATE=PASS")
        return 0
    write_csv(run_dir / "mc_diagnostics.csv", diagnostics)
    write_csv(run_dir / "derived_observables.csv", derived)
    figures = run_dir / "figs"
    figures.mkdir(parents=True, exist_ok=True)
    figure_a = figures / "fig4a_total_energy.svg"
    figure_b = figures / "fig4b_potential_double_occupancy.svg"
    figure_c = figures / "fig4c_kinetic.svg"
    render_panel(figure_a, title="CPMC-Lab Figure 4(a): total energy", ylabel="Total energy E/t", y_min=-19, y_max=-10, y_ticks=list(range(-19, -9)), derived=derived, value_key="energy", error_key="energy_selected_stderr", ed_key="ed_total_digitized", ed_error_key="ed_total_digitization_uncertainty")
    render_panel(figure_b, title="CPMC-Lab Figure 4(b): potential energy", ylabel="Potential energy E_V/t", y_min=0, y_max=3.7, y_ticks=[0, 1, 2, 3], derived=derived, value_key="potential_energy", error_key="potential_total_uncertainty", ed_key="ed_potential_digitized", ed_error_key="ed_potential_digitization_uncertainty", inset=True)
    render_panel(figure_c, title="CPMC-Lab Figure 4(c): kinetic energy", ylabel="Kinetic energy E_K/t", y_min=-19, y_max=-13, y_ticks=list(range(-19, -12)), derived=derived, value_key="kinetic_energy", error_key="kinetic_total_uncertainty", ed_key="ed_kinetic_digitized", ed_error_key="ed_kinetic_digitization_uncertainty")
    run_json = update_run_json(run_dir, rows, derived, matches)
    manifest_files = [run_json, run_dir / "derived_observables.csv", run_dir / "mc_diagnostics.csv", figure_a, figure_b, figure_c]
    for point in POINTS:
        point_dir = run_dir / "raw" / point
        manifest_files.extend([point_dir / "DONE.json", point_dir / "summary.csv", point_dir / "block_energies.csv", point_dir / str(rows[point]["mat_file"])])
    write_manifest(run_dir, manifest_files)
    print("CPMC_FINALIZER_GATE=PASS")
    print("FIG4A_MATCH=yes")
    print("FIG4B_MATCH=yes")
    print("FIG4C_MATCH=yes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
