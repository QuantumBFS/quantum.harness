# Level specification for the issue #92 hierarchy

This document fixes the meaning of every finite relaxation used by the
issue-92 code.  It follows Definition 2.4 of Xu *et al.*, *The bulk spectral
gap is semi-decidable* (arXiv:2606.03836v1), specialized to the
occupation-truncated Bose--Hubbard algebra.  A result may be labelled by
`(L,d)` only if it uses these sets, or if a separately labelled sparse
`basis_family` is an explicit principal-submatrix relaxation of them.

## 1. Graph window, interior, and Hamiltonian

Let `G=(V,E)` be one of the three infinite, locally finite graphs in issue
#92, let `0` be its distinguished root, and let `dist_G` be graph distance.
For every integer `L >= 1`,

\[
  \Lambda_G(L)=\{v\in V:\operatorname{dist}_G(v,0)\le L\}.
\]

The interaction range is one edge, so the interaction length is `l=1`.  The
sites allowed in stationarity and bulk-gap excitations are the exact interior

\[
  \Lambda_G(L-l)=\Lambda_G(L-1).
\]

The finite operator used inside commutators is the induced Hamiltonian

\[
H^{\Lambda_G(L)}=
-t\!\sum_{\{i,j\}\in E:\,i,j\in\Lambda_G(L)}
 (b_i^\dagger b_j+b_j^\dagger b_i)
+\sum_{i\in\Lambda_G(L)}
 \left[\frac U2 n_i(n_i-1)-\mu n_i\right].
\]

There are no boundary fields and no edges from the window to its complement.
This is not an open finite-volume model: if an excitation is supported in
`Lambda_G(L-1)`, every nearest-neighbour interaction that can fail to commute
with it lies wholly in `Lambda_G(L)`.  Therefore its commutator with the
displayed Hamiltonian equals the infinite-volume derivation.

An input graph is acceptable only if shortest-path distances through radius
`L` and all edges induced by those vertices are known.  Code must reject a
smaller patch instead of silently treating its boundary as physical.

## 2. Exact cutoff algebra and degrees

At cutoff `nmax`, put `D=nmax+1`.  The local algebra is `M_D(C)` and uses the
independent, charge-adapted basis

\[
 \mathbf 1,\quad E_{rr}\ (1\le r\le n_{\max}),\quad
 E_{rs}\ (0\le r,s\le n_{\max},\ r\ne s).
\]

`E_00` is eliminated exactly as
`E_00 = 1 - sum(r=1:nmax, E_rr)`.  Multiplication and adjoint are performed
before any numerical conversion:

\[
 E_{rs}E_{uv}=\delta_{su}E_{rv},\qquad E_{rs}^*=E_{sr}.
\]

Coefficients are stored in `Q(sqrt(2),sqrt(3))`, which contains all ladder
matrix elements through `nmax=3`.  The `U(1)` charge of `E_rs` is `r-s`.

Two generator-dependent degree conventions are implemented.

1. `matrix`: every nonidentity element of the independent basis above has
   degree one.  Tensor-product degrees add.  The declared Hamiltonian degree
   is `deg(H)=2`.
2. `ladder`: local filtration degrees are derived by exact graded row
   reduction of all words in `b,bdag`, separately in each charge sector.
   The resulting independent coordinate directions are exact linear
   combinations of matrix units; positive-charge directions are paired with
   their adjoints and neutral directions are self-adjoint.  Prefixes through
   degree `k` span exactly the ladder-word filtration through degree `k`, and
   tensor-product degrees add.  All products are converted back through the
   same exact matrix-unit engine.  For the hierarchy offsets, the Hamiltonian
   retains its declared Bose--Hubbard
   generator degree: `deg(H)=2` at `nmax=1` and `deg(H)=4` at
   `nmax>=2`, because the interaction is represented by
   `(bdag)^2 b^2/2`.  Exact cutoff identities may put an individual matrix
   element in a lower filtration space; they do not change this conservative
   declared degree.

The matrix encoding is primary.  Ladder results are labelled as a generator
dependence cross-check and are never merged with matrix-degree tables.

## 3. Canonical state-polynomial sets

For a region `R`, let `B_A(R,k)` be the complete independent tensor-product
operator basis of degree at most `k`.  A canonical operator word contains at
most one nonidentity matrix-basis element at each site, sorted by site.

For every nonidentity `w in B_A(R,k)`, `varsigma(w)` is a commuting formal
state symbol of degree `deg(w)`.  A pure state monomial is a sorted multiset
of these symbols.  A noncommutative state monomial is

\[
  s=\prod_j\varsigma(w_j)\,u,
\]

where `u` is one canonical operator word and
`sum_j deg(w_j)+deg(u) <= k`.  Their complete set is denoted
`B_S(R,k)`.  Exact matrix multiplication, linearity of `varsigma`,
`varsigma(1)=1`, commutativity of state symbols, and adjoint identify all
duplicates during canonicalization; hence the quotient-algebra ideal is
enforced structurally rather than by redundant floating equalities.

For `U1_INVARIANT_KMS_STATES`, state symbols with nonzero charge vanish and
are removed.  Remaining noncommutative monomials are grouped by total charge.
Moment and gap PSD matrices have one exact block per charge.  The optional
`UNRESTRICTED_KMS_STATES` comparison retains every state symbol and uses the
standard real embedding of complex Hermitian PSD matrices.

## 4. Definition 2.4 index sets

Let `h=deg(H)` for the chosen encoding.  A level is admissible when `2d>=h`
and the requested observable belongs to the degree-`2d` operator space.
The exact sets are:

| object | complete index/test set |
|---|---|
| moment PSD | `s,t in B_S(Lambda_G(L), d)` |
| moment entries | `L(varsigma(s* t))` |
| normalization | `L(1)=1` |
| stationarity | `L(varsigma([H^Lambda,w]))=0` for every `w in B_S(Lambda_G(L-1), 2d-h)` |
| gap PSD | `s,t in B_S(Lambda_G(L-1), d-ceil(h/2))` |
| gap entries | the expression below |

The gap entry is

\[
\mathcal L\!\left[
\frac12\varsigma\!\left(s^*[H^\Lambda,t]-[H^\Lambda,s^*]t\right)
-\gamma\left(\varsigma(s^*t)-\varsigma(s^*)\varsigma(t)\right)
\right].
\]

The covariance term is therefore part of the complete gap matrix.  A
separately reported covariance principal block is a diagnostic, not an extra
definition of the level.

Objectives use the same feasible set:

\[
\rho_0=\varsigma(n_0),\qquad
F_0=\varsigma((n_0-1)^2),\qquad
K_0=\frac1z\sum_{j\sim0}\varsigma(b_0^\dagger b_j+b_j^\dagger b_0).
\]

## 5. Complete and term-sparse families

`COMPLETE` means every monomial in the sets above is present.  `TS2` is a
practical sparse relaxation.  Within each exact charge block it starts from
the support graph induced by diagonal moments, the Hamiltonian, stationarity,
and requested objective supports; performs deterministic chordal completion;
adds every entry support inside the resulting cliques; and repeats this
support closure twice.  Edges from the seed and first iteration are retained
in the second iteration.  Thus `TS2` is deterministic and contains its lower
term-sparsity levels.  It is not called a complete Definition 2.4 level.

## 6. Production levels

The matrix-degree campaign uses:

| cutoff | family and `(L,d)` |
|---:|---|
| 1 | `COMPLETE`: `(1,2)`, `(2,2)`, `(1,3)` |
| 2 | `COMPLETE`: `(1,2)`; `TS2`: `(2,2)`, `(1,3)` |
| 3 | optional `COMPLETE`: `(1,2)`, only if dry-run memory is at most 225 GB and estimated wall time at most 6 hours |

The first two useful ladder cross-check degrees are `(d=2,3)` for `nmax=1`
and `(d=3,4)` for `nmax=2,3`; the first admissible degree with an
identity-only gap index is not used as a headline comparison.

The three primary complete hard-core levels are partially ordered rather than
linearly ordered: `(1,2)` embeds into both `(2,2)` and `(1,3)`.  Tightening in
`L` and in `d` is plotted separately.

## 7. Result semantics

Only `FEASIBLE`, `EXCLUDED`, and `UNKNOWN` are scientific classifications.
`EXCLUDED` requires an independently checked dual Farkas certificate.
Floating solver infeasibility without a passing checker is `UNKNOWN` with
certificate class `FLOATING_CANDIDATE`.  Feasibility never proves a positive
gap.  All primary statements are restricted to
`U1_INVARIANT_KMS_STATES`; finite-cluster ED remains diagnostic only.

Observable optima first require checked primal feasibility, dual
stationarity, dual PSD, and primal/dual agreement.  Selected headline bounds
also preserve an exact projected dual identity.  Such a certificate is
reported separately as `VERIFIED_LOWER_BOUND` or `VERIFIED_UPPER_BOUND`; it is
never interpreted as an exclusion.  When a floating optimum lies on a
singular cone face, the exact endpoint is allowed a small conservative
backoff and is the value reported as certified.
