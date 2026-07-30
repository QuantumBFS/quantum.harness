# Software survey for issue #92

**Question.** Is there a mature programming tool which takes a truncated
Bose--Hubbard Hamiltonian on a hyperbolic lattice and returns the convergent
thermodynamic bulk-gap upper bounds of Xu *et al.*?

**Short answer (28 July 2026): no.** There are mature SDP solvers, mature
modeling layers, a capable hyperbolic-tiling generator, and good finite-system
diagonalization packages. There is also public research code for the new
state-polynomial gap hierarchy. The missing piece is an end-to-end
implementation of that hierarchy for a finite on-site matrix algebra such as
occupation-truncated bosons.

This conclusion follows from reading the package APIs and source, not merely
from failing to find a tutorial. “Mature” below means documented, tested, and
usable by someone other than the original author; it does not mean that the
software can make a rigorous floating-point infeasibility certificate by
itself.

## 1. Tool map

| Layer | Tool | What is usable now | Missing for issue #92 | Assessment |
|---|---|---|---|---|
| Bulk-gap hierarchy | [`SpectralGap.jl`](https://github.com/wangjie212/SpectralGap) 0.3 | Implements the paper's state-polynomial gap matrices, symmetry reductions, and fixed-\(\gamma\) tests | Public API and word reduction are specialized to Pauli Ising and kagome Heisenberg models; Mosek is hard-wired; no boson/matrix-unit backend or user documentation | Closest reference, research prototype |
| State polynomials | [NCTSSOS](https://github.com/wangjie212/NCTSSOS) 0.5 | `statepop` tutorial and moment/SOS machinery for free, projector, and unipotent variables | Its “bosonic” algebra is infinite CCR, not a finite occupation cutoff; the public state interface does not directly encode local matrix units | Useful generator, not an end-to-end answer |
| State polynomials | [NCTSSoS.jl](https://github.com/QuantumSOS/NCTSSoS.jl) 0.1 | Active successor with typed algebras, JuMP/Clarabel, state and trace polynomials, symmetry tools | At the inspected revision, state-polynomial optimization is restricted in source to `MonoidAlgebra`; quotient/PBW finite-matrix algebras are not admitted by that pipeline; Julia 1.12 is required | Promising extension point, experimental API |
| General NC SDP | [ncpol2sdpa](https://github.com/peterwittek/ncpol2sdpa) | Established Python generator for ordinary noncommutative moment relaxations; bosonic examples and multiple solver formats | Does not supply the nonlinear state-symbol lifting or the thermodynamic gap localizer of the 2026 paper | Mature for a different SDP |
| General NC algebra | [NCAlgebra](https://ncalgebra.github.io/) | Rich symbolic noncommutative algebra and SDP-oriented workflows | No ready-made state-polynomial bulk-gap hierarchy or hyperbolic-lattice model | Mature component |
| Symmetry reduction | [SymDPoly](https://denisrosset.github.io/symdpoly/) | Symmetry-adapted noncommutative polynomial optimization | No state-polynomial gap construction or truncated-boson front end | Useful component |
| SDP modeling | [JuMP](https://jump.dev/), [CVXPY](https://www.cvxpy.org/) | Mature ways to assemble custom PSD cones, solve parametrized feasibility problems, and record statuses/statistics | The hierarchy, canonical word algebra, and certificate verification must be implemented by us | Mature infrastructure |
| SDP solver | [Mosek](https://docs.mosek.com/latest/juliaapi/index.html) | Strong commercial conic/SDP solver used by the reference code | License required; floating statuses still need certificate validation | Mature solver |
| SDP solver | [Clarabel](https://clarabel.org/stable/) | Open-source conic solver with PSD cones and Python/Julia interfaces | No exact/rational certificate and no problem generator | Mature solver, good prototype default |
| Hyperbolic geometry | [`hypertiling`](https://git.physik.uni-wuerzburg.de/hypertiling/hypertiling) | Generates regular \(\{p,q\}\) tilings, adjacency and Poincaré-disk coordinates at large scale | Output must be converted to a rooted site graph and then to a line graph where needed | Mature geometry component |
| Finite-system ED | [QuSpin `boson_basis_general`](https://quspin.github.io/QuSpin/generated/quspin.basis.boson_basis_general.html) | Cutoff bosons, number sectors, user-defined graph symmetries, sparse Hamiltonians | Produces finite-patch spectra, not thermodynamic certificates | Mature diagnostic component |

## 2. The important algebra trap

The local Hilbert space after imposing \(n\le n_{\max}\) is
\(M_{n_{\max}+1}(\mathbb C)\). It is **not** the CCR algebra used by most tools
when they advertise bosonic variables:

\[
 [b,b^\dagger]=I-(n_{\max}+1)|n_{\max}\rangle\langle n_{\max}|.
\]

Using an infinite-CCR simplifier and merely adding \(b^{n_{\max}+1}=0\) is not
a harmless approximation; it changes products at the cutoff. A correct backend
must canonicalize matrix units
\(E_{rs}E_{uv}=\delta_{su}E_{rv}\), or use an equivalent complete Hermitian
basis and multiplication table. This is precisely the backend absent from the
public state-polynomial pipelines inspected above.

## 3. What the released bulk-gap code tells us

`SpectralGap.jl` is valuable because it resolves ambiguities in the paper's
pseudocode: it constructs positivity and gap PSD blocks separately, represents
products of state expectations in the lifted support, and solves a sequence of
fixed-\(\gamma\) models. It is not yet a library front end:

- the exported functions name only Ising and kagome Heisenberg models;
- Pauli reduction, mirror reduction, and model-specific charge/sign sectors are
  embedded in the basis construction;
- Mosek is imported directly;
- the current API collapses every termination status other than `OPTIMAL` to a
  zero flag, so robust “unknown versus infeasible” handling must be added before
  using it for certificates;
- tests and user documentation are minimal.

The most direct full implementation is nevertheless to preserve its SDP
assembly logic and replace Pauli word reduction with the exact finite-matrix
canonicalizer described in `ALGORITHM.md`. The more maintainable upstream route
would be to extend NCTSSoS.jl's state-polynomial pipeline to quotient/PBW
algebras and then express the lattice hierarchy on top.

## 4. Slides and tutorials found

No public copy of Jie Wang's 28 July 2026 talk slides was found on his research
page, GitHub repositories, the QuantumBFS organization, or general web search.
That is a statement about the public search result, not evidence that the slides
do not exist. The best substitutes are:

1. Supplementary §2 of [Xu *et al.*](https://arxiv.org/html/2606.03836), which
   gives the full hierarchy and convergence theorem.
2. The short [NCTSSOS state-polynomial
   tutorial](https://wangjie212.github.io/NCTSSOS/dev/state/), which shows the
   software notation for products of expectations.
3. Klep *et al.*, [*State polynomials: positivity, optimization and nonlinear
   Bell inequalities*](https://arxiv.org/abs/2301.12513), for the mathematical
   lifting behind the variance term.
4. [`SpectralGap.jl`](https://github.com/wangjie212/SpectralGap), for an
   executable translation of the new paper in Pauli algebras.

If the morning slides become available, they should be archived alongside this
report and used to check the choices of test basis, stationarity strengthening,
and numerical infeasibility validation. They should not replace the paper as
the source of the certificate direction.

## 5. Recommended research path

The work divides naturally into three levels whose claims must stay separate:

1. **Now:** validate the cutoff algebra, the state-polynomial variance lifting,
   and the atomic exact answer; generate exact finite-patch spectra as a sign and
   scale check.
2. **Next:** implement the full matrix-unit state-polynomial canonicalizer on a
   rooted radius-one window, preserving `FEASIBLE`, `INFEASIBLE`, and
   `UNKNOWN` as distinct outcomes.
3. **Research scale:** add rooted graph automorphisms, \(U(1)\) blocks,
   term/correlative sparsity, nested \((L,d)\), and independently checked dual
   infeasibility certificates.

Thus the answer is encouraging but specific: mature building blocks exist;
the scientifically interesting programming contribution is exactly the missing
finite-matrix state-polynomial backend and its certificate-verification layer.
