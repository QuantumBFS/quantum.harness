#!/usr/bin/env python
"""Earth Mover's Distance as the XRD fit metric.

Milestone 1c. Cosine similarity is a *pointwise* comparison: once two peaks
stop overlapping, the inner product vanishes no matter how far apart they are.
That produces (a) a needle-shaped landscape in lattice parameter with satellite
local maxima, and (b) near-blindness to intensity redistribution, because
moving weight between two peaks barely changes the inner product.

The 1-Wasserstein distance (EMD) charges the *transport cost* of turning one
pattern into the other, so:

  - a shifted peak costs ~ the shift distance      -> smooth, no cliff
  - intensity moved between peaks costs ~ their separation -> motif sensitive

For 1D distributions on a uniform grid, W1 is exact and O(n):

    W1(a, b) = integral |CDF_a(x) - CDF_b(x)| dx        [units: degrees 2theta]

Tests, all on rutile TiO2 (P4_2/mnm, O at 4f (u,u,0), u = 0.3053):
  A  anisotropy at matched rms atomic displacement (unitless -> comparable)
  B  landscape roughness: local extrema in a strain scan
  C  motif sensitivity: the u-scan
  D  robustness to counting noise and background
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SOL = Path(__file__).parent
sys.path.insert(0, str(SOL))
from xrd_reward import PatternSpec, cosine_similarity, simulate_pattern  # noqa: E402

SPEC = PatternSpec()
GRID = SPEC.grid
DX = float(GRID[1] - GRID[0])


# --------------------------------------------------------------------------
# metrics -- all return a DISSIMILARITY (0 = identical, larger = more distinct)
# --------------------------------------------------------------------------


def d_cosine(a: np.ndarray, b: np.ndarray) -> float:
    return 1.0 - cosine_similarity(a, b)


def d_emd(a: np.ndarray, b: np.ndarray) -> float:
    """Exact 1D 1-Wasserstein distance, in degrees 2-theta.

    Both patterns are normalised to unit mass first -- EMD requires equal mass,
    and the fit should not depend on overall scale.
    """
    sa, sb = a.sum(), b.sum()
    if sa <= 0 or sb <= 0:
        return float("inf")
    ca = np.cumsum(a / sa)
    cb = np.cumsum(b / sb)
    return float(np.abs(ca - cb).sum() * DX)


def d_rwp(a: np.ndarray, b: np.ndarray, floor: float = 1e-4) -> float:
    """Naive Rietveld weighted residual (b = target), for reference."""
    w = 1.0 / np.maximum(b, b.max() * floor)
    den_s = np.sum(w * a * a)
    s = np.sum(w * b * a) / den_s if den_s > 0 else 1.0
    num = np.sum(w * (b - s * a) ** 2)
    den = np.sum(w * b * b)
    return float(np.sqrt(num / den)) if den > 0 else 0.0


METRICS = {"cosine": d_cosine, "emd": d_emd, "rwp": d_rwp}


def subtract_linear_background(y: np.ndarray) -> np.ndarray:
    """Crude rolling-minimum background removal, for the noisy-data test."""
    k = max(3, len(y) // 64)
    pad = np.pad(y, k, mode="edge")
    base = np.array([pad[i : i + 2 * k + 1].min() for i in range(len(y))])
    return np.maximum(y - base, 0.0)


def noisy_target(structure, peak_counts, bg_frac, seed=0):
    rng = np.random.default_rng(seed)
    clean = simulate_pattern(structure, SPEC)
    clean = clean / clean.max() * peak_counts
    x = (GRID - GRID.min()) / (GRID.max() - GRID.min())
    bg = bg_frac * peak_counts * (0.6 * np.exp(-3.0 * x) + 0.4 * (1.0 - 0.5 * x))
    return rng.poisson(np.maximum(clean + bg, 0.0)).astype(float)


# --------------------------------------------------------------------------


def main() -> int:
    from reward_variants import A, C, MATCHED_RMS, U, decoys, rms_disp, rutile  # noqa: PLC0415
    out = Path("tracks/other/results/m1c-emd")
    out.mkdir(parents=True, exist_ok=True)

    truth, motif, lattice, du, eps = decoys(MATCHED_RMS)
    p_truth = simulate_pattern(truth, SPEC)
    p_motif = simulate_pattern(motif, SPEC)
    p_lat = simulate_pattern(lattice, SPEC)

    print(f"rutile TiO2  P4_2/mnm  a={A} c={C} u={U}")
    print(f"matched rms atomic displacement = {MATCHED_RMS:.3f} A")
    print(f"  motif decoy   : u -> {U + du:.4f}")
    print(f"  lattice decoy : strain {eps:+.4%}\n")

    # ---- A: anisotropy at matched displacement --------------------------
    print("A. ANISOTROPY at matched rms displacement (lower = more balanced)")
    hdr = f"  {'metric':<10} {'D_motif':>12} {'D_lattice':>12} {'anisotropy':>12}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    aniso = {}
    for name, fn in METRICS.items():
        dm = fn(p_motif, p_truth)
        dl = fn(p_lat, p_truth)
        r = dl / dm if dm > 1e-15 else float("inf")
        aniso[name] = {"D_motif": dm, "D_lattice": dl, "anisotropy": r}
        unit = " deg" if name == "emd" else ""
        print(f"  {name:<10} {dm:>12.5f}{unit} {dl:>12.5f} {r:>12.1f}x")

    # ---- B: landscape roughness in the strain scan ----------------------
    print("\nB. LANDSCAPE ROUGHNESS -- strain scan, +/-10%, 401 points")
    eps_grid = np.linspace(-0.10, 0.10, 401)
    strain_curves = {}
    print(f"  {'metric':<10} {'local minima':>13} {'monotonic?':>12} {'argmin strain':>15}")
    for name, fn in METRICS.items():
        curve = np.array(
            [fn(simulate_pattern(rutile(a=A * (1 + e), c=C * (1 + e)), SPEC), p_truth)
             for e in eps_grid]
        )
        strain_curves[name] = curve.tolist()
        n_min = int(sum(1 for i in range(1, len(curve) - 1)
                        if curve[i] < curve[i - 1] and curve[i] < curve[i + 1]))
        right = curve[eps_grid >= 0]
        left = curve[eps_grid <= 0][::-1]
        mono = bool(np.all(np.diff(right) >= -1e-12) and np.all(np.diff(left) >= -1e-12))
        print(f"  {name:<10} {n_min:>13} {str(mono):>12} "
              f"{eps_grid[int(np.argmin(curve))]:>14.4%}")

    # ---- C: motif sensitivity, the u-scan -------------------------------
    print("\nC. MOTIF SENSITIVITY -- u-scan about u = 0.3053")
    u_grid = np.linspace(U - 0.06, U + 0.06, 49)
    u_curves = {}
    print(f"  {'metric':<10} {'half-width in u':>17}  (smaller = sharper)")
    for name, fn in METRICS.items():
        curve = np.array([fn(simulate_pattern(rutile(u=uu), SPEC), p_truth) for uu in u_grid])
        u_curves[name] = curve.tolist()
        span = curve.max() - curve.min()
        if span <= 0:
            print(f"  {name:<10} {'n/a':>17}")
            continue
        thresh = curve.min() + 0.10 * span
        hw = float(np.abs(u_grid[curve <= thresh] - U).max())
        print(f"  {name:<10} {hw:>17.4f}")

    # ---- D: robustness to noise ------------------------------------------
    print("\nD. NOISE ROBUSTNESS -- motif signal = D(decoy) - D(truth), vs noisy target")
    scenarios = [
        ("noise-free", None, 0.0),
        ("10^6 counts, 2% bg", 1e6, 0.02),
        ("10^5 counts, 5% bg", 1e5, 0.05),
        ("10^4 counts, 10% bg", 1e4, 0.10),
        ("10^3 counts, 20% bg", 1e3, 0.20),
    ]
    print(f"  {'scenario':<22} {'cosine':>11} {'emd (raw)':>12} {'emd (bg-sub)':>14} {'rwp':>11}")
    print("  " + "-" * 72)
    noise_rows = []
    for label, counts, bg in scenarios:
        tgt = p_truth.copy() if counts is None else noisy_target(truth, counts, bg)
        tgt_bs = tgt if counts is None else subtract_linear_background(tgt)
        row = {"scenario": label}
        row["cosine"] = d_cosine(p_motif, tgt) - d_cosine(p_truth, tgt)
        row["emd_raw"] = d_emd(p_motif, tgt) - d_emd(p_truth, tgt)
        row["emd_bgsub"] = d_emd(p_motif, tgt_bs) - d_emd(p_truth, tgt_bs)
        row["rwp"] = d_rwp(p_motif, tgt) - d_rwp(p_truth, tgt)
        noise_rows.append(row)
        print(f"  {label:<22} {row['cosine']:>11.5f} {row['emd_raw']:>12.5f} "
              f"{row['emd_bgsub']:>14.5f} {row['rwp']:>11.5f}")

    payload = {
        "run": "m1c-emd",
        "challenge": "QuantumBFS/quantum.harness#68",
        "team": "ForwardXRD",
        "question": "does Earth Mover's Distance fix the cliff landscape and the motif blindness?",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "test_case": {"formula": "TiO2", "spacegroup": "P4_2/mnm", "a": A, "c": C, "u": U},
        "matched_rms_displacement_angstrom": MATCHED_RMS,
        "anisotropy": aniso,
        "eps_grid": eps_grid.tolist(),
        "strain_curves": strain_curves,
        "u_grid": u_grid.tolist(),
        "u_curves": u_curves,
        "noise": noise_rows,
    }
    (out / "run.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\nwrote {out / 'run.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
