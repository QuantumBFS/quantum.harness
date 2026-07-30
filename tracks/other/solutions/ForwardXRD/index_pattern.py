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


def centering_of(spacegroup: int) -> str:
    """Bravais-lattice centering letter (P/A/B/C/I/F/R) for a space group.

    The first character of the international symbol always names it (Immm,
    Fm-3m, R-3c, ...).
    """
    from pymatgen.symmetry.groups import SpaceGroup  # noqa: PLC0415
    return SpaceGroup.from_int_number(spacegroup).symbol[0]


_HALL_NUMBERS_CACHE: dict[int, list[int]] = {}
_EXTINCTION_MASKS_CACHE: dict[int, list[np.ndarray]] = {}


def _hall_numbers_for(spacegroup: int) -> list[int]:
    """All of spglib's Hall-symbol settings for an ITA space-group number.

    A single ITA number can have several valid settings (axis permutation,
    cell choice, origin choice) -- e.g. SG62/Pnma has 6, one per axis
    labelling (Pnma, Pmnb, Pbnm, Pcmn, Pmcn, Pnam). `SpaceGroup.from_int_
    number` (pymatgen's own static ITA table) always returns just ONE fixed
    setting, which need not be the one `SpacegroupAnalyzer.get_conventional_
    standard_structure()` (spglib) lands a given real structure on -- e.g.
    HoNi standardizes to hall_number=296 ("Pmcn"), not pymatgen's default 292
    ("Pnma"); using 292's operations to predict absences for a 296-set
    structure wrongly marked its real, present (110)/(012) reflections
    absent. See _extinction_masks_for.
    """
    cached = _HALL_NUMBERS_CACHE.get(spacegroup)
    if cached is not None:
        return cached
    import spglib  # noqa: PLC0415
    out = [hn for hn in range(1, 531)
          if spglib.get_spacegroup_type(hn).number == spacegroup]
    _HALL_NUMBERS_CACHE[spacegroup] = out
    return out


def _extinction_masks_for(spacegroup: int) -> list[np.ndarray]:
    """Every DISTINCT boolean mask over HKL (reflections not systematically
    absent) that this space group's Hall settings can produce.

    General rule (International Tables Vol A): for a symmetry operation
    (R, t) whose rotation leaves a reflection h invariant (h @ R == h), the
    structure factor obeys F(h) = exp(2*pi*i* h.t) F(h) -- forcing F(h) = 0
    unless h.t is an integer (verified against known ITA reflection
    conditions and a brute-force orbit structure-factor summation). Applying
    that per Hall setting and deduplicating collapses settings that don't
    actually differ in their absence pattern (common for P-lattice groups
    with no glide/screw component, where axis permutation alone changes
    nothing observable) down to however many DISTINCT absence patterns are
    actually possible -- confirmed empirically small (SG62: 5 of 6 settings
    distinct; SG14: 2 of 9; SG12: 1 of 9) by sampling real MP.db structures
    of each space group through get_conventional_standard_structure() until
    the count of distinct post-standardization operation sets plateaued.

    Since indexing doesn't have real atoms yet (that's what it's solving
    for), which setting the eventual structure will land on isn't knowable
    in advance -- so every distinct mask is tried during the search (see
    index_pattern's axis/mask loop) and the pattern itself picks the winner
    via the figure of merit, the same way unique_axis is resolved.
    """
    cached = _EXTINCTION_MASKS_CACHE.get(spacegroup)
    if cached is not None:
        return cached
    import spglib  # noqa: PLC0415
    masks = []
    for hn in _hall_numbers_for(spacegroup):
        sym = spglib.get_symmetry_from_database(hn)
        absent = np.zeros(len(HKL), dtype=bool)
        for R, t in zip(sym["rotations"], sym["translations"]):
            if np.allclose(t, 0.0):
                continue  # no translation -> no phase constraint, never absences
            hp = HKL @ R
            fixed = np.all(np.isclose(hp, HKL), axis=1)
            phase = HKL @ t
            non_integer = ~np.isclose(phase - np.round(phase), 0.0, atol=1e-6)
            absent |= fixed & non_integer
        mask = ~absent
        if not any(np.array_equal(mask, m) for m in masks):
            masks.append(mask)
    _EXTINCTION_MASKS_CACHE[spacegroup] = masks
    return masks


def predicted_two_theta(lat: Lattice, lo: float, hi: float, mask: np.ndarray | None = None) -> np.ndarray:
    """All Bragg angles the cell allows in [lo, hi].

    `mask` is a boolean array over HKL (see _extinction_masks_for); None
    means no absences modeled (every reflection kept).
    """
    hkl = HKL if mask is None else HKL[mask]
    recip = lat.reciprocal_lattice_crystallographic.matrix
    g = hkl @ recip                      # (n, 3) reciprocal vectors
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


def _q_raw(lat: Lattice) -> np.ndarray:
    """|g|^2 for every HKL entry (no mask, no range filter) -- the expensive
    part of predicted_q (a matmul over the full ~7800-entry HKL grid),
    factored out so it can be computed ONCE per candidate lattice and reused
    across every extinction-mask variant (see _fom_multi), instead of
    repeating the matmul once per mask.
    """
    recip = lat.reciprocal_lattice_crystallographic.matrix
    g = HKL @ recip
    return (g ** 2).sum(axis=1)


def predicted_q(lat: Lattice, q_max: float, mask: np.ndarray | None = None) -> np.ndarray:
    q = _q_raw(lat)
    if mask is not None:
        q = q[mask]
    return np.unique(q[(q > 0) & (q <= q_max)])


def fom(lat: Lattice, obs_q: np.ndarray, eps_floor: float = 2e-5, mask: np.ndarray | None = None):
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

    No longer hard-rejects len(pred) < len(obs_q). That gate assumed every
    observed line is a genuine reflection -- true for this pipeline's own
    clean, self-simulated patterns, but not for an externally-sourced pattern
    with real noise: extract_peaks can pick up a few spurious local maxima
    that aren't Bragg lines at all. A strongly-centered cell (R-centering
    removes 2/3 of reflections) can then legitimately predict fewer lines
    than a noisy pattern reports observed -- confirmed directly on a real
    R-3m case where the TRUE cell's own correctly-filtered prediction list
    (independently verified against pymatgen's structure-factor calculation)
    was hard-rejected this way. The nearest-neighbor residual below already
    penalizes any excess observed line on its own, per the docstring above;
    trusting that uniformly, instead of a hard cutoff, extends the same
    "unindexed line inflates its own residual" logic to this case too.
    """
    q_max = float(obs_q.max())
    pred = predicted_q(lat, q_max * 1.02, mask)
    if len(pred) == 0:
        return 1e6, 0, 0.0
    resid = np.abs(obs_q[:, None] - pred[None, :]).min(axis=1)
    eps = float(resid.mean())
    n_matched = int((resid <= 0.002).sum())
    return max(eps, eps_floor) * len(pred), n_matched, eps


def _fom_multi(lat: Lattice, obs_q: np.ndarray, masks, eps_floor: float = 2e-5) -> list[float]:
    """fom()'s score under EVERY mask in `masks`, sharing one _q_raw matmul.

    Scoring (not the Nelder-Mead polish) is indexing's dominant cost even
    with a single mask; naively calling fom() once per mask per candidate
    (which redoes the matmul each time) multiplied that dominant stage by
    the mask count -- confirmed directly: monoclinic's 9 SG14 settings
    turned a normal ~20s run into 20+ minutes with no result. Reusing
    _q_raw's matmul across masks and doing only cheap boolean indexing +
    residual work per mask removes that multiplier.
    """
    q_max = float(obs_q.max()) * 1.02
    q_raw = _q_raw(lat)
    in_range = (q_raw > 0) & (q_raw <= q_max)
    out = []
    for m in masks:
        sel = in_range if m is None else (in_range & m)
        pred = np.unique(q_raw[sel])
        if len(pred) == 0:
            out.append(1e6)
            continue
        resid = np.abs(obs_q[:, None] - pred[None, :]).min(axis=1)
        eps = float(resid.mean())
        out.append(max(eps, eps_floor) * len(pred))
    return out


# --------------------------------------------------------------------------
# the search
# --------------------------------------------------------------------------


def coeff_vectors(system: str, nmax: int = 4, max_sumsq: int | None = None,
                  unique_axis: str = "b"):
    """Distinct coefficient tuples multiplying the reciprocal-metric unknowns.

    Q is LINEAR in those unknowns, so assigning indices to a few low-angle lines
    turns indexing into a small exact linear solve -- the TREOR strategy, and the
    reason real indexers do not use blind global optimisation.

    Monoclinic has one axis (`unique_axis`) perpendicular to the other two,
    which are joined by the one free angle; the pair carrying that angle is the
    ONLY thing that changes with unique_axis. Output order is always
    (coupled1, clean, coupled2, cross) regardless of which physical axis is
    "clean" -- metric_to_lattice relies on that fixed slot order, not on which
    axis it happens to represent, so the physicality checks in
    index_by_assignment (which index into slots 0/1/2/3 directly) don't need
    to know about unique_axis at all.
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
                elif unique_axis == "b":       # coupled (a,c), clean b
                    c = (h * h, k * k, l * l, h * l)
                elif unique_axis == "a":       # coupled (b,c), clean a
                    c = (k * k, h * h, l * l, k * l)
                else:                          # unique_axis == "c": coupled (a,b), clean c
                    c = (h * h, l * l, k * k, h * k)
                if c not in seen:
                    seen.add(c)
                    out.append(c)
    return np.array(out, dtype=float)


def metric_to_lattice(system: str, x: np.ndarray, unique_axis: str = "b"):
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
        # monoclinic: X = (coupled1, clean, coupled2, cross), see coeff_vectors
        X0, X1, X2, D = x
        if min(X0, X1, X2) <= 0:
            return None
        cos_fs = D / (2.0 * np.sqrt(X0 * X2))
        if not (-0.999 < cos_fs < 0.999):
            return None
        fs = np.arccos(cos_fs)                    # free angle*, reciprocal
        free_angle = 180.0 - np.degrees(fs)
        len_c1 = 1.0 / (np.sqrt(X0) * np.sin(fs))
        len_clean = 1.0 / np.sqrt(X1)
        len_c2 = 1.0 / (np.sqrt(X2) * np.sin(fs))
        if not all(1.0 < v < 40.0 for v in (len_c1, len_clean, len_c2)):
            return None
        if unique_axis == "b":
            return Lattice.from_parameters(len_c1, len_clean, len_c2, 90, free_angle, 90)
        if unique_axis == "a":
            return Lattice.from_parameters(len_clean, len_c1, len_c2, free_angle, 90, 90)
        return Lattice.from_parameters(len_c1, len_c2, len_clean, 90, 90, free_angle)
    except Exception:
        return None


# per-system search budget: (n_lines, nmax, max_sumsq). Systems with more
# unknowns need tighter index bounds or the enumeration explodes -- monoclinic
# is 6e10 solves unrestricted, which is why real indexers use dichotomy instead.
BUDGET = {"cubic": (6, 4, None), "tetragonal": (7, 4, None), "hexagonal": (7, 4, None),
          "orthorhombic": (6, 3, 9), "monoclinic": (6, 3, 6)}


def _score_chunk(args):
    """Score each candidate under EVERY extinction-mask variant via
    _fom_multi (one matmul per candidate, shared across masks -- see its
    docstring for why looping fom() itself per mask here was unusably slow),
    keeping only its own best (score, winning mask index). What must NOT be
    repeated per mask is the caller's Nelder-Mead polish stage (see
    _index_one), which is why each candidate is tagged with its own winner
    instead of the caller looping over masks again.
    """
    Xc, system, obs_q, unique_axis, masks = args
    out = []
    for x in Xc:
        lat = metric_to_lattice(system, x, unique_axis)
        if lat is None:
            continue
        scores = _fom_multi(lat, obs_q, masks)
        mi = int(np.argmin(scores))
        out.append((scores[mi], x, mi))
    return out


def _score_candidates(X, system, obs_q, n_jobs: int, unique_axis: str = "b",
                      masks: tuple = (None,)):
    if n_jobs == 1 or len(X) < 400:
        return [(s, metric_to_lattice(system, x, unique_axis), mi)
                for s, x, mi in _score_chunk((X, system, obs_q, unique_axis, masks))]
    import multiprocessing as mp  # noqa: PLC0415
    chunks = np.array_split(X, n_jobs * 4)
    # Plain fork() Pool. Safe HERE because this module has no jax dependency of
    # its own -- but forking is unsafe once a CALLING process has jax loaded
    # (multithreaded internally: a fork can inherit a lock some other thread
    # held, which then never gets released in the child -- deadlock). Callers
    # that already have jax loaded (e.g. anything importing solve_pattern's
    # awl2struct) must run index_pattern() in a separate process instead of
    # switching this to spawn -- spawn re-executes the caller's entire main
    # module per worker, which reimports jax/haiku/optax there too and, on an
    # NFS-backed $HOME with ~n_jobs concurrent worker startups, turned a 35s
    # call into 20+ minutes. See index_worker.py for the isolation pattern.
    with mp.Pool(n_jobs) as pool:
        parts = pool.map(_score_chunk, [(c, system, obs_q, unique_axis, masks) for c in chunks if len(c)])
    return [(s, metric_to_lattice(system, x, unique_axis), mi) for part in parts for s, x, mi in part]


def index_by_assignment(obs_q: np.ndarray, system: str, n_lines: int | None = None,
                        nmax: int | None = None, keep: int = 40,
                        n_jobs: int = 0, unique_axis: str = "b", masks: tuple = (None,)):
    """Assign indices to the lowest lines and solve exactly."""
    n_unk = {"cubic": 1, "tetragonal": 2, "hexagonal": 2,
             "orthorhombic": 3, "monoclinic": 4}[system]
    if n_jobs <= 0:
        import os as _os  # noqa: PLC0415
        n_jobs = max(1, (_os.cpu_count() or 1) - 2)
    bl, bn, bs = BUDGET[system]
    n_lines = n_lines or bl
    coeffs = coeff_vectors(system, nmax or bn, bs, unique_axis)
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
    best = _score_candidates(X, system, obs_q, n_jobs, unique_axis, masks)
    best.sort(key=lambda t: t[0])
    # de-duplicate near-identical cells
    uniq = []
    for s, lat, mi in best:
        if all(abs(lat.volume / u.volume - 1) > 1e-3 for _, u, _ in uniq):
            uniq.append((s, lat, mi))
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


def _build(system: str, p, unique_axis: str = "b"):
    if system == "cubic":
        return Lattice.cubic(p[0])
    if system == "hexagonal":
        return Lattice.hexagonal(p[0], p[1])
    if system == "tetragonal":
        return Lattice.tetragonal(p[0], p[1])
    if system == "orthorhombic":
        return Lattice.orthorhombic(p[0], p[1], p[2])
    if system == "monoclinic":
        # p = [a, b, c, free_angle]; which angle slot depends on unique_axis
        if unique_axis == "b":
            return Lattice.from_parameters(p[0], p[1], p[2], 90, p[3], 90)
        if unique_axis == "a":
            return Lattice.from_parameters(p[0], p[1], p[2], p[3], 90, 90)
        return Lattice.from_parameters(p[0], p[1], p[2], 90, 90, p[3])
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
    centering = centering_of(spacegroup)
    bounds = _bounds(system, d_max)
    # Every distinct extinction pattern this space group's Hall settings can
    # produce (see _extinction_masks_for) -- which one the eventual structure
    # lands on isn't knowable from peaks alone, so all are tried and the fit
    # itself picks the winner, same as unique_axis below.
    masks = _extinction_masks_for(spacegroup) or [None]

    if verbose:
        print(f"  peaks found      : {len(obs)}  (first at {obs.min():.3f}°, "
              f"d_max = {d_max:.3f} Å)")
        print(f"  crystal system   : {system}  ({len(bounds)} free parameters)"
              f"{f', {centering}-centered' if centering != 'P' else ''}"
              f"{f', {len(masks)} extinction settings' if len(masks) > 1 else ''}")

    obs_q = two_theta_to_q(obs)

    def _index_one(unique_axis: str):
        """Stages 1-2 (assignment solve + Nelder-Mead polish) for one system.

        For monoclinic, `unique_axis` picks which axis carries the fixed 90
        degree angles vs. which two share the one free angle -- see
        coeff_vectors' docstring. Returns (Lattice, fom_score, n_cands,
        winning mask) or (None, inf, 0, None).

        Tries every extinction-mask variant during the (cheap, vectorised)
        assignment-solve scoring stage -- each candidate is tagged with its
        own best-fitting mask there (see _score_chunk) -- but the (expensive,
        Nelder-Mead) polish stage below only runs ONCE per top candidate,
        using that candidate's own tagged mask, not once per mask. Looping
        polish over every mask too (an earlier version of this) multiplied
        monoclinic's already-slowest search by up to 9x and made a routine
        indexing run take 20+ minutes with no result; this keeps the mask
        search where it's cheap and out of where it's not.
        """
        angle_of = {"a": "alpha", "b": "beta", "c": "gamma"}.get(unique_axis)

        cands = index_by_assignment(obs_q, system, n_jobs=n_jobs, unique_axis=unique_axis,
                                    masks=masks)
        if not cands:
            return None, float("inf"), 0, None
        best_lat, best_score, best_mask = cands[0][1], cands[0][0], masks[cands[0][2]]
        for _, lat0, mi in cands[:8]:
            m = masks[mi]

            def obj(p, m=m):
                try:
                    return fom(_build(system, p, unique_axis), obs_q, mask=m)[0]
                except Exception:
                    return 1e6

            p0 = {"cubic": [lat0.a], "tetragonal": [lat0.a, lat0.c],
                  "hexagonal": [lat0.a, lat0.c],
                  "orthorhombic": [lat0.a, lat0.b, lat0.c],
                  "monoclinic": [lat0.a, lat0.b, lat0.c,
                                getattr(lat0, angle_of) if angle_of else None]}[system]
            pol = minimize(obj, p0, method="Nelder-Mead",
                           options={"xatol": 1e-7, "fatol": 1e-12, "maxiter": 6000})
            if pol.fun < best_score:
                cand = _build(system, pol.x, unique_axis)
                if cand is not None:
                    best_lat, best_score, best_mask = cand, float(pol.fun), m
        return best_lat, best_score, len(cands), best_mask

    # stages 1-2: exact assignment solve + local polish (TREOR-style). For
    # monoclinic, the physically-stored cell can use any of the three
    # unique-axis conventions (International Tables doesn't force b-unique --
    # MP.db entries, e.g., are whatever spglib's conventional-cell routine
    # picked) while this indexer's Q-formula only matches one of them at a
    # time, so try all three and keep whichever fits the pattern best.
    axis_choices = ("a", "b", "c") if system == "monoclinic" else ("b",)
    results = {ax: _index_one(ax) for ax in axis_choices}
    winner = min(axis_choices, key=lambda ax: results[ax][1])
    best_lat, best_score, n_cands, win_mask = results[winner]
    win_axis = winner
    win_mask_idx = next((i for i, m in enumerate(masks)
                         if (m is None) == (win_mask is None) and
                         (m is None or np.array_equal(m, win_mask))), 0)
    if best_lat is None:
        return None, {"error": "no valid cell from index assignment"}
    if verbose:
        setting_note = f", extinction setting {win_mask_idx + 1}/{len(masks)}" if len(masks) > 1 else ""
        if system == "monoclinic":
            print(f"  assignment solve : tried unique axis a/b/c "
                  f"({ {ax: results[ax][2] for ax in axis_choices} }); chose {win_axis}"
                  f"{setting_note}, best FOM {best_score:.4g}")
        else:
            print(f"  assignment solve : {n_cands} candidate cells{setting_note}, "
                  f"best FOM {best_score:.4g}")

    lat = best_lat
    if system == "monoclinic":
        if win_axis != "b":
            # relabel into the pipeline's assumed b-unique convention (the
            # "clean"/perpendicular axis becomes b; the free angle becomes
            # beta) -- a pure axis relabelling of the same physical lattice,
            # so downstream code (embedding, setting_variants, CrystalFormer's
            # own b-unique output) doesn't need to know this ever happened.
            if win_axis == "a":
                lat = Lattice.from_parameters(lat.b, lat.a, lat.c, 90, lat.alpha, 90)
            else:  # win_axis == "c"
                lat = Lattice.from_parameters(lat.a, lat.c, lat.b, 90, lat.gamma, 90)
        # canonicalise the basis: indexing fixes the lattice, not a basis for it
        lat = reduce_monoclinic(lat)
    score, n_matched, eps_q = fom(lat, obs_q, mask=win_mask)
    pred_tt = predicted_two_theta(lat, lo, hi, win_mask)
    mean_res = float(np.abs(obs[:, None] - pred_tt[None, :]).min(axis=1).mean()) \
        if len(pred_tt) else 99.0
    # uncertainty proxy: residual spread mapped through Bragg's law at mid-angle
    mid = float(np.median(obs))
    rel_sigma = float(mean_res * np.pi / 180.0 / (2.0 * np.tan(np.radians(mid / 2.0))))

    info = {"system": system, "centering": centering,
            "n_extinction_settings": len(masks), "extinction_setting": win_mask_idx,
            "n_setting_variants": len(setting_variants(lat, system)), "n_peaks": int(len(obs)), "n_matched": n_matched,
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
