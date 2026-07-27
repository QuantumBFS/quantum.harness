#!/usr/bin/env python3
"""Render Li et al. 2011 XY-chain LTRG reproduction figures."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


OKABE_ITO = ["#000000", "#E69F00", "#56B4E9", "#009E73", "#0072B2", "#D55E00"]
LINESTYLES = ["-", "--", "-.", ":", (0, (5, 1)), (0, (3, 1, 1, 1))]
MARKERS = ["o", "s", "^", "D", "v", "P"]

FIGURE4_KEYS = [
    (0.1, 100),
    (0.05, 100),
    (0.05, 150),
    (0.02, 100),
    (0.02, 150),
    (0.01, 150),
]


def _curve_by(curves: dict[str, dict[str, Any]], tau: float, dc: int) -> dict[str, Any]:
    matches = [
        curve
        for curve in curves.values()
        if np.isclose(float(curve["tau"]), tau) and int(curve["Dc"]) == dc
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one curve for tau={tau}, Dc={dc}; found {len(matches)}")
    return {**matches[0], "kind": "ltrg"}


def select_figure4(curves: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [_curve_by(curves, tau, dc) for tau, dc in FIGURE4_KEYS]


def select_figure5(curves: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [_curve_by(curves, 0.05, dc) for dc in (50, 100, 150)]


def select_figure6(curves: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    ltrg = [_curve_by(curves, 0.05, dc) for dc in (100, 150)]
    source = ltrg[-1]
    exact = {
        "kind": "exact",
        "temperature": source["temperature"],
        "specific_heat": source["exact_specific_heat"],
    }
    return [*ltrg, exact]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        temporary = Path(stream.name)
    os.replace(temporary, path)


def load_curves(run_dir: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    run_spec = _read_json(run_dir / "run_spec.json")
    curves: dict[str, dict[str, Any]] = {}
    manifests: list[dict[str, Any]] = []
    incomplete: list[str] = []
    for cell in run_spec["cells"]:
        cell_dir = run_dir / "cells" / cell["cell_id"]
        manifest_path = cell_dir / "manifest.json"
        data_path = cell_dir / "data.json"
        if not manifest_path.is_file() or not data_path.is_file():
            incomplete.append(cell["cell_id"])
            continue
        manifest = _read_json(manifest_path)
        if manifest.get("success") is not True:
            incomplete.append(cell["cell_id"])
            continue
        declared = cell["params"]["curve"]
        if manifest.get("params") != cell["params"]:
            raise ValueError(f"{cell['cell_id']} manifest parameters do not match run_spec")
        curve = _read_json(data_path)
        curve_id = declared["id"]
        curves[curve_id] = {**curve, "id": curve_id}
        manifests.append(manifest)
    if incomplete:
        raise RuntimeError(f"cannot plot incomplete cells: {', '.join(incomplete)}")
    return curves, manifests


def _configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 8,
            "axes.labelsize": 9,
            "axes.titlesize": 9,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.3,
            "savefig.dpi": 300,
        }
    )


def _save(fig: plt.Figure, base: Path) -> None:
    base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(base.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(base.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def _filtered(curve: dict[str, Any], x_key: str, y_key: str, predicate) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(curve[x_key], dtype=float)
    y = np.asarray(curve[y_key], dtype=float)
    keep = np.isfinite(x) & np.isfinite(y) & predicate(x)
    return x[keep], y[keep]


def render_figure4(curves: dict[str, dict[str, Any]], output: Path, quick: bool) -> None:
    fig, axis = plt.subplots(figsize=(5.2, 3.2))
    for index, curve in enumerate(select_figure4(curves)):
        beta, error = _filtered(
            curve,
            "beta",
            "relative_free_energy_error",
            lambda values: values <= (np.inf if quick else 5.0),
        )
        axis.plot(
            beta,
            np.maximum(error, np.finfo(float).tiny),
            color=OKABE_ITO[index],
            linestyle=LINESTYLES[index],
            marker=MARKERS[index],
            markevery=max(1, len(beta) // 10),
            markersize=3,
            label=rf"$\tau={curve['tau']:g}$, $D_c={curve['Dc']}$",
        )
    axis.set_yscale("log")
    axis.set_xlabel(r"Inverse temperature $\beta J$")
    axis.set_ylabel(r"Relative free-energy error $\delta f$")
    axis.set_xlim(left=0.0, right=None if quick else 5.0)
    axis.legend(frameon=False, ncol=2)
    axis.grid(axis="y", which="both", linewidth=0.4, alpha=0.25)
    fig.tight_layout()
    _save(fig, output)


def render_figure5(curves: dict[str, dict[str, Any]], output: Path, quick: bool) -> None:
    selected = select_figure5(curves)
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), sharex=True)
    beta_limit = lambda values: np.ones(values.shape, dtype=bool) if quick else values >= 20.0
    for index, curve in enumerate(selected):
        beta, error = _filtered(curve, "beta", "relative_free_energy_error", beta_limit)
        axes[0].plot(
            beta,
            np.maximum(error, np.finfo(float).tiny),
            color=OKABE_ITO[index + 1],
            linestyle=LINESTYLES[index],
            marker=MARKERS[index],
            markevery=max(1, len(beta) // 8),
            markersize=3,
            label=rf"$D_c={curve['Dc']}$",
        )
        beta, energy = _filtered(curve, "beta", "energy", beta_limit)
        axes[1].plot(
            beta,
            energy,
            color=OKABE_ITO[index + 1],
            linestyle=LINESTYLES[index],
            marker=MARKERS[index],
            markevery=max(1, len(beta) // 8),
            markersize=3,
            label=rf"$D_c={curve['Dc']}$",
        )

    exact_source = selected[-1]
    beta, exact_energy = _filtered(exact_source, "beta", "exact_energy", beta_limit)
    axes[1].plot(beta, exact_energy, color="#000000", linewidth=1.5, label="Exact")
    axes[0].set_yscale("log")
    axes[0].set_ylabel(r"Relative free-energy error $\delta f$")
    axes[1].set_ylabel(r"Energy per site $e/J$")
    for label, axis in zip(("a", "b"), axes):
        axis.set_xlabel(r"Inverse temperature $\beta J$")
        if not quick:
            axis.set_xlim(20.0, 120.0)
        axis.text(-0.13, 1.02, label, transform=axis.transAxes, fontweight="bold")
        axis.legend(frameon=False)
        axis.grid(axis="y", which="both", linewidth=0.4, alpha=0.25)
    fig.tight_layout(w_pad=2.0)
    _save(fig, output)


def render_figure6(curves: dict[str, dict[str, Any]], output: Path, quick: bool) -> None:
    fig, axis = plt.subplots(figsize=(5.2, 3.2))
    selected = select_figure6(curves)
    for index, series in enumerate([selected[-1], *selected[:-1]]):
        temperature = np.asarray(series["temperature"], dtype=float)
        heat = np.asarray(series["specific_heat"], dtype=float)
        keep = np.isfinite(temperature) & np.isfinite(heat)
        if not quick:
            tolerance = 100 * np.finfo(float).eps
            keep &= (temperature >= 1.0 / 120.0 - tolerance) & (
                temperature <= 2.0 + tolerance
            )
        order = np.argsort(temperature[keep])
        x = temperature[keep][order]
        y = heat[keep][order]
        if series["kind"] == "exact":
            axis.plot(x, y, color="#000000", linewidth=1.6, label="Exact", zorder=1)
        else:
            axis.plot(
                x,
                y,
                color=OKABE_ITO[index + 1],
                linestyle=LINESTYLES[index - 1],
                marker=MARKERS[index - 1],
                markevery=max(1, len(x) // 10),
                markersize=3,
                label=rf"LTRG, $D_c={series['Dc']}$",
                zorder=2,
            )
    axis.set_xlabel(r"Temperature $T/J$")
    axis.set_ylabel(r"Specific heat per site $C$")
    axis.set_xlim(left=0.0, right=None if quick else 2.0)
    axis.set_ylim(bottom=0.0)
    axis.legend(frameon=False)
    axis.grid(axis="y", linewidth=0.4, alpha=0.25)
    fig.tight_layout()
    _save(fig, output)


def build_summary(
    curves: dict[str, dict[str, Any]], manifests: list[dict[str, Any]], quick: bool
) -> dict[str, Any]:
    low_temperature = select_figure5(curves)
    beta_endpoint: dict[str, Any] = {}
    for curve in low_temperature:
        endpoint = -1
        beta_endpoint[str(curve["Dc"])] = {
            "beta": curve["beta"][endpoint],
            "relative_free_energy_error": curve["relative_free_energy_error"][endpoint],
            "energy": curve["energy"][endpoint],
            "relative_ground_energy_error": abs(
                (curve["energy"][endpoint] + 1.0 / np.pi) / (-1.0 / np.pi)
            ),
        }

    heat_curve = _curve_by(curves, 0.05, 150)
    temperatures = np.asarray(heat_curve["temperature"], dtype=float)
    heat = np.asarray(heat_curve["specific_heat"], dtype=float)
    keep = np.isfinite(temperatures) & np.isfinite(heat)
    if not quick:
        keep &= temperatures <= 2.0
    peak_index = np.flatnonzero(keep)[np.argmax(heat[keep])]
    return {
        "mode": "quick integration check" if quick else "paper reproduction",
        "beta_endpoint": beta_endpoint,
        "specific_heat_peak": {
            "Dc": 150,
            "temperature": float(temperatures[peak_index]),
            "value": float(heat[peak_index]),
        },
        "diagnostics": {
            "max_truncerr": max(
                float(manifest["metrics"]["max_truncerr"]) for manifest in manifests
            ),
            "cell_wall_seconds": sum(
                float(manifest["metrics"]["wall_seconds"]) for manifest in manifests
            ),
            "peak_rss_bytes": max(
                int(manifest["metrics"].get("peak_rss_bytes", 0)) for manifest in manifests
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args(argv)

    _configure_style()
    curves, manifests = load_curves(args.run_dir)
    figures = args.run_dir / "figs"
    render_figure4(curves, figures / "fig4", args.quick)
    render_figure5(curves, figures / "fig5", args.quick)
    render_figure6(curves, figures / "fig6a", args.quick)
    summary = build_summary(curves, manifests, args.quick)
    summary_path = args.run_dir / "summary.json"
    if summary_path.is_file():
        summary = {**_read_json(summary_path), **summary}
    _write_json_atomic(summary_path, summary)
    print(f"rendered Fig. 4, Fig. 5a-b, and Fig. 6a -> {figures}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
