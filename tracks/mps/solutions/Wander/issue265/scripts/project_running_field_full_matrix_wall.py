#!/usr/bin/env python3
"""Project the finite-time F-GHD field expansion onto the frozen wall PDE.

At fixed giant-string variables ``q=k/h^2`` and ``tau=t*h^3``, the matched
Euler--Maclaurin sequence gives

    S_h(q,tau)=sum_n c_n(q,tau) h^n.

For a physical time ``t`` on the self-consistent ray, the infrared regulator
is not set to zero before projection: ``h_eff(t)=(tau/t)^(1/3)``.  Evaluating
the frozen degree-1,2,3 expansions at this running field retains the
``t^(-1/3) F1`` and higher finite-time corrections.  Each resulting structure
factor is Fourier-inverted before the preregistered weak Burgers projection.
No spin trajectory or target coefficient is read.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scipy.signal import savgol_filter


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.project_replicated_full_matrix_wall import (  # noqa: E402
    DEGREES,
    _positive_even_grid,
    _structure,
    _validate_field_audit,
)
from src.tension_resolution import fit_profiled_weak  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def running_field(tau: float, times: np.ndarray) -> np.ndarray:
    times = np.asarray(times, dtype=float)
    if not np.isfinite(tau) or tau <= 0.0 or np.any(times <= 0.0):
        raise ValueError("tau and physical times must be positive")
    return (float(tau) / times) ** (1.0 / 3.0)


def wall_from_scaled_structure(
    q: np.ndarray,
    structure: np.ndarray,
    x: np.ndarray,
    h_eff: float,
) -> np.ndarray:
    r"""Invert ``S(q)`` using ``k=q h_eff^2`` without width renormalization."""

    q = np.asarray(q, dtype=float)
    structure = np.asarray(structure, dtype=float)
    x = np.asarray(x, dtype=float)
    if (
        q.ndim != 1
        or structure.shape != q.shape
        or x.ndim != 1
        or q.size < 4
        or not np.isclose(q[0], 0.0)
        or np.any(np.diff(q) <= 0.0)
        or not np.isclose(structure[0], 1.0, rtol=1.0e-6, atol=1.0e-8)
        or not np.isfinite(h_eff)
        or h_eff <= 0.0
    ):
        raise ValueError("invalid scaled structure inversion inputs")
    scaled_x = x * float(h_eff) ** 2
    phase = np.outer(scaled_x, q)
    integrand = np.empty_like(phase)
    integrand[:, 0] = scaled_x
    integrand[:, 1:] = (
        np.sin(phase[:, 1:])
        * structure[None, 1:]
        / q[None, 1:]
    )
    return np.trapezoid(integrand, q, axis=1) / np.pi


def _strong_projection(
    x: np.ndarray,
    times: np.ndarray,
    profiles: np.ndarray,
    *,
    fit_start: float,
    fit_stop: float,
    x_crop: tuple[float, float],
) -> dict[str, float]:
    smoothed = savgol_filter(profiles, 31, 7, axis=1, mode="interp")
    if times.size >= 7:
        time_window = min(7, times.size if times.size % 2 else times.size - 1)
        smoothed = savgol_filter(smoothed, time_window, min(3, time_window - 1), axis=0, mode="interp")
    ut = np.gradient(smoothed, times, axis=0, edge_order=2)
    ux = np.gradient(smoothed, x, axis=1, edge_order=2)
    uxx = np.gradient(ux, x, axis=1, edge_order=2)
    mask_t = (times >= fit_start) & (times <= fit_stop)
    mask_x = (x >= x_crop[0]) & (x <= x_crop[1])
    response = ut[np.ix_(mask_t, mask_x)].ravel()
    feature_a = -(smoothed * ux)[np.ix_(mask_t, mask_x)].ravel()
    feature_d = uxx[np.ix_(mask_t, mask_x)].ravel()
    design = np.column_stack([feature_a, feature_d])
    coefficients, *_ = np.linalg.lstsq(design, response, rcond=None)
    residual = response - design @ coefficients
    return {
        "a": float(coefficients[0]),
        "D": float(coefficients[1]),
        "mse": float(np.mean(residual**2)),
        "normal_matrix_condition_number": float(np.linalg.cond(design.T @ design)),
    }


def _project_coefficients(
    coefficients: np.ndarray,
    q: np.ndarray,
    *,
    tau: float,
    length: int,
    dx: float,
    profile_start: float,
    profile_stop: float,
    dt: float,
    fit_start: float,
    fit_stop: float,
    x_crop: tuple[float, float],
) -> dict[str, object]:
    x = (np.arange(length) - 0.5 * (length - 1)) * dx
    times = np.arange(profile_start, profile_stop + 0.5 * dt, dt)
    fields = running_field(tau, times)
    powers = fields[:, None] ** np.arange(coefficients.shape[0])[None, :]
    structures = powers @ coefficients
    structures[:, 0] = 1.0
    profiles = np.asarray(
        [
            wall_from_scaled_structure(q, structure, x, field)
            for structure, field in zip(structures, fields)
        ]
    )
    profiles = savgol_filter(profiles, 31, 7, axis=1, mode="interp")
    weak = fit_profiled_weak(
        x,
        times,
        profiles,
        t_window=(fit_start, fit_stop),
        x_crop=x_crop,
        gamma=0.0,
    )
    strong = _strong_projection(
        x,
        times,
        profiles,
        fit_start=fit_start,
        fit_stop=fit_stop,
        x_crop=x_crop,
    )
    return {
        "a": float(weak.a),
        "D": float(weak.D0),
        "weak_mse": float(weak.mse),
        "weak_n_obs": int(weak.n_obs),
        "strong_projection": strong,
        "running_field_range": [float(np.min(fields)), float(np.max(fields))],
        "maximum_absolute_fourier_tail": float(np.max(np.abs(structures[:, -1]))),
        "profile_range": [float(np.min(profiles)), float(np.max(profiles))],
        "endpoint_profile_samples": {
            "times": [float(times[0]), float(times[-1])],
            "center_values": [
                float(profiles[0, np.argmin(np.abs(x))]),
                float(profiles[-1, np.argmin(np.abs(x))]),
            ],
        },
    }


def derive(args: argparse.Namespace) -> dict[str, object]:
    grouped: dict[float, list[tuple[Path, dict[str, object]]]] = defaultdict(list)
    for path in args.inputs:
        payload = json.loads(path.read_text())
        if payload.get("uses_target_a_or_D") or payload.get("uses_target_trajectory"):
            raise ValueError(f"forbidden target dependency in {path}")
        if not payload["iteration"]["converged"]:
            raise ValueError(f"unconverged matrix fixed point in {path}")
        grouped[float(payload["regulator"]["field"])].append((path, payload))
    fields = np.asarray(sorted(grouped, reverse=True), dtype=float)
    if fields.size < args.required_fields:
        raise ValueError("insufficient fields for the frozen finite-window expansion")
    if any(len(grouped[float(field)]) < args.required_replicates for field in fields):
        raise ValueError("insufficient independent replicas at one or more fields")
    _validate_field_audit(args.field_audit, inputs=list(args.inputs), fields=fields)

    reference = grouped[float(fields[0])][0][1]
    scaled_times = np.asarray(reference["scaled_times_tau_equals_t_h3"], dtype=float)
    endpoint = int(np.argmin(np.abs(scaled_times - args.scaled_time)))
    if abs(scaled_times[endpoint] - args.scaled_time) > args.scaled_time_tolerance:
        raise ValueError("requested scaled time is absent")
    scaled_waves = np.asarray(reference["scaled_waves_q_equals_k_over_h2"], dtype=float)
    field_replicates = []
    q = None
    for field in fields:
        rows = []
        for _, payload in grouped[float(field)]:
            if not np.allclose(payload["scaled_times_tau_equals_t_h3"], scaled_times):
                raise ValueError("scaled-time grid mismatch")
            if not np.allclose(payload["scaled_waves_q_equals_k_over_h2"], scaled_waves):
                raise ValueError("scaled-wave grid mismatch")
            q_row, structure = _positive_even_grid(
                scaled_waves, _structure(payload)[:, endpoint]
            )
            q = q_row if q is None else q
            if not np.allclose(q, q_row):
                raise ValueError("positive Fourier grid mismatch")
            rows.append(structure)
        field_replicates.append(np.asarray(rows))
    assert q is not None
    stacks = field_replicates
    means = np.asarray([np.mean(rows, axis=0) for rows in stacks])

    projection_kwargs = dict(
        tau=float(scaled_times[endpoint]),
        length=args.length,
        dx=args.dx,
        profile_start=args.profile_start,
        profile_stop=args.profile_stop,
        dt=args.dt,
        fit_start=args.fit_start,
        fit_stop=args.fit_stop,
        x_crop=tuple(args.x_crop),
    )
    scheme_rows = {}
    coefficient_rows = {}
    for degree in DEGREES:
        design = np.column_stack([fields**power for power in range(degree + 1)])
        coefficients = np.linalg.pinv(design) @ means
        coefficients[:, 0] = 0.0
        coefficients[0, 0] = 1.0
        coefficient_rows[str(degree)] = coefficients
        scheme_rows[str(degree)] = _project_coefficients(
            coefficients, q, **projection_kwargs
        )

    running_range = running_field(
        float(scaled_times[endpoint]),
        np.asarray([args.profile_start, args.profile_stop]),
    )
    running_inside_field_support = bool(
        np.min(running_range) >= np.min(fields)
        and np.max(running_range) <= np.max(fields)
    )
    pairs = np.asarray([[row["a"], row["D"]] for row in scheme_rows.values()])
    envelopes = {
        "a": [float(np.min(pairs[:, 0])), float(np.max(pairs[:, 0]))],
        "D": [float(np.min(pairs[:, 1])), float(np.max(pairs[:, 1]))],
    }
    relative_widths = {
        key: (value[1] - value[0])
        / max(abs(0.5 * (value[0] + value[1])), np.finfo(float).tiny)
        for key, value in envelopes.items()
    }
    maximum_tail = max(
        float(row["maximum_absolute_fourier_tail"]) for row in scheme_rows.values()
    )
    projection_disagreement = {
        observable: max(
            abs(float(row[observable]) - float(row["strong_projection"][observable]))
            / max(
                abs(float(row[observable])),
                abs(float(row["strong_projection"][observable])),
                np.finfo(float).tiny,
            )
            for row in scheme_rows.values()
        )
        for observable in ("a", "D")
    }
    accepted = bool(
        running_inside_field_support
        and maximum_tail <= args.maximum_fourier_tail
        and all(value <= args.maximum_relative_scheme_width for value in relative_widths.values())
        and all(value <= args.maximum_projection_disagreement for value in projection_disagreement.values())
    )
    return {
        "schema": 1,
        "method": "running_field_finite_window_full_matrix_wall_projection",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "microscopic_mapping": {
            "scaled_time_tau": float(scaled_times[endpoint]),
            "h_eff_of_t": "(tau/t)^(1/3)",
            "finite_time_expansion": "S=sum_n c_n(q,tau) h_eff(t)^n",
            "discarded_f1_by_premature_h_to_zero": False,
        },
        "fields_descending": fields.tolist(),
        "replicates_per_field": [len(grouped[float(field)]) for field in fields],
        "positive_q_grid": q.tolist(),
        "integer_degree_projections": scheme_rows,
        "coefficient_arrays_by_degree": coefficient_rows,
        "scheme_envelope": envelopes,
        "relative_scheme_width": relative_widths,
        "input_sha256_by_file": {str(path): _sha256(path) for path in args.inputs},
        "field_audit_sha256": _sha256(args.field_audit),
        "gates": {
            "running_field_inside_computed_field_support": running_inside_field_support,
            "running_field_endpoint_values": running_range.tolist(),
            "maximum_absolute_fourier_tail": maximum_tail,
            "maximum_fourier_tail_allowed": args.maximum_fourier_tail,
            "weak_strong_relative_projection_disagreement": projection_disagreement,
            "maximum_projection_disagreement_allowed": args.maximum_projection_disagreement,
            "maximum_relative_scheme_width_allowed": args.maximum_relative_scheme_width,
            "accepted": accepted,
        },
        "physical_a_or_D_identified": accepted,
    }


def _jsonable(value):
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--field-audit", required=True, type=Path)
    parser.add_argument("--scaled-time", type=float, default=27 / (10 * np.pi))
    parser.add_argument("--scaled-time-tolerance", type=float, default=1.0e-10)
    parser.add_argument("--required-fields", type=int, default=7)
    parser.add_argument("--required-replicates", type=int, default=4)
    parser.add_argument("--length", type=int, default=400)
    parser.add_argument("--dx", type=float, default=1.0)
    parser.add_argument("--profile-start", type=float, default=50.0)
    parser.add_argument("--profile-stop", type=float, default=200.0)
    parser.add_argument("--dt", type=float, default=0.2)
    parser.add_argument("--fit-start", type=float, default=52.0)
    parser.add_argument("--fit-stop", type=float, default=198.0)
    parser.add_argument("--x-crop", nargs=2, type=float, default=[-120.0, 120.0])
    parser.add_argument("--maximum-relative-scheme-width", type=float, default=0.1)
    parser.add_argument("--maximum-fourier-tail", type=float, default=1.0e-2)
    parser.add_argument("--maximum-projection-disagreement", type=float, default=0.15)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = derive(args)
    encoded = json.dumps(_jsonable(result), indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
