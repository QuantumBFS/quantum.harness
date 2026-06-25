# SSH (Su–Schrieffer–Heeger)

The dimerized hopping chain — the textbook 1D topological insulator. A free-fermion (quadratic) model, exactly solvable in `O(N³)`, whose two phases (trivial vs topological) are distinguished by a quantized winding number / Zak phase, with protected zero-energy edge modes via bulk–boundary correspondence.

## Physics card

### Hamiltonian

$$ H = \sum_{n} \left[ t_1\, c^\dagger_{A,n} c_{B,n} + t_2\, c^\dagger_{B,n} c_{A,n+1} + \text{h.c.} \right] $$

Conventions: spinless fermions on a chain with a two-site (A, B) unit cell; `t_1 > 0` is the **intracell** hopping (A↔B within cell `n`), `t_2 > 0` the **intercell** hopping (B of cell `n` ↔ A of cell `n+1`). Energy unit set by the larger of `t_1, t_2`. The model is purely quadratic (no interactions). Topological for `t_2 > t_1`, trivial for `t_1 > t_2`; gap closes at `t_1 = t_2`. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 1D chain, two-site (A/B sublattice) unit cell | The dimerization is the entire story. |
| A2 boundary conditions | OBC (edge states, bulk–boundary correspondence) · PBC (Bloch bands, winding number) | OBC is essential to expose the zero-energy edge modes; PBC for the bulk invariant. |
| A3 statistics & local dim | spinless fermion; `d = 2` per site (single orbital) | Single-particle problem per `k`; the many-body state is a Slater determinant. |
| A4 interaction range | short-range: nearest-neighbor hopping only (alternating `t_1`, `t_2`) | Local; no interactions. |
| B5 entanglement scaling | area law (constant, gapped) — entanglement spectrum carries the topological signature (degeneracy in the topological phase) | Free-fermion ground state; entanglement-spectrum degeneracy ↔ edge modes. |
| B6 spectral gap | gapped (bulk gap `= 2|t_1 − t_2|`) everywhere **except** the critical point `t_1 = t_2` (Dirac point, gapless) | Gap closing at `t_1=t_2` is the topological phase transition. |
| B7 ground-state order | **1D symmetry-protected topological (SPT)** phase (`t_2>t_1`) vs trivial (`t_1>t_2`) — class **BDI / AIII** (chiral/sublattice symmetry) | Topological phase: winding number `ν=1`, Zak phase `π`, protected zero-energy edge states. Trivial: `ν=0`, Zak phase `0`. |
| B8 frustration | none (free fermions, bipartite) | — |
| C9 global symmetry | chiral / sublattice (A/B) symmetry `Γ = σ_z` (the protecting symmetry; quantizes the winding/Zak phase) + U(1) charge (particle number); time-reversal + particle-hole → class BDI | Chiral symmetry is what protects the SPT; breaking it (e.g. an on-site staggered potential) trivializes the topology. |
| C10 spatial symmetry | translation by one unit cell (`k`); inversion | Inversion also quantizes the Zak phase (inversion-symmetric SPT). |
| C11 integrability | **free-fermion / quadratic → exactly solvable in `O(N³)`** despite the lattice | Diagonalize the `2N×2N` (or `2×2` Bloch) single-particle Hamiltonian; no many-body numerics needed. |
| C12 sign problem | N/A — free fermions, no Monte Carlo required | — |
| D13 regime | ground state (`T=0`) default; quench / dynamics also exactly tractable (quadratic) | Half-filled (one fermion per cell) lower band is the canonical ground state. |
| D14 filling / doping | half-filling (lower band filled) is the insulating, topologically nontrivial reference; the gap sits at zero energy | — |
| D15 disorder | clean by default; bond disorder preserving chiral symmetry keeps the topology (studied as a perturbation) | — |
| D16 hermiticity | Hermitian / closed by default | **Non-Hermitian SSH** is a heavily studied extension (asymmetric hopping → non-Hermitian skin effect, breakdown of conventional bulk–boundary correspondence). |

### Phases & order parameters

- Topological phase (`t_2 > t_1`) : winding number `ν = 1`, Zak phase `π`; under OBC, two exponentially-localized zero-energy edge modes (one per end) — diagnose by the bulk winding number, the Zak/Berry phase, or the OBC edge-state count.
- Trivial phase (`t_1 > t_2`) : winding number `ν = 0`, Zak phase `0`; no edge states.
- Critical point (`t_1 = t_2`) : bulk gap closes (Dirac point), topological transition.

### Canonical observables

- Bulk band structure / bulk gap `= 2|t_1 − t_2|`.
- Winding number `ν` (chiral invariant) / Zak (Berry) phase (`0` or `π`).
- OBC edge-state spectrum (zero-energy modes) and edge-mode localization length.
- Entanglement spectrum (degeneracy = topological marker); single-particle correlation matrix.

### Recommended methods

- Primary: **exact free-fermion diagonalization** — quadratic Hamiltonian, solved in `O(N³)` (Bloch bands for the invariant under PBC; real-space `2N×2N` matrix for the OBC edge modes), per `method-property-map.md` C11 free-fermion row.
- Cross-check: **ED** small-`N` as a sanity check; **DMRG/MPS** to confirm entanglement-spectrum degeneracy and to extend to the interacting / extended-SSH case (where the free-fermion solution no longer applies).

### Key reference

[@asboth_2015_short] — Asbóth, Oroszlány & Pályi, "A Short Course on Topological Insulators": the canonical pedagogical all-details source; its opening SSH chapter develops the dimerized chain, chiral symmetry, the winding number, the Zak phase, bulk–boundary correspondence, and the edge states in full.
Rendered: `./1509.02295_a-short-course-on-topological-insulators-band-structure-topo.md`.

### Benchmarks

- Bulk gap `Δ = 2|t_1 − t_2|` (PBC, convention `H = Σ t_1 c†_A c_B + t_2 c†_B c_{A,n+1} + h.c.`); gap closes at `t_1 = t_2`.
- Winding number / Zak phase: `ν = 1`, Zak `= π` for `t_2 > t_1` (topological); `ν = 0`, Zak `= 0` for `t_1 > t_2` (trivial) — Asbóth et al. [@asboth_2015_short].
- OBC, topological phase (`t_2 > t_1`): exactly two zero-energy edge modes (one localized at each end), exponentially decaying with length `∝ 1/ln(t_2/t_1)`; none in the trivial phase.

## How it is studied / Operational

**Canonical defaults (Diagnose):** spinless fermion chain, two-site cell, `(t_1, t_2)` from the user's prompt (default `t_1 = 1, t_2 = 1.5` — topological), half-filling (lower band filled), `N = 40` cells, OBC to expose edge modes (plus a PBC run for the bulk invariant), target the bulk gap + winding/Zak phase + edge-mode spectrum. If only "SSH" is given, propose one topological and one trivial parameter set and contrast their invariants and edge spectra. Because the model is quadratic, all of this is an exact `O(N³)` single-particle calculation — no variational or sampling method is needed.

| Regime | Method | Card |
|---|---|---|
| Bulk invariant / bands / edge modes (any size) | exact free-fermion diagonalization (`O(N³)`) | `skills/method-ed/SKILL.md` (quadratic / single-particle) |
| Small-`N` cross-check, full many-body spectrum | ED | `skills/method-ed/SKILL.md` |
| Interacting / extended SSH (free-fermion solution breaks) | DMRG/MPS — entanglement-spectrum degeneracy, edge modes | `skills/method-mps/SKILL.md` |

Verification pointers:

- Limit checks: `t_1 = 0` (fully dimerized topological) → perfectly localized zero-energy modes on the two terminal sites; `t_2 = 0` (fully dimerized trivial) → no edge modes. See `.knowledge/limits.md`.
- The bulk winding number / Zak phase (PBC) must match the OBC edge-state count (bulk–boundary correspondence) — the central self-consistency check.
- Chiral (sublattice) symmetry `{Γ, H} = 0` must hold; adding a symmetry-breaking on-site staggered potential should gap the edge modes and trivialize the topology (a directed perturbation check).
- Entanglement-spectrum degeneracy is the SPT marker — confirm it appears only in the topological phase.
