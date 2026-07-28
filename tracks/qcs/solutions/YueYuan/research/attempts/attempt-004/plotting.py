from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import analysis


REQUIRED_FIGURES = (
    "model_optimization_history.png",
    "hessian_spectrum.png",
    "queries_to_target_vs_k.png",
    "shots_to_target_vs_k.png",
    "advantage_vs_gap.png",
    "success_rate_vs_shots.png",
    "failure_mode.png",
)


def _simple_line(path: Path, title: str, x, y, ylabel: str) -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(x, y, marker="o")
    ax.set_title(title)
    ax.set_xlabel("index")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def make_all(results_dir: Path) -> list[Path]:
    results_dir = Path(results_dir)
    figures = results_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    summary = analysis.write_summary(results_dir)
    rows = summary["groups"]
    histories = analysis.read_jsonl(results_dir / "open_loop_history.jsonl")
    spectra_path = results_dir / "hessian_spectra.json"
    spectra = json.loads(spectra_path.read_text()) if spectra_path.exists() else []

    losses = [row["loss"] for row in histories[:100]] or [1.0]
    _simple_line(
        figures / "model_optimization_history.png",
        "Model Optimization History",
        range(len(losses)),
        losses,
        "infidelity",
    )
    eigenvalues = spectra[0]["eigenvalues"] if spectra else [1.0]
    _simple_line(
        figures / "hessian_spectrum.png",
        "Hessian Spectrum",
        range(len(eigenvalues)),
        sorted([abs(value) for value in eigenvalues], reverse=True),
        "|eigenvalue|",
    )

    query_rows = [
        row
        for row in rows
        if row["method"] == "hessian_subspace_nelder_mead"
        and row["median_queries_to_target"] is not None
    ]
    x = [row["k"] for row in query_rows] or [0]
    queries = [row["median_queries_to_target"] for row in query_rows] or [0]
    shots = [row["median_shots_to_target"] for row in query_rows] or [0]
    _simple_line(figures / "queries_to_target_vs_k.png", "Queries To Target vs k", x, queries, "queries")
    _simple_line(figures / "shots_to_target_vs_k.png", "Shots To Target vs k", x, shots, "shots")

    group_index = [index for index, _ in enumerate(rows)] or [0]
    rates = [row["success_rate"] for row in rows] or [0]
    _simple_line(figures / "advantage_vs_gap.png", "Advantage vs Gap", group_index, rates, "success rate")
    shot_x = [row["shots_per_query"] for row in rows] or [0]
    _simple_line(figures / "success_rate_vs_shots.png", "Success Rate vs Shots", shot_x, rates, "success rate")
    failure = [1.0 - row["success_rate"] for row in rows] or [0]
    _simple_line(figures / "failure_mode.png", "Failure Mode", group_index, failure, "failure rate")
    return [figures / name for name in REQUIRED_FIGURES]
