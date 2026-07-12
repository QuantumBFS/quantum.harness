# Toric code — exact-solution oracle

Technique: T5 (commuting-projector / stabilizer) · Tier: A (closed-form, exact) · Script: S

## Hamiltonian & conventions

$$ H = -\sum_v A_v \;-\; \sum_p B_p, \qquad A_v=\prod_{i\in v}\sigma^x_i,\quad B_p=\prod_{i\in p}\sigma^z_i $$

on an `L×L` square-lattice **torus** (PBC×PBC). Spin-1/2 qubits live on the **edges** (`n = 2L²` qubits); the star `A_v` is the product of `σ^x` over the four edges meeting at vertex `v`, the plaquette `B_p` the product of `σ^z` over the four edges bounding face `p`. Any two stabilizers share `0` or `2` edges, so all `A_v`, `B_p` mutually commute; coupling set to the energy unit (`J = 1`). Edges are indexed `(site, direction)` — `edge_index(x,y,d) = 2(yL+x)+d`, `d = 0` horizontal / `d = 1` vertical — so at `L = 2` each vertex still touches four **distinct** edges (no degenerate stars). See `.knowledge/conventions.md`.

Physics card: `.knowledge/models/toric-code/MODEL.md`. That card writes the **identical** Hamiltonian with the same Pauli convention, qubits-on-edges layout, and torus geometry. **Conventions match**; no translation needed. This oracle card adds the explicit `(site,direction)` edge indexing and the finite-`L` stabilizer-rank computation the model card leaves implicit.

## Solvability statement

T5: the toric code is a **commuting-projector stabilizer Hamiltonian**. The ground space is the simultaneous `+1` eigenspace of every `A_v` and `B_p`, and the **entire spectrum** is enumerated by counting violated stabilizers: `E = -N_s + 2\,(\#\text{violated})`, where `N_s = 2L²` is the number of stabilizer terms. Everything reported — the torus ground-state degeneracy `gsd` and the excitation gap `gap_pair` — is **exact** for every `L`; there is no approximation anywhere. **Not exact:** nothing about this model is approximate. Exact content deliberately **out of this card's scope** (all still exact from the same stabilizer structure, just not implemented in `oracle.py`): the anyon braiding data, the topological entanglement entropy `γ = ln 2`, the Wilson/'t Hooft loop logical operators and their algebra, and planar-boundary code distances. The `gsd` is obtained from an exact GF(2) rank (`_lib.gf2.stabilizer_gsd_log2`, which also asserts pairwise commutation), not from a numerical eigensolver.

## Exact results

- **Full spectrum**: `E = -N_s + 2\,(\#\text{violated stabilizers})`, `N_s = 2L²` [@Kitaev2003]
- **Ground-state degeneracy**: `GSD = 2^{2g}` on a genus-`g` surface; on the torus (`g = 1`) `GSD = 4`, size-independent. By generator counting `\log_2 GSD = n - \mathrm{rank}` with `n = 2L²` qubits and `2L²` stabilizers whose rank is `2L² - 2` — the two dependencies `\prod_v A_v = \prod_p B_p = \mathbb{1}` — giving `\log_2 GSD = 2` [@Kitaev2003]
- **Excitation gap** (`J = 1`): the cheapest excitation is a **pair** of like anyons. A single `A_v` (or `B_p`) cannot be violated in isolation because `\prod_v A_v = \mathbb{1}` forces the number of violated stars (and of violated plaquettes) to be **even**; creating the minimal pair violates two stabilizers, `ΔE = 2·2 = 4`. So `gap_pair = 4` on the torus [@Kitaev2003]
- **Anyon content**: `1, e` (violated `A_v`), `m` (violated `B_p`), `ε = e×m`; `e` and `m` are mutual semions (braiding phase `−1`) [@Kitaev2003]

## Oracle script

`python oracle.py --L 3` → prints `gsd`, `gap_pair`, `n_qubits`. Importable: `compute(L=3)`; helpers `edge_index`, `star_edges`, `plaquette_edges`, `stabilizer_rows(L)` (binary symplectic `(x|z)` rows), `_ed_hamiltonian(L)` (sparse `-ΣA-ΣB` for small-`L` ED).
Self-test anchors: (1) `gsd == 4` and `n_qubits == 2L²` for `L ∈ {2,3,4}` (size-independent torus degeneracy, from the GF(2) rank); (2) ED cross-check at `L = 2` (8 qubits, dim 256) — `ed.ground_states == 4` and `ed.gap == 4.0` to `1e-10`, confirming both the four-fold ground space and the pair gap directly from `-ΣA_v-ΣB_p`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `gsd` | torus, any `L` | `4` (`= 2^{2g}`, `g=1`) | [@Kitaev2003] |
| `gap_pair` | torus, `J = 1` | `4` (minimal anyon pair, `ΔE = 4`) | [@Kitaev2003] |
| `n_qubits` | `L×L` torus | `2L²` | — |

## Verification recipes

- To check an ED / DMRG run on the `L×L` toric code: compare `gsd` from `oracle.py --L <L>` (exact integer `4` on the torus) and confirm the lowest gap equals `4` at `J = 1` (a single anyon is forbidden by the product constraint — the first excited state is a two-anyon pair).
- To validate a topological-order toolkit: use `GSD = 4` on the torus and `γ = ln 2` (TEE, from the model card) as the canonical Z₂ anchors.

## Key reference

[@Kitaev2003] — Kitaev, "Fault-tolerant quantum computation by anyons", Ann. Phys. **303**, 2 (2003): the founding paper introducing the toric code, the stabilizer/commuting-projector construction, topological degeneracy `2^{2g}` on surfaces, the Abelian `e`/`m` anyons and their mutual `−1` braiding, and fault-tolerant computation by braiding — the exact structure whose GSD and gap this card reproduces. Rendered: _(Wave 3)_.
