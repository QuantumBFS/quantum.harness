# Retired degree-one scout relaxation

Date: 2026-07-28

Result: the proposed small relaxation is too weak to constrain the gap and was
removed from the implementation.

## Attempt

The scout kept the full `d=2` gap basis and stationarity equations but replaced
the `703 x 703` positive matrix by its `55 x 55` principal submatrix containing
only state monomials of degree at most one. This is a sound constraint subset:
it can only enlarge the feasible set, so any numerical upper bound would be
weaker than the full relaxation.

Clarabel 0.11.1 and JuMP 1.31.1 solved fixed-threshold feasibility problems.
The scout contained:

```text
positive dimension:         55
gap dimension:               7
stationarity equalities:     3
moment variables at g=0:   748
moment variables at g=.8:  820
```

## Numerical result

All tested thresholds returned `OPTIMAL / FEASIBLE_POINT`:

```text
g=0.0: gamma = 1.0, 1.1, 2.0, 5.0
g=0.8: gamma = 0, 0.25, 0.5, 0.6, 0.8, 1, 2, 5, 10
```

This fails the calibration test: the exact `g=0` bulk gap is one, yet the
scout remains feasible at five. Feasibility at `g=0.8, gamma=10` confirms that
the issue is not a mildly loose threshold; the retained positivity block is
effectively blind to the needed gap obstruction.

These are floating-point solver statuses, not certificates or bulk-gap
claims. No threshold from this attempt should be reported as a result.

## Decision

Do not repeat this degree-one truncation. Keep the exact dimer-state `M/G/K`
evaluation as the local correctness gate, and use the existing `703 x 703`
positive basis for the next Shastry-Sutherland SDP run. If a smaller model is
needed, it must preserve more degree-two positivity structure and pass the
`g=0, gamma>1` rejection gate before any `g=0.8` scan.
