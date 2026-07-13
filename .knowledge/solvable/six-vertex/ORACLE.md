# Six-vertex (ice-type) model — exact-solution oracle

Technique: T2 (2D classical / transfer matrix) · Tier: B (integrable, Bethe ansatz) · Script: S

## Model & conventions

$$ Z = \sum_{\text{arrow configs}} a^{n_a}\, b^{n_b}\, c^{n_c}, \qquad \text{ice rule: exactly two arrows in, two out, at every vertex} $$

This is a **classical statistical / combinatorial model**, not an energy spectrum. Arrows live on the edges of the square lattice; the **ice rule** (two-in–two-out) leaves six allowed vertex types, in three weight-degenerate pairs $a,b,c$:

- Edge encoding: $+1$ = arrow points right (horizontal) or up (vertical), $-1$ = left/down. With this sign the ice rule at a vertex $(L,B,R,T)$ = (left, bottom, right, top edge) is exactly $L+B = R+T$ — six solutions, split as $a:(+,+,+,+),(-,-,-,-)$; $b:(+,-,+,-),(-,+,-,+)$; $c:(+,-,-,+),(-,+,+,-)$.
- Partition function $Z=\sum a^{n_a}b^{n_b}c^{n_c}$ over ice configurations on the torus; free energy per vertex $f=-T(\ln Z)/N$; partition function per vertex $\kappa=Z^{1/N}$, $\ln\kappa = -\beta f$.
- Anisotropy parameter $\Delta = (a^2+b^2-c^2)/(2ab)$. The **ice point** $a=b=c$ has $\Delta=\tfrac12$ and lies in the disordered regime.

See `.knowledge/conventions.md` for shared conventions. There is no model-zoo card for the six-vertex model; the nearest catalog relatives are the other T2 classical models (`ising-2d-onsager`, `dimer-kasteleyn`) and the `eight-vertex` card, which contains this one as its $d\to0$ limit.

## Solvability statement

T2 (2D classical / transfer matrix): the model is solved by diagonalizing the row-to-row transfer matrix, whose eigenvectors are the Bethe-ansatz states of the associated XXZ chain (Lieb 1967; Sutherland; Lieb–Wu). Lieb obtained the thermodynamic-limit free energy in every regime; at the ice point it gives the **residual entropy of square ice** $\ln W$, $W=(4/3)^{3/2}$. Exactly known and implemented here: Lieb's square-ice constant (algebraic closed form), the finite $N\times M$ **torus partition function** via the transfer matrix (cross-checked against brute-force enumeration — the ground truth), and the disordered-regime free-energy integral. **Not exact:** nothing — the six-vertex model is fully integrable and every quantity here is exact. Some exact quantities are simply out of this card's scope (not implemented): the ordered-regime (ferroelectric $\Delta>1$, antiferroelectric $\Delta<-1$) free energies, the correlation-length exponents, and the arctic-curve / domain-wall boundary results. The convergence anchor $\Lambda_{\max}(N)^{1/N}\to W$ is genuinely slow (power-law in $1/N$); the **exact-count anchor is the real gate**, and the card says so.

## Phase structure (by $\Delta$)

| Regime | $\Delta$ | Phase | Character |
|---|---|---|---|
| I / II | $\Delta>1$ ($a>b+c$ or $b>a+c$) | ferroelectric | frozen, ordered |
| III | $-1\le\Delta<1$ | **disordered** | critical / massless (power-law correlations) |
| IV | $\Delta<-1$ | antiferroelectric | Néel-ordered (gapped) |

The entire disordered regime is **critical** (a line of fixed points, central charge $c=1$), approached from the antiferroelectric side through a **BKT (Kosterlitz–Thouless) transition** at $\Delta=-1$ and terminating at the ferroelectric freezing transition at $\Delta=+1$. The ice point $\Delta=\tfrac12$ sits in the interior of this critical phase — square ice is a critical, not an ordered, state, which is why its residual entropy is a nontrivial algebraic number rather than $\ln(\text{integer})$.

## Exact results

- Lieb's square-ice constant (ice point $a=b=c$): $W = (4/3)^{3/2} = 1.5396007\ldots$; residual entropy per vertex $\ln W = \tfrac32\ln\tfrac43 = 0.4315231\ldots$ (algebraic, no quadrature) [@Lieb1967]
- Disordered-regime free energy ($-1<\Delta<1$), with $\Delta=-\cos\zeta$, $\zeta\in(0,\pi)$, and $\varphi=\arcsin(b\sin\zeta/c)$ (so $a=b\Leftrightarrow\varphi=\zeta/2$):
$$ \ln\kappa = \ln b + \int_{-\infty}^{\infty} \frac{\sinh[(2\zeta-2\varphi)t]\,\sinh[(\pi-\zeta)t]}{2t\,\cosh(\zeta t)\,\sinh(\pi t)}\,dt $$
reproducing $\ln W$ at the ice point [@Lieb1967]
- Finite $N\times M$ torus: $Z = \mathrm{tr}\,V_N^{\,M}$, $V_N$ the $2^N\times2^N$ transfer matrix in the vertical-arrow basis; equals the exact enumeration of ice configurations [@Lieb1967]
- Ice-configuration counts: the number of two-in–two-out configurations on the $N\times M$ torus (e.g. $2970$ on $4\times4$)

## Oracle script

`python oracle.py --a 1 --b 1 --c 1 --N 4 --M 4` → prints `lieb_constant`, `entropy_per_vertex`, `Delta`, `logZ_torus` ($\ln$ of the exact $N\times M$-torus partition function), and `free_energy_disordered` (when $|\Delta|<1$). Importable: `compute(a,b,c,N,M)`; helpers `lieb_constant()`, `transfer_matrix(N,a,b,c)`, `logZ_torus(N,M,a,b,c)`, `free_energy_disordered(a,b,c)` (log-space $\ln\kappa$).

Self-test anchors: (1) `lieb_constant()` $=(4/3)^{3/2}$ and $\ln W=\tfrac32\ln\tfrac43$ to `1e-12` (algebraic); (2) **ground truth** — `tr(V_N^M)` equals a vectorised brute-force enumeration over all $2^{2NM}$ edge configurations for tori with $2NM\le18$, exact integer count at $a=b=c=1$ and exact float partition function at generic $(a,b,c)$ (tol `1e-8`), and the $4\times4$ ice count $=2970$; (3) the disordered free-energy integral reproduces $\ln W$ at the ice point to `1e-8`; (4) $\Lambda_{\max}(N)^{1/N}\to W$ — width-6 within 5% of $W$ **and** strictly closer than width-2 (the honest slow-convergence statement; anchor (2) is the gate).

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `lieb_constant` | ice point $a=b=c$ | $(4/3)^{3/2}=1.5396007$ | [@Lieb1967] |
| `entropy_per_vertex` | ice point | $\tfrac32\ln\tfrac43 = 0.4315231$ | [@Lieb1967] |
| `logZ_torus` | $4\times4$, $a=b=c=1$ | $\ln 2970 = 7.9963172$ | [@Lieb1967] |
| `free_energy_disordered` | ice point | $=\ln W = 0.4315231$ | [@Lieb1967] |

## Verification recipes

- To check a transfer-matrix / tensor-network six-vertex code (any weights): compare $\ln Z$ against `logZ_torus(N, M, a, b, c)` for a torus small enough to also enumerate — exact equality, `1e-8`.
- To check a residual-entropy / square-ice enumeration or a Monte Carlo entropy estimate: compare against `lieb_constant()` ($W$) or `entropy_per_vertex` ($\ln W$), accounting for the slow $\Lambda_{\max}(N)^{1/N}$ finite-size convergence.
- To check a claimed disordered free energy at generic $a,b,c$ with $|\Delta|<1$: compare against `free_energy_disordered(a, b, c)`.

## Key reference

[@Lieb1967] — Lieb's exact solution of square ice: the residual-entropy constant $W=(4/3)^{3/2}$, the Bethe-ansatz diagonalization of the ice/six-vertex transfer matrix, and the disordered-regime free energy whose ice-point value this card reproduces. Rendered: _(Wave 3)_.
