# Challenge 148 Frozen Production Protocol

Protocol identifier: `c148-prereg-v1+rev1+rev2+rev3`.

This is the clean-checkout copy of the preregistration and three append-only
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
