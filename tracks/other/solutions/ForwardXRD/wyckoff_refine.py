#!/usr/bin/env python
"""Wyckoff-respecting coordinate refinement, derived from the structure itself.

Milestone 7b. m7 showed DE refinement fixes quartz (rms 0.1818 -> 0.0001) and
improves baddeleyite 8x, but it did so with hand-written per-target builders.
A pipeline cannot hardcode the parameterisation of a structure it has not seen,
and the generic alternative -- perturbing all three coordinates of every site and
rebuilding through the space group -- is exactly what failed in m5 with
"multiplicity 10 != 9": it knocks atoms off special positions.

The general rule is a projection. A site at r has a site-symmetry group S (the
operations fixing r modulo lattice translation). A displacement is allowed only
if it is invariant under every element of S, so the allowed subspace is the
column space of

    P = (1/|S|) sum_{op in S} R_op

and its rank is that site's degrees of freedom. For quartz's Si on 3a (x, 0, 1/3)
the rank is 1; for a general position it is 3. Refining only within those
subspaces keeps every atom on its Wyckoff site by construction.
"""

from __future__ import annotations

import numpy as np
from pymatgen.core import Lattice, Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer


def wyckoff_free_basis(struct: Structure, symprec: float = 0.1):
    """-> (spacegroup, species, reps, bases, total_dof, ops), or None if unusable.

    `ops` are spglib's OWN detected operations for this structure, not a fresh
    `SpaceGroup.from_int_number(sg)` lookup -- for the ~24 space groups with
    more than one ITA origin choice (e.g. 86, P4_2/n), spglib's chosen origin
    for a given structure can differ from pymatgen's tabulated default, so a
    representative coordinate `r` extracted here is only meaningful together
    with THESE operations. Callers must reuse this same `ops` when rebuilding
    orbits from `reps`/`bases`, or the orbit sizes silently disagree with the
    true Wyckoff multiplicity ("multiplicity N != M").
    """
    try:
        sga = SpacegroupAnalyzer(struct, symprec=symprec)
        sg = sga.get_space_group_number()
        sym = sga.get_symmetrized_structure()
        ops = sga.get_symmetry_operations()
    except Exception:
        return None

    species, reps, bases = [], [], []
    for grp in sym.equivalent_sites:
        site = grp[0]
        r = np.array(site.frac_coords)
        rots = []
        for op in ops:
            d = op.operate(r) - r
            if np.allclose(d - np.round(d), 0.0, atol=1e-3):   # fixes r mod lattice
                rots.append(op.rotation_matrix)
        if not rots:
            rots = [np.eye(3)]
        P = np.mean(rots, axis=0)
        u, s, _ = np.linalg.svd(P)
        basis = u[:, s > 1e-6]           # allowed displacement directions
        species.append(site.specie)
        reps.append(r)
        bases.append(basis)

    dof = int(sum(b.shape[1] for b in bases))
    return sg, species, reps, bases, dof, ops


def _orbit(ops, r, tol: float = 1e-4):
    """All distinct images of r under the space group, modulo lattice translation.

    Explicit orbit generation rather than `Structure.from_spacegroup`, which
    infers the Wyckoff site from the coordinate and only recognises a special
    position given its CANONICAL form. `SpacegroupAnalyzer` hands back an
    arbitrary orbit member, so quartz's Si -- 3a, canonically (x, 0, 1/3) --
    was expanded to the 6-fold orbit and the rebuild failed with
    "multiplicity 10 != 9". Generating the orbit directly is representative-
    independent, and is what CrystalFormer's own symmetrize_atoms does.
    """
    pts = []
    for op in ops:
        q = np.mod(op.operate(r), 1.0)
        if not any(np.allclose((q - u) - np.round(q - u), 0.0, atol=tol) for u in pts):
            pts.append(q)
    return pts


def build_from_params(p, sg, species, reps, bases, cell: Lattice, n_atoms: int,
                      ops=None):
    """Displace each representative inside its own free subspace, then rebuild."""
    if ops is None:
        from pymatgen.symmetry.groups import SpaceGroup  # noqa: PLC0415
        ops = SpaceGroup.from_int_number(sg).symmetry_ops

    all_sp, all_xyz, i = [], [], 0
    for sp, r, b in zip(species, reps, bases):
        k = b.shape[1]
        rr = r + b @ np.asarray(p[i:i + k]) if k else r
        i += k
        for q in _orbit(ops, np.mod(rr, 1.0)):
            all_sp.append(sp)
            all_xyz.append(q)
    if len(all_sp) != n_atoms:
        raise ValueError(f"multiplicity {len(all_sp)} != {n_atoms}")
    return Structure(cell, all_sp, all_xyz)


class _WyckoffObjective:
    """Picklable stand-in for the `obj(p)` closure `refine()` used to build.

    scipy's DE with workers != 1 sends this to worker processes via
    multiprocessing.Pool.map, which pickles with the plain `pickle` module --
    a nested/local function (the original `obj`) can't be pickled that way
    ("Can't get local object ..."), only module-level classes/functions can.
    `score_fn` must itself be picklable for the same reason: a module-level
    callable (see refine_worker.py's `_PatternScore`), not a local closure.
    """

    def __init__(self, sg, species, reps, bases, cell, n_atoms, ops, score_fn):
        self.sg, self.species, self.reps, self.bases = sg, species, reps, bases
        self.cell, self.n_atoms, self.ops, self.score_fn = cell, n_atoms, ops, score_fn

    def __call__(self, p):
        try:
            st = build_from_params(p, self.sg, self.species, self.reps, self.bases,
                                   self.cell, self.n_atoms, self.ops)
            return self.score_fn(st)
        except Exception:
            return 1e3


def refine(struct: Structure, measured, score_fn, window: float = 0.15,
           seeds: int = 2, maxiter: int = 60, popsize: int = 16, workers: int = 1,
           verbose: bool = False):
    """DE inside the Wyckoff-allowed subspaces. Returns (structure, status).

    `window` bounds each free parameter's displacement in fractional units, so
    this refines the candidate rather than re-solving from scratch.

    `workers` is forwarded to scipy's DE (fork()-based multiprocessing.Pool
    internally, via `updating="deferred"`). This module has no jax dependency,
    so that's safe HERE -- but only when called from a process that hasn't
    imported jax itself. A caller with jax already loaded (e.g. anything
    importing solve_pattern's awl2struct) must run refine() in a separate,
    jax-free process instead of passing workers>1 in-process, or risk the same
    fork-with-threads deadlock index_pattern.py hit. See refine_worker.py.
    """
    from scipy.optimize import differential_evolution  # noqa: PLC0415

    info = wyckoff_free_basis(struct)
    if info is None:
        return struct, "symmetry-analysis-failed"
    sg, species, reps, bases, dof, ops = info
    if dof == 0:
        return struct, "no-free-parameters"

    n_atoms, cell = len(struct), struct.lattice
    try:
        build_from_params(np.zeros(dof), sg, species, reps, bases, cell,
                          n_atoms, ops)
    except Exception as exc:
        return struct, f"rebuild-failed:{exc}"

    obj = _WyckoffObjective(sg, species, reps, bases, cell, n_atoms, ops, score_fn)

    n_pop = popsize * dof  # scipy's own population-size formula
    est_evals = maxiter * n_pop * seeds
    if verbose:
        import time  # noqa: PLC0415
        print(f"  refine: dof={dof} popsize={n_pop} maxiter={maxiter} seeds={seeds} "
              f"workers={workers} -> ~{est_evals} evals", flush=True)
        t_de_start = time.time()

        def _cb(intermediate_result):
            gen = getattr(_cb, "n", 0) + 1
            _cb.n = gen
            print(f"    gen {gen}/{maxiter}  best={intermediate_result.fun:.5g}  "
                  f"{time.time() - t_de_start:.0f}s elapsed", flush=True)
    else:
        _cb = None

    best, best_fun = struct, obj(np.zeros(dof))
    for seed in range(seeds):
        if verbose:
            _cb.n = 0
        try:
            res = differential_evolution(
                obj, [(-window, window)] * dof, seed=seed, maxiter=maxiter,
                popsize=popsize, tol=1e-10, polish=True, init="sobol",
                workers=workers, updating="deferred" if workers != 1 else "immediate",
                callback=_cb)
        except Exception as exc:
            return best, f"de-failed:{type(exc).__name__}:{exc}"
        if res.fun < best_fun:
            try:
                best = build_from_params(res.x, sg, species, reps, bases,
                                         cell, n_atoms, ops)
                best_fun = float(res.fun)
            except Exception:
                pass
    return best, f"ok:dof={dof}"


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent))
    from solve_pattern import REGISTRY  # noqa: E402

    print(f"{'target':<14}{'SG':>5}{'sites':>7}{'dof':>5}  {'expected':<28}{'rebuild':>9}")
    print("-" * 74)
    expect = {"quartz": "Si 3a (1) + O 6c (3) = 4", "baddeleyite": "3 x 4e (3) = 9",
              "rutile": "Ti 2a (0) + O 4f (1) = 1", "pyrite": "Fe 4a (0) + S 8c (1) = 1",
              "tenorite": "Cu 4c (0) + O 4e (1) = 1",
              "marcasite": "Fe 2a (0) + S 4g (2) = 2",
              "perovskite": "Ca,O1 4c (2) + Ti 4b (0) + O2 8d (3) = 7"}
    for name in sorted(REGISTRY):
        build, tp, sg, f, na, csv = REGISTRY[name]
        truth = build(tp)
        info = wyckoff_free_basis(truth)
        if info is None:
            print(f"{name:<14}{'—':>5}{'—':>7}{'—':>5}  {expect.get(name, ''):<28}{'FAILED':>9}")
            continue
        sgn, sp, reps, bases, dof, ops = info
        try:
            s = build_from_params(np.zeros(dof), sgn, sp, reps, bases,
                                  truth.lattice, len(truth), ops=ops)
            ok = "OK" if len(s) == len(truth) else f"{len(s)}!={len(truth)}"
        except Exception as exc:
            ok = type(exc).__name__
        print(f"{name:<14}{sgn:>5}{len(reps):>7}{dof:>5}  {expect.get(name, ''):<28}{ok:>9}")
