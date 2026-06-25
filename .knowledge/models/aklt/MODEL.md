# AKLT

Solve the spin-1 AKLT chain — the Affleck–Kennedy–Lieb–Tasaki bilinear-biquadratic model whose ground state is an exact valence-bond solid (VBS), the paradigmatic representative of the gapped Haldane symmetry-protected-topological phase.

Distinct from `spin-1-xxz` (the tunable spin-1 family): AKLT is the single exactly-solvable point in that family, used as the rigorous anchor for Haldane-phase physics.

## Physics card

### Hamiltonian

$$ H = \sum_i \left[ \mathbf{S}_i\cdot\mathbf{S}_{i+1} + \tfrac{1}{3}\left(\mathbf{S}_i\cdot\mathbf{S}_{i+1}\right)^2 \right] $$

Conventions: spin-1 `S`-operators (`d=3`); the coefficient ratio is fixed (biquadratic = `1/3` × bilinear) — this is the special point where `H` is, up to a constant, a sum of projectors onto total spin-2 on each bond, making the VBS the exact zero-energy ground state. Coupling set to the energy unit `J = 1`. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 1D chain (`Z=2`) | 2D AKLT (e.g. honeycomb) variants exist but the chain is the canonical case. |
| A2 boundary conditions | OBC (exposes the edge spins) · PBC (clean entanglement-spectrum cut) | OBC gives the 4-fold-degenerate edge-state manifold. |
| A3 statistics & local dim | spin-1; `d = 3` | The ground state is an exact bond-dimension-2 MPS. |
| A4 interaction range | short-range (nearest-neighbor, bilinear + biquadratic) | Local. |
| B5 entanglement scaling | area law (constant `S`); entanglement spectrum exactly 2-fold degenerate; `S = 2 ln 2` (open chain, two cut ends) | Each cut contributes `ln 2`; the exact-degeneracy is the SPT fingerprint. |
| B6 spectral gap | gapped (Haldane gap above the unique bulk ground state) | Bulk gap ≈ 0.35 (numerical); the existence of a gap is rigorously established for AKLT. |
| B7 ground-state order | **symmetry-protected topological (SPT)** — valence-bond solid in the Haldane phase | Protected by `SO(3)`/`Z_2×Z_2` / time-reversal / inversion; diagnosed by hidden string order, not a local order parameter. |
| B8 frustration | none | Unfrustrated bilinear-biquadratic chain. |
| C9 global symmetry | SU(2) (total spin) — exact at the AKLT point; U(1) (`S^z_tot`); `Z_2×Z_2` (π-rotations) protects the SPT | The VBS is an SU(2) singlet on a closed chain. |
| C10 spatial symmetry | translation, inversion (protects the SPT), reflection | Inversion is one of the protecting symmetries. |
| C11 integrability | not Bethe-integrable, but the **ground state is exactly constructed** (VBS / MPS) | Exact GS, energy, and correlators; the full spectrum is not solvable. |
| C12 sign problem | sign-free (unfrustrated bipartite chain → QMC applicable; DMRG is the workhorse) | No frustration. |
| D13 regime | ground state (`T=0`) default | Energy, string order, gap, entanglement spectrum, edge states are the targets. |
| D14 filling / doping | N/A (spin model) | — |
| D15 disorder | clean by default | — |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- Haldane VBS (SPT) : nonzero string order parameter `O_string^z = −lim_{|i−j|→∞} ⟨S^z_i exp(iπ Σ_{i<k<j} S^z_k) S^z_j⟩`; doubly-degenerate entanglement spectrum; on an open chain, 4-fold ground-state degeneracy from emergent free spin-1/2 edge modes (the two ends carry `S=1/2` each).
- The AKLT point sits inside (and exemplifies) the Haldane phase of the broader bilinear-biquadratic / spin-1 XXZ family.

### Canonical observables

- Ground-state energy per site `E/N` (exactly `−2/3`).
- String order parameter (Haldane diagnostic); exactly `4/9` for the AKLT state.
- Bulk gap; entanglement spectrum (exact 2-fold degeneracy); edge magnetization (OBC).

### Recommended methods

- Primary: **DMRG/MPS** — the ground state is literally a bond-dimension-2 MPS, so DMRG is exact at tiny `χ`; MPS natively measures string order and the entanglement spectrum (per `method-property-map.md` B7-SPT row).
- Cross-check: **ED** on `L ≲ 14` for the exact spectrum/gap and edge-state degeneracy; the analytic VBS construction provides closed-form benchmarks (`E/N`, string order).

### Key reference

[@affleck_1987_rigorous] — the defining paper: rigorous construction of the valence-bond ground state, proof of the spectral gap, exponentially-decaying correlations, and the hidden topological order of the Haldane phase.
Rendered: `./10-1103-physrevlett-59-799.md` _(bib stub — no PDF reachable; PRL 1987 paywalled, predates arXiv)_.

### Benchmarks

- Ground-state energy: `E/N = −2/3` — **exact** (VBS construction; convention `H = Σ [S_i·S_{i+1} + (1/3)(S_i·S_{i+1})²]`).
- String order parameter: `O_string = 4/9` — exact for the AKLT VBS state.
- Bulk gap: `Δ ≈ 0.35` (numerical, units of `J`); two-point correlations decay with correlation length `ξ = 1/ln 3 ≈ 0.91` sites (exact).

## How it is studied / Operational

**Canonical defaults (Diagnose):** S=1, fixed AKLT couplings (bilinear `1`, biquadratic `1/3`), `S^z_tot = 0` sector, OBC (to expose edge states) or PBC (clean spectrum), `L = 32`, target `E/N` (= `−2/3`) plus a Haldane-phase indicator (string order, entanglement-spectrum degeneracy). If only "AKLT" is given, propose the exact VBS point with the string-order + entanglement-spectrum diagnostics.

| Regime | Method | Card |
|---|---|---|
| 1D chain, ground state + string order + entanglement spectrum | DMRG (exact at `χ=2`) | `skills/method-mps/SKILL.md` |
| Small cluster (`L ≲ 14`), exact spectrum / edge-state degeneracy | ED | `skills/method-ed/SKILL.md` |
| Verify the gap / correlation length | DMRG correlator decay vs the exact `ξ = 1/ln 3` | `skills/method-mps/SKILL.md` |

Verification pointers:

- Exact analytic anchors: `E/N = −2/3`, string order `= 4/9`, `ξ = 1/ln 3` — any method should reproduce these.
- `S^z_tot` and SU(2) conservation; entanglement spectrum exactly 2-fold degenerate on a cut (SPT signature); OBC gives 4-fold near-degeneracy from the spin-1/2 edge modes.
- DMRG should converge to machine precision at `χ = 2` — failure to do so flags a setup error.
- For a `Δ`/biquadratic scan away from the AKLT point (Haldane ↔ trivial transitions), hand off to `spin-1-xxz` and `criticality`.
