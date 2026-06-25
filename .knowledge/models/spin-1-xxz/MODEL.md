# Spin-1 XXZ

Solve spin-1 XXZ chain ground-state problems with optional single-ion anisotropy. Distinct canonical problem family from the `heisenberg` skill (which targets spin-1/2 by default) because the spin-1 Hilbert space and SPT (Haldane) physics define a separate phase-diagram structure.

## Physics card

### Hamiltonian

$$ H = \sum_{\langle ij\rangle}\left[ S_i^x S_j^x + S_i^y S_j^y + \Delta\, S_i^z S_j^z \right] + D \sum_i (S_i^z)^2 $$

Conventions: spin-1 `S`-operators (`d=3`), `⟨ij⟩` nearest-neighbor counted once; in-plane coupling set to 1, `Δ` the XXZ exchange anisotropy (`Δ=1` isotropic Heisenberg, `Δ=0` XY), `D` the single-ion anisotropy. See `.knowledge/conventions.md` for factor/sign translations.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 1D chain (`Z=2`) | Quasi-1D ladders extend the family but soften the topological order. |
| A2 boundary conditions | OBC (DMRG default; exposes edge spins) · PBC (clean entanglement-spectrum cut) | OBC reveals the S=1/2 Haldane edge modes. |
| A3 statistics & local dim | spin-1; `d = 3` | Larger `d` than S=1/2 → higher per-site MPS/ED cost. |
| A4 interaction range | short-range (nearest-neighbor) + on-site `D` | Local. |
| B5 entanglement scaling | Haldane phase: area law (constant `S`), entanglement spectrum doubly degenerate | SPT signature lives in the entanglement spectrum, not a local order parameter. |
| B6 spectral gap | Haldane phase: gapped (Haldane gap) · transitions (Ising/Gaussian): gap closes | Integer-spin chain is gapped — Haldane's conjecture. |
| B7 ground-state order | Haldane = symmetry-protected topological (SPT) · large-`D` trivial · Néel (large `Δ`) SSB | Protected by `Z_2×Z_2` / inversion / time reversal; diagnose via string order. |
| B8 frustration | none (default) | NNN coupling could add competition (out of default scope). |
| C9 global symmetry | U(1) (`S^z_tot`); full SU(2) only at `Δ=1, D=0`; `Z_2×Z_2` (π-rotations) protects the Haldane SPT | `D` breaks SU(2)→U(1) even at `Δ=1`. |
| C10 spatial symmetry | translation, inversion (protects SPT), reflection | Inversion is one of the protecting symmetries. |
| C11 integrability | non-integrable (S=1 Heisenberg chain not Bethe-solvable; cf. exactly-solvable AKLT point with added biquadratic term) | The pure Heisenberg S=1 chain has no exact solution; AKLT is a nearby solvable model. |
| C12 sign problem | sign-free (unfrustrated bipartite chain → QMC applicable; DMRG is the workhorse) | No frustration → no spin sign problem. |
| D13 regime | ground state (`T=0`) default | Gap, string order, entanglement spectrum are the targets. |
| D14 filling / doping | N/A (spin model) | — |
| D15 disorder | clean by default | — |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- Haldane (SPT) : nonzero string order parameter `O_string^z = −lim_{|i−j|→∞} ⟨S_i^z exp(iπ Σ_{i<k<j} S_k^z) S_j^z⟩`; doubly-degenerate entanglement spectrum; fractional S=1/2 edge spins (OBC).
- Large-`D` trivial : product-like `Π|S^z=0⟩`; string order vanishes; entanglement spectrum non-degenerate.
- Néel (large `Δ`) : staggered magnetization, conventional SSB.

### Canonical observables

- `E/N`; Haldane gap `Δ_H`.
- String order parameter (Haldane diagnostic) and conventional staggered magnetization.
- Entanglement spectrum (degeneracy = SPT signature); edge magnetization (OBC).

### Recommended methods

- Primary: **DMRG/MPS** — 1D gapped area-law ground state; MPS natively measures string order and the entanglement spectrum (per `method-property-map.md` B7-SPT row).
- Cross-check: **ED** on `L ≲ 14` for exact gap/spectrum; **TEBD** imaginary-time route; sign-free **QMC** also available (unfrustrated).

### Key reference

[@wierschem_2014_characterizing] — concise review of the Haldane phase in spin-1 Heisenberg antiferromagnets: string order, SPT classification, entanglement spectrum, and quasi-1D phase diagram.
Rendered: `./1501.00422_characterizing-the-haldane-phase-in-quasi-one-dimensional-sp.md`.

### Benchmarks

- Haldane gap (S=1 isotropic Heisenberg chain, `Δ=1, D=0`): `Δ_H/J ≈ 0.41048(6)` — DMRG/QMC (White & Huse, Phys. Rev. B 48, 3844 (1993); Todo & Kato 2001).
- Ground-state energy: `E/N ≈ −1.401484039` per spin (White & Huse DMRG, same `H` with in-plane coupling 1).

## Diagnose

Infer the canonical setup from the user's prompt and propose it for ratification.

**Canonical defaults:** S=1, isotropic `Δ = 1`, `D` from the user's prompt (default `D = 0` — pure Heisenberg spin-1, in the Haldane phase), `S^z_total = 0` sector, OBC, `L = 32`, target `E/N` and a phase-diagnostic observable (e.g., string order parameter).

**Proposal pattern:** "Going with: 1D chain, S=1, `Δ = 1`, `D = [value]`, `S^z_total = 0`, OBC, `L = 32`, target `E/N` and Haldane-phase indicator. Override any, or pick: `D`-scan across the phase diagram (Néel ↔ Haldane ↔ large-`D`), `Δ`-scan."

Build per `.knowledge/conventions.md`. The Hamiltonian:

```
H = Σ_{⟨ij⟩} [ S_i^x S_j^x + S_i^y S_j^y + Δ S_i^z S_j^z ] + D Σ_i (S_i^z)²
```

with `S^a` the spin-1 operators. Explicit factor-of-2 / sign translations live in `.knowledge/conventions.md` if the user reports values from a different paper.

## Workflow

1. Set up sites with local dimension 3 and `S^z_total` conservation; choose initial state in the target sector (e.g., a Néel-like product state for finite-size AFM at `D ≪ 0`, or AKLT-like for default Haldane work).
2. Pick method per the table.
3. Short first run; confirm `S^z_total = 0`, lattice translation respected (PBC) or open-boundary effects characterized (OBC).
4. Sweep bond dim until the target observable stabilizes.
5. Verify (next section).
6. If the question becomes phase-diagnostic, hand off via the branch table.

## Method recommendations

| Regime | Method | Card |
|---|---|---|
| 1D chain, ground-state energy + correlations | DMRG | `skills/method-mps/SKILL.md` |
| Small cluster (`L ≲ 14`) for exact spectrum, gap, or cross-check | ED | `skills/method-ed/SKILL.md` |
| Imaginary-time route to ground state | TEBD | `skills/method-mps/SKILL.md` |

## Branch table

| Condition | Action |
|---|---|
| Question is about the Néel-Haldane (Ising) or Haldane–large-`D` (Gaussian) transition | Run the calculation here, then call `criticality`. Reference transition values: `D ≈ −0.3` (Néel-Haldane Ising), `D ≈ 0.97` (Haldane–large-`D` Gaussian) at `Δ = 1`. |
| Question is about Haldane phase identification | Compute string order parameter and entanglement spectrum (degeneracy on a cut); document. SPT-phase identification is a runtime computation, not a separate skill. |
| User asks about spin-1/2 (`S = 1/2`) Heisenberg | Switch to `heisenberg`. |
| User asks about dynamics or finite-T | Out of current scope. |

## Verification

Default checks (all auto-run; results aggregated into the report's verification line):

- **Limit checks** via `.knowledge/limits.md`: at `Δ → ∞` the model is classical Ising-like in `S^z`; at `Δ = 0` it is XY (gapless free-fermion-like in spin-1/2; spin-1 case is more delicate but still computable); at `D → −∞` the ground state is Néel; at `D → +∞` the ground state is the large-`D` trivial product `Π |S^z_i = 0⟩`.
- **Symmetry**: `S^z_total` conservation; lattice translation; reflection symmetry where applicable. Haldane phase is SPT — the entanglement spectrum is doubly degenerate on a periodic cut.
- **Convergence**: bond-dim sweep gives monotonic, asymptoting energy. The Haldane phase has a finite gap → DMRG converges fast; the transition regions are slower (gap closing).
- **Internal consistency**: energy variance small relative to `E²`; string order parameter saturates to a finite value in Haldane, vanishes in trivial phases.
- **Cross-method validation (auto-paired when available)** — use TEBD or another active independent route. Use an ED cross-check via `/method-ed`.

Optional check:

- Reference transitions at `Δ = 1`: `D ≈ −0.3` (Néel-Haldane Ising), `D ≈ 0.97` (Haldane-large-`D` Gaussian) — the established spin-1 XXZ phase diagram. Compare against the literature range, not a single number.

## Frontier flag

The Haldane phase is SPT-protected by spatial inversion / time reversal / `Z_2 × Z_2`; small symmetry-breaking perturbations can drive crossover-like behavior that is easy to mistake for a phase transition. When the user runs a generic `D`-scan with explicit symmetry-breaking present, surface this and offer:

1. The diagnostic plan above (recommended).
2. A constraint-only report (transitions located but topology not labelled).
3. A pointer to the literature range for the given symmetry sector.

Before interpreting evidence in a frontier symmetry-broken regime, search recent literature with a tailored query.

## Branch table (diagnostics)

| Diagnostic | Action |
|---|---|
| `criticality` | Standard finite-size scaling at the two transitions (Ising at `D ≈ −0.3`, Gaussian at `D ≈ 0.97`). |
| `frustration` | Not the canonical framing here unless the user has added next-nearest neighbor coupling that creates competition. |

## Writeup handoff

After verification, if the user wants to communicate the result, consolidate to a runnable script + short run report, then render it via `/report`. See AGENTS.md "Writeup handoff".

## Related skills

`heisenberg` (spin-1/2 case; `S = 1/2` is a different canonical family), `criticality`.
