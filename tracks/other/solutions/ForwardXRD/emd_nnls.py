#!/usr/bin/env python
"""EMD + non-negative background refinement, tested across four structures.

Milestone 1e. Two jobs.

1. Close the discontinuity found in m1d. There, a badly-wrong candidate got a
   negative refined scale, and ``max(scale * sim, 0)`` zeroed the simulation,
   making EMD undefined. Two fixes, both principled:

   - ``d_emd`` normalises both patterns to unit mass, so the scale factor is
     mathematically irrelevant to the distance. Never multiply by it. Its only
     legitimate job is to let the background fit find the right level.
   - Constrain scale >= 0 in the refinement (bounded least squares) so the
     background cannot absorb the whole pattern with a negative scale.
   - Fall back to the window width -- the largest W1 achievable on a bounded
     support -- if the background-subtracted observation has no mass left, so
     the metric stays finite and bounded everywhere.

2. Stop resting the whole result on rutile. Four structures, each with at least
   one genuine internal degree of freedom, so "solve the motif" is a real task:

     rutile TiO2    P4_2/mnm   O  at 4f  (u,u,0)     u = 0.3053
     anatase TiO2   I4_1/amd   O  at 8e  (0,0,z)     z = 0.2081
     quartz SiO2    P3_121     Si at 3a  (x,0,1/3)   x = 0.4697
     corundum Al2O3 R-3c       Al at 12c (0,0,z)     z = 0.3523

The landscape claim (single monotonic basin) was only ever checked noise-free,
so it is re-checked here against a noisy target as well.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
from pymatgen.core import Lattice, Structure
from scipy.optimize import brentq, lsq_linear

SOL = Path(__file__).parent
sys.path.insert(0, str(SOL))
from background_model import cheb_basis  # noqa: E402
from emd_metric import GRID, SPEC, d_cosine, d_emd  # noqa: E402
from xrd_reward import simulate_pattern  # noqa: E402

WINDOW = float(GRID.max() - GRID.min())  # largest possible W1 on this support
ORDER = 6
MATCHED_RMS = 0.08


# --------------------------------------------------------------------------
# the fixed metric
# --------------------------------------------------------------------------


def refine_nnls(obs: np.ndarray, sim: np.ndarray, order: int = ORDER):
    """Weighted least squares for (scale, Chebyshev background), scale >= 0."""
    w = 1.0 / np.maximum(obs, 1.0)  # Poisson counting variance
    basis = cheb_basis(order)
    design = np.column_stack([sim, basis])
    sw = np.sqrt(w)

    n_bg = basis.shape[1]
    lo = np.concatenate([[0.0], np.full(n_bg, -np.inf)])
    hi = np.full(n_bg + 1, np.inf)

    res = lsq_linear(design * sw[:, None], obs * sw, bounds=(lo, hi), method="bvls")
    scale = float(res.x[0])
    bg = basis @ res.x[1:]
    return scale, bg


def d_emd_bg(obs: np.ndarray, sim: np.ndarray, order: int = ORDER) -> float:
    """EMD between the simulation and the background-corrected observation.

    Scale-free by construction: ``d_emd`` normalises both arguments, so the
    refined scale never multiplies the simulation and cannot zero it out.
    """
    _, bg = refine_nnls(obs, sim, order)
    obs_c = np.maximum(obs - bg, 0.0)
    if obs_c.sum() <= 0.0 or sim.sum() <= 0.0:
        return WINDOW
    return d_emd(sim, obs_c)


# --------------------------------------------------------------------------
# test structures -- each has a real internal degree of freedom
# --------------------------------------------------------------------------


@dataclass
class Case:
    name: str
    param: str
    build: Callable[[float, float], Structure]


def _rutile(strain=0.0, dp=0.0):
    a, c = 4.5937 * (1 + strain), 2.9587 * (1 + strain)
    u = 0.3053 + dp
    return Structure.from_spacegroup(
        "P4_2/mnm", Lattice.tetragonal(a, c), ["Ti", "O"], [[0, 0, 0], [u, u, 0]]
    )


def _anatase(strain=0.0, dp=0.0):
    a, c = 3.7845 * (1 + strain), 9.5143 * (1 + strain)
    z = 0.2081 + dp
    return Structure.from_spacegroup(
        "I4_1/amd", Lattice.tetragonal(a, c), ["Ti", "O"], [[0, 0, 0], [0, 0, z]]
    )


def _quartz(strain=0.0, dp=0.0):
    a, c = 4.9137 * (1 + strain), 5.4047 * (1 + strain)
    x = 0.4697 + dp
    return Structure.from_spacegroup(
        "P3_121", Lattice.hexagonal(a, c), ["Si", "O"],
        [[x, 0, 1 / 3], [0.4135, 0.2669, 0.1191]],
    )


def _corundum(strain=0.0, dp=0.0):
    a, c = 4.7607 * (1 + strain), 12.9947 * (1 + strain)
    z = 0.3523 + dp
    return Structure.from_spacegroup(
        "R-3c", Lattice.hexagonal(a, c), ["Al", "O"], [[0, 0, z], [0.3064, 0, 0.25]]
    )


CASES = [
    Case("rutile TiO2", "u", _rutile),
    Case("anatase TiO2", "z", _anatase),
    Case("quartz SiO2", "x", _quartz),
    Case("corundum Al2O3", "z", _corundum),
]


def rms_disp(s: Structure, s0: Structure) -> float:
    d = np.array(s.cart_coords) - np.array(s0.cart_coords)
    return float(np.sqrt((d**2).sum(axis=1).mean()))


def noisy(structure, counts, bg_frac, seed=0):
    rng = np.random.default_rng(seed)
    clean = simulate_pattern(structure, SPEC)
    clean = clean / clean.max() * counts
    x = (GRID - GRID.min()) / (GRID.max() - GRID.min())
    bg = bg_frac * counts * (0.6 * np.exp(-3.0 * x) + 0.4 * (1.0 - 0.5 * x))
    return rng.poisson(np.maximum(clean + bg, 0.0)).astype(float)


def n_local_minima(curve: np.ndarray) -> int:
    return int(sum(1 for i in range(1, len(curve) - 1)
                   if curve[i] < curve[i - 1] and curve[i] < curve[i + 1]))


def monotonic_about(curve: np.ndarray, grid: np.ndarray, centre: float, tol=1e-12) -> bool:
    right = curve[grid >= centre]
    left = curve[grid <= centre][::-1]
    return bool(np.all(np.diff(right) >= -tol) and np.all(np.diff(left) >= -tol))


# --------------------------------------------------------------------------


def main() -> int:
    out = Path("tracks/other/results/m1e-emd-nnls")
    out.mkdir(parents=True, exist_ok=True)
    results = {}

    print(f"EMD + non-negative background refinement (Chebyshev order {ORDER})")
    print(f"matched rms atomic displacement = {MATCHED_RMS} A, "
          f"fallback = window width = {WINDOW:.1f} deg\n")

    # ---- 1. discontinuity check: refined scales must never be negative ----
    print("1. SCALE NON-NEGATIVITY (the m1d bug: lattice decoy scale went negative)")
    print(f"   {'structure':<16} {'scenario':<20} {'truth':>11} {'motif':>11} {'lattice':>11}")
    scale_rows = []
    for case in CASES:
        truth = case.build()
        p_truth = simulate_pattern(truth, SPEC)
        dp = brentq(lambda d: rms_disp(case.build(dp=d), truth) - MATCHED_RMS, 1e-6, 0.25)
        eps = brentq(lambda e: rms_disp(case.build(strain=e), truth) - MATCHED_RMS, 1e-8, 0.25)
        p_motif = simulate_pattern(case.build(dp=dp), SPEC)
        p_lat = simulate_pattern(case.build(strain=eps), SPEC)
        for label, counts, bg in (("noise-free", None, 0.0), ("10^4 counts, 10% bg", 1e4, 0.10)):
            tgt = p_truth.copy() if counts is None else noisy(truth, counts, bg)
            s = [refine_nnls(tgt, p)[0] for p in (p_truth, p_motif, p_lat)]
            scale_rows.append({"structure": case.name, "scenario": label,
                               "truth": s[0], "motif": s[1], "lattice": s[2]})
            print(f"   {case.name:<16} {label:<20} {s[0]:>11.4e} {s[1]:>11.4e} {s[2]:>11.4e}")
        results.setdefault(case.name, {})["decoys"] = {"dparam": dp, "strain": eps}

    # ---- 2. motif signal and anisotropy, per structure --------------------
    print("\n2. MOTIF SIGNAL and ANISOTROPY  (signal must be positive; "
          "anisotropy lower = more balanced)")
    hdr = (f"   {'structure':<16} {'scenario':<20} {'cos signal':>11} "
           f"{'emd signal':>11} {'gain':>7} {'emd aniso':>10}")
    print(hdr)
    metric_rows = []
    for case in CASES:
        truth = case.build()
        p_truth = simulate_pattern(truth, SPEC)
        dp = results[case.name]["decoys"]["dparam"]
        eps = results[case.name]["decoys"]["strain"]
        p_motif = simulate_pattern(case.build(dp=dp), SPEC)
        p_lat = simulate_pattern(case.build(strain=eps), SPEC)
        for label, counts, bg in (("noise-free", None, 0.0),
                                  ("10^5 counts, 5% bg", 1e5, 0.05),
                                  ("10^4 counts, 10% bg", 1e4, 0.10)):
            tgt = p_truth.copy() if counts is None else noisy(truth, counts, bg)
            cs = d_cosine(p_motif, tgt) - d_cosine(p_truth, tgt)
            base = d_emd_bg(tgt, p_truth)
            em = d_emd_bg(tgt, p_motif) - base
            el = d_emd_bg(tgt, p_lat) - base
            gain = em / cs if cs > 1e-12 else float("inf")
            an = el / em if em > 1e-12 else float("inf")
            metric_rows.append({"structure": case.name, "scenario": label, "cosine": cs,
                                "emd": em, "gain": gain, "anisotropy": an})
            print(f"   {case.name:<16} {label:<20} {cs:>11.5f} {em:>11.5f} "
                  f"{gain:>6.1f}x {an:>9.1f}x")

    # ---- 3. landscape, noise-free AND noisy -------------------------------
    print("\n3. LANDSCAPE -- strain scan +/-10%, 201 points  (1 minimum + monotonic = searchable)")
    hdr3 = (f"   {'structure':<16} {'scenario':<20} {'cos minima':>11} {'cos mono':>9} "
            f"{'emd minima':>11} {'emd mono':>9}")
    print(hdr3)
    eps_grid = np.linspace(-0.10, 0.10, 201)
    land_rows = []
    for case in CASES:
        truth = case.build()
        p_truth = simulate_pattern(truth, SPEC)
        cands = [simulate_pattern(case.build(strain=e), SPEC) for e in eps_grid]
        for label, counts, bg in (("noise-free", None, 0.0), ("10^4 counts, 10% bg", 1e4, 0.10)):
            tgt = p_truth.copy() if counts is None else noisy(truth, counts, bg)
            c_curve = np.array([d_cosine(p, tgt) for p in cands])
            e_curve = np.array([d_emd_bg(tgt, p) for p in cands])
            row = {
                "structure": case.name, "scenario": label,
                "cos_minima": n_local_minima(c_curve),
                "cos_monotonic": monotonic_about(c_curve, eps_grid, 0.0),
                "emd_minima": n_local_minima(e_curve),
                "emd_monotonic": monotonic_about(e_curve, eps_grid, 0.0),
            }
            land_rows.append(row)
            print(f"   {case.name:<16} {label:<20} {row['cos_minima']:>11} "
                  f"{str(row['cos_monotonic']):>9} {row['emd_minima']:>11} "
                  f"{str(row['emd_monotonic']):>9}")

    # ---- 4. window-truncation caveat -------------------------------------
    print("\n4. WINDOW-TRUNCATION CHECK (rutile) -- is the smooth ramp real or an artifact?")
    from xrd_reward import PatternSpec
    print(f"   {'2theta window':<20} {'emd minima':>11} {'emd monotonic':>14}")
    win_rows = []
    for lo, hi, npts in ((10.0, 90.0, 4096), (5.0, 120.0, 6144), (5.0, 150.0, 8192)):
        spec = PatternSpec(two_theta_min=lo, two_theta_max=hi, n_points=npts)
        g = spec.grid
        w_full = float(g.max() - g.min())

        def emd_w(obs, sim):
            wts = 1.0 / np.maximum(obs, 1.0)
            xn = 2.0 * (g - g.min()) / (g.max() - g.min()) - 1.0
            cols = [np.ones_like(xn), xn]
            for k in range(2, ORDER + 1):
                cols.append(2.0 * xn * cols[-1] - cols[-2])
            basis = np.column_stack(cols)
            design = np.column_stack([sim, basis])
            sw = np.sqrt(wts)
            lo_b = np.concatenate([[0.0], np.full(basis.shape[1], -np.inf)])
            hi_b = np.full(basis.shape[1] + 1, np.inf)
            r = lsq_linear(design * sw[:, None], obs * sw, bounds=(lo_b, hi_b), method="bvls")
            oc = np.maximum(obs - basis @ r.x[1:], 0.0)
            if oc.sum() <= 0 or sim.sum() <= 0:
                return w_full
            ca, cb = np.cumsum(sim / sim.sum()), np.cumsum(oc / oc.sum())
            return float(np.abs(ca - cb).sum() * (g[1] - g[0]))

        t = _rutile()
        pt = simulate_pattern(t, spec)
        curve = np.array([emd_w(pt, simulate_pattern(_rutile(strain=e), spec)) for e in eps_grid])
        row = {"window": f"{lo}-{hi}", "minima": n_local_minima(curve),
               "monotonic": monotonic_about(curve, eps_grid, 0.0)}
        win_rows.append(row)
        print(f"   {f'{lo:g}-{hi:g} deg':<20} {row['minima']:>11} {str(row['monotonic']):>14}")

    payload = {
        "run": "m1e-emd-nnls",
        "challenge": "QuantumBFS/quantum.harness#68",
        "team": "ForwardXRD",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "chebyshev_order": ORDER,
        "matched_rms_displacement_angstrom": MATCHED_RMS,
        "scales": scale_rows,
        "metrics": metric_rows,
        "landscape": land_rows,
        "window_check": win_rows,
    }
    (out / "run.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\nwrote {out / 'run.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
