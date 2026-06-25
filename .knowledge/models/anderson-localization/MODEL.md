# Anderson Localization

A **single non-interacting particle** hopping on a tight-binding lattice with random on-site energies (Anderson 1958). The defining phenomenon is the **localization–delocalization (metal–insulator) transition**: disorder can turn extended Bloch states into exponentially localized eigenstates. **Dimensionality is the master axis** — in 1D and 2D (orthogonal class) *all* states localize for any disorder, while in 3D there is a genuine mobility edge / metal–insulator transition at finite disorder. This is the single-particle ancestor of many-body localization.

## Physics card

### Hamiltonian

$$ H = -t \sum_{\langle ij\rangle}\bigl(c^\dagger_i c_j + \text{h.c.}\bigr) \;+\; \sum_i \varepsilon_i\, n_i, \qquad \varepsilon_i \in [-W/2,\,+W/2]\ \text{i.i.d. uniform} $$

Conventions: `t > 0` nearest-neighbor hopping, set `t = 1` as the energy unit; on-site energies `ε_i` are independent random variables, the canonical choice being the **box distribution** of full width `W` (`ε_i∈[-W/2,W/2]`), so `W/t` is the dimensionless disorder strength (Gaussian or Lorentzian/Cauchy disorder are common alternatives — note the distribution and width convention when comparing `W_c`). **This is a single-particle problem**: although the local dimension per site is 2 (empty/occupied), there is no many-body Hilbert space — `H` is an `L^d × L^d` real symmetric (orthogonal class) matrix and is diagonalized directly. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | **dimension is THE master axis**: 1D / 2D / 3D (hyper)cubic, `Z=2d` | 1D & 2D (orthogonal): all states localized for any `W>0` (lower critical dimension `d_c=2`); 3D: extended states + mobility edge → metal–insulator transition. Nothing about this model matters more than `d`. |
| A2 boundary conditions | OBC · PBC · quasi-1D bars / cylinders (transfer-matrix MacKinnon–Kramer) | Transfer-matrix finite-size scaling on long quasi-1D bars of cross-section `M^{d-1}` is the workhorse for the 3D transition. |
| A3 statistics & local dim | **a single non-interacting fermion** (`d=2` per site formally, but no many-body space) | The "Hilbert space" is just the `L^d` lattice sites; cost is polynomial (`O(L^{3d})` dense, far less with sparse/transfer methods), not exponential. |
| A4 interaction range | short-range (nearest-neighbor hopping) · long-range hopping `1/r^a` is a studied variant (power-law random banded matrices) | NN hopping with on-site disorder is the standard Anderson model; long-range hopping can change the critical dimension. |
| B5 entanglement scaling | n/a in the many-body sense (single particle). Eigenfunctions: **exponentially localized** (localized phase) with localization length `ξ`; extended/critical at the mobility edge | The relevant "size" is the localization length `ξ` and the multifractal wavefunction structure at criticality, not entanglement entropy. |
| B6 spectral gap | gapless single-particle band; the key feature is the **mobility edge** `E_c` separating localized (band tails) from extended (band center) states (3D) | `E_c` moves with `W`; when `E_c` sweeps through the Fermi energy the system undergoes the Anderson metal–insulator transition. |
| B7 ground-state order | no symmetry-breaking order — the transition is between an **Anderson insulator** (localized, exponentially small DC conductivity) and a **diffusive metal** (extended) | Order parameter ≈ the typical (geometric-mean) local density of states / inverse participation ratio, not a Landau order parameter. |
| B8 frustration | none (single particle, bipartite hypercubic lattice) | Disorder, not frustration, is the only complication. |
| C9 global symmetry | U(1) (single-particle number) — but the decisive structure is the **symmetry class**: orthogonal (time-reversal, no SOC), unitary (broken T, e.g. magnetic field), symplectic (T + spin–orbit) | The Wigner-Dyson class controls the critical behavior and whether 2D can delocalize (unitary/symplectic classes can; orthogonal cannot). |
| C10 spatial symmetry | none per realization (disorder breaks translation); statistical translation/isotropy after disorder averaging | Each sample is inhomogeneous; observables are averaged or, better, characterized by their full distribution (broad at criticality). |
| C11 integrability | **non-interacting → directly diagonalizable** (`O(L^{3d})` dense; sparse/transfer-matrix/kernel-polynomial much cheaper) | There is no many-body correlation to capture — the entire physics is the localization of single-particle eigenfunctions, accessible from the one-body matrix. |
| C12 sign problem | n/a (single particle, no Monte Carlo over a many-body amplitude) | Studied by exact one-body diagonalization, transfer matrices, kernel-polynomial DOS, and the self-consistent / supersymmetric field theories. |
| D13 regime | eigenstates and single-particle spectrum (`T=0` localization properties); conductance/transport via Landauer / Kubo | One asks where states localize and how the conductance scales with system size, not a finite-`T` many-body quantity. |
| D14 filling / doping | the **Fermi energy / mobility edge** position sets metal vs insulator (3D); tuning `E_F` across `E_c` is the transition | Filling matters only through which single-particle states are occupied relative to `E_c`. |
| D15 disorder | **quenched on-site disorder is the defining axis** — the localization–delocalization transition is tuned by `W` (and `d`, and symmetry class) | Requires averaging over realizations; distributions are broad and **non-self-averaging at criticality** (typical ≠ mean) — use geometric means / finite-size scaling. |
| D16 hermiticity | Hermitian / closed | Non-Hermitian Anderson models (e.g. Hatano–Nelson, imaginary gauge field) are a distinct, actively-studied variant with a different (skin-effect) localization transition. |

### Phases & order parameters

- Extended / metallic phase (3D, weak disorder, near band center) : Bloch-like wavefunctions spread over the whole sample; finite DC conductivity; level statistics Wigner-Dyson (GOE for orthogonal class).
- Localized / Anderson-insulator phase (1D & 2D any `W`; 3D strong `W` or band tails) : eigenfunctions decay as `e^{-r/ξ}`; vanishing DC conductivity; Poisson level statistics.
- Mobility edge `E_c` (3D) : separates the two within a single spectrum; at the critical point wavefunctions are **multifractal** (a continuous set of exponents `τ_q`/`f(α)`), level statistics are scale-invariant ("critical statistics").
- Diagnostics: inverse participation ratio / participation entropy, localization length `ξ` from transfer matrices, typical DOS (geometric mean), Thouless/dimensionless conductance `g`, and the multifractal spectrum at the transition.

### Canonical observables

- Localization length `ξ(W, E)` from transfer-matrix Lyapunov exponents on quasi-1D bars; finite-size scaling of `Λ = ξ_M/M` (the MacKinnon–Kramer ratio whose `M`-flow direction distinguishes metal from insulator).
- Inverse participation ratio `P_2 = Σ_i |ψ_i|^4` and its disorder average / multifractal exponents `τ_q` at the mobility edge.
- Dimensionless (Thouless) conductance `g` and its scaling β-function (the basis of the scaling theory of localization).
- Typical (geometric-mean) local density of states — the natural order parameter that vanishes at localization.

### Recommended methods

- Primary (3D transition): **transfer-matrix finite-size scaling** on long quasi-1D bars (cross-section `M^{d-1}`), extracting `Λ=ξ_M/M` and fitting the crossing / scaling to get `W_c` and `ν`. The classic high-precision route (not a many-body harness solver; a one-body linear-algebra calculation).
- Primary (eigenstates/DOS): **exact one-body diagonalization** (dense `O(L^{3d})` for IPR/multifractality on modest `L`; **sparse / kernel-polynomial / shift-invert** for the DOS and interior states on large `L`). This is "ED" applied to the `L^d` one-body matrix — polynomial, not `d^N`.
- Cross-check: **Kubo / Landauer conductance** (recursive Green's function) for transport; level-spacing statistics (Wigner-Dyson vs Poisson) as an independent localization diagnostic; self-consistent theory of localization / supersymmetric σ-model for analytic guidance.

### Key reference

[@evers_2007_anderson] — Evers & Mirlin, "Anderson transitions" (Rev. Mod. Phys. 80, 1355, 2008): the authoritative downloadable all-details review — the scaling theory of localization, the full symmetry-class classification (Wigner-Dyson, chiral, Bogoliubov–de Gennes), critical exponents, multifractality of wavefunctions at the mobility edge, and the σ-model field theory.
Rendered: `./0707.4378_anderson-transitions.md`.

### Benchmarks

- 3D Anderson model, box disorder, band center (`E=0`), orthogonal class: critical disorder `W_c ≈ 16.5 t` — the standard transfer-matrix value (Slevin–Ohtsuki, Phys. Rev. Lett. 82, 382 (1999); MacKinnon–Kramer) [@evers_2007_anderson].
- 3D orthogonal-class localization-length (correlation-length) exponent `ν ≈ 1.57 ± 0.02` — the high-precision transfer-matrix finite-size-scaling result quoted in the review [@evers_2007_anderson] (contrast the `ε`-expansion `ν≈1`, noted there as asymptotically inaccurate).
- 2D orthogonal class: **all states localized for any `W>0`** (no transition), from the one-parameter scaling theory (Abrahams, Anderson, Licciardello & Ramakrishnan, Phys. Rev. Lett. 42, 673 (1979); `d_c=2`); the unitary and symplectic classes *can* support a 2D transition [@evers_2007_anderson].

## How it is studied / Operational

**Canonical defaults (Diagnose):** single-particle tight-binding Anderson model, box disorder of width `W`, hopping `t=1`, **orthogonal class** (no field, no spin–orbit). Default question = "is the system localized?", answered by dimension: for **3D** propose a transfer-matrix `Λ=ξ_M/M` scan in `W` across `W_c≈16.5` (bars of growing `M`) to locate the transition and extract `ν`; for **1D/2D orthogonal** the answer is "localized for all `W>0`" — verify by exponential eigenfunction decay / `ξ(W)` rather than searching for a transition. If only "Anderson localization" is given, ask/assume the dimension first (it determines everything) and default to 3D for a transition study.

| Regime | Method | Card |
|---|---|---|
| 3D mobility edge / `W_c` / `ν` (transfer-matrix FSS) | one-body transfer matrix + scaling | `skills/method-ed/SKILL.md` (one-body linear algebra) |
| Eigenstates, IPR, multifractality (modest `L^d`, dense) | one-body diagonalization | `skills/method-ed/SKILL.md` |
| DOS / interior states at large `L` (sparse / kernel-polynomial / shift-invert) | one-body sparse eigensolver | `skills/method-ed/SKILL.md` |
| Conductance / Landauer transport | recursive Green's function (Kubo/Landauer) | `skills/method-ed/SKILL.md` |

Verification pointers:

- State the **dimension and symmetry class** up front — they decide whether a transition even exists (1D/2D orthogonal: none; 3D: yes; 2D unitary/symplectic: possible). This is the single most common source of error.
- Average over disorder realizations and use **typical (geometric-mean)** quantities and full distributions; near criticality observables are non-self-averaging, so report distributions / finite-size-scaling crossings, not a single sample mean.
- Negative/positive controls: at `W=0` all eigenstates are extended Bloch waves (`ξ→∞`); at very large `W` every eigenstate is localized on essentially one site (`ξ→0`). The `Λ=ξ_M/M` flow should *increase* with `M` in the metal and *decrease* in the insulator — opposite flows bracket `W_c`.
- Convergence: extrapolate transfer-matrix Lyapunov exponents to the target relative error, and check that the `W_c`/`ν` fit is stable as small-`M` data and irrelevant-scaling corrections are added/removed.
