"""Joint-regulator audit for the zero-field full GHD diffusion limit."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np


def giant_string_leading_tail_bound(xi_cutoff: float) -> float:
    r"""Bound the omitted tail of the exact giant-string ``D0`` integral.

    For ``X>=1`` and

    ``f(x)=(2x/sinh x)^2 (x coth x+1)/(9 pi)``, use

    ``sinh(x)^-2 <= 4 exp(-2x)/(1-exp(-2X))^2`` and
    ``coth(x)<=coth(X)``.  The remaining polynomial-exponential integrals
    are elementary.  This controls the leading giant-string amplitude only;
    it is not a bound on the finite-field dressed-kernel contribution to
    ``D1``.
    """

    cutoff = float(xi_cutoff)
    if not np.isfinite(cutoff) or cutoff < 1.0:
        raise ValueError("xi_cutoff must be finite and at least one")
    exponential = np.exp(-2.0 * cutoff)
    integral_x2 = exponential * (
        cutoff**2 / 2.0 + cutoff / 2.0 + 0.25
    )
    integral_x3 = exponential * (
        cutoff**3 / 2.0
        + 0.75 * cutoff**2
        + 0.75 * cutoff
        + 0.375
    )
    prefactor = 16.0 / (
        9.0 * np.pi * (1.0 - np.exp(-2.0 * cutoff)) ** 2
    )
    return float(prefactor * (integral_x3 / np.tanh(cutoff) + integral_x2))


def _linear_intercept(x: np.ndarray, y: np.ndarray) -> float:
    if x.size < 2:
        raise ValueError("at least two points are required")
    return float(np.polyfit(x, y, 1)[1])


def audit_joint_zero_field_limit(
    payload: dict[str, Any],
    *,
    exact_leading: float,
    value_key: str = "h_times_full_diffusion",
    quantity_label: str = "finite_cutoff_full_cross",
    physical_d1_candidate: bool = False,
    maximum_smallest_field: float = 0.05,
    maximum_regulator_relative_error: float = 5.0e-3,
    maximum_d1_scheme_spread: float = 5.0e-2,
) -> dict[str, Any]:
    r"""Audit ``h D(h)=D0+D1 h+...`` under all recorded regulators.

    The routine never fills missing regulator directions by assumption.  A
    controlled certificate requires, at the smallest fields used for the
    extrapolation, at least two velocity-series truncations and at least two
    string cutoffs (or an explicit tail bound), a rapidity error estimate,
    monotone approach to the exact ``D0``, and stable nested fits for ``D1``.
    """

    rows = payload.get("full_cross_runs")
    if not isinstance(rows, list) or len(rows) < 3:
        raise ValueError("full_cross_runs must contain at least three rows")
    grouped: dict[tuple[float, float], list[dict[str, Any]]] = defaultdict(list)
    by_field: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for raw in rows:
        row = dict(raw)
        field = float(row["field"])
        cutoff = float(row["string_xi_cutoff"])
        terms = int(row["velocity_series_terms"])
        if row.get(value_key) is None:
            raise ValueError(f"missing regulator value {value_key!r}")
        value = float(row[value_key])
        if field <= 0.0 or cutoff <= 0.0 or terms <= 0 or not np.isfinite(value):
            raise ValueError("invalid full-cross regulator row")
        row.update(
            field=field,
            string_xi_cutoff=cutoff,
            velocity_series_terms=terms,
            audited_hD_value=value,
        )
        grouped[(field, cutoff)].append(row)
        by_field[field].append(row)

    regulator_rows: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    for (field, cutoff), sequence in sorted(grouped.items(), reverse=True):
        sequence.sort(key=lambda item: int(item["velocity_series_terms"]))
        terms = np.asarray([int(item["velocity_series_terms"]) for item in sequence])
        values = np.asarray([float(item["audited_hD_value"]) for item in sequence])
        if terms.size >= 2:
            velocity_limit = _linear_intercept(1.0 / terms[-2:], values[-2:])
            velocity_error = abs(velocity_limit - values[-1])
        else:
            velocity_limit = float(values[-1])
            velocity_error = None
        rapidity_errors = [
            float(item["rho_total_relative_l2_error"])
            for item in sequence
            if item.get("rho_total_relative_l2_error") is not None
        ]
        regulator_rows.append(
            {
                "field": field,
                "string_xi_cutoff": cutoff,
                "velocity_terms": terms.tolist(),
                "hD_values": values.tolist(),
                "inverse_terms_extrapolated_hD": velocity_limit,
                "velocity_series_absolute_error": velocity_error,
                "rapidity_density_relative_l2_error": max(rapidity_errors)
                if rapidity_errors
                else None,
            }
        )

    for field in sorted(by_field):
        candidates = [
            row for row in regulator_rows if np.isclose(float(row["field"]), field)
        ]
        chosen = max(candidates, key=lambda item: float(item["string_xi_cutoff"]))
        cutoffs = sorted({float(item["string_xi_cutoff"]) for item in candidates})
        cutoff_error = None
        if len(cutoffs) >= 2:
            high = [item for item in candidates if item["string_xi_cutoff"] == cutoffs[-1]][0]
            low = [item for item in candidates if item["string_xi_cutoff"] == cutoffs[-2]][0]
            cutoff_error = abs(
                float(high["inverse_terms_extrapolated_hD"])
                - float(low["inverse_terms_extrapolated_hD"])
            )
        selected.append(
            {
                **chosen,
                "available_string_cutoffs": cutoffs,
                "string_tail_absolute_error": cutoff_error,
                "relative_leading_error": float(
                    float(chosen["inverse_terms_extrapolated_hD"]) / exact_leading - 1.0
                ),
                "leading_D0_giant_string_tail_bound": giant_string_leading_tail_bound(
                    float(chosen["string_xi_cutoff"])
                ),
                "tail_bound_applies_to_physical_D1": False,
            }
        )

    fields = np.asarray([float(item["field"]) for item in selected])
    values = np.asarray(
        [float(item["inverse_terms_extrapolated_hD"]) for item in selected]
    )
    order = np.argsort(fields)
    fields = fields[order]
    values = values[order]
    selected = [selected[index] for index in order]
    nested: list[dict[str, Any]] = []
    for count in range(3, fields.size + 1):
        h = fields[:count]
        y = values[:count]
        free_linear = np.polyfit(h, y, 1)
        fixed_design = np.column_stack([h, h**2])
        fixed_coefficients, *_ = np.linalg.lstsq(
            fixed_design, y - exact_leading, rcond=None
        )
        free_quadratic = np.polyfit(h, y, 2) if count >= 3 else None
        nested.append(
            {
                "fields": h.tolist(),
                "free_linear_D0": float(free_linear[1]),
                "free_linear_D1": float(free_linear[0]),
                "fixed_D0_quadratic_D1": float(fixed_coefficients[0]),
                "fixed_D0_quadratic_D2": float(fixed_coefficients[1]),
                "free_quadratic_D0": float(free_quadratic[2]),
                "free_quadratic_D1": float(free_quadratic[1]),
            }
        )
    d1_values = np.asarray(
        [
            number
            for fit in nested
            for number in (
                float(fit["free_linear_D1"]),
                float(fit["fixed_D0_quadratic_D1"]),
                float(fit["free_quadratic_D1"]),
            )
        ]
    )
    d1_spread = float(np.ptp(d1_values)) if d1_values.size else float("inf")
    leading_errors = np.abs(values / exact_leading - 1.0)
    approaches_leading = bool(np.all(np.diff(leading_errors) >= 0.0))
    # fields are ascending: errors should grow as one moves away from zero.
    regulator_complete = True
    missing: list[str] = []
    for item in selected:
        if item["velocity_series_absolute_error"] is None:
            regulator_complete = False
            missing.append(f"h={item['field']}: second velocity-series cutoff")
        if item["string_tail_absolute_error"] is None:
            regulator_complete = False
            missing.append(f"h={item['field']}: second string cutoff or analytic tail bound")
        if item["rapidity_density_relative_l2_error"] is None:
            regulator_complete = False
            missing.append(f"h={item['field']}: rapidity-grid error estimate")
    known_regulator_errors = [
        value
        for item in selected
        for value in (
            item["velocity_series_absolute_error"],
            item["string_tail_absolute_error"],
        )
        if value is not None
    ]
    maximum_known_relative = (
        max(known_regulator_errors) / exact_leading
        if known_regulator_errors
        else float("inf")
    )
    controlled = bool(
        fields[0] <= maximum_smallest_field
        and approaches_leading
        and regulator_complete
        and maximum_known_relative <= maximum_regulator_relative_error
        and d1_spread <= maximum_d1_scheme_spread
    )
    return {
        "schema_version": 1,
        "inputs": {
            "trajectory_data_used": False,
            "target_coefficients_used": False,
            "exact_leading_D0": exact_leading,
            "audited_value_key": value_key,
            "quantity_label": quantity_label,
            "physical_D1_candidate_by_order_of_limits": physical_d1_candidate,
        },
        "selected_field_sequence": selected,
        "nested_small_field_fits": nested,
        "joint_limit_audit": {
            "smallest_field": float(fields[0]),
            "approaches_exact_leading_monotonically": approaches_leading,
            "all_regulator_directions_bounded": regulator_complete,
            "missing_regulator_evidence": missing,
            "maximum_known_regulator_relative_error": float(maximum_known_relative),
            "D1_scheme_spread": d1_spread,
            "zero_field_joint_limit_controlled": controlled,
            "physical_D1_certified": bool(controlled and physical_d1_candidate),
            "exact_leading_giant_string_tail_controlled": bool(
                max(
                    float(item["leading_D0_giant_string_tail_bound"])
                    for item in selected
                )
                / exact_leading
                <= maximum_regulator_relative_error
            ),
        },
        "provisional_D1_interval": {
            "minimum": float(np.min(d1_values)) if d1_values.size else None,
            "maximum": float(np.max(d1_values)) if d1_values.size else None,
            "status": "regulator_and_scheme_envelope_not_a_proof",
        },
    }
