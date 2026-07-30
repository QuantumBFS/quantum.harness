# Track A extension: locked distinguishability analysis

Locked while the large-size array is still running and before inspecting its
completed aggregate.

## Scientific question

Can the available sizes distinguish a nonzero thermodynamic wrapping plateau
from a marginal/logarithmic drift toward the short-range value, and, if not,
what size would be required at the achieved precision?

## Inputs

Use central-beta cells from `track_a_20260727` and critical-role cells from
`track_a_large_20260728`. Keep all successful seeds. No point is removed on
the basis of its value. Operational failures may only be rerun with identical
parameters.

## Models

For each sigma and each registered minimum-size window fit:

1. `power`: `O(L) = O_inf + a * L^(-omega)`, `omega > 0`.
2. `marginal`: `O(L) = O_inf + a / log(L/L0)`, `0 < L0 < min(L)`.

The primary observable is `Rp`; `Qm` is a corroborating observable. Fits use
seed standard errors with a conservative floor equal to the median positive
standard error divided by two. Report chi-square, AICc, BIC, and leave-one-size
out weighted prediction error.

## Stability

Repeat for every `L_min` leaving at least five sizes. A boundary statement is
allowed only when the sign and practical classification of `Rp_inf`, and the
preferred model, remain stable under removal of the smallest sizes. Otherwise
the result remains inconclusive.

## Distinguishable-size forecast

For candidate sizes `3072, 4096, 6144, 8192, 12288, 16384, 32768, 65536`,
compute the absolute separation of the two fitted mean predictions divided by
their combined parameter-prediction uncertainty and the extrapolated achieved
Monte Carlo standard error. The first size reaching 3 sigma is reported as a
planning estimate, not as evidence about unmeasured physics. If none reaches
3 sigma, report `>65536`.

Parametric bootstrap intervals use 1000 replicas and the registered seed-error
model. Failed nonlinear fits are counted and reported, never silently dropped.
