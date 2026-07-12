# Color code (6.6.6) — exact-solution oracle

Technique: T4 (commuting-projector / stabilizer) · Tier: A (closed-form, exact) · Script: S

## Hamiltonian & conventions

$$ H = -\sum_{f} X_f \;-\; \sum_{f} Z_f, \qquad X_f=\prod_{i\in f}\sigma^x_i,\quad Z_f=\prod_{i\in f}\sigma^z_i $$

the **6.6.6 (honeycomb) topological color code** on a torus. Spin-1/2 qubits live on the **vertices** of a honeycomb lattice (degree 3); every hexagonal face `f` carries **both** an X-stabilizer `X_f = σ^{x⊗6}` and a Z-stabilizer `Z_f = σ^{z⊗6}` (a CSS code). A `cells×cells` torus of unit cells has `F = cells²` hexagons, `n = 2\,cells²` qubits, and `2\,cells²` stabilizer generators. Two hexagons share `0` or `2` vertices, so every `X_f`/`Z_f` pair commutes (2 anticommuting `σ^xσ^z` overlaps → even → commute); coupling set to the energy unit. Hexagons are traced as the 6-cycle `A(i,j), B(i,j), A(i{+}1,j), B(i{+}1,j{-}1), A(i{+}1,j{-}1), B(i,j{-}1)` on the two-site (`A/B`) unit cell. See `.knowledge/conventions.md`. No model-zoo sibling card exists for the color code (the `models/toric-code` card is the closest relative).

**3-colorability.** Hexagon centres form a triangular lattice; a proper 3-face-colouring `c(i,j) = (i-j) \bmod 3` exists iff both torus dimensions are multiples of 3 (adjacent faces sit at triangular offsets `{(\pm1,0),(0,\pm1),(1,-1),(-1,1)}`, all of which change `c`). The smallest torus is therefore `cells = 3` (`n = 18` qubits, 9 hexagons, 18 stabilizers). `self_test()` verifies the colouring is proper for `cells ∈ {3,6}`.

## Solvability statement

T4: the color code is a **commuting-projector stabilizer Hamiltonian**. The ground space is the simultaneous `+1` eigenspace of every `X_f` and `Z_f`, and the full spectrum is `E = -N_s + 2\,(\#\text{violated})` with `N_s = 2\,cells²`. The reported `gsd` is **exact** for every valid torus size; there is no approximation. **Not exact:** nothing about this model is approximate. Exact content deliberately **out of this card's scope** (all still exact from the same stabilizer structure, just not implemented): the string/logical operators and code distance, the anyon/charge-flux labelling by colour, and the transversal Clifford gates that make the color code notable. The `gsd` comes from an exact GF(2) rank (`_lib.gf2.stabilizer_gsd_log2`, which asserts pairwise commutation internally — reaching the correct value is itself a proof the honeycomb-torus stabilizers all commute), not from an eigensolver.

## Exact results

- **Full spectrum**: `E = -N_s + 2\,(\#\text{violated stabilizers})`, `N_s = 2\,cells²` [@BombinMartinDelgado2006]
- **Ground-state degeneracy**: `GSD = 2^{4g}` on a genus-`g` surface; on the torus (`g = 1`) `GSD = 16`, **size-independent** [@BombinMartinDelgado2006]. By generator counting `\log_2 GSD = n - \mathrm{rank} = 4` with `n = 2\,cells²` qubits and `2\,cells²` face stabilizers (their `2\,cells² - 4` rank reflects the four colour/charge dependencies among the `X`- and `Z`-faces on the torus).
- **Two-toric-codes relation**: a color code is **locally equivalent to two decoupled copies of the toric code** — folding / a constant-depth local Clifford maps the 6.6.6 color code onto two toric codes, consistent with its `2·2 = 4` logical qubits per handle (`GSD = 4² = 16` on the torus vs `4` for one toric code) [@BombinMartinDelgado2006]. (Verified here at the level of the degeneracy count `16 = 4²`; the explicit unfolding circuit is out of scope.)

## Oracle script

`python oracle.py --cells 3` → prints `gsd`, `n_qubits`, `n_hexagons`. Importable: `compute(cells=3)`; helpers `vertex_index`, `hexagon(i,j,cells)` (the six vertices of a face), `stabilizer_rows(cells)` (binary symplectic `(x|z)` rows, X-face then Z-face per hexagon), `_three_coloring_ok(cells)` (proper-colouring check).
Self-test anchors: (1) `gsd == 16` for `cells = 3` **and** `cells = 6` — size-independent `2^{4g}` on the torus, from the GF(2) rank; (2) `n_qubits == 18`, `n_hexagons == 9` at `cells = 3`; (3) `_three_coloring_ok(3)` and `_three_coloring_ok(6)` — the face 3-colouring `c=(i-j)\bmod3` is proper (no two adjacent hexagons share a colour). Reaching `gsd == 16` also certifies (via the internal assertion in `stabilizer_gsd_log2`) that every X-/Z-face pair commutes on this honeycomb torus.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `gsd` | torus, `cells ≡ 0 (mod 3)` | `16` (`= 2^{4g}`, `g=1` `= 4²`) | [@BombinMartinDelgado2006] |
| `n_qubits` | `cells×cells` torus | `2\,cells²` (`= 18` at `cells=3`) | — |
| `n_hexagons` | `cells×cells` torus | `cells²` (`= 9` at `cells=3`) | — |

## Verification recipes

- To check an ED / stabilizer-tableau construction of the 6.6.6 color code on a torus: compare `gsd` from `oracle.py --cells <c>` (exact integer `16` for any `c` divisible by 3) and confirm the face 3-colouring exists (fails when `c` is not a multiple of 3).
- Consistency check against `toric-code`: the color-code torus GSD (`16`) must equal the **square** of the toric-code torus GSD (`4`), reflecting `color code ≃ 2 × toric code`.

## Key reference

[@BombinMartinDelgado2006] — Bombín & Martin-Delgado, "Topological quantum distillation", Phys. Rev. Lett. **97**, 180501 (2006): the paper that introduces topological color codes on trivalent 3-colorable lattices, the dual `X`/`Z` face-stabilizer construction on every face, and the transversal Clifford structure — the exact code whose torus degeneracy this card reproduces. Rendered: _(Wave 3)_.
