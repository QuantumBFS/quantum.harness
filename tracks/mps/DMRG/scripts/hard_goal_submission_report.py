#!/usr/bin/env python3
"""Build an upload-ready Hard Goal terminal audit from verified local evidence."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Sequence
import zipfile

import numpy as np


TRACK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TRACK_ROOT.parents[2]
SRC = TRACK_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vmcrg_ref.artifacts import (  # noqa: E402
    atomic_write_json,
    sha256_file,
    verified_promote_directory,
)


STAGE4 = TRACK_ROOT / "results/hard_goal/stage4-b2-r1/manifest.json"
STAGE5 = TRACK_ROOT / "results/hard_goal/stage5-b3-r1/manifest.json"
STAGE4_NUMERICAL = TRACK_ROOT / "results/hard_goal/stage4-b2-r1/numerical_checks.json"
STAGE5_EXACT = TRACK_ROOT / "results/hard_goal/stage5-b3-r1/exact.json"
STAGE5_RG = TRACK_ROOT / "results/hard_goal/stage5-b3-r1/rg.json"
LOCAL_CAPACITY = TRACK_ROOT / "results/hard_goal/local-cpu-capacity-20260730"
SELECTIONS = {
    24: TRACK_ROOT / "results/hard_goal/stage6-status-20260730/L24-selection.json",
    27: TRACK_ROOT / "results/hard_goal/stage6-status-20260730/L27-selection.json",
}
REPORT_RENDERER = REPO_ROOT / "skills/report/render_report.py"
CANCELLED_JOBS = ("5315365", "5315366", "5315367", "5315368")


def _load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="ascii"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"unreadable JSON evidence: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"JSON evidence must be an object: {path}")
    return payload


def _require_pass_manifest(path: Path, stage: str) -> dict[str, object]:
    payload = _load_json(path)
    if payload.get("stage") != stage or payload.get("classification") != "PASS":
        raise ValueError(f"{stage} manifest is not PASS")
    integrity = payload.get("artifact_integrity") or payload.get("source_integrity")
    if not isinstance(integrity, dict) or integrity.get("passed") is not True:
        raise ValueError(f"{stage} integrity record is not passing")
    return payload


def _load_selection(length: int) -> tuple[dict[str, object], list[dict[str, object]]]:
    selection = _load_json(SELECTIONS[length])
    if (
        selection.get("decision") != "RECALIBRATE"
        or selection.get("scientific_evidence") is not False
        or selection.get("tc_evidence") is not False
    ):
        raise ValueError(f"L={length} selection is not the expected fail-closed result")
    raw_candidates = selection.get("candidates")
    if not isinstance(raw_candidates, list) or len(raw_candidates) != 2:
        raise ValueError(f"L={length} selection must contain two candidates")
    candidates: list[dict[str, object]] = []
    for raw in raw_candidates:
        if not isinstance(raw, dict):
            raise ValueError("selection candidate is malformed")
        path = Path(str(raw.get("manifest")))
        if not path.is_file() or sha256_file(path) != raw.get("manifest_sha256"):
            raise ValueError(f"selection candidate manifest hash mismatch: {path}")
        manifest = _load_json(path)
        parallel = manifest.get("parallel_tempering")
        if (
            manifest.get("classification") != "CALIBRATION_EXTENSION_COMPLETE"
            or manifest.get("completed_sweeps") != 8192
            or manifest.get("tc_evidence") is not False
            or not isinstance(parallel, dict)
            or parallel.get("round_trips_min") != 0
        ):
            raise ValueError(f"unexpected terminal calibration evidence: {path}")
        candidates.append({"selection": raw, "manifest": manifest, "path": path})
    return selection, candidates


def _set_plot_style() -> None:
    import matplotlib as mpl

    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9.5,
            "axes.titlesize": 11,
            "axes.labelsize": 9.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.18,
            "grid.linewidth": 0.7,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def _plot_stage_matrix(path: Path) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    labels = ["0-3\nDesign", "4\nRegression", "5\nValidation", "6\nPilot", "7\nProduction", "8\nAnalysis", "9\nReport"]
    statuses = ["COMPLETE", "PASS", "PASS", "RESOURCE\nNO-GO", "BLOCKED", "NOT RUN", "COMPLETE"]
    colors = ["#1f5cd6", "#1e7d3c", "#1e7d3c", "#b8651e", "#9a9a9a", "#9a9a9a", "#1f5cd6"]
    fig, ax = plt.subplots(figsize=(9.2, 2.3), constrained_layout=True)
    ax.set_xlim(-0.15, len(labels) - 0.15)
    ax.set_ylim(0, 1)
    ax.axis("off")
    for index, (label, status, color) in enumerate(zip(labels, statuses, colors, strict=True)):
        patch = FancyBboxPatch(
            (index, 0.25),
            0.78,
            0.46,
            boxstyle="round,pad=0.015,rounding_size=0.04",
            facecolor=color,
            edgecolor="none",
        )
        ax.add_patch(patch)
        ax.text(index + 0.39, 0.78, label, ha="center", va="bottom", weight="bold")
        ax.text(index + 0.39, 0.48, status, ha="center", va="center", color="white", fontsize=8.5, weight="bold")
        if index < len(labels) - 1:
            ax.annotate("", xy=(index + 0.97, 0.48), xytext=(index + 0.81, 0.48), arrowprops={"arrowstyle": "->", "color": "#777", "lw": 1.2})
    ax.set_title("Milestone outcome under the frozen evidence contract", loc="left", weight="bold")
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _plot_ladders(path: Path, rows: list[dict[str, object]]) -> None:
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(9.2, 6.0), sharey=True, constrained_layout=True)
    for ax, row in zip(axes.flat, rows, strict=True):
        values = np.asarray(row["edge_acceptance"], dtype=np.float64)
        edge = np.arange(values.size)
        ax.axhspan(0.20, 0.50, color="#1e7d3c", alpha=0.13, label="required band")
        ax.plot(edge, values, color=row["color"], lw=1.35, marker="o", markersize=2.5)
        ax.set_title(str(row["label"]), loc="left", weight="bold")
        ax.set_xlabel("Adjacent temperature edge")
        ax.set_ylim(0.15, 0.55)
        ax.text(
            0.98,
            0.06,
            f"range {values.min():.3f}-{values.max():.3f} | min trips 0",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=8,
            color="#4b4b4b",
        )
    axes[0, 0].set_ylabel("Swap acceptance")
    axes[1, 0].set_ylabel("Swap acceptance")
    axes[0, 0].legend(frameon=False, loc="upper right", fontsize=8)
    fig.suptitle("Stage 6 adaptive ladders after 8,192 sweeps", fontsize=13, weight="bold")
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _plot_capacity(path: Path, cpu_rate: float, a800_rates: list[float]) -> None:
    import matplotlib.pyplot as plt

    calibration_hours = 188.39895666403828
    deadline_hours = 4.5
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.7), constrained_layout=True)
    rates = [cpu_rate / 1e6, min(a800_rates) / 1e6, max(a800_rates) / 1e6]
    labels = ["Local CPU", "A800 observed\n(min)", "A800 observed\n(max)"]
    colors = ["#b8651e", "#1f5cd6", "#1e7d3c"]
    bars = axes[0].bar(labels, rates, color=colors, width=0.62)
    axes[0].set_ylabel("Million spin proposals / s")
    axes[0].set_title("Measured backend throughput", loc="left", weight="bold")
    axes[0].bar_label(bars, fmt="%.1f", padding=3)
    axes[0].set_ylim(0, max(rates) * 1.22)

    bars = axes[1].bar(
        ["Time available", "Stage 6 first-pass\ncalibration"],
        [deadline_hours, calibration_hours],
        color=["#1f5cd6", "#b3261e"],
        width=0.62,
    )
    axes[1].set_yscale("log")
    axes[1].set_ylabel("Local wall hours (log scale)")
    axes[1].set_title("Deadline feasibility", loc="left", weight="bold")
    axes[1].bar_label(bars, labels=["4.5 h", "188 h"], padding=3)
    axes[1].set_ylim(1, 500)
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="ascii") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _deterministic_zip(source: Path, archive: Path) -> None:
    if archive.exists():
        raise FileExistsError(f"refusing to overwrite archive: {archive}")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as handle:
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            relative = Path(source.name) / path.relative_to(source)
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            handle.writestr(info, path.read_bytes())


def build_report(output: Path, archive: Path) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite report: {output}")
    stage4 = _require_pass_manifest(STAGE4, "stage4")
    stage5 = _require_pass_manifest(STAGE5, "stage5")
    stage4_numerical = _load_json(STAGE4_NUMERICAL)
    stage5_exact = _load_json(STAGE5_EXACT)
    stage5_rg = _load_json(STAGE5_RG)
    capacity = _load_json(LOCAL_CAPACITY)
    benchmark = capacity.get("benchmark")
    runtime = capacity.get("runtime")
    if (
        capacity.get("classification") != "PASS"
        or capacity.get("scope") != "stage6-pt-backend-smoke-only"
        or not isinstance(benchmark, dict)
        or not isinstance(runtime, dict)
        or runtime.get("default_backend") != "cpu"
    ):
        raise ValueError("local capacity benchmark is invalid")

    selections: dict[int, dict[str, object]] = {}
    candidate_rows: list[dict[str, object]] = []
    plot_rows: list[dict[str, object]] = []
    a800_rates: list[float] = []
    colors = {"A035": "#1f5cd6", "A040": "#b8651e"}
    for length in (24, 27):
        selection, candidates = _load_selection(length)
        selections[length] = selection
        for record in candidates:
            manifest = record["manifest"]
            selected = record["selection"]
            parallel = manifest["parallel_tempering"]
            runtime_record = manifest["runtime"]
            assert isinstance(parallel, dict) and isinstance(runtime_record, dict)
            cell_id = str(selected["cell_id"])
            target = "A035" if "A035" in cell_id else "A040"
            a800_rates.append(float(runtime_record["spin_proposals_per_second"]))
            candidate_rows.append(
                {
                    "cell": f"L{length} {target}",
                    "sweeps": int(manifest["completed_sweeps"]),
                    "acceptance_min": float(selected["edge_acceptance_min"]),
                    "acceptance_max": float(selected["edge_acceptance_max"]),
                    "round_trips_min": int(parallel["round_trips_min"]),
                    "round_trips_max": int(parallel["round_trips_max"]),
                    "selector": "REJECTED",
                    "tc_evidence": False,
                }
            )
            plot_rows.append(
                {
                    "label": f"L={length}, target {target[1:]}",
                    "edge_acceptance": parallel["edge_acceptance"],
                    "color": colors[target],
                }
            )

    l2_errors = [
        float(metric["absolute_error"])
        for row in stage5_exact["l2"]
        for metric in row["metrics"].values()
    ]
    l3_errors = [float(row["absolute_error_per_site"]) for row in stage5_exact["l3"]]
    cpu_rate = float(benchmark["warm_spin_proposals_per_second"])
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        matplotlib_cache = Path(tempfile.mkdtemp(prefix="hg3d-report-mpl-", dir="/tmp"))
        try:
            os.environ["MPLCONFIGDIR"] = str(matplotlib_cache)
            import matplotlib

            matplotlib.use("Agg")
            _set_plot_style()
            _plot_stage_matrix(staging / "stage-outcomes.png")
            _plot_ladders(staging / "stage6-ladders.png", plot_rows)
            _plot_capacity(staging / "local-capacity.png", cpu_rate, a800_rates)
        finally:
            shutil.rmtree(matplotlib_cache)

        stage_rows = [
            {"stage": "0-3", "status": "COMPLETE", "claim": "Model, evidence contract, and implementation plan frozen"},
            {"stage": "4", "status": "PASS", "claim": "2D MPS regression only; not 3D science evidence"},
            {"stage": "5", "status": "PASS", "claim": "Exact and small-3D correctness validated"},
            {"stage": "6", "status": "RESOURCE_NO_GO", "claim": "Acceptance passes; equilibration and physical representation comparison do not"},
            {"stage": "7", "status": "BLOCKED", "claim": "No equilibrated L=45 production"},
            {"stage": "8", "status": "NOT_RUN", "claim": "No valid production summary for FSS or RG-flow analysis"},
            {"stage": "9", "status": "COMPLETE", "claim": "Terminal audit and upload package generated"},
        ]
        _write_csv(staging / "stage_outcomes.csv", ("stage", "status", "claim"), stage_rows)
        _write_csv(
            staging / "stage6_candidates.csv",
            ("cell", "sweeps", "acceptance_min", "acceptance_max", "round_trips_min", "round_trips_max", "selector", "tc_evidence"),
            candidate_rows,
        )
        capacity_rows = [
            {"metric": "local_cpu_proposals_per_second", "value": cpu_rate, "unit": "spin proposals/s"},
            {"metric": "a800_min_proposals_per_second", "value": min(a800_rates), "unit": "spin proposals/s"},
            {"metric": "a800_max_proposals_per_second", "value": max(a800_rates), "unit": "spin proposals/s"},
            {"metric": "stage6_first_pass_local_projection", "value": 188.39895666403828, "unit": "hours"},
            {"metric": "deadline_budget", "value": 4.5, "unit": "hours"},
        ]
        _write_csv(staging / "capacity.csv", ("metric", "value", "unit"), capacity_rows)
        shutil.copy2(LOCAL_CAPACITY, staging / "local_cpu_capacity.json")
        shutil.copy2(SELECTIONS[24], staging / "L24-selection.json")
        shutil.copy2(SELECTIONS[27], staging / "L27-selection.json")

        document = {
            "title": "3D Spin-Glass Hard Goal: Terminal Local Audit",
            "eyebrow": "Issue #28 | 2026-07-30 | upload-ready evidence package",
            "lede": (
                "Stages 4 and 5 pass their declared correctness gates. Stage 6 does not establish "
                "parallel-tempering equilibration, and the local-only deadline cannot support Stage 7 "
                "production. The honest terminal classification is RESOURCE_NO_GO; no transition "
                "temperature is reported."
            ),
            "sections": [
                {
                    "title": "Final Verdict",
                    "note": "A complete report is not the same as a successful physics result.",
                    "blocks": [
                        {
                            "kind": "verdict",
                            "status": "bad",
                            "label": "RESOURCE_NO_GO",
                            "why": "The frozen Hard Goal evidence contract cannot be completed locally before 16:00; L=45 and Tc claims remain unsupported.",
                        },
                        {"kind": "figures", "items": [{"src": "stage-outcomes.png", "caption": "Milestone audit. Green stages passed their fixed gates; orange marks the Stage 6 resource/equilibration stop; gray stages lack valid scientific inputs. Stage 9 denotes report completion only."}]},
                        {
                            "kind": "table",
                            "columns": ["Stage", "Status", "Evidence boundary"],
                            "widths": ["12%", "21%", "67%"],
                            "rows": [[row["stage"], row["status"], row["claim"]] for row in stage_rows],
                        },
                    ],
                },
                {
                    "title": "Physical Contract",
                    "note": "The calculation setup was not changed to fit the deadline.",
                    "blocks": [
                        {"kind": "equation", "tex": "H_J(s)=-\\sum_{\\langle ij\\rangle}J_{ij}s_i s_j,\\qquad P(J_{ij}=+1)=P(J_{ij}=-1)=\\frac{1}{2}"},
                        {
                            "kind": "kv",
                            "pairs": [
                                ["Model", "3D iid symmetric bimodal Edwards-Anderson Ising spin glass"],
                                ["Geometry", "Cubic periodic lattice, zero field, |J|=1"],
                                ["Order parameter", "Two independently evolved real replicas and overlap q_i=s_i^(a)s_i^(b)"],
                                ["RG map", "3 x 3 x 3 majority blocking; second RG remains disabled"],
                                ["Final Tc contract", "Independent unbiased xi_L/L and Binder finite-size evidence, compatible with neural RG flow"],
                            ],
                        },
                    ],
                },
                {
                    "title": "Verified Correctness",
                    "note": "These results validate implementation components, not the thermodynamic transition.",
                    "blocks": [
                        {
                            "kind": "table",
                            "columns": ["Check", "Measured", "Status"],
                            "rows": [
                                ["Stage 4 TT finite-difference gradient error", f"{float(stage4_numerical['gradient']['error']):.3e}", "PASS"],
                                ["Stage 4 incremental local-delta error", f"{float(stage4_numerical['incremental_delta']['error']):.3e}", "PASS"],
                                ["Stage 5 maximum L=2 estimator error", f"{max(l2_errors):.3e}", "PASS"],
                                ["Stage 5 maximum L=3 derivative error/site", f"{max(l3_errors):.3e}", "PASS"],
                                ["Stage 5 RG cache/origin error", f"{max(float(stage5_rg['incremental_cache_error']), float(stage5_rg['maximum_origin_error'])):.1f}", "PASS"],
                                ["Stage 6-8 workflow tests run locally", "67 passed", "PASS"],
                            ],
                        },
                        {"kind": "note", "label": "Scope", "text": "The Stage 5 MPS comparison uses a synthetic local overlap-field teacher. It cannot satisfy the final held-out physical MPS-versus-linear success clause."},
                    ],
                },
                {
                    "title": "Stage 6 Evidence",
                    "note": "All four adaptive ladders have good adjacent-swap acceptance but fail the complete-travel gate.",
                    "blocks": [
                        {"kind": "figures", "items": [{"src": "stage6-ladders.png", "caption": "Rejected equilibration evidence. Cumulative adjacent-temperature acceptance after 8,192 sweeps for one disorder realization at L=24 and L=27. Every edge lies inside the preregistered 0.20-0.50 band, but the minimum complete low-high-low trip count is zero for every candidate."}]},
                        {
                            "kind": "table",
                            "columns": ["Candidate", "Acceptance range", "Round trips min/max", "Decision"],
                            "rows": [[row["cell"], f"{row['acceptance_min']:.3f}-{row['acceptance_max']:.3f}", f"{row['round_trips_min']}/{row['round_trips_max']}", "REJECTED"] for row in candidate_rows],
                        },
                        {"kind": "verdict", "status": "warn", "label": "NO EQUILIBRATION CLAIM", "why": "Good local exchange rates do not prove full temperature-space mixing, stationarity, effective sample size, or unbiased thermodynamic sampling."},
                    ],
                },
                {
                    "title": "Local Resource Audit",
                    "note": "The local benchmark is capacity evidence only and carries no Tc claim.",
                    "blocks": [
                        {"kind": "figures", "items": [{"src": "local-capacity.png", "caption": "Local feasibility audit. The CPU backend sustains 1.57 million spin proposals/s, versus 23.3-27.6 million/s on the measured A800 continuation cells. Even the Stage 6 first-pass calibration projects to about 188 local hours, compared with a 4.5-hour deadline budget."}]},
                        {
                            "kind": "kv",
                            "pairs": [
                                ["Local host", str(runtime["host"])],
                                ["Local backend", "JAX CPU only; GPU access blocked by the operating system"],
                                ["Local memory", "31 GiB RAM available at audit time"],
                                ["Stage 6 first-pass projection", "188.4 local wall hours before equilibration, measurement, or neural comparison"],
                                ["L=45 production", "Not executed; the Stage 6 PASS prerequisite is absent"],
                            ],
                        },
                    ],
                },
                {
                    "title": "Claim Boundary",
                    "note": "What this submission does and does not establish.",
                    "blocks": [
                        {
                            "kind": "list",
                            "title": "Supported",
                            "items": [
                                "The 3D model, overlap observables, RG cache, local TT, checkpoints, production planner, and Stage 8 analysis interfaces have passing deterministic tests.",
                                "Exact L=2/L=3 and small-3D Stage 5 validation pass their frozen numerical tolerances.",
                                "Adaptive temperature spacing places all measured L=24/L=27 exchange edges inside the target band.",
                                "Negative results, stopped jobs, and resource limitations are retained without seed replacement or threshold movement.",
                            ],
                        },
                        {
                            "kind": "list",
                            "title": "Not supported",
                            "items": [
                                "No equilibrated multi-disorder Stage 6 pilot.",
                                "No physical held-out Route C/B MPS improvement over the conditioned-linear baseline.",
                                "No L=45 production, xi_L/L or Binder crossing, neural RG-flow interval, or uncertainty budget.",
                                "No numerical Tc estimate. Quoting the literature anchor near 1.11 as this run's result would be invalid.",
                            ],
                        },
                    ],
                },
                {
                    "title": "Provenance",
                    "blocks": [
                        {
                            "kind": "kv",
                            "pairs": [
                                ["Stage 4 manifest", sha256_file(STAGE4)],
                                ["Stage 5 manifest", sha256_file(STAGE5)],
                                ["L=24 selection", sha256_file(SELECTIONS[24])],
                                ["L=27 selection", sha256_file(SELECTIONS[27])],
                                ["Local capacity record", sha256_file(LOCAL_CAPACITY)],
                                ["Cancelled qdeshell jobs", ", ".join(CANCELLED_JOBS) + " (all cancelled before start)"],
                                ["Overall classification", "RESOURCE_NO_GO"],
                            ],
                        }
                    ],
                },
            ],
        }
        atomic_write_json(staging / "report.json", document)
        subprocess.run(
            [sys.executable, str(REPORT_RENDERER), str(staging)],
            cwd=REPO_ROOT,
            check=True,
        )
        summary = """# 3D Spin-Glass Hard Goal - Local Terminal Audit

Overall classification: `RESOURCE_NO_GO`.

- Stage 4: PASS (2D regression only).
- Stage 5: PASS (exact and small-3D correctness).
- Stage 6: not passed; all four 8,192-sweep ladders have minimum complete round trips equal to zero.
- Stage 7: blocked; no equilibrated L=45 production.
- Stage 8: not run; no valid production summary.
- Stage 9: this report and archive are complete.

No transition temperature is claimed. Open `report.html` for the self-contained report.
"""
        (staging / "SUMMARY.md").write_text(summary, encoding="ascii")
        evidence_sources = {
            "stage4_manifest": sha256_file(STAGE4),
            "stage5_manifest": sha256_file(STAGE5),
            "l24_selection": sha256_file(SELECTIONS[24]),
            "l27_selection": sha256_file(SELECTIONS[27]),
            "local_capacity": sha256_file(LOCAL_CAPACITY),
        }
        artifacts = {
            path.relative_to(staging).as_posix(): sha256_file(path)
            for path in sorted(staging.rglob("*"))
            if path.is_file()
        }
        manifest = {
            "schema_version": 1,
            "stage": "stage9",
            "classification": "RESOURCE_NO_GO",
            "scope": "upload-ready terminal audit; no Tc claim",
            "stage4_classification": stage4["classification"],
            "stage5_classification": stage5["classification"],
            "stage6_decision": "RECALIBRATE",
            "stage7_executed": False,
            "stage8_executed": False,
            "cancelled_jobs": list(CANCELLED_JOBS),
            "source_evidence": evidence_sources,
            "artifacts": artifacts,
        }
        atomic_write_json(staging / "manifest.json", manifest)
        verified_promote_directory(
            staging,
            output,
            {**artifacts, "manifest.json": sha256_file(staging / "manifest.json")},
        )
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    _deterministic_zip(output, archive)
    digest = sha256_file(archive)
    archive.with_suffix(archive.suffix + ".sha256").write_text(
        f"{digest}  {archive.name}\n",
        encoding="ascii",
    )
    return {"classification": "RESOURCE_NO_GO", "output": str(output), "archive": str(archive), "archive_sha256": digest}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    archive = args.archive or args.output.with_suffix(".zip")
    try:
        result = build_report(args.output.resolve(), archive.resolve())
    except (FileExistsError, FileNotFoundError, KeyError, TypeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"submission report failed closed: {error}", file=sys.stderr, flush=True)
        return 2
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
