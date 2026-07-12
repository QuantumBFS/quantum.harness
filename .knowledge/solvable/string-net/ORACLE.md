# Levin–Wen string-net — exact-solution oracle

Technique: T4 (commuting-projector / Levin–Wen) · Tier: A (exact, algebraic) · Script: P

## Hamiltonian & conventions

$$ H = -\sum_v Q_v \;-\; \sum_p B_p, \qquad B_p = \sum_{s} a_s\, B_p^{s} $$

**Levin–Wen string-net model** on a trivalent (honeycomb) lattice **torus**, built from an input unitary fusion category: **simple objects** (string types) `i` with fusion rules `i × j = \sum_k N^k_{ij}\, k`, quantum dimensions `d_i`, and `F`-symbols. The **degrees of freedom** live on edges, labelled by string types. The vertex projector `Q_v` enforces the branching (fusion) rules at each trivalent vertex; the plaquette operator `B_p` (a weighted sum `\sum_s a_s B_p^s` with `a_s = d_s/\sum_t d_t^2`) fluctuates the string-net. All `Q_v`, `B_p` mutually commute — a **commuting-projector** Hamiltonian whose ground state is a **weighted loop/string-net gas** and which realizes the **doubled (Drinfeld-center) topological phase** of the input category. See `.knowledge/conventions.md`.

The `Z2` gauge theory / toric code is the string-net of the group category `Z2`; the doubled Fibonacci and doubled Ising phases here have **no** free-fermion or stabilizer sibling model card. There is no model-zoo sibling for these categorical inputs (`models/toric-code` is the closest relative, via the `Z2` string-net).

## Solvability statement

T4: the Levin–Wen model is a **commuting-projector Hamiltonian**, exactly solvable in its entirety. From the fusion tensor `N^k_{ij}` alone, the quantum dimensions, total quantum dimension, doubled anyon count, and torus GSD are **exact**:

- quantum dimension `d_i` = the **Perron–Frobenius (largest) eigenvalue** of the fusion matrix `(N_i)_{jk} = N^k_{ij}`;
- total quantum dimension squared `D^2 = \sum_i d_i^2`;
- **doubled anyon count** `= (\#\text{simple objects})^2`, and **torus** `\text{GSD}_{T^2} = \#\text{anyons}`.

**Caveat on the `(\#\text{objects})^2` count**: this is the anyon count of the **Drinfeld center** `Z(\mathcal C)` for a **modular / multiplicity-free** input fusion category `\mathcal C`. It is asserted here only for the two shipped inputs (`fibonacci`, `ising`), where it is verified; the **safe exact claim is the `g=1` (torus)** count `\text{GSD}_{T^2} = \#\text{anyons}`. The general genus-`g` statement `\text{GSD}_g = (\#\text{anyons})^g` is *not* claimed by this card beyond `g=1`.

**Not exact:** nothing about the model is approximate. **Script scope — this is a P (partial) card.** What the script *does*: quantum dimensions (Perron root of the fusion matrix), `D^2`, the doubled anyon count and torus GSD, for `category ∈ {fibonacci, ising}`. What it deliberately does **not** build (all still exact from the same data, just not implemented): the **`F`-symbols** and the full Levin–Wen plaquette Hamiltonian `-\sum_v Q_v - \sum_p B_p`; the explicit **string-net ground-state wavefunction** (the weighted loop gas); the modular `S`/`T` data and braiding of the doubled anyons; and higher-genus GSD.

## Exact results

- **Quantum dimension** `d_i = \lambda_{\max}(N_i)`, `(N_i)_{jk} = N^k_{ij}` (Perron–Frobenius root of the nonnegative fusion matrix) [@LevinWen2005]
- **Fibonacci**: simple objects `\{1, \tau\}`, fusion `\tau\times\tau = 1 + \tau`; `d_\tau = \varphi = (1+\sqrt5)/2` (Perron root of `N_\tau = \begin{smallmatrix}0&1\\1&1\end{smallmatrix}`); `D^2 = 1 + \varphi^2`. The doubled theory is **doubled Fibonacci (DFib)**: `2^2 = 4` anyons, `\text{GSD}_{T^2} = 4` [@LevinWen2005]
- **Ising**: simple objects `\{1, \sigma, \psi\}`, fusion `\sigma\times\sigma = 1+\psi`, `\sigma\times\psi = \sigma`, `\psi\times\psi = 1`; `d_\sigma = \sqrt2`, `d_\psi = 1`; `D^2 = 1 + 2 + 1 = 4`. The doubled theory has `3^2 = 9` anyons, `\text{GSD}_{T^2} = 9` [@LevinWen2005]
- **Ground state** = weighted string-net (loop-gas) condensate; total quantum dimension `D` sets the topological entanglement entropy `\gamma = \ln D` (exact, from the category data; not scripted here) [@LevinWen2005]

## Oracle script

`python oracle.py --category fibonacci` → prints `n_simple`, `d_max`, `total_quantum_dim_sq`, `n_anyons_doubled`, `gsd_torus`. Importable: `compute(category="fibonacci")` for `category ∈ {fibonacci, ising}`; helpers `_fibonacci()`, `_ising()` (label list + fusion tensor `N^k_{ij}`), `quantum_dimensions(N)` (Perron eigenvalue per object).
Self-test anchors: (1) Fibonacci `|d_\tau - \varphi| < 10^{-12}`, `\text{GSD} = 4`, `D^2 = 1+\varphi^2` (to `10^{-12}`); (2) Ising `d_\sigma = \sqrt2` and `d_\psi = 1` (to `10^{-12}`), `\text{GSD} = 9`, `D^2 = 4`; (3) `gsd_torus == n_anyons_doubled == n_simple^2` for both inputs.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `d_max` (`= d_\tau`) | `fibonacci` | `\varphi = (1+\sqrt5)/2 ≈ 1.61803` | [@LevinWen2005] |
| `total_quantum_dim_sq` | `fibonacci` | `1 + \varphi^2 ≈ 3.61803` | [@LevinWen2005] |
| `gsd_torus` | `fibonacci` | `4` (doubled Fibonacci) | [@LevinWen2005] |
| `d_max` (`= d_\sigma`) | `ising` | `\sqrt2 ≈ 1.41421` | [@LevinWen2005] |
| `total_quantum_dim_sq` | `ising` | `4` (`= 1+2+1`) | [@LevinWen2005] |
| `gsd_torus` | `ising` | `9` (doubled Ising) | [@LevinWen2005] |

Quantum dimensions are **computed by this script** as Perron eigenvalues of the fusion matrices; the doubled counts follow from `(\#\text{objects})^2` for these multiplicity-free inputs.

## Verification recipes

- To check a string-net / anyon-model implementation of doubled Fibonacci: require `d_\tau = \varphi` to machine precision and `\text{GSD}_{T^2} = 4`; for doubled Ising require `d_\sigma = \sqrt2`, `\text{GSD}_{T^2} = 9`. A wrong quantum dimension signals a transcription error in the fusion rules.
- To validate a topological-entropy toolkit: use `D^2 = 1 + \varphi^2` (Fibonacci) or `D^2 = 4` (Ising) as the exact total-quantum-dimension anchors (`\gamma = \ln D`).

## Key reference

[@LevinWen2005] — Levin & Wen, "String-net condensation: A physical mechanism for topological phases", Phys. Rev. B **71**, 045110 (2005): constructs the exactly soluble commuting-projector string-net Hamiltonians from an input fusion category, identifies tensor-category data (`N^k_{ij}`, `d_i`, `F`-symbols) as the underlying structure, and gives the doubled (Drinfeld-center) topological phases — including doubled Fibonacci and doubled Ising, whose quantum dimensions and torus GSD this card computes. Rendered: _(Wave 3)_.
