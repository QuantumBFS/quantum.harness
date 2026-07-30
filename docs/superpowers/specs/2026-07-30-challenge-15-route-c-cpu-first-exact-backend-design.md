# Challenge #15 Route C Fast Exact Admission Backend Design

> Status: fast-path revision approved by the request to continue Route C faster;
> written-spec review pending
>
> Date: 2026-07-30
>
> Parent attempt: `scalable-v1-s02c-a02`
>
> Parent close commit: `ce12191e9dec53e76c7137a1ff4b530573b878f3`
>
> Prospective attempt: a03 is not allocated by this design commit

## 1. Decision

Route C keeps the frozen one-layer Challenge contract and replaces only the
failed exact coordinate-action backend. The production path is:

```text
division-free analytic JK cofactor reduction
    -> explicit six-component seed polynomial
    -> nested JAX JVP pair-Casimir action
    -> whole-batch JAX/XLA kernel on CPU
    -> optional use of the same kernel on a validated GPU
```

This is a 90-minute backend-admission spike, not an open-ended rewrite. It
tests the shortest exact implementation first. The previously designed fixed
225-coefficient dense-jet backend remains a mathematically valid future R&D
fallback, but it is not implemented during this deadline sprint. If the JAX
JVP path does not pass the unchanged N=6 batch-512 gate inside the timebox,
Route C is classified as not salvageable within the remaining Challenge time.

CPU execution is the required path. GPU execution is an optional placement
optimization and is not a correctness dependency. A missing or queued GPU may
not silently reduce the workload, change the ansatz, or select a different
formula.

The following protocol fields remain unchanged:

- Haldane sphere at `nu=1/3`, with `N=6, 2Q=15` for the primary workload;
- strict electronic LLL and fully polarized fermions;
- one `L=0` ground-state seed and one reduced `L=2` seed generating all five
  `M=-2,-1,0,1,2` components;
- one exact scalar-operator layer with density ranks `2,3,4` and hidden width
  `64`;
- `complex128`, three training seeds, 2048 optimizer updates, batch `512` per
  N=6 sector, and the existing sampling and symmetry thresholds;
- actual `N=8, 2Q=21`, batch `256` smoke;
- the existing oracle-isolation and resource ceilings.

No protocol byte changes in this backend design. No ED/full-basis,
coefficient-only CF, JK1/JKk, GMP, stochastic-amplitude, or Landau-level-mixed
fallback is admitted.

## 2. Evidence and failure boundary

Attempt a02 established the physics and small-instance correctness of the
one-layer action:

```text
[1 + sum_{ell=2,3,4} a_ell S_ell] Psi_JK.
```

The pair-Casimir decomposition, bounded jet algebra, analytic N=2
eigenvalues, independent symbolic reference, all five `L=2` components, and
forbidden-import audit passed. The failure was wall time, not memory:

- the original sparse-dictionary implementation exceeded 600 seconds;
- a vectorized sparse multiplication retry also exceeded 600 seconds;
- the retry completed the five small N=6 multiplet checks and the N=6 `L=0`
  batch-8 branch, but did not complete the N=6 `L=2` batch-8 branch;
- observed working sets stayed below 100 MB, so adding memory does not address
  the bottleneck.

The failed implementation performs three expensive operations inside Python
loops for every configuration and active particle pair:

1. reconstruct the full JK polynomial over sparse `PairJet` dictionaries;
2. evaluate one or more determinants through subset dynamic programming over
   the jet ring;
3. repeat shared JK/Jastrow work separately across `L=2` components.

The new backend must remove these operations algorithmically. Threading the
old object graph is not an admissible redesign.

## 3. Approaches considered

### 3.1 Selected: analytic cofactor reduction plus nested JAX JVP

Exploit the exact Jastrow-times-homogeneous-Vandermonde structure of the
filled JK `n=0` matrix. Rewrite every particle-hole column replacement as a
sum of explicit, division-free cofactors. Apply `J_i dot J_j` to the resulting
six-component polynomial by nested JAX directional derivatives and compile
the whole batch with XLA.

This removes determinant-jet evaluation and all 225-coefficient jet plumbing,
shares derivative traces across the five `L=2` components, has static shapes,
and provides one array contract for CPU and future GPU execution. It is the
only exact backend with a realistic admission answer inside 90 minutes.

### 3.2 Deferred beyond the deadline: fixed 225-coefficient dense jets

The fixed dense-jet design avoids autodiff graph growth and remains the most
controlled long-term exact backend. It also requires coefficient tables,
truncated products, derivative maps, and a separate JAX implementation. That
engineering cost consumes too much of the seven-hour deadline before the
actual resource gate or training can start. It is retained as post-deadline
R&D only, not as an automatic fallback from a failed spike.

### 3.3 Rejected as production: compiled subset-DP determinant

Replacing dictionaries by dense arrays would reduce Python overhead, but it
would retain determinant recurrence for every pair and particle-hole term.
It is useful as a reduced correctness reference, not as the primary N=8
scaling strategy.

### 3.4 Rejected as the redesign: direct JAX translation of a02

JIT-compiling the existing algorithm would preserve its repeated determinant
and seed-construction complexity. JAX acts only on the explicit analytic
cofactor polynomial; the a02 determinant is retained only as a reduced
correctness reference.

## 4. Exact analytic reduction

For `N` particles, write the unexcited projected-orbital matrix as

```text
A[r,h] = c_h u_r^h v_r^(N-1-h) J_r,
c_h    = sqrt(binomial(N-1,h)),
J_r    = product_{s != r} (u_r v_s - v_r u_s).
```

Each `L=2` particle-hole term replaces column `h` by an already validated
projected `n=1` column `b_p`. Multilinearity gives the ring identity

```text
det(A with column h replaced by b_p)
    = sum_r Cofactor(A)[r,h] b_p[r].
```

This identity is valid over any commutative ring, including the truncated
pair-jet ring, and uses no matrix inverse or pivot.

Let `R` be all particles except `r`, and define

```text
Delta_ab = u_a v_b - v_a u_b,

E_k(R) = coefficient of t^k in product_{s in R} (v_s + u_s t).
```

The homogeneous-Vandermonde minor is, up to the fixed row/column sign,

```text
det M^(r,h)
  = sigma(N,r,h)
    [product_{a<b; a,b in R} Delta_ab]
    E_(N-1-h)(R).
```

Therefore each cofactor is an explicit product of:

- the fixed sign and monopole-orbital normalizations;
- `product_{s != r} J_s`;
- the Vandermonde product excluding particle `r`;
- one elementary homogeneous polynomial `E_(N-1-h)(R)`.

The implementation does not hand-code `sigma`. It derives a deterministic
sign/normalization table from the declared row and column ordering and locks
that table against direct complex determinants for `N=2..8`. Prefix/suffix
products compute `product_{s != r} J_s` without division. Static masked factor
tables compute each small excluded-particle Vandermonde product. Prefix/suffix
products of the generating polynomials `v_s + u_s t` compute every required
`E_k(R)`.

The final seed expression is exactly the existing JK polynomial:

```text
Psi_L2^M = sum_(h,p) coupling[M,h,p]
           sum_r Cofactor(A)[r,h] b_p[r].
```

All five `M` values are contracted from the same cofactor and projected-column
tensors in one call. The `L=0` seed remains the existing direct
`product Delta_ij^3` polynomial.

## 5. Exact JVP action contract

Let `F(x)` return the six seed amplitudes from one spinor configuration `x` in
the order `(L0M0,L2M-2,L2M-1,L2M0,L2M1,L2M2)`. For particle `i`, define the
three coordinate vector fields

```text
Z_i F = (u_i d/du_i - v_i d/dv_i) F / 2,
P_i F = u_i dF/dv_i,
M_i F = v_i dF/du_i.
```

Each field is evaluated as one JAX JVP whose tangent is constructed from the
current coordinates. Nested JVPs therefore differentiate both the inner
function and its coordinate-dependent tangent, giving the exact composition

```text
(J_i dot J_j) F
  = Z_j(Z_i F) + [M_j(P_i F) + P_j(M_i F)] / 2.
```

For every unordered pair, the kernel recursively constructs scaled powers
`F, X_ij F, ..., X_ij^4 F`, where `X_ij=(J_i dot J_j)/scale`. The three fixed
pair-Casimir coefficient vectors contract the same powers for ranks `2,3,4`.
The one-body constants are added after summing all unordered pairs.

The production kernel uses only `complex128`, static `N`, static ranks, and
the explicit cofactor seed. It vectorizes across configurations and all six
sectors; it may use `vmap`, `lax.map`, or a fixed chunk size only as measured
execution choices. It contains no determinant, Python object array, ED basis,
finite difference, stochastic derivative, or silent precision fallback.

## 6. Component boundaries

### `cofactor_seed.py`

- Implements the division-free JK cofactor formula.
- Provides an array-namespace-compatible polynomial used by NumPy tests and
  by the JAX executor without importing JAX itself.
- Produces all six sector components in the order
  `(L0M0,L2M-2,L2M-1,L2M0,L2M1,L2M2)`.
- Contains no JAX import and no ED/full-basis dependency.

### `jax_action.py`

- Enables `jax_enable_x64` before kernel construction.
- Implements `Z`, `P`, and `M` as exact directional JVPs and composes the
  pair-Casimir powers through degree four.
- JIT-compiles one whole-batch or fixed-chunk kernel rather than dispatching
  individual derivatives from Python.
- Vectorizes over configurations and contracts all particle pairs, ranks, and
  six sector components before returning to Python.
- Accepts an explicit platform. `cpu` may not fall through to GPU, and `gpu`
  may not fall through to CPU.
- Records compile time separately from post-compile execution time.

### `coordinate_action.py`

- Retains the validated public `evaluate_seed_and_actions(state, configs,
  ells=...)` compatibility surface.
- Adds the family-level production entry point only after admission, returning
  seed values of shape `(B,6)` and actions of shape `(B,6,3)`.
- Validates inputs before dispatch, pads only the final chunk to a static
  shape, masks padded outputs, and rejects non-finite results.
- Never selects the slow reference path implicitly.

### `microbenchmark.py`

- Measures compile time, two warmups, and five steady-state repetitions.
- Measures `L=0` and reduced `L=2` sector-compatible views without claiming
  cross-sector sharing as a resource discount.
- Writes the source commit, protocol hash, platform, device list, JAX/Python
  versions, chunk size, every timing, and peak RSS atomically.

## 7. Data flow

For one static-size chunk:

1. validate finite normalized spinors and place them on the selected device;
2. compute pair factors, all-except-one products, elementary polynomials, and
   projected `n=1` columns;
3. contract the explicit cofactors into all five `L=2` seed amplitudes while
   evaluating the direct `L=0` amplitude;
4. use nested directional JVPs to apply scaled powers of `J_i dot J_j`
   through degree four to the shared six-component seed function;
5. contract the three pair-Casimir polynomials and sum unordered pairs;
6. add the one-body constants and return all seed/action components;
7. apply the final-chunk mask and transfer only the compact result arrays to
   the caller.

Chunk size is a measured execution knob, not a physics parameter. The
microbenchmark selects it from a small fixed set using only public random
probes, records the choice, and then freezes it for all compared runs on the
same device class.

## 8. CPU-first and optional GPU placement

The required production placement is JAX/XLA CPU with 32 or fewer CPU cores,
matching the frozen remote CPU limit. The repository-supported installation is

```text
make install jax EXTRA=cpu
```

The CPU smoke records `jax.devices()`, confirms the CPU platform, enables
`complex128`, and runs one compiled N=2 JVP contraction before the resource
benchmark.

GPU placement uses the same source kernel and tables. It is accepted only
after an in-allocation smoke confirms the GPU platform and a `complex128`
operation. It may not be inferred from partition metadata or a successful
submission. As of this design, SCNet GPU requests passed scheduler syntax but
had impractically distant estimated starts, and a 30-second immediate
allocation obtained no GPU. Those results justify CPU-first placement but are
not permanent claims about SCNet availability.

The committed `scnet.toml` describes an older partition view than the current
live account. Before a remote benchmark, the implementation plan must re-probe
SCNet and either refresh the profile from live evidence or pass explicit
verified overrides. A stale profile may not select resources.

## 9. Correctness gates

The new backend must pass all of these before resource timing is classified:

1. Cofactor values agree with direct complex column-replacement determinants
   for `N=2..8`, every hole column, and deterministic non-node probes, with
   relative residual at most `1e-12`.
2. NumPy and JAX cofactor seed values agree with the existing direct complex
   determinant path for `N=2..8`, with relative residual at most `1e-12`.
3. JVP pair-dot powers and final `S_ell` actions agree with the a02 PairJet
   reference for `N=2,3` and tractable N=6 single-configuration probes, with
   relative residual at most `1e-10`.
4. All five `L=2` components use one shared kernel and retain the existing
   exchange, rotation, ladder, and strict-LLL residual thresholds.
5. The nontrivial-dressing rank test remains GREEN for both `L=0` and `L=2`.
6. Exact nodes remain explicit; near-node finite probes may not be converted
   into false zeros by division or pivot failure.
7. Static import and path audits show no production ED/full-basis dependency.
8. CPU execution is deterministic within the existing numerical tolerances
   for repeated calls with identical inputs and static tables.

The a02 implementation remains a test-only reference. It is never selected as
a production fallback when the new backend fails.

## 10. Resource gate

For the frozen remote placement, the exact action has half of the two-hour
wall ceiling and 75 percent of the 64 GiB RSS ceiling. With two sectors and
2048 updates, the steady-state N=6 batch action threshold is

```text
t_N6_batch512 <= 3600 / (2 * 2048)
                 = 0.87890625 seconds per sector.
```

The memory threshold is

```text
peak_RSS <= 0.75 * 68719476736
         = 51539607552 bytes (48 GiB).
```

The placement passes only if:

- the full N=6 batch `512` shape completes two warmups and five measured
  repetitions for both sector-compatible views;
- JAX compile time is recorded separately, and
  `compile_seconds + 2*2048*median_action_seconds <= 3600`;
- measured peak RSS is at most 48 GiB;
- an actual N=8 batch `256` completes two warmups and five measurements;
- all recorded values are finite and the device/platform contract is exact.

An asymptotic estimate, reduced batch, scheduler success, or partial N=8 run
cannot pass this gate. Training work remains blocked until the gate is GREEN.

## 11. Error handling

- Invalid flux, rank, state ordering, chunk size, dtype, shape, or non-finite
  coordinate fails before JIT dispatch.
- The kernel returns explicit finite-status flags; the host raises
  `CoordinateActionNumericalError` instead of accepting NaN or infinity.
- JAX compilation failure, missing x64 support, device mismatch, or silent
  platform fallback is a backend failure, not a reason to reduce precision.
- A cofactor/reference mismatch blocks performance timing.
- Out-of-memory and wall timeout are recorded as resource failures with the
  exact static shape and device fingerprint.
- Timing records use atomic replacement and contain compile and steady-state
  phases separately.

## 12. Attempt and stop boundaries

This design commit does not allocate a03. The implementation plan begins with
a 90-minute backend-admission slice on the current clean descendant of the a02
close commit:

- prove the cofactor identity against direct complex determinants;
- compile the N=2 CPU JVP correctness fixture, then an N=6 single-config
  probe;
- run the unchanged N=6 batch `512` shape with two warmups and five measured
  repetitions for the `L=0` and reduced `L=2` sector views;
- satisfy the exact N=6 CPU admission inequalities
  `compile_seconds + 2*2048*median_action_seconds <= 3600` and
  `peak_RSS <= 51539607552`, without changing the workload algebra,
  precision, or chunk outputs.

The spike uses three elapsed-time checkpoints from the first implementation
edit: cofactor correctness by 30 minutes, JVP small-exact correctness plus an
N=6 compile probe by 60 minutes, and the unchanged batch-512 classification by
90 minutes. A single full-shape warmup may trigger an early RED only when its
measured lower bound already makes the frozen inequality impossible. A GREEN
classification always requires the complete two-warmup, five-measurement
gate. Failure or non-classification at 90 minutes stops deadline work on Route
C; the dense-jet backend is not started automatically.

Only after that N=6 slice is GREEN may the plan label the work `s02c-a03`, run
the actual N=8 batch `256` gate, and begin production integration. This
preserves the a02 journal's stated prerequisite instead of consuming an
attempt on another object-level rewrite.

If the analytic cofactor formula is incorrect, the compiled kernel cannot use
`complex128`, or the final N=6/N=8 gate fails, the result is recorded as a
named Route C backend failure. No approximation or ansatz downgrade is
allowed. Three Route C attempts remain after a02; this design does not change
that count.

## 13. Out of scope until the backend gate passes

- neural descriptor trunk and scalar heads;
- sampler, local energy, optimizer, and training loop;
- checkpoint/freeze receipt;
- N=8 scientific result interpretation;
- ED oracle reveal or comparison;
- protocol capacity, optimizer, sampling, or threshold changes;
- multi-GPU or distributed execution.

## 14. Deliverables for the implementation plan

The next implementation plan must produce, in order:

1. cofactor derivation tests and the pure NumPy reference;
2. the JAX CPU JVP kernel and reduced exact-action tests;
3. compile/steady-state microbenchmark machinery with the 90-minute stop;
4. full N=6 batch-512 backend-admission evidence;
5. only after admission, compatibility and symmetry integration;
6. only after integration remains GREEN, an a03 allocation record and the
   actual N=8 gate;
7. an updated attempt journal stating exactly what passed, failed, or remains
   blocked.

No implementation task may start trainer or ED work before item 6 is GREEN.
