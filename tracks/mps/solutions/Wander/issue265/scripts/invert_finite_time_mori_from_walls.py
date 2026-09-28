#!/usr/bin/env python3
"""Invert the finite-time KPZ correction from converged opposite weak walls.

The program accepts only validated first-principles spin datasets and the
stationary-KPZ table.  It does not accept Burgers coefficients.  Opposite wall
orientations cancel the leading finite-amplitude even response; deconvolution
of the known initial wall gives the normalized structure factor, from which
``F1`` is separated into dilation and non-dilation components.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.interpolate import CubicSpline
from scipy.signal import savgol_filter


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.derive_kpz_lanczos_terminator import _load_table  # noqa: E402
from src.finite_time_mori_inversion import (  # noqa: E402
    cross_validate_finite_time_structure,
    decompose_dilation_correction,
    finite_q_mori_k0_correction,
    finite_time_structure_correction,
    local_current_vertex,
    opposite_wall_linear_response,
    structure_factor_from_wall,
)
from src.heisenberg_burgers_bridge import kpz_lambda_from_tba  # noqa: E402
from src.research_dataset import load_research_dataset  # noqa: E402
from src.tension_resolution import fit_profiled_weak  # noqa: E402


def _kpz_fourier_splines(table: np.ndarray, q_max: float = 8.0) -> tuple[CubicSpline, CubicSpline]:
    spline = CubicSpline(table[:, 0], table[:, 1])
    nodes, weights = leggauss(900)
    y_max = float(table[-1, 0])
    y = 0.5 * y_max * (nodes + 1.0)
    y_weight = 0.5 * y_max * weights
    density_weight = y_weight * spline(y, 2) / 4.0
    q = np.linspace(0.0, q_max, 2001)
    transform = 2.0 * (np.cos(np.outer(q, y)) @ density_weight)
    derivative = -2.0 * (np.sin(np.outer(q, y)) @ (y * density_weight))
    return CubicSpline(q, transform), CubicSpline(q, derivative)


def _require_gate(path: Path, up_id: str, down_id: str) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    encoded = json.dumps(payload, sort_keys=True)
    if bool(payload.get("convergence_accepted")):
        if up_id not in encoded or down_id not in encoded:
            raise RuntimeError("validation does not cover both requested datasets")
        return
    if not (
        payload.get("status") == "complete"
        and payload.get("all_complete") is True
        and payload.get("submission_complete") is True
    ):
        raise RuntimeError("neither convergence nor Production A is complete")
    rows = payload.get("jobs", [])
    covered: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or row.get("status") != "complete":
            continue
        job = row.get("job", {})
        condition_id = str(
            job.get("condition_id", row.get("condition_id", ""))
        ) if isinstance(job, dict) else str(row.get("condition_id", ""))
        validation = row.get("validation", {})
        if condition_id and isinstance(validation, dict) and validation.get("status") == "valid":
            covered.add(condition_id)
    missing = sorted({up_id, down_id} - covered)
    if missing:
        raise RuntimeError(
            "Production A has no completed valid output for: " + ", ".join(missing)
        )


def derive(
    up_path: Path,
    down_path: Path,
    table: np.ndarray,
    *,
    mode_indices: list[int],
    t_window: tuple[float, float],
    q_max: float,
    fit_window: tuple[float, float] = (52.0, 198.0),
    x_crop: tuple[float, float] = (-120.0, 120.0),
) -> dict[str, object]:
    up = load_research_dataset(up_path)
    down = load_research_dataset(down_path)
    if not np.array_equal(up.x, down.x) or not np.array_equal(up.t, down.t):
        raise ValueError("opposite-wall datasets must have identical grids")
    shared_keys = ("delta", "J", "J2", "temperature", "mu", "profile", "width", "L")
    mismatches = [key for key in shared_keys if up.metadata.get(key) != down.metadata.get(key)]
    if mismatches:
        raise ValueError("opposite-wall metadata mismatch: " + ", ".join(mismatches))
    if int(up.metadata.get("orientation")) != 1 or int(down.metadata.get("orientation")) != -1:
        raise ValueError("expected up orientation +1 and down orientation -1")
    mu = float(up.metadata["mu"])
    wall = opposite_wall_linear_response(up.u, down.u) * mu / np.tanh(mu)
    k, structure = structure_factor_from_wall(up.x, up.t, wall, np.asarray(mode_indices))
    leading, leading_derivative = _kpz_fourier_splines(table, q_max=max(8.0, q_max + 0.5))
    finite = finite_time_structure_correction(
        k,
        up.t,
        structure,
        leading,
        lambda_kpz=kpz_lambda_from_tba(),
        t_window=t_window,
    )
    selected = finite.q <= q_max
    decomposition = decompose_dilation_correction(
        finite.q[selected], finite.correction[selected], leading_derivative
    )
    laplace_grid = np.asarray([0.5, 0.75, 1.0, 1.5, 2.0])
    total_mori = finite_q_mori_k0_correction(
        finite.q[selected],
        finite.correction[selected],
        leading,
        lambda_kpz=kpz_lambda_from_tba(),
        s_values=laplace_grid,
        q_max=q_max,
    )
    perpendicular_mori = finite_q_mori_k0_correction(
        finite.q[selected],
        np.asarray(decomposition["perpendicular"]),
        leading,
        lambda_kpz=kpz_lambda_from_tba(),
        s_values=laplace_grid,
        q_max=q_max,
    )
    split = t_window[0] + 0.48 * (t_window[1] - t_window[0])
    gap = float(np.median(np.diff(up.t)))
    time_cross_validation = cross_validate_finite_time_structure(
        k,
        up.t,
        structure,
        leading,
        lambda_kpz=kpz_lambda_from_tba(),
        train_window=(t_window[0], split),
        test_window=(split + gap, t_window[1]),
        q_max=q_max,
    )
    smoothed_wall = savgol_filter(
        wall, window_length=31, polyorder=7, axis=1, mode="interp"
    )
    weak = fit_profiled_weak(
        up.x,
        up.t,
        smoothed_wall,
        t_window=fit_window,
        x_crop=x_crop,
        gamma=0.0,
    )
    current_vertices = None
    if up.current is not None and down.current is not None:
        up_vertex = local_current_vertex(
            up.x, up.t, up.u, up.current,
            mu=mu, orientation=1, t_window=t_window, x_crop=x_crop,
        )
        down_vertex = local_current_vertex(
            down.x, down.t, down.u, down.current,
            mu=mu, orientation=-1, t_window=t_window, x_crop=x_crop,
        )
        current_vertices = {
            "up": up_vertex,
            "down": down_vertex,
            "orientation_average_a": 0.5
            * (up_vertex["a_current_vertex"] + down_vertex["a_current_vertex"]),
            "orientation_half_difference_a": 0.5
            * abs(up_vertex["a_current_vertex"] - down_vertex["a_current_vertex"]),
            "interpretation": (
                "a is the instantaneous quadratic current vertex; "
                "D_instantaneous_local is not the zero-frequency Mori coefficient"
            ),
        }
    perpendicular = np.asarray(decomposition["perpendicular"])
    q = finite.q[selected]
    edges = np.linspace(float(np.min(q)), float(np.max(q)), 17)
    bins: list[dict[str, float | int]] = []
    for left, right in zip(edges[:-1], edges[1:], strict=True):
        mask = (q >= left) & (q < right if right < edges[-1] else q <= right)
        if np.any(mask):
            bins.append(
                {
                    "q": float(np.mean(q[mask])),
                    "F1_perp": float(np.mean(perpendicular[mask])),
                    "standard_deviation": float(np.std(perpendicular[mask], ddof=1))
                    if np.count_nonzero(mask) > 1
                    else 0.0,
                    "count": int(np.count_nonzero(mask)),
                }
            )
    return {
        "schema": 1,
        "inputs": {
            "up": str(up_path),
            "down": str(down_path),
            "up_condition_id": up.condition_id,
            "down_condition_id": down.condition_id,
            "mode_indices": mode_indices,
            "t_window": list(t_window),
            "q_max": q_max,
            "fit_window": list(fit_window),
            "x_crop": list(x_crop),
            "mu": mu,
            "up_orientation": 1,
            "down_orientation": -1,
            "known_finite_mu_plateau_factor": mu / np.tanh(mu),
            "target_coefficients_used": False,
        },
        "kpz_lambda": kpz_lambda_from_tba(),
        "dilation_coefficient": float(decomposition["dilation_coefficient"]),
        "relative_F1_perp_norm": float(decomposition["relative_perpendicular_norm"]),
        "mori_k0_correction": {
            "s": total_mori["s"].tolist(),
            "delta_K1_total_truncated": total_mori["delta_K1_truncated"].tolist(),
            "delta_K1_perpendicular_truncated": perpendicular_mori[
                "delta_K1_truncated"
            ].tolist(),
            "Phi0_truncated": total_mori["Phi0_truncated"].tolist(),
            "Phi1_total_truncated": total_mori["Phi1_truncated"].tolist(),
            "tail_exponential_weight": total_mori[
                "tail_exponential_weight"
            ].tolist(),
            "q_max": float(total_mori["q_max"]),
            "n_input_samples": int(total_mori["n_input_samples"]),
            "n_nonempty_bins": int(total_mori["n_nonempty_bins"]),
        },
        "finite_time_structure_cross_validation": {
            "train_window": [t_window[0], split],
            "test_window": [split + gap, t_window[1]],
            **time_cross_validation,
        },
        "frozen_weak_projection": {
            "a": float(weak.a),
            "D": float(weak.D0),
            "mse": float(weak.mse),
            "n_obs": int(weak.n_obs),
        },
        "microscopic_current_vertex": current_vertices,
        "F1_perp_bins": bins,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--up", type=Path, required=True)
    parser.add_argument("--down", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--kpz-table", type=Path)
    parser.add_argument("--modes", type=int, nargs="+", default=list(range(1, 9)))
    parser.add_argument("--t-start", type=float, default=50.0)
    parser.add_argument("--t-stop", type=float, default=200.0)
    parser.add_argument("--q-max", type=float, default=5.0)
    parser.add_argument("--fit-start", type=float, default=52.0)
    parser.add_argument("--fit-stop", type=float, default=198.0)
    parser.add_argument("--x-crop", type=float, nargs=2, default=[-120.0, 120.0])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    up = load_research_dataset(args.up)
    down = load_research_dataset(args.down)
    _require_gate(args.validation, up.condition_id, down.condition_id)
    result = derive(
        args.up,
        args.down,
        _load_table(args.kpz_table),
        mode_indices=args.modes,
        t_window=(args.t_start, args.t_stop),
        q_max=args.q_max,
        fit_window=(args.fit_start, args.fit_stop),
        x_crop=(float(args.x_crop[0]), float(args.x_crop[1])),
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")


if __name__ == "__main__":
    main()
