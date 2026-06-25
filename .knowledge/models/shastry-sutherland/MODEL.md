# Shastry–Sutherland

Solve the Shastry–Sutherland model — a spin-1/2 square-lattice antiferromagnet with orthogonal dimer bonds that has an exact dimer-singlet product ground state in a regime, hosts rich magnetization plateaus, and is realized in the material SrCu2(BO3)2.

## Physics card

### Hamiltonian

$$ H = J \sum_{\langle ij\rangle_{NN}} \mathbf{S}_i\cdot\mathbf{S}_j \;+\; J' \sum_{\langle ij\rangle_{\text{dimer}}} \mathbf{S}_i\cdot\mathbf{S}_j $$

Conventions: spin-1/2 `S`-operators (`d=2`); `J` is the square-lattice nearest-neighbor exchange, `J'` the diagonal (orthogonal-dimer) exchange; both antiferromagnetic (`>0`). The control parameter is the ratio `J/J'` (equivalently `J'/J`). The orthogonal-dimer geometry is what makes the dimer-singlet product an exact eigenstate. Energy unit set to the larger coupling. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 2D square lattice with orthogonal diagonal-dimer bonds (`Z=4` from the square + dimer bonds) | The orthogonality of neighboring dimers is the defining structural feature. |
| A2 boundary conditions | torus / PBC (ED) · cylinder (DMRG) | Torus for clean momentum sectors; cylinders for 2D DMRG. |
| A3 statistics & local dim | spin-1/2; `d = 2` | — |
| A4 interaction range | short-range (NN square exchange `J` + dimer exchange `J'`) | Local. |
| B5 entanglement scaling | dimer phase: area law (product of singlets, `S → 0`) · plaquette/Néel: 2D area law (`∝ L`) | The exact dimer phase is essentially unentangled across dimer-respecting cuts. |
| B6 spectral gap | gapped (dimer-singlet and plaquette phases) · gapless (Néel phase, Goldstone magnons) | A spin gap protects the dimer/plaquette states; closes in the Néel phase. |
| B7 ground-state order | **exact dimer-singlet product** (small `J/J'`) · plaquette-singlet (intermediate) · Néel AFM (large `J/J'`) | The dimer phase is a short-range-entangled product; the others are conventional. |
| B8 frustration | strong geometric frustration (orthogonal dimers) | Frustration stabilizes the dimer product and the magnetization plateaus. |
| C9 global symmetry | SU(2) (total spin), U(1) (`S^z_tot`) | A field breaks SU(2)→U(1), tuning the magnetization plateaus. |
| C10 spatial symmetry | translation, point group of the Shastry–Sutherland lattice | Plateau superstructures break translation. |
| C11 integrability | not integrable, but the **dimer-singlet product is an exact ground state for small `J/J'`** (Shastry–Sutherland 1981) | Exact GS in a regime; the rest of the phase diagram is numerical. |
| C12 sign problem | sign-ful (geometric frustration) → QMC blocked for the frustrated regime; the exact dimer state and DMRG/ED sidestep it | Frustration turns on the spin sign problem; sign-free QMC is restricted. |
| D13 regime | ground state (`T=0`) default; magnetization process in a field | `E/spin`, spin gap, and the `m(H)` plateau structure are the targets. |
| D14 filling / doping | N/A (spin model; magnetization `m/m_sat` is the field-tuned analog) | Plateaus appear at commensurate `m/m_sat`. |
| D15 disorder | clean by default | — |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- Exact dimer-singlet (small `J/J'`, `J/J' ≲ 0.675`) : product of NN singlets on the dimer bonds — an exact eigenstate; full spin gap, no magnetic order.
- Plaquette-singlet (intermediate, `0.675 ≲ J/J' ≲ 0.76`) : resonating singlets on empty plaquettes; gapped, breaks lattice symmetry.
- Néel AFM (large `J/J'`, `J/J' ≳ 0.76`) : staggered magnetization, gapless Goldstone modes.
- In a magnetic field: a cascade of **magnetization plateaus** at commensurate `m/m_sat` (e.g. `1/8, 1/4, 1/3, …`) from crystallization of triplet excitations.

### Canonical observables

- Ground-state energy per spin `E/spin`; spin gap.
- Phase-boundary locations in `J/J'`; plaquette / dimer order parameters.
- Magnetization curve `m(H)` and plateau values `m/m_sat`; triplet dispersion (nearly flat → localized triplets).

### Recommended methods

- Primary: **DMRG/MPS** on cylinders and **ED** on finite clusters — QMC is sign-blocked by frustration, so tensor-network and exact-cluster methods carry the phase diagram and plateaus (per `method-property-map.md` B8/C12 frustrated-2D row).
- Cross-check: the **exact dimer-singlet energy** anchors the small-`J/J'` regime; **VMC/NQS** for variational comparison; **PolyOpt** for a certified energy bound in the frustrated regime.

### Key reference

[@miyahara_1998_exact] — Miyahara & Ueda, the foundational analysis identifying the Shastry–Sutherland (orthogonal-dimer) model as the description of SrCu2(BO3)2: the exact dimer ground state, the spin gap, and the critical `J/J'` for the dimer→Néel transition.
Rendered: `./cond-mat-9807075_exact-dimer-ground-state-of-the-two-dimensional-heisenberg-s.md`.

_Reference choice: the canonical Miyahara–Ueda review (J. Phys.: Condens. Matter 15, R327, 2003) has no arXiv preprint and is paywalled; this Miyahara–Ueda PRL preprint (cond-mat/9807075) is the downloadable all-details source for the same physics (exact dimer state, gap, `J/J'` transition) and is preferred over a bib stub for the 1981 original._

### Benchmarks

- Exact dimer phase (small `J/J'`): `E/spin = −3J'/8` — exact dimer-singlet energy (each dimer singlet contributes `−3J'/4` per bond = `−3J'/8` per spin; convention `H = J Σ_NN + J' Σ_dimer`).
- Magnetization plateaus at commensurate `m/m_sat = 1/8, 1/3, …` (and others such as `1/4, 1/2`) observed in SrCu2(BO3)2 and reproduced by ED/DMRG.
- Phase transitions near `J/J' ≈ 0.675` (dimer→plaquette) and `≈ 0.76` (plaquette→Néel). The intermediate plaquette phase and these two boundaries are established by later studies (e.g. Corboz & Mila, PRB 87, 115144 (2013)); the cited 1998 Miyahara–Ueda paper reports a single dimer→Néel transition near `J/J' ≈ 0.7`.

## How it is studied / Operational

**Canonical defaults (Diagnose):** spin-1/2, antiferromagnetic `J, J' > 0`, ratio `J/J'` from the prompt (default the exact-dimer regime `J/J' = 0.5`), `S^z_tot = 0` sector, torus/PBC for ED or cylinder for DMRG, zero field by default, target `E/spin` + phase identification. If only "Shastry–Sutherland" is given, propose the exact dimer point and offer a `J/J'` scan through plaquette → Néel, or a field scan for the magnetization plateaus.

| Regime | Method | Card |
|---|---|---|
| Small `J/J'` (dimer phase) — energy / gap | exact dimer-singlet + ED cross-check | `skills/method-ed/SKILL.md` |
| `J/J'` scan across the phase diagram (cylinder) | DMRG | `skills/method-mps/SKILL.md` |
| Small cluster, exact spectrum / plateau structure | ED | `skills/method-ed/SKILL.md` |
| Frustrated regime, variational comparison (QMC sign-blocked) | VMC/NQS | `skills/method-vmc/SKILL.md` |
| Certified ground-state energy bound | PolyOpt | `skills/method-polyopt/SKILL.md` |

Verification pointers:

- Exact dimer-singlet energy `E/spin = −3J'/8` anchors the small-`J/J'` regime — any method must reproduce it there.
- `S^z_tot` and SU(2) conservation; the dimer state is a product of singlets (`S_tot = 0`).
- QMC is sign-blocked by frustration — do not propose sign-free QMC for the frustrated phase; use DMRG/ED/VMC instead.
- For the magnetization plateaus, run in fixed-`S^z_tot` sectors and read off the `m(H)` steps; for the dimer↔plaquette↔Néel transitions, hand off to `criticality`.
