# XYZ chain — exact-solution oracle

Technique: T3 (Bethe ansatz / Yang–Baxter) · Tier: B (integrable) · Script: P

## Hamiltonian & conventions

$$ H = \sum_{i=1}^{N}\left( J_x\, S^x_i S^x_{i+1} + J_y\, S^y_i S^y_{i+1} + J_z\, S^z_i S^z_{i+1}\right), \qquad \text{PBC } (\mathbf{S}_{N+1}\equiv\mathbf{S}_1) $$

Conventions: spin-½ `S`-operators (`S^a = σ^a/2`), fully anisotropic couplings `(J_x, J_y, J_z)`, nearest-neighbour bonds counted once, `N` even (bipartite ring). Special cases: `J_x=J_y` is the XXZ chain (sibling card `xxz-chain`, with `Δ = J_z/J_x`); `J_x=J_y=J_z` is the isotropic Heisenberg point (`heisenberg-xxx`); `J_z=0` is the anisotropic XY chain at zero field (`xy-chain` with `h=0`). See `.knowledge/conventions.md`.

No dedicated model-zoo card for the fully anisotropic chain; its reductions map onto `.knowledge/models/xxz-chain` (XXZ line) and the `xy-chain` oracle (XY line).

## Solvability statement

T3 (Yang–Baxter): the XYZ chain is the row-to-row transfer-matrix Hamiltonian of Baxter's **eight-vertex model**; the eight-vertex `R`-matrix satisfies the Yang–Baxter equation with an **elliptic** parametrization of the spectral parameter, and Baxter's solution gives the exact thermodynamic ground-state energy per site as a closed-form elliptic-function expression [@Baxter1972]. The model is Bethe-ansatz integrable for every `(J_x, J_y, J_z)`. **Not exact in closed form (Tier B):** the full spectrum, correlation functions, and finite-`T` thermodynamics need the (elliptic) Bethe equations / TBA state-by-state — integrable but not single closed forms; out of scope.

## Script scope (P — read this)

This card ships a **partial** oracle. The scriptable `e0(J_x,J_y,J_z)` is **exact (closed form)** on the two integrable *limit lines*, delegated by importlib cross-load to the sibling cards so no physics is duplicated:

- **XXZ limit** — when two couplings are equal (in-plane pair value `a`, odd coupling `c`): `e0 = |a|\cdot e_0^{\text{XXZ}}(c/|a|)`, where `e_0^{\text{XXZ}}` is the exact Yang–Yang integral/series from `xxz-chain/oracle.py`. (`|a|` via the two-sign-flip symmetry, so `a<0` is handled.)
- **XY limit** — when one coupling is zero (non-zero pair `p, q`): map to the `xy-chain` parametrization `H = J[(1+γ)S^xS^x + (1-γ)S^yS^y]` via `J=(p+q)/2`, `γ=(p-q)/(p+q)` (positive `J` via two-sign-flip; `xy` `e0` is even in `γ`); `e0` is the exact free-fermion value from `xy-chain/oracle.py`.

For a **generic point** (all three couplings distinct and non-zero) the exact statement is Baxter's elliptic formula [@Baxter1972], which this card **tabulates but does not evaluate**. Instead the script ships a **finite-`L` ED-extrapolated estimate** (`1/L^2` Richardson over `L∈{8,10,12}`, PBC), explicitly labelled non-closed-form. This is the deliberate P-scope choice: an honest ED-extrapolation plus the exact formula tabulated, **not** a half-coded elliptic parametrization.

## The eight-vertex / elliptic story

Baxter mapped the XYZ chain to the two-dimensional eight-vertex model and solved it by commuting transfer matrices. The three couplings are parametrized by Jacobi elliptic functions of a modulus `k` and a spectral parameter `η` (schematically `J_x:J_y:J_z = 1 : \mathrm{sn}\!:\!… : \mathrm{cn}\,\mathrm{dn}`), and the ground-state energy per site is an elliptic-theta expression [@Baxter1972]. The XXZ line is the trigonometric (`k→0`) degeneration — which is exactly why the XXZ card's integral/series suffices there, and why this card delegates rather than re-deriving. Two exact symmetries make useful cheap checks: **e0 is invariant under any permutation of `(J_x,J_y,J_z)`** (a global `π/2` spin rotation relabelling axes) and **under a simultaneous sign flip of any two couplings** (a `π` rotation about the third axis on one sublattice, exact on an even-`L` bipartite ring).

## Exact results

- Thermodynamic ground-state energy per site: Baxter's exact elliptic-function expression for the eight-vertex / XYZ chain [@Baxter1972] (tabulated here; evaluated in closed form on the XXZ/XY lines only)
- XXZ line (`J_x=J_y=a`): `e_0 = |a|\,\big(\tfrac{\cos γ}{4} - \sin^2γ\!\int … \big)` etc. — the exact Yang–Yang result at `Δ=J_z/|a|` [@YangYang1966b] (see `xxz-chain`)
- XY line (`J_z=0`): `e_0` the exact Jordan–Wigner free-fermion energy at `J=(J_x+J_y)/2`, `γ=(J_x-J_y)/(J_x+J_y)` [@LiebSchultzMattis1961] (see `xy-chain`)
- Symmetries: `e_0(J_x,J_y,J_z)` invariant under permutations of `(J_x,J_y,J_z)` and under simultaneous sign flip of any two couplings

## Oracle script

`python oracle.py --Jx 1.0 --Jy 0.7 --Jz 0.4 --L 10` → prints `jx, jy, jz, e0_per_site` (exact on XXZ/XY lines; ED-extrapolated generic), `e0_ed_finite` (direct ED at `L`), `L`, `method`. Importable: `compute(Jx, Jy, Jz, L=10)`; `e0(Jx,Jy,Jz)`, `e0_exact(Jx,Jy,Jz)` (raises off the limit lines), `_ed_energy(Jx,Jy,Jz,L)`.

Self-test anchors: (1) **XXZ limit** — `e0(1,1,Δ)` reproduces `xxz-chain`'s `e0(Δ)` (importlib) to `1e-8` for `Δ∈{0.5,2.0}`; (2) **XY limit** — for `J_z=0` the thermodynamic `e0` matches `xy-chain.compute` to `1e-12`, and the finite-`L` XYZ Hamiltonian ED equals `xy-chain`'s ED at `L=8` to `1e-10` (dictionary check); (3) **generic** — the ED-extrapolated `e0` at `(1,0.7,0.4)` and `(1,0.8,0.6)` is within `5%` of the direct `L=10` ED (ground truth); (4) **permutation symmetry** — `_ed_energy` at `L=8` invariant under `J_x↔J_y` and `J_x↔J_z` to `1e-9`; (5) **two-sign-flip symmetry** — invariant under flipping `(J_x,J_y)` and `(J_y,J_z)` to `1e-9`.

## Benchmarks

`e0 ≡ E/N` thermodynamic (exact on limit lines) or ED-extrapolated (generic); `S=σ/2`, PBC.

| Quantity | Params | Value | Source |
|---|---|---|---|
| `e0_per_site` (exact, XXZ line) | `(1,1,0.5)` | `-0.3750000` | [@YangYang1966b] via `xxz-chain` |
| `e0_per_site` (exact, XXZ line) | `(1,1,2.0)` | `-0.6172220` | [@YangYang1966b] via `xxz-chain` |
| `e0_per_site` (exact, XY line) | `(1,1,0)` (XX) | `-1/π ≈ -0.3183099` | [@LiebSchultzMattis1961] via `xy-chain` |
| `e0_per_site` (exact, XY line) | `(1.4,0.6,0)` | `-0.3662651` | [@LiebSchultzMattis1961] via `xy-chain` |
| `e0_per_site` (ED-extrap, generic) | `(1,0.7,0.4)` | `-0.3199262` (non-closed-form; `L=10` ED `-0.3253344`) | this card; exact form [@Baxter1972] |
| `e0_per_site` (ED-extrap, generic) | `(1,0.8,0.6)` | `-0.3580140` (non-closed-form; `L=10` ED `-0.3647016`) | this card; exact form [@Baxter1972] |

The two generic rows are **finite-`L` ED extrapolations**, not closed-form values; the exact thermodynamic statement for those points is Baxter's elliptic formula [@Baxter1972]. The XXZ/XY rows are exact (delegated to the sibling oracles).

## Verification recipes

- To check a DMRG/ED run on the XXZ line (`J_x=J_y`): use `e0(J_x,J_x,J_z) = |J_x|\,e_0^{\text{XXZ}}(J_z/|J_x|)` (exact), tolerance set by the run's finite-size gap.
- To check a run on the XY line (`J_z=0`): use `e0(J_x,J_y,0)` (exact free-fermion), or directly `xy-chain` with `J=(J_x+J_y)/2`, `γ=(J_x-J_y)/(J_x+J_y)`.
- Generic point: compare a finite-`L` PBC energy against `oracle.py --Jx … --Jy … --Jz … --L <L>`'s `e0_ed_finite` (same `L`, exact), or against the `1/L^2`-extrapolated `e0_per_site` for the thermodynamic estimate. For the exact thermodynamic value use Baxter's formula [@Baxter1972].
- Cheap sanity checks on any XYZ code: energy must be invariant under permuting `(J_x,J_y,J_z)` and under flipping the sign of any two couplings.

## Key reference

[@Baxter1972] — Baxter, "One-dimensional anisotropic Heisenberg chain", Ann. Phys. **70**, 323 (1972): the exact eight-vertex/XYZ solution giving the thermodynamic ground-state energy in closed elliptic form (tabulated here). The XXZ-line reduction is Yang–Yang [@YangYang1966b] and the XY-line reduction is Lieb–Schultz–Mattis [@LiebSchultzMattis1961], reused via the sibling oracle cards. Rendered: _(Wave 3)_.
