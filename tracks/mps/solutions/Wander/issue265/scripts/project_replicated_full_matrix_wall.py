#!/usr/bin/env python3
"""Project replicated theory-only full-matrix structure factors onto a wall PDE.

Every input is a fluctuating-GHD/Mori calculation on a common scaled Fourier
and time grid.  Replicates are averaged at fixed infrared field.  The field is
removed only through the preregistered degree-one through degree-three
Euler--Maclaurin expansion after its independent five-field audit has passed.
Only then is the structure factor Fourier-inverted and passed through the
frozen weak projection.  No target trajectory or target value of ``a`` or
``D`` is read by this program.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.signal import savgol_filter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.heisenberg_burgers_bridge import EXACT_D0_INFINITY_T
from src.tension_resolution import fit_profiled_weak


DEGREES = (1, 2, 3)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _structure(payload: dict[str, object]) -> np.ndarray:
    return np.asarray(
        [[complex(*pair) for pair in row] for row in payload["structure_factors_over_chi_by_wave_then_time"]]
    )


def _validate_field_audit(
    path: Path,
    *,
    inputs: list[Path],
    fields: np.ndarray,
) -> dict[str, object]:
    audit = json.loads(path.read_text())
    if audit.get("uses_target_a_or_D") or audit.get("uses_target_trajectory"):
        raise ValueError("target-dependent field audit is forbidden")
    if not audit.get("matched_integer_field_limit_accepted"):
        raise ValueError("matched integer field audit has not been accepted")
    if tuple(audit.get("degrees_tested", ())) != DEGREES:
        raise ValueError("field audit did not freeze degrees 1,2,3")
    if not np.allclose(audit.get("fields_descending", ()), fields):
        raise ValueError("field audit and projection fields differ")
    audit_hashes = sorted(audit.get("input_sha256_by_file", {}).values())
    input_hashes = sorted(_sha256(input_path) for input_path in inputs)
    if audit_hashes != input_hashes:
        raise ValueError("field audit input hashes differ from projection inputs")
    return audit


def _positive_even_grid(waves: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    absolute = np.round(np.abs(waves), 13)
    q_values = np.unique(absolute)
    even = np.asarray([np.mean(values[absolute == q].real) for q in q_values])
    order = np.argsort(q_values)
    return q_values[order], even[order]


def _variance_from_curvature(q: np.ndarray, structure: np.ndarray) -> float:
    mask = (q > 0) & (q <= 1)
    if np.count_nonzero(mask) < 3:
        raise ValueError("at least three nonzero q points up to one are required")
    x = q[mask] ** 2
    design = np.column_stack([x, x**2])
    coefficients, *_ = np.linalg.lstsq(design, 1 - structure[mask], rcond=None)
    variance = 2 * coefficients[0]
    if not np.isfinite(variance) or variance <= 0:
        raise ValueError("non-positive structure-factor variance")
    return float(variance)


def _wall_shape(q: np.ndarray, structure: np.ndarray, variance: float, y: np.ndarray) -> np.ndarray:
    phase = np.sqrt(variance) * np.outer(y, q)
    integrand = np.empty_like(phase)
    integrand[:, 0] = np.sqrt(variance) * y
    integrand[:, 1:] = np.sin(phase[:, 1:]) * structure[None, 1:] / q[None, 1:]
    wall = np.trapezoid(integrand, q, axis=1) / np.pi
    wall[np.argmin(np.abs(y))] = 0.0
    return wall


def _power_time_integral(exponent: float, start: float, stop: float) -> float:
    """Return integral_start^stop t**(-exponent) dt analytically."""

    if abs(exponent - 1.0) < 1e-14:
        return float(np.log(stop / start))
    return float((stop ** (1 - exponent) - start ** (1 - exponent)) / (1 - exponent))


def _analytic_selfsimilar_strong_projection(
    y: np.ndarray,
    wall: np.ndarray,
    *,
    scale: float,
    time_start: float,
    time_stop: float,
    alpha: float = 2 / 3,
) -> dict[str, float]:
    r"""Project a self-similar wall using factored analytic time integrals.

    For ``U=F(x/(c t^alpha))`` the target equation is
    ``U_t=-a U U_x + D U_xx``.  The two spatial features and the response have
    fixed powers of time, so their continuum normal matrix factorizes into
    one-dimensional shape integrals and exact time integrals.
    """

    first = np.gradient(wall, y, edge_order=2)
    second = np.gradient(first, y, edge_order=2)
    pp_shape = np.trapezoid(wall**2 * first**2, y)
    pq_shape = -np.trapezoid(wall * first * second, y)
    qq_shape = np.trapezoid(second**2, y)
    pt_shape = alpha * np.trapezoid(y * wall * first**2, y)
    qt_shape = -alpha * np.trapezoid(y * first * second, y)
    matrix = np.asarray(
        [
            [
                pp_shape / scale * _power_time_integral(alpha, time_start, time_stop),
                pq_shape / scale**2 * _power_time_integral(2 * alpha, time_start, time_stop),
            ],
            [
                pq_shape / scale**2 * _power_time_integral(2 * alpha, time_start, time_stop),
                qq_shape / scale**3 * _power_time_integral(3 * alpha, time_start, time_stop),
            ],
        ]
    )
    response = np.asarray(
        [
            pt_shape * _power_time_integral(1.0, time_start, time_stop),
            qt_shape / scale * _power_time_integral(alpha + 1, time_start, time_stop),
        ]
    )
    coefficients = np.linalg.solve(matrix, response)
    condition = float(np.linalg.cond(matrix))
    return {
        "a": float(coefficients[0]),
        "D": float(coefficients[1]),
        "normal_matrix_condition_number": condition,
        "shape_pp": float(pp_shape),
        "shape_pq": float(pq_shape),
        "shape_qq": float(qq_shape),
        "shape_pt": float(pt_shape),
        "shape_qt": float(qt_shape),
    }


def _project_structure(
    q: np.ndarray,
    structure: np.ndarray,
    *,
    length: int,
    profile_start: float,
    profile_stop: float,
    dt: float,
    fit_start: float,
    fit_stop: float,
    x_crop: tuple[float, float],
    y_maximum: float,
    y_points: int,
) -> dict[str, float | int]:
    structure = np.asarray(structure, dtype=float).copy()
    structure[0] = 1.0
    variance = _variance_from_curvature(q, structure)
    y = np.linspace(-y_maximum, y_maximum, y_points)
    wall = _wall_shape(q, structure, variance, y)
    spline = CubicSpline(y, wall)
    x = np.arange(length) - 0.5 * (length - 1)
    times = np.arange(profile_start, profile_stop + 0.5 * dt, dt)
    chi = 0.25
    rms_scale = (4 * EXACT_D0_INFINITY_T * np.sqrt(chi)) ** (2 / 3)
    strong = _analytic_selfsimilar_strong_projection(
        y,
        wall,
        scale=float(rms_scale),
        time_start=fit_start,
        time_stop=fit_stop,
    )
    profiles = []
    for time in times:
        coordinate = x / (rms_scale * time ** (2 / 3))
        profile = spline(np.clip(coordinate, y[0], y[-1]))
        profile = np.where(coordinate < y[0], -0.5, profile)
        profile = np.where(coordinate > y[-1], 0.5, profile)
        profiles.append(profile)
    profiles = savgol_filter(np.asarray(profiles), 31, 7, axis=1, mode="interp")
    fit = fit_profiled_weak(
        x,
        times,
        profiles,
        t_window=(fit_start, fit_stop),
        x_crop=x_crop,
        gamma=0.0,
    )
    return {
        "a": float(fit.a),
        "D": float(fit.D0),
        "mse": float(fit.mse),
        "n_obs": int(fit.n_obs),
        "variance_before_internal_normalization": variance,
        "fourier_tail_at_qmax": float(structure[-1]),
        "wall_at_positive_boundary": float(wall[-1]),
        "analytic_selfsimilar_strong_projection": strong,
        "weak_strong_absolute_difference": {
            "a": float(abs(fit.a - strong["a"])),
            "D": float(abs(fit.D0 - strong["D"])),
        },
    }


def derive(args: argparse.Namespace) -> dict[str, object]:
    grouped: dict[float, list[dict[str, object]]] = defaultdict(list)
    input_files: dict[float, list[str]] = defaultdict(list)
    for path in args.inputs:
        payload = json.loads(path.read_text())
        if payload.get("uses_target_a_or_D") or payload.get("uses_target_trajectory"):
            raise ValueError(f"forbidden target dependency in {path}")
        if not payload["iteration"]["converged"]:
            raise ValueError(f"unconverged matrix fixed point in {path}")
        field = float(payload["regulator"]["field"])
        grouped[field].append(payload)
        input_files[field].append(str(path))
    fields = np.asarray(sorted(grouped, reverse=True))
    if fields.size < 5 or any(len(grouped[field]) < args.required_replicates for field in fields):
        raise ValueError("five fields with the required replicate count are needed")
    field_audit = _validate_field_audit(
        args.field_audit,
        inputs=list(args.inputs),
        fields=fields,
    )
    reference = grouped[float(fields[0])][0]
    scaled_times = np.asarray(reference["scaled_times_tau_equals_t_h3"])
    endpoint_index = int(np.argmin(np.abs(scaled_times - args.scaled_time)))
    if abs(scaled_times[endpoint_index] - args.scaled_time) > args.scaled_time_tolerance:
        raise ValueError("requested scaled time is absent from the input grid")
    reference_waves = np.asarray(reference["scaled_waves_q_equals_k_over_h2"])
    field_replicates = []
    q = None
    for field in fields:
        rows = []
        for payload in grouped[float(field)]:
            if not np.allclose(payload["scaled_times_tau_equals_t_h3"], scaled_times):
                raise ValueError("scaled-time grid mismatch")
            if not np.allclose(payload["scaled_waves_q_equals_k_over_h2"], reference_waves):
                raise ValueError("scaled-wave grid mismatch")
            q_row, structure_row = _positive_even_grid(
                reference_waves, _structure(payload)[:, endpoint_index]
            )
            if q is None:
                q = q_row
            elif not np.allclose(q, q_row):
                raise ValueError("positive Fourier grid mismatch")
            rows.append(structure_row)
        field_replicates.append(np.asarray(rows))
    assert q is not None
    field_replicates_array = np.asarray(field_replicates)
    field_means = np.mean(field_replicates_array, axis=1)

    projection_kwargs = dict(
        length=args.length,
        profile_start=args.profile_start,
        profile_stop=args.profile_stop,
        dt=args.dt,
        fit_start=args.fit_start,
        fit_stop=args.fit_stop,
        x_crop=tuple(args.x_crop),
        y_maximum=args.y_maximum,
        y_points=args.y_points,
    )
    scheme_rows = {}
    for degree in DEGREES:
        design = np.column_stack(
            [fields**power for power in range(degree + 1)]
        )
        coefficients = np.linalg.pinv(design) @ field_means
        scheme_rows[str(degree)] = _project_structure(
            q, coefficients[0], **projection_kwargs
        )

    rng = np.random.default_rng(args.bootstrap_seed)
    bootstrap = {str(degree): [] for degree in DEGREES}
    for _ in range(args.bootstrap_replicates):
        sampled_means = []
        for rows in field_replicates_array:
            indices = rng.integers(0, rows.shape[0], size=rows.shape[0])
            sampled_means.append(np.mean(rows[indices], axis=0))
        sampled_means_array = np.asarray(sampled_means)
        for degree in DEGREES:
            design = np.column_stack(
                [fields**power for power in range(degree + 1)]
            )
            structure = (np.linalg.pinv(design) @ sampled_means_array)[0]
            try:
                projected = _project_structure(q, structure, **projection_kwargs)
            except ValueError:
                continue
            bootstrap[str(degree)].append([projected["a"], projected["D"]])
    bootstrap_rows = {}
    all_pairs = []
    for power, pairs in bootstrap.items():
        values = np.asarray(pairs)
        if values.size == 0:
            bootstrap_rows[power] = {"valid_replicates": 0}
            continue
        all_pairs.append(values)
        bootstrap_rows[power] = {
            "valid_replicates": int(values.shape[0]),
            "a_percentiles_2p5_50_97p5": np.percentile(values[:, 0], [2.5, 50, 97.5]).tolist(),
            "D_percentiles_2p5_50_97p5": np.percentile(values[:, 1], [2.5, 50, 97.5]).tolist(),
        }
    deterministic_pairs = np.asarray([[row["a"], row["D"]] for row in scheme_rows.values()])
    a_envelope = [float(np.min(deterministic_pairs[:, 0])), float(np.max(deterministic_pairs[:, 0]))]
    d_envelope = [float(np.min(deterministic_pairs[:, 1])), float(np.max(deterministic_pairs[:, 1]))]
    a_midpoint = 0.5 * sum(a_envelope)
    d_midpoint = 0.5 * sum(d_envelope)
    a_relative_width = (a_envelope[1] - a_envelope[0]) / max(abs(a_midpoint), np.finfo(float).tiny)
    d_relative_width = (d_envelope[1] - d_envelope[0]) / max(abs(d_midpoint), np.finfo(float).tiny)
    valid_bootstrap_fraction = min(
        (row.get("valid_replicates", 0) / max(args.bootstrap_replicates, 1))
        for row in bootstrap_rows.values()
    )
    maximum_fourier_tail = max(abs(float(row["fourier_tail_at_qmax"])) for row in scheme_rows.values())
    weak_strong_relative_differences = {
        observable: max(
            float(row["weak_strong_absolute_difference"][observable])
            / max(
                abs(float(row[observable])),
                abs(float(row["analytic_selfsimilar_strong_projection"][observable])),
                np.finfo(float).tiny,
            )
            for row in scheme_rows.values()
        )
        for observable in ("a", "D")
    }
    identified = bool(
        args.bootstrap_replicates > 0
        and valid_bootstrap_fraction >= args.minimum_valid_bootstrap_fraction
        and maximum_fourier_tail <= args.maximum_fourier_tail
        and a_relative_width <= args.maximum_relative_scheme_width
        and d_relative_width <= args.maximum_relative_scheme_width
        and weak_strong_relative_differences["a"] <= args.maximum_relative_projection_disagreement
        and weak_strong_relative_differences["D"] <= args.maximum_relative_projection_disagreement
    )
    return {
        "schema": 1,
        "method": "matched_integer_zero_field_full_matrix_wall_projection",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "microscopic_inputs": {
            "D0": float(EXACT_D0_INFINITY_T),
            "chi": 0.25,
            "scaled_time": float(scaled_times[endpoint_index]),
        },
        "fields_descending": fields.tolist(),
        "replicates_per_field": [len(grouped[float(field)]) for field in fields],
        "input_files_by_field": {str(key): value for key, value in input_files.items()},
        "input_sha256_by_file": {
            str(path): _sha256(path) for path in args.inputs
        },
        "matched_integer_field_audit": {
            "path": str(args.field_audit),
            "sha256": _sha256(args.field_audit),
            "accepted": bool(field_audit["matched_integer_field_limit_accepted"]),
            "degrees": list(DEGREES),
        },
        "positive_q_grid": q.tolist(),
        "integer_degree_projections": scheme_rows,
        "bootstrap_by_integer_degree": bootstrap_rows,
        "deterministic_scheme_envelope": {
            "a": a_envelope,
            "D": d_envelope,
            "a_relative_width": float(a_relative_width),
            "D_relative_width": float(d_relative_width),
        },
        "identification_gate": {
            "maximum_relative_scheme_width": args.maximum_relative_scheme_width,
            "maximum_fourier_tail": args.maximum_fourier_tail,
            "observed_maximum_fourier_tail": maximum_fourier_tail,
            "minimum_valid_bootstrap_fraction": args.minimum_valid_bootstrap_fraction,
            "observed_minimum_valid_bootstrap_fraction": valid_bootstrap_fraction,
            "maximum_relative_projection_disagreement": args.maximum_relative_projection_disagreement,
            "observed_maximum_relative_projection_disagreement": weak_strong_relative_differences,
            "accepted": identified,
        },
        "physical_a_or_D_identified": identified,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--field-audit", required=True, type=Path)
    parser.add_argument("--scaled-time", type=float, default=27 / (10 * np.pi))
    parser.add_argument("--scaled-time-tolerance", type=float, default=1e-10)
    parser.add_argument("--required-replicates", type=int, default=4)
    parser.add_argument("--bootstrap-replicates", type=int, default=128)
    parser.add_argument("--bootstrap-seed", type=int, default=265)
    parser.add_argument("--maximum-relative-scheme-width", type=float, default=0.1)
    parser.add_argument("--maximum-fourier-tail", type=float, default=1e-2)
    parser.add_argument("--minimum-valid-bootstrap-fraction", type=float, default=0.9)
    parser.add_argument("--maximum-relative-projection-disagreement", type=float, default=0.1)
    parser.add_argument("--length", type=int, default=400)
    parser.add_argument("--profile-start", type=float, default=50.0)
    parser.add_argument("--profile-stop", type=float, default=200.0)
    parser.add_argument("--dt", type=float, default=0.2)
    parser.add_argument("--fit-start", type=float, default=52.0)
    parser.add_argument("--fit-stop", type=float, default=198.0)
    parser.add_argument("--x-crop", nargs=2, type=float, default=[-120, 120])
    parser.add_argument("--y-maximum", type=float, default=18.0)
    parser.add_argument("--y-points", type=int, default=3601)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = derive(args)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
