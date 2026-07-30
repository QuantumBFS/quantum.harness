from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure repo root is on sys.path BEFORE importing src.*
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from src.synthetic_data import make_constantD_dataset, make_driftingD_dataset, save_npz, solve_burgers_spectral_rk4
from src.fit_burgers import scan_time_windows, fit_weak_form, fit_strong_form
from src.analysis import fits_to_dataframe, plot_D_time, plot_a_time, plot_D_models, kpz_collapse_score, estimate_instantaneous_series, plot_D_inst, plot_D_inst_models, drift_metrics

DATA = REPO / "data"
RESULTS = REPO / "results"
PLOTS = RESULTS / "plots"
TABLES = RESULTS / "tables"

def ensure_dirs():
    PLOTS.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)

def run_one(kind: str):
    assert kind in ("constantD", "driftingD")
    if kind == "constantD":
        ds = make_constantD_dataset()
    else:
        ds = make_driftingD_dataset()

    # save dataset
    out_npz = DATA / f"synthetic_{kind}.npz"
    save_npz(ds, str(out_npz))

    # global fits (entire range) for reference
    t_window_global = (float(ds.t[10]), float(ds.t[-10]))  # avoid earliest and latest points
    fr_w = fit_weak_form(ds.x, ds.t, ds.u, t_window=t_window_global, x_crop=(-120, 120))
    fr_s = fit_strong_form(ds.x, ds.t, ds.u, t_window=t_window_global, x_crop=(-120, 120))

    # forward-prediction test (another angle on 'D constant vs drift'):
    # Use the fitted *constant* parameters (a_hat, D_hat) and evolve from t0=50, compare to data.
    t0 = 50.0
    i0 = int(np.argmin(np.abs(ds.t - t0)))
    u_init = ds.u[i0].copy()
    t_pred = ds.t[i0:] - ds.t[i0]
    u_pred = solve_burgers_spectral_rk4(x=ds.x, t=t_pred, a=fr_w.a, D_of_t=lambda tt: fr_w.D, u0=u_init, dt_internal=0.01)
    # L2 relative error on x_crop
    xidx = np.where((ds.x >= -120) & (ds.x <= 120))[0]
    errs = []
    for k in range(len(t_pred)):
        num = np.linalg.norm(u_pred[k, xidx] - ds.u[i0+k, xidx])
        den = np.linalg.norm(ds.u[i0+k, xidx]) + 1e-12
        errs.append(float(num/den))
    df_err = pd.DataFrame({'t_abs': ds.t[i0:], 't_rel': t_pred, 'rel_L2_err': errs})
    df_err.to_csv(TABLES / f'forward_pred_err_{kind}.csv', index=False)
    plt.figure()
    plt.plot(df_err['t_abs'], df_err['rel_L2_err'], marker='o')
    plt.xlabel('t (absolute)')
    plt.ylabel('relative L2 error')
    plt.title(f'{kind}: forward prediction error using constant (a,D) from global fit, starting at t0={t0}')
    plt.tight_layout()
    plt.savefig(PLOTS / f'forward_pred_err_{kind}.png', dpi=180)
    plt.close()
    pred_metrics = {'mean_err': float(np.mean(errs)), 'max_err': float(np.max(errs)), 't0': t0, 'a_used': fr_w.a, 'D_used': fr_w.D}

    # sliding windows: focus on mid/late times
    fits_w = scan_time_windows(ds.x, ds.t, ds.u, window=40.0, step=10.0, method="weak_form", x_crop=(-120, 120))
    fits_s = scan_time_windows(ds.x, ds.t, ds.u, window=40.0, step=10.0, method="strong_form", x_crop=(-120, 120))

    df_w = fits_to_dataframe(fits_w)
    df_s = fits_to_dataframe(fits_s)

    # save tables
    df_w.to_csv(TABLES / f"fits_{kind}_weak.csv", index=False)
    df_s.to_csv(TABLES / f"fits_{kind}_strong.csv", index=False)

    # plots
    plot_D_time(df_w, str(PLOTS / f"D_vs_t_{kind}_weak.png"), title=f"{kind}: D(t) window fits (weak form)")
    plot_a_time(df_w, str(PLOTS / f"a_vs_t_{kind}_weak.png"), title=f"{kind}: a(t) window fits (weak form)")
    cmp = plot_D_models(df_w, str(PLOTS / f"D_models_{kind}_weak.png"),
                        t_ref=50.0, title=f"{kind}: const vs power-law D(t)")

    # KPZ scaling collapse (for synthetic Burgers solution)
    times = [50.0, 100.0, 150.0, 200.0]
    collapse = kpz_collapse_score(ds.x, ds.t, ds.u, times=times, zeta=2/3)

    # instantaneous fits (spectral x-derivatives are valid here because synthetic data is periodic)
    df_inst = estimate_instantaneous_series(ds.x, ds.t, ds.u, x_crop=(-120, 120), deriv_x="spectral")
    df_inst.to_csv(TABLES / f"inst_{kind}_strong_spectral.csv", index=False)

    plot_D_inst(df_inst, str(PLOTS / f"D_inst_{kind}.png"), title=f"{kind}: instantaneous D(t) (strong form, spectral x-derivatives)")
    cmp_inst = plot_D_inst_models(df_inst, str(PLOTS / f"D_inst_models_{kind}.png"), t_ref=50.0, t_min=80.0,
                                  title=f"{kind}: instantaneous D(t) const vs power-law")
    drift_inst = drift_metrics(df_inst[df_inst["t"] >= 80.0])

    summary = dict(
        kind=kind,
        ground_truth=ds.meta,
        global_fit_weak=fr_w.__dict__,
        global_fit_strong=fr_s.__dict__,
        drift_model_compare=cmp,
        instantaneous_compare=cmp_inst,
        instantaneous_drift_metrics=drift_inst,
        kpz_collapse=collapse,
        forward_prediction=pred_metrics,
        notes="Synthetic data: constantD should show gamma~0, driftingD should show gamma~1/3."
    )
    (RESULTS / f"summary_{kind}.json").write_text(json.dumps(summary, indent=2))

def main():
    ensure_dirs()
    run_one("constantD")
    run_one("driftingD")

    # build human-readable report
    report_lines = []
    report_lines.append("# Numerical validation report (synthetic datasets)\n")
    report_lines.append("This report is auto-generated by scripts/run_all.py.\n")
    report_lines.append("## Files produced\n")
    report_lines.append("- tables/: window fit CSVs (weak/strong)\n")
    report_lines.append("- plots/: D(t), a(t), and model-comparison plots\n")
    report_lines.append("- summary_*.json: machine-readable summaries\n")

    for kind in ["constantD", "driftingD"]:
        s = json.loads((RESULTS / f"summary_{kind}.json").read_text())
        cmp = s["drift_model_compare"]
        report_lines.append(f"## {kind}\n")
        report_lines.append(f"- Ground truth: {s['ground_truth']}\n")
        report_lines.append(f"- Global fit (weak): a={s['global_fit_weak']['a']:.6f}, D={s['global_fit_weak']['D']:.6f}\n")
        report_lines.append(f"- Drift test (weak sliding windows):\n")
        report_lines.append(f"  - const D = {cmp['D_const']:.6f} ± {cmp['stderr_D_const']:.3g}\n")
        report_lines.append(f"  - power-law γ = {cmp['gamma']:.6f} ± {cmp['stderr_gamma']:.3g}\n")
        report_lines.append(f"  - ΔAIC = AIC_const - AIC_plaw = {cmp['delta_aic']:.3f} (positive => power-law preferred)\n")
        cmpi = s['instantaneous_compare']
        dm = s['instantaneous_drift_metrics']
        report_lines.append(f"- Drift test (instantaneous strong-form, spectral x-derivatives, t>=80):\n")
        report_lines.append(f"  - const D = {cmpi['D_const']:.6f} ± {cmpi['stderr_D_const']:.3g}\n")
        report_lines.append(f"  - power-law γ = {cmpi['gamma']:.6f} ± {cmpi['stderr_gamma']:.3g}\n")
        report_lines.append(f"  - ΔAIC = {cmpi['delta_aic']:.3f}\n")
        report_lines.append(f"  - practical drift: rel_range={dm['relative_range']:.3%}, rel_std={dm['relative_std']:.3%}\n")
        report_lines.append(f"- KPZ-like collapse score (zeta=2/3, heuristic): {s['kpz_collapse']['score']:.6e}\n")

    (RESULTS / "REPORT.md").write_text("\n".join(report_lines))

if __name__ == "__main__":
    main()