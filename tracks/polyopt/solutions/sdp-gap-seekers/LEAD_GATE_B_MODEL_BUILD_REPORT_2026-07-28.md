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

**Historical diagnosis, superseded by Section 8.4 below.**

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

## 8.4 Corrected launch diagnosis and application handoff

The infrastructure-blocked conclusion in Sections 8.2–8.3 was provisional and
is now superseded. The missing `results/` output directory was the cause of
the pre-execution failures. Slurm opens a batch job's configured stdout/stderr
paths before executing the script, so the script's own later `mkdir` could not
repair the path.

The controlled evidence is:

| Job | Node | Result | Meaning |
|---|---|---|---|
| `22986463` | `a01r02n04` | safe-path diagnostic `COMPLETED 0:0` with `OK` output | basic batch launch was healthy |
| `22986467` | `a01r02n04` | bad-output-path reproduction `FAILED 0:53`, batch `CANCELLED 0:53`, no output | reproduced the original path failure on the same healthy node |
| `22986474` | `a01r08n05` | real batch ran 56 seconds and exited `1:0` | pre-creating `results/` allowed the application to execute |

Job `22986474` passed the input SHA-256 checks, validated the Gate B metadata,
read the MOF, and reached solver attachment. It then stopped before
`optimize!` because the runner passed a `Mosek.Iparam` enum where JuMP 1.31.1
requires a raw string or MOI optimizer attribute:

```text
MethodError: set_attribute(::Model, ::Iparam, ::Int64)
```

Commit `634f113` makes both fixes durable:

- Slurm stdout/stderr initially target the existing submission directory and
  are moved into the run bundle after its directory is created;
- the thread parameter uses raw attribute name `MSK_IPAR_NUM_THREADS`;
- a mock-optimizer regression test covers attribute installation.

The full Julia suite passes:

```text
573 passed, 0 failed, 0 errored
```

There is still no feasibility evidence: job `22986474` never called
`optimize!`. The next permitted scientific action is one corrected
`gamma=0` smoke submission from commit `634f113` or a documentation-only
descendant. `gamma=1/4` remains gated on review of that result.

## 8.5 First corrected solve: measured memory gate

The corrected runner was submitted from documentation descendant `dee16cc`:

```text
job_id    = 22986777
partition = xhacnormalb
CPUs      = 16
memory    = 60,800 MB
walltime  = 00:30:00
node      = a01r06n07
```

All setup gates passed. The job:

1. created and retained stdout/stderr inside its run bundle;
2. verified the MOF, runmeta, and input checksum ledger;
3. recorded exact source commit `dee16cc4de938624f4e17ce590af8dd327d1063f`;
4. validated the Gate B metadata and read the MOF;
5. attached Mosek with 16 threads;
6. reached the explicit `optimize! started` marker.

The compute cgroup then killed Julia for memory exhaustion:

```text
Slurm state       = OUT_OF_MEMORY
Slurm exit        = 0:125
batch elapsed     = 00:01:17
requested memory  = 60,800 MB
solver exit       = 137
result.toml       = absent because the Julia process was killed
```

Slurm explicitly reported:

```text
Detected 1 oom-kill event(s) in StepId=22986777.batch
```

The recorded `MaxRSS=1,781,264 KiB` is not a credible peak for this event: it
is a coarse Slurm sample from a process that was killed during a large
allocation. The cgroup OOM state, exit 137, and `slurmstepd` message are the
authoritative evidence.

The surviving bundle was fetched to:

```text
results/square-primal-smoke-22986777/
```

Every file listed in its partial `SHA256SUMS` ledger verifies. No result
classification is possible, because the solver did not return.

### Memory-resized retry

Commit `2efd932` changes only operational resources and hard-kill artifact
handling:

```text
CPUs             = 64
memory per CPU   = 3,800 MB
total memory     = 243,200 MB
walltime         = 01:00:00
Mosek threads    = 64
```

The scientific point, MOF, exact assembly, solver, and status policy are
unchanged. A fourfold memory request is justified because the 60.8 GB cgroup
was exhausted immediately after interior-point optimization began, while the
703-dimensional complex PSD block and 74,602 scalar variables make the
factorization cost substantially larger than Gate B construction.

The batch script now also writes a checksum-bound `result-missing.txt` marker
if a hard-killed solver produces no `result.toml`, instead of failing its
artifact-ledger step on the absent file.

Submit this resized gamma-zero point once. If 243.2 GB also OOMs, stop before
requesting the full 486.4 GB node and inspect formulation/bridge sparsity and
Mosek memory diagnostics. `gamma=1/4` remains gated.

## 8.6 The 243.2 GB gate also OOMs

The memory-resized job was:

```text
job_id    = 22986943
source    = 4dc3a322a83963ed43315fc42d0a1b5616324363
CPUs      = 64
ReqMem    = 237.50 GiB, 243,200 MB
node      = a01r05n08
elapsed   = 00:02:36
```

It again passed all input gates, attached Mosek, and reached
`optimize! started`. Slurm then reported:

```text
State       = OUT_OF_MEMORY
ExitCode    = 0:125
batch MaxRSS = 231,682,520 KiB, approximately 220.95 GiB
solver exit = 137
```

Unlike the coarse measurement from job `22986777`, this peak is close enough
to the 237.50 GiB cgroup limit to establish that the solver path genuinely
needs more than the 243.2 GB allocation in its current form.

The complete hard-kill bundle was fetched to:

```text
results/square-primal-smoke-22986943/
```

Its `result-missing.txt` and all other entries in `SHA256SUMS` verify. There is
still no returned solver status or feasibility evidence.

### Formulation diagnostic before any larger allocation

Do not proceed directly to 128 CPUs/486.4 GB. Commit `8bd21a8` instruments the
same model at the MOI/Mosek boundary:

- explicitly copies the bridged JuMP model into the Mosek task before calling
  `optimize!`;
- records scalar variables, linear constraints, scalar-matrix nonzeros,
  semidefinite block dimensions/nonzeros, attach wall time, and RSS in
  checksum-bound `preopt.toml`;
- flushes Mosek's own log incrementally to checksum-bound `mosek.log`;
- forces `MSK_IPAR_INTPNT_SOLVE_FORM=MSK_SOLVE_DUAL`, which is the candidate
  lower-memory form when the bridged model has many more affine PSD rows than
  free scalar moments;
- leaves the exact MOF, scientific setup, feasibility target, and status
  policy unchanged.

The helper was exercised against a real locally constructed Mosek task without
optimizing. The full suite passes:

```text
576 passed, 0 failed, 0 errored
```

Run this instrumented dual-form diagnostic once at the same 243.2 GB limit.
If model attachment itself OOMs, the MOI bridge/encoding is the target for
redesign. If attachment completes but the dual interior point still OOMs, use
the retained task dimensions and Mosek log to decide between basis reduction,
block/chordal structure, or a larger machine. Do not infer that a 486.4 GB
retry is sufficient without this evidence.

## 9. Claim boundary

Gate B proves a deterministic, replayable solver input for the declared
structured relaxation. It does not prove:

- that the relaxation is feasible at either threshold;
- that the physical Square J1-J2 model is gapped;
- an upper bound on the physical bulk gap;
- numerical convergence;
- a Farkas certificate.

Those statements remain forbidden until the corresponding later gates pass.
