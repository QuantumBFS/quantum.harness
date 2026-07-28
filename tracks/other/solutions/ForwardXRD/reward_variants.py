#!/usr/bin/env python
"""Which fit metric can actually see the atomic motif?

Milestone 1b. The baseline cosine reward is ~500-1600x more sensitive to the
lattice than to the motif at matched atomic displacement (see
``xrd_reward.py`` and the rutile probe). This asks whether that is a property
of the *metric* or of the *data*.

Prediction: it is the metric. Rietveld refinement determines atomic positions
from powder patterns as a matter of routine, so the motif information is in
the data. A plain inner product is dominated by the strongest peaks, while the
motif signal lives largely in the weak ones -- which is precisely why Rietveld
weights its residual by 1/I.

Test: rutile TiO2 (P4_2/mnm), O at 4f (u, u, 0), u = 0.3053 -- one genuine
internal degree of freedom. Two decoy families are built at the *same* rms
atomic displacement:

  motif decoy    -- shift u          (moves intensities only)
  lattice decoy  -- isotropic strain (moves peak positions)

A metric is good for structure solution if its motif dissimilarity is large in
absolute terms, i.e. a wrong motif is actually penalised.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
from pymatgen.core import Lattice, Structure
from scipy.optimize import brentq

sys.path.insert(0, str(Path(__file__).parent))
from xrd_reward import PatternSpec, cosine_similarity, simulate_pattern  # noqa: E402

A, C, U = 4.5937, 2.9587, 0.3053
MATCHED_RMS = 0.08  # angstrom -- the displacement at which decoys are compared


def rutile(a: float = A, c: float = C, u: float = U) -> Structure:
    return Structure.from_spacegroup(
        "P4_2/mnm", Lattice.tetragonal(a, c), ["Ti", "O"], [[0, 0, 0], [u, u, 0]]
    )


def rms_disp(s: Structure, s0: Structure) -> float:
    d = np.array(s.cart_coords) - np.array(s0.cart_coords)
    return float(np.sqrt((d**2).sum(axis=1).mean()))


# --------------------------------------------------------------------------
# metric variants
# --------------------------------------------------------------------------


def _identity(x: np.ndarray) -> np.ndarray:
    return x


def _sqrt(x: np.ndarray) -> np.ndarray:
    return np.sqrt(np.maximum(x, 0.0))


def _log(x: np.ndarray) -> np.ndarray:
    m = x.max()
    return np.log1p(np.maximum(x, 0.0) / m * 1.0e3) if m > 0 else x


@dataclass
class Variant:
    name: str
    note: str
    spec: PatternSpec = field(default_factory=PatternSpec)
    transform: Callable[[np.ndarray], np.ndarray] = _identity
    metric: str = "cosine"  # "cosine" | "rwp"
    window: tuple[float, float] | None = None


def dissimilarity(cand: Structure, truth: Structure, v: Variant) -> float:
    """0 = identical patterns; larger = more distinguishable."""
    ic = simulate_pattern(cand, v.spec)
    it = simulate_pattern(truth, v.spec)

    if v.window is not None:
        g = v.spec.grid
        m = (g >= v.window[0]) & (g <= v.window[1])
        ic, it = ic[m], it[m]

    ic, it = v.transform(ic), v.transform(it)

    if v.metric == "cosine":
        return 1.0 - cosine_similarity(ic, it)

    # Rietveld-style weighted profile residual, with the scale factor refined
    # out (as a real Rietveld refinement does).
    w = 1.0 / np.maximum(it, it.max() * 1.0e-4)
    denom = np.sum(w * ic * ic)
    scale = np.sum(w * it * ic) / denom if denom > 0 else 1.0
    num = np.sum(w * (it - scale * ic) ** 2)
    den = np.sum(w * it * it)
    return float(np.sqrt(num / den)) if den > 0 else 0.0


VARIANTS = [
    Variant("cosine-linear (baseline)", "plain inner product, linear intensity"),
    Variant("cosine-sqrt", "sqrt intensity compression", transform=_sqrt),
    Variant("cosine-log", "log intensity compression", transform=_log),
    Variant("cosine-highangle", "linear, 2theta restricted to 50-90 deg", window=(50.0, 90.0)),
    Variant(
        "cosine-narrow-fwhm",
        "linear, FWHM 0.05 deg (finer grid)",
        spec=PatternSpec(fwhm=0.05, n_points=16384),
    ),
    Variant("rwp-rietveld", "weighted profile residual, w = 1/I", metric="rwp"),
    Variant("rwp-sqrt", "weighted residual on sqrt intensity", transform=_sqrt, metric="rwp"),
]


# --------------------------------------------------------------------------
# matched decoys
# --------------------------------------------------------------------------


def decoys(target_rms: float):
    """Build a motif decoy and a lattice decoy at the same rms displacement."""
    truth = rutile()

    du = brentq(lambda d: rms_disp(rutile(u=U + d), truth) - target_rms, 1e-6, 0.2)
    eps = brentq(
        lambda e: rms_disp(rutile(a=A * (1 + e), c=C * (1 + e)), truth) - target_rms,
        1e-8,
        0.2,
    )
    motif = rutile(u=U + du)
    lattice = rutile(a=A * (1 + eps), c=C * (1 + eps))
    return truth, motif, lattice, du, eps


def main() -> int:
    out = Path("tracks/other/results/m1b-reward-variants")
    out.mkdir(parents=True, exist_ok=True)

    truth, motif, lattice, du, eps = decoys(MATCHED_RMS)
    print(f"rutile TiO2  P4_2/mnm  a={A} c={C} u={U}")
    print(f"matched rms atomic displacement = {MATCHED_RMS:.3f} A")
    print(f"  motif decoy   : u -> {U + du:.4f}   (du = {du:+.4f})")
    print(f"  lattice decoy : strain {eps:+.4%}")
    print(f"  check rms: motif {rms_disp(motif, truth):.4f} A, "
          f"lattice {rms_disp(lattice, truth):.4f} A\n")

    header = f"{'variant':<28} {'D_motif':>10} {'D_lattice':>11} {'anisotropy':>11}"
    print(header)
    print("-" * len(header))

    rows = []
    for v in VARIANTS:
        d_motif = dissimilarity(motif, truth, v)
        d_lat = dissimilarity(lattice, truth, v)
        aniso = d_lat / d_motif if d_motif > 1e-15 else float("inf")
        rows.append(
            {
                "variant": v.name,
                "note": v.note,
                "D_motif": d_motif,
                "D_lattice": d_lat,
                "anisotropy": aniso,
                "gain_vs_baseline": None,
            }
        )
        print(f"{v.name:<28} {d_motif:>10.5f} {d_lat:>11.5f} {aniso:>11.1f}x")

    base = rows[0]["D_motif"]
    for r in rows:
        r["gain_vs_baseline"] = r["D_motif"] / base if base > 0 else float("inf")

    print(f"\n{'variant':<28} {'motif signal vs baseline':>26}")
    print("-" * 55)
    for r in rows:
        print(f"{r['variant']:<28} {r['gain_vs_baseline']:>24.1f}x")

    # ---- u-scan under each variant: does the minimum sharpen? -------------
    u_grid = np.linspace(U - 0.06, U + 0.06, 49)
    scans = {}
    print("\nu-scan half-width (|du| where dissimilarity reaches 10% of its span):")
    for v in VARIANTS:
        curve = np.array([dissimilarity(rutile(u=uu), truth, v) for uu in u_grid])
        scans[v.name] = curve.tolist()
        span = curve.max() - curve.min()
        if span <= 0:
            print(f"  {v.name:<28} n/a")
            continue
        thresh = curve.min() + 0.10 * span
        inside = np.abs(u_grid[curve <= thresh] - U)
        print(f"  {v.name:<28} {inside.max():.4f}   (smaller = sharper)")

    payload = {
        "run": "m1b-reward-variants",
        "challenge": "QuantumBFS/quantum.harness#68",
        "team": "ForwardXRD",
        "question": "is the lattice/motif anisotropy a metric artifact or an information limit?",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "test_case": {"formula": "TiO2", "spacegroup": "P4_2/mnm", "a": A, "c": C, "u": U},
        "matched_rms_displacement_angstrom": MATCHED_RMS,
        "motif_decoy_du": du,
        "lattice_decoy_strain": eps,
        "variants": rows,
        "u_grid": u_grid.tolist(),
        "u_scans": scans,
    }
    (out / "run.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\nwrote {out / 'run.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
