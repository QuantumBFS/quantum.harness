# Lieb–Liniger gas — exact-solution oracle

Technique: T3 (Bethe ansatz / Yang–Baxter) · Tier: B (integrable) · Script: S

## Continuum conventions

$$ H = -\sum_{i=1}^{N}\frac{\partial^2}{\partial x_i^2} + 2c\sum_{i<j}\delta(x_i-x_j), \qquad c>0 $$

- **Units:** `ħ = 1`, `m = 1/2` (Lieb–Liniger units) — the kinetic term is literally `−∂²` and a rapidity `k` contributes `k²` to the energy. A general mass restores `ħ²k²/2m`.
- **Density / coupling:** `n = N/L` (thermodynamic limit `N, L → ∞`, `n` fixed); dimensionless coupling `γ = c/n` (Lieb’s γ). Repulsive `c > 0`, so `γ ∈ (0, ∞)`.
- **Energy scaling:** the ground-state energy per particle is `E/N = n² e(γ)` with `e(γ)` a *universal dimensionless* function — the sole non-trivial object of this card. (Equivalently `E/L = n³ e(γ)`.)
- These conventions are shared with the continuum cousins: `tonks-girardeau` is the `γ → ∞` endpoint of this very `e(γ)`; `yang-gaudin` is the two-component fermionic analogue with the *same* `c` and `γ = c/n`; the weak-coupling `e(γ) → γ` regime is where `bogoliubov-bose-gas` (3D, but the same `g/2 ψ†ψ†ψψ` contact philosophy) lives in spirit. See `.knowledge/conventions.md`.

## Solvability statement

T3 (coordinate/nested Bethe ansatz): the `δ`-interacting Bose gas is integrable [@LiebLiniger1963]. Every eigenstate is a Bethe wavefunction — a sum over permutations of `N` plane waves whose two-body scattering phase `θ(k) = 2\arctan(k/c)` fixes all many-body amplitudes — labelled by quasi-momenta (rapidities) `{k_j}` solving the Bethe equations. **The ground state fills a symmetric Fermi sea of rapidities `[-q, q]`**; in the thermodynamic limit the rapidity density `ρ(k)` obeys the linear **Lieb integral equation**, from which `e(γ)` is computed here to machine precision. **Tier B, not A:** `e(γ)` (and the two elementary excitation branches, the type-I/Bogoliubov and type-II/hole modes) are exactly characterised, but as solutions of integral / transcendental equations, not a single closed form; correlation functions require much heavier machinery (Lenard determinants, quantum inverse scattering) and are out of scope.

## The Bethe-ansatz-in-the-continuum story

For a lattice chain the Bethe roots are discrete; **in the continuum the ground-state roots fill an interval `[-q, q]` with a smooth density `ρ(k)`** (`L·ρ(k) dk` = number of rapidities in `dk`). Taking the thermodynamic limit of the logarithmic Bethe equations turns the sum over roots into an integral and yields a linear Fredholm equation of the second kind:

$$ \rho(k) = \frac{1}{2\pi} + \frac{1}{2\pi}\int_{-q}^{q}\frac{2c}{c^2+(k-k')^2}\,\rho(k')\,dk'. $$

The Lorentzian kernel is `θ'(k−k')`, the derivative of the two-body phase. Rescaling to the fixed interval `[-1,1]` via `k = q x`, `λ = c/q`, `g(x) = ρ(qx)` gives the **scaled Lieb equation**

$$ g(x) - \frac{1}{2\pi}\int_{-1}^{1}\frac{2\lambda}{\lambda^2+(x-y)^2}\,g(y)\,dy = \frac{1}{2\pi}, $$

solved by the shared Gauss–Legendre Nyström routine `_lib/fredholm.py`. The physics then follows from the **scaling chain**

$$ \gamma = \frac{\lambda}{I_0},\qquad e(\gamma) = \frac{I_2}{I_0^{3}},\qquad I_0=\int_{-1}^{1} g\,dx,\quad I_2=\int_{-1}^{1} x^2 g\,dx, $$

which is just `n = q I_0`, `E/L = q³ I_2`, `γ = c/n`, `e = (E/L)/n³` written in scaled variables. `γ(λ)` is monotone increasing, so `e(γ)` is obtained by inverting `γ(λ)` at the requested `γ`.

## Regimes & asymptotics

| Regime | `e(γ)` | Physics |
|---|---|---|
| Weak `γ → 0` | `γ − (4/3π) γ^{3/2} + …` | mean-field/Bogoliubov; energy `∝ c`, the gas is a quasi-condensate |
| Intermediate `γ ~ 1` | `e(1) ≈ 0.6392` | full crossover, no small parameter |
| Strong `γ → ∞` | `(π²/3)(1 − 4/γ + 12/γ² − …)` | Tonks–Girardeau: fermionization, `e → π²/3` (see `tonks-girardeau`) |

Both asymptotic forms are **derived, not assumed**, and are the self-test anchors (below). The leading strong-coupling constant `π²/3` is exactly the free-fermion Fermi-sea energy in these units — the content of the Bose–Fermi mapping.

## Exact results

- Scaled Lieb equation `g(x) − (1/2π)∫_{−1}^{1} 2λ/(λ²+(x−y)²) g(y) dy = 1/2π` [@LiebLiniger1963]
- Energy coefficient `e(γ) = I_2/I_0³`, `γ = λ/I_0` (scaling chain above) [@LiebLiniger1963]
- Strong coupling `e(γ) = (π²/3)(1 − 4/γ + 12/γ² − …)` → `π²/3` (Tonks limit)
- Weak coupling `e(γ) = γ − (4/3π) γ^{3/2} + …`
- `e(γ)` strictly monotone increasing, bounded above by `π²/3` for all finite `γ`

## Oracle script

`python oracle.py --gamma 1.0 --n 256` → prints `gamma`, `e_gamma` (`e(γ)`), `energy_per_particle_over_n2` (`= e(γ)`, since `E/N = n² e`), `e_tonks_limit` (`π²/3`). Importable: `compute(gamma=1.0, n=256)`; `e_of_gamma(gamma, n=256)` is the raw coefficient (used by the `tonks-girardeau` and `yang-gaudin` cross-checks). The solver is `_lib/fredholm.py` (`solve(kernel, B, n)`).

Self-test anchors: (1) **strong coupling** — `e(1000)` matches the derived `(π²/3)(1−4/γ+12/γ²)` to `1e-3` relative; (2) **weak coupling** — `e(0.01)` matches the derived `γ − (4/3π)γ^{3/2}` to `1e-2` relative; (3) `e(γ)` monotone increasing across `γ ∈ {0.05, …, 500}`; (4) `e(γ) < π²/3` for all finite `γ` (approached from below); (5) solver-resolution convergence `|e(γ=1)|_{n=128} − e(γ=1)|_{n=256}| < 1e-8`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e_gamma` | `γ = 1` | `≈ 0.639` | [@LiebLiniger1963] |
| `e_gamma` | `γ → ∞` | `π²/3 ≈ 3.289868` | [@LiebLiniger1963] |
| `e_gamma` | `γ = 1000` | `≈ 3.27675` (`(π²/3)(1−4/γ+12/γ²)`) | [@LiebLiniger1963] |
| `e_gamma` | `γ = 0.01` | `≈ 0.009576` (`γ−(4/3π)γ^{3/2}`) | [@LiebLiniger1963] |

## Verification recipes

- To check a Bethe/DMRG/QMC ground-state energy of the 1D `δ`-Bose gas at coupling `γ`: compute `E/N` and compare `(E/N)/n²` against `e_gamma` from `oracle.py --gamma <γ>`, tolerance `1e-6` in the well-resolved window `γ ∈ [0.05, 10³]`.
- To check a weak-coupling/Bogoliubov calculation: compare against `γ − (4/3π)γ^{3/2}`; deviations growing with `γ` are the *expected* breakdown of mean-field, not a bug.
- To check a strong-coupling (near-Tonks) calculation: compare against `(π²/3)(1 − 4/γ)`; the exact `γ → ∞` endpoint is the `tonks-girardeau` card’s `π²/3`.

## Key reference

[@LiebLiniger1963] — Lieb & Liniger, "Exact Analysis of an Interacting Bose Gas. I. The General Solution and the Ground State", Phys. Rev. **130**, 1605 (1963): the exact eigenfunctions, the ground-state integral equation, and the coupling-dependent ground-state energy `e(γ)` reproduced here. Rendered: _(Wave 3)_.
