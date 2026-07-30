"""Independent scientific claim gates for the pole-resolved heat valve."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class HeatValveAudit:
    complete: bool
    dark_channel_passed: bool
    many_body_amplification_passed: bool
    markov_payoff_passed: bool
    failures: tuple[str, ...]
    metrics: dict[str, float]


def _same_numeric(values: list[float], tolerance: float = 1e-12) -> bool:
    return bool(values) and bool(
        np.allclose(values, values[0], rtol=tolerance, atol=tolerance)
    )


def _ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return float("inf")
    return numerator / denominator


def audit_heat_valve_manifest(manifest: dict[str, Any]) -> HeatValveAudit:
    """Apply the design gates without relying on any plotting decisions."""
    dark_failures: list[str] = []
    auxiliary_failures: list[str] = []
    metrics: dict[str, float] = {}
    selected = list(manifest.get("selected_points", ()))
    points = list(manifest.get("points", ()))

    selected_keys = [
        (int(item["n"]), float(item["xi"]))
        for item in selected
        if isinstance(item, dict) and "n" in item and "xi" in item
    ]
    point_map = {
        (int(item["point"]["n"]), float(item["point"]["xi"])): item
        for item in points
        if isinstance(item, dict)
        and isinstance(item.get("point"), dict)
        and "n" in item["point"]
        and "xi" in item["point"]
    }
    complete = bool(
        manifest.get("complete", False)
        and len(selected_keys) == 9
        and len(set(selected_keys)) == 9
        and len(point_map) == 9
        and set(selected_keys) == set(point_map)
        and all(sum(key[0] == n for key in selected_keys) == 3 for n in (1, 2, 3))
    )
    if not complete:
        dark_failures.append("heat-valve manifest is incomplete")

    drive_frequencies = [
        float(item["model"]["drive_frequency"])
        for item in point_map.values()
    ]
    if point_map and not _same_numeric(drive_frequencies):
        dark_failures.append("fixed drive frequency was not held constant")

    fixed_controls = (
        ("j", [float(item["model"]["j"]) for item in point_map.values()]),
        (
            "omega",
            [float(item["model"]["omega"]) for item in point_map.values()],
        ),
        (
            "alpha",
            [float(item["bath"]["alpha"]) for item in point_map.values()],
        ),
        (
            "cutoff",
            [float(item["bath"]["cutoff"]) for item in point_map.values()],
        ),
        (
            "temperature",
            [float(item["bath"]["temperature"]) for item in point_map.values()],
        ),
    )
    for label, values in fixed_controls:
        if point_map and not _same_numeric(values):
            dark_failures.append(f"fixed physical control {label} changed")
    for label in ("normalization", "drive_normalization"):
        labels = {str(item["model"][label]) for item in point_map.values()}
        if point_map and len(labels) != 1:
            dark_failures.append(f"fixed physical control {label} changed")

    for key, item in point_map.items():
        label = f"N={key[0]}, xi={key[1]:g}"
        if not bool(item.get("converged", False)):
            dark_failures.append(f"{label}: convergence gate failed")
        diagnostics = item.get("diagnostics", {})
        if (
            float(diagnostics.get("trace_error", float("inf"))) > 5e-3
            or float(diagnostics.get("hermiticity_error", float("inf"))) > 5e-3
            or float(
                diagnostics.get("minimum_density_eigenvalue", -float("inf"))
            )
            < -5e-3
            or float(diagnostics.get("fixed_point_residual", float("inf")))
            > 1e-3
            or float(diagnostics.get("connected_tail", float("inf"))) > 5e-2
        ):
            dark_failures.append(f"{label}: physical diagnostics gate failed")
        reconstruction = float(
            item.get("pole_fit", {}).get(
                "reconstruction_residual",
                float("inf"),
            )
        )
        if reconstruction > 5e-2:
            dark_failures.append(f"{label}: pole reconstruction residual exceeds 5%")
        for pole in item.get("poles", ()):
            if float(pole.get("eigenpair_residual", float("inf"))) > 1e-8:
                dark_failures.append(f"{label}: eigenpair residual exceeds 1e-8")
                break
        for pole in item.get("poles", ()):
            modulus = float(
                pole.get("eigenvalue", {}).get("abs", float("inf"))
            )
            if modulus > 1 + 1e-6:
                dark_failures.append(f"{label}: transfer pole leaves the unit disk")
                break

    heat_contrasts: dict[int, float] = {}
    for n in (1, 2, 3):
        ordered_keys = [key for key in selected_keys if key[0] == n]
        if len(ordered_keys) != 3 or any(key not in point_map for key in ordered_keys):
            continue
        lower, minimum, upper = (point_map[key] for key in ordered_keys)
        lower_heat = float(lower.get("integrated_absolute_heat", float("nan")))
        minimum_heat = float(minimum.get("integrated_absolute_heat", float("nan")))
        upper_heat = float(upper.get("integrated_absolute_heat", float("nan")))
        heat_ratio = max(
            _ratio(minimum_heat, lower_heat),
            _ratio(minimum_heat, upper_heat),
        )
        heat_contrast = _ratio(min(lower_heat, upper_heat), minimum_heat)
        heat_contrasts[n] = heat_contrast
        metrics[f"heat_ratio_n{n}"] = heat_ratio
        metrics[f"heat_contrast_n{n}"] = heat_contrast
        if not np.isfinite(heat_ratio) or heat_ratio > 0.1:
            dark_failures.append(
                f"N={n}: tenfold heat suppression against both flanks failed"
            )

        lower_residue = float(
            lower.get("visible_residue_weight", float("nan"))
        )
        minimum_residue = float(
            minimum.get("visible_residue_weight", float("nan"))
        )
        upper_residue = float(
            upper.get("visible_residue_weight", float("nan"))
        )
        residue_ratio = max(
            _ratio(minimum_residue, lower_residue),
            _ratio(minimum_residue, upper_residue),
        )
        metrics[f"residue_ratio_n{n}"] = residue_ratio
        if not np.isfinite(residue_ratio) or residue_ratio > 0.1:
            dark_failures.append(
                f"N={n}: tenfold residue suppression against both flanks failed"
            )

    dark_channel_passed = complete and not dark_failures
    amplification = bool(
        dark_channel_passed
        and 1 in heat_contrasts
        and 3 in heat_contrasts
        and heat_contrasts[3] >= 5 * heat_contrasts[1]
    )
    if dark_channel_passed and not amplification:
        auxiliary_failures.append(
            "many-body amplification did not exceed the fivefold contrast gate"
        )
    markov_payoff = bool(
        manifest.get("markov_comparison", {}).get("passed", False)
    )
    return HeatValveAudit(
        complete=complete,
        dark_channel_passed=dark_channel_passed,
        many_body_amplification_passed=amplification,
        markov_payoff_passed=markov_payoff,
        failures=tuple(dark_failures + auxiliary_failures),
        metrics=metrics,
    )
