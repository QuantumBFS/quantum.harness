# Dimer coverings of the square lattice (Kasteleyn) — exact-solution oracle

Technique: T2 (2D classical / transfer matrix) · Tier: A (closed-form, exact) · Script: S

## Model & conventions

$$ Z(m,n) = \#\{\text{perfect matchings of the } m\times n \text{ grid graph}\} = \#\{\text{domino tilings of the } m\times n \text{ board}\} $$

This is an exactly-solvable **combinatorial / classical statistical model**, not an energy spectrum:

- A *dimer* covers one edge of the lattice (two adjacent sites); a *dimer covering* (perfect matching / domino tiling) covers every site exactly once. $Z(m,n)$ counts them.
- Boundaries: **OPEN (free)** — the $m\times n$ grid graph with no wrap-around. This is the boundary condition the shipped product formula is exact for.
- All dimers have equal weight $1$, so $Z$ is a pure count (an integer). With edge fugacities it would become a weighted partition function; that generalization is out of scope here.
- $Z(m,n) = 0$ whenever $mn$ is odd (an odd number of sites cannot be perfectly matched). Entropy per site $s = (\ln Z)/N$, $N = mn$.

See `.knowledge/conventions.md` for shared conventions. There is no model-zoo card for the dimer model; the closest relatives in this catalog are the other T2 classical models (`ising-2d-onsager`, `ising-triangular`) and the quantum `rk-quantum-dimer` card (wave 3), whose Rokhsar–Kivelson point sits on top of the classical dimer ensemble counted here.

## Solvability statement

T2 (2D classical / transfer matrix), by the **Kasteleyn Pfaffian method**. Kasteleyn (1961) showed that the perfect matchings of a planar lattice are counted by the Pfaffian of a suitably **oriented** (signed) adjacency matrix: choosing edge orientations so that every elementary face is "clockwise-odd" makes every matching contribute $+1$ to the Pfaffian, so $Z = |\mathrm{Pf}(A)| = \sqrt{|\det A|}$. Diagonalizing $A$ for the open $m\times n$ grid gives the eigenvalues $\pm 2i\cos\frac{j\pi}{m+1} \pm 2\cos\frac{k\pi}{n+1}$ and hence the closed **product form** below. Everything reported — the exact integer count for any finite board and the thermodynamic-limit entropy — is exact. **Not exact:** nothing about the *open-boundary* count; it is exact and closed-form. What is **out of scope** (exactly solvable, but not implemented here): the **torus (periodic) dimer count**, which on a genus-1 surface is not a single Pfaffian but a signed combination of **four** Pfaffians (the four spin structures) — exactly known, but a different formula from the one shipped; and weighted/monomer-doped variants. The card is honest about this: the product formula here is for **open boundaries only**.

## Exact results

- Kasteleyn product formula (open $m\times n$, symmetric full-range form):
$$ Z(m,n) = \prod_{j=1}^{m}\prod_{k=1}^{n}\left(4\cos^2\frac{j\pi}{m+1} + 4\cos^2\frac{k\pi}{n+1}\right)^{1/4} $$
The $1/4$ power compensates the double counting under $j\leftrightarrow m{+}1{-}j$ and $k\leftrightarrow n{+}1{-}k$; the result is an exact integer when $mn$ is even and $0$ when $mn$ is odd. [@Kasteleyn1961]
- Thermodynamic-limit entropy per site: $\displaystyle \lim_{m,n\to\infty}\frac{\ln Z(m,n)}{mn} = \frac{G}{\pi} \approx 0.2915609$, where $G = 0.9159655942\ldots$ is **Catalan's constant** [@Kasteleyn1961]
- Open boundaries converge to this limit only **algebraically**: the per-site entropy sits below $G/\pi$ by an $O(1/L)$ boundary deficit ($L\times(\text{deviation})\approx 0.297$, nearly constant), so an $L\times L$ board reaches $G/\pi$ slowly (16×16 is ~6% low; 64×64 is ~1.6% low).

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| $n_\text{coverings}$ | $2\times2$ | $2$ | [@Kasteleyn1961] |
| $n_\text{coverings}$ | $2\times3$ | $3$ | [@Kasteleyn1961] |
| $n_\text{coverings}$ | $4\times4$ | $36$ | [@Kasteleyn1961] |
| $n_\text{coverings}$ | $8\times8$ open | $12\,988\,816$ | [@Kasteleyn1961] |

The $8\times8 = 12{,}988{,}816$ row is the classic Fisher–Kasteleyn benchmark (the number of ways to tile a chessboard with 32 dominoes).

## Oracle script

`python oracle.py --m 8 --n 8` → prints `n_coverings` (exact integer count), `ln_Z`, `entropy_per_site` ($=\ln Z/mn$), `catalan_limit` ($=G/\pi$). Importable: `compute(m=8, n=8)`; individual functions `count(m, n)`, `ln_Z(m, n)` (log space), `entropy_per_site(m, n)`, `catalan_limit()`.

`count` is an **exact integer only while $Z < 2^{53}$** (through $8\times8$ and up to about $10\times10$); for larger boards (e.g. $12\times12$) float64 rounds the trailing digits, so trust `ln_Z`/`entropy_per_site` there rather than the integer.

Self-test anchors: (1) exact integer counts `count(2,2)=2`, `count(2,3)=3`, `count(4,4)=36`, `count(8,8)=12988816`, and $Z=0$ for odd area ($3\times3$, $5\times5$); (2) **ground truth** — a broken-profile bitmask enumeration of domino tilings equals the product formula for **every** board with $mn\le 16$ (exact integer equality); (3) the entropy per site approaches $G/\pi$ **from below and monotonically** ($e_{8\times8} < e_{16\times16} < e_{64\times64} < G/\pi$), with $16\times16$ closer than $8\times8$ and $64\times64$ within 2% of $G/\pi$ (16×16 is not yet within 2% — the open-boundary $O(1/L)$ deficit is honest here, not hidden).

## Verification recipes

- To check a dimer / domino-tiling enumeration or a Pfaffian code (open boundaries): compare its count against `count(m, n)` for $mn$ small enough that $Z < 2^{53}$ — exact integer equality.
- To check a classical / quantum dimer-model tensor-network or Monte Carlo estimate of the entropy density: compare $(\ln Z)/N$ against `entropy_per_site(m, n)` at the same finite size, or against `catalan_limit()` in the large-$L$ extrapolation (accounting for the $O(1/L)$ open-boundary correction).
- To check an RK-point quantum-dimer ground-state degeneracy / dimer count: the open-lattice classical count is `count(m, n)` (see the `rk-quantum-dimer` card).

## Key reference

[@Kasteleyn1961] — Kasteleyn's Pfaffian solution of the dimer problem on a quadratic lattice: source of the product formula, the $8\times8 = 12{,}988{,}816$ benchmark, and the Catalan-constant entropy density $G/\pi$. Rendered: _(Wave 3)_.
