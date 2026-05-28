---
name: method-qmc
description: Use when a quantum Monte Carlo (QMC) reproduction needs method-level route and tool selection — stochastic series expansion (SSE) for sign-free spin/boson finite-temperature targets, or constrained-path / phaseless auxiliary-field QMC (CPMC/AFQMC) for fermionic Hubbard ground states. Triggers include "QMC", "SSE", "stochastic series expansion", "finite-temperature susceptibility", "sign problem", "AFQMC", "CPMC", "constrained path", "Hubbard ground state by Monte Carlo".
---

# Method QMC

QMC is the stochastic-sampling method class. This card owns method selection (step 1), software routing (step 2), and method-level setup (step 3, method side). Method internals are in `## Details`; software parameter *values* live in the tool skills; paper- and model-specific facts live in `/reproduce-paper` and `.knowledge/models/`.

Two routes:

- **SSE** — stochastic series expansion for sign-problem-free spin/bosonic lattices, finite-temperature curves (and ground states via large β).
- **CPMC/AFQMC** — constrained-path / phaseless auxiliary-field QMC for ground states of repulsive Hubbard-type fermions, via the official CPMC-Lab package.

## Sources

- Track README: `tracks/qmc/README.md`
- Tool skills: `/using-sse` (SSE route), `/using-cpmc-lab` (CPMC/AFQMC route)
- Primary literature: Nguyen, Shi, Xu, Zhang, *CPMC-Lab* (2014) `.knowledge/literature/quantum-monte-carlo/1407.7967_cpmc-lab-a-matlab-package-for-constrained-path-monte-carlo-c.md`; Sandvik, *Computational Studies of Quantum Spin Systems* (2010) for SSE; Becca & Sorella (2017).

## Select method — step 1

### Suited for {survey}

- **CPMC/AFQMC:** ground states of repulsive Hubbard-type fermion models in any dimension, finite supercell with periodic or twisted boundary — the 2D-fermion regime where the sign problem blocks naive QMC. The constraint restores polynomial (~cube-of-size) scaling; it is exact only if the trial wavefunction equals the true ground state. `[High]`
- **SSE:** sign-problem-free spin and bosonic lattice models in a fixed basis — finite-temperature observables (susceptibility, magnetization, structure factor, stiffness, energy, Binder ratios), and ground states by taking β large. `[High]`
- Sizes reached: CPMC-Lab demonstrates 1D chains up to 128 sites (65↑/63↓) and 2D up to 4×4 (5↑5↓, 7↑7↓), any filling; thermodynamic limit via a size series + twist averaging. `[High]` SSE scales to ~10³ sign-free spins. `[Med]`

### Route elsewhere when

- Frustrated or fermionic model with an **uncontrolled** sign problem outside a supported package route → official code / web search / another track.
- Real-time dynamics, generic unconstrained determinant QMC, or continuous-time impurity QMC → out of scope for this card.
- A 1D / quasi-1D ground state → `/method-mps` (DMRG) is usually cheaper and near-exact.

### Options & trade-offs {survey}

| Route / method | Good at | Weak at | Typical size |
|---|---|---|---|
| SSE (this card) | sign-free spin/boson, finite-T, large sizes | fermions, frustration (sign problem) | 10²–10³ spins `[Med]` |
| CPMC/AFQMC (this card) | 2D fermion ground states, no area-law bias | constraint bias; non-commuting observables need back-propagation | 10s–100+ sites `[High]` |
| DMRG (`/method-mps`) | 1D/quasi-1D ground states, near-exact | 2D area-law cost | wide cylinders `[Low]` |
| ED (`/method-ed`) | exact, any observable, the cross-check | exponential in size | ~tens of sites `[High]` |
| free-projection QMC | unbiased | variance grows exponentially (sign problem) | small / short `[High]` |

## Select software — step 2

### Open-source tools

- **SSE:** StochasticSeriesExpansion.jl on Carlo.jl (Julia) — the harness default for the SSE route.
- **CPMC/AFQMC:** the official **CPMC-Lab** MATLAB package (pedagogical, ~2850 lines, CPC non-profit license); returns ground-state energy ± standard error for the single-band repulsive Hubbard model, with a free-electron (restricted-HF) trial wavefunction built automatically. It is explicitly a *template* for a production FORTRAN/C AFQMC code, not a production code itself. `[High]`
- A sign-free SSE result needs no custom code; AFQMC beyond single-band repulsive Hubbard requires CPMC-Lab source edits — route back here.

### Features to confirm

- SSE: thermalization, sweeps, chains, bins, β/temperature grid, autocorrelation/binning diagnostics, MPI — owned by `/using-sse`.
- CPMC-Lab: the 21-positional-argument `CPMC_Lab` entry point, `.mat` outputs (per-block energies, trial WF), `matlab -batch` invocation — owned by `/using-cpmc-lab`.

### Options & trade-offs {survey}

| Tool | Ecosystem / examples | Efficiency | When |
|---|---|---|---|
| StochasticSeriesExpansion.jl / Carlo.jl | Julia; tutorial (BaNi₂V₂O₈ MagChi vs T) | native, MPI-parallel | SSE route `[Med]` |
| CPMC-Lab (MATLAB) | official package + `sample.m`, GUI | MATLAB ≈32× slower than production FORTRAN at 4×4, narrowing to ≈2.5× at 128×1 `[High]` | learning / medium AFQMC runs `[High]` |
| Production AFQMC (Zhang/Qin lineage) | multi-determinant/symmetry trials, back-propagation, phaseless | fast; not in this harness | large / ab-initio `[Low]` |

### Handoff

- Invoke **`/using-sse`** once an SSE route is chosen — it owns thermalization, sweeps, chains, bins, the β grid, autocorrelation/binning diagnostics, MPI, and time estimate. The sign criterion stays in this card's *Verification*.
- Invoke **`/using-cpmc-lab`** once a CPMC/AFQMC route is chosen — it owns MATLAB setup, package install/discovery, the `CPMC_Lab` signature, `.mat` output extraction, and package-level timing.
- This card owns the method-level *why* (route choice, sign-problem control, Trotter/constraint bias); the tool skills own software parameter values; the model/paper skills own scientific values.

## Method setup — step 3 (method side)

Conceptual knobs and the tricks behind them. Concrete software values live in `/using-sse` and `/using-cpmc-lab`.

**CPMC/AFQMC** {survey}:

| Knob | Controls | Trick / how it affects results |
|---|---|---|
| `Δτ` (deltau) | imaginary-time step | Trotter error ∝ Δτ²; extrapolate Δτ→0 (e.g. 0.025/0.05/0.1; production 0.01) `[High]` |
| `N_wlk` | walker population | too few → population-control bias; bias shrinks as it grows (test 10/20/40/80) `[High]` |
| `N_eqblk` | equilibration blocks | burn-in τ_eq = Δτ·N_blksteps·N_eqblk must exceed projection-to-ground-state time; read τ_eq off the E-vs-τ plot `[High]` |
| `N_blksteps` | steps per block | set ≥ autocorrelation time so saved blocks decorrelate `[High]` |
| `N_blk` | measurement blocks | sample count → error ∝ 1/√N_blk `[High]` |
| `itv_pc` | population-control interval | comb walkers to stop weight blow-up; introduces a bias that can be extrapolated away `[High]` |
| `itv_modsvd` | re-orthonormalization interval | modified Gram-Schmidt vs round-off in repeated B-matrix products; smaller is safer/costlier `[High]` |
| twist `kx,ky` | boundary phase (TABC) | PBC has large finite-size / open-shell error → twist-average; keep size × #twists ≈ const `[High]` |
| trial wavefunction | the constraint | CP bias is set by trial quality; CPMC-Lab fixes one RHF determinant — multi-determinant/symmetry trials reduce bias (not in CPMC-Lab) `[High/Low]` |

**SSE** {survey}: β = 1/T grid (a ground-state claim needs a β sweep, not one low-T point); thermalization sweeps (drop early bins); bin size (raise near criticality where autocorrelation grows); sweeps/chains (error bars); MPI chain count. `[High/Med]`

## Details

Stochastic sampling of a quantum partition function or ground-state projection.

This card is generic methodology. Paper-specific Hamiltonian choices, figure protocols, and target claims belong in `/reproduce-paper`; model facts belong in `.knowledge/models/`.

### Notation

- `β = 1/T`: inverse temperature.
- Sweep / Monte Carlo step: one update pass.
- Thermalization (equilibration): updates discarded before measurement.
- Bin: sweeps averaged into one saved statistical sample.
- Autocorrelation time: correlation scale that sets honest error bars.
- Sign (SSE): average Monte Carlo sign; should stay near 1.
- Mixed estimator (CPMC): ⟨Ψ_T|O|Φ⟩ / ⟨Ψ_T|Φ⟩ — exact for the energy, biased for observables that do not commute with H (need back-propagation).
- Constrained path (CPMC): random-walk paths kept on one side of the trial-WF node to tame the sign/phase problem; the resulting energy is non-variational and biased.

### Routes

- **SSE:** expand `Z = Tr e^{−βH}` as a power series and sample operator strings; measure finite-T observables in a fixed basis. Sign-freeness needs a bipartite / unfrustrated structure (e.g. a sublattice rotation).
- **CPMC/AFQMC:** Hubbard-Stratonovich the interaction into auxiliary fields, project the trial WF by an imaginary-time random walk in Slater-determinant space, and keep paths under the constraint. Ground-state energy via the mixed estimator.

## Verification — implementation stage {survey}

### Intermediate (mid-run)

- **CPMC:** the energy vs imaginary-time projection should flatten once equilibrated (read τ_eq off it); per-block energies should stabilize; growing free-projection fluctuations signal the sign problem. `[High]`
- **SSE:** the average sign must stay near 1 — a decaying sign means the route is not controlled. `[High]`

### Final verification + expert criticism

- Exact small-system cross-check: CPMC vs ED on the same Hamiltonian/boundary (CPMC-Lab Table I gives exact 2-site / 4-site / 2×4 / 4×4 energies at U/t = 4). `[High]`
- Δτ→0 extrapolation; `N_wlk` population-control-bias check; block decorrelation (vary `binsize` / `N_blksteps`). `[High]`
- Twist averaging + energy/site vs 1/L² to the thermodynamic limit; benchmark vs Bethe-ansatz / ED (1D E₀/M = −0.5736(1) vs −0.573729). `[High]`
- SSE: β convergence for any ground-state claim; finite-size scaling across several L; compare square-lattice Heisenberg to published reference values. `[High/Med]`
- **Criticize:** quoting the constrained-path energy as if it were variational (it is not); no Δτ→0 or `N_wlk` extrapolation; non-commuting observables read off the mixed estimator without back-propagation; a single-determinant trial with no symmetry restoration and no release/free-projection check on the constraint bias; PBC-only finite-size claims with no twist averaging. `[High/Low]`

## Citations

- `.knowledge/literature/quantum-monte-carlo/1407.7967_cpmc-lab-a-matlab-package-for-constrained-path-monte-carlo-c.md` — Nguyen, Shi, Xu, Zhang, *CPMC-Lab* (2014). CPMC method, parameters, Table I exact energies, §V timing.
- `.knowledge/literature/quantum-monte-carlo/1101.3281_computational-studies-of-quantum-spin-systems.md` — Sandvik (2010). SSE methodology.
- `.knowledge/literature/quantum-monte-carlo/10-1017-9781316417041.md` — Becca & Sorella (2017).
