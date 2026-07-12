# 1D Anderson model — exact-solution oracle

Technique: T1 (free-particle / transfer matrix) · Tier: A (numerically exact) · Script: S

## Hamiltonian & conventions

$$ H = -t \sum_{i} \bigl(c^\dagger_i c_{i+1} + \text{h.c.}\bigr) \;+\; \sum_i \varepsilon_i\, n_i, \qquad \varepsilon_i \sim \mathrm{U}[-W/2,\,+W/2]\ \text{i.i.d.} $$

Conventions: spinless fermions, single-particle (one-body) problem — the "Hilbert space" is just the `L` lattice sites, not a many-body Fock space; `t > 0` nearest-neighbor hopping, `t = 1` the energy unit; on-site energies `ε_i` drawn i.i.d. from the box distribution of full width `W`, so `W/t = W` is the dimensionless disorder strength; `numpy.random.default_rng(seed)` (CLI param, default `seed = 1`) makes every draw reproducible. See `.knowledge/conventions.md`.

Physics card: `.knowledge/models/anderson-localization/MODEL.md`. That card writes the identical Hamiltonian `H = -t Σ(c†c+h.c.) + Σ ε_i n_i` with the same box-disorder convention (`ε_i ∈ [-W/2, W/2]`, `t = 1` energy unit) and identifies dimension as "the master axis": in 1D (this card's scope) *every* state is localized for any `W > 0` — there is no metal–insulator transition to find, only a localization length `ξ(E, W)` to compute. Conventions match exactly; no translation needed. The MODEL.md card's recommended primary tool for exactly this quantity is "transfer-matrix finite-size scaling" — this card *is* that computation, specialized to `d = 1` where no finite-size scaling in the bar width is needed (the Lyapunov exponent itself is already the `L → ∞` observable).

## Solvability statement

T1: in 1D, the tight-binding eigenvalue equation at energy `E` is equivalent to an `SL(2,ℝ)` transfer-matrix recursion `(ψ_{i+1}, ψ_i)^T = T_i (ψ_i, ψ_{i-1})^T` with `T_i = [[E - ε_i, -1], [1, 0]]`, `det T_i = 1`. By the Furstenberg theorem, the ordered product `T_N ⋯ T_1` grows almost surely as `e^{γN}` for a disorder-realization-independent (self-averaging) Lyapunov exponent `γ(E, W) > 0` whenever the disorder has a continuous, non-degenerate distribution — which the box distribution is. `γ` **is** the inverse localization length: `ξ_loc = 1/γ`. This script estimates `γ` by the standard QR (Benettin) algorithm on `n_steps = 10^6` transfer-matrix multiplications, re-orthogonalizing every 10 steps to avoid over/underflow; this is a numerically exact, non-perturbative estimator of a quantity that is *itself* exact in the `N → ∞` limit (finite `n_steps` gives a statistical estimate with `O(1/√n_steps)` sampling error, not a systematic bias, since disorder is self-averaging along the chain — no ensemble averaging over independent realizations is needed for a single long chain). **Not exact:** the *closed-form* `thouless_perturbative = W²/(96(1-(E/2)²))` reported alongside `lyapunov` is a second-order (Born) weak-disorder approximation [@Thouless1972] — valid only for `W ≪ 1` (in units of the `4t = 4` bandwidth) and *not* valid near the band edges `E → ±2` (where it diverges, `1-(E/2)² → 0`) or at the exact band center `E = 0` (band-center anomaly, below). `lyapunov` (the transfer-matrix output) is the exact quantity; `thouless_perturbative` is a cross-check formula, not a substitute.

## Band-center anomaly — why the anchor sits at `E = 0.5`

At exactly `E = 0` the weak-disorder perturbation theory behind `thouless_perturbative` breaks down: **backscattering at `k = π/2` is anomalously enhanced** because the two counter-propagating channels at the band center become resonant with each other at every order of the disorder expansion (Kappus & Wegner [@KappusWegner1981], discussed as the definitive weak-disorder correction in the transfer-matrix literature building on the Thouless formula [@Thouless1972]). The result is a genuine correction to the coefficient, not a higher-order tail: `γ(0, W) ≈ W²/105.2` for small `W`, roughly `9%` smaller than the naive extrapolation `W²/96` of the formula used elsewhere in the band. Because `self_test`'s tolerance band (`0.7×`–`1.4×` the perturbative formula) is generous enough to absorb this `~9%` shift, the *numerical* test would not actually catch a `thouless_perturbative` bug at `E = 0` — so the self-test anchor is deliberately placed at `E = 0.5`, safely inside the regular band (away from both the `E = 0` anomaly and the `E = ±2` band-edge divergence), where the leading-order Thouless formula is expected to hold to the stated tolerance. Users who need `γ(E=0, W)` should use the Kappus–Wegner-corrected coefficient, not `thouless_perturbative`, and users who need any `γ` at strong disorder (`W ≳ t`, where `thouless_perturbative` is not even qualitatively reliable — see below) should trust only `lyapunov`.

## Exact results

- Localization length is the inverse Lyapunov exponent of the transfer-matrix product: $\xi_{\text{loc}}(E,W) = 1/\gamma(E,W)$, numerically exact (Furstenberg) for any `E, W`
- Weak-disorder (`W ≪ t`) perturbative Lyapunov exponent, box disorder: $\gamma(E,W) \approx \dfrac{W^2}{96\left(1-(E/2)^2\right)}$, from `σ² = W²/12` (box-distribution variance) and $\gamma(E) = \sigma^2/(8\sin^2k)$, $E = 2\cos k$ [@Thouless1972]
- Band-center anomaly: $\gamma(0, W) \approx W^2/105.2$ for small `W`, not `W²/96` [@KappusWegner1981]
- Every eigenstate is exponentially localized for any `W > 0` (no metal–insulator transition exists in 1D, orthogonal class) [@Ashcroft1976]

## Oracle script

`python oracle.py --E 0.5 --W 1.0 --n_steps 1000000 --seed 1` → prints `lyapunov`, `xi_loc`, `thouless_perturbative`. Importable: `compute(E=0.5, W=1.0, n_steps=10**6, seed=1)`.
Self-test anchors: (1) at `E=0.5, W=1.0`, the numerically exact `lyapunov` lands within `0.7×`–`1.4×` of `thouless_perturbative` (the perturbative formula is only leading-order, so a loose band, not a tight tolerance, is the correct check); (2) stronger disorder localizes harder: `lyapunov(W=2.0) > lyapunov(W=1.0)` at fixed `E`; (3) reproducibility: identical `(E, W, n_steps, seed)` gives an exactly identical `lyapunov` (no unseeded randomness).

## Benchmarks

| Quantity | Params | Value | Source |
|---|---|---|---|
| `lyapunov` | `E=0.5, W=1.0, n_steps=10^6, seed=1` | `≈ 0.0111` (within `0.7–1.4×` of `thouless_perturbative`) | self-test |
| `thouless_perturbative` | `E=0.5, W=1.0` | `1/90 ≈ 0.01111` | [@Thouless1972] |
| `γ(E=0, W)` (band-center anomaly) | `W → 0` | `≈ W²/105.2`, not `W²/96` | [@KappusWegner1981] |
| Localization at any `W>0`, 1D | all `E, W` | every eigenstate exponentially localized | [@Ashcroft1976] |

## Verification recipes

- To check a transfer-matrix / recursive Green's-function localization-length calculation at `(E, W)`: compare `xi_loc` from `oracle.py --E <E> --W <W>`, using a matched or larger `n_steps` (statistical error shrinks as `1/√n_steps`; `n_steps=10^6` gives ξ_loc typically good to `<1%`).
- To check a weak-disorder analytic estimate: compare against `thouless_perturbative`, but only for `W ≪ t` and `E` away from `0` and `±2` — see the anomaly note above.
- To check finite-size numerics (exact diagonalization at moderate `L`, IPR/participation-ratio localization-length estimates): the transfer-matrix `xi_loc` is the `L → ∞` reference value; finite-`L` estimates should approach it as `L` grows past a few `ξ_loc`.

## Key reference

[@Thouless1972] — Thouless, "A relation between the density of states and range of localization for one dimensional random systems", J. Phys. C: Solid State Phys. **5**, 77 (1972): derives the weak-disorder Lyapunov-exponent formula used here as `thouless_perturbative`, and is the standard citation for the perturbative (Born) result away from the band-center anomaly. Rendered: _(Wave 3)_.
