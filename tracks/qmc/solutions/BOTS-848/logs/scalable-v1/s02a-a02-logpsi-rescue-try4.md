# Scalable v1 S02A A02 logpsi rescue — try 4

- Date: `2026-07-29` (`Asia/Shanghai`)
- Parent / try 3 terminal: `fad24b06fb8a60280ea002e4e6c55b7c449bc418`
- Rescue attempt: `4/5`
- Route boundary: A02 occupation estimators only; A03 was not started
- Protocol SHA-256: `2435cd2e72ffae88117ee194f45b15451c8653dafa755b732005b6a199251d38`
- Active implementation elapsed: approximately `00:31`, from the first try 4
  worktree inspection through implementation, verification, and measurement;
  the RED-to-GREEN commit span was `00:16:27`, below the 90-minute limit
- Slice disposition: `slice-pass / external-spec-review-pending`

## Architecture reset hypothesis

Three consecutive rescue failures established that a coefficient log cannot
be the estimator's numerical truth.  Try 3 converted each binary64 coefficient
component to a rounded log magnitude before cancellation.  Distinct adjacent
coefficients `x=1e300` and `y=nextafter(x,+inf)` therefore acquired equal logs,
were reduced as `+1-1`, and lost the exact binary64 residual
`-1.487016908477783e284`.  Its 100-digit Decimal boundary path independently
rounded the exact 309-digit integer representation of `max_float` upward and
then compared that rounded product with an exact boundary.

Try 4 resets both assumptions.  The only coefficient truth is the input
complex128 real and imaginary components.  Log magnitudes are coarse ordering
hints only.  `_phase_direction` retains its existing binary64 trigonometric
contract; after it returns, both phase components are treated as exact dyadic
inputs.  No new mathematical phase convention or dependency is introduced.

## Numerical invariants

1. Every finite binary64 rectangular component is converted with
   `as_integer_ratio` into an integer mantissa and power-of-two exponent.
   Addition and multiplication normalize Python-integer dyadics and may exceed
   float range without losing information.
2. Terms with bit-identical target log-magnitude and phase factors first merge
   their original coefficient components exactly.  The exact coefficient is
   then multiplied by the binary64 phase direction as a complex dyadic.
   Rotated terms sharing a target log-magnitude merge again before any
   exponential is evaluated.  Only a structurally proven integer zero is
   removed.
3. Mapping-order independence comes from bit-pattern factor keys and
   deterministic sorting.  Neither insertion order nor a rounded
   coefficient-log collision selects the numerical truth.
4. The ordinary fast path uses ratios constructed from the real dyadic
   component scales and a target-log difference.  It never forms
   `exp(log(scale_i)-log(scale_anchor))`.  It includes every component and
   transfers the whole component to fallback on ratio under/overflow, a huge
   target difference, more than `2^20` cancellation conditioning, a zero that
   was not structurally proved, or a binary64 boundary component.
5. Fallback recomputes the complete structurally grouped row.  Its initial
   Decimal precision is at least 1,600 digits and is raised to cover the exact
   decimal length of every dyadic input; unresolved rounding doubles precision
   up to a hard 6,400-digit limit.  Effective-log bands avoid direct
   `exp(±1e308)`.  Omitted lower bands and Decimal rounding receive an explicit
   upper bound, and a result is returned only when the entire interval rounds
   to one binary64 value.  Failure to prove a unique result raises an explicit
   indeterminate-rounding error rather than guessing.
6. Real and imaginary components are independently converted by Python's
   binary64 round-to-nearest-even conversion.  `OverflowError` is raised only
   when the certified component conversion is infinite.

The fast path is therefore a performance optimization over the retained
dyadic truth, not an alternate coefficient model.  It does not discard a lower
band; uncertain rows restart from the grouped exact inputs in fallback.

## RED evidence

The tests-only RED commit is
`e464b13de028f98d1b4a9d6a6ff0f1e57ba4318e`
(`test(qmc): specify dyadic logpsi rescue try4`).  The selected pre-production
run produced:

`8 failed, 5 passed, 68 deselected in 30.44s`

The failures were the expected rounded-log ULP erasure, false `max_float`
overflow, loss/rejection of the minimum imaginary component, incorrect
ULP-residual-plus-lower-band result, inaccurate `complex(max,max)` restoration,
missing true complex overflow, and both estimator/prepared-operator uses of the
obsolete component dynamic-range rejection.  The deterministic random-oracle
loop was reduced before the RED commit from 16 ten-term rows to six eight-term
rows to control test cost; its precision, exponent range, shuffle coverage,
and behavioral contract were unchanged.

The committed regressions cover:

- both orders of `{+1e300, -nextafter(1e300,+inf)}` at a common factor;
- `max_float*exp(0)=max_float` and `min_subnormal*exp(0)=min_subnormal`;
- every order of `(max_float+i*min_subnormal)-max_float`;
- all six `+exp(1e308)-exp(1e308)+1` permutations and all 120 orthogonal
  multi-level `2+3j` permutations retained from try 3;
- an ULP-scale dominant residual combined with a distinct lower log band;
- three individually sub-half-ULP lower terms whose sum crosses the midpoint;
- both finite try 2 near-maximum restorations, its true overflow, and the true
  finite `nextafter` order-invariance case;
- the minimum-subnormal half boundary from below and above;
- finite `complex(max_float,max_float)` and a true overflow of both components;
- sampled/target log-magnitude differences formed from `±1e308` without a
  direct huge exponential;
- six fixed-seed, eight-term signed complex rows spanning wide coefficient and
  log exponents, each compared with an independent 2,500-digit whole-row
  Decimal oracle under three deterministic shuffles.

## Superseded component-rejection contract

Try 1 introduced `coefficient component dynamic range` rejection because its
log-polar normalization could turn an originally nonzero rectangular component
into zero.  That rejection protected the old representation; it is not a
physical input restriction.  It conflicts with the new required finite row
`(max+i*min_subnormal)-max = i*min_subnormal`.

Try 4 therefore replaces the two rejection tests with preservation tests in
the same RED commit.  A single finite `complex(max,min_subnormal)` coefficient
must retain both components, and `PreparedPairOperator.build` must retain the
same Hermitian matrix entry.  Nonfinite coefficient rejection, scalar
validation, overflow-safe Hermitian normalization, and the relative Hermitian
defect criterion are unchanged.  This is an explicit representation-contract
correction, not a silent weakening of finite/nonfinite validation.

## GREEN implementation and verification

The production commit is
`974ab4b2fc784d519047e4bbee09ecb35ae8cf4d`
(`fix(qmc): retain dyadic logpsi row truth`).

| Check | Result |
|---|---|
| New boundary selection | `13 passed, 68 deselected` |
| Focused occupation operators | `81 passed in 37.43s` |
| Full BOTS-848 | `296 passed in 57.90s` |
| Python compilation | exit 0 |
| Forbidden benchmark ED imports | `rg` exit 1, expected no matches |
| Full-basis/matrix/projector/Ritz constructs | `rg` exit 1, expected no matches |
| Removed raw-amplitude compatibility API | `rg` exit 1, expected no matches |
| Protocol hash | exact match |
| Working and staged diff checks | exit 0 |

The fixed-seed wide-exponent oracle test reports identical results for every
shuffle.  It uses only test-side Decimal arithmetic and the declared
binary64 `_phase_direction` formula; production does not import that oracle.

## N=6 fallback and performance audit

The audit used `FeasibilityTable` at `N=6`, `2Q=15`, `target_m2=0`, seed 848,
and 256 sampled local-energy evaluations.  The exact sector support is 338;
the 256 with-replacement draws contained 176 unique configurations.  Public
LLL Coulomb quadrature and antisymmetrization constructed the physical pair
operator.  A deterministic ordinary complex amplitude supplied equivalent
raw amplitude and logpsi callbacks.

Each implementation ran seven complete repetitions after warm-up.  A wrapper
around the try 4 fallback counted component calls without changing the fast
path.

| Quantity | Observed value |
|---|---:|
| Try 4 fallback components during 256-row warm-up | `0` |
| Try 4 fallback components during 1,792 timed rows | `0` |
| Try 4 median per local energy | `0.868456 ms` |
| Failed raw-amplitude parent median | `0.507998 ms` |
| Try 4 / raw parent | `1.709567x` |
| Maximum ordinary-row absolute difference | `1.7764788079573408e-15` |

Try 4 does not make fallback the ordinary physical path and remains below the
`2x` raw-parent review blocker.

| Physical quantity | Observed value |
|---|---:|
| Nonzero pair coefficients | `624` |
| Pair magnitude range | `4.417382115017986e-06` to `0.478100216245975` |
| Merged local entries across draws | `9,410` |
| Merged local magnitude range | `4.417382115017986e-06` to `4.604604583900868` |
| Local Coulomb neighbor count | min `32`, median `36`, max `50` |
| One-step ladder entries / range | `1,967`; `3.872983346207417` to `8` |
| Composed ladder entries / range | `3,311`; `15.000000000000002` to `293` |

No ED results were read.  The audit imported only public Coulomb integral
machinery, the route feasibility table, and occupation operators.  The raw
comparison loaded only the failed parent's occupation-operator source; it did
not import or inspect Fock ED, ED matrices, eigenvalues, saved ED artifacts,
full-basis data, or oracle outputs.

## Self-review and handoff

- The estimator no longer constructs a coefficient log magnitude or normalized
  coefficient direction.
- Exact dyadic grouping occurs before every cancellation decision and can
  retain components across the complete binary64 dynamic range.
- Decimal operands and the final boundary are formed under the same sufficient
  precision; `max_float*exp(0)` never passes through an inexact 100-digit
  product.
- Sparse occupation traversal, prepared-pair caching, fermion signs,
  Hermitian row conjugation, composed ladders, and the public logpsi API remain
  unchanged.
- Diff scope is limited to the focused tests, production operator, and this
  independent try 4 journal.
- No push was performed and A03 was not started.

Local try 4 result: `slice-pass / external-spec-review-pending`.  External
specification review is required before declaring try 4 spec-compliant or
starting any later route item.

## External specification review — try 4 failed

This section supersedes the local `slice-pass` disposition above.  The final
external review conclusion was:

> Not Spec compliant — 3 Important issues; quality review must be blocked.

The 81 focused tests, 296 full tests, compilation and static isolation checks,
zero N=6 fallback calls, and approximately `1.64x` to `1.71x` raw-parent
performance ratios remain factual.  They do not establish specification
compliance against the following new finite-result and termination
counterexamples.

### Important 1 — fast path rounds the dyadic anchor before scaling

Use coefficient `min_subnormal`, sampled source log-magnitude `-700`, target
log-magnitude `0`, and a target/source phase difference of `acos(0.75)`.  The
fallback and high-precision reference return

`3.758229113666584e-20 + 3.314446534921493e-20j`.

The ordinary fast path instead returns

`5.010972151555445e-20 + 5.010972151555445e-20j`.

Root-cause evidence: phase rotation correctly creates exact dyadic components,
including `0.75 * min_subnormal`, that are not themselves representable as
binary64.  `_dyadic_to_float` rounds each anchor component before the common
`exp(700)` restoration.  Both distinct dyadics round to the same minimum
subnormal scale, so the later multiplication magnifies an already lost
component difference.  Retaining a dyadic as the source of truth is
insufficient if the fast path converts that truth to float before scaling.

### Important 2 — ordinary fast path lacks whole-row RN-even certification

Set sampled source log-magnitude to `1.3735516793873876` and use the four
coefficient/target-log-magnitude pairs:

- `(3.4428098013331905, -0.47673852159895347)`;
- `(6.530397713504417, -0.8514257707488002)`;
- `(-5.208222393324844, -1.2559283904236707)`;
- `(-4.376072469198897, 0.06587580241150182)`.

The 2,500-digit whole-row reference and the explicit fallback both return
`-0.3121756978941482`.  The fast path returns
`-0.3121756978941483` for all 24 insertion orders, a two-ulp error.

Root-cause evidence: deterministic ordering prevents permutation drift but
does not prove correct rounding.  The fast path separately rounds dyadic
ratios, exponentials, scaled terms, the `math.fsum` result, and final restore.
Its cancellation threshold detects only gross conditioning; it has no
whole-row error interval showing that all accumulated uncertainty lies inside
one binary64 round-to-nearest-even cell.

### Important 3 — exact halfway ties cannot terminate

Use equal logpsi factors with coefficients `a = 2^-901` and `b = 2^-954`.
Their exact dyadic sum is the halfway value between `a` and the next binary64
number.  Round-to-nearest-even must return

`a = 5.915260930833874e-272`.

Both insertion orders instead exhaust the 6,400-digit precision limit and
raise `ArithmeticError`.

Root-cause evidence: the fallback surrounds its Decimal approximation with a
symmetric nonzero uncertainty interval.  At an exact midpoint that interval
always crosses both adjacent rounding cells, regardless of increased Decimal
precision.  The implementation has no exact dyadic tie detector and no direct
binary64 round-to-nearest-even termination rule for an exactly representable
structural sum.

### Terminal disposition and final-attempt boundary

- Try 4 result: `failed`.
- Reviewer disposition: `Not Spec compliant`; quality review is blocked by
  three Important finite-result or termination failures.
- Try 4 active implementation time remains approximately `00:31`.  Activity
  after final external review was documentation-only closeout; no additional
  implementation interval was started or inferred.
- The commit containing this section is the terminal commit for try 4.  This
  worktree must not receive further production or test patches.
- Any next rescue is the final allowed attempt, try `5/5`.  It must start in a
  new independent worktree from this terminal commit; try 5 was not started
  here.
- A final architecture must not round dyadic anchors before common scaling,
  must certify the complete fast-row round-to-nearest-even result, and must
  terminate exact dyadic halfway ties with the IEEE even rule.  Another failed
  rescue exhausts the attempt budget and leaves the goal blocked.
- No production code or tests were changed after review.  No A03 work was
  started, and no push was performed.

Final try 4 disposition: `failed / terminal`.
