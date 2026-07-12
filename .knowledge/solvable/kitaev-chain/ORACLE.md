# Kitaev p-wave chain — exact-solution oracle

Technique: T1 (free-fermion / BdG) · Tier: A (closed-form, exact) · Script: S

## Hamiltonian & conventions

$$ H = -\mu \sum_{i=1}^{L}\left(c^\dagger_i c_i - \tfrac12\right) - t\sum_{i=1}^{L}\left(c^\dagger_i c_{i+1} + \text{h.c.}\right) + \Delta \sum_{i=1}^{L}\left(c_i c_{i+1} + \text{h.c.}\right), \qquad \text{PBC } (c_{L+1}\equiv c_1) $$

Conventions: spinless fermions; `t > 0` hopping (energy unit `t = 1` by default), `μ` chemical potential written particle-hole-symmetrically via `n_i − ½`, `Δ` the real nearest-neighbor p-wave pairing amplitude. Native fermion model — no Jordan–Wigner string, so PBC means literally periodic fermions and the ground state spans the full Fock space (no boundary/parity sector choice; contrast `xy-chain`). See `.knowledge/conventions.md`.

Physics card: `.knowledge/models/kitaev-chain/MODEL.md`. That card writes the identical Hamiltonian `H = Σ[−t(c†c+h.c.) − μ(n−½) + Δ(cc+h.c.)]` with the same `t, μ, Δ` meanings, the same topological criterion `|μ| < 2t`, and the same gap-closing at `|μ| = 2t`. Conventions match exactly — no translation needed.

## Solvability statement

T1: the Hamiltonian is quadratic in the fermions and is diagonalized exactly by a Bogoliubov–de Gennes (BdG) transformation. Everything reported here — the full single-particle spectrum (via `ε(k)`), the ground-state energy per site, the bulk gap, and the topological flag — is exact for any `L, μ, t, Δ`. The model is exactly solvable in its entirety; there is no approximation. **Not exact:** nothing about this model is approximate. Some exact quantities are simply out of this card's scope (bulk-statics only): the OBC Majorana end-mode wavefunctions and the exponentially small even/odd parity splitting `∝ e^{−L/ξ}` (exactly computable from the real-space Nambu matrix), the bulk Z₂ invariant, and quench/braiding dynamics (all exactly tractable because the model stays quadratic).

## Exact results

- Single-fermion dispersion (PBC): $\varepsilon(k) = \sqrt{(2t\cos k + \mu)^2 + 4\Delta^2 \sin^2 k}$ [@Kitaev2001]
- Ground-state energy per site: $e_0 = -\dfrac{1}{2L}\sum_k \varepsilon(k)$ (equivalently $\tfrac1L\left[\tfrac12\operatorname{tr}A - \tfrac12\sum_m \varepsilon_m\right] + \tfrac{\mu}{2}$, with the $+\mu/2$ from the $-\mu(n-\tfrac12)$ constant)
- Bulk gap: $\Delta_{\text{gap}} = \min_k \varepsilon(k)$ — the script reports the numerical minimum (`bdg_energies[0]`), which is correct for all parameters. Closed form, two branches: the minimum sits at the zone edge ($k = 0$ or $\pi$), giving $\Delta_{\text{gap}} = \big|\,|\mu| - 2t\,\big|$, whenever $t \le \Delta$ or $t|\mu| \ge 2(t^2 - \Delta^2)$; for $t > \Delta$ and $t|\mu| < 2(t^2-\Delta^2)$ the minimum moves to an interior momentum $\cos k_* = -t\mu/\big(2(t^2-\Delta^2)\big)$ with $\Delta_{\text{gap}} = \Delta\sqrt{4(t^2-\Delta^2)-\mu^2}\,\big/\sqrt{t^2-\Delta^2}$ (e.g. $t=1, \Delta=0.5, \mu=1$: gap $= \sqrt{2/3} \approx 0.8165$, not the zone-edge value $1$). The two branches agree at the boundary $t|\mu| = 2(t^2-\Delta^2)$ (both give $2\Delta^2/t$); the interior minimum exists only for $|\mu| < 2t$, so in every case the gap vanishes exactly at $|\mu| = 2t$
- Topological criterion: **topological** (Majorana number `M = sign[(2t−μ)(2t+μ)] = −1`) iff $|\mu| < 2t$ with $\Delta \neq 0$; trivial for $|\mu| > 2t$ [@Kitaev2001]
- Sweet spot $\mu = 0,\ t = \Delta$: flat BdG band $\varepsilon(k) = 2t$ for all `k`, perfectly localized terminal Majoranas (OBC), $e_0 = -t$

## Oracle script

`python oracle.py --L 64 --mu 0.0 --t 1.0 --delta 1.0` → prints `e0_per_site`, `gap`, `topological`. Importable: `compute(L=64, mu=0.0, t=1.0, delta=1.0)`; `matrices(...)` returns the BdG `(A, B)`.
Self-test anchors: (1) sweet-spot flat band `ε = 2t` to `1e-12`; (2) gap closes at `|μ| = 2t` (`L=400`); (3) `topological` flag equals `|μ| < 2t` at `μ = 1` and `μ = 3`; (4) BdG ground energy matches brute-force ED (`ed.fermion_ops`, `L=8`) at `(μ,t,Δ) ∈ {(0.5,1,1),(1.7,0.8,0.6)}`, tolerance `1e-10`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e0_per_site` | `μ=0, t=Δ=1` (sweet spot) | `-1` | [@Kitaev2001] |
| `gap` (flat band) | `μ=0, t=Δ=1` | `2` (`= 2t`) | [@Kitaev2001] |
| `gap` | `μ=2t` (transition) | `0` | [@Kitaev2001] |
| `topological` | `|μ| < 2t` / `|μ| > 2t` | `True` / `False` | [@Kitaev2001] |

## Verification recipes

- To check any BdG or DMRG run at size `L`, PBC: compare `e0_per_site` and `gap` from `oracle.py --L <L> --mu <μ> --t <t> --delta <Δ>`, tolerance `1e-8` (exact).
- To locate the topological transition, sweep `μ` and confirm `gap → 0` at `|μ| = 2t` and the `topological` flag flips.

## Key reference

[@Kitaev2001] — Kitaev, "Unpaired Majorana fermions in quantum wires": the defining paper for this model, the p-wave chain, the topological vs trivial phases, the Majorana end modes, and the `|μ| = 2t` phase boundary. Rendered: _(Wave 3)_.
