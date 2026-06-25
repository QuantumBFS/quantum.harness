# MBL — Disordered (Random-Field) Heisenberg Chain

Spin-½ Heisenberg/XXZ chain in a static random field — the canonical model of **many-body localization (MBL)**. As the disorder strength `W` is increased the chain crosses from a **thermal/ergodic** phase (obeys ETH, volume-law excited-state entanglement, Wigner-Dyson level statistics) to an **MBL** phase (ETH-violating, area-law entanglement even in highly-excited eigenstates, emergent local integrals of motion, Poisson statistics, only logarithmic entanglement growth after a quench). The physics lives in the **excited states and quench dynamics at finite energy density**, not the ground state.

## Physics card

### Hamiltonian

$$ H = J \sum_i \mathbf{S}_i\cdot\mathbf{S}_{i+1} \;+\; \sum_i h_i\, S^z_i, \qquad h_i \in [-W,\,+W]\ \text{i.i.d. uniform} $$

Conventions: `S`-operator normalization (`S^a = σ^a/2` for S=1/2); `J > 0` antiferromagnetic, set `J = 1` as the energy unit; the on-site fields `h_i` are independent, uniformly distributed in `[-W, +W]` (some references use `[-W/2, W/2]` or a Gaussian — note the box-vs-Gaussian and the `W` half-width convention when comparing `W_c`). The XXZ generalization `H = Σ J[Δ S^z_i S^z_{i+1} + S^x_i S^x_{i+1} + S^y_i S^y_{i+1}] + Σ h_i S^z_i` (with `Δ=1` the isotropic point) is the literature workhorse; via Jordan-Wigner it is interacting spinless fermions (`Δ` = interaction, `h_i` = random potential), so MBL here is the **interacting** descendant of Anderson localization. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 1D chain (`Z=2`) | 1D is where MBL is best established; higher-`d` MBL stability is debated (avalanche instability). |
| A2 boundary conditions | OBC (DMRG-X / shift-invert ED) · PBC (clean ED level statistics) | PBC restores translation for level-statistics ensembles; OBC is convenient for entanglement cuts and DMRG-X. |
| A3 statistics & local dim | spin-½; `d = 2` per site (Jordan-Wigner → interacting spinless fermions) | Same `2^N` Hilbert space as the clean chain; disorder lifts the need for momentum sectors. |
| A4 interaction range | short-range (nearest-neighbor exchange + on-site random field) | Locality is essential: it is what allows quasi-local integrals of motion (l-bits) to form in the MBL phase. |
| B5 entanglement scaling | **excited eigenstates: volume-law (thermal, small `W`) → area-law (MBL, large `W`)** | The eigenstate-entanglement transition is the defining MBL diagnostic; area-law excited states are why MPS/DMRG-X can target them. |
| B6 spectral gap | no protecting gap — physics is at finite energy density (mid-spectrum), many-body level spacing `∼ 2^{-N}` | The relevant scale is the level statistics of bulk eigenstates, not a ground-state gap. |
| B7 ground-state order | thermal phase: no order (ergodic) · MBL phase: emergent integrability; possible eigenstate (localization-protected) order / spin-glass order in eigenstates | MBL can stabilize order and "forbidden" eigenstate order at high energy density that equilibrium would wash out. |
| B8 frustration | none (unfrustrated NN chain); the complication is quenched randomness, not geometric frustration | Disorder, not frustration, drives the physics. |
| C9 global symmetry | U(1) (`S^z_tot` conserved; random field breaks SU(2)→U(1) and breaks translation) | `S^z`-resolution is the cheap ED/DMRG-X reduction; the random field removes momentum as a good quantum number. |
| C10 spatial symmetry | none (disorder breaks translation and point group); restored only after disorder averaging | Each realization is inhomogeneous; observables are averaged (median/typical) over realizations. |
| C11 integrability | clean chain: Bethe-ansatz integrable · thermal phase (`W` small): non-integrable, chaotic (ETH) · **MBL phase: emergent integrability — extensive set of quasi-local integrals of motion (l-bits)** | The l-bit picture is the central theoretical structure: `H = Σ h̃_i τ^z_i + Σ J̃_{ij} τ^z_i τ^z_j + …` in dressed pseudospins `τ^z` (exponentially localized), contrasting the clean chain's Bethe-ansatz integrability. |
| C12 sign problem | n/a — real fields, but studied by ED / shift-invert / Krylov / DMRG-X, **not QMC** (mid-spectrum excited states + real-time at finite energy density are off-limits to QMC) | The target (highly-excited eigenstates, long-time dynamics) is exactly the regime where Monte Carlo has no foothold. |
| D13 regime | **excited eigenstates / quench dynamics at finite energy density** (mid-spectrum, infinite-T ensemble) — the headline regime | Not a ground-state problem: one targets the middle of the many-body spectrum and post-quench dynamics, not `E_0`. |
| D14 filling / doping | fixed `S^z` sector (≈ half-filling in fermion language); usually the `S^z_tot=0` / largest sector | Filling fixes the sector size for shift-invert ED. |
| D15 disorder | **disordered (quenched random field) — the defining axis; ergodic ↔ MBL transition tuned by `W`** | Requires averaging over many realizations (sample multiplier); the ergodic→MBL crossover is the whole point of the model. |
| D16 hermiticity | Hermitian / closed (unitary dynamics) | Coupling to a bath / dissipation destabilizes MBL — a separate open-system question. |

### Phases & order parameters

- Thermal / ergodic phase (small `W`) : obeys ETH; excited eigenstates have **volume-law** entanglement; GOE/Wigner-Dyson level statistics (level-spacing ratio `⟨r⟩ ≈ 0.53`); DC transport and thermalization after a quench.
- MBL phase (large `W`) : ETH-violating; excited eigenstates have **area-law** entanglement; **emergent l-bits** (quasi-local integrals of motion); Poisson level statistics (`⟨r⟩ ≈ 0.386`); no DC transport; only **logarithmic-in-time** entanglement growth `S(t) ∝ ln t` after a quench; memory of initial-state imbalance.
- Diagnostics: level-spacing ratio `⟨r⟩`, mid-spectrum entanglement entropy and its variance, post-quench imbalance/return probability, the logarithmic entanglement-growth slope, l-bit localization length.

### Canonical observables

- Adjacent-gap (level-spacing) ratio `⟨r_n⟩ = ⟨min(δ_n,δ_{n+1})/max(δ_n,δ_{n+1})⟩` for mid-spectrum eigenvalues (GOE ≈ 0.5307, Poisson ≈ 0.3863).
- Bipartite entanglement entropy of mid-spectrum eigenstates (volume vs area law) and its sample-to-sample variance (peaks at the transition).
- Post-quench imbalance `I(t)` / staggered-magnetization memory, and entanglement entropy `S(t)` (linear in thermal phase, `∝ ln t` in MBL).
- All quantities are **disorder-averaged** (often the median / typical value) over many field realizations.

### Recommended methods

- Primary (eigenstates): **shift-invert / Krylov ED** for mid-spectrum eigenstates (`L ≲ 22–24` after `S^z` resolution) — gives `⟨r⟩`, eigenstate entanglement, and level statistics; the standard MBL workhorse (per `method-property-map.md` §ED, B5 volume↔area, D15).
- Primary (deep-MBL eigenstates, larger `L`): **DMRG-X / MPS** — exploits the area-law of MBL excited eigenstates to target individual highly-excited states variationally (§MPS, D15 "excited-state area law").
- Primary (dynamics): **TEBD / TDVP** for post-quench evolution at moderate times; entanglement grows only logarithmically in the MBL phase, so MPS reaches long times there (§MPS, D13).
- Cross-check: full ED on small `L` (exact spectrum / oracle); always **average over realizations** and report the distribution, not a single sample.

### Key reference

[@abanin_2018_colloquium] — Abanin, Altman, Bloch & Serbyn, "Colloquium: Many-body localization, thermalization, and entanglement" (Rev. Mod. Phys. 91, 021001, 2019): the authoritative downloadable all-details review — ETH and its MBL breakdown, the random-field XXZ/Heisenberg chain, the l-bit (quasi-local integrals of motion) picture, area-law excited-state entanglement, logarithmic entanglement growth, level statistics, eigenstate order, and the experimental platforms.
Rendered: `./1804.11065_colloquium-many-body-localization-thermalization-and-entangl.md`.

### Benchmarks

- Ergodic→MBL crossover (1D random-field Heisenberg, mid-spectrum, infinite-T ensemble): `W_c ≈ 3.5 J` (box disorder `h_i∈[-W,W]`) — the much-cited Pal–Huse / Luitz–Laflorencie–Alet value, with a strong caveat that finite-size drifts and avalanche arguments cast doubt on whether a sharp transition survives `L→∞` [@abanin_2018_colloquium] (Luitz, Laflorencie & Alet, Phys. Rev. B 91, 081103 (2015)).
- Level-spacing ratio: `⟨r⟩ ≈ 0.5307` (GOE, thermal) → `⟨r⟩ ≈ 0.3863` (Poisson, MBL) — the standard ergodicity diagnostic (Oganesyan–Huse, Phys. Rev. B 75, 155111 (2007); Atas et al. 2013) [@abanin_2018_colloquium].
- Post-quench entanglement growth: `S(t) ∝ ln t` in the MBL phase (vs linear in the thermal phase) — the slow-dynamics signature explained by the l-bit dephasing (Žnidarič et al. 2008; Bardarson–Pollmann–Moore 2012) [@abanin_2018_colloquium].

## How it is studied / Operational

**Canonical defaults (Diagnose):** spin-½ random-field Heisenberg/XXZ chain (`J=1`, `Δ=1`), box disorder `h_i∈[-W,W]`, OBC, `L = 16–18`, `S^z_tot=0` sector, **mid-spectrum** target. Default deliverable: the disorder-averaged level-spacing ratio `⟨r⟩(W)` and mid-spectrum entanglement across a `W`-scan bracketing `W_c≈3.5`, with many (≳10²–10³) realizations. If only "MBL / disordered Heisenberg" is given, propose this `W`-scan; offer the post-quench imbalance/entanglement-growth dynamics as the alternative deliverable.

| Regime | Method | Card |
|---|---|---|
| Full spectrum, level statistics, eigenstate entanglement (`L ≲ 16`) | ED | `skills/method-ed/SKILL.md` |
| Mid-spectrum eigenstates only (`L ≲ 22–24`), shift-invert / Krylov | ED (interior eigensolver) | `skills/method-ed/SKILL.md` |
| Individual highly-excited MBL eigenstates at larger `L` (DMRG-X) | MPS | `skills/method-mps/SKILL.md` |
| Post-quench dynamics, imbalance, entanglement growth | MPS (TEBD/TDVP) | `skills/method-mps/SKILL.md` |

Verification pointers:

- Average over disorder realizations and report the **distribution** (median/typical + variance), not a single sample; the entanglement-entropy variance peaks at the transition — a useful crossing diagnostic.
- Deep in the thermal phase `⟨r⟩→0.531` (GOE) and deep in the MBL phase `⟨r⟩→0.386` (Poisson); these two limits are the negative/positive controls. At `W=0` the clean chain is Bethe-ansatz integrable (Poisson-like in a fixed sector) — exclude it from the ergodic control.
- Check `S^z_tot` conservation and that mid-spectrum (not edge) eigenstates are targeted (the energy-density / `ε=(E-E_min)/(E_max-E_min)≈0.5` window).
- Be explicit about strong finite-size drift: report `W_c(L)` for several `L` and resist claiming a thermodynamic transition from one size. For the criticality of the crossover or its survival in `L→∞`, surface the open debate rather than asserting a clean exponent.
