"""Replot the 17 frozen model-specific figures with Chinese reader-facing text."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Mapping, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from analysis.comparison_plots import apply_plot_style
from analysis.locale import ZH_LOCALE


PlotKey = Tuple[str, str]
COLORS = ("#225EA8", "#D95F0E", "#238B45")


def build_chinese_source_plots(
    repo_root: Path, output_dir: Path
) -> Dict[PlotKey, Path]:
    root = Path(repo_root).resolve()
    destination = Path(output_dir)
    apply_plot_style(ZH_LOCALE)
    outputs: Dict[PlotKey, Path] = {}
    outputs.update(_clean_plots(root, destination / "clean-ising"))
    outputs.update(_nishimori_plots(root, destination / "nishimori-ising"))
    outputs.update(_weak_plots(root, destination / "weak-self-dual"))
    return outputs


def _clean_plots(root: Path, destination: Path) -> Dict[PlotKey, Path]:
    run = root / "tracks/qmc/results/clean-ising-20260729-120302"
    processed = run / "processed"
    free = _csv_rows(processed / "free_energies.csv")
    fits = _csv_rows(processed / "central_charge_fits.csv")
    energy = _csv_rows(processed / "energy_vs_k.csv")
    diagnostics = {
        row["metric"]: float(row["value"])
        for row in _csv_rows(processed / "diagnostics.csv")
    }
    metadata = _json(processed / "analysis_metadata.json")
    destination.mkdir(parents=True, exist_ok=True)
    paths: Dict[PlotKey, Path] = {}

    widths = np.asarray([float(row["L"]) for row in free])
    x = 1.0 / widths**2
    exact_g = np.asarray([float(row["g_exact"]) for row in free])
    mc_g = np.asarray([float(row["g_mc_129"]) for row in free])
    mc_se = np.asarray([float(row["g_mc_129_se"]) for row in free])
    nested_g = np.asarray([float(row["g_mc_65"]) for row in free])

    fig, ax = _figure()
    ax.plot(x, exact_g / widths, "o-", label="传递矩阵")
    ax.errorbar(
        x,
        mc_g / widths,
        yerr=mc_se / widths,
        fmt="s",
        capsize=3,
        label="Wolff + 热力学积分",
    )
    ax.set(xlabel=r"圆周宽度平方的倒数 $1/L^2$", ylabel="每格点无量纲自由能 g(L)/L")
    ax.set_title("临界自由能的有限尺寸标度")
    ax.legend(frameon=False)
    paths[("clean-ising", "free_energy_scaling.png")] = _save(
        fig, destination / "free_energy_scaling.png"
    )

    fit_by_key = {(int(r["L_min"]), r["method"]): r for r in fits}
    exact = float(fit_by_key[(6, "transfer_matrix")]["c"])
    mc = fit_by_key[(6, "monte_carlo")]
    fig, ax = _figure()
    ax.axhspan(0.495, 0.505, color="#4DAF4A", alpha=0.12, label="精确值通过区间")
    ax.axhspan(0.47, 0.53, color="#377EB8", alpha=0.08, label="蒙特卡洛通过区间")
    ax.axhline(0.5, color="black", linewidth=1.2, linestyle="--", label="Ising：c=0.5")
    ax.scatter([0], [exact], color=COLORS[1], s=55, zorder=3)
    ax.errorbar(
        [1],
        [float(mc["c"])],
        yerr=[
            [float(mc["c"]) - float(mc["ci_low"])],
            [float(mc["ci_high"]) - float(mc["c"])],
        ],
        fmt="o",
        color="#1B9E77",
        capsize=5,
    )
    ax.set_xticks([0, 1], ["传递矩阵", "蒙特卡洛"])
    ax.set_ylabel("中心荷 c")
    ax.set_title("相互独立的中心荷估计")
    ax.legend(frameon=False, fontsize=8)
    paths[("clean-ising", "central_charge_comparison.png")] = _save(
        fig, destination / "central_charge_comparison.png"
    )

    grouped: Mapping[int, List[dict]] = defaultdict(list)
    for row in energy:
        grouped[int(row["L"])].append(row)
    fig, ax = _figure()
    for width in sorted(grouped):
        rows = grouped[width]
        ax.plot(
            [float(row["K"]) for row in rows],
            [float(row["mean_H_per_site"]) for row in rows],
            label=f"L={width}",
        )
    ax.set(xlabel="无量纲耦合 K", ylabel=r"每格点平均能量 $\langle H\rangle/N$")
    ax.set_title("热力学积分的被积函数")
    ax.legend(frameon=False, ncol=2, fontsize=8)
    paths[("clean-ising", "energy_vs_k.png")] = _save(
        fig, destination / "energy_vs_k.png"
    )

    retained = widths >= 6
    design = np.column_stack(
        (widths[retained], 1.0 / widths[retained], 1.0 / widths[retained] ** 3)
    )
    nested_beta = np.linalg.lstsq(design, nested_g[retained], rcond=None)[0]
    nested_c = float(6.0 * nested_beta[1] / np.pi)
    grid_sizes = [int(metadata["nested_grid_points"]), int(metadata["primary_grid_points"])]
    primary_c = float(mc["c"])
    primary_se = float(mc["standard_error"])
    fig, ax = _figure()
    ax.errorbar(
        grid_sizes,
        [nested_c, primary_c],
        yerr=[primary_se, primary_se],
        fmt="o-",
        capsize=4,
        color="#377EB8",
    )
    ax.axhline(0.5, color="black", linestyle="--", linewidth=1)
    ax.set_xticks(grid_sizes)
    ax.set(xlabel="积分网格点数", ylabel="主拟合中心荷 c")
    ax.set_title("嵌套 Simpson 网格的收敛性")
    paths[("clean-ising", "integration_convergence.png")] = _save(
        fig, destination / "integration_convergence.png"
    )

    windows = np.asarray(metadata["fit_windows"], dtype=int)
    exact_values = [float(fit_by_key[(int(w), "transfer_matrix")]["c"]) for w in windows]
    mc_rows = [fit_by_key[(int(w), "monte_carlo")] for w in windows]
    fig, ax = _figure()
    ax.plot(windows, exact_values, "o-", label="传递矩阵")
    ax.errorbar(
        windows,
        [float(row["c"]) for row in mc_rows],
        yerr=[float(row["standard_error"]) for row in mc_rows],
        fmt="s-",
        capsize=4,
        label="蒙特卡洛",
    )
    ax.axhline(0.5, color="black", linestyle="--", linewidth=1)
    ax.set_xticks(windows)
    ax.set(xlabel="保留的最小宽度 L_min", ylabel="中心荷 c")
    ax.set_title("预先声明的拟合窗口稳定性")
    ax.legend(frameon=False)
    paths[("clean-ising", "fit_stability.png")] = _save(
        fig, destination / "fit_stability.png"
    )

    diagnostic_values = [diagnostics["max_half_z"], diagnostics["max_replica_z"]]
    fig, ax = _figure()
    ax.bar(
        ["前后半程漂移", "副本间差异"],
        diagnostic_values,
        color=["#4DAF4A" if value < 4 else "#E41A1C" for value in diagnostic_values],
    )
    ax.axhline(4.0, color="black", linestyle="--", linewidth=1, label="声明的 |z|=4 上限")
    ax.set_ylabel("最大绝对 z 分数")
    ax.set_title("链平稳性与副本一致性")
    ax.legend(frameon=False)
    paths[("clean-ising", "replica_diagnostics.png")] = _save(
        fig, destination / "replica_diagnostics.png"
    )
    return paths


def _nishimori_plots(root: Path, destination: Path) -> Dict[PlotKey, Path]:
    run = root / "tracks/qmc/results/nishimori-ising-20260729-refinement1"
    summary = _json(run / "processed/summary.json")
    free = _csv_rows(run / "processed/free_energy.csv")
    bootstrap = _csv_rows(run / "processed/central_charge_bootstrap.csv")
    destination.mkdir(parents=True, exist_ok=True)
    paths: Dict[PlotKey, Path] = {}

    widths = np.asarray([float(row["width"]) for row in free])
    phi = np.asarray([float(row["phi"]) for row in free])
    phi_se = np.asarray([float(row["standard_error"]) for row in free])
    fitted = np.asarray([float(row["fitted_phi"]) for row in free])
    order = np.argsort(1.0 / widths**2)
    fig, ax = _figure()
    ax.errorbar(1.0 / widths**2, phi, yerr=phi_se, fmt="o", color=COLORS[0], capsize=3, label="淬火分块均值")
    ax.plot((1.0 / widths**2)[order], fitted[order], color=COLORS[1], label=r"含 $L^{-2}$ 与 $L^{-4}$ 修正的拟合")
    ax.set(xlabel=r"$1/L^2$", ylabel=r"$\phi_L = E[\ln Z]/(ML)$")
    ax.set_title("Nishimori 淬火自由能标度")
    ax.legend(frameon=False)
    paths[("nishimori-ising", "free_energy_fit.png")] = _save(fig, destination / "free_energy_fit.png")

    primary_bootstrap = np.asarray([float(row["c_lmin4"]) for row in bootstrap])
    diagnostic_bootstrap = np.asarray([float(row["c_lmin6"]) for row in bootstrap])
    fig, ax = _figure()
    ax.hist(primary_bootstrap, bins=36, color=COLORS[0], alpha=0.82, density=True)
    ax.axvline(0.464, color=COLORS[2], linewidth=2, label="基准值 0.464")
    ax.axvline(np.mean(primary_bootstrap), color=COLORS[1], linewidth=2, label="自助法均值")
    ax.set(xlabel="有效中心荷 c_eff", ylabel="自助分布密度")
    ax.set_title("跨宽度联合分层自助法")
    ax.legend(frameon=False)
    paths[("nishimori-ising", "central_charge_bootstrap.png")] = _save(fig, destination / "central_charge_bootstrap.png")

    fig, ax = _figure()
    ax.errorbar(
        ["L_min = 4", "L_min = 6"],
        [summary["primary_fit"]["central_charge"], summary["diagnostic_fit"]["central_charge"]],
        yerr=[np.std(primary_bootstrap, ddof=1), np.std(diagnostic_bootstrap, ddof=1)],
        fmt="o",
        color=COLORS[0],
        capsize=5,
    )
    ax.axhline(0.464, color=COLORS[2], linestyle="--", label="基准值 0.464")
    ax.set_ylabel("有效中心荷 c_eff")
    ax.set_title("有限尺寸拟合窗口稳定性")
    ax.legend(frameon=False)
    paths[("nishimori-ising", "fit_window_stability.png")] = _save(fig, destination / "fit_window_stability.png")

    stability = summary["stability"]
    labels = ["前半程", "后半程"] + [f"删除副本 R{i}" for i in range(len(stability["leave_one_replica_out"]))]
    values = stability["half_central_charges"] + stability["leave_one_replica_out"]
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    ax.plot(range(len(values)), values, "o", color=COLORS[0])
    ax.axhline(0.464, color=COLORS[2], linestyle="--", label="基准值 0.464")
    ax.set_xticks(range(len(labels)), labels, rotation=35, ha="right")
    ax.set_ylabel("有效中心荷 c_eff")
    ax.set_title("半程与删副本稳定性")
    ax.legend(frameon=False)
    _style(ax)
    paths[("nishimori-ising", "sampling_stability.png")] = _save(fig, destination / "sampling_stability.png")

    identity = summary["nishimori_energy_identity"]
    fig, ax = _figure()
    ax.bar(["有限差分", "2 tanh K_N"], [identity["derivative"], identity["expected"]], color=[COLORS[0], COLORS[2]], width=0.62)
    ax.set_ylabel("∂φ/∂K")
    ax.set_title("Nishimori 内能恒等式")
    ax.text(0.5, 0.04, f"绝对误差 = {identity['absolute_error']:.3g}", transform=ax.transAxes, ha="center")
    paths[("nishimori-ising", "nishimori_energy_identity.png")] = _save(fig, destination / "nishimori_energy_identity.png")

    bond = summary["bond_frequency"]
    fig, ax = _figure()
    ax.bar(["观测值", "配置值"], [bond["observed_probability"], bond["expected_probability"]], color=[COLORS[0], COLORS[2]], width=0.62)
    ax.set_ylabel("反铁磁键概率")
    ax.set_title("无序流频率检查")
    ax.text(0.5, 0.04, f"z = {bond['z_score']:.3f}，N = {bond['total_bonds']:,}", transform=ax.transAxes, ha="center")
    paths[("nishimori-ising", "negative_bond_frequency.png")] = _save(fig, destination / "negative_bond_frequency.png")
    return paths


def _weak_plots(root: Path, destination: Path) -> Dict[PlotKey, Path]:
    run = root / "tracks/qmc/results/weak-self-dual-20260729-154737"
    summary = _json(run / "processed/summary.json")
    finite = _csv_rows(run / "processed/finite_size.csv")
    variants = {row["variant"]: row for row in _csv_rows(run / "processed/fit_variants.csv")}
    destination.mkdir(parents=True, exist_ok=True)
    paths: Dict[PlotKey, Path] = {}

    widths = np.asarray([float(row["width"]) for row in finite])
    gamma = np.asarray([float(row["gamma"]) for row in finite])
    gamma_se = np.asarray([float(row["standard_error"]) for row in finite])
    fitted = np.asarray([float(row["fitted_gamma"]) for row in finite])
    x = 1.0 / widths**2
    order = np.argsort(x)
    fig, ax = _figure()
    ax.errorbar(x, gamma / widths, yerr=gamma_se / widths, fmt="o", color=COLORS[0], capsize=3)
    ax.plot(x[order], (fitted / widths)[order], color=COLORS[1], label=r"主 $L^{-1}+L^{-3}$ 拟合")
    ax.set(xlabel=r"$1/L^2$", ylabel=r"$\gamma_1(L)/L$")
    ax.set_title("弱自对偶真空自由能标度")
    ax.legend(frameon=False)
    paths[("weak-self-dual", "finite-size-scaling.png")] = _save(fig, destination / "finite-size-scaling.png")

    residual = np.asarray([float(row["residual"]) for row in finite]) / gamma_se
    fig, ax = _figure()
    ax.axhspan(-3, 3, color="#D9F0D3", alpha=0.5)
    ax.axhline(0, color="black", linewidth=1)
    ax.plot(widths, residual, "o-", color=COLORS[0])
    ax.set(xlabel="圆周宽度 L", ylabel="学生化残差")
    ax.set_title("有限尺寸拟合残差")
    paths[("weak-self-dual", "residuals.png")] = _save(fig, destination / "residuals.png")

    names = ["primary", "lmin8", "lmin10", "extra_burnin", "double_block", "drop_l30"]
    labels = ["主拟合", "L_min 8", "L_min 10", "额外预热", "2× 分块", "删除 L30"]
    centers = np.asarray([float(variants[name]["mean"]) for name in names])
    intervals = np.asarray([[float(variants[name]["ci95_low"]), float(variants[name]["ci95_high"])] for name in names])
    errors = np.vstack((centers - intervals[:, 0], intervals[:, 1] - centers))
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    ax.errorbar(labels, centers, yerr=errors, fmt="o", color=COLORS[0], capsize=4)
    ax.axhspan(0.446, 0.448, color=COLORS[2], alpha=0.18, label="0.447 ± 0.001")
    ax.tick_params(axis="x", rotation=25)
    ax.set_ylabel("有效中心荷 c_eff")
    ax.set_title("拟合窗口与采样稳定性")
    ax.legend(frameon=False)
    _style(ax)
    paths[("weak-self-dual", "fit-stability.png")] = _save(fig, destination / "fit-stability.png")

    sampling = summary["sampling_diagnostics"]
    ess = [sampling[str(int(width))]["effective_sample_size"] for width in widths]
    lag = [sampling[str(int(width))]["maximum_absolute_lag_one"] for width in widths]
    fig, first = plt.subplots(figsize=(7.2, 4.8))
    second = first.twinx()
    first.plot(widths, ess, "o-", color=COLORS[0], label="有效样本量")
    second.plot(widths, lag, "s--", color=COLORS[1], label="|一阶滞后|")
    first.axhline(100, color=COLORS[2], linestyle=":", label="有效样本量门槛")
    first.set(xlabel="圆周宽度 L", ylabel="有效样本量")
    second.set_ylabel("最大 |一阶滞后相关|")
    first.set_title("各宽度的采样收敛性")
    _style(first)
    paths[("weak-self-dual", "convergence-ess.png")] = _save(fig, destination / "convergence-ess.png")

    diagnostic = summary["self_duality"]
    fig, ax = _figure()
    ax.bar(["电通道", "磁通道"], [diagnostic["electric_density"], diagnostic["magnetic_density"]], color=[COLORS[0], COLORS[1]])
    ax.set_ylabel("涡旋密度")
    ax.set_title(f"自对偶检查：差值 z={diagnostic['z_score']:.3f}")
    paths[("weak-self-dual", "self-duality.png")] = _save(fig, destination / "self-duality.png")
    return paths


def _figure():
    fig, axis = plt.subplots(figsize=(7.2, 4.8))
    _style(axis)
    return fig, axis


def _style(axis) -> None:
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.grid(alpha=0.2)


def _save(figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(
        path,
        dpi=180,
        bbox_inches="tight",
        facecolor="white",
        metadata={"Software": "Quantum Harness integrated report"},
    )
    plt.close(figure)
    return path


def _csv_rows(path: Path) -> List[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
