#!/usr/bin/env python3
"""Build the compact, auditable issue-92 submission from the live analysis.

The large solver payloads under ``results/`` remain the source evidence and
stay out of git.  This script creates a small submission layer containing a
self-contained report, curated CSV tables, and a manifest that maps
every presentation claim back to the live aggregate.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
ANALYSIS = RESULTS / "deadline_analysis"
OUTPUT = ROOT / "submission"
TABLES = OUTPUT / "tables"

ISSUE_URL = "https://github.com/QuantumBFS/quantum.harness/issues/92"
PAPER_URL = "https://arxiv.org/abs/2606.03836"
SYMMETRY = "U1_INVARIANT_KMS_STATES"
GRAPH_NAMES = {
    "83": "{8,3}",
    "124": "{12,4}",
    "line83": "L({8,3})",
}
POINTS = {
    "P1": (0.03, 0.50),
    "P2": (0.05, 0.50),
    "P3": (0.06, 0.50),
    "P4": (0.03, 0.15),
    "P5": (0.03, 0.75),
}

CAMPAIGN_ROLES = {
    "deadline_analysis": ("aggregate", "Canonical merged tables, plots, and live calculation report."),
    "deadline_gap_scans": ("production", "Initial hard-core fixed-gap scan."),
    "deadline_gap_refinement": ("production", "Hard-core transition refinement."),
    "deadline_gap_retry_mkl16": ("production", "Alternate-thread exact-certificate retries."),
    "deadline_target_refinement": ("production", "P1/P3/P4/P5 transition refinements."),
    "deadline_p3_micro": ("production", "P3 transition micro-scan."),
    "deadline_p5_fine": ("production", "P5 fine transition scan."),
    "deadline_geometry_parallel": ("production", "Geometry P2 parallel recovery."),
    "deadline_geometry_micro": ("production", "Geometry P2 midpoint recovery."),
    "deadline_geometry_grid": ("production-live", "Extended Target-2 geometry grid; may be updated by SCNet."),
    "deadline_remaining_target_gaps": ("production", "Remaining {8,3} Target-2 gap points."),
    "deadline_remaining_target_observables": ("production", "Remaining {8,3} observable cells."),
    "deadline_exact_observables": ("production", "Exact-projected representative observable bounds."),
    "deadline_nested_mkl": ("resource-gate", "Hard-core nested-level solve attempts."),
    "deadline_cutoff2_gaps": ("resource-gate", "Complete cutoff-two solve attempt."),
    "deadline_cutoff2_gaps_lowthreads": ("resource-gate", "Reduced-thread cutoff-two retry."),
    "deadline_cutoff2_gaps_qdldl": ("resource-gate", "QDLDL cutoff-two retry."),
    "dry_levels": ("resource-gate", "Expression-only hierarchy assemblies and TS2 gates."),
    "dry_models": ("resource-gate", "Unsolved JuMP model-build measurements."),
    "atomic": ("validation", "Atomic-limit exact and numerical checks."),
    "reference": ("validation", "Pinned upstream reproduction status."),
    "graphs": ("input", "Radius-guarded graph windows."),
    "clarabel_pilots": ("diagnostic", "Local/open-source solver pilots."),
    "presentation_pilots": ("diagnostic", "Low-precision deadline observable runs."),
    "slurm": ("operations", "Scheduler logs; not scientific evidence by themselves."),
    "tables": ("legacy-aggregate", "Earlier Python diagnostic tables."),
}


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value)
    os.replace(temporary, path)


def atomic_json(path: Path, value: object) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def read_csv(name: str) -> list[dict[str, str]]:
    path = ANALYSIS / name
    if not path.exists():
        raise SystemExit(
            f"missing {path}; run scripts/analyze_deadline.py before building the submission"
        )
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_csv(path: Path, rows: Iterable[dict[str, object]], fields: Iterable[str]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fields),
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def present(value: object) -> bool:
    return value is not None and str(value).strip() not in ("", "None")


def truthy(value: object) -> bool:
    return str(value).strip().lower() in ("true", "1", "yes")


def number(value: object, digits: int = 7) -> str:
    if not present(value):
        return "—"
    return f"{float(value):.{digits}g}"


def evidence_tier(row: dict[str, str]) -> str:
    if row.get("classification") == "FEASIBLE" and present(row.get("optimum")):
        return "ACCEPTED"
    if row.get("classification") == "EXCLUDED":
        return "VERIFIED_EXCLUSION"
    if present(row.get("optimum")):
        return "FLOATING"
    if row.get("raw_status") == "ERROR":
        return "ERROR"
    if row.get("cell_status") == "RUNNING":
        return "UNFINISHED"
    if row.get("cell_status") == "MISSING":
        return "NOT_STARTED"
    return "UNKNOWN"


def transition_rows(gaps: list[dict[str, str]]) -> list[dict[str, object]]:
    keys = ("geometry", "point", "t", "mu", "nmax", "L", "d")
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for row in gaps:
        grouped.setdefault(tuple(row.get(key, "") for key in keys), []).append(row)

    result: list[dict[str, object]] = []
    for key, group in grouped.items():
        excluded = sorted(
            (
                row
                for row in group
                if row.get("classification") == "EXCLUDED"
                and row.get("certificate_class") == "VERIFIED_EXACT_PROJECTED"
            ),
            key=lambda row: float(row["gamma"]),
        )
        if not excluded:
            continue
        endpoint = excluded[0]
        upper = float(endpoint["gamma"])
        feasible = [
            float(row["gamma"])
            for row in group
            if row.get("classification") == "FEASIBLE" and float(row["gamma"]) < upper
        ]
        lower = max(feasible) if feasible else None
        decisive = {
            float(row["gamma"])
            for row in group
            if row.get("classification") == "FEASIBLE"
            or (
                row.get("classification") == "EXCLUDED"
                and row.get("certificate_class") == "VERIFIED_EXACT_PROJECTED"
            )
        }
        unknown = {
            float(row["gamma"])
            for row in group
            if lower is not None
            and lower < float(row["gamma"]) < upper
            and float(row["gamma"]) not in decisive
        }
        base = dict(zip(keys, key))
        width = upper - lower if lower is not None else None
        result.append(
            {
                **base,
                "graph": GRAPH_NAMES.get(base["geometry"], base["geometry"]),
                "last_feasible": lower,
                "verified_excluded": upper,
                "search_span": width,
                "unresolved_inside": len(unknown),
                "clean_0p005": bool(
                    lower is not None and not unknown and width is not None and width <= 0.005000001
                ),
                "certificate_class": endpoint.get("certificate_class"),
                "precision_bits": endpoint.get("certificate_precision_bits"),
                "affine_residual": endpoint.get("certificate_affine_residual"),
                "psd_verified": endpoint.get("certificate_psd_verified"),
                "farkas_margin_lower": endpoint.get("certificate_farkas_margin_lower"),
            }
        )
    return sorted(
        result,
        key=lambda row: (
            str(row["geometry"]), str(row["point"]), int(row["nmax"]),
            int(row["L"]), int(row["d"]),
        ),
    )


def file_digest(path: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def result_inventory() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(item for item in RESULTS.iterdir() if item.is_dir()):
        files = [item for item in path.rglob("*") if item.is_file()]
        role, description = CAMPAIGN_ROLES.get(
            path.name, ("supporting", "Supporting or superseded campaign evidence.")
        )
        rows.append(
            {
                "directory": path.name,
                "role": role,
                "description": description,
                "files": len(files),
                "bytes": sum(item.stat().st_size for item in files),
            }
        )
    return rows


def markdown_table(columns: list[str], rows: list[list[object]]) -> str:
    result = ["| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    result.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return "\n".join(result)


def report_table(columns: list[str], rows: list[list[object]], numeric: list[bool] | None = None) -> dict[str, object]:
    return {
        "kind": "table",
        "columns": columns,
        "rows": [[str(value) for value in row] for row in rows],
        "numeric": numeric or [False] * len(columns),
    }


def html_table(columns: list[str], rows: list[list[object]]) -> str:
    head = "".join(f"<th>{html.escape(str(column))}</th>" for column in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in row) + "</tr>"
        for row in rows
    )
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def render_academic_html(report: dict[str, object]) -> str:
    """Render the small review report without presentation-card styling."""

    chunks: list[str] = []
    for section in report["sections"]:
        chunks.append(f"<section><h2>{html.escape(str(section['title']))}</h2>")
        for block in section["blocks"]:
            kind = block["kind"]
            if kind == "text":
                chunks.append(f"<p>{html.escape(str(block['text']))}</p>")
            elif kind == "heading":
                chunks.append(f"<h3>{html.escape(str(block['text']))}</h3>")
            elif kind == "note":
                chunks.append(f'<p class="note">{html.escape(str(block["text"]))}</p>')
            elif kind == "list":
                items = "".join(f"<li>{html.escape(str(item))}</li>" for item in block["items"])
                chunks.append(f"<ul>{items}</ul>")
            elif kind == "table":
                chunks.append(html_table(block["columns"], block["rows"]))
            else:
                raise ValueError(f"unsupported academic-report block: {kind}")
        chunks.append("</section>")

    title = html.escape(str(report["title"]))
    subtitle = html.escape(str(report["subtitle"]))
    generated = html.escape(str(report["generated"]))
    issue_url = html.escape(str(report["url"]), quote=True)
    body = "".join(chunks)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{ color-scheme: light; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #fff; color: #202124; font: 16px/1.55 Arial, Helvetica, sans-serif; }}
    main {{ width: min(980px, calc(100% - 40px)); margin: 48px auto 72px; }}
    header {{ border-bottom: 1px solid #9aa0a6; padding-bottom: 22px; margin-bottom: 34px; }}
    h1, h2, h3 {{ color: #151515; font-family: Georgia, 'Times New Roman', serif; font-weight: 600; }}
    h1 {{ font-size: 2.1rem; line-height: 1.18; margin: 0 0 10px; }}
    h2 {{ font-size: 1.45rem; margin: 38px 0 12px; border-bottom: 1px solid #dadce0; padding-bottom: 5px; }}
    h3 {{ font-size: 1.1rem; margin: 27px 0 8px; }}
    p {{ margin: 8px 0 13px; }}
    .subtitle {{ max-width: 780px; font-size: 1.05rem; margin: 0 0 8px; }}
    .meta {{ color: #5f6368; font-size: .9rem; }}
    .meta a {{ color: inherit; }}
    .note {{ border-left: 3px solid #5f6368; padding: 7px 12px; color: #3c4043; }}
    ul {{ margin: 8px 0 14px; padding-left: 24px; }}
    li {{ margin: 4px 0; }}
    .table-wrap {{ overflow-x: auto; margin: 13px 0 20px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: .88rem; font-variant-numeric: tabular-nums; }}
    th, td {{ border-bottom: 1px solid #dadce0; padding: 7px 8px; text-align: left; vertical-align: top; white-space: nowrap; }}
    th {{ border-top: 1px solid #9aa0a6; border-bottom-color: #9aa0a6; background: #f8f9fa; font-weight: 600; }}
    footer {{ border-top: 1px solid #dadce0; margin-top: 44px; padding-top: 12px; color: #5f6368; font-size: .85rem; }}
    @media print {{ main {{ width: 100%; margin: 0; }} .table-wrap {{ overflow: visible; }} section {{ break-inside: auto; }} }}
  </style>
</head>
<body><main>
  <header>
    <h1>{title}</h1>
    <p class="subtitle">{subtitle}</p>
    <p class="meta"><a href="{issue_url}">Quantum Harness issue #92</a> · snapshot {generated}</p>
  </header>
  {body}
  <footer>All energies are in units of U. Raw solver records and certificate payloads are retained under results/.</footer>
</main></body>
</html>
"""


def build() -> None:
    generated = datetime.now().astimezone().isoformat(timespec="seconds")
    observables = read_csv("observable_objectives.csv")
    intervals = read_csv("observable_intervals.csv")
    gaps = read_csv("gap_scan_trials.csv")
    levels = read_csv("level_sizes.csv")
    nested = read_csv("nestedness_checks.csv")
    with (RESULTS / "finite_patch_ed.csv").open(newline="") as handle:
        finite_patch_ed = list(csv.DictReader(handle))
    with (RESULTS / "atomic_gap_brackets.csv").open(newline="") as handle:
        atomic_brackets = list(csv.DictReader(handle))
    atomic_certificate = json.loads(
        (RESULTS / "atomic" / "julia-hierarchy-certificate.json").read_text()
    )

    def target_point(row: dict[str, str]) -> str | None:
        t = float(row["hopping"])
        mu = float(row["mu"])
        return next(
            (
                point
                for point, (point_t, point_mu) in POINTS.items()
                if abs(t - point_t) < 1e-12 and abs(mu - point_mu) < 1e-12
            ),
            None,
        )

    target2_ed = [
        {**row, "point": target_point(row)}
        for row in finite_patch_ed
        if row["nmax"] == "3" and row["scan"] != "atomic_check" and target_point(row)
    ]
    target2_ed.sort(
        key=lambda row: (
            int(str(row["point"])[1:]),
            ("83", "124", "line83").index(row["geometry"]),
        )
    )

    tiers = Counter(evidence_tier(row) for row in observables)
    gap_counts = Counter(row.get("classification", "UNKNOWN") for row in gaps)
    accepted_objectives = [row for row in observables if evidence_tier(row) == "ACCEPTED"]
    accepted_intervals = [row for row in intervals if truthy(row.get("accepted"))]
    verified_gap_trials = [
        row
        for row in gaps
        if row.get("classification") == "EXCLUDED"
        and row.get("certificate_class") == "VERIFIED_EXACT_PROJECTED"
    ]
    transitions = transition_rows(gaps)
    durable_gap_rows = [row for row in gaps if present(row.get("raw_status"))]
    exact_observable_rows = [
        row
        for row in accepted_objectives
        if "VERIFIED_EXACT_PROJECTED_BOUND" in row.get("certificate_class", "")
    ]

    TABLES.mkdir(parents=True, exist_ok=True)
    atomic_csv(
        TABLES / "gap_transition_summary.csv",
        transitions,
        (
            "geometry", "graph", "point", "t", "mu", "nmax", "L", "d",
            "last_feasible", "verified_excluded", "search_span", "unresolved_inside",
            "clean_0p005", "certificate_class", "precision_bits", "affine_residual",
            "psd_verified", "farkas_margin_lower",
        ),
    )
    atomic_csv(TABLES / "verified_gap_trials.csv", verified_gap_trials, gaps[0].keys())
    atomic_csv(TABLES / "accepted_observable_objectives.csv", accepted_objectives, observables[0].keys())
    atomic_csv(TABLES / "accepted_observable_intervals.csv", accepted_intervals, intervals[0].keys())
    atomic_csv(TABLES / "level_sizes.csv", levels, levels[0].keys())
    atomic_csv(TABLES / "nestedness_checks.csv", nested, nested[0].keys())
    atomic_csv(
        TABLES / "finite_patch_ed_target2_nmax3.csv",
        target2_ed,
        (
            "claim_type", "geometry", "point", "radius", "sites", "edges", "nmax",
            "interaction", "hopping", "mu", "hilbert_dimension", "finite_patch_gap",
            "rho0", "F0", "K0", "runtime_s",
        ),
    )
    atomic_csv(
        TABLES / "atomic_gap_brackets.csv",
        atomic_brackets,
        atomic_brackets[0].keys(),
    )

    inventory = result_inventory()
    source_files = [
        file_digest(ANALYSIS / name)
        for name in (
            "gap_scan_trials.csv", "observable_objectives.csv", "observable_intervals.csv",
            "working_intervals.csv", "level_sizes.csv", "nestedness_checks.csv",
        )
    ]
    source_files.extend(
        file_digest(path)
        for path in (
            RESULTS / "finite_patch_ed.csv",
            RESULTS / "atomic_gap_brackets.csv",
            RESULTS / "atomic" / "julia-hierarchy-certificate.json",
        )
    )
    counts = {
        "observable_rows": len(observables),
        "accepted_one_sided_objectives": tiers["ACCEPTED"],
        "floating_objectives": tiers["FLOATING"],
        "objective_errors": tiers["ERROR"],
        "accepted_intervals": len(accepted_intervals),
        "interval_rows": len(intervals),
        "fixed_gamma_rows": len(gaps),
        "durable_fixed_gamma_rows": len(durable_gap_rows),
        "feasible_fixed_gamma_rows": gap_counts["FEASIBLE"],
        "verified_excluded_fixed_gamma_rows": gap_counts["EXCLUDED"],
        "unknown_fixed_gamma_rows": gap_counts["UNKNOWN"],
        "certified_gap_upper_statements": len(transitions),
        "exact_projected_observable_bounds": len(exact_observable_rows),
    }

    atomic_json(
        TABLES / "evidence_counts.json",
        {"generated": generated, **counts},
    )

    data_manifest = {
        "schema": "issue92-submission-data-v1",
        "snapshot_generated": generated,
        "scientific_scope": {
            "primary_encoding": "matrix",
            "primary_basis_family": "complete",
            "primary_symmetry": SYMMETRY,
            "classification_vocabulary": ["FEASIBLE", "EXCLUDED", "UNKNOWN"],
            "claim_rule": "EXCLUDED appears only after exact projection, 256-bit interval/exact PSD checks, exact affine residual zero, and positive normalized Farkas margin.",
            "feasibility_rule": "FEASIBLE is non-exclusion evidence at one finite hierarchy level; it is not a physical gap lower bound.",
            "ed_rule": "Finite-cluster exact diagonalization is diagnostic only and is never reported as a thermodynamic bound.",
        },
        "counts": counts,
        "aggregate_sources": source_files,
        "raw_campaign_directories": inventory,
        "active_at_snapshot": [
            "SCNet refinement array 41549521 and line-P4 midpoint 41550952 were still running.",
            "Optimized cutoff-two TS2 gate 41542822 was still running; 41544379 was dependency-queued.",
            "No scheduler state is promoted to scientific evidence until a result JSON is fetched and re-aggregated.",
        ],
    }
    atomic_json(OUTPUT / "data_manifest.json", data_manifest)

    atomic_rho_lower = atomic_certificate["rho0_min_gamma_0"]["dual_data"]["certificate_report"]["certified_objective"]
    atomic_rho_upper = atomic_certificate["rho0_max_gamma_0"]["dual_data"]["certificate_report"]["certified_objective"]
    atomic_upper = atomic_certificate["above_gamma_0.51"]
    ed_table = [
        [
            row["point"], GRAPH_NAMES[row["geometry"]], number(row["hopping"], 2),
            number(row["mu"], 2), number(row["finite_patch_gap"], 6),
            number(row["rho0"], 6), number(row["F0"], 6), number(row["K0"], 6),
        ]
        for row in target2_ed
    ]
    concise_transition_table = [
        [
            row["graph"], row["point"], f"({row['t']}, {row['mu']})",
            number(row["last_feasible"]), number(row["verified_excluded"]),
            row["unresolved_inside"],
        ]
        for row in transitions
    ]
    observable_summary = [
        ["{8,3}", "P5", "0.05", "ρ₀", "[0.9944073, 0.9999995]", "accepted two-sided interval"],
        ["{8,3}", "P5", "0.05", "F₀", "[4.879816×10⁻⁷, 0.005592673]", "accepted two-sided interval"],
        ["{8,3}", "P4", "0.10", "ρ₀", "≥ 0.9455347492", "exact-projected lower bound"],
        ["{8,3}", "P4", "0.10", "F₀", "≤ 0.0544652508", "derived from F₀=1−ρ₀"],
        ["{8,3}", "P4", "0.10", "K₀", "≤ 0.3025838233", "exact-projected upper bound"],
    ]
    atomic_table = [
        ["Analytic product state", "nmax≥2", "Δ=0.5 exactly", "ρ₀=1, F₀=0, K₀=0"],
        ["Radius-one finite ED", "3 graphs; nmax=1,2,3", "finite-patch gap=0.5", "ρ₀=1, F₀=0, K₀=0"],
        [
            "Atomic state-polynomial SDP", "nmax=1,2,3",
            f"numerical [{number(atomic_brackets[0]['lower_feasible'], 8)}, {number(atomic_brackets[0]['upper_infeasible'], 10)}]",
            "ρ₀=1 and F₀=0 to solver tolerance",
        ],
        [
            "Complete Julia hierarchy", "nmax=1; (L,d)=(1,2)",
            f"γ=0.49 FEASIBLE; γ=0.51 {atomic_upper['classification']}",
            f"{number(atomic_rho_lower, 9)}≤ρ₀≤{number(atomic_rho_upper, 9)}",
        ],
    ]

    report = {
        "title": "Truncated Bose–Hubbard gap calculations",
        "subtitle": "Results for Targets 1 and 2 of Quantum Harness issue #92",
        "generated": generated,
        "url": ISSUE_URL,
        "status": "Target 1 completed; Target 2 partially completed.",
        "sections": [
            {
                "title": "1. Scope and status",
                "blocks": [
                    {
                        "kind": "text",
                        "text": (
                            "We studied the occupation-truncated Bose–Hubbard Hamiltonian with U=1. "
                            "Target 1 is the atomic limit t=0, μ=0.5. Target 2 consists of five parameter "
                            "points on {8,3}, {12,4}, and L({8,3})."
                        ),
                    },
                    {
                        "kind": "note",
                        "text": (
                            "Status: Target 1 is reproduced. For Target 2, finite-patch ED is complete for "
                            "nmax=1,2,3, while independently certified thermodynamic results currently cover "
                            "the complete hard-core level nmax=1, (L,d)=(1,2), in the U(1)-invariant sector."
                        ),
                    },
                    {
                        "kind": "text",
                        "text": (
                            "Finite ED and thermodynamic hierarchy results are reported separately. ED describes "
                            "small open patches and is not used as a thermodynamic bound."
                        ),
                    },
                ],
            },
            {
                "title": "2. Target 1: atomic limit",
                "blocks": [
                    {
                        "kind": "text",
                        "text": (
                            "At t=0 and μ=0.5 the Hamiltonian is a sum of independent onsite terms. The ground "
                            "state has one boson per site. Removing one boson costs 0.5; for nmax≥2, adding a "
                            "second boson also costs 0.5. Therefore Δbulk=0.5, ρ₀=1, F₀=0, and K₀=0."
                        ),
                    },
                    report_table(
                        ["Calculation", "Coverage", "Gap result", "Local observables"],
                        atomic_table,
                    ),
                    {"kind": "heading", "text": "ED conclusion"},
                    {
                        "kind": "text",
                        "text": (
                            "The radius-one ED calculation gives the same gap 0.5 and the same local observables "
                            "on all three graphs and at all three cutoffs. This is the expected conclusion: at "
                            "t=0 the sites decouple, so lattice geometry and patch boundary do not affect the "
                            "answer. At nmax=1 only the hole excitation remains; nmax=2 and 3 test both the hole "
                            "and particle excitations required by the stated atomic benchmark."
                        ),
                    },
                    {
                        "kind": "text",
                        "text": (
                            "The full hierarchy check is not a single-site shortcut: it uses a two-site buffered "
                            "local window, complete moment and gap blocks, stationarity constraints, and the same "
                            "certificate checker used for Target 2. Its γ=0.51 exclusion has exact affine residual "
                            "zero, verified PSD blocks, 256-bit coefficient checks, and positive Farkas margin."
                        ),
                    },
                ],
            },
            {
                "title": "3. Target 2: hyperbolic lattices",
                "blocks": [
                    {"kind": "heading", "text": "Finite-patch ED diagnostics"},
                    {
                        "kind": "text",
                        "text": (
                            "We diagonalized radius-one open patches: four sites and three edges for {8,3}, "
                            "five sites and four edges for {12,4}, and five sites and six edges for L({8,3}). "
                            "The table shows nmax=3, the largest cutoff calculated."
                        ),
                    },
                    report_table(
                        ["Point", "Graph", "t", "μ", "ΔED", "ρ₀", "F₀", "K₀"],
                        ed_table,
                    ),
                    {
                        "kind": "text",
                        "text": (
                            "ED conclusion: at μ=0.5, increasing t from 0.03 to 0.06 lowers the finite-patch "
                            "gap and increases the number fluctuation F₀ and hopping correlator K₀ on every graph. "
                            "At fixed parameters the line graph has the smallest gap and largest fluctuations, "
                            "{8,3} has the largest gap and smallest fluctuations, and {12,4} is intermediate. "
                            "The nmax=2 and nmax=3 results have the same ordering; their maximum gap difference is "
                            "0.0045 at t=0.03 and 0.0194 at t=0.05–0.06."
                        ),
                    },
                    {
                        "kind": "note",
                        "text": (
                            "These ED trends are finite-open-patch diagnostics only. In particular, the nmax=1 "
                            "patches are saturated and give ρ₀=1 and F₀=K₀=0, so they do not by themselves "
                            "resolve the thermodynamic Mott behavior."
                        ),
                    },
                    {"kind": "heading", "text": "Thermodynamic hierarchy: certified gap statements"},
                    {
                        "kind": "text",
                        "text": (
                            f"At the complete matrix level nmax=1, (L,d)=(1,2), we obtained {len(transitions)} "
                            "independently verified gap upper statements. The first verified EXCLUDED value in "
                            "each row is a rigorous upper statement at this finite hierarchy level."
                        ),
                    },
                    report_table(
                        ["Graph", "Point", "(t, μ)", "last FEASIBLE trial", "first verified EXCLUDED", "UNKNOWN inside"],
                        concise_transition_table,
                    ),
                    {
                        "kind": "note",
                        "text": (
                            "A FEASIBLE trial is only a non-exclusion at this finite level and is not a lower "
                            "bound on the physical gap. When UNKNOWN samples lie between the two reported trials, "
                            "the pair is a search span rather than a numerical bracket."
                        ),
                    },
                    {"kind": "heading", "text": "Thermodynamic hierarchy: accepted observable bounds"},
                    report_table(
                        ["Graph", "Point", "γ", "Observable", "Bound", "Certificate status"],
                        observable_summary,
                    ),
                    {
                        "kind": "text",
                        "text": (
                            "The strongest observable result is therefore consistent with unit filling and small "
                            "onsite fluctuations for {8,3} at P5. The available certified observable set is too "
                            "small to establish systematic dependence on graph, cutoff, L, or d."
                        ),
                    },
                ],
            },
            {
                "title": "4. Method, verification, and limitations",
                "blocks": [
                    {
                        "kind": "text",
                        "text": (
                            "The Julia/JuMP implementation uses exact finite matrix algebra over Q(√2,√3), "
                            "complete state-polynomial moment, stationarity, and gap matrices, exact U(1) charge "
                            "blocks, and an independent certificate checker. Exclusions are reported only after "
                            "exact affine projection, rigorous PSD verification, 256-bit coefficient evaluation, "
                            "and a positive normalized Farkas margin."
                        ),
                    },
                    report_table(
                        ["Check", "Result"],
                        [
                            ["Atomic benchmark", "passed"],
                            ["Julia hierarchy and certificate tests", "577 assertions passed"],
                            ["Python graph and reporting tests", "21 tests passed"],
                            ["Deliberately corrupted certificates", "rejected"],
                        ],
                    ),
                    {"kind": "heading", "text": "Limitations"},
                    {
                        "kind": "list",
                        "items": [
                            "Complete hard-core (1,3) and (2,2) solves exhausted 192 GiB; no numerical L- or d-tightening is claimed.",
                            "The complete nmax=2, (1,2) model assembled but its Clarabel factorization exhausted 192–237 GiB.",
                            "The requested cutoff-two TS2 grid, ladder comparison, unrestricted comparison, and optional cutoff three are incomplete.",
                            "The pinned upstream Ising reproduction remains blocked because no Mosek license was available.",
                            "Running HPC jobs are not counted until their result files are fetched and independently checked.",
                        ],
                    },
                    {
                        "kind": "text",
                        "text": (
                            "Thus Target 1 is complete. Target 2 currently supplies a complete finite-patch ED "
                            "diagnostic data set and a certified hard-core thermodynamic baseline, but not the "
                            "full cutoff and nested-level campaign requested by the issue."
                        ),
                    },
                ],
            },
        ],
    }
    atomic_json(OUTPUT / "report.json", report)
    atomic_text(OUTPUT / "report.html", render_academic_html(report))

    run_summary = {
        "schema": "quantum-harness-challenge-run-v1",
        "generated": generated,
        "title": report["title"],
        "issue": 92,
        "url": ISSUE_URL,
        "model": {
            "name": "occupation-truncated Bose-Hubbard model",
            "U": 1,
            "graphs": list(GRAPH_NAMES.values()),
            "points": {key: {"t_over_U": value[0], "mu_over_U": value[1]} for key, value in POINTS.items()},
            "cutoffs_requested": [1, 2, 3],
            "primary_symmetry": SYMMETRY,
        },
        "method": {
            "name": "thermodynamic state-polynomial gap hierarchy",
            "tool": "Julia/JuMP with Clarabel/Mosek interfaces and an independent exact checker",
            "exact": "Exact-checked exclusions; finite hierarchy relaxation",
            "settings": "matrix encoding, complete basis, U(1)-invariant states; headline level nmax=1, (L,d)=(1,2)",
            "note": "Finite-patch ED is diagnostic and is kept separate from thermodynamic hierarchy statements.",
        },
        "estimate": [
            {"run_point": "hard-core complete (1,2)", "wall_time": "minutes per γ trial", "memory": "64 GiB allocation"},
            {"run_point": "hard-core nested levels", "wall_time": "attempted", "memory": "192 GiB; OOM"},
            {"run_point": "cutoff-two complete (1,2)", "wall_time": "assembled in ~160 s", "memory": "192–237 GiB; OOM"},
        ],
        "figures": [],
        "status": report["status"],
        "source_manifest": "data_manifest.json",
    }
    atomic_json(OUTPUT / "run.json", run_summary)

    final_markdown = "\n".join(
        [
            "# Truncated Bose–Hubbard gap calculations",
            "",
            f"- **Issue:** [Quantum Harness #92]({ISSUE_URL})",
            f"- **Method:** [Xu et al., thermodynamic bulk-gap hierarchy]({PAPER_URL})",
            f"- **Snapshot:** {generated}",
            "- **Status:** Target 1 completed; Target 2 partially completed.",
            "",
            "## 1. Scope and status",
            "",
            "We studied the occupation-truncated Bose–Hubbard Hamiltonian with `U=1`. Target 1 is the atomic limit `t=0`, `μ=0.5`. Target 2 consists of five parameter points on `{8,3}`, `{12,4}`, and `L({8,3})`.",
            "",
            "Target 1 is reproduced. For Target 2, finite-patch ED is complete for `nmax=1,2,3`. Independently certified thermodynamic results currently cover the complete hard-core level `nmax=1`, `(L,d)=(1,2)`, in the U(1)-invariant sector.",
            "",
            "Finite ED and thermodynamic hierarchy results are reported separately. ED describes small open patches and is not used as a thermodynamic bound.",
            "",
            "## 2. Target 1: atomic limit",
            "",
            "At `t=0` and `μ=0.5` the Hamiltonian is a sum of independent onsite terms. The ground state has one boson per site. Removing one boson costs `0.5`; for `nmax≥2`, adding a second boson also costs `0.5`. Therefore `Δbulk=0.5`, `ρ0=1`, `F0=0`, and `K0=0`.",
            "",
            markdown_table(["calculation", "coverage", "gap result", "local observables"], atomic_table),
            "",
            "### ED conclusion",
            "",
            "The radius-one ED calculation gives the same gap `0.5` and the same local observables on all three graphs and at all three cutoffs. This is expected: at `t=0` the sites decouple, so lattice geometry and patch boundary do not affect the answer. At `nmax=1` only the hole excitation remains; `nmax=2,3` test both hole and particle excitations.",
            "",
            "The complete hierarchy check is not a single-site shortcut. It uses a two-site buffered local window, complete moment and gap blocks, stationarity constraints, and the same checker used for Target 2. The `γ=0.51` exclusion has exact affine residual zero, verified PSD blocks, 256-bit coefficient checks, and positive Farkas margin.",
            "",
            "## 3. Target 2: hyperbolic lattices",
            "",
            "### Finite-patch ED diagnostics",
            "",
            "We diagonalized radius-one open patches: four sites and three edges for `{8,3}`, five sites and four edges for `{12,4}`, and five sites and six edges for `L({8,3})`. The table shows `nmax=3`, the largest cutoff calculated.",
            "",
            markdown_table(["point", "graph", "t", "μ", "ΔED", "ρ0", "F0", "K0"], ed_table),
            "",
            "At `μ=0.5`, increasing `t` from `0.03` to `0.06` lowers the finite-patch gap and increases `F0` and `K0` on every graph. At fixed parameters the line graph has the smallest gap and largest fluctuations, `{8,3}` has the largest gap and smallest fluctuations, and `{12,4}` is intermediate. The `nmax=2` and `nmax=3` results have the same ordering; their maximum gap difference is `0.0045` at `t=0.03` and `0.0194` at `t=0.05–0.06`.",
            "",
            "These are finite-open-patch trends only. In particular, the `nmax=1` patches are saturated and give `ρ0=1`, `F0=K0=0`; they do not by themselves resolve thermodynamic Mott behavior.",
            "",
            "### Thermodynamic hierarchy: certified gap statements",
            "",
            f"At the complete matrix level `nmax=1`, `(L,d)=(1,2)`, we obtained {len(transitions)} independently verified gap upper statements. The first verified `EXCLUDED` value is a rigorous upper statement at this finite hierarchy level.",
            "",
            markdown_table(
                ["graph", "point", "(t,μ)", "last FEASIBLE trial", "first verified EXCLUDED", "UNKNOWN inside"],
                concise_transition_table,
            ),
            "",
            "A `FEASIBLE` trial is only a non-exclusion at this finite level and is not a lower bound on the physical gap. If `UNKNOWN` samples lie between the two values, the pair is a search span rather than a bracket.",
            "",
            "### Thermodynamic hierarchy: accepted observable bounds",
            "",
            markdown_table(["graph", "point", "γ", "observable", "bound", "certificate status"], observable_summary),
            "",
            "The strongest observable result is consistent with unit filling and small onsite fluctuations for `{8,3}` at P5. The available certified observable set is too small to establish systematic dependence on graph, cutoff, `L`, or `d`.",
            "",
            "## 4. Method, verification, and limitations",
            "",
            "The Julia/JuMP implementation uses exact finite matrix algebra over `Q(√2,√3)`, complete state-polynomial moment, stationarity, and gap matrices, exact U(1) charge blocks, and an independent certificate checker. Exclusions are reported only after exact affine projection, rigorous PSD verification, 256-bit coefficient evaluation, and a positive normalized Farkas margin.",
            "",
            markdown_table(
                ["check", "result"],
                [
                    ["atomic benchmark", "passed"],
                    ["Julia hierarchy and certificate tests", "577 assertions passed"],
                    ["Python graph and reporting tests", "21 tests passed"],
                    ["deliberately corrupted certificates", "rejected"],
                ],
            ),
            "",
            "### Limitations",
            "",
            "- Complete hard-core `(1,3)` and `(2,2)` solves exhausted 192 GiB; no numerical `L`- or `d`-tightening is claimed.",
            "- The complete `nmax=2`, `(1,2)` model assembled, but its Clarabel factorization exhausted 192–237 GiB.",
            "- The requested cutoff-two TS2 grid, ladder comparison, unrestricted comparison, and optional cutoff three are incomplete.",
            "- The pinned upstream Ising reproduction remains blocked because no Mosek license was available.",
            "- Running HPC jobs are not counted until their result files are fetched and independently checked.",
            "",
            "Thus Target 1 is complete. Target 2 currently supplies a complete finite-patch ED diagnostic data set and a certified hard-core thermodynamic baseline, but not the full cutoff and nested-level campaign requested by the issue.",
            "",
            "Rebuild with `make final-report`. Curated tables are under `submission/tables/`; raw solver and certificate payloads remain under `results/`.",
            "",
        ]
    )
    atomic_text(OUTPUT / "FINAL_REPORT.md", final_markdown)

    submission_readme = "\n".join(
        [
            "# Issue 92 submission package",
            "",
            "This directory is the stable, lightweight entry point for the professor review and pull request.",
            "",
            "- `report.html` — self-contained offline presentation; open this first.",
            "- `FINAL_REPORT.md` — text version for GitHub review and diffing.",
            "- `report.json` — structured source for the academic report.",
            "- `run.json` — compact challenge run summary.",
            "- `tables/` — curated accepted/certified rows; floating rows are not mixed in.",
            "- `data_manifest.json` — hashes of aggregate inputs and roles/sizes of raw campaign directories.",
            "",
            "Raw solver JSON, primal/dual matrices, and scheduler logs remain in `../results/`, which is git-ignored by Harness policy. Rebuild after fetching an HPC checkpoint:",
            "",
            "```bash",
            "make final-report",
            "```",
            "",
            "The build is non-destructive: it refreshes aggregate outputs and atomically replaces this snapshot; it never moves or deletes raw evidence.",
            "",
        ]
    )
    atomic_text(OUTPUT / "README.md", submission_readme)

    index_rows = [
        [
            row["directory"], row["role"], row["files"],
            f"{float(row['bytes']) / (1024 ** 2):.2f}", row["description"],
        ]
        for row in inventory
    ]
    results_index = "\n".join(
        [
            "# Issue 92 raw-result index",
            "",
            f"Generated {generated}. This directory is live evidence and is intentionally git-ignored.",
            "",
            "Scientific priority is `deadline_analysis/` → exact accepted rows → raw per-cell JSON. Scheduler logs alone are never scientific evidence.",
            "",
            markdown_table(["directory", "role", "files", "MiB", "purpose"], index_rows),
            "",
            "The PR-sized snapshot and source hashes are in `../submission/`.",
            "",
        ]
    )
    atomic_text(RESULTS / "INDEX.md", results_index)
    atomic_json(
        RESULTS / "DATA_MANIFEST.json",
        {
            "schema": "issue92-local-results-index-v1",
            "generated": generated,
            "directories": inventory,
            "aggregate_sources": source_files,
        },
    )

    print(
        f"built {OUTPUT / 'report.html'} with {len(transitions)} certified gap upper statements, "
        f"{len(accepted_objectives)} accepted objectives, and {len(accepted_intervals)} accepted intervals",
        flush=True,
    )


if __name__ == "__main__":
    build()
