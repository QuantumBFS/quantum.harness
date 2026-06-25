# Attractive Hubbard

The Hubbard model with on-site **attraction** (`U < 0`) — the minimal lattice model of s-wave **superconductivity / pairing** and the **BCS–BEC crossover**. Its headline computational feature is that it is **sign-free in determinant QMC at any filling** (unlike the doped repulsive Hubbard). On a bipartite lattice at half-filling an exact **pseudospin (η-pairing) SU(2)** symmetry makes the s-wave-superconducting and charge-density-wave orders degenerate.

## Physics card

### Hamiltonian

$$ H = -t \sum_{\langle ij\rangle,\sigma} \left( c^\dagger_{i\sigma} c_{j\sigma} + \text{h.c.} \right) \;-\; |U| \sum_i n_{i\uparrow} n_{i\downarrow} \;-\; \mu \sum_i n_i $$

Conventions: `t > 0` standard hopping (energy unit `t = 1`); `U < 0` (written `−|U|`) is the on-site **attraction** (energy gained by double occupancy); `⟨ij⟩` = nearest-neighbor bonds counted once; `μ` is the chemical potential, with half-filling at `μ = −|U|/2` (particle-hole-symmetric form subtracts `(|U|/2)Σ n_i`). The pairs that form are bosonic; the model crosses over from weak-coupling BCS (loosely-bound Cooper pairs) to strong-coupling BEC (tightly-bound local pairs) as `|U|/t` grows. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 1D chain / 2D square (`Z = 4`) / 3D cubic; bipartite lattices are the canonical setting | 2D square is the standard testbed for the superconducting `T_c` dome. |
| A2 boundary conditions | PBC (ED / QMC) · OBC / cylinder (DMRG) · infinite (iDMRG) | Bipartite PBC clusters used for sign-free DQMC. |
| A3 statistics & local dim | fermion; `d = 4` per site (∅, ↑, ↓, ↑↓) | Same four-state local space as the repulsive Hubbard; the doubly-occupied state is now energetically favored. |
| A4 interaction range | short-range: on-site `U < 0` + NN hopping | Local — area-law-compatible. |
| B5 entanglement scaling | 1D: area + log near criticality (gapless pairing/charge mode) · 2D: area law | 1D Luther–Emery liquid (gapped spin, gapless charge) off half-filling. |
| B6 spectral gap | **spin gap** (pairs are spin singlets) for any `U < 0`; charge sector gapless off half-filling (superconductor), gapped at half-filling (pair CDW) | The pairing gap is the order; the spin gap is a hallmark of local-pair formation in the BEC regime. |
| B7 ground-state order | **s-wave superconductor** (off half-filling); **at half-filling on a bipartite lattice the SC and charge-density-wave orders are degenerate** (pseudospin SU(2)) | Off half-filling the pseudospin field tilts toward SC; at half-filling SC and CDW are exactly degenerate. |
| B8 frustration | none on bipartite lattices; fermionic statistics present but **does not** produce a DQMC sign here (see C12) | The attraction pairs up/down spins symmetrically, removing the usual fermionic sign. |
| C9 global symmetry | U(1)_charge × SU(2)_spin; **PLUS an exact pseudospin (η-pairing) SU(2) at half-filling on bipartite lattices** | The pseudospin SU(2) rotates between pairing and charge density — its three components are the SC order parameter (two) and the density (one); it forces the SC–CDW degeneracy. |
| C10 spatial symmetry | translation (`k`), point group (`D_4` square), inversion | Bipartite sublattice structure underlies the sign-free property. |
| C11 integrability | 1D: **Bethe-ansatz integrable** (Lieb–Wu with `U < 0`) · 2D / 3D: non-integrable | 1D has the exact spectrum / thermodynamics; higher D is fully numerical. |
| C12 sign problem | **SIGN-FREE in DQMC at ANY filling** (the attraction gives identical up- and down-spin determinants, `\det M_↑ \det M_↓ = (\det M)^2 ≥ 0`) | This is the headline computational feature — contrast the doped repulsive Hubbard, which has a severe sign problem. |
| D13 regime | ground state (`T = 0`) and **finite temperature** (the `T_c` of the SC transition is the central target) | Finite-`T` DQMC for `T_c`; ground-state DMRG/ED for pairing correlations. |
| D14 filling / doping | filling tunes the order: off half-filling → s-wave SC; half-filling → the SC/CDW-degenerate (pseudospin-symmetric) point | Filling is the key control axis between the SC and SC+CDW regimes (and along the `T_c` dome). |
| D15 disorder | clean by default; disorder studied for the SC–insulator (localization) transition of pairs | — |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- s-wave superconductor (off half-filling, any `U < 0`) : pairing order parameter `Δ = ⟨c_{i↑} c_{i↓}⟩`; pair-field (s-wave) correlation function and superfluid density; spin gap. Diagnose by the `q = 0` pair structure factor and superfluid stiffness.
- Half-filling (bipartite) : SC and charge-density-wave are **degenerate** (pseudospin SU(2)); the combined order is a "supersolid"-like degenerate manifold. Diagnose by the equal SC and CDW structure factors.
- BCS–BEC crossover : a smooth crossover (not a transition) from overlapping Cooper pairs (`|U| \ll t`) to tightly-bound on-site bosonic pairs (`|U| \gg t`), tracked by the pair size, double occupancy, and the two temperature scales `T_p` (pairing) and `T_c` (condensation).

### Canonical observables

- Pair-field correlation function `P_s(r) = ⟨Δ_i^\dagger Δ_j⟩` and s-wave pair structure factor; superfluid density `ρ_s`.
- Superconducting `T_c` vs filling `⟨n⟩` and `|U|/t` (the `T_c` dome).
- Double occupancy `⟨n_↑ n_↓⟩` (grows toward 1 in the BEC limit); momentum distribution `n(k)`; quasiparticle weight.
- Spin gap; pairing temperature `T_p`; at half-filling the CDW structure factor `S(π,π)` (degenerate with SC).

### Recommended methods

- Primary (any filling, large `N`, finite-`T` and ground state): **sign-free DQMC** — the attractive interaction makes the determinant a perfect square, so DQMC is numerically exact at scale at all fillings (per `method-property-map.md` §QMC / C12) — the decisive advantage over the doped repulsive model.
- Cross-check: **DMRG/MPS** in 1D / on cylinders (pairing correlations, spin gap); **ED** small-cluster oracle; the 1D Lieb–Wu Bethe-ansatz solution as an analytic benchmark.

### Key reference

[@fontenele_2022_attractive] — Fontenele, Costa, dos Santos & Paiva, "The 2D attractive Hubbard model and the BCS-BEC crossover" (Phys. Rev. B 105, 184502, 2022): a downloadable all-details study using **sign-free DQMC** to map the superconducting `T_c` across band filling and `|U|/t`, the BCS–BEC crossover (pairing `T_p` vs degeneracy `T_d` scales, double occupancy, `n(k)`, quasiparticle weight), chosen as the key reference because it directly delivers the headline benchmarks. Broader context: Micnas, Ranninger & Robaszkiewicz, "Superconductivity in narrow-band systems with local nonretarded attractive interactions", Rev. Mod. Phys. **62**, 113 (1990) (doi:10.1103/RevModPhys.62.113; no arXiv preprint).
Rendered: `./2201.02156_the-2d-attractive-hubbard-model-and-the-bcs-bec-crossover.md`.

### Benchmarks

- Sign-free DQMC at all fillings: the up/down determinants are identical (`\det M_↑ \det M_↓ = (\det M)^2 ≥ 0`), so the average sign is exactly 1 for any `⟨n⟩` (convention `H = -tΣc†c − |U|Σn↑n↓`) — the contrast with the sign-ful doped repulsive Hubbard.
- 2D square `T_c` dome (DQMC): a broad maximum `T_c ≈ 0.16\,t` near `|U|/t ≈ 5 ± 1` and band filling `⟨n⟩ ≈ 0.79 ± 0.09` — Fontenele et al. [@fontenele_2022_attractive].
- Half-filling SC–CDW degeneracy: on a bipartite lattice at `⟨n⟩ = 1` the s-wave-SC and CDW order parameters are exactly degenerate (pseudospin / η-pairing SU(2)).
- BCS–BEC crossover: a smooth crossover from BCS (`|U| \ll t`, large overlapping pairs, `T_c` rising with `|U|`) to BEC (`|U| \gg t`, tightly-bound local pairs, `T_c ∝ t^2/|U|` falling) with the maximum in between — Fontenele et al. [@fontenele_2022_attractive].

## How it is studied / Operational

**Canonical defaults (Diagnose):** attractive Hubbard on a 2D square lattice (or 1D chain), `|U|/t` from the user's prompt (default `|U|/t = 4` — moderate coupling, near the `T_c` maximum), filling `⟨n⟩` from the prompt (default half-filling `⟨n⟩ = 1` for the symmetric pseudospin point, or `⟨n⟩ ≈ 0.8` to sit near the `T_c` dome), PBC, target the pair structure factor + superfluid density + (finite-`T`) `T_c`. Because the model is **sign-free in DQMC at any filling**, that is the default workhorse — state this explicitly (it is the whole point versus the repulsive model). If only "attractive Hubbard" is given, propose half-filling (SC–CDW degenerate) and a doped (`⟨n⟩ ≈ 0.8`, pure SC) run and contrast.

| Regime | Method | Card |
|---|---|---|
| Any filling, finite-`T` `T_c`, large `N` (the default — sign-free) | DQMC / AFQMC | `skills/method-qmc/SKILL.md` |
| 1D chain / ladder / cylinder, pairing correlations & spin gap | DMRG / MPS | `skills/method-mps/SKILL.md` |
| Small cluster, full spectrum / pseudospin sectors | ED | `skills/method-ed/SKILL.md` |
| 1D analytic benchmark | Lieb–Wu Bethe ansatz (`U < 0`) | `.knowledge/models/hubbard/MODEL.md` |

Verification pointers:

- Limit checks via `.knowledge/limits.md`: `U = 0` → free fermions on the lattice; `|U| → ∞` → tightly-bound hard-core bosonic pairs (effective XXZ / hard-core-boson model, `T_c ∝ t^2/|U|`); attractive↔repulsive at half-filling on a bipartite lattice are related by a partial particle-hole transformation (maps SC ↔ AFM, CDW ↔ AFM components).
- Sign check: the DQMC average sign must be exactly 1 at all fillings (the diagnostic that confirms the sign-free property) — contrast with the doped repulsive run.
- Symmetry: charge U(1) × spin SU(2) conserved; at half-filling on a bipartite lattice verify the pseudospin SU(2) by the exact degeneracy of the SC and CDW structure factors (a directed self-consistency check).
- The partial particle-hole map to the repulsive Hubbard at half-filling gives an independent cross-check of energies and correlators.
