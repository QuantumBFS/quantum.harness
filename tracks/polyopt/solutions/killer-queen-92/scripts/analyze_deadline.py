#!/usr/bin/env python3
"""Aggregate short-deadline runs into explicit tables, checks, and presentation plots."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable

CLASSIFICATIONS = frozenset(("FEASIBLE", "EXCLUDED", "UNKNOWN"))
OBSERVABLES = ("rho0", "F0", "K0")
SENSES = ("min", "max")
SCNET_CAMPAIGN_JOBS = {
    "observable array": "41510919",
    "nested-level array": "41510920",
    "fixed-gamma array": "41510940",
    "expedited fixed-gamma arrays": "41519302, 41523224",
    "gap-refinement array": "41523716",
    "alternate-KKT retry": "41525914",
    "reduced-thread MKL retry": "41531990",
    "CHOLMOD retry": "41532367",
    "8-thread MKL retry": "41533826",
    "transition micro-scan": "41534382",
    "geometry refinements": "41534386, 41534390",
    "geometry parallel recovery": "41541949",
    "geometry midpoint recovery": "41542751",
    "extended geometry Target-2 grid": "41543225 (tasks 0-3 running; tasks 4-7 array-throttled)",
    "remaining-point gap scan": "41534717",
    "remaining-point transition refinement": "41538360 (pre-fast-path replacement), 41539201",
    "P5 fine refinement": "41539896",
    "P3 micro refinement": "41540154",
    "remaining-point observables": "41534723",
    "cutoff-2 representative": "41535104 (allocation-gate failure), 41535172 (192-GiB OOM), 41540049 (237-GiB OOM), 41540879 (237-GiB/8-thread OOM), 41541639 (237-GiB QDLDL OOM)",
    "cutoff-2 TS2 dry gate": "41541783 (task 28 SIGBUS; old-code task 31 canceled without checkpoint), 41542822 (optimized task-28 running), 41544379 (resumable optimized task-31 guard)",
    "exact observable representative": "41535927 (QDLDL no-checkpoint replacement), 41536972 (MKL)",
}
CUTOFF2_RESOURCE_ROW = {
    "geometry": "83 (nmax=2)",
    "point": "P2",
    "L": 1,
    "d": 2,
    "requested_memory_gb": "192 / 237",
    "message": (
        "job 41535172 assembled the workspace in 158.52 s, then Slurm recorded "
        "OUT_OF_MEMORY (MaxRSS 199029304 KiB) while solving gamma=0.75; "
        "max-size retry 41540049 assembled in 162.12 s and checkpointed all four "
        "trials as UNKNOWN/OutOfMemoryError (MaxRSS 237910752 KiB); wrapper "
        "completion is not a solver result; eight-thread retry 41540879 also OOMed "
        "at MaxRSS 233357596 KiB; QDLDL retry 41541639 likewise checkpointed "
        "four UNKNOWN/OutOfMemoryError rows at MaxRSS 214327588 KiB"
    ),
}
TS2_DRY_RESOURCE_ROW = {
    "geometry": "83 (nmax=2 TS2)",
    "point": "dry gate",
    "L": 1,
    "d": 3,
    "requested_memory_gb": 192,
    "message": (
        "job 41541783_28 died with SIGBUS after 648 s at MaxRSS 1878056 KiB, "
        "far below allocation; no level record was produced; optimized different-node "
        "retry 41542822 is running and optimized task-31 guard 41544379 is queued"
    ),
}


def classification(value: object) -> str:
    result = str(value if value is not None else "UNKNOWN").upper()
    if result not in CLASSIFICATIONS:
        raise ValueError(f"invalid scientific classification {result!r}")
    return result


def load_json(path: Path) -> dict[str, object] | None:
    return json.loads(path.read_text()) if path.exists() else None


def atomic_csv(path: Path, rows: list[dict[str, object]], fields: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text)
    os.replace(temporary, path)


def observable_rows(manifest_path: Path, results_dir: Path) -> list[dict[str, object]]:
    manifest = json.loads(manifest_path.read_text())
    rows: list[dict[str, object]] = []
    for cell in manifest["cells"]:
        payload = load_json(results_dir / f"{cell['id']}.json")
        indexed = {
            (item["observable"], item["sense"]): item["record"]
            for item in (payload or {}).get("results", [])
        }
        for observable in OBSERVABLES:
            for sense in SENSES:
                record = indexed.get((observable, sense), {})
                scientific = classification(record.get("classification"))
                dual_data = record.get("dual_data") or {}
                direct_report = dual_data.get("certificate_report") or {}
                source_report = dual_data.get("source_certificate_report") or {}
                evidence_report = direct_report or source_report
                certificate_class = record.get("certificate_class", "NO_CERTIFICATE")
                floating_objective = record.get("objective")
                certified_objective = direct_report.get("certified_objective")
                reported_objective = (
                    certified_objective
                    if certificate_class == "VERIFIED_EXACT_PROJECTED_BOUND"
                    and certified_objective is not None
                    else floating_objective
                )
                rows.append(
                    {
                        "id": cell["id"], "geometry": cell["geometry"],
                        "point": cell["point"], "t": cell["t"], "mu": cell["mu"],
                        "gamma": cell["gamma"], "nmax": cell["nmax"],
                        "L": cell["L"], "d": cell["d"], "observable": observable,
                        "encoding": cell.get("encoding"),
                        "basis_family": cell.get("basis_family"),
                        "symmetry": cell.get("symmetry"),
                        "precision_profile": cell.get("precision_profile"),
                        "requested_memory_gb": cell.get("requested_memory_gb"),
                        "sense": sense, "classification": scientific,
                        "optimum": reported_objective,
                        "floating_optimum": floating_objective,
                        "certified_objective": certified_objective,
                        "raw_status": record.get("raw_status"),
                        "solver": record.get("solver"), "runtime_seconds": record.get("runtime_seconds"),
                        "primal_residual": record.get("primal_residual"),
                        "dual_residual": record.get("dual_residual"),
                        "min_psd_eigenvalue": record.get("min_psd_eigenvalue"),
                        "certificate_class": certificate_class,
                        "certificate_precision_bits": evidence_report.get("precision_bits"),
                        "certificate_affine_residual": evidence_report.get("max_affine_residual"),
                        "certificate_psd_verified": evidence_report.get("psd_verified"),
                        "certificate_objective_gap": evidence_report.get("normalized_objective_gap"),
                        "message": record.get("message", "objective not completed"),
                        "cell_status": (payload or {}).get("status", "MISSING"),
                        "diagnostic_only": bool(cell.get("diagnostic_only", False)),
                    }
                )
    return rows


def deduplicate_observable_rows(
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Prefer exact upgrades over the same physical objective's earlier checkpoint."""
    keys = (
        "geometry", "point", "t", "mu", "gamma", "nmax", "L", "d",
        "encoding", "basis_family", "symmetry", "observable", "sense",
    )

    def rank(row: dict[str, object]) -> tuple[int, int]:
        certificate = str(row.get("certificate_class") or "")
        if "VERIFIED_EXACT_PROJECTED_BOUND" in certificate:
            return (5, 1)
        if row.get("classification") == "FEASIBLE" and (
            "PRIMAL_DUAL_CHECKED" in certificate or certificate.startswith("DERIVED_EXACT_AFFINE")
        ):
            return (4, 1)
        if row.get("classification") == "FEASIBLE":
            return (3, 1)
        if row.get("raw_status") is not None:
            return (2, 1)
        return (0, 0)

    selected: dict[tuple[object, ...], dict[str, object]] = {}
    for row in rows:
        key = tuple(row.get(name) for name in keys)
        current = selected.get(key)
        if current is None or rank(row) > rank(current):
            selected[key] = row
    return sorted(
        selected.values(),
        key=lambda row: (
            str(row["geometry"]), str(row["point"]), float(row["gamma"]),
            int(row["nmax"]), int(row["L"]), int(row["d"]),
            str(row["observable"]), str(row["sense"]),
        ),
    )


def interval_rows(records: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], dict[str, dict[str, object]]] = {}
    # `records` has already selected the strongest endpoint for each physical
    # objective.  Do not include the campaign id here: an exact-certificate
    # rerun intentionally has a different id from the floating baseline whose
    # opposite endpoint it upgrades.
    keys = ("geometry", "point", "t", "mu", "gamma", "nmax", "L", "d", "observable")
    for row in records:
        key = tuple(row[field] for field in keys)
        grouped.setdefault(key, {})[str(row["sense"])] = row
    intervals: list[dict[str, object]] = []
    for key, senses in grouped.items():
        base = dict(zip(keys, key))
        lower, upper = senses.get("min", {}), senses.get("max", {})
        source = lower or upper
        base["id"] = source.get("id", "")
        accepted = (
            lower.get("classification") == "FEASIBLE"
            and upper.get("classification") == "FEASIBLE"
            and lower.get("optimum") is not None and upper.get("optimum") is not None
        )
        lower_value = float(lower["optimum"]) if accepted else None
        upper_value = float(upper["optimum"]) if accepted else None
        ordered = accepted and lower_value <= upper_value + 1e-6
        intervals.append(
            {
                **base, "lower": lower_value, "upper": upper_value,
                "width": upper_value-lower_value if accepted else None,
                "accepted": bool(accepted and ordered),
                "order_check": "PASS" if ordered else "FAIL" if accepted else "UNKNOWN",
                "lower_certificate_class": lower.get("certificate_class", "NO_CERTIFICATE"),
                "upper_certificate_class": upper.get("certificate_class", "NO_CERTIFICATE"),
                "reason": "both endpoints passed independent checks" if accepted and ordered else "one or both endpoints unavailable",
            }
        )
    return intervals


def gap_scan_rows(manifest_path: Path, results_dir: Path) -> list[dict[str, object]]:
    manifest = json.loads(manifest_path.read_text())
    rows: list[dict[str, object]] = []
    for cell in manifest["cells"]:
        payload = load_json(results_dir / f"{cell['id']}.json")
        indexed = {
            round(float(item["gamma"]), 12): item["record"]
            for item in (payload or {}).get("trials", [])
        }
        for gamma in cell["gamma_trials"]:
            record = indexed.get(round(float(gamma), 12), {})
            certificate_report = (
                (record.get("dual_data") or {}).get("certificate_report") or {}
            )
            rows.append(
                {
                    "id": cell["id"], "geometry": cell["geometry"],
                    "point": cell["point"], "t": cell["t"], "mu": cell["mu"],
                    "gamma": gamma, "nmax": cell["nmax"], "L": cell["L"], "d": cell["d"],
                    "encoding": cell.get("encoding"),
                    "basis_family": cell.get("basis_family"),
                    "symmetry": cell.get("symmetry"),
                    "precision_profile": cell.get("precision_profile"),
                    "requested_memory_gb": cell.get("requested_memory_gb"),
                    "classification": classification(record.get("classification")),
                    "raw_status": record.get("raw_status"),
                    "solver": record.get("solver"),
                    "runtime_seconds": record.get("runtime_seconds"),
                    "primal_residual": record.get("primal_residual"),
                    "dual_residual": record.get("dual_residual"),
                    "min_psd_eigenvalue": record.get("min_psd_eigenvalue"),
                    "certificate_class": record.get("certificate_class", "NO_CERTIFICATE"),
                    "certificate_precision_bits": certificate_report.get("precision_bits"),
                    "certificate_affine_residual": certificate_report.get("max_affine_residual"),
                    "certificate_psd_verified": certificate_report.get("psd_verified"),
                    "certificate_farkas_margin_lower": certificate_report.get("farkas_margin_lower"),
                    "message": record.get("message", "trial not completed"),
                    "cell_status": (payload or {}).get("status", "MISSING"),
                }
            )
    return rows


def level_size_rows(
    sources: Iterable[tuple[Path, Path]],
) -> list[dict[str, object]]:
    """Collect one auditable size row per assembled hierarchy template."""
    keys = ("geometry", "nmax", "L", "d", "encoding", "basis_family", "symmetry")
    indexed: dict[tuple[object, ...], dict[str, object]] = {}
    for manifest_path, results_dir in sources:
        manifest = json.loads(manifest_path.read_text())
        cells = manifest.get("cells",manifest.get("levels",[]))
        for cell in cells:
            payload = load_json(results_dir / f"{cell['id']}.json")
            level = (payload or {}).get("level")
            if not isinstance(level, dict):
                continue
            key = tuple(cell.get(name) for name in keys)
            runner = (payload or {}).get("runner") or {}
            row = indexed.setdefault(
                key,
                {
                    **dict(zip(keys, key)),
                    "window_sites": level.get("window_sites"),
                    "interior_sites": level.get("interior_sites"),
                    "induced_edges": level.get("induced_edges"),
                    "moment_basis_count": level.get("moment_basis_count"),
                    "moment_block_sizes": level.get("moment_block_sizes"),
                    "gap_basis_count": level.get("gap_basis_count"),
                    "gap_block_sizes": level.get("gap_block_sizes"),
                    "equality_count": level.get("equality_count"),
                    "real_scalar_variable_count": level.get("real_scalar_variable_count"),
                    "affine_term_count": level.get("affine_term_count"),
                    "estimated_memory_gb": level.get("estimated_memory_gb"),
                    "requested_memory_gb": cell.get("requested_memory_gb"),
                    "max_rss_gb": None,
                    "assembled_cell_count": 0,
                },
            )
            row["assembled_cell_count"] = int(row["assembled_cell_count"]) + 1
            rss = runner.get("max_rss_gb")
            if rss is not None:
                row["max_rss_gb"] = max(float(row["max_rss_gb"] or 0.0), float(rss))
            allocated_memory = runner.get("allocated_memory_gb")
            if allocated_memory is not None:
                row["requested_memory_gb"] = max(
                    float(row["requested_memory_gb"] or 0.0), float(allocated_memory)
                )
    return sorted(
        indexed.values(),
        key=lambda row: (str(row["geometry"]), int(row["nmax"]), int(row["L"]), int(row["d"])),
    )


def block_text(value: object) -> str:
    return " / ".join(str(item) for item in value) if isinstance(value, list) else "—"


def gap_bracket_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Summarize certified upper endpoints without stepping across UNKNOWNs.

    ``search_span`` is only the distance from the last checked FEASIBLE sample
    to the first verified EXCLUDED sample. It is not called a bracket when
    unresolved samples lie between those two values.
    """
    keys = ("geometry", "point", "t", "mu", "nmax", "L", "d")
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(tuple(row[key] for key in keys), []).append(row)
    summaries: list[dict[str, object]] = []
    for key, group in grouped.items():
        excluded = sorted(
            (row for row in group if row["classification"] == "EXCLUDED"),
            key=lambda row: float(row["gamma"]),
        )
        if not excluded:
            continue
        endpoint = excluded[0]
        upper = float(endpoint["gamma"])
        feasible_below = [
            float(row["gamma"]) for row in group
            if row["classification"] == "FEASIBLE" and float(row["gamma"]) < upper
        ]
        last_not_excluded = max(feasible_below) if feasible_below else None
        unresolved_between: set[float] = set()
        if last_not_excluded is not None:
            decisive = {
                float(row["gamma"])
                for row in group
                if row["classification"] in ("FEASIBLE", "EXCLUDED")
            }
            unresolved_between = {
                float(row["gamma"])
                for row in group
                if last_not_excluded < float(row["gamma"]) < upper
                and float(row["gamma"]) not in decisive
            }
        summaries.append(
            {
                **dict(zip(keys, key)),
                "last_not_excluded": last_not_excluded,
                "upper_endpoint": upper,
                "search_span": upper-last_not_excluded if last_not_excluded is not None else None,
                # Compatibility alias retained for existing report consumers.
                "sample_width": upper-last_not_excluded if last_not_excluded is not None else None,
                "unknown_between": len(unresolved_between),
                "certificate_class": endpoint["certificate_class"],
                "certificate_precision_bits": endpoint.get("certificate_precision_bits"),
                "certificate_affine_residual": endpoint.get("certificate_affine_residual"),
                "certificate_psd_verified": endpoint.get("certificate_psd_verified"),
                "certificate_farkas_margin_lower": endpoint.get("certificate_farkas_margin_lower"),
                "message": endpoint["message"],
            }
        )
    return sorted(
        summaries,
        key=lambda row: (
            str(row["geometry"]), str(row["point"]), int(row["nmax"]),
            int(row["L"]), int(row["d"]),
        ),
    )


def gap_comparison_rows(
    summaries: list[dict[str, object]],
) -> list[dict[str, str]]:
    """Build auditable comparisons without ordering the unknown physical gaps."""
    rows: list[dict[str, str]] = []

    def evidence(group: list[dict[str, object]], label: str) -> str:
        return "; ".join(
            f"{item[label]}: Gamma/U<={compact_number(item['upper_endpoint'])} "
            f"(span {compact_number(item['search_span'])}, unresolved {item['unknown_between']})"
            for item in group
        )

    by_geometry: dict[tuple[object, ...], list[dict[str, object]]] = {}
    by_parameter: dict[tuple[object, ...], list[dict[str, object]]] = {}
    by_cutoff: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for item in summaries:
        by_geometry.setdefault(
            (item["point"], item["nmax"], item["L"], item["d"]), []
        ).append(item)
        by_parameter.setdefault(
            (item["geometry"], item["nmax"], item["L"], item["d"]), []
        ).append(item)
        by_cutoff.setdefault(
            (item["geometry"], item["point"], item["L"], item["d"]), []
        ).append(item)
    for (point, nmax, L, d), group in sorted(by_geometry.items(), key=str):
        if len({str(item["geometry"]) for item in group}) < 2:
            continue
        ordered = sorted(group, key=lambda item: str(item["geometry"]))
        rows.append(
            {
                "dimension": "geometry",
                "fixed_scope": f"{point}, nmax={nmax}, (L,d)=({L},{d})",
                "evidence": evidence(ordered, "geometry"),
                "claim_boundary": "compares hierarchy upper statements, not the true-gap ordering",
            }
        )
    for (geometry, nmax, L, d), group in sorted(by_parameter.items(), key=str):
        if len({str(item["point"]) for item in group}) < 2:
            continue
        ordered = sorted(group, key=lambda item: str(item["point"]))
        rows.append(
            {
                "dimension": "parameter point",
                "fixed_scope": f"{geometry}, nmax={nmax}, (L,d)=({L},{d})",
                "evidence": evidence(ordered, "point"),
                "claim_boundary": "finite-level upper statements can have unequal looseness",
            }
        )
    for (geometry, point, L, d), group in sorted(by_cutoff.items(), key=str):
        if len({int(item["nmax"]) for item in group}) < 2:
            continue
        ordered = sorted(group, key=lambda item: int(item["nmax"]))
        rows.append(
            {
                "dimension": "cutoff",
                "fixed_scope": f"{geometry}, {point}, (L,d)=({L},{d})",
                "evidence": evidence(ordered, "nmax"),
                "claim_boundary": "different truncated local Hilbert spaces define different Hamiltonians",
            }
        )
    return rows


def make_gap_status_plot(rows: list[dict[str, object]], output: Path) -> str | None:
    # A fallback attempt at the same gamma should replace an earlier UNKNOWN
    # marker once it yields checked FEASIBLE or verified EXCLUDED evidence.
    rank = {"UNKNOWN": 0, "FEASIBLE": 1, "EXCLUDED": 2}
    display: dict[tuple[str, str, int, int, int, float], dict[str, object]] = {}
    for row in rows:
        if row.get("raw_status") is None:
            continue
        key = (
            str(row["geometry"]), str(row["point"]), int(row["nmax"]),
            int(row["L"]), int(row["d"]), float(row["gamma"]),
        )
        current = display.get(key)
        if current is None or rank[str(row["classification"])] > rank[str(current["classification"])]:
            display[key] = row
    completed = list(display.values())
    if not completed:
        return None
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/issue92-matplotlib")
    Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    group_keys = sorted(
        {
            (str(row["geometry"]), str(row["point"]), int(row["nmax"]), int(row["L"]), int(row["d"]))
            for row in completed
        }
    )
    positions = {key: index for index, key in enumerate(group_keys)}
    styles = {
        "FEASIBLE": ("#16746f", "o"),
        "EXCLUDED": ("#aa3f3f", "X"),
        "UNKNOWN": ("#8a8f96", "s"),
    }
    fig, axis = plt.subplots(figsize=(9.4, max(2.7, 1.0 + .75*len(group_keys))), constrained_layout=True)
    for row in completed:
        key = (
            str(row["geometry"]), str(row["point"]), int(row["nmax"]),
            int(row["L"]), int(row["d"]),
        )
        color, marker = styles[str(row["classification"])]
        axis.scatter(float(row["gamma"]), positions[key], color=color, marker=marker, s=72, zorder=3)
    axis.set_yticks(
        range(len(group_keys)),
        [f"{geometry} {point} n{nmax} L{L}d{d}" for geometry, point, nmax, L, d in group_keys],
    )
    axis.set_xlabel("assumed gap γ/U")
    axis.set_title("Fixed-γ hierarchy classifications")
    axis.grid(axis="x", alpha=.25)
    handles = [
        Line2D([], [], marker=marker, linestyle="none", color=color, markersize=8, label=label)
        for label, (color, marker) in styles.items()
    ]
    axis.legend(handles=handles, frameon=False, ncol=3, loc="upper left")
    path = output / "fixed_gamma_status.png"
    temporary = path.with_name(path.stem + ".tmp" + path.suffix)
    fig.savefig(temporary, dpi=190, bbox_inches="tight")
    plt.close(fig)
    os.replace(temporary, path)
    return path.name


def nested_checks(intervals: list[dict[str, object]], tolerance: float = 1e-6) -> list[dict[str, object]]:
    indexed = {
        (item["geometry"], item["point"], float(item["gamma"]), int(item["L"]), int(item["d"]), item["observable"]): item
        for item in intervals
    }
    checks: list[dict[str, object]] = []
    for direction, target in (("d", (1, 3)), ("L", (2, 2))):
        for observable in OBSERVABLES:
            baseline = indexed.get(("83", "P2", 0.0, 1, 2, observable), {})
            tighter = indexed.get(("83", "P2", 0.0, target[0], target[1], observable), {})
            available = bool(baseline.get("accepted") and tighter.get("accepted"))
            lower_delta = float(tighter["lower"])-float(baseline["lower"]) if available else None
            upper_delta = float(tighter["upper"])-float(baseline["upper"]) if available else None
            passed = available and lower_delta >= -tolerance and upper_delta <= tolerance
            checks.append(
                {
                    "direction": direction, "baseline_L": 1, "baseline_d": 2,
                    "target_L": target[0], "target_d": target[1], "observable": observable,
                    "lower_delta": lower_delta, "upper_delta": upper_delta,
                    "status": "PASS" if passed else "FAIL" if available else "UNKNOWN",
                }
            )
    return checks


def evidence_tier(row: dict[str, object]) -> str:
    """Presentation tier without weakening the three scientific classifications."""
    if row.get("classification") == "FEASIBLE" and row.get("optimum") is not None:
        return "ACCEPTED"
    if row.get("classification") == "EXCLUDED":
        return "VERIFIED_EXCLUSION"
    if row.get("optimum") is not None:
        return "FLOATING"
    if row.get("raw_status") == "ERROR":
        return "ERROR"
    if row.get("cell_status") == "RUNNING":
        return "UNFINISHED"
    if row.get("cell_status") == "MISSING":
        return "NOT_STARTED"
    return "UNKNOWN"


def working_interval_rows(records: list[dict[str, object]]) -> list[dict[str, object]]:
    """Keep numerical endpoints even when one or both failed acceptance checks."""
    grouped: dict[tuple[object, ...], dict[str, dict[str, object]]] = {}
    keys = ("geometry", "point", "t", "mu", "gamma", "nmax", "L", "d", "observable")
    for row in records:
        key = tuple(row[field] for field in keys)
        grouped.setdefault(key, {})[str(row["sense"])] = row
    result: list[dict[str, object]] = []
    for key, senses in grouped.items():
        lower = senses.get("min", {})
        upper = senses.get("max", {})
        lower_value = lower.get("optimum")
        upper_value = upper.get("optimum")
        if lower_value is None and upper_value is None:
            continue
        source = lower or upper
        result.append(
            {
                **dict(zip(keys, key)),
                "id": source.get("id", ""),
                "lower": lower_value,
                "upper": upper_value,
                "lower_tier": evidence_tier(lower),
                "upper_tier": evidence_tier(upper),
                "lower_raw_status": lower.get("raw_status"),
                "upper_raw_status": upper.get("raw_status"),
                "complete_numeric": lower_value is not None and upper_value is not None,
            }
        )
    return result


def compact_number(value: object, digits: int = 7) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}g}"


def residual_text(value: object) -> str:
    if value is None:
        return "—"
    return f"{float(value):.2e}"


def exact_observable_evidence(row: dict[str, object]) -> str:
    bits = row.get("certificate_precision_bits")
    if bits is None:
        return "—"
    return (
        f"{bits}-bit; affine {compact_number(row.get('certificate_affine_residual'))}; "
        f"PSD {row.get('certificate_psd_verified')}; "
        f"objective gap {compact_number(row.get('certificate_objective_gap'))}"
    )


def endpoint_text(value: object, tier: str) -> str:
    if value is None:
        return "—"
    marker = {"ACCEPTED": "A", "FLOATING": "F"}.get(tier, "?")
    return f"{compact_number(value)} {marker}"


def cell_status_counts(records: list[dict[str, object]]) -> Counter:
    unique: dict[str, str] = {}
    for row in records:
        unique[str(row["id"])] = str(row["cell_status"])
    return Counter(unique.values())


def make_working_plot(records: list[dict[str, object]], output: Path) -> str | None:
    selected = [
        row for row in records
        if row["geometry"] == "83" and row["point"] == "P2"
        and int(row["L"]) == 1 and int(row["d"]) == 2
        and row.get("optimum") is not None
    ]
    if not selected:
        return None
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/issue92-matplotlib")
    Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    colors = {"min": "#156f69", "max": "#d36b2c"}
    markers = {"min": "^", "max": "v"}
    fig, axes = plt.subplots(1, 3, figsize=(12.2, 3.8), constrained_layout=True)
    for axis, observable in zip(axes, OBSERVABLES):
        for sense in SENSES:
            series = sorted(
                (row for row in selected if row["observable"] == observable and row["sense"] == sense),
                key=lambda row: float(row["gamma"]),
            )
            if not series:
                continue
            x = [float(row["gamma"]) for row in series]
            y = [float(row["optimum"]) for row in series]
            axis.plot(x, y, color=colors[sense], alpha=.45, linewidth=1.4)
            for tier, face in (("ACCEPTED", colors[sense]), ("FLOATING", "white")):
                tier_rows = [row for row in series if evidence_tier(row) == tier]
                if not tier_rows:
                    continue
                axis.scatter(
                    [float(row["gamma"]) for row in tier_rows],
                    [float(row["optimum"]) for row in tier_rows],
                    marker=markers[sense], s=54, facecolors=face,
                    edgecolors=colors[sense], linewidths=1.5,
                    label=f"{sense}: {tier.lower()}", zorder=3,
                )
        axis.set_title({"rho0": r"$\rho_0$", "F0": r"$F_0$", "K0": r"$K_0$"}[observable])
        axis.set_xlabel("assumed gap γ/U")
        axis.grid(alpha=.22)
    axes[0].set_ylabel("SDP objective value")
    handles = [
        Line2D([], [], marker=markers[sense], linestyle="none", markersize=7,
               markerfacecolor=face, markeredgecolor=colors[sense], markeredgewidth=1.5,
               label=f"{sense}: {tier.lower()}")
        for sense in SENSES
        for tier, face in (("ACCEPTED", colors[sense]), ("FLOATING", "white"))
    ]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(.5, 1.10), ncol=4, frameon=False)
    path = output / "working_endpoints_83_p2.png"
    temporary = path.with_name(path.stem + ".tmp" + path.suffix)
    fig.savefig(temporary, dpi=190, bbox_inches="tight")
    plt.close(fig)
    os.replace(temporary, path)
    return path.name


def make_plots(intervals: list[dict[str, object]], output: Path) -> list[str]:
    accepted = [item for item in intervals if item["accepted"]]
    if not accepted:
        return []
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/issue92-matplotlib")
    Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    import matplotlib.pyplot as plt

    produced: list[str] = []
    geometry_rows = [item for item in accepted if item["point"]=="P2" and item["L"]==1 and item["d"]==2]
    if geometry_rows:
        fig, axes = plt.subplots(1,3,figsize=(12,3.6),constrained_layout=True)
        for axis, observable in zip(axes,OBSERVABLES):
            for geometry in ("83","124","line83"):
                selected = sorted(
                    (item for item in geometry_rows if item["observable"]==observable and item["geometry"]==geometry),
                    key=lambda item: float(item["gamma"]),
                )
                if not selected:
                    continue
                x = [float(item["gamma"]) for item in selected]
                mid = [(float(item["lower"])+float(item["upper"]))/2 for item in selected]
                err = [(float(item["upper"])-float(item["lower"]))/2 for item in selected]
                axis.errorbar(x,mid,yerr=err,marker="o",capsize=3,label=geometry)
            axis.set_title(observable); axis.set_xlabel("assumed gap gamma/U"); axis.grid(alpha=0.25)
        axes[0].set_ylabel("outer interval"); axes[-1].legend(frameon=False)
        path = output/"geometry_gamma_intervals.png"
        temporary = path.with_name(path.stem+".tmp"+path.suffix)
        fig.savefig(temporary,dpi=180); plt.close(fig); os.replace(temporary,path)
        produced.append(path.name)
    nested_rows = [item for item in accepted if item["geometry"]=="83" and item["point"]=="P2" and float(item["gamma"])==0]
    if nested_rows:
        levels = ((1,2),(1,3),(2,2))
        fig, axes = plt.subplots(1,3,figsize=(12,3.6),constrained_layout=True)
        for axis, observable in zip(axes,OBSERVABLES):
            selected = {(int(item["L"]),int(item["d"])):item for item in nested_rows if item["observable"]==observable}
            for index, level in enumerate(levels):
                item = selected.get(level)
                if item is None: continue
                lower,upper = float(item["lower"]),float(item["upper"])
                axis.errorbar(index,(lower+upper)/2,yerr=(upper-lower)/2,marker="o",capsize=4)
            axis.set_xticks(range(3),["(1,2)","(1,3)","(2,2)"])
            axis.set_title(observable); axis.set_xlabel("(L,d)"); axis.grid(alpha=0.25)
        axes[0].set_ylabel("outer interval")
        path = output/"nested_intervals.png"
        temporary = path.with_name(path.stem+".tmp"+path.suffix)
        fig.savefig(temporary,dpi=180); plt.close(fig); os.replace(temporary,path)
        produced.append(path.name)
    return produced


def markdown_summary(observable_records, intervals, gap_trials, checks, plots) -> str:
    observable_counts = Counter(item["classification"] for item in observable_records)
    gap_counts = Counter(item["classification"] for item in gap_trials)
    accepted = [item for item in intervals if item["accepted"]]
    lines = [
        "# Issue 92 short-deadline results", "",
        f"Generated {datetime.now().astimezone().isoformat(timespec='seconds')}.", "",
        "All lattice rows are low-precision Clarabel diagnostics unless an exact certificate class explicitly says otherwise.", "",
        "## Completion", "", "| evidence | FEASIBLE | EXCLUDED | UNKNOWN |", "|---|---:|---:|---:|",
        f"| observable objectives | {observable_counts['FEASIBLE']} | {observable_counts['EXCLUDED']} | {observable_counts['UNKNOWN']} |",
        f"| fixed-gamma feasibility trials | {gap_counts['FEASIBLE']} | {gap_counts['EXCLUDED']} | {gap_counts['UNKNOWN']} |", "",
        f"Accepted two-sided observable intervals: **{len(accepted)} / {len(intervals)}**.", "",
        "## Accepted intervals", "", "| graph | point | gamma/U | (L,d) | observable | interval |", "|---|---|---:|---|---|---:|",
    ]
    for item in accepted:
        lines.append(
            f"| {item['geometry']} | {item['point']} | {float(item['gamma']):.3f} | ({item['L']},{item['d']}) | "
            f"{item['observable']} | [{float(item['lower']):.7g}, {float(item['upper']):.7g}] |"
        )
    if not accepted: lines.append("| — | — | — | — | — | no complete accepted interval yet |")
    lines.extend(["", "## Nestedness checks", "", "| tightening | observable | lower change | upper change | status |", "|---|---|---:|---:|---|"])
    for item in checks:
        lower = "—" if item["lower_delta"] is None else f"{float(item['lower_delta']):.3e}"
        upper = "—" if item["upper_delta"] is None else f"{float(item['upper_delta']):.3e}"
        lines.append(f"| {item['direction']} to ({item['target_L']},{item['target_d']}) | {item['observable']} | {lower} | {upper} | {item['status']} |")
    if plots:
        lines.extend(["", "## Figures", "", *(f"- `{name}`" for name in plots)])
    lines.extend(["", "A floating infeasibility is never promoted to `EXCLUDED`; failed residual checks and unfinished jobs remain `UNKNOWN`.", ""])
    return "\n".join(lines)


def current_progress_markdown(
    observable_records: list[dict[str, object]],
    intervals: list[dict[str, object]],
    gap_trials: list[dict[str, object]],
    working: list[dict[str, object]],
    levels: list[dict[str, object]],
    working_plot: str | None,
    gap_plot: str | None,
    generated: str,
) -> str:
    tiers = Counter(evidence_tier(row) for row in observable_records)
    cell_counts = cell_status_counts(observable_records)
    accepted = sorted(
        (row for row in observable_records if evidence_tier(row) == "ACCEPTED"),
        key=lambda row: (str(row["geometry"]), str(row["point"]), float(row["gamma"]), str(row["observable"]), str(row["sense"])),
    )
    floating = sorted(
        (row for row in observable_records if evidence_tier(row) == "FLOATING"),
        key=lambda row: (str(row["geometry"]), str(row["point"]), float(row["gamma"]), str(row["observable"]), str(row["sense"])),
    )
    errors: dict[str, dict[str, object]] = {}
    for row in observable_records:
        if evidence_tier(row) == "ERROR":
            errors.setdefault(str(row["id"]), row)
    errors.setdefault("cutoff2-resource-gate", CUTOFF2_RESOURCE_ROW)
    errors.setdefault("cutoff2-ts2-dry-sigbus", TS2_DRY_RESOURCE_ROW)
    accepted_intervals = sum(bool(row["accepted"]) for row in intervals)
    gap_counts = Counter(str(row["classification"]) for row in gap_trials)
    gap_completed = sum(row.get("raw_status") is not None for row in gap_trials)
    gap_brackets = gap_bracket_rows(gap_trials)
    gap_comparisons = gap_comparison_rows(gap_brackets)
    lines = [
        "# Issue 92 — current SCNet calculation report", "",
        f"**Snapshot generated:** {generated}  ",
        "**Campaign:** Target 2 short-deadline diagnostic run, primary matrix encoding, complete hard-core hierarchy  ",
        "**Scientific scope:** thermodynamic hierarchy with `U1_INVARIANT_KMS_STATES`; finite-cluster ED is not used as a bound.", "",
        "Parameter points: `P1=(0.03,0.50)`, `P2=(0.05,0.50)`, `P3=(0.06,0.50)`, "
        "`P4=(0.03,0.15)`, and `P5=(0.03,0.75)`, written as `(t/U,μ/U)`. "
        "Here `rho0` is the root density, `F0 = ⟨(n0-1)²⟩`, and "
        "`K0 = z⁻¹ Σj~0 ⟨b0†bj + bj†b0⟩` is the mean incident hopping correlator. "
        "Graph codes are `83 = {8,3}`, `124 = {12,4}`, and `line83 = L({8,3})`.", "",
        "> This report deliberately shows calculations on the way. `A` endpoints passed the independent checks. "
        "`F` endpoints are floating Clarabel optima that did not pass the strict residual/PSD acceptance threshold. "
        "They are useful numerical evidence but are not claimed as certified bounds.", "",
        "## Executive snapshot", "",
        "| item | count |", "|---|---:|",
        f"| accepted one-sided observable objectives | {tiers['ACCEPTED']} |",
        f"| floating numerical objectives | {tiers['FLOATING']} |",
        f"| solver/resource errors | {tiers['ERROR']} |",
        f"| accepted two-sided intervals | {accepted_intervals} / {len(intervals)} |",
        f"| fixed-γ trials with a durable solver record | {gap_completed} / {len(gap_trials)} |",
        f"| result cells marked COMPLETE | {cell_counts['COMPLETE']} |",
        f"| result cells with a RUNNING checkpoint | {cell_counts['RUNNING']} |",
        f"| observable cells without a durable checkpoint | {cell_counts['MISSING']} |", "",
        "The presentation deadline is 20:00 CST. SCNet observable array `41510919`, expedited "
        "coarse scans `41519302`/`41523224`, refinement `41523716`, transition micro-scan "
        "`41534382`, dependency-safe geometry refinements `41534386`/`41534390` plus recoveries `41541949`/`41542751`, and remaining "
        "Target-2 arrays `41534717`/`41534723`, transition refinements "
        "`41539201`/`41539896`/`41540154`, "
        "MKL exact-observable representative `41536972`, "
        "and corrected-tier cutoff-2 attempts `41535172`/`41540049`/`41540879`/`41541639` feed this "
        "resumable snapshot.", "",
        "## Certified thermodynamic upper statements", "",
    ]
    for row in gap_brackets:
        cutoff_label = "hard-core (`nmax=1`)" if int(row["nmax"]) == 1 else f"cutoff `nmax={row['nmax']}`"
        lines.append(
            f"- `{row['geometry']}` {row['point']}, {cutoff_label} complete matrix level "
            f"`(L,d)=({row['L']},{row['d']})`: **Γ/U ≤ {compact_number(row['upper_endpoint'])}** "
            f"within `U1_INVARIANT_KMS_STATES` (`{row['certificate_class']}`). "
            f"Exact affine residual {compact_number(row['certificate_affine_residual'])}, "
            f"Farkas margin ≥ {compact_number(row['certificate_farkas_margin_lower'])}, "
            f"{row['certificate_precision_bits']}-bit interval checks. Search span "
            f"{compact_number(row['search_span'])} with {row['unknown_between']} unresolved interior samples."
        )
    if not gap_brackets:
        lines.append("- No verified non-atomic upper statement at this snapshot.")
    lines.extend([
        "", "These are thermodynamic hierarchy exclusions, not finite-cluster ED values. "
        "The FEASIBLE-side samples are non-exclusion evidence only.", "",
        "## How to read the evidence", "",
        "- **Accepted (`A`)**: the solver optimum passed the independent primal/dual residual, PSD, and objective-gap checks.",
        "- **Floating (`F`)**: the solver returned a numerical optimum, but at least one independent threshold failed.",
        "- **Unknown**: no accepted conclusion. This includes floating values, unfinished jobs, numerical errors, and resource failures.",
        "- **Excluded**: an infeasibility certificate passed exact projection, Arb interval signs, PSD LDL, and a positive Farkas-margin check.", "",
        "## Accepted one-sided results", "",
        "| graph | point | γ/U | (L,d) | accepted statement | certificate class | dual residual | min PSD eigenvalue | exact evidence |",
        "|---|---|---:|---|---|---|---:|---:|---|",
    ])
    for row in accepted:
        relation = "≥" if row["sense"] == "min" else "≤"
        lines.append(
            f"| {row['geometry']} | {row['point']} | {float(row['gamma']):.3f} | ({row['L']},{row['d']}) | "
            f"{row['observable']} {relation} {compact_number(row['optimum'])} | {row['certificate_class']} | "
            f"{residual_text(row['dual_residual'])} | {residual_text(row['min_psd_eigenvalue'])} | "
            f"{exact_observable_evidence(row)} |"
        )
    if not accepted:
        lines.append("| — | — | — | — | no accepted endpoint yet | — | — | — | — |")
    lines.extend([
        "", "For `nmax=1`, the accepted `F0` upper endpoints are exact affine consequences of "
        "the opposite `rho0` lower endpoint through `F0 = 1 - rho0`; this identity does not add a separate SDP solve.", "",
        "## Working numerical intervals", "",
        "These intervals retain every numerical endpoint. A missing side means that objective has not reached a durable checkpoint.", "",
        "| graph | point | γ/U | (L,d) | observable | lower endpoint | upper endpoint | interpretation |",
        "|---|---|---:|---|---|---:|---:|---|",
    ])
    for row in sorted(working, key=lambda item: (str(item["geometry"]), str(item["point"]), float(item["gamma"]), str(item["observable"]))):
        qualities = {row["lower_tier"], row["upper_tier"]}
        if qualities == {"ACCEPTED"}:
            interpretation = "accepted interval"
        elif "ACCEPTED" in qualities and "FLOATING" in qualities:
            interpretation = "one accepted, one floating"
        elif row["complete_numeric"]:
            interpretation = "floating interval"
        else:
            interpretation = "partial checkpoint"
        lines.append(
            f"| {row['geometry']} | {row['point']} | {float(row['gamma']):.3f} | ({row['L']},{row['d']}) | "
            f"{row['observable']} | {endpoint_text(row['lower'], str(row['lower_tier']))} | "
            f"{endpoint_text(row['upper'], str(row['upper_tier']))} | {interpretation} |"
        )
    if not working:
        lines.append("| — | — | — | — | — | — | — | no numerical endpoint yet |")
    lines.extend([
        "", "## Floating endpoint diagnostics", "",
        "| graph | point | γ/U | objective | value | primal residual | dual residual | min PSD eigenvalue | reason kept floating |",
        "|---|---|---:|---|---:|---:|---:|---:|---|",
    ])
    for row in floating:
        message = str(row["message"]).replace("|", "/")
        lines.append(
            f"| {row['geometry']} | {row['point']} | {float(row['gamma']):.3f} | {row['observable']} {row['sense']} | "
            f"{compact_number(row['optimum'])} | {residual_text(row['primal_residual'])} | "
            f"{residual_text(row['dual_residual'])} | {residual_text(row['min_psd_eigenvalue'])} | {message} |"
        )
    if not floating:
        lines.append("| — | — | — | — | — | — | — | — | no floating endpoint |")
    lines.extend([
        "", "## Larger-level resource outcomes", "",
        "| graph | point | (L,d) | requested memory | classification | recorded reason |",
        "|---|---|---|---:|---|---|",
    ])
    for row in sorted(errors.values(), key=lambda item: (int(item["L"]), int(item["d"]))):
        lines.append(
            f"| {row['geometry']} | {row['point']} | ({row['L']},{row['d']}) | "
            f"{row.get('requested_memory_gb') or '—'} GiB | UNKNOWN | {str(row['message']).replace('|', '/')} |"
        )
    if not errors:
        lines.append("| — | — | — | — | — | no recorded resource error |")
    lines.extend([
        "", "Both nested `{8,3}` cells, `(L,d)=(1,3)` and `(2,2)`, built their cached workspaces but then "
        "raised Julia `OutOfMemoryError`. Their shell jobs completed because the runner recorded explicit `UNKNOWN` rows; "
        "they did not produce bounds. The complete cutoff-2 baseline is also explicit: its 192-GiB "
        "attempt was killed by Slurm's memory cgroup after assembly.  The 237-GiB retry also "
        "exhausted memory inside Julia and safely checkpointed all four probes as `UNKNOWN`; "
        "its shell completion is not a bound.  Eight-thread recovery `41540879` also exhausted "
        "memory at 233,357,596 KiB MaxRSS.  QDLDL reduced the peak to 214,327,588 KiB but "
        "also exhausted memory, making this an explicit structural resource gate.  TS2 "
        "`(1,3)` task `41541783_28` died with `SIGBUS` at only 1.8 GiB RSS, a node/runtime "
        "failure rather than an OOM.  Pre-optimization `(2,2)` task 31 was canceled after "
        "50 minutes without a checkpoint; optimized different-node `(1,3)` retry `41542822` "
        "is running and resumable optimized `(2,2)` guard `41544379` is queued.", "",
        "The queued retry uses an assembly-only optimization to the deterministic chordal "
        "completion: active degrees are maintained incrementally instead of rescanned "
        "cubically.  Nineteen direct reference comparisons preserve the exact clique "
        "sequence, and a 220-vertex kernel benchmark was 20.6 times faster.  This changes "
        "runtime only, not the formal `TS2` support-closure level.  Its read-only pair "
        "support pass is also threaded and merged lexicographically; `(1,3)` and `(2,2)` "
        "contain 11.60 million and 3.11 million charge-compatible pairs per pass.", "",
        "## Assembled level sizes", "",
        "| graph | nmax | (L,d) | window/interior/edges | moment basis | moment charge blocks | gap basis | gap charge blocks | equalities | real variables | affine terms | max RSS GiB |",
        "|---|---:|---|---|---:|---|---:|---|---:|---:|---:|---:|",
    ])
    for row in levels:
        lines.append(
            f"| {row['geometry']} | {row['nmax']} | ({row['L']},{row['d']}) | "
            f"{row['window_sites']}/{row['interior_sites']}/{row['induced_edges']} | "
            f"{row['moment_basis_count']} | {block_text(row['moment_block_sizes'])} | "
            f"{row['gap_basis_count']} | {block_text(row['gap_block_sizes'])} | "
            f"{row['equality_count']} | {row['real_scalar_variable_count']} | "
            f"{row['affine_term_count']} | {compact_number(row['max_rss_gb'])} |"
        )
    if not levels:
        lines.append("| — | — | — | — | — | — | — | — | — | — | — | — |")
    lines.extend([
        "", "Block sizes are exact `U(1)` charge blocks. Max RSS is the largest recorded cell-level runner RSS for that assembled template.", "",
        "## Gap calculation status", "",
        f"The aggregated fixed-γ evidence contains {len(gap_trials)} trial-attempt rows: {gap_counts['FEASIBLE']} `FEASIBLE`, "
        f"{gap_counts['EXCLUDED']} `EXCLUDED`, and {gap_counts['UNKNOWN']} `UNKNOWN` at this snapshot. "
        "An upper endpoint is reported only when an exclusion passes the independent certificate checker.", "",
        "| graph | point | nmax | (L,d) | last sampled FEASIBLE | first verified EXCLUDED | search span | unresolved inside | exact affine residual | Farkas margin lower | bits | PSD | implication |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ])
    for row in gap_brackets:
        lines.append(
            f"| {row['geometry']} | {row['point']} | {row['nmax']} | ({row['L']},{row['d']}) | {compact_number(row['last_not_excluded'])} | "
            f"{compact_number(row['upper_endpoint'])} | {compact_number(row['search_span'])} | "
            f"{row['unknown_between']} | {compact_number(row['certificate_affine_residual'])} | "
            f"{compact_number(row['certificate_farkas_margin_lower'])} | {row['certificate_precision_bits']} | "
            f"{row['certificate_psd_verified']} | assumed gap ≥ {compact_number(row['upper_endpoint'])} is excluded |"
        )
    if not gap_brackets:
        lines.append("| — | — | — | — | — | — | — | — | — | — | — | — | no verified lattice exclusion yet |")
    completed_gap = sorted(
        (row for row in gap_trials if row.get("raw_status") is not None),
        key=lambda row: (str(row["geometry"]), str(row["point"]), int(row["nmax"]), float(row["gamma"])),
    )
    lines.extend([
        "", "`FEASIBLE` means only *not excluded at this finite hierarchy level*; it is not a physical gap lower bound. "
        "Every `EXCLUDED` row shown here has an independently verified exact-projected Farkas certificate. "
        "A search span with unresolved samples is not a numerical bracket; solver errors and unfinished points do not move either endpoint.", "",
        "The stored `{12,4}` P2 `gamma/U=0.520` proof was replayed through the optimized rigorous PSD path: "
        "all eight blocks (largest `222x222`) passed in 3.125 seconds, versus 1,943 seconds in the "
        "already-running legacy fallback.  Exact affine residual zero and Farkas margin one are unchanged.", "",
        "| graph | point | nmax | (L,d) | γ/U | classification | raw solver status | solver | certificate class |",
        "|---|---|---:|---|---:|---|---|---|---|",
    ])
    for row in completed_gap:
        lines.append(
            f"| {row['geometry']} | {row['point']} | {row['nmax']} | ({row['L']},{row['d']}) | {float(row['gamma']):.3f} | "
            f"{row['classification']} | {row['raw_status']} | {row.get('solver') or '—'} | "
            f"{row['certificate_class']} |"
        )
    if gap_plot:
        lines.extend(["", f"![Fixed-gamma status map]({gap_plot})", ""])
    lines.extend([
        "", "## Geometry, parameter, and cutoff comparisons", "",
        "Only matched finite-level certified upper statements are placed side by side. "
        "Their numerical order does not establish the order of the unknown true gaps.", "",
        "| dimension | fixed scope | certified evidence | claim boundary |",
        "|---|---|---|---|",
    ])
    for row in gap_comparisons:
        lines.append(
            f"| {row['dimension']} | {row['fixed_scope']} | {row['evidence']} | {row['claim_boundary']} |"
        )
    if not gap_comparisons:
        lines.append("| — | — | no matched certified comparison yet | no physical ordering inferred |")
    lines.extend([
        "", "The exact atomic `t=0` benchmark at Δ/U=0.5 remains a regression check, not a Target 2 lattice result.", "",
        "## Interpretation of the emerging trend", "",
        "For `{8,3}` at P2, increasing the *assumed* γ in the hierarchy from 0 to 0.10 raises the accepted "
        "lower endpoint for `rho0` and lowers the accepted upper endpoint for `F0`. This is tightening of the "
        "conditional feasible set as the imposed gap inequality becomes stronger; it must not be described as changing "
        "the physical Hamiltonian's gap.", "",
    ])
    if working_plot:
        lines.extend([f"![Working accepted and floating endpoints]({working_plot})", ""])
    lines.extend([
        "## Audit files", "",
        "- `observable_objectives.csv`: every requested min/max objective, including missing and failed rows.",
        "- `working_intervals.csv`: accepted/floating status of each numerical endpoint.",
        "- `gap_scan_trials.csv`: every coarse and refinement fixed-γ row; unrun rows remain explicit `UNKNOWN`.",
        "- `level_sizes.csv`: exact basis/block/equality sizes and recorded runner memory by assembled template.",
        "- Raw per-cell JSON preserves solver status, residuals, primal/dual data, runtime, and checkpoint status.", "",
        "This is a progress report, not the final Target 2 campaign table. Floating values may be presented as calculations "
        "in progress only when their failed acceptance status is shown next to the number.", "",
    ])
    return "\n".join(lines)


def html_table(headers: list[str], rows: list[list[object]]) -> str:
    head = "".join(f"<th>{html.escape(str(value))}</th>" for value in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in row) + "</tr>"
        for row in rows
    )
    return f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def current_progress_html(
    observable_records: list[dict[str, object]],
    intervals: list[dict[str, object]],
    gap_trials: list[dict[str, object]],
    working: list[dict[str, object]],
    levels: list[dict[str, object]],
    working_plot: str | None,
    gap_plot: str | None,
    generated: str,
) -> str:
    tiers = Counter(evidence_tier(row) for row in observable_records)
    cells = cell_status_counts(observable_records)
    accepted = sorted(
        (row for row in observable_records if evidence_tier(row) == "ACCEPTED"),
        key=lambda row: (str(row["geometry"]), float(row["gamma"]), str(row["observable"])),
    )
    floating = sorted(
        (row for row in observable_records if evidence_tier(row) == "FLOATING"),
        key=lambda row: (str(row["geometry"]), float(row["gamma"]), str(row["observable"]), str(row["sense"])),
    )
    errors: dict[str, dict[str, object]] = {}
    for row in observable_records:
        if evidence_tier(row) == "ERROR":
            errors.setdefault(str(row["id"]), row)
    errors.setdefault("cutoff2-resource-gate", CUTOFF2_RESOURCE_ROW)
    errors.setdefault("cutoff2-ts2-dry-sigbus", TS2_DRY_RESOURCE_ROW)
    accepted_rows = [
        [row["geometry"], row["point"], f"{float(row['gamma']):.3f}", f"({row['L']},{row['d']})",
         f"{row['observable']} {'≥' if row['sense']=='min' else '≤'} {compact_number(row['optimum'])}",
         row["certificate_class"], residual_text(row["dual_residual"]), residual_text(row["min_psd_eigenvalue"]),
         exact_observable_evidence(row)]
        for row in accepted
    ] or [["—", "—", "—", "—", "No accepted endpoint", "—", "—", "—", "—"]]
    working_rows = []
    for row in sorted(working, key=lambda item: (str(item["geometry"]), str(item["point"]), float(item["gamma"]), str(item["observable"]))):
        qualities = {row["lower_tier"], row["upper_tier"]}
        label = "accepted" if qualities == {"ACCEPTED"} else "mixed" if "ACCEPTED" in qualities and "FLOATING" in qualities else "floating" if row["complete_numeric"] else "partial"
        working_rows.append([
            row["geometry"], row["point"], f"{float(row['gamma']):.3f}", f"({row['L']},{row['d']})", row["observable"],
            endpoint_text(row["lower"], str(row["lower_tier"])), endpoint_text(row["upper"], str(row["upper_tier"])), label,
        ])
    floating_rows = [
        [row["geometry"], row["point"], f"{float(row['gamma']):.3f}", f"{row['observable']} {row['sense']}",
         compact_number(row["optimum"]), residual_text(row["primal_residual"]), residual_text(row["dual_residual"]),
         residual_text(row["min_psd_eigenvalue"])]
        for row in floating
    ] or [["—", "—", "—", "No floating endpoint", "—", "—", "—", "—"]]
    error_rows = [
        [row["geometry"], row["point"], f"({row['L']},{row['d']})", f"{row.get('requested_memory_gb') or '—'} GiB", "UNKNOWN", row["message"]]
        for row in sorted(errors.values(), key=lambda item: (int(item["L"]), int(item["d"])))
    ] or [["—", "—", "—", "—", "—", "No recorded resource error"]]
    gap_counts = Counter(str(row["classification"]) for row in gap_trials)
    gap_completed = sum(row.get("raw_status") is not None for row in gap_trials)
    gap_brackets = gap_bracket_rows(gap_trials)
    gap_comparisons = gap_comparison_rows(gap_brackets)
    gap_headline = "".join(
        "<li><strong>"
        f"{html.escape(str(row['geometry']))} {html.escape(str(row['point']))}: Γ/U ≤ "
        f"{html.escape(compact_number(row['upper_endpoint']))}</strong> at complete "
        f"{'hard-core' if int(row['nmax']) == 1 else 'cutoff-'+str(row['nmax'])} "
        f"(L,d)=({row['L']},{row['d']}), with exact-projected exclusion evidence. "
        f"Exact affine residual {html.escape(compact_number(row['certificate_affine_residual']))}, "
        f"Farkas margin ≥ {html.escape(compact_number(row['certificate_farkas_margin_lower']))}, "
        f"{row['certificate_precision_bits']}-bit interval checks. "
        f"Search span {html.escape(compact_number(row['search_span']))}; "
        f"{row['unknown_between']} unresolved interior samples.</li>"
        for row in gap_brackets
    ) or "<li>No verified non-atomic upper statement at this snapshot.</li>"
    bracket_rows = [
        [row["geometry"], row["point"], row["nmax"], f"({row['L']},{row['d']})", compact_number(row["last_not_excluded"]),
         compact_number(row["upper_endpoint"]), compact_number(row["search_span"]), row["unknown_between"],
         compact_number(row["certificate_affine_residual"]),
         compact_number(row["certificate_farkas_margin_lower"]),
         row["certificate_precision_bits"], row["certificate_psd_verified"],
         f"gap ≥ {compact_number(row['upper_endpoint'])} excluded"]
        for row in gap_brackets
    ] or [["—"] * 13]
    completed_gap_rows = [
        [row["geometry"], row["point"], row["nmax"], f"({row['L']},{row['d']})", f"{float(row['gamma']):.3f}", row["classification"],
         row["raw_status"], row.get("solver") or "—", row["certificate_class"]]
        for row in sorted(
            (item for item in gap_trials if item.get("raw_status") is not None),
            key=lambda item: (str(item["geometry"]), str(item["point"]), int(item["nmax"]), float(item["gamma"])),
        )
    ] or [["—", "—", "—", "—", "—", "—", "—", "—", "No completed fixed-γ trial"]]
    comparison_table_rows = [
        [row["dimension"], row["fixed_scope"], row["evidence"], row["claim_boundary"]]
        for row in gap_comparisons
    ] or [["—", "—", "No matched certified comparison yet", "No physical ordering inferred"]]
    level_table_rows = [
        [
            row["geometry"], row["nmax"], f"({row['L']},{row['d']})",
            f"{row['window_sites']}/{row['interior_sites']}/{row['induced_edges']}",
            row["moment_basis_count"], block_text(row["moment_block_sizes"]),
            row["gap_basis_count"], block_text(row["gap_block_sizes"]),
            row["equality_count"], row["real_scalar_variable_count"], row["affine_term_count"],
            compact_number(row["max_rss_gb"]),
        ]
        for row in levels
    ] or [["—"] * 12]
    image = f"<figure><img src='{html.escape(working_plot)}' alt='Working accepted and floating endpoints'><figcaption>Filled markers passed acceptance; open markers are floating calculations.</figcaption></figure>" if working_plot else ""
    gap_image = f"<figure><img src='{html.escape(gap_plot)}' alt='Fixed-gamma hierarchy classifications'><figcaption>FEASIBLE means not excluded at this level; EXCLUDED markers have exact-projected Farkas certificates.</figcaption></figure>" if gap_plot else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Issue 92 — Current SCNet Calculation Report</title>
<style>
:root{{--ink:#182431;--muted:#607080;--paper:#f6f3eb;--panel:#fffdf8;--line:#d9d3c6;--navy:#173b57;--teal:#16746f;--orange:#cf682d;--red:#a23e3e;--green:#26704c}}
*{{box-sizing:border-box}} body{{margin:0;color:var(--ink);background:linear-gradient(135deg,#e8f2ef,var(--paper) 24rem);font:16px/1.55 Inter,system-ui,sans-serif}}
main{{max-width:1180px;margin:auto;padding:2rem 1.2rem 5rem}} h1,h2{{color:var(--navy);font-family:Georgia,serif;line-height:1.15}} h1{{font-size:clamp(2.2rem,5vw,4rem);margin:.2rem 0}} h2{{margin-top:2.3rem}}
.subtitle{{color:var(--muted);max-width:75ch}} .notice{{padding:1rem 1.2rem;border-left:5px solid var(--orange);background:#fff3e6;border-radius:.4rem}}
.result{{margin:1.2rem 0;padding:.2rem 1.2rem 1rem;border:2px solid var(--teal);background:#effaf6;border-radius:.7rem}} .result h2{{margin-top:1rem}} .result li{{margin:.45rem 0}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:.8rem;margin:1.4rem 0}} .card{{background:var(--panel);border:1px solid var(--line);border-radius:.7rem;padding:1rem;box-shadow:0 5px 18px #1824310d}} .card b{{display:block;font-size:1.75rem;color:var(--navy)}} .card span{{color:var(--muted);font-size:.88rem}}
.legend{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:.7rem}} .legend div{{padding:.8rem 1rem;border-radius:.5rem;background:var(--panel);border:1px solid var(--line)}} .a{{border-left:5px solid var(--green)!important}} .f{{border-left:5px solid var(--orange)!important}} .u{{border-left:5px solid var(--red)!important}}
.table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:.6rem;background:var(--panel)}} table{{width:100%;border-collapse:collapse;font-size:.89rem}} th{{background:#e8efef;color:var(--navy);text-align:left}} th,td{{padding:.6rem .7rem;border-bottom:1px solid #e8e3d9;white-space:nowrap}} tr:last-child td{{border-bottom:0}}
code{{background:#ebe7dd;padding:.12rem .3rem;border-radius:.25rem}} figure{{margin:1.5rem 0;background:white;border:1px solid var(--line);border-radius:.7rem;padding:1rem}} img{{max-width:100%;display:block;margin:auto}} figcaption{{color:var(--muted);text-align:center;font-size:.88rem}}
.foot{{margin-top:2.5rem;padding-top:1rem;border-top:1px solid var(--line);color:var(--muted)}} a{{color:#09627a}} @media(max-width:650px){{main{{padding:1rem .7rem 3rem}}}}
</style></head><body><main>
<p><a href="../../README.md">Issue 92 workspace</a> · <a href="observable_objectives.csv">objective CSV</a> · <a href="working_intervals.csv">working intervals CSV</a> · <a href="gap_scan_trials.csv">gap CSV</a> · <a href="level_sizes.csv">level sizes CSV</a></p>
<h1>Current SCNet calculation report</h1>
<p class="subtitle">Target 2 thermodynamic state-polynomial hierarchy · generated {html.escape(generated)} · primary matrix encoding · complete hard-core baseline · U(1)-invariant KMS states.</p>
<p><strong>Parameters (t/U, μ/U):</strong> P1=(0.03,0.50), P2=(0.05,0.50), P3=(0.06,0.50), P4=(0.03,0.15), P5=(0.03,0.75). Here ρ0 is the root density, F0 = ⟨(n0−1)²⟩, and K0 is the mean root-neighbor hopping correlator. Graph codes: 83 = {{8,3}}, 124 = {{12,4}}, line83 = L({{8,3}}).</p>
<div class="notice"><strong>Calculations on the way are included.</strong> Accepted endpoints and floating solver candidates are displayed together, but every number carries its evidence tier. Floating values are not promoted to certified bounds or gap exclusions.</div>
<div class="result"><h2>Certified thermodynamic upper statements</h2><ul>{gap_headline}</ul><p>These are hierarchy exclusions within <code>U1_INVARIANT_KMS_STATES</code>, not finite-cluster ED gaps. FEASIBLE samples are not lower bounds.</p></div>
<div class="cards"><div class="card"><b>{tiers['ACCEPTED']}</b><span>accepted one-sided objectives</span></div><div class="card"><b>{tiers['FLOATING']}</b><span>floating objectives</span></div><div class="card"><b>{sum(bool(row['accepted']) for row in intervals)}</b><span>accepted two-sided intervals</span></div><div class="card"><b>{gap_completed}/{len(gap_trials)}</b><span>fixed-γ trials recorded</span></div><div class="card"><b>{cells['COMPLETE']}</b><span>complete observable cells</span></div><div class="card"><b>{cells['RUNNING']}</b><span>observable cells running</span></div></div>
<h2>Evidence legend</h2><div class="legend"><div class="a"><strong>Accepted (A)</strong><br>Independent primal/dual, PSD, and objective-gap checks passed.</div><div class="f"><strong>Floating (F)</strong><br>Clarabel returned an optimum, but a strict independent threshold failed.</div><div class="u"><strong>Unknown</strong><br>Includes floating, unfinished, error, and resource-limited rows. No exclusion is inferred.</div></div>
<h2>Accepted one-sided results</h2>{html_table(['graph','point','γ/U','(L,d)','accepted statement','certificate','dual residual','min PSD eigenvalue','exact evidence'],accepted_rows)}
<p>For <code>nmax=1</code>, accepted F0 upper endpoints follow exactly from <code>F0 = 1 - rho0</code> and the opposite accepted rho0 endpoint.</p>
<h2>Working numerical intervals</h2><p>Endpoint suffix <strong>A</strong> means accepted; <strong>F</strong> means floating. A blank side has no durable result yet.</p>{html_table(['graph','point','γ/U','(L,d)','observable','lower','upper','state'],working_rows or [['—']*8])}
{image}
<h2>Floating endpoint diagnostics</h2>{html_table(['graph','point','γ/U','objective','value','primal residual','dual residual','min PSD eigenvalue'],floating_rows)}
<h2>Larger-level resource outcomes</h2>{html_table(['graph','point','(L,d)','requested memory','classification','recorded reason'],error_rows)}
<p>The nested cells recorded explicit <code>UNKNOWN</code> rows after Julia <code>OutOfMemoryError</code>; Slurm shell completion is not a scientific result. The complete cutoff-2 baseline likewise remains <code>UNKNOWN</code>: the 192-GiB attempt was killed by the memory cgroup, and its 237-GiB retry exhausted memory inside Julia while safely checkpointing all four probes as <code>UNKNOWN</code>. Eight-thread MKL and QDLDL recoveries <code>41540879</code>/<code>41541639</code> also exhausted memory, establishing a structural resource gate. TS2 dry task <code>41541783_28</code> instead died with <code>SIGBUS</code> at only 1.8 GiB RSS. Pre-optimization task 31 was canceled after 50 minutes without a checkpoint; optimized different-node <code>(1,3)</code> retry <code>41542822</code> is running and resumable optimized <code>(2,2)</code> guard <code>41544379</code> is queued.</p>
<p>The queued retry uses incrementally maintained active degrees in deterministic chordal completion, removing the former cubic rescan. Nineteen direct reference comparisons preserve the exact clique sequence; a 220-vertex kernel benchmark was 20.6 times faster. This is an assembly optimization, not a change to the formal <code>TS2</code> support-closure level.</p>
<p>The read-only pair-support pass is also threaded and merged lexicographically. The cutoff-two <code>(1,3)</code>/<code>(2,2)</code> gates contain 11.60/3.11 million charge-compatible pairs per closure pass; the full suite passes under four Julia threads before the 104-thread SCNet retry.</p>
<h2>Assembled level sizes</h2>{html_table(['graph','nmax','(L,d)','window/interior/edges','moment basis','moment blocks','gap basis','gap blocks','equalities','real variables','affine terms','max RSS GiB'],level_table_rows)}
<p>Block sizes are exact U(1)-charge blocks. Max RSS is the largest recorded runner RSS for that assembled template.</p>
<h2>Gap calculation status</h2><p>The fixed-γ campaign currently contains <strong>{gap_counts['FEASIBLE']} FEASIBLE</strong>, <strong>{gap_counts['EXCLUDED']} EXCLUDED</strong>, and <strong>{gap_counts['UNKNOWN']} UNKNOWN</strong> rows. FEASIBLE means only “not excluded at this level”; it is not a physical lower bound.</p>
{html_table(['graph','point','nmax','(L,d)','last sampled FEASIBLE','first verified EXCLUDED','search span','unresolved inside','exact affine residual','Farkas margin lower','bits','PSD','implication'],bracket_rows)}
<p>A search span is not a numerical bracket when its unresolved count is nonzero. Solver errors and unfinished refinement points do not move either endpoint.</p>
<p>Every EXCLUDED endpoint in this table passed exact Q(√2,√3) projection, 256-bit Arb sign checks, rigorous PSD verification (interval LDL with exact-field fallback), and a positive normalized Farkas margin.</p>
<p>The stored <code>{{12,4}}</code> P2 <code>gamma/U=0.520</code> proof was replayed through the optimized rigorous PSD path: all eight blocks (largest <code>222x222</code>) passed in 3.125 seconds, versus 1,943 seconds in the already-running legacy fallback. Exact affine residual zero and Farkas margin one are unchanged.</p>
{html_table(['graph','point','nmax','(L,d)','γ/U','classification','raw status','solver','certificate'],completed_gap_rows)}
{gap_image}
<h2>Geometry, parameter, and cutoff comparisons</h2><p>Only matched finite-level certified upper statements are placed side by side. Their numerical order does not establish the order of the unknown true gaps.</p>
{html_table(['dimension','fixed scope','certified evidence','claim boundary'],comparison_table_rows)}
<h2>Physical interpretation</h2><p>For {{8,3}} at P2, the accepted rho0 lower endpoint rises and the accepted F0 upper endpoint falls as the <em>assumed</em> γ is increased from 0 to 0.10. This is tightening of the conditional hierarchy feasible set—not a change in the Hamiltonian and not yet a measured bulk gap.</p>
<h2>Claim boundary</h2><p>This snapshot may be used to present numerical progress. Values marked F must remain labeled “floating candidate” or “calculation in progress.” Gap exclusions labeled <code>VERIFIED_EXACT_PROJECTED</code> are independently certified; FEASIBLE samples remain non-exclusion evidence only.</p>
<p class="foot">SCNet jobs: observables {SCNET_CAMPAIGN_JOBS['observable array']}; nested levels {SCNET_CAMPAIGN_JOBS['nested-level array']}; original fixed-γ scan {SCNET_CAMPAIGN_JOBS['fixed-gamma array']} (held to enforce the cap); expedited scans {SCNET_CAMPAIGN_JOBS['expedited fixed-gamma arrays']}; refinement {SCNET_CAMPAIGN_JOBS['gap-refinement array']}; alternate-KKT retry {SCNET_CAMPAIGN_JOBS['alternate-KKT retry']}; reduced-thread MKL retry {SCNET_CAMPAIGN_JOBS['reduced-thread MKL retry']}; CHOLMOD retry {SCNET_CAMPAIGN_JOBS['CHOLMOD retry']}; 8-thread MKL retry {SCNET_CAMPAIGN_JOBS['8-thread MKL retry']}; transition micro-scan {SCNET_CAMPAIGN_JOBS['transition micro-scan']}; geometry refinements {SCNET_CAMPAIGN_JOBS['geometry refinements']}; geometry recovery {SCNET_CAMPAIGN_JOBS['geometry parallel recovery']}; geometry midpoints {SCNET_CAMPAIGN_JOBS['geometry midpoint recovery']}; extended geometry grid {SCNET_CAMPAIGN_JOBS['extended geometry Target-2 grid']}; remaining-point gap scan {SCNET_CAMPAIGN_JOBS['remaining-point gap scan']}; remaining-point transition refinement {SCNET_CAMPAIGN_JOBS['remaining-point transition refinement']}; P5 fine refinement {SCNET_CAMPAIGN_JOBS['P5 fine refinement']}; P3 micro refinement {SCNET_CAMPAIGN_JOBS['P3 micro refinement']}; remaining-point observables {SCNET_CAMPAIGN_JOBS['remaining-point observables']}; cutoff-2 representative {SCNET_CAMPAIGN_JOBS['cutoff-2 representative']}; cutoff-2 TS2 dry gate {SCNET_CAMPAIGN_JOBS['cutoff-2 TS2 dry gate']}; exact observable representative {SCNET_CAMPAIGN_JOBS['exact observable representative']}. Raw JSON records retain solver state, residuals, primal/dual data, runtime, and checkpoint provenance.</p>
</main></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--presentation-manifest",type=Path,default=Path("results/presentation_manifest.json"))
    parser.add_argument("--presentation-results",type=Path,default=Path("results/presentation_pilots"))
    parser.add_argument("--remaining-observable-manifest",type=Path,default=Path("results/deadline_remaining_target_observable_manifest.json"))
    parser.add_argument("--remaining-observable-results",type=Path,default=Path("results/deadline_remaining_target_observables"))
    parser.add_argument("--exact-observable-manifest",type=Path,default=Path("results/deadline_exact_observable_manifest.json"))
    parser.add_argument("--exact-observable-results",type=Path,default=Path("results/deadline_exact_observables"))
    parser.add_argument("--nested-manifest",type=Path,default=Path("results/deadline_nested_manifest.json"))
    parser.add_argument("--nested-results",type=Path,default=Path("results/deadline_nested"))
    parser.add_argument("--dry-level-manifest",type=Path,default=Path("results/dry_level_manifest.json"))
    parser.add_argument("--dry-level-results",type=Path,default=Path("results/dry_levels"))
    parser.add_argument("--gap-manifest",type=Path,default=Path("results/deadline_gap_scan_manifest.json"))
    parser.add_argument("--gap-results",type=Path,default=Path("results/deadline_gap_scans"))
    parser.add_argument("--refinement-manifest",type=Path,default=Path("results/deadline_gap_refinement_manifest.json"))
    parser.add_argument("--refinement-results",type=Path,default=Path("results/deadline_gap_refinement"))
    parser.add_argument("--retry-manifest",type=Path,default=Path("results/deadline_gap_retry_manifest.json"))
    parser.add_argument("--retry-results",type=Path,default=Path("results/deadline_gap_retry"))
    parser.add_argument("--retry-mkl-results",type=Path,default=Path("results/deadline_gap_retry_mkl16"))
    parser.add_argument("--retry-cholmod-results",type=Path,default=Path("results/deadline_gap_retry_cholmod"))
    parser.add_argument("--retry-mkl8-results",type=Path,default=Path("results/deadline_gap_retry_mkl8"))
    parser.add_argument("--micro-manifest",type=Path,default=Path("results/deadline_gap_micro_manifest.json"))
    parser.add_argument("--geometry-refinement-manifest",type=Path,default=Path("results/deadline_geometry_refinement_manifest.json"))
    parser.add_argument("--geometry-parallel-manifest",type=Path,default=Path("results/deadline_geometry_parallel_manifest.json"))
    parser.add_argument("--geometry-parallel-results",type=Path,default=Path("results/deadline_geometry_parallel"))
    parser.add_argument("--geometry-micro-manifest",type=Path,default=Path("results/deadline_geometry_micro_manifest.json"))
    parser.add_argument("--geometry-micro-results",type=Path,default=Path("results/deadline_geometry_micro"))
    parser.add_argument("--geometry-grid-manifest",type=Path,default=Path("results/deadline_geometry_grid_manifest.json"))
    parser.add_argument("--geometry-grid-results",type=Path,default=Path("results/deadline_geometry_grid"))
    parser.add_argument("--remaining-gap-manifest",type=Path,default=Path("results/deadline_remaining_target_gap_manifest.json"))
    parser.add_argument("--remaining-gap-results",type=Path,default=Path("results/deadline_remaining_target_gaps"))
    parser.add_argument("--target-refinement-manifest",type=Path,default=Path("results/deadline_target_refinement_manifest.json"))
    parser.add_argument("--target-refinement-results",type=Path,default=Path("results/deadline_target_refinement"))
    parser.add_argument("--p5-fine-manifest",type=Path,default=Path("results/deadline_p5_fine_manifest.json"))
    parser.add_argument("--p5-fine-results",type=Path,default=Path("results/deadline_p5_fine"))
    parser.add_argument("--p3-micro-manifest",type=Path,default=Path("results/deadline_p3_micro_manifest.json"))
    parser.add_argument("--p3-micro-results",type=Path,default=Path("results/deadline_p3_micro"))
    parser.add_argument("--cutoff2-gap-manifest",type=Path,default=Path("results/deadline_cutoff2_gap_manifest.json"))
    parser.add_argument("--cutoff2-gap-results",type=Path,default=Path("results/deadline_cutoff2_gaps"))
    parser.add_argument("--cutoff2-lowthread-results",type=Path,default=Path("results/deadline_cutoff2_gaps_lowthreads"))
    parser.add_argument("--cutoff2-qdldl-results",type=Path,default=Path("results/deadline_cutoff2_gaps_qdldl"))
    parser.add_argument("--output",type=Path,default=Path("results/deadline_analysis"))
    args = parser.parse_args()
    observable_records = [
        *observable_rows(args.presentation_manifest,args.presentation_results),
        *observable_rows(args.nested_manifest,args.nested_results),
    ]
    if args.remaining_observable_manifest.exists():
        observable_records.extend(
            observable_rows(args.remaining_observable_manifest,args.remaining_observable_results)
        )
    if args.exact_observable_manifest.exists():
        observable_records.extend(
            observable_rows(args.exact_observable_manifest,args.exact_observable_results)
        )
    observable_records = deduplicate_observable_rows(observable_records)
    level_sources = [
        (args.presentation_manifest,args.presentation_results),
        (args.nested_manifest,args.nested_results),
    ]
    if args.dry_level_manifest.exists():
        level_sources.append((args.dry_level_manifest,args.dry_level_results))
    if args.remaining_observable_manifest.exists():
        level_sources.append(
            (args.remaining_observable_manifest,args.remaining_observable_results)
        )
    if args.cutoff2_gap_manifest.exists():
        level_sources.append((args.cutoff2_gap_manifest,args.cutoff2_gap_results))
        if args.cutoff2_lowthread_results.exists():
            level_sources.append(
                (args.cutoff2_gap_manifest,args.cutoff2_lowthread_results)
            )
        if args.cutoff2_qdldl_results.exists():
            level_sources.append(
                (args.cutoff2_gap_manifest,args.cutoff2_qdldl_results)
            )
    levels = level_size_rows(
        level_sources
    )
    intervals = interval_rows(observable_records)
    gap_trials = gap_scan_rows(args.gap_manifest,args.gap_results)
    if args.refinement_manifest.exists():
        gap_trials.extend(gap_scan_rows(args.refinement_manifest,args.refinement_results))
    if args.micro_manifest.exists():
        gap_trials.extend(gap_scan_rows(args.micro_manifest,args.refinement_results))
    if args.geometry_refinement_manifest.exists():
        gap_trials.extend(gap_scan_rows(args.geometry_refinement_manifest,args.refinement_results))
    if args.geometry_parallel_manifest.exists():
        gap_trials.extend(
            gap_scan_rows(args.geometry_parallel_manifest,args.geometry_parallel_results)
        )
    if args.geometry_micro_manifest.exists():
        gap_trials.extend(
            gap_scan_rows(args.geometry_micro_manifest,args.geometry_micro_results)
        )
    if args.geometry_grid_manifest.exists():
        gap_trials.extend(
            gap_scan_rows(args.geometry_grid_manifest,args.geometry_grid_results)
        )
    if args.remaining_gap_manifest.exists():
        gap_trials.extend(gap_scan_rows(args.remaining_gap_manifest,args.remaining_gap_results))
    if args.target_refinement_manifest.exists():
        gap_trials.extend(
            gap_scan_rows(args.target_refinement_manifest,args.target_refinement_results)
        )
    if args.p5_fine_manifest.exists():
        gap_trials.extend(gap_scan_rows(args.p5_fine_manifest,args.p5_fine_results))
    if args.p3_micro_manifest.exists():
        gap_trials.extend(gap_scan_rows(args.p3_micro_manifest,args.p3_micro_results))
    if args.cutoff2_gap_manifest.exists():
        gap_trials.extend(gap_scan_rows(args.cutoff2_gap_manifest,args.cutoff2_gap_results))
        if args.cutoff2_lowthread_results.exists():
            gap_trials.extend(
                gap_scan_rows(args.cutoff2_gap_manifest,args.cutoff2_lowthread_results)
            )
        if args.cutoff2_qdldl_results.exists():
            gap_trials.extend(
                gap_scan_rows(args.cutoff2_gap_manifest,args.cutoff2_qdldl_results)
            )
    if args.retry_manifest.exists():
        gap_trials.extend(gap_scan_rows(args.retry_manifest,args.retry_results))
        if args.retry_mkl_results.exists():
            gap_trials.extend(gap_scan_rows(args.retry_manifest,args.retry_mkl_results))
        if args.retry_cholmod_results.exists():
            gap_trials.extend(gap_scan_rows(args.retry_manifest,args.retry_cholmod_results))
        if args.retry_mkl8_results.exists():
            gap_trials.extend(gap_scan_rows(args.retry_manifest,args.retry_mkl8_results))
    checks = nested_checks(intervals)
    working = working_interval_rows(observable_records)
    args.output.mkdir(parents=True,exist_ok=True)
    common = ("id","geometry","point","t","mu","gamma","nmax","L","d","encoding","basis_family","symmetry","precision_profile","requested_memory_gb")
    atomic_csv(args.output/"observable_objectives.csv",observable_records,(*common,"observable","sense","classification","optimum","floating_optimum","certified_objective","raw_status","solver","runtime_seconds","primal_residual","dual_residual","min_psd_eigenvalue","certificate_class","certificate_precision_bits","certificate_affine_residual","certificate_psd_verified","certificate_objective_gap","cell_status","diagnostic_only","message"))
    atomic_csv(args.output/"observable_intervals.csv",intervals,(*common,"observable","lower","upper","width","accepted","order_check","lower_certificate_class","upper_certificate_class","reason"))
    atomic_csv(args.output/"working_intervals.csv",working,(*common,"observable","lower","upper","lower_tier","upper_tier","lower_raw_status","upper_raw_status","complete_numeric"))
    atomic_csv(args.output/"gap_scan_trials.csv",gap_trials,(*common,"classification","raw_status","solver","runtime_seconds","primal_residual","dual_residual","min_psd_eigenvalue","certificate_class","certificate_precision_bits","certificate_affine_residual","certificate_psd_verified","certificate_farkas_margin_lower","cell_status","message"))
    atomic_csv(args.output/"level_sizes.csv",levels,("geometry","nmax","L","d","encoding","basis_family","symmetry","window_sites","interior_sites","induced_edges","moment_basis_count","moment_block_sizes","gap_basis_count","gap_block_sizes","equality_count","real_scalar_variable_count","affine_term_count","estimated_memory_gb","requested_memory_gb","max_rss_gb","assembled_cell_count"))
    atomic_csv(args.output/"nestedness_checks.csv",checks,("direction","baseline_L","baseline_d","target_L","target_d","observable","lower_delta","upper_delta","status"))
    plots = make_plots(intervals,args.output)
    atomic_text(args.output/"PRESENTATION_RESULTS.md",markdown_summary(observable_records,intervals,gap_trials,checks,plots))
    working_plot = make_working_plot(observable_records,args.output)
    gap_plot = make_gap_status_plot(gap_trials,args.output)
    generated = datetime.now().astimezone().isoformat(timespec="seconds")
    atomic_text(args.output/"CURRENT_HPC_REPORT.md",current_progress_markdown(observable_records,intervals,gap_trials,working,levels,working_plot,gap_plot,generated))
    atomic_text(args.output/"CURRENT_HPC_REPORT.html",current_progress_html(observable_records,intervals,gap_trials,working,levels,working_plot,gap_plot,generated))
    print(f"wrote {len(observable_records)} objective rows, {len(intervals)} intervals, {len(gap_trials)} fixed-gamma rows, and {len(checks)} nested checks",flush=True)


if __name__ == "__main__":
    main()
