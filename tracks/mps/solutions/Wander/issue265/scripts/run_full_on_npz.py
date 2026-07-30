#!/usr/bin/env python3
"""
Full analysis pipeline on an external u(t,x) dataset (npz with x,t,u,meta).

This script is the "do everything" version you want for deciding:
    Is D a true constant, or does it drift (e.g. D(t) ~ t^{1/3})?

It produces:
  - windowed weak/strong fits (a(t), D(t))
  - instantaneous strong-form series (a(t), D(t))
  - constant vs power-law model selection (AIC) on D(t)
  - forward prediction test using fitted constant (a,D)
  - KPZ-style collapse score (heuristic)
  - summary.json, tables/*.csv, plots/*.png

Usage (generic):
  python scripts/run_full_on_npz.py --input data/your.npz --outdir results_your

Usage (B2 Kharkov public Δ=1 data):
  # 1) download + convert
  bash scripts/b2_download_kharkov_highT_delta1.sh
  python scripts/b2_convert_kharkov_npy_to_npz.py --npy data/highT_delta1.npy --out data/kharkov_highT_delta1.npz --center-x --drop-first 250 --savgol-x 31 7
  # 2) full analysis
  python scripts/run_full_on_npz.py --input data/kharkov_highT_delta1.npz --outdir results_kharkov_B2 --x-crop -120 120 --t-ref 50 --t-min-inst 80 --deriv-x finite

Important:
  For non-periodic/open-boundary data, `--deriv-x finite` is often more robust than spectral FFT derivatives.
"""
from __future__ import annotations

import argparse
import json
import sys
import dataclasses
from pathlib import Path
import numpy as np
import pandas as pd

# Ensure repo root on sys.path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.synthetic_data import load_npz, solve_burgers_spectral_rk4
from src.fit_burgers import scan_time_windows, fit_weak_form, fit_strong_form
from src.analysis import (
    fits_to_dataframe,
    plot_D_time,
    plot_a_time,
    plot_D_models,
    kpz_collapse_score,
    estimate_instantaneous_series,
    plot_D_inst,
    plot_D_inst_models,
    drift_metrics,
)

def forward_pred_err(x: np.ndarray, t: np.ndarray, u: np.ndarray, *, a: float, D: float, t0: float, x_crop):
    """Forward-prediction error using constant (a,D) from time t0 onward."""
    i0 = int(np.argmin(np.abs(t - t0)))
    u0 = u[i0].copy()
    # predict over remaining times, using internal dt ~ 0.01 for stability
    t_pred = t[i0:] - t[i0]
    u_pred = solve_burgers_spectral_rk4(
        x=x, t=t_pred, a=a, D_of_t=lambda tt: D, u0=u0, dt_internal=0.01
    )
    x1, x2 = x_crop
    xidx = np.where((x >= x1) & (x <= x2))[0]
    errs = []
    for k, ti in enumerate(t[i0:]):
        num = np.linalg.norm(u_pred[k, xidx] - u[i0 + k, xidx])
        den = np.linalg.norm(u[i0 + k, xidx]) + 1e-12
        errs.append([float(ti), float(num/den)])
    return np.asarray(errs), u_pred

def plot_forward_err(errs: np.ndarray, out_png: str, title: str):
    import matplotlib.pyplot as plt
    plt.figure(figsize=(6,4))
    plt.plot(errs[:,0], errs[:,1])
    plt.xlabel("t")
    plt.ylabel("relative L2 error (x-crop)")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_png, dpi=160)
    plt.close()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Input .npz with x,t,u,meta")
    ap.add_argument("--outdir", required=True, help="Output directory")
    ap.add_argument("--window", type=float, default=40.0, help="time-window length for sliding fits")
    ap.add_argument("--step", type=float, default=10.0, help="time-window step for sliding fits")
    ap.add_argument("--x-crop", nargs=2, type=float, default=[-120.0, 120.0], metavar=("X1","X2"))
    ap.add_argument("--t-ref", type=float, default=50.0, help="reference time for power-law D(t)=D0 (t/t_ref)^gamma")
    ap.add_argument("--t-min-inst", type=float, default=80.0, help="min t for instantaneous D(t) drift test")
    ap.add_argument("--deriv-x", choices=["finite","spectral"], default="finite", help="x-derivative method for strong/instantaneous")
    ap.add_argument("--smooth-x-window", type=int, default=9)
    ap.add_argument("--smooth-t-window", type=int, default=5)
    ap.add_argument("--smooth-poly", type=int, default=3)
    ap.add_argument("--t0-pred", type=float, default=50.0, help="start time for forward prediction test")
    args = ap.parse_args()

    ds = load_npz(args.input)
    x, t, u = ds.x, ds.t, ds.u

    outdir = Path(args.outdir)
    plots = outdir / "plots"
    tables = outdir / "tables"
    plots.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)

    x_crop = (float(args.x_crop[0]), float(args.x_crop[1]))

    # --- global fits (constant a,D) ---
    t_window_global = (float(t[10]), float(t[-10]))  # avoid earliest/last points
    fr_w = fit_weak_form(
        x, t, u,
        t_window=t_window_global,
        x_crop=x_crop,
        smooth_x_window=args.smooth_x_window,
        smooth_t_window=args.smooth_t_window,
        smooth_poly=args.smooth_poly,
    )
    fr_s = fit_strong_form(
        x, t, u,
        t_window=t_window_global,
        x_crop=x_crop,
        smooth_x_window=args.smooth_x_window,
        smooth_t_window=args.smooth_t_window,
        smooth_poly=args.smooth_poly,
        deriv_x=args.deriv_x,
    )

    # --- sliding-window fits ---
    t_min = float(t[0])
    t_max = float(t[-1])
    starts = np.arange(t_min, t_max - args.window + 1e-12, args.step)
    windows = [(float(s), float(s + args.window)) for s in starts]

    fits_w = [fit_weak_form(x, t, u, t_window=w, x_crop=x_crop,
                            smooth_x_window=args.smooth_x_window, smooth_t_window=args.smooth_t_window, smooth_poly=args.smooth_poly)
              for w in windows]
    fits_s = [fit_strong_form(x, t, u, t_window=w, x_crop=x_crop,
                              smooth_x_window=args.smooth_x_window, smooth_t_window=args.smooth_t_window, smooth_poly=args.smooth_poly,
                              deriv_x=args.deriv_x)
              for w in windows]

    df_w = fits_to_dataframe(fits_w)
    df_s = fits_to_dataframe(fits_s)
    df_w.to_csv(tables/"fits_weak.csv", index=False)
    df_s.to_csv(tables/"fits_strong.csv", index=False)

    plot_D_time(df_w, str(plots/"D_vs_t_weak.png"), title="D(t) window fits (weak form)")
    plot_a_time(df_w, str(plots/"a_vs_t_weak.png"), title="a(t) window fits (weak form)")
    cmp_w = plot_D_models(df_w, str(plots/"D_models_weak.png"), t_ref=args.t_ref, title="D(t): const vs power-law (weak)")

    plot_D_time(df_s, str(plots/"D_vs_t_strong.png"), title=f"D(t) window fits (strong form, {args.deriv_x})")
    plot_a_time(df_s, str(plots/"a_vs_t_strong.png"), title=f"a(t) window fits (strong form, {args.deriv_x})")
    cmp_s = plot_D_models(df_s, str(plots/"D_models_strong.png"), t_ref=args.t_ref, title=f"D(t): const vs power-law (strong, {args.deriv_x})")

    # --- instantaneous strong-form series ---
    inst = estimate_instantaneous_series(
        x, t, u,
        x_crop=x_crop,
        smooth_x_window=args.smooth_x_window,
        smooth_t_window=args.smooth_t_window,
        smooth_poly=args.smooth_poly,
        deriv_x=args.deriv_x,
    )
    inst.to_csv(tables/f"inst_strong_{args.deriv_x}.csv", index=False)

    # cut to t >= t_min_inst for drift test
    inst_tail = inst[inst["t"] >= float(args.t_min_inst)].copy()
    plot_D_inst(inst_tail, str(plots/f"D_inst_{args.deriv_x}.png"), title=f"Instantaneous D(t), t>={args.t_min_inst} ({args.deriv_x})")
    cmp_inst = plot_D_inst_models(inst_tail, str(plots/f"D_inst_models_{args.deriv_x}.png"), t_ref=args.t_ref,
                                  title=f"Instantaneous D(t): const vs power-law ({args.deriv_x})")
    drift = drift_metrics(inst_tail)

    # --- forward prediction test ---
    errs, _ = forward_pred_err(x, t, u, a=float(fr_w.a), D=float(fr_w.D), t0=float(args.t0_pred), x_crop=x_crop)
    np.savetxt(tables/"forward_pred_err.csv", errs, delimiter=",", header="t,relL2", comments="")
    plot_forward_err(errs, str(plots/"forward_pred_err.png"), title=f"Forward prediction error (const a,D) from t0={args.t0_pred}")

    # --- KPZ collapse heuristic ---
    # pick a few times inside available range
    times_try = [args.t_ref, 2*args.t_ref, 3*args.t_ref, 4*args.t_ref]
    times_try = [tt for tt in times_try if (tt >= float(t[0]) and tt <= float(t[-1]))]
    collapse = kpz_collapse_score(x, t, u, times=times_try, zeta=2/3)

    summary = {
        "input": str(Path(args.input).resolve()),
        "meta": ds.meta,
        "global_fit_weak": dataclasses.asdict(fr_w),
        "global_fit_strong": dataclasses.asdict(fr_s),
        "drift_model_compare_window_weak": cmp_w,
        "drift_model_compare_window_strong": cmp_s,
        "drift_model_compare_instantaneous": cmp_inst,
        "drift_metrics_instantaneous": drift,
        "kpz_collapse_score": collapse,
        "notes": {
            "decision_hint": "If gamma≈0 and drift_metrics(relative_range,relative_std) are small, D is effectively constant. If gamma≈1/3 and drift is large, D(t) drifts (KPZ)."
        }
    }
    (outdir/"summary.json").write_text(json.dumps(summary, indent=2))
    print("[OK] Done. Outputs in", outdir)

if __name__ == "__main__":
    main()
