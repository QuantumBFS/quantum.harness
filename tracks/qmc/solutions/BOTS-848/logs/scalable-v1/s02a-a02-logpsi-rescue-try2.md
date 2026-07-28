# Scalable v1 S02A A02 logpsi rescue — try 2

- Date: `2026-07-29` (`Asia/Shanghai`)
- Parent / try 1 terminal: `9b37842f5ba36047d27c36de1c39b066fec62f4f`
- Rescue attempt: `2/5`
- Route boundary: A02 occupation estimators only; A03 was not started
- Protocol SHA-256: `2435cd2e72ffae88117ee194f45b15451c8653dafa755b732005b6a199251d38`
- Active implementation elapsed: approximately `00:12`; the RED-to-GREEN
  commit span was `00:08:14`, below the 90-minute limit
- Slice disposition: `slice-pass / external-spec-review-pending`

## Hypothesis

The three try 1 specification failures share two narrow numerical boundaries
and do not require another estimator API redesign:

1. Equal effective term magnitudes need a deterministic anchor and a final
   component restore that distinguishes a legal near-maximum binary64 result
   from a genuinely unrepresentable `2^1024`, independent of mapping order.
2. A log difference that overflows negatively denotes a safely negligible
   contribution, while positive overflow still denotes an unrepresentable
   result.  The sign must be retained instead of rejecting both cases.
3. Hermiticity can be tested without overflow by normalizing the whole matrix
   with its largest finite rectangular component before computing complex
   magnitudes and defects.

The coefficient component dynamic-range rejection from try 1 remains in force.
No raw-amplitude fallback, ED object, full basis, matrix oracle, projector, or
Ritz path is introduced.

## Independent reproduction and RED

Before production changes, all three review cases were reproduced on the try 1
terminal code:

- A-then-B returned the finite value
  `1.7976931348622732e308 + i*1.7976931348622732e308`; B-then-A raised
  `OverflowError: local estimator result is outside complex128 range`.
- With source logpsi `1e308` and target logpsi `1e308/-1e308`, the estimator
  raised `OverflowError: local estimator log scale is outside the supported
  range` instead of returning approximately `1`.
- `PreparedPairOperator.build` accepted `[[0,z],[0,0]]` for
  `z=complex(max_float,max_float)`; the raw matrix scale and Hermitian defect
  both evaluated to `inf`.

The tests-only RED commit is
`d30137f4b8345223083bb6ec94655889192f0925` (`test(qmc): specify logpsi rescue
try2 edge cases`).  The minimal three-case run produced:

`3 failed, 61 deselected in 0.56s`

The failures were the expected restore overflow, `math.fsum` intermediate
overflow, and missing Hermitian rejection.  No production file had changed.

## Minimal implementation

The GREEN commit is `2fa7090913fa5cb86e7041809612a05a03b9625f`
(`fix(qmc): make logpsi rescue order-safe`).

- `_log_difference` keeps `math.fsum` on the normal hot path.  Only when fsum
  itself overflows does an exact `Decimal.from_float` fallback recover the
  sign and any finite cancellation.  Negative infinity then scales a term to
  zero; positive infinity remains an explicit overflow.
- Equal effective log magnitudes choose the largest exact rectangular
  coefficient scale, so anchor selection no longer depends on neighbor
  insertion order.
- Final restoration first preserves the direct exact-scale multiplication.
  If that intermediate overflows at the binary64 boundary, a mantissa/exponent
  reconstruction distinguishes the legal maximum-component case from
  `2^1024`.  Components safely below the boundary retain the more accurate
  single `exp(full_log)` path required by the existing extreme-phase test.
- `PreparedPairOperator.build` finds the maximum rectangular matrix component,
  divides the matrix by that finite scale, and compares the normalized
  Hermitian defect against the normalized matrix magnitude.  It never applies
  `np.abs` directly to the original extreme complex matrix.
- The production diff is limited to the occupation operator.  The only
  post-RED test adjustment changes the maximum complex assertion to separate
  real/imaginary checks because `pytest.approx(complex(max,max))` overflows
  while computing the expected complex modulus; the required behavior is
  unchanged.

## GREEN verification

| Check | Result |
|---|---|
| Three review regressions | `3 passed, 61 deselected in 0.33s` |
| Focused occupation operators | `64 passed in 0.37s` |
| Full BOTS-848, fresh pre-commit | `279 passed in 22.06s` |
| Python compilation | exit 0 |
| Forbidden benchmark ED imports | `rg` exit 1, expected no matches |
| Full-basis/matrix/projector/Ritz constructs | `rg` exit 1, expected no matches |
| Working and staged diff checks | exit 0 |
| Protocol hash | exact match |

Existing normal-scale complex Hermitian oracle comparisons, logpsi shift and
phase invariance, exact-zero handling, multiply-first/divide-first extremes,
coefficient component dynamic-range rejection at both boundaries, final
overflow, and exact cancellation all remain green.

## N=6 physical and performance audit

The audit used `FeasibilityTable` with `N=6`, `2Q=15`, `target_m2=0` and seed
848.  Its sector support is 338, and 256 ordinary-scale draws were used.  Public
LLL Coulomb quadrature and antisymmetrization constructed the operator.

| Quantity | Observed value |
|---|---:|
| Nonzero pair-matrix coefficients | 624 |
| Pair coefficient magnitude range | `4.4173821150179858e-06` to `0.47810021624597498` |
| Merged local Coulomb entries across draws | 9,410 |
| Merged Coulomb magnitude range | `4.4173821150179858e-06` to `4.6046045839008682` |
| One-step ladder entries | 1,967 |
| Ladder magnitude range | `3.872983346207417` to `8` |
| Composed ladder entries | 3,311 |
| Composed ladder magnitude range | `15.000000000000002` to `293` |
| Local Coulomb neighbor count | min 32, median 36, max 50 |

Each implementation ran seven repetitions over all 256 states after warm-up,
or 1,792 timed local-energy evaluations per implementation.

| Implementation | Median per local energy | Try 2 ratio |
|---|---:|---:|
| Try 2 | `0.444980 ms` | `1.000000x` |
| Try 1 terminal | `0.449667 ms` | `0.989577x` |
| Failed raw-amplitude parent `4d395031` | `0.486326 ms` | `0.914983x` |

Try 2 and try 1 ordinary-scale outputs were identical.  The maximum absolute
difference between try 2 and the raw failed parent was
`1.7901808365247238e-15`.  Try 2 is not more than twice as slow as either
comparison, so the performance review-blocker threshold is not activated.

No ED results were read.  The measurement used only public Coulomb integral
machinery, the route feasibility table, and occupation operators; it did not
import or inspect Fock ED, ED matrices, eigenvalues, or saved ED artifacts.

## Self-review and handoff

- All three external review counterexamples now have direct regression tests.
- Negative log overflow saturates only in the safe direction; positive final
  overflow remains an error.
- Hermitian validation remains scale-relative while avoiding original-matrix
  complex-magnitude overflow.
- Coefficient component dynamic-range rejection and the pure logpsi API are
  unchanged.
- Diff scope is limited to the focused test file, production operator, and this
  independent try 2 journal.
- No push was performed and A03 was not started.

Local slice result: `slice-pass`.  External specification review is still
required before declaring try 2 spec-compliant or starting any later route
item.
