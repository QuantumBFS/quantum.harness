# Gate B report: exact Square primal models and SCNet smoke proposal

Date: 2026-07-28

Branch: `challenge/polyopt-sdp-gap`

Ratified setup: Square J1-J2, `J1=+1`, `g=J2/J1=1/2`, `L=1`, `d=2`,
unrestricted state, no physical boundary condition, structured
`one_symbol_lift/v1` bases, `bare_inner_pauli/v1` stationarity, feasibility
only, `gamma in {0,1/4}`.

## 1. Gate B outcome

**PASS.** Both exact assemblies were generated, converted to optimizer-free
JuMP models, exported to MathOptFormat, reloaded, and structurally checked.
No optimizer was attached and no solve was performed.

Artifact bundle:

```text
tracks/polyopt/solutions/sdp-gap-seekers/results/
  square-primal-gate-b-20260728-r1/
```

The `results` tree is gitignored. The reproducible builder is committed as:

```text
tracks/polyopt/solutions/sdp-gap-seekers/scripts/
  build_square_primal_mof.jl
```

## 2. Shared inventory

Both thresholds have:

| Field | Value |
|---|---:|
| Hamiltonian terms | 60 |
| Real scalar moment variables | 74,602 |
| Normalization equalities | 1 |
| Stationarity candidates including identity/zero | 4 |
| Nonzero canonical real stationarity equalities | 3 |
| Positive Hermitian PSD dimension | 703 |
| Gap Hermitian PSD dimension | 7 |
| Constraint count excluding variable-in-set constraints | 6 |

Shared hashes:

| Inventory | SHA-256 |
|---|---|
| Positive basis | `83befe24c09bccdc7d228fc60c606d301dd76c10688121e1e466d43a583d5c13` |
| Gap basis | `5be3d2db7be104d1bc431898496e8e34116787a7f14a30886fa6933924bea169` |
| Moment inventory | `dec55b4bd9741f19c96945446c3d35acb4308573c487c872249c9be1f2d4c22a` |
| Stationarity candidates | `09f3e5a0ffe77c9812910085875eb2720f939b136d8d59313a4e00618dc0cae9` |
| Stationarity equalities | `6e6d23fbb347dd0e23aa818f02dad91ec8de930c5c7b2f547158a68deb71bbc6` |

The common moment inventory is expected: changing `gamma` changes the affine
coefficients of the gap cone, not the available scalar monomials.

## 3. Threshold-specific identities

### 3.1 `gamma=0`

| Field | Value |
|---|---|
| Problem SHA-256 | `d59e56b342dc519755347dcafee22fd6c16673fad8833982b3c65e4b6c1ca711` |
| Coefficient-map SHA-256 | `aa212b96e857a82fc55ca6a790f2d8777ddd84735b34a9eb6faa82a989541bba` |
| Assembly SHA-256 | `a032c4bc99056e48eede10cf394ad4f5bf81d121f6a6b9b41b88d58ff28c848e` |
| MOF SHA-256 | `191690a197fb3aff1870ee1fee73b0ab3d2cd88fa9e73f623ae9283ba57d76e0` |
| MOF bytes | 24,736,907 |

### 3.2 `gamma=1/4`

| Field | Value |
|---|---|
| Problem SHA-256 | `95695b7699d2bc348cab32f7107a5599b4021b49152f626edce19c0742e915cc` |
| Coefficient-map SHA-256 | `7474a5b80c748dc4419babfe960adf44be9437bbd33a8b2abb868253f5cdeb8a` |
| Assembly SHA-256 | `9e2c5f6550358a82a41e8f122b212b229fd38901f15a21fe4d66ab151861d8b0` |
| MOF SHA-256 | `ea4fc2ffe30caa41ba2cb571fddddec2049df397c5adf5c5cab2cfbdf8f2e4e6` |
| MOF bytes | 24,737,856 |

The different problem, coefficient-map, assembly, and MOF hashes prove that
the threshold entered the actual affine model rather than only the metadata.

## 4. Reload contract checked

For each MOF, a new `JuMP.Model` was constructed by reading the file. The
following conditions passed:

- variable count is exactly 74,602;
- variable names and order are exactly
  `moment[1]` through `moment[74602]`;
- `moment[1]` is the declared identity variable;
- constraint `normalization` exists;
- constraints `stationarity[1]` through `stationarity[3]` exist;
- `positive_psd` is a 703-by-703
  `HermitianPositiveSemidefiniteConeTriangle`;
- `gap_psd` is a 7-by-7
  `HermitianPositiveSemidefiniteConeTriangle`;
- the objective sense is feasibility;
- the total non-variable constraint count is six.

All bundle, runmeta, and MOF checksum ledgers pass `sha256sum -c` when checked
from their declared directories.

This is structural replay through the same JuMP/MOI reader, not an independent
coefficient emitter and not a certificate verification.

## 5. Measured construction cost

The two points were generated in one Julia process.

| Step | `gamma=0` wall | `gamma=1/4` wall |
|---|---:|---:|
| Exact assembly | 2.09 s | 1.95 s |
| JuMP construction | 6.33 s | 5.49 s |
| MOF export | 6.11 s | 0.25 s |
| MOF reload | 6.02 s | 1.76 s |

Peak process resident-set high-water mark:

```text
1,725,176 KiB, approximately 1.65 GiB
```

The first export/reload includes compilation and format warm-up, explaining
most of the difference between the two points.

## 6. Provenance

Builder commit:

```text
0b0f50524f72341152885f5e06c25165f645448c
```

Builder tree:

```text
b1da3ba4aae45d5d54661df35214f76d5dc721ee
```

Runtime:

```text
Julia 1.11.5
JuMP 1.31.1
MathOptInterface 1.51.2
```

The runmeta records the known pre-existing dirty paths:

- modified `Ion.lock`;
- two untracked prior advisor notes.

None is included in the model source-file hash set.

## 7. Gate C raw-status runner

The proposed solver runner:

```text
scripts/solve_square_primal_mof.jl
scripts/square_primal_smoke.sbatch
```

The first job is hard-locked by runmeta validation to:

```text
g=1/2, gamma=0, L=1, d=2, outer sites=9, inner sites=1
```

It:

1. checks the MOF SHA-256 against Gate B runmeta;
2. checks variable and constraint counts;
3. attaches Mosek only after those gates pass;
4. retains raw MOI termination, primal, dual, and raw solver statuses;
5. retains result count, objective availability, solve time, exception and
   stack trace, peak process memory, environment, Slurm job ID, and checksums;
6. labels a normal feasible return only `feasible_candidate`;
7. labels an infeasibility status only
   `infeasibility_candidate_requires_ray_replay`;
8. labels every other status `unknown`.

The runner does not claim that a solver status alone is a certificate.

## 8. Partition probe and recommendation

Live SCNet probe:

| Partition | Relevant live state | Profile capacity | Assessment |
|---|---|---|---|
| `xhacnormalb` | 3 idle, 133 mixed, 158 allocated | CPU, 128 cores, 500 GB | **Recommended.** Correct CPU class; queue may be nonzero. |
| `xhhgnormal` | 30 idle, 22 mixed | GPU, 64 cores, 300 GB, 4 RTX 3080 | More idle nodes, but wastes GPU capacity for a CPU-only SDP. |
| `xhhgnormal02` | 3 idle, 3 mixed | not declared as a selectable profile partition | Do not use without a profile update and resource contract. |

Proposed first request:

```text
partition = xhacnormalb
CPUs      = 16
memory    = 3,800 MB per CPU = 60,800 MB total
walltime  = 00:30:00
points    = gamma=0 only
```

Reasoning:

- Gate B needed 1.65 GiB, but Mosek's real PSD bridge and interior-point
  factorization can be much larger;
- 64 GB is a conservative first bound without occupying a full 500 GB node;
- 16 threads are sufficient for a smoke model and remain below the profile's
  32-CPU soft warning;
- a 30-minute hard limit prevents an unexpectedly difficult first model from
  consuming an open-ended allocation.

`gamma=1/4` must not be submitted until `gamma=0` returns coherently and its
artifacts are fetched and checked.

## 8.1 Operational correction after scheduler preflight

The first preflight used `--mem=64000M` with 16 CPUs. SCNet rejected it because
the account enforces approximately 3,800 MB per requested CPU. Increasing to
17 CPUs made that request valid, but `sbatch --test-only` returned a highly
pessimistic December 2026 estimated start. A 9-CPU/32-GB request returned a
similar estimate. Attempts to use the generic GPU partition were correctly
abandoned because its QOS requires a GPU and the tested GRES requests did not
match an available configuration.

The existing repository already contains the relevant successful operational
contract, which should have been reused first:

- `SESSION_STATUS_2026-07-28.md`, Infrastructure notes;
- `GAP_RUN_PROVENANCE.md`, Section 3;
- successful jobs `22970362` and `22970838`.

That contract is:

```text
partition=xhacnormalb
cpus-per-task=16
mem-per-cpu=3800M
explicit Julia 1.11.5 and Mosek 11.2 environment
direct sbatch from ~/quantum.harness
```

The smoke script now embeds that exact resource and environment pattern.
The December estimate was a scheduler priority/start projection, not evidence
that SSH, repository shipping, Julia, Mosek, or `sbatch` were misconfigured.
Future work should not probe GPU partitions for this CPU-only SDP unless the
known CPU partition actually rejects a real submission.

## 8.2 First real submission and infrastructure-only failure

The exact corrected script was submitted through `harness_slurm.sh`:

```text
job_id   = 22986072
partition = xhacnormalb
CPUs      = 16
memory    = 60,800 MB
walltime  = 00:30:00
```

Despite the preceding `--test-only` projection of December 2026, the real job
started one second after submission:

```text
SubmitTime = 2026-07-28T22:35:10
StartTime  = 2026-07-28T22:35:11
EndTime    = 2026-07-28T22:35:11
```

It failed before the batch script executed:

```text
State    = FAILED
Reason   = JobLaunchFailure
ExitCode = 0:53
Elapsed  = 00:00:00
Node     = a01r06n03
MaxRSS   = unavailable
stdout   = not created
result   = not created
```

This is scheduler/node launch evidence, not a Julia, Mosek, MOF, memory, or
model failure. The assigned node was already heavily shared:

```text
State=MIXED
CPUAlloc=112 of 128
AllocMem=381472M
FreeMem=92700M
```

The appropriate single retry is the identical committed request with:

```text
--exclude=a01r06n03
```

No scientific or solver setting should change. If that retry also produces a
pre-execution `JobLaunchFailure`, stop and treat the cluster launch path as the
blocker rather than repeatedly resubmitting.

## 8.3 Authorized identical retry: launch path blocked

The single authorized retry was submitted with the same committed batch
script and only the failed node excluded:

```text
job_id    = 22986104
partition = xhacnormalb
CPUs      = 16
memory    = 60,800 MB
walltime  = 00:30:00
exclude   = a01r06n03
```

Slurm assigned a different node and again failed before the batch script
executed:

```text
State    = FAILED
ExitCode = 0:53
Elapsed  = 00:00:01
Node     = a01r08n02
stdout   = not created
result   = not created
```

The accounting rows were:

```text
22986104        FAILED     0:53  00:00:01  a01r08n02
22986104.batch  CANCELLED  0:53  00:00:01  a01r08n02
22986104.extern COMPLETED   0:0  00:00:01  a01r08n02
```

This reproduces the pre-execution launch failure on two distinct compute
nodes. In particular, neither attempt loaded Julia, read the MOF, initialized
Mosek, or allocated the SDP. It is therefore not evidence about feasibility,
model correctness, solver stability, runtime, or memory.

### Stop decision

Do not submit a third copy of this SDP job without new evidence. Gate C is
**BLOCKED at the SCNet batch-launch layer**, while Gate B remains passed.

The next action should be one of the following, in order:

1. ask SCNet support/administration to inspect jobs `22986072` and `22986104`
   and the node-side reason for batch launch exit `0:53`;
2. if an infrastructure diagnostic is desired before that response, obtain
   explicit approval for a minimal batch script on `xhacnormalb` using the
   same account/resource pattern but no Julia, Mosek, or model input;
3. after a minimal job executes successfully, resubmit the unchanged
   `gamma=0` smoke job once and inspect its checksum-bound result;
4. do not submit `gamma=1/4` until `gamma=0` has executed and its artifacts
   have passed review.

Changing the scientific model, MOF, Julia/Mosek paths, partition, or memory
request is not justified by the evidence currently available.

## 9. Claim boundary

Gate B proves a deterministic, replayable solver input for the declared
structured relaxation. It does not prove:

- that the relaxation is feasible at either threshold;
- that the physical Square J1-J2 model is gapped;
- an upper bound on the physical bulk gap;
- numerical convergence;
- a Farkas certificate.

Those statements remain forbidden until the corresponding later gates pass.
