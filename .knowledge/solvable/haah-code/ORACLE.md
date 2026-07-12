# Haah cubic code (fracton) — exact-solution oracle

Technique: T4 (commuting-projector / stabilizer) · Tier: A (exact via GF(2)) · Script: P

## Hamiltonian & conventions

$$ H = -\sum_{s} A_s \;-\; \sum_{s} B_s, \qquad A_s = \text{(X-type cube operator)},\quad B_s = \text{(Z-type cube operator)} $$

**Haah's cubic code** ("code 1") on an `L×L×L` cubic **torus** (PBC³). **Two** spin-1/2 qubits sit on **each site** (`n = 2L³` qubits). Every site `s` carries one X-type generator `A_s` and one Z-type generator `B_s`, each supported on the eight corners of a unit cube; the two types are related by **spatial inversion + qubit swap**. In polynomial notation over `F₂[x,y,z]/(x^L-1, y^L-1, z^L-1)`, with

$$ f = 1 + x + y + z, \qquad g = 1 + xy + yz + zx, $$

the generators at site `s` are (qubit 0 / qubit 1 columns):

- **X-type** `A_s`: `σ^x` support `f` on qubit 0, `g` on qubit 1;
- **Z-type** `B_s`: `σ^z` support `\bar g` on qubit 0, `\bar f` on qubit 1 (bar = `x → x^{-1}`, spatial inversion).

Commutation is automatic: the CSS symplectic overlap is `f·g + g·f = 0` over `F₂`, so every X/Z translate pair commutes — the swapped-inverse arrangement is precisely what makes the code well defined. Sites are indexed `qubit_index(x,y,z,q) = 2((zL+y)L+x)+q`. See `.knowledge/conventions.md`. No model-zoo sibling card exists for the Haah code (the `models/toric-code` card is the closest relative).

Rows are built by **XOR-toggling** bit positions so a Pauli landing twice on a qubit at a periodic wrap cancels rather than double-counting.

## Solvability statement

T4: the Haah code is a **commuting-projector stabilizer Hamiltonian**. The ground space is the simultaneous `+1` eigenspace of every `A_s`, `B_s`, and the full spectrum is `E = -N_s + 2\,(\#\text{violated})` with `N_s = 2L³`. The reported degeneracy `gsd_log2 = k = \log_2 GSD` is an **exact integer** for every `L`, obtained from an exact GF(2) rank (`_lib.gf2.stabilizer_gsd_log2`, which also asserts pairwise commutation — reaching a value at all certifies the transcription commutes). **Not exact:** nothing is approximated — `k(L)` is computed exactly by integer GF(2) elimination. What is *absent* is a **closed form**: `k(L)` has a subextensive, number-theoretic dependence on `L` with no simple formula (only the bound `2 ≤ k ≤ 4L - 2` and the polynomial-algebra origin below are stated in closed form) [@Haah2011]. Exact content deliberately **out of this card's scope** (still exact from the same stabilizer structure, just not implemented): the fractal logical-operator supports, the code distance `d ~ 2^{...}` growth, the immobile-fracton excitation structure, and the polynomial/homological classification of `k(L)`.

## Exact results

- **No string logical operators**: the Haah code is a **Type-II fracton** phase — there are **no string-like logical operators whatsoever**; all point excitations (fractons) are strictly **immobile**, unable to be transported by any finite operator [@Haah2011]. This is the defining property that distinguishes it from both conventional topological codes and Type-I fractons (e.g. X-cube, which has mobile lineons).
- **Subextensive, number-theoretic GSD**: `k(L) = \log_2 GSD` fluctuates strongly with `L`, bounded by `2 ≤ k ≤ 4L - 2` [@Haah2011]. Its origin is algebraic: `k` is fixed by the `F₂[x,y,z]/(x^L-1,y^L-1,z^L-1)`-module structure of the stabilizer map built from `f, g` — the number of encoded qubits is a property of that quotient ring, not a smooth function of `L`. For system sizes `L` free of the special factors `{2, 15, 63}` the code has the **generic** four-fold degeneracy `k = 2` (`GSD = 4`); special sizes carry more [@Haah2011].
- **Full spectrum**: `E = -N_s + 2\,(\#\text{violated stabilizers})`, `N_s = 2L³`.

## Oracle script

`python oracle.py --L 3` → prints `gsd_log2` (`= k`), `n_qubits`. Importable: `compute(L=3)`; helpers `qubit_index(x,y,z,q,L)`, `stabilizer_rows(L)` (binary symplectic `(x|z)` rows, one X- then one Z-generator per site, built by XOR-toggle from the monomial supports `F, G, FBAR, GBAR`).
Self-test anchors: (1) **commutation** — `stabilizer_gsd_log2` throws if any X/Z pair fails to commute, so a no-throw result for `L ∈ {2,3,4}` certifies the polynomial transcription; (2) `k ≥ 2` and `k ≤ 4L-2` for all tested `L` (the published bound); (3) `k(4) ≥ k(2)`; (4) **determinism** — two independent constructions agree; (5) **regression anchors** `k = {2:6, 3:2, 4:14}` with two published cross-checks: `k(3) = 2` matches the literature statement that factor-free `L` (no `2/15/63`) sit at `GSD = 4`, and `k(2) = 6 = 4·2-2`, `k(4) = 14 = 4·4-2` **saturate** the published upper bound `4L-2`.

## Benchmarks

| Quantity | Params | Value | Source |
|---|---|---|---|
| `gsd_log2` (`k`) | `L=2` torus | `6` (`= 4L-2`, saturates bound) | computed here (GF(2) rank); bound [@Haah2011] |
| `gsd_log2` (`k`) | `L=3` torus | `2` (generic; `3` factor-free) | computed here; matches generic-`k` statement [@Haah2011] |
| `gsd_log2` (`k`) | `L=4` torus | `14` (`= 4L-2`, saturates bound) | computed here (GF(2) rank); bound [@Haah2011] |
| `gsd_log2` (`k`) | general `L` | `2 ≤ k ≤ 4L-2`, no closed form | [@Haah2011] |
| `n_qubits` | `L×L×L` torus | `2L³` | — |

The `k` values at `L ∈ {2,3,4}` are **computed by this script via exact GF(2) rank** (not read from a published table). They are cross-checked against published statements [@Haah2011]: the generic four-fold degeneracy at factor-free sizes (`k(3)=k(5)=k(7)=2`, verified) and the `2 ≤ k ≤ 4L-2` bound (both `k(2)` and `k(4)` saturate it). Consistency is further underwritten by the internal commutation assertion and by determinism across repeated builds.

## Verification recipes

- To check an independent stabilizer-tableau / homological construction of the Haah code on a cubic torus: compare `gsd_log2` from `oracle.py --L <L>`. For any `L` free of the factors `{2, 15, 63}` the answer **must** be `2` (`GSD = 4`); a different value signals a transcription error in the generators.
- Sanity bracket: for every `L`, require `2 ≤ gsd_log2 ≤ 4L - 2`. A value of `0` or `1`, or anything exceeding `4L-2`, means the X/Z generators are wrong (or fail to commute — which this script would catch by assertion first).

## Key reference

[@Haah2011] — Haah, "Local stabilizer codes in three dimensions without string logical operators", Phys. Rev. A **83**, 042330 (2011): introduces the cubic codes (including "code 1" used here), proves the absence of string logical operators (the Type-II fracton hallmark), and analyzes the number of encoded qubits and its bound `2 ≤ k ≤ 4L-2` on finite periodic lattices — the exact structure whose degeneracy this card computes. Rendered: _(Wave 3)_.
