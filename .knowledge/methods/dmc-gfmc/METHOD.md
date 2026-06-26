<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Projector / Green's-Function / Diffusion Monte Carlo + Fixed-Node (DMC-GFMC)

Imaginary-time projection of a trial state toward the ground state via stochastic walkers; the fermion sign problem is controlled by the fixed-node (or fixed-phase) approximation.

## Method card

### What it is

DMC/GFMC iterates the imaginary-time Schrödinger equation `|Ψ(τ)⟩ = e^{−τH}|Ψ_T⟩` stochastically: `N_w` walkers (particle configurations `R`) diffuse, drift, and are born/killed according to the local energy `E_L(R)`. For bosons and unfrustrated systems the weights are positive throughout — the algorithm is sign-free and exact in the limit `N_w,N_proj→∞`. For fermions the antisymmetry causes walkers to acquire opposite signs; the **fixed-node approximation** kills any walker that crosses the nodal surface of the trial wavefunction `Ψ_T(R)`, replacing the exact GS by the best GS consistent with the trial node. This is a controlled-bias variational bound. GFMC uses the exact propagator in a discrete basis; DMC uses the continuous-space diffusion approximation.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | GS energy (fixed-node = best variational energy given the trial node) · mixed estimators for other observables · forward-walking estimators for unbiased observables (at extra cost) | Mixed estimators for non-commuting observables carry bias `O((Ψ_T−Ψ_0)²)`; forward-walking removes leading bias but adds variance. |
| M2 regime | T=0 (ground state) | Purely a GS projector method; finite-T not naturally accessible. |
| M3 accuracy class | Controlled-bias (fixed-node / fixed-phase = best variational energy given the trial nodal surface); stochastic | Energy is an upper bound given the trial node; exact for bosons/unfrustrated systems (sign-free, no bias). |
| M4 dimension fit (A1) | Any dimension (1D, 2D, 3D, continuum) | Especially powerful in continuum (electronic structure, quantum liquids); lattice GFMC works in any dimension. |
| M5 statistics & local dim (A3) | Bosons (sign-free, exact) · fermions (fixed-node, biased) · spins (via lattice GFMC) | Fermions require a fixed-node constraint; bosons are exact. Continuum electrons are the primary application domain. |
| M6 entanglement regime (B5) | Volume-law tolerated | Walker-based sampling imposes no entanglement restriction; quality determined by the trial node, not entanglement. |
| M7 sign-problem dependence (C12) | Sign-free for bosons / unfrustrated systems; fixed-node (nodal-surface bias) controls the fermion sign | Fixed-node = best variational energy given the trial node; nodal bias is the primary systematic error; stochastic reconfiguration can also help. |
| M8 symmetry exploitation (C9/C10) | Trial state `\|Ψ_T⟩` can carry full point-group / translation / spin symmetry; walker propagation respects these | Better-symmetry trial node → lower fixed-node bias. |
| M9 time complexity | `O(N_w·N_proj·c_step)`; statistical error `1/√(N_w·N_proj)` | `c_step` = cost per walker step (`O(N)` for simple wave functions; `O(N³)` for Slater-determinant trial states); `N_proj` = total projection time / `Δτ`. |
| M10 memory | `O(N_w·N)` | Stores `N_w` walker configurations of `N` particles; modest. |
| M11 control knob | `N_w` (walkers) · `N_proj` (projection time) → statistical error `1/√(N_w·N_proj)`; trial node quality → fixed-node bias | `Δτ→0` extrapolation removes time-step bias; trial node improved by VMC optimization. |
| M12 scale frontier | `N~100`–`1000` particles (continuum electronic structure); `N~100`–`500` sites (lattice GFMC) | State-of-the-art for electron gas, quantum liquids (⁴He, ³He), and lattice Hubbard clusters. |
| M13 primary approximation / bias | Fixed-node (nodal-surface bias): energy upper bound given the trial node; bias eliminated only if the trial node is exact | Controlled in the sense that a better trial node monotonically improves the energy; not variational w.r.t. node position for all observables. |
| M14 hard blocker / failure mode | Fixed-node bias can be large for strongly correlated / frustrated systems where no good trial node is known; forward-walking estimators for observables have large variance; continuum time-step bias `O(Δτ)` requires `Δτ→0` extrapolation | In lattice frustrated magnets the trial node quality degrades rapidly and the fixed-node energy may be far above the true GS. |

### Cost & scaling

- Time: `O(N_w·N_proj·c_step)`; statistical error `1/√(N_w·N_proj)`
- Memory: `O(N_w·N)` walker configurations
- Control knob: `N_w` and `N_proj` (statistical error); trial node (fixed-node bias); `Δτ` (time-step bias)
- Scale frontier: `N~100`–`1000` (continuum); `N~100`–`500` (lattice); thermodynamic-limit via finite-size scaling

### Accuracy & guarantees

- Class: controlled-bias (fixed-node), stochastic; exact for bosons (sign-free)
- Primary approximation & its control: fixed-node approximation → improved by better trial state from VMC optimization
- Error scaling: statistical `1/√(N_w·N_proj)`; fixed-node bias decreases as trial node improves; `Δτ`-bias `O(Δτ)` extrapolated away

### Tasks it computes

- Ground-state energy with the fixed-node upper bound
- Mixed estimators: density, pair correlations `g(r)`, structure factor `S(q)` (mixed-estimator bias for non-commuting observables)
- Forward-walking estimators: unbiased observables at higher variance cost
- For bosons: exact GS energy, superfluid density, condensate fraction

### Recommended for (models / regimes)

- **Continuum bosons (⁴He, cold atoms, quantum liquids):** sign-free, numerically exact — the definitive method for quantum liquid ground states
- **Continuum fermion systems (electron gas, atoms, molecules):** fixed-node DMC gives the best-in-class correlation energies for weakly to moderately correlated systems
- **Lattice GFMC for unfrustrated spins / bosons:** exact GS energy for Heisenberg models where SSE is also available (cross-check partner)
- **When VMC-NQS provides a trial state:** VMC optimizes the node; DMC projects to the fixed-node GS for additional improvement
- Per `method-property-map.md`: preferred for continuum systems; blocked by frustration (poor nodal surface)

### Key reference

[@becca_2017_quantum] — textbook treatment of VMC and projector QMC (GFMC/DMC) with stochastic reconfiguration; the standard pedagogical reference covering the fixed-node approximation, forward-walking estimators, and benchmarks.
Rendered: `../../literature/quantum-monte-carlo/10-1017-9781316417041.md` _(reused)_.

[@sorella_1998_green] — introduces Green Function Monte Carlo with stochastic reconfiguration; foundational for the SR-enhanced projector QMC approach used in lattice systems.
Rendered: `../../literature/variational-monte-carlo-neural-quantum-states/cond-mat-9803107_green-function-monte-carlo-with-stochastic-reconfiguration.md` _(reused)_.

### Benchmarks

- Electron gas `r_s=1`–`5`: DMC fixed-node energy matches diffusion MC benchmark to `< 1 mHa/particle` with Slater–Jastrow trial function [@becca_2017_quantum].
- ⁴He liquid: exact GFMC GS energy `E/N = −7.17(2) K` at experimental density — the reference for quantum liquid benchmarks [@becca_2017_quantum].

## How it is used / Operational

**Owning skill:** `/method-qmc`.

**Default workflow:**
1. Prepare and VMC-optimize the trial state `Ψ_T(R)` (Slater–Jastrow, backflow, or NQS trial state).
2. Initialize `N_w` walkers from `|Ψ_T⟩`; set time step `Δτ` and target population.
3. Propagate walkers: diffuse (kinetic), drift (gradient of `log|Ψ_T|`), reweight (local energy), branching (birth/death).
4. Accumulate fixed-node energy and mixed estimators; run several independent blocks.
5. Extrapolate `Δτ→0` to remove time-step bias; vary `N_w` to converge statistical error.
6. For unbiased observables: run forward-walking estimators (extra propagation after measurement).

**Verification pointers:**
- Fixed-node energy must be ≥ true GS energy: verify against ED on small clusters.
- Time-step extrapolation: plot `E(Δτ)` vs `Δτ`; should be linear → extrapolate to `Δτ=0`.
- Compare to VMC energy: `E_DMC ≤ E_VMC` always (DMC improves on VMC with the same trial state).

**Cross-links:**
- Survey: `method-survey.md` §4.2 (Projector / Green's-function / diffusion MC + fixed-node)
- Model↔method gate: `method-property-map.md` (DMC-GFMC profile)
- Complementary methods: VMC-NQS (provides optimized trial state); AFQMC-CPMC (alternative projector for lattice fermions); SSE (exact lattice GS for unfrustrated spins/bosons — cross-check)
