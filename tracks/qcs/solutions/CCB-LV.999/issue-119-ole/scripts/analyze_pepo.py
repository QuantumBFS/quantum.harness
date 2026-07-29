#!/usr/bin/env python3
"""Collect, assess, and plot PEPO Dop/chi_env convergence records."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


OLE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = OLE_ROOT.parents[4]
if str(WORKSPACE_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

import parameter_scan as parameter_scan  # noqa: E402


DEFAULT_BP_MEAN = 0.8183229131612796
DEFAULT_BP_BUDGET = 0.0044
DEFAULT_TARGET = 0.001
DUPLICATE_TOLERANCE = 1.0e-12
APPROVED_QASM_SHA256 = "1705197e7b1ebb02266600b3ddaba0d2c47a96de84c5895e2bb530728b815455"
APPROVED_QUIMB_COMMIT = "3c89529fe0a3487133a3928201691161e110abdf"
APPROVED_OBSERVABLE_SITES = [52, 59, 72]
APPROVED_EVOLUTION_CUTOFF = 1.0e-12
APPROVED_CONTRACTION_CUTOFF = 1.0e-12
APPROVED_DELTAS = (0.0, 0.15)


def _finite_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number")
    return number


def _positive_integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _cut(records: list[dict[str, Any]], axis: str, fixed_axis: str, fixed_value: int) -> list[dict[str, Any]]:
    return sorted(
        (record for record in records if record[fixed_axis] == fixed_value),
        key=lambda record: record[axis],
    )


def _trend(cut: list[dict[str, Any]], axis: str) -> dict[str, Any]:
    if len(cut) < 3:
        raise ValueError(f"{axis} cut needs at least three completed levels")
    values = [record["value"] for record in cut]
    signed_differences = [values[index + 1] - values[index] for index in range(len(values) - 1)]
    newest = abs(signed_differences[-1])
    preceding = abs(signed_differences[-2])
    return {
        "levels": [record[axis] for record in cut],
        "signed_differences": signed_differences,
        "newest_difference": newest,
        "preceding_difference": preceding,
        "growing": newest > preceding + 1.0e-12,
    }


def assess_convergence(
    records: list[dict[str, Any]],
    bp_mean: float,
    bp_budget: float,
    target: float,
) -> dict[str, Any]:
    """Assess the approved empirical PEPO envelope at the largest corner."""
    if not records:
        raise ValueError("no successful PEPO records are available")
    bp_mean = _finite_number(bp_mean, "bp_mean")
    bp_budget = _finite_number(bp_budget, "bp_budget")
    target = _finite_number(target, "target")
    if bp_budget < 0.0 or target < 0.0:
        raise ValueError("bp_budget and target must be nonnegative")

    normalized: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for raw in records:
        dop = _positive_integer(raw.get("dop"), "dop")
        chi_env = _positive_integer(raw.get("chi_env"), "chi_env")
        coordinate = (dop, chi_env)
        if coordinate in seen:
            raise ValueError(f"duplicate successful PEPO cell at Dop={dop}, chi_env={chi_env}")
        seen.add(coordinate)
        normalized.append({"dop": dop, "chi_env": chi_env, "value": _finite_number(raw.get("value"), "value")})

    dop_levels = sorted({record["dop"] for record in normalized})
    chi_levels = sorted({record["chi_env"] for record in normalized})
    if len(dop_levels) < 3 or len(chi_levels) < 3:
        raise ValueError("at least three distinct levels are required on both axes")
    max_dop, max_chi_env = dop_levels[-1], chi_levels[-1]
    by_coordinate = {(record["dop"], record["chi_env"]): record for record in normalized}
    try:
        corner = by_coordinate[(max_dop, max_chi_env)]
    except KeyError as error:
        raise ValueError(
            f"maximum completed corner Dop={max_dop}, chi_env={max_chi_env} is missing"
        ) from error

    dop_cut = _cut(normalized, "dop", "chi_env", max_chi_env)
    complete_chi_cuts = [
        (dop, cut)
        for dop in dop_levels
        if len(cut := _cut(normalized, "chi_env", "dop", dop)) >= 3
        and cut[-1]["chi_env"] == max_chi_env
    ]
    if not complete_chi_cuts:
        raise ValueError("no Dop level has three completed chi_env levels ending at chi_env max")
    chi_reference_dop, chi_cut = complete_chi_cuts[-1]
    chi_env_at_corner = chi_reference_dop == max_dop
    dop_trend = _trend(dop_cut, "dop")
    chi_trend = _trend(chi_cut, "chi_env")
    previous_dop = dop_cut[-2]
    previous_chi_env = chi_cut[-2]
    delta_dop = abs(corner["value"] - previous_dop["value"])
    delta_chi_env = abs(chi_cut[-1]["value"] - previous_chi_env["value"])
    epsilon_pepo = delta_dop + delta_chi_env
    trend_resolved = not dop_trend["growing"] and not chi_trend["growing"]
    internally_converged = epsilon_pepo <= target and trend_resolved and chi_env_at_corner
    bp_difference = abs(corner["value"] - bp_mean)
    agreement_limit = epsilon_pepo + bp_budget
    within_budget = bp_difference <= agreement_limit
    agrees_with_bp = internally_converged and within_budget
    comparison_status = (
        "agreement" if agrees_with_bp else "diagnostic" if not internally_converged else "disagreement"
    )

    return {
        "corner": corner,
        "dop_cut": dop_cut,
        "chi_env_cut": chi_cut,
        "chi_env_reference_dop": chi_reference_dop,
        "chi_env_at_corner": chi_env_at_corner,
        "delta_dop": delta_dop,
        "delta_chi_env": delta_chi_env,
        "epsilon_pepo": epsilon_pepo,
        "target": target,
        "trend": {"dop": dop_trend, "chi_env": chi_trend, "resolved": trend_resolved},
        "internally_converged": internally_converged,
        "bp_mean": bp_mean,
        "bp_budget": bp_budget,
        "bp_difference": bp_difference,
        "agreement_limit": agreement_limit,
        "within_bp_budget": within_budget,
        "agrees_with_bp": agrees_with_bp,
        "comparison_status": comparison_status,
    }


def _require_mapping(document: dict[str, Any], key: str, cell_id: str) -> dict[str, Any]:
    value = document.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{cell_id}: {key} is missing")
    return value


def _require_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label}: expected {expected!r}, got {actual!r}")


def _approved_contract(
    *,
    label: str,
    provenance: dict[str, Any],
    settings: dict[str, Any],
    delta: object,
) -> None:
    _require_equal(provenance.get("qasm_sha256"), APPROVED_QASM_SHA256, f"{label}: approved qasm_sha256")
    _require_equal(provenance.get("quimb_commit"), APPROVED_QUIMB_COMMIT, f"{label}: approved quimb_commit")
    _require_equal(settings.get("observable_sites"), APPROVED_OBSERVABLE_SITES, f"{label}: approved observable_sites")
    _require_equal(_finite_number(settings.get("evolution_cutoff"), f"{label}: evolution_cutoff"), APPROVED_EVOLUTION_CUTOFF, f"{label}: approved evolution_cutoff")
    _require_equal(_finite_number(settings.get("contraction_cutoff"), f"{label}: contraction_cutoff"), APPROVED_CONTRACTION_CUTOFF, f"{label}: approved contraction_cutoff")
    numeric_delta = _finite_number(delta, f"{label}: delta")
    if numeric_delta not in APPROVED_DELTAS:
        raise ValueError(f"{label}: approved delta must be one of {APPROVED_DELTAS!r}, got {numeric_delta!r}")


def _planned_cell_contract(run_spec: dict[str, Any], cell: dict[str, Any]) -> dict[str, Any]:
    cell_id = str(cell.get("cell_id"))
    params = _require_mapping(cell, "params", cell_id)
    shared_settings = _require_mapping(run_spec, "settings", "run_spec")
    cell_settings = cell.get("settings", {})
    if not isinstance(cell_settings, dict):
        raise ValueError(f"{cell_id}: planned settings must be a JSON object")
    settings = {**shared_settings, **cell_settings}
    provenance = _require_mapping(run_spec, "provenance", "run_spec")
    delta = params.get("delta", settings.get("delta"))
    _approved_contract(
        label=f"planned {cell_id}",
        provenance=provenance,
        settings=settings,
        delta=delta,
    )
    return {
        "params": dict(params),
        "dop": _positive_integer(params.get("dop"), f"{cell_id}: planned params.dop"),
        "chi_env": _positive_integer(params.get("chi_env"), f"{cell_id}: planned params.chi_env"),
        "delta": _finite_number(delta, f"{cell_id}: planned delta"),
        "settings": settings,
        "provenance": provenance,
    }


def _successful_record(
    manifest: dict[str, Any],
    cell_id: str,
    run_dir: Path,
    expected: dict[str, Any],
) -> dict[str, Any]:
    params = _require_mapping(manifest, "params", cell_id)
    settings = _require_mapping(manifest, "settings", cell_id)
    provenance = _require_mapping(manifest, "provenance", cell_id)
    result = _require_mapping(manifest, "result", cell_id)
    observable_sites = settings.get("observable_sites")
    if not isinstance(observable_sites, list) or not observable_sites:
        raise ValueError(f"{cell_id}: observable_sites is missing")
    declared_delta = params.get("delta", settings.get("delta"))
    _approved_contract(
        label=f"{cell_id} manifest",
        provenance=provenance,
        settings=settings,
        delta=declared_delta,
    )
    _require_equal(params.get("dop"), expected["dop"], f"{cell_id}: manifest params.dop must match run_spec")
    _require_equal(params.get("chi_env"), expected["chi_env"], f"{cell_id}: manifest params.chi_env must match run_spec")
    _require_equal(_finite_number(declared_delta, f"{cell_id}: manifest delta"), expected["delta"], f"{cell_id}: manifest delta must match run_spec")
    for field in ("observable_sites", "evolution_cutoff", "contraction_cutoff"):
        actual = settings.get(field)
        expected_value = expected["settings"].get(field)
        if field.endswith("cutoff"):
            actual = _finite_number(actual, f"{cell_id}: manifest {field}")
            expected_value = _finite_number(expected_value, f"{cell_id}: planned {field}")
        _require_equal(actual, expected_value, f"{cell_id}: manifest {field} must match run_spec")
    for field in ("qasm_sha256", "quimb_commit"):
        _require_equal(
            provenance.get(field),
            expected["provenance"].get(field),
            f"{cell_id}: manifest {field} must match run_spec",
        )
    return {
        "dop": _positive_integer(params.get("dop"), f"{cell_id}: params.dop"),
        "chi_env": _positive_integer(params.get("chi_env"), f"{cell_id}: params.chi_env"),
        "value": _finite_number(result.get("value_real"), f"{cell_id}: result.value_real"),
        "delta": _finite_number(
            declared_delta,
            f"{cell_id}: declared delta",
        ),
        "observable_sites": observable_sites,
        "evolution_cutoff": _finite_number(settings.get("evolution_cutoff"), f"{cell_id}: settings.evolution_cutoff"),
        "contraction_cutoff": _finite_number(settings.get("contraction_cutoff"), f"{cell_id}: settings.contraction_cutoff"),
        "qasm_sha256": provenance.get("qasm_sha256"),
        "quimb_commit": provenance.get("quimb_commit"),
        "cell_id": cell_id,
        "run_dir": str(run_dir),
    }


def _validate_consensus(records: list[dict[str, Any]]) -> None:
    fields = ("qasm_sha256", "quimb_commit", "observable_sites", "evolution_cutoff", "contraction_cutoff", "delta")
    for field in fields:
        values = {json.dumps(record[field], sort_keys=True) for record in records}
        if "null" in values or len(values) != 1:
            label = field.replace("_", " ")
            raise ValueError(f"inconsistent {label} across successful PEPO manifests")


def _reconcile_duplicate_records(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for record in records:
        coordinate = (record["dop"], record["chi_env"])
        grouped.setdefault(coordinate, []).append(record)

    unique: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    for (dop, chi_env), group in grouped.items():
        unique.append(group[0])
        if len(group) == 1:
            continue
        values = [record["value"] for record in group]
        difference = max(values) - min(values)
        if difference > DUPLICATE_TOLERANCE:
            raise ValueError(
                "duplicate successful PEPO cells disagree at "
                f"Dop={dop}, chi_env={chi_env}: "
                f"max absolute difference {difference:.6g} exceeds "
                f"{DUPLICATE_TOLERANCE:.6g}"
            )
        checks.append(
            {
                "dop": dop,
                "chi_env": chi_env,
                "values": values,
                "max_absolute_difference": difference,
                "tolerance": DUPLICATE_TOLERANCE,
                "sources": [
                    {
                        "run_dir": record["run_dir"],
                        "cell_id": record["cell_id"],
                    }
                    for record in group
                ],
            }
        )
    return unique, checks


def _load_run(run_dir: Path) -> tuple[list[dict[str, Any]], dict[str, int], list[dict[str, Any]]]:
    spec_path = run_dir / "run_spec.json"
    try:
        run_spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"run specification does not exist: {spec_path}") from error
    if not isinstance(run_spec, dict) or not isinstance(run_spec.get("cells"), list):
        raise ValueError(f"invalid run specification: {spec_path}")
    planned = {
        str(cell.get("cell_id")): _planned_cell_contract(run_spec, cell)
        for cell in run_spec["cells"]
    }
    if len(planned) != len(run_spec["cells"]):
        raise ValueError(f"duplicate cell_id in run specification: {spec_path}")

    report = parameter_scan.collect(run_spec, run_dir, "status", "success", ["result.value_real"])
    parameter_scan.write_csv(report["rows"], run_dir / "parameter-scan.csv")
    records: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    for row in report["rows"]:
        cell_id = str(row["cell_id"])
        expected = planned[cell_id]
        if row["status"] != "success":
            unavailable.append(
                {
                    "cell_id": cell_id,
                    "status": str(row["status"]),
                    "run_dir": str(run_dir),
                    "params": expected["params"],
                    "dop": expected["dop"],
                    "chi_env": expected["chi_env"],
                    "delta": expected["delta"],
                }
            )
            continue
        _, manifest = parameter_scan.classify_cell(run_dir, cell_id)
        if manifest is None:
            raise ValueError(f"{cell_id}: successful cell has no readable manifest")
        records.append(_successful_record(manifest, cell_id, run_dir, expected))
    return records, report["status_counts"], unavailable


def _sum_status_counts(counts: Iterable[dict[str, int]]) -> dict[str, int]:
    total = {"success": 0, "failed": 0, "missing": 0, "pending": 0}
    for count in counts:
        for status in total:
            total[status] += count.get(status, 0)
    return total


def _render_plot(
    assessment: dict[str, Any],
    unavailable: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, str]:
    plt.rcParams.update({"font.size": 8, "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8})
    figure, axes = plt.subplots(1, 2, figsize=(7.0, 3.1), sharey=True)
    cuts = (("Dₒₚ", "Operator bond Dₒₚ", assessment["dop_cut"], "dop", "#0072B2", "o", "-"), ("χₑₙᵥ", "Contraction bond χₑₙᵥ", assessment["chi_env_cut"], "chi_env", "#D55E00", "s", "--"))
    band_label = f"BP-TN mean ±{assessment['bp_budget']:.4f} (empirical)"
    for panel, (short_name, xlabel, cut, key, color, marker, linestyle) in enumerate(cuts):
        axis = axes[panel]
        xs = [record[key] for record in cut]
        ys = [record["value"] for record in cut]
        axis.axhspan(
            assessment["bp_mean"] - assessment["bp_budget"],
            assessment["bp_mean"] + assessment["bp_budget"],
            color="#999999",
            alpha=0.25,
            label=band_label,
            zorder=0,
        )
        axis.axhline(assessment["bp_mean"], color="#222222", linestyle=":", linewidth=1.0, label="BP-TN mean", zorder=1)
        axis.plot(xs, ys, color=color, marker=marker, linestyle=linestyle, linewidth=1.6, markersize=5, label=f"PEPO cut over {short_name}", zorder=2)
        for x, y in zip(xs, ys):
            axis.annotate(f"{y:.6f}", (x, y), xytext=(0, 6), textcoords="offset points", ha="center", color=color, fontsize=7)
        axis.set_xlabel(xlabel)
        axis.set_title("A" if panel == 0 else "B", loc="left", fontweight="bold")
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.legend(frameon=False, fontsize=6.5, loc="best")
    axes[0].set_ylabel("Normalized OLE F")
    if unavailable:
        shown = "; ".join(
            f"Dop={item['dop']}, χenv={item['chi_env']}, δ={item['delta']:g} ({item['status']})"
            for item in unavailable[:3]
        )
        extra = "" if len(unavailable) <= 3 else f"; +{len(unavailable) - 3} more"
        figure.text(0.01, 0.01, f"Unavailable planned cells: {shown}{extra}", fontsize=7)
    figure.tight_layout(rect=(0.0, 0.05 if unavailable else 0.0, 1.0, 1.0))
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / "pepo-convergence.png"
    pdf_path = output_dir / "pepo-convergence.pdf"
    figure.savefig(png_path, dpi=300)
    figure.savefig(pdf_path)
    plt.close(figure)
    return {"png": str(png_path), "pdf": str(pdf_path)}


def _write_report(assessment: dict[str, Any], output_dir: Path) -> Path:
    corner = assessment["corner"]
    unavailable = assessment["failed_or_incomplete_cells"]
    internal = "converged" if assessment["internally_converged"] else "not converged"
    comparison = assessment["comparison_status"]
    lines = [
        "# 49-qubit PEPO validation",
        "",
        f"FPEPO = {corner['value']:.16g} at Dop={corner['dop']}, χenv={corner['chi_env']}.",
        f"εPEPO = {assessment['epsilon_pepo']:.6g} (empirical ΔDop + Δχenv); internal convergence: **{internal}**.",
        f"BP-TN comparison: **{comparison}**; |FPEPO − FBP| = {assessment['bp_difference']:.6g}, combined empirical budget = {assessment['agreement_limit']:.6g}.",
        "",
        "The PEPO and BP-TN budgets are empirical numerical envelopes, not rigorous error bounds. No infinite-bond extrapolation was used.",
        "",
        "## Scan coverage",
        "",
        f"Successful cells: {assessment['successful_record_count']}; failed/missing/pending planned cells: {len(unavailable)}.",
        f"ΔDop = {assessment['delta_dop']:.6g}; Δχenv = {assessment['delta_chi_env']:.6g}; target = {assessment['target']:.6g}.",
    ]
    if not assessment["chi_env_at_corner"]:
        lines.extend(
            [
                "",
                (
                    f"χenv cut evaluated at Dop={assessment['chi_env_reference_dop']}, "
                    f"below the Dop={corner['dop']} corner; this inherited χenv proxy "
                    "cannot by itself certify internal convergence at the corner."
                ),
            ]
        )
    if unavailable:
        lines.extend(["", "Unavailable cells are retained in assessment.json:"])
        lines.extend(
            f"- Dop={item['dop']}, χenv={item['chi_env']}, δ={item['delta']:g}: {item['status']} ({item['run_dir']}/{item['cell_id']})"
            for item in unavailable
        )
    report_path = output_dir / "PEPO_49Q_VALIDATION.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def analyze_run_directories(
    run_dirs: Iterable[str | Path],
    *,
    output_dir: str | Path,
    bp_mean: float = DEFAULT_BP_MEAN,
    bp_budget: float = DEFAULT_BP_BUDGET,
    target: float = DEFAULT_TARGET,
) -> dict[str, Any]:
    """Collect generic scan records, assess convergence, and write artifacts."""
    paths = [Path(path) for path in run_dirs]
    if not paths:
        raise ValueError("at least one run directory is required")
    all_records: list[dict[str, Any]] = []
    all_unavailable: list[dict[str, Any]] = []
    counts: list[dict[str, int]] = []
    for run_dir in paths:
        records, status_counts, unavailable = _load_run(run_dir)
        all_records.extend(records)
        all_unavailable.extend(unavailable)
        counts.append(status_counts)
    _validate_consensus(all_records)
    unique_records, duplicate_checks = _reconcile_duplicate_records(all_records)
    assessment = assess_convergence(unique_records, bp_mean, bp_budget, target)
    assessment["records"] = all_records
    assessment["run_dirs"] = [str(path) for path in paths]
    assessment["status_counts"] = _sum_status_counts(counts)
    assessment["successful_record_count"] = len(all_records)
    assessment["unique_coordinate_count"] = len(unique_records)
    assessment["duplicate_checks"] = duplicate_checks
    assessment["failed_or_incomplete_cells"] = all_unavailable
    destination = Path(output_dir)
    assessment["figure"] = _render_plot(assessment, all_unavailable, destination)
    assessment["report"] = str(_write_report(assessment, destination))
    (destination / "assessment.json").write_text(json.dumps(assessment, indent=2) + "\n", encoding="utf-8")
    return assessment


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", action="append", required=True, help="PEPO run directory containing run_spec.json; repeatable")
    parser.add_argument("--output-dir", required=True, help="directory for assessment.json, report, and figures")
    parser.add_argument("--bp-mean", type=float, default=DEFAULT_BP_MEAN)
    parser.add_argument("--bp-budget", type=float, default=DEFAULT_BP_BUDGET)
    parser.add_argument("--target", type=float, default=DEFAULT_TARGET)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        assessment = analyze_run_directories(
            args.run_dir,
            output_dir=args.output_dir,
            bp_mean=args.bp_mean,
            bp_budget=args.bp_budget,
            target=args.target,
        )
    except ValueError as error:
        print(f"analysis error: {error}", file=sys.stderr)
        return 2
    print(f"FPEPO={assessment['corner']['value']:.16g}")
    print(f"epsilon_pepo={assessment['epsilon_pepo']:.6g}")
    print(f"internal_convergence={assessment['internally_converged']}")
    print(f"bp_comparison={assessment['comparison_status']}")
    print(f"assessment={Path(args.output_dir) / 'assessment.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
