#!/usr/bin/env python3
"""Raw-data-only fitting pipelines for experimental Figs. 2--4.

The command never fabricates missing observations.  With no --input file it
writes the required column contracts and records the panels as unavailable.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit


CONTRACTS = {
    "fig2a_imaging": [
        "shot_id",
        "prepared_state",
        "first_image_photon_count",
        "second_image_photon_count",
        "state_assignment",
        "loss_assignment",
    ],
    "fig2b_single_qubit_rb": [
        "rb_depth",
        "sequence_id",
        "shot_id",
        "success",
        "survival",
        "postselection_flag",
    ],
    "fig3d_mode_sensitivity": [
        "mode",
        "coefficient",
        "rb_fidelity_or_error",
        "uncertainty",
        "theory_sensitivity",
    ],
    "fig3e_channel_decomposition": [
        "mode",
        "coefficient",
        "initial_computational_state",
        "leakage_channel",
        "measured_leakage",
        "leakage_uncertainty",
        "ramsey_phase",
        "ramsey_phase_uncertainty",
    ],
    "fig4a_waveforms": [
        "time_us",
        "ideal_amplitude",
        "before_amplitude",
        "after_amplitude",
        "ideal_intensity",
        "before_intensity",
        "after_intensity",
        "wrapped_phase",
        "unwrapped_phase",
        "measurement_uncertainty",
    ],
    "fig4b_closed_loop": [
        "cycle",
        "mode",
        "scan_coefficient",
        "gate_error",
        "uncertainty",
        "selected_optimum",
    ],
    "fig4c_echoed_rb": [
        "rb_circuit_depth",
        "sequence_id",
        "shot_id",
        "success",
        "loss",
        "postselection_flag",
    ],
    "fig4d_intensity": [
        "gate_type",
        "intensity_ratio",
        "gate_error",
        "uncertainty",
        "fidelity_convention",
    ],
    "fig4e_stability": [
        "elapsed_time",
        "gate_error",
        "uncertainty",
        "calibration_or_reoptimization_event",
    ],
    "fig4f_error_budget": [
        "noise_source",
        "raw_contribution",
        "postselected_contribution",
        "uncertainty",
        "parameter_source",
    ],
}

MICROSCOPIC_INPUT_CONTRACTS = {
    "pulse_waveform": [
        "time_us",
        "amplitude_rad_per_us",
        "phase_rad",
    ],
    "zeeman_calibration": [
        "state_label",
        "field_gauss",
        "shift_mhz",
        "uncertainty_mhz",
    ],
    "polarization_calibration": [
        "beam_id",
        "component",
        "relative_amplitude",
        "phase_rad",
        "uncertainty",
    ],
    "mqdt_pair_states": [
        "distance_um",
        "pair_state_id",
        "energy_mhz",
        "product_state",
        "overlap_real",
        "overlap_imag",
    ],
    "distance_samples": [
        "sample_id",
        "distance_um",
        "polar_angle_rad",
        "azimuth_rad",
    ],
    "decay_branching": [
        "initial_state",
        "final_state",
        "rate_per_us",
    ],
    "laser_phase_noise_psd": [
        "frequency_mhz",
        "psd_rad2_per_mhz",
    ],
    "laser_amplitude_noise_psd": [
        "frequency_mhz",
        "psd_fraction2_per_mhz",
    ],
}

STRING_COLUMNS = {
    "prepared_state",
    "state_assignment",
    "initial_computational_state",
    "leakage_channel",
    "gate_type",
    "fidelity_convention",
    "calibration_or_reoptimization_event",
    "noise_source",
    "parameter_source",
}

SYNTHETIC_LABEL = "SYNTHETIC TEST DATA — NOT EXPERIMENTAL"


def _required_object(parent: dict, key: str, location: str) -> dict:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{location}.{key} must be an object")
    return value


def _required_list(parent: dict, key: str, location: str) -> list:
    value = parent.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{location}.{key} must be a list")
    return value


def _validate_state_list(states: list, location: str) -> list[str]:
    labels = []
    for index, state in enumerate(states):
        item_location = f"{location}[{index}]"
        if not isinstance(state, dict):
            raise ValueError(f"{item_location} must be an object")
        label = state.get("label")
        if not isinstance(label, str) or not label:
            raise ValueError(f"{item_location}.label must be a non-empty string")
        labels.append(label)
    if len(labels) != len(set(labels)):
        raise ValueError(f"{location} state labels must be unique")
    return labels


def _validate_optional_positive(
    parent: dict, key: str, location: str
) -> None:
    value = parent.get(key)
    if value is not None and (
        not isinstance(value, (int, float)) or value <= 0.0
    ):
        raise ValueError(f"{location}.{key} must be positive or null")


def _validate_optional_vector3(
    parent: dict, key: str, location: str
) -> None:
    value = parent.get(key)
    if value is None:
        return
    if (
        not isinstance(value, list)
        or len(value) != 3
        or any(not isinstance(component, (int, float)) for component in value)
    ):
        raise ValueError(f"{location}.{key} must be a numeric 3-vector or null")


def _validate_microscopic_rows(
    rows: list, required: list[str], location: str
) -> int:
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"{location}.rows[{index}] must be an object")
        missing = [column for column in required if column not in row]
        if missing:
            raise ValueError(
                f"{location}.rows[{index}] is missing columns {missing}"
            )
    if not rows:
        raise ValueError(f"{location}.rows must not be empty when supplied")
    return len(rows)


def _validate_microscopic_csv(
    path: Path, required: list[str], location: str
) -> int:
    if not path.exists():
        raise FileNotFoundError(f"{location} CSV path does not exist: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        missing = [column for column in required if column not in columns]
        if missing:
            raise ValueError(f"{location} CSV is missing columns {missing}")
        row_count = sum(1 for _ in reader)
        if row_count == 0:
            raise ValueError(f"{location} CSV has no data rows")
        return row_count


def validate_physical_model(manifest: dict, manifest_path: Path) -> dict:
    """Validate and summarize optional full-physics inputs in schema v2.

    These inputs are provenance-bearing data contracts.  They are not silently
    consumed by the current ten-state perfect-blockade Hessian calculation.
    """
    physical = _required_object(manifest, "physical_model", "input.in")
    atom = _required_object(physical, "atom", "input.in.physical_model")
    qubit_labels = _validate_state_list(
        _required_list(atom, "qubit_states", "input.in.physical_model.atom"),
        "input.in.physical_model.atom.qubit_states",
    )
    intermediate_labels = _validate_state_list(
        _required_list(
            atom, "intermediate_states", "input.in.physical_model.atom"
        ),
        "input.in.physical_model.atom.intermediate_states",
    )
    rydberg_labels = _validate_state_list(
        _required_list(atom, "rydberg_states", "input.in.physical_model.atom"),
        "input.in.physical_model.atom.rydberg_states",
    )

    beams = _required_list(
        physical, "laser_beams", "input.in.physical_model"
    )
    beam_ids = []
    for index, beam in enumerate(beams):
        location = f"input.in.physical_model.laser_beams[{index}]"
        if not isinstance(beam, dict):
            raise ValueError(f"{location} must be an object")
        beam_id = beam.get("id")
        if not isinstance(beam_id, str) or not beam_id:
            raise ValueError(f"{location}.id must be a non-empty string")
        beam_ids.append(beam_id)
        _validate_optional_positive(beam, "wavelength_nm", location)
        _validate_optional_vector3(
            beam, "propagation_direction_lab", location
        )
    if len(beam_ids) != len(set(beam_ids)):
        raise ValueError("input.in physical-model laser beam ids must be unique")

    field = _required_object(
        physical, "magnetic_field", "input.in.physical_model"
    )
    _validate_optional_positive(
        field,
        "rydberg_zeeman_splitting_mhz",
        "input.in.physical_model.magnetic_field",
    )
    _validate_optional_vector3(
        field, "direction_lab", "input.in.physical_model.magnetic_field"
    )
    geometry = _required_object(
        physical, "geometry", "input.in.physical_model"
    )
    _validate_optional_positive(
        geometry, "dimer_distance_um", "input.in.physical_model.geometry"
    )
    _validate_optional_vector3(
        geometry, "dimer_axis_lab", "input.in.physical_model.geometry"
    )

    supplied = _required_object(
        physical, "microscopic_inputs", "input.in.physical_model"
    )
    unknown = sorted(set(supplied) - set(MICROSCOPIC_INPUT_CONTRACTS))
    if unknown:
        raise ValueError(f"unknown microscopic input slots: {unknown}")

    inputs = {}
    for name, required in MICROSCOPIC_INPUT_CONTRACTS.items():
        entry = supplied.get(name, {"source": "unavailable"})
        if not isinstance(entry, dict):
            raise ValueError(f"microscopic input {name} must be an object")
        source = entry.get("source", "unavailable")
        location = f"input.in.physical_model.microscopic_inputs.{name}"
        if source == "unavailable":
            row_count = 0
            resolved_path = None
        elif source == "inline":
            rows = entry.get("rows")
            if not isinstance(rows, list):
                raise ValueError(f"{location} inline source needs rows")
            row_count = _validate_microscopic_rows(rows, required, location)
            resolved_path = None
        elif source == "csv":
            relative = entry.get("path")
            if not isinstance(relative, str) or not relative:
                raise ValueError(f"{location} CSV source needs a path")
            path = (manifest_path.parent / relative).resolve()
            row_count = _validate_microscopic_csv(path, required, location)
            resolved_path = str(path)
        else:
            raise ValueError(
                f"{location}.source must be unavailable, inline, or csv"
            )
        inputs[name] = {
            "source": source,
            "status": "supplied" if source != "unavailable" else "unavailable",
            "rows": row_count,
            "path": resolved_path,
            "required_columns": required,
            "provenance": entry.get("provenance", "not supplied"),
            "consumed_by_current_hessian": False,
        }

    return {
        "status": "physical-model input contract validated",
        "provenance": physical.get("provenance", "mixed"),
        "atom": {
            "isotope": atom.get("isotope"),
            "qubit_states": atom["qubit_states"],
            "intermediate_states": atom["intermediate_states"],
            "rydberg_states": atom["rydberg_states"],
            "state_labels": {
                "qubit": qubit_labels,
                "intermediate": intermediate_labels,
                "rydberg": rydberg_labels,
            },
        },
        "laser_beams": beams,
        "laser_beam_ids": beam_ids,
        "magnetic_field": field,
        "geometry": geometry,
        "microscopic_inputs": inputs,
        "supplied_input_count": sum(
            item["status"] == "supplied" for item in inputs.values()
        ),
        "missing_input_count": sum(
            item["status"] == "unavailable" for item in inputs.values()
        ),
        "current_hessian_model": (
            "ten-state perfect-blockade model configured separately; "
            "physical_model inputs are audited but not silently consumed"
        ),
    }


def rb_model(length: np.ndarray, amplitude: float, decay: float, offset: float):
    return amplitude * decay**length + offset


def fit_rb(table: dict[str, np.ndarray]) -> dict:
    sigma = table.get("survival_sigma")
    parameters, covariance = curve_fit(
        rb_model,
        table["sequence_length"],
        table["survival"],
        sigma=sigma,
        absolute_sigma=sigma is not None,
        p0=(0.5, 0.99, 0.5),
        bounds=([-1.0, 0.0, -1.0], [2.0, 1.0, 2.0]),
    )
    return {
        "amplitude": float(parameters[0]),
        "decay": float(parameters[1]),
        "offset": float(parameters[2]),
        "covariance": covariance.tolist(),
    }


def fit_mode_sensitivity(table: dict[str, np.ndarray]) -> dict:
    results = {}
    for mode in np.unique(table["mode"]):
        selected = table["mode"] == mode
        coefficients = table["coefficient"][selected]
        infidelity = table["rb_fidelity_or_error"][selected]
        sigma = table.get("uncertainty")
        weights = None if sigma is None else 1.0 / sigma[selected]
        quadratic = np.polyfit(coefficients, infidelity, 2, w=weights)
        results[str(mode)] = {
            "curvature_lambda": float(2.0 * quadratic[0]),
            "linear": float(quadratic[1]),
            "offset": float(quadratic[2]),
            "optimum": float(-quadratic[1] / (2.0 * quadratic[0])),
        }
    return results


def fit_intensity_power(table: dict[str, np.ndarray]) -> dict:
    results = {}
    keys = np.unique(
        np.char.add(
            np.char.add(table["gate_type"].astype(str), "::"),
            table["fidelity_convention"].astype(str),
        )
    )
    combined = np.char.add(
        np.char.add(table["gate_type"].astype(str), "::"),
        table["fidelity_convention"].astype(str),
    )
    for gate in keys:
        selected = combined == gate
        delta = abs(table["intensity_ratio"][selected] - 1.0)
        error = table["gate_error"][selected]
        baseline = float(np.min(error))
        excess = error - baseline
        results[str(gate)] = {"baseline": baseline, "directions": {}}
        for name, sign in (("negative", -1), ("positive", 1)):
            signed_delta = table["intensity_ratio"][selected] - 1.0
            valid = (
                (np.sign(signed_delta) == sign)
                & (delta > 0.0)
                & (excess > 0.0)
            )
            if np.count_nonzero(valid) < 3:
                results[str(gate)]["directions"][name] = {
                    "status": "insufficient points"
                }
                continue
            slope, intercept = np.polyfit(
                np.log(delta[valid]), np.log(excess[valid]), 1
            )
            results[str(gate)]["directions"][name] = {
                "power": float(slope),
                "prefactor": float(np.exp(intercept)),
                "model": "excess error=A*|delta_I|^p",
            }
    return results


def fit_closed_loop(table: dict[str, np.ndarray]) -> dict:
    results = {}
    for cycle in np.unique(table["cycle"]):
        for mode in np.unique(table["mode"][table["cycle"] == cycle]):
            selected = (table["cycle"] == cycle) & (table["mode"] == mode)
            x = table["scan_coefficient"][selected]
            y = table["gate_error"][selected]
            sigma = table["uncertainty"][selected]
            polynomial, covariance = np.polyfit(
                x, y, 2, w=1.0 / sigma, cov=True
            )
            optimum = (
                float(-polynomial[1] / (2.0 * polynomial[0]))
                if polynomial[0] > 0.0
                else np.nan
            )
            results[f"cycle_{int(cycle)}_mode_{int(mode)}"] = {
                "curvature": float(2.0 * polynomial[0]),
                "optimum": optimum,
                "covariance": covariance.tolist(),
                "selected_optimum_rows": int(
                    np.count_nonzero(table["selected_optimum"][selected])
                ),
            }
    return results


def aggregate_rb_shots(
    table: dict[str, np.ndarray], depth_column: str
) -> dict:
    depths = np.unique(table[depth_column])
    rows = []
    for depth in depths:
        selected = table[depth_column] == depth
        success = table["success"][selected].astype(float)
        if "postselection_flag" in table:
            selected_success = success[
                table["postselection_flag"][selected].astype(bool)
            ]
        else:
            selected_success = success
        rows.append(
            {
                "depth": float(depth),
                "shots": int(len(success)),
                "postselected_shots": int(len(selected_success)),
                "success_probability": float(np.mean(selected_success)),
                "binomial_sigma": float(
                    np.sqrt(
                        np.mean(selected_success)
                        * (1.0 - np.mean(selected_success))
                        / len(selected_success)
                    )
                ),
            }
        )
    fit_table = {
        "sequence_length": np.asarray([row["depth"] for row in rows]),
        "survival": np.asarray([row["success_probability"] for row in rows]),
        "survival_sigma": np.asarray(
            [max(row["binomial_sigma"], 1e-12) for row in rows]
        ),
    }
    return {"aggregated": rows, "fit": fit_rb(fit_table)}


def summarize_imaging(table: dict[str, np.ndarray]) -> dict:
    return {
        "shots": int(len(np.unique(table["shot_id"]))),
        "prepared_states": table["prepared_state"].astype(str).tolist(),
        "loss_fraction": float(
            np.mean(table["loss_assignment"].astype(float))
        ),
        "photon_count_quantiles": {
            "first_image": np.quantile(
                table["first_image_photon_count"], [0.05, 0.5, 0.95]
            ).tolist(),
            "second_image": np.quantile(
                table["second_image_photon_count"], [0.05, 0.5, 0.95]
            ).tolist(),
        }
    }


def _table_from_rows(
    rows: list[dict[str, object]], required: list[str], source: str
) -> dict[str, np.ndarray]:
    if not rows:
        raise ValueError(f"{source} has no observations")
    missing = [column for column in required if column not in rows[0]]
    if missing:
        raise ValueError(f"{source} is missing columns: {missing}")
    table = {}
    for column in required:
        values = [row[column] for row in rows]
        if column in STRING_COLUMNS:
            table[column] = np.asarray([str(value) for value in values], dtype=str)
            continue
        if column in {
            "success",
            "survival",
            "postselection_flag",
            "loss",
            "loss_assignment",
            "selected_optimum",
        }:
            normalized = [str(value).strip().lower() for value in values]
            if all(
                value in {"0", "1", "false", "true", "no", "yes"}
                for value in normalized
            ):
                table[column] = np.asarray(
                    [value in {"1", "true", "yes"} for value in normalized],
                    dtype=bool,
                )
                continue
        try:
            table[column] = np.asarray(values, dtype=float)
        except (TypeError, ValueError):
            table[column] = np.asarray(values, dtype=str)
    return table


def read_table(path: Path, required: list[str]) -> dict[str, np.ndarray]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return _table_from_rows(rows, required, str(path))


def fit_panel(panel: str, table: dict[str, np.ndarray]) -> dict:
    """Run only the fit appropriate to one experimental panel."""
    if panel == "fig2a_imaging":
        return summarize_imaging(table)
    if panel in {"fig2b_single_qubit_rb", "fig4c_echoed_rb"}:
        depth = (
            "rb_depth"
            if panel == "fig2b_single_qubit_rb"
            else "rb_circuit_depth"
        )
        return aggregate_rb_shots(table, depth)
    if panel == "fig3d_mode_sensitivity":
        return fit_mode_sensitivity(table)
    if panel == "fig3e_channel_decomposition":
        return {
            "rows": int(len(table["mode"])),
            "weighted_mean_leakage": float(
                np.average(
                    table["measured_leakage"],
                    weights=1.0 / table["leakage_uncertainty"] ** 2,
                )
            ),
            "weighted_mean_ramsey_phase": float(
                np.average(
                    table["ramsey_phase"],
                    weights=1.0 / table["ramsey_phase_uncertainty"] ** 2,
                )
            ),
        }
    if panel == "fig4b_closed_loop":
        return fit_closed_loop(table)
    if panel == "fig4d_intensity":
        return fit_intensity_power(table)
    if panel == "fig4e_stability":
        weights = 1.0 / table["uncertainty"] ** 2
        return {
            "weighted_mean_gate_error": float(
                np.average(table["gate_error"], weights=weights)
            ),
            "events": table[
                "calibration_or_reoptimization_event"
            ].astype(str).tolist(),
        }
    if panel in {"fig4a_waveforms", "fig4f_error_budget"}:
        return {
            "rows": int(len(next(iter(table.values())))),
            "note": "validated raw-data table; no generic cross-panel fit",
        }
    raise ValueError(f"unknown panel {panel!r}")


def _finish_plot(
    fig: plt.Figure, path: Path, provenance: str
) -> str:
    label = (
        SYNTHETIC_LABEL
        if provenance == "synthetic demonstration"
        else provenance.upper()
    )
    fig.suptitle(label, color="firebrick", fontsize=11, fontweight="bold")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.94))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return str(path.resolve())


def _plot_rb(
    panel: str,
    table: dict[str, np.ndarray],
    fit: dict,
    provenance: str,
    path: Path,
) -> str:
    depth_column = (
        "rb_depth"
        if panel == "fig2b_single_qubit_rb"
        else "rb_circuit_depth"
    )
    aggregated = fit["aggregated"]
    x = np.asarray([row["depth"] for row in aggregated])
    y = np.asarray([row["success_probability"] for row in aggregated])
    sigma = np.asarray([row["binomial_sigma"] for row in aggregated])
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    ax.errorbar(x, y, yerr=sigma, fmt="o", capsize=3, label="test shots")
    parameters = fit["fit"]
    dense = np.linspace(float(np.min(x)), float(np.max(x)), 300)
    ax.plot(
        dense,
        rb_model(
            dense,
            parameters["amplitude"],
            parameters["decay"],
            parameters["offset"],
        ),
        label=f"RB fit, decay={parameters['decay']:.4f}",
    )
    ax.set(
        xlabel="RB circuit depth",
        ylabel="postselected success probability",
        ylim=(-0.08, 1.08),
        title="Fig. 2(b) test pipeline"
        if panel == "fig2b_single_qubit_rb"
        else "Fig. 4(c) test pipeline",
    )
    ax.grid(alpha=0.25)
    ax.legend()
    return _finish_plot(fig, path, provenance)


def plot_panel(
    panel: str,
    table: dict[str, np.ndarray],
    fit: dict,
    provenance: str,
    path: Path,
) -> str:
    """Render one input.in panel without changing or inventing observations."""
    if panel == "fig2a_imaging":
        states = np.unique(table["prepared_state"].astype(str))
        fig, axes = plt.subplots(
            1, len(states), figsize=(5.0 * len(states), 4.5),
            sharex=True, sharey=True
        )
        axes = np.atleast_1d(axes)
        colors = {"0": "tab:blue", "1": "tab:green", "loss": "0.6"}
        for ax, state in zip(axes, states):
            selected = table["prepared_state"].astype(str) == state
            assignments = table["state_assignment"][selected].astype(str)
            for assignment in np.unique(assignments):
                assigned = assignments == assignment
                ax.scatter(
                    table["first_image_photon_count"][selected][assigned],
                    table["second_image_photon_count"][selected][assigned],
                    s=36,
                    alpha=0.75,
                    color=colors.get(assignment, "tab:orange"),
                    label=f"assigned {assignment}",
                )
            ax.set(
                title=f"Prepare |{state}⟩",
                xlabel="counts, first image",
            )
            ax.grid(alpha=0.25)
            ax.legend(fontsize=8)
        axes[0].set_ylabel("counts, second image")
        return _finish_plot(fig, path, provenance)

    if panel in {"fig2b_single_qubit_rb", "fig4c_echoed_rb"}:
        return _plot_rb(panel, table, fit, provenance, path)

    if panel == "fig3d_mode_sensitivity":
        fig, ax = plt.subplots(figsize=(6.2, 4.3))
        for mode in np.unique(table["mode"]):
            selected = table["mode"] == mode
            x = table["coefficient"][selected]
            y = table["rb_fidelity_or_error"][selected]
            sigma = table["uncertainty"][selected]
            order = np.argsort(x)
            key = str(mode)
            if key not in fit:
                key = str(float(mode))
            values = fit[key]
            dense = np.linspace(float(np.min(x)), float(np.max(x)), 200)
            curve = (
                0.5 * values["curvature_lambda"] * dense**2
                + values["linear"] * dense
                + values["offset"]
            )
            label = f"mode {int(mode)}"
            ax.errorbar(x[order], y[order], yerr=sigma[order], fmt="o",
                        capsize=3, label=label)
            ax.plot(dense, curve, alpha=0.8)
        ax.set(
            xlabel="principal-mode coefficient",
            ylabel="RB gate error",
            title="Fig. 3(d) Hessian-mode scan test",
        )
        ax.grid(alpha=0.25)
        ax.legend()
        return _finish_plot(fig, path, provenance)

    if panel == "fig3e_channel_decomposition":
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.0, 6.2),
                                       sharex=True)
        labels = table["leakage_channel"].astype(str)
        positions = np.arange(len(labels))
        ax1.bar(positions, table["measured_leakage"],
                yerr=table["leakage_uncertainty"], capsize=3)
        ax1.set(ylabel="measured leakage",
                title="Fig. 3(e) channel-decomposition test")
        ax2.errorbar(
            positions,
            table["ramsey_phase"],
            yerr=table["ramsey_phase_uncertainty"],
            fmt="o",
            capsize=3,
        )
        ax2.axhline(0.0, color="0.5", linewidth=1)
        ax2.set(ylabel="Ramsey phase (rad)", xlabel="leakage channel")
        ax2.set_xticks(positions, labels, rotation=20, ha="right")
        ax1.grid(axis="y", alpha=0.25)
        ax2.grid(axis="y", alpha=0.25)
        return _finish_plot(fig, path, provenance)

    if panel == "fig4a_waveforms":
        order = np.argsort(table["time_us"])
        t = table["time_us"][order]
        fig, axes = plt.subplots(3, 1, figsize=(7.0, 7.0), sharex=True)
        for prefix, label in (
            ("ideal", "Ideal"),
            ("before", "Before"),
            ("after", "After"),
        ):
            axes[0].plot(t, table[f"{prefix}_amplitude"][order], "o-",
                         label=label)
            axes[1].plot(t, table[f"{prefix}_intensity"][order], "o-",
                         label=label)
        axes[2].plot(t, table["wrapped_phase"][order], "o-",
                     label="wrapped")
        axes[2].plot(t, table["unwrapped_phase"][order], "s--",
                     label="unwrapped")
        axes[0].set(title="Fig. 4(a) waveform test", ylabel="amplitude")
        axes[1].set(ylabel="intensity")
        axes[2].set(ylabel="phase (rad)", xlabel="time (μs)")
        for ax in axes:
            ax.grid(alpha=0.25)
            ax.legend(ncol=3, fontsize=8)
        return _finish_plot(fig, path, provenance)

    if panel == "fig4b_closed_loop":
        fig, ax = plt.subplots(figsize=(6.2, 4.3))
        for cycle in np.unique(table["cycle"]):
            for mode in np.unique(table["mode"][table["cycle"] == cycle]):
                selected = (table["cycle"] == cycle) & (
                    table["mode"] == mode
                )
                x = table["scan_coefficient"][selected]
                y = table["gate_error"][selected]
                sigma = table["uncertainty"][selected]
                order = np.argsort(x)
                key = f"cycle_{int(cycle)}_mode_{int(mode)}"
                values = fit[key]
                polynomial = np.polyfit(x, y, 2, w=1.0 / sigma)
                dense = np.linspace(float(np.min(x)), float(np.max(x)), 200)
                label = f"cycle {int(cycle)}, mode {int(mode)}"
                ax.errorbar(x[order], y[order], yerr=sigma[order], fmt="o",
                            capsize=3, label=label)
                ax.plot(dense, np.polyval(polynomial, dense))
                if np.isfinite(values["optimum"]):
                    ax.axvline(values["optimum"], color="0.4",
                               linestyle=":", linewidth=1)
        ax.set(
            xlabel="scan coefficient",
            ylabel="gate error",
            title="Fig. 4(b) closed-loop scan test",
        )
        ax.grid(alpha=0.25)
        ax.legend()
        return _finish_plot(fig, path, provenance)

    if panel == "fig4d_intensity":
        fig, ax = plt.subplots(figsize=(6.6, 4.5))
        for gate in np.unique(table["gate_type"]):
            selected = table["gate_type"] == gate
            order = np.argsort(table["intensity_ratio"][selected])
            x = table["intensity_ratio"][selected][order]
            y = table["gate_error"][selected][order]
            sigma = table["uncertainty"][selected][order]
            label = "AR" if gate == "AR" else "same-duration surrogate"
            ax.errorbar(x, y, yerr=sigma, fmt="o-", capsize=3,
                        label=label)
        ax.set(
            xlabel="intensity ratio I/I₀",
            ylabel="gate error",
            title="Fig. 4(d) intensity-robustness test",
        )
        ax.grid(alpha=0.25)
        ax.legend()
        return _finish_plot(fig, path, provenance)

    if panel == "fig4e_stability":
        order = np.argsort(table["elapsed_time"])
        fig, ax = plt.subplots(figsize=(6.4, 4.3))
        ax.errorbar(
            table["elapsed_time"][order],
            table["gate_error"][order],
            yerr=table["uncertainty"][order],
            fmt="o-",
            capsize=3,
        )
        for x, y, event in zip(
            table["elapsed_time"][order],
            table["gate_error"][order],
            table["calibration_or_reoptimization_event"][order],
        ):
            if str(event) != "none":
                ax.annotate(str(event), (x, y), xytext=(4, 7),
                            textcoords="offset points", fontsize=8)
        ax.set(
            xlabel="elapsed time",
            ylabel="gate error",
            title="Fig. 4(e) stability test",
        )
        ax.grid(alpha=0.25)
        return _finish_plot(fig, path, provenance)

    if panel == "fig4f_error_budget":
        labels = table["noise_source"].astype(str)
        positions = np.arange(len(labels))
        width = 0.36
        fig, ax = plt.subplots(figsize=(6.8, 4.5))
        ax.bar(
            positions - width / 2,
            table["raw_contribution"],
            width,
            yerr=table["uncertainty"],
            capsize=3,
            label="raw",
        )
        postselected = table["postselected_contribution"]
        reported = np.isfinite(postselected)
        ax.bar(
            positions[reported] + width / 2,
            postselected[reported],
            width,
            yerr=table["uncertainty"][reported],
            capsize=3,
            label="postselected",
        )
        ax.set_xticks(positions, labels, rotation=20, ha="right")
        ax.set(
            ylabel="gate-error contribution",
            title="Fig. 4(f) error-budget test",
        )
        ax.grid(axis="y", alpha=0.25)
        ax.legend()
        return _finish_plot(fig, path, provenance)

    raise ValueError(f"no plot implementation for panel {panel!r}")


def plot_manifest_overview(
    panel_paths: dict[str, str], path: Path, provenance: str
) -> str:
    fig, axes = plt.subplots(5, 2, figsize=(14, 22))
    for ax, panel in zip(axes.flat, CONTRACTS):
        image = plt.imread(panel_paths[panel])
        ax.imshow(image)
        ax.set_title(panel, fontsize=9)
        ax.axis("off")
    return _finish_plot(fig, path, provenance)


def _image_panel(ax: plt.Axes, image_path: str, letter: str) -> None:
    ax.imshow(plt.imread(image_path))
    ax.axis("off")
    ax.text(
        0.0, 1.0, letter, transform=ax.transAxes, fontsize=16,
        fontweight="bold", va="top", ha="left"
    )


def _save_layout_figure(fig: plt.Figure, path: Path, title: str) -> str:
    fig.suptitle(title, fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.965))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return str(path.resolve())


def plot_figure2_paper_layout(
    panel_paths: dict[str, str], path: Path
) -> str:
    """Match the paper's Figure 2 grouping: panel a above panel b."""
    fig = plt.figure(figsize=(10.0, 12.0))
    grid = fig.add_gridspec(2, 1, height_ratios=(1.0, 1.0))
    top = fig.add_subplot(grid[0, 0])
    bottom = fig.add_subplot(grid[1, 0])
    _image_panel(top, panel_paths["fig2a_imaging"], "a")
    _image_panel(bottom, panel_paths["fig2b_single_qubit_rb"], "b")
    return _save_layout_figure(
        fig,
        path,
        "Figure 2 paper layout — SYNTHETIC TEST DATA, NOT EXPERIMENTAL",
    )


def _theory_csv_path(theory_run_dir: Path, name: str) -> Path:
    direct = theory_run_dir / name
    nested = theory_run_dir / "data" / name
    path = nested if nested.exists() else direct
    if not path.exists():
        raise FileNotFoundError(
            f"Figure 3 layout needs theory data file {name}: {path}"
        )
    return path


def _read_csv_columns(path: Path) -> dict[str, np.ndarray]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"theory CSV has no rows: {path}")
    result: dict[str, np.ndarray] = {}
    for column in rows[0]:
        values = [row[column] for row in rows]
        try:
            result[column] = np.asarray(values, dtype=float)
        except ValueError:
            result[column] = np.asarray(values, dtype=str)
    return result


def _panel_letter(
    ax: plt.Axes, letter: str, provenance: str, color: str = "black"
) -> None:
    ax.text(
        -0.12, 1.08, letter, transform=ax.transAxes, fontsize=15,
        fontweight="bold", va="top"
    )
    ax.text(
        0.0, 1.04, provenance, transform=ax.transAxes, fontsize=7,
        color=color, va="bottom"
    )


def plot_figure3_paper_layout(
    tables: dict[str, dict[str, np.ndarray]],
    fits: dict[str, dict],
    theory_run_dir: Path,
    path: Path,
) -> str:
    """Match Figure 3: a,b,c on top and d,e on the bottom."""
    waveform = _read_csv_columns(
        _theory_csv_path(theory_run_dir, "fig3_waveform_populations.csv")
    )
    spectrum = _read_csv_columns(
        _theory_csv_path(theory_run_dir, "fig3_hessian_spectrum.csv")
    )
    fig = plt.figure(figsize=(15.5, 8.5))
    grid = fig.add_gridspec(2, 6, height_ratios=(1.0, 1.25))

    axa = fig.add_subplot(grid[0, 0:2])
    energy_0 = 0.12
    energy_1 = 0.17
    energy_r = 0.78
    energy_rprime = 0.86
    axa.plot([0.12, 0.38], [energy_0, energy_0],
             color="purple", linewidth=2)
    axa.plot([0.62, 0.88], [energy_1, energy_1],
             color="purple", linewidth=2)
    axa.plot([0.12, 0.38], [energy_r, energy_r],
             color="purple", linewidth=2)
    axa.plot([0.62, 0.88], [energy_rprime, energy_rprime],
             color="purple", linewidth=2)
    axa.annotate("", xy=(0.25, energy_r - 0.015),
                 xytext=(0.75, energy_1 + 0.025),
                 arrowprops={"arrowstyle": "->", "color": "purple",
                             "linewidth": 2})
    axa.annotate("", xy=(0.75, energy_rprime - 0.015),
                 xytext=(0.25, energy_0 + 0.025),
                 arrowprops={"arrowstyle": "->", "color": "plum",
                             "linewidth": 2})
    axa.plot([0.94, 0.94], [energy_r, energy_rprime],
             color="black", linewidth=1)
    axa.plot([0.925, 0.955], [energy_r, energy_r],
             color="black", linewidth=1)
    axa.plot([0.925, 0.955], [energy_rprime, energy_rprime],
             color="black", linewidth=1)
    axa.plot([0.48, 0.48], [energy_0, energy_1],
             color="black", linewidth=1)
    axa.plot([0.465, 0.495], [energy_0, energy_0],
             color="black", linewidth=1)
    axa.plot([0.465, 0.495], [energy_1, energy_1],
             color="black", linewidth=1)
    axa.text(0.20, energy_0 - 0.08, "|0⟩")
    axa.text(0.70, energy_1 - 0.08, "|1⟩")
    axa.text(0.20, energy_r + 0.025, "|r⟩")
    axa.text(0.70, energy_rprime + 0.025, "|r′⟩")
    axa.text(0.50, 0.45, "Ω", color="purple", fontsize=13)
    axa.text(0.955, 0.5 * (energy_r + energy_rprime), "Δᵣ",
             va="center")
    axa.text(0.495, 0.5 * (energy_0 + energy_1), "Δq",
             va="center")
    axa.text(0.50, 0.01, "energy gaps schematic, not to scale",
             ha="center", fontsize=7, color="0.35")
    axa.set(xlim=(0, 1), ylim=(0, 1), title="Four-level model")
    axa.axis("off")
    _panel_letter(axa, "a", "exact analytic model")

    bgrid = grid[0, 2:4].subgridspec(2, 1, hspace=0.12)
    axb1 = fig.add_subplot(bgrid[0, 0])
    axb2 = fig.add_subplot(bgrid[1, 0], sharex=axb1)
    axb1.plot(waveform["time_us"], waveform["intensity_ratio"])
    axb2.plot(waveform["time_us"], waveform["phase_unwrapped_turns"])
    axb1.set(ylabel="|Ω/Ω₀|²", title="AR waveform")
    axb2.set(ylabel="φ/(2π)", xlabel="time (μs)")
    axb1.tick_params(labelbottom=False)
    axb1.grid(alpha=0.2)
    axb2.grid(alpha=0.2)
    _panel_letter(
        axb1, "b", "equivalent numerical reoptimization", "darkorange"
    )

    axc = fig.add_subplot(grid[0, 4:6])
    axc.plot(waveform["time_us"], waveform["P00_total_rydberg"],
             label="|00⟩")
    axc.plot(waveform["time_us"], waveform["P01_total_rydberg"],
             label="|01⟩")
    axc.plot(waveform["time_us"], waveform["P11_total_rydberg"],
             label="|11⟩")
    axc.set(
        xlabel="time (μs)", ylabel="Rydberg population",
        title="State populations"
    )
    axc.grid(alpha=0.2)
    axc.legend(fontsize=8)
    _panel_letter(
        axc, "c", "equivalent numerical reoptimization", "darkorange"
    )

    axd = fig.add_subplot(grid[1, 0:3])
    physical = spectrum["mode"] <= 10
    null = spectrum["mode"] > 10
    axd.semilogy(
        spectrum["mode"][physical], spectrum["eigenvalue"][physical],
        "s", markerfacecolor="none", label="calculated principal"
    )
    axd.semilogy(
        spectrum["mode"][null],
        np.abs(spectrum["eigenvalue"][null]),
        "D", markerfacecolor="none", label="calculated numerical null"
    )
    mode_fit = fits["fig3d_mode_sensitivity"]
    measured_modes = np.asarray([float(key) for key in mode_fit])
    measured = np.asarray(
        [mode_fit[key]["curvature_lambda"] for key in mode_fit]
    )
    axd.semilogy(
        measured_modes, measured, "o", label="synthetic measured test"
    )
    axd.set(
        xlabel="Hessian mode i", ylabel="sensitivity λᵢ",
        title="Sensitivity spectrum"
    )
    axd.grid(alpha=0.2, which="both")
    axd.legend(fontsize=8)
    _panel_letter(
        axd, "d", "theory + synthetic input test", "firebrick"
    )

    axe = fig.add_subplot(grid[1, 3:6])
    first_ten = spectrum["mode"] <= 10
    modes = spectrum["mode"][first_ten]
    bottom = np.zeros_like(modes)
    for column, label, color in (
        ("alpha00", "α₀₀", "tab:blue"),
        ("alpha01", "α₀₁", "tab:orange"),
        ("alpha11", "α₁₁", "tab:green"),
        ("theta", "θ", "tab:purple"),
    ):
        values = spectrum[column][first_ten]
        axe.bar(modes, values, bottom=bottom, label=label, color=color)
        bottom += values
    axe.set(
        xlabel="Hessian mode i", ylabel="calculated contribution",
        title="Error-channel decomposition"
    )
    axe.grid(axis="y", alpha=0.2)
    axe.legend(fontsize=8, ncol=2)
    _panel_letter(
        axe, "e", "equivalent numerical reoptimization", "darkorange"
    )

    return _save_layout_figure(
        fig,
        path,
        "Figure 3 paper layout — panel-level provenance shown",
    )


def plot_figure4_paper_layout(
    panel_paths: dict[str, str], path: Path
) -> str:
    """Match the paper's Figure 4 grouping: a,b,c / d,e,f."""
    panels = (
        "fig4a_waveforms",
        "fig4b_closed_loop",
        "fig4c_echoed_rb",
        "fig4d_intensity",
        "fig4e_stability",
        "fig4f_error_budget",
    )
    fig, axes = plt.subplots(2, 3, figsize=(18.0, 11.0))
    for ax, panel, letter in zip(axes.flat, panels, "abcdef"):
        _image_panel(ax, panel_paths[panel], letter)
    return _save_layout_figure(
        fig,
        path,
        "Figure 4 paper layout — SYNTHETIC TEST DATA, NOT EXPERIMENTAL",
    )


def plot_paper_layout_figures(
    tables: dict[str, dict[str, np.ndarray]],
    fits: dict[str, dict],
    panel_paths: dict[str, str],
    plot_dir: Path,
    theory_run_dir: Path | None,
) -> dict[str, str]:
    figures = {
        "figure2": plot_figure2_paper_layout(
            panel_paths, plot_dir / "figure2_paper_layout_synthetic.png"
        ),
        "figure4": plot_figure4_paper_layout(
            panel_paths, plot_dir / "figure4_paper_layout_synthetic.png"
        ),
    }
    if theory_run_dir is not None:
        figures["figure3"] = plot_figure3_paper_layout(
            tables,
            fits,
            theory_run_dir,
            plot_dir / "figure3_paper_layout_mixed_provenance.png",
        )
    return figures


def _unavailable_result(panel: str) -> dict:
    return {
        "status": "unavailable without supplied input data",
        "provenance": "unavailable",
        "panel": panel,
        "required_columns": CONTRACTS[panel],
        "synthetic_points_generated": False,
    }


def load_manifest(path: Path) -> dict:
    """Load the user-editable JSON manifest stored in input.in."""
    with path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict) or not isinstance(
        manifest.get("panels"), dict
    ):
        raise ValueError("input.in must contain a panels mapping")
    schema_version = manifest.get("schema_version")
    if schema_version not in (1, 2):
        raise ValueError("input.in schema_version must be 1 or 2")
    if schema_version == 2:
        validate_physical_model(manifest, path)
    return manifest


def run_manifest(
    manifest_path: Path,
    output_dir: Path,
    plot_dir: Path | None = None,
    theory_run_dir: Path | None = None,
) -> dict:
    """Analyze every panel named by input.in and write one result per panel."""
    manifest = load_manifest(manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    physical_model = (
        validate_physical_model(manifest, manifest_path)
        if manifest["schema_version"] == 2
        else {
            "status": "not present in legacy schema v1",
            "supplied_input_count": 0,
            "missing_input_count": len(MICROSCOPIC_INPUT_CONTRACTS),
        }
    )
    with (output_dir / "physical_model_inputs.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(physical_model, handle, indent=2, allow_nan=False)
        handle.write("\n")
    default_provenance = manifest.get(
        "provenance", "synthetic demonstration"
    )
    panel_results = {}
    panel_paths: dict[str, str] = {}
    panel_tables: dict[str, dict[str, np.ndarray]] = {}
    panel_fits: dict[str, dict] = {}
    diagnostic_dir = (
        plot_dir / "diagnostics" if plot_dir is not None else None
    )
    layout_dir = (
        plot_dir / "paper_layout" if plot_dir is not None else None
    )
    for panel in CONTRACTS:
        entry = manifest["panels"].get(panel)
        if entry is None:
            result = _unavailable_result(panel)
            panel_results[panel] = result
            continue
        if not isinstance(entry, dict):
            raise ValueError(f"manifest entry for {panel} must be an object")
        source_kind = entry.get("source", "inline")
        if source_kind == "inline":
            rows = entry.get("rows")
            if not isinstance(rows, list):
                raise ValueError(f"inline manifest entry for {panel} needs rows")
            table = _table_from_rows(
                rows, CONTRACTS[panel], f"input.in:{panel}"
            )
            source_label = f"{manifest_path}::{panel}::inline"
            provenance = entry.get("provenance", default_provenance)
        elif source_kind == "csv":
            relative = entry.get("path")
            if not isinstance(relative, str):
                raise ValueError(f"CSV manifest entry for {panel} needs path")
            csv_path = (manifest_path.parent / relative).resolve()
            if not csv_path.exists():
                raise FileNotFoundError(
                    f"input.in CSV path does not exist: {csv_path}"
                )
            table = read_table(csv_path, CONTRACTS[panel])
            source_label = str(csv_path)
            provenance = entry.get(
                "provenance", "experimental raw data"
            )
        else:
            raise ValueError(f"unsupported input.in source {source_kind!r}")
        result = {
            "status": "analysis of supplied manifest data",
            "provenance": provenance,
            "panel": panel,
            "input_manifest": str(manifest_path.resolve()),
            "input_source": source_label,
            "fit": fit_panel(panel, table),
            "rows": int(len(next(iter(table.values())))),
            "synthetic_points_generated": (
                provenance == "synthetic demonstration"
            ),
        }
        panel_tables[panel] = table
        panel_fits[panel] = result["fit"]
        if plot_dir is not None:
            assert diagnostic_dir is not None
            figure_path = diagnostic_dir / f"{panel}.png"
            result["figure"] = plot_panel(
                panel, table, result["fit"], provenance, figure_path
            )
            result["figure_provenance"] = provenance
            panel_paths[panel] = result["figure"]
        panel_results[panel] = result
        with (output_dir / f"{panel}.json").open(
            "w", encoding="utf-8"
        ) as handle:
            json.dump(result, handle, indent=2, allow_nan=True)
            handle.write("\n")
    summary = {
        "status": "manifest analysis complete",
        "input_manifest": str(manifest_path.resolve()),
        "schema_version": manifest["schema_version"],
        "manifest_provenance": default_provenance,
        "physical_model": physical_model,
        "panels": panel_results,
        "synthetic_points_generated": any(
            result.get("synthetic_points_generated", False)
            for result in panel_results.values()
        ),
        "experimental_points_generated": any(
            result.get("provenance") == "experimental raw data"
            for result in panel_results.values()
        ),
    }
    if plot_dir is not None and len(panel_paths) == len(CONTRACTS):
        assert diagnostic_dir is not None
        assert layout_dir is not None
        summary["figure_dir"] = str(plot_dir.resolve())
        summary["overview_figure"] = plot_manifest_overview(
            panel_paths,
            diagnostic_dir / "input_manifest_overview.png",
            default_provenance,
        )
        summary["paper_layout_figures"] = plot_paper_layout_figures(
            panel_tables,
            panel_fits,
            panel_paths,
            layout_dir,
            theory_run_dir,
        )
    with (output_dir / "manifest_summary.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(summary, handle, indent=2, allow_nan=True)
        handle.write("\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", choices=tuple(CONTRACTS))
    parser.add_argument("--input", type=Path)
    parser.add_argument(
        "--manifest",
        "--input-in",
        dest="manifest",
        type=Path,
        help="an input.in manifest; analyzes all experimental panels",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--plot-dir",
        type=Path,
        help="optional directory for per-panel PNGs and an overview image",
    )
    parser.add_argument(
        "--theory-run-dir",
        type=Path,
        help="optional theory run used for paper-layout Figure 3(a-c)",
    )
    args = parser.parse_args()
    if args.manifest is not None:
        if args.panel is not None:
            raise SystemExit("--manifest analyzes all panels; omit --panel")
        if args.output_dir is None:
            raise SystemExit("--manifest requires --output-dir")
        run_manifest(
            args.manifest,
            args.output_dir,
            args.plot_dir,
            args.theory_run_dir,
        )
        return
    if args.output is None:
        raise SystemExit("single-panel mode requires --output")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.input is None or args.panel is None:
        result = {
            "status": "unavailable without raw experimental data",
            "provenance": "unavailable",
            "contracts": CONTRACTS,
            "synthetic_points_generated": False,
        }
    else:
        table = read_table(args.input, CONTRACTS[args.panel])
        fit = fit_panel(args.panel, table)
        result = {
            "status": "analysis of supplied experimental raw data",
            "provenance": "experimental raw data",
            "panel": args.panel,
            "input": str(args.input),
            "fit": fit,
            "synthetic_points_generated": False,
        }
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
