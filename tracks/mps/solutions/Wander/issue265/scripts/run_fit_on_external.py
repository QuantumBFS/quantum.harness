from __future__ import annotations

import argparse
import sys
from pathlib import Path
import json

# Ensure repo root is on sys.path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd

from src.synthetic_data import load_npz
from src.fit_burgers import scan_time_windows, fit_weak_form, fit_strong_form
from src.analysis import fits_to_dataframe, plot_D_time, plot_a_time, plot_D_models, kpz_collapse_score, estimate_instantaneous_series, plot_D_inst, plot_D_inst_models, drift_metrics

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to npz with arrays x,t,u")
    ap.add_argument("--outdir", default="results_external", help="Output directory")
    ap.add_argument("--method", default="weak_form", choices=["weak_form","strong_form"])
    ap.add_argument("--inst_deriv_x", default="finite", choices=["finite","spectral"], help="x-derivative method for instantaneous strong-form series")
    ap.add_argument("--window", type=float, default=40.0)
    ap.add_argument("--step", type=float, default=10.0)
    ap.add_argument("--x_crop", type=float, nargs=2, default=[-120.0, 120.0])
    args = ap.parse_args()

    ds = load_npz(args.input)
    outdir = Path(args.outdir)
    plots = outdir / "plots"
    tables = outdir / "tables"
    plots.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)

    fits = scan_time_windows(ds.x, ds.t, ds.u, window=args.window, step=args.step, method=args.method, x_crop=tuple(args.x_crop))
    df = fits_to_dataframe(fits)
    df.to_csv(tables / f"fits_{args.method}.csv", index=False)

    plot_D_time(df, str(plots / f"D_vs_t_{args.method}.png"), title=f"External data: D(t) window fits ({args.method})")
    plot_a_time(df, str(plots / f"a_vs_t_{args.method}.png"), title=f"External data: a(t) window fits ({args.method})")
    cmp = plot_D_models(df, str(plots / f"D_models_{args.method}.png"), t_ref=50.0,
                        title=f"External data: const vs power-law D(t) ({args.method})")

    collapse = kpz_collapse_score(ds.x, ds.t, ds.u, times=[50.0,100.0,150.0,200.0], zeta=2/3)

    summary = dict(meta=ds.meta, drift_model_compare=cmp, kpz_collapse=collapse)
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2))

    print("Done. Outputs in", outdir)

if __name__ == "__main__":
    main()
