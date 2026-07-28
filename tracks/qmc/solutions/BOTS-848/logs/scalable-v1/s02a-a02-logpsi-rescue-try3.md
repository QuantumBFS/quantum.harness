# Scalable v1 S02A A02 logpsi rescue — try 3

- Date: `2026-07-29` (`Asia/Shanghai`)
- Parent / try 2 terminal: `2b4cd87cb11cc6fa36041b9d47f3319632eb07a3`
- Rescue attempt: `3/5`
- Route boundary: A02 occupation estimators only; A03 was not started
- Protocol SHA-256: `2435cd2e72ffae88117ee194f45b15451c8653dafa755b732005b6a199251d38`
- Active implementation elapsed: approximately `00:15`, from worktree creation
  through implementation, verification, and measurement; the RED-to-GREEN
  commit span was `00:08:47`, below the 90-minute limit
- Slice disposition: `slice-pass / external-spec-review-pending`

## Hypothesis and root cause

Try 2's max-shift reduction discarded every term more than one binary64
dynamic range below the current anchor before knowing whether the dominant
signed or complex terms would cancel.  Thus
`exp(1e308) - exp(1e308) + 1` lost the finite remainder even though all six
neighbor orders represent the same row.  Orthogonal real and imaginary
cancellations can repeat at several log scales, so a single special case for
three real terms would not repair the architecture.

The minimal replacement is a deterministic hierarchical reduction performed
independently for real and imaginary components.  At each level, terms within
the representable band of the largest effective log magnitude are reduced
with bounded exponentials and `math.fsum`.  Exact cancellation descends to the
next band.  A nonzero residual is represented as a new log-component term and
folded back together with the lower bands.  Therefore lower finite terms are
discarded only when a surviving larger result makes them irrelevant to
binary64 rounding.

Try 2 also used inconsistent direct and reconstructed decisions around
`log(max_float)`.  Try 3 keeps ordinary restoration on the float hot path but
uses a 100-digit `Decimal.from_float` product only near the binary64 boundary.
It compares against the actual binary64 maximum, accepting a finite rounded
component and rejecting a true overflow.  The overflow-safe Hermitian
normalization and coefficient component dynamic-range rejection from try 2
remain unchanged.  No raw-amplitude fallback, ED object, full basis, matrix
oracle, projector, or Ritz path was introduced.

## RED and GREEN evidence

The tests-only RED commit is
`2d8261d3c0afc6700091013d2b6f420f1c550bd2` (`2026-07-29T01:54:49+08:00`,
`test(qmc): specify logpsi rescue try3 boundaries`).  The targeted run before
production changes produced:

`5 failed, 64 deselected in 0.55s`

The RED coverage requires:

- all six permutations of `+exp(1e308) - exp(1e308) + 1` to return exactly
  `1`;
- all 120 permutations of two orthogonal cancellation levels followed by a
  finite remainder to return `2 + 3j`;
- the finite near-maximum values
  `1e-300 * exp(1400.5582407915977) = 1.7976931348622307e308` and
  `2^-1074 * exp(1454.2227848147652) = 1.7976931348621938e308` to be restored;
- `1e300 * exp(19.00718499517029)` to raise `OverflowError`.

The GREEN commit is
`5dc194bdf7cc179bfe4b8be16aeb8bcc41db5336` (`2026-07-29T02:03:36+08:00`,
`fix(qmc): preserve hierarchical logpsi cancellation`).  It contains the
hierarchical reducer, boundary-only Decimal restoration, and the associated
test correction described below.

| Check | Result |
|---|---|
| Five new regression cases | `5 passed, 64 deselected` |
| Focused occupation operators | `70 passed in 0.42s` |
| Full BOTS-848 | `285 passed in 22.15s` |
| Python compilation | exit 0 |
| Forbidden benchmark ED imports | `rg` exit 1, expected no matches |
| Full-basis/matrix/projector/Ritz constructs | `rg` exit 1, expected no matches |
| Raw-amplitude compatibility API | `rg` exit 1, expected no matches |
| Working and staged diff checks | exit 0 |
| Protocol hash | exact match |

On 200 deterministic ordinary complex rows, the maximum relative/absolute
error against the direct reference was `1.3495852962262386e-14`; reversing
neighbor order changed no result (`0` maximum difference).  Additional complex
near-maximum adversarial scans found no representability mismatches.

## Corrected try 2 boundary specification

The former try 2 order-invariance test expected both components to remain
finite for a row containing coefficient `1` at `log(max_float)` and
coefficient `1e300j` at
`log(max_float) - log(1e300)`.  That expectation was contradictory with the
actual binary64 inputs.  Although the rounded log difference equals
`19.00718499517029`, a high-precision evaluation of those exact floats gives

`1e300 * exp(19.00718499517029) = 1.0000000000000001116 * max_float`.

The imaginary component is therefore genuinely unrepresentable.  Both
insertion orders now must raise `OverflowError`; treating either order as
finite would preserve try 2's false acceptance.

The finite order-invariance regression moves that imaginary target logabs one
binary64 step toward `-inf` with `math.nextafter`.  Its high-precision ratio is
`0.9999999999999965589 * max_float`, its expected float is
`1.7976931348623095e308`, and both insertion orders return the identical finite
complex result.  This correction changes the inaccurate test oracle, not the
requirement that representability be mapping-order independent.

## N=6 physical and performance audit

The audit used 256 states from the route `FeasibilityTable` at `N=6`, `2Q=15`,
and `target_m2=0`.  Each implementation ran seven complete repetitions after
warm-up.  The median is the median per local-energy evaluation.

| Implementation | Median per local energy | Try 3 ratio |
|---|---:|---:|
| Try 3 | `0.564331 ms` | `1.000000x` |
| Try 2 terminal | `0.475978 ms` | `1.185624x` |
| Try 1 terminal | `0.455325 ms` | `1.239404x` |
| Failed raw-amplitude parent | `0.501909 ms` | `1.124371x` |

Try 3 is not more than twice as slow as any comparison, so the performance
review-blocker threshold is not activated.

| Physical quantity | Observed range |
|---|---:|
| Coulomb pair coefficient magnitude | `4.4173821150179858e-06` to `0.47810021624597498` |
| Merged local Coulomb magnitude | `4.4173821150179858e-06` to `4.6046045839008682` |
| One-step ladder magnitude | `3.872983346207417` to `8` |
| Composed ladder magnitude | `15.000000000000002` to `293` |
| Local Coulomb neighbor count | min 32, median 36, max 50 |

No ED results were read.  The audit used only public Coulomb integral
machinery, the route feasibility table, and occupation operators; it did not
import or inspect Fock ED, ED matrices, eigenvalues, saved ED artifacts,
full-basis data, or oracle outputs.

## Self-review and handoff

- Dominant signed and orthogonal cancellation now descends through lower log
  levels without losing a representable finite remainder.
- Near-maximum restoration makes one bidirectional decision against the actual
  binary64 limit, including exact subnormal coefficient inputs.
- Sparse occupation traversal, prepared-pair caching, fermion signs,
  Hermitian row conjugation, composed ladders, and public logpsi API remain
  unchanged.
- Diff scope is limited to the focused test file, production operator, and
  this independent try 3 journal.
- No push was performed and A03 was not started.

Local try 3 result: `slice-pass / external-spec-review-pending`.  External
specification review is required before declaring try 3 spec-compliant or
starting any later route item.

## External specification review — try 3 failed

This section supersedes the local `slice-pass` disposition above.  The final
external review conclusion was:

> Not Spec compliant — 2 Important issues; quality review must be blocked.

The 70 focused tests, 285 full tests, compilation and static isolation checks,
ordinary-row comparisons, physical-range audit, and performance measurements
remain factual.  They do not establish specification compliance against the
following new finite-result counterexamples.

### Important 1 — rounded coefficient-log collision erases one ulp

Set sampled source and both target logpsi values to `0`.  Let
`x = 1e300` and `y = math.nextafter(x, +math.inf)`, with neighbors
`{2: x, 3: -y}`.  The two distinct binary64 coefficients satisfy
`math.log(x) == math.log(y)`.  The estimator returns `0j`, but summing the
original coefficients gives

`math.fsum((x, -y)) = -1.487016908477783e284`.

Root-cause evidence: the reduction around `operators.py:549-555` uses only the
rounded coefficient-log delta.  Both terms therefore become unit magnitudes
with opposite signs and are classified as an exact cancellation.  Compressing
each binary64 coefficient to `coefficient_logabs` before summation has already
discarded the ulp-scale difference, so the later hierarchical descent cannot
recover the finite answer.

### Important 2 — insufficient Decimal precision causes false overflow

Use one neighbor with coefficient `max_float`, sampled source logpsi `0`, and
target logpsi `0`.  The exact operation is multiplication by `exp(0) = 1`, so
the estimator must return the original finite `max_float`.  It instead raises
`OverflowError`.

Root-cause evidence: the fallback around `operators.py:430-438` performs the
product with Decimal precision 100.  `Decimal.from_float(max_float)` needs
about 309 decimal digits for its exact integer representation.  The
multiplication is rounded upward at precision 100 and then compared against a
separately exact `Decimal.from_float(max_float)`, producing a false overflow.
The path therefore mixes a rounded Decimal result with an exact boundary in a
comparison that is not conservative in either direction.

### Terminal disposition and architecture reset boundary

- Try 3 result: `failed`.
- Reviewer disposition: `Not Spec compliant`; quality review is blocked by
  two Important finite-result errors.
- Try 3 active implementation time remains approximately `00:15`.  Activity
  after final external review was documentation-only closeout; no additional
  implementation interval was started or inferred.
- This is the third consecutive failed rescue.  Any future try 4 must begin
  with an architecture reset in a new independent worktree from the terminal
  commit, not another local patch to this reduction.
- The reset must not treat `coefficient_logabs` as the sole numerical truth.
  It must preserve the actual binary64 scale/component through cancellation,
  and every high-precision path must carry enough precision to represent any
  binary64 input exactly before making a representability comparison.
- The commit containing this section is the terminal commit for try 3.
- No production code or tests were changed after review.  No try 4 or A03 was
  started, and no push was performed.

Final try 3 disposition: `failed / terminal`.
