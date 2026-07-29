#!/usr/bin/env python3
"""Build a deterministic provenance record for the completed challenge analysis."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _git_value(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _repo_root(path: Path) -> Path:
    value = _git_value(["rev-parse", "--show-toplevel"], path)
    return Path(value) if value else path


def _numeric_row(row: dict[str, str]) -> dict[str, Any]:
    integers = {
        "Lmin",
        "point_count",
        "size_count",
        "dof",
        "bootstrap_requested",
        "bootstrap_successful",
        "bootstrap_failed",
    }
    booleans = {
        "drop_largest",
        "converged",
        "boundary_contact",
        "h_c_inside_scan",
        "inside_field_scan",
    }
    result: dict[str, Any] = {}
    for name, value in row.items():
        if name in integers:
            result[name] = int(value)
        elif name in booleans:
            result[name] = value.lower() == "true"
        else:
            try:
                parsed = float(value)
                result[name] = parsed if math.isfinite(parsed) else None
            except ValueError:
                result[name] = value
    return result


def _scan_axes(cells: list[dict[str, str]]) -> dict[str, Any]:
    axes = {}
    for lattice in ("triangular", "honeycomb"):
        selected = [row for row in cells if row["lattice"] == lattice]
        axes[lattice] = {
            "sizes": sorted({int(row["L"]) for row in selected}),
            "fields": sorted({float(row["hTrfd"]) for row in selected}),
            "requested_Dltau": sorted({float(row["FixedDltau"]) for row in selected}),
            "actual_Dltau_range": [
                min(float(row["Dltau"]) for row in selected),
                max(float(row["Dltau"]) for row in selected),
            ],
            "cell_count": len(selected),
        }
    return axes


def _runtime_estimates(analysis_dir: Path, run_ids: list[str]) -> list[dict[str, Any]]:
    totals: dict[str, dict[str, float]] = defaultdict(
        lambda: {"cells": 0.0, "cell_wall_seconds": 0.0, "core_hours": 0.0, "max_cell_seconds": 0.0}
    )
    for run_id in run_ids:
        for path in sorted((analysis_dir.parent / run_id / "cells").glob("cell-*/manifest.json")):
            manifest = json.loads(path.read_text(encoding="utf-8"))
            lattice = str(manifest["actual_parameters"]["lattice"])
            wall = float(manifest["runtime"]["wall_time_seconds"])
            nprocs = int(manifest["runtime"]["mpi_size"])
            totals[lattice]["cells"] += 1
            totals[lattice]["cell_wall_seconds"] += wall
            totals[lattice]["core_hours"] += wall * nprocs / 3600.0
            totals[lattice]["max_cell_seconds"] = max(
                totals[lattice]["max_cell_seconds"], wall
            )
    estimates = []
    for lattice in sorted(totals):
        values = totals[lattice]
        estimates.append(
            {
                "run_point": f"{lattice} scan ({int(values['cells'])} cells)",
                "wall_time": (
                    f"{values['cell_wall_seconds'] / 3600.0:.1f} aggregate cell-hours; "
                    f"{values['max_cell_seconds'] / 3600.0:.2f} h slowest cell"
                ),
                "memory": "one full Markov chain per MPI rank; peak RSS unavailable from scheduler",
                "core_hours": values["core_hours"],
            }
        )
    return estimates


def _artifact_hashes(analysis_dir: Path) -> dict[str, str]:
    paths = []
    for pattern in ("*.csv", "*.json", "figures/*.png", "figures/*.pdf"):
        paths.extend(analysis_dir.glob(pattern))
    excluded = {"run.json", "report.json"}
    return {
        str(path.relative_to(analysis_dir)): _sha256(path)
        for path in sorted(set(paths))
        if path.name not in excluded
    }


def build_run(analysis_dir: Path) -> dict[str, Any]:
    analysis_dir = analysis_dir.resolve()
    repo_root = _repo_root(analysis_dir)
    inventory = json.loads((analysis_dir / "raw_inventory.json").read_text(encoding="utf-8"))
    audit = json.loads((analysis_dir / "audit.json").read_text(encoding="utf-8"))
    final = json.loads((analysis_dir / "final_results.json").read_text(encoding="utf-8"))
    cells = _read_csv(analysis_dir / "cells.csv")
    fits = [_numeric_row(row) for row in _read_csv(analysis_dir / "finite_size_fits.csv")]
    sensitivities = [
        _numeric_row(row)
        for row in _read_csv(analysis_dir / "finite_size_sensitivities.csv")
    ]
    dtau_rows = [_numeric_row(row) for row in _read_csv(analysis_dir / "dtau_fits.csv")]
    summary = audit["summary"]
    unique_settings = {
        name: sorted({int(row[name]) for row in cells})
        for name in ("nprocs", "nWarm", "NmBin", "NSwep", "NmMeaConfg")
    }
    figure_specs = [
        (
            "binder-triangular",
            "Triangular-lattice Binder curves",
            "figures/binder_Q_triangular.png",
            "warn",
            "Largest-size points miss the declared SEM target and the fitted critical field lies beyond the measured field window.",
        ),
        (
            "binder-honeycomb",
            "Honeycomb-lattice Binder curves",
            "figures/binder_Q_honeycomb.png",
            "warn",
            "Curves cross in the measured window, but finite-size variants are not stable to five decimals.",
        ),
        (
            "data-collapse",
            "Finite-size data collapse",
            "figures/data_collapse.png",
            "warn",
            "The correction-adjusted Binder data follow the declared scaling function, while residuals and fit variants remain wider than the fifth-decimal target.",
        ),
        (
            "finite-size-stability",
            "Finite-size fit stability",
            "figures/finite_size_fit_stability.png",
            "warn",
            "The a2 model is the minimum adequate family, while adjacent size cuts and correction terms exceed the fifth-decimal target.",
        ),
        (
            "dtau-extrapolation",
            "Actual time-step-squared extrapolation",
            "figures/dtau2_extrapolation.png",
            "warn",
            "Most step-specific estimates require field extrapolation; the two-stage and joint fits disagree beyond the target precision.",
        ),
        (
            "ratio",
            "Critical-field ratio compared with sqrt(5)",
            "figures/ratio_vs_sqrt5.png",
            "warn",
            "The interval contains sqrt(5), but its width is about two orders of magnitude above the challenge target.",
        ),
    ]
    figures = [
        {
            "id": identifier,
            "plots": title,
            "src": source,
            "results": {
                "match": status,
                "why": why,
                "numbers": (
                    final["ratio"] if identifier == "ratio" else {}
                ),
            },
        }
        for identifier, title, source, status, why in figure_specs
    ]
    record = {
        "schema_version": 1,
        "run_id": analysis_dir.name,
        "title": "Harnessing Quantum Challenge #148: transverse-field Ising critical-field ratio",
        "paper": {
            "title": "Cluster Monte Carlo simulation of the transverse Ising model",
            "doi": "10.1103/PhysRevE.66.066110",
            "reference_values": final["pre_comparison"],
        },
        "model": {
            "hamiltonian": "H = J1 sum_<i,j> sigma_z_i sigma_z_j - hTrfd sum_i sigma_x_i",
            "J1": -1.0,
            "J2": 0.0,
            "boundary": "periodic",
            "lattices": ["triangular", "honeycomb"],
            "BetaT_rule": "L/hTrfd",
            "observable": "Q = <m^2>^2/<m^4>",
        },
        "method": {
            "name": "discrete-imaginary-time cluster Monte Carlo for the transverse-field Ising model",
            "tool": "Julia, MPI.jl, independent Markov chains",
            "exact": False,
            "note": (
                "Local Metropolis and ordinary Wolff cluster updates were sampled "
                "with deterministic rank seeds. Critical fields use fixed exponents "
                "yt=1.587 and yi=-0.815, bin-level bootstrap, and an actual-Dltau^2 "
                "extrapolation."
            ),
            "settings": unique_settings,
        },
        "scan": _scan_axes(cells),
        "audit": {
            **summary,
            "quality_override_decision": "keep all 177 integrity-valid cells",
            "selection_sha256": json.loads(
                (analysis_dir / "accepted_cells.json").read_text(encoding="utf-8")
            )["selection_payload_sha256"],
        },
        "finite_size": {
            "yt": 1.587,
            "yi": -0.815,
            "primary_terms": ["a2"],
            "primary_Lmin": 16,
            "variants": fits,
            "sensitivities": sensitivities,
        },
        "time_step": {
            "independent_variable": "actual Dltau squared",
            "step_variants": [
                row for row in dtau_rows if row["record_type"] == "step"
            ],
            "extrapolations": [
                row for row in dtau_rows if row["record_type"] != "step"
            ],
        },
        "results": final,
        "verification": {
            "finite_size_fifth_decimal_stable": final["fifth_decimal_stability"]["pass"],
            "precision_targets_pass": all(
                item["precision_target_pass"]
                for item in final["critical_fields"].values()
            )
            and final["ratio"]["precision_target_pass"],
            "sqrt5_verdict": final["ratio"]["sqrt5_verdict"],
            "residual_uncertainties": final["limitations"],
        },
        "estimate": _runtime_estimates(analysis_dir, inventory["run_ids"]),
        "figures": figures,
        "commands": [
            "python tracks/qmc/solutions/Only-team/scripts/audit_challenge_results.py --run-dir <each-raw-run> --output-dir <analysis-dir> --write-ratified-selection",
            "python tracks/qmc/solutions/Only-team/scripts/assemble_challenge_dataset.py --run-dir <each-raw-run> --output-dir <analysis-dir>",
            "python tracks/qmc/solutions/Only-team/scripts/fit_binder_scaling.py --cells <analysis-dir>/cells.csv --bins <analysis-dir>/bins.csv --output-dir <analysis-dir> --bootstrap 2000 --seed 20260729",
            "python tracks/qmc/solutions/Only-team/scripts/extrapolate_dtau.py --cells <analysis-dir>/cells.csv --bins <analysis-dir>/bins.csv --output-dir <analysis-dir> --bootstrap 2000 --seed 20260731 --finite-size-fits <analysis-dir>/finite_size_fits.csv --finite-size-sensitivities <analysis-dir>/finite_size_sensitivities.csv",
            "python tracks/qmc/solutions/Only-team/scripts/plot_challenge_results.py --cells <analysis-dir>/cells.csv --finite-size-fits <analysis-dir>/finite_size_fits.csv --dtau-fits <analysis-dir>/dtau_fits.csv --final-results <analysis-dir>/final_results.json --output-dir <analysis-dir>/figures",
        ],
        "provenance": {
            "raw_inventory_sha256": _sha256(analysis_dir / "raw_inventory.json"),
            "raw_run_spec_hashes": inventory["run_spec_hashes"],
            "raw_manifest_count": inventory["manifest_count"],
            "scheduler_job_ids": inventory["scheduler_job_ids"],
            "git_commit": _git_value(["rev-parse", "HEAD"], repo_root),
            "git_branch": _git_value(["branch", "--show-current"], repo_root),
            "python_version": platform.python_version(),
            "julia_version": "1.12.6",
            "artifact_sha256": _artifact_hashes(analysis_dir),
        },
    }
    return record


def build_report(run: dict[str, Any], *, draft: bool = True) -> dict[str, Any]:
    results = run["results"]
    triangular = results["critical_fields"]["triangular"]
    honeycomb = results["critical_fields"]["honeycomb"]
    ratio = results["ratio"]
    estimate_rows = [
        [item["run_point"], item["wall_time"], item["memory"]]
        for item in run["estimate"]
    ]
    report = {
        "title": "Challenge #148: Is the critical-field ratio exactly √5?",
        "eyebrow": "QMC TRACK · DRAFT FOR REVIEW" if draft else "QMC TRACK",
        "url": "https://doi.org/10.1103/PhysRevE.66.066110",
        "lede": (
            "A fully audited cluster-QMC scan is statistically compatible with √5, "
            "but its field coverage and systematic uncertainty do not support a "
            "fifth-decimal claim."
        ),
        "sections": [
            {
                "title": "Challenge",
                "blocks": [
                    {
                        "kind": "text",
                        "text": (
                            "We study the transverse-field Ising model on triangular "
                            "and honeycomb lattices and test whether "
                            "$h_c^{tri}/h_c^{hon}=\\sqrt{5}$. The calculation extends "
                            "to triangular $L=48$ and honeycomb $L=32$, using the "
                            "Binder moment ratio, finite-size scaling, and an "
                            "actual-$\\Delta\\tau^2$ extrapolation."
                        ),
                    },
                    {
                        "kind": "card",
                        "title": "Significance",
                        "blocks": [
                            {
                                "kind": "text",
                                "text": (
                                    "The proposed √5 relation has no known analytic "
                                    "derivation, so resolving it requires both high "
                                    "statistical precision and controlled finite-size "
                                    "and time-step limits. A negative precision result "
                                    "is informative when every limitation is quantified "
                                    "instead of absorbed into a narrow error bar."
                                ),
                            }
                        ],
                    },
                    {
                        "kind": "kv",
                        "pairs": [
                            ["Paper", "Phys. Rev. E 66, 066110 (2002)"],
                            ["Track", "Quantum Monte Carlo — Challenge #148"],
                            ["Target", "h_c(triangular) / h_c(honeycomb) versus √5"],
                            ["System sizes", "Triangular L=8–48; honeycomb L=10–32"],
                        ],
                    },
                ],
            },
            {
                "title": "Approach",
                "blocks": [
                    {
                        "kind": "badge",
                        "style": "warn",
                        "text": "Approximate: finite size and discrete imaginary time",
                    },
                    {
                        "kind": "kv",
                        "pairs": [
                            [
                                "Method",
                                "Discrete-imaginary-time cluster Monte Carlo for the transverse-field Ising model",
                            ],
                            ["Tool", "Julia + MPI.jl, 32 independent Markov chains"],
                            [
                                "Hamiltonian",
                                "H = J1 Σ⟨i,j⟩ σᶻᵢσᶻⱼ − h Σᵢσˣᵢ; J1=−1, J2=0",
                            ],
                            [
                                "Sampling",
                                "nWarm=10000, NmBin=32, NSwep=2000, nLocal=1, nWolff=5",
                            ],
                            [
                                "Scaling",
                                "yt=1.587, yi=−0.815; 64 declared model variants; 2000 bin bootstraps",
                            ],
                        ],
                    },
                    {
                        "kind": "text",
                        "text": (
                            "All 177 cells passed manifest, hash, seed, bin-count, "
                            "finiteness, and Binder-formula checks. The primary scaling "
                            "family was fixed before computing the √5 offset: it keeps "
                            "the leading irrelevant correction and adds the field "
                            "quadratic term required by fit quality. Requested time "
                            "steps 0.013, 0.016, and 0.020 are analyzed with each "
                            "cell's actual $\\Delta\\tau$."
                        ),
                    },
                    {
                        "kind": "table",
                        "columns": ["Run group", "Observed cost", "Memory record"],
                        "rows": estimate_rows,
                    },
                ],
            },
            {
                "title": "Results",
                "blocks": [
                    {"kind": "heading", "text": "Binder-ratio scans"},
                    {
                        "kind": "figures",
                        "items": [
                            {
                                "src": "figures/binder_Q_triangular.png",
                                "caption": (
                                    "Warning. Triangular Binder moment ratios at requested "
                                    "Δτ=0.013. Orange rings identify cells that miss the "
                                    "declared large-size SEM target; the largest curves do "
                                    "not cross inside the scanned field window."
                                ),
                            },
                            {
                                "src": "figures/binder_Q_honeycomb.png",
                                "caption": (
                                    "Warning. Honeycomb Binder moment ratios at requested "
                                    "Δτ=0.013. The large-size curves cross inside the scan, "
                                    "but finite-size variants remain wider than the target."
                                ),
                            },
                        ],
                    },
                    {
                        "kind": "verdict",
                        "status": "warn",
                        "label": "177/177 cells valid; 38 precision warnings retained",
                        "why": (
                            "No raw result was discarded, but the declared per-cell "
                            "precision threshold was not achieved for triangular L=40,48."
                        ),
                    },
                    {"kind": "heading", "text": "Finite-size and time-step stability"},
                    {
                        "kind": "figures",
                        "items": [
                            {
                                "src": "figures/data_collapse.png",
                                "caption": (
                                    "Finite-size data collapse for the primary Δτ=0.013, "
                                    "Lmin=16, a2 scaling family. The leading irrelevant "
                                    "correction b1 L^yi is removed using the same declared "
                                    "fit; the lower panels show residuals in units of each "
                                    "cell's SEM."
                                ),
                            },
                            {
                                "src": "figures/finite_size_fit_stability.png",
                                "caption": (
                                    "Warning. All 64 predefined finite-size variants are "
                                    "shown with bootstrap uncertainty. One honeycomb "
                                    "high-order variant is numerically unstable; adjacent "
                                    "size cuts do not share one fifth decimal."
                                ),
                            },
                            {
                                "src": "figures/dtau2_extrapolation.png",
                                "caption": (
                                    "Warning. Critical fields versus actual Δτ². Orange "
                                    "rings mark field-extrapolated step estimates; green "
                                    "squares are joint-fit sensitivities at Δτ=0."
                                ),
                            },
                        ],
                    },
                    {
                        "kind": "table",
                        "columns": ["Quantity", "Estimate", "Bootstrap standard error", "95% interval"],
                        "rows": [
                            [
                                "h_c triangular, Δτ→0",
                                f"{triangular['h_c_zero']:.9f}",
                                f"{triangular['standard_error']:.3e}",
                                f"[{triangular['ci95'][0]:.9f}, {triangular['ci95'][1]:.9f}]",
                            ],
                            [
                                "h_c honeycomb, Δτ→0",
                                f"{honeycomb['h_c_zero']:.9f}",
                                f"{honeycomb['standard_error']:.3e}",
                                f"[{honeycomb['ci95'][0]:.9f}, {honeycomb['ci95'][1]:.9f}]",
                            ],
                            [
                                "R = h_c triangular / h_c honeycomb",
                                f"{ratio['median']:.9f}",
                                f"{ratio['standard_error']:.3e}",
                                f"[{ratio['ci95'][0]:.9f}, {ratio['ci95'][1]:.9f}]",
                            ],
                        ],
                    },
                    {"kind": "heading", "text": "Ratio verdict"},
                    {
                        "kind": "figures",
                        "items": [
                            {
                                "src": "figures/ratio_vs_sqrt5.png",
                                "caption": (
                                    "Inconclusive. The median ratio nearly coincides with "
                                    "√5, but the 95% bootstrap interval is broad. The "
                                    "central offset is only "
                                    f"{ratio['delta_over_sigma']:.3f} standard errors."
                                ),
                            }
                        ],
                    },
                    {
                        "kind": "verdict",
                        "status": "warn",
                        "label": "Compatible with √5, challenge precision not achieved",
                        "why": (
                            f"R−√5={ratio['delta_sqrt5']:+.3e}, while "
                            f"σ(R)={ratio['standard_error']:.3e}; all three declared "
                            "precision targets and the fifth-decimal stability gate fail."
                        ),
                    },
                ],
            },
            {
                "title": "Highlight",
                "blocks": [
                    {
                        "kind": "card",
                        "title": "What's innovative",
                        "blocks": [
                            {
                                "kind": "text",
                                "text": (
                                    "The workflow combines a minimal independently "
                                    "validated Julia cluster-QMC implementation with "
                                    "cell-level cryptographic provenance, bin-level "
                                    "bootstrap, exhaustive predefined scaling variants, "
                                    "and actual-time-step extrapolation."
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
                                    "The central ratio is compatible with √5, but the "
                                    "analysis demonstrates that numerical proximity alone "
                                    "is not evidence for exact equality. Scan bracketing "
                                    "and stability dominate the uncertainty."
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
                                    "The durable outcome is a reproducible diagnostic "
                                    "pipeline that separates Monte Carlo noise, finite-size "
                                    "model dependence, and Trotter extrapolation. It also "
                                    "gives a concrete design rule for a future decisive "
                                    "scan: bracket each finite-step crossing before "
                                    "increasing raw sweep counts."
                                ),
                            }
                        ],
                    },
                ],
            },
        ],
    }
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis_dir", type=Path)
    parser.add_argument("--draft-report", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    record = build_run(args.analysis_dir)
    output = args.analysis_dir / "run.json"
    output.write_text(
        json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {output}", flush=True)
    if args.draft_report:
        report_output = args.analysis_dir / "report.json"
        report_output.write_text(
            json.dumps(
                build_report(record, draft=True),
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {report_output}", flush=True)


if __name__ == "__main__":
    main()
