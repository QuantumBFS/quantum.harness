# SSH (Su–Schrieffer–Heeger) chain — exact-solution oracle

Technique: T1 (free-fermion / single-particle diagonalization) · Tier: A (closed-form, exact) · Script: S

## Hamiltonian & conventions

$$ H = \sum_{i=1}^{L} \left[ v\, a^\dagger_i b_i + w\, b^\dagger_i a_{i+1} + \text{h.c.} \right], \qquad \text{OBC (edge modes) or PBC (bulk invariant)} $$

Conventions: spinless fermions, two-site (A, B) unit cell, `L` = number of unit cells; `v` the **intracell** hopping (A↔B, same cell `i`), `w` the **intercell** hopping (B of cell `i` ↔ A of cell `i+1`). Native number-conserving fermion hopping model — no pairing, no Jordan–Wigner string; the many-body ground state at half filling is exactly the Slater determinant filling every negative-energy single-particle eigenstate. Bloch off-diagonal `g(k) = v + w e^{ik}`, bands `ε(k) = ±|g(k)|`. Topological (`ν=1`) for `|w| > |v|`; trivial (`ν=0`) for `|v| > |w|`; gap closes at `|v| = |w|`. See `.knowledge/conventions.md`.

Physics card: `.knowledge/models/ssh/MODEL.md`. That card writes the identical Hamiltonian with `t_1` (intracell) and `t_2` (intercell) in place of this card's `v` and `w` — same roles, same topological criterion (`t_2 > t_1` ⇔ `|w| > |v|`; that card takes both hoppings positive, this card's criterion is the signed-hopping generalization), same gap `2|t_1-t_2| = 2||v|-|w||`, same edge-mode decay length. **Conventions match exactly** (pure renaming `t_1→v, t_2→w`); no translation needed.

## Solvability statement

T1: the Hamiltonian is quadratic (bilinear, number-conserving) in the fermions, diagonalized exactly by Fourier transform (PBC, bulk bands + winding number) or by direct real-space diagonalization of the `2L×2L` OBC hopping matrix (edge modes). Everything reported here — the bulk dispersion, the winding invariant, the bulk gap, the OBC edge-mode count, the edge-mode decay length, and the filled-band (half-filling) ground-state energy — is exact for any `L, v, w`. The model is exactly solvable in its entirety; there is no approximation anywhere. **Not exact:** nothing about this model is approximate. Some exact quantities are simply out of this card's scope (ground-state statics only): the exponentially small even/odd finite-size splitting of the two near-zero OBC edge modes, the Zak/Berry phase as a continuous quantity (only the quantized winding number is reported), single-particle correlation functions, and quench/dynamics (all exactly tractable because the model stays quadratic).

## Exact results

- Bulk single-particle dispersion (PBC): $\varepsilon(k) = \pm|g(k)|$, $g(k) = v + w e^{ik}$
- Winding number (chiral/sublattice invariant): $\nu = \dfrac{1}{2\pi i}\oint \dfrac{g'(k)}{g(k)}\,dk \in \{0,1\}$ — computed here via `topology.winding(g, nk)` (phase-unwrapping of `g(k)` around the origin); $\nu=1$ (topological) for $|w|>|v|$, $\nu=0$ (trivial) for $|v|>|w|$ [@SSH1979]
- Bulk gap: $\Delta = 2\big|\,|v|-|w|\,\big|$, vanishing at the critical point $|v| = |w|$
- OBC edge modes: exactly two near-zero-energy states (one per end) in the topological phase ($|w|>|v|$), none in the trivial phase; detected here as OBC single-particle eigenvalues with $|\varepsilon| < \Delta/4$
- Edge-mode decay length (topological phase, $|w|>|v|$): $\xi = 1/\ln(|w|/|v|)$ [@SSH1979]
- Ground-state energy per unit cell (filled lower band, half filling — exactly one fermion per unit cell): $e_0 = -\dfrac{1}{2\pi}\displaystyle\int_0^{2\pi} |v+we^{ik}|\,dk$. **Density convention:** here "per site" means per unit cell (`L` counts unit cells, matching the OBC matrix size `2L` and `models/ssh/MODEL.md`'s "`N` cells" convention) — equivalently the energy per particle, since half filling puts exactly one occupied fermion per unit cell. This is `E_total / L`, *not* `E_total / (2L)`. (The ED cross-check itself sidesteps normalization entirely: it compares **total** energies — the sum of negative OBC single-particle eigenvalues against `ed.ground_energy` of the many-body Hamiltonian at `L = 4` unit cells — with no division by any length, so it is valid under either density convention)

## Oracle script

`python oracle.py --L 100 --v 0.5 --w 1.0` → prints `winding`, `gap`, `n_edge_modes_obc`, `e0_per_site`, `edge_decay_length`. Importable: `compute(L=100, v=0.5, w=1.0, nk=2001)`; `matrices(L, v, w)` returns the OBC `2L×2L` hopping matrix.
Self-test anchors: (1) `winding(v=0.5,w=1.0) == 1` (topological), `winding(v=1.0,w=0.5) == 0` (trivial); (2) `n_edge_modes_obc(v=0.5,w=1.0) == 2`; (3) `gap(v=0.5,w=1.0) == 1.0` exactly; (4) ED cross-check — at `L=4` unit cells (8 sites), the sum of negative OBC single-particle eigenvalues equals the brute-force JW many-body ground energy (`ed.fermion_ops`, `ed.ground_energy`), tolerance `1e-10`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `winding` | `v=0.5, w=1.0` | `1` (topological) | [@SSH1979] |
| `winding` | `v=1.0, w=0.5` | `0` (trivial) | [@SSH1979] |
| `gap` | `v=0.5, w=1.0` | `1` (`= 2\|v-w\|`) | [@SSH1979] |
| `n_edge_modes_obc` | `v=0.5, w=1.0`, OBC | `2` | [@SSH1979] |
| `n_edge_modes_obc` | `v=1.0, w=0.5`, OBC | `0` | [@SSH1979] |
| `edge_decay_length` | `v=0.5, w=1.0` | `1/\ln 2 \approx 1.4427` | [@SSH1979] |

## Verification recipes

- To check a DMRG/ED run at unit-cell count `L`, OBC: compare `n_edge_modes_obc` (should be `2` in the topological phase, `0` in the trivial phase) and `gap` via `oracle.py --L <L> --v <v> --w <w>`, tolerance `1e-8` (exact).
- Bulk–boundary correspondence self-check: `winding` (PBC invariant) must equal `n_edge_modes_obc / 2` (OBC count) at every `(v,w)`.
- Fully dimerized limits: `v→0` (topological) gives perfectly localized zero-energy modes on the two terminal `B`/`A` sites (`ξ→0`); `w→0` (trivial) gives no edge modes.

## Key reference

[@SSH1979] — Su, Schrieffer & Heeger, "Solitons in Polyacetylene": the original paper introducing the dimerized hopping chain, its two-fold degenerate dimerization pattern, and the domain-wall/soliton (edge-mode) physics that the modern winding-number formulation of this card makes precise. Rendered: _(Wave 3)_.
