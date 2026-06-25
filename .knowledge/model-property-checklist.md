# Model Property Checklist

A taxonomy of the intrinsic properties of a quantum many-body lattice model.
Each property is a single axis you can read off a model; together they determine
how hard the model is to study and (via `method-property-map.md`) which numerical
method is appropriate.

This file is the **property list only** — names, possible values, and why each
property matters for tractability/performance. The mapping from properties to
methods lives in `.knowledge/method-property-map.md`.

Use it as a per-model card: fill in the value for each axis, then consult the
method map.

---

## A. Geometry & Hilbert space

### A1 — Dimensionality & geometry
- **Values:** 1D · quasi-1D (ladders, width-`W` cylinders) · 2D · 3D ·
  infinite-dimensional (coordination `Z → ∞`); plus lattice type (chain, square,
  honeycomb, triangular, kagome, pyrochlore, …) and coordination number `Z`.
- **Why it matters:** Dimension and `Z` jointly set the entanglement scaling and
  the strength of quantum fluctuations — the two things that most determine which
  method is feasible. This is the master axis.

### A2 — Boundary conditions
- **Values:** open (OBC) · periodic (PBC) · cylinder (open × periodic) ·
  torus (periodic × periodic) · infinite / translationally-invariant.
- **Why it matters:** Controls finite-size effects, the entanglement across a cut,
  and access to topological diagnostics — ground-state degeneracy needs a torus;
  minimally-entangled states live on cylinders.

### A3 — Particle statistics & local Hilbert dimension
- **Values:** statistics ∈ {spin, hard-core boson, soft-core boson, fermion,
  anyon}; local dimension `d` (2 for spin-½, 3 for spin-1, 4 for a Hubbard site,
  ∞ for bosons → truncated to `n_max`).
- **Why it matters:** Statistics governs whether a Monte Carlo sign appears.
  `d` sets the exponential base of the full Hilbert space (`d^N`) and the per-site
  cost of tensor-network methods.

### A4 — Interaction range
- **Values:** short-range (nearest-neighbor / exponentially decaying) ·
  long-range (power-law `1/r^α`, dipolar, Coulomb).
- **Why it matters:** Long-range couplings can violate the entanglement area law
  and require many-term operator representations, raising cost; short-range
  locality is what most efficient methods assume.

---

## B. Phase & entanglement

### B5 — Entanglement scaling
- **Values:** area law (`S ∝ boundary`: constant in 1D, `∝ L` in 2D) ·
  area law + logarithm (1D criticality, `S = (c/3) log ℓ`, central charge `c`) ·
  volume law (`S ∝ subsystem volume`; generic excited, thermal, and long-time
  states). Subleading constant = topological entanglement entropy `γ = log 𝒟`
  (`𝒟` = total quantum dimension).
- **Why it matters:** The single most important axis for tensor-network methods,
  whose required bond dimension scales as `χ ≳ e^S`. Volume law is the wall that
  pushes you off tensor networks entirely.

### B6 — Spectral gap
- **Values:** gapped (finite `Δ`, finite correlation length `ξ`, exponentially
  decaying correlations) · gapless / critical (`Δ → 0`, `ξ → ∞`, power-law
  correlations).
- **Why it matters:** Gapped local ground states obey the area law (a theorem in
  1D); gapless/critical systems have growing entanglement and stronger
  finite-size effects, making every method harder.

### B7 — Ground-state order type
- **Values:** trivial / product-like · symmetry-broken (conventional order
  parameter) · symmetry-protected topological (SPT — Haldane/AKLT, short-range
  entangled, edge modes, string order) · intrinsic topological order
  (long-range entangled, anyons, ground-state degeneracy, TEE) · quantum spin
  liquid.
- **Why it matters:** Determines whether the unique-ground-state assumption holds
  and which observables/diagnostics are meaningful (order parameter vs string
  order vs minimally-entangled-state degeneracy + TEE).

### B8 — Frustration
- **Values:** none · geometric (triangular, kagome, pyrochlore) · interaction-
  driven (competing couplings, e.g. `J1-J2`) · fermionic (sign from
  antisymmetry).
- **Why it matters:** Produces near-degenerate manifolds and highly entangled
  ground states, and is the usual origin of the Monte Carlo sign problem in spin
  models.

---

## C. Symmetry & solvability

### C9 — Global / internal symmetry
- **Values:** U(1) (particle number or `S^z`) · SU(2) (total spin) · Z₂ ·
  particle-hole · time-reversal · higher groups.
- **Why it matters:** Each commuting symmetry block-diagonalizes the Hamiltonian
  into independent sectors labeled by conserved quantum numbers — the cheapest
  available reduction of cost. Particle-hole symmetry at half-filling additionally
  protects against the fermion sign problem.

### C10 — Spatial / lattice symmetry
- **Values:** translation (→ conserved momentum `k`) · point group (rotations,
  reflections) · inversion / parity.
- **Why it matters:** Further block-diagonalizes within a quantum-number sector
  (momentum and irrep resolution) and labels excited states.

### C11 — Integrability
- **Values:** free-fermion / quadratic (transverse-field Ising, XY, Kitaev
  honeycomb — diagonalizable in `O(N³)` despite a `2^N` space) · Bethe-ansatz
  integrable (1D Heisenberg, 1D Hubbard — exact spectrum and thermodynamics via
  TBA) · non-integrable / generic (chaotic, obeys ETH).
- **Why it matters:** Integrability provides exact analytic benchmarks and forbids
  thermalization (generalized Gibbs ensemble). A generic perturbation destroys it.

### C12 — Sign problem
- **Values:** provably sign-free (bipartite half-filled or attractive Hubbard;
  unfrustrated bipartite spins via the Marshall sign rule) · mild / algebraic ·
  severe (exponential). Basis-dependent, not intrinsic.
- **Why it matters:** The average sign decays as `e^{−βN Δf}`, so a severe sign
  problem makes Monte Carlo cost grow exponentially; the generic problem is
  NP-hard. Caused by fermionic antisymmetry, frustration, doping, magnetic flux,
  and real-time dynamics.

---

## D. Regime & complications

### D13 — Computational regime
- **Values:** ground state (`T = 0`) · finite temperature (thermal equilibrium) ·
  real-time dynamics.
- **Why it matters:** Ground states are easiest for variational methods; finite-T
  needs thermal/purification techniques; real-time evolution makes entanglement
  grow linearly in time (capping the reachable time) and produces the dynamical
  sign problem.

### D14 — Filling / doping
*(fermionic & bosonic models)*
- **Values:** commensurate (half-filling, integer filling → Mott physics) ·
  incommensurate / doped.
- **Why it matters:** Commensurate fillings on bipartite lattices are often
  sign-free and more symmetric; doping breaks particle-hole symmetry, turns on the
  fermion sign problem, and opens competing orders.

### D15 — Disorder / quenched randomness
- **Values:** clean (translation-invariant) · disordered; if disordered,
  ergodic vs many-body-localized (MBL).
- **Why it matters:** Disorder requires averaging over realizations (a sample
  multiplier); MBL produces local integrals of motion, area-law entanglement even
  in excited states, and only logarithmic-in-time entanglement growth.

### D16 — Hermiticity
- **Values:** Hermitian / closed (unitary) · non-Hermitian / open (Lindblad
  master equation, PT-symmetric, post-selected).
- **Why it matters:** Non-Hermitian systems have complex spectra and biorthogonal
  eigenstates (no standard variational principle), exhibit the skin effect, and
  require density-matrix or quantum-trajectory formulations.

---

## Cross-cutting study choices

Not intrinsic model properties, but they co-determine cost and should be recorded
alongside the card:

- **Target observable** — energy / order parameter / correlation function /
  spectrum / dynamics / entanglement.
- **Target system size** `N` — finite cluster vs thermodynamic-limit extrapolation.
- **Accuracy goal** — absolute vs relative energy, acceptable error bar.

---

## How to use this card

1. For a given model, fill in the value for each axis A1–D16.
2. Consult `.knowledge/method-property-map.md` to turn those values into a method
   recommendation.
3. The decisive clusters: **B5 + B6 + B8** gate tensor networks; **C12** gates
   QMC; **A1** picks the method family; **C9 + C10** cut the cost; **C11** can make
   the problem exactly solvable.
