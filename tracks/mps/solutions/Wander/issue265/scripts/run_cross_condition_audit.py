#!/usr/bin/env python3
"""Run preregistered cross-condition scalar Burgers tests."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_research_datasets import validate_manifest
from src.cross_condition_validation import (
    bootstrap_shared_burgers,
    coefficient_heterogeneity,
    fit_condition_specific,
    fit_sector_amplitude_law,
    fit_shared_burgers,
    leave_one_condition_out,
    rolling_shared_fits,
    spin_flip_defect,
)
from src.research_dataset import ResearchDataset, load_research_dataset
from src.research_protocol import (
    load_decision_rules,
    load_research_matrix,
)
from src.tension_resolution import WeakFit, forecast_profile


def _write_report(outdir: Path, summary: dict[str, Any]) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    )
    if summary["status"] != "evaluated":
        lines = [
            "# Cross-condition Burgers audit",
            "",
            f"**Status:** `{summary['status']}`",
            "",
            summary["explanation"],
            "",
            "This status is a data-availability result, not evidence for or "
            "against Burgers universality.",
        ]
    else:
        verdict = summary["verdict"]
        lines = [
            "# Cross-condition Burgers audit",
            "",
            f"**Universal scalar verdict:** `{verdict}`",
            "",
            "The fit rows for every held-out condition were excluded before "
            "its forecast was generated.",
            "",
            f"- shared a: {summary['shared_fit']['a']:.8g}",
            f"- shared D: {summary['shared_fit']['D']:.8g}",
            f"- sector-law g: {summary['sector_fit']['g']:.8g}",
            f"- maximum LOCO integrated error: "
            f"{summary['decision_metrics']['max_loco_integrated']:.6g}",
            f"- maximum LOCO endpoint error: "
            f"{summary['decision_metrics']['max_loco_endpoint']:.6g}",
            f"- relative coefficient spread: "
            f"{summary['decision_metrics']['coefficient_relative_spread']:.6g}",
        ]
    (outdir / "REPORT.md").write_text("\n".join(lines) + "\n")


def _common_crop(datasets: list[ResearchDataset]) -> tuple[float, float]:
    half_width = min(
        min(abs(float(dataset.x[0])), abs(float(dataset.x[-1])))
        for dataset in datasets
    )
    if half_width <= 10:
        raise ValueError("Domains are too small for a common fit crop")
    return -0.75 * half_width, 0.75 * half_width


def _coefficient_plot(
    outdir: Path,
    datasets: list[ResearchDataset],
    specific: dict[str, Any],
    shared_a: float,
    sector_g: float,
) -> None:
    signed_mu = np.array(
        [
            int(dataset.metadata["orientation"])
            * float(dataset.metadata["mu"])
            for dataset in datasets
        ]
    )
    values = np.array([specific[dataset.condition_id].a for dataset in datasets])
    order = np.argsort(signed_mu)
    figure, axis = plt.subplots(figsize=(6.4, 4.2))
    axis.scatter(signed_mu, values, label="condition-specific")
    axis.axhline(shared_a, color="tab:orange", label="shared constant a")
    axis.plot(
        signed_mu[order],
        2.0 * sector_g * signed_mu[order],
        color="tab:green",
        label=r"$a=2\sigma g\mu$",
    )
    axis.set(xlabel=r"signed amplitude $\sigma\mu$", ylabel="fitted a")
    axis.legend(frameon=False)
    figure.tight_layout()
    figure.savefig(outdir / "amplitude_orientation_coefficients.png", dpi=180)
    plt.close(figure)


def _loco_plot(outdir: Path, rows: list[dict[str, Any]]) -> None:
    models = ["shared_constant", "sector_amplitude_law"]
    condition_ids = sorted({str(row["held_out_condition_id"]) for row in rows})
    values = np.full((len(models), len(condition_ids)), np.nan)
    for row in rows:
        values[
            models.index(str(row["model"])),
            condition_ids.index(str(row["held_out_condition_id"])),
        ] = float(row["integrated_relative_l2"])
    figure, axis = plt.subplots(
        figsize=(max(7.0, 0.38 * len(condition_ids)), 3.2)
    )
    image = axis.imshow(values, aspect="auto", cmap="magma")
    axis.set_yticks(range(len(models)), labels=models)
    axis.set_xticks(
        range(len(condition_ids)), labels=condition_ids, rotation=90
    )
    figure.colorbar(image, ax=axis, label="integrated relative L2")
    figure.tight_layout()
    figure.savefig(outdir / "leave_one_condition_out_heatmap.png", dpi=180)
    plt.close(figure)


def _symmetry_plot(
    outdir: Path,
    datasets: list[ResearchDataset],
) -> list[dict[str, Any]]:
    by_key: dict[tuple[Any, ...], dict[int, ResearchDataset]] = {}
    for dataset in datasets:
        metadata = dataset.metadata
        key = (
            metadata.get("mu"),
            metadata.get("profile"),
            metadata.get("width"),
            metadata.get("background_m"),
            metadata.get("delta"),
            metadata.get("J2"),
        )
        by_key.setdefault(key, {})[int(metadata["orientation"])] = dataset
    pairs: list[dict[str, Any]] = []
    figure, axis = plt.subplots(figsize=(6.4, 4.2))
    for group in by_key.values():
        if 1 not in group or -1 not in group:
            continue
        defect = spin_flip_defect(group[1], group[-1])
        pairs.append(
            {
                "up": group[1].condition_id,
                "down": group[-1].condition_id,
                "max_defect": float(np.max(defect)),
                "mean_defect": float(np.mean(defect)),
            }
        )
        axis.plot(group[1].t, defect, alpha=0.75, label=group[1].condition_id)
    axis.set(xlabel="t", ylabel="spin-flip defect")
    if pairs:
        axis.legend(frameon=False, fontsize=7, ncol=2)
    figure.tight_layout()
    figure.savefig(outdir / "symmetry_defects.png", dpi=180)
    plt.close(figure)
    return pairs


def _window_flow_plot(
    outdir: Path,
    rolling: list[dict[str, Any]],
) -> None:
    figure, axes = plt.subplots(2, 1, figsize=(6.4, 6.0), sharex=True)
    centers = [float(row["t_center"]) for row in rolling]
    axes[0].plot(centers, [float(row["a"]) for row in rolling], "o-")
    axes[1].plot(centers, [float(row["D"]) for row in rolling], "o-")
    axes[0].set_ylabel("shared a")
    axes[1].set_ylabel("shared D")
    axes[1].set_xlabel("rolling-window center")
    for axis in axes:
        axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(outdir / "window_parameter_flow.png", dpi=180)
    plt.close(figure)


def _profile_examples_plot(
    outdir: Path,
    datasets: list[ResearchDataset],
    *,
    train_window: tuple[float, float],
    validation_window: tuple[float, float],
    x_crop: tuple[float, float],
) -> None:
    examples = datasets[: min(3, len(datasets))]
    figure, axes = plt.subplots(
        len(examples),
        1,
        figsize=(7.0, 2.7 * len(examples)),
        squeeze=False,
    )
    for axis, held_out in zip(axes[:, 0], examples, strict=True):
        training = [
            dataset
            for dataset in datasets
            if dataset.condition_id != held_out.condition_id
        ]
        shared = fit_shared_burgers(
            training,
            train_window=train_window,
            x_crop=x_crop,
        )
        start = int(np.argmin(np.abs(held_out.t - validation_window[0])))
        stop = int(np.argmin(np.abs(held_out.t - validation_window[1])))
        relative_t = held_out.t[start : stop + 1] - held_out.t[start]
        prediction = forecast_profile(
            held_out.x,
            relative_t,
            held_out.u[start],
            fit=WeakFit(
                a=shared.a,
                D0=shared.D,
                gamma=0.0,
                mse=shared.mse,
                n_obs=shared.n_obs,
                t_window=train_window,
                t_ref=max(validation_window[0], 1.0),
            ),
            absolute_start_time=float(held_out.t[start]),
            dt_internal=0.02,
        )
        mask = (held_out.x >= x_crop[0]) & (held_out.x <= x_crop[1])
        axis.plot(
            held_out.x[mask],
            held_out.u[stop, mask],
            label="held-out quantum",
        )
        axis.plot(
            held_out.x[mask],
            prediction[-1, mask],
            "--",
            label="shared scalar forecast",
        )
        axis.set_title(held_out.condition_id)
        axis.set_ylabel("U")
        axis.legend(frameon=False, fontsize=8)
    axes[-1, 0].set_xlabel("x")
    figure.tight_layout()
    figure.savefig(outdir / "profile_examples_train_vs_unseen.png", dpi=180)
    plt.close(figure)


def _flow_exponent(
    rolling: list[dict[str, Any]],
    key: str,
) -> float:
    if len(rolling) < 3:
        return float("nan")
    time = np.array([float(row["t_center"]) for row in rolling])
    values = np.abs(np.array([float(row[key]) for row in rolling]))
    mask = (time > 0) & (values > 1e-14)
    if np.count_nonzero(mask) < 3:
        return float("nan")
    return float(np.polyfit(np.log(time[mask]), np.log(values[mask]), 1)[0])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "results_research_program" / "manifest.json",
    )
    parser.add_argument(
        "--matrix",
        type=Path,
        default=ROOT / "configs" / "burgers_research_matrix.json",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        default=ROOT / "configs" / "burgers_decision_rules.json",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=ROOT / "results_research_program" / "cross_condition",
    )
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    validation = validate_manifest(
        args.manifest,
        include_blinded=False,
        rules_path=args.rules,
    )
    if not validation["convergence"]["accepted"]:
        summary = {
            "schema_version": 1,
            "status": "simulation_unresolved",
            "explanation": (
                "The preregistered coarse/medium/fine convergence gate is "
                "not complete or did not pass."
            ),
            "convergence": validation["convergence"],
        }
        _write_report(args.outdir, summary)
        print(json.dumps({"status": summary["status"]}))
        return

    matrix = load_research_matrix(args.matrix)
    primary_ids = {
        condition.condition_id
        for condition in matrix.conditions
        if condition.role.startswith("primary_")
    }
    jobs = [
        job
        for job in manifest["jobs"]
        if job["stage"] == "production_a"
        and job["condition_id"] in primary_ids
    ]
    available = [job for job in jobs if Path(job["output_path"]).exists()]
    if len(available) != len(jobs):
        missing = sorted(
            str(job["job_id"])
            for job in jobs
            if not Path(job["output_path"]).exists()
        )
        summary = {
            "schema_version": 1,
            "status": "insufficient_initial_conditions",
            "explanation": (
                "Convergence passed, but not all preregistered primary "
                "production-A conditions are available."
            ),
            "missing_job_ids": missing,
        }
        _write_report(args.outdir, summary)
        print(json.dumps({"status": summary["status"], "missing": len(missing)}))
        return

    datasets = [
        load_research_dataset(Path(job["output_path"])) for job in available
    ]
    crop = _common_crop(datasets)
    shared = fit_shared_burgers(
        datasets, train_window=matrix.train_window, x_crop=crop
    )
    sector = fit_sector_amplitude_law(
        datasets, train_window=matrix.train_window, x_crop=crop
    )
    specific = fit_condition_specific(
        datasets, train_window=matrix.train_window, x_crop=crop
    )
    rolling = rolling_shared_fits(
        datasets,
        windows=matrix.rolling_windows,
        x_crop=crop,
    )
    loco_shared = leave_one_condition_out(
        datasets,
        train_window=matrix.train_window,
        forecast_window=matrix.validation_window,
        x_crop=crop,
        model="shared_constant",
    )
    loco_sector = leave_one_condition_out(
        datasets,
        train_window=matrix.train_window,
        forecast_window=matrix.validation_window,
        x_crop=crop,
        model="sector_amplitude_law",
    )
    loco = loco_shared + loco_sector

    heterogeneity = coefficient_heterogeneity(shared, specific)
    coefficient_spread = float(
        heterogeneity["max_relative_spread"]
    )
    shared_rows = [
        row for row in loco if row["model"] == "shared_constant"
    ]
    max_integrated = max(
        float(row["integrated_relative_l2"]) for row in shared_rows
    )
    max_endpoint = max(
        float(row["endpoint_relative_l2"]) for row in shared_rows
    )
    rules = load_decision_rules(args.rules)
    bootstrap = bootstrap_shared_burgers(
        datasets,
        train_window=matrix.train_window,
        x_crop=crop,
        block_duration=rules.threshold("bootstrap_block_duration"),
        n_replicates=int(rules.threshold("bootstrap_replicates")),
        seed=20260729,
    )
    a_drift = _flow_exponent(rolling, "a")
    D_drift = _flow_exponent(rolling, "D")
    late_exponent_errors = [
        abs(float(row["late_width_exponent_error"]))
        for row in shared_rows
        if np.isfinite(float(row["late_width_exponent_error"]))
    ]
    late_width_error = (
        max(late_exponent_errors)
        if late_exponent_errors
        else float("nan")
    )
    numerical_floor = max(
        (
            float(record.get("numerical_floor", 0.0))
            for record in validation["convergence"]["records"]
            if record.get("accepted", False)
        ),
        default=0.0,
    )
    args.outdir.mkdir(parents=True, exist_ok=True)
    symmetry_pairs = _symmetry_plot(args.outdir, datasets)
    spin_flip_max = max(
        (
            float(record["max_defect"])
            for record in symmetry_pairs
        ),
        default=float("nan"),
    )
    passes = (
        max_integrated
        <= rules.threshold("universal_loco_integrated_max")
        and max_endpoint <= rules.threshold("universal_loco_endpoint_max")
        and coefficient_spread
        <= rules.threshold("coefficient_relative_spread_max")
        and np.isfinite(a_drift)
        and abs(a_drift) <= rules.threshold("window_drift_abs_max")
        and np.isfinite(D_drift)
        and abs(D_drift) <= rules.threshold("window_drift_abs_max")
        and np.isfinite(late_width_error)
        and abs(late_width_error)
        <= rules.threshold("late_width_exponent_abs_error_max")
        and np.isfinite(spin_flip_max)
        and spin_flip_max <= 5.0 * numerical_floor
    )

    _coefficient_plot(
        args.outdir, datasets, specific, shared.a, sector.g
    )
    _loco_plot(args.outdir, loco)
    _window_flow_plot(args.outdir, rolling)
    _profile_examples_plot(
        args.outdir,
        datasets,
        train_window=matrix.train_window,
        validation_window=matrix.validation_window,
        x_crop=crop,
    )
    bootstrap_json = {
        key: (
            value.tolist() if isinstance(value, np.ndarray) else value
        )
        for key, value in bootstrap.items()
    }
    summary = {
        "schema_version": 1,
        "status": "evaluated",
        "verdict": "supported" if passes else "falsified",
        "common_crop": list(crop),
        "shared_fit": shared.to_dict(),
        "sector_fit": sector.to_dict(),
        "condition_specific": {
            condition_id: asdict(fit)
            for condition_id, fit in specific.items()
        },
        "rolling_shared": rolling,
        "parameter_flow": {
            "a_drift_exponent": a_drift,
            "D_drift_exponent": D_drift,
        },
        "bootstrap": bootstrap_json,
        "heterogeneity": heterogeneity,
        "loco": loco,
        "symmetry_pairs": symmetry_pairs,
        "decision_metrics": {
            "max_loco_integrated": max_integrated,
            "max_loco_endpoint": max_endpoint,
            "coefficient_relative_spread": coefficient_spread,
            "late_width_exponent_error_max": (
                late_width_error
            ),
            "spin_flip_defect_max": spin_flip_max,
            "numerical_floor": numerical_floor,
        },
        "superposition": {
            "status": "not_tested",
            "reason": (
                "The frozen matrix contains the two component packets but no "
                "separately evolved A+B production condition."
            ),
        },
    }
    _write_report(args.outdir, summary)
    print(json.dumps({"status": "evaluated", "verdict": summary["verdict"]}))


if __name__ == "__main__":
    main()
