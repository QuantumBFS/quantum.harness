# Spin ice (pyrochlore)

Ising-like rare-earth moments on the 3D pyrochlore lattice of corner-sharing tetrahedra, pinned along their local ⟨111⟩ axes. Effective ferromagnetic coupling enforces a "2-in-2-out" ice rule per tetrahedron, producing a macroscopically degenerate classical spin liquid (the Coulomb phase) with residual Pauling entropy and emergent magnetic monopole excitations.

Distinct from `kitaev-honeycomb` and `toric-code`: spin ice realizes an *emergent U(1)* gauge structure (a classical Coulomb phase / quantum U(1) spin liquid) rather than a `Z₂` topological order, and the canonical regime is finite-temperature statistical mechanics (Monte Carlo, neutron scattering) of a frustrated magnet, not a `T=0` lattice-gauge ground state.

## Physics card

### Hamiltonian

$$ H = J_{\text{eff}} \sum_{\langle ij\rangle} S^{z_i}_i S^{z_j}_j \;\;\Big(\text{equivalently } H = -J \sum_{\langle ij\rangle} \mathbf{S}_i\cdot\mathbf{S}_j \text{ with } \mathbf{S}_i \parallel \hat{z}_i\Big) \;+\; D \sum_{i<j} \frac{\hat{z}_i\cdot\hat{z}_j - 3(\hat{z}_i\cdot\hat{r}_{ij})(\hat{z}_j\cdot\hat{r}_{ij})}{|r_{ij}|^3} $$

Conventions: classical Ising spins `S_i = ±1` pointing along the site-dependent local ⟨111⟩ easy axis `ẑ_i` (the line joining the two tetrahedron centers); `S^{z_i}_i` is the projection onto that local axis. The nearest-neighbor effective coupling `J_eff` is *antiferromagnetic in local-axis variables* but *ferromagnetic in global spins*, so the ground state of each tetrahedron is "2-in-2-out" (the ice rule). `D` is the long-range dipolar coupling (the dominant interaction in real Dy₂Ti₂O₇/Ho₂Ti₂O₇; the "dipolar spin ice" model), which projects onto nearly the same ice manifold. The minimal nearest-neighbor spin-ice model keeps only `J_eff`. Quantum spin ice adds transverse exchange (`S^x S^x + S^y S^y`) terms that lift the classical degeneracy into a U(1) quantum spin liquid. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 3D pyrochlore lattice (corner-sharing tetrahedra, 4-site unit cell, `Z=6`) | The canonical 3D frustrated geometry; FCC array of tetrahedra. |
| A2 boundary conditions | PBC (Monte Carlo on `L×L×L` cubic cells) · open (real crystals) | Long-range dipolar sums use Ewald summation under PBC. |
| A3 statistics & local dim | classical Ising spin (`d=2`, `S=±1` along local ⟨111⟩); quantum spin ice → effective spin-1/2 | Classical version is a statistical-mechanics model; quantum version is a genuine QMB problem. |
| A4 interaction range | NN effective exchange (minimal model) · **long-range dipolar `1/r^3`** (realistic dipolar spin ice) | Remarkably, the dipolar interaction "projects" onto essentially the same ice manifold (near self-screening). |
| B5 entanglement scaling | classical: n/a (thermal ensemble) · quantum spin ice: area law with emergent-gauge structure | The classical Coulomb phase is characterized by power-law (dipolar) *correlations*, not entanglement. |
| B6 spectral gap | classical: gapless ice manifold (macroscopic degeneracy) · monopole excitations cost a finite energy `Δ` above the ice rules · quantum spin ice: gapless emergent **photon** | The 2-in-2-out manifold is the degenerate ground space; flipping to 3-in-1-out creates a monopole pair. |
| B7 ground-state order | **classical spin liquid / Coulomb phase** with an emergent U(1) gauge field (dipolar correlations, pinch points); excitations are fractionalized emergent **magnetic monopoles**. Quantum spin ice → **U(1) quantum spin liquid** with an emergent photon | No conventional symmetry-broken order; the "order" is the emergent gauge constraint (`∇·B = 0` ice rule). |
| B8 frustration | **strong geometric frustration** (corner-sharing tetrahedra) | The ice rule cannot pick a unique state → extensive ground-state degeneracy (the defining feature). |
| C9 global symmetry | global Ising `Z_2` (classical); U(1) emergent gauge symmetry in the Coulomb phase; spin-rotation broken to the local ⟨111⟩ axes | Local axes are fixed by crystal field; the emergent U(1) is a *low-energy* gauge structure, not microscopic. |
| C10 spatial symmetry | cubic point group `Fd-3m`; pyrochlore translations; large degenerate manifold per the symmetry | The structure factor's pinch points sit at high-symmetry zone-boundary points. |
| C11 integrability | not integrable | Solved by Monte Carlo (classical) / numerics (quantum), not by exact ansatz; Pauling's count is an approximation. |
| C12 sign problem | classical → **sign-free Monte Carlo** (positive Boltzmann weights, loop/worm updates) · **quantum spin ice has a sign problem** (frustrated transverse terms) | Classical dipolar spin ice is a Monte Carlo workhorse; the U(1) QSL needs sign-problem-aware methods. |
| D13 regime | mostly **finite-temperature thermodynamics** (specific heat, residual entropy) + dynamics (monopole transport, neutron scattering); quantum spin ice → ground state + low-`T` | The residual-entropy plateau and pinch points are finite-`T` equilibrium signatures. |
| D14 filling / doping | n/a (localized moments); "doping" = nonmagnetic dilution (e.g. Y substitution) which modifies the residual entropy | Dilution studies probe the robustness of the Pauling count. |
| D15 disorder | clean (ideal crystal) by default; real materials have stuffing/dilution disorder | Dilution and the slow-equilibration of Dy₂Ti₂O₇ are active experimental subtleties. |
| D16 hermiticity | classical (Boltzmann) / Hermitian quantum | — |

### Phases & order parameters

- Paramagnet (high `T`) : thermally disordered, no ice correlations.
- Spin-ice Coulomb phase (low `T`, above any ordering) : extensive 2-in-2-out manifold; **residual Pauling entropy**; emergent U(1) gauge field with dipolar spin correlations producing **pinch points** in the (neutron) structure factor; fractionalized **magnetic monopole** excitations (deconfined defects of the ice rule). No local order parameter — the "order" is the divergence-free emergent field `∇·B = 0`.
- Quantum spin ice (transverse coupling) : U(1) quantum spin liquid with an emergent gapless photon and gapped electric/magnetic monopole matter.
- (Material-dependent low-`T` orderings, e.g. all-in-all-out, can pre-empt the ideal Coulomb phase.)

### Canonical observables

- Magnetic specific heat `C(T)` and the integrated residual entropy `S(T→0)`.
- Spin structure factor `S(q)` from (polarized) neutron scattering — the pinch-point singularities are the smoking gun of the Coulomb phase.
- Monopole density and correlations; magnetization curves; ac susceptibility / spin-relaxation dynamics (monopole mobility).

### Recommended methods

- Primary (classical): **Monte Carlo** — sign-free; single-spin-flip plus loop/worm updates (needed because local moves cannot traverse the constrained ice manifold), with Ewald summation for the dipolar tail (per `method-property-map.md` §QMC/MCRG, C12 sign-free).
- Primary (quantum spin ice): **DMRG / ED on finite clusters** and **VMC/gauge-mean-field**, since the transverse terms reintroduce a sign problem for QMC.
- Cross-check: analytic Pauling/ice-rule entropy estimate; experimental specific-heat and neutron-scattering benchmarks.

### Key reference

[@castelnovo_2011_spin] — Annual Review of Condensed Matter Physics review "Spin Ice, Fractionalization, and Topological Order"; the all-details source for the ice rule and pyrochlore geometry, the Coulomb-phase emergent gauge field and pinch points, the residual Pauling entropy, and (centrally) the fractionalized magnetic-monopole excitations and their deconfinement. (The monopole-defining paper is Castelnovo-Moessner-Sondhi, Nature 2008, arXiv:0710.5515; this review subsumes it with the full Coulomb-phase / topological context.)
Rendered: `./1112.3793_spin-ice-fractionalization-and-topological-order.md`.

### Benchmarks

- Residual (Pauling) entropy per spin: `S ≈ (1/2) ln(3/2) ≈ 0.202 k_B` per spin (`≈ 0.202 R` per mole of spins) — Pauling's ice-rule count, consistent with the residual entropy measured in Dy₂Ti₂O₇ by Ramirez et al. (Nature 399, 333 (1999)). Convention: nearest-neighbor / dipolar spin-ice. (Caveat: thermally well-equilibrated Dy₂Ti₂O₇ shows the residual entropy can be released at very low `T` — Pomaranski et al., Nat. Phys. 9, 353 (2013) — so the plateau is a quasi-equilibrium feature.)
- Pinch points: sharp bow-tie singularities in the spin structure factor `S(q)` at high-symmetry zone-boundary points, the real-space dipolar-correlation signature of the emergent U(1) Coulomb phase (neutron scattering on Ho₂Ti₂O₇/Dy₂Ti₂O₇) [@castelnovo_2011_spin].
- Monopole deconfinement: ice-rule defects behave as free magnetic charges interacting via an emergent (entropic + magnetic) Coulomb `1/r` potential; their density and transport set the low-`T` dynamics [@castelnovo_2011_spin].

## How it is studied

Spin ice is primarily a **classical statistical-mechanics and materials** problem rather than a `T=0` variational compute target, so it is analyzed differently from the lattice models in this zoo.

- **Monte Carlo.** The classical (nearest-neighbor or dipolar) model is simulated with Metropolis Monte Carlo, but single-spin flips break the ice rule and freeze; the standard tool is **loop / worm updates** that flip closed loops of alternating spins, moving within the 2-in-2-out manifold ergodically. The long-range dipolar interaction is handled with **Ewald summation** under periodic boundary conditions. Because the Boltzmann weights are positive, there is no sign problem and large `L×L×L` pyrochlore cells are reachable. The headline outputs are the magnetic specific heat `C(T)` and, by integrating `C/T`, the **residual Pauling entropy** `S(T→0) ≈ (1/2)ln(3/2) k_B`/spin — the thermodynamic fingerprint of the macroscopic ice degeneracy.

- **Neutron-scattering pinch points.** The Coulomb phase has an emergent divergence-free field (`∇·B = 0`, the coarse-grained ice rule), which dictates dipolar `1/r^3` spin correlations. In reciprocal space these show up as **pinch points** — sharp bow-tie singularities in the (polarized-neutron) structure factor `S(q)` at zone-boundary points. Their presence (and their broadening by monopole defects as `T` rises) is the experimental and Monte-Carlo diagnostic of the emergent U(1) gauge structure.

- **Magnetic monopoles.** Excitations above the ice manifold are local 3-in-1-out (and 1-in-3-out) defects that fractionalize into pairs of mobile, oppositely-charged **emergent magnetic monopoles** connected by a "Dirac string." They interact via an emergent magnetic Coulomb law and a string tension that is *entropic* (the Coulomb-phase string costs free energy via lost configurations); their density, deconfinement, and transport govern the low-`T` thermodynamics and slow relaxation.

- **Quantum spin ice.** Adding transverse exchange promotes the classical Coulomb phase to a **U(1) quantum spin liquid** with an emergent gapless "photon" and gapped electric/magnetic charges. This regime *does* carry a sign problem, so it is studied with finite-cluster ED, DMRG, gauge-mean-field theory, and VMC rather than sign-free Monte Carlo.

Within the harness, a classical spin-ice request routes to a Monte Carlo calculation of `C(T)` / residual entropy / `S(q)` (the `frustration` skill for regime classification); a quantum-spin-ice request routes to ED/DMRG/VMC with the frustration caveat that QMC is sign-blocked.
