# Cluster-state SPT chain — exact-solution oracle

Technique: T4 (commuting-projector / stabilizer) · Tier: A (closed-form, exact) · Script: S

## Hamiltonian & conventions

$$ H = -\sum_i K_i, \qquad K_i = \sigma^z_{i-1}\,\sigma^x_i\,\sigma^z_{i+1} $$

a 1D spin-1/2 chain of Pauli operators (`σ^a`, coupling `= 1`). The stabilizers `K_i` all mutually commute (neighbours overlap on two sites → even → commute), so `H` is a **commuting-projector** Hamiltonian whose unique PBC ground state is the 1D **cluster state**. **PBC** (`σ_{L} ≡ σ_0`): one `K_i` per site, `i = 0..L-1`. **OBC**: only the `L-2` interior sites `i = 1..L-2` carry a stabilizer — the two boundary sites lose one each. See `.knowledge/conventions.md`. No model-zoo sibling card exists for the cluster SPT.

The cluster state is a **Z₂ × Z₂ symmetry-protected topological (SPT)** state, protected by the two sublattice spin-flip symmetries `X_{\text{even}} = \prod_{i\,\text{even}}\sigma^x_i` and `X_{\text{odd}} = \prod_{i\,\text{odd}}\sigma^x_i`, and is the canonical **measurement-based-quantum-computation (MBQC)** resource state [@RaussendorfBriegel2001].

## Solvability statement

T4: a **commuting-projector stabilizer Hamiltonian**. The ground space is the simultaneous `+1` eigenspace of every `K_i`; the full spectrum is `E = -N_s + 2\,(\#\text{violated})` with `N_s` the number of stabilizers. Everything reported — the PBC/OBC degeneracies, the gap, and the string-order parameter — is **exact** for every `L`; no approximation anywhere. **Not exact:** nothing about this model is approximate. Exact content deliberately **out of this card's scope** (all still exact, just not implemented): the explicit edge-mode logical operators of the OBC degeneracy, the full entanglement spectrum (doubly degenerate — the SPT fingerprint), and the MBQC gate-teleportation identities. `gsd_pbc`/`gsd_obc` come from an exact GF(2) rank; `string_order` is proved exactly by GF(2) stabilizer-membership and cross-checked in ED.

## Exact results

- **Full spectrum**: `E = -N_s + 2\,(\#\text{violated } K_i)`; every `K_i` can be violated independently (PBC has no product constraint on a single flip, since `\prod_i K_i = \prod_i \sigma^x_i \neq \mathbb{1}`) [@RaussendorfBriegel2001]
- **PBC degeneracy**: `gsd_pbc = 1`. The `L` stabilizers are independent (their `X`-parts are the `L` distinct single-site vectors → rank `L`), so `\log_2 GSD = L - L = 0`. Unique, bulk-trivial ground state.
- **OBC degeneracy**: `gsd_obc = 4`. Only `L-2` stabilizers survive (rank `L-2`), so `\log_2 GSD = L - (L-2) = 2` → `GSD = 4`: **two protected boundary modes** (`2^2`), the hallmark of the nontrivial SPT.
- **Gap** (PBC, coupling `1`): flipping one stabilizer costs `ΔE = 2`, so `gap = 2` [@RaussendorfBriegel2001]
- **String order** `= 1` (exact). The SPT string operator on endpoints `a<b`,
  $$ O(a,b) = \prod_{i=a+1}^{b-1} K_i = \sigma^z_a\,\sigma^y_{a+1}\,\sigma^x_{a+2}\cdots\sigma^x_{b-2}\,\sigma^y_{b-1}\,\sigma^z_b, $$
  is **literally a product of stabilizers** (the enclosed `K_{a+1}\cdots K_{b-1}`), so `\langle O\rangle = +1` in every ground state. Note the `σ^y` "decoration" one site inside each `σ^z` endpoint: the naive undecorated string `\sigma^z_a\,\sigma^x_{a+1}\cdots\sigma^x_{b-1}\,\sigma^z_b` is **not** a stabilizer and has expectation `0` — the decorated form above is the genuine cluster-SPT order parameter [@RaussendorfBriegel2001].

## Oracle script

`python oracle.py --L 8` → prints `gsd_pbc`, `gsd_obc`, `gap`, `string_order`. Importable: `compute(L=8)`; helpers `stabilizer_rows(L, pbc)` (binary symplectic `(x|z)` rows), `string_order_value(L,a,b)` (exact `⟨O⟩` via GF(2) stabilizer-membership — the symplectic vector of `O` is built independently from its Pauli content, then checked to lie in the stabilizer row span, with the naive undecorated `ZX…XZ` string verified to lie **outside** it as a negative control), `_ed_hamiltonian(L, pbc)` (sparse `-ΣK_i`).
Self-test anchors: (1) `gsd_pbc(8) == 1`, `gsd_obc(8) == 4`, `string_order == 1.0` (GF(2) membership, with the undecorated-string negative control); (2) ED cross-check `L = 8` PBC (dim 256) — `ed.ground_states == 1`, `ed.gap == 2.0` to `1e-10`; (3) ED OBC — `ed.ground_states == 4`; (4) ED expectation of the decorated string operator `Z_1 Y_2 X_3 X_4 Y_5 Z_6` in the unique PBC ground state equals `1` to `1e-10`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `gsd_pbc` | `L`-site ring | `1` (unique, bulk-trivial) | [@RaussendorfBriegel2001] |
| `gsd_obc` | open chain | `4` (`= 2²`, two edge modes) | [@RaussendorfBriegel2001] |
| `gap` | PBC, coupling `1` | `2` (one flipped `K_i`) | [@RaussendorfBriegel2001] |
| `string_order` | `⟨\prod K_i⟩` | `1` (product of stabilizers) | derived above |

## Verification recipes

- To check an ED / DMRG run of the cluster chain: compare `gsd_pbc` (unique) vs `gsd_obc` (`4`) from `oracle.py --L <L>`, the gap (`2` at coupling `1`), and the decorated string order (`1`). The PBC/OBC degeneracy contrast — `1` in the bulk, `4` with boundaries — is the operational SPT signature.
- To probe symmetry protection: breaking either `X_{\text{even}}` or `X_{\text{odd}}` (adding a field on one sublattice) lifts the OBC edge degeneracy; the string order then decays, distinguishing the SPT from a trivial paramagnet.

## Key reference

[@RaussendorfBriegel2001] — Raussendorf & Briegel, "A one-way quantum computer", Phys. Rev. Lett. **86**, 5188 (2001): introduces the cluster state and its stabilizer generators `K_i = \sigma^z_{i-1}\sigma^x_i\sigma^z_{i+1}`, and its role as the universal resource for measurement-based quantum computation — the state whose exact degeneracy, gap, and string order this card reproduces, later recognized as the archetypal 1D Z₂×Z₂ SPT. Rendered: _(Wave 3)_.
