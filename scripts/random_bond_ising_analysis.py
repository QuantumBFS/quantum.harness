#!/usr/bin/env python3
"""Finite-size central-charge analysis for random-bond Ising transfer strips."""

import argparse
import csv
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np

try:
    from random_bond_ising_transfer import run_random_strip
except ImportError:  # imported from the repository root during tests
    from scripts.random_bond_ising_transfer import run_random_strip


PLOT_ALPHA = 0.78
MARKER_AREA = 72.0
FIT_COLOR = "red"
FIT_LINESTYLE = "-"


def fit_central_charge(
    sizes,
    free_energies,
    errors,
    include_l4=True,
    lmin=8,
):
    """Fit f_L=f_inf-pi*c/(6 L^2)+a/L^4 with known standard errors."""
    sizes = np.asarray(sizes, dtype=float)
    values = np.asarray(free_energies, dtype=float)
    errors = np.asarray(errors, dtype=float)
    if sizes.ndim != 1 or values.shape != sizes.shape or errors.shape != sizes.shape:
        raise ValueError("sizes, free_energies, and errors must have equal 1D shapes")
    if not np.all(np.isfinite(sizes)) or not np.all(np.isfinite(values)):
        raise ValueError("sizes and free energies must be finite")
    if not np.all(np.isfinite(errors)) or np.any(errors <= 0.0):
        raise ValueError("errors must be finite and positive")

    mask = sizes >= float(lmin)
    selected = sizes[mask]
    columns = [np.ones_like(selected), selected**-2]
    if include_l4:
        columns.append(selected**-4)
    design = np.column_stack(columns)
    if design.shape[0] < design.shape[1]:
        raise ValueError("not enough sizes for the requested fit")

    weighted_design = design / errors[mask, None]
    weighted_values = values[mask] / errors[mask]
    coefficients, _, rank, _ = np.linalg.lstsq(
        weighted_design, weighted_values, rcond=None
    )
    if rank != design.shape[1]:
        raise RuntimeError("rank-deficient central-charge fit")
    covariance = np.linalg.inv(weighted_design.T @ weighted_design)
    residual = values[mask] - design @ coefficients
    charge = -6.0 * coefficients[1] / math.pi
    charge_se = 6.0 * math.sqrt(covariance[1, 1]) / math.pi
    return {
        "sizes": selected.astype(int).tolist(),
        "include_l4": bool(include_l4),
        "coefficients": [float(value) for value in coefficients],
        "central_charge": float(charge),
        "central_charge_linear_se": float(charge_se),
        "weighted_residual_norm": float(np.linalg.norm(residual / errors[mask])),
    }


def estimate_required_rows(strip_result, target_free_energy_se):
    """Project retained rows and wall time using standard-error squared scaling."""
    target_free_energy_se = float(target_free_energy_se)
    if not math.isfinite(target_free_energy_se) or target_free_energy_se <= 0.0:
        raise ValueError("target_free_energy_se must be finite and positive")
    measured_se = float(strip_result["free_energy_se"])
    if not math.isfinite(measured_se) or measured_se < 0.0:
        raise ValueError("strip free_energy_se must be finite and nonnegative")

    ratio = measured_se / target_free_energy_se
    raw_rows = int(strip_result["retained_rows"]) * max(1.0, ratio * ratio)
    block = int(strip_result["block_length"])
    required = int(math.ceil(raw_rows / block) * block)
    measured_rows = int(strip_result["burn_in"]) + int(strip_result["retained_rows"])
    projected_rows = int(strip_result["burn_in"]) + required
    return {
        "L": int(strip_result.get("L", 0)),
        "required_retained_rows": required,
        "projected_runtime_seconds": float(strip_result["runtime_seconds"])
        * projected_rows
        / measured_rows,
    }


def central_charge_summary(strip_results, bootstrap_samples, seed):
    """Return three fit forms and a block-bootstrap error for the primary fit."""
    if len(strip_results) < 5:
        raise ValueError("five widths are required for the central-charge summary")
    bootstrap_samples = int(bootstrap_samples)
    if bootstrap_samples < 2:
        raise ValueError("bootstrap_samples must be at least two")

    sizes = np.asarray([item["L"] for item in strip_results], dtype=float)
    values = np.asarray([item["free_energy"] for item in strip_results], dtype=float)
    errors = np.asarray([item["free_energy_se"] for item in strip_results], dtype=float)
    fits = {
        "primary_L8_l24": fit_central_charge(sizes, values, errors, True, 8),
        "all_L_l2": fit_central_charge(sizes, values, errors, False, 8),
        "drop_L8_l24": fit_central_charge(sizes, values, errors, True, 10),
    }

    rng = np.random.default_rng(seed)
    bootstrap_charges = []
    for _ in range(bootstrap_samples):
        sampled_values = []
        for item in strip_results:
            blocks = np.asarray(item["block_log_norm_means"], dtype=float)
            if blocks.ndim != 1 or len(blocks) < 2 or not np.all(np.isfinite(blocks)):
                raise ValueError("each width requires at least two finite block means")
            sampled = rng.choice(blocks, size=len(blocks), replace=True)
            observed_mean = float(np.mean(blocks))
            sampled_mean = float(np.mean(sampled))
            corrected_mean = observed_mean + math.sqrt(
                len(blocks) / (len(blocks) - 1.0)
            ) * (sampled_mean - observed_mean)
            sampled_values.append(-corrected_mean / item["L"])
        bootstrap_charges.append(
            fit_central_charge(sizes, sampled_values, errors, True, 8)[
                "central_charge"
            ]
        )

    deterministic = [fit["central_charge"] for fit in fits.values()]
    fits["reported"] = {
        "central_charge": fits["primary_L8_l24"]["central_charge"],
        "bootstrap_se": float(np.std(bootstrap_charges, ddof=1)),
        "fit_envelope_lower": float(min(deterministic)),
        "fit_envelope_upper": float(max(deterministic)),
        "bootstrap_samples": bootstrap_samples,
    }
    return fits


def aggregate_sample_records(records):
    """Aggregate independent fixed-count strip records by cylinder width."""
    records = list(records)
    if not records:
        raise ValueError("at least one sample record is required")

    grouped = {}
    seen = set()
    for record in records:
        L = int(record["L"])
        sample_index = int(record["sample_index"])
        key = (L, sample_index)
        if key in seen:
            raise ValueError(f"duplicate sample record for L={L}, index={sample_index}")
        seen.add(key)
        value = float(record["free_energy"])
        runtime = float(record["runtime_seconds"])
        if not math.isfinite(value) or not math.isfinite(runtime) or runtime < 0.0:
            raise ValueError("sample free energies and runtimes must be finite")
        grouped.setdefault(L, []).append(record)

    width_results = []
    invariant_fields = (
        "p",
        "coupling",
        "burn_in",
        "retained_rows",
        "block_length",
        "total_retained_bonds",
        "disorder_ensemble",
    )
    for L in sorted(grouped):
        samples = sorted(grouped[L], key=lambda item: int(item["sample_index"]))
        if len(samples) < 2:
            raise ValueError(f"L={L} requires at least two independent samples")
        first = samples[0]
        for sample in samples[1:]:
            for field in invariant_fields:
                if sample[field] != first[field]:
                    raise ValueError(f"inconsistent {field} for L={L}")
        values = np.asarray([item["free_energy"] for item in samples], dtype=float)
        runtimes = np.asarray([item["runtime_seconds"] for item in samples], dtype=float)
        width_results.append(
            {
                "L": L,
                "p": float(first["p"]),
                "coupling": float(first["coupling"]),
                "burn_in": int(first["burn_in"]),
                "retained_rows": int(first["retained_rows"]),
                "block_length": int(first["block_length"]),
                "sample_count": len(samples),
                "free_energy": float(np.mean(values)),
                "free_energy_se": float(
                    np.std(values, ddof=1) / math.sqrt(len(values))
                ),
                "sample_free_energies": values,
                "mean_runtime_seconds": float(np.mean(runtimes)),
                "antiferromagnetic_bonds": int(
                    first["antiferromagnetic_bonds"]
                ),
                "total_retained_bonds": int(first["total_retained_bonds"]),
                "disorder_ensemble": str(first["disorder_ensemble"]),
            }
        )
    return width_results


def central_charge_ensemble_summary(
    width_results,
    bootstrap_samples,
    seed,
    lmins=(4, 5, 6, 8),
):
    """Fit an ensemble of independent strips and bootstrap whole samples."""
    width_results = sorted(width_results, key=lambda item: int(item["L"]))
    if len(width_results) < 4:
        raise ValueError("at least four widths are required")
    bootstrap_samples = int(bootstrap_samples)
    if bootstrap_samples < 2:
        raise ValueError("bootstrap_samples must be at least two")

    sizes = np.asarray([item["L"] for item in width_results], dtype=float)
    values = np.asarray([item["free_energy"] for item in width_results], dtype=float)
    errors = np.asarray([item["free_energy_se"] for item in width_results], dtype=float)
    if np.any(~np.isfinite(errors)) or np.any(errors <= 0.0):
        raise ValueError("each width requires a finite positive sample error")

    fits = {}
    for lmin in tuple(int(value) for value in lmins):
        if np.count_nonzero(sizes >= lmin) >= 2:
            fits[f"l2_Lmin{lmin}"] = fit_central_charge(
                sizes, values, errors, include_l4=False, lmin=lmin
            )
        if np.count_nonzero(sizes >= lmin) >= 4:
            fits[f"l4_Lmin{lmin}"] = fit_central_charge(
                sizes, values, errors, include_l4=True, lmin=lmin
            )
    primary_key = "l4_Lmin4"
    if primary_key not in fits:
        raise ValueError("the requested widths do not support the primary fit")

    rng = np.random.default_rng(seed)
    bootstrap_charges = []
    for _ in range(bootstrap_samples):
        sampled_values = []
        for item in width_results:
            samples = np.asarray(item["sample_free_energies"], dtype=float)
            if samples.ndim != 1 or len(samples) < 2 or not np.all(np.isfinite(samples)):
                raise ValueError("each width requires finite independent samples")
            resampled = rng.choice(samples, size=len(samples), replace=True)
            sampled_values.append(float(np.mean(resampled)))
        bootstrap_charges.append(
            fit_central_charge(
                sizes,
                sampled_values,
                errors,
                include_l4=True,
                lmin=4,
            )["central_charge"]
        )

    deterministic = [fit["central_charge"] for fit in fits.values()]
    fits["reported"] = {
        "primary_fit": primary_key,
        "central_charge": fits[primary_key]["central_charge"],
        "bootstrap_se": float(np.std(bootstrap_charges, ddof=1)),
        "fit_envelope_lower": float(min(deterministic)),
        "fit_envelope_upper": float(max(deterministic)),
        "bootstrap_samples": bootstrap_samples,
    }
    return fits


def write_analysis_artifacts(
    strip_results,
    summary,
    projections,
    runtime,
    output_dir,
):
    """Write raw blocks, width statistics, fit metadata, runtime, and plot."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with (output_dir / "blocks.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("L", "block_index", "block_log_norm_mean"),
        )
        writer.writeheader()
        for item in strip_results:
            for block_index, block_mean in enumerate(
                item["block_log_norm_means"], start=1
            ):
                writer.writerow(
                    {
                        "L": item["L"],
                        "block_index": block_index,
                        "block_log_norm_mean": float(block_mean),
                    }
                )

    width_fields = (
        "L",
        "p",
        "coupling",
        "seed",
        "burn_in",
        "retained_rows",
        "block_length",
        "lyapunov",
        "lyapunov_se",
        "free_energy",
        "free_energy_se",
        "runtime_seconds",
        "rows_per_second",
    )
    with (output_dir / "width_summary.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=width_fields)
        writer.writeheader()
        for item in strip_results:
            writer.writerow({field: item[field] for field in width_fields})

    with (output_dir / "central_charge_fit.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")

    runtime_document = dict(runtime)
    runtime_document["width_projections"] = projections
    with (output_dir / "runtime_projection.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(runtime_document, handle, indent=2, sort_keys=True)
        handle.write("\n")

    sizes = np.asarray([item["L"] for item in strip_results], dtype=float)
    values = np.asarray([item["free_energy"] for item in strip_results], dtype=float)
    errors = np.asarray([item["free_energy_se"] for item in strip_results], dtype=float)
    primary = summary["primary_L8_l24"]
    coefficients = primary["coefficients"]
    grid = np.linspace(float(np.min(sizes)), float(np.max(sizes)), 400)
    fitted = coefficients[0] + coefficients[1] / grid**2
    if primary["include_l4"]:
        fitted += coefficients[2] / grid**4

    figure, axis = plt.subplots(figsize=(6.4, 4.4))
    axis.errorbar(
        1.0 / sizes**2,
        values,
        yerr=errors,
        fmt="o",
        color="tab:blue",
        capsize=3,
        label="quenched strip data",
    )
    axis.plot(
        1.0 / grid**2,
        fitted,
        color="tab:orange",
        label=r"fit: $L^{-2}+L^{-4}$",
    )
    reported = summary["reported"]
    axis.set_xlabel(r"$1/L^2$")
    axis.set_ylabel(r"$f_L=-\Lambda_0/L$")
    axis.set_title("RBIM Nishimori-point effective central charge")
    axis.grid(alpha=0.25)
    axis.legend()
    axis.text(
        0.04,
        0.08,
        rf"$c_{{\rm eff}}={reported['central_charge']:.4f}"
        + "\n"
        + rf"bootstrap SE $={reported['bootstrap_se']:.3g}$",
        transform=axis.transAxes,
    )
    figure.tight_layout()
    figure.savefig(output_dir / "central_charge_fit.png", dpi=180)
    plt.close(figure)


def format_charge_annotation(reported):
    """Return a two-line Matplotlib mathtext annotation for a charge fit."""
    return (
        rf"$c_{{\mathit{{eff}}}}={reported['central_charge']:.4f}$"
        + "\n"
        + rf"bootstrap SE $={reported['bootstrap_se']:.3g}$"
    )


def _apply_italic_axis_style(axis):
    """Apply italic typography to every text artist owned by an axis."""
    text_artists = [
        axis.title,
        axis.xaxis.label,
        axis.yaxis.label,
        axis.xaxis.get_offset_text(),
        axis.yaxis.get_offset_text(),
        *axis.get_xticklabels(),
        *axis.get_yticklabels(),
        *axis.texts,
    ]
    legend = axis.get_legend()
    if legend is not None:
        text_artists.extend(legend.get_texts())
        if legend.get_title() is not None:
            text_artists.append(legend.get_title())
    for artist in text_artists:
        artist.set_fontstyle("italic")


def make_ensemble_central_charge_figure(width_results, summary):
    """Build the styled independent-sample RBIM central-charge figure."""
    width_results = sorted(width_results, key=lambda item: int(item["L"]))
    sizes = np.asarray([item["L"] for item in width_results], dtype=float)
    values = np.asarray([item["free_energy"] for item in width_results], dtype=float)
    errors = np.asarray(
        [item["free_energy_se"] for item in width_results], dtype=float
    )
    primary = summary[summary["reported"]["primary_fit"]]
    coefficients = primary["coefficients"]
    grid = np.linspace(float(np.min(sizes)), float(np.max(sizes)), 400)
    fitted = coefficients[0] + coefficients[1] / grid**2
    if primary["include_l4"]:
        fitted += coefficients[2] / grid**4

    figure, axis = plt.subplots(figsize=(6.4, 4.4))
    axis.errorbar(
        1.0 / sizes**2,
        values,
        yerr=errors,
        fmt="o",
        color="tab:blue",
        markersize=math.sqrt(MARKER_AREA),
        alpha=PLOT_ALPHA,
        capsize=3,
        label="quenched sample mean",
    )
    axis.plot(
        1.0 / grid**2,
        fitted,
        color=FIT_COLOR,
        linestyle=FIT_LINESTYLE,
        alpha=PLOT_ALPHA,
        label=r"fit: $L^{-2}+L^{-4}$",
    )
    reported = summary["reported"]
    axis.set_xlabel(r"$1/L^2$")
    axis.set_ylabel(r"$f_L=-\overline{\Lambda_0}/L$")
    axis.set_title("RBIM Nishimori-point two-hour pilot")
    axis.grid(alpha=0.25)
    axis.legend()
    axis.text(
        0.04,
        0.08,
        format_charge_annotation(reported),
        transform=axis.transAxes,
    )
    _apply_italic_axis_style(axis)
    figure.tight_layout()
    return figure, axis


def regenerate_ensemble_plot_from_artifacts(output_dir):
    """Regenerate only the ensemble PNG from existing width and fit artifacts."""
    output_dir = Path(output_dir)
    with (output_dir / "width_summary.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        width_results = [
            {
                "L": int(row["L"]),
                "free_energy": float(row["free_energy"]),
                "free_energy_se": float(row["free_energy_se"]),
            }
            for row in csv.DictReader(handle)
        ]
    with (output_dir / "central_charge_fit.json").open(encoding="utf-8") as handle:
        summary = json.load(handle)

    figure, _ = make_ensemble_central_charge_figure(width_results, summary)
    plot_path = output_dir / "central_charge_fit.png"
    figure.savefig(plot_path, dpi=180)
    plt.close(figure)
    return plot_path


def write_ensemble_artifacts(
    records,
    width_results,
    summary,
    run_config,
    output_dir,
):
    """Write independent-sample data, fit metadata, configuration, and plot."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    records = sorted(
        records, key=lambda item: (int(item["L"]), int(item["sample_index"]))
    )
    width_results = sorted(width_results, key=lambda item: int(item["L"]))

    sample_fields = (
        "L",
        "sample_index",
        "seed",
        "p",
        "coupling",
        "burn_in",
        "retained_rows",
        "block_length",
        "free_energy",
        "runtime_seconds",
        "antiferromagnetic_bonds",
        "total_retained_bonds",
        "disorder_ensemble",
    )
    with (output_dir / "samples.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=sample_fields)
        writer.writeheader()
        for record in records:
            writer.writerow({field: record[field] for field in sample_fields})

    width_fields = (
        "L",
        "p",
        "coupling",
        "burn_in",
        "retained_rows",
        "block_length",
        "sample_count",
        "free_energy",
        "free_energy_se",
        "mean_runtime_seconds",
        "antiferromagnetic_bonds",
        "total_retained_bonds",
        "disorder_ensemble",
    )
    with (output_dir / "width_summary.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=width_fields)
        writer.writeheader()
        for item in width_results:
            writer.writerow({field: item[field] for field in width_fields})

    with (output_dir / "central_charge_fit.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")
    with (output_dir / "run_config.json").open("w", encoding="utf-8") as handle:
        json.dump(run_config, handle, indent=2, sort_keys=True)
        handle.write("\n")

    figure, _ = make_ensemble_central_charge_figure(width_results, summary)
    figure.savefig(output_dir / "central_charge_fit.png", dpi=180)
    plt.close(figure)


def run_workflow(
    sizes,
    p,
    seed,
    pilot_blocks,
    target_se,
    max_local_seconds,
    bootstrap_samples,
    output_dir,
    strip_runner=None,
):
    """Run a five-width pilot and continue only when its measured cost fits."""
    if strip_runner is None:
        strip_runner = run_random_strip
    sizes = [int(L) for L in sizes]
    pilot_blocks = int(pilot_blocks)
    bootstrap_samples = int(bootstrap_samples)
    p = float(p)
    target_se = float(target_se)
    max_local_seconds = float(max_local_seconds)
    if pilot_blocks < 2:
        raise ValueError("pilot_blocks must be at least two")
    if len(sizes) < 5 or len(set(sizes)) != len(sizes):
        raise ValueError("at least five unique widths are required")
    if any(L < 2 for L in sizes):
        raise ValueError("all widths must be at least two")
    if sum(L >= 8 for L in sizes) < 3 or sum(L >= 10 for L in sizes) < 3:
        raise ValueError("sizes do not support the requested L>=8 and L>=10 fits")
    if not math.isfinite(p) or not 0.0 < p < 0.5:
        raise ValueError("p must satisfy 0 < p < 0.5")
    if not math.isfinite(target_se) or target_se <= 0.0:
        raise ValueError("target_se must be finite and positive")
    if not math.isfinite(max_local_seconds) or max_local_seconds < 0.0:
        raise ValueError("max_local_seconds must be finite and nonnegative")
    if bootstrap_samples < 2:
        raise ValueError("bootstrap_samples must be at least two")

    pilots = []
    for L in sizes:
        L = int(L)
        block_length = 100 * L
        pilots.append(
            strip_runner(
                L=L,
                p=p,
                seed=int(seed) + L,
                burn_in=50 * L,
                retained_rows=pilot_blocks * block_length,
                block_length=block_length,
                progress=True,
            )
        )

    projections = [estimate_required_rows(item, target_se) for item in pilots]
    projected_total = float(
        sum(item["projected_runtime_seconds"] for item in projections)
    )
    production_launched = projected_total <= float(max_local_seconds)
    if production_launched:
        selected = []
        for pilot, projection in zip(pilots, projections):
            L = pilot["L"]
            selected.append(
                strip_runner(
                    L=L,
                    p=p,
                    seed=int(seed) + 10000 + L,
                    burn_in=50 * L,
                    retained_rows=projection["required_retained_rows"],
                    block_length=100 * L,
                    progress=True,
                )
            )
    else:
        selected = pilots

    summary = central_charge_summary(
        selected, bootstrap_samples=bootstrap_samples, seed=int(seed) + 20000
    )
    achieved_target_all = bool(
        all(item["free_energy_se"] <= target_se for item in selected)
    )
    runtime = {
        "production_launched": production_launched,
        "projected_total_seconds": projected_total,
        "projected_production_seconds": projected_total,
        "pilot_runtime_seconds": float(
            sum(item["runtime_seconds"] for item in pilots)
        ),
        "target_free_energy_se": float(target_se),
        "max_local_seconds": float(max_local_seconds),
        "achieved_target_all": achieved_target_all,
        "preliminary": not achieved_target_all,
    }
    write_analysis_artifacts(
        selected, summary, projections, runtime, output_dir
    )
    reported = summary["reported"]
    print(
        f"c_eff={reported['central_charge']:.8f} +/- "
        f"{reported['bootstrap_se']:.3e} (bootstrap); "
        f"production_launched={production_launched}; "
        f"preliminary={not achieved_target_all}",
        flush=True,
    )
    return selected, summary, runtime


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=int, default=[8, 10, 12, 16, 20])
    parser.add_argument("--p", type=float, default=0.1092212)
    parser.add_argument("--seed", type=int, default=1221092212)
    parser.add_argument("--pilot-blocks", type=int, default=2)
    parser.add_argument("--target-se", type=float, default=1e-4)
    parser.add_argument("--max-local-seconds", type=float, default=600.0)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/random_bond_ising_nishimori"),
    )
    return parser


def main(argv=None):
    arguments = build_parser().parse_args(argv)
    run_workflow(
        sizes=arguments.sizes,
        p=arguments.p,
        seed=arguments.seed,
        pilot_blocks=arguments.pilot_blocks,
        target_se=arguments.target_se,
        max_local_seconds=arguments.max_local_seconds,
        bootstrap_samples=arguments.bootstrap_samples,
        output_dir=arguments.output_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
