# Bose-Hubbard

Lattice bosons hopping with amplitude `t` and paying an on-site repulsion `U` per pair. The competition between kinetic delocalization and on-site repulsion drives the superfluid–Mott-insulator quantum phase transition — the canonical interacting-boson model and the workhorse of cold-atom optical-lattice experiments.

Distinct from `hubbard` (spinful fermions, Pauli exclusion, fermion sign problem): bosons have no spin index and a large/unbounded on-site occupation, and the model is **sign-free**, making it a QMC benchmark.

## Physics card

### Hamiltonian

$$ H = -t \sum_{\langle ij\rangle} \left( b^\dagger_i b_j + \text{h.c.} \right) + \frac{U}{2} \sum_i n_i (n_i - 1) - \mu \sum_i n_i $$

Conventions: soft-core bosons `b_i`, `n_i = b^\dagger_i b_i`; `t > 0` hopping (energy unit `t = 1`), `U > 0` on-site repulsion, `μ` chemical potential (fixes the filling). `⟨ij⟩` = NN bonds counted once. The local Hilbert space is truncated at a maximum occupation `n_max`, giving `d = n_max + 1` (converge `n_max` for the target filling). The **hard-core limit** (`U → ∞`, `d = 2`, at most one boson per site) maps exactly to the spin-1/2 XY/XXZ model and to spinless fermions via Jordan-Wigner. The control parameter is `t/U`; `μ` selects the Mott lobe / filling. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 1D chain · 2D square (`Z=4`) · 3D cubic (`Z=6`); any optical-lattice geometry | Each dimension has a well-characterized SF–Mott transition. |
| A2 boundary conditions | OBC (DMRG) · PBC (ED/QMC) · cylinder (2D DMRG); trap potential in experiments | A harmonic trap produces the "wedding-cake" shells of alternating SF/Mott regions. |
| A3 statistics & local dim | **soft-core boson**, local dim `d = n_max + 1` (truncated) | Hard-core limit `d = 2` maps to XY/XXZ; soft-core needs `n_max` convergence (cost `∝ d·χ³` in MPS). |
| A4 interaction range | short-range: NN hopping + on-site `U` (extended Bose-Hubbard adds NN `V`, giving supersolid/density-wave) | Local — area-law compatible. |
| B5 entanglement scaling | Mott (gapped): area law · superfluid (gapless): area-law-ish in 2D/3D, area+log in 1D (`c=1` Luttinger liquid) | 1D SF is a critical Luttinger liquid; gapped Mott is the cheap regime for tensor networks. |
| B6 spectral gap | **Mott insulator: gapped** (incompressible, charge gap `∝ U`) · **superfluid: gapless** (sound mode, compressible) | The Mott gap and compressibility `κ = ∂n/∂μ` are the order diagnostics. |
| B7 ground-state order | **superfluid** (off-diagonal long-range order, `⟨b^\dagger_i b_j⟩ → const`, condensate) ↔ **Mott insulator** (no ODLRO, integer filling, gapped) | The SF–Mott quantum phase transition; SF spontaneously breaks the U(1) phase. |
| B8 frustration | none on bipartite lattices; geometric frustration possible (triangular → frustrated/supersolid) | Bipartite Bose-Hubbard is unfrustrated and sign-free. |
| C9 global symmetry | **U(1) particle number** (`N = Σ n_i` conserved); the SF phase spontaneously breaks U(1) phase rotation | The conserved `N` blocks the Hamiltonian and is exploited by ED/DMRG/QMC. |
| C10 spatial symmetry | translation (`k`), point group, inversion/parity | Block-diagonalizes ED; Mott lobes respect translation, SF is uniform. |
| C11 integrability | 1D non-integrable (generic) — except the hard-core limit, which is free-fermion (Jordan-Wigner) | The hard-core point gives exact 1D benchmarks; the soft-core model needs full numerics. |
| C12 sign problem | **sign-free** (bosonic, positive worldline weights) on any lattice/filling | The defining advantage: worm-algorithm / SSE QMC is numerically exact at scale — the workhorse method. |
| D13 regime | ground state (`T=0`, SF–Mott phase diagram) default; finite-`T` (thermal SF, BKT in 2D) and real-time quench dynamics all standard | Cold-atom quench experiments probe SF→Mott dynamics directly. |
| D14 filling / doping | **commensurate (integer) filling → Mott insulator** at small `t/U`; **incommensurate filling → superfluid** | Mott lobes occur only at integer `n`; off-integer the system is always (compressible) SF. |
| D15 disorder | clean by default; on-site disorder + interactions → **Bose glass** (compressible, gapless, insulating) | The disordered Bose-Hubbard model is the canonical Bose-glass platform. |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- Superfluid : off-diagonal long-range order `⟨b^\dagger_i b_j⟩` (condensate fraction / superfluid stiffness `ρ_s`), gapless, compressible (`κ > 0`); spontaneously breaks U(1). Occurs at large `t/U` and at any incommensurate filling.
- Mott insulator : integer filling `n ∈ ℤ`, gapped (charge gap `Δ ∝ U`), incompressible (`κ = 0`), no ODLRO. Occurs in lobes at small `t/U` and commensurate filling.
- SF–Mott transition : two universality classes — the **Mott-lobe tip** (fixed integer density) is in the `(d+1)`D XY universality class with dynamical exponent `z=1`; the **generic lobe boundary** (density-changing) is mean-field-like with `z=2`.

### Canonical observables

- Energy per site `E/N`; density `n` and compressibility `κ = ∂n/∂μ` (zero in Mott, finite in SF).
- Single-particle correlator `⟨b^\dagger_i b_j⟩` / condensate fraction; superfluid stiffness `ρ_s` (winding number in QMC); momentum distribution `n(k)` (the experimentally imaged quantity).
- Mott gap `Δ = E(N+1) + E(N-1) - 2E(N)`; phase-boundary `(t/U)_c` of each lobe.

### Recommended methods

- Primary (any dimension, sign-free): **QMC** — worm-algorithm / SSE; numerically exact at large `N` and finite `T`, the standard benchmark for the SF–Mott phase diagram (per `method-property-map.md` §QMC, C12 sign-free).
- Primary (1D / ladders): **DMRG/MPS** — near-exact in 1D, U(1) `N` conservation; converge `n_max` and `χ` (§MPS).
- Cross-check: **ED** small-cluster oracle (fixed-`N` sector); **mean-field / Gutzwiller** for a quick phase-boundary sketch (becomes exact as `Z → ∞`).

### Key reference

[@bloch_2007_many] — Reviews of Modern Physics "Many-Body Physics with Ultracold Gases"; the all-details downloadable source for the Bose-Hubbard model in optical lattices — derives `H` from the continuum, lays out the SF–Mott transition and phase diagram, the Mott-lobe structure, mean-field/Gutzwiller treatment, and the experimental signatures (momentum distribution, the Greiner SF→Mott observation). (The defining theory paper is Fisher-Weichman-Grinstein-Fisher, PRB 40, 546 (1989); no arXiv preprint exists, so it would be a stub — this RMP review is preferred as the full-text source covering the same physics.)
Rendered: `./0704.3011_many-body-physics-with-ultracold-gases.md`.

### Benchmarks

- 1D, `n = 1` SF–Mott (Mott-lobe tip): `(t/U)_c ≈ 0.2974(3)` — DMRG (Kühner-White-Monien, PRB 61, 12474 (2000); consistent with Läuchli-Kollath). Convention `H = -t Σ(b†b+h.c.) + (U/2)Σ n(n-1)`.
- 2D square, `n = 1`: `(t/U)_c = (J/U)_c = 0.05974(3)` — worm-algorithm QMC (Capogrosso-Sansone et al., PRA 77, 015602 (2008)).
- 3D cubic, mean-field (Mott-tip estimate): `U_c/(z t) ≈ 5.83` at the `n=1` tip (`z = 6`), the Gutzwiller/strong-coupling result — exact-in-`Z→∞` baseline, corrected downward by fluctuations [@bloch_2007_many].

## How it is studied / Operational

**Canonical defaults (Diagnose):** soft-core bosons, `t = 1`, `t/U` from the prompt (default near the `n=1` transition for the chosen dimension), unit filling `n = 1` (or `μ` set to the `n=1` lobe), `n_max = 4–5` (converge), OBC for DMRG / PBC for QMC, `N` per method, target `E/N` + superfluid stiffness `ρ_s` / Mott gap to identify the phase. If only "Bose-Hubbard" is given, propose the `n=1` SF–Mott line and offer a `t/U`-scan across the transition or a `μ`-scan to map the Mott lobes.

| Regime | Method | Card |
|---|---|---|
| 2D/3D phase diagram, finite-`T`, large `N` (sign-free) | QMC (worm / SSE) | `skills/method-qmc/SKILL.md` |
| 1D chain / ladder, ground state, gap / `ρ_s` | DMRG | `skills/method-mps/SKILL.md` |
| Small cluster (`N ≲ 16`, fixed `N`), exact spectrum / cross-check | ED | `skills/method-ed/SKILL.md` |
| Quick SF–Mott phase boundary sketch | mean-field / Gutzwiller | `skills/method-mf/SKILL.md` |

Verification pointers:

- Limit checks: `U → ∞` hard-core (`n_max=1`) reproduces the XY/XXZ chain (1D) and the exact free-fermion energy; `t → 0` gives the atomic Mott limit with integer `n` fixed by `μ`.
- U(1) particle-number conservation; in QMC the superfluid stiffness is the winding-number fluctuation `ρ_s = ⟨W²⟩/(βt·dim)`, zero in the (incompressible) Mott phase.
- `n_max` convergence: increase the truncation until `E/N` and `ρ_s` are stable — essential for soft-core bosons near the SF side.
- Anchor against the benchmark `(t/U)_c` for the chosen dimension (1D `≈0.297`, 2D `≈0.0597`); a negative control is to confirm `κ = 0` (incompressible) deep in a Mott lobe and `κ > 0` in the SF. For the SF–Mott criticality / universality class, hand off to `criticality`.
