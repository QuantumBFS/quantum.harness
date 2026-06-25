# Kondo lattice

Solve the Kondo lattice model — itinerant conduction electrons coupled to a regular lattice of localized spin-½ moments. The arena of heavy-fermion physics: the Doniach competition between Kondo screening and RKKY magnetism, heavy Fermi liquids, and the Kondo insulator at half-filling.

## Physics card

### Hamiltonian

$$ H = -t \sum_{\langle ij\rangle,\sigma} \left( c^\dagger_{i\sigma} c_{j\sigma} + \text{h.c.} \right) + J_K \sum_i \mathbf{S}_i \cdot \mathbf{s}_i $$

Conventions: `t > 0` standard hopping (energy unit `t = 1`); `J_K > 0` antiferromagnetic Kondo coupling (the physically relevant sign — Kondo screening). `S_i` is a localized spin-½ moment at site `i`; `s_i = ½ Σ_{αβ} c†_{iα} σ_{αβ} c_{iβ}` is the conduction-electron spin density at the same site. `⟨ij⟩` = nearest-neighbor bonds counted once. This is the **lattice** model (one moment per site), distinct from the single Kondo impurity (`anderson-impurity`). See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 1D chain / quasi-1D ladder / 2D square (`Z=4`) / 3D / `Z→∞` (DMFT/DMFT-DCA) | 1D KLM is the cleanest DMRG target; higher D is the heavy-fermion / quantum-criticality arena. |
| A2 boundary conditions | OBC (DMRG) · PBC (ED) · cylinder (2D DMRG) · infinite (DMFT) | Cylinder width caps the 2D-DMRG bond-dim budget. |
| A3 statistics & local dim | fermion conduction band (`d_c = 4`: ∅, ↑, ↓, ↑↓) **plus** a localized spin-½ at each site → effective `d = 8` per site | The extra two-dimensional local spin space doubles the per-site cost over plain Hubbard. |
| A4 interaction range | short-range: on-site Kondo exchange `J_K` + NN hopping | Local — area-law-compatible. |
| B5 entanglement scaling | 1D: area law (gapped Kondo insulator at half-filling) · area+log near gapless metallic / critical regimes · 2D: area law | Heavy-Fermi-liquid metal is gapless (Fermi-surface log corrections). |
| B6 spectral gap | half-filling: spin gap **and** charge gap for all `J_K>0` (Kondo insulator, 1D) · doped / metallic: gapless (heavy Fermi liquid) | 1D half-filled KLM is gapped for any `J_K>0` (Tsunetsugu–Sigrist–Ueda). |
| B7 ground-state order | **heavy Fermi liquid** (paramagnetic, large Fermi surface) · **RKKY antiferromagnet** (small `J_K`) · ferromagnet (low conduction filling) · **Kondo insulator** (half-filling) | Doniach picture: AF order at small `J_K`, screened paramagnet (heavy FL) at large `J_K`. |
| B8 frustration | none on bipartite lattices · interaction-driven competition (Kondo vs RKKY) · fermionic sign always present | The Kondo–RKKY competition is the model's defining tension, not geometric frustration. |
| C9 global symmetry | U(1)_charge (conduction `N`) × SU(2)_spin (total spin of conduction + local moments); `S^z` conserved | Particle-hole symmetry at half-filling on bipartite lattices (sign-free DQMC). |
| C10 spatial symmetry | translation (`k`), point group (`D_4` square), inversion | Block-diagonalizes ED sectors. |
| C11 integrability | **non-integrable** (the lattice model) | Contrast the single Kondo impurity, which IS Bethe-ansatz solvable; the lattice destroys integrability → full numerics required. |
| C12 sign problem | half-filled particle-hole-symmetric KLM: **sign-free in DQMC** · doped: severe sign problem in general | Half-filling on a bipartite lattice is the sign-free reference point. |
| D13 regime | ground state (`T=0`) default; finite-T (DQMC/DMFT) for the Kondo crossover `T_K` and `T_coh` | `E/N`, spin/charge gaps, and the Doniach phase boundary are the targets. |
| D14 filling / doping | half-filling → Kondo insulator (symmetric reference); doping turns on the sign problem and the heavy-FL / magnetic competition | Conduction filling is the key control axis (along with `J_K/t`). |
| D15 disorder | clean by default; disorder → Kondo-disorder / non-Fermi-liquid physics (out of scope) | — |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- Heavy Fermi liquid (paramagnetic) : Kondo screening wins (`J_K ≳ J_K*`); large Fermi surface enclosing conduction + local-moment count, strongly enhanced effective mass `m*`. Diagnostics: `m*` / coherence temperature `T_coh`, large-Fermi-surface volume.
- RKKY antiferromagnet : at small `J_K`, indirect RKKY exchange (`∝ J_K²`) orders the local moments — staggered magnetization `m_s`, spin structure-factor peak `S(π,…)`.
- Ferromagnet : at low conduction-electron filling, double-exchange-like ferromagnetism of the local moments.
- Kondo insulator (half-filling) : both spin and charge gap open for any `J_K>0` — measure `Δ_spin`, `Δ_charge`.

### Canonical observables

- Ground-state energy per site `E/N`; spin gap `Δ_spin` and charge gap `Δ_charge` (half-filling).
- Staggered magnetization `m_s`, spin structure factor `S(q)` (RKKY phase).
- Effective mass `m*` / quasiparticle weight `Z`; coherence / Kondo temperature `T_K ∝ exp(−1/J_K ρ)`.
- Doniach crossover scale `J_K*` where `T_K ~ T_RKKY` (RKKY-AF ↔ heavy-FL boundary).

### Recommended methods

- Primary (1D / ladder / cylinder): **DMRG/MPS** — near-exact in 1D, U(1)×SU(2) quantum-number conservation cuts cost (per `method-property-map.md` §MPS); the standard tool for the 1D-KLM phase diagram.
- Primary (high-D / local self-energy): **DMFT / DMFT-DCA** — captures Kondo screening, heavy-FL coherence, and the Kondo insulator in the large-`Z` limit (§A1 `Z→∞`).
- Cross-check: **sign-free DQMC** at half-filling (particle-hole symmetry, §C12); **ED** small-cluster oracle; **VMC/NQS** for doped / sign-blocked regimes.

### Key reference

[@coleman_2006_heavy] — Coleman's "Heavy Fermions: electrons at the edge of magnetism" review: the all-details pedagogical source covering the Kondo lattice, the Doniach phase diagram, Kondo screening vs RKKY, heavy Fermi liquids and Kondo insulators. Chosen over Tsunetsugu–Sigrist–Ueda RMP 69, 809 (1997) because it is freely downloadable (arXiv) and broader in scope, while still covering the 1D-KLM benchmarks cited below.
Rendered: `./cond-mat-0612006_heavy-fermions-electrons-at-the-edge-of-magnetism.md`.

### Benchmarks

- 1D half-filled KLM is a **Kondo insulator** with both a spin gap and a charge gap for all `J_K > 0` (no magnetic order, no Doniach transition at half-filling) — Tsunetsugu, Sigrist & Ueda, Rev. Mod. Phys. 69, 809 (1997) (convention `H = −tΣc†c + J_K Σ S·s`, `J_K>0`).
- Doniach competition (away from half-filling): RKKY scale `T_RKKY ∝ J_K²` vs Kondo scale `T_K ∝ exp(−1/J_K ρ)` cross at a coupling `J_K*`; for `J_K < J_K*` the ground state is an RKKY antiferromagnet, for `J_K > J_K*` a paramagnetic heavy Fermi liquid (Doniach 1977; reviewed in [@coleman_2006_heavy]).

## How it is studied / Operational

**Canonical defaults (Diagnose):** 1D chain, half-filling (one conduction electron per site, `S^z=0` sector), `J_K/t` from the user's prompt (default `J_K/t = 1` — intermediate coupling), NN hopping, OBC, `N=20`, target `E/N` + spin/charge gaps (Kondo-insulator identification). If only "Kondo lattice" is given, propose the 1D half-filled Kondo insulator with DMRG, and offer a `J_K` scan or a doped run to probe the Doniach competition.

| Regime | Method | Card |
|---|---|---|
| Small cluster (N ≲ 12 sites), exact spectrum / cross-check | ED | `skills/method-ed/SKILL.md` |
| 1D chain, ladder, narrow cylinder — gaps, phase diagram | DMRG | `skills/method-mps/SKILL.md` |
| Half-filled bipartite, large `N` (sign-free) | DQMC | `skills/method-qmc/SKILL.md` |
| High-D / local self-energy, heavy-FL coherence, Kondo insulator | DMFT / DMFT-DCA — surface explicitly (out of current install scope) | — |
| Doped / sign-blocked variational comparison | VMC/NQS | `skills/method-vmc/SKILL.md` |

Verification pointers:

- Limit checks: `J_K = 0` → free conduction band + decoupled paramagnetic local moments; `J_K → ∞` → on-site Kondo singlets (local-singlet product reference). See `.knowledge/limits.md`.
- Symmetry: conduction `N` and total `S^z` conservation; particle-hole symmetry at half-filling on bipartite lattices (enables sign-free DQMC and a free check).
- 1D half-filling benchmark: confirm a finite spin gap AND charge gap for any `J_K>0` (Kondo insulator) — no magnetic order should appear at half-filling.
- Doniach diagnostic (doped): track `m_s` vs `J_K`; magnetic order should onset below `J_K*` and give way to a paramagnetic heavy FL above it.
- Convergence: bond-dim sweep (+ cylinder width when 2D); cross-check small clusters against ED.
