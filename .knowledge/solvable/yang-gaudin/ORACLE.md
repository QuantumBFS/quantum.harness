# Yang–Gaudin gas — exact-solution oracle

Technique: T3 (Bethe ansatz / Yang–Baxter — nested) · Tier: B (integrable) · Script: S

## Continuum conventions

$$ H = -\sum_{i=1}^{N}\frac{\partial^2}{\partial x_i^2} + 2c\sum_{i<j}\delta(x_i-x_j), \qquad c>0 $$

- **Units:** `ħ = 1`, `m = 1/2` (Lieb–Liniger units); kinetic term `−∂²`, rapidity `k` contributes `k²`.
- **State:** spin-1/2 fermions, **balanced** (`N/2` up, `N/2` down) — the zero-field ground state, a spin singlet. Density `n = N/L`, dimensionless coupling `γ = c/n` (same `c`, same `γ` as `lieb-liniger`).
- **Energy scaling:** `E/N = n² e(γ)`, `e(γ)` universal and dimensionless — the object of this card.
- **Endpoints:** `γ → 0` is the free two-component Fermi gas, `e → π²/12`; `γ → ∞` is the spin-incoherent impenetrable point, `e → π²/3` = the `tonks-girardeau` value. Cross-references: `lieb-liniger` (bosonic sibling, same `H`), `tonks-girardeau` (the `γ→∞` endpoint). See `.knowledge/conventions.md`.

## Solvability statement

T3 (**nested** Bethe ansatz): the two-component `δ`-Fermi gas is integrable [@Yang1967; @Gaudin1967]. Because the internal (spin) degrees of freedom scatter non-trivially, a *single* Bethe ansatz is not enough — Yang’s diagonalization of the spin transfer matrix requires a **second** Bethe ansatz nested inside the first, introducing spin rapidities `λ_α` alongside the charge rapidities `k_j`. **The balanced ground state fills a charge Fermi sea `[-Q, Q]` and a spin sea over the entire real axis** (`B = ∞`, since there is no field). The densities obey two coupled linear integral equations; `e(γ)` is computed here to machine precision. **Tier B, not A:** `e(γ)`, the spin/charge velocities, and the (gapless) excitation structure are exactly characterised as integral-equation solutions, not closed forms; correlators need heavier machinery and are out of scope.

## The Bethe-ansatz-in-the-continuum story: eliminating the spin sea

The coupled thermodynamic-limit equations for the charge density `ρ(k)` (on `[-Q,Q]`) and spin density `σ(λ)` (on the full line) are

$$ \rho(k) = \frac{1}{2\pi} + \int a_1(k-\lambda)\,\sigma(\lambda)\,d\lambda, \qquad
   \sigma(\lambda) = \int_{-Q}^{Q} a_1(\lambda-k)\,\rho(k)\,dk - \int a_2(\lambda-\lambda')\,\sigma(\lambda')\,d\lambda', $$

with Lorentzian kernels `a_1(x) = (1/π)(c/2)/((c/2)²+x²)` and `a_2(x) = (1/π)c/(c²+x²)` (Fourier transforms `\hat a_1 = e^{-(c/2)|ω|}`, `\hat a_2 = e^{-c|ω|}`). **Because the balanced spin sea is the entire real axis, the spin equation is a pure convolution and is eliminated *exactly* by Fourier transform** — no truncation, no approximation:

$$ \hat\sigma = \frac{\hat a_1}{1+\hat a_2}\hat\rho, \qquad
   \frac{\hat a_1^{\,2}}{1+\hat a_2} = \frac{\hat a_2}{1+\hat a_2} = \frac{1}{1+e^{c|ω|}}, $$

collapsing the pair to a **single well-conditioned equation on the compact charge interval**

$$ \rho(k) - \int_{-Q}^{Q} R(k-k')\,\rho(k')\,dk' = \frac{1}{2\pi}, \qquad
   \hat R(ω) = \frac{1}{1+e^{c|ω|}}, $$

whose real-space kernel has the closed digamma form `R(x) = (1/2πc)\,\mathrm{Re}\!\left[\psi\!\left(1+\tfrac{ix}{2c}\right)-\psi\!\left(\tfrac12+\tfrac{ix}{2c}\right)\right]`. This is solved by `_lib/fredholm.solve`; observables follow exactly as on the `lieb-liniger` card, `γ = c/n = c/I_0`, `e(γ) = I_2/I_0³`, `I_0=\int_{-Q}^{Q}\rho`, `I_2=\int_{-Q}^{Q} k^2\rho`. (The explicit `2×2` block Nyström — `σ` on a *finite* spin cutoff, built from `fredholm.nodes_weights` — is exactly what this Fourier step avoids: it is ill-conditioned as `c → 0`. The block solver is kept in the script and cross-checked against the reduced one at `γ~1`, confirming the elimination.)

## Regimes & asymptotics

| Regime | `e(γ)` | Physics |
|---|---|---|
| Free `γ → 0` | `π²/12 + γ/2 + …` | two half-filled Fermi seas (density `n/2` each); `+γ/2` is the exact first-order contact shift |
| Intermediate `γ ~ 1` | `e(1) ≈ 1.250` | full spin-charge crossover |
| Strong `γ → ∞` | `→ π²/3` | spin-incoherent; charge fermionizes to the Tonks value (see `tonks-girardeau`) |

**Free-limit derivation (`e → π²/12`):** two decoupled spin species, each a free Fermi gas of density `n/2` filling `[-πn/2, πn/2]`, give `E/L = 2·(1/2π)\int_{-πn/2}^{πn/2}k²dk = π²n³/12`, so `e = π²/12`. **First-order shift (`+γ/2`):** repulsive contact acts only between *opposite* spins (Pauli kills same-spin contact); `E_{int}/N = 2c(n/2)²/n = γn²/2`, i.e. `e = π²/12 + γ/2`. Both are derived, not assumed — and note the raw `π²/12` is only the strict `γ→0` limit: at `γ = 0.05` the true `e` already sits `~3%` above it, exactly the `+γ/2` term (this is why the self-test anchors the *two-term* form, per the “trust your derivation” house rule). **Strong-coupling `→ π²/3`:** as `c→∞` the reduced kernel `\hat R → 0`, `ρ → 1/2π`, and the charge sector reproduces the spinless Tonks–Girardeau Fermi sea — the balanced fermions become impenetrable and spin-incoherent.

## Exact results

- Coupled Gaudin–Yang equations for `(ρ, σ)`; balanced spin sea `B = ∞` [@Yang1967; @Gaudin1967]
- Reduced charge equation `ρ − (1/2π)∫ 2π R\,ρ = 1/2π`, `\hat R(ω)=1/(1+e^{c|ω|})` (spin sea eliminated exactly) [@Gaudin1967]
- Energy coefficient `e(γ) = I_2/I_0³`, `γ = c/I_0`
- Free limit `e(γ) = π²/12 + γ/2 + …` → `π²/12` (two-component Fermi gas)
- Strong limit `e(γ) → π²/3` (spinless Tonks–Girardeau; see `tonks-girardeau`)
- `e(γ)` monotone increasing, bounded in `(π²/12, π²/3)`

## Oracle script

`python oracle.py --gamma 1.0 --n 256` → prints `gamma`, `e_gamma` (`e(γ)`), `energy_per_particle_over_n2` (`= e(γ)`), `e_free_limit` (`π²/12`), `e_tonks_limit` (`π²/3`). Importable: `compute(gamma=1.0, n=256)`; `e_of_gamma(gamma, n=256)` is the coefficient; `_block_e(gamma)` is the reference `2×2` block Nyström. Solver: `_lib/fredholm.py`.

Self-test anchors: (1) **weak coupling** — `e(0.05)` matches the derived `π²/12 + γ/2` to `5e-3` relative, and `e(0.05) − γ/2` recovers `π²/12` to `3e-3` (the bare free value is only the `γ→0` limit); (2) **cross-card strong coupling** — `e(1000)` equals `tonks-girardeau`’s `π²/3` within `2%` (imported, not duplicated); (3) `e(γ)` monotone increasing on `γ ∈ {0.05,…,500}`, bounded in `(π²/12, π²/3)`; (4) solver-resolution convergence `|e(γ=1)|_{n=128} − e(γ=1)|_{n=256}| < 1e-8`; (5) the explicit block Nyström agrees with the reduced solver at `γ=1` to `1%` (validates the Fourier elimination).

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e_gamma` | `γ → 0` | `π²/12 ≈ 0.822467` | [@Gaudin1967] |
| `e_gamma` | `γ = 1` | `≈ 1.250` | [@Yang1967] |
| `e_gamma` | `γ → ∞` | `π²/3 ≈ 3.289868` | [@Yang1967] |
| `e_gamma` | `γ = 0.05` | `≈ 0.8473` (`π²/12 + γ/2`) | [@Gaudin1967] |

## Verification recipes

- To check a Bethe/DMRG/QMC energy of the balanced 1D two-component Fermi gas at coupling `γ`: compute `(E/N)/n²` and compare against `e_gamma` from `oracle.py --gamma <γ>`, tolerance `1e-6` in the well-resolved window `γ ∈ [0.05, 10³]`.
- To check a weak-coupling calculation: compare against `π²/12 + γ/2` — the free value `π²/12` alone is correct only at `γ → 0`; the `+γ/2` opposite-spin contact shift must appear.
- To check a strong-coupling calculation: compare against `π²/3` (the `tonks-girardeau` value); the balanced fermions become spin-incoherent impenetrable particles.

## Key reference

[@Yang1967] — C. N. Yang, "Some Exact Results for the Many-Body Problem in One Dimension with Repulsive Delta-Function Interaction", Phys. Rev. Lett. **19**, 1312 (1967): the nested Bethe ansatz reducing the spin-1/2 ground state to a Fredholm equation. The balanced case and the coupled density equations are Gaudin’s [@Gaudin1967] (Phys. Lett. A **24**, 55). Rendered: _(Wave 3)_.
