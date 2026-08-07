# Challenge #15 Route A Log-Psi Estimator Rescue Design

## Decision

Route A will replace its production raw-amplitude callback with a log-wavefunction
callback before training begins.  The production estimator interface is
`logpsi(state) -> complex`, where the real part is `log(abs(psi))` and the
imaginary part is the phase.  Raw amplitudes remain only in tiny independent test
fixtures that construct reference matrices; they are not a second production
path.

This is an A02 architecture rescue, not a change to the physics target.  The
Haldane-sphere Hamiltonian, fixed `N=6`, `2Q=15` sector, sparse Coulomb operator,
ladder Casimir construction, frozen protocol hash, and Benchmark v0 gates remain
unchanged.

## Why this change is necessary

The failed A02 branch ends at
`3145bfd3407f488ebbf230470b058088766aefab`.  Its journal records three
successively broader arithmetic designs:

1. Multiplying a matrix element by a tiny amplitude before dividing by the
   sampled amplitude underflowed to zero.
2. Dividing amplitudes first avoided that underflow but could overflow before a
   small matrix element restored a finite result.
3. Carrying one mantissa/exponent pair per complex term, then exactly summing the
   row, still lost a small rectangular component when one complex number
   contained components separated by more than the binary64 exponent range.

The final counterexample used two target amplitudes equal to `1e308`, denominator
`1`, and coefficients `1e308 + i*2^-1074` and `-1e308`.  The exact finite result
is `i*4.9406564584124655e-16`; the failed implementation returned `0j`.  The
whole-row exact accumulator also increased a measured 736-neighbor accumulation
from `0.24 ms` to `3.21 ms`.

These failures share one root cause: the estimator materialized absolute
amplitudes and attempted to repair their dynamic range afterward.  An NQS
naturally produces `log(psi)`, the common scalable evaluator already consumes
`state.logpsi`, and a wavefunction's global normalization is physically
irrelevant.  Therefore the production boundary should preserve log amplitudes
instead of reconstructing raw amplitudes.

## Scope and non-goals

This rescue changes only the Route A estimator boundary and the tests and
documentation needed to prove it.  It does not implement the A03 network, train
a model, reveal ED results, change the protocol, or weaken the sparse/no-full-
basis requirement.

The estimator guarantees correctness for the prepared LLL Coulomb and angular-
momentum coefficients used by this route, ordinary finite complex test
coefficients, exact zero neighbor amplitudes, and arbitrary global log-amplitude
shifts within binary64 subtraction precision.  It does not promise arbitrary-
precision algebra for every formally finite complex128 value.  A coefficient
whose nonzero rectangular component would disappear during safe normalization
is rejected explicitly instead of being silently rounded to a different
operator.

## Production interfaces

`operators.py` will define one callback type:

```python
LogAmplitude = Callable[[int], complex]
```

For a nonzero state, `logpsi(state).real` is finite and
`logpsi(state).imag` is a finite phase in radians.  A neighbor with exactly zero
amplitude is represented by real part `-inf` and a finite phase; its contribution
is skipped.  The sampled source state must have finite real and imaginary parts,
because a zero-probability state cannot be sampled.

The production entry points become:

```python
local_from_log_neighbors(state, neighbors, logpsi)
local_energy(state, operator, logpsi)
local_l2(state, *, two_q, target_m, logpsi)
```

There is no production `amplitude=` compatibility overload.  Tests that compare
with a tiny exact vector convert each nonzero reference amplitude to
`log(abs(value)) + 1j*phase(value)` and use `-inf` for exact zeros.

## Stable sparse-row reduction

For source `s` and each nonzero neighbor `t`, the local estimator needs

`H[s,t] * exp(logpsi(t) - logpsi(s))`.

The implementation will never exponentiate either absolute log amplitude.  It
will:

1. Validate the source log value and compute each log difference directly.
2. Skip exact-zero targets before exponentiation.
3. Convert each nonzero matrix coefficient to log magnitude and phase without
   changing either nonzero rectangular component.
4. Form a term as `(log_magnitude, phase)` by adding the log-amplitude difference.
5. Subtract the largest term log magnitude from every row term, so all
   exponentials have magnitude at most one.
6. Sum the bounded real and imaginary components with `math.fsum`.
7. Combine the row shift with the log magnitude of the bounded sum and restore a
   complex128 result only once.

An exactly canceling row returns `0j`.  A final result outside complex128 range
raises `OverflowError`; no path may return a silent `NaN` or infinity.  Input
shape, state, coefficient, and log-value errors retain explicit `TypeError` or
`ValueError` messages.

The reducer iterates only over the already merged sparse neighbor map.  Its work
and memory are linear in the number of neighbors, so the existing `O(N^2)`
ladder-neighborhood bound and the no-full-basis rule remain intact.

## Coefficient safety boundary

`PreparedPairOperator.build` continues to require a finite Hermitian pair matrix.
Preparation additionally proves that scaling each nonzero complex coefficient by
its dominant binary exponent preserves every nonzero rectangular component.  The
same validation applies to direct neighbor maps used by the route-local reducer.

This admits the physical LLL Coulomb matrix and real ladder coefficients.  It
rejects the failed artificial coefficient `1e308 + i*2^-1074`, because its
imaginary component cannot coexist with its real component in a normalized
binary64 mantissa.  Rejection is the intended result: silently accepting it would
claim a numerical contract the production representation cannot satisfy.

The implementation journal must record the observed minimum and maximum nonzero
coefficient magnitudes for the actual `N=6, 2Q=15` prepared Coulomb and ladder
operators, demonstrating that the physical workload lies inside this boundary.

## Tests and acceptance gates

The rescue follows strict RED-to-GREEN development in a new worktree.  It must
pass all of the following before A02 can be reclassified:

- Tiny `N<=4` Coulomb local energies agree with the independent direct matrix to
  absolute error below `1e-12` for real and complex states.
- Tiny `N<=4` local `L^2` values agree with the independent direct matrix to
  absolute error below `1e-12`, including negative and half-integer `M` sectors.
- Adding the same real shift `-1000`, `0`, or `+1000` and the same finite phase
  shift to every nonzero `logpsi` value leaves each local estimator unchanged
  within `2e-13` relative/absolute tolerance.
- An exact-zero neighbor contributes zero; an exact-zero or nonfinite sampled
  source is rejected.
- Multiply-first underflow and divide-first overflow examples from the failed
  journal return their correct finite values through the log interface.
- The final extreme mixed-component coefficient is rejected with a clear error,
  not accepted as `0j` and not routed through arbitrary precision.
- Random finite Hermitian physical-scale pair matrices retain correct complex
  row/column orientation and agree with direct matrices.
- Production code has no forbidden oracle import and never enumerates a full
  basis, Hamiltonian, projector, or Ritz solve.
- Targeted tests, the complete BOTS-848 suite, compilation, forbidden-import
  audit, `git diff --check`, protocol-hash check, and clean status all pass.
- A journaled `N=6` timing compares the log reducer with the last ordinary-scale
  sparse estimator.  A slowdown above `2x` requires review before A03; it is not
  hidden by reducing the frozen batch or model width.

## Downstream contract

A03 will make `AutoregressiveNQS.logpsi` the primary state evaluation method and
will test normalization with log probabilities rather than materialized tiny
amplitudes.  Analytic log derivatives already differentiate `log(psi)`, so this
removes a conversion instead of adding one.

A04 tower states and A05 `OccupationState` adapters will expose `logpsi` to the
common evaluator.  The post-reveal overlap code already contains stabilized
log-amplitude paths.  If a later tower construction needs a complex linear
combination, it must reuse the reviewed sparse log-row reducer rather than
reintroducing raw absolute amplitudes.

## Worktree and evidence policy

The failed A02 worktree and its commits remain unchanged as failure evidence.
The rescue starts from terminal commit `3145bfd3407f488ebbf230470b058088766aefab`
in branch `challenge/qmc-chiral-graviton-scalable-v1-s02a-a02-logpsi-rescue` and
worktree
`D:/Playground/worktrees/quantum.harness/challenge-qmc-chiral-graviton-scalable-v1-s02a-a02-logpsi-rescue`.

Implementation will have a dedicated rescue journal recording the design reason,
RED output, GREEN output, coefficient range, timing, hashes, external spec review,
external quality review, and final A02 classification.  No remote push and no A03
worktree are allowed until the rescued A02 passes both reviews and the main agent
repeats every gate independently.
