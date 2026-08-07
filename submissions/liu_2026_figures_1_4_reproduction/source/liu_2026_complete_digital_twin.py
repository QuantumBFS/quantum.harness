#!/usr/bin/env python3
"""Budgeted Liu-2026 Figure-4 digital twin using Cold_Atom Gate Simu_Platform.

The controller receives only finite-shot estimates. Exact coherent/open-system
metrics are written under ``validator_only`` and are never used to choose a
scan point. Stochastic physics is evaluated with a fixed hidden-context
ensemble and then sampled in batch, which preserves the one-hour wall budget.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from scipy import optimize

from cs_tweezer_sim import (
    CompositeShotNoiseModel,
    CompositeTransfer,
    DopplerNoiseModel,
    FirstOrderLowPassTransfer,
    GainOffsetTransfer,
    GaussianBeamCouplingSpec,
    HardwareTransferGraph,
    LaserPhaseFrequencyNoiseModel,
    PulseEnergyNoiseModel,
    SampledWaveform,
    SimulationContext,
    StochasticScopeEngine,
    ThermalPositionNoiseModel,
    draw_program_contexts,
    liu_2026_yb171_four_level_profile,
    single_photon_effective_wavevector_rad_per_m,
)
from cs_tweezer_sim.config import TransitionCouplingSpec
from cs_tweezer_sim.gate_metrics import (
    evaluate_coherent_ensemble,
    evaluate_coherent_gate,
    evaluate_open_system_gate,
)
from cs_tweezer_sim.multilevel_config import PairInteractionSpec
from cs_tweezer_sim.qutip_multilevel_backend import QutipMultilevelBackend
from cs_tweezer_sim.stochastic import (
    thermal_velocity_sigma_m_per_s,
)
from cs_tweezer_sim.waveform_compiler import compile_sampled_fields


TWOPI = 2.0 * math.pi
OMEGA0 = TWOPI * 6.0
SEED = 260605060
FINITE_BLOCKADE_MHZ = 303.325
SHOT_COUNT = 50_000


def progress(message: str) -> None:
    print(message, flush=True)


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(
            json_safe(value),
            handle,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        handle.write("\n")
    temporary.replace(path)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def load_ideal_waveform(
    archive_path: Path, *, intervals: int = 64
) -> tuple[SampledWaveform, np.ndarray]:
    with np.load(archive_path) as archive:
        times = np.asarray(archive["times_us"], dtype=float)
        amplitude = np.asarray(archive["amplitude"], dtype=float)
        phase = np.asarray(archive["phase_unwrapped"], dtype=float)
    duration = float(times[-1] - times[0])
    dt = duration / intervals
    centers = times[0] + (np.arange(intervals) + 0.5) * dt
    complex_field = (
        OMEGA0
        * np.interp(centers, times, amplitude)
        * np.exp(1j * np.interp(centers, times, phase))
    )
    waveform = SampledWaveform(
        dt_us=dt,
        amplitude_rad_per_us=tuple(float(x) for x in np.abs(complex_field)),
        phase_rad=tuple(float(x) for x in np.unwrap(np.angle(complex_field))),
        detuning_rad_per_us=(0.0,) * intervals,
    )
    return waveform, complex_field


def complex_to_waveform(field: np.ndarray, dt_us: float) -> SampledWaveform:
    return SampledWaveform(
        dt_us=dt_us,
        amplitude_rad_per_us=tuple(float(x) for x in np.abs(field)),
        phase_rad=tuple(float(x) for x in np.unwrap(np.angle(field))),
        detuning_rad_per_us=(0.0,) * len(field),
    )


def gate_program(waveform: SampledWaveform, name: str):
    return compile_sampled_fields(
        n_atoms=2,
        fields={"rydberg_302": waveform},
        targets={"rydberg_302": (0, 1)},
        measure=False,
        name=name,
    )


def yb_config(*, include_decay: bool):
    config = liu_2026_yb171_four_level_profile(
        n_atoms=2,
        include_effective_rydberg_decay=include_decay,
        nominal_rr_interaction_rad_per_us=None,
    )
    interactions = (
        PairInteractionSpec(
            "r", "r", TWOPI * FINITE_BLOCKADE_MHZ, label="measured blockade"
        ),
        PairInteractionSpec(
            "r",
            "r_prime",
            TWOPI * FINITE_BLOCKADE_MHZ,
            symmetric=True,
            label="measured blockade",
        ),
        PairInteractionSpec(
            "r_prime",
            "r_prime",
            TWOPI * FINITE_BLOCKADE_MHZ,
            label="measured blockade",
        ),
    )
    channels = dict(config.channels)
    channels["rydberg_302"] = replace(
        channels["rydberg_302"],
        additional_transition_couplings=(
            TransitionCouplingSpec("0_r_prime", -1.0),
        ),
    )
    return replace(
        config,
        channels=channels,
        model=replace(
            config.model,
            static_level_energies_rad_per_us={
                **dict(config.model.static_level_energies_rad_per_us),
                "r_prime": TWOPI * 16.1,
            },
            pair_interactions=interactions,
        ),
    )


def apply_aom(
    command: SampledWaveform, bandwidth_mhz: float, gain: float
) -> SampledWaveform:
    graph = HardwareTransferGraph(
        {
            "rydberg_302": CompositeTransfer(
                (
                    GainOffsetTransfer(amplitude_gain=gain),
                    FirstOrderLowPassTransfer(
                        bandwidth_mhz, ringdown_time_constants=0.0
                    ),
                )
            )
        }
    )
    return graph.apply({"rydberg_302": command})["rydberg_302"]


def digitize_figure4a_before_amplitude(
    image_path: Path,
) -> tuple[np.ndarray, np.ndarray]:
    """Digitize visible blue pixels from Figure 4a's upper panel.

    Pixel calibration follows the printed ticks: x=80,164,248 maps to
    0,0.2,0.4 us; y=111,72,33 maps to intensity 0,0.5,1.0.
    """

    pixels = np.asarray(Image.open(image_path).convert("RGB"), dtype=float)
    target = np.asarray((65.0, 105.0, 224.0))
    x_values: list[float] = []
    intensity_values: list[float] = []
    for x_pixel in range(80, 319):
        distances = np.linalg.norm(
            pixels[22:114, x_pixel, :] - target, axis=1
        )
        selected = np.flatnonzero(distances < 85.0)
        if not len(selected):
            continue
        weights = np.exp(-((distances[selected] / 35.0) ** 2))
        y_pixel = 22.0 + float(np.average(selected, weights=weights))
        x_values.append((x_pixel - 80.0) / 420.0)
        intensity_values.append(max(0.0, (111.0 - y_pixel) / 78.0))
    if len(x_values) < 50:
        raise RuntimeError("too few Figure 4a blue pixels were recovered")
    return np.asarray(x_values), np.asarray(intensity_values)


def fit_aom_transfer(
    ideal: SampledWaveform,
    paper_image: Path,
) -> tuple[float, float, dict[str, Any]]:
    digitized_t, digitized_i = digitize_figure4a_before_amplitude(paper_image)
    centers = (np.arange(ideal.n_samples) + 0.5) * ideal.dt_us

    def objective(values: np.ndarray) -> float:
        bandwidth, gain = (float(values[0]), float(values[1]))
        output = apply_aom(ideal, bandwidth, gain)
        predicted_i = (
            np.asarray(output.amplitude_rad_per_us, dtype=float) / OMEGA0
        ) ** 2
        prediction = np.interp(digitized_t, centers, predicted_i)
        return float(np.mean((prediction - digitized_i) ** 2))

    fitted = optimize.differential_evolution(
        objective,
        bounds=((2.0, 20.0), (0.9, 1.1)),
        seed=SEED,
        popsize=8,
        maxiter=40,
        polish=True,
        workers=1,
    )
    bandwidth, gain = map(float, fitted.x)
    return bandwidth, gain, {
        "bandwidth_mhz": bandwidth,
        "gain": gain,
        "objective_mse": float(fitted.fun),
        "digitized_points": len(digitized_t),
        "digitized_time_us": digitized_t,
        "digitized_before_intensity": digitized_i,
        "source": "Liu et al. Figure 4a raster trace",
    }


def additive_coefficients(
    output: np.ndarray, ideal: np.ndarray, dt_us: float
) -> np.ndarray:
    envelope = np.abs(ideal)
    ridge = (1e-4 * OMEGA0) ** 2
    delta = output - ideal
    sx = envelope * delta.real / (envelope**2 + ridge)
    sy = envelope * delta.imag / (envelope**2 + ridge)
    return np.concatenate((sx, sy)) * math.sqrt(dt_us)


def command_from_coefficients(
    ideal: np.ndarray, coefficients: np.ndarray, dt_us: float
) -> np.ndarray:
    n = len(ideal)
    sx = coefficients[:n] / math.sqrt(dt_us)
    sy = coefficients[n:] / math.sqrt(dt_us)
    return ideal + np.abs(ideal) * (sx + 1j * sy)


def sample_contexts(
    waveform: SampledWaveform,
    *,
    linewidth_hz: float,
    count: int,
    seed: int,
    include_doppler: bool = True,
    include_position: bool = True,
    include_amplitude: bool = True,
    include_phase: bool = True,
) -> tuple[SimulationContext, ...]:
    models = []
    if include_doppler:
        models.append(
            DopplerNoiseModel(
                temperature_uk=2.7,
                rydberg_level="r",
                additional_shifted_levels=("r_prime",),
                effective_wavevector_rad_per_m=(
                    single_photon_effective_wavevector_rad_per_m(302.0)
                ),
                mass_kg=170.93633152 * 1.66053906660e-27,
            )
        )
    if include_position:
        models.append(
            ThermalPositionNoiseModel(
                nominal_positions_um=((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
                sigma_xyz_um=((0.02, 0.02, 0.02), (0.02, 0.02, 0.02)),
                beams=(
                    GaussianBeamCouplingSpec(
                        "rydberg_302", 0, 12.0, (0.0, 0.0, 0.0)
                    ),
                    GaussianBeamCouplingSpec(
                        "rydberg_302", 1, 12.0, (2.0, 0.0, 0.0)
                    ),
                ),
                pair_interaction_label="measured blockade",
                blockade_power=6.0,
            )
        )
    if include_amplitude:
        models.append(
            PulseEnergyNoiseModel(
                channels=("rydberg_302",),
                energy_covariance=((0.01**2,),),
            )
        )
    if include_phase:
        models.append(
            LaserPhaseFrequencyNoiseModel(
                channels=("rydberg_302",),
                lorentzian_linewidth_fwhm_hz=(linewidth_hz,),
                quasistatic_frequency_covariance_hz2=((500.0**2,),),
                ou_frequency_sigma_hz=(1000.0,),
                sample_interval_us=waveform.dt_us,
                ou_correlation_time_us=0.2,
            )
        )
    composite = CompositeShotNoiseModel(tuple(models))
    return draw_program_contexts(
        composite,
        gate_program(waveform, "context-template"),
        n_atoms=2,
        count=count,
        seed=seed,
    )


def finite_shot_error(
    physical_error: float, rng: np.random.Generator
) -> tuple[float, float, int]:
    probability = float(np.clip(physical_error, 1e-9, 1.0 - 1e-9))
    failures = int(rng.binomial(SHOT_COUNT, probability))
    estimate = (failures + 0.5) / (SHOT_COUNT + 1.0)
    sigma = math.sqrt(estimate * (1.0 - estimate) / (SHOT_COUNT + 2.0))
    return float(estimate), float(sigma), failures


def evaluate_feedback(
    backend: QutipMultilevelBackend,
    waveform: SampledWaveform,
    contexts: tuple[SimulationContext, ...],
    target: np.ndarray,
    irreversible_floor: float,
    rng: np.random.Generator,
) -> dict[str, Any]:
    ensemble = evaluate_coherent_ensemble(
        backend,
        gate_program(waveform, "finite-shot-feedback"),
        contexts=contexts,
        target=target,
    )
    physical_error = min(1.0, ensemble.infidelity_mean + irreversible_floor)
    observed, sigma, failures = finite_shot_error(physical_error, rng)
    return {
        "observed_error": observed,
        "uncertainty": sigma,
        "failures": failures,
        "shots": SHOT_COUNT,
        "controller_visible_fidelity": 1.0 - observed,
        "validator_only": {
            "coherent_ensemble_infidelity": ensemble.infidelity_mean,
            "coherent_ensemble_standard_error": ensemble.fidelity_standard_error,
            "irreversible_floor": irreversible_floor,
            "physical_error_before_shot_sampling": physical_error,
        },
    }


def run_closed_loop(
    *,
    ideal_field: np.ndarray,
    ideal_waveform: SampledWaveform,
    eigenvectors: np.ndarray,
    eigenvalues: np.ndarray,
    bandwidth_mhz: float,
    gain: float,
    target: np.ndarray,
    irreversible_floor: float,
    contexts: tuple[SimulationContext, ...],
    backend: QutipMultilevelBackend,
) -> tuple[np.ndarray, list[dict[str, Any]], list[dict[str, Any]]]:
    rng = np.random.default_rng(SEED + 900)
    correction = np.zeros(2 * len(ideal_field), dtype=float)
    principal = eigenvectors[:, :10]
    initial_output = apply_aom(ideal_waveform, bandwidth_mhz, gain)
    initial_field = np.asarray(initial_output.amplitude_rad_per_us) * np.exp(
        1j * np.asarray(initial_output.phase_rad)
    )
    output_distortion = additive_coefficients(
        initial_field, ideal_field, ideal_waveform.dt_us
    )
    scan_rows: list[dict[str, Any]] = []
    trajectory: list[dict[str, Any]] = []

    initial_feedback = evaluate_feedback(
        backend,
        initial_output,
        contexts,
        target,
        irreversible_floor,
        rng,
    )
    trajectory.append(
        {
            "step": 0,
            "mode": 0,
            "observed_error": initial_feedback["observed_error"],
            "uncertainty": initial_feedback["uncertainty"],
            "controller_visible_fidelity": initial_feedback[
                "controller_visible_fidelity"
            ],
        }
    )

    for mode_index in range(10):
        mode = principal[:, mode_index]
        current = float(mode @ correction)
        inferred_offset = float(mode @ output_distortion)
        curvature = max(float(eigenvalues[mode_index]), 1e-12)
        shot_sigma = math.sqrt(0.004 * 0.996 / SHOT_COUNT)
        span = max(
            0.002,
            min(
                0.08,
                max(1.5 * abs(inferred_offset), math.sqrt(12 * shot_sigma / curvature)),
            ),
        )
        trials = np.linspace(current - span, current + span, 5)
        observations = []
        uncertainties = []
        candidates = []
        for trial in trials:
            candidate = correction + (float(trial) - current) * mode
            command_field = command_from_coefficients(
                ideal_field, candidate, ideal_waveform.dt_us
            )
            command = complex_to_waveform(command_field, ideal_waveform.dt_us)
            output = apply_aom(command, bandwidth_mhz, gain)
            feedback = evaluate_feedback(
                backend,
                output,
                contexts,
                target,
                irreversible_floor,
                rng,
            )
            observations.append(feedback["observed_error"])
            uncertainties.append(feedback["uncertainty"])
            candidates.append(candidate)
            scan_rows.append(
                {
                    "cycle": 1,
                    "mode": mode_index + 1,
                    "coefficient": float(trial),
                    "observed_error": feedback["observed_error"],
                    "uncertainty": feedback["uncertainty"],
                    "failures": feedback["failures"],
                    "shots": feedback["shots"],
                    "selected": False,
                    "data_class": "simulator-generated finite-shot observation",
                }
            )
        weights = 1.0 / np.maximum(np.asarray(uncertainties), 1e-9)
        polynomial = np.polyfit(trials, observations, 2, w=weights)
        if polynomial[0] > 0:
            optimum = float(-polynomial[1] / (2.0 * polynomial[0]))
            optimum = float(np.clip(optimum, trials[0], trials[-1]))
            selected_index = int(np.argmin(np.abs(trials - optimum)))
        else:
            selected_index = int(np.argmin(observations))
        correction = candidates[selected_index]
        scan_rows[-len(trials) + selected_index]["selected"] = True
        trajectory.append(
            {
                "step": mode_index + 1,
                "mode": mode_index + 1,
                "observed_error": observations[selected_index],
                "uncertainty": uncertainties[selected_index],
                "controller_visible_fidelity": 1.0 - observations[selected_index],
            }
        )
        progress(
            f"  mode {mode_index + 1:02d}/10: "
            f"observed 1-F={observations[selected_index]:.4e}"
        )
    final_field = command_from_coefficients(
        ideal_field, correction, ideal_waveform.dt_us
    )
    return final_field, scan_rows, trajectory


def ensemble_metrics(
    backend: QutipMultilevelBackend,
    waveform: SampledWaveform,
    target: np.ndarray,
    contexts: tuple[SimulationContext, ...],
) -> dict[str, float]:
    result = evaluate_coherent_ensemble(
        backend,
        gate_program(waveform, "noise-ablation"),
        contexts=contexts,
        target=target,
    )
    # These coherent contexts contain no |L> erasure sink. Liu's no-loss
    # postselection therefore removes nothing here; dividing by computational
    # return would incorrectly discard coherent Rydberg leakage as detected
    # atom loss. The separate open-system anchor handles the true |L> sink.
    conditional = result.fidelity_mean
    return {
        "raw_infidelity": result.infidelity_mean,
        "conditional_infidelity": 1.0 - conditional,
        "computational_return": result.computational_return_mean,
        "standard_error": result.fidelity_standard_error,
    }


def make_summary_figure(
    output: Path,
    *,
    ideal: SampledWaveform,
    before: SampledWaveform,
    after: SampledWaveform,
    trajectory: list[dict[str, Any]],
    budget_rows: list[dict[str, Any]],
    linewidth_rows: list[dict[str, Any]],
) -> None:
    times = (np.arange(ideal.n_samples) + 0.5) * ideal.dt_us
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.5))
    axis = axes[0, 0]
    for waveform, label, color in (
        (ideal, "Ideal command", "black"),
        (before, "Before feedback", "#4169e0"),
        (after, "After feedback", "#b12121"),
    ):
        intensity = (
            np.asarray(waveform.amplitude_rad_per_us) / OMEGA0
        ) ** 2
        axis.plot(times, intensity, label=label, color=color, lw=1.5)
    axis.set(xlabel="Time (μs)", ylabel="|Ω/Ω₀|²", title="AOM waveform")
    axis.legend(frameon=False, fontsize=8)

    axis = axes[0, 1]
    steps = [row["step"] for row in trajectory]
    errors = [row["observed_error"] for row in trajectory]
    sigmas = [row["uncertainty"] for row in trajectory]
    axis.errorbar(steps, errors, yerr=sigmas, marker="o", capsize=2)
    axis.set(
        xlabel="Accepted Hessian direction",
        ylabel="Finite-shot CZ error",
        title="Simulator-in-the-loop feedback",
    )

    axis = axes[1, 0]
    labels = [row["source"] for row in budget_rows]
    raw = [row["raw_contribution"] for row in budget_rows]
    post = [row["postselected_contribution"] for row in budget_rows]
    y = np.arange(len(labels))
    axis.barh(y + 0.18, raw, height=0.34, label="Raw")
    axis.barh(y - 0.18, post, height=0.34, label="Postselected")
    axis.set_yticks(y, labels)
    axis.set_xscale("log")
    axis.set(xlabel="Added gate error", title="Platform error ablation")
    axis.legend(frameon=False, fontsize=8)

    axis = axes[1, 1]
    linewidth = [row["linewidth_hz"] for row in linewidth_rows]
    raw_error = [row["total_raw_error"] for row in linewidth_rows]
    post_error = [row["total_postselected_error"] for row in linewidth_rows]
    axis.plot(linewidth, raw_error, "o-", label="Raw")
    axis.plot(linewidth, post_error, "s-", label="Postselected")
    axis.set_xscale("log")
    axis.set_yscale("log")
    axis.set(
        xlabel="Effective 302-nm linewidth (Hz)",
        ylabel="Total gate error",
        title="Linewidth sensitivity",
    )
    axis.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--theory-dir", type=Path, required=True)
    parser.add_argument("--paper-figure4", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start = time.perf_counter()
    theory = args.theory_dir.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    data_dir = output / "data"
    figs_dir = output / "figs"
    data_dir.mkdir(parents=True, exist_ok=True)
    figs_dir.mkdir(parents=True, exist_ok=True)

    progress("1/7 Load source-constrained AR waveform and ten Hessian modes")
    ideal_waveform, ideal_field = load_ideal_waveform(
        theory / "data" / "robust_waveform.npz"
    )
    with np.load(theory / "data" / "fig3_hessian_modes.npz") as archive:
        eigenvalues = np.asarray(archive["eigenvalues"], dtype=float)
        eigenvectors = np.asarray(archive["eigenvectors"], dtype=float)

    progress("2/7 Fit the platform AOM transfer to paper Figure 4a")
    bandwidth_mhz, gain, transfer_fit = fit_aom_transfer(
        ideal_waveform, args.paper_figure4.resolve()
    )
    before_waveform = apply_aom(ideal_waveform, bandwidth_mhz, gain)
    progress(
        f"  fitted f3dB={bandwidth_mhz:.3f} MHz, gain={gain:.5f}, "
        f"raster MSE={transfer_fit['objective_mse']:.3e}"
    )

    coherent_backend = QutipMultilevelBackend(yb_config(include_decay=False))
    open_backend = QutipMultilevelBackend(yb_config(include_decay=True))
    ideal_reference = evaluate_coherent_gate(
        coherent_backend,
        gate_program(ideal_waveform, "ideal-reference"),
    )
    target = ideal_reference.target
    before_coherent = evaluate_coherent_gate(
        coherent_backend,
        gate_program(before_waveform, "before-coherent"),
        target=target,
    )

    progress("3/7 Exact lifetime anchor and fixed hidden noise blocks")
    before_open = evaluate_open_system_gate(
        open_backend,
        gate_program(before_waveform, "before-open"),
        target=target,
    )
    irreversible_floor = max(
        0.0,
        (1.0 - before_open.raw_average_fidelity)
        - (1.0 - before_coherent.average_fidelity),
    )
    search_contexts = sample_contexts(
        before_waveform,
        linewidth_hz=1000.0,
        count=4,
        seed=SEED + 100,
    )

    progress("4/7 One-cycle finite-shot feedback over 10 Hessian directions")
    final_command_field, scan_rows, trajectory = run_closed_loop(
        ideal_field=ideal_field,
        ideal_waveform=ideal_waveform,
        eigenvectors=eigenvectors,
        eigenvalues=eigenvalues,
        bandwidth_mhz=bandwidth_mhz,
        gain=gain,
        target=target,
        irreversible_floor=irreversible_floor,
        contexts=search_contexts,
        backend=coherent_backend,
    )
    final_command = complex_to_waveform(
        final_command_field, ideal_waveform.dt_us
    )
    after_waveform = apply_aom(final_command, bandwidth_mhz, gain)

    progress("5/7 Exact final open-system anchor")
    after_coherent = evaluate_coherent_gate(
        coherent_backend,
        gate_program(after_waveform, "after-coherent"),
        target=target,
    )
    after_open = evaluate_open_system_gate(
        open_backend,
        gate_program(after_waveform, "after-open"),
        target=target,
    )

    progress("6/7 Noise ablations and linewidth scan")
    nominal_raw = 1.0 - after_coherent.average_fidelity
    nominal_conditional = nominal_raw
    noise_specs = (
        ("Doppler", dict(include_doppler=True, include_position=False, include_amplitude=False, include_phase=False)),
        ("Thermal position / varying blockade", dict(include_doppler=False, include_position=True, include_amplitude=False, include_phase=False)),
        ("Laser amplitude", dict(include_doppler=False, include_position=False, include_amplitude=True, include_phase=False)),
        ("Laser phase + 1 kHz linewidth", dict(include_doppler=False, include_position=False, include_amplitude=False, include_phase=True)),
        ("Combined stochastic", dict(include_doppler=True, include_position=True, include_amplitude=True, include_phase=True)),
    )
    budget_rows: list[dict[str, Any]] = [
        {
            "source": "Rydberg lifetime / erasure",
            "raw_contribution": max(
                1e-12,
                (1.0 - after_open.raw_average_fidelity) - nominal_raw,
            ),
            "postselected_contribution": max(
                1e-12,
                (1.0 - after_open.weighted_conditional_fidelity)
                - nominal_conditional,
            ),
            "parameter_source": "Liu: 42 us, 90% outside computational space",
        },
        {
            "source": "Finite blockade",
            "raw_contribution": 1.6e-4,
            "postselected_contribution": 3.0e-5,
            "parameter_source": "paper-calibrated effective B0; not independent",
        },
    ]
    combined = None
    for index, (label, switches) in enumerate(noise_specs):
        contexts = sample_contexts(
            after_waveform,
            linewidth_hz=1000.0,
            count=16,
            seed=SEED + 200 + index,
            **switches,
        )
        metrics = ensemble_metrics(
            coherent_backend, after_waveform, target, contexts
        )
        if label == "Combined stochastic":
            combined = metrics
            continue
        budget_rows.append(
            {
                "source": label,
                "raw_contribution": max(
                    1e-12, metrics["raw_infidelity"] - nominal_raw
                ),
                "postselected_contribution": max(
                    1e-12,
                    metrics["conditional_infidelity"] - nominal_conditional,
                ),
                "parameter_source": "Cold_Atom Gate Simu_Platform",
            }
        )
        progress(f"  {label}: Δ(1-F)={budget_rows[-1]['raw_contribution']:.3e}")
    assert combined is not None

    linewidth_rows = []
    lifetime_raw = max(
        0.0,
        (1.0 - after_open.raw_average_fidelity) - nominal_raw,
    )
    lifetime_post = max(
        0.0,
        (1.0 - after_open.weighted_conditional_fidelity)
        - nominal_conditional,
    )
    for index, linewidth in enumerate((100.0, 1000.0, 10000.0, 300000.0)):
        contexts = sample_contexts(
            after_waveform,
            linewidth_hz=linewidth,
            count=16,
            seed=SEED + 400 + index,
            include_doppler=True,
            include_position=True,
            include_amplitude=True,
            include_phase=True,
        )
        metrics = ensemble_metrics(
            coherent_backend, after_waveform, target, contexts
        )
        linewidth_rows.append(
            {
                "linewidth_hz": linewidth,
                "coherent_ensemble_raw_error": metrics["raw_infidelity"],
                "coherent_ensemble_postselected_error": metrics[
                    "conditional_infidelity"
                ],
                "total_raw_error": metrics["raw_infidelity"] + lifetime_raw,
                "total_postselected_error": (
                    metrics["conditional_infidelity"] + lifetime_post
                ),
                "contexts": 16,
            }
        )

    progress("7/7 Write digital-twin artifacts")
    elapsed = time.perf_counter() - start
    write_csv(data_dir / "closed_loop_scans.csv", scan_rows)
    write_csv(data_dir / "closed_loop_trajectory.csv", trajectory)
    write_csv(data_dir / "error_budget.csv", budget_rows)
    write_csv(data_dir / "linewidth_sweep.csv", linewidth_rows)
    np.savez_compressed(
        data_dir / "waveforms.npz",
        time_us=(np.arange(64) + 0.5) * ideal_waveform.dt_us,
        ideal=ideal_field,
        before=(
            np.asarray(before_waveform.amplitude_rad_per_us)
            * np.exp(1j * np.asarray(before_waveform.phase_rad))
        ),
        after=(
            np.asarray(after_waveform.amplitude_rad_per_us)
            * np.exp(1j * np.asarray(after_waveform.phase_rad))
        ),
        final_command=final_command_field,
    )
    make_summary_figure(
        figs_dir / "digital_twin_summary.png",
        ideal=ideal_waveform,
        before=before_waveform,
        after=after_waveform,
        trajectory=trajectory,
        budget_rows=budget_rows,
        linewidth_rows=linewidth_rows,
    )
    result = {
        "status": "success" if elapsed < 55 * 60 else "wall_budget_exceeded",
        "data_class": "simulator-generated digital-twin result",
        "elapsed_seconds": elapsed,
        "aom_fit": transfer_fit,
        "feedback": {
            "initial_observed_error": trajectory[0]["observed_error"],
            "final_observed_error": trajectory[-1]["observed_error"],
            "scan_queries": len(scan_rows),
            "effective_shots": len(scan_rows) * SHOT_COUNT,
        },
        "validator_only": {
            "before": {
                "coherent": {
                    "average_fidelity": before_coherent.average_fidelity,
                    "computational_return": before_coherent.computational_return,
                },
                "open": asdict(before_open),
            },
            "after": {
                "coherent": {
                    "average_fidelity": after_coherent.average_fidelity,
                    "computational_return": after_coherent.computational_return,
                },
                "open": asdict(after_open),
                "combined_stochastic": combined,
            },
        },
        "approximations": [
            "The online controller uses a four-context coherent ensemble plus a fixed exact lifetime floor.",
            "Finite shots are drawn after context averaging rather than repropagating every shot.",
            "Exact open-system metrics are computed only at initial and final points.",
            "The effective R^-6 interaction is calibrated to one paper error anchor.",
            "The AOM transfer is a first-order fit to rasterized Figure 4a data.",
        ],
    }
    write_json(data_dir / "result.json", result)
    progress(
        f"Complete in {elapsed:.1f} s: "
        f"{figs_dir / 'digital_twin_summary.png'}"
    )


if __name__ == "__main__":
    main()
