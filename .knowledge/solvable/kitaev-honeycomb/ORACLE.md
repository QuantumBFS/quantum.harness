# Kitaev honeycomb model — exact-solution oracle

Technique: T1 (free-fermion / Majorana) · Tier: A (closed-form, exact) · Script: S

## Hamiltonian & conventions

$$ H = -J_x \sum_{\langle ij\rangle_x}\sigma^x_i\sigma^x_j \;-\; J_y \sum_{\langle ij\rangle_y}\sigma^y_i\sigma^y_j \;-\; J_z \sum_{\langle ij\rangle_z}\sigma^z_i\sigma^z_j $$

honeycomb lattice, two sublattices `A, B` (two sites per unit cell, coordination `Z=3`); the three inequivalent bond directions `x/y/z` carry, respectively, `σ^xσ^x`, `σ^yσ^y`, `σ^zσ^z` couplings (the bond-dependent "compass" structure). Conventions: Pauli-matrix operators `σ^a` (NOT `S^a` — a factor 4 per bond vs the `S`-convention); `J_a > 0` ferromagnetic per the sign above; the largest coupling sets the energy unit; isotropic point `J_x=J_y=J_z`. See `.knowledge/conventions.md`.

**Basis used here.** Primitive Bravais vectors `n1 = (1, 0)`, `n2 = (1/2, √3/2)` (lattice constant 1). Within a unit cell the `A`-site couples to `B(r)` by the `z`-bond (`J_z`), to `B(r+n1)` by the `x`-bond (`J_x`), and to `B(r+n2)` by the `y`-bond (`J_y`). The Majorana off-diagonal Bloch factor is

$$ f(\mathbf k) = J_z + J_x\,e^{i\mathbf k\cdot n_1} + J_y\,e^{i\mathbf k\cdot n_2}, \qquad \varepsilon(\mathbf k) = 2|f(\mathbf k)| $$

`|f|` depends on `k` only through the reduced coordinates `u = k·n1`, `v = k·n2` (each a full `2π` period, constant Jacobian), so every BZ average / minimum below is an exact uniform quadrature on `(u,v) ∈ [0,2π)²`. The isotropic Dirac point is `K = (2π/3, 2π/√3)`, i.e. `(u,v) = (2π/3, 4π/3)`, where `1 + e^{i2π/3} + e^{i4π/3} = 0` exactly.

Physics card: `.knowledge/models/kitaev-honeycomb/MODEL.md`. That card writes the identical Hamiltonian with the same Pauli `J_x,J_y,J_z` compass convention, the same two-site honeycomb geometry, the same gapless-B / gapped-A phase structure and boundary `|J_z| = |J_x|+|J_y|` (and cyclic), and Lieb's flux-free ground state. **Conventions match**; the model card does not fix a specific `(n1,n2)` axis convention for the Bloch factor (it states the real-space Hamiltonian only), so this card's basis choice above is this card's own realization within the model card's freedom — no conflict, no translation needed for `J_x,J_y,J_z`.

## Solvability statement

T1: Kitaev's four-Majorana representation `σ^a_j = i\,b^a_j c_j` (with the on-site gauge constraint `b^x b^y b^z c = 1`) turns each bond operator `\hat u_{jk} = i\,b^a_j b^a_k` into a **conserved** Z₂ gauge field, and every plaquette flux `W_p = \prod \hat u` is a constant of motion. In each fixed flux sector the Hamiltonian is a **quadratic** (free) Majorana hopping of the single `c`-Majorana per site — `σ^a_j σ^a_k = -i\,\hat u_{jk} c_j c_k`, so `H = i\sum_{\langle jk\rangle,\,j\in A} J_a \hat u_{jk} c_j c_k` — diagonalized exactly by Fourier transform, giving `ε(k) = 2|f(k)|`. By **Lieb's theorem** the ground state lies in the **flux-free sector** (`W_p = +1` on every plaquette), realized by the gauge `\hat u_{jk} = +1`; the quantities this card reports (`e0_per_site`, `gap`, `phase`) are the exact flux-free-sector values.

**Not exact:** nothing about this model is approximate — Lieb's theorem guarantees the flux-free sector solved here is the true ground-state sector, and within it the Majorana diagonalization is exact for every `k`. Out of this card's scope (still exact, from the same free-Majorana solution, just not implemented here): the energetics of **vortex/flux sectors** (excited `W_p = -1` plaquettes and the finite flux gap), the **field-induced non-Abelian phase** (a magnetic field opens a gap in the gapless B phase with spectral Chern number `ν = ±1` and Ising anyons — Kitaev's headline result), and the **anyon content** (toric-code `e/m` anyons and TEE `γ = ln 2` in the gapped A phase; Ising anyons in the field-induced phase).

## Exact results

- Majorana quasiparticle dispersion (flux-free sector): $\varepsilon(\mathbf k) = 2|f(\mathbf k)|$, $f(\mathbf k) = J_z + J_x e^{i\mathbf k\cdot n_1} + J_y e^{i\mathbf k\cdot n_2}$ [@Kitaev2006]
- **Ground-state energy per site** (prefactor derived below): $e_0 = -\tfrac12\,\langle|f|\rangle_{\text{BZ}} = -\dfrac{1}{2}\dfrac{1}{(2\pi)^2}\displaystyle\int_{\text{BZ}} |f(\mathbf k)|\,d^2k$ [@Kitaev2006]
- Quasiparticle gap: $\Delta = \min_{\mathbf k}\varepsilon(\mathbf k) = 2\min_{\text{BZ}}|f|$. In the gapped **A** phase (one `|J_a|` exceeds the sum of the other two) the three phasors cannot cancel and the minimum is $\Delta = 2\big(|J_{\max}| - |J_{\text{mid}}| - |J_{\min}|\big)$ (e.g. `J_z=2.5, J_x=J_y=1`: `Δ = 2(2.5−2) = 1`); in the gapless **B** phase `f` vanishes at the Dirac point and `Δ = 0`
- **Phase boundary** (triangle inequality): gapless **B** phase iff `|J_x| ≤ |J_y|+|J_z|` **and** `|J_y| ≤ |J_x|+|J_z|` **and** `|J_z| ≤ |J_x|+|J_y|`; otherwise gapped **A** phase [@Kitaev2006]

### Energy-per-site prefactor (derivation)

A quadratic Majorana Hamiltonian written `H = \tfrac{i}{2}\sum_{j<k} A_{jk} c_j c_k` (real antisymmetric `A`) has ground-state energy `E_0 = -\tfrac12\sum_m \varepsilon_m` over its non-negative single-particle levels. Here there is one level per unit cell, `ε(k) = 2|f(k)|`, so

$$ E_0 = -\tfrac12\sum_{\mathbf k}\varepsilon(\mathbf k) = -\sum_{\mathbf k}|f(\mathbf k)| = -N_{\text{uc}}\,\langle|f|\rangle_{\text{BZ}}, $$

and with **two sites per unit cell** `e_0 = E_0/(2N_{\text{uc}}) = -\tfrac12\langle|f|\rangle_{\text{BZ}}`. The `−1/2` (not `−1/4`) prefactor is **pinned exactly** by the decoupled-dimer limit `J_x=J_y=0, J_z=1`: then `|f|=1` everywhere so `e_0 = −1/2`, which is the exact per-site energy of an isolated `z`-dimer `H = −σ^z σ^z` (ground energy `−1` shared by two sites). This limit is asserted in `self_test()`.

## Oracle script

`python oracle.py --Jx 1.0 --Jy 1.0 --Jz 1.0 --n 600` → prints `e0_per_site`, `gap`, `phase`. Importable: `compute(Jx=1.0, Jy=1.0, Jz=1.0, n=600)`; helpers `f_k(k,...)` (physical-momentum Bloch factor), `f_uv(u,v,...)` (reduced-coordinate form), `e0(...)`, `gap(...)`, `phase(...)`. The BZ grid `n` is chosen divisible by 6 so both the Dirac point `(2π/3, 4π/3)` and the A-phase gap minimum `(π,π)` sit exactly on the grid.
Self-test anchors: (1) `f` vanishes exactly (`< 1e-12`) at the analytic `K` point for isotropic couplings, in both `f_k` and `f_uv` forms; (2) grid convergence `|e0(n=300) − e0(n=600)| < 1e-5` (both divisible by 3, Dirac cone on-grid); (3) prefactor pin — decoupled `z`-dimer limit gives `e0 = −1/2` to `1e-12`; (4) A phase (`J_z=2.5, J_x=J_y=1`) gapped with `gap = 1.0` and `phase == "A-gapped"`; (5) isotropic B phase gapless (`gap < 1e-6`, `phase == "B-gapless"`).

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e0_per_site` | isotropic `J_x=J_y=J_z=1` (Pauli convention) | `−0.787299` (`= −½⟨|f|⟩_BZ`, `⟨|f|⟩ ≈ 1.574597`) | [@Kitaev2006] |
| `gap` | isotropic (B phase, Dirac point) | `0` | [@Kitaev2006] |
| `e0_per_site` | decoupled dimers `J_x=J_y=0, J_z=1` | `−1/2` | derived above |
| `gap` | A phase `J_z=2.5, J_x=J_y=1` | `1` (`= 2(J_z−J_x−J_y)`) | derived above, [@Kitaev2006] |

The isotropic `e0_per_site ≈ −0.787299` is quoted in this card's **Pauli** normalization with the largest coupling `J = 1` in `H = −Σ J σσ`; converting to the `S^a`-spin convention `H = −Σ J S·S`-style couplings rescales by the usual factor-4-per-bond.

## Verification recipes

- To check an ED / Majorana-mean-field run of the pure Kitaev model at couplings `(J_x,J_y,J_z)`: confirm the flux sector is flux-free first (Lieb), then compare `e0_per_site` from `oracle.py --Jx <..> --Jy <..> --Jz <..>`, tolerance `1e-6` (grid-quadrature limited; tighten by raising `--n`).
- To locate the B→A transition: sweep one coupling across `|J_max| = |J_mid| + |J_min|` and confirm `gap → 0` at the boundary and `phase` flips between `B-gapless` and `A-gapped`.

## Key reference

[@Kitaev2006] — Kitaev, "Anyons in an exactly solved model and beyond", Ann. Phys. **321**, 2 (2006): the foundational paper giving the four-Majorana solution, the conserved plaquette fluxes and Lieb flux-free ground state, the full gapless-B / gapped-A phase diagram (triangle inequality), and the field-induced non-Abelian (Ising-anyon) phase — the defining exact solution whose flux-free-sector spectrum and energy this card reproduces. Rendered: _(Wave 3)_.
