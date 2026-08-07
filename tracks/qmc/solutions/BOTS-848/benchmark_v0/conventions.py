from __future__ import annotations

import math
from collections.abc import Mapping


def background_energy(n_electrons: int, q: float) -> float:
    """Uniform neutralizing-background energy in e^2/(epsilon l_B)."""

    return -(n_electrons**2) / (2.0 * math.sqrt(q))


def density_shift_factor(
    n_electrons: int,
    two_q: int,
    filling: float,
) -> float:
    """Finite-sphere density correction used by the comparison paper."""

    return math.sqrt(two_q * filling / n_electrons)


def energy_conventions(
    *,
    ground_energy: float,
    excited_energies_by_m: Mapping[int, float],
    n_electrons: int,
    two_q: int,
    filling: float,
) -> dict[str, dict[str, object]]:
    """Return immutable raw and background/density-corrected energy views."""

    raw_excited = dict(excited_energies_by_m)
    combined_excited = sum(raw_excited.values()) / len(raw_excited)
    raw_gap = combined_excited - ground_energy

    background = background_energy(n_electrons, two_q / 2.0)
    factor = density_shift_factor(n_electrons, two_q, filling)
    paper_total_excited = {
        m: factor * (energy + background) for m, energy in raw_excited.items()
    }
    paper_total = {
        "ground_energy": factor * (ground_energy + background),
        "excited_energies_by_m": paper_total_excited,
        "combined_excited_energy": factor * (combined_excited + background),
        "gap": factor * raw_gap,
    }
    paper_per_particle = {
        "ground_energy": paper_total["ground_energy"] / n_electrons,
        "excited_energies_by_m": {
            m: energy / n_electrons for m, energy in paper_total_excited.items()
        },
        "combined_excited_energy": (
            paper_total["combined_excited_energy"] / n_electrons
        ),
        "gap": paper_total["gap"] / n_electrons,
    }

    return {
        "raw_lll": {
            "ground_energy": ground_energy,
            "excited_energies_by_m": raw_excited,
            "combined_excited_energy": combined_excited,
            "gap": raw_gap,
        },
        "paper_convention": {
            "total": paper_total,
            "per_particle": paper_per_particle,
            "uniform_background_energy": background,
            "density_shift_factor": factor,
        },
    }
