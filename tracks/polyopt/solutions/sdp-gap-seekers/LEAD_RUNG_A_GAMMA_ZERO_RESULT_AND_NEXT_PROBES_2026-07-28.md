# Square J1-J2 Rung A gamma-zero result and next probes

Date: 2026-07-28

Decision: the Rung A gamma-zero sanity gate passed. Proceed to one modest
positive threshold, `gamma=1/4`, and review it before submitting the
deliberately high `gamma=2` probe.

This note is both the result review and the requirements packet for the next
two Rung A jobs.

## 1. Executed model

SCNet job `22987727` used the committed implementation at:

```text
commit = ea07011a6705b62d0efde1d2918b59c1b284cfbc
host   = a01r04n02
```

The checksum-bound input was:

```text
model             = Square J1-J2 Heisenberg
J1                = +1 antiferromagnetic
g=J2/J1           = 1/2
L                 = 1
outer / inner     = 9 / 1 sites
d                 = 2
state class       = unrestricted
positive basis    = bare_weight_one/v1, dimension 28
gap basis         = bare_weight_one/v1, dimension 4
stationarity      = bare_inner_pauli/v1, 3 nonzero real equalities
gamma             = 0
moments           = 352
Hamiltonian terms = 60
target            = feasibility only
```

Input identities:

```text
problem SHA-256 =
  0943a4f7c3786e927f71e5f122c5256ced291fed08f5ea1c884eb59f92f7f687

assembly SHA-256 =
  4ffed703ab3d84660bf03fd5bf7f524ec0bd697560f304b9cb5a08de863125a5

MOF SHA-256 =
  fda495a30aca5f662131331fc42c20a0a5fd0e8074a719659ba43be6b8aff84c

input runmeta SHA-256 =
  d83ac627d25302521b9eb21ade600af6abb174d27110ad7b42ad4bec1f863d16
```

The SCNet copy passed the parent and point checksum ledgers before submission.
The fetched `input-runmeta.toml` is byte-identical to the final local source
runmeta.

## 2. Raw result

The Slurm allocation completed normally:

```text
job state       = COMPLETED
job exit code   = 0:0
solver exit     = 0
allocated CPUs  = 4
requested memory= 15,200 MB
Slurm elapsed   = 00:01:06
Slurm batch RSS = 573,916 KiB
```

The solver result was:

```text
termination = OPTIMAL
raw status  = Mosek.MSK_SOL_STA_OPTIMAL
primal      = FEASIBLE_POINT
dual        = FEASIBLE_POINT
has values  = true
has duals   = true
result count= 1
classification = feasible_candidate
```

Timing and process measurements:

```text
MOI-to-Mosek attachment       = 6.011 s
optimize! wall                = 1.535 s
Mosek-reported solve          = 0.283 s
solver-script total wall      = 25.295 s
peak /proc process RSS        = 672,996 KiB
peak /proc RSS after attach   = 574,892 KiB
```

The Slurm and `/proc` RSS counters use different accounting and differ by
about 99 MiB. The conservative conclusion is simply that observed memory
stayed below 0.7 GiB, far below the 15.2-GB request.

Mosek received:

```text
scalar variables       = 352
linear constraints     = 4
affine conic constraints= 2
affine conic rows      = 1,632
semidefinite blocks    = 2 after scalarization
```

The interior-point solve took three iterations after iteration zero. Its last
logged feasibility measures were:

```text
PFEAS = 2.4e-13
DFEAS = 2.4e-13
GFEAS = 1.2e-16
```

The reported objective is exactly zero. The dual objective is
`-1.88e-13`. The generic relative-gap getter returns approximately
`1.88e-3`; that ratio is not a useful diagnostic for a zero-objective
feasibility problem. The raw feasibility measures and decisive status are the
relevant evidence here.

## 3. Artifact verification

Fetched result directory:

```text
results/square-rung-a-smoke-22987727
```

Every file listed in its `SHA256SUMS` passed locally:

- `result.toml`;
- `preopt.toml`;
- `mosek.log`;
- copied input runmeta and input checksum ledger;
- harness commit and git status;
- environment;
- solver exit code;
- provisional Slurm accounting.

The final external `sacct` query also reported `COMPLETED|0:0`. The batch
script necessarily captured provisional accounting while it was still
running, so terminal accounting is documented in this note rather than
claimed to be inside the original checksum ledger. The Slurm stdout/stderr
files are also outside that ledger because they remain open until the batch
script exits. Do not describe the entire directory as cryptographically
sealed; describe the files named by `SHA256SUMS` as verified.

## 4. Scientific interpretation

The gamma-zero sanity gate passed.

This is the expected consistency result: the exact tiny relaxation, MOF
serialization/reload, remote transport, JuMP-to-Mosek bridge, solver
invocation, and result capture all work end to end. It also shows that the
previous OOM was specific to the much larger conic formulation rather than a
general Square-model or cluster failure.

This does **not** establish:

- a positive lower bound on the Square bulk gap;
- a physical infinite-volume state reconstructed from the pseudo-moments;
- an upper bound on the gap;
- a certified numerical theorem.

At gamma zero, feasibility is only a sanity result.

The solve requested `MSK_IPAR_INTPNT_SOLVE_FORM=MSK_SOLVE_DUAL`, and the
preopt metadata records that request. The final Mosek log nevertheless says
`solved problem: the primal` for this tiny presolved instance. This does not
change the feasibility status, but it means this run must not be cited as
evidence that the solve-form parameter always forces the logged form. The
larger-model OOM diagnosis should continue to rely on its own raw log.

## 5. Next thresholds and rationale

The next probes keep every physical and relaxation choice fixed.

### Modest probe: gamma=1/4

`gamma=1/4` is the previously ratified first positive threshold and is modest
on the `J1=1` energy scale. It also makes comparison with the original Gate B
point direct.

Submit this point first and stop for review after it reaches a terminal state.

### High probe: gamma=2

`gamma=2` is deliberately high on the same normalization and is intended only
to test whether this very weak relaxation ever becomes infeasible at a
clearly separated threshold. It is not a claimed physical scale estimate.

Submit it only if the `gamma=1/4` job:

- uses the intended checksum-bound input;
- reaches a decisive raw solver status;
- produces a fetched and verified result bundle;
- exhibits no formulation or numerical failure.

## 6. Implementation requirements for positive probes

The builder may be extended to export exactly:

```text
gamma = 0, 1/4, 2
```

under a new immutable bundle ID. Existing `r1` and job `22987727` must remain
unchanged.

The solver launch must add an explicit expected-gamma contract, compared
against the canonical rational string in runmeta before MOF reload or solver
attachment. Expected family and dimensions remain mandatory.

The reusable Rung A batch script must:

- accept only an explicit whitelist of point label/canonical-gamma pairs;
- reject missing, unknown, or mismatched pairs before reading the model;
- include the point label in the run-directory name;
- retain the 4-CPU, 15.2-GB, 10-minute request;
- preserve the existing result, preopt, Mosek log, source, environment, exit,
  and checksum artifacts.

Required whitelist:

```text
gamma-0     <-> 0//1
gamma-0p25  <-> 1//4
gamma-2     <-> 2//1
```

Tests must cover expected-gamma parsing and rejection of a mismatched
canonical gamma. The final solver-free bundle must independently reload all
three MOFs and pass both checksum levels before it is copied to SCNet.

## 7. Status semantics for the next results

- `gamma=1/4` or `gamma=2` feasible: no lower-bound claim; the selected
  finite relaxation is simply too weak to exclude that threshold.
- Decisive infeasible status: candidate upper-gap exclusion at that threshold,
  but not yet certified.
- Any infeasible point requires exported dual/ray data and independent replay
  before calling it a reliable gap upper bound.
- Unknown, numerical error, time limit, exception, or gamma-zero inconsistency:
  stop and diagnose rather than bracket.

If `gamma=1/4` is feasible and `gamma=2` is decisively infeasible, the next
step is a coarse bracket within `[1/4,2]`. If both are feasible, do not scan
blindly upward; first determine whether the Rung A constraints admit an
analytic or numerical unbounded-in-gamma pseudo-moment construction. If
`gamma=1/4` is already infeasible, verify its witness before probing lower
thresholds.
