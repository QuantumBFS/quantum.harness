# t-J

Solve t-J ground-state problems. The no-double-occupancy projection makes the local Hilbert space three-dimensional (empty / up / down) and changes both diagnostics and method choice relative to Hubbard.

## Physics card

### Hamiltonian

$$ H = -t \sum_{\langle ij\rangle,\sigma} P \left( c^\dagger_{i\sigma} c_{j\sigma} + \text{h.c.} \right) P + J \sum_{\langle ij\rangle} \left( \mathbf{S}_i \cdot \mathbf{S}_j - \tfrac{1}{4} n_i n_j \right) $$

Conventions: `t > 0` (energy unit `t = 1`), `J > 0` antiferromagnetic; `P` projects out doubly-occupied sites (the local space is `{∅, ↑, ↓}`). Derived from the large-`U` Hubbard model by a Schrieffer–Wolff transformation, giving `J = 4t²/U`; the `-n_i n_j/4` term is the canonical form (often dropped in "pure t-J"). Three-site hopping terms (same `O(t²/U)`) are usually omitted unless requested. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 1D chain / quasi-1D ladder / 2D square (`Z=4`); triangular when frustrated | 2D square doped is the cuprate-physics target. |
| A2 boundary conditions | OBC (DMRG) · PBC (ED) · cylinder (2D DMRG) | Cylinder width caps the 2D-DMRG budget; stripes need long cylinders. |
| A3 statistics & local dim | fermion; `d = 3` per site (∅, ↑, ↓) — no double occupancy | The no-double-occupancy constraint is a **Hilbert-space restriction, not a symmetry**; `d=3` (not 4) is the projected local space. |
| A4 interaction range | short-range: NN hopping + NN exchange `J` (extended t-J adds `t'`, `J'`) | Local — area-law compatible. |
| B5 entanglement scaling | 1D: area+log (gapless Luttinger liquid; `c=1` charge + `c=1` spin) · 2D: area law | Doped 1D t-J is a Luttinger liquid with spin-charge separation. |
| B6 spectral gap | doped: gapless · zero doping: reduces to Heisenberg (gapless 1D / 2D AFM) | At half-filling (`n=1`) kinetic term is fully projected → pure Heisenberg. |
| B7 ground-state order | 2D large-`J/t`: `d_{x²-y²}` superconductivity / stripes / phase separation · doped: Luttinger liquid (1D) · half-filled: AFM | Phase separation at large `J/t`; stripe vs uniform d-SC near degenerate in the cuprate window. |
| B8 frustration | none on bipartite lattices · geometric on triangular · fermionic sign on doping | Fermionic antisymmetry under doping is the intrinsic frustration. |
| C9 global symmetry | U(1)_charge × SU(2)_spin (`N↑`, `N↓` conserved; `S^z`) | At the supersymmetric point `J=2t`, an enlarged `su(2|1)` superalgebra appears (1D). |
| C10 spatial symmetry | translation (`k`), point group (`D_4` square), inversion | Block-diagonalizes ED sectors. |
| C11 integrability | 1D **supersymmetric integrable point at `J = 2t`** (Bethe ansatz, Sutherland/Schlottmann); otherwise non-integrable | `J=2t` gives an exact spectrum/thermodynamics benchmark; generic `J/t` is fully numerical. |
| C12 sign problem | half-filling (`n=1`, → Heisenberg, bipartite): sign-free · doped: severe sign problem | Doping turns on the fermion sign — QMC is blocked away from the Heisenberg limit. |
| D13 regime | ground state (`T=0`) default; finite-T / dynamics out of card scope | `E/N` + spin/charge correlations are the canonical targets. |
| D14 filling / doping | doping `δ = 1-n` is the central axis; `n=1` (half-filling) → Heisenberg | Doping breaks particle-hole symmetry and drives SC/stripe competition. |
| D15 disorder | clean by default | — |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- Half-filling (`n=1`) : antiferromagnet (the kinetic term is projected away → Heisenberg) — staggered magnetization, `S(π,π)` (2D) or power-law spin correlations (1D).
- Doped 1D : Luttinger liquid — power-law `K_ρ`-controlled correlations, spin-charge separation; check exponents.
- Doped 2D, large `J/t` : `d_{x²-y²}` pairing (pair-field correlations), stripe order (charge/spin density modulation), and phase separation at large `J/t` (`J/t ≳ 3` per Emery–Kivelson–Lin) — diagnose via density profile and pair/charge structure factors.

### Canonical observables

- Ground-state energy per site `E/N`; hole density `δ`.
- Spin correlations `⟨S_i·S_j⟩`, spin structure factor `S(q)`; charge/density correlations `N(q)`.
- `d`-wave pair-field correlations (2D doped); single-hole dispersion / quasiparticle weight.
- Luttinger exponent `K_ρ`, central charge `c` (1D entanglement scaling).

### Recommended methods

- Primary (1D / ladder / cylinder): **DMRG/MPS** — near-exact in 1D, the `d=3` projected local space + U(1)×SU(2) conservation keep cost low (per `method-property-map.md` §MPS).
- Primary (small clusters): **projected ED** — exact oracle on the no-double-occupancy basis (§ED).
- Doped 2D (sign-blocked): **DMRG cylinders + VMC/NQS** cross-checked (§B8/C12) for stripes vs pairing; QMC blocked by the doping sign problem.

### Key reference

[@dagotto_1993_correlated] — the authoritative review of computational studies of the t-J and Hubbard models for the cuprates (d-wave SC, phase separation, spin correlations vs doping, photoemission), the standard reference for what numerics established about correlated electrons in high-`T_c` materials.
Rendered: bib stub — no PDF reachable.

### Benchmarks

- 1D supersymmetric point `J = 2t` at half-filling: exactly solvable (Bethe ansatz) with ground-state energy per site `E/N = -2t·ln 2 + ... ` reducing to the Heisenberg value at `n=1` — the canonical integrable benchmark (Sutherland, Phys. Rev. B 12, 3795 (1975); Schlottmann, Phys. Rev. B 36, 5177 (1987)).
- 2D t-J, phase separation: the doped system phase-separates into hole-rich and AFM regions for `J/t ≳ 3` (and at all `J/t` near half-filling), established by ED/numerics (Emery, Kivelson & Lin, PRL 64, 475 (1990)); the small-`J/t` cuprate window (`J/t ≈ 0.3-0.4`) hosts the contested stripe-vs-uniform-d-SC competition reviewed in [@dagotto_1993_correlated].

## Diagnose

Infer setup from the user's prompt and propose for ratification.

**Canonical defaults:** 1D chain, J/t=0.4 (corresponds to Hubbard U/t=10), filling from the user's prompt (if not given, default n=0.875 — 12.5% doping), OBC, N=20, target E/N + spin-charge correlations. No three-site terms unless specifically requested.

**Proposal pattern:** "Going with: 1D chain, J/t=[value], n=[filling], OBC, N=20, no-double-occupancy projected, target E/N + spin-charge correlations. Override any, or pick: 2D square cylinder (Ly=4), comparison to Hubbard at large U, zero-doping limit (→ Heisenberg)."

Build per `.knowledge/conventions.md`: `H = -t P(c†c+h.c.)P + J Σ(S·S - nn/4)`.

## Workflow

1. Set up sites with `("Electron"; conserve_qns=true)` in ITensors (or equivalent), pinned to the target `(N↑, N↓)`. Verify that double occupancy is excluded by the construction.
2. Pick method per the table.
3. First short run; verify projection, particle counts, fermionic signs.
4. Sweep convergence parameter; track observable.
5. Verify (next section).
6. If the user is comparing to Hubbard or asking about Mott / large-U emergence, hand off.

## Method recommendations

| Regime | Method | Card |
|---|---|---|
| Small cluster, exact reference | Projected ED | `skills/method-ed/SKILL.md` |
| 1D chain, narrow cylinder | DMRG | `skills/method-mps/SKILL.md` |
| Imaginary-time route | TEBD | `skills/method-mps/SKILL.md` |
| 2D doped variational (VMC / NQS) | VMC via NetKet for projected wavefunctions. Requires `make install netket`. | `skills/method-vmc/SKILL.md` |

## Branch table

| Condition | Action |
|---|---|
| User wants the connection to large-U Hubbard and Mott physics | Call `mott-transition`. |
| Frustrated lattice (triangular t-J, etc.) | Call `frustration`. |
| Questions about pairing / superconductivity / stripes in 2D doped t-J | Surface as out of current scope (variational territory); offer a 1D / narrow-cylinder DMRG analog. |
| At zero doping, the model reduces to Heisenberg | Switch to `heisenberg`. |

## Verification

Default checks:

- **Projection enforcement**: every site has occupancy ∈ {0, ↑, ↓}; double occupancy literally absent in the basis.
- **Limit checks** via `.knowledge/limits.md`: at zero doping → Heisenberg; at infinite-`J` limit → spin-isolated singlet pairs; at `t/J → ∞` and small doping → kinetic-dominated regime.
- **Symmetry**: particle counts; `S^z` (and SU(2) when isotropic); lattice symmetries.
- **Convergence**: bond-dim sweep; cylinder-width comparison for 2D.
- **Hubbard cross-check**: when `J = 4t²/U` is being claimed, run the corresponding Hubbard at large `U` and compare ground-state energies up to the expected `O((t/U)^4)` correction.
- **Cross-method validation** (when feasible) — re-run on a small projected cluster with an independent method; use an ED cross-check via `/method-ed`. See AGENTS.md "Verification practice".

Optional check:

- Use known integrable points (1D supersymmetric t-J at `J = 2t`) as a benchmark.

## Writeup handoff

After verification, if the user wants to communicate the result, consolidate to a runnable script + short run report, then render it via `/report`. See AGENTS.md "Writeup handoff".

## Related skills

`hubbard`, `mott-transition`, `heisenberg` (zero-doping), `frustration`.
