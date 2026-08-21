"""Locked per-sigma exponential-fit regeneration protocol."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .couplings import periodic_couplings
from .exponential_fit import fit_power_law, periodized_exponential_couplings


PRIMARY_K = 24
PRIMARY_ALPHA = 0.5


@dataclass(frozen=True, order=True)
class FitProtocolSpec:
    num_exponentials: int
    alpha: float
    r_fit: int


def fit_protocol_specs(l_max: int) -> list[FitProtocolSpec]:
    """Return the seven preregistered pole/window/bound protocol cells."""
    if not isinstance(l_max, (int, np.integer)) or l_max < 2:
        raise ValueError("l_max must be an integer >= 2")
    primary_window = 8 * int(l_max)
    specs = {
        FitProtocolSpec(PRIMARY_K, PRIMARY_ALPHA, 4 * l_max),
        FitProtocolSpec(PRIMARY_K, PRIMARY_ALPHA, primary_window),
        FitProtocolSpec(PRIMARY_K, PRIMARY_ALPHA, 16 * l_max),
        FitProtocolSpec(16, PRIMARY_ALPHA, primary_window),
        FitProtocolSpec(32, PRIMARY_ALPHA, primary_window),
        FitProtocolSpec(PRIMARY_K, 0.25, primary_window),
        FitProtocolSpec(PRIMARY_K, 1.0, primary_window),
    }
    return sorted(specs)


def _fit_record(sigma: float, lengths: list[int], spec: FitProtocolSpec) -> dict:
    fit = fit_power_law(
        sigma=sigma,
        num_exponentials=spec.num_exponentials,
        r_fit=spec.r_fit,
        min_rate_scale=spec.alpha,
    )
    rates = -np.log(fit.lambdas)
    profiles = {}
    summaries = {}
    for length in lengths:
        exact = periodic_couplings(length, sigma)
        compact = periodized_exponential_couplings(length, fit)
        relative = np.abs(compact - exact) / exact
        profiles[str(length)] = [
            {
                "distance": distance,
                "exact": float(exact_value),
                "compact": float(compact_value),
                "absolute_error": float(abs(compact_value - exact_value)),
                "relative_error": float(relative_value),
            }
            for distance, (exact_value, compact_value, relative_value) in enumerate(
                zip(exact, compact, relative, strict=True),
                start=1,
            )
        ]
        summaries[str(length)] = {
            "max_relative_error": float(np.max(relative)),
            "rms_relative_error": float(np.sqrt(np.mean(relative**2))),
            "maximum_distance": int(np.argmax(relative) + 1),
            "central_relative_error": float(relative[length // 2 - 1]),
        }
    return {
        "num_exponentials": spec.num_exponentials,
        "alpha": spec.alpha,
        "r_fit": spec.r_fit,
        "lambdas": fit.lambdas.tolist(),
        "rates": rates.tolist(),
        "coefficients": fit.coefficients.tolist(),
        "min_rate_times_r_fit": float(np.min(rates) * spec.r_fit),
        "kernel_max_relative_error": fit.max_relative_error,
        "kernel_rms_relative_error": fit.rms_relative_error,
        "coupling_summaries": summaries,
        "coupling_profiles": profiles,
    }


def regenerate_sigma_fits(
    *,
    sigma: float,
    lengths: list[int],
    l_max: int,
) -> dict:
    """Regenerate and validate every locked fit cell for one sigma."""
    if sorted(set(lengths)) != sorted(lengths) or any(
        length < 2 for length in lengths
    ):
        raise ValueError("lengths must be unique integers >= 2")
    records = [
        _fit_record(sigma, lengths, spec) for spec in fit_protocol_specs(l_max)
    ]
    primary_window = 8 * l_max

    def find(k: int) -> dict:
        return next(
            record
            for record in records
            if record["num_exponentials"] == k
            and record["alpha"] == PRIMARY_ALPHA
            and record["r_fit"] == primary_window
        )

    k24 = find(24)
    k32 = find(32)
    by_length = {}
    for length in lengths:
        key = str(length)
        profile24 = k24["coupling_profiles"][key]
        profile32 = k32["coupling_profiles"][key]
        differences = [
            abs(row32["compact"] - row24["compact"])
            for row24, row32 in zip(profile24, profile32, strict=True)
        ]
        by_length[key] = {
            "K24_max_relative_error": k24["coupling_summaries"][key][
                "max_relative_error"
            ],
            "K32_max_relative_error": k32["coupling_summaries"][key][
                "max_relative_error"
            ],
            "max_coupling_shift": max(differences),
            "central_K24_relative_error": k24["coupling_summaries"][key][
                "central_relative_error"
            ],
            "central_K32_relative_error": k32["coupling_summaries"][key][
                "central_relative_error"
            ],
        }
    return {
        "sigma": float(sigma),
        "lengths": list(lengths),
        "l_max": int(l_max),
        "primary": {
            "num_exponentials": PRIMARY_K,
            "alpha": PRIMARY_ALPHA,
            "r_fit": primary_window,
        },
        "fits": records,
        "K_comparison": {
            "hamiltonian": {"status": "complete", "by_length": by_length},
            "physics": {
                "status": "pending",
                "crossings": None,
                "gaps": None,
                "z_eff": None,
            },
        },
    }


def regenerate_primary_sigma_fit(
    *,
    sigma: float,
    lengths: list[int],
    l_max: int,
) -> dict:
    """Regenerate only the validated K24 exploration fit for one sigma."""
    if sorted(set(lengths)) != sorted(lengths) or any(
        length < 2 for length in lengths
    ):
        raise ValueError("lengths must be unique integers >= 2")
    spec = FitProtocolSpec(PRIMARY_K, PRIMARY_ALPHA, 8 * int(l_max))
    record = _fit_record(sigma, lengths, spec)
    return {
        "sigma": float(sigma),
        "lengths": list(lengths),
        "l_max": int(l_max),
        "primary": {
            "num_exponentials": PRIMARY_K,
            "alpha": PRIMARY_ALPHA,
            "r_fit": spec.r_fit,
        },
        "fits": [record],
        "K_comparison": {
            "status": "deferred_representative_validation",
        },
    }
