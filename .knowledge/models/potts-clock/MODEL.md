# Potts / Clock

Solve `q`-state quantum Potts and quantum Clock ground-state problems. Generic over `q`. The 1D `q = 3` Clock model is also the quantum 3-state Potts model (after the standard duality), with critical `Z_3` parafermion CFT at `c = 4/5`. Higher `q` extends the family; `q = 2` reduces to the transverse-field Ising chain (use `transverse-field-ising` for that).

## Physics card

### Hamiltonian

$$ H = -\sum_{\langle ij\rangle}\left(X_i X_j^\dagger + X_i^\dagger X_j\right) - h\sum_i\left(Z_i + Z_i^\dagger\right) $$

Conventions: qudit clock/shift operators with `X|k⟩ = |k+1 \bmod q⟩`, `Z|k⟩ = ω_q^k|k⟩`, `ω_q = e^{2πi/q}`; local dimension `d = q`; ferromagnetic coupling set to 1, `h ≥ 0` the transverse clock field (`h_c = 1` for `q=3`). For `q=2` this is the TFIM. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 1D chain (`Z=2`) · 2D square | 1D `q=3` is the canonical parafermion-CFT critical chain. |
| A2 boundary conditions | PBC ring (criticality work) · OBC · cylinder (2D) | PBC preferred for finite-size scaling of the QPT. |
| A3 statistics & local dim | qudit; `d = q` (3, 4, 5, …) | Local dimension grows with `q`, raising ED/MPS cost. |
| A4 interaction range | short-range (nearest-neighbor) | Local. |
| B5 entanglement scaling | gapped phases: area law · 1D critical (`q≤4`): area+log (`c=4/5` at `q=3`, `c=1` at `q=4`) | Central charge set by the parafermion/Potts CFT; `q=3 → c=4/5`. |
| B6 spectral gap | gapped FM (`h<h_c`) and PM (`h>h_c`) · gapless at QCP (`q≤4`) · `q≥5`: first-order (no gapless point) | Order of transition changes at `q=5` in 1D. |
| B7 ground-state order | FM (`h<h_c`): `Z_q` SSB, `q`-fold degenerate · PM (`h>h_c`): trivial | `Z_q` clock order parameter `⟨Z⟩`. |
| B8 frustration | none on bipartite FM · possible on non-square (e.g. triangular Potts) | Default square/chain FM unfrustrated. |
| C9 global symmetry | `Z_q` clock symmetry (generator `Π_i Z_i`) | The symmetry whose breaking defines the FM phase. |
| C10 spatial symmetry | translation (`k`), inversion/reflection | Conserved momentum in PBC rings. |
| C11 integrability | non-integrable in general; `q=2` free-fermion (TFIM); 1D critical point described by `Z_q` parafermion / Potts CFT | Self-dual critical point (Kramers–Wannier-type) located analytically. |
| C12 sign problem | sign-free (ferromagnetic / bipartite) | QMC/SSE applicable; DMRG-qudit is the default workhorse. |
| D13 regime | ground state (`T=0`) + order parameter scan | Criticality via finite-size scaling. |
| D14 filling / doping | N/A (spin/qudit model) | — |
| D15 disorder | clean by default | — |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- Ferromagnet (`h < h_c`) : `Z_q`-broken, `q`-fold degenerate; clock order parameter `⟨Z⟩ ≠ 0`.
- Paramagnet (`h > h_c`) : trivial, field-polarized; `⟨Z⟩ = 0`.
- Critical point (1D `q ≤ 4`) : continuous transition, parafermion/Potts CFT (`q=3`: `c=4/5`, `ν=5/6`). For `q ≥ 5` (1D) the transition is first-order.

### Canonical observables

- `E/N`; `Z_q` order parameter `⟨Z⟩` across an `h`-scan.
- Spectral gap; correlation function `⟨Z_i Z_j^†⟩`.
- Central charge `c` / critical exponent `ν` from finite-size collapse (`q=3`: `ν=5/6`).

### Recommended methods

- Primary: **DMRG (qudit MPS)** in 1D — area-law / area+log ground state, conserves the `Z_q` quantum number (per `method-property-map.md` §MPS, C9).
- Cross-check: **ED** small clusters (`N ≲ 16` for `q=3`) for exact spectrum and the order of the transition; **TEBD** imaginary-time; sign-free **QMC** also applicable.

### Key reference

[@wu_1982_potts] — the authoritative review of the Potts model (classical and quantum, all `q`, duality, order of transition, exact results, CFT connections).
Rendered: `./10-1103-revmodphys-54-235.md` _(bib stub — no PDF reachable; RMP 1982 paywalled, predates arXiv)_.

### Benchmarks

- 1D `q=3` Clock (= 3-state Potts) QCP: `h_c = 1` (self-dual), `Z_3` parafermion CFT `c = 4/5`, `ν = 5/6 ≈ 0.833` (literature range `ν ∈ [0.83, 0.85]`).
- 1D `q=4`: critical `c = 1`; `q ≥ 5` (1D): first-order transition (no continuous critical point) — Wu RMP 1982.
- Limit checks: `h = 0` → `q`-fold-degenerate FM, `E/N = −2`; `h → ∞` → PM, `E/N = −2h`; `q = 2` → recovers TFIM.

## Diagnose

Infer the canonical setup from the user's prompt and propose it for ratification.

**Canonical defaults:** 1D chain, `q = 3` (Clock = 3-state Potts), ferromagnetic, `h` on the user's prompt (default critical point `h_c = 1`), PBC ring (preferred for criticality work; OBC available), target `E/N` and the `Z_q` order parameter across an `h`-scan. Local Hilbert dimension `d = q`.

**Proposal pattern:** "Going with: 1D chain, `q = 3` Clock (= 3-state Potts), `h`-scan around `h_c = 1`, PBC ring, `L = 32`, target `E/N` and the `Z_q` order parameter. Override any, or pick: different `q` (e.g., `q = 4`), 2D square, full criticality scan."

Build per `.knowledge/conventions.md` (default sign / coupling). The Hamiltonian is

```
H = − Σ_{⟨ij⟩} (X_i X_j^† + X_i^† X_j) − h Σ_i (Z_i + Z_i^†)
```

with `X, Z` the qudit shift / clock operators (`X|k⟩ = |k+1 mod q⟩`, `Z|k⟩ = ω_q^k |k⟩`, `ω_q = e^{2πi/q}`).

## Workflow

1. Set up sites with local dimension `d = q`; pin sector via `Z_q` quantum number (the symmetry generator is `Π_i Z_i`; conserve where the stack supports it).
2. Pick method per the table.
3. Short first run; verify the `Z_q` sector and the parity / clock symmetry expected from the input.
4. Sweep convergence parameter (bond dim or basis size) until the target observable stabilizes.
5. Verify (next section).
6. If the target is criticality, hand off to `criticality`.

## Method recommendations

| Regime | Method | Card |
|---|---|---|
| 1D chain, any `q`, ground-state energy + standard observables | DMRG (qudit MPS) | `skills/method-mps/SKILL.md` |
| Tiny cluster (`N ≲ 16` for `q = 3`), exact spectrum | ED | `skills/method-ed/SKILL.md` |
| 2D square (small clusters / cylinders) | DMRG cylinder | `skills/method-mps/SKILL.md` |
| Imaginary-time route to ground state | TEBD | `skills/method-mps/SKILL.md` |

## Branch table

| Condition | Action |
|---|---|
| `q = 2` | Switch to `transverse-field-ising` — same physics, simpler stack. |
| Question is about the FM/PM critical point (universality class, exponents) | Run the calculation here, then call `criticality`. The 1D `q = 3` critical point is `Z_3` parafermion CFT, `c = 4/5`, `ν_Potts = 5/6` (limit anchor). |
| 2D square, large `q`, exotic phase content | Beyond current scope for systematic ground-state work; surface uncertainty. |
| Lattice is non-square (triangular Potts, etc.) | Stay here; flag that the universality class differs from the 1D Clock case. Call `frustration` if relevant. |

## Verification

Default checks (all auto-run; results aggregated into the report's verification line):

- **Limit checks** via `.knowledge/limits.md` and analytic limits of the Clock Hamiltonian: `h = 0` ⇒ `q`-fold-degenerate ferromagnetic ground state with `E/N = −2` (sum over both `(X X† + X† X)` directions); `h → ∞` ⇒ paramagnetic, `E/N = −2 h` (clock-aligned along the field direction); `q = 2` ⇒ recovers TFIM exactly.
- **Symmetry**: `Z_q` symmetry (`Π_i Z_i`) respected; ground state in the trivial sector for finite `L` with no symmetry-breaking field.
- **Convergence**: bond-dim or basis-size sweep gives a monotonic, asymptoting energy curve. Auto-saved convergence plot per AGENTS.md output norm.
- **Internal consistency**: energy variance small relative to `E²`.
- **Cross-method validation (auto-paired when available)** — use DMRG / TTN cross-checks first. Use an ED cross-check via `/method-ed`.

Optional check:

- For `q = 3` 1D Clock at `h_c = 1`: the critical exponent `ν_Potts = 5/6` from the `Z_3` parafermion CFT is the limit anchor. When extracting `ν` from a finite-size collapse, compare to the analytic value, not to a numerical extrapolation. Per AGENTS.md verification rule §6, compare against the literature *range* (`ν ∈ [0.83, 0.85]`), which brackets the analytic value.

## Frontier flag

`q ≥ 5` quantum Potts models in 1D have a first-order transition rather than a continuous one; the framing is different from the canonical `q ∈ {2, 3, 4}` continuous-transition story. State the regime explicitly and route to `criticality` for the order-of-transition diagnostic.

## Branch table (diagnostics)

| Diagnostic | Action |
|---|---|
| `criticality` | Standard finite-size scaling on the order parameter or gap. The 1D `q = 3` critical point is `c = 4/5` parafermion CFT. |
| `confinement` | Not the canonical framing for Potts/Clock at the FM/PM transition (no gauge interpretation); skip unless the user is in an extended-coupling regime that genuinely raises a confinement question. |

## Writeup handoff

After verification, if the user wants to communicate the result, consolidate to a runnable script + short run report, then render it via `/report`. See AGENTS.md "Writeup handoff".

## Related skills

`transverse-field-ising` (`q = 2` reduction), `criticality` (parafermion CFT scaling).
