"""Convergence analysis and plots for the B METTS effort (report §6).

Produces, under metts_runs/<label>/analysis/:
  * delta_beta_convergence.csv + .png  -- Trotter dtau scan (2nd-order check)
  * sample_convergence.csv + .png      -- SEM vs M (1/sqrt(M) scaling, Rhat)
  * bond_convergence.csv + .png        -- u,C vs chi (MPS backend)
  * ed_comparison.csv                  -- the §9.3 METTS-vs-ED table

Uses matplotlib Agg (no display). Every plot is crash-guarded: a failed plot
is logged, not fatal. Designed to run on the laptop budget (small systems,
modest samples).
"""
from __future__ import annotations

import os
import sys
import time
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from metts_b.bridge import ed_thermodynamics, write_csv, rel_err
from metts_b.measure import DenseBackend
from metts_b.mps_backend import MPSBackend
from metts_b.chain import run_chain, binning_sem
from metts_b.config import METTSConfig


def _safe_savefig(path):
    try:
        plt.tight_layout()
        plt.savefig(path, dpi=120)
    except Exception as e:
        sys.stderr.write(f"[analyze] plot save failed {path}: {e!r}\n")
    plt.close()


# ---------------------------------------------------------------------------
# Trotter dtau convergence (dense backend, single product state, vs spectral)
# ---------------------------------------------------------------------------

def delta_beta_convergence(out_dir, Lx=2, Ly=2, h=3.0, beta=0.4,
                           dtuas=(0.08, 0.04, 0.02, 0.01, 0.005)):
    """Scan dtau; E(dtau) for a fixed product state should converge to the
    spectral E as dtau->0 with 2nd-order scaling."""
    be_sp = DenseBackend(Lx, Ly, h, evolve="spectral")
    rng = np.random.default_rng(0)
    spins = (rng.integers(0, 2, size=Lx * Ly) * 2 - 1).astype(np.int8)
    psi_sp = be_sp.evolve(be_sp.make_product_state(spins), beta)
    E_sp, _, _ = be_sp.energy_moments(psi_sp)
    rows = []
    for dtau in dtuas:
        be = DenseBackend(Lx, Ly, h, evolve="trotter", dtau=dtau)
        psi = be.evolve(be.make_product_state(spins), beta)
        E, _, _ = be.energy_moments(psi)
        rows.append({"dtau": dtau, "E_trotter": E, "E_spectral": E_sp,
                     "abs_err": abs(E - E_sp)})
    write_csv(os.path.join(out_dir, "delta_beta_convergence.csv"), rows,
              ["dtau", "E_trotter", "E_spectral", "abs_err"])
    # plot
    dts = np.array([r["dtau"] for r in rows])
    errs = np.array([r["abs_err"] for r in rows])
    plt.figure(figsize=(5, 4))
    plt.loglog(dts, errs, "o-", label="|E_trotter - E_spectral|")
    # 2nd-order reference line
    if errs[-1] > 0:
        ref = errs[-1] * (dts / dts[-1]) ** 2
        plt.loglog(dts, ref, "--", color="gray", label=r"$\propto \Delta\beta^2$")
    plt.xlabel(r"Trotter step $\Delta\beta$")
    plt.ylabel("energy error vs spectral")
    plt.title(f"Trotter convergence ({Lx}x{Ly} h={h} beta={beta})")
    plt.legend()
    plt.grid(True, which="both", ls=":", alpha=0.5)
    _safe_savefig(os.path.join(out_dir, "delta_beta_convergence.png"))
    return rows


# ---------------------------------------------------------------------------
# Sample-count convergence (1/sqrt(M) scaling, Rhat)
# ---------------------------------------------------------------------------

def sample_convergence(out_dir, Lx=2, Ly=2, h=3.0, beta=0.8,
                       backend="dense", chi=32, dtau=0.01,
                       sample_counts=(100, 200, 500, 1000, 2000, 4000),
                       n_chains=4, seed=20260801):
    """For each M, run n_chains chains of M production samples and record the
    u SEM (binning) and the Gelman-Rubin Rhat. SEM should scale ~1/sqrt(M).

    Each chain's per-sample E array is kept once and reused for both the
    pooled SEM and Rhat (no double computation).
    """
    from metts_b.chain import _gelman_rubin
    ed = ed_thermodynamics(Lx, Ly, h, beta_list=[beta])[0] if Lx * Ly <= 12 else None
    rows = []
    for M in sample_counts:
        per_chain = []           # list of per-chain E arrays
        for c in range(n_chains):
            if backend == "dense":
                be = DenseBackend(Lx, Ly, h, dtau=dtau, evolve="spectral")
            else:
                be = MPSBackend(Lx, Ly, h, dtau=dtau, max_bond_dim=chi)
            cseed = (seed + c * 7919) & 0x7FFFFFFF
            res = run_chain(be, beta, n_warmup=min(50, M // 4 + 10),
                            n_production=M, seed=cseed, dtau=dtau,
                            evolve_mode=("spectral" if backend == "dense"
                                         else "trotter"),
                            write_traces=False)
            if res.n_production > 0:
                per_chain.append(np.array(res.E_samples))
        if not per_chain:
            continue
        Es = np.concatenate(per_chain)
        N = Lx * Ly
        u = Es.mean() / N
        sem = binning_sem(Es) / N
        rhat = _gelman_rubin(per_chain) if len(per_chain) >= 2 else float("nan")
        rows.append({"M": M, "u": u, "sem": sem, "rhat": rhat,
                     "u_ed": ed.u if ed else float("nan"),
                     "u_rel_err": rel_err(u, ed.u) if ed else float("nan")})
    if rows:
        write_csv(os.path.join(out_dir, "sample_convergence.csv"), rows,
                  ["M", "u", "sem", "rhat", "u_ed", "u_rel_err"])
        Ms = np.array([r["M"] for r in rows])
        sems = np.array([r["sem"] for r in rows])
        plt.figure(figsize=(5, 4))
        plt.loglog(Ms, sems, "o-", label="SEM(u) (binning)")
        if sems[-1] > 0:
            plt.loglog(Ms, sems[-1] * np.sqrt(Ms[-1] / Ms), "--",
                       color="gray", label=r"$\propto 1/\sqrt{M}$")
        plt.xlabel("production samples M")
        plt.ylabel("SEM(u)")
        plt.title(f"Sample convergence ({Lx}x{Ly} h={h} beta={beta})")
        plt.legend()
        plt.grid(True, which="both", ls=":", alpha=0.5)
        _safe_savefig(os.path.join(out_dir, "sample_convergence.png"))
    return rows


# ---------------------------------------------------------------------------
# Bond-dimension chi convergence (MPS backend)
# ---------------------------------------------------------------------------

def bond_convergence(out_dir, Lx=3, Ly=4, h=3.0, beta=0.5, dtau=0.02,
                     chis=(8, 16, 32, 48, 64), n_production=300, seed=77):
    ed = ed_thermodynamics(Lx, Ly, h, beta_list=[beta])[0]
    rows = []
    for chi in chis:
        be = MPSBackend(Lx, Ly, h, dtau=dtau, max_bond_dim=chi, trunc_tol=1e-12)
        res = run_chain(be, beta, n_warmup=15, n_production=n_production,
                        seed=seed, dtau=dtau, evolve_mode="trotter",
                        write_traces=False)
        if res.n_production == 0:
            rows.append({"chi": chi, "u": float("nan"), "u_err": float("nan"),
                         "u_rel_err": float("nan"), "n_samples": 0})
            continue
        rows.append({"chi": chi, "u": res.u, "u_err": res.u_err,
                     "u_rel_err": rel_err(res.u, ed.u), "n_samples": res.n_production})
    write_csv(os.path.join(out_dir, "bond_convergence.csv"), rows,
              ["chi", "u", "u_err", "u_rel_err", "n_samples"])
    chis_ok = [r["chi"] for r in rows if np.isfinite(r["u"])]
    us = [r["u"] for r in rows if np.isfinite(r["u"])]
    if chis_ok:
        plt.figure(figsize=(5, 4))
        plt.plot(chis_ok, us, "o-", label="u(chi)")
        plt.axhline(ed.u, color="r", ls="--", label=f"ED u={ed.u:.4f}")
        plt.xlabel("bond dimension chi")
        plt.ylabel("u")
        plt.title(f"Bond convergence ({Lx}x{Ly} h={h} beta={beta})")
        plt.legend()
        plt.grid(True, ls=":", alpha=0.5)
        _safe_savefig(os.path.join(out_dir, "bond_convergence.png"))
    return rows


def ed_comparison_plot(csv_path, out_png, title="METTS vs ED"):
    """Plot u(beta) and C(beta) METTS-vs-ED from a comparison CSV (the output
    of run.py's metts_vs_ed.csv). Crash-guarded."""
    from metts_b.bridge import read_csv
    rows = read_csv(csv_path)
    if not rows or "u_ed" not in rows[0]:
        sys.stderr.write(f"[analyze] no ED column in {csv_path}\n")
        return
    b = [float(r["beta"]) for r in rows]
    um = [float(r["u_metts"]) for r in rows]
    ue = [float(r["u_err"]) for r in rows]
    ud = [float(r["u_ed"]) for r in rows]
    cm = [float(r["C_metts"]) for r in rows]
    ce = [float(r["C_err"]) for r in rows]
    cd = [float(r["C_ed"]) for r in rows]
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].errorbar(b, um, yerr=ue, fmt="o-", label="METTS")
    ax[0].plot(b, ud, "s--", color="k", label="ED")
    ax[0].set_xlabel(r"$\beta J$"); ax[0].set_ylabel(r"$u$")
    ax[0].legend(); ax[0].grid(ls=":", alpha=0.5)
    ax[0].set_title(title + " — internal energy")
    ax[1].errorbar(b, cm, yerr=ce, fmt="o-", label="METTS")
    ax[1].plot(b, cd, "s--", color="k", label="ED")
    ax[1].set_xlabel(r"$\beta J$"); ax[1].set_ylabel(r"$C$")
    ax[1].legend(); ax[1].grid(ls=":", alpha=0.5)
    ax[1].set_title(title + " — specific heat")
    _safe_savefig(out_png)


def run_all_analysis(out_dir, label="analysis"):
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    print("[analyze] delta-beta convergence ...")
    delta_beta_convergence(out_dir)
    print("[analyze] sample-count convergence (dense, beta=0.8) ...")
    sample_convergence(out_dir, backend="dense", beta=0.8)
    print("[analyze] bond-dimension convergence (MPS, 3x4) ...")
    bond_convergence(out_dir)
    print(f"[analyze] done in {time.time()-t0:.1f}s -> {out_dir}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="metts_runs/analysis")
    p.add_argument("--ed-csv", default=None,
                   help="optional metts_vs_ed.csv to plot")
    p.add_argument("--ed-title", default="METTS vs ED")
    args = p.parse_args()
    if args.ed_csv:
        ed_comparison_plot(args.ed_csv,
                           os.path.join(os.path.dirname(args.ed_csv) or ".",
                                        "ed_comparison.png"),
                           args.ed_title)
    else:
        run_all_analysis(args.out)
