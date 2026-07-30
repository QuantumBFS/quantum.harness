---
title: "Challenge 148: Protocol Revision 7 - ParaToric Critical Scan"
date: 2026-07-29
tags:
  - quantum-harness
  - challenge-148
  - protocol-revision
  - paratoric
  - finite-size-scaling
status: frozen
related:
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 6.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 7 Report.md
  - Harnessing Quantum 2026/Challenge 148 - TFIM Critical-Field Ratio.md
---

# Challenge 148: Protocol Revision 7

Protocol identifier: `c148-prereg-v1+rev1+rev2+rev3+rev4+rev5+rev6+rev7`.

This append-only revision freezes the independent ParaToric critical scan
before any critical-observable pilot or production data are generated. It does
not alter the target Hamiltonian, direct-SSE estimator, sealed verdict, or
Revision 6 dual normalization.

## 1. Source-fixed observable semantics

ParaToric v1.0.3 implements `percolation_probability` as a binary projector
onto configurations containing a nonzero winding cluster on a periodic
lattice. Its generic Binder convention is

$$
U_O=\frac{\langle O^4\rangle}{\langle O^2\rangle^2},
$$

which is inverse to the direct-SSE $Q_L$ convention. The independent primary
locator is $U_\Pi$ for `percolation_probability`. It must be labeled with the
ParaToric convention and must not be compared numerically to the direct
$Q^*$.

The supporting locator is the Binder statistic of
`staggered_imaginary_times` (SIT). In the $x$ basis, each raw SIT measurement
is the signed imaginary-time average for a randomly chosen plaquette. Both
statistics are rebuilt from stored raw series; ParaToric's package summaries
remain diagnostics.

## 2. Couplings and temperature

For target TFIM field $g=h_{\rm TFIM}/J_{\rm TFIM}$, configure

$$
h_{\rm eTC}=1,\qquad J_{\rm eTC}=g,\qquad
\lambda=0,\qquad\mu=64,\qquad\beta=\frac{L}{g}.
$$

After dividing the Hamiltonian by $g$, this is the paper convention
$J_{\rm eTC}=1$, $h_{\rm eTC}=1/g$, and $\beta=L$. Periodic boundaries and
the $x$ basis are mandatory.

## 3. Frozen scan axes

| Target TFIM | Gauge lattice | $L$ | Target-field values $g$ | Registered $L_{\min}$ |
|---|---|---|---|---|
| Triangular | Honeycomb | 8, 12, 16, 20, 24, 32 | 4.740 to 4.800 inclusive by 0.005 | 8, 12, 16 |
| Honeycomb | Triangular | 10, 12, 16, 20, 24, 32 | 2.110 to 2.150 inclusive by 0.005 | 10, 12, 16 |

The target-field values are the complete production grids, not planning
anchors. Changing any size or field value requires a new protocol identifier.

## 4. Sampling and raw-data gates

Every production point uses four independently seeded chains. Each chain uses

$$
N_{\rm therm}=500L^3,\qquad
N_{\rm between}=8L^3,\qquad
N_{\rm samples}=30000.
$$

This matches the published ParaToric cadence and multiplies its per-point
statistics across independent chains. Seeds are deterministic nonzero hashes
of the protocol, run ID, target lattice, $L$, $g$, and chain index, and are
unique across the complete scan.

A cost-only pilot may reduce `N_samples`, but it cannot enter a critical fit,
select a narrower grid, change a production cadence, or revise an observable.

The following are hard gates:

1. ParaToric emits no warnings and every stored star observable is exactly
   $A_v=+1$.
2. The analytic charge-pair acceptance bound is recorded at every point.
3. The circular block length is $\lceil2\max\tau_{\rm int}\rceil$ over the
   primary, SIT, and star series; every chain contains at least eight blocks.
4. Both critical observables have at least 1,000 effective samples per chain.
5. First-half versus second-half, base-versus-doubled-block, and each chain
   versus all other chains differ by at most five combined standard errors.
6. Doubled/base standard-error ratios lie in $[1/2,2]$.
7. Fits after discarding an additional 10% and 20% of every chain shift by at
   most five combined standard errors.
8. Each size has at least two fields with pooled
   $0.05<\langle\Pi\rangle<0.95$.

## 5. Frozen finite-size analysis

The primary joint fit applies the already registered scaling family to
$U_\Pi$:

$$
U_L(g)=U^*+a_1\delta gL^{1/\nu}+a_2\delta g^2L^{2/\nu}
+b_1L^{-\omega}+c_1\delta gL^{1/\nu-\omega},
$$

with $\delta g=g-g_c$, $\nu=0.629971$, and $\omega=0.83$. The SIT Binder
statistic uses the same family as a supporting fit. Registered variants omit
the mixed term, set $\omega$ to 0.80, 0.83, or 0.86, and apply every listed
$L_{\min}$.

Both fits use 2,000 chain-plus-circular-block bootstrap resamples. A fit fails
if more than 1% of resamples fail, the design loses rank, its condition number
exceeds $10^{12}$, or $\chi^2/{\rm dof}>3$. The total uncertainty is

$$
\sigma_{\rm ind}=\sqrt{\sigma_{\rm bootstrap}^2+\Delta_{\rm variant}^2},
$$

where $\Delta_{\rm variant}$ is the largest absolute registered-variant shift.
Adjacent-size crossing drift with exponent $1/\nu+\omega$ is reported as a
secondary diagnostic and is never averaged with the joint fit.

## 6. Independent-route acceptance

Each target lattice is accepted separately only when:

1. all sampling, bracketing, bootstrap, and fit-quality gates pass;
2. the primary and SIT critical fields agree within three combined total
   uncertainties;
3. the primary total uncertainty is no greater than $1.8\times10^{-5}$ for
   triangular or $8.0\times10^{-6}$ for honeycomb;
4. the primary ParaToric field agrees with the separately frozen direct-SSE
   field within three combined total uncertainties.

No discrepant estimates are averaged. No triangular-to-honeycomb ratio is
calculated while these gates are evaluated.
