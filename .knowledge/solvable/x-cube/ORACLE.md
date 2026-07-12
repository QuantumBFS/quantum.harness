# X-cube model (fracton) — exact-solution oracle

Technique: T4 (commuting-projector / stabilizer) · Tier: A (closed-form, exact) · Script: S

## Hamiltonian & conventions

$$ H = -\sum_{c} A_c \;-\; \sum_{v,\,\mu\nu} B^{\mu\nu}_v, \qquad A_c=\prod_{i\in c}\sigma^x_i,\quad B^{\mu\nu}_v=\prod_{i\in \times^{\mu\nu}_v}\sigma^z_i $$

the **X-cube model** on an `L×L×L` cubic **torus** (PBC³). Spin-1/2 qubits live on the **edges** (`n = 3L³` qubits). The X-type cube term `A_c` is the product of `σ^x` over the **12 edges** of an elementary cube `c`; the Z-type vertex term `B^{μν}_v` is a **planar 4-edge cross** — the product of `σ^z` over the four edges incident to vertex `v` that lie in the `μν` plane (`μν ∈ {xy, yz, zx}`). At each vertex the three planar crosses satisfy one relation (`B^{xy}_v B^{yz}_v B^{zx}_v = \mathbb{1}`, every edge appearing twice), so only **two of the three are independent**; all three are included and the GF(2) rank removes the dependency. Any cube and any planar cross overlap in an **even** number of edges, so all `A_c`, `B^{μν}_v` mutually commute; coupling set to the energy unit. Edges are indexed `(vertex, direction)` — `edge_index(x,y,z,d) = 3((zL+y)L+x)+d`, `d ∈ {0,1,2}` for `{+x,+y,+z}`. See `.knowledge/conventions.md`. No model-zoo sibling card exists for the X-cube model (the `models/toric-code` card is the closest relative).

Rows are built by **XOR-toggling** edge bit positions, so that if a periodic wrap ever makes two formally distinct edges coincide (a concern at the smallest torus `L=2`) the duplicated Pauli **cancels** rather than being double-counted.

## Solvability statement

T4: the X-cube model is a **commuting-projector stabilizer Hamiltonian**. The ground space is the simultaneous `+1` eigenspace of every cube `A_c` and every planar cross `B^{μν}_v`, and the **entire spectrum** is enumerated by counting violated stabilizers, `E = -N_s + 2\,(\#\text{violated})`. The reported subextensive degeneracy `gsd_log2 = \log_2 GSD` is **exact** for every `L`; there is no approximation. **Not exact:** nothing about this model is approximate. Exact content deliberately **out of this card's scope** (all still exact from the same stabilizer structure, just not implemented in `oracle.py`): the fracton/lineon excitation content and their restricted mobility, the fractal/planar logical-operator membranes, the entanglement structure, and the RG/coupled-layer construction relating X-cube to stacks of 2D toric codes. The `gsd_log2` is obtained from an exact GF(2) rank (`_lib.gf2.stabilizer_gsd_log2`, which also asserts pairwise commutation), not from a numerical eigensolver.

## Exact results

- **Full spectrum**: `E = -N_s + 2\,(\#\text{violated stabilizers})`, `N_s = L³` cubes `+ 3L³` vertex crosses (of which `2L³` per-vertex are independent).
- **Subextensive ground-state degeneracy**: `\log_2 GSD = 6L - 3` on the `L×L×L` torus [@VijayHaahFu2016]. The degeneracy **grows with system size** — the defining signature of a **fracton (Type-I) topological order**, unlike the size-independent `GSD` of a conventional topological code. By generator counting `\log_2 GSD = n - \mathrm{rank}` with `n = 3L³` edges and `4L³` stabilizer rows whose rank is `3L³ - (6L-3)`.
- **Restricted mobility**: violating cube terms creates **fractons** (immobile point excitations sitting at cube-flip corners, movable only in bound groups); composites of two fractons form **lineons** that move only along a single lattice line [@VijayHaahFu2016]. Type-I: some excitations are mobile along sub-dimensional manifolds, but no fully mobile isolated charge exists.

## Oracle script

`python oracle.py --L 3` → prints `gsd_log2`, `n_qubits`. Importable: `compute(L=3)`; helpers `edge_index(x,y,z,d,L)`, `cube_edges(x,y,z,L)` (12 edges of a cube), `vertex_crosses(x,y,z,L)` (the three planar 4-edge crosses at a vertex), `stabilizer_rows(L)` (binary symplectic `(x|z)` rows, X-cubes then Z-crosses, built by XOR-toggle).
Self-test anchors: (1) `gsd_log2 == 6L - 3` for `L ∈ {2,3}` (the Vijay–Haah–Fu subextensive degeneracy, from the GF(2) rank — `9` at `L=2`, `15` at `L=3`); (2) `n_qubits == 3L³`. Reaching `6L-3` also certifies (via the internal assertion in `stabilizer_gsd_log2`) that every cube/planar-cross pair commutes on the cubic torus, including at `L=2` where the XOR row-build guards against wrap-induced edge coincidences.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `gsd_log2` | `L=2` torus | `9` (`= 6·2-3`) | [@VijayHaahFu2016] |
| `gsd_log2` | `L=3` torus | `15` (`= 6·3-3`) | [@VijayHaahFu2016] |
| `gsd_log2` | `L×L×L` torus | `6L - 3` (subextensive) | [@VijayHaahFu2016] |
| `n_qubits` | `L×L×L` torus | `3L³` | — |

## Verification recipes

- To check an ED / stabilizer-tableau construction of the X-cube model on a cubic torus: compare `gsd_log2` from `oracle.py --L <L>` against `6L - 3` (exact integer). The **linear-in-`L`** growth is the diagnostic that distinguishes fracton order from a conventional topological code (constant `\log_2 GSD`).
- Consistency: the degeneracy must be **subextensive** — `\log_2 GSD ∝ L`, not `∝ L³` (extensive) nor constant (topological). Any construction giving a size-independent value has the wrong stabilizer group.

## Key reference

[@VijayHaahFu2016] — Vijay, Haah & Fu, "Fracton topological order, generalized lattice gauge theory, and duality", Phys. Rev. B **94**, 235157 (2016): introduces and names the X-cube model, derives its subextensive ground-state degeneracy `\log_2 GSD = 6L - 3` on the 3-torus, and classifies its fracton/lineon excitations and restricted mobility via the coupled-layer / generalized-gauge-theory construction — the exact structure whose degeneracy this card reproduces. Rendered: _(Wave 3)_.
