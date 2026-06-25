# Haldane (Chern insulator)

The honeycomb tight-binding model with a complex next-nearest-neighbor hopping (staggered flux, **zero net flux per cell**) and a sublattice mass — the first **Chern insulator / quantum anomalous Hall** model: a quantized Hall conductance `σ_xy = ±e²/h` with no net magnetic field. A free-fermion (quadratic) model, exactly solvable, the prototype of band topology in symmetry class A.

## Physics card

### Hamiltonian

$$ H = t_1 \sum_{\langle ij\rangle} c^\dagger_i c_j \;+\; t_2 \sum_{\langle\langle ij\rangle\rangle} e^{i\phi_{ij}}\, c^\dagger_i c_j \;+\; M \sum_i \xi_i\, n_i $$

Conventions: spinless fermions on the honeycomb lattice (two sublattices A, B). `t_1 > 0` is the **real** nearest-neighbor (A↔B) hopping (energy unit `t_1 = 1`); `t_2` is the **complex** next-nearest-neighbor (same-sublattice) hopping with phase `φ_{ij} = +φ` for one chirality of NNN bond and `−φ` for the other (the staggered flux pattern gives **zero net flux through the unit cell**); `M` is the sublattice (Semenoff) on-site mass with `ξ_i = +1` on A, `−1` on B. The state is a topological Chern insulator (`C = ±1`) when `|M| < |3\sqrt{3}\, t_2 \sin\phi|` and a trivial band insulator otherwise; the two Dirac points gap with opposite/same sign depending on which term dominates. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 2D honeycomb lattice, two-site (A/B) unit cell, coordination `Z = 3` | Two Dirac points (`K`, `K'`) in the Brillouin zone are the seat of the topology. |
| A2 boundary conditions | PBC / torus (Bloch bands, Chern number) · ribbon / cylinder (chiral edge modes, bulk–boundary correspondence) | The ribbon geometry exposes the chiral edge states; the torus defines `C`. |
| A3 statistics & local dim | spinless fermion; `d = 2` per site; **quadratic** (single-particle) | `d = 2` (single orbital per site); the many-body state is a Slater determinant filling the lower band. |
| A4 interaction range | short-range: real NN hopping + complex NNN hopping + on-site mass | Local; no interactions in the canonical model. |
| B5 entanglement scaling | 2D area law (gapped); the half-filled lower-band ground state is short-range entangled but carries a nonzero Chern number | Free-fermion ground state; the Chern number is the bulk topological signature (no local order parameter). |
| B6 spectral gap | gapped (band gap at `K`, `K'`) except on the phase boundary `M = ±3\sqrt{3}\, t_2 \sin\phi` where one Dirac point closes | Gap closing at a single Dirac cone = topological transition (`C` jumps by `±1`). |
| B7 ground-state order | **Chern insulator / quantum anomalous Hall** (topological band, class **A**, `C = ±1`) for `|M| < |3\sqrt{3}\, t_2 \sin\phi|`; trivial band insulator otherwise | Topological phase: one chiral edge mode per edge, quantized `σ_xy = ±e²/h`. No symmetry breaking — the order is purely band-topological. |
| B8 frustration | none (free fermions) | — |
| C9 global symmetry | charge U(1) (particle number); **time-reversal is broken** by the complex `t_2` (this is what allows `C ≠ 0`) | Broken time-reversal → class A; the staggered flux carries no net flux but breaks `T`. The mass term `M` instead breaks inversion. |
| C10 spatial symmetry | translation (`k`); `C_3` rotation; inversion broken by `M`, `T` broken by `φ` | At `M = 0, \sin\phi \ne 0` inversion is preserved but `T` is broken (topological); at `\phi = 0, M \ne 0` `T` is preserved but inversion broken (trivial). |
| C11 integrability | **free-fermion / quadratic → exactly solvable** (diagonalize the `2×2` Bloch Hamiltonian per `k`, `O(N³)` real-space) | Berry curvature integrated over the BZ gives the integer Chern number. |
| C12 sign problem | N/A — free fermions, no Monte Carlo required (interacting/Haldane–Hubbard extensions are sign-ful) | — |
| D13 regime | ground state (`T = 0`) default; quench / Hall-response dynamics also exactly tractable (quadratic) | The Chern number and edge spectrum are the targets. |
| D14 filling / doping | half-filling (lower band filled, gap at zero energy) is the topological insulating reference | At half-filling the Fermi level sits in the gap; the quantized Hall response requires the gap to be at the chemical potential. |
| D15 disorder | clean by default; weak disorder preserves the quantized `σ_xy` (topological protection) until it closes the mobility gap | Topological robustness against disorder is a defining feature of the QAH plateau. |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- Chern-insulator (QAH) phase (`|M| < |3\sqrt{3}\, t_2 \sin\phi|`) : Chern number `C = ±1` (sign set by `\mathrm{sgn}(\phi)`); one chiral edge mode per edge; quantized Hall conductance `σ_xy = C e²/h`. Diagnose by the BZ-integrated Berry curvature (Chern number), the ribbon edge spectrum, or the Hall conductance.
- Trivial band insulator (`|M| > |3\sqrt{3}\, t_2 \sin\phi|`) : `C = 0`; no chiral edge modes; `σ_xy = 0`.
- Transition (`M = ±3\sqrt{3}\, t_2 \sin\phi`) : one Dirac point closes, `C` jumps by `±1`.

### Canonical observables

- Bulk Bloch band structure / band gap at `K`, `K'`.
- Chern number `C` (BZ-integrated Berry curvature of the filled band).
- Hall conductance `σ_xy = C e²/h` (TKNN / Kubo).
- Ribbon edge-state spectrum (chiral, gap-traversing) and edge-mode chirality.

### Recommended methods

- Primary: **exact free-fermion diagonalization** — diagonalize the `2×2` Bloch Hamiltonian on a `k`-grid for the Chern number / bands, and the real-space ribbon for edge modes, `O(N³)`, per `method-property-map.md` C11 free-fermion row.
- Cross-check: **ED** small torus (Chern number from the many-body twisted-boundary response) as a sanity check; **DMRG/MPS** on cylinders or **VMC/iPEPS** for the interacting Haldane–Hubbard extension (where the free-fermion solution breaks and a sign problem appears).

### Key reference

[@hasan_2010_topological] — Hasan & Kane, "Colloquium: Topological insulators" (RMP 82, 3045, 2010): the authoritative all-details downloadable review. Section II.B.2 ("Graphene, Dirac electrons, Haldane model") develops the honeycomb Dirac structure, the complex-NNN staggered-flux term, the time-reversal-breaking gap, the Chern number, the chiral edge states, and the quantized Hall response in full — chosen over the (no-arXiv) original because it is downloadable and covers the model end-to-end. The defining paper is Haldane, Phys. Rev. Lett. **61**, 2015 (1988) (doi:10.1103/PhysRevLett.61.2015; predates arXiv).
Rendered: `./1002.3895_topological-insulators.md`.

### Benchmarks

- Topological criterion: `C = ±1` (QAH) for `|M| < |3\sqrt{3}\, t_2 \sin\phi|`, `C = 0` (trivial) otherwise (convention `H = t_1 Σ_⟨ij⟩ c†c + t_2 Σ_⟨⟨ij⟩⟩ e^{iφ} c†c + M Σ ξ_i n_i`) — Haldane 1988; reviewed in Hasan & Kane [@hasan_2010_topological].
- Quantized Hall conductance: `σ_xy = C e²/h = ±e²/h` in the topological phase, `0` in the trivial phase (TKNN integer).
- Bulk–boundary correspondence: a ribbon hosts exactly `|C| = 1` chiral edge mode per edge in the topological phase (none in the trivial phase) — the central self-consistency check.

## How it is studied / Operational

**Canonical defaults (Diagnose):** spinless fermions on the honeycomb lattice, two-site cell, parameters `(t_1, t_2, φ, M)` from the user's prompt (default `t_1 = 1, t_2 = 0.1, φ = π/2, M = 0` — deep in the QAH phase), half-filling (lower band filled), PBC `k`-grid for the Chern number plus a ribbon (width `W ≈ 20`, periodic along the ribbon) for the edge modes, target the band gap + Chern number + Hall conductance + edge spectrum. If only "Haldane model" is given, propose one topological (`|M| < 3\sqrt3 t_2 \sinφ`) and one trivial (`|M|` above the boundary) parameter set and contrast their Chern numbers and edge spectra. The model is quadratic → all of this is an exact `O(N³)` single-particle calculation; no variational or sampling method is needed.

| Regime | Method | Card |
|---|---|---|
| Chern number / bands / edge modes (any size) | exact free-fermion diagonalization (Bloch + ribbon, `O(N³)`) | `skills/method-ed/SKILL.md` (quadratic / single-particle) |
| Many-body Chern number cross-check (small torus, twisted BC) | ED | `skills/method-ed/SKILL.md` |
| Interacting Haldane–Hubbard (free-fermion solution breaks, sign-ful) | DMRG cylinders / VMC / iPEPS | `skills/method-mps/SKILL.md`, `skills/method-vmc/SKILL.md` |

Verification pointers:

- Limit checks: `t_2 = 0` or `φ = 0` → time-reversal restored, `C = 0` (trivial / gapless graphene if also `M = 0`); `M = 0, φ = π/2` → maximal topological gap. See `.knowledge/limits.md`.
- The bulk Chern number (PBC) must equal the number of chiral edge modes per edge in a ribbon (bulk–boundary correspondence) — the central self-consistency check.
- The integrated Berry curvature must be an integer (to numerical tolerance); a non-integer signals an insufficiently dense `k`-grid or a gap closing.
- Sweeping `M` across `3\sqrt3 t_2 \sinφ` must close the gap at one Dirac point and flip `C` by `±1` (a directed transition check).
