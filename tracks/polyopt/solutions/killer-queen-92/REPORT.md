# Research report: bulk-gap SDP for truncated bosons on hyperbolic lattices

**Date:** 29 July 2026
**Target:** [Quantum Harness issue #92](https://github.com/QuantumBFS/quantum.harness/issues/92)
**Model convention:**
\[
H=-t\sum_{\langle i,j\rangle}(b_i^\dagger b_j+b_j^\dagger b_i)
 +\frac{1}{2}\sum_i n_i(n_i-1)-\mu\sum_i n_i,
\qquad n_i\le n_{\max}.
\]

> **Campaign update.** The Julia core now implements the complete
> Definition-2.4 matrix hierarchy, exact charge-adapted ladder filtration,
> deterministic `TS2`, cached JuMP/Clarabel/Mosek workspaces, resumable
> bisection/objectives, and exact-projected dual checking.  Its complete-level
> atomic check passed on SCNet, including the exact conservative observable
> interval `rho0` in `[986498/986499, 5806375/5806374]`.  The first complete
> lattice Clarabel driver pilot remained `UNKNOWN`: `gamma=0` was feasible but
> `gamma=1` ended in a numerical error, so `[0,1]` was not moved.  The older
> root-local and finite-ED numbers
> summarized below remain diagnostics: no non-atomic Target-2 endpoint has yet
> been accepted, and production plus the pinned Ising reference remain blocked
> on a valid Mosek license.  [`status.md`](status.md) is the authoritative live
> campaign record.

## Executive conclusion

There is no mature end-to-end tool which presently takes this cutoff
Bose--Hubbard model and returns the convergent thermodynamic bulk-gap upper
bounds of Xu *et al.* Mature components do exist. `hypertiling` generates the
graphs, CVXPY/JuMP and Clarabel/Mosek model and solve SDPs, and QuSpin or a small
number-sector code handles finite exact diagonalization. Jie Wang's
`SpectralGap.jl` is the closest implementation of the new hierarchy, but it is
specialized to Pauli Ising and Heisenberg examples. The missing reusable part is
a state-polynomial backend for a finite on-site matrix algebra.

This project supplies that first backend in a small, transparent form and
establishes three results:

1. The exact truncated algebra, graph construction, state lifting, and atomic
   benchmark are working. The atomic SDP gives
   \(0.5000000000\le\Gamma<0.5000009537\) for
   \(n_{\max}=1,2,3\), agreeing with the exact gap \(0.5\).
2. A genuine radius-one thermodynamic outer SDP is implemented. It has the
   correct certificate direction and distinguishes \(z=3\) from \(z=4\), but
   it is weak and numerically ill-conditioned at \(n_{\max}=3\). At
   \((t,\mu)=(0.06,0.5)\), the hard-core model is feasible at \(\gamma=0.5\);
   the first clean floating-point infeasibility occurs at \(0.6\) for
   \(\{8,3\}\), and at \(0.8\) for the two \(z=4\) windows. These are numerical
   upper-bound candidates, not machine-verified certificates.
3. Exact radius-one patch spectra were obtained for both requested scans and
   all cutoffs. They are useful sign/cutoff diagnostics and show the expected
   stronger suppression of the finite-patch gap at higher coordination and on
   the triangular line-graph window. They are not thermodynamic results.

Thus issue #92 is not completely solved by this first relaxation. What is now
complete is the algorithmic survey, a tested minimal implementation, all
requested small parameter scans, and a precise map of the remaining research
work.

## 1. What is being certified

For a local excitation \(a\), an infinite-volume KMS ground state with locally
non-degenerate bulk gap at least \(\gamma\) obeys

\[
 \omega(a^\dagger[H,a])\ge
 \gamma\bigl(\omega(a^\dagger a)-|\omega(a)|^2\bigr). \tag{1}
\]

The finite region is a test window, not a sample with an open boundary. For a
nearest-neighbor Hamiltonian, all terms meeting the support of \(a\) are kept,
so the commutator is exactly the infinite-lattice commutator. Products such as
\(|\omega(a)|^2\) are lifted to state-polynomial moments. At fixed \(\gamma\),
the resulting positivity, stationarity, covariance, and gap constraints are
affine SDPs.

Every genuine infinite-volume state with gap at least \(\gamma\) supplies a
feasible point. Therefore exact infeasibility excludes \(\gamma\), and the last
feasible \(\gamma\) is an **upper** bound on the bulk gap. A feasible finite
relaxation only means “not excluded.” It is not a gap lower bound. The complete
nested hierarchy and its convergence proof are described in
[`ALGORITHM.md`](ALGORITHM.md) and in [Xu *et
al.*](https://arxiv.org/html/2606.03836).

All thermodynamic SDPs in this prototype impose a \(U(1)\)-invariant state.
Their conclusions are therefore explicitly **symmetry restricted**.

## 2. Lattices and why local thermodynamic tests matter here

A regular \(\{p,q\}\) tiling has \(p\)-gonal faces and \(q\) faces at every
vertex, so the site coordination is \(z=q\). The two parent graphs are

| graph | coordination | girth | exact radius-one sites/edges |
|---|---:|---:|---:|
| \(\{8,3\}\) | 3 | 8 | 4 / 3 |
| \(\{12,4\}\) | 4 | 12 | 5 / 4 |
| \(L(\{8,3\})\) | 4 | 3 locally | 5 / 6 |

The line graph replaces each parent edge by a vertex and joins two new vertices
when their parent edges share an endpoint. A cubic parent therefore gives
degree \(2(3-1)=4\), and each root edge lies in two local triangles. Line-graph
lattices are known to support flat bands and compact localized states, although
which side of the hopping spectrum is physically low depends on the sign
convention [Kollár *et al.*](https://arxiv.org/abs/1902.02794).

The genuine graph generator uses the cell-adjacency graph of the dual tiling
\(\{q,p\}\), which is combinatorially the site graph of \(\{p,q\}\). The
generated rooted-ball counts are

| radius | \(\{8,3\}\) | \(\{12,4\}\) | \(L(\{8,3\})\) |
|---:|---:|---:|---:|
| 1 | 4 | 5 | 5 |
| 2 | 10 | 17 | 13 |
| 3 | 22 | 53 | 29 |

At radius three the outer shell already contains 12/22, 36/53, and 16/29 of
the sites, respectively. Open balls are consequently dominated by boundary
sites at these sizes. This is why the local-commutator SDP is much better
matched to the question than extrapolating open-ball spectra.

Prior mean-field/QMC work on hyperbolic Bose--Hubbard models found that Mott
lobes shrink as \(q\) increases, attributing it to the increased kinetic energy
from higher coordination [Zhu *et al.*](https://arxiv.org/abs/2103.15274). The
small finite-patch ordering below is qualitatively consistent with that trend,
but is not an independent thermodynamic phase-boundary calculation.

## 3. Implementation and claim boundaries

### 3.1 Exact cutoff algebra

The code represents the one-site algebra with matrix units
\(E_{rs}=|r\rangle\langle s|\):

\[
E_{rs}E_{uv}=\delta_{su}E_{rv},\qquad E_{rs}^\dagger=E_{sr}.
\]

It verifies

\[
[b,b^\dagger]=I-(n_{\max}+1)E_{n_{\max},n_{\max}},
\]

with infinity-norm residuals \(0\), \(4.44\times10^{-16}\), and
\(8.88\times10^{-16}\) for cutoffs 1, 2, and 3. This avoids the most dangerous
software error: using an infinite CCR algebra for a cutoff Hilbert space.

### 3.2 Atomic state-polynomial SDP

For a \(U(1)\)-invariant atomic state, \(p_r=\omega(E_{rr})\). A lifted matrix
\(P\) represents products \(p_rp_s\). The model includes

\[
\begin{bmatrix}1&p^T\\p&P\end{bmatrix}\succeq0,
\quad P\mathbf1=p,
\quad \gamma(P-\operatorname{diag}p)\succeq0,
\]

and the charged excitation inequalities

\[
p_s(e_r-e_s-\gamma)\ge0\quad(r\ne s).
\]

This is a genuine state-polynomial SDP, not an energy minimization. The charged
constraints make it exact for the unique atomic ground state.

### 3.3 Rooted radius-one thermodynamic SDP

The first lattice relaxation uses:

- root-supported matrix-unit excitations;
- the complete root on-site term and all incident hopping terms, hence the
  exact infinite-lattice commutator for those excitations;
- an operator moment matrix indexed by identity and all one-site matrix units
  in the root-plus-neighbor window;
- exact adjoint, multiplication, and \(U(1)\) charge rules;
- local normalization and root stationarity;
- a lifted state-symbol moment matrix;
- a separate covariance PSD block;
- the fixed-\(\gamma\) gap PSD block.

Any infinite \(U(1)\)-invariant state obeying (1) maps into this feasible set,
so exact infeasibility has the desired thermodynamic implication. Constraints
from higher operator/state-polynomial degrees are omitted, making it a weak
outer relaxation rather than a named complete \((L,d)\) level.

At radius one, \(\{12,4\}\) and \(L(\{8,3\})\) give identical SDPs: root
excitations only see four incident edges. Their different neighbor-neighbor and
loop structure first appears at a larger excitation window. This is a known
level limitation, not an accidental graph identification.

### 3.4 Finite-patch ED

The baseline enumerates bounded occupations in each conserved total-number
sector and diagonalizes the exact truncated Hamiltonian. Its CSV marks every
row `FINITE_OPEN_PATCH_NOT_THERMODYNAMIC_CERTIFICATE`. The largest full Hilbert
space is 1024 and the largest number block is 155.

## 4. Numerical validation

Eight unit tests cover cutoff commutators/nilpotency, radius-one graph
combinatorics, `hypertiling` agreement, hopping sign and Hermiticity, atomic ED,
the atomic SDP threshold, and the rooted thermodynamic atomic threshold. All
pass.

At \(t=0,U=1,\mu=0.5\), both SDP formulations and ED recover

\[
\Delta=0.5,\qquad \rho_0=1,\qquad F_0=0,\qquad K_0=0
\]

for all three cutoffs. The atomic bisection result is

| \(n_{\max}\) | last feasible | first infeasible | width |
|---:|---:|---:|---:|
| 1 | 0.5000000000 | 0.5000009537 | \(9.54\times10^{-7}\) |
| 2 | 0.5000000000 | 0.5000009537 | \(9.54\times10^{-7}\) |
| 3 | 0.5000000000 | 0.5000009537 | \(9.54\times10^{-7}\) |

Atomic normalization residuals are below \(4\times10^{-11}\). The smallest
returned atomic PSD eigenvalues are of order \(10^{-9}\), consistent with a
singular exact solution plus floating error.

## 5. Thermodynamic rooted-SDP results

### 5.1 Requested fixed-\(\gamma\) grid

The full two parameter scans at \(\gamma=0,0.05,0.10\), three geometries, and
three cutoffs comprise 135 models:

| cutoff | clean `optimal` | `optimal_inaccurate` | `UNKNOWN`/solver error |
|---:|---:|---:|---:|
| 1 | 33 | 12 | 0 |
| 2 | 17 | 22 | 6 |
| 3 | 7 | 20 | 18 |

No usable row is infeasible at these three assumed gaps. The conclusion is only
that \(\gamma\le0.10\) is not excluded by this weak root level. Two
\(n_{\max}=3,z=4,\gamma=0.1\) `optimal_inaccurate` rows have an operator-moment
minimum eigenvalue \(-3.73\times10^{-6}\); they should be treated as unresolved,
not feasible. The other returned PSD violations are at or below the small
floating tolerances recorded in the CSV.

### 5.2 Coarse upper-bound probes at \(t=0.06,\mu=0.5\)

For \(n_{\max}=1\), all three windows are feasible at \(\gamma=0.5\). The first
clean solver infeasibility on the predefined grid is

| geometry | last sampled feasible | first clean sampled infeasible | floating candidate |
|---|---:|---:|---:|
| \(\{8,3\}\) | 0.5 | 0.6 | \(\Delta_{U(1)}<0.6\) |
| \(\{12,4\}\) | 0.5 | 0.8 | \(\Delta_{U(1)}<0.8\) |
| \(L(\{8,3\})\) | 0.5 | 0.8 | \(\Delta_{U(1)}<0.8\) |

The two \(z=4\) models return `infeasible_inaccurate` already at 0.6, but this
is not used as the clean endpoint. For \(n_{\max}=2,3\), the grid contains
`solver_error` and `infeasible_inaccurate` near the transition and no dependable
clean bracket. A better-conditioned block formulation and dual-certificate
verification are required before publishing those gap bounds.

Even the “clean” endpoints in this table are only floating-point solver
statuses. The exact SDP implication is rigorous; the computed infeasibility is
not machine-verified yet.

### 5.3 Local observable outer bounds

At \((t,\mu,\gamma)=(0.06,0.5,0.1)\), the hard-core root relaxation gives the
following floating outer intervals:

| geometry | \(\rho_0\) | \(F_0\) | \(K_0\) |
|---|---:|---:|---:|
| \(\{8,3\}\) | [0.9550, 1.0000] | [0, 0.0450] | [0, 0.3000] |
| \(\{12,4\}\) | [0.9200, 1.0000] | [0, 0.0800] | [0, 0.4000] |
| \(L(\{8,3\})\) | [0.9200, 1.0000] | [0, 0.0800] | [0, 0.4000] |

Some \(\{8,3\}\) endpoints have `optimal_inaccurate` status; all \(z=4\)
hard-core endpoints returned `optimal`. The \(n_{\max}=2\) bounds are much
looser—for example \(\rho_0\in[0.9392,1.1611]\) on \(\{8,3\}\)—and several
endpoints are inaccurate. No \(n_{\max}=3\) objective interval is reported.

## 6. Exact finite-patch diagnostic results

For \(n_{\max}=3\), the exact open radius-one gaps on the fixed-\(\mu=0.5\)
scan are

| \(t\) | \(\{8,3\}\) | \(\{12,4\}\) | \(L(\{8,3\})\) |
|---:|---:|---:|---:|
| 0.03 | 0.399100 | 0.383430 | 0.347447 |
| 0.05 | 0.335728 | 0.310382 | 0.250538 |
| 0.06 | 0.305373 | 0.275531 | 0.204805 |

At fixed \(t=0.03\),

| \(\mu\) | \(\{8,3\}\) | \(\{12,4\}\) | \(L(\{8,3\})\) |
|---:|---:|---:|---:|
| 0.15 | 0.103434 | 0.096235 | 0.077882 |
| 0.50 | 0.399100 | 0.383430 | 0.347447 |
| 0.75 | 0.149100 | 0.133430 | 0.097447 |

The ground sector remains unit filling (4 particles on \(\{8,3\}\), 5 on the
other windows) throughout these scans. At \(t=0.06,\mu=0.5,n_{\max}=3\), the
root observables are

| geometry | \(\rho_0\) | \(F_0\) | \(K_0\) |
|---|---:|---:|---:|
| \(\{8,3\}\) | 1.001618 | 0.041482 | 0.476196 |
| \(\{12,4\}\) | 1.003230 | 0.055389 | 0.481283 |
| \(L(\{8,3\})\) | 1.003777 | 0.073857 | 0.603063 |

Across all non-atomic scan points, changing the cutoff from 2 to 3 changes the
finite-patch gap by at most 0.01939 (mean 0.00640), \(\rho_0\) by at most
0.00199, \(F_0\) by at most 0.00377, and \(K_0\) by at most 0.02072. The
hard-core cutoff is qualitatively different at unit filling: hopping is blocked
in the filled ground state, so \(F_0=K_0=0\).

These trends are physically sensible, but every value in this section has an
open-boundary spectrum interpretation only.

## 7. Performance and software findings

- The 54 ED rows take 1.72 seconds of measured diagonalization time in total;
  the slowest row takes 0.184 seconds.
- The 120 atomic SDP rows take 0.081 seconds of solver time in total.
- The first rooted models have operator PSD blocks up to 81, state blocks up to
  5, and CVXPY reports up to 336 scalar decision variables before cone
  canonicalization.
- Rooted-model wall time is dominated by rebuilding/canonicalizing CVXPY
  expression graphs, while solver errors concentrate in the five-site,
  \(n_{\max}=3\) models.
- Clarabel is adequate for the atomic and hard-core prototypes but not a final
  certificate pipeline at the larger cutoff.

The detailed package assessment is in [`SURVEY.md`](SURVEY.md). The key answer
is “mature pieces, no mature end-to-end tool.” The current NCTSSoS.jl state
pipeline is promising but, at the inspected revision, accepts monoid algebras
rather than the quotient/PBW finite matrix algebra needed here. The public
`SpectralGap.jl` code already implements the correct gap construction for Pauli
words and is the best reference for a production reimplementation.

No public copy of Jie Wang's 28 July 2026 slides was found on his site, GitHub,
the QuantumBFS organization, or general web search. The closest tutorial is the
[NCTSSOS state-polynomial
example](https://wangjie212.github.io/NCTSSOS/dev/state/), supplemented by the
paper's Supplementary §2.

## 8. What is needed for a complete issue #92 result

The next work should proceed in this order:

1. Remove exact linear dependencies from matrix units and explicitly block the
   operator, covariance, and gap matrices by \(U(1)\) charge. This targets the
   observed \(n_{\max}=3\) conditioning problem.
2. Cache a parameterized SDP template so scans change only
   \((t,\mu,\gamma)\), rather than rebuilding symbolic expressions.
3. Reproduce one Ising result from `SpectralGap.jl`, then compare the two SDP
   assemblers term by term.
4. Add the complete state-polynomial monomial hierarchy, not just the present
   necessary subset, and label nested levels unambiguously.
5. Enlarge the excitation window to radius two. This is the first level that
   can distinguish \(\{12,4\}\) from the line graph through loop structure.
6. Orbit-reduce by rooted graph automorphisms and add term/correlative
   sparsity. Report unrestricted and \(U(1)\)-restricted models separately.
7. Preserve solver dual rays and verify infeasibility with interval or rational
   post-processing. Until this is done, use “floating-point upper-bound
   candidate,” not “computer-certified bound.”
8. Repeat the full cutoff/parameter scan and demonstrate the required monotone
   movement with window and polynomial degree.

## 9. Reproducibility artifacts

Run from this directory:

```bash
make setup
make test
make study
make rooted-study
make rooted-issue-scan
```

Raw outputs are intentionally git-ignored but are present locally:

- [`results/atomic_sdp_runs.csv`](results/atomic_sdp_runs.csv)
- [`results/atomic_gap_brackets.csv`](results/atomic_gap_brackets.csv)
- [`results/rooted_thermodynamic_sdp.csv`](results/rooted_thermodynamic_sdp.csv)
- [`results/rooted_issue_fixed_gamma_scan.csv`](results/rooted_issue_fixed_gamma_scan.csv)
- [`results/finite_patch_ed.csv`](results/finite_patch_ed.csv)
- [`results/graph_scaling.csv`](results/graph_scaling.csv)
- [`results/metadata.json`](results/metadata.json)
- [finite-patch gap versus \(t\)](.figures/finite_patch_gap_vs_t.pdf)
- [finite-patch gap versus \(\mu\)](.figures/finite_patch_gap_vs_mu.pdf)

The environment used Python 3.12.3, CVXPY 1.9.2, Clarabel 0.11.1,
`hypertiling` 1.5.1, NetworkX 3.6.1, NumPy 2.5.1, and SciPy 1.18.0.

## Sources

1. X. Xu *et al.*, [*The bulk spectral gap is semi-decidable: a convergent
   family of certified upper bounds*](https://arxiv.org/html/2606.03836), 2026.
2. I. Klep *et al.*, [*State polynomials: positivity, optimization and nonlinear
   Bell inequalities*](https://arxiv.org/abs/2301.12513), 2024.
3. J. Wang, [`SpectralGap.jl`](https://github.com/wangjie212/SpectralGap) and
   [NCTSSOS state tutorial](https://wangjie212.github.io/NCTSSOS/dev/state/).
4. X. Zhu *et al.*, [*Quantum phase transitions of interacting bosons on
   hyperbolic lattices*](https://arxiv.org/abs/2103.15274), 2021.
5. A. J. Kollár *et al.*, [*Line-Graph Lattices: Euclidean and Non-Euclidean
   Flat Bands*](https://arxiv.org/abs/1902.02794), 2019.
6. M. Schrauth *et al.*, [`hypertiling`](https://arxiv.org/abs/2309.10844), 2023.
