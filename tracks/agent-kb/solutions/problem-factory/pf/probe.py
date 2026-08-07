"""Hop test: run the card's (L, delta, j2) grid and measure the signal."""

import numpy as np

from . import ed


def run_grid(card):
    """gap(L, delta, j2) for the full declared grid. No skipping, no cherry-picking."""
    s = card["setup"]
    gaps = {}
    for L in s["sizes"]:
        for d in s["delta"]:
            for j in s["j2"]:
                e = ed.low_spectrum(L, d, j, convention=card["convention"])
                gaps[(L, d, j)] = float(e[1] - e[0])
    return gaps


def metrics(card, gaps):
    """decisiveness: perturbation effect vs finite-size noise of the baseline.
    gradient_vs_L: slope of the effect with system size at the loudest grid point."""
    s = card["setup"]
    sizes, j0 = sorted(s["sizes"]), s["j2"][0]

    noise = np.mean([
        np.std(np.diff([gaps[(L, d, j0)] for L in sizes])) for d in s["delta"]
    ])
    noise = max(noise, 1e-12)

    best = None
    for d in s["delta"]:
        for j in s["j2"][1:]:
            shifts = np.array([abs(gaps[(L, d, j)] - gaps[(L, d, j0)]) for L in sizes])
            effect = shifts.mean()
            if best is None or effect > best[0]:
                best = (effect, shifts)
    effect, shifts = best
    gradient = np.polyfit(sizes, shifts, 1)[0]

    return {
        "decisiveness": float(effect / noise),
        "gradient_vs_L": float(gradient),
        "effect": float(effect),
        "noise": float(noise),
    }
