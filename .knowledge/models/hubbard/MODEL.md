# Hubbard

Solve Hubbard ground-state problems as correlated-electron tasks. Doping, extended terms (`t'`, `V`), lattice, and DMFT-style embedding are all workflow choices inside this problem — not separate skills.

## Physics card

### Hamiltonian

$$ H = -t \sum_{\langle ij\rangle,\sigma} \left( c^\dagger_{i\sigma} c_{j\sigma} + \text{h.c.} \right) + U \sum_i n_{i\uparrow} n_{i\downarrow} - \mu \sum_i n_i $$

Conventions: `t > 0` standard hopping (energy unit `t = 1`), `U > 0` on-site repulsion (`U < 0` attractive), `⟨ij⟩` = nearest-neighbor bonds counted once. Half-filling sits at `μ = U/2`; the particle-hole-symmetric form subtracts `(U/2)Σ n_i`. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 1D chain / quasi-1D ladder / 2D square (`Z=4`), triangular / 3D cubic / `Z→∞` (DMFT) | Geometry sets the difficulty; 2D square is the cuprate-parent target. |
| A2 boundary conditions | OBC (DMRG) · PBC (ED/QMC) · cylinder (2D DMRG) · infinite (iDMRG/DMFT) | Cylinder width caps the 2D-DMRG bond-dim budget. |
| A3 statistics & local dim | fermion; `d = 4` per site (∅, ↑, ↓, ↑↓) | The four-state local space sets the ED `4^N` wall and MPS per-site cost. |
| A4 interaction range | short-range: on-site `U` + NN hopping (extended Hubbard adds NN `V`, `t'`) | Local — area-law-compatible. |
| B5 entanglement scaling | 1D: area+log near criticality (`c=1` charge + `c=1` spin off half-filling; Mott-gapped charge at half-filling) · 2D: area law | Spin-charge separation gives two gapless modes in the 1D metal. |
| B6 spectral gap | half-filling: Mott charge gap for any `U>0` in 1D, for `U≳U_c` in 2D (gapless spin) · doped: gapless (metal) | 1D Mott gap opens at infinitesimal `U` (Lieb–Wu); spin sector stays gapless. |
| B7 ground-state order | half-filled bipartite: AF Mott insulator (Néel SSB in 2D/3D) · doped 2D: stripes / d-wave SC candidate / pseudogap | Doped 2D ground state is the central open problem; stripes vs uniform SC nearly degenerate. |
| B8 frustration | none on bipartite (chain, square, cubic) · geometric on triangular/`t'≠0` · fermionic sign always present | Fermionic antisymmetry is the intrinsic frustration. |
| C9 global symmetry | U(1)_charge × SU(2)_spin (`N↑`, `N↓` separately conserved; `S^z`) · half-filled bipartite: SO(4) = spin SU(2) × η-pairing SU(2) | SO(4) (Yang–Zhang) adds pseudospin/η-pairing at half-filling on bipartite lattices. |
| C10 spatial symmetry | translation (`k`), point group (`D_4` square), inversion | Block-diagonalizes ED sectors. |
| C11 integrability | 1D: Bethe-ansatz integrable (Lieb–Wu) · 2D / 3D: non-integrable | 1D has exact spectrum and thermodynamics (TBA); higher D fully numerical. |
| C12 sign problem | half-filled bipartite: sign-free in DQMC (particle-hole) · attractive `U<0`: sign-free at any filling · doped repulsive: severe sign problem | Sign-free at half-filling is what makes that regime numerically exact at scale. |
| D13 regime | ground state (`T=0`) default; finite-T (DQMC/DMFT) and dynamics out of card scope | `E/N` + double occupancy are canonical GS targets. |
| D14 filling / doping | half-filling (Mott) is the symmetric reference; doping is the key axis (turns on sign problem, opens competing orders) | Mott→doped is the decisive control parameter. |
| D15 disorder | clean by default; disorder → Anderson–Hubbard / MIT (out of scope) | — |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- Half-filled bipartite (2D/3D) : antiferromagnetic Mott insulator — staggered magnetization `m_s`, spin structure-factor peak `S(π,π)`, charge (Mott) gap `Δ_c`.
- 1D at half-filling : Mott insulator, no SSB (Mermin–Wagner); power-law spin correlations, gapped charge sector.
- Doped 2D : competing stripe order (charge/spin density modulation), `d_{x²−y²}` superconducting pairing, pseudogap — diagnose via pair-field and charge/spin structure factors.

### Canonical observables

- Ground-state energy per site `E/N`; double occupancy `⟨n↑ n↓⟩`.
- Staggered magnetization `m_s`, spin structure factor `S(q)`; charge gap `Δ_c`.
- `d`-wave pair correlations and charge/spin stripe order parameters (doped 2D).
- Momentum distribution `n(k)`; central charge `c` (1D, entanglement scaling).

### Recommended methods

- Primary (1D / ladder / cylinder): **DMRG/MPS** — near-exact in 1D, U(1)×SU(2) quantum-number conservation cuts cost (per `method-property-map.md` §MPS).
- Primary (half-filled bipartite, large `N`): **sign-free DQMC/AFQMC** — particle-hole symmetry makes it numerically exact at scale (§QMC, C12).
- Doped 2D (sign-blocked): **DMRG cylinders + AFQMC (constrained-path/phaseless) + VMC/NQS + iPEPS**, cross-checked (§B8/C12); **ED** as small-cluster oracle; **DMFT** for local self-energy / Mott transition.

### Key reference

[@qin_2021_hubbard] — the authoritative multi-method computational review of the Hubbard model (DMRG, AFQMC, DMFT/DCA, tensor networks) covering half-filling and the doped 2D problem, with cross-method consensus benchmarks.
Rendered: `./2104.00064_the-hubbard-model-a-computational-perspective.md`.

### Benchmarks

- 1D chain, half-filling, thermodynamic limit (`U/t=4`): exact ground-state energy per site `E/N ≈ −0.5737 t` from the Lieb–Wu integral equations (Lieb & Wu, Phys. Rev. Lett. 20, 1445 (1968); convention `H = -tΣc†c + UΣn↑n↓`). At `U→∞` half-filling, `E/N → 4 ln 2 · (−t²/U)` (Heisenberg AFM, `J=4t²/U`).
- 2D square, `U/t=8`, `δ=1/8` doping (`t'=0`): ground state is a period-8 stripe with `E/N = −0.767 ± 0.004 t` — four-method agreement (DMRG, AFQMC, iPEPS, DMET), reported in the Qin review [@qin_2021_hubbard] from the Simons-collaboration benchmark (Zheng et al., Science 358, 1155 (2017)).

## Diagnose

Infer setup from the user's prompt and propose for ratification.

**Canonical defaults:** 1D chain, half-filling (N↑=N↓=N/2), U/t from the user's prompt (if not given, default U/t=4 — moderate correlation), NN hopping only, OBC, N=20, target E/N + double occupancy.

**Proposal pattern:** "Going with: 1D chain, half-filled, U/t=[value], NN hopping, OBC, N=20, target E/N + ⟨n↑n↓⟩. Override any, or pick: 2D square cylinder (Ly=4), doped system (specify filling), extended Hubbard (t', V terms)."

Build per `.knowledge/conventions.md`: `H = -t Σ (c†c + h.c.) + U Σ n↑n↓`.

## Workflow

1. Set up sites with `(N↑, N↓)` conservation; choose initial state in target sector.
2. Pick method per the table.
3. First short run; verify particle/spin numbers, particle-hole at half-filling, fermionic signs.
4. Sweep convergence parameter; track observable.
5. Verify (next section).
6. If the question becomes a Mott / large-U / multi-orbital question, hand off.

## Method recommendations

| Regime | Method | Card |
|---|---|---|
| Small cluster (N ≲ 16 sites) | ED | `skills/method-ed/SKILL.md` |
| 1D chain, ladder, narrow cylinder | DMRG | `skills/method-mps/SKILL.md` |
| Imaginary-time route to ground state | TEBD | `skills/method-mps/SKILL.md` |
| Half-filled bipartite at moderate `U` | AFQMC may be sign-free; recommend only after checking. | — |
| Frustrated / doped 2D variational (VMC / NQS) | Compare ansatz energies. Requires `make install netket`. | `skills/method-vmc/SKILL.md` |
| Local self-energy / Mott transition framing | DMFT — out of current scope unless an install target lands; surface explicitly. | — |

## Branch table

| Condition | Action |
|---|---|
| `U/t ≫ 1` and finite hole density | Switch to `t-j` (faithful large-U reduction with `J = 4t²/U`). |
| Question is about Mott localization, double occupancy, charge gap | Call `mott-transition`. |
| Multiple orbitals or Hund's coupling | Switch to `multiorbital-hubbard`. |
| Question is about quantum critical behavior (e.g., Mott QCP) | Call `criticality` after the calculation. |
| Frustrated lattice (triangular Hubbard, etc.) | Call `frustration`. |

## Verification

Default checks:

- **Limit checks** via `.knowledge/limits.md`: `U = 0` → free fermions on lattice (compute analytically); `U → ∞` half-filled bipartite → Heisenberg AFM with `J = 4t²/U`; atomic limit `t = 0` → trivial occupation.
- **Symmetry**: `(N↑, N↓)` conservation; SU(2) for `H_Hubbard` with no field; particle-hole symmetry at half-filling on bipartite lattices.
- **Convergence**: bond-dim sweep + cylinder-width when 2D.
- **Internal consistency**: variance, double-occupancy trend (decreases with `U/t`), spin-spin correlations build up at large `U`.
- **Cross-method validation** (when feasible) — check the U→∞ Heisenberg mapping at large U/t; use an ED cross-check via `/method-ed`. See AGENTS.md "Verification practice".

Optional check:

- 1D chain at half-filling: compare to Lieb-Wu integral equations. For 2D, the field is contested at intermediate `U` and finite doping — report values with their convergence trend rather than claiming a benchmark.

## Writeup handoff

After verification, if the user wants to communicate the result, consolidate to a runnable script + short run report, then render it via `/report`. See AGENTS.md "Writeup handoff".

## Related skills

`mott-transition`, `t-j`, `multiorbital-hubbard`, `frustration`, `criticality`.
