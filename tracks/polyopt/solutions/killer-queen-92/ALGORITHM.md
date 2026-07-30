# Algorithm note: certified bulk-gap upper bounds

**Scope.** This note explains the algorithm requested in
[Quantum Harness issue #92](https://github.com/QuantumBFS/quantum.harness/issues/92).
It is not the usual moment-SDP lower bound on a finite Hamiltonian's ground-state
energy. It is a feasibility hierarchy for excluding a hypothesized gap of an
infinite lattice directly in the thermodynamic limit.

The primary source is Xu *et al.*, [*The bulk spectral gap is semi-decidable: a
convergent family of certified upper bounds*](https://arxiv.org/html/2606.03836),
especially Supplementary §2. The authors' proof-of-principle Julia code is
[`wangjie212/SpectralGap`](https://github.com/wangjie212/SpectralGap). A public
copy of Jie Wang's 28 July 2026 talk slides was not found in searches of his
website, GitHub, or the QuantumBFS repository as of 28 July 2026. The closest
short software tutorial found is the
[NCTSSOS state-polynomial example](https://wangjie212.github.io/NCTSSOS/dev/state/).

## 1. The distinction that matters

An ordinary noncommutative ground-energy relaxation has the schematic form

\[
  \min_{\mathcal L}\;\mathcal L(H),\qquad
  \mathcal L(1)=1,\qquad M_d(\mathcal L)\succeq0.
\]

Every physical state supplies feasible moments, so the minimum is a **lower
bound** on the ground-state energy of the problem being modeled. This is a
linear optimization over moments.

The bulk-gap algorithm asks a different question:

> For a fixed number \(\gamma\geq0\), can there exist an infinite-volume KMS
> ground state whose locally non-degenerate bulk gap is at least \(\gamma\)?

At each finite relaxation level \((L,d)\), the answer is relaxed to an SDP
feasibility test. If that relaxation is **infeasible**, the hypothesized state
cannot exist, so \(\gamma\) is rigorously excluded. Define

\[
  \Gamma_{L,d}=\sup\{\gamma:\text{the level-}(L,d)\text{ relaxation is feasible}\}.
\]

Increasing the local window \(L\) or polynomial degree \(d\) adds necessary
conditions. Hence the feasible sets shrink and

\[
  \Gamma_{L,d}\searrow\Delta_{\mathrm{bulk}}.
\]

For a fixed \(\gamma\), minimizing and maximizing a local observable over the
same relaxation gives outer bounds which tighten monotonically. This is the
content of [Theorem 2.5](https://arxiv.org/html/2606.03836#S2.SS2.SSS0.Px1) of
the paper.

## 2. Why the construction is already in the thermodynamic limit

Let \(\mathcal A_{\mathrm{loc}}\) be the algebra of operators with finite support
on the infinite graph. The formal sum \(H=\sum_X h_X\) is not itself a bounded
local operator, but for every local excitation \(a\),

\[
  [H,a]=\sum_{X:X\cap\operatorname{supp}(a)\ne\varnothing}[h_X,a]
\]

is a finite, well-defined sum. A state \(\omega\) is a KMS ground state when no
local excitation lowers its energy:

\[
  \omega\!\left(a^\dagger[H,a]\right)\geq0
  \quad\text{for all }a\in\mathcal A_{\mathrm{loc}}.
\]

The state has a locally non-degenerate bulk gap at least \(\gamma\) when

\[
  \omega\!\left(a^\dagger[H,a]\right)
  \geq \gamma\left(\omega(a^\dagger a)-|\omega(a)|^2\right)
  \quad\text{for every local }a. \tag{1}
\]

The left side is the excitation energy. The right side is \(\gamma\) times the
squared component of \(a|\Omega_\omega\rangle\) orthogonal to the ground-state
vector in the GNS representation.

The finite region \(\Lambda(L)\) is therefore a **local test window**, not a
finite sample whose spectrum is extrapolated. No boundary condition is chosen.
For nearest-neighbor interactions, the tested excitations must lie at least one
graph layer inside the Hamiltonian window: use \(a\) supported on
\(\Lambda(L-1)\) while the commutator is evaluated with \(H^{\Lambda(L)}\).
This buffer makes the commutator identical to the infinite-lattice derivation.

This is the logical reason that finite-level infeasibility implies a
thermodynamic-limit statement. Open-boundary exact diagonalization does not
have that implication and will be used in this project only as a baseline.

## 3. Why an ordinary moment matrix is insufficient

Equation (1) contains \(|\omega(a)|^2\). The map \(\omega\mapsto|\omega(a)|^2\)
is nonlinear, and the set of states satisfying the assumed-gap condition is in
general nonconvex. Merely adding (1) to an ordinary NPA/moment relaxation does
not give an SDP.

State-polynomial optimization resolves this by introducing a commuting formal
symbol \(\varsigma(w)\) for every operator word \(w\). It represents
\(\omega(w)\), while products such as
\(\varsigma(a^\dagger)\varsigma(a)\) are now ordinary commutative monomials.
A second linear functional \(\mathcal L\) acts on these state polynomials.
Nonlinear expressions in \(\omega\) therefore become linear entries in lifted
pseudo-moments of \(\mathcal L\).

For state-polynomial monomials \(s,t\) of degree at most \(d\), the positivity
moment matrix is

\[
  [M_d(\mathcal L)]_{s,t}
  =\mathcal L\!\left(\varsigma(s^\dagger t)\right). \tag{2}
\]

The assumed-gap localizing matrix is

\[
\begin{aligned}
  [M^{\mathrm{gap},\gamma}(\mathcal L)]_{s,t}
  =\mathcal L\!\Big[&\tfrac12\varsigma\!\left(
  s^\dagger[H^{\Lambda(L)},t]
  -[H^{\Lambda(L)},s^\dagger]t\right)\\
  &-\gamma\big(\varsigma(s^\dagger t)
  -\varsigma(s^\dagger)\varsigma(t)\big)\Big]. \tag{3}
\end{aligned}
\]

The symmetrization makes the matrix Hermitian. At a **fixed** \(\gamma\), every
entry in (2) and (3) is affine in the lifted pseudo-moments, so the constraints
are SDPs. Treating \(\gamma\) as a simultaneous decision variable would create
bilinear products; in practice one solves a sequence of fixed-\(\gamma\)
feasibility problems, normally by bisection.

The complete level-\((L,d)\) test is

\[
\begin{array}{ll}
\text{find} & \mathcal L\\
\text{such that}
 & \mathcal L(1)=1,\\
 & M_d(\mathcal L)\succeq0,\\
 & \mathcal L\!\left(\varsigma([H^{\Lambda(L)},w])\right)=0
   \quad\text{for all allowed interior }w,\\
 & M^{\mathrm{gap},\gamma}(\mathcal L)\succeq0.
\end{array} \tag{4}
\]

The stationarity equations are essential. Positivity plus the gap localizer at
\(\gamma=0\) expresses the KMS ground-state condition; for \(\gamma>0\), the
gap localizer imposes the stronger energy-to-variance ratio.

## 4. Completeness and the direction of the certificate

Every genuine infinite-volume state with bulk gap at least \(\gamma\) restricts
to a feasible point at every \((L,d)\). Therefore:

- **feasible** at one finite level means only “not excluded yet”;
- **infeasible** at one finite level excludes that \(\gamma\);
- maximizing the last feasible \(\gamma\) gives an **upper**, not lower, gap
  bound;
- increasing \(L,d\) can only improve the upper bound downward.

Conversely, if every level remains feasible, compactness and an Archimedean
state-polynomial representation theorem construct an infinite-volume KMS state
obeying (1). This yields convergence, not merely a collection of necessary
tests. The finite-dimensional local matrix algebras are crucial: their
generators are bounded, which supplies the Archimedean bounds used in the
proof.

## 5. Correct algebra for occupation-truncated bosons

For cutoff \(n_{\max}\), one site is the matrix algebra
\(M_D(\mathbb C)\), \(D=n_{\max}+1\). With matrix units
\(E_{rs}=|r\rangle\langle s|\),

\[
  b=\sum_{r=1}^{n_{\max}}\sqrt r\,E_{r-1,r},\qquad
  b^\dagger=\sum_{r=0}^{n_{\max}-1}\sqrt{r+1}\,E_{r+1,r},\qquad
  n=\sum_{r=0}^{n_{\max}}rE_{rr}. \tag{5}
\]

The local multiplication and adjoint rules are exact:

\[
  E_{rs}E_{uv}=\delta_{su}E_{rv},\qquad
  E_{rs}^\dagger=E_{sr},\qquad
  \sum_rE_{rr}=I. \tag{6}
\]

Operators on distinct sites commute. A particularly important boundary
identity is

\[
  [b,b^\dagger]=I-D\,E_{n_{\max},n_{\max}}, \tag{7}
\]

not the infinite-dimensional canonical commutation relation
\([b,b^\dagger]=I\). Consequently, selecting a package's built-in “bosonic/CCR”
algebra would model the wrong problem. The safe implementation choices are:

1. canonicalize words with the finite matrix-unit rules (6); or
2. use a complete Hermitian basis of \(M_D(\mathbb C)\) and its multiplication
   table.

The second choice also lowers the apparent Hamiltonian degree. In a local
matrix basis, on-site terms are linear and edge hopping terms are degree two;
leaving \(n(n-1)\) as a raw word in \(b,b^\dagger\) makes it look degree four
and needlessly enlarges the relaxation.

For the issue's Bose–Hubbard model,

\[
  H=-t\sum_{\langle i,j\rangle}(b_i^\dagger b_j+b_j^\dagger b_i)
  +\frac12\sum_i n_i(n_i-1)-\mu\sum_i n_i, \tag{8}
\]

the three graphs have coordination \(z=3\) for \(\{8,3\}\) and \(z=4\) for
\(\{12,4\}\) and the line graph \(L(G_{8,3})\).

## 6. Symmetry: useful, but it changes the quantified state set

The Hamiltonian is invariant under global \(U(1)\) particle-number rotations.
Words carry charge “number of creations minus annihilations.” Imposing an
invariant state sets nonzero-charge moments to zero and block-diagonalizes the
moment matrices by charge. This can be a large reduction.

It must be reported as a **symmetry-restricted certificate**. The result then
excludes a gap only among \(U(1)\)-invariant KMS ground states; it is not an
unrestricted statement if spontaneous symmetry breaking is allowed. We will
keep unrestricted and symmetry-restricted results separate.

Graph automorphisms fixing the reference site can likewise identify moment
orbits without changing the physical question when they are used as an exact
block decomposition. Requiring the state itself to be invariant is a stronger
assumption and must be labeled.

## 7. Concrete algorithm for issue #92

For a graph \(G\), cutoff \(n_{\max}\), and relaxation level \((L,d)\):

1. Build the rooted ball \(\Lambda(L)\) and its induced edges. For a
   nearest-neighbor Hamiltonian reserve the outer shell as a commutator buffer.
2. Construct the finite local algebra using (6), then assemble
   \(H^{\Lambda(L)}\) from (8).
3. Enumerate a selected basis of operator and state-polynomial monomials up to
   total degree \(d\), canonicalizing after every multiplication.
4. Optionally orbit-reduce by rooted graph symmetry and block by \(U(1)\)
   charge; record whether this restricts the state.
5. Create one scalar SDP variable for every independent lifted pseudo-moment.
6. Assemble normalization, the positivity matrix (2), stationarity equations,
   and the gap matrix (3).
7. At fixed \(\gamma\), solve (4). Check primal/dual residuals and the minimum
   eigenvalues of returned PSD blocks.
8. Bracket and bisect \(\gamma\). An infeasibility certificate above the final
   feasible endpoint gives \(\Gamma_{L,d}\).
9. At fixed feasible \(\gamma\), minimize and maximize
   \(\rho_0=\omega(n_0)\),
   \(F_0=\omega((n_0-1)^2)\), and
   \(K_0=z^{-1}\sum_{j\sim0}\omega(b_0^\dagger b_j+b_j^\dagger b_0)\)
   over the same SDP.
10. Repeat in nested \(L,d\). Gap upper bounds must move downward, observable
    lower bounds upward, and observable upper bounds downward.

Pseudocode:

```text
for geometry, cutoff, (t, mu), symmetry_mode:
    algebra = truncated_matrix_algebra(cutoff)
    for (L, d) in nested_relaxations:
        patch = rooted_ball(geometry, L, buffer=1)
        model = bose_hubbard(patch, algebra, U=1, t=t, mu=mu)
        sdp_template = state_polynomial_relaxation(model, d, symmetry_mode)

        lo, hi = bracket_gap(sdp_template)
        while hi - lo > gamma_tolerance:
            gamma = (lo + hi) / 2
            status, certificate = solve_feasibility(sdp_template, gamma)
            if reliably_feasible(status): lo = gamma
            elif reliably_infeasible(status, certificate): hi = gamma
            else: mark_unresolved_and_stop()

        report Gamma_Ld in [lo, hi]
        for gamma in selected_assumed_gaps_below_hi:
            optimize rho0, F0, K0 in both directions
```

## 8. Validation ladder before claiming new lattice results

1. **Algebra tests.** Verify (5)–(7) exactly for every cutoff and verify
   different sites commute.
2. **Atomic limit.** At \(t=0,U=1,\mu=0.5\), recover
   \(\Delta_{\mathrm{bulk}}=0.5\), \(\rho_0=1\), \(F_0=K_0=0\) for
   \(n_{\max}\ge2\). The result must not depend on the graph.
3. **Reference implementation.** Reproduce one small transverse-field Ising
   value from the released `SpectralGap.jl` code before trusting an algebra
   extension.
4. **Tiny finite-patch cross-check.** Use exact diagonalization only to catch
   signs, factors, and observable definitions. Do not call its gap a bulk
   certificate.
5. **Nestedness.** Check the mathematically required monotonic directions in
   \(L,d\).
6. **Numerical certificate.** A floating-point status string alone is not a
   rigorous proof. Preserve residuals and a dual ray/certificate; use verified
   or rational post-processing for final claims.

The paper itself notes that its reported numerical SDPs used floating-point
arithmetic without accounting for numerical errors. Thus “certified” describes
the mathematical implication of exact SDP infeasibility; a machine-checkable
numerical certificate requires an additional verification step.

## 9. Software conclusion before implementation

- `SpectralGap.jl` implements this specific hierarchy and is therefore the
  closest reference, but its public API is specialized to Pauli Ising and
  Heisenberg examples and uses JuMP with Mosek. It is research code, not a
  general truncated-boson package.
- NCTSSOS and its successor NCTSSoS.jl support state-polynomial optimization,
  but their built-in bosonic algebra is CCR. They are useful SDP generators only
  if the finite matrix algebra is encoded correctly.
- ncpol2sdpa, NCAlgebra, and generic CVXPY/JuMP tools can represent ordinary
  noncommutative or custom SDPs, but none supplies issue #92's complete
  thermodynamic bulk-gap construction as a ready-made function.
- `hypertiling` is a suitable mature graph generator for the regular
  \(\{p,q\}\) tilings; its output still needs rooted-ball canonicalization and
  the line-graph transformation.

The practical research route is therefore to preserve the paper's
state-polynomial hierarchy and replace only its Pauli word algebra with an
exact finite-matrix-algebra backend. Finite-patch diagonalization is a valuable
independent baseline, not a substitute for that work.

## Sources

1. X. Xu *et al.*, [bulk-gap paper and Supplementary
   Information](https://arxiv.org/html/2606.03836), 2026.
2. I. Klep *et al.*, [*State polynomials: positivity, optimization and nonlinear
   Bell inequalities*](https://arxiv.org/abs/2301.12513), *Mathematical
   Programming* 2024.
3. J. Wang, [`SpectralGap.jl` reference code](https://github.com/wangjie212/SpectralGap).
4. NCTSSOS, [state-polynomial optimization
   tutorial](https://wangjie212.github.io/NCTSSOS/dev/state/).
5. NCTSSoS.jl, [current package repository](https://github.com/QuantumSOS/NCTSSoS.jl).
6. M. Schrauth *et al.*, [`hypertiling` paper](https://arxiv.org/abs/2309.10844)
   and [package](https://pypi.org/project/hypertiling/).
