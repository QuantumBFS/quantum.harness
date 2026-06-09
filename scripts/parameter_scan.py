#!/usr/bin/env python3
"""Mechanical stages of the parameter-scan workflow.

This CLI implements the deterministic, physics-free stages of
``skills/parameter-scan/SKILL.md``: Cartesian-product planning, manifest
collection/validation, data-shape labeling, and arity-based plotting. Range
choice and physical interpretation stay with the calling agent.

Everything is generic over axis names and manifest fields: ``params``,
``settings``, and ``provenance`` are treated as opaque data, never schema.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


# --------------------------------------------------------------------------- #
# Generic helpers
# --------------------------------------------------------------------------- #
def _load_json(path: str | Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _dump_json(obj: Any, path: str | Path, *, pretty: bool = True) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        if pretty:
            json.dump(obj, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        else:
            json.dump(obj, fh, ensure_ascii=False)


def _get_path(obj: Any, dotted: str) -> tuple[bool, Any]:
    """Walk a dotted path into nested dicts. Returns (found, value)."""
    cur = obj
    for key in dotted.split("."):
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return False, None
    return True, cur


def _coerce_str(value: Any) -> str:
    """Render a scalar so it compares stably against a CLI string value."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Stage 1: plan
# --------------------------------------------------------------------------- #
def build_plan(
    axes: dict[str, list[Any]],
    run_id: str,
    run_dir: str,
    settings: dict[str, Any] | None,
    provenance: dict[str, Any] | None,
) -> dict[str, Any]:
    """Enumerate the Cartesian product of axes (insertion order preserved)."""
    axis_names = list(axes.keys())
    value_lists = [axes[name] for name in axis_names]
    cells: list[dict[str, Any]] = []
    for idx, combo in enumerate(itertools.product(*value_lists), start=1):
        params = {name: val for name, val in zip(axis_names, combo)}
        cells.append({"cell_id": f"cell-{idx:04d}", "params": params})
    run_spec: dict[str, Any] = {
        "run_id": run_id,
        "run_dir": run_dir,
        "settings": settings or {},
        "provenance": provenance or {},
        "cells": cells,
    }
    return run_spec


def cmd_plan(args: argparse.Namespace) -> None:
    axes = _load_json(args.axes)
    if not isinstance(axes, dict):
        raise SystemExit("axes.json must be a JSON object {axis_name: [values...]}")
    settings = _load_json(args.settings) if args.settings else {}
    provenance = _load_json(args.provenance) if args.provenance else {}
    run_dir = args.run_dir or f"results/{args.run_id}"

    run_spec = build_plan(axes, args.run_id, run_dir, settings, provenance)

    plan = {
        "run_id": args.run_id,
        "run_dir": run_dir,
        "axes": axes,
        "cells": run_spec["cells"],
    }
    _dump_json(plan, Path(run_dir) / "parameter-scan.plan.json")
    _dump_json(run_spec, Path(run_dir) / "run_spec.json")
    print(f"planned {len(run_spec['cells'])} cells -> {run_dir}/run_spec.json")


# --------------------------------------------------------------------------- #
# Stage 2: collect
# --------------------------------------------------------------------------- #
def classify_cell(run_dir: Path, cell_id: str) -> tuple[str, dict[str, Any] | None]:
    """Return (raw_status, manifest). raw_status is pending|missing|present."""
    cell_dir = run_dir / "cells" / cell_id
    if not cell_dir.is_dir():
        return "pending", None
    manifest_path = cell_dir / "manifest.json"
    if not manifest_path.is_file():
        return "missing", None
    try:
        manifest = _load_json(manifest_path)
    except (json.JSONDecodeError, OSError):
        return "missing", None
    return "present", manifest


def _success_status(
    manifest: dict[str, Any],
    success_field: str | None,
    success_value: str,
) -> str:
    if success_field is None:
        return "success"
    found, val = _get_path(manifest, success_field)
    if not found:
        return "failed"
    return "success" if _coerce_str(val) == success_value else "failed"


def _check_contract(
    manifest: dict[str, Any],
    contract: dict[str, Any],
) -> list[str]:
    """Generic field-path checks. Returns a list of violation strings."""
    violations: list[str] = []
    for field, rule in contract.items():
        found, val = _get_path(manifest, field)
        rtype = rule.get("type", "required") if isinstance(rule, dict) else "required"
        if rtype == "optional" and not found:
            continue
        if not found:
            violations.append(f"{field}: missing (required)")
            continue
        if rtype in ("required", "nonempty"):
            if val is None or val == "" or val == [] or val == {}:
                violations.append(f"{field}: empty (nonempty required)")
        elif rtype == "equality":
            expected = rule.get("value")
            if _coerce_str(val) != _coerce_str(expected):
                violations.append(f"{field}: {val!r} != declared {expected!r}")
        elif rtype == "membership":
            allowed = rule.get("values", [])
            if val not in allowed:
                violations.append(f"{field}: {val!r} not in {allowed!r}")
        elif rtype == "bounds":
            fv = _to_float(val)
            if fv is None:
                violations.append(f"{field}: {val!r} not numeric")
            else:
                lo, hi = rule.get("min"), rule.get("max")
                if lo is not None and fv < lo:
                    violations.append(f"{field}: {fv} < min {lo}")
                if hi is not None and fv > hi:
                    violations.append(f"{field}: {fv} > max {hi}")
        elif rtype == "evidence-set":
            required = set(rule.get("members", []))
            present = set(val) if isinstance(val, (list, set, tuple)) else set()
            missing = required - present
            if missing:
                violations.append(f"{field}: missing evidence {sorted(missing)}")
    return violations


def collect(
    run_spec: dict[str, Any],
    run_dir: Path,
    success_field: str | None,
    success_value: str,
    value_fields: list[str],
) -> dict[str, Any]:
    """Assemble every planned cell, classify status, validate manifests."""
    shared_settings = run_spec.get("settings", {})
    shared_prov = run_spec.get("provenance", {})
    assemble = run_spec.get("assemble", {})
    manifest_contract = assemble.get("manifest_contract", {})
    consensus_fields = assemble.get("consensus_fields", [])
    provenance_fields = assemble.get("provenance_fields", [])

    rows: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {"success": 0, "failed": 0, "missing": 0, "pending": 0}
    contract_violations: list[str] = []
    consensus_observed: dict[str, set[str]] = {f: set() for f in consensus_fields}
    provenance_violations: list[str] = []
    # observed settings per cell, for constant-vs-varying summary
    settings_observed: dict[str, set[str]] = {}

    for cell in run_spec["cells"]:
        cell_id = cell["cell_id"]
        params = cell.get("params", {})
        per_cell_settings = cell.get("settings", {})
        merged_settings = {**shared_settings, **per_cell_settings}

        raw_status, manifest = classify_cell(run_dir, cell_id)
        if raw_status == "pending":
            status = "pending"
        elif raw_status == "missing":
            status = "missing"
        else:
            status = _success_status(manifest, success_field, success_value)

        row: dict[str, Any] = {"cell_id": cell_id, **params, "status": status}

        if manifest is not None:
            # Pull requested observable fields.
            for vf in value_fields:
                found, val = _get_path(manifest, vf)
                col = vf.split(".")[-1]
                row[col] = val if found else ""

            # Contract checks.
            if manifest_contract:
                for v in _check_contract(manifest, manifest_contract):
                    contract_violations.append(f"{cell_id}: {v}")

            # Consensus tracking (equality across all cells).
            for f in consensus_fields:
                found, val = _get_path(manifest, f)
                if found:
                    consensus_observed[f].add(_coerce_str(val))

            # Provenance equality vs run-spec provenance.
            for f in provenance_fields:
                m_found, m_val = _get_path(manifest, f)
                p_found, p_val = _get_path({"provenance": shared_prov}, f)
                if not p_found:
                    p_found, p_val = _get_path(shared_prov, f)
                if m_found and p_found and _coerce_str(m_val) != _coerce_str(p_val):
                    provenance_violations.append(f"{cell_id}: {f} {m_val!r} != run_spec {p_val!r}")

            # Observed merged-settings for constant-vs-varying report. We use
            # the manifest's echoed settings when present, else merged plan.
            echoed = manifest.get("settings") if isinstance(manifest, dict) else None
            effective = echoed if isinstance(echoed, dict) else merged_settings
            for k, v in effective.items():
                settings_observed.setdefault(k, set()).add(_coerce_str(v))
        else:
            for vf in value_fields:
                row[vf.split(".")[-1]] = ""

        rows.append(row)
        status_counts[status] += 1

    consensus_violations = [
        f"{f}: varies across cells {sorted(vals)}"
        for f, vals in consensus_observed.items()
        if len(vals) > 1
    ]

    constant_settings = {k: next(iter(v)) for k, v in settings_observed.items() if len(v) == 1}
    varying_settings = {k: sorted(v) for k, v in settings_observed.items() if len(v) > 1}

    return {
        "rows": rows,
        "status_counts": status_counts,
        "constant_settings": constant_settings,
        "varying_settings": varying_settings,
        "contract_violations": contract_violations,
        "consensus_violations": consensus_violations,
        "provenance_violations": provenance_violations,
    }


def write_csv(rows: list[dict[str, Any]], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Union of keys, preserving first-seen order.
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def cmd_collect(args: argparse.Namespace) -> None:
    run_spec = _load_json(args.run_spec)
    run_dir = Path(run_spec.get("run_dir") or Path(args.run_spec).parent)
    if not run_dir.is_absolute() and not run_dir.exists():
        # run_dir from spec may be relative to cwd; fall back to spec location.
        candidate = Path(args.run_spec).parent
        if (candidate / "cells").exists() or not run_dir.exists():
            run_dir = candidate

    report = collect(
        run_spec,
        run_dir,
        args.success_field,
        args.success_value,
        args.value_field or [],
    )
    csv_path = run_dir / "parameter-scan.csv"
    write_csv(report["rows"], csv_path)

    sc = report["status_counts"]
    print(f"collected {len(report['rows'])} cells -> {csv_path}")
    print(
        f"  status: success={sc['success']} failed={sc['failed']} "
        f"missing={sc['missing']} pending={sc['pending']}"
    )
    if report["constant_settings"]:
        print(f"  constant settings: {report['constant_settings']}")
    if report["varying_settings"]:
        print(f"  varying settings:  {report['varying_settings']}")
    for v in report["contract_violations"]:
        print(f"  CONTRACT VIOLATION: {v}")
    for v in report["consensus_violations"]:
        print(f"  CONSENSUS VIOLATION: {v}")
    for v in report["provenance_violations"]:
        print(f"  PROVENANCE VIOLATION: {v}")


# --------------------------------------------------------------------------- #
# Stage 3: shape
# --------------------------------------------------------------------------- #
def _diffs(ys: list[float]) -> list[float]:
    return [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]


def _is_monotone(ys: list[float]) -> bool:
    d = _diffs(ys)
    nz = [x for x in d if x != 0]
    if not nz:
        return False
    return all(x > 0 for x in nz) or all(x < 0 for x in nz)


def _is_asymptoting(ys: list[float]) -> bool:
    ad = [abs(x) for x in _diffs(ys)]
    if len(ad) < 2:
        return False
    # successive absolute differences shrink monotonically (non-increasing,
    # with at least one strict decrease).
    strict = False
    for i in range(len(ad) - 1):
        if ad[i + 1] > ad[i] + 1e-12:
            return False
        if ad[i + 1] < ad[i] - 1e-12:
            strict = True
    return strict


def _is_power_law_like(xs: list[float], ys: list[float]) -> tuple[bool, float]:
    """Stable log-log local slope -> small relative variance of slopes."""
    if any(x <= 0 for x in xs) or any(y <= 0 for y in ys):
        return False, float("nan")
    lx = [math.log(x) for x in xs]
    ly = [math.log(y) for y in ys]
    slopes = []
    for i in range(len(lx) - 1):
        dx = lx[i + 1] - lx[i]
        if dx == 0:
            return False, float("nan")
        slopes.append((ly[i + 1] - ly[i]) / dx)
    if len(slopes) < 2:
        return False, float("nan")
    mean = sum(slopes) / len(slopes)
    if mean == 0:
        return False, float("nan")
    var = sum((s - mean) ** 2 for s in slopes) / len(slopes)
    rel = math.sqrt(var) / abs(mean)
    return rel < 0.15, rel


def _interior_extrema(ys: list[float]) -> list[int]:
    """Indices of interior local peaks/valleys."""
    idx = []
    for i in range(1, len(ys) - 1):
        if (ys[i] > ys[i - 1] and ys[i] > ys[i + 1]) or (ys[i] < ys[i - 1] and ys[i] < ys[i + 1]):
            idx.append(i)
    return idx


def _is_step_like(ys: list[float]) -> tuple[bool, int]:
    """A single successive jump much larger than the others."""
    ad = [abs(x) for x in _diffs(ys)]
    if len(ad) < 2:
        return False, -1
    order = sorted(range(len(ad)), key=lambda i: ad[i], reverse=True)
    largest, second = ad[order[0]], ad[order[1]]
    if largest > 1e-12 and (second < 1e-12 or largest > 4.0 * second):
        return True, order[0]
    return False, -1


def _detect_crossing(curves: dict[str, tuple[list[float], list[float]]]) -> bool:
    """Two series cross if their difference changes sign along shared x."""
    keys = list(curves.keys())
    for a in range(len(keys)):
        for b in range(a + 1, len(keys)):
            xa, ya = curves[keys[a]]
            xb, yb = curves[keys[b]]
            # align on common x values
            mb = dict(zip(xb, yb))
            diffs = [ya[i] - mb[x] for i, x in enumerate(xa) if x in mb]
            signs = [d for d in diffs if abs(d) > 1e-12]
            for i in range(len(signs) - 1):
                if signs[i] * signs[i + 1] < 0:
                    return True
    return False


def label_curve(xs: list[float], ys: list[float]) -> dict[str, Any]:
    """Single-curve data-shape label (no physics)."""
    n = len(ys)
    if n < 2:
        return {"label": "Drifting/oscillating", "metric": "insufficient-points"}

    step, step_idx = _is_step_like(ys)
    if step:
        return {"label": "Step-like", "metric": f"jump-at-index-{step_idx}"}

    extrema = _interior_extrema(ys)
    # A single dominant interior extremum is "Extremum"; multiple interior
    # turning points are "Drifting/oscillating".
    if len(extrema) == 1:
        return {"label": "Extremum", "metric": f"interior-index-{extrema[0]}"}
    if len(extrema) > 1:
        return {"label": "Drifting/oscillating", "metric": f"{len(extrema)}-interior-extrema"}

    if _is_monotone(ys):
        pl, rel = _is_power_law_like(xs, ys)
        if pl:
            return {"label": "Power-law-like", "metric": f"loglog-slope-relstd-{rel:.4f}"}
        if _is_asymptoting(ys):
            return {"label": "Asymptoting", "metric": "shrinking-abs-diffs"}
        direction = "increasing" if ys[-1] > ys[0] else "decreasing"
        return {"label": "Monotone", "metric": direction}

    if _is_asymptoting(ys):
        return {"label": "Asymptoting", "metric": "shrinking-abs-diffs"}

    return {"label": "Drifting/oscillating", "metric": "no-clean-trend"}


def _read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def shape_from_csv(
    rows: list[dict[str, str]],
    x_axis: str,
    value_col: str,
    series_axis: str | None,
) -> dict[str, Any]:
    """Build curves from rows and label each."""

    def numeric_rows(filtered: list[dict[str, str]]) -> tuple[list[float], list[float]]:
        pts = []
        for r in filtered:
            x = _to_float(r.get(x_axis))
            y = _to_float(r.get(value_col))
            if x is not None and y is not None:
                pts.append((x, y))
        pts.sort(key=lambda p: p[0])
        return [p[0] for p in pts], [p[1] for p in pts]

    result: dict[str, Any] = {}
    if series_axis:
        curves: dict[str, tuple[list[float], list[float]]] = {}
        series_vals = []
        for r in rows:
            sv = r.get(series_axis)
            if sv not in series_vals:
                series_vals.append(sv)
        for sv in series_vals:
            sub = [r for r in rows if r.get(series_axis) == sv]
            xs, ys = numeric_rows(sub)
            curves[str(sv)] = (xs, ys)
            result[str(sv)] = label_curve(xs, ys)
        if _detect_crossing(curves):
            result["_crossing"] = {"label": "Crossing", "metric": "sign-change-between-series"}
    else:
        xs, ys = numeric_rows(rows)
        result["all"] = label_curve(xs, ys)
    return result


def cmd_shape(args: argparse.Namespace) -> None:
    rows = _read_csv_rows(args.csv)
    result = shape_from_csv(rows, args.x_axis, args.value_col, args.series_axis)
    print(json.dumps(result, ensure_ascii=False))
    labels = {k: v["label"] for k, v in result.items()}
    print(f"shape: {labels}")


# --------------------------------------------------------------------------- #
# Stage 4: plot
# --------------------------------------------------------------------------- #
def _resolve_axes(axes_arg: str) -> list[str]:
    p = Path(axes_arg)
    if p.is_file():
        axes = _load_json(p)
        if isinstance(axes, dict):
            return list(axes.keys())
        raise SystemExit("axes file must be a JSON object")
    return [a.strip() for a in axes_arg.split(",") if a.strip()]


def plot_from_csv(
    rows: list[dict[str, str]],
    axis_names: list[str],
    value_col: str,
    err_col: str | None,
    out: str | Path,
) -> str:
    arity = len(axis_names)
    fig, ax = plt.subplots(figsize=(6, 4.2))

    def fnum(r: dict[str, str], key: str) -> float | None:
        return _to_float(r.get(key))

    if arity <= 1:
        x_axis = axis_names[0] if axis_names else None
        pts = []
        for r in rows:
            x = fnum(r, x_axis) if x_axis else None
            y = fnum(r, value_col)
            if x is not None and y is not None:
                e = fnum(r, err_col) if err_col else None
                pts.append((x, y, e))
        pts.sort(key=lambda p: p[0])
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if err_col:
            es = [p[2] if p[2] is not None else 0.0 for p in pts]
            ax.errorbar(xs, ys, yerr=es, marker="o", capsize=3)
        else:
            ax.plot(xs, ys, marker="o")
        ax.set_xlabel(x_axis or "index")
        ax.set_ylabel(value_col)
        ax.set_title(f"{value_col} vs {x_axis}")

    elif arity == 2:
        x_axis, series_axis = axis_names[0], axis_names[1]
        series_vals = []
        for r in rows:
            sv = r.get(series_axis)
            if sv not in series_vals:
                series_vals.append(sv)
        for sv in series_vals:
            sub = [r for r in rows if r.get(series_axis) == sv]
            pts = []
            for r in sub:
                x = fnum(r, x_axis)
                y = fnum(r, value_col)
                if x is not None and y is not None:
                    pts.append((x, y))
            pts.sort(key=lambda p: p[0])
            ax.plot(
                [p[0] for p in pts], [p[1] for p in pts], marker="o", label=f"{series_axis}={sv}"
            )
        ax.set_xlabel(x_axis)
        ax.set_ylabel(value_col)
        ax.set_title(f"{value_col} vs {x_axis} (family over {series_axis})")
        ax.legend(fontsize=8)

    else:
        # >=3 axes: heatmap over the two axes with the most distinct values.
        distinct = {}
        for a in axis_names:
            distinct[a] = len({r.get(a) for r in rows})
        ranked = sorted(axis_names, key=lambda a: distinct[a], reverse=True)
        ax_x, ax_y = ranked[0], ranked[1]
        held = ranked[2:]

        x_vals = sorted(
            {_to_float(r.get(ax_x)) for r in rows if _to_float(r.get(ax_x)) is not None}
        )
        y_vals = sorted(
            {_to_float(r.get(ax_y)) for r in rows if _to_float(r.get(ax_y)) is not None}
        )
        grid = [[math.nan for _ in x_vals] for _ in y_vals]
        xi = {v: i for i, v in enumerate(x_vals)}
        yi = {v: i for i, v in enumerate(y_vals)}
        for r in rows:
            xv = _to_float(r.get(ax_x))
            yv = _to_float(r.get(ax_y))
            zv = _to_float(r.get(value_col))
            if xv in xi and yv in yi and zv is not None:
                grid[yi[yv]][xi[xv]] = zv
        im = ax.imshow(
            grid,
            origin="lower",
            aspect="auto",
            extent=[min(x_vals), max(x_vals), min(y_vals), max(y_vals)]
            if x_vals and y_vals
            else None,
        )
        fig.colorbar(im, ax=ax, label=value_col)
        ax.set_xlabel(ax_x)
        ax.set_ylabel(ax_y)
        held_note = f"; held/faceted: {', '.join(held)}" if held else ""
        ax.set_title(f"{value_col} over {ax_x}x{ax_y}{held_note}")

    fig.tight_layout()
    out = str(out)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def cmd_plot(args: argparse.Namespace) -> None:
    rows = _read_csv_rows(args.csv)
    axis_names = _resolve_axes(args.axes)
    out = args.out or str(Path(args.csv).parent / "parameter-scan.png")
    path = plot_from_csv(rows, axis_names, args.value_col, args.err_col, out)
    print(path)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="Cartesian-product enumeration -> run_spec.json")
    p_plan.add_argument("--axes", required=True, help="JSON object {axis: [values...]}")
    p_plan.add_argument("--run-id", required=True)
    p_plan.add_argument("--run-dir", default=None, help="default results/<run-id>")
    p_plan.add_argument("--settings", default=None, help="shared settings JSON")
    p_plan.add_argument("--provenance", default=None, help="shared provenance JSON")
    p_plan.set_defaults(func=cmd_plan)

    p_col = sub.add_parser("collect", help="assemble + validate manifests -> csv")
    p_col.add_argument("--run-spec", required=True)
    p_col.add_argument("--success-field", default=None, help="dotted path into manifest")
    p_col.add_argument("--success-value", default="true")
    p_col.add_argument(
        "--value-field", action="append", default=None, help="dotted path; repeatable"
    )
    p_col.set_defaults(func=cmd_collect)

    p_shape = sub.add_parser("shape", help="data-shape labels (no physics)")
    p_shape.add_argument("--csv", required=True)
    p_shape.add_argument("--x-axis", required=True)
    p_shape.add_argument("--value-col", required=True)
    p_shape.add_argument("--series-axis", default=None)
    p_shape.set_defaults(func=cmd_shape)

    p_plot = sub.add_parser("plot", help="choose plot by axis arity")
    p_plot.add_argument("--csv", required=True)
    p_plot.add_argument("--axes", required=True, help="axes.json or comma list of axis names")
    p_plot.add_argument("--value-col", required=True)
    p_plot.add_argument("--err-col", default=None)
    p_plot.add_argument("--out", default=None)
    p_plot.set_defaults(func=cmd_plot)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
