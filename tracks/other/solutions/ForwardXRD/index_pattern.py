#!/usr/bin/env python
"""Symmetry-constrained indexing: recover the unit cell from peak positions.

Milestone 6. Replaces the mocked indexer. Nothing here touches the ground-truth
cell -- the only inputs are the measured pattern and the space group (which a
crystallographer reads off systematic absences).

Full auto-indexing also has to *determine* the crystal system, which is what
makes DICVOL/TREOR/ITO hard. Given the space group, the problem collapses to
fitting a handful of free lengths:

    cubic         1     a
    tetragonal    2     a, c
    trigonal/hex  2     a, c
    orthorhombic  3     a, b, c
    monoclinic    4     a, b, c, beta
    triclinic     6     everything

Method, which is the classical one:

  1. subtract background, find peaks in the measured pattern
  2. for a trial cell, enumerate (hkl) and predict 2-theta from Bragg's law
  3. score how well predictions explain the OBSERVED peaks, penalising cells
     that predict far more lines than are seen (otherwise any supercell wins)
  4. minimise that figure of merit by differential evolution, then polish
  5. estimate uncertainty from the spread of matched-peak residuals

Step 3's penalty is the crux. Doubling a cell axis explains every observed peak
while predicting twice as many lines, so a pure residual score is degenerate --
the same reasoning behind de Wolff's M20.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from pymatgen.core import Lattice
from scipy.optimize import differential_evolution, minimize
from scipy.signal import find_peaks

SOL = Path(__file__).parent
sys.path.insert(0, str(SOL))
from emd_metric import SPEC, noisy_target  # noqa: E402
from xrd_reward import simulate_pattern  # noqa: E402

LAMBDA = 1.54184  # Cu K-alpha, matching pymatgen's "CuKa"


# --------------------------------------------------------------------------
# peak extraction
# --------------------------------------------------------------------------


def rolling_min_background(y: np.ndarray, frac: int = 48) -> np.ndarray:
    k = max(3, len(y) // frac)
    pad = np.pad(y, k, mode="edge")
    return np.array([pad[i: i + 2 * k + 1].min() for i in range(len(y))])


def extract_peaks(pattern: np.ndarray, spec=SPEC, min_prominence_frac: float = 0.01):
    """Observed 2-theta positions, background-subtracted."""
    grid = spec.grid
    y = np.maximum(pattern - rolling_min_background(pattern), 0.0)
    if y.max() <= 0:
        return np.array([]), y
    idx, _ = find_peaks(y, prominence=min_prominence_frac * y.max(),
                        distance=max(1, len(y) // 900))
    return grid[idx], y


# --------------------------------------------------------------------------
# forward model: cell -> predicted 2-theta
# --------------------------------------------------------------------------


def _hkl_list(nmax: int = 6):
    h = np.arange(-nmax, nmax + 1)
    g = np.array(np.meshgrid(h, h, h)).reshape(3, -1).T
    g = g[np.any(g != 0, axis=1)]
    # Friedel pairs give identical d, keep one of each +/- pair
    keep = (g[:, 0] > 0) | ((g[:, 0] == 0) & (g[:, 1] > 0)) | \
           ((g[:, 0] == 0) & (g[:, 1] == 0) & (g[:, 2] > 0))
    return g[keep]


# nmax must cover every reflection inside the 2-theta window for the LARGEST
# cell the search can propose. Too small and N_poss is undercounted for big
# cells -- which biases the figure of merit toward the supercells it exists to
# reject. a_max ~ 2.5 d_max ~ 13 A against d_min ~ 1.09 A needs nmax >= 12.
HKL = _hkl_list(12)


def predicted_two_theta(lat: Lattice, lo: float, hi: float) -> np.ndarray:
    """All Bragg angles the cell allows in [lo, hi], ignoring extinctions.

    Ignoring systematic absences is deliberate: it over-predicts, which the
    figure of merit penalises, but it keeps the indexer independent of the
    space-group choice beyond the crystal system.
    """
    recip = lat.reciprocal_lattice_crystallographic.matrix
    g = HKL @ recip                      # (n, 3) reciprocal vectors
    q = np.linalg.norm(g, axis=1)        # 1/d
    with np.errstate(invalid="ignore"):
        s = LAMBDA * q / 2.0
    ok = (s > 0) & (s < 1.0)
    tt = np.degrees(2.0 * np.arcsin(s[ok]))
    tt = tt[(tt >= lo) & (tt <= hi)]
    return np.unique(np.round(tt, 6))


# --------------------------------------------------------------------------
# figure of merit
# --------------------------------------------------------------------------


def two_theta_to_q(tt: np.ndarray) -> np.ndarray:
    """Q = 1/d^2, the natural coordinate for indexing (linear in the metric)."""
    return (2.0 * np.sin(np.radians(tt / 2.0)) / LAMBDA) ** 2


def predicted_q(lat: Lattice, q_max: float) -> np.ndarray:
    recip = lat.reciprocal_lattice_crystallographic.matrix
    q = (HKL @ recip) ** 2
    q = q.sum(axis=1)
    return np.unique(q[(q > 0) & (q <= q_max)])


def fom(lat: Lattice, obs_q: np.ndarray, eps_floor: float = 2e-5):
    """de Wolff M20-style cost = mean|dQ| x (number of possible lines).

    Deliberately has NO tolerance cutoff and NO separate unindexed penalty. An
    unindexed observed line is far from every prediction, so it inflates the
    mean residual on its own -- which is how M20 handles it, and it avoids the
    balance problem a hand-tuned penalty creates (too large, and a supercell
    that indexes everything beats a correct cell that misses one line).

    Multiplying by the possible-line count is what breaks the supercell
    degeneracy: doubling an axis leaves the residual unchanged but multiplies
    the line count ~8x. The floor stops an exact fit driving the product to
    zero, which would restore it.
    """
    q_max = float(obs_q.max())
    pred = predicted_q(lat, q_max * 1.02)
    if len(pred) < len(obs_q):
        return 1e6, 0, 0.0
    resid = np.abs(obs_q[:, None] - pred[None, :]).min(axis=1)
    eps = float(resid.mean())
    n_matched = int((resid <= 0.002).sum())
    return max(eps, eps_floor) * len(pred), n_matched, eps


# --------------------------------------------------------------------------
# the search
# --------------------------------------------------------------------------


def coeff_vectors(system: str, nmax: int = 4, max_sumsq: int | None = None):
    """Distinct coefficient tuples multiplying the reciprocal-metric unknowns.

    Q is LINEAR in those unknowns, so assigning indices to a few low-angle lines
    turns indexing into a small exact linear solve -- the TREOR strategy, and the
    reason real indexers do not use blind global optimisation.
    """
    rng = range(-nmax, nmax + 1)
    seen, out = set(), []
    for h in rng:
        for k in rng:
            for l in rng:
                if h == k == l == 0:
                    continue
                # low-angle lines carry low indices; bounding the index
                # magnitude is what makes 3- and 4-unknown systems tractable
                if max_sumsq is not None and h * h + k * k + l * l > max_sumsq:
                    continue
                if system == "cubic":
                    c = (h * h + k * k + l * l,)
                elif system == "tetragonal":
                    c = (h * h + k * k, l * l)
                elif system == "hexagonal":
                    c = (h * h + h * k + k * k, l * l)
                elif system == "orthorhombic":
                    c = (h * h, k * k, l * l)
                else:  # monoclinic, b unique
                    c = (h * h, k * k, l * l, h * l)
                if c not in seen:
                    seen.add(c)
                    out.append(c)
    return np.array(out, dtype=float)


def metric_to_lattice(system: str, x: np.ndarray):
    """Reciprocal-metric unknowns -> a real Lattice, or None if unphysical."""
    try:
        if system == "cubic":
            (A,) = x
            if A <= 0:
                return None
            return Lattice.cubic(1.0 / np.sqrt(A))
        if system == "tetragonal":
            A, C = x
            if A <= 0 or C <= 0:
                return None
            return Lattice.tetragonal(1.0 / np.sqrt(A), 1.0 / np.sqrt(C))
        if system == "hexagonal":
            A, C = x
            if A <= 0 or C <= 0:
                return None
            # Q = (4/3)(h^2+hk+k^2)/a^2 + l^2/c^2
            return Lattice.hexagonal(2.0 / np.sqrt(3.0 * A), 1.0 / np.sqrt(C))
        if system == "orthorhombic":
            A, B, C = x
            if min(A, B, C) <= 0:
                return None
            return Lattice.orthorhombic(1 / np.sqrt(A), 1 / np.sqrt(B), 1 / np.sqrt(C))
        A, B, C, D = x
        if min(A, B, C) <= 0:
            return None
        cos_bs = D / (2.0 * np.sqrt(A * C))
        if not (-0.999 < cos_bs < 0.999):
            return None
        bs = np.arccos(cos_bs)              # beta*
        beta = 180.0 - np.degrees(bs)
        a = 1.0 / (np.sqrt(A) * np.sin(bs))
        b = 1.0 / np.sqrt(B)
        c = 1.0 / (np.sqrt(C) * np.sin(bs))
        if not all(1.0 < v < 40.0 for v in (a, b, c)):
            return None
        return Lattice.monoclinic(a, b, c, beta)
    except Exception:
        return None


# per-system search budget: (n_lines, nmax, max_sumsq). Systems with more
# unknowns need tighter index bounds or the enumeration explodes -- monoclinic
# is 6e10 solves unrestricted, which is why real indexers use dichotomy instead.
BUDGET = {"cubic": (6, 4, None), "tetragonal": (7, 4, None), "hexagonal": (7, 4, None),
          "orthorhombic": (6, 3, 9), "monoclinic": (6, 3, 6)}


def _score_chunk(args):
    Xc, system, obs_q = args
    out = []
    for x in Xc:
        lat = metric_to_lattice(system, x)
        if lat is not None:
            out.append((fom(lat, obs_q)[0], x))
    return out


def _score_candidates(X, system, obs_q, n_jobs: int):
    if n_jobs == 1 or len(X) < 400:
        return [(s, metric_to_lattice(system, x))
                for s, x in _score_chunk((X, system, obs_q))]
    import multiprocessing as mp  # noqa: PLC0415
    chunks = np.array_split(X, n_jobs * 4)
    with mp.Pool(n_jobs) as pool:
        parts = pool.map(_score_chunk, [(c, system, obs_q) for c in chunks if len(c)])
    return [(s, metric_to_lattice(system, x)) for part in parts for s, x in part]


def index_by_assignment(obs_q: np.ndarray, system: str, n_lines: int | None = None,
                        nmax: int | None = None, keep: int = 40,
                        n_jobs: int = 0):
    """Assign indices to the lowest lines and solve exactly."""
    n_unk = {"cubic": 1, "tetragonal": 2, "hexagonal": 2,
             "orthorhombic": 3, "monoclinic": 4}[system]
    if n_jobs <= 0:
        import os as _os  # noqa: PLC0415
        n_jobs = max(1, (_os.cpu_count() or 1) - 2)
    bl, bn, bs = BUDGET[system]
    n_lines = n_lines or bl
    coeffs = coeff_vectors(system, nmax or bn, bs)
    lines = np.sort(obs_q)[:n_lines]

    from itertools import combinations, product  # noqa: PLC0415

    # Batch every (line subset x index assignment) into one array of linear
    # systems. Scoring each solve individually would mean millions of calls to
    # the figure of merit; solving in bulk and pre-filtering on cheap physical
    # tests leaves only a few thousand worth scoring.
    combos = np.array(list(product(range(len(coeffs)), repeat=n_unk)))
    Ms = coeffs[combos]                                   # (C, n_unk, n_unk)
    dets = np.linalg.det(Ms)
    good = np.abs(dets) > 1e-9
    Ms = Ms[good]

    sols, kept = [], []
    for line_set in combinations(range(len(lines)), n_unk):
        q = lines[list(line_set)]
        rhs = np.tile(q, (len(Ms), 1))[..., None]     # (N, m, 1), not (N, m)
        try:
            x = np.linalg.solve(Ms, rhs)[..., 0]
        except np.linalg.LinAlgError:
            continue
        sols.append(x)
        kept.append(np.full(len(x), 0))
    if not sols:
        return []
    X = np.concatenate(sols, axis=0)

    # cheap vectorised physicality screen before any FOM evaluation
    diag = X[:, :3] if n_unk >= 3 else X
    ok = np.all(diag > 1e-6, axis=1) & np.all(np.isfinite(X), axis=1)
    # implied lengths must be physically sensible (1-40 A)
    with np.errstate(invalid="ignore", divide="ignore"):
        lens = 1.0 / np.sqrt(np.abs(diag))
    ok &= np.all((lens > 1.0) & (lens < 40.0), axis=1)
    if n_unk == 4:  # |cos beta*| < 1
        with np.errstate(invalid="ignore", divide="ignore"):
            cb = X[:, 3] / (2.0 * np.sqrt(np.abs(X[:, 0] * X[:, 2])))
        ok &= np.abs(cb) < 0.999
    X = X[ok]
    if len(X) == 0:
        return []

    # collapse duplicates before scoring
    X = np.unique(np.round(X, 5), axis=0)

    # Scoring dominates indexing (18 s of a ~22 s run), and each candidate is
    # independent, so fan out across cores. Metric parameters are shipped to
    # workers instead of Lattice objects -- cheaper to pickle, and the worker
    # rebuilds them.
    best = _score_candidates(X, system, obs_q, n_jobs)
    best.sort(key=lambda t: t[0])
    # de-duplicate near-identical cells
    uniq = []
    for s, lat in best:
        if all(abs(lat.volume / u.volume - 1) > 1e-3 for _, u in uniq):
            uniq.append((s, lat))
        if len(uniq) >= keep:
            break
    return uniq


def reduce_monoclinic(lat: Lattice) -> Lattice:
    """Gauss-reduce the (a, c) basis in the plane perpendicular to b.

    Indexing fixes the LATTICE, not a basis for it. In monoclinic the pair
    (a, c) is defined only up to a unimodular transformation, so an indexer can
    legitimately return c' = c + a -- which is what happened for baddeleyite
    (c' = 6.783 A, beta' = 50.69, describing the same lattice as c = 5.317,
    beta = 99.23). Re-embedding a motif expressed in the conventional basis into
    that alternative one would scramble it, so the basis has to be canonicalised.

    Gauss (Lagrange) reduction returns the two shortest vectors spanning the
    plane; the conventional monoclinic cell then takes beta obtuse.
    """
    u = np.array([lat.a, 0.0])
    beta = np.radians(lat.beta)
    v = np.array([lat.c * np.cos(beta), lat.c * np.sin(beta)])

    for _ in range(64):
        if v @ v < u @ u:
            u, v = v, u
        m = round((u @ v) / (u @ u))
        if m == 0:
            break
        v = v - m * u

    if u @ v > 0:            # conventional monoclinic uses obtuse beta
        v = -v
    a_new, c_new = float(np.linalg.norm(u)), float(np.linalg.norm(v))
    cosb = (u @ v) / (a_new * c_new)
    beta_new = float(np.degrees(np.arccos(np.clip(cosb, -1.0, 1.0))))
    return Lattice.monoclinic(a_new, lat.b, c_new, beta_new)


def setting_variants(lat: Lattice, system: str) -> list[Lattice]:
    """Conventional-setting candidates for an indexed lattice.

    Cubic / tetragonal / hexagonal are unambiguous once the crystal system is
    known -- the constructors already fix the unique axis. Orthorhombic is NOT:
    a, b, c may be permuted, and no lattice-only rule says which is which (Pnnm
    vs Pmnn is a labelling of axes, not a property of the lattice). So all six
    permutations are returned and the pattern fit is left to choose, which is
    both robust and reuses a metric already validated for exactly this job.
    """
    if system == "monoclinic":
        return [reduce_monoclinic(lat)]
    if system == "orthorhombic":
        from itertools import permutations  # noqa: PLC0415
        seen, out = set(), []
        for p in permutations((lat.a, lat.b, lat.c)):
            key = tuple(round(x, 6) for x in p)
            if key in seen:
                continue
            seen.add(key)
            out.append(Lattice.orthorhombic(*p))
        return out
    return [lat]


def _build(system: str, p):
    if system == "cubic":
        return Lattice.cubic(p[0])
    if system == "hexagonal":
        return Lattice.hexagonal(p[0], p[1])
    if system == "tetragonal":
        return Lattice.tetragonal(p[0], p[1])
    if system == "orthorhombic":
        return Lattice.orthorhombic(p[0], p[1], p[2])
    if system == "monoclinic":
        return Lattice.monoclinic(p[0], p[1], p[2], p[3])
    return Lattice.from_parameters(p[0], p[1], p[2], p[3], p[4], p[5])


def system_of(spacegroup: int) -> str:
    if spacegroup > 194:
        return "cubic"
    if spacegroup > 142:
        return "hexagonal"
    if spacegroup > 74:
        return "tetragonal"
    if spacegroup > 15:
        return "orthorhombic"
    if spacegroup > 2:
        return "monoclinic"
    return "triclinic"


def _bounds(system: str, d_max: float):
    """Physical bounds derived from the largest observed d-spacing.

    The first observed reflection need not be (100) -- for rutile it is (110),
    with d = a/sqrt(2) -- so the lower bound must sit well below d_max or the
    true cell lands on the boundary. The upper bound still admits supercells;
    rejecting those is the figure of merit's job, not the search range's.
    """
    lo, hi = 0.4 * d_max, 2.5 * d_max
    n = {"cubic": 1, "hexagonal": 2, "tetragonal": 2,
         "orthorhombic": 3, "monoclinic": 3, "triclinic": 3}[system]
    b = [(lo, hi)] * n
    if system == "monoclinic":
        b += [(90.0, 140.0)]
    elif system == "triclinic":
        b += [(60.0, 120.0)] * 3
    return b


def index_pattern(pattern: np.ndarray, spacegroup: int, spec=SPEC, seed: int = 0,
                  verbose: bool = True, n_jobs: int = 0):
    grid = spec.grid
    lo, hi = float(grid.min()), float(grid.max())
    obs, _ = extract_peaks(pattern, spec)
    if len(obs) < 3:
        return None, {"error": f"only {len(obs)} peaks found"}

    d_max = LAMBDA / (2.0 * np.sin(np.radians(obs.min() / 2.0)))
    system = system_of(spacegroup)
    bounds = _bounds(system, d_max)

    if verbose:
        print(f"  peaks found      : {len(obs)}  (first at {obs.min():.3f}°, "
              f"d_max = {d_max:.3f} Å)")
        print(f"  crystal system   : {system}  ({len(bounds)} free parameters)")

    obs_q = two_theta_to_q(obs)

    def obj(p):
        try:
            return fom(_build(system, p), obs_q)[0]
        except Exception:
            return 1e6

    # stage 1: exact solves from trial index assignments (TREOR-style)
    cands = index_by_assignment(obs_q, system, n_jobs=n_jobs)
    if not cands:
        return None, {"error": "no valid cell from index assignment"}
    if verbose:
        print(f"  assignment solve : {len(cands)} candidate cells, "
              f"best FOM {cands[0][0]:.4g}")

    # stage 2: local polish of the best few
    best_lat, best_score = cands[0][1], cands[0][0]
    for _, lat0 in cands[:8]:
        p0 = {"cubic": [lat0.a], "tetragonal": [lat0.a, lat0.c],
              "hexagonal": [lat0.a, lat0.c],
              "orthorhombic": [lat0.a, lat0.b, lat0.c],
              "monoclinic": [lat0.a, lat0.b, lat0.c, lat0.beta]}[system]
        pol = minimize(obj, p0, method="Nelder-Mead",
                       options={"xatol": 1e-7, "fatol": 1e-12, "maxiter": 6000})
        if pol.fun < best_score:
            cand = _build(system, pol.x)
            if cand is not None:
                best_lat, best_score = cand, float(pol.fun)
    best = {"cubic": [best_lat.a], "tetragonal": [best_lat.a, best_lat.c],
            "hexagonal": [best_lat.a, best_lat.c],
            "orthorhombic": [best_lat.a, best_lat.b, best_lat.c],
            "monoclinic": [best_lat.a, best_lat.b, best_lat.c, best_lat.beta]}[system]

    lat = _build(system, best)
    # canonicalise the basis: indexing fixes the lattice, not a basis for it
    if system == "monoclinic":
        lat = reduce_monoclinic(lat)
    score, n_matched, eps_q = fom(lat, obs_q)
    pred_tt = predicted_two_theta(lat, lo, hi)
    mean_res = float(np.abs(obs[:, None] - pred_tt[None, :]).min(axis=1).mean()) \
        if len(pred_tt) else 99.0
    # uncertainty proxy: residual spread mapped through Bragg's law at mid-angle
    mid = float(np.median(obs))
    rel_sigma = float(mean_res * np.pi / 180.0 / (2.0 * np.tan(np.radians(mid / 2.0))))

    info = {"system": system, "n_setting_variants": len(setting_variants(lat, system)), "n_peaks": int(len(obs)), "n_matched": n_matched,
            "mean_residual_deg": mean_res, "fom": float(score),
            "rel_sigma_est": rel_sigma,
            "cell": [lat.a, lat.b, lat.c, lat.alpha, lat.beta, lat.gamma]}
    if verbose:
        print(f"  indexed          : {n_matched}/{len(obs)} peaks, "
              f"mean residual {mean_res:.4f}°")
        print(f"  cell             : a={lat.a:.4f} b={lat.b:.4f} c={lat.c:.4f} "
              f"beta={lat.beta:.2f}")
        print(f"  est. rel. error  : {rel_sigma:.3%}")
    return lat, info


# --------------------------------------------------------------------------


def main() -> int:
    from solve_pattern import REGISTRY  # noqa: PLC0415

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--targets", nargs="+", default=sorted(REGISTRY))
    ap.add_argument("--counts", type=float, default=None,
                    help="peak counts for a noisy pattern; omit for noise-free")
    ap.add_argument("--bg", type=float, default=0.10)
    args = ap.parse_args()

    out = Path("tracks/other/results/m6-indexing")
    out.mkdir(parents=True, exist_ok=True)
    rows = []

    label = "noise-free" if args.counts is None else f"{args.counts:.0g} counts/{args.bg:.0%} bg"
    print(f"=== symmetry-constrained indexing from peak positions ({label}) ===")

    for name in args.targets:
        build, truth_p, sg, formula, n_atoms, csv = REGISTRY[name]
        truth = build(truth_p)
        pattern = (simulate_pattern(truth, SPEC) if args.counts is None
                   else noisy_target(truth, args.counts, args.bg))
        print(f"\n{name}  (SG {sg}, true a={truth.lattice.a:.4f} "
              f"b={truth.lattice.b:.4f} c={truth.lattice.c:.4f})")
        lat, info = index_pattern(pattern, sg)
        if lat is None:
            print(f"  FAILED: {info}")
            rows.append({"target": name, "ok": False, **info})
            continue

        t = truth.lattice
        err = [abs(lat.a / t.a - 1), abs(lat.b / t.b - 1), abs(lat.c / t.c - 1)]
        # Orthorhombic axis LABELS are not determined by the lattice (Pnnm vs
        # Pmnn is a labelling), so score on sorted lengths and let the solver
        # pick the permutation by pattern fit.
        st, sf = sorted([t.a, t.b, t.c]), sorted([lat.a, lat.b, lat.c])
        err_sorted = [abs(f / x - 1) for f, x in zip(sf, st)]
        permuted = max(err_sorted) < 0.01 <= max(err)
        worst = max(err_sorted) if permuted else max(err)
        # m2f: 9 free coords tolerate ~0.2-0.5%; 1-4 tolerate >=5%
        verdict = ("excellent <0.1%" if worst < 0.001 else
                   "ok <0.5%" if worst < 0.005 else
                   "marginal <5%" if worst < 0.05 else "FAILED")
        tag = "  (axes permuted — resolved downstream by pattern fit)" if permuted else ""
        print(f"  true vs indexed  : Δa={err[0]:.3%} Δb={err[1]:.3%} "
              f"Δc={err[2]:.3%}  → {verdict}{tag}")
        rows.append({"target": name, "ok": True, "spacegroup": sg,
                     "true_cell": [t.a, t.b, t.c, t.alpha, t.beta, t.gamma],
                     "errors": err, "errors_sorted": err_sorted,
                     "axes_permuted": bool(permuted),
                     "worst_error": worst, "verdict": verdict, **info})

    print("\n" + "=" * 84)
    print("INDEXING ACCURACY — no ground-truth cell used")
    print("=" * 84)
    print(f"{'target':<14}{'system':<14}{'matched':>10}{'resid°':>9}{'worst Δ':>10}{'verdict':>17}")
    print("-" * 84)
    for r in rows:
        if not r.get("ok"):
            print(f"{r['target']:<14}{'—':<14}{'—':>10}{'—':>9}{'—':>10}{'FAILED':>17}")
            continue
        frac = "{}/{}".format(r["n_matched"], r["n_peaks"])
        print(f"{r['target']:<14}{r['system']:<14}{frac:>10}"
              f"{r['mean_residual_deg']:>9.4f}{r['worst_error']:>10.3%}"
              f"{r['verdict']:>17}")

    (out / "run.json").write_text(json.dumps({
        "run": "m6-indexing", "challenge": "QuantumBFS/quantum.harness#68",
        "team": "ForwardXRD", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "question": "can the cell be recovered from peak positions alone?",
        "method": "symmetry-constrained DE fit to observed peak positions; "
                  "space group assumed known from systematic absences",
        "measurement": label, "rows": rows,
    }, indent=2, default=str) + "\n")
    print(f"\nwrote {out / 'run.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
