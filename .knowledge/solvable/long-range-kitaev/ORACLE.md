# Long-range Kitaev chain — exact-solution oracle

Technique: T1 (free-fermion / BdG) · Tier: A (closed-form, exact) · Script: S

## Hamiltonian & conventions

$$ H = -\mu\sum_{i}\left(c^\dagger_i c_i - \tfrac12\right) - t\sum_{i}\left(c^\dagger_i c_{i+1} + \text{h.c.}\right) + \sum_{i<j}\Delta_{ij}\left(c_i c_j + \text{h.c.}\right), \qquad \Delta_{ij} = \frac{\Delta}{d(i,j)^{\alpha}} $$

Conventions: spinless fermions on a PBC ring; `t > 0` **nearest-neighbor** hopping (energy unit `t = 1` by default), `μ` chemical potential (particle-hole-symmetric via `n_i − ½`), and a **long-range p-wave pairing** with amplitude decaying as a power law in the minimum-image chain distance `d(i,j) = min(|i−j|, L−|i−j|)`, cut off at `d ≤ L/2`; the antipodal bond (`d = L/2`, even `L`) is counted once. Native fermion model — no Jordan–Wigner string, so the ground state spans the full Fock space (no boundary/parity sector choice). `α → ∞` recovers the nearest-neighbor `kitaev-chain`. See `.knowledge/conventions.md`.

No model-zoo sibling under `.knowledge/models/`; the `α → ∞` limit is the sibling card `.knowledge/models/kitaev-chain/MODEL.md` (and the solvable `kitaev-chain/`), whose convention this card matches exactly at short range.

## Solvability statement

T1: the Hamiltonian remains quadratic in the fermions for any pairing range, so it is diagonalized exactly by a Bogoliubov–de Gennes transformation. The ground-state energy per site and the BdG single-particle spectrum (hence the gap) reported here are exact for any `L, μ, t, Δ, α`. **Not exact:** nothing about this model is approximate. What is out of this card's scope (bulk spectrum/energy only): the edge physics that makes the long-range model interesting — for `α < 1` the model hosts **massive Dirac-like edge modes** and **violates the entanglement area law** (logarithmic / super-area-law growth), and the pairing-induced correlations decay algebraically rather than exponentially; these are exactly studied from the same BdG solution but are not computed by the script [@Vodola2014].

## Exact results

- Ground-state energy per site: $e_0 = \dfrac1L\left[\tfrac12\operatorname{tr}A - \tfrac12\sum_m \varepsilon_m\right] + \dfrac{\mu}{2}$ (the $+\mu/2$ from the $-\mu(n-\tfrac12)$ constant), with `ε_m` the non-negative BdG eigenvalues of the numeric `(A, B)` matrices
- Pairing kernel: $\Delta_{ij} = \Delta\, d(i,j)^{-\alpha}$, minimum-image distance on the ring, cutoff `d ≤ L/2` — no closed-form dispersion is used; the script builds `(A, B)` numerically and diagonalizes
- `α → ∞` limit: only the `d = 1` term survives, reproducing the nearest-neighbor Kitaev chain `ε(k) = √((2t cos k + μ)² + 4Δ² sin²k)` and its `e0_per_site`
- `α < 1` regime: gapless-like edge sector with massive Dirac edge modes and area-law violation (diagnostic, not scripted) [@Vodola2014]

## Oracle script

`python oracle.py --L 64 --mu 0.0 --t 1.0 --delta 1.0 --alpha 1.0` → prints `e0_per_site`, `gap`. Importable: `compute(L=64, mu=0.0, t=1.0, delta=1.0, alpha=1.0)`; `matrices(...)` returns the BdG `(A, B)`.
Self-test anchors: (1) `α = 30` reproduces the NN `kitaev-chain` `e0_per_site` (`L=64, μ=0.5`) to `1e-6`, importing `kitaev-chain/oracle.py` by path (no code duplication); (2) BdG ground energy matches brute-force ED (`ed.fermion_ops`, `L=8, α=1.5, μ=0.5`) to `1e-10`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e0_per_site` | `α=30, μ=0.5, t=Δ=1, L=64` | `-1.0156870128` (= NN Kitaev) | [@Kitaev2001] |
| `e0_per_site` (`L=8`, ED) | `α=1.5, μ=0.5, t=Δ=1` | `-1.0128951194` | self-test |
| `e0_per_site` | `α=1.5, μ=0, t=Δ=1, L=64` | `-1.0301797662` | this card |

## Verification recipes

- To check a BdG run at size `L`, PBC: compare `e0_per_site` and `gap` from `oracle.py --L <L> --mu <μ> --alpha <α>`, tolerance `1e-8` (exact). Confirm the pairing convention (minimum-image distance, `L/2` cutoff, antipodal bond counted once) matches the code under test.
- Sanity limit: large `α` (e.g. `30`) must collapse onto `kitaev-chain/oracle.py` at the same `(μ, t, Δ, L)`.

## Key reference

[@Vodola2014] — Vodola, Lepori, Ercolessi, Gorshkov & Pupillo, "Kitaev chains with long-range pairing": establishes the power-law-pairing model, its massive Dirac edge modes for `α < 1`, and the area-law violation. Rendered: _(Wave 3)_.
