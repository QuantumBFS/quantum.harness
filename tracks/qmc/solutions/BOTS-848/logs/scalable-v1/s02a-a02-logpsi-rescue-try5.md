# Scalable v1 S02A A02 logpsi rescue — try 5

- Date: `2026-07-29` (`Asia/Shanghai`)
- Parent / try 4 terminal: `1fc7dd71e5490adc95d77be3d38fc0ac75afa912`
- Rescue attempt: `5/5` (final allowed attempt)
- Route boundary: A02 occupation estimators only; A03 was not started
- Protocol SHA-256: `2435cd2e72ffae88117ee194f45b15451c8653dafa755b732005b6a199251d38`
- Active implementation interval: approximately `00:21`, from
  `2026-07-29 03:26:41+08:00` through the final performance decision; the
  remaining work was documentation-only closeout
- Final disposition: `failed / terminal`; the goal is blocked

## Final-attempt contract

Try 5 had to close both boundaries at once:

1. fix all three try 4 review failures with direct regressions; and
2. keep the N=6 ordinary-row median at no more than `2x` the retained failed
   raw-amplitude parent.

The correctness certificate could not be weakened merely to reach the
performance target. If either boundary failed, production changes had to be
removed and no sixth rescue could start.

## Independent reproduction and RED

Before production work, try 4's three review failures were reproduced:

- the rotated minimum-subnormal row returned
  `5.010972151555445e-20 + 5.010972151555445e-20j` instead of
  `3.758229113666584e-20 + 3.314446534921493e-20j`;
- the ordinary four-term row returned real bits `bfd3faafc743ed0b`, while the
  fallback and independent reference returned `bfd3faafc743ed09` for all 24
  insertion orders; and
- the exact dyadic halfway row raised `ArithmeticError` instead of terminating
  at the round-to-nearest-even value.

The tests-only RED commit is
`783dabf` (`test(qmc): specify final logpsi rescue boundaries`). It adds nine
table-driven exact-dyadic-to-binary64 cases, the rotated-subnormal regression,
the 24-order ordinary-row bit regression, and the exact-halfway termination
regression. The initial RED run produced:

`12 failed, 81 deselected in 1.20s`

## Evaluated implementation

The uncommitted production experiment kept exact dyadics as the coefficient
truth and added:

- pure-integer IEEE binary64 round-to-nearest-even conversion, including
  signed zero, subnormal, normal, halfway, maximum, and overflow boundaries;
- a direct exact-dyadic path for equal target/source factors, so structural
  halfway ties terminate without a symmetric Decimal uncertainty interval;
- a shared real/imaginary whole-row Decimal interval certifier at 22 digits
  with two guard digits; and
- shared target exponential factors and cached powers of two for the two
  rectangular components.

With that implementation present, the complete new selection passed:

`12 passed, 81 deselected in 1.05s`

This is focused evidence only. The full occupation and BOTS-848 suites were not
run because the mandatory performance gate failed first.

## Final N=6 performance decision

The audit used the same established benchmark definition: `N=6`, `2Q=15`,
`target_m2=0`, the 338-state feasibility sector, 256 seed-848 draws, public LLL
Coulomb quadrature and antisymmetrization, and the deterministic ordinary-scale
wavefunction used by the earlier rescue audits. The comparison loaded only the
occupation-operator source from raw parent
`4d39503114f133ef3e0a4bd772e30c98e9029f13`. No ED oracle, full-basis matrix,
eigenvalue, or saved ED artifact was read.

After one full 256-row warm-up per implementation, seven 256-row repetitions
were run in alternating try5/raw order.

| Quantity | Observed value |
|---|---:|
| Try 5 median per local energy | `1.051410938 ms` |
| Raw parent median per local energy | `0.491429297 ms` |
| Try 5 / raw parent | `2.139495843x` |
| Certifier rows during warm-up / failures | `256 / 0` |
| Fallback components during warm-up | `0` |
| Certifier rows during 1,792 timed rows / failures | `1,792 / 0` |
| Fallback components during 1,792 timed rows | `0` |
| Maximum ordinary-row absolute difference | `1.7763570511584747e-15` |

The seven try 5 repetition medians in milliseconds per evaluation were
`1.120078906`, `1.046036328`, `1.051410938`, `1.011480859`, `1.032347656`,
`1.094878906`, and `1.078246875`. The raw-parent repetitions were
`0.491429297`, `0.480294922`, `0.496491016`, `0.484074609`, `0.584255078`,
`0.498844141`, and `0.452575000`.

The whole-row certificate handled every physical row without fallback, but its
`2.139495843x` median exceeded the hard `2x` limit. Reducing precision or guard
width further, bypassing the certificate, or restoring the uncertified try 4
fast answer would violate the final-attempt correctness boundary. No such
change was made.

## Terminal closeout

All uncommitted production changes were removed with an exact reverse patch.
The occupation operator is byte-identical to parent HEAD. A fresh selected run
in this terminal state reproduced the intended RED boundary:

`12 failed, 81 deselected in 1.11s`

- No production commit was created for try 5.
- The committed tests remain as the durable specification of the unresolved
  numerical behavior.
- No A03 work was started and no push was performed.
- Try 5 exhausts the `5/5` rescue budget. There is no authorized try 6.

Final try 5 disposition: `failed / terminal`; correctness and the required
performance bound were not jointly achieved, so the goal is blocked.
