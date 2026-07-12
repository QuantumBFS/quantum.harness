# Kitaev quantum double D(G) — exact-solution oracle

Technique: T4 (commuting-projector / stabilizer) · Tier: A (exact, algebraic) · Script: P

## Hamiltonian & conventions

$$ H = -\sum_v A_v \;-\; \sum_p B_p, \qquad A_v = \frac{1}{|G|}\sum_{g\in G} A_v^g,\quad B_p = B_p^{e} $$

**Kitaev's quantum double** `D(G)` for a finite group `G`, on an oriented square-lattice **torus** (PBC×PBC). Each **edge** carries a `|G|`-dimensional dof `\{|g\rangle : g\in G\}` (for `G = Z2` this is a qubit). The vertex operator `A_v` is the gauge-averaged local `G`-action at `v` (a projector, `A_v = \frac1{|G|}\sum_g A_v^g`), and the plaquette operator `B_p = B_p^e` projects onto trivial oriented flux around `p`. All `A_v`, `B_p` mutually commute — a **commuting-projector** (quantum-double stabilizer) Hamiltonian, coupling set to the energy unit. For `G = Z2` the dof are qubits, `A_v = \prod_{i\in v}\sigma^x_i`, `B_p = \prod_{i\in p}\sigma^z_i`, and this **is exactly the toric code**. See `.knowledge/conventions.md`.

The **model-zoo sibling** is `models/toric-code` (the `G = Z2` special case); there is no general non-abelian quantum-double model card. This oracle card computes the anyon census and torus GSD for `G ∈ {Z2, Z3, Z4, S3}` from group data, and cross-checks the `Z2` count against `toric-code/oracle.py`.

## Solvability statement

T4: `D(G)` is a **commuting-projector stabilizer(-like) lattice gauge theory**, exactly solvable in its entirety. Its anyons are the irreducible representations of the Drinfeld double, labelled by pairs `([c], \pi)` with `[c]` a conjugacy class of `G` and `\pi` an irrep of the centralizer `Z(c)` of a representative; hence the anyon count and the torus ground-state degeneracy are **exact**:

$$ \#\text{anyons} \;=\; \sum_{[c]} \#\mathrm{Irr}\big(Z(c)\big) \;=\; \sum_{[c]} \#\text{conj-classes}\big(Z(c)\big), \qquad \text{GSD}_{T^2} = \#\text{anyons}, $$

using `#Irr(H) = #conj-classes(H)`. The script evaluates this census **algebraically** from a group multiplication table (conjugacy classes, centralizers, and each centralizer's class-number) — exact integers, no eigensolver, no approximation.

**Not exact:** nothing about `D(G)` is approximate. **Script scope — this is a P (partial) card.** What the script *does*: the anyon count `n_anyons`, the torus GSD, and the abelian/non-abelian flag, for `G ∈ {Z2, Z3, Z4, S3}`. What it deliberately does **not** build (all still exact from the same structure, just not implemented): the explicit commuting-projector **lattice Hamiltonian** `H = -\sum_v A_v - \sum_p B_p` with `G`-valued edges; the **ribbon operators** that create/transport the dyonic charge-flux excitations; the **non-abelian fusion and braiding** (`S`/`T` modular data) of `D(S3)`; and higher-genus counts `\text{GSD}_g` (only the torus `g=1` count is claimed here).

## Exact results

- **Anyon labels**: `([c], \pi)`, `[c]` a conjugacy class of `G`, `\pi ∈ Irr(Z(c))` — the "charge–flux dyons" of the discrete gauge theory [@Kitaev2003]
- **Anyon count / torus GSD**: `\#\text{anyons} = \sum_{[c]} \#\mathrm{Irr}(Z(c))`, and `\text{GSD}_{T^2} = \#\text{anyons}` [@Kitaev2003]
- **Abelian `D(Z_n)`**: `G` abelian ⇒ every centralizer is all of `G`, every class is a singleton, so `\#\text{anyons} = n\cdot n = n^2`, all abelian. `D(Z2) → 4` (**the toric code**, anyons `1,e,m,\varepsilon`), `D(Z3) → 9`, `D(Z4) → 16`
- **Non-abelian `D(S3)`**: classes `\{e\}`, the 3 transpositions, the 2 three-cycles, with centralizers `S3` (3 irreps), `Z2` (2 irreps), `Z3` (3 irreps) → `3 + 2 + 3 = 8` anyons — the smallest non-abelian quantum double [@Kitaev2003]
- **`D(Z2) ≡ toric code`**: the `G = Z2` quantum double is *identical* to Kitaev's toric code; its GSD `= 4` matches `toric-code/oracle.py` (asserted in `self_test`)

## Oracle script

`python oracle.py --G S3` → prints `n_anyons`, `gsd_torus`, `abelian`, `n_group`. Importable: `compute(G="S3")` for `G ∈ {Z2, Z3, Z4, S3}`; helpers `_cyclic(n)`, `_symmetric3()` (group tables), `_conjugacy_classes(elems, mul)`, `_centralizer(g, elems, mul)`, `_n_irreps(subgroup, mul)` (`= #conj-classes`).
Self-test anchors: (1) `D(Z2) → 4`, `D(Z3) → 9`, `D(Z4) → 16` (abelian `n^2` census); (2) `D(S3) → 8` non-abelian, `n_group = 6`, with the `3+2+3` centralizer breakdown; (3) `n_anyons == gsd_torus` for every group; (4) **cross-card anchor** — `D(Z2)` GSD equals `toric-code/oracle.py`'s `compute(L=3)["gsd"]` (imported by path, not duplicated), pinning the `Z2` double to the toric code.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `gsd_torus` | `G = Z2` | `4` (= toric code) | [@Kitaev2003] |
| `gsd_torus` | `G = Z3` | `9` (`= 3²`) | [@Kitaev2003] |
| `gsd_torus` | `G = Z4` | `16` (`= 4²`) | [@Kitaev2003] |
| `gsd_torus` | `G = S3` | `8` (`= 3+2+3`, non-abelian) | [@Kitaev2003] |
| `n_anyons` | any listed `G` | `= gsd_torus` | [@Kitaev2003] |

The anyon counts are **computed by this script** from group data (conjugacy classes and centralizer class-numbers), not read from a table; `D(Z2) = 4` is additionally cross-checked against the toric-code oracle.

## Verification recipes

- To check a non-abelian anyon-model / MTC toolkit on `D(S3)`: require `#anyons = 8` with the `3 + 2 + 3` split over the classes `\{e\}`, transpositions, three-cycles — a different total signals a wrong centralizer or class computation.
- To validate a discrete-gauge-theory / quantum-double simulator: use `\text{GSD}_{T^2} = n^2` for `D(Z_n)` and the `Z2 ≡` toric-code anchor (`GSD = 4`) as canonical checks.

## Key reference

[@Kitaev2003] — Kitaev, "Fault-tolerant quantum computation by anyons", Ann. Phys. **303**, 2 (2003): introduces the quantum-double models `D(G)` (the toric code is `G = Z2`), the commuting-projector vertex/plaquette construction, the dyonic `([c], \pi)` anyons with their ribbon operators and fusion/braiding, and topological degeneracy on surfaces — the exact structure whose anyon census and torus GSD this card computes. Rendered: _(Wave 3)_.
