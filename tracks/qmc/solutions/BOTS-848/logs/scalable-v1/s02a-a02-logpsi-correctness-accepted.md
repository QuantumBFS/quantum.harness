# Scalable v1 S02A A02 logpsi correctness acceptance

- Date: `2026-07-29` (`Asia/Shanghai`)
- Starting SHA: `7b9747e18bd65d4edfaeb37857e0da99a8973d58`
- Accepted production SHA: `d1f1196f4cc2932adb9dc41aff634f80b36202ce`
- Comparison SHA: `5aa9219f4cd24bc2274f0514b621c2f9b47cead7`
- Raw performance parent: `4d39503114f133ef3e0a4bd772e30c98e9029f13`
- Protocol SHA-256: `2435cd2e72ffae88117ee194f45b15451c8653dafa755b732005b6a199251d38`
- Active elapsed: approximately `00:20`, from `2026-07-29 09:52:54+08:00`
  through the production verification and commit; documentation and final
  repository-state audit followed
- Route boundary: A02 occupation estimators only; A03 was not started
- Reviewed implementation terminal: `77dd4825ced2bdcfd462b8bfad595545ae671699`
- Final disposition: `slice-pass`

## Revised acceptance contract

The acceptance amendment at starting SHA `7b9747e` keeps numerical correctness
as a hard gate.  The N=6 timing ratio remains mandatory evidence, but is now a
cost metric and optimization-backlog item rather than a blocking gate.  This
commit therefore restores the already-tested try-5 correctness implementation;
it is not a sixth rescue attempt.  No regression was weakened, no uncertified
try-4 fast answer was restored, and no precision or guard width was reduced for
performance.

### Review correction: oracle scope

The historical 308-test verification did execute test-only fixtures that call
`run_ed_oracle` and exercise `fock_ed` full-basis, dense-Hamiltonian, dense
L-squared-matrix, and projected-NQS paths.  The earlier statement that no such
path was read or run was therefore too broad.

The four-route barrier still held for the accepted production implementation,
the N=6 performance measurement, and the occupation-autoregressive route code:
they did not import or open those prohibited ED/full-basis/dense modules.  No
`run_scalable_evaluator.py` invocation occurred, and no Route A candidate was
given an ED reveal, overlap, or ED-based selection.  The historical test-only
fixtures were not a candidate-state common-evaluator run.

## RED and GREEN evidence

The committed tests-only RED baseline before this work was:

```text
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_operators.py -q
12 failed, 81 passed in 59.76s
```

A fresh focused pre-implementation run in this worktree reproduced exactly the
nine missing dyadic-converter cases plus the rotated-subnormal, ordinary-row,
and exact-halfway failures:

```text
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_operators.py -q -k "exact_dyadic_to_binary64 or does_not_round_rotated_subnormal_anchor_before_scale or certifies_ordinary_row_rounding_under_all_orders or terminates_exact_dyadic_halfway_tie"
12 failed, 81 deselected in 1.28s
```

With the production implementation present, the same selection produced:

```text
12 passed, 81 deselected in 1.22s
```

The complete verification results were:

```text
python -m pytest tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_operators.py -q
93 passed in 24.28s

python -m pytest tracks/qmc/solutions/BOTS-848/tests -q
308 passed in 43.40s

python -m compileall -q tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive
exit 0; no output

rg -n "benchmark_v0\.(fock_ed|ed_oracle|projected_nqs|nqs_benchmark)|full_basis|hamiltonian_matrix|l_squared_matrix" tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive
exit 1; no matches

git diff --check
exit 0; no whitespace errors
```

The host required the explicit existing interpreter path
`%LOCALAPPDATA%\Programs\Python\Python313\python.exe`; this did
not change the commands' modules, arguments, or selected tests.

## Root cause and implementation

Try 4 retained exact dyadic coefficient truth but lost it at three later
boundaries:

1. it rounded a rotated, non-binary64 dyadic anchor before applying the common
   exponential scale;
2. its ordinary path had deterministic ordering but no whole-row
   round-to-nearest-even certificate; and
3. a symmetric Decimal uncertainty interval could never terminate when an
   exact structural sum lay exactly halfway between adjacent binary64 values.

The accepted implementation adds pure-integer dyadic-to-IEEE-binary64
round-to-nearest-even conversion, including signed zero, subnormal, normal,
halfway, maximum-finite, and overflow boundaries.  Equal target/source factors
use a direct exact-dyadic route, so structural halfway ties terminate under the
even rule.  Other ordinary rows use one shared real/imaginary whole-row Decimal
outward-cell certificate at 22 digits with two guard digits.  Target
exponential factors and powers of two are shared and cached across the two
rectangular components.  The existing escalating fallback remains intact.

Only
`scalable_v1/routes/occupation_autoregressive/operators.py` changed in the
production commit.  The RED tests were not rewritten or weakened.

## N=6 cost evidence

The local measurement used the public LLL Coulomb integral builder only:
`coulomb_integrals(15)` followed by `antisymmetrized_pair_matrix`.  It used
`FeasibilityTable.build(6, 15, 0)`, whose sector contains 338 states, and 256
seed-848 draws.  The deterministic ordinary-scale wavefunction and raw-parent
comparison definition match try 5.  Each implementation received one complete
256-row warm-up, followed by seven alternating 256-row timing repetitions, or
1,792 timed local-energy evaluations per implementation.

| Quantity | Observed value |
|---|---:|
| Nonzero pair coefficients | `624` |
| Pair coefficient magnitude range | `4.4173821150179858e-06` to `0.47810021624597498` |
| Accepted median per local energy | `1.147960156 ms` |
| Raw-parent median per local energy | `0.533172656 ms` |
| Accepted / raw parent | `2.153073949x` |
| Warm-up certificate rows / failures | `256 / 0` |
| Timed certificate rows / failures | `1,792 / 0` |
| Warm-up / timed fallback components | `0 / 0` |
| Maximum ordinary-row absolute difference | `1.7763570511584747e-15` |

Accepted repetition times in milliseconds per evaluation were
`1.114771875`, `1.169432422`, `1.181660547`, `1.208798437`, `1.116214453`,
`1.147960156`, and `1.097673438`.  Raw-parent times were `0.524780469`,
`0.533172656`, `0.545978125`, `0.538385938`, `0.527708984`, `0.509748047`,
and `0.551866016`.

Device fingerprint:

```text
Windows-11-10.0.26200-SP0
Intel64 Family 6 Model 170 Stepping 4, GenuineIntel
AMD64; 22 logical CPUs
Python 3.13.2; NumPy 2.4.4
```

The measured `2.153073949x` slowdown is reported without rounding below `2x`.
Under the revised contract it is accepted as A02 cost evidence and retained as
an optimization backlog item; it does not override the hard correctness GREEN.

## Scope and final disposition

- Production code commit: `d1f1196f4cc2932adb9dc41aff634f80b36202ce`.
- No test file was changed during correctness acceptance.
- Review correction: the historical full test suite executed test-only
  ED/full-basis/dense/projected-NQS fixtures; production, the N=6 performance
  measurement, and route code did not use them, and no Route A candidate
  received an ED reveal, overlap, or ED-based selection.
- No A03 implementation or common evaluator work was started.
- No push was performed.

Final result: `slice-pass`.

## Post-review amendment

The obsolete monkeypatch-only fast gate was removed in
`1600bbfbf9e01058a84de8365f8527c3ec931bd3`.  The oracle-scope correction in
`914e695f1e0ad5268341119d2252b5bec5446fb1` is the parent of the independent
certificate-bound review attempt.

That review found the precision-22 fixed uncertainty scale did not grow with
the number of rounded operations and formed its endpoints under
round-to-nearest.  The tests-only RED is
`dbfb60dbb00c30d04d8c45750512243b98f7769e`; the operation-count gamma bound
and directed outward endpoints are in
`e2f2efe9f60cd3dc093ca753daefe77306d4795e`.

- Terminal production placeholder, resolved after the scoped production
  commit: `e2f2efe9f60cd3dc093ca753daefe77306d4795e`.
- Precision 22 and the two guard digits remain unchanged.
- The 66-term strong-cancellation regression uses a 2,500-digit independent
  oracle and requires the existing fallback when the enlarged interval crosses
  adjacent binary64 rounding cells.
- A 256-row N=6 sparse-route audit retained 252 fully fast rows; 4 rows used 8
  fallback components out of 512 components spanning 32 through 50 terms.
- No common evaluator, ED reveal, overlap, candidate selection, A03 work, push,
  or full BOTS-848 suite was performed during the review attempt.

Post-review local result: `slice-pass / external-spec-review-pending`.

## Certificate-bound review-fix amendment

A follow-up review found that the certificate reused the grouping/cache key
helper, which intentionally canonicalizes signed zero, for RN-cell identity.
It also found that the precision-22 fast certificate context inherited the
ambient Decimal rounding mode even though the certificate bound assumes
round-to-nearest-even.

The public tests-only RED is
`46c9304bd58e94f89a53fee89a77b3bcddfc50df`.  Its signed-zero case uses a
2,500-digit Decimal oracle and requires raw `-0.0` plus one real fallback.  Its
two deterministic ambient-rounding cases compare public result bits and the
real fast/fallback decision under `ROUND_FLOOR` and `ROUND_CEILING` against an
explicit RN baseline.  Before the correction, the selected result was
`3 failed, 95 deselected in 5.04s` for exactly those three behaviors.

The production review-fix is
`f5233a3008fd51353787b3c5a1cb64d8d8ac6b4b`.  It uses raw IEEE-binary64 bits
only for certificate-cell identity and explicitly sets the precision-22 fast
context to `ROUND_HALF_EVEN`; grouping/cache zero canonicalization, the
operation-count bound, precision, guard digits, expected values, and fallback
algorithm remain unchanged.

Fresh verification produced `3 passed, 95 deselected in 1.27s` for the new
review cases, `2 passed, 96 deselected in 84.93s` for the prior
operation-count-bound cases, `12 passed, 86 deselected in 1.62s` for the
original focused selection, and `98 passed in 163.85s` for the complete
operator file.  Compileall exited `0`, the production forbidden scan exited
`1` with no matches, and the pre-documentation `git diff --check` exited `0`.

The review-fix active interval was approximately `00:13`, from
`2026-07-29 11:35:34+08:00` through `2026-07-29 11:48:13+08:00`;
documentation closeout followed.  The complete operator file executed its
historical test-only `fock_ed` full-basis/dense fixtures, but no common
evaluator, candidate ED reveal, overlap, candidate selection, A03 work, push,
deletion, or move occurred.

Post-review-fix local result: `review-fix complete /
external-spec-review-pending`; no specification-compliance claim is made.

## Independent review and fresh closeout

The specification review passed with no remaining blocker after verifying the
operation-count gamma bound, 24-digit directed outward endpoints, raw IEEE
signed-zero certificate cells, explicit `ROUND_HALF_EVEN`, the original 12
regressions, and the absence of a production ED path.  The subsequent quality
review found no Critical or Important issue.  Its sole Minor requested a fresh
N=6 wall-time measurement after the physical fallback path was introduced.

The main-agent verification at reviewed implementation terminal
`77dd4825ced2bdcfd462b8bfad595545ae671699` produced:

| Check | Fresh result |
|---|---|
| Original focused regressions | `12 passed, 86 deselected in 1.19s` |
| Complete occupation-operator file | `98 passed in 35.91s` |
| Complete BOTS-848 suite | `313 passed in 58.63s` |
| Python compileall | exit `0` |
| Required and extended production forbidden scans | exit `1`; no matches |
| Protocol SHA-256 | `2435cd2e72ffae88117ee194f45b15451c8653dafa755b732005b6a199251d38` |
| `git diff --check` | exit `0` |
| Worktree before documentation closeout | clean |

The complete operator and BOTS-848 suites include historical test-only
Fock-ED/full-basis/dense fixtures.  No common scalable evaluator was run and no
Route A candidate received an ED reveal, overlap, or ED-based selection.

The requested fresh N=6 cost audit used a newly archived deterministic callback
definition because the exact try-5 callback formula was not preserved.  It is
therefore a new same-framework audit, not a claim of exact try-5 reproduction.
The definition was N=6, 2Q=15, M2=0, 338-state support, 256 seed-848 rows, one
warm-up, and seven alternating 256-row repetitions.  The raw JSON evidence is
`challenge15-a02-performance-fresh-77dd482.json`, SHA-256
`84293e113cde2b943ec3079c3b44caff4a229ed0bdb606eb4f7d5222e644c396`.

| Fresh cost quantity | Observed value |
|---|---:|
| Accepted median per row | `28.35994453125 ms` |
| Raw-parent median per row | `0.673766796875 ms` |
| Accepted / raw parent | `42.09163268772868x` |
| Warm-up certifier failures / fallback components | `1 / 2` |
| Timed certifier failures / fallback components | `7 / 14` |
| Maximum accepted/raw absolute difference | `1.7763602275288083e-15` |

This large callback-specific slowdown is retained as an explicit optimization
backlog and resource-planning input.  Under the approved acceptance amendment,
it does not override the hard numerical-correctness gate or the two independent
reviews.  Final reviewed A02 result: `slice-pass`; A03 remained unstarted during
this closeout, and no push was performed.
