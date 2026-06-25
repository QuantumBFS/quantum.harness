# Hofstadter model (Harper / butterfly)

Square-lattice tight-binding electrons in a uniform perpendicular magnetic field with rational flux per plaquette `α = p/q` — the Harper/Hofstadter equation. The single-particle spectrum is the self-similar fractal **Hofstadter butterfly**; at flux `p/q` the band splits into `q` subbands, and each spectral gap carries an integer **Chern number** via the TKNN / Diophantine equation — the integer quantum Hall effect realized on a lattice.

## Physics card

### Hamiltonian

$$ H = -t \sum_{\langle ij\rangle} e^{i\theta_{ij}}\, c^\dagger_i c_j + \text{h.c.}, \qquad \sum_{\square} \theta_{ij} = 2\pi\alpha,\quad \alpha = \frac{p}{q} $$

Conventions: spinless fermions on a 2D square lattice; `t > 0` nearest-neighbor hopping (energy unit `t = 1`); the Peierls phases `θ_{ij}` encode a uniform perpendicular magnetic field, with the total phase around each plaquette equal to `2πα` (flux per plaquette in units of the flux quantum `h/e`). In the Landau gauge `θ` depends only on one coordinate, reducing the 2D problem to the 1D **Harper equation** with a magnetic unit cell of `q` sites. Rational `α = p/q` (coprime `p, q`) makes the spectrum periodic and tractable; irrational `α` gives a Cantor-set spectrum. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 2D square lattice; **magnetic unit cell of `q` sites** at flux `p/q` (`Z = 4`) | The enlarged magnetic cell (→ `q` subbands) is the defining structure; reduces to the 1D Harper equation in Landau gauge. |
| A2 boundary conditions | torus / PBC (magnetic Brillouin zone, Chern/TKNN labels) · cylinder / strip (chiral edge modes in the gaps) | The magnetic BZ requires magnetic translation operators; a strip exposes the IQHE edge modes. |
| A3 statistics & local dim | spinless fermion; `d = 2` per site; **quadratic** (single-particle) | Single orbital per site; the spectrum is a single-particle band problem (Slater-determinant many-body state). |
| A4 interaction range | short-range: nearest-neighbor hopping with Peierls phases | Local; no interactions (Hofstadter–Hubbard is the interacting extension). |
| B5 entanglement scaling | 2D area law (gapped, when the Fermi level sits in a gap); filled-subband ground states carry nonzero Chern numbers | Free-fermion ground state; topology lives in the gap labels, not a local order parameter. |
| B6 spectral gap | self-similar fractal of gaps and `q` subbands (the butterfly); gapped whenever `E_F` sits in a butterfly gap, gap closings on subband touchings | The fractal gap structure as a function of `α` is the signature; each gap is robust where it is open. |
| B7 ground-state order | topological bands labeled by **Chern numbers** (integer quantum Hall on a lattice, class **A**) | Each filled set of subbands has a total Chern number `C`; the Hall conductance is `σ_xy = C e²/h`. No symmetry breaking — purely band-topological. |
| B8 frustration | none (free fermions) | — |
| C9 global symmetry | charge U(1); **magnetic translation symmetry** (a projective / ray representation — the two magnetic translations commute only up to a phase) | Ordinary translation is broken by the gauge field; the magnetic translation group is the residual symmetry and forces the `q`-site magnetic cell. Time-reversal is broken by the field. |
| C10 spatial symmetry | magnetic translations (`Z_q`-enlarged unit cell → magnetic BZ); point-group symmetry reduced by the field | Magnetic translations replace ordinary translations; the magnetic BZ is `1/q` of the original. |
| C11 integrability | **free-fermion / quadratic → exactly solvable** via the Harper equation (a `q×q` Bloch matrix per magnetic crystal momentum), `O(N³)` | Diagonalizing the `q×q` Harper matrix over the magnetic BZ gives the full butterfly and the Chern labels. |
| C12 sign problem | N/A — free fermions, no Monte Carlo required (Hofstadter–Hubbard / interacting extensions become sign-ful, magnetic-flux sign problem) | The magnetic field is itself a generic source of the QMC sign problem in interacting variants. |
| D13 regime | ground state (`T = 0`) default; spectrum/transport are the targets; dynamics exactly tractable (quadratic) | The butterfly and the gap Chern labels are computed once and for all. |
| D14 filling / doping | gaps open at fillings set by the **Diophantine equation** `r = q\, s + p\, C` (TKNN; `C` = gap Chern number, `s` integer); the Hall plateau sits at each such commensurate filling | Filling selects which butterfly gap (and hence which Chern number `C`) determines `σ_xy`. |
| D15 disorder | clean by default; disorder broadens subbands into Landau-like bands with localized states between the (topologically protected) extended levels — the mechanism of IQHE plateaus | Disorder is what makes the experimental quantum Hall plateaus flat; the Chern number is robust. |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- Integer quantum Hall states (one per butterfly gap) : labeled by the total Chern number `C` of the filled subbands; quantized Hall conductance `σ_xy = C e²/h`; chiral edge modes in a strip geometry. Diagnose by the TKNN integers from the Diophantine equation and the strip edge spectrum.
- The Hofstadter butterfly itself : the spectrum vs `α ∈ [0,1]`, a self-similar fractal; at `α = p/q` the band splits into exactly `q` subbands.

### Canonical observables

- Single-particle spectrum vs flux `α` — the Hofstadter butterfly.
- Number of subbands (`= q` at `α = p/q`) and the butterfly gap structure.
- Chern number `C` of each gap (TKNN / Diophantine equation); Hall conductance `σ_xy = C e²/h`.
- Strip edge-state spectrum (chiral, gap-traversing).

### Recommended methods

- Primary: **exact single-particle diagonalization of the Harper equation** — the `q×q` magnetic-Bloch matrix over the magnetic BZ gives the spectrum, subbands, and Chern labels in `O(q³)` per `k`; a strip diagonalization gives the edge modes. Free-fermion / quadratic, per `method-property-map.md` C11 row.
- Cross-check: **ED** on a small torus with magnetic flux quanta for the many-body Chern number; the TKNN / Diophantine equation gives the gap Chern numbers analytically as an independent check.

### Key reference

[@hofstadter_1976_energy] — Hofstadter, "Energy levels and wave functions of Bloch electrons in rational and irrational magnetic fields", Phys. Rev. B **14**, 2239 (1976): the defining paper that derives the Harper equation, the `q`-subband structure at rational flux, and the self-similar butterfly spectrum. The TKNN topological labeling (Thouless, Kohmoto, Nightingale, den Nijs, Phys. Rev. Lett. **49**, 405 (1982)) supplies the Chern-number / Hall-conductance interpretation. _bib stub — original PRB predates arXiv, no PDF reachable._
Rendered: _(none — bib stub; see `INDEX.md`)_.

### Benchmarks

- Subband count: at flux `α = p/q` (coprime) the spectrum splits into exactly `q` subbands separated by `q − 1` gaps (Hofstadter 1976) [@hofstadter_1976_energy].
- Self-similar butterfly: the spectrum as a function of `α ∈ [0,1]` is a fractal with the same structure recurring at all scales (Hofstadter 1976).
- Gap Chern numbers: each gap carries an integer `C` solving the Diophantine equation `r = q\, s + C\, p` with `|C| ≤ q/2` (TKNN 1982); the Hall conductance at that filling is `σ_xy = C e²/h`.

## How it is studied

The Hofstadter model is not run as a variational / sampling compute target — it is a **single-particle (free-fermion) problem solved by direct diagonalization**, and serves as the canonical anchor for lattice band topology in a magnetic field.

- **Harper equation.** In Landau gauge the 2D problem decouples into a 1D difference equation, the Harper equation, with a magnetic unit cell of `q` sites at flux `α = p/q`. Diagonalizing the resulting `q × q` magnetic-Bloch Hamiltonian over the magnetic Brillouin zone yields the full spectrum at that flux. Sweeping `α` over the rationals traces out the spectrum.
- **The Hofstadter butterfly.** Plotting the allowed energies against `α ∈ [0,1]` produces the self-similar fractal "butterfly": at `α = p/q` the original band fragments into `q` subbands, and the gap pattern recurs at every scale (a Cantor set for irrational `α`). This is the iconic result of the 1976 paper.
- **Chern / TKNN labels.** Each gap of the butterfly is topologically nontrivial: integrating the Berry curvature over the magnetic BZ for the filled subbands gives an integer Chern number, equivalently the solution `C` of the Diophantine equation `r = q s + C p` (Thouless–Kohmoto–Nightingale–den Nijs, 1982). The Hall conductance when the Fermi level lies in that gap is `σ_xy = C e²/h` — the integer quantum Hall effect on a lattice. In a strip geometry the same integer counts the chiral edge modes crossing the gap (bulk–boundary correspondence).

When the Hofstadter model appears inside a calculation it is usually as (i) the lattice realization of Landau levels / the IQHE, (ii) a calibration target for Chern-number and edge-mode diagnostics, or (iii) the non-interacting backbone of the Hofstadter–Hubbard problem (interactions + flux → a generic QMC sign problem, studied with DMRG/ED/VMC). The interacting, fractionally-filled version is the lattice route to the fractional quantum Hall effect.
