# Tight-binding lattices (square, honeycomb, kagome, Lieb) — exact-solution oracle

Technique: T1 (free-fermion / Bloch diagonalization) · Tier: A (closed-form, exact) · Script: S

## Hamiltonian & conventions

$$ H = -t \sum_{\langle i,j\rangle} \left(c^\dagger_i c_j + \text{h.c.}\right), \qquad t = 1 \text{ default} $$

i.e. `H = -t × (nearest-neighbor adjacency matrix)` on one of four 2D lattices, selected via `--lattice square|honeycomb|kagome|lieb`. Spinless fermions, single-particle band structure (the many-body ground state at any filling is the Slater determinant of the lowest bands — this card reports band-structure quantities only). All four Bloch Hamiltonians below are written in **reduced crystal-momentum coordinates** `u = k·a₁`, `v = k·a₂` (each a full `2π` period), so a plain uniform grid `u,v ∈ [0,2π)` is exactly one Brillouin zone for every lattice — no lattice-specific BZ geometry is needed in the implementation. See `.knowledge/conventions.md`.

- **Square**: Bravais vectors `a₁=(1,0), a₂=(0,1)`; 1 site/cell.
- **Honeycomb**: triangular Bravais vectors `a₁,a₂` at 60°; 2 sites/cell (A, B), A–B bonds at cell-offsets `0, -a₁, -a₂`.
- **Kagome**: same `a₁,a₂` as honeycomb; 3 sites/cell (A at `0`, B at `a₁/2`, C at `a₂/2`), each pair of sublattices connected by 2 bonds (offsets `0` and `-aᵢ`).
- **Lieb**: same `a₁,a₂` as square; 3 sites/cell (A corner at `0`, B edge-center at `a₁/2`, C edge-center at `a₂/2`); bipartite — only A–B and A–C bonds exist, B and C never connect directly.

## Solvability statement

T1: each lattice's Hamiltonian is quadratic and translationally invariant, block-diagonalized exactly by Fourier transform into an `n×n` Bloch matrix per crystal momentum (`n` = sites per unit cell: 1, 2, 3, 3). Everything reported here — the full band structure (via numerical diagonalization of the Bloch matrix on a fine `u,v` grid), the bandwidth, the flat-band energy where one exists, the honeycomb Dirac-point gap (evaluated exactly at the analytic Dirac point, not by grid search), and a grid-histogram estimate of the DOS peak — is obtained from the exact Bloch Hamiltonian; the only numerical ingredients are the (exact, textbook) matrix diagonalization and, for `dos_van_hove` only, a finite-resolution energy histogram (see below). The model is exactly solvable in its entirety; there is no approximation in the Hamiltonian or its diagonalization. **Not exact:** nothing about the band structure itself is approximate. `dos_van_hove` specifically is computed as the bin-center of the highest-count bin of a `400`-bin histogram over the sampled grid's eigenvalues — a numerical estimate whose value depends on grid/bin resolution (stated explicitly here, not a hidden imprecision: the underlying spectrum is exact, only the *peak-finding* is a numerical convenience). For the square lattice this estimate converges to the exactly-derivable value `E=0` (see below); for the flat-band lattices (kagome, Lieb) the histogram peak is dominated by the flat band itself, which is correct — a flat band is an even stronger DOS singularity than a van Hove point — but is a different phenomenon than a van Hove saddle-point divergence. Out of this card's scope entirely (not attempted): real-space flat-band eigenstate wavefunctions (see below for the one-line description), correlation functions, and interacting extensions.

## Exact results

### Dispersions (Bloch matrix eigenvalues; `t=1` default; `u=k·a₁, v=k·a₂`)

- **Square** (1 band): $\varepsilon(u,v) = -2t(\cos u + \cos v)$. Bandwidth $= 8t$ (min $-4t$ at $u=v=0$, max $+4t$ at $u=v=\pi$).
- **Honeycomb** (2 bands): $f(u,v) = 1 + e^{iu} + e^{iv}$; $\varepsilon_\pm(u,v) = \pm t\,|f(u,v)|$. Dirac points where $f=0$: since $1+e^{iu}+e^{iv}=0$ iff $\{0,u,v\}$ are the three cube roots of unity's arguments, $K=(u,v)=(2\pi/3,\,4\pi/3)$ (and symmetry-related points) — bands touch exactly, $\varepsilon_+(K)=\varepsilon_-(K)=0$.
- **Kagome** (3 bands): with $x=\cos(u/2), y=\cos(v/2), z=\cos((v-u)/2)$, the Bloch matrix is
  $$ H(u,v) = -2t \begin{pmatrix} 0 & x & y \\ x & 0 & z \\ y & z & 0 \end{pmatrix} $$
  which has eigenvalue $\varepsilon_{\text{flat}} = +2t$ for **all** $(u,v)$ (identity $x^2+y^2+z^2-2xyz\equiv 1$ makes $-1$ an eigenvalue of the unit-off-diagonal matrix identically) and two dispersive bands $\varepsilon_\pm(u,v) = -t\big(1 \mp \sqrt{4(x^2+y^2+z^2)-3}\big)$, touching the flat band at $\Gamma$ ($u=v=0$).
- **Lieb** (3 bands): with $h_{AB}=-t(1+e^{-iu})$, $h_{AC}=-t(1+e^{-iv})$, the bipartite structure gives one identically-zero eigenvalue for all $(u,v)$ (the vector $(0,\,h_{AC},\,-h_{AB})$ is an exact null vector of the Bloch matrix) plus $\varepsilon_\pm(u,v) = \pm\sqrt{|h_{AB}|^2+|h_{AC}|^2} = \pm t\sqrt{4+2\cos u+2\cos v}$.

### Flat bands and their real-space eigenstates

- **Kagome** flat band at $E=+2t$: the localized eigenstate is the alternating-sign amplitude around a single elementary hexagon (zero amplitude everywhere else), destructively interfering out of every corner-sharing triangle it touches — the paradigm flat-band "loop state" [@Bergman2008].
- **Lieb** flat band at $E=0$: the localized eigenstate lives on the four edge-center sites surrounding one empty square plaquette with alternating $\pm1$ amplitudes (zero on all corner sites), again destructively canceling at every corner site it borders [@Bergman2008].
- Both are compact localized states: finite real-space support, exactly zero group velocity, existing because the lattice geometry (corner-sharing triangles for kagome, the edge-decorated square net for Lieb) permits perfect destructive interference — the general mechanism analyzed in [@Bergman2008].

### DOS van Hove point

- **Square only** (stated per this card's scope): $\varepsilon(u,v)=-2t(\cos u+\cos v)$ has saddle points ($\nabla\varepsilon=0$, indefinite Hessian) at $(u,v)=(\pi,0)$ and $(0,\pi)$, both giving $\varepsilon=0$ — the standard 2D logarithmic van Hove singularity at the band center, exactly derivable from the dispersion above (no external citation needed).

## Oracle script

`python oracle.py --lattice square --t 1.0` → prints `n_bands`, `bandwidth`, `flat_band_energy`, `flat_band_flatness`, `dos_van_hove`, `dirac_point_gap`. Importable: `compute(lattice="square", t=1.0, nk=200)`; `bloch(lattice, U, V, t)` returns the batched Bloch matrix.
Self-test anchors: (1) square `bandwidth == 8.0` to `1e-12`; (2) honeycomb `dirac_point_gap < 1e-12`, evaluated directly at the analytic Dirac point `(u,v)=(2π/3,4π/3)` (not via grid search); (3) kagome flat band at `+2.0` (tol `1e-10`) with `flat_band_flatness < 1e-10`; (4) Lieb flat band at `0.0` to `1e-12`; (5) `flat_band_energy` is `nan` for square/honeycomb (no flat band); (6) `n_bands` = 1/2/3/3.

## Benchmarks

| Quantity | Lattice / params | Exact value | Source |
|---|---|---|---|
| `bandwidth` | square, `t=1` | `8` | derived above |
| `bandwidth` | honeycomb, `t=1` | `6` (`= 2 \times 3t`) | derived above |
| `dirac_point_gap` | honeycomb, at `K` | `0` | derived above |
| `flat_band_energy` | kagome, `t=1` | `2` | [@Bergman2008] |
| `flat_band_energy` | Lieb, `t=1` | `0` | [@Bergman2008] |
| `bandwidth` | Lieb, `t=1` | `4\sqrt2 \approx 5.657` | derived above |

## Verification recipes

- To check an ED/DMRG band-structure run: compare `bandwidth` and (kagome/Lieb) `flat_band_energy` from `oracle.py --lattice <name>`, tolerance `1e-8` (exact diagonalization).
- Flat-band sanity check for any many-body extension (e.g. adding interactions on top of kagome/Lieb): confirm the non-interacting `flat_band_flatness` is at floating-point-roundoff level before attributing any residual dispersion to the interaction.
- Honeycomb Dirac point: evaluate the Bloch matrix directly at `(u,v)=(2π/3,4π/3)` (or any lattice-symmetry-related point) rather than searching a finite grid, to avoid reporting a spurious nonzero gap from grid resolution.

## Key reference

[@Bergman2008] — Bergman, Wu & Balents, "Band touching from real-space topology in frustrated hopping models": the systematic treatment of flat bands from destructive interference on line-graph/corner-sharing lattices (kagome, Lieb among them), source of the compact-localized-eigenstate description used above. Rendered: _(Wave 3)_.
