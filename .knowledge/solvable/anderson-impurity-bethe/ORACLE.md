# Anderson impurity model (Bethe ansatz) — exact-solution oracle

Technique: T3 (Bethe ansatz / Yang–Baxter) · Tier: B (integrable) · Script: T

## Hamiltonian & conventions

$$ H = \varepsilon_d\sum_\sigma n_{d\sigma} + U\,n_{d\uparrow}n_{d\downarrow} + \sum_{k\sigma}\varepsilon_k c^\dagger_{k\sigma}c_{k\sigma} + \sum_{k\sigma}\big(V_k\,d^\dagger_\sigma c_{k\sigma}+\mathrm{h.c.}\big),\qquad \varepsilon_d=-\tfrac{U}{2} $$

Conventions: the **single-impurity Anderson model (SIAM)** — one interacting impurity level `ε_d` with on-site repulsion `U>0`, hybridized (`V_k`) to a non-interacting band `{ε_k}`; hybridization strength `Γ(ω)=\pi\sum_k|V_k|^2\delta(ω-ε_k)`. The **symmetric** point is `ε_d=-U/2`, where the model is particle–hole symmetric and `⟨n_d⟩=1`. Same convention as the model-zoo card `.knowledge/models/anderson-impurity` (identical `H`, same `Γ` definition, same symmetric point) — **no convention translation is needed** between the two cards. See `.knowledge/conventions.md`.

Model-zoo sibling: `.knowledge/models/anderson-impurity` (physics card; NRG/ED/CTQMC methods). The local-moment regime maps to the Kondo model (`kondo-bethe`) by the Schrieffer–Wolff transformation `J=8V^2/U` at the symmetric point.

## Solvability statement

T3 (Bethe ansatz): the symmetric single-impurity Anderson model is exactly solvable by the Bethe ansatz — with a linearized conduction band the model is integrable and its impurity thermodynamics (free energy, occupation, charge and spin susceptibilities, specific heat) follow as exact universal functions from the Bethe/thermodynamic-Bethe-ansatz equations [@KawakamiOkiji1981; @TsvelickWiegmann1983]. In the local-moment regime (`U\gg\Gamma`) the spin sector reduces to the Kondo problem with `J=8V^2/U`, reproducing the Kondo scale `T_K` and the universal spin thermodynamics; away from it the exact solution also captures the mixed-valence/charge-fluctuation crossover. This is Tier B (integrable): the exact content is universal scaling functions and closed-form limits (below) from the Bethe/TBA equations, not a single elementary closed form; finite-bath energetics require ED (the pinned rows). This is a **T-flag** card — no `oracle.py`; the exact content is the integrability facts plus finite-size ED reference rows computed once for this card.

## No oracle script — tabulated benchmarks below

This is a **T-flag** card: there is no `oracle.py`. The concrete numbers pinned here are (i) exact statements from the Bethe-ansatz solution (particle–hole symmetry, Wilson ratio, the Kondo mapping) and (ii) finite-bath ED ground-state energies of the fully specified **discretized** symmetric SIAM below (computed once for this card, script not shipped — see the note under the table).

## Exact results

- Symmetric single-impurity Anderson model is Bethe-ansatz integrable — exact impurity thermodynamics at all `T`, `H` [@KawakamiOkiji1981; @TsvelickWiegmann1983]
- **Particle–hole symmetry** at `ε_d=-U/2`: `⟨n_d⟩=1` exactly (fixed impurity occupancy), impurity charge susceptibility structure fixed by PH symmetry [@KawakamiOkiji1981]
- **Strong-coupling fixed point**: the Wilson ratio is `R_W=2` in the Kondo (local-moment) limit — the impurity spin susceptibility is exactly twice the value implied by its specific-heat coefficient [@TsvelickWiegmann1983]
- **Local-moment → Kondo mapping**: for `U\gg\Gamma`, Schrieffer–Wolff gives `J=8V^2/U`; the spin thermodynamics collapses onto the universal Kondo curves with `T_K\sim\sqrt{U\Gamma}\,\exp(-\pi U/8\Gamma)` [@TsvelickWiegmann1983]
- **Impurity entropy crossover**: `S_{\mathrm{imp}}\to\ln 2` (free moment, `T\gg T_K`) `\to 0` (screened singlet, `T\ll T_K`) [@TsvelickWiegmann1983]

## Benchmarks

Two kinds of number. **Universal (Bethe-ansatz)**: dimensionless exact statements. **Pinned finite-bath ED (this card)**: the **discretized** symmetric SIAM — impurity `d`-orbital (`U`, `ε_d=-U/2`) hybridized with amplitude `V` to site 1 of an `L=5`-site open tight-binding bath chain (hopping `t`, on-site energy 0), i.e.
`H = ε_d\sum_\sigma n_{d\sigma} + U n_{d\uparrow}n_{d\downarrow} - t\sum_{i=1}^{L-1}\sum_\sigma(c^\dagger_{i\sigma}c_{i+1,\sigma}+\mathrm{h.c.}) + V\sum_\sigma(d^\dagger_\sigma c_{1\sigma}+\mathrm{h.c.})`,
with `U=2`, `V=1`, `t=1`, at half-filling (`N_e=6` electrons over `6` orbitals; Hilbert space `4^6=4096`, `N_e=6` sector dim `924`), dense ED.

| Quantity | Params | Value | Source |
|---|---|---|---|
| `⟨n_d⟩` (symmetric) | `ε_d=-U/2` | `1` (exact, PH symmetry) | [@KawakamiOkiji1981] |
| Wilson ratio `R_W` | Kondo limit | `2` (exact) | [@TsvelickWiegmann1983] |
| `E_0` (total, ED) | `L=5`, `U=2`, `V=1`, `t=1`, `N_e=6` | `-7.5645006223` | finite-bath ED reference, this card |
| `E_0` (total, ED) | `L=5`, `U=0`, `V=1`, `t=1`, `N_e=6` | `-6.9879184149` | finite-bath ED reference, this card |
| first excitation gap | `L=5`, `U=2`, `N_e=6` | `0.7216924611` | finite-bath ED reference, this card |

The `U=0` row is the non-interacting reference: with `ε_d=0` and `V=t=1` the impurity+bath is a uniform open 6-site chain (single-particle levels `-2\cos(k\pi/7)`, `k=1..6`), `E_0=-6.9879184149` at half-filling — a clean check handle. Turning on `U=2` (with `ε_d=-U/2=-1`) drives the symmetric SIAM: `E_0=-7.5645006223`, `⟨n_d⟩=1`. These are **finite-bath ED references for this card, not thermodynamic values** — the universal PH-symmetry and Wilson-ratio rows are the exact Bethe-ansatz content; the ED rows are pinned, unambiguous check numbers (computed once, Hermiticity residual `0`), *not* an extrapolation to a continuum bath.

## Verification recipes

- To check a SIAM ED code: build the discretized symmetric SIAM above with `U=2`, `V=1`, `t=1`, `ε_d=-1`, `L=5` bath sites, at `N_e=6` (half-filling), and reproduce `E_0=-7.5645006223` (and the `U=0` value `-6.9879184149`) to `1e-8`. A mismatch usually means an asymmetric `ε_d\ne-U/2`, a `Γ`/`V` normalization slip, a wrong bath-chain length or filling, or hybridizing to the wrong bath site.
- To confirm particle–hole symmetry: at `ε_d=-U/2` the ground state has `⟨n_d⟩=1` for any `U`; a deviation means the symmetric point is mis-set (the model has drifted into the mixed-valence regime).
- To check universal thermodynamics: in the local-moment regime `U\gg\Gamma` the spin susceptibility/entropy must collapse onto the Kondo curves with `J=8V^2/U`; the Wilson ratio approaches `R_W=2`. A finite discretized bath (as pinned here) only *approximates* the continuum `T_K`; treat `T_K\sim\sqrt{U\Gamma}\,e^{-\pi U/8\Gamma}` as order-of-magnitude, not a benchmark match.

## Key reference

[@KawakamiOkiji1981] — N. Kawakami & A. Okiji, "Exact expression of the ground-state energy for the symmetric Anderson model", Phys. Lett. A **86**, 483 (1981): the Bethe-ansatz exact ground-state energy and susceptibilities of the symmetric SIAM; the full finite-`T` universal thermodynamics and the Wilson ratio `R_W=2` are Tsvelick–Wiegmann [@TsvelickWiegmann1983]. The physics-card sibling is `.knowledge/models/anderson-impurity`; the Kondo-limit spin sector is `kondo-bethe`. Rendered: _(Wave 3)_.
