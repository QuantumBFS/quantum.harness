#!/usr/bin/env python3
"""Generate transport-first figures from completed L=8 aggregate data."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.transport_analysis import efficiency, group_path_rows  # noqa: E402


COLORS = {2.0: "#D1495B", 10.0: "#EDAE49", 50.0: "#087E8B"}
TYPICAL = ((0.0, "U0"), (7.25, "U7p25"), (7.5, "U7p5"), (16.0, "U16"))
PATH_STYLE = {
    "center": ("centered", "#263238"),
    "shift-1p5": (r"$\Delta_c=1.5$", "#087E8B"),
    "near-tangent": (r"$\Delta_c=2.85$", "#EDAE49"),
    "outside": (r"$\Delta_c=3.6$", "#D1495B"),
}
PATH_IDS = ("shift-1p5", "near-tangent", "outside")
CRITICAL_U = {
    "center": (7.372348498,),
    "shift-1p5": (4.352096694, 10.354477369),
    "near-tangent": (0.882883835, 13.039003998),
    "outside": (2.343682390, 14.531681175),
}


def _rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _grid(rows: list[dict], field: str, *, period: float | None = None):
    selected = rows if period is None else [r for r in rows if float(r["period"]) == period]
    U = np.asarray(sorted({float(r["U"]) for r in selected}))
    t = np.asarray(sorted({float(r["t"]) for r in selected}))
    values = np.full((t.size, U.size), np.nan)
    ui = {value: index for index, value in enumerate(U)}
    ti = {value: index for index, value in enumerate(t)}
    for row in selected:
        values[ti[float(row["t"])], ui[float(row["U"])]] = float(row[field])
    if not np.all(np.isfinite(values)):
        raise ValueError(f"aggregate grid for {field} is incomplete")
    return U, t, values


def _edges(values: np.ndarray) -> np.ndarray:
    middle = 0.5 * (values[:-1] + values[1:])
    return np.concatenate(([values[0] - (middle[0] - values[0])], middle, [values[-1] + (values[-1] - middle[-1])]))


def _style() -> None:
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "figure.dpi": 150,
            "savefig.dpi": 240,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "lines.linewidth": 1.7,
        }
    )


def plot_phase_maps(static: list[dict], realtime: list[dict], output: Path) -> None:
    U, t, chern = _grid(static, "C_MB")
    _, _, gap = _grid(static, "Delta_min")
    _, _, q50 = _grid(realtime, "Q_real_time", period=50.0)
    fields = (
        (chern, r"$C_{\rm MB}$", "coolwarm", None, -0.1, 2.1),
        (gap, r"$\Delta_{\min}$", "viridis", LogNorm(vmin=max(gap.min(), 1e-3), vmax=gap.max()), None, None),
        (chern / 2.0, r"$\eta_{\rm topo}=C_{\rm MB}/2$", "RdBu_r", None, -0.1, 1.1),
        (q50 / 2.0, r"$\eta(T=50)=Q(T)/2$", "RdBu_r", None, -0.1, 1.1),
    )
    fig, axes = plt.subplots(2, 2, figsize=(10.2, 6.8), constrained_layout=True, sharex=True, sharey=True)
    ue, te = _edges(U), _edges(t)
    for label, (ax, (values, title, cmap, norm, vmin, vmax)) in zip("abcd", zip(axes.ravel(), fields)):
        mesh = ax.pcolormesh(ue, te, values, shading="flat", cmap=cmap, norm=norm, vmin=vmin, vmax=vmax)
        ax.scatter(np.tile(U, t.size), np.repeat(t, U.size), s=2, c="black", alpha=0.3, linewidths=0)
        ax.contour(U, t, chern, levels=[1.0], colors="white", linewidths=1.2)
        ax.set_title(f"({label}) {title}", loc="left")
        ax.set_xlabel(r"Hubbard $U$")
        ax.set_ylabel(r"hopping $t$")
        fig.colorbar(mesh, ax=ax, pad=0.02)
    fig.suptitle(r"L=8, centered path: $\delta_0=0.9,\ \Delta_0=3$", fontsize=12)
    fig.savefig(output / "center_phase_maps.png")
    fig.savefig(output / "center_phase_maps.pdf")
    plt.close(fig)


def plot_u_transport(
    static: list[dict],
    realtime: list[dict],
    output: Path,
    refined_static: list[dict] | None = None,
    critical_gap: list[dict] | None = None,
) -> None:
    s = sorted((r for r in static if float(r["t"]) == 1.0), key=lambda r: float(r["U"]))
    U_base = np.asarray([float(r["U"]) for r in s])
    qad = np.asarray([float(r["Q_adiabatic"]) for r in s])
    topology_by_u = {float(r["U"]): float(r["C_MB"]) for r in s}
    gap_by_u = {float(r["U"]): float(r["Delta_min"]) for r in s}
    for row in refined_static or ():
        if row["path_id"] == "center":
            topology_by_u[float(row["U"])] = float(row["C_MB"])
            gap_by_u[float(row["U"])] = float(row["Delta_min"])
    for row in critical_gap or ():
        if row["path_id"] == "center":
            gap_by_u[float(row["U"])] = float(row["Delta_min_line"])
    U_topology = np.asarray(sorted(topology_by_u))
    chern = np.asarray([topology_by_u[value] for value in U_topology])
    U_gap = np.asarray(sorted(gap_by_u))
    gap = np.asarray([gap_by_u[value] for value in U_gap])
    fig, axes = plt.subplots(3, 1, figsize=(8.3, 8.0), sharex=True, constrained_layout=True)
    axes[0].plot(U_topology, chern, "o-", ms=3, color="#263238", label=r"$C_{\rm MB}$")
    axes[0].plot(U_base, qad, "s--", ms=3, color="#087E8B", label=r"$Q_{\rm adiabatic}$")
    axes[0].axhline(2, color="0.7", lw=1)
    axes[0].set_ylabel("topology / charge")
    axes[0].legend(ncol=2)
    axes[0].set_title(r"(a) Chern number and adiabatic polarization winding", loc="left")
    axes[1].semilogy(U_gap, gap, "o-", ms=3, color="#D1495B")
    imin = int(np.argmin(gap))
    axes[1].annotate(f"refined closing gap\nU={U_gap[imin]:.6g}, {gap[imin]:.3g}", (U_gap[imin], gap[imin]), xytext=(U_gap[imin]-15, 2e-7), arrowprops={"arrowstyle": "->"})
    axes[1].set_ylabel(r"$\Delta_{\min}$")
    axes[1].set_title(r"(b) Gap protection collapses near the Chern transition", loc="left")
    axes[2].plot(U_topology, chern / 2, "k--", label=r"$\eta_{\rm topo}=C_{\rm MB}/2$")
    for period in (2.0, 10.0, 50.0):
        rows = sorted((r for r in realtime if float(r["t"]) == 1.0 and float(r["period"]) == period), key=lambda r: float(r["U"]))
        axes[2].plot(U_base, [efficiency(float(r["Q_real_time"])) for r in rows], "o-", ms=3, color=COLORS[period], label=rf"$\eta(T={period:g})$")
    axes[2].axhline(1, color="0.7", lw=1)
    axes[2].set_ylim(-0.12, 1.35)
    axes[2].set_xlabel(r"Hubbard $U$")
    axes[2].set_ylabel(r"efficiency $\eta$")
    axes[2].set_title(r"(c) Finite-time transport efficiency", loc="left")
    axes[2].legend(ncol=4)
    fig.suptitle(r"L=8, $t=1$, centered path $(\delta_0,\Delta_0)=(0.9,3)$", fontsize=12)
    fig.savefig(output / "center_u_transport.png")
    fig.savefig(output / "center_u_transport.pdf")
    plt.close(fig)


def _center_adiabatic_curve(
    traces: np.lib.npyio.NpzFile,
    token: str,
    U: float,
    paths_root: Path | None,
) -> tuple[np.ndarray, np.ndarray]:
    if paths_root is not None:
        wilson_path = paths_root / "static" / f"center_U_{_local_token(U)}.npz"
        if wilson_path.exists():
            with np.load(wilson_path, allow_pickle=False) as data:
                phi = np.asarray(data["phi"])
                polarization = np.asarray(data["polarization"])
            return phi, polarization - polarization[0]
    polarization = traces[f"{token}_polarization"]
    return traces[f"{token}_phi_ad"], polarization - polarization[0]


def plot_typical_cycles(traces: Path, output: Path, paths_root: Path | None = None) -> None:
    """Plot the `36.md` polarization-winding adiabatic charge.

    Saved twist Wilson-loop curves take precedence over legacy Resta traces.
    """
    with np.load(traces, allow_pickle=False) as data:
        fig, axes = plt.subplots(2, 4, figsize=(13, 5.5), constrained_layout=True)
        for column, (U, token) in enumerate(TYPICAL):
            phi, pad = _center_adiabatic_curve(data, token, U, paths_root)
            label = r"$Q_{\rm ad}(\phi)$"
            axes[0, column].plot(phi / np.pi, pad, "k--", label=label)
            for period in (2.0, 10.0, 50.0):
                time = data[f"{token}_T{period:g}_times"]
                charge = data[f"{token}_T{period:g}_cumulative"]
                axes[0, column].plot(2 * time / period, charge, color=COLORS[period], label=rf"$T={period:g}$")
            axes[0, column].axhline(2, color="0.8", lw=1)
            axes[0, column].set_title(rf"$U={U:g}$")
            axes[0, column].set_xlabel(r"pump phase $\phi/\pi$")
            axes[0, column].set_ylabel(r"accumulated $Q(\phi)$")
            e0 = data[f"{token}_e0_torus"][0]
            gap = data[f"{token}_gap_torus"][0]
            phig = data[f"{token}_phi_grid"] / np.pi
            ax = axes[1, column]
            ax.plot(phig, e0 - e0.min(), color="#263238", label=r"$E_0-E_{0,\min}$")
            twin = ax.twinx()
            twin.plot(phig, gap, color="#D1495B", marker="o", ms=2.5, label=r"$E_1-E_0$")
            ax.set_xlabel(r"$\phi/\pi$ at $\theta=0$")
            ax.set_ylabel("relative ground energy")
            twin.set_ylabel("gap", color="#D1495B")
        handles, labels = axes[0, 0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="upper center", ncol=4, bbox_to_anchor=(0.5, 1.04))
        fig.suptitle("One-cycle charge formation and instantaneous spectrum", y=1.10, fontsize=12)
        fig.savefig(output / "center_typical_cycles.png", bbox_inches="tight")
        fig.savefig(output / "center_typical_cycles.pdf", bbox_inches="tight")
        plt.close(fig)


def plot_torus_maps(traces: Path, output: Path) -> None:
    with np.load(traces, allow_pickle=False) as data:
        fig, axes = plt.subplots(2, 4, figsize=(13, 5.6), constrained_layout=True, sharex=True, sharey=True)
        for column, (U, token) in enumerate(TYPICAL):
            e0 = data[f"{token}_e0_torus"]
            gap = data[f"{token}_gap_torus"]
            N = e0.shape[0]
            extent = (0, 2, 0, 2)
            top = axes[0, column].imshow(e0 - e0.min(), origin="lower", extent=extent, aspect="auto", cmap="cividis")
            bottom = axes[1, column].imshow(gap, origin="lower", extent=extent, aspect="auto", cmap="magma")
            axes[0, column].set_title(rf"$U={U:g}$")
            fig.colorbar(top, ax=axes[0, column], pad=0.02, label=r"$E_0-E_{0,\min}$")
            fig.colorbar(bottom, ax=axes[1, column], pad=0.02, label=r"$E_1-E_0$")
            axes[1, column].set_xlabel(r"$\phi/\pi$")
            axes[0, column].set_ylabel(r"$\theta/\pi$")
            axes[1, column].set_ylabel(r"$\theta/\pi$")
        fig.suptitle(r"Many-body energy and gap on the $(\theta,\phi)$ torus", fontsize=12)
        fig.savefig(output / "center_torus_energy_gap.png")
        fig.savefig(output / "center_torus_energy_gap.pdf")
        plt.close(fig)


def plot_interactive(static: list[dict], realtime: list[dict], output: Path) -> None:
    U, t, chern = _grid(static, "C_MB")
    _, _, gap = _grid(static, "Delta_min")
    _, _, q50 = _grid(realtime, "Q_real_time", period=50.0)
    fig = make_subplots(rows=2, cols=2, specs=[[{"type": "surface"}, {"type": "surface"}], [{"type": "surface"}, {"type": "surface"}]], subplot_titles=("Many-body Chern number", "Minimum many-body gap", "Topological efficiency", "Finite-time efficiency, T=50"))
    for index, (z, colorscale) in enumerate(((chern, "RdBu"), (gap, "Viridis"), (chern / 2, "RdBu"), (q50 / 2, "RdBu"))):
        row, col = divmod(index, 2)
        fig.add_trace(go.Surface(x=U, y=t, z=z, colorscale=colorscale, showscale=True), row=row + 1, col=col + 1)
    fig.update_scenes(xaxis_title="U", yaxis_title="t", zaxis_title="value")
    fig.update_layout(title=r"L=8 centered Rice-Mele-Hubbard pump: transport landscape", height=900, width=1250, margin=dict(l=20, r=20, t=80, b=20))
    _write_html(fig, output / "center_transport_interactive.html")


def _local_token(value: float) -> str:
    return f"{value:+.2f}".replace("+", "p").replace("-", "m").replace(".", "d")


def _write_html(fig: go.Figure, path: Path) -> None:
    fig.write_html(path, include_plotlyjs=True, full_html=True)
    normalized = "\n".join(line.rstrip() for line in path.read_text().splitlines())
    path.write_text(normalized + "\n", encoding="utf-8")


def _path_rows(
    center_static: list[dict],
    local_static: list[dict],
    refined_static: list[dict],
) -> dict[str, list[dict]]:
    return group_path_rows(
        center_static,
        local_static,
        refined_static,
        path_ids=PATH_IDS,
        critical_u=CRITICAL_U,
        replacement_half_width=1.05,
    )


def plot_path_observables(
    center_static: list[dict],
    local_static: list[dict],
    refined_static: list[dict],
    critical_gap: list[dict],
    output: Path,
) -> None:
    grouped = _path_rows(center_static, local_static, refined_static)
    fig, axes = plt.subplots(2, 2, figsize=(10.2, 7.4), constrained_layout=True)
    phi = np.linspace(0, 2 * np.pi, 400)
    for path_id, rows in grouped.items():
        label, color = PATH_STYLE[path_id]
        center = 0.0 if path_id == "center" else float(rows[0]["Delta_center"])
        axes[0, 0].plot(0.9 * np.cos(phi), center + 3.0 * np.sin(phi), color=color, label=label)
        axes[0, 1].plot([float(r["U"]) for r in rows], [float(r["C_MB"]) for r in rows], "o-", ms=3, color=color, label=label)
        gap_by_u = {float(r["U"]): float(r["Delta_min"]) for r in rows}
        gap_by_u.update(
            {
                float(r["U"]): float(r["Delta_min_line"])
                for r in critical_gap
                if r["path_id"] == path_id
            }
        )
        gap_u = np.asarray(sorted(gap_by_u))
        axes[1, 0].semilogy(gap_u, [gap_by_u[value] for value in gap_u], "o-", ms=2.7, color=color)
        axes[1, 1].plot([float(r["U"]) for r in rows], [float(r["C_MB"]) / 2 for r in rows], "o-", ms=3, color=color)
    axes[0, 0].scatter([0], [0], marker="x", s=60, color="black", zorder=5, label="origin")
    axes[0, 0].set_aspect("equal", adjustable="box")
    axes[0, 0].set_xticks((-0.9, 0.9))
    axes[0, 0].set_xlabel(r"dimerization $\delta$")
    axes[0, 0].set_ylabel(r"staggering $\Delta$")
    axes[0, 0].set_title("(a) Pump paths", loc="left")
    axes[0, 0].legend(ncol=2)
    axes[0, 1].set_ylabel(r"$C_{\rm MB}$")
    axes[0, 1].set_title("(b) Path-dependent topology", loc="left")
    axes[0, 1].legend(ncol=2)
    axes[1, 0].set_ylabel(r"$\Delta_{\min}$")
    axes[1, 0].set_title("(c) Torus gap with critical-line refinement", loc="left")
    for path_id, values in CRITICAL_U.items():
        color = PATH_STYLE[path_id][1]
        for value in values:
            axes[1, 0].axvline(value, color=color, ls=":", lw=0.9, alpha=0.7)
    axes[1, 1].set_ylabel(r"$\eta_{\rm topo}=C_{\rm MB}/2$")
    axes[1, 1].set_title("(d) Twist-averaged topological efficiency", loc="left")
    for ax in axes[1]:
        ax.set_xlabel(r"Hubbard $U$")
    axes[0, 1].set_xlabel(r"Hubbard $U$")
    fig.suptitle(r"L=8, $t=1$, translated Rice--Mele pump paths", fontsize=12)
    fig.savefig(output / "path_static_observables.png")
    fig.savefig(output / "path_static_observables.pdf")
    plt.close(fig)


def plot_amplitude_efficiency(center_static: list[dict], amplitude: list[dict], output: Path) -> None:
    U = np.asarray(sorted({float(row["U"]) for row in amplitude}))
    Delta0 = np.asarray([1.0, 2.0, 3.0, 4.0, 5.0])
    values = np.empty((Delta0.size, U.size))
    for i, D0 in enumerate(Delta0):
        if D0 == 3.0:
            rows = [row for row in center_static if float(row["t"]) == 1.0 and float(row["U"]) in U]
        else:
            rows = [row for row in amplitude if float(row["Delta0"]) == D0]
        by_u = {float(row["U"]): float(row["C_MB"]) / 2 for row in rows}
        values[i] = [by_u[value] for value in U]
    fig, ax = plt.subplots(figsize=(9.2, 4.2), constrained_layout=True)
    mesh = ax.pcolormesh(_edges(U), _edges(Delta0), values, cmap="RdBu_r", vmin=-0.05, vmax=1.05, shading="flat")
    ax.scatter(np.tile(U, Delta0.size), np.repeat(Delta0, U.size), s=6, color="black", alpha=0.45)
    ax.contour(U, Delta0, values, levels=[0.5], colors="white", linewidths=1.4)
    ax.set_xlabel(r"Hubbard $U$")
    ax.set_ylabel(r"path amplitude $\Delta_0$")
    ax.set_title(r"Twist-averaged topological efficiency $\eta_{\rm topo}=C_{\rm MB}/2$", loc="left")
    fig.colorbar(mesh, ax=ax, label=r"$\eta_{\rm topo}$")
    fig.savefig(output / "amplitude_efficiency.png")
    fig.savefig(output / "amplitude_efficiency.pdf")
    plt.close(fig)


def plot_path_charge_cycles(center_traces: Path, paths_root: Path, output: Path) -> None:
    with np.load(center_traces, allow_pickle=False) as center:
        fig, axes = plt.subplots(2, 2, figsize=(10.2, 7.0), sharex=True, constrained_layout=True)
        for ax, (U, token) in zip(axes.ravel(), TYPICAL):
            center_phi, center_adiabatic = _center_adiabatic_curve(
                center,
                token,
                U,
                paths_root,
            )
            ax.plot(
                center_phi / np.pi,
                center_adiabatic,
                "--",
                color=PATH_STYLE["center"][1],
                label=r"center, $Q_{\rm ad}$",
            )
            time = center[f"{token}_T10_times"]
            ax.plot(2 * time / 10, center[f"{token}_T10_cumulative"], color=PATH_STYLE["center"][1], label="center, T=10")
            for path_id in PATH_IDS:
                label, color = PATH_STYLE[path_id]
                static_path = paths_root / "static" / f"{path_id}_U_{_local_token(U)}.npz"
                realtime_path = paths_root / "realtime" / f"{path_id}_U_{_local_token(U)}_T_{_local_token(10.0)}.npz"
                with np.load(static_path, allow_pickle=False) as data:
                    polarization = data["polarization"] - data["polarization"][0]
                    ax.plot(data["phi"] / np.pi, polarization, "--", color=color, label=rf"{label}, $Q_{{\rm ad}}$")
                with np.load(realtime_path, allow_pickle=False) as data:
                    ax.plot(2 * data["times"] / 10, data["cumulative_charge"], color=color, label=f"{label}, T=10")
            ax.set_title(rf"$U={U:g}$", loc="left")
            ax.set_xlabel(r"pump phase $\phi/\pi$")
            ax.set_ylabel(r"accumulated charge $Q(\phi)$")
            ax.axhline(0, color="0.8", lw=0.8)
        handles, labels = axes[0, 0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="upper center", ncol=4, bbox_to_anchor=(0.5, 1.08))
        fig.suptitle(r"Adiabatic polarization winding and finite-time charge on translated paths", y=1.13, fontsize=12)
        fig.savefig(output / "path_charge_cycles.png", bbox_inches="tight")
        fig.savefig(output / "path_charge_cycles.pdf", bbox_inches="tight")
        plt.close(fig)


def plot_path_torus(center_traces: Path, paths_root: Path, output: Path) -> None:
    U, token = 7.25, "U7p25"
    with np.load(center_traces, allow_pickle=False) as center:
        datasets = [("center", center[f"{token}_e0_torus"], center[f"{token}_gap_torus"])]
        for path_id in ("shift-1p5", "near-tangent", "outside"):
            with np.load(paths_root / "static" / f"{path_id}_U_{_local_token(U)}.npz", allow_pickle=False) as data:
                datasets.append((path_id, np.asarray(data["e0"]), np.asarray(data["gap"])))
    fig, axes = plt.subplots(2, 4, figsize=(13, 5.4), constrained_layout=True, sharex=True, sharey=True)
    for column, (path_id, e0, gap) in enumerate(datasets):
        label, _ = PATH_STYLE[path_id]
        top = axes[0, column].imshow(e0 - e0.min(), origin="lower", extent=(0, 2, 0, 2), aspect="auto", cmap="cividis")
        bottom = axes[1, column].imshow(gap, origin="lower", extent=(0, 2, 0, 2), aspect="auto", cmap="magma")
        axes[0, column].set_title(label)
        axes[1, column].set_xlabel(r"$\phi/\pi$")
        fig.colorbar(top, ax=axes[0, column], pad=0.02)
        fig.colorbar(bottom, ax=axes[1, column], pad=0.02)
    axes[0, 0].set_ylabel(r"$\theta/\pi$; $E_0-E_{0,\min}$")
    axes[1, 0].set_ylabel(r"$\theta/\pi$; $E_1-E_0$")
    fig.suptitle(r"Path-resolved torus spectrum at $L=8,t=1,U=7.25$", fontsize=12)
    fig.savefig(output / "path_torus_energy_gap.png")
    fig.savefig(output / "path_torus_energy_gap.pdf")
    plt.close(fig)


def plot_paths_interactive(
    center_static: list[dict],
    local_static: list[dict],
    refined_static: list[dict],
    critical_gap: list[dict],
    amplitude: list[dict],
    output: Path,
) -> None:
    grouped = _path_rows(center_static, local_static, refined_static)
    fig = make_subplots(rows=2, cols=2, subplot_titles=("Chern number", "Minimum gap", "Topological efficiency", "Path-amplitude topological efficiency"))
    for path_id, rows in grouped.items():
        label, color = PATH_STYLE[path_id]
        U = [float(row["U"]) for row in rows]
        fig.add_trace(go.Scatter(x=U, y=[float(row["C_MB"]) for row in rows], name=label, line={"color": color}, legendgroup=path_id), row=1, col=1)
        gap_by_u = {float(row["U"]): float(row["Delta_min"]) for row in rows}
        gap_by_u.update(
            {
                float(row["U"]): float(row["Delta_min_line"])
                for row in critical_gap
                if row["path_id"] == path_id
            }
        )
        gap_u = sorted(gap_by_u)
        fig.add_trace(go.Scatter(x=gap_u, y=[gap_by_u[value] for value in gap_u], name=label, line={"color": color}, legendgroup=path_id, showlegend=False), row=1, col=2)
        fig.add_trace(go.Scatter(x=U, y=[float(row["C_MB"]) / 2 for row in rows], name=label, line={"color": color}, legendgroup=path_id, showlegend=False), row=2, col=1)
    for D0 in (1.0, 2.0, 4.0, 5.0):
        rows = sorted((row for row in amplitude if float(row["Delta0"]) == D0), key=lambda row: float(row["U"]))
        fig.add_trace(go.Scatter(x=[float(row["U"]) for row in rows], y=[float(row["C_MB"]) / 2 for row in rows], name=f"Delta0={D0:g}", showlegend=False), row=2, col=2)
    fig.update_yaxes(type="log", row=1, col=2)
    fig.update_xaxes(title_text="Hubbard U")
    fig.update_layout(title="L=8 path-resolved Thouless transport", height=800, width=1200)
    _write_html(fig, output / "path_transport_interactive.html")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--paths", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    static = _rows(args.source / "static_summary.csv")
    realtime = _rows(args.source / "realtime_summary.csv")
    _style()
    plot_phase_maps(static, realtime, args.output)
    refined_static = None
    critical_gap = None
    if args.paths is not None:
        refined_static = _rows(args.paths / "refined_static_summary.csv")
        critical_gap = _rows(args.paths / "critical_gap_summary.csv")
    plot_u_transport(static, realtime, args.output, refined_static, critical_gap)
    traces = args.source / "center_transport_traces.npz"
    plot_typical_cycles(traces, args.output, args.paths)
    plot_torus_maps(traces, args.output)
    plot_interactive(static, realtime, args.output)
    if args.paths is not None:
        local_static = _rows(args.paths / "static_summary.csv")
        assert refined_static is not None and critical_gap is not None
        amplitude = _rows(args.paths / "amplitude_summary.csv")
        plot_path_observables(static, local_static, refined_static, critical_gap, args.output)
        plot_amplitude_efficiency(static, amplitude, args.output)
        plot_path_charge_cycles(traces, args.paths, args.output)
        plot_path_torus(traces, args.paths, args.output)
        plot_paths_interactive(static, local_static, refined_static, critical_gap, amplitude, args.output)


if __name__ == "__main__":
    main()
