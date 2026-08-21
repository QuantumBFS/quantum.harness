# Challenge 148 Frozen Production Protocol

Protocol identifier: `c148-prereg-v1+rev1+rev2+rev3+rev4+rev5+rev6+rev7`.

This is the clean-checkout copy of the preregistration and seven append-only
clarifications. Pilot evidence may select final sizes and sampling budgets, but
may not change the Hamiltonian, primary estimator, fit family, uncertainty
rules, blinding rule, or verdict gate without a new protocol identifier.

## Physical convention

$$
H=-J\sum_{\langle i,j\rangle}\sigma_i^z\sigma_j^z
  -h\sum_i\sigma_i^x,
\qquad J=1.
$$

This is Pauli-matrix normalization, periodic boundaries, and no longitudinal
field. Triangular has $N=L^2$, $N_b=3N$, geometry `triangular-v1`. Honeycomb
has a two-site basis, $N=2L^2$, $N_b=3N/2$, geometry `honeycomb-v2`.

Blote-Deng's continuous-time condition is

$$
\beta h=c_\tau L.
$$

The primary run fixes $c_\tau=1$ and selected doubled checks use $c_\tau=2$.
Every raw row records enough metadata to verify this identity.

## Estimators and statistics

The primary estimator is

$$
Q_L=\frac{\langle\bar m^2\rangle^2}{\langle\bar m^4\rangle},
\qquad
\bar m=\frac{1}{\beta}\int_0^\beta m(\tau)\,d\tau.
$$

The mandatory secondary estimator is equal-time $\xi_L/L$ from
$S(0)/S(q_{\min})$, averaged over all symmetry-related shortest torus momenta.
Nonlinear quantities and fitted fields are rebuilt inside a chain-plus-
circular-block bootstrap with block length
$\lceil2\max\tau_{\mathrm{int}}\rceil$. Failed fits are counted.

Every production point contains at least two hot and two cold independently
seeded chains. Gates cover start agreement, additional-prefix discard, bin
growth, autocorrelation, effective sample size, chain spread, and the
$c_\tau=1$ versus $c_\tau=2$ shift.

Protocol Revision 3 freezes the sampling-test calibration before any corrected
triangular or honeycomb data were generated. Hot/cold agreement and first-half
versus second-half stationarity are tested on blocks of length
$\lceil2\max\tau_{\rm int}\rceil$. Each chain must contain at least eight such
blocks. The maximum standardized difference over the five raw observables must
not exceed 5.0. This family-wise threshold replaces the unregistered pilot
implementation's per-comparison 3.5 cutoff, which produced the expected false
flags when maximized over roughly two thousand square-calibration comparisons.

Protocol Revision 4 freezes the remaining sampling diagnostics before any
doubled-$c_\tau$ or larger-size Stage 5 data are generated. Reblocking uses the
Revision 3 base block and twice that block; the maximum raw-observable mean
difference must be at most 5.0 standard errors and every standard-error ratio
must lie in $[1/2,2]$. The maximum single-chain versus all-other-chains raw-
observable difference must be at most 5.0 standard errors. Registered
additional-prefix refits discard 10% and 20% of every measured chain, and each
$h_c$ shift must be at most 5.0 combined standard errors. These checks use all
five stored raw observables and failures remain explicit.

The direct $c_\tau=1$ versus $c_\tau=2$ comparison requires both dimensionless
observables and the fitted critical field to be reported on the common grid.
Protocol Revision 5 corrects Revision 4's pointwise-invariance requirement
after the first doubled-$c_\tau$ pilot exposed its false premise. $Q_L$ uses a
full imaginary-time average and both dimensionless observables are finite-size
scaling functions of the space-time aspect ratio, so changing $c_\tau$ is
expected to change their point values. Pointwise standardized shifts remain
diagnostics but are not pass/fail gates. The invariant is the extrapolated
transition location. Its two-sided 95% upper bound
$|\Delta h_c|+1.96\sigma_{\Delta h_c}$ must not exceed one quarter of the
total target uncertainty: $4.5\times10^{-6}$ for triangular and
$2.0\times10^{-6}$ for honeycomb. A fitted comparison may be statistically
consistent but unresolved; unresolved is a failed final systematic gate.

Protocol Revision 6 freezes the independent-route normalization before any
ParaToric thermodynamic-limit scan. The route uses ParaToric v1.0.3 at commit
`e7bc78446ba083aeeae1ada9c883fa03bf205890`, with the external build-only
compatibility diff SHA-256
`3bd7a5231c38f048035f13f23bb20162b6f6e1f2264270dbeb61e2ce35073d30`.
In the $x$ basis with $\lambda=0$, the target TFIM maps to

$$
h_{\rm eTC}=J_{\rm TFIM}=1,\qquad
J_{\rm eTC}=h_{\rm TFIM},\qquad \mu=64.
$$

The target triangular lattice uses ParaToric's honeycomb gauge lattice; the
target honeycomb lattice uses its triangular gauge lattice. ParaToric's
periodic trace is compared to the full finite-volume TFIM thermal trace. The
even spin-flip sector remains a reported diagnostic, not the comparison
oracle. This ensemble choice was fixed by the nondegenerate square $L=3$
comparison before target-lattice production.

Qualification compares the exchange and transverse-field energies to ED. Its
QMC uncertainty is the maximum of base-block, doubled-block, and independent-
chain standard errors; the ED budget is $10^{-10}$ and agreement requires a
difference no larger than five combined standard errors. Every sampled
$A_v$ must remain $+1$. The analytic full-edge-flip acceptance bound
$\exp[-\beta(4\mu-2)]$ is recorded. ParaToric triangular $L=2$ has degenerate
periodic plaquette incidence and is not a honeycomb-target oracle; the first
independent honeycomb scan must therefore use $L\ge4$. These qualification
checks do not satisfy the independent thermodynamic-limit verdict gate.

Protocol Revision 7 freezes the ParaToric critical-observable scan before any
such data are generated. ParaToric is run in the $x$ basis with
$h_{\rm eTC}=1$, $J_{\rm eTC}=g$, and $\beta=L/g$, where $g$ is the target
TFIM field. This is the energy-rescaled form of the paper convention
$J_{\rm eTC}=1$, $h_{\rm eTC}=1/g$, and $\beta=L$.

The independent primary observable is ParaToric's binary periodic winding
projector $\Pi$ under the package name `percolation_probability`. Its
dimensionless statistic is

$$
U_\Pi=\frac{\langle\Pi^4\rangle}{\langle\Pi^2\rangle^2}.
$$

This is ParaToric's Binder convention, which is inverse to the registered
direct-SSE convention and must not be compared to the direct $Q^*$. The
supporting observable is `staggered_imaginary_times`, analyzed through the
same $U_O=\langle O^4\rangle/\langle O^2\rangle^2$ convention. Package-level
summary statistics are diagnostics only; accepted estimates are rebuilt from
the stored raw series.

The frozen ParaToric grids are:

| Target TFIM | Gauge lattice | $L$ | Target-field values $g$ | Registered $L_{\min}$ |
|---|---|---|---|---|
| Triangular | Honeycomb | 8, 12, 16, 20, 24, 32 | 4.740 to 4.800 inclusive by 0.005 | 8, 12, 16 |
| Honeycomb | Triangular | 10, 12, 16, 20, 24, 32 | 2.110 to 2.150 inclusive by 0.005 | 10, 12, 16 |

Every production point contains four independently seeded chains, each with
$500L^3$ thermalization updates, 30,000 stored samples, and $8L^3$ updates
between samples. Seeds are nonzero and unique across the complete grid. A
bounded cost pilot may use fewer stored samples, but its data cannot enter a
critical fit and cannot change the axes or production cadence.

Acceptance requires no ParaToric warning, every stored $A_v=+1$, at least
eight circular blocks per chain at block length
$\lceil2\max\tau_{\rm int}\rceil$, and at least 1,000 effective samples per
chain for both critical observables. First-half versus second-half,
base-versus-doubled-block, and single-chain-versus-other-chain differences
must be at most five combined standard errors; doubled/base standard-error
ratios must lie in $[1/2,2]$. Fits after discarding an additional 10% and 20%
of every chain must shift by at most five combined standard errors. Each size
must contain at least two field points with pooled
$0.05<\langle\Pi\rangle<0.95$.

The primary joint fit applies the frozen scaling family below to $U_\Pi$.
The supporting SIT fit uses the same family. Both use 2,000 chain-plus-
circular-block bootstrap resamples; more than 1% failed resamples, rank loss,
a condition number above $10^{12}$, or $\chi^2/{\rm dof}>3$ fails the fit.
The registered variants omit the mixed term, take
$\omega\in\{0.80,0.83,0.86\}$, and apply every listed $L_{\min}$. The total
uncertainty is

$$
\sigma_{\rm ind}=\sqrt{\sigma_{\rm bootstrap}^2+\Delta_{\rm variant}^2},
$$

where $\Delta_{\rm variant}$ is the largest absolute registered-variant shift.
Adjacent-size crossing drift with exponent $1/\nu+\omega$ is reported as a
secondary diagnostic and is not averaged with the joint fit.

The independent route is accepted separately for each target lattice only if
the $U_\Pi$ and SIT fields agree within three combined total uncertainties,
the primary total uncertainty is at most $1.8\times10^{-5}$ for triangular or
$8.0\times10^{-6}$ for honeycomb, and the primary field agrees with the
separately frozen direct-SSE field within three combined total uncertainties.
No triangular-to-honeycomb ratio is evaluated during these checks.

## Frozen fit family

$$
Q_L(h)=Q^*+a_1\delta hL^{1/\nu}+a_2\delta h^2L^{2/\nu}
+b_1L^{-\omega}+c_1\delta hL^{1/\nu-\omega},
$$

where $\delta h=h-h_c$, $\nu=0.629971$, and $\omega=0.83$. Registered
variants omit the mixed term, use $\omega\in\{0.80,0.83,0.86\}$, vary
$L_{\min}$, and repeat the analysis for $\xi_L/L$. Crossing drift is a
secondary route and is never averaged with the joint fit.

Protocol Revision 2 freezes the previously omitted numeric choices:

| Lattice | Broad field window | Narrow field window | Registered $L_{\min}$ |
|---|---:|---:|---|
| Square calibration | [3.00, 3.10] | [3.03, 3.06] | 4, 6, 8 |
| Triangular | [4.70, 4.84] | [4.74, 4.80] | 6, 8, 10, 12 |
| Honeycomb | [2.08, 2.18] | [2.11, 2.15] | 10, 12, 14 |

These were copied from pre-verdict historical grids and commands before any
corrected target-lattice production data existed. A pilot may add larger sizes
but cannot tune these windows after viewing the ratio.

## Reproducibility and blinding

Each `(lattice,L,h,initial_state,replica)` is one resumable cell. Its manifest
records source commit and dirty state, sampler binary hash, compiler/build,
Hamiltonian and geometry, sampling parameters, seed, host, wall time,
diagnostics, completion state, and raw SHA-256. Collection fails on any
missing, failed, mismatched, or hash-invalid cell unless explicitly requested
as an incomplete diagnostic collection.

Triangular and honeycomb fits are accepted and hashed separately. The ratio is
not evaluated until both run IDs, hashes, fit variants, sampling gates, error
envelopes, and independent-route result are frozen.

## Precision and verdict

$$
\sigma(h_c^\triangle)\le1.8\times10^{-5},\qquad
\sigma(h_c^\hexagon)\le8\times10^{-6},\qquad
\sigma_R\le1.2\times10^{-5}.
$$

- Reject exact $\sqrt5$ when $|R-\sqrt5|/\sigma_R\ge10$ and every gate passes.
- Report survival when $|R-\sqrt5|\le2\sigma_R$ and every gate passes.
- Report inconclusive otherwise.

Survival is not proof of exact equality. ED is mandatory code validation but
does not replace the independent thermodynamic-limit route.
