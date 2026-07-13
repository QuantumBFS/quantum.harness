# Kondo model (Bethe ansatz) — exact-solution oracle

Technique: T3 (Bethe ansatz / Yang–Baxter) · Tier: B (integrable) · Script: T

## Hamiltonian & conventions

$$ H = \sum_{k\sigma}\varepsilon_k\,c^\dagger_{k\sigma}c_{k\sigma} \;+\; J\,\mathbf{S}_{\mathrm{imp}}\cdot\mathbf{s}_0, \qquad \mathbf{s}_0 = \tfrac12\sum_{\alpha\beta}c^\dagger_{0\alpha}\,\boldsymbol{\sigma}_{\alpha\beta}\,c_{0\beta} $$

Conventions: the **`s`–`d` exchange (Kondo) model** — a single localized spin-1/2 impurity `S_imp` antiferromagnetically exchange-coupled (`J>0`) to the conduction-electron spin density `s_0` at the origin, spin-1/2 `S`-operators (`S^a=σ^a/2`), conduction band with dispersion `ε_k`. The exact solution linearizes the dispersion about the Fermi level (left-movers on a half-line), leaving one relevant coupling `J` and the bandwidth/cutoff `D` that together define the Kondo scale `T_K`. See `.knowledge/conventions.md`.

Model-zoo sibling: `.knowledge/models/anderson-impurity` (the Anderson impurity, whose local-moment regime maps to this Kondo model by the Schrieffer–Wolff transformation `J=8V^2/U`); the lattice generalization is `.knowledge/models/kondo-lattice`. The Bethe-ansatz *Anderson* card is the neighbour `anderson-impurity-bethe`.

## Solvability statement

T3 (Bethe ansatz): the single-channel spin-1/2 Kondo model is exactly solvable by the Bethe ansatz — after linearizing the conduction dispersion, the electron–impurity scattering is factorizable (Yang–Baxter) and the spectrum and full thermodynamics follow from Bethe/thermodynamic-Bethe-ansatz equations [@AndreiFuruyaLowenstein1983; @TsvelickWiegmann1983]. This yields the impurity free energy, entropy, and magnetic susceptibility at all temperatures and fields as universal functions of `T/T_K` and `H/T_K`, with the crossover from a free local moment to a screened singlet controlled by the single scale `T_K`. This is Tier B (integrable): the exact results are universal scaling functions and closed-form limits (below), obtained from the Bethe/TBA equations rather than a single elementary closed form; finite-`L`/lattice energetics still require ED (the pinned rows below). This is a **T-flag** card — no `oracle.py`; the exact content is the integrability facts and universal numbers below plus finite-size ED reference rows computed once for this card.

## No oracle script — tabulated benchmarks below

This is a **T-flag** card: there is no `oracle.py`. The concrete numbers pinned here are (i) universal exact numbers from the Bethe-ansatz solution (the Wilson ratio, the entropy crossover) and (ii) finite-size ED ground-state energies of the fully specified lattice `s`–`d` Hamiltonian below (computed once for this card, script not shipped — see the note under the table).

## Exact results

- Single-channel spin-1/2 Kondo model is Bethe-ansatz integrable — exact impurity thermodynamics at all `T`, `H` [@AndreiFuruyaLowenstein1983; @TsvelickWiegmann1983]
- **Wilson ratio** `R = \dfrac{\chi_{\mathrm{imp}}/\chi_0}{\gamma_{\mathrm{imp}}/\gamma_0} = 2` exactly (spin-1/2, single channel): the impurity susceptibility is enhanced by a factor 2 relative to its linear-specific-heat coefficient [@AndreiFuruyaLowenstein1983]
- **Zero-field impurity entropy crossover**: `S_{\mathrm{imp}}(T)\to\ln 2` for `T\gg T_K` (free local moment) and `S_{\mathrm{imp}}(T)\to 0` for `T\ll T_K` (Kondo-screened singlet) [@TsvelickWiegmann1983]
- **Zero-`T` impurity susceptibility** is finite (Pauli-like), `\chi_{\mathrm{imp}}(0)=(g\mu_B)^2/(4 T_K)` up to the convention-dependent definition of `T_K` — the moment is fully quenched, no residual Curie term [@AndreiFuruyaLowenstein1983]
- The screening is a **crossover, not a phase transition**: all impurity properties are analytic universal functions of `T/T_K`, `H/T_K`

## Benchmarks

Two kinds of number. **Universal (Bethe-ansatz)**: dimensionless exact values. **Pinned finite-size ED (this card)**: the `s`–`d` Hamiltonian on an `L=5`-site **open** tight-binding chain (hopping `t=1`), spin-1/2 impurity exchange-coupled at site 0 with `\mathbf{s}_0=\tfrac12\sum_{\alpha\beta}c^\dagger_{0\alpha}\boldsymbol{\sigma}_{\alpha\beta}c_{0\beta}`, coupling `J`, at conduction half-filling (`N_e=5` electrons; Hilbert space `4^5\times2=2048`, `N_e=5` sector dim `504`), dense ED.

| Quantity | Params | Value | Source |
|---|---|---|---|
| Wilson ratio `R` | spin-1/2, 1 channel | `2` (exact) | [@AndreiFuruyaLowenstein1983] |
| `S_{\mathrm{imp}}` (`T\gg T_K`) | zero field | `\ln 2` | [@TsvelickWiegmann1983] |
| `S_{\mathrm{imp}}` (`T\ll T_K`) | zero field | `0` | [@TsvelickWiegmann1983] |
| `E_0` (total, ED) | `L=5`, `J=1`, `t=1`, `N_e=5` | `-5.8397495469` | finite-`L` ED reference, this card |
| `E_0` (total, ED) | `L=5`, `J=0`, `t=1`, `N_e=5` | `-5.4641016151` | finite-`L` ED reference, this card |
| singlet–excitation gap | `L=5`, `J=1`, `N_e=5` | `0.4167212187` | finite-`L` ED reference, this card |

The `J=0` row is the decoupled reference: the open 5-site tight-binding chain at half-filling (single-particle levels `-2\cos(k\pi/6)`, `k=1..5`) has `E_0=-5.4641016151` with a free (2-fold degenerate) impurity spin — the exchange `J=1` lifts that degeneracy (gap `0.4167`) and lowers `E_0` to `-5.8397495469` as the impurity binds into a local singlet. These are **finite-`L` ED references for this card, not thermodynamic `T_K` values** — the universal Wilson-ratio and entropy rows are the exact Bethe-ansatz content; the ED rows are pinned, unambiguous check numbers (computed once, Hermiticity residual `0`).

## Verification recipes

- To check a Kondo ED code: build the open `L=5` chain `H=-t\sum_{i\sigma}(c^\dagger_{i\sigma}c_{i+1,\sigma}+\mathrm{h.c.}) + J\,\mathbf{S}_{\mathrm{imp}}\cdot\mathbf{s}_0` with `t=1`, `\mathbf{s}_0` the conduction spin at site 0, at `N_e=5` (half-filling), and reproduce `E_0(J=1)=-5.8397495469` and `E_0(J=0)=-5.4641016151` to `1e-8`. A mismatch usually means a `\tfrac12\boldsymbol\sigma`-vs-`\boldsymbol\sigma` factor in `s_0` (factor 2 on `J`), a wrong filling sector, or periodic-vs-open boundaries.
- To check a Wilson-ratio measurement: the spin-1/2 single-channel Kondo Wilson ratio is exactly `R=2`; a numerical `R` drifting from 2 signals either a residual free moment (temperature not below `T_K`) or a multichannel/anisotropic coupling.
- To check an impurity-entropy curve: `S_{\mathrm{imp}}` must interpolate `\ln 2` (high `T`) down to `0` (low `T`) as a universal function of `T/T_K`; a residual `\ln 2` at `T\to0` means the moment is unscreened (e.g. ferromagnetic `J<0`, which does *not* screen).

## Key reference

[@AndreiFuruyaLowenstein1983] — N. Andrei, K. Furuya & J. H. Lowenstein, "Solution of the Kondo problem", Rev. Mod. Phys. **55**, 331 (1983): the Bethe-ansatz solution of the Kondo model and its exact impurity thermodynamics, including the Wilson ratio `R=2` and the `\ln 2\to0` entropy crossover; the parallel thermodynamic treatment (and the Anderson-model solution feeding the neighbour card) is Tsvelick–Wiegmann [@TsvelickWiegmann1983]. Rendered: _(Wave 3)_.
