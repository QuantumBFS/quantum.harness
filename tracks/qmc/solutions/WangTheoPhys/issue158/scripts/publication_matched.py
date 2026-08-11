#!/usr/bin/env python3
"""Post-lock audit of the exact published shifted-log and residual ansatz."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import minimize, minimize_scalar
from scipy.stats import chi2 as chi2_dist

from extended_analysis import (
    P_MAX,
    P_MIN,
    fit_scalar,
    information_criteria,
    load_data,
    primary_data,
    weighted_linear,
)


def fit_ordered_shift(
    L: np.ndarray, y: np.ndarray, se: np.ndarray
) -> dict:
    logL = np.log(L)
    upper = float(logL.min() - 0.1)

    def solve(logL0: float):
        ell = logL - logL0
        return weighted_linear(
            np.column_stack([np.ones_like(ell), ell**-1]), y, se
        )

    grid = np.linspace(-20.0, upper, 301)
    vals = np.asarray([solve(point)[0] for point in grid])
    j = int(np.argmin(vals))
    lo, hi = grid[max(0, j - 1)], grid[min(len(grid) - 1, j + 1)]
    opt = minimize_scalar(
        lambda point: solve(float(point))[0],
        bounds=(float(lo), float(hi)),
        method="bounded",
        options={"xatol": 1e-11, "maxiter": 300},
    )
    logL0 = float(opt.x) if opt.success else float(grid[j])
    chi2, coef, _, pred = solve(logL0)
    n, k = len(y), 3
    dof = n - k
    aicc, bic = information_criteria(chi2, n, k)
    return {
        "kind": "OP",
        "n": n,
        "k": k,
        "chi2": chi2,
        "dof": dof,
        "reduced_chi2": chi2 / dof,
        "gof_p": float(chi2_dist.sf(chi2, dof)),
        "aicc": aicc,
        "bic": bic,
        "g0": float(coef[0]),
        "a": float(coef[1]),
        "logL0": logL0,
        "L0": math.exp(logL0),
        "prediction": pred.tolist(),
    }


def fit_decaying_shift(
    L: np.ndarray, y: np.ndarray, se: np.ndarray
) -> dict:
    logL = np.log(L)
    upper_l0 = float(logL.min() - 0.1)
    q_bounds = (math.log(P_MIN), math.log(P_MAX))
    l0_bounds = (-20.0, upper_l0)

    def solve(q: float, logL0: float):
        p = math.exp(q)
        ell = logL - logL0
        if np.any(ell <= 0):
            return 1e300, np.array([float("nan")]), np.array([]), np.array([])
        return weighted_linear(ell[:, None] ** (-p), y, se)

    q_grid = np.linspace(q_bounds[0], q_bounds[1], 35)
    l0_grid = np.linspace(l0_bounds[0], l0_bounds[1], 45)
    best = (1e300, q_grid[0], l0_grid[0])
    for q in q_grid:
        for logL0 in l0_grid:
            value = solve(float(q), float(logL0))[0]
            if value < best[0]:
                best = (value, float(q), float(logL0))

    opt = minimize(
        lambda z: solve(float(z[0]), float(z[1]))[0],
        x0=np.array(best[1:]),
        method="Powell",
        bounds=[q_bounds, l0_bounds],
        options={
            "ftol": 1e-13,
            "xtol": 1e-11,
            "maxiter": 2000,
        },
    )
    optimized_value = (
        solve(float(opt.x[0]), float(opt.x[1]))[0]
        if opt.success
        else float("inf")
    )
    q, logL0 = (
        (float(opt.x[0]), float(opt.x[1]))
        if optimized_value <= best[0]
        else (best[1], best[2])
    )
    chi2, coef, _, pred = solve(q, logL0)
    p = math.exp(q)
    n, k = len(y), 3
    dof = n - k
    aicc, bic = information_criteria(chi2, n, k)
    return {
        "kind": "DP",
        "n": n,
        "k": k,
        "chi2": chi2,
        "dof": dof,
        "reduced_chi2": chi2 / dof,
        "gof_p": float(chi2_dist.sf(chi2, dof)),
        "aicc": aicc,
        "bic": bic,
        "A": float(coef[0]),
        "p": p,
        "logL0": logL0,
        "L0": math.exp(logL0),
        "prediction": pred.tolist(),
    }


def predict_shift(result: dict, L: np.ndarray) -> np.ndarray:
    ell = np.log(L) - result["logL0"]
    if result["kind"] == "OP":
        return result["g0"] + result["a"] / ell
    return result["A"] * ell ** (-result["p"])


def heldout(kind: str, L, y, se, drop: int) -> dict | None:
    if len(L) - drop <= 4:
        return None
    fit = (
        fit_ordered_shift(L[:-drop], y[:-drop], se[:-drop])
        if kind == "OP"
        else fit_decaying_shift(L[:-drop], y[:-drop], se[:-drop])
    )
    prediction = predict_shift(fit, L[-drop:])
    z = (prediction - y[-drop:]) / se[-drop:]
    return {
        "drop": drop,
        "L": L[-drop:].tolist(),
        "z": z.tolist(),
        "rms_z": float(np.sqrt(np.mean(z**2))),
    }


def source_matched_windows(raw, names) -> list[dict]:
    out = []
    for beta in [1, 2, 4, 8]:
        data = primary_data(raw, names, beta, "M2", "M2_err")
        for Lmin in [16, 32, 48, 64, 96, 128, 192, 256, 384, 512]:
            selected = data[data[:, 0] >= Lmin]
            if len(selected) < 6:
                continue
            L, y, se = selected[:, :3].T
            op = fit_ordered_shift(L, y, se)
            dp = fit_decaying_shift(L, y, se)
            for model in [op, dp]:
                model["heldout"] = [
                    h
                    for drop in [1, 2]
                    if (h := heldout(model["kind"], L, y, se, drop))
                    is not None
                ]
            out.append(
                {
                    "beta": beta,
                    "Lmin": Lmin,
                    "Lmax": int(L.max()),
                    "ordered_shift": op,
                    "decaying_shift": dp,
                    "delta_AICc_ordered_minus_decaying": (
                        op["aicc"] - dp["aicc"]
                    ),
                }
            )
    return out


def reported_l0_reproduction(raw, names) -> list[dict]:
    reported = {1: -5.4, 2: -6.8, 4: -6.38, 8: -6.2}
    out = []
    for beta, logL0 in reported.items():
        data = primary_data(raw, names, beta, "M2", "M2_err")
        data = data[data[:, 0] >= 64]
        L, y, se = data[:, :3].T
        ell = np.log(L) - logL0
        chi2, coef, _, _ = weighted_linear(
            np.column_stack([np.ones_like(ell), ell**-1]), y, se
        )
        dof = len(L) - 3
        out.append(
            {
                "beta": beta,
                "Lmin": 64,
                "reported_logL0": logL0,
                "reported_L0": math.exp(logL0),
                "g0": float(coef[0]),
                "a": float(coef[1]),
                "chi2": chi2,
                "dof_counting_fitted_L0": dof,
                "reduced_chi2": chi2 / dof,
                "gof_p": float(chi2_dist.sf(chi2, dof)),
            }
        )
    return out


def residual_sensitivity(raw, names) -> list[dict]:
    b_values = {1: 149.0, 2: 175.0, 4: 152.0, 8: 154.0}
    out = []
    for beta, b in b_values.items():
        m2 = primary_data(raw, names, beta, "M2", "M2_err")
        m2k = primary_data(
            raw, names, beta, "M2_k_min", "M2_k_min_err"
        )
        common = np.intersect1d(m2[:, 0], m2k[:, 0])
        common = common[common >= 64]
        m2 = np.asarray([m2[m2[:, 0] == size][0] for size in common])
        m2k = np.asarray([m2k[m2k[:, 0] == size][0] for size in common])
        residual = m2[:, 1] - b * m2k[:, 1]
        p_shared = fit_scalar(
            "D2", m2[:, 0], m2[:, 1], m2[:, 2]
        )["p"]
        ell = np.log(common)
        for rho in np.linspace(-0.8, 0.8, 9):
            se = np.sqrt(
                m2[:, 2] ** 2
                + b**2 * m2k[:, 2] ** 2
                - 2 * b * rho * m2[:, 2] * m2k[:, 2]
            )
            design_ordered = np.column_stack(
                [np.ones_like(common), common ** (-0.4)]
            )
            design_decay = np.column_stack(
                [ell ** (-p_shared), ell ** (-p_shared - 1)]
            )
            chi_o, coef_o, _, _ = weighted_linear(
                design_ordered, residual, se
            )
            chi_d, coef_d, _, _ = weighted_linear(
                design_decay, residual, se
            )
            n, k = len(common), 2
            dof = n - k
            aicc_o, _ = information_criteria(chi_o, n, k)
            aicc_d, _ = information_criteria(chi_d, n, k)
            out.append(
                {
                    "beta": beta,
                    "b": b,
                    "rho": float(rho),
                    "Lmin": 64,
                    "Lmax": int(common.max()),
                    "p_shared_from_M2": p_shared,
                    "ordered_g0": float(coef_o[0]),
                    "ordered_chi2": chi_o,
                    "ordered_reduced_chi2": chi_o / dof,
                    "decaying_chi2": chi_d,
                    "decaying_reduced_chi2": chi_d / dof,
                    "delta_AICc_ordered_minus_decaying": aicc_o - aicc_d,
                    "residual_at_smallest_L": float(residual[0]),
                    "residual_at_largest_L": float(residual[-1]),
                    "warning": (
                        "b uncertainty omitted; rho is assumed, not measured."
                    ),
                }
            )
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    names, raw = load_data(args.data)
    windows = source_matched_windows(raw, names)
    reported = reported_l0_reproduction(raw, names)
    residual = residual_sensitivity(raw, names)
    payload = {
        "source": str(args.data),
        "status": "post-lock/source-matched addendum",
        "source_matched_windows": windows,
        "reported_L0_reproduction_at_Lmin64": reported,
        "residual_magnetization_sensitivity": residual,
    }
    (args.out_dir / "publication_matched_results.json").write_text(
        json.dumps(payload, indent=2)
    )

    window_rows = []
    for row in windows:
        for name in ["ordered_shift", "decaying_shift"]:
            model = row[name]
            window_rows.append(
                {
                    "beta": row["beta"],
                    "Lmin": row["Lmin"],
                    "Lmax": row["Lmax"],
                    "model": model["kind"],
                    "chi2": model["chi2"],
                    "dof": model["dof"],
                    "reduced_chi2": model["reduced_chi2"],
                    "gof_p": model["gof_p"],
                    "AICc": model["aicc"],
                    "delta_AICc_OP_minus_DP": row[
                        "delta_AICc_ordered_minus_decaying"
                    ],
                    "g0": model.get("g0"),
                    "p": model.get("p"),
                    "logL0": model["logL0"],
                    "L0": model["L0"],
                    "heldout1_rms_z": (
                        model["heldout"][0]["rms_z"]
                        if model["heldout"]
                        else None
                    ),
                    "heldout2_rms_z": (
                        model["heldout"][1]["rms_z"]
                        if len(model["heldout"]) > 1
                        else None
                    ),
                }
            )
    write_csv(args.out_dir / "publication_matched_windows.csv", window_rows)
    write_csv(args.out_dir / "reported_L0_reproduction.csv", reported)
    write_csv(args.out_dir / "residual_magnetization_sensitivity.csv", residual)


if __name__ == "__main__":
    main()
