"""Deterministic bilingual plots generated only from frozen summary arrays."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

import matplotlib

matplotlib.use("Agg")
from matplotlib import font_manager, pyplot as plt
import numpy as np

from .locale import Locale, get_locale


PLOT_NAMES = (
    "xy-phase-scan.png",
    "diii-phase-scan.png",
    "entanglement-arcs.png",
    "entropy-coefficients.png",
    "casimir-fit.png",
    "bootstrap-amplitude.png",
    "anisotropy-calibration.png",
    "alpha-sensitivity.png",
    "negative-control.png",
    "runtime-ess.png",
)


def make_plots(summary: dict, locale: str, output_dir: Path) -> list[Path]:
    language = get_locale(locale)
    _configure_font(language)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    renderers: tuple[Callable[[dict, Locale], tuple[plt.Figure, plt.Axes]], ...] = (
        _xy_scan,
        _diii_scan,
        _entanglement_arcs,
        _entropy_coefficients,
        _casimir,
        _bootstrap,
        _anisotropy,
        _alpha_sensitivity,
        _negative_control,
        _runtime,
    )
    paths = []
    for name, renderer in zip(PLOT_NAMES, renderers, strict=True):
        figure, _ = renderer(summary, language)
        path = output_dir / name
        figure.savefig(
            path,
            dpi=180,
            bbox_inches="tight",
            facecolor="white",
            metadata={"Software": "learning-mit deterministic plotter"},
        )
        plt.close(figure)
        paths.append(path)
    return paths


def plot_data_hashes(summary: dict, locale: str | None = None) -> tuple[str, ...]:
    del locale
    data = (
        summary.get("xy", {}),
        summary.get("diii", {}),
        summary.get("entanglement", {}).get("arcs", []),
        summary.get("entanglement", {}).get("coefficients", []),
        summary.get("casimir", {}),
        summary.get("bootstrap", {}),
        summary.get("anisotropy", {}).get("spatial", [])
        + summary.get("anisotropy", {}).get("temporal", []),
        summary.get("anisotropy", {}).get("window_estimates", []),
        summary.get("negative_control", {}),
        {
            "runtime": summary.get("runtime", {}),
            "ess": summary.get("bootstrap", {}).get("effective_sample_size"),
        },
    )
    return tuple(
        hashlib.sha256(
            json.dumps(item, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        for item in data
    )


def _figure() -> tuple[plt.Figure, plt.Axes]:
    figure, axis = plt.subplots(figsize=(7.2, 4.25))
    axis.grid(True, color="#dce5ea", linewidth=0.7, alpha=0.8)
    axis.spines[["top", "right"]].set_visible(False)
    return figure, axis


def _scan(summary: dict, locale: Locale, key: str) -> tuple[plt.Figure, plt.Axes]:
    figure, axis = _figure()
    section = summary[key]
    x = [point["phi_pi"] for point in section.get("evidence", [])]
    y = [point["score"] for point in section.get("evidence", [])]
    axis.plot(x, y, "o-", color="#175a7a", linewidth=2)
    axis.axhline(0, color="#7b8790", linewidth=1)
    if section.get("bracket"):
        axis.axvspan(*section["bracket"], color="#d9853b", alpha=0.2)
    if key == "xy" and section.get("reference_window"):
        axis.axvspan(*section["reference_window"], color="#2d8b68", alpha=0.12)
    axis.set(xlabel=locale.labels["phi"], ylabel=locale.labels["evidence"])
    axis.set_title(locale.labels[f"{key}_scan"], loc="left", fontweight="bold")
    return figure, axis


def _xy_scan(summary: dict, locale: Locale):
    return _scan(summary, locale, "xy")


def _diii_scan(summary: dict, locale: Locale):
    return _scan(summary, locale, "diii")


def _entanglement_arcs(summary: dict, locale: Locale):
    figure, axis = _figure()
    for arc in summary.get("entanglement", {}).get("arcs", []):
        points = np.asarray(arc["points"], dtype=float)
        axis.plot(points[:, 0], points[:, 1], "o-", label=arc["label"])
    axis.set(xlabel=locale.labels["interval"], ylabel=locale.labels["entropy"])
    axis.legend(frameon=False, fontsize=8)
    return figure, axis


def _entropy_coefficients(summary: dict, locale: Locale):
    figure, axis = _figure()
    rows = summary.get("entanglement", {}).get("coefficients", [])
    x = np.arange(len(rows))
    for name, color in (("v", "#277c5a"), ("c_prime", "#b95c23"), ("c", "#175a7a")):
        axis.plot(x, [row[name] for row in rows], "o-", label=name, color=color)
    axis.set(
        xticks=x,
        xticklabels=[f"{row['phi_pi']:.2f}/L{row['width']}" for row in rows],
        ylabel=locale.labels["coefficient"],
    )
    axis.legend(frameon=False)
    return figure, axis


def _casimir(summary: dict, locale: Locale):
    figure, axis = _figure()
    data = summary.get("casimir", {})
    width = data.get("widths", [])
    axis.plot(width, data.get("gamma", []), "o", color="#175a7a", label=locale.labels["data"])
    axis.plot(width, data.get("fitted", []), "-", color="#b95c23", label=locale.labels["fit"])
    twin = axis.twinx()
    twin.plot(width, data.get("residuals", []), "s--", color="#697780", label=locale.labels["residual"])
    twin.set_ylabel(locale.labels["residual"])
    axis.set(xlabel=locale.labels["width"], ylabel=locale.labels["gamma"])
    axis.legend(frameon=False, loc="upper left")
    return figure, axis


def _bootstrap(summary: dict, locale: Locale):
    figure, axis = _figure()
    samples = summary.get("bootstrap", {}).get("amplitude_samples", [])
    axis.hist(samples, bins=min(16, max(5, len(samples))), color="#175a7a", alpha=0.8)
    axis.set(xlabel=locale.labels["amplitude"], ylabel=locale.labels["count"])
    return figure, axis


def _anisotropy(summary: dict, locale: Locale):
    figure, axis = _figure()
    data = summary.get("anisotropy", {})
    spatial = np.asarray(data.get("spatial", []), dtype=float)
    if spatial.size:
        axis.loglog(spatial[:, 0], np.abs(spatial[:, 1]), "o-", color="#175a7a")
    axis.set(xlabel=locale.labels["distance"], ylabel=locale.labels["correlation"])
    twin = axis.twinx()
    temporal = np.asarray(data.get("temporal", []), dtype=float)
    if temporal.size:
        twin.plot(temporal[:, 0], temporal[:, 1], "s--", color="#b95c23")
    twin.set_ylabel(locale.labels["gap"])
    return figure, axis


def _alpha_sensitivity(summary: dict, locale: Locale):
    figure, axis = _figure()
    rows = summary.get("anisotropy", {}).get("window_estimates", [])
    x = np.arange(len(rows))
    axis.errorbar(
        x,
        [row["alpha"] for row in rows],
        yerr=[row["error"] for row in rows],
        fmt="o",
        color="#175a7a",
        capsize=4,
    )
    window_labels = [_localized_window(row["window"], locale) for row in rows]
    axis.set(xticks=x, xticklabels=window_labels, ylabel=locale.labels["alpha"])
    axis.tick_params(axis="x", rotation=15)
    return figure, axis


def _negative_control(summary: dict, locale: Locale):
    figure, axis = _figure()
    data = summary.get("negative_control", {})
    axis.bar(
        ["Born", "IID"],
        [data.get("born_mean", 0), data.get("iid_mean", 0)],
        color=["#277c5a", "#b95c23"],
    )
    axis.set_ylabel(locale.labels["mean"])
    return figure, axis


def _runtime(summary: dict, locale: Locale):
    figure, axis = _figure()
    rows = summary.get("runtime", {}).get("allocation", [])
    labels = [_localized_runtime(row[0], locale) for row in rows]
    minutes = [row[1] for row in rows]
    axis.barh(labels, minutes, color="#175a7a")
    axis.set_xlabel(locale.labels["minutes"])
    ess = summary.get("bootstrap", {}).get("effective_sample_size")
    if ess is not None:
        axis.text(
            0.98,
            0.05,
            f"{locale.labels['ess']}: {ess:.1f}",
            transform=axis.transAxes,
            ha="right",
            color="#324b5a",
        )
    return figure, axis


def _configure_font(locale: Locale) -> None:
    if locale.code == "zh":
        candidates = (
            Path("/System/Library/Fonts/STHeiti Medium.ttc"),
            Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
        )
        for path in candidates:
            if path.is_file():
                font_manager.fontManager.addfont(str(path))
                family = font_manager.FontProperties(fname=str(path)).get_name()
                plt.rcParams["font.family"] = family
                break
        else:
            raise RuntimeError("no usable local CJK font found for Chinese plots")
    else:
        plt.rcParams["font.family"] = "DejaVu Sans"
    plt.rcParams["axes.unicode_minus"] = False


def _localized_runtime(value: str, locale: Locale) -> str:
    if locale.code != "zh":
        return value
    return {
        "Oracles/benchmark": "预言机/基准",
        "XY scan": "XY 扫描",
        "DIII coarse": "DIII 粗扫描",
        "Refinement": "细化",
        "Analysis/report": "分析/报告",
        "xy-coarse": "XY 粗扫描",
        "diii-coarse": "DIII 粗扫描",
        "diii-refine": "DIII 细化",
    }.get(value, value)


def _localized_window(value: str, locale: Locale) -> str:
    if locale.code != "zh":
        return value
    return {
        "L/8–3L/8": "L/8 至 3L/8",
        "L/6–L/3": "L/6 至 L/3",
        "drop first block": "删除首块",
    }.get(value, value.replace("–", " 至 "))
