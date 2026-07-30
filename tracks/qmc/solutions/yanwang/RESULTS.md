# Issue #148 baseline result

## Question and convention

We study

\[
H=-J\sum_{\langle i,j\rangle}\sigma_i^z\sigma_j^z
  -h\sum_i\sigma_i^x
\]

on triangular and honeycomb lattices in the Pauli-matrix convention of
Blöte and Deng (2002). The target ratio is
\(R=h_c^\triangle/h_c^\hexagon\).

The literature survey found no post-2002 direct calculation that improves
both published estimates in the same convention. The trusted reference is

- triangular: `4.76811(9)`;
- honeycomb: `2.13250(4)`.

See [`research/CATALOG.md`](research/CATALOG.md) for the search, method and
convention audit, finite-size ranges, and uncertainty limitations.
The classical star–triangle transformation and 2+1-dimensional Ising
duality do not currently provide an exact triangular–honeycomb TFIM coupling
map; see
[`research/ANALYTIC_RELATION.md`](research/ANALYTIC_RELATION.md).

## Computational routes

The primary route uses a dedicated sign-problem-free stochastic-series-
expansion implementation with cluster updates. Small periodic triangular and
honeycomb cells were checked against an independent exact-diagonalization
oracle. The analysis uses the pre-registered spacetime Binder-ratio fit

\[
Q_L=Q^\star+a_1x+a_2x^2+a_3x^3
  +b_1L^{-0.815}+b_2L^{-1.9665},
\qquad x=(h-h_c)L^{1.587}.
\]

The independent route uses the ALPS looper continuous-time QMC
implementation. It is retained as a pilot cross-method check, not promoted to
final-production evidence.

Both lattice estimates were fitted independently. The conjectured value
\(\sqrt5\) was not used in either field fit or in model selection.

## Numerical result

| Quantity | Central value | Statistical uncertainty | Systematic uncertainty |
|---|---:|---:|---:|
| \(h_c^\triangle/J\) | `4.7682137757` | `6.3977e-5` | `2.7994e-4` |
| \(h_c^\hexagon/J\) | `2.1324944020` | `1.6757e-5` | `2.5117e-5` |
| \(R\) | `2.2359795042` | `3.4768e-5` | `1.5731e-4` |

Using the frozen Cartesian product of all 22 accepted triangular and 17
accepted honeycomb variants gives

```text
sqrt(5)        = 2.2360679775
R - sqrt(5)    = -8.8473e-5
sigma_R,total  = 1.6111e-4
|R-sqrt(5)|/sigma_R,total = 0.55
```

The triangular primary fit has `χ²=19.44` for 26 degrees of freedom
(`p=0.817`). A completed exact-RNG check repeated all 23 registered fit
variants with 100,000 bootstrap resamples; it reproduced the same central
field and `6.3977e-5` statistical uncertainty. The largest shift among
accepted triangular variants is `2.7994e-4` (`L_min=14`), which is used as a
conservative systematic envelope.

The independent ALPS pilot gives

```text
h_c(triangular) = 4.7682224
h_c(honeycomb)  = 2.1324600
R               = 2.2360196
```

It agrees with the primary route at its current precision, but its larger
systematic uncertainty prevents promotion to final evidence.

## Frozen-gate result

The pre-registered gate requires both:

1. \(\sigma_R\le 1.2\times10^{-5}\);
2. accepted critical-point and crossing diagnostics for both lattices.

The present data fail both the target ratio precision and the triangular
all-adjacent-size crossing gate. The latter failure arises because the frozen
narrow field window does not bracket crossings for the smallest adjacent
size pairs. It is a scientific gate failure, not a program crash.

Accordingly, the verdict is:

> **Inconclusive but consistent with \(\sqrt5\).** The conjecture survives
> this baseline numerical test; the present precision does not establish
> exact equality.

Printing the ratio to seven decimal places would not change this verdict.

## Provenance and included artifacts

- Exact-RNG full-variant check: Slurm job `23025426`, 100,000 resamples per
  registered variant; exit code 1 records the frozen crossing-gate failure.
- Honeycomb baseline: Slurm job `89413`, 100,000 resamples.
- Independent-route bootstrap: Slurm job `89526`, 100,000 resamples per
  lattice.
- Triangular raw-input manifest:
  `ae3541478dd81dae5b2836f02cd7302f90b18e6a56e263ef4ff61e3e78aa10d5`.

The repository includes compact JSON/CSV summaries, crossing and residual
plots, reviewed source, ED validation code, tests, the literature catalog,
data schema, analysis contract, and pre-registration. Multi-gigabyte raw QMC
chains are intentionally not committed.

## Remaining work for a final verdict

A production result needs a wider triangular field window with the frozen
analysis unchanged, sufficient statistics to pass the crossing gate, and a
full independent production route. Until those checks pass, the result must
remain baseline-stage and inconclusive.
