# Scalable v1 S02A A02 logpsi rescue

- Date: `2026-07-29` (`Asia/Shanghai`)
- Result: `DONE`
- Rescue try: `1/5`
- Route boundary: A02 occupation estimators only; A03 was not started
- Protocol SHA-256: `2435cd2e72ffae88117ee194f45b15451c8653dafa755b732005b6a199251d38`
- Active elapsed: approximately `00:27`, including test migration, implementation,
  verification, and measurement; the RED-to-GREEN commit span was `00:18:21`,
  well below the 90-minute active implementation limit

## Motivation and contract

The retained raw-amplitude implementation could normalize a complex
coefficient by its dominant rectangular component and silently discard a much
smaller but nonzero component.  The reviewed counterexample combined
`1e308 + i*2^-1074` with a canceling real term, so the lost imaginary component
was the complete representable answer.  A fourth raw product-ratio scaling
patch was therefore not attempted.

This rescue moves the estimator boundary to `logpsi(state) = log(abs(psi)) +
i*arg(psi)` and removes the raw-amplitude compatibility API.  The sampled
source must have finite real and imaginary logpsi components.  A neighbor may
use `complex(-inf, finite_phase)` as the sole exact-zero representation; other
nonfinite forms are rejected.  Zero coefficients are skipped before evaluating
neighbor logpsi.

Every nonzero coefficient is normalized by its largest rectangular component.
If an originally nonzero real or imaginary component becomes zero during that
normalization, the estimator and `PreparedPairOperator.build` both raise a
`ValueError` containing `coefficient component dynamic range`.  This makes the
former silent-information-loss case explicit instead of returning a false
finite answer.

Valid terms are represented by coefficient log-magnitude and direction plus
the target/source logpsi difference.  The largest term anchors bounded
exponentials; real and imaginary rows are summed independently with
`math.fsum`.  Exact cancellation returns `0j`.  Only the final real and
imaginary components are restored, and a final component outside binary64
range raises `OverflowError` rather than returning Inf or NaN.

## RED and GREEN evidence

| Phase | Command or evidence | Result |
|---|---|---|
| RED commit | `0ad60aff2ebc87a523236615fdb5735201267d1a` — `test(qmc): specify logpsi occupation estimators` | tests only |
| RED run | `python -m pytest tests/routes/test_occupation_operators.py -q` | exit 1 during collection: `ImportError: cannot import name 'local_from_log_neighbors'` |
| GREEN implementation | `a38b944e198cbe7c97cd6eeb44bf7107044b9a5f` — `fix(qmc): move occupation estimators to logpsi` | production plus focused tests |
| Focused GREEN | same targeted pytest command | `61 passed in 0.42s` |
| Full BOTS-848 GREEN | `python -m pytest -q` | `276 passed in 22.19s` |
| Python compilation | `python -m compileall -q scalable_v1 tests` | exit 0, no output |
| Forbidden oracle imports | `rg` over the production operator for benchmark ED modules | exit 1, expected no matches |
| Full-basis constructs | `rg` for `full_basis`, `fixed_m_basis`, Hamiltonian/L2 matrices, projector, or Ritz | exit 1, expected no matches |
| Removed raw API | `rg` for `Fraction`, standalone `Amplitude`, `local_from_neighbors`, and exact scaled accumulators | exit 1, expected no matches |
| Diff audit | working and staged `git diff --check` | exit 0 |

The focused tests retain the tiny public Coulomb matrix oracle, random complex
Hermitian row/column oracle, and exact L2 matrix comparisons.  New coverage
includes real logpsi shifts `-1000`, `0`, and `+1000`, a uniform phase shift,
exact-zero neighbors, invalid source and neighbor logpsi forms, zero-coefficient
short-circuiting, both historical multiply-first/divide-first extremes, the
pathological coefficient rejection at both API boundaries, final overflow,
large-term cancellation, and exact-zero row cancellation.

## N=6 physical coefficient and performance audit

The measurement used the route `FeasibilityTable` at `N=6`, `2Q=15`,
`target_m2=0`.  The table reports 338 configurations.  Seed 848 supplied 256
ordinary-scale draws.  Public LLL Coulomb quadrature and antisymmetrization
constructed the physical pair operator.

| Quantity | Observed value |
|---|---:|
| Nonzero Coulomb pair-matrix entries | 624 |
| Coulomb pair coefficient magnitude range | `4.4173821150179858e-06` to `0.47810021624597498` |
| Nonzero merged local Coulomb entries across draws | 9,410 |
| Merged local Coulomb magnitude range | `4.4173821150179858e-06` to `4.6046045839008682` |
| Nonzero one-step ladder entries across both directions | 1,967 |
| One-step ladder magnitude range | `3.872983346207417` to `8` |
| Nonzero composed ladder entries | 3,311 |
| Composed ladder magnitude range | `15.000000000000002` to `293` |
| Local Coulomb neighbor count | min 32, median 36, max 50 |

The same 256 states and deterministic ordinary-scale wavefunction were used for
the rescue and the retained failed parent `4d39503114f133ef3e0a4bd772e30c98e9029f13`.
After warm-up, each implementation ran seven complete repetitions, or 1,792
timed local-energy evaluations.  The median is the median of the seven
per-evaluation repetition times.

| Implementation | Median per local energy |
|---|---:|
| Logpsi rescue | `0.430013 ms` |
| Failed raw-amplitude parent | `0.462771 ms` |
| Rescue / parent | `0.929215x` |

The maximum absolute difference on the ordinary-scale outputs was
`1.7901808365247238e-15`.  The rescue is not more than twice as slow; it was
slightly faster in this audit, so no performance concern changes the `DONE`
result.

No ED results were read for this audit.  The measurement imported only the
public Coulomb integral machinery and the route feasibility/operator code; it
did not import or inspect the Fock ED oracle, ED matrices, eigenvalues, or saved
ED result artifacts.

## Self-review and handoff

- Production contains no raw-amplitude overload or exact `Fraction`
  accumulator.
- The former lost-component counterexample is rejected before log-polar data
  can be cached or accumulated.
- Normal-scale complex Hermitian results agree with the retained parent and
  direct-matrix tests within the declared tolerances.
- Sparse occupation traversal, prepared-pair caching, fermion signs,
  Hermitian row conjugation, and composed ladders remain unchanged.
- No full basis, Hamiltonian matrix, projector, Ritz solve, or ED result entered
  the production route.
- No push was performed, and A03 was not started.

Final disposition: `DONE`.

## External specification review — try 1 failed

This section supersedes the pre-review `DONE` disposition above.  The external
specification review examined HEAD
`782f745b36983a7c268df673ec99ed2df10ca355` and concluded:

> Not Spec compliant — BLOCKED. Three Important issues were found; the first
> two are new finite-result errors and trigger the architecture stop signal.

### Important 1 — order-dependent finite result

Let `L = log(np.finfo(np.float64).max)`, with sampled source logpsi `0`.  The
two neighbor terms are:

- A: coefficient `1`, target logpsi `L`;
- B: coefficient `1j * 1e300`, target logpsi `L - log(1e300)`.

In A-then-B insertion order, the estimator returns approximately
`1.7976931348622732e308 + i*1.7976931348622732e308`.  In B-then-A order, it
raises `OverflowError`.  Both mappings represent the same mathematical row and
should return the same finite complex value.

Root-cause evidence: terms with equal effective log magnitude retain the first
term as the anchor.  The two insertion orders therefore select different
anchor rectangular scales and reach recovery paths with different overflow
semantics.  The result is incorrectly dependent on mapping order.

### Important 2 — safe negative log difference rejected

Use sampled source logpsi `1e308`, two target logpsi values `1e308` and
`-1e308`, and coefficient `1` for both terms.  The expected result is
`1 + exp(-2e308)`, which rounds safely to approximately `1`.  Instead, forming
the second relative log difference produces `-2e308`, and the implementation
raises:

`OverflowError: local estimator log scale is outside the supported range`.

Root-cause evidence: `_log_difference` rejects every nonfinite floating result.
A negative overflow in a log-magnitude difference is a safe underflowing term
and should saturate to zero contribution; only a positive unrepresentable
difference should be rejected.  The current shared rejection path therefore
turns a finite row result into an exception.

### Important 3 — non-Hermitian extreme matrix accepted

Let `z = complex(max_float, max_float)` and pass the matrix
`[[0, z], [0, 0]]` to `PreparedPairOperator.build`.  This matrix is plainly not
Hermitian and must be rejected.  It is instead accepted.

Root-cause evidence: `np.abs` overflows both the matrix scale and Hermitian
defect to `inf`.  The comparison becomes `inf > inf`, which is false, so the
non-Hermitian matrix passes validation.  Hermiticity needs an overflow-safe
relative comparison.

### Terminal disposition and next-attempt boundary

- Try 1 result: `failed`.
- Reviewer disposition: `Not Spec compliant — BLOCKED`.
- The earlier ordinary-scale tests and performance record remain factual but
  do not establish specification compliance against these finite-result and
  validation counterexamples.
- Try 1 active implementation time remains approximately `00:27`.  Work after
  the external review was documentation-only closeout; no new active
  implementation interval was started or inferred.
- The commit containing this section is the terminal commit for try 1.
- Any next rescue must start from that terminal commit in a new, independent
  worktree.  It must not continue patching this try 1 worktree.
- No try 2 or A03 work was started, no production code or tests were changed
  after review, and no push was performed.

Final try 1 disposition: `failed / terminal`.
