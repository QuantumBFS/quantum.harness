# Baseline Reproduction Plan

Status: **reviewed pilot/baseline plan; production blocked**.

## Reference target

The target is Blöte and Deng, Physical Review E 66, 066110 (2002):

| Lattice | Reference \(h_c/J\) | Quoted uncertainty | Reported final-fit cutoffs |
|---|---:|---:|---:|
| triangular | 4.76811 | 0.00009 | \(L_{\min}=6,\ L_{\max}=20\) |
| honeycomb | 2.13250 | 0.00004 | \(L_{\min}=10,\ L_{\max}=20\) |

The paper reports only these minimum and maximum sizes, not the complete
size roster. A later reproduction must therefore label its explicit roster
as our operational convention rather than claiming that every listed size
was used in the 2002 calculation.

The paper uses Pauli operators, \(J=1\), periodic boundaries, the Binder ratio

\[
Q_L=\frac{\langle m^2\rangle^2}{\langle m^4\rangle},
\]

and a continuous imaginary-time physical length \(M_p=\beta h=L\).
Therefore the direct baseline aspect ratio is \(\beta=L/h\), not an
unrecorded generic “large beta”.

Here \(m\) is the magnetization density of the full continuous classical
system. The literal reproduction observable is therefore the
space--imaginary-time estimator `spacetime_binder_q`. The same-chain
`equal_time_binder_q` is retained as a diagnostic but cannot substitute for
the reproduction observable and does not count as an independent QMC route.

## Reproduction stages

### B0: independent lattice and ED oracle

Implement a small-system Hamiltonian independently from the QMC lattice code.
The ED program must construct the full Pauli Hamiltonian directly from a
separately serialized edge list and compute finite-temperature energy,
\(\langle m^2\rangle\), \(\langle m^4\rangle\), and \(Q\).

Required fixtures:

- triangular periodic clusters with at least \(N=9\) and one additional
  non-square fundamental cell;
- honeycomb periodic clusters with at least \(N=8\) and \(N=12\);
- zero-field spectra against analytically enumerable classical energies;
- \(J=0\) spectra and energy against independent spins in a transverse field;
- exact \(\beta=0\) moments;
- graph degree, bond count, connectivity, translation, and edge-multiplicity
  checks.

Each QMC route must agree with ED at at least three off-critical
\((J,h,\beta)\) points and two near-critical points per lattice. For every
reported observable, the ED value must lie inside a two-sided 99% Monte Carlo
confidence interval. The seven-observable family—energy, equal-time
\(m^2,m^4,Q\), and spacetime \(m^2,m^4,Q\)—is controlled with a Holm
correction separately for each frozen validation campaign. Any failure blocks
the baseline. Attempt 008 is only an estimator-integration pilot and does not
meet this B0 point roster or Holm gate.

### B1: algorithmic smoke tests

For each lattice and at least four independent seeds:

- demonstrate thermalization using running means and first-half/second-half
  comparisons;
- estimate integrated autocorrelation time for \(m^2\), \(m^4\), energy, and
  the operator-string length;
- show that increasing discarded sweeps and beta does not create a significant
  shift;
- verify that bin size is at least \(10\tau_{\rm int}\);
- verify reproducible results from the recorded commit, manifest, and command.

These are pilot results and cannot enter a verdict.

### B2: literal 2002-style reproduction

Use the reported size cutoffs, \(\beta=L/h\), \(Q_L\), and the paper's scaling
form:

\[
Q_L(h)=Q^\star+a_1x+a_2x^2+a_3x^3+b_1L^{y_i}
       +b_2L^{y_2}+c_1xL^{y_i}+\cdots ,
\qquad x=(h-h_c)L^{1/\nu}.
\]

First fit with the historical fixed exponents
\(y_t=1/\nu=1.587(2)\) and \(y_i=-0.815(4)\). Table I reports different
nonzero term rosters for the two lattices:

- honeycomb primary: \(a_1,a_2,a_3,b_1\);
- triangular primary: \(a_1,a_2,a_3,b_1,b_2\), with
  \(y_2=d-2y_h\).

Although Eq. (23) defines the mixed \(c_1\) term, Table I does not report it
for either final fit. It is therefore a predeclared sensitivity term, not
part of the literal honeycomb primary model. The triangular \(b_2\) term
is now source-bound to the historical \(y_h=2.4815(15)\) estimate of Blöte,
Luijten & Heringa (1995), so \(y_2=3-2y_h=-1.9630(30)\). Attempt-014 fixes
the central exponent at `-1.9630` and records the external uncertainty for a
separate sensitivity; it is not inferred from the critical-field target.
Repeat the primary fits with the modern 3D-Ising values
\(\nu=0.629971(4)\) and \(\omega=0.82968(23)\) as a separately labelled
sensitivity check. A \(L^{-2\omega}\) term is allowed only in a separately
labelled modern sensitivity model.

Baseline sampling windows may be widened from the paper's central values
after low-statistics crossings, but may not be narrowed by reference to
\(\sqrt5\).

### B3: reproduction acceptance

Both lattices must satisfy all of the following:

1. \(|\hat h_c-h_{c,2002}|\) is no larger than the paper's quoted
   one-standard-deviation uncertainty.
2. The reproduction's total uncertainty is no larger than the corresponding
   quoted uncertainty.
3. The reference value is compatible at \(z\le2\) using the quadratic sum of
   the reproduction and reference uncertainties.
4. The primary fit has at least four degrees of freedom, bootstrap coverage
   tests pass on synthetic data, and goodness-of-fit \(p\ge0.05\).
5. Removing any one lattice size does not move \(h_c\) by more than twice the
   reproduction's total uncertainty.
6. The ED, beta, seed, autocorrelation, and thermalization gates pass.

Approximate values such as `4.77` and `2.13` fail this gate.

## Improvement campaign after B3

Only after B3 passes:

- extend \(L_{\max}\) and increase independent replicas;
- add \(\xi_L/L\) as a second dimensionless observable if its estimator has
  passed ED/synthetic checks;
- tune compute allocation to reduce uncertainty per scheduler-hour, never to
  shift the central value;
- test \(\beta\) multipliers, \(L_{\min}\), \(L_{\max}\), crossing windows,
  correction terms, and seed subsets declared in the preregistration;
- require an independent continuous-time or independently maintained QMC
  implementation to pass B0/B1 before the production verdict.

## Worktree sequence

No experimental worktree is opened until this plan and the validator are
reviewed. Proposed branches:

1. `exp/ed-oracle`
2. `exp/sse-baseline`
3. `exp/ctqmc-independent`
4. `exp/fss-pipeline`
5. `exp/production-freeze`

Each starts from a clean reviewed commit, lives under `.worktrees/`, and has
an `experiments/<id>/LOG.md` copied from the template. Merge only accepted,
reviewed infrastructure into `main`; retain rejected branches and logs long
enough to preserve the scientific record.
