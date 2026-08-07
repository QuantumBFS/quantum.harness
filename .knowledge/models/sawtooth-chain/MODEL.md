# Sawtooth chain

Solve the spin-1/2 sawtooth (delta) chain — a frustrated chain of corner-sharing triangles that is *exactly* solvable at high field through localized-magnon physics at the flat-band point `J2 = 2 J1`: magnetization jump, `m = M_sat/2` plateau, and residual entropy.
Exact solution: see `.knowledge/solvable/sawtooth-localized-magnon/` (oracle card).

## Physics card

### Hamiltonian

$$ H = \sum_i \left[\, J_1\,\mathbf{S}_{A_i}\!\cdot\!\mathbf{S}_{A_{i+1}} + J_2\,(\mathbf{S}_{A_i}\!\cdot\!\mathbf{S}_{B_i} + \mathbf{S}_{B_i}\!\cdot\!\mathbf{S}_{A_{i+1}})\,\right] - h \sum_i S^z_i $$

Conventions: spin-1/2 `S`-operators (`d=2`); `N = 2N_c` sites, base `A_i` = site `2i`, apex `B_i` = site `2i+1` (0-based), PBC. `J1` is the base-chain exchange, `J2` the apex–base exchange; both antiferromagnetic (`>0`), `J1 = 1` sets the unit. Control parameter: the ratio `J2/J1` (flat-band point at `2`, Monti–Sütő point at `1` — distinct, do not conflate). See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 1D, corner-sharing triangles (base chain + apex sites), `Z = 4` | The triangle geometry is what makes magnons localizable. |
| A2 boundary conditions | PBC (ED default) | Localized-magnon counting assumes the ring. |
| A3 statistics & local dim | spin-1/2; `d = 2` | — |
| A4 interaction range | short-range (base NN `J1`, apex–base `J2`) | Local. |
| B5 entanglement scaling | localized-magnon states: product-like at the flat-band point | Flat-band eigenstates are single-cell objects. |
| B6 spectral gap | one-magnon band exactly flat at `J2 = 2 J1` (zero dispersion) | Flatness is exact, not small. |
| B7 ground-state order | `h = 0`: spin-liquid-like, no simple order; `h = h_sat`: localized-magnon crystal (`m = M_sat/2` plateau) | The plateau state is an exact magnon crystal at the flat-band point. |
| B8 frustration | strong geometric frustration (triangles) | Frustration enables destructive interference → flat band. |
| C9 global symmetry | SU(2) (total spin); field breaks to U(1) | `S^z_tot` sectors are the workhorse basis. |
| C10 spatial symmetry | translation (one cell), reflection | Localized magnons break translation spontaneously at the plateau. |
| C11 integrability | not integrable, but **exact eigenstates at `J2 = 2 J1`** (localized magnons) and an exact two-fold GS at `J2 = J1` (Monti–Sütő) | Tier-C solvability: special points only — see solvable card. |
| C12 sign problem | sign-ful (frustration) → QMC blocked; ED/DMRG carry it | Frustration turns on the sign problem. |
| D13 regime | ground state + magnetization process in a field; finite-T (magnetocaloric effect) | The MCE near `h_sat` is the materials connection. |
| D14 filling / doping | N/A (spin model; `m/m_sat` is the field-tuned analog) | — |
| D15 disorder | clean by default | — |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- `m = M_sat/2` plateau (localized-magnon crystal): at `J2 = 2 J1` an exact product of independent cell magnons; width `W(J2/J1)` shrinks linearly as the flat band is detuned (reconnaissance ED, N≤16).
- Saturation (`m = M_sat`): reached via a **macroscopic jump** `ΔM = M_sat/2` at `h_sat = 4 J1` exactly at the flat-band point; the jump smears into a staircase for `J2 ≠ 2 J1` with width Γ set by the detuned one-magnon bandwidth.
- Zero-field GS: featureless spin-liquid-like; at `J2 = J1` the exact Monti–Sütő two-fold valence-bond state.

### Canonical observables

- Ground-state energy per sector `E(S^z_tot)`; magnetization curve `m(h)` with plateau width `W` and jump height `ΔM`.
- Ground-state degeneracy at `h_sat` (exact integer, Lucas numbers); residual entropy `S/N`.
- One-magnon dispersion (flatness); finite-T isothermal entropy peak and magnetocaloric cooling rate near `h_sat`.

### Recommended methods

- Primary: **ED** in `S^z_tot` sectors — the exact anchors are sector-resolved, and N ≤ 20 covers all of them (see `skills/method-ed/SKILL.md`, `skills/using-xdiag/SKILL.md`).
- Cross-check: the **solvable oracle** (`.knowledge/solvable/sawtooth-localized-magnon/`) — flat band, Lucas degeneracy, jump; DMRG for larger-N erosion curves; FTLM for the finite-T magnetocaloric axis.

### Key reference

[@Schulenburg2002] — Schulenburg–Honecker–Schnack–Richter–Schmidt, the foundational localized-magnon paper (flat-band condition, macroscopic jump, exact eigenstates). `bib stub — no PDF reachable (2026-07-28)`; review [@Derzhko2015].

### Benchmarks

- Flat-band one-magnon energy `ε = −4 J1` at `J2 = 2 J1` — exact; verified by ED + XDiag (Harness anchor, solvable card).
- Saturation field `h_sat = 4 J1`; jump `ΔM = M_sat/2` — exact (Harness anchor).
- Degeneracy at `h_sat` = Lucas(N_c) (`N=12 → 18`); `S/N = (1/2) ln φ ≈ 0.2406 k_B` — exact (Harness anchor).
- Erosion reconnaissance (N=12–16 ED): `W(δ)` peaks at δ=0 and falls ~linearly; `ΔM` is full only at δ=0; `Γ(δ)` tracks the one-magnon bandwidth (Harness anchor, `tracks/agent-kb/solutions/problem-factory/briefs/sawtooth-erosion-001.md`).

## How it is studied / Operational

**Canonical defaults (Diagnose):** spin-1/2, AFM `J1 = 1`, ratio `J2/J1` from the prompt (default the flat-band point `2`), PBC, `S^z_tot` sectors enumerated from polarization (`n_up = N − k`, `k = 0…N/2`), target `m(h)` + the exact anchors. If only "sawtooth" is given, propose the anchor battery at `J2 = 2 J1` (flat band, jump, degeneracy, entropy) and a detuning sweep `δ = J2/J1 − 2` for the erosion curves.

| Regime | Method | Card |
|---|---|---|
| Anchor battery (flat band, jump, Lucas degeneracy) | ED per `S^z_tot` sector, N ≤ 20 | `skills/method-ed/SKILL.md` |
| Erosion curves `W(δ), Γ(δ)` at larger N | ED → DMRG | `skills/method-ed/SKILL.md`, `skills/method-mps/SKILL.md` |
| Finite-T magnetocaloric effect | full-spectrum ED (N ≤ 20) / FTLM | `skills/method-ed/SKILL.md` |
| Exact checks at any step | solvable oracle | `.knowledge/solvable/sawtooth-localized-magnon/` |

Verification pointers:

- The `h_sat` degeneracy is an **exact integer** (Lucas(N_c)) — off by one is a bug, not a discrepancy.
- `J2/J1 = 1` (Monti–Sütő) and `2` (flat band) are different special points; conflating them is a known trap.
- Convention trap: energies off by ~4× mean Pauli-vs-spin mix-up; a flat band at `−2 J1` means a `J2` bond was double-counted.
- `S^z_tot` conservation always; at the flat-band point additionally verify the one-magnon band is flat to solver precision before trusting any detuning sweep.
