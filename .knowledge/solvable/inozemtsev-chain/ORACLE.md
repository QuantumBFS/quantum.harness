# Inozemtsev chain — exact-solution oracle

Technique: T3 (Bethe ansatz / Yang–Baxter, elliptic) · Tier: B (integrable) · Script: T

## Hamiltonian & conventions

$$ H = \sum_{i<j} J(i-j)\,\mathbf{S}_i\cdot\mathbf{S}_j, \qquad J(r) = \wp\!\left(r;\, \omega_1=\tfrac{N}{2},\, \omega_2=\tfrac{i\pi}{2\kappa}\right) $$

Conventions: spin-1/2 `S`-operators (`S^a = σ^a/2`), `N` even, periodic ring of `N` sites. The exchange is the **Weierstrass `℘` function** with real half-period `ω₁ = N/2` (fixing the `N`-site periodicity, `J(r)=J(r+N)`) and imaginary half-period `ω₂ = iπ/(2κ)` (setting the interaction range through `κ`), up to an additive constant absorbing `℘`'s pole normalisation. This is the **elliptic** (doubly-periodic) exchange that interpolates the two `1/r²`-family limits below. See `.knowledge/conventions.md`.

No dedicated model-zoo sibling under `.knowledge/models/`; the two integrable endpoints each have an oracle card — `heisenberg-xxx` (nearest-neighbour XXX) and `haldane-shastry` (`1/r²` chord chain).

## Model identification (read this first)

The slug names Inozemtsev, whose 1990 paper "On the connection between the one-dimensional `S=1/2` Heisenberg chain and Haldane–Shastry model" [@Inozemtsev1990] introduced this elliptic-exchange chain as a **one-parameter family interpolating between two known integrable points**:

- **`κ → ∞` (short-range limit):** the imaginary period `ω₂ → 0`, `℘` collapses so that `J(r)` retains only the `r=1` bond — the **nearest-neighbour Heisenberg XXX chain** (`heisenberg-xxx`), `E/N → 1/4 − ln 2`.
- **`κ → 0` (long-range limit):** the imaginary period `ω₂ → ∞`, `℘` degenerates to the trigonometric `1/sin²` chord form — the **Haldane–Shastry `1/r²` chain** (`haldane-shastry`), `e0 → −π²/24`.

At generic `κ` the chain is a genuinely distinct long-range model, **not** reducible to either endpoint; it is nevertheless integrable (below). A convenient one-sided degeneration replaces the elliptic `℘` by its **hyperbolic** limit `J(r) ∝ sinh²κ / sinh²(κr)` (the `ω₁ → ∞` open-line form), which is the concrete normalisation used for this card's pinned finite-`L` number.

## Solvability statement

T3 (Bethe ansatz / Yang–Baxter, elliptic): the Inozemtsev chain is **integrable at every `κ`** — it possesses a full tower of commuting conserved charges, and its spectrum is accessible through a (coordinate/asymptotic) Bethe ansatz with elliptic two-body data [@Inozemtsev1990]. It is the spin analogue of the elliptic Calogero–Moser–Sutherland system, and the two limits inherit the closed-form solvability of their endpoints (Bethe ansatz at `heisenberg-xxx`, Yangian/Jastrow at `haldane-shastry`). **Tier B, not A:** integrable but not a single closed form — at generic `κ` there is no elementary expression for the ground energy; the finite-`N`/thermodynamic energetics require solving the elliptic Bethe equations state-by-state, and correlation functions need heavier machinery. Out of this card's scope.

## No oracle script — tabulated benchmarks below

This is a **T-flag** card: there is no `oracle.py`. The exact statements are the integrability/interpolation facts above and the literature results below; the one concrete number this card pins is a single finite-`L` ED ground-state energy at one intermediate coupling, in a fully specified periodic normalisation (computed once for this card, script not shipped — see the note under the table).

## Exact results

- Elliptic-exchange `S=1/2` chain integrable at all `κ`: a one-parameter integrable family with a full set of commuting charges [@Inozemtsev1990]
- Interpolates the two integrable `1/r²`-family points: `κ→∞` ⇒ nearest-neighbour XXX (`heisenberg-xxx`); `κ→0` ⇒ Haldane–Shastry `1/r²` chord chain (`haldane-shastry`) [@Inozemtsev1990]
- Spin analogue of the elliptic Calogero–Moser–Sutherland system; two-magnon (two spin-wave) scattering solved explicitly in closed form [@Inozemtsev1990]
- Ground state is a total-spin singlet in the `S^z_{tot}=0` sector (`N` even)

## Benchmarks

`e0 ≡ E/N`. **Pinned reference normalisation (this card):** the *hyperbolic-limit* Inozemtsev exchange with **nearest-image periodization** on the `N`-site ring —

$$ H = \sum_{i<j} J(r_{ij})\,\mathbf{S}_i\cdot\mathbf{S}_j, \quad J(r) = \frac{\sinh^2\kappa}{\sinh^2(\kappa r)}, \quad r_{ij} = \min(|i-j|,\, N-|i-j|), \quad \kappa = 1, $$

spin-1/2 `S = σ/2`, PBC — dense ED at `N=8`.

| Quantity | Params | Value | Source |
|---|---|---|---|
| `E0` (total, ED) | `N=8`, `κ=1`, hyperbolic, PBC | `−3.5083521420` | finite-`L` ED reference, this card |
| `e0 = E0/N` (ED) | `N=8`, `κ=1`, hyperbolic, PBC | `−0.4385440178` | finite-`L` ED reference, this card |
| `e0` (limit `κ→∞`) | `N→∞` | `1/4 − ln 2 ≈ −0.4431472` (XXX) | [@Inozemtsev1990] → `heisenberg-xxx` |
| `e0` (limit `κ→0`) | `N→∞` | `−π²/24 ≈ −0.4112335` (Haldane–Shastry) | [@Inozemtsev1990] → `haldane-shastry` |

The `N=8` energy is a **finite-`L` ED reference for this card, not a thermodynamic value** — computed once (spin-1/2 ED, PBC, the hyperbolic `κ=1` nearest-image Hamiltonian written above) to give future users a pinned, unambiguous check number; it is **not** an extrapolation. The two limit rows are the *endpoint* thermodynamic energies (see the linked oracle cards for their exact derivations), included to show the interpolation, not properties of the `κ=1` point.

## Verification recipes

- To check an ED/DMRG code against the pinned point: build `H = Σ_{i<j} [\sinh²κ/\sinh²(κ r_{ij})]\,\mathbf{S}_i·\mathbf{S}_j` with `κ=1`, nearest-image `r_{ij}=\min(|i−j|,N−|i−j|)`, `S=σ/2`, PBC, and reproduce `E0(N=8) = −3.5083521420` (per site `−0.4385440178`) to `1e-8`. A mismatch usually means a periodization slip (using the raw `|i−j|` instead of the nearest image), a `κ` or normalisation difference, or Pauli-vs-`S` operators (a factor `4`).
- To confirm the interpolation numerically: as `κ` is raised the ED ground energy per site should drift toward the XXX value `1/4 − ln 2` (only the `r=1` bond survives); as `κ→0` it should drift toward the Haldane–Shastry `−π²/24`. Check the two endpoints against the sibling oracle cards `heisenberg-xxx` and `haldane-shastry`.

## Key reference

[@Inozemtsev1990] — Inozemtsev, "On the connection between the one-dimensional `S=1/2` Heisenberg chain and Haldane–Shastry model", J. Stat. Phys. **59**, 1143 (1990): the elliptic-exchange chain, its integrability, and the two `1/r²`-family limits pinned by the neighbour cards `heisenberg-xxx` (`κ→∞`) and `haldane-shastry` (`κ→0`). Rendered: _(Wave 3)_.
