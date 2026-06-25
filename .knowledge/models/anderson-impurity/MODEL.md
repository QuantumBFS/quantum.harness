# Anderson Impurity

Solve Anderson impurity ground-state problems. The Hamiltonian decomposes into a local interacting piece, a bath, and a hybridization. Bath discretization quality is the dominant practical concern.

## Physics card

### Hamiltonian

$$ H = \varepsilon_d \sum_\sigma n_{d\sigma} + U\, n_{d\uparrow} n_{d\downarrow} + \sum_{k\sigma} \varepsilon_k c^\dagger_{k\sigma} c_{k\sigma} + \sum_{k\sigma} \left( V_k\, d^\dagger_\sigma c_{k\sigma} + \text{h.c.} \right) $$

Conventions: a single interacting impurity level `ε_d` with on-site repulsion `U > 0`, hybridized (`V_k`) to a non-interacting bath `{ε_k}`. The hybridization strength is `Γ(ω) = π Σ_k |V_k|² δ(ω - ε_k)` (flat-band `Γ` = constant). The **symmetric** Anderson model sits at `ε_d = -U/2`, where the model is particle-hole symmetric and `⟨n_d⟩ = 1`. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 0D impurity + bath (**not a lattice**) — bath represented as a star (from `Γ(ω)`) or a 1D Wilson/Lanczos chain | The bath geometry (star vs chain) is a representation choice, not a lattice. |
| A2 boundary conditions | none in the lattice sense; finite-bath ED truncates the bath, NRG uses a semi-infinite chain | Bath discretization quality is the dominant concern. |
| A3 statistics & local dim | fermion; impurity local dim `d = 4` (∅, ↑, ↓, ↑↓) + bath sites (`d=4` each) | Cost is impurity `4` × bath `4^{L_bath}`. |
| A4 interaction range | interaction is purely local (on the impurity); hybridization is local impurity↔bath | Only the impurity is interacting — this is what makes NRG/CTQMC tractable. |
| B5 entanglement scaling | area-law along the Wilson/Lanczos bath chain (single cut) → MPS/NRG friendly | Logarithmic discretization gives energy-scale separation NRG exploits. |
| B6 spectral gap | gapless (metallic bath); below `T_K` a Kondo resonance pins at the Fermi level | The Kondo screening scale `T_K`, not a gap, is the relevant low-energy scale. |
| B7 ground-state order | unique non-degenerate Kondo singlet (local moment screened by the bath) | Local-moment regime above `T_K`, screened singlet below — a crossover, not SSB. |
| B8 frustration | none (single impurity); fermionic, but sign-controlled by NRG/ED | No geometric frustration; multichannel variants can give non-Fermi-liquid fixed points. |
| C9 global symmetry | total `N` and total `S^z` conserved (impurity + bath); symmetric point `ε_d=-U/2` adds particle-hole symmetry; SU(2) spin with no field | PH symmetry at the symmetric point fixes `⟨n_d⟩=1` and protects the NRG iteration. |
| C10 spatial symmetry | n/a (0D); channel/orbital symmetry in multichannel/multiorbital variants | Single-channel symmetric SIAM is the canonical case. |
| C11 integrability | **Bethe-ansatz solvable** (Wiegmann; Tsvelick–Wiegmann) — exact thermodynamics | Provides exact `T_K`, susceptibility, and Wilson-ratio benchmarks. |
| C12 sign problem | NRG/ED: none · CT-HYB CTQMC: sign-free for the single-orbital SIAM | Single-orbital is benign; multiorbital with spin-flip/pair-hopping is sign-ful (→ multiorbital-hubbard). |
| D13 regime | ground state + finite-T (NRG gives full `T`-dependence) and dynamics (spectral functions) | NRG natively produces thermodynamics and `A(ω)` down to `T→0`. |
| D14 filling / doping | impurity occupancy `⟨n_d⟩` set by `ε_d/U`; `⟨n_d⟩=1` at the symmetric point (Kondo regime); mixed-valence near `ε_d≈0` or `ε_d≈-U` | Tuning `ε_d` moves between Kondo, empty/full, and mixed-valence regimes. |
| D15 disorder | clean single impurity by default (disorder enters only via lattice/DMFT embedding) | — |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- Local-moment regime (`T ≫ T_K`) : unscreened impurity spin — Curie-like susceptibility `χ_imp ~ 1/T`, impurity entropy `S_imp → ln 2`.
- Kondo-screened singlet (`T ≪ T_K`) : moment quenched — Pauli-like (`χ_imp` finite), `S_imp → 0`, Kondo resonance in `A(ω)` at the Fermi level. Crossover, not a phase transition; characterized by the Kondo scale `T_K`.
- Mixed valence / empty-orbital : away from the symmetric point, charge fluctuations dominate (`⟨n_d⟩ ≠ 1`).

### Canonical observables

- Impurity occupancy `⟨n_d⟩`, double occupancy `⟨n_{d↑} n_{d↓}⟩`; local moment `⟨S_z^2⟩`.
- Kondo temperature `T_K`; impurity contributions to entropy `S_imp(T)`, specific heat, magnetic susceptibility `χ_imp(T)`.
- Wilson ratio `R_W = 4π²χ_imp/(3γ_imp)`; impurity spectral function `A(ω)` (Kondo resonance, Hubbard satellites).

### Recommended methods

- Primary: **NRG** (numerical renormalization group) — logarithmic bath discretization + iterative diagonalization resolves the exponentially small `T_K` and the full crossover; the method of record for quantum-impurity problems (per `method-property-map.md` §ED/RG reasoning).
- Cross-check: **ED with a finite discretized bath** (`L_bath ≲ 8`) as an exact oracle (§ED); **CT-HYB CTQMC** for a continuous bath at finite-T (§QMC, sign-free single-orbital); **DMRG/MPS** impurity solver for a long bath chain (§MPS).

### Key reference

[@bulla_2007_numerical] — the authoritative review of the numerical renormalization group for quantum-impurity systems (logarithmic discretization, iterative diagonalization, fixed points, thermodynamics, spectral functions, Wilson ratio), the all-details methods source for the Anderson/Kondo impurity.
Rendered: `./cond-mat-0701105_numerical-renormalization-group-method-for-quantum-impurity.md`.

### Benchmarks

- Symmetric single-channel Anderson/Kondo model, strong-coupling fixed point: high-`T` impurity entropy `S_imp(T→∞) = ln 2` and Wilson ratio `R_W = 2` are reproduced by NRG with high precision (Wilson, Rev. Mod. Phys. 47, 773 (1975); Bulla–Costi–Pruschke review [@bulla_2007_numerical], Fig. 5). NRG with discretization `Λ ≈ 2` already gives static properties to within a few percent.
- Symmetric Anderson Kondo scale: `T_K ∝ √{UΓ}·exp(-πU/8Γ + πΓ/2U)` (Haldane, Phys. Rev. Lett. 40, 416 (1978)); the leading exponential `T_K ~ exp(-πU/8Γ)` sets the exponentially small low-energy scale that NRG is built to resolve. The Bethe-ansatz solution (Tsvelick–Wiegmann, Adv. Phys. 32, 453 (1983)) gives the exact universal thermodynamics against which NRG `χ_imp(T)` is checked.

## Diagnose

Infer setup from the user's prompt and propose for ratification.

**Canonical defaults:** single-orbital symmetric Anderson (ε_d = -U/2), U and Γ from the user's prompt, flat-band bath with L_bath=6, half-filling, target occupancy + local moment + T_K estimate.

**Proposal pattern:** "Going with: single-orbital symmetric Anderson, U/Γ=[value], flat-band bath L_bath=6, half-filling. Target: ⟨n_d⟩, local moment, T_K estimate (Haldane formula + ED cross-check). Override any, or pick: multi-orbital (→ multiorbital-hubbard), asymmetric Anderson (ε_d ≠ -U/2), longer bath chain (DMRG)."

If multi-orbital, hand off to `multiorbital-hubbard`. Build per `.knowledge/conventions.md`.

## Workflow

1. Choose bath representation: star geometry (direct from `Δ(ω)`) or chain geometry (after Lanczos-style mapping). Document.
2. Set up sites; pin `(N↑, N↓)` sector.
3. Pick method per the table.
4. First short run; verify particle / spin numbers, impurity occupancy at trivial limits.
5. Vary bath size (or chain length, bond dim) until target observable converges.
6. Verify (next section).

## Method recommendations

| Regime | Method | Card |
|---|---|---|
| Finite bath, small system (`L_bath` ≲ 8) | ED | `skills/method-ed/SKILL.md` |
| Bath as a chain, longer chains | DMRG / MPS impurity solver | `skills/method-mps/SKILL.md` |
| Continuous bath, low-energy Kondo scaling | NRG-style reasoning (out of current scope to run; note conceptually). | — |
| DMFT lattice self-consistency | Out of current scope; flag and discuss the embedding context. | — |

## Branch table

| Condition | Action |
|---|---|
| Question is about Kondo screening, local moment formation, screening scales | Call `kondo-effect`. |
| Multi-orbital, Hund's coupling, Kanamori interactions | Switch to `multiorbital-hubbard`. |
| Impurity arises from a lattice DMFT loop | Out of current scope; surface and discuss. |

## Verification

Default checks:

- **Limit checks** via `.knowledge/limits.md`: `V = 0` → impurity decouples (trivial atomic limit); `U = 0` → resonant level model (exactly solvable); symmetric Anderson at `ε_d = -U/2` → particle-hole symmetric, `⟨n_d⟩ = 1`.
- **Symmetry**: total particle count, `S^z`, particle-hole at the symmetric point.
- **Bath-size convergence**: report the trend of the observable as `L_bath` (or chain length) grows.
- **Internal consistency**: variance; impurity occupancy; local moment.
- **Cross-method validation** (when feasible) — cross-check star vs chain bath geometry; use an ED cross-check via `/method-ed`. See AGENTS.md "Verification practice".

Optional check:

- Symmetric Anderson Kondo scale via Haldane formula in `.knowledge/limits.md` (`T_K`); compare against a finite-bath estimate where possible. Treat as order-of-magnitude consistency, not a benchmark match.

## Writeup handoff

After verification, if the user wants to communicate the result, consolidate to a runnable script + short run report, then render it via `/report`. See AGENTS.md "Writeup handoff".

## Related skills

`kondo-effect`, `multiorbital-hubbard`, `mott-transition` (lattice context).
