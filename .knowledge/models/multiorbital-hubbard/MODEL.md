# Multiorbital Hubbard

Solve multiorbital Hubbard / Kanamori-interaction ground-state problems. Local Hilbert space grows as `4^M` for `M` orbitals — always cost out the local sector before recommending a method.

## Physics card

### Hamiltonian

$$ H = -t \sum_{\langle ij\rangle,m,\sigma} \left( c^\dagger_{im\sigma} c_{jm\sigma} + \text{h.c.} \right) + H_{\text{Kanamori}} $$

$$ H_{\text{Kanamori}} = U \sum_{i,m} n_{im\uparrow} n_{im\downarrow} + U' \sum_{i,m\neq m'} n_{im\uparrow} n_{im'\downarrow} + (U'-J_H) \sum_{i,m<m',\sigma} n_{im\sigma} n_{im'\sigma} - J_H \sum_{i,m\neq m'} c^\dagger_{im\uparrow} c_{im\downarrow} c^\dagger_{im'\downarrow} c_{im'\uparrow} + J_H \sum_{i,m\neq m'} c^\dagger_{im\uparrow} c^\dagger_{im\downarrow} c_{im'\downarrow} c_{im'\uparrow} $$

Conventions: `t > 0` (energy unit `t = 1` or bandwidth `D`); orbital index `m = 1..M`; intra-orbital repulsion `U > 0`; for rotationally invariant `t_{2g}`/`e_g` shells `U' = U - 2J_H` and the last two terms are the spin-flip and pair-hopping (Hund) terms (drop them for "density-density only"). Hund's coupling `J_H > 0` favors high-spin alignment. At a half-filled shell (`N = M`) the effective Mott gap is `U_{eff} = U + (M-1)J_H`. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | single-site/impurity + bath · lattice (square/cubic) · `Z→∞` (DMFT/CDMFT) | Runtime scope is the impurity/DMFT-embedded problem; lattice multiorbital is DMFT territory. |
| A2 boundary conditions | impurity: none (0D + bath) · lattice: PBC/cylinder/infinite (DMFT) | Bath discretization, not boundaries, dominates the impurity problem. |
| A3 statistics & local dim | fermion; local dim `4^M` per site (`64` for `M=3`) | The `4^M` local wall is the master cost axis — cost it out before any method. |
| A4 interaction range | short-range: on-site Kanamori (`U`, `U'`, `J_H`) + NN hopping | Local interactions; area-law compatible. |
| B5 entanglement scaling | impurity: area-law bath chain · lattice: area law (2D) / DMFT local | Impurity-as-chain is MPS-friendly; `4^M` inflates per-site MPS cost. |
| B6 spectral gap | metal (Hund's metal, gapless) · Mott insulator (`U > U_c(J_H)`) · orbital-selective Mott (some bands gapped, others metallic) | `J_H` suppresses the Fermi-liquid coherence scale → bad metal above it. |
| B7 ground-state order | Hund's metal (incoherent correlated metal) · Mott / orbital-selective Mott insulator · magnetic order at low T | "Spin-freezing" non-Fermi-liquid regime is the hallmark of Hund's-metal physics. |
| B8 frustration | fermionic sign always; orbital + spin degeneracy enlarges the low-energy manifold | Multiorbital low-energy degeneracy is the source of Hund's-metal correlations. |
| C9 global symmetry | U(1)_charge × SU(2)_spin × orbital symmetry; `J_H` breaks full orbital rotation (keeps SO(3) only with full rotationally-invariant Kanamori) | `J_H` is what lowers orbital symmetry; density-density-only further breaks it. |
| C10 spatial symmetry | impurity: orbital point group (`t_{2g}`/`e_g` crystal field) · lattice: translation + point group | Crystal-field splitting labels the orbital sectors. |
| C11 integrability | non-integrable (multiorbital interactions) | No exact solution; numerical throughout. |
| C12 sign problem | generically severe in multiorbital DQMC; CT-HYB (hybridization-expansion CTQMC) sign-free for density-density, sign-ful with spin-flip/pair-hopping & off-diagonal hybridization | The severe multiorbital sign problem is why CTQMC/ED-bath dominate over lattice DQMC. |
| D13 regime | ground state + finite-T (CTQMC/DMFT); dynamics out of card scope | Hund's-metal coherence scale is a finite-T phenomenon. |
| D14 filling / doping | shell filling `N` (per-orbital occupancy) is the control parameter; strongest correlations away from `N=M` or `N=1` ("Janus" fillings `N=2,4` for `M=3`) | Average shell occupancy, not just `U`, sets the correlation strength. |
| D15 disorder | clean by default | — |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- Hund's metal : incoherent correlated metal — small quasiparticle weight `Z`, large effective mass `m*/m`, reduced coherence temperature `T_coh`; non-Fermi-liquid self-energy in the spin-freezing regime (`Im Σ(iω_n) ∝ ω_n^α`, `α ≈ 0.5` at the boundary).
- Mott insulator : opens for `U > U_c(J_H)`; charge gap `Δ_c ~ U_{eff} = U+(M-1)J_H` at `N=M`.
- Orbital-selective Mott : some orbitals localized (gapped) while others remain itinerant — diagnose per-orbital `Z_m` and spectral weight.
- Magnetic / orbital order at low T : staggered local moment, orbital occupancy imbalance.

### Canonical observables

- Per-orbital occupancies `⟨n_m⟩`, double occupancy `⟨n_{m↑} n_{m↓}⟩`.
- Local moment `⟨S^2⟩`, instantaneous `⟨S_z^2⟩`; total spin (high-spin Hund's-rule multiplet at large `J_H`).
- Quasiparticle weight `Z_m = (1 - ∂Σ/∂ω)^{-1}`, effective mass `m*/m`; coherence scale `T_coh`.
- Spectral function `A(ω)`, self-energy `Σ(iω_n)` (spin-freezing diagnostic).

### Recommended methods

- Primary (single-site / impurity, small `M`, finite bath): **ED** — exact within the discretized bath, U(1)×SU(2)×orbital sectors cut the `4^M·d_bath` space (per `method-property-map.md` §ED).
- Primary (impurity solver in DMFT, finite-T): **CTQMC (CT-HYB)** — handles a continuous bath; sign-free for density-density Kanamori (§QMC/C12).
- Cross-check: **DMRG/MPS impurity solver** for a longer bath chain (§MPS); **DMFT/CDMFT** for the lattice self-energy and Mott/orbital-selective transition. Lattice DQMC is sign-blocked (C12).

### Key reference

[@georges_2012_strong] — the authoritative review of Hund's-coupling physics (Hund's metals, spin-freezing, orbital-selective Mott, the `U_c(J_H)` and `U_{eff}=U+(M-1)J_H` relations) for multiorbital correlated metals, with DMFT benchmarks across `3d`/`4d` TMOs and iron pnictides.
Rendered: `./1207.3033_strong-correlations-from-hund-s-coupling.md`.

### Benchmarks

- Half-filled `M`-orbital shell (`N=M`): the atomic/Mott gap is enhanced by Hund's coupling to `U_{eff} = U + (M-1)J_H` (Georges-de'Medici-Mravlje, Annu. Rev. Condens. Matter Phys. 4, 137 (2012), Eq. 11; Kanamori convention `U' = U - 2J_H`). For the half-filled 3-orbital Hubbard-Kanamori model, DMFT finds `U_c` strongly *reduced* by `J_H` (their Fig. 2), whereas at `N=1` `U_c` *increases* quasi-linearly with `J_H`.
- 3-orbital Hubbard-Kanamori model, "spin-freezing" regime: the imaginary-frequency self-energy behaves as `Im Σ(iω_n) ∝ ω_n^α` with `α ≈ 1/2` at the frozen-moment phase boundary (Werner-Gull-Troyer-Millis, PRL 101, 166405 (2008); reviewed in [@georges_2012_strong]).

## Diagnose

Infer setup from the user's prompt and propose for ratification.

**Canonical defaults:** 3-orbital, density-density Kanamori (no spin-flip/pair-hopping unless requested), impurity context (single site + bath), U and J_Hund from the user's prompt, half-filling per orbital, no spin-orbit, target orbital occupancies + total spin + local moment. Local Hilbert dimension 4^M — cost it out before committing.

**Proposal pattern:** "Going with: 3-orbital Kanamori impurity, density-density only, U=[value], J_Hund=[value], L_bath=4, half-filling. Target: orbital occupancies, total spin, local moment. Override any, or pick: full Kanamori (+ spin-flip + pair-hopping), 2-orbital, lattice context (→ out of current scope for runtime), single-orbital (→ anderson-impurity)."

Build per `.knowledge/conventions.md`. State which Kanamori terms are kept.

## Workflow

1. Cost out the local Hilbert space; if too large, push the user toward fewer orbitals or impurity-only setups.
2. Build interaction terms; document Kanamori relations and which terms are kept.
3. Pick method per the table.
4. First short run on a single-site or impurity problem; verify orbital occupancies and rotational invariance under SO(3) when full Kanamori is used.
5. Sweep convergence parameter; track observable.
6. Verify (next section).

## Method recommendations

| Regime | Method | Card |
|---|---|---|
| Single-site / impurity, small `M`, finite bath | ED | `skills/method-ed/SKILL.md` |
| Multi-orbital impurity with longer bath chain | DMRG / MPS impurity solver | `skills/method-mps/SKILL.md` |
| Lattice multi-orbital | Out of current scope unless DMFT-embedded; flag explicitly. | — |
| DMFT impurity solver | Out of current scope to run; note the context. | — |

## Branch table

| Condition | Action |
|---|---|
| Single-orbital → user is actually doing `hubbard` | Switch to `hubbard`. |
| Question is about local-moment screening, Kondo, mixed valence | Call `kondo-effect`. |
| Question is about Mott / orbital-selective Mott | Call `mott-transition`. |
| Lattice context with self-consistent embedding | Surface DMFT framework as out of current scope. |

## Verification

Default checks:

- **Limit checks** via `.knowledge/limits.md`: `J_Hund = 0` reduces to multi-band Hubbard with only `U` and `U' = U`; full SO(3) rotational invariance only when full Kanamori is used; atomic limit at large `U/W` gives Hund's-rule multiplet (max total spin / orbital angular momentum).
- **Symmetry**: orbital occupancies; total particle count; `S^z` and total `S²` when SU(2) is preserved; rotational invariance check at the local level.
- **Hilbert space sanity**: confirm the basis size matches the analytic `4^M`-style count.
- **Convergence**: bond-dim sweep; bath-size sweep for impurity problems.
- **Cross-method validation** (when feasible) — re-solve at smaller orbital count or with density-density-only interactions as a sanity check; use an ED cross-check via `/method-ed`. See AGENTS.md "Verification practice".

Optional check:

- For three-orbital Kanamori at canonical fillings, compare to published literature where `U`, `J_Hund` match.

## Writeup handoff

After verification, if the user wants to communicate the result, consolidate to a runnable script + short run report, then render it via `/report`. See AGENTS.md "Writeup handoff".

## Related skills

`hubbard` (single-orbital reduction), `anderson-impurity` (impurity-flavored), `mott-transition`, `kondo-effect`.
