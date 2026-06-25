# XXZ chain

Solve the spin-1/2 XXZ chain — the canonical Bethe-ansatz-integrable 1D magnet whose anisotropy `Δ` tunes between gapped ferromagnet, gapless Luttinger liquid, and gapped Néel antiferromagnet.

Distinct from `heisenberg` (which defaults to the isotropic SU(2) point and broader lattices): this card is the 1D `Δ`-tuned phase diagram, where integrability supplies exact benchmarks for all `Δ`.

## Physics card

### Hamiltonian

$$ H = J \sum_i \left( S^x_i S^x_{i+1} + S^y_i S^y_{i+1} + \Delta\, S^z_i S^z_{i+1} \right) $$

Conventions: spin-1/2 `S`-operators (`S^a = σ^a/2`, `d=2`); in-plane coupling set to the energy unit `J = 1`; `Δ` the XXZ exchange anisotropy. `Δ = 1` recovers the isotropic Heisenberg point; `Δ = 0` the XX (free-fermion) point. `J > 0` is the antiferromagnetic convention used here. Common alternative: Pauli notation differs by a factor 4 per bilinear. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 1D chain (`Z=2`) | The defining 1D integrable spin chain. |
| A2 boundary conditions | PBC (Bethe ansatz / ED) · OBC (DMRG default) | PBC needed for the clean Bethe-ansatz spectrum and momentum sectors. |
| A3 statistics & local dim | spin-1/2; `d = 2` | Jordan–Wigner maps to spinless fermions with NN hopping + NN interaction (the t-V chain). |
| A4 interaction range | short-range (nearest-neighbor) | Local — area-law compatible. |
| B5 entanglement scaling | critical phase (`−1<Δ≤1`): area+log, `S=(c/3)log ℓ`, `c=1` · gapped phases (`Δ<−1`, `Δ>1`): area law (constant `S`) | Luttinger-liquid central charge `c=1` in the whole XY/critical window. |
| B6 spectral gap | gapless (`−1<Δ≤1`, power-law correlations) · gapped FM (`Δ<−1`) · gapped Ising-Néel AFM (`Δ>1`) | Gap opens exponentially as `Δ→1⁺` (BKT); FM transition at `Δ=−1` is first-order. |
| B7 ground-state order | gapless XY/Luttinger liquid (quasi-long-range, no SSB) · ferromagnet (`Δ<−1`, fully polarized SSB) · Ising-Néel AFM (`Δ>1`, staggered SSB) | Quasi-LRO in the critical phase (Mermin–Wagner forbids true LRO in 1D). |
| B8 frustration | none (bipartite chain) | NN-only on a bipartite lattice; the AFM case is sign-free (Marshall). |
| C9 global symmetry | U(1) (`S^z_tot`); full SU(2) only at `Δ=1`; `Z_2` spin-flip | Anisotropy `Δ≠1` breaks SU(2)→U(1). |
| C10 spatial symmetry | translation (`k`), inversion/parity | Block-diagonalizes ED sectors; CDW/Néel image breaks translation by one site. |
| C11 integrability | **Bethe-ansatz integrable for all `Δ`** | Exact spectrum, ground-state energy, gap, and thermodynamics (TBA) at every anisotropy. |
| C12 sign problem | sign-free for the bipartite AFM (Marshall sign rule) | Unfrustrated bipartite chain → QMC-exact; DMRG is the practical workhorse. |
| D13 regime | ground state (`T=0`) default; finite-T accessible via TBA / LTRG (out of card scope) | `E/N`, gap, `c`, correlators are the canonical targets. |
| D14 filling / doping | N/A (spin model; `S^z_tot` plays the role of magnetization/filling) | A longitudinal field tunes magnetization, staying integrable. |
| D15 disorder | clean (translation-invariant) by default | Bond disorder → random-singlet phase (out of scope). |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- Gapless XY / Luttinger liquid (`−1 < Δ ≤ 1`) : quasi-long-range order, no SSB; spin–spin correlations decay as a power law with `Δ`-dependent exponent; central charge `c = 1`.
- Ising-Néel AFM (`Δ > 1`) : staggered magnetization `m_s = (1/N)Σ_i (−1)^i ⟨S^z_i⟩`, structure-factor peak `S(π)`, finite gap. Onset is a BKT transition at `Δ = 1`.
- Ferromagnet (`Δ < −1`) : fully polarized `⟨S^z_i⟩ = ±1/2`. The transition at `Δ = −1` is first-order (ground-state level crossing).

### Canonical observables

- Ground-state energy per site `E/N`.
- Spin gap (`Δ>1`); central charge `c` and Luttinger parameter `K` (critical phase, from entanglement / correlation scaling).
- Static structure factor `S(q)` (peaks at `q=π` in the Néel phase); spin–spin correlators `⟨S^z_0 S^z_r⟩`, `⟨S^+_0 S^-_r⟩`.

### Recommended methods

- Primary: **DMRG/MPS** — 1D area-law / area+log ground states; U(1) `S^z` conservation; converges fast in the gapped phases, `χ`-hungry but reliable in the critical phase (per `method-property-map.md` §MPS, B5).
- Cross-check: **ED** on small clusters (exact spectrum, momentum sectors); **exact Bethe ansatz** for the energy/gap at any `Δ` (C11); sign-free **QMC/SSE** for the AFM side at scale.

### Key reference

[@franchini_2016_introduction] — pedagogical all-details monograph on integrable techniques; works the XXZ chain explicitly from the coordinate Bethe ansatz to the algebraic Bethe ansatz, with the ground-state energy, the `Δ`-tuned phase structure, and finite-temperature thermodynamics.
Rendered: `./1609.02100_an-introduction-to-integrable-techniques-for-one-dimensional.md`.

### Benchmarks

- Isotropic point `Δ = 1` (Heisenberg, PBC, thermodynamic limit): `E/N = 1/4 − ln 2 ≈ −0.443147` — exact Bethe ansatz (convention `H = J Σ S_i·S_j`, `J = 1`).
- XX point `Δ = 0` (free fermions via Jordan–Wigner, half-filling, thermodynamic limit): `E/N = −1/π ≈ −0.318310` (convention `J = 1`, in-plane terms only).

## How it is studied / Operational

**Canonical defaults (Diagnose):** S=1/2, `J = 1`, `Δ` from the prompt (default `Δ = 1` isotropic), `S^z_tot = 0` sector, OBC, `N = 32`, target `E/N` (+ gap / `c` if a phase question). If only "XXZ chain" is given, propose the isotropic point and offer a `Δ`-scan across FM (`Δ<−1`) → critical (`−1<Δ≤1`) → Néel (`Δ>1`).

| Regime | Method | Card |
|---|---|---|
| 1D chain, ground-state energy / correlators (any `Δ`) | DMRG | `skills/method-mps/SKILL.md` |
| Small cluster (`N ≲ 24`), exact spectrum / momentum sectors / cross-check | ED | `skills/method-ed/SKILL.md` |
| Critical phase, central charge `c` from entanglement scaling | DMRG + finite-entanglement scaling | `skills/method-mps/SKILL.md` |
| AFM side (`Δ≥1`) at large `N`, sign-free | QMC/SSE | `skills/method-qmc/SKILL.md` |

Verification pointers:

- Exact Bethe-ansatz energy at `Δ=1` (`E/N = 1/4 − ln2`) and `Δ=0` (`E/N = −1/π`) anchor the calculation.
- `S^z_tot` conservation; expected ground-state sector (`S^z_tot = 0` for the AFM/critical regimes); first-order level crossing at `Δ=−1`.
- Convergence: bond-dim sweep monotonic and asymptoting; the critical phase needs larger `χ` (gap closes) than the gapped phases.
- For the `Δ=1` → BKT transition or critical exponents, hand off to `criticality` after the calculation.
