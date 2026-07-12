# Haldane model (Chern insulator) — exact-solution oracle

Technique: T1 (free-fermion / Bloch diagonalization) · Tier: A (closed-form, exact) · Script: S

## Hamiltonian & conventions

$$ H = t_1 \sum_{\langle ij\rangle} c^\dagger_i c_j \;+\; t_2 \sum_{\langle\langle ij\rangle\rangle} e^{i\phi_{ij}}\, c^\dagger_i c_j \;+\; M \sum_i \xi_i\, n_i $$

honeycomb lattice, two sublattices `A, B`; `t_1` real NN hopping, `t_2` complex NNN (same-sublattice) hopping with orientation-dependent phase `φ_{ij}=±φ`, `M` the sublattice (Semenoff) mass (`ξ_i=+1` on A, `-1` on B).

**Bloch form used here** (reduced crystal-momentum coordinates `u = k·A_1`, `v = k·A_2`, each a full `2π` period, `A_1, A_2` the honeycomb's primitive Bravais vectors at 60° — identical device to `tight-binding-lattices/oracle.py`'s honeycomb block, 2 sites/cell, A–B bonds at cell offsets `0, -A_1, -A_2`; this "periodic gauge" choice, dropping the intra-cell sublattice offset from the phase, is what makes `H(u,v)` exactly `2π`-periodic in `u` and `v` separately, as `_lib.topology.chern`'s `[0,2π)²` grid requires — a naive convention using the literal A→B bond vectors instead gives Bloch factors periodic only in `6π`, breaking the FHS loop closure; this was checked and rejected before adopting the form below):

$$ f(u,v) = 1 + e^{iu} + e^{iv} \qquad \text{(NN Bloch factor)} $$
$$ d_0(u,v) = 2t_2\cos\phi\,[\cos u + \cos(v{-}u) + \cos v] $$
$$ d_3(u,v) = M - 2t_2\sin\phi\,[\sin u + \sin(v{-}u) - \sin v] $$
$$ H(u,v) = \begin{pmatrix} d_0+d_3 & t_1 f \\ t_1 f^* & d_0 - d_3 \end{pmatrix} $$

`d_0, d_3` sum over the three NNN bond vectors `b_1=A_1, b_2=A_2-A_1, b_3=-A_2` (reduced arguments `u, v-u, -v`; these three sum to zero, the standard closed triangle of second-neighbor hops on the triangular sublattice formed by each honeycomb sublattice on its own) — this is exactly the task brief's "standard Haldane form" `d_3 = M - 2t_2\sin\phi\sum_i \sin(k\cdot b_i)`, with the `a_i` (NN, entering `f`) / `b_i` (NNN) vector conventions now stated explicitly. Energy unit `t_1 = 1` default; `t_2, \phi, M` are the tunable parameters. See `.knowledge/conventions.md`.

Physics card: `.knowledge/models/haldane-chern/MODEL.md`. That card writes the identical Hamiltonian `H = t_1 Σ c†c + t_2 Σ e^{iφ}c†c + M Σ ξ_i n_i` with the same `t_1, t_2, φ, M` meanings, the same topological criterion `|M| < 3\sqrt3\,t_2\sinφ`, and the same class-A Chern-insulator phase. **Conventions match**; the model card does not fix a specific reduced-`(u,v)` axis convention for the Bloch matrix (it states the real-space Hamiltonian only), so this card's `A_1, A_2`/periodic-gauge choice above is this card's own realization within the model card's freedom — no conflict, no translation needed for `t_1, t_2, φ, M` themselves.

## Solvability statement

T1: the Hamiltonian is quadratic and translationally invariant, block-diagonalized exactly by Fourier transform into the `2×2` Bloch matrix above, diagonalized exactly by `numpy.linalg.eigvalsh` for any `k`. Everything reported here — the Chern number of the filled lower band (Fukui–Hatsugai–Suzuki lattice-gauge invariant, `_lib.topology.chern`) and the closed-form phase boundary `M = \pm3\sqrt3\,t_2\sin\phi` (derived below from the exact Dirac-point locations) — follows from the exact Bloch Hamiltonian with no uncontrolled approximation. **Not exact:** nothing about this model is approximate. One quantity is obtained via a numerical routine that converges to the exact value rather than a closed-form substitution: `gap` (minimum direct gap over the BZ) is found by a finite grid scan (`nk_gap=200`) followed by a local Nelder–Mead refinement, converging to the true minimum but not evaluated from a closed form for generic `M` — although the *location* of that minimum (the Dirac point `K` or `K'`) **is** known in closed form and is what the `phase_boundary_M` closed-form result below is derived from directly (so the phase boundary itself is exact even though the generic-`M` `gap` value is found numerically). Out of this card's scope entirely (not attempted): the real-space ribbon/edge-mode spectrum, the Hall conductance as a transport (Kubo) calculation (equal to `chern` by TKNN, not separately computed), and the interacting Haldane–Hubbard extension (sign-problem-ful).

## Exact results

- **Dirac points**: `f(u,v)=0` at `(u,v) = K = (2\pi/3, 4\pi/3)` and `K' = (4\pi/3, 2\pi/3)` (identical to `tight-binding-lattices/oracle.py`'s `_dirac_K()` for the same honeycomb convention) — the two points where `d_1=d_2=0` (i.e. `f=0`), so the gap there is `2|d_3|`.
- **Phase-diagram closed form (headline result)**: substituting `K, K'` into `d_3(u,v)` gives, using `\sin u+\sin(v{-}u)-\sin v` evaluated at each point,
  $$ d_3(K) = M - 3\sqrt3\,t_2\sin\phi, \qquad d_3(K') = M + 3\sqrt3\,t_2\sin\phi $$
  so the gap closes at exactly one Dirac point when `M = \pm3\sqrt3\,t_2\sin\phi`, giving the **phase boundary**
  $$ \boxed{M_c = 3\sqrt3\,|t_2|\,|\sin\phi|} $$
  Topological (`|C|=1`) for `|M| < M_c`; trivial (`C=0`) for `|M| > M_c` [@Haldane1988]. This is reported as `phase_boundary_M` and matches the model-zoo card's `3\sqrt3\,t_2\sinφ` benchmark exactly.
- **Chern number sign**: at `M=0`, `C = -\,\mathrm{sgn}(t_2\sin\phi)` in this card's convention (verified in `self_test()`: flipping `t_2 \to -t_2` at fixed `\phi=\pi/2` flips `C`, `1/3 \to -1$ and `-1/3 \to +1`) — the Haldane model's defining feature, a quantized Hall response with **zero net flux** through the unit cell [@Haldane1988].

## Oracle script

`python oracle.py --t1 1.0 --t2 0.3333333333333333 --phi 1.5707963267948966 --M 0.0` → prints `chern`, `gap`, `phase_boundary_M`. Importable: `compute(t1=1.0, t2=1/3, phi=pi/2, M=0.0, nk=60, nk_gap=200)`; `bloch(u, v, t1, t2, phi, M)` returns the batched `2×2` Bloch matrix; `hk(...)` returns the scalar closure for `_lib.topology.chern`.
Self-test anchors: (1) `|chern| == 1` deep in the topological phase (`M=0, t_2=1/3, φ=π/2`); (2) `chern == 0` in the trivial phase (`M=2.0 > M_c ≈ 1.732`), and `phase_boundary_M` matches `3\sqrt3/3` to `1e-12`; (3) `chern` is odd under `φ → -φ`; (4) `gap < 1e-2` exactly on the phase boundary `M = M_c`; (5) `chern` is odd under `t_2 → -t_2` at fixed `φ`, and a smaller `φ` (same sign) gives the same `chern` but a strictly smaller `phase_boundary_M`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `phase_boundary_M` | `t_2=1/3, φ=π/2` | `\sqrt3 ≈ 1.7321` (`=3\sqrt3\cdot\frac13\cdot1`) | derived above, [@Haldane1988] |
| `chern` | `M=0, t_2=1/3, φ=π/2` | `-1` | derived above |
| `chern` | `M=2.0, t_2=1/3, φ=π/2` | `0` | derived above (`2.0 > 1.7321`) |
| `gap` | `M=phase_boundary_M, t_2=1/3, φ=π/2` | `0` (closes at `K`) | derived above |

## Verification recipes

- To check an ED/DMRG-with-twisted-BC calculation at a given `(t_1,t_2,φ,M)`: compare `chern` (bulk, this card) against the number of chiral edge modes per edge in a ribbon calculation (bulk–boundary correspondence), tolerance exact (both integers).
- Directed transition check: sweep `M` across `\pm3\sqrt3\,t_2\sinφ` and confirm `gap → 0` at the crossing and `chern` flips by `±1` — the central self-consistency check for this model.
- Graphene-limit caution: `t_2=0` (or `sinφ=0`) makes the lower/upper bands touch everywhere the NN Dirac points sit (`phase_boundary_M=0`), so `chern` becomes gauge-dependent / ill-defined there (a spurious FHS integer can appear on a finite grid) — this card does **not** assert a value for `chern` in that gapless limit; only genuinely gapped `(M,t_2,φ)` give a meaningful Chern number.

## Key reference

[@Haldane1988] — Haldane, "Model for a Quantum Hall Effect without Landau Levels: Condensed-Matter Realization of the Parity Anomaly", Phys. Rev. Lett. **61**, 2015 (1988): the defining paper introducing this Hamiltonian, the zero-net-flux complex-NNN construction, and the `|M| < 3\sqrt3\,t_2\sinφ` topological criterion used throughout this card. Rendered: _(Wave 3)_.
