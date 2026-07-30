# Higher-dimensional fermions: what this VMC calculation does and does not solve

Lei Wang's question on Quantum Harness PR #262 separates two issues that are
easy to conflate: the sign or phase problem of a path-integral measure, and the
statistical and optimization cost of a direct variational wave-function
calculation.  This repository addresses the second problem.  It does not turn
generic higher-dimensional fermionic path-integral Monte Carlo into a
sign-free method.

## Generic path-integral sign and phase problems

For indistinguishable fermions in two or more spatial dimensions, particle
exchanges generally give positive and negative path-integral contributions.
Sampling the absolute weight and restoring the sign by reweighting introduces
an average sign of the form

\[
\langle s\rangle_{|w|}=\frac{Z_F}{Z_{|w|}}
\sim e^{-\beta V\Delta f}.
\]

The signal can therefore decrease exponentially with inverse temperature and
system volume.  The generic fermion sign problem is NP-hard
([Troyer and Wiese, 2005](https://doi.org/10.1103/PhysRevLett.94.170201),
BibTeX key `TroyerWiese2005`).  Restricted-path or fixed-node constructions
replace cancellation by an assumed nodal constraint
([Ceperley, 1991](https://doi.org/10.1007/BF01030009),
`Ceperley1991Nodes`).  In a magnetic field the many-body wave function and
weights can be complex, so the corresponding difficulty is a phase problem;
the fixed-phase method imposes an approximate phase constraint
([Ortiz, Ceperley, and Martin, 1993](https://doi.org/10.1103/PhysRevLett.71.2777),
`OrtizCeperleyMartin1993`).

Special Hamiltonians, symmetries, bases, and algorithms can be sign-free, but
the one-dimensional short-range result does not extend generically to
higher-dimensional fermions.  In particular, this repository makes no claim
that the fractional-quantum-Hall Hamiltonian is sign- or phase-problem free in
path-integral Monte Carlo.

## What the repository samples

The implementation is a direct complex wave-function variational Monte Carlo
(VMC) calculation.  Fermionic exchange antisymmetry and the magnetic phase are
encoded in the ansatz itself.  Configurations are sampled from

\[
p_\theta(R)=\frac{|\Psi_\theta(R)|^2}{Z_\theta}\ge 0,
\qquad
Z_\theta=\int dR\,|\Psi_\theta(R)|^2,
\]

and observables are evaluated through local estimators such as

\[
E_{\rm loc}(R)=\frac{H\Psi_\theta(R)}{\Psi_\theta(R)}.
\]

This is the standard direct-wave-function VMC structure used by neural
fermionic ansätze; see
[Pfau *et al.*, 2020](https://doi.org/10.1103/PhysRevResearch.2.033429)
(`Pfau2020FermiNet`).  Because the sampling density is nonnegative, this
variational estimator does not divide by an exponentially small path-integral
average sign.  That precise statement is narrower than saying that the method
"solves the fermion sign problem."

## Where the difficulty can reappear

The hard part can be relocated rather than removed.  The checks relevant to
this calculation are:

- whether the ansatz can express the correct nodal and complex phase
  structure;
- whether stochastic optimization is stable and reaches the same state from
  independent seeds;
- whether local-energy or bridge-weight variance grows with particle number;
- whether Markov-chain autocorrelation time grows;
- whether raw, autocorrelation-adjusted, and bridge effective sample sizes
  collapse;
- whether wall time or memory per effective independent sample grows rapidly;
- whether rare configurations near wave-function zeros dominate an
  estimator.

Neural sign structure can remain difficult even when samples are drawn from a
positive distribution
([Szabó and Castelnovo, 2020](https://doi.org/10.1103/PhysRevResearch.2.033075),
`SzaboCastelnovo2020`).  Consequently, the repository treats variance,
autocorrelation, effective sample size (ESS), seed-to-seed dispersion, failure
counts, memory, and wall time as part of the scientific result rather than as
mere performance metadata.

Wall time and memory are nevertheless hardware-dependent.  The checked
records combine local `N=4,8` anchors with XH5 `N=10,12` production chains, so
the report preserves those resource diagnostics but does not use a
cross-platform wall-time ratio to decide whether sampling collapses.  The
tested-size decision uses completion, ESS, bridge ESS, autocorrelation, and
variance.  It makes no hardware-normalized or asymptotic complexity claim.

## Evidence status and allowed conclusion

The separate compute task owns the `N=10,12` cluster deployment and raw
per-chain outputs.  This response task does not edit its Slurm scripts, remote
runtime, job state, or result selection.  When those records arrive, every
submitted seed—including failed, timed-out, rejected, and non-equilibrated
runs—will enter the versioned scaling report.

Until that report passes validation, the higher-dimensional scaling question
is **unresolved**.  If the completed records show controlled completion,
variance, autocorrelation, and ESS fractions over the tested sizes, the
strongest authorized statement will be:

> No exponential sampling collapse is resolved over the tested sizes.

That finite-range observation would not prove polynomial asymptotic cost,
measure a path-integral average sign, or solve the generic fermion sign
problem.  If diagnostics deteriorate or coverage is insufficient, the report
will say so directly.
