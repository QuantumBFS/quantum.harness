# Heisenberg

Solve Heisenberg-spin ground-state problems. Lattice geometry and coupling regime determine which method works.

## Physics card

### Hamiltonian

$$ H = J \sum_{\langle ij\rangle} \mathbf{S}_i\cdot\mathbf{S}_j $$

Conventions: `S`-operator normalization (`S^a = σ^a/2` for S=1/2), `⟨ij⟩` = nearest-neighbor bonds counted once, `J > 0` antiferromagnetic (AFM), `J < 0` ferromagnetic (FM); largest coupling set to `J = 1`. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 1D chain / quasi-1D ladder / 2D square (`Z=4`), triangular, kagome / 3D | Geometry is the master axis: it sets entanglement scaling and frustration. |
| A2 boundary conditions | OBC (DMRG default) · PBC (ED/QMC) · cylinder (2D DMRG) | Cylinder width caps the 2D-DMRG bond-dim budget. |
| A3 statistics & local dim | spin-S; `d = 2S+1` (`d=2` for S=1/2) | Maps to hard-core bosons via Matsubara–Matsuda; no statistics sign by itself. |
| A4 interaction range | short-range (nearest-neighbor) | Local — area-law-compatible. |
| B5 entanglement scaling | 1D gapless: area+log, `S=(c/3)log ℓ`, `c=1` · 2D ordered: area law (`∝ L`) | 1D AFM chain is critical (`c=1`); 2D Néel state obeys area law. |
| B6 spectral gap | 1D S=1/2 AFM: gapless (power-law correlations) · 2D square AFM: gapless Goldstone magnons over ordered GS | Half-integer 1D chain gapless (LSM); 2D has long-range order + gapless spin waves. |
| B7 ground-state order | 1D S=1/2: quasi-long-range (no SSB, Mermin–Wagner) · 2D square/3D: Néel SSB · frustrated 2D: candidate spin liquid / VBS | Bipartite unfrustrated lattices order (2D/3D); 1D and frustrated cases do not. |
| B8 frustration | none on bipartite (chain, square, cubic) · geometric on triangular/kagome/pyrochlore | Frustration is what turns on the QMC sign problem for spins. |
| C9 global symmetry | SU(2) (total `S`), U(1) (`S^z_tot`) | Full SU(2) at the isotropic point; a field breaks SU(2)→U(1). |
| C10 spatial symmetry | translation (`k`), point group (`D_4` square, `D_6` triangular) | Block-diagonalizes ED sectors. |
| C11 integrability | 1D S=1/2 chain: Bethe-ansatz integrable · 2D / S≥1 / frustrated: non-integrable | Exact 1D thermodynamics via TBA; everything else numerical. |
| C12 sign problem | sign-free on bipartite (Marshall rule) · sign-ful on frustrated lattices | Unfrustrated → exact QMC at scale; frustrated → QMC blocked. |
| D13 regime | ground state (`T=0`) default; finite-T and dynamics out of card scope | GS energy / order parameter are the canonical targets. |
| D14 filling / doping | N/A (spin model, no charge) | Doping appears only after fermionization (t-J / Hubbard). |
| D15 disorder | clean (translation-invariant) by default | Bond/site disorder → random-singlet physics (out of scope). |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- 1D S=1/2 AFM chain : quasi-long-range order, no SSB; spin–spin correlations decay as a power law `⟨S_0·S_r⟩ ∼ (-1)^r / r` (log corrections).
- 2D square / 3D AFM : Néel order; staggered (sublattice) magnetization `m_s` and structure-factor peak `S(π,π)`.
- Frustrated (triangular/kagome) : 120° order (triangular) or candidate spin liquid / VBS (kagome) — diagnose via `spin-liquid`.

### Canonical observables

- Ground-state energy per site `E/N`.
- Staggered magnetization `m_s` / sublattice magnetization (order parameter).
- Static structure factor `S(q)`, peaked at the ordering wavevector.
- Spin–spin correlation function `⟨S_i·S_j⟩`; central charge `c` (1D, from entanglement scaling).

### Recommended methods

- Primary: **DMRG/MPS** for 1D chains, ladders, and 2D cylinders — near-exact in 1D area-law/area+log regimes; SU(2)/U(1) quantum-number conservation cuts cost (per `method-property-map.md` §MPS).
- Primary (unfrustrated 2D/3D, large `N`): **sign-free QMC** (SSE) — bipartite Marshall sign rule makes it exact at scale (§QMC, C12).
- Cross-check: **ED** on small clusters (exact spectrum, oracle); **VMC/NQS** for frustrated 2D where QMC is sign-blocked.

### Key reference

[@manousakis_1991_spin] — the authoritative review of the spin-½ square-lattice Heisenberg antiferromagnet (spin-wave, Schwinger boson, series, QMC, ED) and its connection to the cuprate parents.
Rendered: `./10-1103-revmodphys-63-1.md` _(bib stub — no PDF reachable; RMP 1991 paywalled, predates arXiv)_.

### Benchmarks

- 1D S=1/2 AFM chain (PBC, thermodynamic limit): `E/N = 1/4 − ln 2 ≈ −0.443147` — exact Bethe ansatz (Hulthén 1938; convention `H = J Σ S_i·S_j`, `J=1`).
- 2D square S=1/2 AFM: `E/N ≈ −0.6694` (high-precision `−0.669441857(7)`), staggered magnetization `m_s ≈ 0.3074` — QMC/SSE (Sandvik, Phys. Rev. B 56, 11678 (1997)).

## Diagnose

Infer the canonical setup from the user's prompt and propose it for ratification. Do not ask 8 questions.

**Canonical defaults:** S=1/2, isotropic NN, antiferromagnetic (J > 0), OBC, target E/N. Lattice and system size inferred from the prompt — if only "Heisenberg" is given, default to 1D chain N=20.

**Proposal pattern:** "Going with: 1D chain, S=1/2, J=1 AFM, OBC, N=20, target E/N. Override any, or pick a variant: square lattice (4×4 pending ED), triangular cylinder (Ly=4), kagome cylinder (Ly=4)."

Only surface a real choice when the prompt is genuinely ambiguous about the lattice family. Build the Hamiltonian per `.knowledge/conventions.md`.

## Workflow

1. Set up sites and Hamiltonian per conventions; pin sector via conservation laws (see `.knowledge/symmetry-cheatsheet.md`).
2. Pick method per the table below.
3. Run a short, conservative first calculation; verify it ran cleanly and respected conservation laws.
4. Sweep the convergence parameter (bond dim for DMRG, basis size for ED) until the target observable stops moving within the accuracy goal.
5. Verify (next section).
6. If the problem branches into a more specific physics question, hand off via the branch table.

## Method recommendations

| Regime | Method | Card |
|---|---|---|
| 1D chain (any N), quasi-1D ladder | DMRG | `skills/method-mps/SKILL.md` |
| Small cluster (N ≲ 24 sites), exact spectrum, debugging | ED | `skills/method-ed/SKILL.md` |
| Cylinder (square / triangular / kagome strips, `L_y` small) | DMRG | `skills/method-mps/SKILL.md` |
| Imaginary-time route to ground state, gap probes | TEBD | `skills/method-mps/SKILL.md` |
| Frustrated 2D variational (VMC / NQS) | Compare ansatz energies on kagome / triangular. Requires `make install netket`. | `skills/method-vmc/SKILL.md` |
| Frustrated 2D thermodynamic limit | Beyond current scope for exact methods; surface uncertainty. VMC + DMRG cylinder can constrain. | — |

## Branch table

| Condition | Action |
|---|---|
| Lattice is triangular, kagome, or pyrochlore (frustrated) | Continue here for setup; if the question is about absence of order or topology, also call `spin-liquid`; if about the source of frustration, call `frustration`. |
| User asks about NN + NNN couplings | Switch to `j1-j2`. |
| Question is about quantum critical behavior (e.g., XXZ at Δ=1, dimerization) | Call `criticality` after the calculation. |
| User wants `S = 1` chain with single-ion anisotropy | Switch to `spin-1-xxz`. |
| User wants doped, fermionic correlated physics | Switch to `t-j` or `hubbard`. |
| User asks about `S(q,ω)` or dynamics | Out of current scope. |
| User asks about finite-T (susceptibility, specific heat) | Out of current scope. |

## Verification

Default checks (all auto-run; results aggregated into the report's verification line):

- **Limit checks** — confirm sign convention and trivial limits via `.knowledge/limits.md`. Examples: at `Δ = 1` XXZ reduces to isotropic Heisenberg; ferromagnetic ground state is fully polarized; `J = 0` gives uncoupled spins.
- **Symmetry** — total `S^z` conservation; expected ground-state sector (singlet for finite AFM); lattice point group respected (see `.knowledge/symmetry-cheatsheet.md`).
- **Convergence** — bond-dim or basis-size sweep produces a monotonic, asymptoting curve. Report the curve, not just the final value.
- **Internal consistency** — energy variance is small relative to `E²` at the reported accuracy.
- **Cross-method validation (auto-paired when available)** — use TEBD or another active independent route. Use an ED cross-check via `/method-ed`.

Optional check (when a published reference exists):

- Compare against published literature for the lattice / coupling combination. Report the discrepancy honestly. If the published value is a *range* (e.g., kagome), report whether your value is consistent with the range, not whether it "matches."

If no benchmark exists for the user's specific problem (which is common for non-canonical sizes / parameters), report the converged value with bond-dim trend, variance, and the satisfied limit + symmetry checks. Do not claim a "match" without a reference.

## Writeup handoff

After verification, if the user wants to communicate the result, consolidate to a runnable script + short run report, then render it via `/report`. See AGENTS.md "Writeup handoff".

## Related skills

`frustration`, `spin-liquid`, `criticality`, `j1-j2`.
