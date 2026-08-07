"""Numerical evidence recorded when the stage-0 oracle suite passes."""

from __future__ import annotations

import math

import numpy as np

from .born_oracle import (
    enumerate_born_distribution,
    sample_by_exact_conditionals,
    vacuum_wilson_loop,
)
from .conventions import ISING_K_CRITICAL, NISHIMORI_PC, nishimori_coupling
from .exact import BondFields, direct_amplitude, gauge_transform, row_transfer_amplitude
from .majorana_oracle import (
    clifford_residual,
    majorana_mx_layer,
    majorana_mz_layer,
    majorana_operators,
    project_parity,
    spin_mx_layer,
    spin_mz_layer,
)


def _signed_log_difference(
    left: tuple[int, float], right: tuple[int, float]
) -> float:
    if left[0] != right[0]:
        return math.inf
    return abs(left[1] - right[1])


def collect_stage0_metrics() -> dict[str, float | int]:
    clean = BondFields.clean(nx=3, ny=2)
    clean_difference = _signed_log_difference(
        direct_amplitude(clean, ISING_K_CRITICAL),
        row_transfer_amplitude(clean, ISING_K_CRITICAL),
    )

    signed = BondFields(
        s_horizontal=np.array([[1, -1, 1], [-1, 1, 1]], dtype=np.int8),
        s_vertical=np.array([[1, -1, -1]], dtype=np.int8),
        t_horizontal=np.array([[-1, 1, 1], [1, -1, 1]], dtype=np.int8),
        t_vertical=np.array([[1, -1, 1]], dtype=np.int8),
    )
    signed_difference = _signed_log_difference(
        direct_amplitude(signed, ISING_K_CRITICAL),
        row_transfer_amplitude(signed, ISING_K_CRITICAL),
    )

    rbim = BondFields(
        s_horizontal=np.array([[1, -1, 1], [-1, 1, 1]], dtype=np.int8),
        s_vertical=np.array([[1, -1, -1]], dtype=np.int8),
    )
    site_gauge = np.array([[1, -1, 1], [-1, -1, 1]], dtype=np.int8)
    rbim_transformed = gauge_transform(rbim, site_gauge)
    rbim_gauge_difference = _signed_log_difference(
        direct_amplitude(rbim, nishimori_coupling(NISHIMORI_PC)),
        direct_amplitude(
            rbim_transformed, nishimori_coupling(NISHIMORI_PC)
        ),
    )

    outcomes = enumerate_born_distribution(
        nx=2,
        ny=1,
        coupling=ISING_K_CRITICAL,
        vacuum_only=True,
        max_variables=8,
    )
    normalization_error = abs(
        math.fsum(outcome.probability for outcome in outcomes) - 1.0
    )
    wilson_violations = sum(
        vacuum_wilson_loop(outcome.fields) != 1 for outcome in outcomes
    )
    sampled, sampled_log_probability = sample_by_exact_conditionals(
        outcomes, np.random.default_rng(20260727)
    )
    conditional_log_probability_error = abs(
        sampled_log_probability - math.log(sampled.probability)
    )

    coefficients_x = np.array([0.11, -0.23, 0.07])
    mx_difference = float(
        np.linalg.norm(
            spin_mx_layer(coefficients_x) - majorana_mx_layer(coefficients_x)
        )
    )
    coefficients_z = np.array([0.13, -0.09, 0.17, 0.04])
    spin_z = spin_mz_layer(coefficients_z, periodic=True)
    mz_differences = []
    for parity in (-1, 1):
        projector = project_parity(4, parity)
        majorana_z = majorana_mz_layer(
            coefficients_z, periodic=True, parity_sector=parity
        )
        mz_differences.append(
            float(np.linalg.norm(projector @ (spin_z - majorana_z) @ projector))
        )

    return {
        "clean_logZ_transfer_abs_error": clean_difference,
        "signed_logZ_transfer_abs_error": signed_difference,
        "rbim_gauge_logZ_abs_error": rbim_gauge_difference,
        "born_outcome_count": len(outcomes),
        "born_normalization_abs_error": normalization_error,
        "born_conditional_logP_abs_error": conditional_log_probability_error,
        "vacuum_wilson_loop_violations": wilson_violations,
        "majorana_clifford_residual": clifford_residual(majorana_operators(3)),
        "majorana_mx_operator_norm_error": mx_difference,
        "majorana_periodic_mz_odd_sector_norm_error": mz_differences[0],
        "majorana_periodic_mz_even_sector_norm_error": mz_differences[1],
    }
