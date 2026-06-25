# J1-J2

Solve J1-J2 spin-model ground-state problems. Competing nearest- and next-nearest-neighbor couplings make the regime `J2/J1 ≈ 0.5` (square lattice) one of the canonical hard / contested benchmarks in QMB.

## Physics card

### Hamiltonian

$$ H = J_1 \sum_{\langle ij\rangle} \mathbf{S}_i\cdot\mathbf{S}_j + J_2 \sum_{\langle\langle ij\rangle\rangle} \mathbf{S}_i\cdot\mathbf{S}_j $$

Conventions: `S`-operator normalization, `⟨ij⟩` nearest-neighbor and `⟨⟨ij⟩⟩` next-nearest-neighbor (diagonal) bonds, each counted once; `J_1, J_2 > 0` AFM; `J_1 = 1` sets the scale, `g ≡ J_2/J_1` is the control parameter. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 2D square lattice (`Z=4` NN + 4 NNN); also 1D zigzag chain | NNN couplings span both sublattices, breaking bipartiteness for QMC. |
| A2 boundary conditions | cylinder (2D DMRG default) · torus (ED) · OBC | Cylinder wrapping/width strongly affects the intermediate regime. |
| A3 statistics & local dim | spin-1/2; `d = 2` | Default S=1/2; the contested regime is specific to S=1/2. |
| A4 interaction range | short-range (NN + NNN) | Still local, but two competing couplings. |
| B5 entanglement scaling | ordered phases: 2D area law · intermediate `g≈0.5`: enhanced/area-violating (candidate gapless QSL → power-law) | Entanglement growth in the window is what makes it method-limited. |
| B6 spectral gap | Néel/stripe: gapless (Goldstone) over ordered GS · intermediate: gapped Z2 vs gapless U(1) QSL — unresolved | Order-of-gap in the window is part of the open question. |
| B7 ground-state order | `g≲0.4` Néel SSB · `g≳0.6` stripe (collinear) SSB · `g≈0.5` candidate spin liquid / VBS (contested) | Two ordered phases flank a debated nonmagnetic window. |
| B8 frustration | interaction-driven (competing `J_1` vs `J_2`) | The canonical interaction-frustrated benchmark. |
| C9 global symmetry | SU(2) (total `S`), U(1) (`S^z_tot`) | Isotropic Heisenberg couplings → full SU(2). |
| C10 spatial symmetry | translation, `C_4v` point group; stripe phase breaks `C_4 → C_2` | Lattice-rotation breaking is a stripe-order diagnostic. |
| C11 integrability | non-integrable | No exact solution at any `g≠0`. |
| C12 sign problem | severe (frustration breaks the Marshall sign rule) | QMC blocked → DMRG/PEPS/VMC + PolyOpt bounds. |
| D13 regime | ground state (`T=0`) | Phase identification is the goal. |
| D14 filling / doping | N/A (spin model) | — |
| D15 disorder | clean by default | — |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- Néel (`g ≲ 0.4`) : staggered magnetization `m_s`, structure-factor peak at `(π,π)`.
- Stripe / collinear (`g ≳ 0.6`) : peak at `(π,0)`/`(0,π)`, breaks `C_4` lattice rotation.
- Intermediate `g ∈ [0.45,0.55]` (frontier) : candidate gapless U(1) spin liquid vs gapped Z2 vs valence-bond solid — diagnose with `spin-liquid`; dimer order parameter / VBS structure factor and entanglement spectrum.

### Canonical observables

- `E/N`; spin structure factor `S(q)` (locating `(π,π)` vs `(π,0)` peaks).
- Order parameters `m_s` (Néel), stripe magnetization, VBS/dimer order parameter.
- Entanglement entropy / spectrum (cylinder topological-degeneracy diagnostics).

### Recommended methods

- Primary: **DMRG on cylinders** + **PEPS/iPEPS** — frustration sign-blocks QMC, so tensor networks carry the load in 2D (per `method-property-map.md` B8/C12 gate).
- Cross-check: **VMC/NQS** (variational upper bound, compare ansatz families); **ED** on `N ≤ 40` clusters; **PolyOpt** for a certified lower bound. Cross-method disagreement in the window is a known, reportable phenomenon — do not average it away.

### Key reference

[@morita_2014_quantum] — many-variable VMC with quantum-number projection mapping the full square-lattice `J_1`–`J_2` phase diagram; a canonical, downloadable entry into the contested intermediate-regime debate.
Rendered: `./1410.7557_quantum-spin-liquid-in-spin-1-2-j1-j2-heisenberg-model-on-sq.md`.

### Benchmarks

- Phase boundaries (square lattice, S=1/2): Néel for `g ≲ 0.4`, nonmagnetic window `g ∈ ~[0.4, 0.6]`, stripe for `g ≳ 0.6` (Morita, Kaneko, Imada, J. Phys. Soc. Jpn. 84, 024720 (2015)).
- Limit `g = 0`: reduces to NN square Heisenberg, `E/N ≈ −0.6694` (Sandvik QMC benchmark) — a built-in limit check.

## Diagnose

Infer setup from the user's prompt and propose for ratification.

**Canonical defaults:** square lattice, S=1/2, J1=1 AFM, J2/J1 from the user's prompt (if not given, ask this one question — it defines the physics entirely). OBC cylinder Ly=4, target E/N + structure factor.

**Proposal pattern:** "Going with: square lattice, S=1/2, J1=1, J2/J1=[value], cylinder Ly=4 Lx=12, target E/N + structure factor. Override any, or pick: pending ED small cluster (N≤32), Néel-regime check (J2/J1<0.4), intermediate-regime diagnostic (J2/J1≈0.5 → routes to spin-liquid)."

Build per `.knowledge/conventions.md`: `H = J1 Σ S_i·S_j + J2 Σ S_i·S_j` (NN+NNN).

## Workflow

1. Set up the Hamiltonian; pin sector via `S^z_total = 0` (singlet) for AFM finite-N.
2. Pick method per the table.
3. Short first run on a small cluster or narrow cylinder; confirm conservation laws and sign convention.
4. Sweep bond dim (DMRG) or extend cylinder width; track the target observable.
5. Verify (next section).
6. If user is asking about spin-liquid candidacy or phase classification, hand off via the branch table.

## Method recommendations

| Regime | Method | Card |
|---|---|---|
| Small cluster (N ≲ 32), exact comparison | ED | `skills/method-ed/SKILL.md` |
| Narrow cylinder (`L_y` ≲ 8) | DMRG | `skills/method-mps/SKILL.md` |
| Imaginary-time route to ground state | TEBD | `skills/method-mps/SKILL.md` |
| Wide-cylinder / 2D thermodynamic limit | Beyond current scope. Surface uncertainty; report what cylinder DMRG + ED constrain. | — |
| Frustrated 2D variational (VMC / NQS) | VMC via NetKet; compare ansatz energies. Requires `make install netket`. | `skills/method-vmc/SKILL.md` |

## Branch table

| Condition | Action |
|---|---|
| `J2/J1 ∈ [0.45, 0.55]` (intermediate regime) | Continue here for setup; the question is almost certainly about phase identification — call `spin-liquid` for the diagnostic. |
| User wants the source of frustration explained | Call `frustration`. |
| User wants critical-point characterization (deconfined criticality, Z2 transition) | Call `criticality` after running. |
| `J2/J1 → 0` | Reduces to NN Heisenberg; switch to `heisenberg` if the user is no longer in the J2-relevant regime. |

## Verification

Default checks:

- **Limit checks** via `.knowledge/limits.md`: `J2 = 0` → NN Heisenberg (compare to the published square-lattice value if available); `J1 = 0` → decoupled sublattices (each is NN Heisenberg).
- **Symmetry**: total `S^z = 0` for AFM; lattice point group respected.
- **Convergence**: bond-dim sweep + cylinder-width comparison. For the intermediate regime, document both — the answer often depends on the geometry choice.
- **Internal consistency**: variance, sub-leading bond-dim corrections.
- **Cross-method validation** (when feasible) — compare across cylinder geometries (`L_y` and wrapping); use an ED cross-check via `/method-ed`. Disagreement on the intermediate regime is a known phenomenon — document, don't average it away. See AGENTS.md "Verification practice".

Optional check:

- For canonical `J2/J1` regimes (Néel at small `J2`, stripe at large `J2`), compare to ranges in the published literature. **For `J2/J1 ≈ 0.5`, do not claim a literature match**: the field has not closed the question. Report your converged value, your sizes, and the active uncertainty.

## Frontier flag

The intermediate regime `J2/J1 ∈ [0.45, 0.55]` on the square lattice is among the canonical open problems in QMB. Competing claims (gapless U(1) spin liquid, gapped Z2, valence-bond crystal) coexist in the literature, with the answer often depending on geometry, sizes, and method. **Do not claim closure in this regime.**

When the user is in a frontier regime, search recent literature with a tailored query (e.g., `J1-J2 square spin liquid`, `J1-J2 deconfined criticality`) to surface the current debate before interpreting your evidence. Then call `spin-liquid` for the diagnostic and `criticality` if a transition is being characterized.

## Writeup handoff

After verification, if the user wants to communicate the result, consolidate to a runnable script + short run report, then render it via `/report`. See AGENTS.md "Writeup handoff".

## Related skills

`heisenberg` (J2 = 0 reduction), `frustration`, `spin-liquid`, `criticality`.
