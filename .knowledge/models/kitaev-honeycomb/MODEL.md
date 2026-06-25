# Kitaev honeycomb

Solve the Kitaev honeycomb model — a spin-1/2 model with bond-dependent (compass) Ising exchange that is exactly solvable by Majorana fermionization and hosts a Z2 quantum spin liquid with Abelian and non-Abelian anyonic phases.

## Physics card

### Hamiltonian

$$ H = -J_x \sum_{\langle ij\rangle_x}\sigma^x_i\sigma^x_j \;-\; J_y \sum_{\langle ij\rangle_y}\sigma^y_i\sigma^y_j \;-\; J_z \sum_{\langle ij\rangle_z}\sigma^z_i\sigma^z_j $$

Conventions: spin-1/2 Pauli operators `σ^a` (NOT `S^a`; divide by 2 per operator to convert to `S`-convention, i.e. a factor 4 per bilinear); the three honeycomb bond directions `x/y/z` carry, respectively, `σ^xσ^x`, `σ^yσ^y`, `σ^zσ^z` couplings (the bond-dependent "compass" structure). `J_a > 0` ferromagnetic per the sign above; the largest coupling is set to the energy unit. Isotropic point `J_x=J_y=J_z`. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 2D honeycomb lattice (`Z=3`, two-site unit cell) | Three inequivalent bond directions — the source of the compass exchange. |
| A2 boundary conditions | torus / PBC (flux sectors, exact solution) · cylinder (DMRG) | Torus is needed for the Z2 ground-state degeneracy and flux sectors. |
| A3 statistics & local dim | spin-1/2; `d = 2`; solved via Majorana fermions (4 Majoranas/site, projected) | Fermionization is the engine of exact solvability. |
| A4 interaction range | short-range (nearest-neighbor, bond-dependent) | Local. |
| B5 entanglement scaling | area law + topological term; gapped phase has TEE `γ = ln 𝒟 = ln 2` (total quantum dimension `𝒟 = 2`) | The toric-code (gapped) phase is a Z2 topological state. |
| B6 spectral gap | gapless Z2 spin liquid (Dirac cones, isotropic regime) · gapped Z2 (anisotropic regime) · field-induced gap in the gapless phase | A magnetic field gaps the gapless phase into a chiral non-Abelian (Ising-anyon) phase. |
| B7 ground-state order | **Z2 quantum spin liquid** — no local order; fractionalized Majorana + static Z2 flux excitations | Gapless (B-phase, Dirac) or gapped (A-phase, Abelian toric-code anyons); field → non-Abelian Ising anyons. |
| B8 frustration | bond-dependent (compass) exchange frustration | Competing `x/y/z` Ising axes cannot be simultaneously satisfied → exchange frustration. |
| C9 global symmetry | Z2 gauge structure (static flux `W_p` per plaquette, conserved); time-reversal; lattice-encoded | Each plaquette flux `W_p = ±1` is a constant of motion; ground state is flux-free (Lieb's theorem). |
| C10 spatial symmetry | translation, `C_3` rotation (permutes `x/y/z` bonds), inversion | `C_3` exchanges the three coupling channels. |
| C11 integrability | **exactly solvable** (free Majorana fermions in a static Z2 gauge field) | Quadratic after fermionization → exact spectrum, phase diagram, and anyon content. |
| C12 sign problem | the spin model has a sign problem; the exact Majorana solution sidesteps it entirely | Direct spin QMC is sign-blocked (frustration); the free-fermion mapping makes the model exactly tractable instead. |
| D13 regime | ground state (`T=0`) default; the exact solution also gives finite-T and dynamics | Flux-sector energetics, gap, anyon statistics are the targets. |
| D14 filling / doping | N/A (spin model; the Majorana sector is at its natural filling) | — |
| D15 disorder | clean by default | Bond disorder studied as a perturbation (out of scope). |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- Gapless Z2 spin liquid (B phase) : isotropic / near-isotropic regime `|J_x| ≤ |J_y|+|J_z|` (and cyclic), Majorana Dirac cones; no local order parameter — diagnosed by the flux structure and gaplessness.
- Gapped Z2 spin liquid (A phase, toric-code) : anisotropic regime, e.g. `|J_z| > |J_x|+|J_y|`; Abelian anyons (`e`, `m`), TEE `γ = ln 2`.
- Non-Abelian (Ising-anyon) phase : the gapless B phase in a magnetic field acquires a gap with spectral Chern number `ν = ±1`; excitations are Ising (non-Abelian) anyons.

### Canonical observables

- Ground-state energy per site (flux-free sector, Lieb's theorem).
- Phase boundary location; spectral gap; flux gap.
- Topological entanglement entropy `γ`; spectral Chern number `ν` (field-induced phase); anyon braiding / fusion data.

### Recommended methods

- Primary: **exact Majorana / free-fermion solution** — the model is quadratic after fermionization (`O(N³)`), giving the spectrum, phase diagram, and anyon content exactly (per `method-property-map.md` C11 free-fermion row).
- Cross-check: **ED** on small tori (exact spectrum, flux sectors); **DMRG/MPS** on cylinders for field-perturbed or material-extended (Kitaev–Heisenberg) versions where the exact solution breaks; **VMC** for extended models (QMC sign-blocked).

### Key reference

[@kitaev_2005_anyons] — the foundational paper: exact Majorana solution, the full phase diagram (gapless vs gapped Z2), Lieb's flux-free ground state, the field-induced non-Abelian phase, and the Chern-number classification of anyons.
Rendered: `./cond-mat-0506438_anyons-in-an-exactly-solved-model-and-beyond.md`.

### Benchmarks

- Gapless↔gapped phase boundary (isotropic-coupling triangle): the gapless B phase occupies `|J_x| ≤ |J_y|+|J_z|` and cyclic permutations; the gapped A phases lie outside, e.g. the boundary `|J_z| = |J_x|+|J_y|` (convention `H = −Σ J_a σ^a σ^a`).
- Field-induced B phase: spectral Chern number `ν = ±1`, Ising (non-Abelian) anyons; the gapped A phase has `ν = 0`, Abelian toric-code anyons with TEE `γ = ln 2`.

## How it is studied / Operational

**Canonical defaults (Diagnose):** spin-1/2, isotropic couplings `J_x=J_y=J_z=1` (gapless point) or a user-specified anisotropy, torus/PBC (flux sectors) or cylinder for DMRG, zero field by default, target the ground-state energy + phase identification (gapless vs gapped). If only "Kitaev honeycomb" is given, propose the isotropic point with the exact Majorana solution and offer an anisotropy scan across the phase boundary.

| Regime | Method | Card |
|---|---|---|
| Pure Kitaev model, any coupling — energy, gap, phase | exact Majorana / free-fermion solution | `skills/method-ed/SKILL.md` (quadratic diagonalization) |
| Small torus, exact spectrum / flux sectors / cross-check | ED | `skills/method-ed/SKILL.md` |
| Field-perturbed or Kitaev–Heisenberg extension (not exactly solvable) | DMRG cylinder | `skills/method-mps/SKILL.md` |
| Extended 2D model, variational comparison (QMC sign-blocked) | VMC/NQS | `skills/method-vmc/SKILL.md` |

Verification pointers:

- Ground state is flux-free (Lieb's theorem) — confirm the flux sector before reading off energies.
- Phase boundary `|J_z| = |J_x|+|J_y|` (and cyclic) separates gapless from gapped; the gapped phase has TEE `γ = ln 2`.
- Plaquette flux `W_p` conserved; `C_3` symmetry permutes the `x/y/z` channels.
- The exact Majorana spectrum is the benchmark for any approximate (DMRG/VMC) run on the pure model; for topological diagnostics (TEE, anyons) use the cylinder/torus protocols.
