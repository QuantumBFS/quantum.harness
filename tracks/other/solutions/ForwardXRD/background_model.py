#!/usr/bin/env python
"""Joint background + scale refinement, and what it does to each fit metric.

Milestone 1d. Both the Rietveld weighted residual and EMD collapsed under
realistic noise for the same reason: the observed pattern carries a background
that the simulated pattern does not, so the two were never comparable.

The fix is what a real Rietveld refinement does -- model the observation as

    obs(x)  ~  s * sim(x)  +  sum_k c_k T_k(x)

with T_k Chebyshev polynomials. This is *linear* in (s, c_0..c_n), so weighted
least squares solves it exactly, per candidate, at negligible cost. Weights are
counting variance, w = 1/max(obs, 1), as Poisson statistics require.

Then:
  - R_wp is evaluated on the refined residual
  - EMD is evaluated between the scaled simulation and the background-subtracted
    observation, which restores the equal-mass condition optimal transport needs

The control that matters: a sufficiently flexible background can absorb the
mismatch of a *wrong* structure and hide it. Polynomial order is therefore swept,
and background absorption is measured directly.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SOL = Path(__file__).parent
sys.path.insert(0, str(SOL))
from emd_metric import GRID, SPEC, d_cosine, d_emd, noisy_target  # noqa: E402
from xrd_reward import simulate_pattern  # noqa: E402

# Chebyshev basis on the 2-theta window, mapped to [-1, 1]
XN = 2.0 * (GRID - GRID.min()) / (GRID.max() - GRID.min()) - 1.0


def cheb_basis(order: int) -> np.ndarray:
    """Columns T_0..T_order evaluated on the grid."""
    cols = [np.ones_like(XN), XN]
    for k in range(2, order + 1):
        cols.append(2.0 * XN * cols[-1] - cols[-2])
    return np.column_stack(cols[: order + 1])


def refine(obs: np.ndarray, sim: np.ndarray, order: int = 6):
    """Weighted least squares for scale + Chebyshev background.

    Returns (scale, background, model, weights).
    """
    w = 1.0 / np.maximum(obs, 1.0)  # Poisson counting variance
    design = np.column_stack([sim, cheb_basis(order)])
    sw = np.sqrt(w)
    coef, *_ = np.linalg.lstsq(design * sw[:, None], obs * sw, rcond=None)
    scale = float(coef[0])
    bg = cheb_basis(order) @ coef[1:]
    return scale, bg, design @ coef, w


def rwp_refined(obs: np.ndarray, sim: np.ndarray, order: int = 6) -> float:
    _, _, model, w = refine(obs, sim, order)
    num = np.sum(w * (obs - model) ** 2)
    den = np.sum(w * obs**2)
    return float(np.sqrt(num / den)) if den > 0 else 0.0


def emd_refined(obs: np.ndarray, sim: np.ndarray, order: int = 6) -> float:
    """EMD after removing the refined background from the observation."""
    scale, bg, _, _ = refine(obs, sim, order)
    obs_corr = np.maximum(obs - bg, 0.0)
    sim_scaled = np.maximum(scale * sim, 0.0)
    if obs_corr.sum() <= 0 or sim_scaled.sum() <= 0:
        return float("inf")
    return d_emd(sim_scaled, obs_corr)


# --------------------------------------------------------------------------


SCENARIOS = [
    ("noise-free", None, 0.0),
    ("10^6 counts, 2% bg", 1e6, 0.02),
    ("10^5 counts, 5% bg", 1e5, 0.05),
    ("10^4 counts, 10% bg", 1e4, 0.10),
    ("10^3 counts, 20% bg", 1e3, 0.20),
]


def main() -> int:
    from reward_variants import A, C, MATCHED_RMS, U, decoys, rutile  # noqa: PLC0415
    out = Path("tracks/other/results/m1d-background")
    out.mkdir(parents=True, exist_ok=True)

    truth, motif, lattice, du, eps = decoys(MATCHED_RMS)
    p_truth = simulate_pattern(truth, SPEC)
    p_motif = simulate_pattern(motif, SPEC)
    p_lat = simulate_pattern(lattice, SPEC)

    print(f"rutile TiO2, matched rms displacement {MATCHED_RMS:.3f} A")
    print(f"  motif decoy u -> {U + du:.4f} | lattice decoy strain {eps:+.4%}")
    print("  motif signal = D(motif decoy) - D(truth); must be POSITIVE and large\n")

    ORDER = 6
    hdr = (f"  {'scenario':<22} {'cosine':>10} {'emd raw':>10} "
           f"{'emd+bg':>10} {'rwp raw':>10} {'rwp+bg':>10}")
    print(f"A. MOTIF SIGNAL, Chebyshev order {ORDER}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))

    rows = []
    for label, counts, bg_frac in SCENARIOS:
        tgt = p_truth.copy() if counts is None else noisy_target(truth, counts, bg_frac)
        row = {
            "scenario": label,
            "cosine": d_cosine(p_motif, tgt) - d_cosine(p_truth, tgt),
            "emd_raw": d_emd(p_motif, tgt) - d_emd(p_truth, tgt),
            "emd_bg": emd_refined(tgt, p_motif, ORDER) - emd_refined(tgt, p_truth, ORDER),
            "rwp_raw": None,
            "rwp_bg": rwp_refined(tgt, p_motif, ORDER) - rwp_refined(tgt, p_truth, ORDER),
        }
        # naive rwp for reference (weights from observed intensity, no background)
        from emd_metric import d_rwp

        row["rwp_raw"] = d_rwp(p_motif, tgt) - d_rwp(p_truth, tgt)
        rows.append(row)
        print(f"  {label:<22} {row['cosine']:>10.5f} {row['emd_raw']:>10.5f} "
              f"{row['emd_bg']:>10.5f} {row['rwp_raw']:>10.5f} {row['rwp_bg']:>10.5f}")

    # ---- B: does a flexible background absorb a wrong structure? ----------
    print("\nB. BACKGROUND-ABSORPTION CONTROL -- 10^4 counts, 10% bg")
    print("   higher order = more flexible = more able to hide a wrong structure")
    tgt = noisy_target(truth, 1e4, 0.10)
    print(f"  {'order':>6} {'emd motif signal':>18} {'rwp motif signal':>18} {'rwp(truth)':>12}")
    order_rows = []
    for order in (0, 2, 4, 6, 8, 12, 20):
        es = emd_refined(tgt, p_motif, order) - emd_refined(tgt, p_truth, order)
        rs = rwp_refined(tgt, p_motif, order) - rwp_refined(tgt, p_truth, order)
        rt = rwp_refined(tgt, p_truth, order)
        order_rows.append({"order": order, "emd_signal": es, "rwp_signal": rs, "rwp_truth": rt})
        print(f"  {order:>6} {es:>18.5f} {rs:>18.5f} {rt:>12.5f}")

    # ---- C: lattice signal too, for the anisotropy ------------------------
    print("\nC. ANISOTROPY after background refinement (order 6)")
    print(f"  {'scenario':<22} {'emd motif':>11} {'emd lattice':>13} {'anisotropy':>12}")
    aniso_rows = []
    for label, counts, bg_frac in SCENARIOS:
        tgt = p_truth.copy() if counts is None else noisy_target(truth, counts, bg_frac)
        base = emd_refined(tgt, p_truth, ORDER)
        em = emd_refined(tgt, p_motif, ORDER) - base
        el = emd_refined(tgt, p_lat, ORDER) - base
        a = el / em if em > 1e-12 else float("inf")
        aniso_rows.append({"scenario": label, "emd_motif": em, "emd_lattice": el, "anisotropy": a})
        print(f"  {label:<22} {em:>11.5f} {el:>13.5f} {a:>11.1f}x")

    payload = {
        "run": "m1d-background",
        "challenge": "QuantumBFS/quantum.harness#68",
        "team": "ForwardXRD",
        "question": "does joint background+scale refinement rescue EMD and Rwp on noisy data?",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "chebyshev_order": ORDER,
        "matched_rms_displacement_angstrom": MATCHED_RMS,
        "motif_signal": rows,
        "background_absorption": order_rows,
        "anisotropy": aniso_rows,
    }
    (out / "run.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\nwrote {out / 'run.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
