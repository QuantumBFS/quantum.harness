#!/usr/bin/env python3
"""Reproduce and compare the transversal single-spin data from PRL Fig. 3."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.request import urlopen
from zipfile import ZipFile

import numpy as np
from matplotlib import pyplot as plt
from scipy.integrate import trapezoid

from floquet_if_manybody.backends.uniform_tempo import (
    UNIFORM_TEMPO_REVISION,
    UniformTempoBackend,
    UniformTempoControls,
)
from floquet_if_manybody.config import BathConfig, ModelConfig
from floquet_if_manybody.convergence import atomic_write_result, curve_residual
from floquet_if_manybody.heat_current import heat_current_spectrum
from floquet_if_manybody.operators import pauli

ZENODO_RECORD = "https://zenodo.org/records/19593671"
ZENODO_ARCHIVE = (
    "https://zenodo.org/api/records/19593671/files/"
    "exact_floquet_dynamics_of_strongly_damped_driven_quantum_systems.zip/content"
)
ZENODO_MD5 = "0f3f9d9d8538aa96aee089973df7d9c2"
REFERENCE_FREQUENCY = np.arange(0.005, 15.0001, 0.005)


def _reference_name(drive_frequency: float) -> str:
    label = f"{drive_frequency:g}"
    return (
        "fig_3/heat_current_transversal_Ω_1_ϵ_d_1_"
        f"ω_d_{label}_α_0.05_ω_c_2.5_bond_dim_235_dt_0.052.csv"
    )


def download_reference() -> dict[float, np.ndarray]:
    """Download the immutable author archive and extract the three bottom-panel curves."""
    with urlopen(ZENODO_ARCHIVE, timeout=30) as response:  # noqa: S310
        archive = response.read()
    digest = hashlib.md5(archive, usedforsecurity=False).hexdigest()
    if digest != ZENODO_MD5:
        raise ValueError(f"Zenodo archive checksum mismatch: {digest}")
    curves: dict[float, np.ndarray] = {}
    with ZipFile(BytesIO(archive)) as bundle:
        for drive_frequency in (1.0, 1.5, 2.0):
            values = np.loadtxt(BytesIO(bundle.read(_reference_name(drive_frequency))))
            if values.shape != REFERENCE_FREQUENCY.shape or not np.all(np.isfinite(values)):
                raise ValueError(f"invalid Fig. 3 reference curve for wd={drive_frequency:g}")
            curves[drive_frequency] = np.asarray(values, dtype=float)
    return curves


def comparison_metrics(reference: np.ndarray, candidate: np.ndarray) -> dict[str, float]:
    """Return direct-amplitude and normalized-shape discrepancies."""
    direct = curve_residual(
        REFERENCE_FREQUENCY,
        reference,
        REFERENCE_FREQUENCY,
        candidate,
    )
    reference_area = float(trapezoid(abs(reference), REFERENCE_FREQUENCY))
    candidate_area = float(trapezoid(abs(candidate), REFERENCE_FREQUENCY))
    if reference_area <= 0 or candidate_area <= 0:
        raise ValueError("Fig. 3 curves must have positive integrated magnitude")
    shape = curve_residual(
        REFERENCE_FREQUENCY,
        reference / reference_area,
        REFERENCE_FREQUENCY,
        candidate / candidate_area,
    )
    return {
        "continuous_relative_l1": direct,
        "normalized_shape_relative_l1": shape,
        "integrated_magnitude_ratio": candidate_area / reference_area,
    }


def run_point(
    drive_frequency: float,
    reference: np.ndarray,
    cache_directory: Path,
    *,
    tolerance: float = 1e-6,
    phase_samples: int = 4,
) -> dict[str, Any]:
    """Run one independent UniformTEMPO point at the published Fig. 3 controls."""
    steps_per_period = int(round(120 / drive_frequency))
    model = ModelConfig(
        n=1,
        j=0.0,
        omega=1.0,
        drive_amplitude=1.0,
        drive_frequency=drive_frequency,
    )
    bath = BathConfig(alpha=0.05, cutoff=2.5, temperature=0.0)
    controls = UniformTempoControls(
        steps_per_period=steps_per_period,
        tolerance=tolerance,
        phase_samples=phase_samples,
        delay_periods=12,
        low_rank_svd=True,
        truncation="abs",
        cap_rank=5_000,
        max_rank=10_000,
    )
    run = UniformTempoBackend(
        tensor_cache_directory=cache_directory / "process_tensors"
    ).run_periodic(
        0.5 * pauli("x"),
        pauli("z"),
        model,
        bath,
        controls,
        drive_operator=pauli("z"),
    )
    heat = heat_current_spectrum(run.correlation, bath, REFERENCE_FREQUENCY)
    diagnostics = {
        **run.diagnostics,
        **run.metadata,
        "connected_tail_amplitude": float(abs(run.correlation.connected[-1])),
    }
    physical_gates_passed = bool(
        float(diagnostics["fixed_point_residual"]) <= 1e-3
        and float(diagnostics["trace_error"]) <= 5e-3
        and float(diagnostics["hermiticity_error"]) <= 5e-3
        and float(diagnostics["minimum_density_eigenvalue"]) >= -5e-3
        and float(diagnostics["connected_tail_amplitude"]) <= 5e-2
    )
    return {
        "method": "uniform_tempo_fig3_transversal_reproduction",
        "converged": physical_gates_passed,
        "reference": {
            "record": ZENODO_RECORD,
            "archive_md5": ZENODO_MD5,
            "panel": "Fig. 3 bottom",
        },
        "uniform_tempo_revision": UNIFORM_TEMPO_REVISION,
        "model": asdict(model),
        "bath": asdict(bath),
        "controls": asdict(controls),
        "diagnostics": diagnostics,
        "metrics": comparison_metrics(reference, heat.continuous),
        "frequency": heat.frequencies.tolist(),
        "reference_continuous": reference.tolist(),
        "continuous": heat.continuous.tolist(),
        "delta_peaks": [asdict(item) for item in heat.delta_peaks],
    }


def plot_result(result: dict[str, Any], stem: Path) -> None:
    frequency = np.asarray(result["frequency"], dtype=float)
    reference = np.asarray(result["reference_continuous"], dtype=float)
    candidate = np.asarray(result["continuous"], dtype=float)
    figure, axis = plt.subplots(figsize=(7.2, 4.2))
    axis.plot(frequency, reference, label="Mickiewicz et al. Fig. 3 data", lw=1.5)
    axis.plot(frequency, candidate, "--", label="independent UniformTEMPO", lw=1.2)
    for peak in result["delta_peaks"]:
        axis.axvline(float(peak["frequency"]), color="black", alpha=0.35, lw=0.8)
    model = result["model"]
    axis.set(
        xlim=(0, 4),
        xlabel=r"bath frequency $\omega/\Omega$",
        ylabel=r"continuous $\bar j(\omega)/\Omega$",
        title=rf"Fig. 3 bottom validation, $\omega_d={float(model['drive_frequency']):g}\Omega$",
    )
    axis.grid(alpha=0.2)
    axis.legend(frameon=False)
    figure.tight_layout()
    stem.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(stem.with_suffix(".png"), dpi=220)
    figure.savefig(stem.with_suffix(".pdf"))
    plt.close(figure)


def plot_summary(results: list[dict[str, Any]], stem: Path) -> None:
    """Plot the complete three-curve bottom-panel validation in one artifact."""
    ordered = sorted(results, key=lambda item: float(item["model"]["drive_frequency"]))
    figure, axes = plt.subplots(1, 3, figsize=(12.0, 3.55), sharex=True)
    for axis, result in zip(axes, ordered, strict=True):
        frequency = np.asarray(result["frequency"], dtype=float)
        reference = np.asarray(result["reference_continuous"], dtype=float)
        candidate = np.asarray(result["continuous"], dtype=float)
        model = result["model"]
        metrics = result["metrics"]
        axis.plot(frequency, reference, label="published data", lw=1.35)
        axis.plot(frequency, candidate, "--", label="independent run", lw=1.15)
        for peak in result["delta_peaks"]:
            if float(peak["frequency"]) <= 4:
                axis.axvline(float(peak["frequency"]), color="black", alpha=0.3, lw=0.7)
        axis.set(
            xlim=(0, 4),
            xlabel=r"$\omega/\Omega$",
            title=(
                rf"$\omega_d={float(model['drive_frequency']):g}\Omega$"
                "\n"
                rf"shape $L^1={float(metrics['normalized_shape_relative_l1']):.3f}$"
            ),
        )
        axis.grid(alpha=0.2)
    axes[0].set_ylabel(r"continuous $\bar j(\omega)/\Omega$")
    axes[0].legend(frameon=False, fontsize=8)
    figure.suptitle("Independent reproduction of Mickiewicz et al., Fig. 3 bottom")
    figure.tight_layout()
    stem.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(stem.with_suffix(".png"), dpi=220)
    figure.savefig(stem.with_suffix(".pdf"))
    plt.close(figure)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--drive-frequency",
        type=float,
        choices=(1.0, 1.5, 2.0),
        default=2.0,
    )
    parser.add_argument("--plot-only", type=Path)
    parser.add_argument("--plot-summary", action="store_true")
    parser.add_argument("--tolerance", type=float, default=1e-6)
    parser.add_argument("--phase-samples", type=int, default=4)
    parser.add_argument(
        "--figures",
        type=Path,
        default=Path("figures/validation"),
    )
    parser.add_argument("--output", type=Path, default=Path("results/validation"))
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path("results/cache/fig3_uniform_tempo"),
    )
    arguments = parser.parse_args()
    if arguments.plot_summary:
        result_paths = [
            arguments.output / "fig3_transversal_wd1.json",
            arguments.output / "fig3_transversal_wd1p5.json",
            arguments.output / "fig3_transversal_wd2.json",
        ]
        results = [json.loads(path.read_text(encoding="utf-8")) for path in result_paths]
        if not all(bool(result["converged"]) for result in results):
            raise ValueError("all three Fig. 3 points must pass physical gates")
        plot_summary(results, arguments.figures / "fig3_transversal_summary")
        return 0
    if arguments.plot_only is not None:
        result = json.loads(arguments.plot_only.read_text(encoding="utf-8"))
        label = f"{float(result['model']['drive_frequency']):g}".replace(".", "p")
        plot_result(result, arguments.figures / f"fig3_transversal_wd{label}")
        return 0
    references = download_reference()
    result = run_point(
        arguments.drive_frequency,
        references[arguments.drive_frequency],
        arguments.cache,
        tolerance=arguments.tolerance,
        phase_samples=arguments.phase_samples,
    )
    arguments.output.mkdir(parents=True, exist_ok=True)
    label = f"{arguments.drive_frequency:g}".replace(".", "p")
    atomic_write_result(arguments.output / f"fig3_transversal_wd{label}.json", result)
    plot_result(result, arguments.figures / f"fig3_transversal_wd{label}")
    return 0 if result["converged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
