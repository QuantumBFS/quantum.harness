# Toric code

The exactly-solvable Z2 stabilizer model on a square lattice (qubits on edges) — the minimal model of intrinsic topological order, with a 4-fold-degenerate ground space on the torus, Abelian `e`/`m` anyons, and topological entanglement entropy `γ = ln 2`.

This is a reference / conceptual card, not a compute target: every quantity of interest is known exactly, so it serves as the canonical anchor for topological-order diagnostics (GSD, anyons, TEE) used elsewhere.

## Physics card

### Hamiltonian

$$ H = -\sum_v A_v \;-\; \sum_p B_p, \qquad A_v=\prod_{i\in v}\sigma^x_i,\quad B_p=\prod_{i\in p}\sigma^z_i $$

Conventions: spin-1/2 qubits live on the **edges** of a square lattice; the star operator `A_v` is the product of `σ^x` over the four edges meeting at vertex `v`; the plaquette operator `B_p` is the product of `σ^z` over the four edges around plaquette `p`. All `A_v`, `B_p` mutually commute (each shares 0 or 2 edges) → exactly solvable stabilizer Hamiltonian. Coupling set to the energy unit. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 2D square lattice, qubits on edges (`Z` = 4 edges per star/plaquette) | Generalizes to any 2D surface; genus controls the degeneracy. |
| A2 boundary conditions | torus (PBC×PBC) for the topological degeneracy · planar with boundaries for codes | Ground-state degeneracy is `2^{2g}` on a genus-`g` surface. |
| A3 statistics & local dim | spin-1/2 qubit; `d = 2` | The qubit-on-edge layout is the defining feature. |
| A4 interaction range | short-range (local 4-body stabilizers) | Strictly local. |
| B5 entanglement scaling | area law with a topological correction: `S = α L − γ`, `γ = ln 2` (`𝒟 = 2`) | TEE `γ = ln 2` is the entanglement signature of the Z2 order. |
| B6 spectral gap | gapped (constant gap above the ground space) | Excitations cost a fixed energy per violated stabilizer. |
| B7 ground-state order | **intrinsic topological order** (Z2 / long-range entangled) | No local order parameter; characterized by GSD, anyons, TEE — not symmetry breaking. |
| B8 frustration | none in the usual sense (commuting stabilizers) | The model is exactly frustration-free (all terms minimized simultaneously). |
| C9 global symmetry | Z2 × Z2 (1-form) symmetries; the conserved stabilizers `A_v`, `B_p` | The Wilson/'t Hooft loop operators generate the topological sectors. |
| C10 spatial symmetry | translation, square point group `D_4` | Not needed for solvability; the topological structure is symmetry-independent. |
| C11 integrability | **exactly solvable** (commuting stabilizer Hamiltonian) | Entire spectrum known; ground states are common `+1` eigenstates of all stabilizers. |
| C12 sign problem | N/A — solved exactly; commuting projectors mean no Monte Carlo is needed | The exact stabilizer structure bypasses any sampling. |
| D13 regime | ground state (`T=0`); finite-T destroys the order in 2D (no thermal stability) | The 2D toric code has no finite-`T` topological order; 4D variant does. |
| D14 filling / doping | N/A (spin/qubit model) | — |
| D15 disorder | clean by default; disorder/perturbations studied for code thresholds | Stability under perturbation underlies its use as a quantum memory. |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- Z2 topologically ordered phase : no local order parameter. Diagnostics are the ground-state degeneracy (GSD), the anyon content, and the topological entanglement entropy `γ`.
- Anyons: `e` (electric charge, violated `A_v`), `m` (magnetic flux, violated `B_p`), and the composite fermion `ε = e × m`; `e` and `m` are mutual semions (braiding phase `−1`).

### Canonical observables

- Ground-state degeneracy: `4` on the torus (`2^{2g}` on genus `g`).
- Topological entanglement entropy `γ = ln 2` (total quantum dimension `𝒟 = 2`).
- Spectral gap; anyon braiding statistics; Wilson/'t Hooft loop expectation values.

### Recommended methods

- Primary: **exact stabilizer analysis** — the ground space and full spectrum follow directly from the commuting `A_v`, `B_p` (no numerics required).
- Cross-check / pedagogy: **ED** on a small torus to exhibit GSD = 4 and measure `γ`; **DMRG** on cylinders to extract `γ` from the entanglement entropy as a benchmark of the topological-order toolkit.

### Key reference

[@kitaev_1997_fault] — the founding paper: introduces the toric code, the stabilizer formalism, topological degeneracy on surfaces, Abelian anyons, and fault-tolerant quantum computation by anyon braiding.
Rendered: `./quant-ph-9707021_fault-tolerant-quantum-computation-by-anyons.md`.

### Benchmarks

- Ground-state degeneracy: `GSD = 4` on the torus (exact; `2^{2g}` on genus `g`).
- Topological entanglement entropy: `γ = ln 2` (exact; `𝒟 = 2`).
- Spectral gap: `Δ = 2` (in units of the stabilizer coupling — one `e` plus one `m` excitation, or `2` per single anyon pair depending on convention).

## How it is studied

The toric code is not run as a variational/sampling compute target — it is **solved exactly** and used as the reference standard for topological order. Because every `A_v` and `B_p` commutes with every other and with `H`, the model is a commuting-stabilizer Hamiltonian: the ground states are the simultaneous `+1` eigenstates of all stabilizers, and the entire spectrum is enumerable by counting stabilizer violations (each violated `A_v` is an `e` anyon, each violated `B_p` an `m` anyon). The analysis is therefore algebraic rather than numerical.

What is "measured" are the topological invariants, all of which the model fixes exactly:

- **Ground-state degeneracy (GSD).** On the torus the degeneracy is `4` (`2^{2g}` on a genus-`g` surface), counted by the non-contractible Wilson-loop operators that commute with `H` but not with each other. This is the operational definition of intrinsic topological order: the degeneracy is a global, not local, property.
- **Anyons.** Excitations are deconfined point particles — `e` (charge), `m` (flux), and the composite fermion `ε = e × m`. `e` and `m` braid with a mutual statistical phase of `−1` (mutual semions); braiding is what enables topological quantum computation.
- **Topological entanglement entropy (TEE).** The subleading constant in the area law, `γ = ln 𝒟 = ln 2`, is the entanglement fingerprint of the order and the quantity numerical methods (ED on a torus, DMRG on a cylinder) target when validating their topological-order machinery against this exact answer.

When the toric code appears inside a calculation it is usually as (i) the gapped (Abelian) limit of the `kitaev-honeycomb` model, (ii) a calibration target for measuring `γ` or GSD with a numerical method, or (iii) a quantum error-correcting code, where the same structure protects logical qubits against local errors.
