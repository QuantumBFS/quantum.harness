# Superintegrable chiral Potts chain — exact-solution oracle

Technique: T3 (Bethe ansatz / Yang–Baxter) · Tier: B (integrable) · Script: T

## Hamiltonian & conventions

$$ H = -\sum_{i=1}^{L}\sum_{k=1}^{N-1}\Big[\, \bar\alpha_k\,\big(Z_i Z_{i+1}^\dagger\big)^k \;+\; \alpha_k\, X_i^k \,\Big], \qquad \alpha_k=\bar\alpha_k=\frac{2}{1-\omega^{-k}}=\frac{e^{\,i(\pi k/N-\pi/2)}}{\sin(\pi k/N)} $$

Conventions: `Z_N` **clock (`Z`) and shift (`X`)** operators at each of `L` sites, `Z=\mathrm{diag}(1,\omega,\dots,\omega^{N-1})`, `X|j\rangle=|j{+}1\bmod N\rangle`, `\omega=e^{2\pi i/N}`, with `ZX=\omega XZ`, `Z^N=X^N=\mathbb{1}`. PBC (`Z_{L+1}\equiv Z_1`). The couplings are **complex and chiral**: `|\alpha_k| = 1/\sin(\pi k/N)` but each `k`-mode carries the phase `e^{i(\pi k/N - \pi/2)}` — this phase *is* the chirality, and dropping it gives a **different model** (the achiral self-dual clock chain; see the warning below). **Hermiticity structure:** individual terms are *not* Hermitian, but `\alpha_{N-k}=\alpha_k^{*}` together with `(X^k)^\dagger=X^{N-k}` (and likewise for `(Z_iZ_{i+1}^\dagger)^k`) makes each of the two `k`-sums Hermitian as a whole (verified numerically: Hermiticity residual `<8×10^{-15}` at `L=6`). These couplings are the **superintegrable point** (chiral angles `\varphi=\bar\varphi=\pi/2` in the [@vonGehlenRittenberg1985] parametrization), the point that carries an infinite set of commuting charges and an Onsager-algebra symmetry. This is the self-dual, `Z_N`-symmetric parafermionic generalisation of the transverse-field Ising chain (`N=2` gives exactly TFIM at criticality). See `.knowledge/conventions.md`.

No dedicated model-zoo sibling under `.knowledge/models/`; the `N=2` reduction is the `tfim-chain` oracle card, and the classical 2D descendant is the chiral Potts *statistical* model whose star-triangle solution is [@BaxterPerkAuYang1988].

## Model identification (read this first)

"Chiral Potts" spans a classical 2D lattice model and a 1D quantum chain, and within each a *general* (integrable) line and a special **superintegrable** point. This card covers the **quantum chain at the superintegrable point** — the Hamiltonian written above. The reasons for pinning that specific object:

- The **general** integrable chiral Potts model has Boltzmann weights parametrised by rapidities `p, q` living on a **higher-genus algebraic curve** (genus `> 1` for `N\ge 3`), *not* on a rational/trigonometric/elliptic curve with a difference property — that departure is the whole story of why the model resisted solution until [@BaxterPerkAuYang1988] and why the usual Bethe-ansatz closed forms do **not** apply.
- The **superintegrable** point is the tractable slice: it acquires an extra infinite tower of conserved charges forming an **Onsager algebra** [@vonGehlenRittenberg1985] — the same algebra Onsager used to solve the 2D Ising model — so the spectrum organises into Ising-like "Onsager sectors" and much is known exactly.

**Coupling-convention warning (the N=2 trap).** The *complex* `\alpha_k = 2/(1-\omega^{-k})` above **is** the superintegrable chiral Potts convention. The superficially similar *real* couplings `\alpha_k = 1/\sin(\pi k/N)` — same magnitudes, no chiral phase — define a **distinct model**, the achiral self-dual `Z_N` clock (Fateev–Zamolodchikov-type) chain, which is *not* the superintegrable chiral Potts chain and fails the Dolan–Grady superintegrability test (measured residuals below). The two conventions **coincide at `N=2`** (both reduce to the critical TFIM), so an Ising-limit check cannot distinguish them — discriminate with the Dolan–Grady test or the pinned `N=3` ED numbers below.

Honest scope caveat: this is a **T-flag** card (no `oracle.py`). The exact statements are the integrability/algebraic facts below plus pinned finite-`L` ED numbers computed once for this card (script not shipped — see the note under the table). We do **not** ship a scripted thermodynamic ground-state energy, because no web-verified numeric value in *this card's exact normalisation* was found — see the honest row in the table.

## Solvability statement

T3 (Yang–Baxter, but off the difference property): the chiral Potts Boltzmann weights satisfy the **star–triangle (Yang–Baxter) relations** with rapidities on a higher-genus curve [@BaxterPerkAuYang1988]; the model is integrable (commuting transfer matrices, infinite conserved charges) yet the rapidity curve's genus `>1` blocks the elementary uniformisation that gives closed-form Bethe roots for the six/eight-vertex family. At the **superintegrable point** the quantum chain gains an **Onsager-algebra** symmetry [@vonGehlenRittenberg1985]: writing `H = H_X + H_Z` (the field and bond `k`-sums above) with normalised generators `A_0 \propto H_X`, `A_1 \propto H_Z`, the pair satisfies the **Dolan–Grady relations** `[A_0,[A_0,[A_0,A_1]]]=16\,[A_0,A_1]` (and `0\leftrightarrow1`), generating the Onsager algebra; eigenstates fall into Ising-like multiplets and the energy levels are `E=a+bk'+\sum_j m_j\sqrt{1+2k'\cos\theta_j+k'^2}` with occupation numbers `m_j\in\{0,\dots,N-1\}` and Ising-like `\theta_j` — a *parafermionic* free-particle-like spectrum. **Tier B, not A:** superintegrability makes the spectrum highly structured (and the order parameter exactly known, below), but the general model is not a single closed form, and finite-`L` energies/correlators still require the Onsager-sector machinery or ED. Out of this card's scope beyond the pinned numbers.

## No oracle script — tabulated benchmarks below

This is a **T-flag** card: there is no `oracle.py`. The concrete numbers pinned here are finite-`L` ED ground-state energies of the exact superintegrable Hamiltonian written above, in the fully specified `2/(1-\omega^{-k})` normalisation with `N=3` (computed once for this card, script not shipped — see the note under the table).

## Exact results

- Superintegrable point of the `Z_N` chiral Potts chain carries an **infinite set of commuting conserved charges** and an **Onsager-algebra** symmetry; the field/bond generators satisfy the **Dolan–Grady relations** `[A,[A,[A,B]]]=16[A,B]` [@vonGehlenRittenberg1985]
- General chiral Potts integrability: star–triangle relations with **rapidities on a genus `>1` curve** (no difference property) [@BaxterPerkAuYang1988]
- Parafermionic spectrum: Ising-like energy levels `E=a+bk'+\sum_j m_j\sqrt{1+2k'\cos\theta_j+k'^2}`, `m_j\in\{0,\dots,N-1\}` (Onsager sectors) [@vonGehlenRittenberg1985]
- **Order parameters** (spontaneous magnetisations) `\mathcal{M}_n=(1-k'^2)^{\,n(N-n)/2N^2}=k^{\,n(N-n)/N^2}`, `n=1,\dots,N-1` (conjectured 1989, proved by Baxter) [@Baxter2005] — critical exponents `\beta_n=n(N-n)/(2N^2)`
- `N=2` reduction is the critical transverse-field Ising chain (`tfim-chain`); order-parameter exponent `\beta_1=1/8` there

## Benchmarks

`e0 ≡ E_0/L`. **Pinned reference (this card):** the `N=3` superintegrable chiral Potts chain with the Hamiltonian written at the top — `H=-\sum_{i=1}^{L}\sum_{k=1}^{2}\alpha_k[(Z_iZ_{i+1}^\dagger)^k+X_i^k]`, `\alpha_1=2/(1-\omega^{-1})=1-i/\sqrt3`, `\alpha_2=\alpha_1^{*}=1+i/\sqrt3` (`|\alpha_k|=2/\sqrt3`), `Z=\mathrm{diag}(1,\omega,\omega^2)`, `\omega=e^{2\pi i/3}`, `X` the cyclic shift, PBC — dense/Lanczos ED.

| Quantity | Params | Value | Source |
|---|---|---|---|
| `E_0` (total, ED) | `N=3`, `L=8`, PBC | `−20.0323794586` | finite-`L` ED reference, this card |
| `e0 = E_0/L` (ED) | `N=3`, `L=8`, PBC | `−2.5040474323` | finite-`L` ED reference, this card |
| `E_0` (total, ED) | `N=3`, `L=6`, PBC | `−15.0702102767` | finite-`L` ED reference, this card |
| `e0 = E_0/L` (ED) | `N=3`, `L=6`, PBC | `−2.5117017128` | finite-`L` ED reference, this card |
| Dolan–Grady residual | `N=3`, `L=4`, `\alpha_k=2/(1-\omega^{-k})` | `3.8×10^{-16}` (holds) | this card (measured) |
| Dolan–Grady residual | `N=3`, `L=4`, `\alpha_k=1/\sin(\pi k/3)` (achiral) | `0.47` (fails — different model) | this card (measured) |
| order-parameter exponent | `\beta_n`, any `N` | `n(N-n)/(2N^2)` (`N=3`: `1/9`) | [@Baxter2005] |
| `e0` (thermodynamic) | `N=3`, `L→∞` | *no web-verified numeric value quoted here* | [@vonGehlenRittenberg1985; @BaxterPerkAuYang1988] |

The `L=6,8` energies are **finite-`L` ED references for this card, not thermodynamic values** — computed once (dense `eigvalsh` for `L=6` (`3^6=729`), Lanczos `eigsh` for `L=8` (`3^8=6561`), Hamiltonian exactly as above, Hermiticity residual `<8×10^{-15}`) to give future users pinned, unambiguous check numbers; they are **not** an extrapolation. The ground state is non-degenerate (finite-size gap `≈0.083` at `L=6`, `≈0.050` at `L=8`). The thermodynamic per-site energy is fixed by the exact solution [@vonGehlenRittenberg1985; @BaxterPerkAuYang1988] but we quote **no** number, because the literature values use different coupling normalisations and no web-verifiable number in *this* convention was found — treat those references as the exact source and the ED numbers as the pinned finite-size checks.

## Verification recipes

- To check an ED/DMRG code against the pinned point: build `Z=\mathrm{diag}(1,\omega,\omega^2)`, `X` = cyclic shift (`X|j\rangle=|j{+}1\bmod 3\rangle`), `\omega=e^{2\pi i/3}`, and `H=-\sum_{i=1}^{L}\sum_{k=1}^{2}\tfrac{2}{1-\omega^{-k}}[(Z_iZ_{i+1}^\dagger)^k+X_i^k]` with PBC, and reproduce `E_0(L=6)=−15.0702102767` and `E_0(L=8)=−20.0323794586` (per site `−2.5117017128`, `−2.5040474323`) to `1e-8`. A mismatch usually means a convention slip — most commonly using the **real** `1/\sin(\pi k/3)` couplings (that is the *achiral clock* model, a different chain: its `L=6` ground energy is `−17.0885…`, not `−15.0702…`), or `Z_iZ_{i+1}^\dagger` vs `Z_i^\dagger Z_{i+1}` (complex-conjugate chirality), a missing `k=2` term, or a sign on `H`.
- **The definitive superintegrability test (Dolan–Grady):** form `A = -(4/N)\sum_i\sum_k X_i^k/(1-\omega^{-k})` and `B = -(4/N)\sum_i\sum_k (Z_iZ_{i+1}^\dagger)^k/(1-\omega^{-k})` and check `[A,[A,[A,B]]]=16[A,B]`. With this card's complex couplings the measured relative residual is `3.8×10^{-16}` (`N=3`, `L=4`); with the real `1/\sin` couplings it is `0.47` — that single commutator test discriminates the superintegrable chiral Potts chain from the achiral clock chain. Beware the **`N=2` coincidence**: at `N=2` both conventions collapse to the critical TFIM, so an Ising-limit check passes for *both* and proves nothing about the chiral phases.
- To check a critical-exponent measurement: the order parameter exponents are `\beta_n=n(N-n)/(2N^2)`; for `N=3`, `\beta_1=\beta_2=1/9`. The `N=2` case degenerates to the Ising `\beta=1/8` (see `tfim-chain`).
- To confirm the Onsager structure: at the superintegrable point the energy levels are Ising-like, `E=a+bk'+\sum_j m_j\sqrt{1+2k'\cos\theta_j+k'^2}` with parafermionic occupations `m_j\in\{0,1,2\}` for `N=3` — level spacings organise into these multiplets, a fingerprint distinguishing the superintegrable point from a generic (non-superintegrable) chiral Potts chain.

## Key reference

[@BaxterPerkAuYang1988] — R. J. Baxter, J. H. H. Perk & H. Au-Yang, "New solutions of the star-triangle relations for the chiral Potts model", Phys. Lett. A **128**, 138 (1988): the star–triangle (Yang–Baxter) solution on the higher-genus rapidity curve that made the chiral Potts model integrable. The superintegrable quantum chain, its infinite conserved charges and Onsager algebra are von Gehlen & Rittenberg [@vonGehlenRittenberg1985]; the exact order parameter `\mathcal{M}_n=(1-k'^2)^{n(N-n)/2N^2}` is Baxter's proof [@Baxter2005] of the 1989 conjecture. Rendered: _(Wave 3)_.
