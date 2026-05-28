---
name: using-cpmc-lab
description: Use when installing, smoke-testing, locating, invoking, or choosing run parameters for the official CPMC-Lab Matlab package; covers MATLAB path setup, package-root discovery, batch execution, download/license handling, package output extraction, and the documented CPMC_Lab parameter set (meaning, constraints, setup strategy).
---

# CPMC-Lab

Use this as a software stack skill. It owns package mechanics: where CPMC-Lab is installed, how Matlab finds it, how to call it non-interactively, what it returns, and the package's own documented guidance for setting its run parameters.

It does not own model choice, QMC method theory, paper figure facts, or physics validation. `/method-qmc` decides when this package is the backend and owns the method-level "why"; the model and paper skills own scientific values. This card records the package's documented parameter strategy so those choices can be surfaced to the user — not so it can invent them.

## Sources

- Stack contract: `skills/using-cpmc-lab/stack.toml`
- Official package page: `https://cpmc-lab.wm.edu/`
- Install + smoke target: `make install cpmc-lab`
- Parameter guidance and small-system exact energies (Table I): `.knowledge/literature/quantum-monte-carlo/1407.7967_cpmc-lab-a-matlab-package-for-constrained-path-monte-carlo-c.md` (§II.6–8, §IV.2, §V)

## Workflow

1. Consult `stack.toml` for the install command, smoke command, docs URL, and runtime profile.
2. Install with `make install cpmc-lab`; it downloads the official package into ignored local storage under `.external/cpmc-lab/`.
3. Locate the extracted package root by finding `CPMC_Lab.m`.
4. **Surface the run choices brainstorming-style before running.** For every parameter (see Parameters) whose value is not already fixed by an upstream model or reproduction skill, present its meaning, the documented setup strategy, and the tradeoff — one at a time — and let the user decide. Never silently default a value. Also surface the package-fixed choices so the user knows what is not adjustable here.
5. Build a driver that fills the `CPMC_Lab` signature with the agreed values and run it through `matlab -batch`, falling back to the full Matlab app path when `matlab` is not on `PATH` (see Invocation).
6. Save package outputs under the active run directory: `.mat` files, logs, and any derived text/CSV summaries.
7. Read `.mat` outputs with Matlab or Python `scipy.io.loadmat`; never treat console output as the only result record.

## Invocation

Entry point is the function in `CPMC_Lab.m`, called with 21 positional arguments in fixed order:

```matlab
[E_ave, E_err, savedFileName] = CPMC_Lab( ...
    Lx, Ly, Lz, N_up, N_dn, kx, ky, kz, U, tx, ty, tz, ...   % model
    deltau, N_wlk, N_blksteps, N_eqblk, N_blk, ...           % run / sampling
    itv_modsvd, itv_pc, itv_Em, suffix);                     % intervals + output tag
```

- Returns `E_ave` (ground-state energy), `E_err` (standard error), `savedFileName`. The saved `.mat` also holds `E` (per-block energies), `time`, `E_nonint_v` (non-interacting levels), and `Phi_T` (trial wavefunction).
- No built-in parameter sweep — loop `CPMC_Lab` externally to vary a slot.
- `sample.m` runs a real 2-site calculation; use it as a functional smoke test (stronger than the path-existence check `make install` performs). `GUI.m` is a standalone interactive entry — ignore it for batch runs.

## Parameters

Meaning, hard constraint (enforced by `validation.m`), and the package's documented setup strategy. The method-level "why" (Trotter error, sign problem, constrained-path bias) lives in `/method-qmc`; values come from the caller.

Model slots (from the model / problem layer):

| Slot | Meaning | Constraint | Setup strategy |
|---|---|---|---|
| `Lx,Ly,Lz` | sites per axis (supercell) | positive integers | a `1` axis collapses (its `t`, `k` ignored); for the thermodynamic limit run a size series and extrapolate energy/site vs `1/L²` |
| `N_up,N_dn` | up / down electron counts | non-neg int, `≤ Lx·Ly·Lz` per spin (validation.m only caps at `2·N_sites`, but the trial WF needs `≤ N_sites`) | filling `(N_up+N_dn)/N_sites`; half-filling at `N_up=N_dn=N_sites/2` |
| `kx,ky,kz` | twist angle `θ = π·k` (TABC) | each in `(−1,1]` | PBC `(0,0,0)` has large finite-size / shell error → twist-average over random twists; collapsed-axis component is ignored |
| `U` | on-site Hubbard repulsion | `U ≥ 0` (repulsive only) | sets correlation strength `U/t`; constrained-path bias grows with `U` |
| `tx,ty,tz` | nearest-neighbor hopping | `≥ 0` | usually `t = 1` as the energy unit; collapsed-axis hopping is ignored |

Run / sampling slots (from the method / reproduction layer):

| Slot | Meaning | Constraint | Setup strategy |
|---|---|---|---|
| `deltau` | imaginary time step Δτ | `> 0`; warns if `> 1` | Trotter error `∝ Δτ²` → run several values (e.g. 0.025, 0.05, 0.1) and extrapolate `Δτ → 0`; production used 0.01 |
| `N_wlk` | walker population | positive int | population-control bias shrinks as it grows (try 10/20/40/80); fewer walkers need more blocks for the same statistics |
| `N_blksteps` | random-walk steps per block | positive int | set `≥` autocorrelation time so saved blocks decorrelate; find the minimum that does |
| `N_eqblk` | equilibration (burn-in) blocks | non-neg int | burn-in time `τ_eq = deltau·N_blksteps·N_eqblk` must exceed the projection-to-ground-state time; read `τ_eq` off the E-vs-τ plot |
| `N_blk` | measurement blocks | positive int | sets the sample count → error bar `∝ 1/√N_blk` |
| `itv_modsvd` | re-orthonormalization interval | positive int; `> N_blksteps` ⇒ none | re-orthonormalize (modified Gram-Schmidt) often enough to stay numerically faithful; smaller is safer but costlier |
| `itv_pc` | population-control interval | positive int; `> N_blksteps` ⇒ none | comb walkers periodically to stop weight blow-up; introduces a bias that can be extrapolated away |
| `itv_Em` | energy-measurement interval | positive int, `≤ N_blksteps` | how often to measure energy within a block |

`suffix` — char string appended to the saved `.mat` filename; use a timestamp or run-id to disambiguate batch runs.

### Reference runs (published — scale references, not defaults)

Sampling-parameter sets the authors actually used (the `U` and lattice in each row are the scientific target, not part of the recipe — Fig. 4 in fact scans `U = 0–8`). They are listed only to anchor the scale of a sensible run; **do not copy them as defaults**. Each was tuned for the system and target shown, and still requires the per-slot convergence checks above (`Δτ → 0`, `N_wlk` bias, block decorrelation, `τ_eq`) on your own system. Note how the authors changed `itv_pc` (40 → 5) and `itv_modsvd` (5 → 1) between systems — evidence that these are tuned, not fixed.

| Source | System (`t=1`) | `deltau` | `N_wlk` | `N_blksteps` | `N_eqblk` | `N_blk` | `itv_modsvd` | `itv_pc` | `itv_Em` |
|---|---|---|---|---|---|---|---|---|---|
| `sample.m` tutorial | 2×1, 1↑1↓ | 0.01 | 100 | 40 | 2 | 20 | 5 | 10 | 20 |
| §V timing | 4×4 5↑5↓ … 128×1 65↑63↓ | 0.01 | 1000 | 40 | 10 | 50 | 5 | 40 | 40 |
| §VI Fig. 4 | 16×1, 5↑7↓ | 0.01 | 5000 | 40 | 30 | 150 | 1 | 5 | 40 |

### Choices the package fixes for you

Surface these too, because they are not adjustable here without editing the package:

- **Trial wavefunction** is the free-electron (restricted-HF) Slater determinant, built automatically. Constrained-path bias is reduced by better / multi-determinant trial WFs, which this package does not provide.
- **Energy uses the mixed estimator** — fine for the energy, but observables that do not commute with `H` are biased (need back-propagation).
- **Repulsive single-band Hubbard only** (`U ≥ 0`). Other Hamiltonians require code changes → route back to `/method-qmc`.
- **The CP energy is non-variational and biased**; removing the bias needs release / free-projection, which is not built in.

## Caller Contract

The scientific values — model, lattice, couplings, sectors, run parameters, estimator, figure mapping, validation target — are caller-supplied. Where a value is open, resolve it via the step-4 brainstorm using the documented strategy above; defer model-physics choices to the model card and the run-design rationale to `/method-qmc`. This skill turns agreed values into a reproducible CPMC-Lab invocation; it does not originate them.

## Time estimate

Estimate runtime only after the run parameters are set.

- Built-in cost heuristic (`validation.m`): `N_wlk·N_blksteps·(N_eqblk+N_blk)·Lx·Ly·(N_up+N_dn) > 1e11` warns of a run longer than a day.
- Cost scales roughly as `size³`; memory `∝ basis × electrons × walkers`. MATLAB is much slower than a FORTRAN production code by a system-dependent factor — ≈32× for 4×4 5↑5↓ (32 vs 1 min), narrowing to ≈2.5× for 128×1 65↑63↓ (460 vs 186 min) (§V).
- For an uncertain run size, use a short timing probe that measures package step rate only (no scientific claim), then multiply by the caller-specified parameter grid and repeat count.
- Route to `/using-slurm` when the estimate exceeds local exploratory budget, or when independent points (twists, sizes) can run as an array.

## Usage Notes

- Prefer MATLAB over Octave for this package. Octave is a possible compatibility experiment, not the canonical route.
- The package license is the Computer Physics Communications Non-Profit Use License; do not vendor the downloaded package into git.
- On this macOS machine, MATLAB is available at `/Applications/MATLAB_R2026a.app/bin/matlab` even when `matlab` is not on `PATH`.
- To put MATLAB on `PATH`, create a shell-visible symlink such as `ln -s /Applications/MATLAB_R2026a.app/bin/matlab /opt/homebrew/bin/matlab`.
