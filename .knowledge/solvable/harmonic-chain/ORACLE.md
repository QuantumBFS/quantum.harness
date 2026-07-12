# 1D harmonic chain — exact-solution oracle

Technique: T1 (free-particle / normal-mode diagonalization) · Tier: A (closed-form, exact) · Script: S

## Hamiltonian & conventions

$$ H = \sum_{i=1}^{L} \left[\frac{p_i^2}{2m} + \frac{\kappa}{2}\bigl(x_i - x_{i+1}\bigr)^2\right], \qquad \text{PBC } (x_{L+1}\equiv x_1) $$

Conventions: identical masses `m` on a ring of `L` sites, nearest-neighbor Hookean springs of constant `κ`, lattice constant `a = 1` (so momenta run over `k ∈ [0, 2π)`), `ħ = 1`. No model-zoo sibling under `.knowledge/models/` for this model — the closest cousin, `.knowledge/models/bose-hubbard`, is a different (interacting, lattice-boson) model; this card's oracle is the free-boson/phonon limit with no on-site interaction, no coupling needed. See `.knowledge/conventions.md`.

## Solvability statement

T1: `H` is already quadratic in `(x_i, p_i)` — a normal-mode (Fourier) transformation diagonalizes it exactly for any `L, κ, m`, giving a set of `L` independent harmonic oscillators of frequency `ω(k_n) = 2\sqrt{κ/m}\,|\sin(k_n/2)|`, `k_n = 2πn/L`. Everything reported here — the finite-`L` zero-point energy, its thermodynamic limit, and the sound speed — is exact. The model is exactly solvable in its entirety; there is no approximation anywhere. **Not exact:** nothing about this model is approximate. Exact quantities not implemented here (out of this card's ground-state-statics scope): finite-temperature phonon occupation `⟨n_k⟩ = 1/(e^{ω(k)/T}-1)` and the associated thermal energy/specific heat, real-space displacement–displacement correlators `⟨x_i x_j⟩` (a closed-form Bessel-function-type sum over `k`), and the classical-statistical-mechanics partition function (also exactly Gaussian) — all straightforwardly exact from the same normal-mode solution.

## Exact results

- Normal-mode dispersion (lattice constant 1): $\omega(k) = 2\sqrt{\kappa/m}\,\bigl|\sin(k/2)\bigr|$
- Finite-`L` zero-point energy per site (PBC, `k_n = 2\pi n/L`): $e_0(L) = \dfrac{1}{2L}\displaystyle\sum_{n=0}^{L-1}\omega(k_n)$
- Thermodynamic-limit zero-point energy per site: $e_0 = \dfrac{1}{2}\cdot\dfrac{1}{2\pi}\displaystyle\int_0^{2\pi}\omega(k)\,dk = \dfrac{2}{\pi}\sqrt{\kappa/m}$
- Sound speed (phonon-limit slope): $c_s = \lim_{k\to 0}\dfrac{\omega(k)}{k} = \sqrt{\kappa/m}$
- Full spectrum: `L` independent oscillators, $E = \sum_n \omega(k_n)\bigl(n_k + \tfrac12\bigr)$, `n_k ∈ ℤ_{≥0}` — exact for any excited state, not just the ground state (out of this card's scripted scope, but immediate from the normal-mode solution)

## Oracle script

`python oracle.py --L 4000 --kappa 1.0 --m 1.0` → prints `e0_per_site`, `e0_thermodynamic`, `sound_speed`. Importable: `compute(L=4000, kappa=1.0, m=1.0)`.
Self-test anchors: (1) finite-`L` zero-point sum at `L=4000` matches the thermodynamic closed form `2/π` to `1e-6` (the `|sin(k/2)|` cusp at `k=0 (mod 2π)` makes the Riemann-sum convergence rate `O(1/L²)`, not spectral, so `L=4000` is needed for `1e-6`); (2) independent path — diagonalizing the `L×L` PBC dynamical (spring) matrix `D` (`2κ/m` on the diagonal, `-κ/m` on the near off-diagonals and the PBC corners) reproduces the closed-form dispersion at `L=6` to `atol=1e-12` on `ω²` (the pre-`sqrt` eigenvalues; the translational zero mode is resolved by `eigvalsh` only to `~1e-16` absolute error, which `sqrt` amplifies to `~1e-8` — the script clips sub-`1e-10` numerical noise to exactly zero before the square root, since the zero mode is analytically exact by translational invariance); (3) the numerical slope `ω(k)/k` at small `k` converges to `√(κ/m)` to `1e-6`, checked at two independent `(κ, m)` points.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e0_thermodynamic` | `κ=m=1` | `2/π ≈ 0.636620` | normal-mode sum |
| `sound_speed` | `κ=m=1` | `1` | dispersion slope |
| Dynamical-matrix spectrum | `L=6, κ=m=1` | `{0, 1, 1, 3, 3, 4}` (`= ω²`) | eigenvalue check |
| `sound_speed` | `κ=2, m=0.5` | `2` | dispersion slope |

## Verification recipes

- To check a phonon-chain DMRG/QMC ground-state-energy run at size `L`, PBC: compare `e0_per_site` from `oracle.py --L <L> --kappa <κ> --m <m>`, tolerance `1e-8` (exact, up to the `O(1/L²)` finite-size Riemann-sum error already present in the exact `e0_per_site` definition itself — not a numerical-method error).
- To check a Bogoliubov-diagonalization or normal-mode-solver implementation on the same model: compare its returned frequencies against `ω(k) = 2\sqrt{κ/m}|\sin(k/2)|` directly at the solver's momenta, or against the dynamical-matrix eigenvalues built the same way as in `self_test`.
- To check the sound speed extracted from a finite-`L` dispersion fit: compare against `sound_speed = √(κ/m)`, tolerance set by how small the fitted `k`-window is (linear dispersion holds to `O(k²)` corrections).

## Key reference

[@Ashcroft1976] — Ashcroft & Mermin, *Solid State Physics* (1976), Ch. 22: the standard textbook derivation of the 1D harmonic-chain (monatomic lattice) normal-mode dispersion `ω(k) = 2\sqrt{κ/m}|\sin(ka/2)|` and its zero-point and thermodynamic properties, used throughout this card. Rendered: _(book — no PDF ingested)_.
