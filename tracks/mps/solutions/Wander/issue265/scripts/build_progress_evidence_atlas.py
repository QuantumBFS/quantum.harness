#!/usr/bin/env python3
"""Render the first provenance-backed Hydrodynamic Evidence Atlas release."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.progress_atlas.io import (
    load_final_datasets,
    load_json,
    load_partial_progress,
)
from src.progress_atlas.metrics import (
    common_coordinate_indices,
    normalized_even_odd_residual,
)
from src.progress_atlas.style import COLORS, apply_style


ROOT = PROJECT_ROOT
SNAPSHOT = ROOT / "artifacts/progress_atlas/source_data"
OUTPUT = ROOT / "artifacts/progress_atlas/figures"
METRICS = ROOT / "artifacts/progress_atlas/metrics"

CONDITION_LABELS = {
    "amp_mu005_up": r"wall $+\mu$",
    "amp_mu005_down": r"wall $-\mu$",
    "background_p005_up": r"background $m_0=0.05$",
    "shape_double_wall": "double wall",
}
CONDITION_ORDER = [
    "amp_mu005_up",
    "amp_mu005_down",
    "background_p005_up",
    "shape_double_wall",
]
RESOLUTION_ORDER = ["coarse", "medium", "fine"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def metadata(dataset: dict) -> dict:
    return json.loads(str(dataset["metadata_json"].item()))


def stem(condition: str, resolution: str) -> str:
    return f"{condition}__convergence__{resolution}"


def build_job_table(datasets: dict, partial: dict, submission: dict) -> list[dict]:
    summaries = {}
    for path in (SNAPSHOT / "final").glob("*.run.json"):
        summaries[path.stem.removesuffix(".run")] = load_json(path)
    rows = []
    for source in submission["jobs"]:
        job_id = source["job_id"]
        condition = source["condition_id"]
        resolution = source["resolution_level"]
        if job_id in summaries:
            summary = summaries[job_id]
            data = datasets[job_id]
            meta = metadata(data)
            rows.append(
                {
                    "job_id": job_id,
                    "condition": condition,
                    "resolution": resolution,
                    "status": "complete artifact",
                    "t_max": float(data["t"][-1]),
                    "chi": int(summary["maximum_chi_observed"]),
                    "discarded": float(summary["discarded_weight_cumulative"]),
                    "drift": float(summary["maximum_total_magnetization_drift"]),
                    "wall_seconds": float(summary["wall_time_seconds"]),
                    "fcs": int(summary["fcs_branch_count"]),
                    "L": int(meta["L"]),
                }
            )
        else:
            record = partial[job_id]
            rows.append(
                {
                    "job_id": job_id,
                    "condition": condition,
                    "resolution": resolution,
                    "status": "checkpointed TIMEOUT",
                    "t_max": float(record["t"]),
                    "chi": int(record["chi_max_observed"]),
                    "discarded": float(record["discarded_weight_cumulative"]),
                    "drift": abs(float(record["magnetization_drift"])),
                    "wall_seconds": float(record["elapsed_seconds"]),
                    "fcs": int(record["fcs_branch_count"]),
                    "L": {"medium": 384, "fine": 512}[resolution],
                }
            )
    return sorted(
        rows,
        key=lambda r: (
            CONDITION_ORDER.index(r["condition"]),
            RESOLUTION_ORDER.index(r["resolution"]),
        ),
    )


def convergence_metrics(datasets: dict) -> dict:
    result = {}
    for condition, background in (
        ("background_p005_up", 0.05),
        ("shape_double_wall", 0.0),
    ):
        coarse = datasets[stem(condition, "coarse")]
        medium = datasets[stem(condition, "medium")]
        ic, im = common_coordinate_indices(coarse["x"], medium["x"], 100.0)
        signal = medium["m"][:, im] - background
        delta = medium["m"][:, im] - coarse["m"][:, ic]
        m_rel = np.linalg.norm(delta, axis=1) / np.maximum(
            np.linalg.norm(signal, axis=1), 1e-30
        )
        xjc = (coarse["x"][:-1] + coarse["x"][1:]) / 2
        xjm = (medium["x"][:-1] + medium["x"][1:]) / 2
        jc, jm = common_coordinate_indices(xjc, xjm, 100.0)
        j_delta = medium["current"][:, jm] - coarse["current"][:, jc]
        j_rel = np.linalg.norm(j_delta, axis=1) / np.maximum(
            np.linalg.norm(medium["current"][:, jm], axis=1), 1e-30
        )
        result[condition] = {
            "t": coarse["t"].tolist(),
            "m_relative_l2": m_rel.tolist(),
            "j_relative_l2": j_rel.tolist(),
            "m_max_abs": np.max(np.abs(delta), axis=1).tolist(),
            "j_max_abs": np.max(np.abs(j_delta), axis=1).tolist(),
        }
    return result


def spin_metrics(datasets: dict) -> dict:
    up = datasets[stem("amp_mu005_up", "coarse")]
    down = datasets[stem("amp_mu005_down", "coarse")]
    fcs_res = []
    for a, b in zip(up["fcs_logZ"], down["fcs_logZ"]):
        reflected = a[::-1]
        fcs_res.append(
            float(np.linalg.norm(b - reflected) / max(np.linalg.norm(b + reflected), 1e-30))
        )
    return {
        "t": up["t"].tolist(),
        "m_even_odd": normalized_even_odd_residual(up["m"], down["m"]),
        "j_even_odd": normalized_even_odd_residual(up["current"], down["current"]),
        "czz_odd_even": normalized_even_odd_residual(
            up["czz"] - down["czz"], up["czz"] + down["czz"]
        ),
        "fcs_orientation": fcs_res,
    }


def width_metrics(dataset: dict) -> dict:
    x = dataset["x"]
    t = dataset["t"]
    background = metadata(dataset).get("background_m", 0.0)
    signal = dataset["m"] - background
    gradient = np.abs(np.gradient(signal, x, axis=1))
    norm = np.sum(gradient, axis=1)
    center = np.sum(gradient * x[None, :], axis=1) / np.maximum(norm, 1e-30)
    width2 = np.sum(gradient * (x[None, :] - center[:, None]) ** 2, axis=1) / np.maximum(
        norm, 1e-30
    )
    ell = np.sqrt(np.maximum(width2 - width2[0], 0.0))
    valid = t >= 5.0
    beta = np.full_like(t, np.nan)
    beta[valid] = np.gradient(
        np.log(np.maximum(ell[valid], 1e-12)), np.log(t[valid])
    )
    return {"t": t, "ell": ell, "beta": beta}


def save_metrics(rows: list[dict], convergence: dict, spin: dict) -> None:
    METRICS.mkdir(parents=True, exist_ok=True)
    payloads = {
        "job_coverage.json": {"schema": 1, "jobs": rows},
        "convergence.json": {"schema": 1, "common_window": [-100, 100], **convergence},
        "spin_symmetry.json": {"schema": 1, **spin},
    }
    for name, payload in payloads.items():
        (METRICS / name).write_text(json.dumps(payload, indent=2) + "\n")


def clean_axis(ax, grid: str = "y") -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis=grid, color=COLORS["grid"], linewidth=0.7, alpha=0.75)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def title(fig, headline: str, subtitle: str = "") -> None:
    # Reserve the rightmost title rail for the status badge. Deterministic
    # wrapping keeps PNG, PDF, and SVG exports visually identical.
    wrapped = textwrap.fill(headline, width=68, break_long_words=False)
    lines = wrapped.count("\n") + 1
    fig.text(0.055, 0.955, wrapped, ha="left", va="top", fontsize=21.5,
             linespacing=1.04, weight="bold", color=COLORS["ink"])
    if subtitle:
        subtitle_y = 0.895 if lines == 1 else 0.845
        fig.text(0.055, subtitle_y, subtitle, ha="left", va="top", fontsize=11.2, color="#586574")


def badge(fig, text: str, color: str = COLORS["risk"]) -> None:
    fig.text(
        0.945,
        0.947,
        text,
        ha="right",
        va="top",
        fontsize=10,
        weight="bold",
        color=color,
        bbox=dict(boxstyle="round,pad=0.45", facecolor="white", edgecolor=color, linewidth=1.3),
    )


def panel_label(ax, label: str) -> None:
    ax.text(-0.08, 1.06, label, transform=ax.transAxes, fontsize=13, weight="bold", color=COLORS["ink"])


def save(fig, group: str, name: str, manifest: list[dict], caption: str) -> None:
    directory = OUTPUT / group
    directory.mkdir(parents=True, exist_ok=True)
    files = []
    for ext in ("png", "pdf", "svg"):
        path = directory / f"{name}.{ext}"
        fig.savefig(path, dpi=240 if ext == "png" else None, facecolor=fig.get_facecolor())
        files.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path)})
    plt.close(fig)
    manifest.append({"name": name, "group": group, "caption": caption, "files": files})


def specimen(manifest: list[dict]) -> None:
    fig = plt.figure(figsize=(16, 9))
    title(fig, "Hydrodynamic Evidence Atlas", "Visual specimen · fixed hierarchy, evidence language, and collision-safe layout")
    badge(fig, "GATE NOT ACCEPTED")
    ax = fig.add_axes([0.055, 0.12, 0.89, 0.70])
    ax.axis("off")
    names = ["magnetization", "current", "kpz", "memory", "risk", "unresolved"]
    for i, name in enumerate(names):
        x = 0.02 + (i % 3) * 0.32
        y = 0.74 - (i // 3) * 0.23
        ax.add_patch(FancyBboxPatch((x, y), 0.28, 0.16, boxstyle="round,pad=0.018", facecolor="white", edgecolor=COLORS["grid"], linewidth=1.2))
        ax.add_patch(FancyBboxPatch((x + 0.02, y + 0.04), 0.055, 0.08, boxstyle="round,pad=0.01", facecolor=COLORS[name], edgecolor="none"))
        ax.text(x + 0.095, y + 0.096, name.replace("_", " ").title(), va="center", fontsize=16, weight="bold", color=COLORS["ink"])
        ax.text(x + 0.095, y + 0.052, COLORS[name], va="center", fontsize=10, color="#66717E")
    ax.text(0.02, 0.27, "Evidence states", fontsize=17, weight="bold", color=COLORS["ink"])
    states = [("complete artifact", COLORS["kpz"]), ("checkpointed TIMEOUT", COLORS["risk"]), ("unresolved", COLORS["unresolved"])]
    for i, (label, color) in enumerate(states):
        ax.text(0.02 + i * 0.31, 0.17, label, fontsize=12, color=color, weight="bold", bbox=dict(boxstyle="round,pad=.42", facecolor="white", edgecolor=color))
    save(fig, "hero", "00_visual_specimen", manifest, "Visual tokens and evidence-state language used throughout the atlas.")


def hero_evidence_map(rows: list[dict], manifest: list[dict]) -> None:
    fig = plt.figure(figsize=(16, 9))
    title(fig, "Six complete trajectories constrain the picture; the gate remains open", "Four initial states connect numerical coverage to the effective-equation hierarchy")
    badge(fig, "6 / 12 COMPLETE")
    left = fig.add_axes([0.045, 0.16, 0.275, 0.65]); left.axis("off")
    levels = [("Microscopic continuity", COLORS["ink"]), ("Infinite-mode fluctuating GHD", COLORS["magnetization"]), ("Projected Mori memory", COLORS["memory"]), ("KPZ / two-mode / running coefficients", COLORS["kpz"]), ("Finite-window Burgers surrogate", COLORS["current"])]
    ys = np.linspace(0.88, 0.10, len(levels))
    for i, ((label, color), y) in enumerate(zip(levels, ys)):
        left.add_patch(FancyBboxPatch((0.04, y - 0.06), 0.88, 0.12, boxstyle="round,pad=.018", facecolor="white", edgecolor=color, linewidth=1.8))
        left.text(0.48, y, label, ha="center", va="center", fontsize=11.2, weight="bold", color=color)
        if i < len(levels) - 1:
            left.add_patch(FancyArrowPatch((0.48, y - 0.065), (0.48, ys[i + 1] + 0.066), arrowstyle="-|>", mutation_scale=13, color="#95A0AC", linewidth=1.2))
    ax = fig.add_axes([0.47, 0.20, 0.48, 0.57])
    short_conditions = {
        "amp_mu005_up": "+ wall",
        "amp_mu005_down": "− wall",
        "background_p005_up": "background",
        "shape_double_wall": "double wall",
    }
    labels = [f"{short_conditions[r['condition']]} · {r['resolution']}" for r in rows][::-1]
    vals = [r["t_max"] for r in rows][::-1]
    colors = [COLORS["kpz"] if r["status"] == "complete artifact" else COLORS["risk"] for r in rows][::-1]
    y = np.arange(len(rows))
    ax.barh(y, [200] * len(rows), color="#E9EEF3", height=0.62)
    ax.barh(y, vals, color=colors, height=0.62)
    ax.axvspan(50, 200, color=COLORS["magnetization"], alpha=0.035)
    ax.axvline(50, color="#8591A0", linestyle="--", linewidth=1)
    ax.axvline(200, color="#8591A0", linestyle="--", linewidth=1)
    ax.set_yticks(y, labels); ax.tick_params(axis="y", labelsize=8.8, pad=5); ax.set_xlim(0, 212); ax.set_xticks([0, 50, 100, 150, 200]); ax.set_xlabel("physical time reached")
    clean_axis(ax, "x")
    ax.text(50, len(rows) - 0.1, "analysis window", ha="left", va="bottom", fontsize=9, color="#687481")
    fig.text(0.47, 0.115, "AVAILABLE  profile tests", color=COLORS["kpz"], weight="bold", fontsize=9.8)
    fig.text(0.665, 0.115, "UNRESOLVED  current", color=COLORS["current"], weight="bold", fontsize=9.8)
    fig.text(0.855, 0.115, "NEXT  frozen audit", color=COLORS["risk"], weight="bold", fontsize=9.8)
    save(fig, "hero", "01_evidence_map", manifest, "Current numerical coverage mapped onto the controlled hydrodynamic reduction hierarchy.")


def hero_time_coverage(rows: list[dict], manifest: list[dict]) -> None:
    fig, (ax, cost) = plt.subplots(1, 2, figsize=(16, 9), gridspec_kw={"width_ratios": [1.55, 1], "wspace": 0.28})
    fig.subplots_adjust(left=.15, right=.95, top=.80, bottom=.13)
    title(fig, "Physical time—not file count—is the limiting resource", "Fine amplitude runs have not yet entered the preregistered 50 < t < 200 analysis window")
    badge(fig, "6 CHECKPOINTED TIMEOUTS")
    labels = [f"{CONDITION_LABELS[r['condition']]} · {r['resolution']}" for r in rows][::-1]
    values = np.array([r["t_max"] for r in rows][::-1])
    status = [r["status"] for r in rows][::-1]
    y = np.arange(len(rows))
    ax.barh(y, 200, color="#E8EDF2", height=.58)
    ax.barh(y, values, color=[COLORS["kpz"] if s == "complete artifact" else COLORS["risk"] for s in status], height=.58)
    ax.set_yticks(y, labels); ax.set_xlim(0, 210); ax.set_xticks([0, 50, 100, 150, 200]); ax.set_xlabel("$t_{max}$")
    ax.axvline(50, color=COLORS["ink"], linestyle="--", linewidth=1.1)
    ax.axvline(200, color=COLORS["ink"], linestyle=":", linewidth=1.1)
    for yi, val in zip(y, values): ax.text(min(val + 3, 202), yi, f"{val:.0f}", va="center", fontsize=9, color=COLORS["ink"])
    clean_axis(ax, "x"); panel_label(ax, "a")
    rates = np.array([r["wall_seconds"] / 86400 / max(r["t_max"], 1e-9) for r in rows])
    markers = {"coarse": "o", "medium": "s", "fine": "^"}
    for condition in CONDITION_ORDER:
        subset = [r for r in rows if r["condition"] == condition]
        for r in subset:
            cost.scatter(r["t_max"], r["wall_seconds"] / 86400, s=95, marker=markers[r["resolution"]], color=COLORS["risk"] if r["status"] != "complete artifact" else COLORS["magnetization"], edgecolor="white", linewidth=1.2, zorder=3)
    cost.set_xlabel("physical time reached"); cost.set_ylabel("cumulative wall time [days]")
    clean_axis(cost); panel_label(cost, "b")
    cost.text(.04, .97, "marker: ○ coarse   □ medium   △ fine", transform=cost.transAxes, va="top", fontsize=10, color="#64707D")
    save(fig, "hero", "02_time_coverage", manifest, "Physical-time coverage and cumulative wall-time cost for all twelve convergence jobs.")


def profile_pair(ax, datasets: dict, condition: str, observable: str, tt: float) -> None:
    coarse = datasets[stem(condition, "coarse")]
    medium = datasets[stem(condition, "medium")]
    color = COLORS["magnetization"] if observable == "m" else COLORS["current"]
    if observable == "m":
        xc, xm = coarse["x"], medium["x"]
    else:
        xc = (coarse["x"][:-1] + coarse["x"][1:]) / 2
        xm = (medium["x"][:-1] + medium["x"][1:]) / 2
    it = int(np.argmin(abs(coarse["t"] - tt)))
    ax.plot(xc, coarse[observable][it], color=color, alpha=.42, linewidth=1.5, label="coarse")
    ax.plot(xm, medium[observable][it], color=color, linewidth=2.3, label="medium")
    ax.set_xlim(-110, 110); ax.set_title(f"{CONDITION_LABELS[condition]} · $t={tt:.0f}$", loc="left", weight="bold")
    clean_axis(ax)


def hero_convergence(datasets: dict, conv: dict, manifest: list[dict]) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(16, 9), gridspec_kw={"wspace": .28, "hspace": .42})
    fig.subplots_adjust(left=.07, right=.94, top=.80, bottom=.12)
    title(fig, "Profiles agree below 0.6%; current differences exceed 7%", "Common spatial window |x| ≤ 100 · numerical envelope, not a confidence interval")
    badge(fig, "PROFILE ≠ CLOSURE", COLORS["current"])
    profile_pair(axes[0,0], datasets, "background_p005_up", "m", 200)
    profile_pair(axes[0,1], datasets, "shape_double_wall", "m", 200)
    profile_pair(axes[1,0], datasets, "background_p005_up", "current", 200)
    profile_pair(axes[1,1], datasets, "shape_double_wall", "current", 200)
    for j, condition in enumerate(("background_p005_up", "shape_double_wall")):
        t = np.asarray(conv[condition]["t"])
        axes[0,2].plot(t, 100*np.asarray(conv[condition]["m_relative_l2"]), linewidth=2.2, label=CONDITION_LABELS[condition])
        axes[1,2].plot(t, 100*np.asarray(conv[condition]["j_relative_l2"]), linewidth=2.2, label=CONDITION_LABELS[condition])
    axes[0,2].set_title("magnetization sensitivity", loc="left", weight="bold"); axes[0,2].set_ylabel("relative $L^2$ difference [%]"); axes[0,2].set_ylim(0, .75)
    axes[1,2].set_title("current sensitivity", loc="left", weight="bold"); axes[1,2].set_ylabel("relative $L^2$ difference [%]"); axes[1,2].set_ylim(0, 10.5)
    for ax in axes[:,2]:
        ax.set_xlim(0,200); ax.set_xticks([0,50,100,150,200]); ax.set_xlabel("time"); clean_axis(ax); ax.legend(frameon=False, loc="upper left")
    for i, ax in enumerate(axes.flat): panel_label(ax, chr(ord('a')+i))
    save(fig, "hero", "03_profile_current_convergence", manifest, "Coarse--medium comparison of magnetization and current in the two fully completed resolution pairs.")


def hero_dynamics(datasets: dict, manifest: list[dict]) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 9), gridspec_kw={"wspace":.17,"hspace":.34})
    fig.subplots_adjust(left=.08,right=.925,top=.80,bottom=.11)
    title(fig, "Four initial states probe distinct closure failures", "Raw coarse magnetization trajectories · common physical axes and color scale · no checkpoint interpolation")
    badge(fig, "RAW FINAL NPZ", COLORS["magnetization"])
    images = []
    common_vmax = 0.025
    for ax, condition in zip(axes.flat, CONDITION_ORDER):
        data=datasets[stem(condition,"coarse")]; bg=metadata(data).get("background_m",0.0); z=data["m"]-bg
        image=ax.imshow(z,origin="lower",aspect="auto",extent=[data["x"][0],data["x"][-1],data["t"][0],data["t"][-1]],cmap="RdBu_r",vmin=-common_vmax,vmax=common_vmax,rasterized=True)
        images.append(image)
        ax.set_xlim(-128,128); ax.set_xticks([-100,0,100]); ax.set_yticks([0,50,100,150,200]); ax.set_xlabel("position $x$"); ax.set_ylabel("time $t$"); ax.set_title(CONDITION_LABELS[condition],loc="left",weight="bold")
    cax = fig.add_axes([.945, .18, .010, .52])
    cb = fig.colorbar(images[-1], cax=cax)
    cb.ax.set_title(r"$m-m_{bg}$", fontsize=10, pad=7)
    for i,ax in enumerate(axes.flat): panel_label(ax,chr(ord('a')+i))
    save(fig,"hero","04_initial_state_dynamics",manifest,"Time--space magnetization maps for the four complete coarse trajectories.")


def hero_spin(datasets: dict, spin: dict, manifest: list[dict]) -> None:
    fig, axes=plt.subplots(2,3,figsize=(16,9),gridspec_kw={"wspace":.25,"hspace":.42})
    fig.subplots_adjust(left=.07,right=.94,top=.80,bottom=.11)
    title(fig,"Spin inversion remains accurate to the 10⁻³ level","Opposite-wall coarse trajectories test signs, parity, current orientation, and FCS reconstruction")
    badge(fig,"SYMMETRY CHECK PASSES",COLORS["kpz"])
    up=datasets[stem("amp_mu005_up","coarse")]; down=datasets[stem("amp_mu005_down","coarse")]
    for ax,tt in zip(axes[0],(20,100,200)):
        i=int(np.argmin(abs(up["t"]-tt))); ax.plot(up["x"],up["m"][i],color=COLORS["magnetization"],lw=2.2,label=r"$m_+$"); ax.plot(down["x"],-down["m"][i],color=COLORS["current"],lw=1.7,ls="--",label=r"$-m_-$"); ax.set_xlim(-100,100); ax.set_title(f"$t={tt}$",loc="left",weight="bold"); clean_axis(ax)
    axes[0,0].legend(frameon=False,loc="upper left")
    t=np.asarray(spin["t"])
    axes[1,0].semilogy(t,spin["m_even_odd"],color=COLORS["magnetization"],lw=2,label="magnetization")
    axes[1,1].semilogy(t,spin["j_even_odd"],color=COLORS["current"],lw=2,label="current")
    axes[1,2].semilogy(t,spin["fcs_orientation"],color=COLORS["memory"],lw=2,label="FCS")
    for ax in axes[1]: ax.set_xlim(0,200); ax.set_xticks([0,50,100,150,200]); ax.set_xlabel("time"); clean_axis(ax); ax.legend(frameon=False,loc="upper left")
    axes[1,0].set_ylabel("normalized residual")
    for i,ax in enumerate(axes.flat): panel_label(ax,chr(ord('a')+i))
    save(fig,"hero","05_spin_inversion",manifest,"Opposite-wall profile overlays and normalized spin-flip/FCS orientation residuals.")


def hero_scaling(datasets: dict, manifest: list[dict]) -> None:
    data=datasets[stem("background_p005_up","medium")]; wm=width_metrics(data); t=wm["t"]; ell=wm["ell"]; valid=t>=5
    fig,axes=plt.subplots(1,4,figsize=(16,9),gridspec_kw={"wspace":.33})
    fig.subplots_adjust(left=.07,right=.95,top=.78,bottom=.17)
    title(fig,"Broadening tests competing finite-time exponents","Background-wall medium trajectory · width from the second moment of |∂ₓm|")
    badge(fig,"EXPLORATORY SCALING",COLORS["unresolved"])
    axes[0].loglog(t[valid],ell[valid],color=COLORS["magnetization"],lw=2.3); axes[0].set_xlabel("time"); axes[0].set_ylabel(r"$\ell(t)$")
    powers=[.5,2/3,1.0]; labels=["diffusive $t^{1/2}$","KPZ $t^{2/3}$","ballistic $t$"]; colors=[COLORS["unresolved"],COLORS["kpz"],COLORS["current"]]
    for ax,p,label,c in zip(axes[1:],powers,labels,colors): ax.plot(t[valid],ell[valid]/t[valid]**p,color=c,lw=2.3); ax.set_xlabel("time"); ax.set_ylabel(rf"$\ell/t^{{{p:.3g}}}$"); ax.set_title(label,loc="left",weight="bold"); ax.set_xlim(5,200); clean_axis(ax)
    axes[0].set_title("raw broadening",loc="left",weight="bold"); clean_axis(axes[0])
    for i,ax in enumerate(axes): panel_label(ax,chr(ord('a')+i))
    fig.text(.07,.09,"A flatter compensated curve is more compatible with the displayed window; this is not a formal exponent decision.",fontsize=11,color="#5D6976")
    save(fig,"hero","06_scaling_competition",manifest,"Diffusive, KPZ, and ballistic compensation plots for the completed finite-background medium trajectory.")


def hero_closure(conv: dict, manifest: list[dict]) -> None:
    fig=plt.figure(figsize=(16,9)); title(fig,"Stable profiles can hide an unresolved current","The present data occupy the low-profile-residual / elevated-current-residual sector")
    badge(fig,"MEMORY REMAINS ELIGIBLE",COLORS["memory"])
    ax=fig.add_axes([.055,.16,.50,.66]); ax.axis("off")
    boxes=[(.05,.62,.35,.18,"Local closure",COLORS["current"],r"$j(t)=j[m(t),\partial_xm(t)]$"),(.59,.62,.35,.18,"Projected memory",COLORS["memory"],r"$j(t)=j_{loc}(t)+\int_0^tK(t-s)m(s)ds$")]
    for x,y,w,h,label,c,formula in boxes:
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=.025",facecolor="white",edgecolor=c,lw=2)); ax.text(x+w/2,y+h*.67,label,ha="center",va="center",fontsize=17,weight="bold",color=c); ax.text(x+w/2,y+h*.30,formula,ha="center",va="center",fontsize=13,color=COLORS["ink"])
    ax.add_patch(FancyArrowPatch((.22,.60),(.48,.35),arrowstyle="-|>",mutation_scale=16,color="#8D98A5")); ax.add_patch(FancyArrowPatch((.76,.60),(.52,.35),arrowstyle="-|>",mutation_scale=16,color="#8D98A5")); ax.text(.50,.29,"double wall + current",ha="center",fontsize=15,weight="bold",color=COLORS["ink"],bbox=dict(boxstyle="round,pad=.5",fc="white",ec=COLORS["grid"]))
    phase=fig.add_axes([.64,.20,.30,.55]); phase.set_xlim(0,1); phase.set_ylim(0,12); phase.axvspan(0,.6,color=COLORS["kpz"],alpha=.08); phase.axhspan(5,12,color=COLORS["memory"],alpha=.08); phase.set_xlabel("profile difference [%]"); phase.set_ylabel("current difference [%]"); phase.set_xticks([0,.2,.4,.6,.8,1.0]); phase.set_yticks([0,3,6,9,12]); clean_axis(phase)
    for condition,marker in (("background_p005_up","o"),("shape_double_wall","s")):
        x=100*np.asarray(conv[condition]["m_relative_l2"])[-1]; y=100*np.asarray(conv[condition]["j_relative_l2"])[-1]; phase.scatter(x,y,s=180,marker=marker,color=COLORS["memory"],edgecolor="white",lw=1.5,zorder=4,label=CONDITION_LABELS[condition])
    phase.legend(frameon=False,loc="upper right"); phase.text(.04,.96,"profile stable",transform=phase.transAxes,va="top",color=COLORS["kpz"],weight="bold"); phase.text(.04,.76,"current unresolved",transform=phase.transAxes,va="top",color=COLORS["memory"],weight="bold")
    save(fig,"hero","07_local_closure_vs_memory",manifest,"Conceptual distinction between local closure and projected memory, located by observed coarse--medium differences.")


def hero_hierarchy(manifest: list[dict]) -> None:
    fig=plt.figure(figsize=(16,9)); title(fig,"Fewer variables require stronger closure assumptions","Present evidence supports a hierarchy of effective descriptions rather than one exact scalar PDE")
    badge(fig,"CONTROLLED HIERARCHY",COLORS["magnetization"])
    ax=fig.add_axes([.08,.14,.84,.68]); ax.axis("off")
    levels=[("Full fluctuating GHD","exact hydrodynamic state",.88,COLORS["magnetization"]),("Physical magnetization + Mori kernel","exact projected structure",.70,COLORS["memory"]),("Two-mode / running local coefficients","controlled only with spectral separation",.52,COLORS["memory"]),("Stochastic Burgers / KPZ normal mode","long-wave stochastic reduction",.34,COLORS["kpz"]),("Deterministic Burgers mean surrogate","not rejected in available window",.16,COLORS["current"])]
    widths=np.linspace(.80,.48,len(levels))
    for i,((name,description,y,status),w) in enumerate(zip(levels,widths)):
        x=.5-w/2
        ax.add_patch(FancyBboxPatch((x,y-.055),w,.11,boxstyle="round,pad=.018",facecolor="white",edgecolor=status,lw=2))
        ax.text(.5,y+.016,name,ha="center",va="center",fontsize=16-i*.45,weight="bold",color=status)
        ax.text(.5,y-.026,description,ha="center",va="center",fontsize=10,color="#626F7C")
        if i<len(levels)-1:
            ax.add_patch(FancyArrowPatch((.5,y-.063),(.5,levels[i+1][2]+.063),arrowstyle="-|>",mutation_scale=14,color="#9AA4AF",lw=1.2))
    ax.text(.08,.025,"more variables · fewer closure assumptions",ha="left",fontsize=11.5,color="#65717E")
    ax.text(.92,.025,"fewer variables · stronger conditions",ha="right",fontsize=11.5,color="#65717E")
    save(fig,"hero","08_controlled_hierarchy",manifest,"Controlled hierarchy from infinite-mode fluctuating GHD to a finite-window deterministic Burgers surrogate.")


def support_profiles(datasets: dict, condition: str, observable: str, manifest: list[dict]) -> None:
    times=(20,50,100,150,200); fig,axes=plt.subplots(1,5,figsize=(16,5.8),sharey=True,gridspec_kw={"wspace":.10}); fig.subplots_adjust(left=.06,right=.95,top=.76,bottom=.16)
    obs_label="magnetization" if observable=="m" else "current"; title(fig,f"{CONDITION_LABELS[condition]}: {obs_label} across the full time window","coarse and medium final artifacts · common physical axes")
    badge(fig,"COMPLETE PAIR",COLORS["kpz"])
    for ax,tt in zip(axes,times): profile_pair(ax,datasets,condition,observable,tt); ax.set_title(f"$t={tt}$",loc="left",weight="bold"); ax.set_xlabel("$x$")
    axes[0].set_ylabel("$m$" if observable=="m" else "$j$"); axes[0].legend(frameon=False,loc="upper left")
    name=f"{condition}_{observable}_profiles"; save(fig,"support",name,manifest,f"Coarse--medium {obs_label} profiles at five representative times.")


def support_error_curves(conv: dict, manifest: list[dict]) -> None:
    fig,axes=plt.subplots(2,2,figsize=(16,9),gridspec_kw={"wspace":.22,"hspace":.35}); fig.subplots_adjust(left=.08,right=.95,top=.79,bottom=.12)
    title(fig,"Numerical sensitivity grows with time and is observable dependent","Relative L² and maximum pointwise coarse--medium differences in |x| ≤ 100")
    badge(fig,"NUMERICAL ENVELOPE",COLORS["unresolved"])
    for condition,c in (("background_p005_up",COLORS["magnetization"]),("shape_double_wall",COLORS["memory"])):
        t=np.asarray(conv[condition]["t"]); label=CONDITION_LABELS[condition]
        axes[0,0].plot(t,100*np.asarray(conv[condition]["m_relative_l2"]),lw=2,color=c,label=label); axes[0,1].plot(t,100*np.asarray(conv[condition]["j_relative_l2"]),lw=2,color=c,label=label); axes[1,0].plot(t,conv[condition]["m_max_abs"],lw=2,color=c,label=label); axes[1,1].plot(t,conv[condition]["j_max_abs"],lw=2,color=c,label=label)
    labels=[("magnetization relative", "difference [%]"),("current relative","difference [%]"),("magnetization pointwise","max |Δm|"),("current pointwise","max |Δj|")]
    for ax,(ttl,yl) in zip(axes.flat,labels): ax.set_title(ttl,loc="left",weight="bold"); ax.set_xlim(0,200); ax.set_xticks([0,50,100,150,200]); ax.set_xlabel("time"); ax.set_ylabel(yl); clean_axis(ax); ax.legend(frameon=False,loc="upper left")
    save(fig,"support","convergence_error_curves",manifest,"Time-dependent coarse--medium numerical sensitivity for profiles and currents.")


def support_resources(rows: list[dict], manifest: list[dict]) -> None:
    fig,axes=plt.subplots(1,3,figsize=(16,7.2),gridspec_kw={"wspace":.30}); fig.subplots_adjust(left=.08,right=.95,top=.76,bottom=.22)
    title(fig,"Conservation can remain excellent while accumulated truncation becomes severe","Resource and error indicators are complementary, not interchangeable")
    badge(fig,"AMPLITUDE / FCS IS COSTLIEST",COLORS["risk"])
    x=np.arange(len(rows)); labels=[f"{r['condition'].replace('background_p005_up','bg').replace('shape_double_wall','double').replace('amp_mu005_up','+μ').replace('amp_mu005_down','−μ')}\n{r['resolution'][0]}" for r in rows]
    axes[0].bar(x,[r["discarded"] for r in rows],color=[COLORS["risk"] if r["discarded"]>.1 else COLORS["magnetization"] for r in rows]); axes[0].set_yscale("log"); axes[0].set_ylabel("cumulative discarded weight")
    axes[1].bar(x,[max(r["drift"],1e-12) for r in rows],color=COLORS["kpz"]); axes[1].set_yscale("log"); axes[1].set_ylabel("magnetization drift")
    axes[2].bar(x,[r["wall_seconds"]/86400 for r in rows],color=[COLORS["risk"] if r["status"]!="complete artifact" else COLORS["memory"] for r in rows]); axes[2].set_ylabel("cumulative wall time [days]")
    for ax in axes: ax.set_xticks(x,labels,rotation=0); clean_axis(ax); ax.tick_params(axis="x",labelsize=8)
    save(fig,"support","resource_error_budget",manifest,"Discarded weight, magnetization drift, and cumulative wall time for all convergence jobs.")


def support_heatmaps(datasets: dict, manifest: list[dict]) -> None:
    for condition in CONDITION_ORDER:
        data=datasets[stem(condition,"coarse")]; bg=metadata(data).get("background_m",0.0)
        for observable,color_label in (("m",r"$m-m_{bg}$"),("current",r"$j$")):
            values=data[observable]; x=data["x"] if observable=="m" else (data["x"][:-1]+data["x"][1:])/2
            z=values-bg if observable=="m" else values; vmax=float(np.quantile(np.abs(z),.997)); vmax=max(vmax,1e-8)
            fig,ax=plt.subplots(figsize=(16,7.8)); fig.subplots_adjust(left=.08,right=.88,top=.78,bottom=.13)
            title(fig,f"{CONDITION_LABELS[condition]} · {'magnetization' if observable=='m' else 'current'} evolution","complete coarse artifact · symmetric color scale centered at zero")
            badge(fig,"RAW FINAL NPZ",COLORS["magnetization"] if observable=="m" else COLORS["current"])
            im=ax.imshow(z,origin="lower",aspect="auto",extent=[x[0],x[-1],data["t"][0],data["t"][-1]],cmap="RdBu_r",vmin=-vmax,vmax=vmax,rasterized=True); ax.set_xlim(-128,128); ax.set_xlabel("position $x$"); ax.set_ylabel("time $t$"); ax.set_xticks([-100,-50,0,50,100]); ax.set_yticks([0,50,100,150,200]); cb=fig.colorbar(im,ax=ax,fraction=.028,pad=.025); cb.set_label(color_label)
            save(fig,"support",f"{condition}_{observable}_spacetime",manifest,"Raw time--space field from the complete coarse trajectory.")


def contact_sheet(manifest: list[dict]) -> None:
    """Create a single visual index of the nine argument-level figures."""
    hero_items = [x for x in manifest if x["group"] == "hero"]
    fig, axes = plt.subplots(3, 3, figsize=(16, 9), gridspec_kw={"wspace": .025, "hspace": .06})
    fig.subplots_adjust(left=.025, right=.975, top=.90, bottom=.035)
    fig.text(.035, .965, "Hydrodynamic Evidence Atlas · visual index", ha="left", va="top",
             fontsize=22, weight="bold", color=COLORS["ink"])
    fig.text(.965, .963, "GATE NOT ACCEPTED", ha="right", va="top", fontsize=10,
             weight="bold", color=COLORS["risk"],
             bbox=dict(boxstyle="round,pad=.42", facecolor="white", edgecolor=COLORS["risk"], linewidth=1.2))
    for ax, item in zip(axes.flat, hero_items):
        png = next(ROOT / f["path"] for f in item["files"] if f["path"].endswith(".png"))
        ax.imshow(plt.imread(png))
        ax.set_axis_off()
        ax.set_title(item["name"].split("_", 1)[1].replace("_", " "), loc="left", fontsize=9.5,
                     color="#566371", pad=3)
    for ax in axes.flat[len(hero_items):]:
        ax.set_axis_off()
    save(fig, "overview", "00_atlas_contact_sheet", manifest,
         "Nine-panel visual index of the argument-level evidence atlas.")


def write_atlas_index(manifest: list[dict]) -> None:
    """Write a compact, browsable index without duplicating scientific claims."""
    atlas_root = ROOT / "artifacts/progress_atlas"
    lines = [
        "# Hydrodynamic Evidence Atlas\n",
        "Current evidence state: **convergence gate not accepted**. The figures show numerical evidence in the frozen snapshot; they do not claim a mathematically exact scalar closure.\n",
        "Each figure is exported as PNG, PDF, and editable-text SVG.\n",
    ]
    for group, heading in (("overview", "Atlas overview"), ("hero", "Core argument"), ("support", "Supporting views")):
        lines.append(f"## {heading}\n")
        for item in (x for x in manifest if x["group"] == group):
            png = next(x["path"] for x in item["files"] if x["path"].endswith(".png"))
            pdf = next(x["path"] for x in item["files"] if x["path"].endswith(".pdf"))
            svg = next(x["path"] for x in item["files"] if x["path"].endswith(".svg"))
            rel_png = Path(png).relative_to("artifacts/progress_atlas")
            rel_pdf = Path(pdf).relative_to("artifacts/progress_atlas")
            rel_svg = Path(svg).relative_to("artifacts/progress_atlas")
            lines.extend(
                [
                    f"### {item['name']}\n",
                    f"{item['caption']} [PDF]({rel_pdf}) · [SVG]({rel_svg})\n",
                    f"![{item['name']}]({rel_png})\n",
                ]
            )
    (atlas_root / "README.md").write_text("\n".join(lines), encoding="utf-8")


def build() -> None:
    apply_style("presentation")
    datasets=load_final_datasets(SNAPSHOT); partial=load_partial_progress(SNAPSHOT); submission=load_json(SNAPSHOT/"convergence_submission.json")
    rows=build_job_table(datasets,partial,submission); conv=convergence_metrics(datasets); spin=spin_metrics(datasets); save_metrics(rows,conv,spin)
    manifest=[]
    specimen(manifest); hero_evidence_map(rows,manifest); hero_time_coverage(rows,manifest); hero_convergence(datasets,conv,manifest); hero_dynamics(datasets,manifest); hero_spin(datasets,spin,manifest); hero_scaling(datasets,manifest); hero_closure(conv,manifest); hero_hierarchy(manifest)
    contact_sheet(manifest)
    for condition in ("background_p005_up","shape_double_wall"):
        support_profiles(datasets,condition,"m",manifest); support_profiles(datasets,condition,"current",manifest)
    support_error_curves(conv,manifest); support_resources(rows,manifest); support_heatmaps(datasets,manifest)
    out={"schema":1,"evidence_status":"gate not accepted","snapshot_manifest":"artifacts/progress_atlas/source_manifest.json","figures":manifest}
    (ROOT/"artifacts/progress_atlas/figure_manifest.json").write_text(json.dumps(out,indent=2)+"\n")
    write_atlas_index(manifest)
    print(json.dumps({"figures":len(manifest),"files":sum(len(x["files"]) for x in manifest)},indent=2))


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__); parser.parse_args(); build()


if __name__=="__main__": main()
