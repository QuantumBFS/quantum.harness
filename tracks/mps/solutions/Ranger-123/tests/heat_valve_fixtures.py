from __future__ import annotations

from copy import deepcopy
from typing import Any


def valid_heat_valve_manifest() -> dict[str, Any]:
    selected_points: list[dict[str, Any]] = []
    points: list[dict[str, Any]] = []
    flank_heat = {1: 1.0, 2: 2.0, 3: 6.0}
    for n in (1, 2, 3):
        for role, xi in zip(
            ("lower_flank", "minimum", "upper_flank"),
            (2.0, 2.2, 2.4),
            strict=True,
        ):
            selected_points.append({"n": n, "xi": xi})
            heat = 0.05 if role == "minimum" else flank_heat[n]
            residue = 0.05 if role == "minimum" else flank_heat[n]
            points.append(
                {
                    "complete": True,
                    "converged": True,
                    "point": {"n": n, "xi": xi},
                    "model": {
                        "n": n,
                        "j": 1.0,
                        "omega": 1.0,
                        "drive_amplitude": 1.5 * xi,
                        "drive_frequency": 3.0,
                        "normalization": "bounded",
                        "drive_normalization": "per_spin",
                    },
                    "bath": {
                        "alpha": 0.05,
                        "cutoff": 2.5,
                        "temperature": 0.0,
                    },
                    "numerics": {
                        "steps_per_period": 60,
                        "tolerance": 1e-6,
                        "phase_samples": 3,
                        "delay_periods": 12,
                        "pole_count": 8,
                    },
                    "diagnostics": {
                        "trace_error": 1e-10,
                        "hermiticity_error": 1e-10,
                        "minimum_density_eigenvalue": 0.01,
                        "fixed_point_residual": 1e-10,
                        "connected_tail": 1e-3,
                        "maximum_eigenpair_residual": 1e-12,
                        "maximum_pole_modulus": 0.9,
                    },
                    "pole_fit": {
                        "reconstruction_residual": 1e-3,
                        "condition_number": 10.0,
                    },
                    "poles": [
                        {
                            "eigenvalue": {
                                "real": 0.85,
                                "imag": 0.1,
                                "abs": 0.9,
                            },
                            "decay_rate": 0.05,
                            "quasifrequency": 0.1,
                            "eigenpair_residual": 1e-12,
                            "residue": {"abs": residue},
                        }
                    ],
                    "frequency": [0.0, 1.0, 2.0, 3.0],
                    "continuous": [0.0, heat, heat / 2, 0.0],
                    "integrated_absolute_heat": heat,
                    "dominant_residue": {"abs": residue},
                    "visible_residue_weight": residue,
                }
            )
    return deepcopy(
        {
            "complete": True,
            "selected_points": selected_points,
            "points": points,
            "markov_comparison": {"passed": True},
        }
    )
