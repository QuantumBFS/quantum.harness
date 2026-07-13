# Hard-hexagon lattice gas (Baxter) — exact-solution oracle

Technique: T2 (2D classical / transfer matrix) · Tier: B (integrable, corner transfer matrix) · Script: P

## Model & conventions

$$ Z(z) = \sum_{\text{independent sets } S} z^{|S|}, \qquad \text{triangular lattice, no two nearest neighbours both occupied} $$

A **classical lattice gas**: particles occupy sites of the triangular lattice; the **hard-hexagon exclusion** forbids two particles on nearest-neighbour sites (each particle "covers" a hexagon of neighbours). Each occupied site carries an activity (fugacity) $z$.

- Geometry: draw the triangular lattice as a square grid with the extra down-right diagonal bonds — site $(i,j)$ is adjacent to $(i,j\pm1)$, $(i\pm1,j)$, and $(i{+}1,j{+}1)/(i{-}1,j{-}1)$: six neighbours. Boundaries periodic (torus).
- $Z(z)=\sum_{\text{independent sets}} z^{|S|}$; density $\rho(z)=\frac{z}{N}\partial_z\ln Z$; maximum density $\tfrac13$ (one of three sublattices fully packed).
- Headline: a fluid→solid critical point at the **golden-ratio** activity $z_c=\varphi^5$, $\varphi=\tfrac{1+\sqrt5}2$.

See `.knowledge/conventions.md`. There is no model-zoo card; the closest catalog relatives are the other T2 classical models (`ising-triangular` — same lattice, spins not a gas) and the transfer-matrix machinery of `six-vertex`/`eight-vertex`.

## Solvability statement

T2 (2D classical / transfer matrix): Baxter (1980) solved the hard-hexagon model exactly using the **corner-transfer-matrix (CTM) method** — the "miracle" being that the sublattice densities and the free energy come out as **Rogers–Ramanujan** functions, and the critical activity is the algebraic number $z_c=(11+5\sqrt5)/2=\varphi^5$. **Not exact:** nothing — the model is exactly solvable in its entirety; nothing about it is approximate.

**Script scope — this is a P (partial) card.** What the script *does*: (i) the critical activity $z_c$ in closed form, with the in-card **golden-ratio identity** $z_c=\varphi^5=5\varphi+3=(11+5\sqrt5)/2$ checked two ways; (ii) the **exact ground truth** — the row-to-row transfer matrix on occupation states of a width-$W$ triangular strip ($W\le6$), whose $\mathrm{tr}\,T^N$ equals a brute-force enumeration of hard-hexagon configurations on the $N\times W$ torus (exact integer count at $z=1$, exact float at generic $z$); (iii) the **density** $\rho(z)$ from the largest eigenvalue, monotone across $z_c$ and reproducing the low-activity virial series. What it deliberately does **not** compute (exact, but **tabulated** below with citation): the **critical exponents** $\alpha=1/3$, $\beta=1/9$ (three-state-Potts universality) and the **sublattice order parameter** $R$ — Baxter's Rogers–Ramanujan one-point functions are quoted, not recomputed. The precise split: *$z_c$, torus counts, and $\rho(z)$ = scripted; exponents and order parameter = tabulated.*

## Golden-ratio criticality (the headline)

With $\varphi=\tfrac{1+\sqrt5}2$ the golden ratio, the Fibonacci identity $\varphi^5=5\varphi+3$ gives
$$ z_c \;=\; \varphi^5 \;=\; 5\varphi+3 \;=\; \frac{11+5\sqrt5}{2} \;=\; 11.0901699\ldots $$
Below $z_c$ the gas is a homogeneous fluid (all three triangular sublattices equally occupied); above $z_c$ one sublattice is preferentially filled — a spontaneously broken $\mathbb Z_3$ symmetry, placing the transition in the **three-state Potts** universality class. That the fluid/solid boundary lands exactly on the fifth power of the golden ratio is Baxter's celebrated closed form.

## Exact results

- Critical activity: $z_c=(11+5\sqrt5)/2=\varphi^5=11.0901699\ldots$ [@Baxter1980]
- Finite $N\times W$ torus: $Z(z)=\mathrm{tr}\,T^N$, $T$ the width-$W$ triangular-strip transfer matrix; equals the exact enumeration of hard-hexagon configurations (e.g. $201$ independent sets on the $4\times4$ torus at $z=1$) [@Baxter1980]
- Low-activity virial series (bulk density): $\rho = z - 7z^2 + 58z^3 - 519z^4 + 4856z^5 - \cdots$; the width-$W$ strip reproduces the leading coefficients ($\rho\to z$, $(\rho-z)/z^2\to-7$ as $z\to0$) [@Baxter1980]
- **Tabulated (not scripted)** — critical exponents $\alpha=1/3$ (specific heat), $\beta=1/9$ (order parameter), three-state-Potts universality; sublattice order parameter $R=\rho_1-\rho_2 = Q(x)Q(x^5)/Q(x^3)^2$ (Rogers–Ramanujan $Q$), with the near-critical density $\rho(z_c)\approx0.2764$ (the width-6 strip value, observed) [@Baxter1980]

## Oracle script

`python oracle.py --z 1.0 --N 4 --W 4` → prints `zc`, `logZ_torus` ($\ln$ of the exact $N\times W$-torus partition function), and `density_width6` ($\rho(z)$ from the width-6 strip). Importable: `compute(z,N,W)`; helpers `zc()`, `transfer_matrix(W,z)`, `logZ_torus(N,W,z)`, `density(z,W)`.

Self-test anchors: (1) $z_c=(11+5\sqrt5)/2=\varphi^5=5\varphi+3$ to `1e-12` (two algebraic forms agree); (2) **ground truth** — `tr(T^N)` equals brute-force torus enumeration over all $2^{NW}$ occupations: exact integer count at $z=1$ (incl. the $4\times4$ count $201$) and exact float partition function at $z=0.7$ (tol `1e-10`); (3) $\rho(z)$ monotone increasing across $z_c$, bounded by the packing limit $\tfrac13$, and resolution-consistent between widths 4, 5, 6 in the low-activity phase (`1e-3`); (4) low-activity series — $\rho/z\to1$ and $(\rho-z)/z^2\to-7$ as $z\to0$ (reproducing the $-7z^2$ virial coefficient).

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `zc` | — | $(11+5\sqrt5)/2=\varphi^5=11.0901699$ | [@Baxter1980] |
| `logZ_torus` | $4\times4$, $z=1$ | $\ln 201 = 5.3033049$ (independent-set count) | [@Baxter1980] |
| `density_width6` | $z\to0$ | $\rho\to z-7z^2+\cdots$ | [@Baxter1980] |
| exponents (tabulated) | at $z_c$ | $\alpha=1/3,\ \beta=1/9$ (3-state Potts) | [@Baxter1980] |

## Verification recipes

- To check a hard-hexagon / triangular hard-core transfer-matrix or enumeration code: compare $\ln Z$ against `logZ_torus(N, W, z)` on a torus small enough to also enumerate — exact integer count at $z=1$, exact float at generic $z$.
- To check a claimed critical activity from a finite-size crossing: compare against `zc()` ($=\varphi^5$).
- To check a Monte Carlo / DMRG density curve $\rho(z)$: compare against `density(z, W)` in the fluid phase (and against the tabulated exponents $\alpha,\beta$ near $z_c$), accounting for the finite-$W$ strip correction.

## Key reference

[@Baxter1980] — Baxter's exact hard-hexagon solution by the corner-transfer-matrix method: the golden-ratio critical activity $z_c=(11+5\sqrt5)/2$, the Rogers–Ramanujan sublattice densities and order parameter, and the exponents $\alpha=1/3$, $\beta=1/9$ that this card scripts ($z_c$, counts, $\rho$) and tabulates (exponents, $R$). Rendered: _(Wave 3)_.
