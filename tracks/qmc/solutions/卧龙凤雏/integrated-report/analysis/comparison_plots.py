"""Cross-model synthesis figures derived from frozen report values."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Patch

from analysis.locale import EN_LOCALE, ReportLocale
from analysis.sources import ModelResult


COLORS = ("#2878B5", "#D95F02", "#2A9D6F")
SHORT_NAMES = ("Clean Ising", "Nishimori", "Weak self-dual")
ZH_SHORT_NAMES = ("纯净 Ising", "Nishimori", "弱自对偶")

EN_COPY = {
    "estimate_ci": "Estimate with 95% CI",
    "benchmark": "Benchmark target",
    "central_xlabel": "Central charge or effective central charge",
    "central_title": "Three central-charge verifications",
    "band": "Nominal 95% band",
    "z_xlabel": "(estimate - target) / standard error",
    "z_title": "Deviation from each model's benchmark",
    "se": "SE",
    "half_width": "95% interval half-width",
    "precision": "Reported precision",
    "runtime_ylabel": "Recorded end-to-end runtime (s)",
    "runtime": "Frozen workflow runtime",
    "precision_runtime": "Precision and runtime are related but not equivalent",
    "target_agreement": "Target agreement",
    "fit_stability": "Fit stability",
    "sampling_stability": "Sampling stability",
    "physical_oracle": "Physical oracle",
    "numerical_invariants": "Numerical invariants",
    "convergence": "Convergence",
    "validation_title": "Required scientific-gate coverage",
    "passed_gate": "Passed required gate",
    "model_check": "Different model-specific check",
    "pass": "PASS",
    "na": "N/A",
    "fail": "FAIL",
    "seconds": "s",
}

ZH_COPY = {
    "estimate_ci": "估计值及 95% 置信区间",
    "benchmark": "基准目标值",
    "central_xlabel": "中心荷或有效中心荷",
    "central_title": "三种中心荷验证",
    "band": "名义 95% 区间",
    "z_xlabel": "（估计值 − 目标值）/ 标准误",
    "z_title": "相对各模型基准值的偏差",
    "se": "标准误",
    "half_width": "95% 区间半宽",
    "precision": "报告精度",
    "runtime_ylabel": "记录的端到端运行时间（秒）",
    "runtime": "冻结工作流运行时间",
    "precision_runtime": "精度与运行时间相关，但并不等价",
    "target_agreement": "目标一致性",
    "fit_stability": "拟合稳定性",
    "sampling_stability": "采样稳定性",
    "physical_oracle": "物理校验量",
    "numerical_invariants": "数值不变量",
    "convergence": "收敛性",
    "validation_title": "必需科学门控覆盖情况",
    "passed_gate": "通过必需门控",
    "model_check": "模型专属的其他检查",
    "pass": "通过",
    "na": "不适用",
    "fail": "失败",
    "seconds": "秒",
}


def build_comparison_plots(
    models: Sequence[ModelResult],
    output_dir: Path,
    locale: ReportLocale = EN_LOCALE,
) -> Dict[str, Path]:
    if len(models) != 3:
        raise ValueError("comparison plots require exactly three models")
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    copy = ZH_COPY if locale.code == "zh" else EN_COPY
    names = ZH_SHORT_NAMES if locale.code == "zh" else SHORT_NAMES
    apply_plot_style(locale)
    paths = {
        "central-charge-intervals": destination / "central-charge-intervals.png",
        "target-deviation": destination / "target-deviation.png",
        "precision-runtime": destination / "precision-runtime.png",
        "validation-gates": destination / "validation-gates.png",
    }
    _central_charge_intervals(models, paths["central-charge-intervals"], copy, names)
    _target_deviation(models, paths["target-deviation"], copy, names)
    _precision_runtime(models, paths["precision-runtime"], copy, names)
    _validation_gates(models, paths["validation-gates"], copy, names)
    return paths


def apply_plot_style(locale: ReportLocale = EN_LOCALE) -> None:
    font_family = "DejaVu Sans"
    if locale.code == "zh":
        font_family = _cjk_font().get_name()
    plt.rcParams.update(
        {
            "font.family": font_family,
            "font.size": 11,
            "axes.titlesize": 16,
            "axes.labelsize": 12,
            "axes.edgecolor": "#203040",
            "axes.linewidth": 0.9,
            "axes.grid": True,
            "grid.color": "#DDE5EC",
            "grid.linewidth": 0.8,
            "grid.alpha": 0.9,
            "figure.facecolor": "white",
            "axes.facecolor": "#F8FAFC",
            "savefig.facecolor": "white",
            "axes.unicode_minus": False,
        }
    )


def _central_charge_intervals(
    models: Sequence[ModelResult],
    path: Path,
    copy: Mapping[str, str],
    names: Sequence[str],
) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    y = np.arange(len(models))
    for index, (model, color) in enumerate(zip(models, COLORS)):
        left = model.estimate - model.ci95[0]
        right = model.ci95[1] - model.estimate
        ax.errorbar(
            model.estimate,
            index,
            xerr=np.asarray([[left], [right]]),
            fmt="o",
            markersize=9,
            capsize=5,
            color=color,
            ecolor=color,
            linewidth=2.2,
            label=copy["estimate_ci"] if index == 0 else None,
        )
        ax.scatter(
            model.target,
            index,
            marker="D",
            s=72,
            facecolor="white",
            edgecolor="#172B3A",
            linewidth=1.8,
            zorder=4,
            label=copy["benchmark"] if index == 0 else None,
        )
        ax.text(
            model.ci95[1] + 0.0018,
            index,
            f"{model.estimate:.4f}",
            va="center",
            fontsize=10,
            color="#203040",
        )
    ax.set_yticks(y, names)
    ax.invert_yaxis()
    ax.set_xlabel(copy["central_xlabel"])
    ax.set_title(copy["central_title"])
    ax.set_xlim(0.425, 0.515)
    ax.legend(loc="lower right", frameon=True, framealpha=1.0)
    ax.grid(axis="y", visible=False)
    _save(fig, path)


def _target_deviation(
    models: Sequence[ModelResult],
    path: Path,
    copy: Mapping[str, str],
    names: Sequence[str],
) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    z_values = np.asarray(
        [(model.estimate - model.target) / model.standard_error for model in models]
    )
    y = np.arange(len(models))
    ax.axvspan(-1.96, 1.96, color="#DDEFE8", alpha=0.85, label=copy["band"])
    ax.axvline(0.0, color="#203040", linewidth=1.2)
    ax.axvline(-1.96, color="#4B6F61", linewidth=1.0, linestyle="--")
    ax.axvline(1.96, color="#4B6F61", linewidth=1.0, linestyle="--")
    for index, (z_value, color) in enumerate(zip(z_values, COLORS)):
        ax.scatter(z_value, index, s=115, color=color, edgecolor="white", linewidth=1.2)
        ax.text(
            z_value + (0.10 if z_value >= 0 else -0.10),
            index - 0.17,
            f"{z_value:+.2f} {copy['se']}",
            ha="left" if z_value >= 0 else "right",
            fontsize=10,
        )
    ax.set_yticks(y, names)
    ax.invert_yaxis()
    ax.set_xlim(-2.5, 2.5)
    ax.set_xlabel(copy["z_xlabel"])
    ax.set_title(copy["z_title"])
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", frameon=True)
    _save(fig, path)


def _precision_runtime(
    models: Sequence[ModelResult],
    path: Path,
    copy: Mapping[str, str],
    names: Sequence[str],
) -> None:
    fig, (precision_ax, runtime_ax) = plt.subplots(1, 2, figsize=(10.2, 5.2))
    x = np.arange(len(models))
    half_widths = [(model.ci95[1] - model.ci95[0]) / 2.0 for model in models]
    runtimes = [model.runtime_s for model in models]
    precision_ax.bar(x, half_widths, color=COLORS, width=0.64)
    precision_ax.set_xticks(x, names, rotation=18, ha="right")
    precision_ax.set_ylabel(copy["half_width"])
    precision_ax.set_title(copy["precision"])
    precision_ax.grid(axis="x", visible=False)
    for index, value in enumerate(half_widths):
        precision_ax.text(index, value + 0.00035, f"{value:.4f}", ha="center", fontsize=10)

    runtime_ax.bar(x, runtimes, color=COLORS, width=0.64)
    runtime_ax.set_xticks(x, names, rotation=18, ha="right")
    runtime_ax.set_ylabel(copy["runtime_ylabel"])
    runtime_ax.set_title(copy["runtime"])
    runtime_ax.grid(axis="x", visible=False)
    for index, value in enumerate(runtimes):
        runtime_ax.text(
            index,
            value + 11,
            f"{value:.0f} {copy['seconds']}",
            ha="center",
            fontsize=10,
        )
    fig.suptitle(copy["precision_runtime"], fontsize=17)
    fig.subplots_adjust(top=0.82, bottom=0.22, wspace=0.34)
    _save(fig, path, tight=False)


def _validation_gates(
    models: Sequence[ModelResult],
    path: Path,
    copy: Mapping[str, str],
    names: Sequence[str],
) -> None:
    categories = (
        (copy["target_agreement"], ("target", "accuracy", "interval")),
        (copy["precision"], ("standard_error", "precision")),
        (copy["fit_stability"], ("fit", "window", "systematic", "residual")),
        (copy["sampling_stability"], ("thermal", "replica", "half", "effective_sample")),
        (copy["physical_oracle"], ("oracle", "identity", "duality", "bond")),
        (copy["numerical_invariants"], ("invariant", "integration")),
        (copy["convergence"], ("convergence", "trend")),
        (copy["runtime"], ("runtime",)),
    )
    matrix = np.zeros((len(categories), len(models)), dtype=int)
    for column, model in enumerate(models):
        for row, (_, tokens) in enumerate(categories):
            matches = [
                gate
                for gate in model.gates
                if gate.required
                and any(token in gate.name.lower() for token in tokens)
            ]
            if matches:
                matrix[row, column] = 1 if all(gate.passed for gate in matches) else -1

    fig, ax = plt.subplots(figsize=(8.6, 6.2))
    cmap = ListedColormap(("#C94C4C", "#E9EEF2", "#3A9D72"))
    ax.imshow(matrix, cmap=cmap, vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(np.arange(len(models)), names)
    ax.set_yticks(np.arange(len(categories)), [item[0] for item in categories])
    ax.tick_params(top=True, bottom=False, labeltop=True, labelbottom=False)
    ax.grid(False)
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            label = {1: copy["pass"], 0: copy["na"], -1: copy["fail"]}[
                int(matrix[row, column])
            ]
            color = "white" if matrix[row, column] != 0 else "#52616B"
            ax.text(column, row, label, ha="center", va="center", color=color, weight="bold")
    ax.set_xticks(np.arange(-0.5, len(models), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(categories), 1), minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=2)
    ax.tick_params(which="minor", bottom=False, left=False)
    ax.set_title(copy["validation_title"], pad=38)
    ax.legend(
        handles=(
            Patch(facecolor="#3A9D72", label=copy["passed_gate"]),
            Patch(facecolor="#E9EEF2", label=copy["model_check"]),
        ),
        loc="lower center",
        bbox_to_anchor=(0.5, -0.18),
        ncol=2,
        frameon=False,
    )
    fig.subplots_adjust(left=0.30, right=0.98, top=0.80, bottom=0.18)
    _save(fig, path, tight=False)


def _cjk_font() -> FontProperties:
    candidates = (
        Path("/System/Library/Fonts/STHeiti Medium.ttc"),
        Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    )
    for path in candidates:
        if path.is_file():
            return FontProperties(fname=str(path))
    raise RuntimeError("no usable CJK font found for Chinese plots")


def _save(fig: plt.Figure, path: Path, tight: bool = True) -> None:
    kwargs = {"bbox_inches": "tight"} if tight else {}
    fig.savefig(
        path,
        dpi=180,
        metadata={"Software": "Quantum Harness integrated report"},
        **kwargs,
    )
    plt.close(fig)
