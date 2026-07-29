"""METTS run driver for the B effort.

Produces the metts_runs/ tree (configs/, traces/, comparisons/, logs/, reports/)
and the metts_vs_ed.csv comparison table mandated by the B task spec §9.

Usage:
    python -m metts_b.run --config configs/2x2_h3.0.yaml
    python -m metts_b.run --Lx 2 --Ly 2 --h 3.0 --backend dense \\
        --evolve trotter --dtau 0.05 --n-production 1000 --out metts_runs/2x2_h3.0
"""
from __future__ import annotations

import os
import sys
import json
import time
import argparse
import numpy as np

# make `metts_b` importable when run as a script from the memberB root
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from metts_b.bridge import (  # noqa: E402
    ed_thermodynamics, write_csv, write_manifest, rel_err,
)
from metts_b.config import METTSConfig, load_config, config_from_dict  # noqa: E402
from metts_b.chain import metts_scan, config_hash, git_version  # noqa: E402
from metts_b.measure import DenseBackend  # noqa: E402
from metts_b import status  # noqa: E402


def make_backend(cfg):
    if cfg.backend == "dense":
        return DenseBackend(cfg.Lx, cfg.Ly, cfg.h, J=cfg.J,
                            dtau=cfg.dtau, evolve=cfg.evolve_mode,
                            mem_guard=cfg.mem_guard)
    if cfg.backend == "mps":
        from metts_b.mps_backend import MPSBackend
        return MPSBackend(cfg.Lx, cfg.Ly, cfg.h, J=cfg.J, dtau=cfg.dtau,
                          max_bond_dim=cfg.max_bond_dim,
                          trunc_tol=cfg.trunc_tol, evolve=cfg.evolve_mode,
                          mem_guard=cfg.mem_guard)
    raise ValueError(f"unknown backend {cfg.backend}")


def run(cfg: METTSConfig):
    t0 = time.time()
    os.makedirs(cfg.out_dir, exist_ok=True)
    traces_root = os.path.join(cfg.out_dir, "traces")
    logs = os.path.join(cfg.out_dir, "logs")
    comparisons = os.path.join(cfg.out_dir, "comparisons")
    configs_dir = os.path.join(cfg.out_dir, "configs")
    for d in (traces_root, logs, comparisons, configs_dir):
        os.makedirs(d, exist_ok=True)

    # snapshot the config
    cfg_path = os.path.join(configs_dir, "run_config.yaml")
    try:
        import yaml
        with open(cfg_path, "w") as f:
            yaml.safe_dump(cfg.to_dict(), f, sort_keys=False)
    except Exception:
        with open(os.path.join(configs_dir, "run_config.json"), "w") as f:
            json.dump(cfg.to_dict(), f, indent=2)

    chash = config_hash(cfg.to_dict())
    gver = git_version()

    backend = make_backend(cfg)
    N = cfg.Lx * cfg.Ly

    # ED reference (small system only; for N>12 ED refuses and we skip it)
    ed_results = {}
    ed_available = N <= 12
    if ed_available:
        try:
            ed_results = {r.beta: r for r in
                          ed_thermodynamics(cfg.Lx, cfg.Ly, cfg.h, cfg.betas)}
        except Exception as e:
            ed_available = False
            with open(os.path.join(logs, "errors.log"), "a") as f:
                f.write(f"ED failed: {e!r}\n")

    # METTS scan
    rows = metts_scan(
        backend, cfg.betas, cfg.n_warmup, cfg.n_production, cfg.seed,
        cfg.dtau, evolve_mode=cfg.evolve_mode, trace_root=traces_root,
        write_traces=cfg.write_traces, prob_tol=cfg.prob_tol, basis=cfg.basis,
        n_chains=cfg.n_chains,
    )

    # build comparison + manifest
    comp_rows = []
    thermo_rows = []
    n_failed_total = 0
    n_ok_total = 0
    for r in rows:
        beta = r["beta"]
        row = {
            "beta": beta, "u_metts": r["u"], "u_err": r["u_err"],
            "C_metts": r["C"], "C_err": r["C_err"], "f_metts": r["f"],
            "n_samples": r["n_samples"], "n_chains": r["n_chains"],
            "rhat_u": r["rhat_u"], "n_failed": r.get("n_failed", 0),
            "status": r["status"],
        }
        n_failed_total += r.get("n_failed", 0)
        n_ok_total += r["n_samples"]
        if beta in ed_results:
            ed = ed_results[beta]
            row.update({
                "u_ed": ed.u, "C_ed": ed.C, "f_ed": ed.f,
                "u_abs_err": abs(r["u"] - ed.u),
                "u_rel_err": rel_err(r["u"], ed.u),
                "C_abs_err": abs(r["C"] - ed.C),
                "C_rel_err": rel_err(r["C"], ed.C),
                "f_abs_err": abs(r["f"] - ed.f),
                "f_rel_err": rel_err(r["f"], ed.f),
            })
        comp_rows.append(row)
        thermo_rows.append({
            "beta": beta, "f": r["f"], "u": r["u"], "C": r["C"],
            "u_err": r["u_err"], "C_err": r["C_err"],
            "n_samples": r["n_samples"], "rhat_u": r["rhat_u"],
        })

    comp_fields = ["beta", "u_metts", "u_err", "C_metts", "C_err", "f_metts",
                   "n_samples", "n_chains", "rhat_u", "n_failed", "status",
                   "u_ed", "C_ed", "f_ed", "u_abs_err", "u_rel_err",
                   "C_abs_err", "C_rel_err", "f_abs_err", "f_rel_err"]
    write_csv(os.path.join(comparisons, "metts_vs_ed.csv"), comp_rows,
              comp_fields)
    write_csv(os.path.join(cfg.out_dir, "thermodynamics.csv"), thermo_rows,
              ["beta", "f", "u", "C", "u_err", "C_err", "n_samples", "rhat_u"])

    manifest = {
        "run_id": cfg.run_id(), "label": cfg.label,
        "Lx": cfg.Lx, "Ly": cfg.Ly, "h": cfg.h, "J": cfg.J, "N": N,
        "backend": cfg.backend, "evolve_mode": cfg.evolve_mode,
        "dtau": cfg.dtau, "trotter_order": cfg.trotter_order,
        "n_warmup": cfg.n_warmup, "n_production": cfg.n_production,
        "n_chains": cfg.n_chains, "seed": cfg.seed, "basis": cfg.basis,
        "betas": cfg.betas, "config_hash": chash, "code_version": gver,
        "wall_time_s": time.time() - t0, "n_samples_total": n_ok_total,
        "n_failed_total": n_failed_total,
        "ed_available": ed_available,
        "status": "OK" if n_failed_total == 0 else "partial",
        "max_bond_dim": (cfg.max_bond_dim if cfg.backend == "mps"
                         else 2 ** N if cfg.evolve_mode != "spectral" else None),
    }
    write_manifest(os.path.join(cfg.out_dir, "manifest.json"), manifest)

    # console summary (the comparison table, §9.3)
    print(f"\n=== METTS run {cfg.run_id()} ===")
    print(f"backend={cfg.backend} evolve={cfg.evolve_mode} dtau={cfg.dtau} "
          f"N={N} h={cfg.h} chains={cfg.n_chains} "
          f"warmup={cfg.n_warmup} prod={cfg.n_production} seed={cfg.seed}")
    print(f"wall_time={manifest['wall_time_s']:.1f}s "
          f"ok_samples={n_ok_total} failed={n_failed_total} "
          f"config_hash={chash} git={gver}")
    if ed_available:
        hdr = (f"{'beta':>5} {'u_metts':>10} {'u_ed':>10} {'u_rel%':>7} "
               f"{'C_metts':>10} {'C_ed':>10} {'C_rel%':>7} {'nsamp':>7} "
               f"{'rhat':>6}")
        print(hdr)
        for r in comp_rows:
            if "u_ed" in r:
                print(f"{r['beta']:5.2f} {r['u_metts']:10.5f} {r['u_ed']:10.5f} "
                      f"{100*r['u_rel_err']:7.2f} {r['C_metts']:10.5f} "
                      f"{r['C_ed']:10.5f} {100*r['C_rel_err']:7.2f} "
                      f"{r['n_samples']:7d} {r['rhat_u']:6.3f}")
    else:
        for r in comp_rows:
            print(f"beta={r['beta']:.2f} u={r['u_metts']:.5f}+-{r['u_err']:.2e} "
                  f"C={r['C_metts']:.5f}+-{r['C_err']:.2e} "
                  f"f={r['f_metts']:.5f} nsamp={r['n_samples']} "
                  f"rhat={r['rhat_u']:.3f}")
    print(f"\ntraces  -> {traces_root}")
    print(f"compare -> {os.path.join(comparisons, 'metts_vs_ed.csv')}")
    print(f"manifest-> {os.path.join(cfg.out_dir, 'manifest.json')}")
    return manifest, comp_rows


def main(argv=None):
    p = argparse.ArgumentParser(description="METTS run driver (B effort)")
    p.add_argument("--config", help="YAML config file")
    p.add_argument("--Lx", type=int)
    p.add_argument("--Ly", type=int)
    p.add_argument("--h", type=float)
    p.add_argument("--backend", choices=["dense", "mps"])
    p.add_argument("--evolve", choices=["trotter", "spectral"])
    p.add_argument("--dtau", type=float)
    p.add_argument("--n-warmup", type=int)
    p.add_argument("--n-production", type=int)
    p.add_argument("--n-chains", type=int)
    p.add_argument("--seed", type=int)
    p.add_argument("--betas", type=str,
                   help="comma-separated beta list, e.g. 0.1,0.3,0.5,1.0")
    p.add_argument("--max-bond-dim", type=int)
    p.add_argument("--out", type=str)
    p.add_argument("--label", type=str)
    p.add_argument("--no-traces", action="store_true")
    args = p.parse_args(argv)

    if args.config:
        cfg = load_config(args.config)
    else:
        cfg = METTSConfig()
    # CLI overrides
    for k, v in [("Lx", args.Lx), ("Ly", args.Ly), ("h", args.h),
                 ("backend", args.backend), ("evolve_mode", args.evolve),
                 ("dtau", args.dtau), ("n_warmup", args.n_warmup),
                 ("n_production", args.n_production), ("n_chains", args.n_chains),
                 ("seed", args.seed), ("max_bond_dim", args.max_bond_dim),
                 ("out_dir", args.out), ("label", args.label)]:
        if v is not None:
            setattr(cfg, k, v)
    if args.betas:
        cfg.betas = [float(b) for b in args.betas.split(",")]
    if args.no_traces:
        cfg.write_traces = False
    if not cfg.label or cfg.label == "default":
        cfg.label = f"{cfg.Lx}x{cfg.Ly}_h{cfg.h:g}_{cfg.evolve_mode}"
    if cfg.out_dir == "metts_runs/run_default":
        cfg.out_dir = os.path.join("metts_runs", cfg.label)
    run(cfg)


if __name__ == "__main__":
    main()
