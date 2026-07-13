# Supersymmetric t-J chain (J = 2t) — exact-solution oracle

Technique: T3 (Bethe ansatz / Yang–Baxter) · Tier: B (integrable) · Script: P

## Hamiltonian & conventions

$$ H = -t \sum_{\langle ij\rangle,\sigma} P\!\left( c^\dagger_{i\sigma} c_{j\sigma} + \text{h.c.} \right)\!P + J \sum_{\langle ij\rangle}\left( \mathbf{S}_i\cdot\mathbf{S}_j - \tfrac{1}{4} n_i n_j \right), \qquad J = 2t $$

Conventions: `t = 1` (energy unit), spin-½ `S`-operators (`S^a = σ^a/2`), `P` projects out double occupancy so the local space is `{∅, ↑, ↓}` (`d = 3`); nearest-neighbour bonds counted once. The `-¼ n_i n_j` density term is the canonical (Hubbard-derived) form and is kept. The **supersymmetric point is `J = 2t`**. See `.knowledge/conventions.md`.

Physics card: `.knowledge/models/t-j/MODEL.md`. That card uses the **same** projected `H = -t P(c†c+h.c.)P + J Σ(S·S - ¼ nn)` form and names the same integrable point (`J = 2t`, Sutherland/Schlottmann) and the same `su(2|1)` superalgebra. No convention translation is needed. The large-`U` Hubbard origin (`J = 4t²/U`, so `J = 2t ↔ U = 2t`) links to `hubbard-1d-lieb-wu` / `models/hubbard`.

## Solvability statement

T3 (Bethe ansatz): at `J = 2t` the t-J chain is Bethe-ansatz integrable and carries a graded `su(2|1)` supersymmetry — the three local states `{∅, ↑, ↓}` (one boson, two fermions) form a fundamental of the superalgebra, and the Hamiltonian is (up to a constant and chemical potential) the sum of nearest-neighbour **graded permutation** operators. Sutherland's multicomponent Bethe ansatz [@Sutherland1975] and Schlottmann's narrow-band solution [@Schlottmann1987] give the exact spectrum and thermodynamics via nested Bethe / thermodynamic-Bethe-ansatz equations. **Not exact in closed form (Tier B):** the ground-state energy at generic filling, the full spectrum, and finite-`T` thermodynamics require solving the (nested) Bethe equations state-by-state — integrable but not single closed forms.

## Script scope (P — read this)

This card ships a **partial** oracle. What is scriptable is **exact diagonalisation in the projected occupation basis** `{∅,↑,↓}^L` (dim `3^L`; `L=6 → 729`, `L=8 → 6561`), building the hopping (with explicit fermion signs), the spin-exchange, and the `-¼ n_i n_j` term directly — no double-occupancy states are ever created. **OBC** is used so nearest-neighbour hops carry a trivial `+1` sign; the sign structure is validated against hand-computable 2- and 3-site spectra (self-test anchors 1–3).

From this ED the script extracts the **supersymmetry signature** exactly (anchor 4): at `J = 2t` the half-filled (`N = L`) and one-hole (`N = L-1`) sectors share **many exact common eigenvalues** — supermultiplets paired by the odd supercharge that removes an electron — and every one of them **lifts** at `J = 1.9t`. This is a sharp, `1e-8`-level fingerprint of the SUSY point that needs no Bethe-ansatz machinery.

What is **tabulated, not coded**: the thermodynamic ground-state energy at generic filling (Sutherland/Schlottmann TBA). Only the half-filling value is exact and reported, because there the kinetic term is fully projected away and the model **reduces to the Heisenberg chain** (`J = 2t`) plus the `-¼ n_i n_j` density term.

## The supersymmetry story

Write the local basis as `|∅⟩` (grading `+`, bosonic) and `|↑⟩, |↓⟩` (grading `-`, fermionic). The graded permutation `Π_{ij}` swaps the states of sites `i, j` with a `-1` whenever both are fermionic; at `J = 2t` one has `H = Σ_{⟨ij⟩}(Π_{ij} - 1)` up to a constant. `Π` is invariant under the global `su(2|1)` generators — the even part is `U(1)_{\text{charge}} × SU(2)_{\text{spin}}`, and the **odd** generators are supercharges `Q_σ` that convert a hole into a `σ`-electron (and back), changing the particle number by one. Because `[Q_σ, H] = 0` at the SUSY point, any eigenstate not annihilated by `Q_σ` has a **degenerate partner in the adjacent particle-number sector** — a supermultiplet. Numerically this is why the `N=L` and `N=L-1` spectra overlap so heavily at `J = 2t`. Detuning to `J = 1.9t` breaks the superalgebra: the multiplets split and the sector spectra no longer share a single eigenvalue (to `1e-8`). At half filling the hole content is zero, hopping is fully projected, and `H` collapses to the antiferromagnetic Heisenberg chain (with the constant `-¼` per bond), so the `n = 1` ground state is the Heisenberg singlet.

## Exact results

- Supersymmetric point: `J = 2t` — graded `su(2|1)` symmetry, Bethe-ansatz integrable [@Sutherland1975; @Schlottmann1987]
- **Supermultiplet degeneracy (pinned):** on the `L = 6` OBC chain the `N=6` and `N=5` sectors share exactly 21 common eigenvalues at `J = 2t` (to `1e-8`), the lowest being `E = -(2+\sqrt 3) ≈ -3.7320508`; at `J = 1.9t` they share **none** (to `1e-8`). (`L = 8` reproduces the structure: 43 shared, lowest `≈ -3.8477591`.)
- Half-filling thermodynamic ground energy per site (`n = 1`, exact via Heisenberg reduction): `e_0 = J(\tfrac14 - \ln 2) - J/4 = -J\ln 2 = -2\ln 2 ≈ -1.3862944` (`J = 2`), matching the Hubbard strong-coupling `-4\ln2/U` at `U = 4t²/J = 2` [@Sutherland1975]
- Generic filling `0 < n < 1`: exact ground energy from the Sutherland/Schlottmann TBA — **tabulated, not coded here**

## Oracle script

`python oracle.py --L 6` → prints `susy_point_J_over_t` (`2.0`), `e0_halffilling_per_site` (ED `N=L` sector energy per site), `e0_halffilling_thermo` (`-2 ln2`, exact), `n_susy_supermultiplets` (count of `N=L`↔`N=L-1` shared eigenvalues at `J=2t`), `lowest_supermultiplet_energy` (`-(2+√3)` at `L=6`). Importable: `compute(L=6)`; `tj_hamiltonian(L, t, J, pbc)`, `sector_spectrum(L, N, J)`, `n_shared_eigenvalues(a, b, tol)`.

Self-test anchors: (1) **hand-computed 2-site spectrum** at `J=2` is exactly `{-2,-1,-1,0,0,0,0,1,1}` (`N=0`: `{0}`; `N=1` bonding/antibonding `{-1,-1,1,1}`; `N=2` triplet `{0,0,0}` + singlet `{-J}`); (2) fermion-sign check — the `N=2` singlet energy is exactly `-J` for `J ∈ {1,1.9,2}`; (3) the `N=1` (single-electron, `J`-free) 3-site hopping triplet `{-√2, 0, √2}` appears, verifying the many-body hopping signs; (4) **the SUSY anchor** — `L=6` `N=6`↔`N=5` share `≥ 20` eigenvalues at `J=2t` with lowest `-(2+√3)` (to `1e-8`), and share `0` at `J=1.9t`; (5) the half-filled `L=6` per-site energy lies above the thermodynamic `-2\ln2` (open ends) but within `0.2`.

## The fermionic sign structure (validated, not assumed)

Signs are the classic failure point of a projected t-J ED, so they are pinned rather than trusted. Each Fock state is `|s⟩ = ∏_{k:\,s_k≠∅}^{\text{ascending }k} c^\dagger_{k,\sigma_k}|0⟩`; a hop annihilates at `frm` (sign `(-1)^{\#\text{occupied}<frm}`) then creates at `to` (sign `(-1)^{\#\text{occupied}<to}` in the updated string). For OBC nearest neighbours with no site between them this is `+1`, but the code computes it generally. The spin-exchange `½(S^+_iS^-_j + S^-_iS^+_j)` moves two fermions and is sign-free. Anchors 1–3 confirm the whole construction against numbers computable by hand: the two-site singlet at `-J`, and the single-electron `-√2` hopping level.

## Benchmarks

`t = 1`, `J = 2t` (SUSY point), OBC ED; energies exact to machine precision.

| Quantity | Params | Value | Source |
|---|---|---|---|
| `lowest_supermultiplet_energy` | `L=6`, `N=6↔5`, `J=2t` | `-(2+√3) ≈ -3.7320508` (0 shared at `J=1.9t`) | this card; [@Sutherland1975] |
| `n_susy_supermultiplets` | `L=6`, `N=6↔5`, `J=2t` | `21` shared eigenvalues (`1e-8`) | this card |
| `e0_halffilling_thermo` | `n=1`, `N→∞` | `-2 ln2 ≈ -1.3862944` (Heisenberg limit) | [@Sutherland1975] |
| `e0_halffilling_per_site` | `n=1`, `L=6` OBC | `-1.2478590` (finite `L`; `→ -2 ln2`) | this card |
| generic-filling `e_0` | `0<n<1` | Sutherland/Schlottmann TBA (**not coded**) | [@Sutherland1975; @Schlottmann1987] |

The generic-filling row is the **tabulated** exact statement (nested Bethe ansatz / TBA); the ED rows are exact finite-`L` values from the projected diagonalisation. The half-filling thermodynamic value is exact via the Heisenberg reduction.

## Verification recipes

- To confirm a t-J code sits at the SUSY point: build the `N=L` and `N=L-1` OBC spectra at `J=2t` and check they share eigenvalues (supermultiplets) that vanish under a small detuning `J = 1.9t` — `oracle.py` reports the count and the pinned `-(2+√3)` level.
- To check a projected-ED / DMRG ground state at half filling: compare against the Heisenberg reduction `e_0 → -2\ln2` (thermodynamic) or the finite-`L` OBC value from `sector_spectrum(L, L)`; the kinetic term must be fully projected (`n=1`, no holes).
- Cheap sanity checks on any projected t-J code: no doubly-occupied state in the basis; the 2-site singlet energy is `-J`; a single electron on an open chain reproduces the tight-binding levels (`-√2, 0, √2` at `L=3`).

## Key reference

[@Sutherland1975] — Sutherland, "Model for a Multicomponent Quantum System", Phys. Rev. B **12**, 3795 (1975): the multicomponent (graded) Bethe-ansatz solution that contains the supersymmetric t-J chain at `J = 2t`. Schlottmann [@Schlottmann1987] gives the narrow-band / t-J formulation and thermodynamics. Rendered: _(Wave 3)_.
