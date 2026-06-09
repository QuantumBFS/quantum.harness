#!/usr/bin/env python3
"""Deterministic finite-size-scaling pipeline.

Fits one of four scaling forms to a size-indexed (and optionally
parameter-indexed) observable table, with parametric-bootstrap confidence
intervals, a quality-of-fit number, a CSV of fitted parameters, and a
diagnostic PNG.

This script is content-agnostic. It NEVER names a physical exponent or a
universality class: parameter symbols (alpha, A, B, h_c, nu, gamma_over_nu)
are plain fit labels, not physics interpretation.
"""

import argparse
import csv
import os
import sys

import matplotlib

matplotlib.use("Agg")  # headless: must precede pyplot import

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.optimize import curve_fit, minimize  # noqa: E402

FORMS = ("power-law", "log-L", "polynomial", "data-collapse")


# --------------------------------------------------------------------------- #
# Data loading and validation
# --------------------------------------------------------------------------- #
def load_table(path, size_col, obs_col, err_col, param_col=None):
    """Load a CSV table and validate required columns row-by-row.

    Returns a dict of numpy arrays. On a missing/empty required cell, prints a
    one-line ``blocked:`` message and exits nonzero. Never imputes.
    """
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("blocked: empty data table")
        sys.exit(1)

    header = rows[0].keys()
    required = [size_col, err_col, obs_col]
    if param_col is not None:
        required.append(param_col)
    for col in required:
        if col not in header:
            print(f"blocked: {col}")
            sys.exit(1)

    cols = {c: [] for c in required}
    # Validation contract: size and uncertainty columns must be present AND
    # non-empty for EVERY row. We treat all required columns the same way.
    for row in rows:
        for col in required:
            val = row.get(col, "")
            if val is None or str(val).strip() == "":
                print(f"blocked: {col}")
                sys.exit(1)
            cols[col].append(float(val))

    out = {
        "L": np.asarray(cols[size_col], dtype=float),
        "obs": np.asarray(cols[obs_col], dtype=float),
        "err": np.asarray(cols[err_col], dtype=float),
    }
    if param_col is not None:
        out["param"] = np.asarray(cols[param_col], dtype=float)
    return out


# --------------------------------------------------------------------------- #
# Fit models
# --------------------------------------------------------------------------- #
def _power_law(L, A, alpha):
    return A * np.power(L, -alpha)


def _design_log_L(L):
    """Design matrix for obs = A*log(L) + B."""
    return np.column_stack([np.log(L), np.ones_like(L)])


def _design_poly(L, degree):
    """Design matrix for a polynomial in (1/L); column 0 is the constant."""
    inv = 1.0 / L
    return np.column_stack([inv**k for k in range(degree + 1)])


def weighted_linear_fit(X, y, err):
    """Weighted linear least squares. Returns coefficient vector."""
    w = 1.0 / np.asarray(err, dtype=float)
    Xw = X * w[:, None]
    yw = y * w
    coef, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
    return coef


def _apply_pins(param_names, p0, pins):
    """Split parameters into free (to fit) and pinned (fixed).

    Returns (free_names, free_p0, pinned_dict).
    """
    pinned = {}
    for name, val in pins.items():
        if name not in param_names:
            print(f"blocked: unknown pin {name}")
            sys.exit(1)
        pinned[name] = val
    free_names = [n for n in param_names if n not in pinned]
    free_p0 = [p0[param_names.index(n)] for n in free_names]
    return free_names, free_p0, pinned


def _assemble(param_names, free_names, free_values, pinned):
    """Recombine free + pinned values into a full ordered dict."""
    free_map = dict(zip(free_names, free_values))
    return {n: (pinned[n] if n in pinned else free_map[n]) for n in param_names}


# --------------------------------------------------------------------------- #
# Single-fit dispatch (returns dict of param -> value, plus chi2/dof or resid)
# --------------------------------------------------------------------------- #
def fit_power_law(L, y, err, pins):
    names = ["A", "alpha"]
    p0 = [float(np.max(np.abs(y))) or 1.0, 1.0]
    free_names, free_p0, pinned = _apply_pins(names, p0, pins)

    def model(LL, *free):
        params = _assemble(names, free_names, free, pinned)
        return _power_law(LL, params["A"], params["alpha"])

    if free_names:
        popt, _ = curve_fit(model, L, y, p0=free_p0, sigma=err, absolute_sigma=True, maxfev=20000)
    else:
        popt = []
    params = _assemble(names, free_names, popt, pinned)
    resid = (y - _power_law(L, params["A"], params["alpha"])) / err
    dof = max(len(y) - len(free_names), 1)
    return params, float(np.sum(resid**2) / dof)


def fit_log_L(L, y, err, pins):
    names = ["A", "B"]
    if not pins:
        coef = weighted_linear_fit(_design_log_L(L), y, err)
        params = {"A": float(coef[0]), "B": float(coef[1])}
    else:
        # Pinned linear fit: subtract pinned contribution, fit remaining cols.
        pinned = {k: v for k, v in pins.items() if k in names}
        for k in pins:
            if k not in names:
                print(f"blocked: unknown pin {k}")
                sys.exit(1)
        full = _design_log_L(L)
        col_idx = {"A": 0, "B": 1}
        y_adj = y.copy()
        for k, v in pinned.items():
            y_adj = y_adj - v * full[:, col_idx[k]]
        free_names = [n for n in names if n not in pinned]
        free_cols = full[:, [col_idx[n] for n in free_names]]
        coef = weighted_linear_fit(free_cols, y_adj, err)
        params = dict(pinned)
        params.update(dict(zip(free_names, [float(c) for c in coef])))
        params = {n: float(params[n]) for n in names}
    model = params["A"] * np.log(L) + params["B"]
    resid = (y - model) / err
    n_free = len([n for n in names if n not in pins])
    dof = max(len(y) - n_free, 1)
    return params, float(np.sum(resid**2) / dof)


def fit_polynomial(L, y, err, degree, pins):
    names = [f"c{k}" for k in range(degree + 1)]
    full = _design_poly(L, degree)
    col_idx = {n: k for k, n in enumerate(names)}
    pinned = {}
    for k, v in pins.items():
        if k not in names:
            print(f"blocked: unknown pin {k}")
            sys.exit(1)
        pinned[k] = v
    y_adj = y.copy()
    for k, v in pinned.items():
        y_adj = y_adj - v * full[:, col_idx[k]]
    free_names = [n for n in names if n not in pinned]
    free_cols = full[:, [col_idx[n] for n in free_names]]
    coef = weighted_linear_fit(free_cols, y_adj, err)
    params = dict(pinned)
    params.update(dict(zip(free_names, [float(c) for c in coef])))
    params = {n: float(params[n]) for n in names}
    model = full @ np.asarray([params[n] for n in names])
    resid = (y - model) / err
    dof = max(len(y) - len(free_names), 1)
    return params, float(np.sum(resid**2) / dof)


def collapse_residual(h_c, nu, gamma_over_nu, L, param, obs, nbins=20):
    """Pooled collapse residual.

    Maps every point to (x = L^{1/nu} (param - h_c), y = obs * L^{gamma/nu}),
    bins x, and sums the within-bin variance of y. A clean collapse gives a
    single-valued curve and hence a small within-bin spread.
    """
    if nu == 0:
        return np.inf
    x = np.power(L, 1.0 / nu) * (param - h_c)
    yy = obs * np.power(L, gamma_over_nu)
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(yy)):
        return np.inf
    order = np.argsort(x)
    xs, ys = x[order], yy[order]
    edges = np.linspace(xs[0], xs[-1] + 1e-12, nbins + 1)
    idx = np.clip(np.digitize(xs, edges) - 1, 0, nbins - 1)
    total = 0.0
    for b in range(nbins):
        sel = ys[idx == b]
        if sel.size > 1:
            total += float(np.sum((sel - sel.mean()) ** 2))
    return total


def fit_data_collapse(L, param, obs, pins, p0=None):
    names = ["h_c", "nu", "gamma_over_nu"]
    if p0 is None:
        p0 = [float(np.median(param)), 1.0, 0.0]
    free_names, free_p0, pinned = _apply_pins(names, p0, pins)

    def objective(free):
        params = _assemble(names, free_names, free, pinned)
        return collapse_residual(
            params["h_c"], params["nu"], params["gamma_over_nu"], L, param, obs
        )

    if free_names:
        res = minimize(
            objective,
            free_p0,
            method="Nelder-Mead",
            options={"xatol": 1e-6, "fatol": 1e-9, "maxiter": 5000},
        )
        if not res.success:
            raise RuntimeError("collapse fit failed to converge")
        free_vals = res.x
        resid = float(res.fun)
    else:
        free_vals = []
        resid = objective([])
    params = _assemble(names, free_names, free_vals, pinned)
    return params, resid


# --------------------------------------------------------------------------- #
# Bootstrap
# --------------------------------------------------------------------------- #
def run_single(form, data, degree, pins):
    """Run one fit on the given (possibly perturbed) data. Returns (params, qof)."""
    L, y, err = data["L"], data["obs"], data["err"]
    if form == "power-law":
        return fit_power_law(L, y, err, pins)
    if form == "log-L":
        return fit_log_L(L, y, err, pins)
    if form == "polynomial":
        return fit_polynomial(L, y, err, degree, pins)
    if form == "data-collapse":
        return fit_data_collapse(L, data["param"], y, pins)
    raise ValueError(f"unknown form {form}")


def bootstrap(form, data, degree, pins, n_boot, seed=0):
    """Parametric bootstrap: perturb each observable by Gaussian(err), refit.

    Returns (samples_dict, failed_resamples). Every resample is attempted;
    non-converging fits are counted, never silently dropped.
    """
    rng = np.random.default_rng(seed)
    err = data["err"]
    obs = data["obs"]
    samples = {}
    failed = 0
    for _ in range(n_boot):
        pert = dict(data)
        pert["obs"] = obs + rng.normal(0.0, err)
        try:
            params, _ = run_single(form, pert, degree, pins)
        except (RuntimeError, ValueError, np.linalg.LinAlgError):
            failed += 1
            continue
        for k, v in params.items():
            samples.setdefault(k, []).append(v)
    return {k: np.asarray(v) for k, v in samples.items()}, failed


def quantile_ci(arr):
    if len(arr) == 0:
        return (float("nan"), float("nan"))
    return (float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975)))


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def write_csv(path, form, params, cis, qof_label, qof_value, failed):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["parameter", "value", "ci_lo", "ci_hi"])
        for name in params:
            lo, hi = cis.get(name, (float("nan"), float("nan")))
            w.writerow([name, params[name], lo, hi])
        w.writerow([qof_label, qof_value, "", ""])
        w.writerow(["failed_resamples", failed, "", ""])


def make_plot(path, form, data, params, degree):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    L = data["L"]
    if form == "data-collapse":
        fig, ax = plt.subplots(figsize=(6, 4))
        param = data["param"]
        obs = data["obs"]
        nu = params["nu"]
        x = np.power(L, 1.0 / nu) * (param - params["h_c"])
        yy = obs * np.power(L, params["gamma_over_nu"])
        for Lval in np.unique(L):
            sel = L == Lval
            order = np.argsort(x[sel])
            ax.plot(x[sel][order], yy[sel][order], "o-", label=f"L={Lval:g}")
        ax.set_xlabel("L^(1/nu) (param - h_c)")
        ax.set_ylabel("obs * L^(gamma_over_nu)")
        ax.set_title("data collapse")
        ax.legend(fontsize=7)
    else:
        y, err = data["obs"], data["err"]
        if form == "power-law":
            model = _power_law(L, params["A"], params["alpha"])
        elif form == "log-L":
            model = params["A"] * np.log(L) + params["B"]
        else:  # polynomial
            full = _design_poly(L, degree)
            names = [f"c{k}" for k in range(degree + 1)]
            model = full @ np.asarray([params[n] for n in names])
        resid = (y - model) / err
        fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(9, 4))
        order = np.argsort(L)
        ax0.errorbar(L[order], y[order], yerr=err[order], fmt="o", label="data")
        ax0.plot(L[order], model[order], "-", label="fit")
        ax0.set_xlabel("L")
        ax0.set_ylabel("obs")
        ax0.set_title(form)
        ax0.legend(fontsize=8)
        ax1.axhline(0.0, color="k", lw=0.8)
        ax1.plot(L[order], resid[order], "o")
        ax1.set_xlabel("L")
        ax1.set_ylabel("(obs - model) / err")
        ax1.set_title("normalized residuals")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_pins(pin_list):
    pins = {}
    for item in pin_list or []:
        if "=" not in item:
            print(f"blocked: bad pin {item}")
            sys.exit(1)
        name, val = item.split("=", 1)
        pins[name.strip()] = float(val)
    return pins


def build_parser():
    p = argparse.ArgumentParser(description="Deterministic finite-size-scaling fit.")
    p.add_argument("data", help="input CSV table")
    p.add_argument(
        "--form", required=True, choices=FORMS, help="exactly one scaling form (never auto-cycled)"
    )
    p.add_argument("--size-col", default="L")
    p.add_argument("--obs-col", default="obs")
    p.add_argument("--err-col", default="err")
    p.add_argument(
        "--param-col", default=None, help="parameter column (required for data-collapse)"
    )
    p.add_argument(
        "--degree", type=int, default=2, help="polynomial degree in 1/L (polynomial form)"
    )
    p.add_argument(
        "--pin",
        action="append",
        default=[],
        help="fix a parameter, e.g. --pin h_c=2.0 (repeatable)",
    )
    p.add_argument(
        "--bootstrap", type=int, default=1000, help="number of parametric-bootstrap resamples"
    )
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out-csv", default="results/scaling-fit.csv")
    p.add_argument("--out-png", default="results/scaling-fit.png")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    pins = parse_pins(args.pin)

    param_col = args.param_col
    if args.form == "data-collapse" and param_col is None:
        print("blocked: --param-col required for data-collapse")
        sys.exit(1)

    data = load_table(args.data, args.size_col, args.obs_col, args.err_col, param_col)

    params, qof = run_single(args.form, data, args.degree, pins)

    samples, failed = bootstrap(args.form, data, args.degree, pins, args.bootstrap, seed=args.seed)
    cis = {name: quantile_ci(samples.get(name, np.asarray([]))) for name in params}

    qof_label = "collapse_residual" if args.form == "data-collapse" else "chi2_per_dof"

    write_csv(args.out_csv, args.form, params, cis, qof_label, qof, failed)
    make_plot(args.out_png, args.form, data, params, args.degree)

    # Report: 2-3 lines, generic labels only.
    lines = []
    for name in params:
        lo, hi = cis[name]
        lines.append(
            f"{name} = {params[name]:.6g} "
            f"(95% CI {lo:.6g}-{hi:.6g} from {args.bootstrap} bootstrap, "
            f"{failed} failed)"
        )
    print("; ".join(lines))
    print(f"{qof_label} = {qof:.6g}")
    print(f"wrote {args.out_csv} and {args.out_png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
