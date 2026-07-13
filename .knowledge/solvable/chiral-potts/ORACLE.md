# Superintegrable chiral Potts chain — exact-solution oracle

Technique: T3 (Bethe ansatz / Yang–Baxter) · Tier: B (integrable) · Script: T

## Hamiltonian & conventions

$$ H = -\sum_{i=1}^{L}\sum_{k=1}^{N-1}\Big[\, \bar\alpha_k\,\big(Z_i Z_{i+1}^\dagger\big)^k \;+\; \alpha_k\, X_i^k \,\Big], \qquad \alpha_k=\bar\alpha_k=\frac{1}{\sin(\pi k/N)} $$

Conventions: `Z_N` **clock (`Z`) and shift (`X`)** operators at each of `L` sites, `Z=\mathrm{diag}(1,\omega,\dots,\omega^{N-1})`, `X|j\rangle=|j{+}1\bmod N\rangle`, `\omega=e^{2\pi i/N}`, with `ZX=\omega XZ`, `Z^N=X^N=\mathbb{1}`. PBC (`Z_{L+1}\equiv Z_1`). The real, `k\!\leftrightarrow\!N{-}k$-symmetric couplings `\alpha_k=\bar\alpha_k=1/\sin(\pi k/N)` are the **superintegrable point** — the chiral angles are fixed at `\phi=\bar\phi=\pi/2` (maximal chirality), the point of the [@vonGehlenRittenberg1985] chain that carries an infinite set of commuting charges and an Onsager-algebra symmetry. This is the self-dual, `Z_N`-symmetric parafermionic generalisation of the transverse-field Ising chain (`N=2` gives exactly TFIM at criticality). See `.knowledge/conventions.md`.

No dedicated model-zoo sibling under `.knowledge/models/`; the `N=2` reduction is the `tfim-chain` oracle card, and the classical 2D descendant is the chiral Potts *statistical* model whose star-triangle solution is [@BaxterPerkAuYang1988].

## Model identification (read this first)

"Chiral Potts" spans a classical 2D lattice model and a 1D quantum chain, and within each a *general* (integrable) line and a special **superintegrable** point. This card covers the **quantum chain at the superintegrable point** — the Hamiltonian written above. The reasons for pinning that specific object:

- The **general** integrable chiral Potts model has Boltzmann weights parametrised by rapidities `p, q` living on a **higher-genus algebraic curve** (genus `> 1` for `N\ge 3`), *not* on a rational/trigonometric/elliptic curve with a difference property — that departure is the whole story of why the model resisted solution until [@BaxterPerkAuYang1988] and why the usual Bethe-ansatz closed forms do **not** apply.
- The **superintegrable** point (`\phi=\bar\phi=\pi/2`) is the tractable slice: it acquires an extra infinite tower of conserved charges forming an **Onsager algebra** [@vonGehlenRittenberg1985] — the same algebra Onsager used to solve the 2D Ising model — so the spectrum organises into Ising-like "Onsager sectors" and much is known exactly.

Honest scope caveat: this is a **T-flag** card (no `oracle.py`). The exact statements are the integrability/algebraic facts below plus one pinned finite-`L` ED number computed once for this card (script not shipped — see the note under the table). We do **not** ship a scripted thermodynamic ground-state energy, because no web-verified numeric value in *this card's exact `1/\sin` normalisation* was found — see the honest row in the table.

## Solvability statement

T3 (Yang–Baxter, but off the difference property): the chiral Potts Boltzmann weights satisfy the **star–triangle (Yang–Baxter) relations** with rapidities on a higher-genus curve [@BaxterPerkAuYang1988]; the model is integrable (commuting transfer matrices, infinite conserved charges) yet the rapidity curve's genus `>1` blocks the elementary uniformisation that gives closed-form Bethe roots for the six/eight-vertex family. At the **superintegrable point** the quantum chain gains an **Onsager-algebra** symmetry [@vonGehlenRittenberg1985]: `H=H_0+k'H_1` with `[H_0,[H_0,[H_0,H_1]]]=16[H_0,H_1]` (Dolan–Grady / Onsager relations), so eigenstates fall into Ising-like multiplets and the energy levels are `E=a+bk'+\sum_j m_j\sqrt{1+2k'\cos\theta_j+k'^2}` with occupation numbers `m_j\in\{0,\dots,N-1\}` and Ising-like `\theta_j` — a *parafermionic* free-particle-like spectrum. **Tier B, not A:** superintegrability makes the spectrum highly structured (and the order parameter exactly known, below), but the general model is not a single closed form, and finite-`L` energies/correlators still require the Onsager-sector machinery or ED. Out of this card's scope beyond the pinned number.

## No oracle script — tabulated benchmarks below

This is a **T-flag** card: there is no `oracle.py`. The one concrete number pinned here is a single finite-`L` ED ground-state energy of the exact superintegrable Hamiltonian written above, in the fully specified `1/\sin(\pi k/N)` normalisation with `N=3` (computed once for this card, script not shipped — see the note under the table).

## Exact results

- Superintegrable point (`\phi=\bar\phi=\pi/2`) of the `Z_N` chiral Potts chain carries an **infinite set of commuting conserved charges** and an **Onsager-algebra** symmetry [@vonGehlenRittenberg1985]
- General chiral Potts integrability: star–triangle relations with **rapidities on a genus `>1` curve** (no difference property) [@BaxterPerkAuYang1988]
- Parafermionic spectrum: Ising-like energy levels `E=a+bk'+\sum_j m_j\sqrt{1+2k'\cos\theta_j+k'^2}`, `m_j\in\{0,\dots,N-1\}` (Onsager sectors) [@vonGehlenRittenberg1985]
- **Order parameters** (spontaneous magnetisations) `\mathcal{M}_n=(1-k'^2)^{\,n(N-n)/2N^2}=k^{\,n(N-n)/N^2}`, `n=1,\dots,N-1` (conjectured 1989, proved by Baxter) [@Baxter2005] — critical exponents `\beta_n=n(N-n)/(2N^2)`
- `N=2` reduction is the critical transverse-field Ising chain (`tfim-chain`); order-parameter exponent `\beta_1=1/8` there

## Benchmarks

`e0 ≡ E_0/L`. **Pinned reference (this card):** the `N=3` superintegrable chiral Potts chain with the Hamiltonian written at the top — `H=-\sum_{i=1}^{L}\sum_{k=1}^{2}[\alpha_k(Z_iZ_{i+1}^\dagger)^k+\alpha_k X_i^k]`, `\alpha_1=\alpha_2=1/\sin(\pi/3)=2/\sqrt3`, `Z=\mathrm{diag}(1,\omega,\omega^2)`, `\omega=e^{2\pi i/3}`, `X` the cyclic shift, PBC — dense/Lanczos ED.

| Quantity | Params | Value | Source |
|---|---|---|---|
| `E_0` (total, ED) | `N=3`, `L=8`, PBC | `−22.6606773083` | finite-`L` ED reference, this card |
| `e0 = E_0/L` (ED) | `N=3`, `L=8`, PBC | `−2.8325846635` | finite-`L` ED reference, this card |
| `e0 = E_0/L` (ED) | `N=3`, `L=6`, PBC | `−2.8480873206` | finite-`L` ED reference, this card |
| order-parameter exponent | `\beta_n`, any `N` | `n(N-n)/(2N^2)` (`N=3`: `1/9`) | [@Baxter2005] |
| `e0` (thermodynamic) | `N=3`, `L→∞` | *no web-verified numeric value quoted here* | [@vonGehlenRittenberg1985; @BaxterPerkAuYang1988] |

The `L=6,8` energies are **finite-`L` ED references for this card, not thermodynamic values** — computed once (dense `eigvalsh` for `L=6` (`3^6=729`), Lanczos `eigsh` for `L=8` (`3^8=6561`), Hamiltonian exactly as above, Hermiticity residual `<5×10^{-15}`) to give future users a pinned, unambiguous check number; they are **not** an extrapolation. The ground state is non-degenerate (gap `≈0.318` at `L=8`). The thermodynamic per-site energy is fixed by the exact solution [@vonGehlenRittenberg1985; @BaxterPerkAuYang1988] but we quote **no** number, because the literature values use different coupling normalisations and no web-verifiable number in *this* `1/\sin` convention was found — treat those references as the exact source and the ED numbers as the pinned finite-size checks.

## Verification recipes

- To check an ED/DMRG code against the pinned point: build `Z=\mathrm{diag}(1,\omega,\omega^2)`, `X` = cyclic shift (`X|j\rangle=|j{+}1\bmod 3\rangle`), `\omega=e^{2\pi i/3}`, and `H=-\sum_{i=1}^{L}\sum_{k=1}^{2}\tfrac{1}{\sin(\pi k/3)}[(Z_iZ_{i+1}^\dagger)^k+X_i^k]` with PBC, and reproduce `E_0(L=8)=−22.6606773083` (per site `−2.8325846635`) to `1e-8`. A mismatch usually means a convention slip — wrong `\alpha_k` normalisation (`1/\sin` vs the complex `1/(1-\omega^{-k})` weights), `Z_iZ_{i+1}^\dagger` vs `Z_i^\dagger Z_{i+1}`, missing the `k=2` term, or a sign on `H`.
- To check a critical-exponent measurement: the order parameter exponents are `\beta_n=n(N-n)/(2N^2)`; for `N=3`, `\beta_1=\beta_2=1/9`. The `N=2` case degenerates to the Ising `\beta=1/8` (see `tfim-chain`).
- To confirm the Onsager structure: at the superintegrable point the energy levels are Ising-like, `E=a+bk'+\sum_j m_j\sqrt{1+2k'\cos\theta_j+k'^2}` with parafermionic occupations `m_j\in\{0,1,2\}` for `N=3` — level spacings organise into these multiplets, a fingerprint distinguishing the superintegrable point from a generic (non-superintegrable) chiral Potts chain.

## Key reference

[@BaxterPerkAuYang1988] — R. J. Baxter, J. H. H. Perk & H. Au-Yang, "New solutions of the star-triangle relations for the chiral Potts model", Phys. Lett. A **128**, 138 (1988): the star–triangle (Yang–Baxter) solution on the higher-genus rapidity curve that made the chiral Potts model integrable. The superintegrable quantum chain, its infinite conserved charges and Onsager algebra are von Gehlen & Rittenberg [@vonGehlenRittenberg1985]; the exact order parameter `\mathcal{M}_n=(1-k'^2)^{n(N-n)/2N^2}` is Baxter's proof [@Baxter2005] of the 1989 conjecture. Rendered: _(Wave 3)_.
