#!/usr/bin/env python3
"""Locked public-data analysis for quantum.harness Issue #158.

The script implements the protocol in ``../ANALYSIS_PROTOCOL.md``.
It deliberately keeps the scalar and covariance-sensitivity conclusions
separate because synchronized bin-level covariance is not public.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Callable

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import chi2 as chi2_dist


P_MIN = 1e-5
P_MAX = 2.0


def load_data(path: Path) -> tuple[list[str], np.ndarray]:
    names = path.read_text().splitlines()[1].lstrip("#").split()
    data = np.genfromtxt(path, comments="#")
    return names, data


def primary_data(
    raw: np.ndarray,
    names: list[str],
    beta: float,
    value: str,
    error: str,
) -> np.ndarray:
    """Select the largest-N_sample row at each size.

    Extra L=512 replicas are reserved for the covariance audit and are not
    combined into the primary scalar series.
    """
    ix = {name: i for i, name in enumerate(names)}
    rows = raw[
        np.isclose(raw[:, ix["sigma"]], 2.0)
        & np.isclose(raw[:, ix["T"]], 1.0 / beta)
    ]
    out: list[list[float]] = []
    for L in np.unique(rows[:, ix["L"]]):
        group = rows[rows[:, ix["L"]] == L]
        ok = (
            np.isfinite(group[:, ix[value]])
            & np.isfinite(group[:, ix[error]])
            & (group[:, ix[error]] > 0)
        )
        group = group[ok]
        if not len(group):
            continue
        max_samples = np.max(group[:, ix["N_sample"]])
        candidates = group[group[:, ix["N_sample"]] == max_samples]
        row = candidates[np.argmin(candidates[:, ix[error]])]
        out.append(
            [
                float(L),
                float(row[ix[value]]),
                float(row[ix[error]]),
                float(row[ix["seed"]]),
                float(row[ix["N_sample"]]),
            ]
        )
    return np.asarray(sorted(out, key=lambda r: r[0]), dtype=float)


def weighted_linear(
    design: np.ndarray, y: np.ndarray, se: np.ndarray
) -> tuple[float, np.ndarray, np.ndarray, np.ndarray]:
    xw = design / se[:, None]
    yw = y / se
    coef, _, _, _ = np.linalg.lstsq(xw, yw, rcond=None)
    pred = design @ coef
    resid = (y - pred) / se
    chi2 = float(resid @ resid)
    info = xw.T @ xw
    cov = np.linalg.pinv(info, rcond=1e-13)
    return chi2, coef, cov, pred


def profile_power(
    design_at_p: Callable[[float], np.ndarray],
    y: np.ndarray,
    se: np.ndarray,
) -> tuple[float, float, np.ndarray, np.ndarray, np.ndarray]:
    """Profile a positive exponent on a log grid, then refine continuously."""

    def objective(q: float) -> float:
        p = math.exp(q)
        design = design_at_p(p)
        val, coef, _, _ = weighted_linear(design, y, se)
        if not np.isfinite(val) or coef[0] <= 0:
            return 1e300
        return val

    q_grid = np.linspace(math.log(P_MIN), math.log(P_MAX), 41)
    vals = np.asarray([objective(q) for q in q_grid])
    j = int(np.argmin(vals))
    lo = q_grid[max(0, j - 1)]
    hi = q_grid[min(len(q_grid) - 1, j + 1)]
    if lo == hi:
        q_best = q_grid[j]
    else:
        opt = minimize_scalar(
            objective,
            method="bounded",
            bounds=(float(lo), float(hi)),
            options={"xatol": 1e-10, "maxiter": 200},
        )
        q_best = float(opt.x) if opt.success else float(q_grid[j])
    p_best = math.exp(q_best)
    design = design_at_p(p_best)
    chi2, coef, cov, pred = weighted_linear(design, y, se)
    return chi2, p_best, coef, cov, pred


def information_criteria(chi2: float, n: int, k: int) -> tuple[float, float]:
    aic = chi2 + 2 * k
    aicc = (
        aic + 2 * k * (k + 1) / (n - k - 1)
        if n > k + 1
        else float("inf")
    )
    bic = chi2 + k * math.log(n)
    return float(aicc), float(bic)


def fit_scalar(
    kind: str, L: np.ndarray, y: np.ndarray, se: np.ndarray
) -> dict:
    ell = np.log(L)
    if kind == "O1":
        design = np.column_stack([np.ones_like(ell), ell**-1])
        chi2, coef, cov, pred = weighted_linear(design, y, se)
        p = None
        k = 2
    elif kind == "O2":
        design = np.column_stack(
            [np.ones_like(ell), ell**-1, ell**-2]
        )
        chi2, coef, cov, pred = weighted_linear(design, y, se)
        p = None
        k = 3
    elif kind == "D1":
        chi2, p, coef, cov, pred = profile_power(
            lambda exponent: ell[:, None] ** (-exponent), y, se
        )
        k = 2
    elif kind == "D2":
        chi2, p, coef, cov, pred = profile_power(
            lambda exponent: np.column_stack(
                [ell ** (-exponent), ell ** (-exponent - 1)]
            ),
            y,
            se,
        )
        k = 3
    else:
        raise ValueError(kind)

    n = len(y)
    dof = n - k
    aicc, bic = information_criteria(chi2, n, k)
    reduced = chi2 / dof if dof > 0 else float("nan")
    result = {
        "kind": kind,
        "n": n,
        "k": k,
        "chi2": chi2,
        "dof": dof,
        "reduced_chi2": reduced,
        "gof_p": float(chi2_dist.sf(chi2, dof)) if dof > 0 else None,
        "aicc": aicc,
        "bic": bic,
        "coefficients": coef.tolist(),
        "prediction": pred.tolist(),
        "p": p,
    }
    if kind.startswith("O"):
        g0_se = math.sqrt(max(0.0, float(cov[0, 0])))
        scale = math.sqrt(max(1.0, reduced)) if dof > 0 else float("nan")
        result.update(
            {
                "g0": float(coef[0]),
                "g0_se_nominal": g0_se,
                "g0_se_overdispersion": g0_se * scale,
                "g0_lower95_nominal": float(coef[0] - 1.96 * g0_se),
                "g0_lower95_overdispersion": float(
                    coef[0] - 1.96 * g0_se * scale
                ),
            }
        )
    return result


def predict_scalar(kind: str, result: dict, L: np.ndarray) -> np.ndarray:
    ell = np.log(L)
    coef = np.asarray(result["coefficients"])
    if kind == "O1":
        design = np.column_stack([np.ones_like(ell), ell**-1])
    elif kind == "O2":
        design = np.column_stack(
            [np.ones_like(ell), ell**-1, ell**-2]
        )
    elif kind == "D1":
        p = float(result["p"])
        design = ell[:, None] ** (-p)
    elif kind == "D2":
        p = float(result["p"])
        design = np.column_stack([ell**-p, ell ** (-p - 1)])
    else:
        raise ValueError(kind)
    return design @ coef


def heldout_scalar(
    kind: str, L: np.ndarray, y: np.ndarray, se: np.ndarray, drop: int
) -> dict | None:
    if len(L) - drop <= 4:
        return None
    fit = fit_scalar(kind, L[:-drop], y[:-drop], se[:-drop])
    prediction = predict_scalar(kind, fit, L[-drop:])
    z = (prediction - y[-drop:]) / se[-drop:]
    return {
        "drop": drop,
        "L": L[-drop:].tolist(),
        "prediction": prediction.tolist(),
        "observed": y[-drop:].tolist(),
        "z": z.tolist(),
        "rms_z": float(np.sqrt(np.mean(z**2))),
    }


def scalar_window_analysis(
    raw: np.ndarray, names: list[str]
) -> tuple[list[dict], list[dict]]:
    fits: list[dict] = []
    effective: list[dict] = []
    lmins = [16, 32, 48, 64, 96, 128, 192, 256, 384, 512]
    for beta in [1, 2, 4, 8]:
        data = primary_data(raw, names, beta, "M2", "M2_err")
        by_L = {int(row[0]): row for row in data}
        for L1 in sorted(by_L):
            L2 = 2 * L1
            if L2 not in by_L:
                continue
            r1, r2 = by_L[L1], by_L[L2]
            denominator = math.log(math.log(L2) / math.log(L1))
            p_eff = -math.log(r2[1] / r1[1]) / denominator
            p_se = (
                math.sqrt((r1[2] / r1[1]) ** 2 + (r2[2] / r2[1]) ** 2)
                / denominator
            )
            effective.append(
                {
                    "beta": beta,
                    "L1": L1,
                    "L2": L2,
                    "p_eff": p_eff,
                    "p_eff_se": p_se,
                }
            )
        for Lmin in lmins:
            selected = data[data[:, 0] >= Lmin]
            if len(selected) < 6:
                continue
            L, y, se = selected[:, :3].T
            models = []
            for kind in ["O1", "D1", "O2", "D2"]:
                result = fit_scalar(kind, L, y, se)
                result["heldout"] = [
                    h
                    for drop in [1, 2]
                    if (h := heldout_scalar(kind, L, y, se, drop))
                    is not None
                ]
                models.append(result)
            fits.append(
                {
                    "beta": beta,
                    "Lmin": Lmin,
                    "Lmax": int(L.max()),
                    "sizes": L.tolist(),
                    "models": models,
                }
            )
    return fits, effective


def joint_whitened_system(
    kind: str,
    p: float | None,
    L: np.ndarray,
    d0: np.ndarray,
    dk: np.ndarray,
    rho: float,
) -> tuple[np.ndarray, np.ndarray]:
    ell = np.log(L)
    x_blocks: list[np.ndarray] = []
    y_blocks: list[np.ndarray] = []
    for i, log_size in enumerate(ell):
        if kind == "ordered":
            design = np.array(
                [
                    [1.0, log_size**-1, log_size**-2, 0.0, 0.0],
                    [0.0, 0.0, 0.0, log_size**-1, log_size**-2],
                ]
            )
        elif kind == "decaying":
            assert p is not None
            design = np.array(
                [
                    [
                        log_size**-p,
                        log_size ** (-p - 1),
                        0.0,
                        0.0,
                    ],
                    [
                        0.0,
                        0.0,
                        log_size ** (-p - 1),
                        log_size ** (-p - 2),
                    ],
                ]
            )
        else:
            raise ValueError(kind)
        s0, sk = d0[i, 2], dk[i, 2]
        covariance = np.array(
            [[s0 * s0, rho * s0 * sk], [rho * s0 * sk, sk * sk]]
        )
        chol = np.linalg.cholesky(covariance)
        x_blocks.append(np.linalg.solve(chol, design))
        y_blocks.append(
            np.linalg.solve(chol, np.array([d0[i, 1], dk[i, 1]]))
        )
    return np.vstack(x_blocks), np.concatenate(y_blocks)


def fit_joint(
    kind: str,
    L: np.ndarray,
    d0: np.ndarray,
    dk: np.ndarray,
    rho: float,
) -> dict:
    def solve(p: float | None) -> tuple[float, np.ndarray]:
        xw, yw = joint_whitened_system(kind, p, L, d0, dk, rho)
        coef, _, _, _ = np.linalg.lstsq(xw, yw, rcond=None)
        residual = yw - xw @ coef
        return float(residual @ residual), coef

    if kind == "ordered":
        chi2, coef = solve(None)
        p = None
    else:
        def objective(q: float) -> float:
            value, coef_q = solve(math.exp(q))
            return value if coef_q[0] > 0 else 1e300

        q_grid = np.linspace(math.log(P_MIN), math.log(P_MAX), 41)
        values = np.asarray([objective(q) for q in q_grid])
        j = int(np.argmin(values))
        lo = q_grid[max(0, j - 1)]
        hi = q_grid[min(len(q_grid) - 1, j + 1)]
        if lo == hi:
            q_best = float(q_grid[j])
        else:
            opt = minimize_scalar(
                objective,
                bounds=(float(lo), float(hi)),
                method="bounded",
                options={"xatol": 1e-10, "maxiter": 200},
            )
            q_best = float(opt.x) if opt.success else float(q_grid[j])
        p = math.exp(q_best)
        chi2, coef = solve(p)

    n = 2 * len(L)
    k = 5
    dof = n - k
    aicc, bic = information_criteria(chi2, n, k)
    return {
        "kind": kind,
        "rho": rho,
        "n": n,
        "k": k,
        "chi2": chi2,
        "dof": dof,
        "reduced_chi2": chi2 / dof,
        "gof_p": float(chi2_dist.sf(chi2, dof)),
        "aicc": aicc,
        "bic": bic,
        "p": p,
        "coefficients": coef.tolist(),
    }


def joint_sensitivity(raw: np.ndarray, names: list[str]) -> list[dict]:
    out: list[dict] = []
    for beta in [1, 2, 4, 8]:
        d0 = primary_data(raw, names, beta, "M2", "M2_err")
        dk = primary_data(raw, names, beta, "M2_k_min", "M2_k_min_err")
        common = np.intersect1d(d0[:, 0], dk[:, 0])
        common = common[common >= 64]
        d0 = np.asarray([d0[d0[:, 0] == L][0] for L in common])
        dk = np.asarray([dk[dk[:, 0] == L][0] for L in common])
        for rho in np.linspace(-0.8, 0.8, 9):
            ordered = fit_joint("ordered", common, d0, dk, float(rho))
            decaying = fit_joint("decaying", common, d0, dk, float(rho))
            out.append(
                {
                    "beta": beta,
                    "Lmin": 64,
                    "Lmax": int(common.max()),
                    "rho": float(rho),
                    "ordered": ordered,
                    "decaying": decaying,
                    "delta_aicc_ordered_minus_decaying": (
                        ordered["aicc"] - decaying["aicc"]
                    ),
                }
            )
    return out


def synthetic_identifiability(
    raw: np.ndarray,
    names: list[str],
    replicates: int,
    seed: int,
) -> list[dict]:
    rng = np.random.default_rng(seed)
    results: list[dict] = []
    for beta in [1, 2, 4, 8]:
        data = primary_data(raw, names, beta, "M2", "M2_err")
        data = data[data[:, 0] >= 64]
        L, observed, se = data[:, :3].T
        bases = {
            "O2": fit_scalar("O2", L, observed, se),
            "D2": fit_scalar("D2", L, observed, se),
        }
        for truth in ["O2", "D2"]:
            mu = predict_scalar(truth, bases[truth], L)
            deltas: list[float] = []
            g0_values: list[float] = []
            positive = nominal = scaled = 0
            ordered_gof = ordered_preferred = ordered_decisive = 0
            decay_preferred = decay_decisive = 0
            for _ in range(replicates):
                sample = mu + rng.normal(0.0, se)
                ordered = fit_scalar("O2", L, sample, se)
                decaying = fit_scalar("D2", L, sample, se)
                delta = ordered["aicc"] - decaying["aicc"]
                deltas.append(delta)
                if delta < 0:
                    ordered_preferred += 1
                if delta < -6:
                    ordered_decisive += 1
                if delta > 0:
                    decay_preferred += 1
                if delta > 6:
                    decay_decisive += 1
                if truth == "D2":
                    g0_values.append(ordered["g0"])
                    positive += ordered["g0"] > 0
                    nominal += ordered["g0_lower95_nominal"] > 0
                    scaled += ordered["g0_lower95_overdispersion"] > 0
                    ordered_gof += ordered["gof_p"] > 0.05
            row = {
                "beta": beta,
                "truth": truth,
                "replicates": replicates,
                "median_delta_aicc_ordered_minus_decaying": float(
                    np.median(deltas)
                ),
                "q05_delta_aicc": float(np.quantile(deltas, 0.05)),
                "q95_delta_aicc": float(np.quantile(deltas, 0.95)),
                "ordered_preferred_rate": ordered_preferred / replicates,
                "ordered_decisive_rate": ordered_decisive / replicates,
                "decaying_preferred_rate": decay_preferred / replicates,
                "decaying_decisive_rate": decay_decisive / replicates,
                "base_parameters": bases[truth],
            }
            if truth == "D2":
                row.update(
                    {
                        "ordered_fit_positive_g0_rate": positive / replicates,
                        "ordered_fit_nominal_lower95_positive_rate": (
                            nominal / replicates
                        ),
                        "ordered_fit_overdispersion_lower95_positive_rate": (
                            scaled / replicates
                        ),
                        "ordered_model_gof_pass_rate": (
                            ordered_gof / replicates
                        ),
                        "median_spurious_g0": float(np.median(g0_values)),
                        "q05_spurious_g0": float(
                            np.quantile(g0_values, 0.05)
                        ),
                        "q95_spurious_g0": float(
                            np.quantile(g0_values, 0.95)
                        ),
                    }
                )
            results.append(row)
    return results


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--replicates", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=1582026)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    names, raw = load_data(args.data)
    scalar_fits, effective = scalar_window_analysis(raw, names)
    joint = joint_sensitivity(raw, names)
    synthetic = synthetic_identifiability(
        raw, names, args.replicates, args.seed
    )

    payload = {
        "source": str(args.data),
        "protocol": "ANALYSIS_PROTOCOL.md",
        "primary_row_rule": "largest N_sample at each (beta,L)",
        "scalar_fits": scalar_fits,
        "effective_exponents": effective,
        "joint_covariance_sensitivity": joint,
        "synthetic_identifiability": {
            "seed": args.seed,
            "replicates": args.replicates,
            "results": synthetic,
        },
    }
    (args.out_dir / "extended_analysis_results.json").write_text(
        json.dumps(payload, indent=2)
    )

    scalar_rows: list[dict] = []
    for window in scalar_fits:
        for model in window["models"]:
            scalar_rows.append(
                {
                    "beta": window["beta"],
                    "Lmin": window["Lmin"],
                    "Lmax": window["Lmax"],
                    "model": model["kind"],
                    "n": model["n"],
                    "chi2": model["chi2"],
                    "dof": model["dof"],
                    "reduced_chi2": model["reduced_chi2"],
                    "gof_p": model["gof_p"],
                    "AICc": model["aicc"],
                    "BIC": model["bic"],
                    "g0": model.get("g0"),
                    "g0_se_nominal": model.get("g0_se_nominal"),
                    "g0_se_overdispersion": model.get(
                        "g0_se_overdispersion"
                    ),
                    "p": model.get("p"),
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
    write_csv(
        args.out_dir / "scalar_fit_windows.csv",
        scalar_rows,
        [
            "beta",
            "Lmin",
            "Lmax",
            "model",
            "n",
            "chi2",
            "dof",
            "reduced_chi2",
            "gof_p",
            "AICc",
            "BIC",
            "g0",
            "g0_se_nominal",
            "g0_se_overdispersion",
            "p",
            "heldout1_rms_z",
            "heldout2_rms_z",
        ],
    )
    write_csv(
        args.out_dir / "effective_log_exponents.csv",
        effective,
        ["beta", "L1", "L2", "p_eff", "p_eff_se"],
    )
    joint_rows = [
        {
            "beta": row["beta"],
            "Lmin": row["Lmin"],
            "Lmax": row["Lmax"],
            "rho": row["rho"],
            "delta_AICc_ordered_minus_decaying": row[
                "delta_aicc_ordered_minus_decaying"
            ],
            "ordered_chi2": row["ordered"]["chi2"],
            "ordered_reduced_chi2": row["ordered"]["reduced_chi2"],
            "ordered_gof_p": row["ordered"]["gof_p"],
            "decaying_chi2": row["decaying"]["chi2"],
            "decaying_reduced_chi2": row["decaying"]["reduced_chi2"],
            "decaying_gof_p": row["decaying"]["gof_p"],
            "decaying_p": row["decaying"]["p"],
        }
        for row in joint
    ]
    write_csv(
        args.out_dir / "joint_covariance_sensitivity.csv",
        joint_rows,
        [
            "beta",
            "Lmin",
            "Lmax",
            "rho",
            "delta_AICc_ordered_minus_decaying",
            "ordered_chi2",
            "ordered_reduced_chi2",
            "ordered_gof_p",
            "decaying_chi2",
            "decaying_reduced_chi2",
            "decaying_gof_p",
            "decaying_p",
        ],
    )
    synthetic_rows: list[dict] = []
    for row in synthetic:
        synthetic_rows.append(
            {
                key: value
                for key, value in row.items()
                if key != "base_parameters"
            }
        )
    synthetic_fields = sorted(
        {key for row in synthetic_rows for key in row.keys()}
    )
    write_csv(
        args.out_dir / "synthetic_identifiability.csv",
        synthetic_rows,
        synthetic_fields,
    )


if __name__ == "__main__":
    main()
