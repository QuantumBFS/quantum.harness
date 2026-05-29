---
name: method-qmc
description: Use when a quantum Monte Carlo (QMC) reproduction needs method-level route and tool selection — stochastic series expansion (SSE) for sign-free spin/boson finite-temperature targets, or constrained-path / phaseless auxiliary-field QMC (CPMC/AFQMC) for fermionic Hubbard ground states. Triggers include "QMC", "SSE", "stochastic series expansion", "finite-temperature susceptibility", "sign problem", "AFQMC", "CPMC", "constrained path", "Hubbard ground state by Monte Carlo".
---

# Method QMC

QMC is the stochastic-sampling method class. This card owns method selection (step 1), software routing (step 2), and method-level setup (step 3, method side). Method internals are in `## Details`; software parameter *values* live in the tool skills; paper- and model-specific facts live in `/reproduce-paper` and `.knowledge/models/`.

Two routes:

- **SSE** — stochastic series expansion for sign-problem-free spin/bosonic lattices, finite-temperature curves (and ground states via large β).
- **CPMC/AFQMC** — constrained-path / phaseless auxiliary-field QMC for interacting fermions. The survey covers both the **zero-temperature** (ground-state projection) and **finite-temperature** (grand-canonical) forms; the harness route — the official CPMC-Lab package — implements the ground-state form for repulsive Hubbard-type models.

## Sources

- Track README: `tracks/qmc/README.md`
- Tool skills: `/using-sse` (SSE route), `/using-cpmc-lab` (CPMC/AFQMC route)
- Survey (primary, AFQMC): Zhang, *Auxiliary-Field Quantum Monte Carlo at Zero- and Finite-Temperature* (2019) `.knowledge/literature/quantum-monte-carlo/zhang_2019_auxiliary-field-quantum-monte-carlo.md` — the methodology reference for the CPMC/AFQMC route.
- Reproduction target + CP algorithm details: Nguyen, Shi, Xu, Zhang, *CPMC-Lab* (2014) `.knowledge/literature/quantum-monte-carlo/1407.7967_cpmc-lab-a-matlab-package-for-constrained-path-monte-carlo-c.md`.
- SSE methodology: Sandvik, *Computational Studies of Quantum Spin Systems* (2010); QMC textbook: Becca & Sorella (2017).
- Software landscape (step 2): ipie (`github.com/JoonhoLee-Group/ipie`), QMCPACK AFQMC module, ALF, SmoQyDQMC.jl.

## Select method — step 1

### Suited for

- **CPMC/AFQMC:** ground states (and, in the grand-canonical form, finite temperature) of interacting many-fermion systems with two-body interactions — in any one-particle basis (lattice sites, plane waves, Gaussians), spanning correlated-electron models, cold Fermi gases, solids, and quantum chemistry. The constraint restores low-polynomial (~cube-of-size) scaling, exact only if the trial wavefunction is exact; production AFQMC routinely treats O(1000) electrons at accuracy comparable to CCSD(T) near equilibrium. **In this harness the only AFQMC tool is CPMC-Lab — single-band repulsive Hubbard ground state**; broader targets need a production code (route out).
- **SSE:** sign-problem-free spin and bosonic lattice models in a fixed basis — finite-temperature observables (susceptibility, magnetization, structure factor, stiffness, energy, Binder ratios), and ground states by taking β large.
- Sizes reached: CPMC-Lab demonstrates 1D chains up to 128 sites (65↑/63↓) and 2D up to 4×4 (5↑5↓, 7↑7↓), any filling; thermodynamic limit via a size series + twist averaging. SSE scales to ~10³ sign-free spins.

### Route elsewhere when

- Frustrated or fermionic model with an **uncontrolled** sign problem outside a supported package route → official code / web search / another track.
- Real-time dynamics, generic unconstrained determinant QMC, or continuous-time impurity QMC → out of scope for this card.
- A 1D / quasi-1D ground state → `/method-mps` (DMRG) is usually cheaper and near-exact.

### Options & trade-offs

| Route / method | Good at | Weak at | Typical size |
|---|---|---|---|
| SSE (this card) | sign-free spin/boson, finite-T, large sizes | fermions, frustration (sign problem) | 10²–10³ spins |
| CPMC/AFQMC (this card) | 2D fermion ground states, no area-law bias | constraint bias; non-commuting observables need back-propagation | 10s–100+ sites |
| DMRG (`/method-mps`) | 1D/quasi-1D ground states, near-exact | 2D area-law cost | wide cylinders |
| ED (`/method-ed`) | exact, any observable, the cross-check | exponential in size | ~tens of sites |
| free-projection QMC | unbiased | variance grows exponentially (sign problem) | small / short |

## Select software — step 2

### Tools — the route, the maintained SOTA, and a cross-check

- **SSE route:** StochasticSeriesExpansion.jl on Carlo.jl (Julia) — the harness default for sign-free spin/boson SSE.
- **CPMC/AFQMC — harness tool:** the official **CPMC-Lab** MATLAB package — pedagogical, frozen since 2014, single-band-Hubbard ground-state constrained-path. Easy to read and run, not production-scale. Tool specifics live in `/using-cpmc-lab`.
- **CPMC/AFQMC — maintained production SOTA (not in the harness; route out / install on demand):**
  - **ipie** (Apache-2.0; Python + C/C++; active through 2026; `github.com/JoonhoLee-Group/ipie`) — the leading phaseless AFQMC code: ground-state and finite-T, lattice **and** ab-initio (PySCF interface), single/multi-determinant and selected-CI trials, back-propagation, GPU + MPI. Best general-purpose choice once CPMC-Lab is outgrown.
  - **QMCPACK AFQMC module** (open / NCSA-style; C++; v4.2.0, 2026) — mature ph-AFQMC, ab-initio focused, NOMSD/PHMSD trials, back-propagated RDM observables, PySCF front end, leadership-HPC scale; GPU for single-determinant trials.
  - PAUXY is deprecated → use ipie.
- **Independent cross-check (different method, not constrained-path):** unconstrained finite-T determinant QMC — **ALF** (Fortran, lattice) or **SmoQyDQMC.jl** (Julia, very active) — numerically exact but sign-problem-limited; cross-validate, don't substitute.

### Features to confirm

- SSE: thermalization, sweeps, chains, bins, β/temperature grid, autocorrelation/binning diagnostics, MPI — owned by `/using-sse`.
- CPMC-Lab: signature, parameters, `.mat` outputs, install/run mechanics — all owned by `/using-cpmc-lab`.

### Options & trade-offs

| Tool | Maintained | Lang | CP / ph | T=0 / T>0 | Lattice / ab-initio | GPU | Use when |
|---|---|---|---|---|---|---|---|
| CPMC-Lab (harness) | frozen 2014 | MATLAB | constrained-path | T=0 | Hubbard | no | learning / small Hubbard ground states |
| ipie | yes (2026) | Python+C/C++ | phaseless (+ free-proj) | both | both | yes | production AFQMC, ab-initio, GPU |
| QMCPACK AFQMC | yes (2026) | C++ | phaseless | T=0 | mainly ab-initio | partial | ab-initio at HPC scale |
| ALF / SmoQyDQMC.jl | yes (2026) | Fortran / Julia | unconstrained DQMC | T>0 | lattice | no | finite-T lattice cross-check (sign-limited) |

The SSE route uses StochasticSeriesExpansion.jl / Carlo.jl (Julia; native, MPI-parallel).

### Efficiency & parallelism

Cost is ~O(N³) per propagation step (N = sites/basis) × walkers × steps, memory ~O(N²) per walker; AFQMC is *embarrassingly parallel* over walkers and over independent points (twists, sizes, Δτ). What each tool does with that:

| Tool | Parallelism | Reach |
|---|---|---|
| CPMC-Lab (harness) | single-core MATLAB — no MPI/GPU/threading; parallel only by farming independent runs as array jobs (`/using-slurm`) | ~100 sites locally (≈32 min @ 4×4 5↑5↓, ≈460 min @ 128×1) |
| ipie | MPI + GPU (batched propagation / force bias) | O(1000) electrons on GPU clusters |
| QMCPACK AFQMC | MPI + GPU (single-determinant trials) | leadership-HPC scale |
| ALF / SmoQyDQMC.jl | MPI, lattice DQMC | finite-T lattice; sign-limited |

### Handoff

- Invoke **`/using-sse`** once an SSE route is chosen — it owns thermalization, sweeps, chains, bins, the β grid, autocorrelation/binning diagnostics, MPI, and time estimate. The sign criterion stays in this card's *Verification*.
- Invoke **`/using-cpmc-lab`** once a CPMC/AFQMC route is chosen — it owns MATLAB setup, package install/discovery, the `CPMC_Lab` signature, `.mat` output extraction, and package-level timing.
- This card owns the method-level *why* (route choice, sign-problem control, Trotter/constraint bias); the tool skills own software parameter values; the model/paper skills own scientific values.

## Method setup — step 3 (method side)

Conceptual knobs and the tricks behind them — for each, the **intuition for choosing it** and how it moves the result; these have no one-size default, so the trick *is* the guidance. Concrete software values live in `/using-sse` and `/using-cpmc-lab`.

**CPMC/AFQMC** — method-level knobs (concrete CPMC-Lab parameter names, starting points, and convergence values live in `/using-cpmc-lab`):

| Knob (method-level) | Controls | Trick / how it affects results |
|---|---|---|
| Imaginary-time step | Trotter discretization | error ∝ step²; extrapolate step→0. The constraint also carries a small finite-step error |
| Population control | walker-weight stability | stops weight blow-up but biases the result when total weight is modified — a bias/variance trade; extrapolate or carry a weight-history correction |
| Importance sampling / force bias | sampling efficiency | shift the field distribution by the optimal force bias (∝ √step) to minimize weight fluctuation; for complex fields this is the phaseless force bias |
| Trial wavefunction + constraint | the CP / phaseless bias | set by trial quality; lower it via mean-field background subtraction, symmetry restoration, or multi-determinant / symmetry-projected trials |
| Boundary / twist averaging | finite-size error | PBC has large shell effects; twist-average (TABC) to reach the thermodynamic limit faster; keep size × #twists ≈ const |
| Estimator (mixed vs back-propagated) | observable accuracy | mixed is exact for the energy, biased for non-commuting observables → back-propagation for pure estimates |
| Constraint release / self-consistency | systematic bias removal | free-projection to gauge/remove CP bias, or feed the AFQMC density matrix back as a self-consistent constraint |

**SSE**: β = 1/T grid (a ground-state claim needs a β sweep, not one low-T point); thermalization sweeps (drop early bins); bin size (raise near criticality where autocorrelation grows); sweeps/chains (error bars); MPI chain count.

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
- Phaseless (AFQMC): the complex-auxiliary-field generalization of the constraint (force bias + cosine projection), for systems with a phase problem (Coulomb / ab-initio).

### Routes

- **SSE:** expand `Z = Tr e^{−βH}` as a power series and sample operator strings; measure finite-T observables in a fixed basis. Sign-freeness needs a bipartite / unfrustrated structure (e.g. a sublattice rotation).
- **CPMC/AFQMC:** Hubbard-Stratonovich the two-body interaction into auxiliary fields, then sample paths in over-complete Slater-determinant space — imaginary-time projection of a trial WF (ground state) or a grand-canonical path integral `det[I + B_L⋯B_1]` with fluctuating particle number (finite T). The sign/phase problem comes from the |Ψ₀⟩ ↔ −|Ψ₀⟩ symmetry: determinant space splits at the unknown node ⟨Ψ₀|φ⟩ = 0, and paths reaching it contribute only noise. An exact boundary condition (discard paths crossing the node) keeps the estimate exact; in practice the node is approximated by the trial WF — the **constraint** — removing the sign/phase decay at the cost of a bias. Real fields (short-range Hubbard) → sign problem → **CPMC**; complex fields (Coulomb / ab-initio) → phase problem → **phaseless AFQMC** (force bias). Ground-state energy via the mixed estimator.

## Verification — implementation stage

### Intermediate (mid-run)

- **CPMC:** the energy vs imaginary-time projection should flatten once equilibrated (read τ_eq off it); per-block energies should stabilize; growing free-projection fluctuations signal the sign problem.
- **SSE:** the average sign must stay near 1 — a decaying sign means the route is not controlled.

### Final verification + expert criticism

- Exact small-system cross-check: CPMC vs ED on the same Hamiltonian/boundary (the CPMC-Lab paper tabulates exact small-lattice energies; reproduction values live in `/reproduce-paper`).
- Imaginary-time-step → 0 extrapolation; population-control-bias check (vary walker count); block decorrelation.
- Twist averaging + energy/site vs 1/L² to the thermodynamic limit; benchmark vs Bethe-ansatz / ED where available.
- Constraint-bias control: free-projection / constraint release, a better or symmetry-projected trial, or a self-consistent constraint — the CP energy sitting *below* the exact value is expected, not a correctness guarantee.
- SSE: β convergence for any ground-state claim; finite-size scaling across several L; compare square-lattice Heisenberg to published reference values.
- **Criticize:** quoting the constrained-path energy as if it were variational (it is not); no Δτ→0 or `N_wlk` extrapolation; non-commuting observables read off the mixed estimator without back-propagation; a single-determinant trial with no symmetry restoration and no release/free-projection check on the constraint bias; PBC-only finite-size claims with no twist averaging.

## Citations

- `.knowledge/literature/quantum-monte-carlo/zhang_2019_auxiliary-field-quantum-monte-carlo.md` — Zhang, *AFQMC at Zero- and Finite-Temperature* (2019). Survey: §2 formalism (HS transformation, ground-state projection, §2.3 finite-T grand-canonical), §3 sign/phase problem, exact boundary condition, constrained-path & phaseless approximations.
- `.knowledge/literature/quantum-monte-carlo/1407.7967_cpmc-lab-a-matlab-package-for-constrained-path-monte-carlo-c.md` — Nguyen, Shi, Xu, Zhang, *CPMC-Lab* (2014). CPMC method, parameters, Table I exact energies, §V timing.
- `.knowledge/literature/quantum-monte-carlo/1101.3281_computational-studies-of-quantum-spin-systems.md` — Sandvik (2010). SSE methodology.
- `.knowledge/literature/quantum-monte-carlo/10-1017-9781316417041.md` — Becca & Sorella (2017).
