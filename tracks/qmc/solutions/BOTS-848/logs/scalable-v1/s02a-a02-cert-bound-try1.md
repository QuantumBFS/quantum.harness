# Scalable v1 S02A A02 certificate-bound review — try 1

- Date: `2026-07-29` (`Asia/Shanghai`)
- Parent: `914e695f1e0ad5268341119d2252b5bec5446fb1`
- Correctness attempt: `1/5`
- Active interval start: `2026-07-29 11:03:37+08:00`
- Active implementation budget: at most `00:90`
- Route boundary: A02 occupation estimators only; A03 is not started
- Oracle boundary: no common evaluator, real ED reveal, overlap, or candidate
  selection may be run; the mandatory complete operator test may execute its
  historical test-only Fock-ED/dense fixtures
- Current disposition: `reviewed slice-pass`

## Phase 1/2 root-cause hypothesis

`_certify_fast_components` performs target/source subtraction, Decimal
exponentiation, dyadic power and product construction, contribution
multiplication, and central/absolute-sum accumulation at precision 22.  The
current uncertainty band

`(absolute_sum + abs(central) + min_subnormal) * 1e-20`

does not expand with the number of rounded operations.  Its endpoints are also
formed under the default round-to-nearest context rather than with directed
outward rounding.  The single root-cause hypothesis is therefore that the
fixed band is not a general enclosure of the exact row once term count and
operation count grow, even when fuzzing has not exposed a wrong returned bit.

The planned correction keeps precision 22 and the two guard digits.  It uses
the base-10 unit roundoff `u = 0.5 * 10^(1 - 22) = 5e-22`, an explicit upper
bound `k` for factor sensitivity, dyadic/contribution construction, and both
accumulations, and `gamma_k = k*u/(1-k*u)`.  The band multiplier is at least
`gamma_k/(1-gamma_k)` so a rounded absolute sum cannot understate the exact
magnitude budget.  Lower and upper endpoints will be constructed in higher
precision with `ROUND_FLOOR` and `ROUND_CEILING`, then expanded outward once.
An unprovable or cell-crossing result must use the existing fallback.

## RED target

A deterministic 66-term public row uses 32 adjacent-log pairs with complex
coefficients `+(1+0.5j)` and `-(1+0.5j)`, followed by a base and a small tuner.
It has strong cancellation: the observed real absolute sum is approximately
`555.54` while the final real result is approximately `1`.  The old fixed band
certifies both components without fallback.  With `k=147`, the planned bound
has real uncertainty approximately `4.09e-17`; its directed endpoints round to
adjacent binary64 values, so a correct certificate must fall back.  The test
will compare both real and imaginary result bits with the existing 2,500-digit
independent Decimal row oracle and spy on the real fallback implementation.

## RED evidence

The tests-only RED commit is
`dbfb60dbb00c30d04d8c45750512243b98f7769e`
(`test(qmc): require operation-count certificate bound`).  The fresh selected
run after removing a duplicated high-precision condition-number calculation
produced:

```text
2 failed, 93 deselected in 37.48s
```

The helper-contract test failed with `AttributeError` because
`_fast_roundoff_multiplier` did not exist.  In the public 66-term regression,
both independent-oracle bit assertions passed before the expected failure:
the old fixed band made zero fallback calls instead of the required two.  The
test optimization retained the 2,500-digit oracle, both bit assertions, the
66-term construction, the `>500` real cancellation ratio, and the real
fallback spy.

## Bound derivation and production correction

At decimal precision `p=22`, round-to-nearest has unit roundoff
`u=0.5*10^(1-p)=5e-22`.  For one component the implementation bounds the
rounded-operation count by

`k = 2*n_terms + max(ceil(abs(target-source)) + 4) + 8`.

The two per-term operations cover the central and observed-absolute-sum
accumulations.  The fixed margin covers dyadic power/product construction,
contribution multiplication, and correctly-rounded Decimal exponentiation;
the magnitude term bounds the rounded target/source subtraction's
amplification through the exponential.  The standard accumulated relative
bound is `gamma_k=k*u/(1-k*u)`.  Because the observed absolute sum can itself
round downward, the band multiplier uses at least
`gamma_k/(1-gamma_k)`, with the original `1e-20` two-guard-digit scale retained
as a floor.

Uncertainty is rounded upward at 24 digits.  The lower endpoint is formed with
`ROUND_FLOOR`, the upper with `ROUND_CEILING`, and each is expanded once with
`next_minus` or `next_plus`.  An invalid multiplier or endpoints that do not
round to the central candidate's binary64 bits return `None` and use the
existing high-precision fallback.  The dead `_dyadic_to_float` helper was also
removed.  No estimator API, physical operator, precision, guard width, or
fallback algorithm changed.

The production commit is
`e2f2efe9f60cd3dc093ca753daefe77306d4795e`
(`fix(qmc): bound logpsi certifier roundoff`).

## GREEN evidence

All commands used the existing interpreter
`%LOCALAPPDATA%\Programs\Python\Python313\python.exe`.

| Check | Result |
|---|---|
| New certificate-bound regressions | `2 passed, 93 deselected in 63.39s` |
| Existing focused 12 | `12 passed, 83 deselected in 1.34s` |
| Complete occupation-operator file | `95 passed in 179.45s` |
| Python compileall | exit `0`; no output |
| Production forbidden scan | `rg` exit `1`; no matches |
| `git diff --check` | exit `0` |

The new public regression is slower than the old fast path because its required
GREEN behavior executes the real 1,600-digit fallback independently for both
complex components.  The oracle precision, bit assertions, and fallback spy
were not reduced to hide that cost.

## N=6 sparse-route usability

The audit used only public LLL Coulomb integrals, antisymmetrization,
`FeasibilityTable.build(6, 15, 0)`, 256 seed-848 draws, the prepared sparse
operator, and a deterministic ordinary complex logpsi callback.  It did not
import or call Fock ED, a common evaluator, full-basis or dense matrices,
eigenvalues, overlap, or candidate-selection paths.

| Quantity | Observed value |
|---|---:|
| Feasibility support | `338` |
| Certifier rows | `256` |
| Fully fast rows | `252` |
| Rows returning `None` from the fast certifier | `4` |
| Fallback components | `8 / 512` (`1.5625%`) |
| Component term-count range | `32` to `50` |
| Components in the 32-to-50 range | `512 / 512` |

The operation-count bound therefore does not unconditionally send physical
32-to-50-term rows to fallback.

## Terminal disposition

- Active implementation interval: approximately `00:21`, from
  `2026-07-29 11:03:37+08:00` through
  `2026-07-29 11:24:17+08:00`; documentation closeout followed.
- Tests-only RED, production fix, and documentation remain separated by scope.
- No existing regression expected value, physical direction, acceptance
  precision, or guard width was changed.
- The mandatory complete operator test did execute its historical test-only
  `fock_ed` full-basis, Hamiltonian, and L-squared fixtures.  These were not a
  candidate-state common-evaluator run or real ED reveal.
- No common evaluator, real ED reveal, full BOTS-848 suite, A03 work, push,
  deletion, or move was performed.

Final try 1 disposition: `slice-pass / external-spec-review-pending`.

## Review-fix: raw RN cells and ambient Decimal isolation

The review-fix interval started at `2026-07-29 11:35:34+08:00`.  Review
verified two independent certificate defects:

1. `_float_bits` intentionally canonicalizes `+0.0` and `-0.0` for grouping
   and cache keys, but its reuse for certificate cell identity incorrectly
   treated the two signed-zero RN results as one cell in both the fast and
   fallback certifiers.
2. The precision-22 fast certificate context inherited the caller's ambient
   Decimal rounding mode even though its roundoff derivation assumes
   round-to-nearest-even.

The tests-only RED commit is
`46c9304bd58e94f89a53fee89a77b3bcddfc50df`
(`test(qmc): specify signed-zero certificate boundaries`).  A fresh selected
run produced:

```text
3 failed, 95 deselected in 5.04s
```

The signed-zero public regression used a 2,500-digit independent Decimal row
oracle, established raw expected bits `8000000000000000`, and required one
call to the real fallback; the old path returned raw bits
`0000000000000000` with no fallback.  The two ambient-rounding public
regressions used deterministic rows under `ROUND_FLOOR` and `ROUND_CEILING`.
Their public result bits matched an explicit RN baseline, but the old fast
certifier made one unnecessary real-fallback call in each case instead of
preserving the RN fast/fallback decision.

The minimal production correction is
`f5233a3008fd51353787b3c5a1cb64d8d8ac6b4b`
(`fix(qmc): preserve certificate rounding cells`).  It adds raw IEEE-binary64
bit identity only for fast and fallback certificate-cell comparisons and sets
the precision-22 fast context explicitly to `ROUND_HALF_EVEN`.  The existing
zero-canonicalizing `_float_bits` remains unchanged for grouping and cache
keys.  The operation-count bound, precision 22, two guard digits, grouping,
expected values, and fallback algorithm were not changed.

Fresh post-fix verification used the explicit Python 3.13 interpreter:

| Check | Result |
|---|---|
| Signed-zero plus ambient-rounding review regressions | `3 passed, 95 deselected in 1.27s` |
| Existing operation-count-bound regressions | `2 passed, 96 deselected in 84.93s` |
| Original focused 12 | `12 passed, 86 deselected in 1.62s` |
| Complete occupation-operator file | `98 passed in 163.85s` |
| Python compileall | exit `0`; no output |
| Production forbidden scan | `rg` exit `1`; no matches |
| `git diff --check` before documentation | exit `0` |

The review-fix active interval was approximately `00:13`, from
`2026-07-29 11:35:34+08:00` through `2026-07-29 11:48:13+08:00`;
documentation closeout followed.  The complete operator test did execute its
historical test-only `fock_ed` full-basis, Hamiltonian, and L-squared fixtures.
Those fixtures were not a candidate-state common-evaluator run or real ED
reveal.  No common evaluator, candidate ED reveal, overlap, candidate
selection, A03 work, push, deletion, or move was performed.

Final review-fix disposition: `review-fix complete /
external-spec-review-pending`; no specification-compliance claim is made.

## External reviews and main-agent closeout

Specification review passed with no remaining blocker.  It independently
verified the operation-count gamma bound, the 24-digit directed outward
endpoints, raw IEEE signed-zero RN-cell identity, explicit
`ROUND_HALF_EVEN`, canonical-zero grouping/cache behavior, all scoped
regressions, the historical test-only ED disclosure, and the production
forbidden-path boundary.  Quality review then reported no Critical or Important
issue.  Its only Minor was to measure post-fallback N=6 wall time.

At reviewed implementation terminal
`77dd4825ced2bdcfd462b8bfad595545ae671699`, fresh main-agent verification
reported `12 passed, 86 deselected in 1.19s` for the original focused set,
`98 passed in 35.91s` for the complete operator file, and
`313 passed in 58.63s` for the complete BOTS-848 suite.  Compileall exited `0`;
the required and extended production forbidden scans exited `1` with no
matches; the protocol hash was
`2435cd2e72ffae88117ee194f45b15451c8653dafa755b732005b6a199251d38`;
`git diff --check` exited `0`; and the worktree was clean before this
documentation closeout.  Historical test-only ED/dense fixtures ran inside the
complete suites, but no common evaluator or candidate-state ED reveal ran.

The fresh N=6 performance audit used a new explicitly archived callback rather
than guessing the lost try-5 formula.  For 256 seed-848 rows, one warm-up, and
seven alternating repetitions, accepted median time was
`28.35994453125 ms/row`, raw-parent median time was
`0.673766796875 ms/row`, and the ratio was `42.09163268772868x`.  Warm-up used
one failed row certificate and two fallback components; timed repetitions used
seven failed row certificates and 14 fallback components.  The maximum
accepted/raw difference remained `1.7763602275288083e-15`.  The raw JSON is
`challenge15-a02-performance-fresh-77dd482.json`, SHA-256
`84293e113cde2b943ec3079c3b44caff4a229ed0bdb606eb4f7d5222e644c396`.

The callback-specific `42.09163268772868x` ratio is a non-blocking resource
metric and optimization backlog item under the approved contract.  Final try 1
disposition after both reviews and fresh verification: `reviewed slice-pass`.
A03 was not started during this attempt, and no push was performed.
