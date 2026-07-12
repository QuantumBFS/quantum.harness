# Bogoliubov theory of the dilute Bose gas — exact-solution oracle

Technique: T1 (free-particle / Bogoliubov diagonalization) · Tier: A/D (exact *within* the theory; the theory is the weak-coupling limit of the true gas) · Script: S

## Hamiltonian & conventions

$$ H = \int d^3r\, \hat\psi^\dagger\!\left(-\frac{\nabla^2}{2m}\right)\!\hat\psi + \frac{g}{2}\int d^3r\, \hat\psi^\dagger\hat\psi^\dagger\hat\psi\hat\psi, \qquad \hbar = 1 $$

3D uniform (translation-invariant) dilute Bose gas with a contact (`δ`-function) interaction of coupling `g = 4πa/m` (`a` the s-wave scattering length), density `n`, no external trap. Conventions: `ħ = 1` throughout; `εₖ = k²/(2m)` the free-particle dispersion. Bogoliubov theory substitutes `ψ̂ → √n + δψ̂` (condensate + fluctuation) and keeps `H` to quadratic order in `δψ̂`, then diagonalizes that quadratic form by a momentum-space Bogoliubov (`u_k, v_k`) transformation — **this substitution and truncation is the approximation**; everything computed below is then exact *for that quadratic Hamiltonian*. No model-zoo sibling under `.knowledge/models/` for the continuum dilute Bose gas (the zoo's `bose-hubbard` card is the lattice, on-site-interacting cousin — a different model, not a convention match to translate against). See `.knowledge/conventions.md`.

## Solvability statement

T1: the Bogoliubov-truncated Hamiltonian is quadratic in the bosonic fluctuation operators and is diagonalized exactly (for any `g, n, m`) by a `k`-space Bogoliubov transformation, giving the excitation spectrum `ε(k) = \sqrt{ε_k(ε_k+2gn)}`. Everything reported here — the dispersion, its `k→0` phonon slope (sound speed), the healing length, and the momentum-integrated quantum depletion — is an **exact closed-form (or exactly-convergent-integral) property of the Bogoliubov Hamiltonian itself**: tier A *as a statement about that quadratic theory*. **Not exact:** the Bogoliubov Hamiltonian is not the true interacting-boson Hamiltonian — it is the leading-order term of an expansion in the diluteness parameter `na³ ≪ 1` (dropping cubic-and-higher fluctuation terms, i.e. exchange/beyond-mean-field corrections to the depletion and the ground-state energy, captured at the next order by the Lee–Huang–Yang correction). As a statement about a real interacting Bose gas (e.g. liquid ⁴He, where `na³ ~ O(1)`, or even a dilute ultracold gas at the percent-level depletion corrections), Bogoliubov theory is only **tier D — exact in the dilute/weak-coupling limit `na³ → 0`**, not for the true many-body ground state at finite coupling. The quantity `depletion_3d` itself is a direct diagnostic of how good the approximation is: it *is* (to leading order) the fraction of atoms depleted from the condensate by interactions, and the theory is self-consistent only where this fraction is small.

## Exact results (within Bogoliubov theory)

- Excitation spectrum: $\varepsilon(k) = \sqrt{\varepsilon_k(\varepsilon_k + 2gn)}$, $\varepsilon_k = k^2/2m$ [@Bogoliubov1947]
- Coherence factor: $v_k^2 = \dfrac{\varepsilon_k + gn - \varepsilon(k)}{2\varepsilon(k)} = \dfrac{(gn)^2}{2\varepsilon(k)\bigl(\varepsilon_k+gn+\varepsilon(k)\bigr)}$ (second form numerically well-conditioned — the naive subtraction cancels catastrophically for `k ≫ √(2mgn)`) [@Bogoliubov1947]
- Phonon-limit sound speed: $c_s = \lim_{k\to 0}\varepsilon(k)/k = \sqrt{gn/m}$ (linear/phonon dispersion at small `k`; crosses over to the free-particle `ε_k` at large `k`) [@Bogoliubov1947]
- Healing length (crossover momentum scale, `k_ξ = 1/\xi`): $\xi = 1/\sqrt{2mgn}$
- Quantum depletion (exact evaluation of the Bogoliubov integral, any `g, n, m`): $\dfrac{n_{\text{ex}}}{n} = \dfrac{1}{n}\dfrac{1}{(2\pi)^3}\displaystyle\int d^3k\, v_k^2 = \dfrac{8}{3\sqrt\pi}\sqrt{na^3}, \qquad a = \dfrac{mg}{4\pi}$ [@Bogoliubov1947]

## Oracle script

`python oracle.py --g 0.1 --n 1.0 --m 1.0` → prints `sound_speed` (numeric `k→0` slope), `sound_speed_closed` (`√(gn/m)`), `healing_length`, `depletion_3d` (numeric radial integral), `depletion_3d_closed` (`(8/3√π)√(na³)`). Importable: `compute(g=0.1, n=1.0, m=1.0)`.
Self-test anchors: (1) the numeric `k→0` slope of `ε(k)` matches the closed-form sound speed `√(gn/m)` to `1e-6`; (2) the numeric radial integral for `depletion_3d` matches the closed-form `depletion_3d_closed` to `1e-2` (in practice they agree to `~1e-4` relative at `na³ ~ 5×10⁻⁷` — the closed form is an exact evaluation of the integral, not a further approximation, so the two only disagree at float-precision/quadrature level); (3) phonon-limit convergence: `ε(k)/k` approaches `c_s` monotonically from above as `k → 0` (`ε(k) = c_s k\sqrt{1+(kξ/2)^2} > c_s k` for all `k > 0`).

## Benchmarks

| Quantity | Params | Value | Source |
|---|---|---|---|
| `sound_speed_closed` | `g=0.1, n=1, m=1` | `√0.1 ≈ 0.316228` | [@Bogoliubov1947] |
| `healing_length` | `g=0.1, n=1, m=1` | `1/√0.2 ≈ 2.236068` | [@Bogoliubov1947] |
| `depletion_3d_closed` | `g=0.1, n=1, m=1` (`a ≈ 7.96×10⁻³`, `na³ ≈ 5.04×10⁻⁷`) | `≈ 1.068×10⁻³` | [@Bogoliubov1947] |
| Validity regime | — | closed forms trustworthy for `na³ ≲ 10⁻³`; `He-4`-like `na³ ~ O(1)` is **outside** the theory's regime | tier statement above |

## Verification recipes

- To check a Bogoliubov-de Gennes / mean-field numerical solver on the uniform dilute Bose gas: compare its excitation spectrum against `ε(k) = √(εₖ(εₖ+2gn))` pointwise, tolerance `1e-8` (exact, within the theory).
- To check a QMC (e.g. diffusion or path-integral Monte Carlo) ground-state depletion at weak coupling: compare against `depletion_3d_closed`, expecting agreement only in the dilute regime `na³ ≪ 1` — deviations that grow with `na³` are the *expected* signature of beyond-Bogoliubov (Lee–Huang–Yang and higher) corrections, not a bug in either calculation.
- To check a sound-speed measurement (Bragg spectroscopy simulation, structure-factor extraction): compare against `sound_speed_closed = √(gn/m)`, valid only in the phonon (`k ≪ 1/ξ`) regime.

## Key reference

[@Bogoliubov1947] — N. N. Bogoliubov, "On the theory of superfluidity", J. Phys. (USSR) **11**, 23 (1947): the original derivation of the quadratic (Bogoliubov) Hamiltonian, the `u_k, v_k` diagonalization, the phonon-to-free-particle crossover spectrum, and the resulting quantum depletion — the foundational reference for every closed form on this card. Rendered: _(pre-DOI-era Soviet journal — bib stub, no PDF ingested)_.
