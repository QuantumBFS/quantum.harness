# Confirmatory-protocol amendment log

## 2026-07-29: explicit sign convention for the J2 environment control

**Timing:** before generation of any convergence, production-A, or
production-B dataset.

The frozen matrix specified `J2=0.1` but did not spell out its Hamiltonian sign
and normalization. The machine-readable scope and protocol now define

\[
H_{J_2}=-J_2\sum_i\mathbf S_i\cdot\mathbf S_{i+2}.
\]

No condition, time window, observable, fit model, or decision threshold was
changed. The clarification prevents two inequivalent microscopic controls
from sharing the same label. The nearest-neighbour purification-TEBD runner
continues to reject these two jobs until a separately validated long-range
backend is available.

## 2026-07-30: Production-B eligibility policy v1.2

**Timing:** frozen while the SCNet convergence jobs were still running and
before any Production-A result or Production-B datum was available.

The earlier launch-control draft allowed Production B only after a supported
two-mode outcome. That rule was scientifically incomplete: if the registered
scalar surrogate survives Production A, the decisive next test is precisely
whether it also survives the independent \(t>200\) window. Protocol v1.2
therefore makes exactly three terminal validation statuses eligible:

- `scalar_surrogate_not_rejected`;
- `independent_two_burgers_supported`;
- `coupled_two_mode_supported`.

`memory_or_more_modes_required` and every unresolved, missing, malformed, or
contradictory state remain ineligible. This amendment changes no dataset,
initial condition, split, fit, statistic, or numerical threshold. It freezes
which already-registered forecast, if any, receives the confirmatory
Production-B calculation.
