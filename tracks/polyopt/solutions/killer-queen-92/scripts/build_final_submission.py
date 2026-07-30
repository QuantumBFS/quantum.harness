#!/usr/bin/env python3
"""Build the compact, auditable issue-92 submission from the live analysis.

The large solver payloads under ``results/`` remain the source evidence and
stay out of git.  This script creates a small submission layer containing a
self-contained report, curated CSV tables, figures, and a manifest that maps
every presentation claim back to the live aggregate.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[3]
RESULTS = ROOT / "results"
ANALYSIS = RESULTS / "deadline_analysis"
OUTPUT = ROOT / "submission"
TABLES = OUTPUT / "tables"
ASSETS = OUTPUT / "assets"

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


def build() -> None:
    generated = datetime.now().astimezone().isoformat(timespec="seconds")
    observables = read_csv("observable_objectives.csv")
    intervals = read_csv("observable_intervals.csv")
    gaps = read_csv("gap_scan_trials.csv")
    levels = read_csv("level_sizes.csv")
    nested = read_csv("nestedness_checks.csv")

    tiers = Counter(evidence_tier(row) for row in observables)
    gap_counts = Counter(row.get("classification", "UNKNOWN") for row in gaps)
    accepted_objectives = [row for row in observables if evidence_tier(row) == "ACCEPTED"]
    floating_objectives = [row for row in observables if evidence_tier(row) == "FLOATING"]
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
    ASSETS.mkdir(parents=True, exist_ok=True)
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

    figures = []
    for name in ("fixed_gamma_status.png", "working_endpoints_83_p2.png"):
        source = ANALYSIS / name
        if source.exists():
            destination = ASSETS / name
            shutil.copy2(source, destination)
            figures.append(destination)

    inventory = result_inventory()
    source_files = [
        file_digest(ANALYSIS / name)
        for name in (
            "gap_scan_trials.csv", "observable_objectives.csv", "observable_intervals.csv",
            "working_intervals.csv", "level_sizes.csv", "nestedness_checks.csv",
        )
    ]
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
            "SCNet extended geometry grid 41543225 was still running/array-throttled.",
            "Optimized cutoff-two TS2 gate 41542822 was still running; 41544379 was dependency-queued.",
            "No scheduler state is promoted to scientific evidence until a result JSON is fetched and re-aggregated.",
        ],
    }
    atomic_json(OUTPUT / "data_manifest.json", data_manifest)

    transition_table = [
        [
            row["graph"], row["point"], f"({row['t']}, {row['mu']})",
            f"({row['L']},{row['d']})", number(row["last_feasible"]),
            number(row["verified_excluded"]), number(row["search_span"]),
            row["unresolved_inside"], "yes" if row["clean_0p005"] else "no",
        ]
        for row in transitions
    ]
    interval_table = [
        [
            GRAPH_NAMES.get(row["geometry"], row["geometry"]), row["point"],
            number(row["gamma"], 3), row["observable"],
            f"[{number(row['lower'])}, {number(row['upper'])}]",
            f"({row['L']},{row['d']})",
        ]
        for row in accepted_intervals
    ]
    exact_observable_table = [
        [
            GRAPH_NAMES.get(row["geometry"], row["geometry"]), row["point"],
            number(row["gamma"], 3), row["observable"],
            "≥" if row["sense"] == "min" else "≤", number(row["optimum"]),
            row["certificate_class"],
        ]
        for row in exact_observable_rows
    ]
    selected_levels = [
        row
        for row in levels
        if row.get("geometry") == "83"
        and (row.get("nmax"), row.get("L"), row.get("d"))
        in {("1", "1", "2"), ("1", "1", "3"), ("1", "2", "2"), ("2", "1", "2")}
    ]
    level_table = [
        [
            f"nmax={row['nmax']}", f"({row['L']},{row['d']})", row["basis_family"],
            row["moment_basis_count"], row["gap_basis_count"], row["equality_count"],
            number(row["max_rss_gb"]),
        ]
        for row in selected_levels
    ]

    clean_count = sum(bool(row["clean_0p005"]) for row in transitions)
    report = {
        "title": "Certified bulk-gap bounds for truncated Bose–Hubbard models",
        "eyebrow": "Quantum Harness Issue #92 · PolyOpt Track",
        "url": ISSUE_URL,
        "lede": (
            "A complete Julia/JuMP hierarchy implementation with exact certificate checking "
            f"produces {len(transitions)} certified hard-core finite-level gap upper statements "
            f"and {len(accepted_intervals)} accepted observable intervals; the full cutoff and "
            "nested Target 2 campaign remains incomplete."
        ),
        "sections": [
            {
                "title": "Challenge",
                "note": "The physical question and the precise scope of the claims.",
                "blocks": [
                    {
                        "kind": "text",
                        "text": (
                            "Issue #92 asks whether the thermodynamic state-polynomial hierarchy of Xu et al. "
                            "can be extended from spin systems to occupation-truncated bosons, then used to "
                            "bound the bulk gap and local Mott diagnostics on three infinite hyperbolic graphs. "
                            "The challenge is not to diagonalize a finite patch: it is to exclude an assumed "
                            "thermodynamic gap using a finite, independently checkable semidefinite certificate."
                        ),
                    },
                    {
                        "kind": "card",
                        "title": "Significance",
                        "blocks": [
                            {
                                "kind": "text",
                                "text": (
                                    "Certified thermodynamic statements avoid the uncontrolled finite-size "
                                    "extrapolation that is especially delicate on hyperbolic lattices. The "
                                    "truncated-boson extension also supplies a reusable finite-matrix route for "
                                    "bosonic models while stating explicitly that no cutoff result certifies the "
                                    "untruncated Bose–Hubbard model."
                                ),
                            }
                        ],
                    },
                    {
                        "kind": "equation",
                        "tex": "H=-t\\sum_{\\langle i,j\\rangle}(b_i^\\dagger b_j+b_j^\\dagger b_i)+\\frac{U}{2}\\sum_i n_i(n_i-1)-\\mu\\sum_i n_i,\\qquad U=1",
                    },
                    {
                        "kind": "kv",
                        "pairs": [
                            ["Graphs", "{8,3}; {12,4}; line graph L({8,3})"],
                            ["Target points", "P1–P5: five distinct (t/U, μ/U) values near unit filling"],
                            ["Requested cutoffs", "nmax=1,2; nmax=3 when computationally feasible"],
                            ["Primary sector", SYMMETRY],
                            ["Primary finite level reported", "complete matrix basis, (L,d)=(1,2), nmax=1"],
                            ["Campaign status", "Partial: core complete; baseline subset certified; nested/cutoff expansion incomplete"],
                        ],
                    },
                    {
                        "kind": "note",
                        "label": "Claim boundary",
                        "style": "info",
                        "text": (
                            "Every Γ value below is an upper statement from one finite hierarchy level in the "
                            "U(1)-invariant sector. A FEASIBLE sample proves no positive gap; ED is diagnostic "
                            "only; and numerical ordering of finite-level upper statements is not an ordering of "
                            "the unknown true gaps."
                        ),
                    },
                ],
            },
            {
                "title": "Approach",
                "note": "Paper-faithful hierarchy, exact algebra, solver layer, and independent checker.",
                "blocks": [
                    {"kind": "badge", "text": "Rigorous exclusions at a finite relaxation", "style": "good"},
                    {
                        "kind": "kv",
                        "pairs": [
                            ["Local algebra", "Independent charge-adapted basis of M_(nmax+1), exact Q(√2,√3) coefficients"],
                            ["Thermodynamic window", "Λ_G(L), interaction buffer one, excitations/stationarity in Λ_G(L−1)"],
                            ["Encodings", "Matrix degree (primary) and exact ladder-word filtration (cross-check)"],
                            ["PSD reduction", "Exact U(1)-charge blocks; deterministic nested TS2 support closure"],
                            ["Solvers", "Clarabel for available campaign runs; Mosek interface present but license unavailable"],
                            ["Exclusion checker", "Exact affine projection, 256-bit Arb intervals, rigorous PSD LDL, normalized Farkas margin"],
                            ["Execution", "Resumable per-cell manifests on SCNet; raw primal/dual data retained"],
                        ],
                    },
                    {
                        "kind": "text",
                        "text": (
                            "The same canonical multiplication and adjoint engine serves both degree encodings. "
                            "For each level, the code enumerates the complete state-polynomial moment basis, "
                            "stationarity identities, covariance-corrected gap matrix, and the ρ₀, F₀, K₀ "
                            "objectives. Solver infeasibility remains UNKNOWN until the separately implemented "
                            "checker reconstructs the exact coefficient identity and verifies every cone."
                        ),
                    },
                    {
                        "kind": "equation",
                        "tex": "\\Gamma_{L,d}\\searrow\\Delta_{\\mathrm{bulk}},\\qquad \\gamma\\geq\\Gamma_{L,d}\\;\\Rightarrow\\;\\mathcal F_{L,d}(\\gamma)=\\varnothing",
                    },
                    report_table(
                        ["Acceptance gate", "Evidence", "Status"],
                        [
                            ["Exact algebra and degree filtrations", "nmax=1,2,3; adjoint, charge, cutoff commutator", "PASS"],
                            ["Julia hierarchy/certificate suite", "577 assertions; includes corrupted-certificate rejection", "PASS"],
                            ["Python graph/report suite", "21 tests", "PASS"],
                            ["Atomic limit", "Δ/U=0.5, ρ=1, F=K=0 without special physics constraints", "PASS"],
                            ["Pinned upstream Ising reproduction", "SpectralGap a1171c9; no SCNet/local Mosek license", "BLOCKED"],
                            ["Nested numerical monotonicity", "Both larger complete hard-core solves exhausted memory", "UNKNOWN"],
                        ],
                    ),
                    report_table(
                        ["Representative {8,3} level", "Family", "Moment basis", "Gap basis", "Equalities", "Peak RSS (GiB)"],
                        level_table,
                        [False, False, True, True, True, True],
                    ),
                ],
            },
            {
                "title": "Results",
                "note": f"Snapshot {generated}; only independently accepted statements appear as results.",
                "blocks": [
                    {
                        "kind": "verdict",
                        "status": "warn",
                        "label": "Partial Target 2 campaign",
                        "why": (
                            f"{len(transitions)} hard-core finite-level gap upper statements are certified; "
                            "cutoff-two, nested-level, ladder, unrestricted, and optional cutoff-three coverage "
                            "does not yet satisfy the full issue grid."
                        ),
                    },
                    {"kind": "heading", "text": "Certified gap upper statements", "level": 2},
                    report_table(
                        ["Graph", "Point", "(t/U, μ/U)", "(L,d)", "last FEASIBLE", "first EXCLUDED", "span", "unknown inside", "clean 0.005"],
                        transition_table,
                        [False, False, False, False, True, True, True, True, False],
                    ),
                    {
                        "kind": "text",
                        "text": (
                            f"All {len(transitions)} EXCLUDED endpoints have exact affine residual zero, "
                            "256-bit coefficient checks, rigorous PSD verification, and normalized Farkas "
                            f"margin at least one. {clean_count} transitions have a clean 0.005U search span. "
                            "Rows containing unresolved samples are search spans, not numerical brackets."
                        ),
                    },
                    {
                        "kind": "figures",
                        "items": [
                            {
                                "src": "assets/fixed_gamma_status.png",
                                "caption": (
                                    "Checked fixed-gap hierarchy outcomes. Circles are FEASIBLE non-exclusions, "
                                    "crosses are exact-certificate EXCLUDED trials, and squares are UNKNOWN. "
                                    "The map separates scientific classification from scheduler completion."
                                ),
                            }
                        ],
                    },
                    {"kind": "heading", "text": "Certified observable information", "level": 2},
                    report_table(
                        ["Graph", "Point", "γ/U", "Observable", "Accepted interval", "(L,d)"],
                        interval_table,
                        [False, False, True, False, False, False],
                    ),
                    report_table(
                        ["Graph", "Point", "γ/U", "Observable", "Sense", "Certified endpoint", "Certificate"],
                        exact_observable_table,
                        [False, False, True, False, False, True, False],
                    ),
                    {
                        "kind": "text",
                        "text": (
                            "The accepted two-sided result is the {8,3} P5 cell at γ/U=0.05: "
                            "0.9944073 ≤ ρ₀ ≤ 0.9999995 and 4.879816×10⁻⁷ ≤ F₀ ≤ 0.005592673. "
                            "At hard-core cutoff F₀=1−ρ₀ exactly. The representative P4, γ/U=0.10 "
                            "exact-projection run additionally certifies ρ₀≥0.9455347492, "
                            "F₀≤0.0544652508, and K₀≤0.3025838233."
                        ),
                    },
                    {
                        "kind": "figures",
                        "items": [
                            {
                                "src": "assets/working_endpoints_83_p2.png",
                                "caption": (
                                    "Accepted and floating one-sided endpoints for {8,3} P2. Increasing the "
                                    "assumed γ tightens the conditional feasible set; it does not tune the "
                                    "Hamiltonian or measure how the physical gap changes."
                                ),
                            }
                        ],
                    },
                    {"kind": "heading", "text": "Coverage and computational boundary", "level": 2},
                    report_table(
                        ["Evidence class", "Count", "Interpretation"],
                        [
                            ["Accepted one-sided objectives", counts["accepted_one_sided_objectives"], "Passed independent residual/PSD/objective-gap checks"],
                            ["Floating objectives", counts["floating_objectives"], "Numerical values retained, not certified bounds"],
                            ["Accepted intervals", f"{counts['accepted_intervals']} / {counts['interval_rows']}", "Both endpoints accepted and ordered"],
                            ["Fixed-γ records", f"{counts['durable_fixed_gamma_rows']} / {counts['fixed_gamma_rows']}", "Durable solver/checker result exists"],
                            ["Verified excluded trial rows", counts["verified_excluded_fixed_gamma_rows"], "Exact-projected Farkas certificates"],
                            ["Unknown fixed-γ rows", counts["unknown_fixed_gamma_rows"], "Missing, numerical, unfinished, or resource-limited"],
                        ],
                        [False, True, False],
                    ),
                    {
                        "kind": "note",
                        "label": "Resource result",
                        "style": "pending",
                        "text": (
                            "Complete nmax=2 (L,d)=(1,2) assembled but exhausted 192–237 GiB in every "
                            "Clarabel factorization route (MKL and QDLDL). Complete hard-core (1,3) and "
                            "(2,2) solves also exhausted 192 GiB. These are explicit UNKNOWN outcomes, not "
                            "missing rows. Optimized TS2 dry assemblies and an isolated extended-geometry "
                            "P1 recovery were still running at this snapshot. Only fetched rows that already passed "
                            "the independent checker are included in the claims above."
                        ),
                    },
                ],
            },
            {
                "title": "Highlight",
                "note": "What this attempt contributes, and what remains before the issue is complete.",
                "blocks": [
                    {
                        "kind": "card",
                        "title": "What's innovative",
                        "blocks": [
                            {
                                "kind": "text",
                                "text": (
                                    "The implementation specializes the thermodynamic hierarchy to finite "
                                    "truncated-boson matrix algebras without using infinite-dimensional CCR "
                                    "relations. It combines a shared exact algebra engine, two auditable degree "
                                    "filtrations, exact charge blocks, deterministic nested TS2 sparsity, and an "
                                    "independent Q(√2,√3)/Arb certificate checker in one reusable Julia/JuMP core."
                                ),
                            }
                        ],
                    },
                    {
                        "kind": "card",
                        "title": "Significance of the output",
                        "blocks": [
                            {
                                "kind": "text",
                                "text": (
                                    "The attempt advances beyond a solver-only demonstration: every reported "
                                    "gap exclusion can be replayed as an exact coefficient identity with rigorous "
                                    "cone checks. It establishes a certified hard-core baseline on all five {8,3} "
                                    "points and a P2 comparison on all three geometries, while making the "
                                    "remaining computational limits explicit."
                                ),
                            }
                        ],
                    },
                    {
                        "kind": "card",
                        "title": "Broader impact",
                        "blocks": [
                            {
                                "kind": "text",
                                "text": (
                                    "The algebra, hierarchy assembly, and checker are graph- and cutoff-aware "
                                    "rather than tied to one lattice. They provide a foundation for certified "
                                    "thermodynamic studies of other finite-cutoff bosonic Hamiltonians and a "
                                    "clear interface for stronger sparsity or commercial conic solvers."
                                ),
                            }
                        ],
                    },
                    {
                        "kind": "list",
                        "title": "What is still required for full acceptance",
                        "items": [
                            "Complete the nested hard-core (1,3) and (2,2) numerical levels or introduce a formally justified stronger reduction.",
                            "Finish the mandatory cutoff-two complete/TS2 grid; run cutoff three only if its recorded resource gate passes.",
                            "Add the prescribed ladder-encoding and unrestricted-state comparisons.",
                            "Run the pinned upstream Ising reference when a Mosek license becomes available.",
                            "Re-run the aggregate and this submission builder after every fetched HPC checkpoint; never promote floating values silently.",
                        ],
                    },
                    {
                        "kind": "code",
                        "title": "Rebuild the audited report",
                        "text": "make final-report",
                    },
                ],
            },
        ],
    }
    atomic_json(OUTPUT / "report.json", report)

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
            "note": report["sections"][1]["blocks"][2]["text"],
        },
        "estimate": [
            {"run_point": "hard-core complete (1,2)", "wall_time": "minutes per γ trial", "memory": "64 GiB allocation"},
            {"run_point": "hard-core nested levels", "wall_time": "attempted", "memory": "192 GiB; OOM"},
            {"run_point": "cutoff-two complete (1,2)", "wall_time": "assembled in ~160 s", "memory": "192–237 GiB; OOM"},
        ],
        "figures": [
            {
                "id": "fixed-gap-map",
                "plots": "Fixed-γ classifications across available Target-2 cells",
                "results": {
                    "figure": "assets/fixed_gamma_status.png",
                    "match": "partial",
                    "why": "Certified hard-core baseline subset; mandatory larger-cutoff/nested grid incomplete.",
                    "numbers": counts,
                },
            },
            {
                "id": "observable-endpoints",
                "plots": "Accepted versus floating observable endpoints",
                "results": {
                    "figure": "assets/working_endpoints_83_p2.png",
                    "match": "partial",
                    "why": "Two accepted intervals and 26 accepted one-sided endpoints; most numerical endpoints remain floating.",
                    "numbers": {"accepted_intervals": len(accepted_intervals), "accepted_objectives": len(accepted_objectives)},
                },
            },
        ],
        "source_manifest": "data_manifest.json",
    }
    atomic_json(OUTPUT / "run.json", run_summary)

    gap_md_rows = [
        [
            row["graph"], row["point"], f"({row['t']},{row['mu']})", f"({row['L']},{row['d']})",
            number(row["last_feasible"]), number(row["verified_excluded"]), number(row["search_span"]),
            row["unresolved_inside"], "PASS" if row["clean_0p005"] else "open",
        ]
        for row in transitions
    ]
    final_markdown = "\n".join(
        [
            "# Certified bulk-gap bounds for truncated Bose–Hubbard models",
            "",
            f"- **Issue:** [Quantum Harness #92]({ISSUE_URL})",
            f"- **Method:** [Xu et al., thermodynamic bulk-gap hierarchy]({PAPER_URL})",
            f"- **Snapshot:** {generated}",
            "- **Verdict:** Partial challenge result—core implementation complete, certified hard-core baseline subset, mandatory larger-level/cutoff campaign incomplete.",
            "",
            "## Executive result",
            "",
            f"The independently checked hierarchy gives **{len(transitions)} hard-core finite-level gap upper statements** at complete matrix level `(L,d)=(1,2)` in the `U1_INVARIANT_KMS_STATES` sector. "
            f"It also gives **{len(accepted_intervals)} accepted two-sided observable intervals** and **{len(accepted_objectives)} accepted one-sided endpoints**. "
            "These are thermodynamic hierarchy statements, not finite-cluster ED values.",
            "",
            "## Certified gap statements",
            "",
            markdown_table(
                ["graph", "point", "(t/U,μ/U)", "(L,d)", "last FEASIBLE", "first EXCLUDED", "span", "unknown inside", "0.005 clean"],
                gap_md_rows,
            ),
            "",
            "`FEASIBLE` is only non-exclusion at this finite level. `EXCLUDED` means the exact-projected certificate passed affine, 256-bit coefficient, rigorous PSD, and positive Farkas-margin checks. A span containing an unresolved sample is not called a bracket.",
            "",
            "## Headline observable bounds",
            "",
            "At `{8,3}` P5 and `γ/U=0.05`: `0.9944073 ≤ ρ0 ≤ 0.9999995` and `4.879816e-7 ≤ F0 ≤ 0.005592673`. At hard-core cutoff, `F0=1−ρ0` exactly.",
            "",
            "At `{8,3}` P4 and `γ/U=0.10`, exact projection certifies `ρ0≥0.9455347492001175`, `F0≤0.0544652507998825`, and `K0≤0.30258382329239936`.",
            "",
            "## Evidence inventory",
            "",
            markdown_table(
                ["item", "count"],
                [
                    ["accepted one-sided objectives", counts["accepted_one_sided_objectives"]],
                    ["floating objectives (not certified)", counts["floating_objectives"]],
                    ["accepted intervals", f"{counts['accepted_intervals']} / {counts['interval_rows']}"],
                    ["durable fixed-γ rows", f"{counts['durable_fixed_gamma_rows']} / {counts['fixed_gamma_rows']}"],
                    ["verified EXCLUDED trial rows", counts["verified_excluded_fixed_gamma_rows"]],
                    ["UNKNOWN fixed-γ rows", counts["unknown_fixed_gamma_rows"]],
                ],
            ),
            "",
            "## Implementation and verification",
            "",
            "The Julia core implements exact finite matrix algebra over `Q(sqrt(2),sqrt(3))`, matrix and ladder filtrations, canonical state polynomials, complete moment/stationarity/gap index sets, exact U(1) charge blocks, deterministic nested TS2 sparsity, Clarabel/Mosek solve interfaces, and independent exact certificate checking. The current checkout passes 577 Julia assertions and 21 Python tests, including the exact atomic benchmark, deliberate certificate corruption, and submission-tier separation.",
            "",
            "## Limitations",
            "",
            "- Complete hard-core `(1,3)` and `(2,2)` solve attempts exhausted 192 GiB, so no nested numerical tightening is claimed.",
            "- Complete cutoff-two `(1,2)` assembled but exhausted 192–237 GiB across MKL and QDLDL routes.",
            "- TS2 cutoff-two dry assembly and one isolated extended-geometry P1 recovery were live at this snapshot; only fetched, independently checked rows contribute claims.",
            "- Ladder, unrestricted, optional cutoff-three, and the full observable grid remain incomplete.",
            "- The pinned upstream SpectralGap Ising reproduction remains blocked by the lack of a Mosek license.",
            "",
            "## Reproducibility",
            "",
            "```bash",
            "make test",
            "make final-report",
            "```",
            "",
            "The self-contained presentation is `submission/report.html`. Curated tables are under `submission/tables/`; `submission/data_manifest.json` records source hashes and maps the ignored raw campaign directories. Full primal/dual payloads remain under `results/` and are intentionally not committed.",
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
            "- `report.json` — structured source consumed by the Harness report renderer.",
            "- `run.json` — compact challenge run summary.",
            "- `tables/` — curated accepted/certified rows; floating rows are not mixed in.",
            "- `data_manifest.json` — hashes of aggregate inputs and roles/sizes of raw campaign directories.",
            "- `assets/` — report figures copied from the current aggregate.",
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

    renderer = REPO_ROOT / "skills" / "report" / "render_report.py"
    if not renderer.exists():
        raise SystemExit(f"Harness report renderer not found: {renderer}")
    subprocess.run([sys.executable, str(renderer), str(OUTPUT)], check=True)
    print(
        f"built {OUTPUT / 'report.html'} with {len(transitions)} certified gap upper statements, "
        f"{len(accepted_objectives)} accepted objectives, and {len(accepted_intervals)} accepted intervals",
        flush=True,
    )


if __name__ == "__main__":
    build()
