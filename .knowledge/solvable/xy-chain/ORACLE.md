# Anisotropic XY chain — exact-solution oracle

Technique: T1 (free-fermion / Jordan–Wigner) · Tier: A (closed-form, exact) · Script: S

## Hamiltonian & conventions

$$ H = J\sum_{i=1}^{L}\left[(1+\gamma)\,S^x_i S^x_{i+1} + (1-\gamma)\,S^y_i S^y_{i+1}\right] - h\sum_{i=1}^{L} S^z_i, \qquad \text{PBC } (S_{L+1}\equiv S_1) $$

Conventions: spin-`S=½` operators `S^a = σ^a/2` (the harness default, **not** Pauli — a factor of 4 per bilinear vs the `σ^a` convention; matches the `S^a` convention of `.knowledge/models/xxz-chain`), `J` the exchange (energy unit `J = 1` by default), `γ ∈ [0,1]` the XY anisotropy, `h` the transverse field along `z`. `γ = 0` is the isotropic XX point; `γ = 1` is the (transverse-field) Ising limit. See `.knowledge/conventions.md`.

No model-zoo sibling under `.knowledge/models/` for the anisotropic XY chain; its `γ = 1` line maps exactly onto `.knowledge/models/transverse-field-ising/MODEL.md` (dictionary below), and the solvable exemplar `tfim-chain/` is the companion card.

## Solvability statement

T1: the Jordan–Wigner transformation `c_i = (∏_{j<i} σ^z_j)\,σ^-_i` maps the chain to free fermions with pairing, i.e. a quadratic (Bogoliubov-diagonalizable) Hamiltonian. Everything reported here — the full single-particle spectrum via `ε(k)`, the ground-state energy per site at finite `L` and in the thermodynamic limit, and the gap — is exact for any `L, γ, h`. The model is exactly solvable in its entirety; there is no approximation. **Not exact:** nothing about this model is approximate. Exact quantities not implemented here (out of this card's ground-state-statics scope): the Barouch–McCoy spin–spin correlators `⟨S^x_i S^x_j⟩`, `⟨S^y_i S^y_j⟩`, `⟨S^z_i S^z_j⟩` (Toeplitz-determinant / Pfaffian expressions of the free-fermion correlation matrix) and the transverse magnetization, plus all finite-`T` and quench quantities (also exactly computable from the same free-fermion solution).

## Boundary-sector subtlety (important)

A PBC **spin** chain maps to a **parity-dependent** fermion boundary condition. The even-fermion-parity sector uses antiperiodic (ABC) hopping across the `L→1` seam (wrap-bond sign flipped); the odd-parity sector uses periodic (PBC) fermions. The true ground-state energy is the **lower of the two BdG ground energies**, and which sector wins depends on the parameters: at the ED-checked points `(γ,h)` the winner is `(0,0)→ABC`, `(0.7,0.3)→PBC`, `(1.0,0.5)→ABC`. `compute` evaluates both sectors and returns the minimum together with the winning `sector` label (verified against exact ED to `1e-10`, so the Gaussian BdG ground state of the winning sector lands in the physically allowed parity at every point here). In the thermodynamic limit the two sectors converge and the distinction is `O(1/L)`.

## Exact results

- Single-fermion dispersion (`J = 1`): $\varepsilon(k) = \sqrt{(\cos k + h)^2 + \gamma^2 \sin^2 k}$ (general `J`: $\varepsilon(k) = \sqrt{(J\cos k + h)^2 + J^2\gamma^2\sin^2 k}$) [@LiebSchultzMattis1961]
- Ground-state energy per site: $e_0 = \min_{\text{sector}}\left[\dfrac1L\Big(\tfrac12\operatorname{tr}A - \tfrac12\sum_m \varepsilon_m\Big)\right] - \dfrac{h}{2}$, the $-h/2$ from normal-ordering $S^z_i = \tfrac12 - n_i$
- XX point (`γ = 0, h = 0`): $e_0 = -\dfrac1\pi = -\dfrac{1}{2}\cdot\dfrac{1}{2\pi}\displaystyle\int_0^{2\pi}|\cos k|\,dk$
- `γ = 1` ↔ transverse-field Ising: $H(\gamma{=}1) = \tfrac{J}{2}\sum σ^x_i σ^x_{i+1} - \tfrac{h}{2}\sum σ^z_i$, i.e. the TFIM `H = -J_{\text{Is}}\sumσ^zσ^z - Γ\sumσ^x` (up to an axis relabel) with **exact dictionary** $J_{\text{Is}} = J/2,\ Γ = h/2$; at `J = h = 1` this gives $e_0 = -2/\pi$, matching the TFIM closed form $-\tfrac{2}{\pi}(J_{\text{Is}}+Γ)E(m)$ at criticality (`m = 1`, `E(1) = 1`)

## Oracle script

`python oracle.py --L 64 --gamma 0.0 --h 0.0 --J 1.0` → prints `e0_per_site`, `gap`, `sector`. Importable: `compute(L=64, gamma=0.0, h=0.0, J=1.0)`; `matrices(L, gamma, h, J, sector)` returns the BdG `(A, B)` for `sector ∈ {"abc","pbc"}`.
Self-test anchors: (1) XX point (`γ=0, h=0`, `L=2000`) gives `e0 = -1/π` to `1e-4`; (2) JW energy matches brute-force spin ED (`ed.spin_ops`, `L=8`) for `(γ,h) ∈ {(0,0),(0.7,0.3),(1.0,0.5)}` to `1e-10`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e0_per_site` (thermo) | `γ=0, h=0` (XX) | `-1/π ≈ -0.318310` | [@LiebSchultzMattis1961] |
| `e0_per_site` (`L=8`, ED) | `γ=0, h=0` | `-0.3266407412` (sector ABC) | self-test |
| `e0_per_site` (`L=8`, ED) | `γ=0.7, h=0.3` | `-0.4405791876` (sector PBC) | self-test |
| `e0_per_site` (`L=8`, ED) | `γ=1.0, h=0.5` | `-0.5318176397` (sector ABC) | self-test |
| `e0_per_site` (thermo) | `γ=1, J=h=1` (Ising critical) | `-2/π ≈ -0.636620` | TFIM map [@LiebSchultzMattis1961] |

## Verification recipes

- To check a DMRG/ED run at size `L`, PBC: compare `e0_per_site` from `oracle.py --L <L> --gamma <γ> --h <h>`, tolerance `1e-8` (exact). For small `L` note that the winning boundary sector can be either ABC or PBC — `compute` already takes the minimum, but a fixed-sector code must compare against the same sector.
- To cross-check against `tfim-chain/`, set `γ = 1` and use `J_Is = J/2, Γ = h/2`.

## Key reference

[@LiebSchultzMattis1961] — Lieb, Schultz & Mattis, "Two soluble models of an antiferromagnetic chain": the original Jordan–Wigner solution of the XY chain, source of the dispersion and the free-fermion (ABC/PBC parity-sector) treatment used here. Rendered: _(Wave 3)_.
