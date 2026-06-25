# Falicov–Kimball

Itinerant `c`-electrons interacting with localized, immobile `f`-electrons via an on-site repulsion. The simplest correlated lattice model with a metal–insulator transition and charge-density-wave order; exactly solvable by dynamical mean-field theory in infinite dimensions, and free of the fermion sign problem because the `f`-configuration is static.

## Physics card

### Hamiltonian

$$ H = -t \sum_{\langle ij\rangle} \left( c^\dagger_i c_j + \text{h.c.} \right) + U \sum_i n^c_i\, n^f_i $$

Conventions: `t > 0` hopping of the itinerant `c`-electrons (energy unit `t = 1`, often `t* = 1` after the DMFT `1/√Z` scaling); `U > 0` on-site `c`–`f` Coulomb repulsion; the `f`-electrons have **no hopping** (localized, immobile), so each `n^f_i ∈ {0,1}` is a static (classical) occupation. `⟨ij⟩` = nearest-neighbor bonds counted once. The spinless version is shown; with spin the `c`-site dimension is 4. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 1D chain / 2D square (`Z=4`) / 3D / `Z→∞` (DMFT — exact) | The infinite-dimensional limit is exactly solvable (DMFT); finite-D studied by Monte Carlo over `f`-configs. |
| A2 boundary conditions | PBC / OBC (finite clusters) · infinite (DMFT, Bethe / hypercubic DOS) | DMFT works directly in the thermodynamic limit. |
| A3 statistics & local dim | itinerant `c` (spinless `d_c = 2`; `d_c = 4` with spin) **plus** a classical static `f`-occupation `{0,1}` per site | The `f`-electrons are not a quantum degree of freedom in the dynamics — a classical Ising-like variable. |
| A4 interaction range | short-range: on-site `c`–`f` repulsion `U` + NN `c`-hopping | Local. |
| B5 entanglement scaling | the `c`-subsystem (for a fixed `f`-config) is a free-fermion area-law state; the full model = classical average over `f`-configurations | No genuine `c`–`f` entanglement growth — the `f`-config is a conserved classical field. |
| B6 spectral gap | metal at small `U` · `c`-spectral (Mott-like) gap opens at large `U` (band splits into lower/upper Hubbard-like sub-bands) | The metal–insulator feature is driven by `U`; at half-filling the CDW also gaps the spectrum at low `T`. |
| B7 ground-state order | half-filling, bipartite, low `T`: **checkerboard charge-density wave** (staggered `f`-occupation) · large `U`: Mott-like insulator | The simplest correlated model with both a CDW transition and a metal–insulator transition. |
| B8 frustration | none on bipartite lattices (checkerboard CDW); geometric frustration of the `f`-arrangement on non-bipartite lattices | The `f`-config ordering can be frustrated by lattice geometry. |
| C9 global symmetry | `c`-charge U(1) **plus** each `n^f_i` separately conserved → **extensively many conserved quantities** (`f`-electrons are static) | The macroscopic set of conserved `n^f_i` is the model's defining structural feature (`[H, n^f_i] = 0` for all `i`). |
| C10 spatial symmetry | translation (`k`), point group (`D_4` square), inversion; sublattice (bipartite) for the checkerboard CDW | The CDW spontaneously breaks the sublattice (translation) symmetry. |
| C11 integrability | **exactly solvable in infinite dimensions (DMFT)** — Brandt–Mielsch / Freericks–Zlatić | The `Z→∞` self-energy is local and the impurity problem closes exactly; finite-D is not integrable but is sign-free. |
| C12 sign problem | **sign-free**: the static `f`-configuration reduces the quantum problem to a classical Monte Carlo over `f`-configs (each config = a free-fermion `c`-determinant, manifestly positive) | No fermion sign — the `f`-config sum is a classical statistical-mechanics problem. |
| D13 regime | ground state and **finite-T** (the CDW ordering temperature `T_c` is a central target); real-time / spectral via DMFT | Finite-T phase diagram (CDW `T_c(U)`) and the `T=0` MIT are the canonical targets. |
| D14 filling / doping | half-filling (`ρ_c = ρ_f = ½`) → checkerboard CDW, symmetric reference; doping the `c` or `f` density changes the ordered pattern / melts the CDW | Both `c`-filling and `f`-filling are control axes. |
| D15 disorder | clean by default; an annealed/quenched random `f`-config maps the model onto a binary-alloy / Anderson-disorder problem | The `c`-electrons effectively see the `f`-config as a (self-consistent) disorder potential. |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- Checkerboard charge-density wave (half-filling, bipartite, `T < T_c`) : staggered `f`-occupation (`f`-electrons localize on one sublattice) — order parameter is the staggered `f`-density / CDW structure-factor peak `S_f(π,…)`; also gaps the `c`-spectrum.
- Homogeneous metal (small `U`, `T > T_c`) : disordered `f`-config, metallic `c`-band.
- Mott-like insulator (large `U`) : the `c`-density of states splits into lower/upper sub-bands separated by a `U`-driven gap — metal–insulator transition with `U`.

### Canonical observables

- `c`-electron spectral function `A(ω)` / density of states (DMFT) — band splitting / MIT.
- CDW order parameter (staggered `f`-density) and structure factor `S_f(q)`; ordering temperature `T_c(U)`.
- Ground-state energy; `f`-occupation pattern; `c`-charge gap.
- Static / dynamic charge susceptibility (CDW instability).

### Recommended methods

- Primary (high-D / local self-energy): **DMFT** — exact in `Z→∞`; gives the `c`-spectral function, the metal–insulator transition, and the CDW transition analytically/numerically (per `method-property-map.md` A1 `Z→∞` row).
- Primary (finite D, exact): **classical Monte Carlo over `f`-configurations** — for each `f`-config diagonalize the free-fermion `c`-Hamiltonian (a positive weight); sign-free, numerically exact at scale (§C12).
- Cross-check: **ED** on small clusters (enumerate `f`-configs exactly); free-fermion `c`-diagonalization for any fixed `f`-config.

### Key reference

[@freericks_2003_exact] — Freericks & Zlatić, "Exact dynamical mean-field theory of the Falicov–Kimball model" (the RMP review): the all-details source for the DMFT solution, the formalism, the CDW transition, and the metal–insulator physics. (arXiv preprint cond-mat/0301188; published RMP 75, 1333 (2003).)
Rendered: `./cond-mat-0301188_exact-solution-of-the-falicov-kimball-model-with-dynamical-m.md`.

### Benchmarks

- Half-filling, bipartite, `T=0`: ground state is the **checkerboard CDW** (`f`-electrons occupy one sublattice) for any `U>0` — exact for the infinite-D / bipartite case (Brandt–Mielsch; reviewed in [@freericks_2003_exact]).
- Finite-T: a CDW ordering temperature `T_c(U)` separates the ordered checkerboard phase from the disordered phase; `T_c` is non-monotonic in `U` (rises then falls, peaking at intermediate `U`) — DMFT result [@freericks_2003_exact].
- Large `U`: the `c`-density of states splits into lower and upper sub-bands separated by a gap `≈ U` (metal–insulator transition) — exact DMFT spectral function [@freericks_2003_exact] (convention `H = −tΣc†c + U Σ n^c n^f`).

## How it is studied / Operational

**Canonical defaults (Diagnose):** spinless `c`-band, half-filling (`ρ_c = ρ_f = ½`), `U/t` from the user's prompt (default `U/t = 2` — intermediate), bipartite lattice (square in 2D, or DMFT for the exact infinite-D limit), target the CDW order parameter + `c`-spectral gap (or `T_c` if finite-T). If only "Falicov–Kimball" is given, propose the half-filled bipartite case via DMFT (exact) or finite-D Monte-Carlo-over-`f`-configs, and offer a `U` scan across the metal–insulator transition. Exploit that the `f`-config is static and sign-free — for any fixed config the `c`-problem is a free-fermion determinant.

| Regime | Method | Card |
|---|---|---|
| Infinite-D / local self-energy — spectral function, MIT, CDW `T_c` | DMFT (exact) — surface explicitly (out of current install scope) | — |
| Finite-D, exact — CDW order, energies, `T_c` | classical Monte Carlo over `f`-configs (free-fermion `c`-determinant per config, sign-free) | `skills/method-qmc/SKILL.md` |
| Small cluster — enumerate `f`-configs exactly | ED | `skills/method-ed/SKILL.md` |

Verification pointers:

- Limit checks: `U = 0` → free `c`-band + decoupled `f`-electrons (any `f`-config degenerate); `t = 0` (atomic limit) → trivial site occupations; `U → ∞` half-filling → frozen checkerboard `f`-pattern. See `.knowledge/limits.md`.
- Symmetry: each `n^f_i` must be exactly conserved (`[H, n^f_i] = 0`) — the static-`f` structure is the defining check; `c`-charge U(1) conserved.
- Sign-free verification: every `f`-configuration yields a positive (free-fermion) weight — no Monte Carlo sign should appear; confirm before trusting averages.
- Half-filling benchmark: the `T=0` ground state on a bipartite lattice must be the checkerboard CDW; the `c`-spectral gap should grow with `U`.
