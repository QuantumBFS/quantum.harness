# Lead review of the SCNet submission runbook

Date: 2026-07-28

Reviewed file:

```text
tracks/polyopt/solutions/sdp-gap-seekers/notes/scnet-job-submission.md
```

Relevant failed jobs:

```text
22986072  FAILED  0:53  a01r06n03  elapsed 00:00:00
22986104  FAILED  0:53  a01r08n02  elapsed 00:00:01
```

## Updated conclusion after commit `75d9b14`

The worker's new root-cause diagnosis is **credible and independently
supported**. The two original jobs failed because their Slurm output path was
under the gitignored `results/` directory, which did not exist when Slurm tried
to open stdout before executing the batch script. This supersedes the earlier
provisional diagnosis of a scheduler/node problem.

The word **fixed** needs qualification:

- the SCNet working tree was operationally repaired by pre-creating
  `results/`, and job `22986474` consequently entered the batch script;
- the durable output-path fix is not committed:
  `square_primal_smoke.sbatch` still declares
  `#SBATCH --output=results/slurm-square-primal-%j.out`;
- the application error exposed by `22986474` is correctly diagnosed in the
  runbook but is not fixed in source:
  `solve_square_primal_mof.jl` still passes a `Mosek.Iparam` enum to
  `JuMP.set_optimizer_attribute`.

Thus the submission-layer diagnosis is fixed on the current remote checkout,
but a fresh checkout remains vulnerable and the gamma-zero smoke solve has not
started.

The earlier observation that the SCNet working checkout was at `0bfd019` is
not evidence about its state when the failed jobs were submitted: the worker
updated the checkout afterward. At submission time, however, the working
checkout had already been fast-forwarded to `032df92`. That commit contains
the current smoke batch
script, its proven resource request, and all required Julia/Mosek environment
settings. The commits between `032df92` and `0bfd019` only record launch
results and add operational notes; they do not change the solver or batch
script. Therefore, being behind those later note commits could not cause the
observed launch failure.

## Independent evidence for the updated diagnosis

SCNet accounting and artifacts were checked directly:

| Job | Test | Node | Result | Interpretation |
|---|---|---|---|---|
| `22986463` | minimal diagnostic with stdout/stderr in the existing submit directory | `a01r02n04` | `COMPLETED`, `0:0`; complete `start`/`finish`/`OK` output | the partition, node and basic batch-launch path work |
| `22986467` | worker's missing-output-directory reproduction | `a01r02n04` | job `FAILED 0:53`; batch `CANCELLED 0:53`; extern `COMPLETED 0:0`; no output | reproduces the original signature on the same node that had just completed the safe diagnostic |
| `22986474` | real gamma-zero batch after `results/` was created | `a01r08n05` | ran for 56 seconds and exited `1:0` | Slurm opened stdout and executed the application |

Job `22986474` produced a normal log and result bundle. It:

1. printed the script start marker and compute hostname;
2. passed `model.mof.json`, `runmeta.toml`, and `SHA256SUMS` checks;
3. validated the Gate B input;
4. loaded the MOF;
5. reached Mosek attachment;
6. then raised
   `MethodError: set_attribute(::Model, ::Iparam, ::Int64)`.

Its result binds the expected inputs:

```text
MOF SHA-256      = 191690a197fb3aff1870ee1fee73b0ab3d2cd88fa9e73f623ae9283ba57d76e0
assembly SHA-256 = a032c4bc99056e48eede10cf394ad4f5bf81d121f6a6b9b41b88d58ff28c848e
problem SHA-256  = d59e56b342dc519755347dcafee22fd6c16673fad8833982b3c65e4b6c1ca711
moment count     = 74602
```

This evidence is sufficient to reverse the old infrastructure-blocked
decision. One audit improvement remains: future controlled reproductions
should preserve the exact `sbatch` command or override ledger, because Slurm
accounting alone does not record that `22986467` was submitted with the
deliberately bad output path.

The `0:53` pattern should not be documented as globally unique to a missing
output directory. It is decisive here because of the same-node A/B diagnostic
and the successful post-creation run, but future `0:53` cases should still
check the configured stdout/stderr paths rather than infer the cause solely
from the numeric status.

## Runbook checks against the failed submissions

| Runbook requirement or trap | Assessment |
|---|---|
| Push to the bare repository and then update the working checkout | Important. The working checkout was explicitly updated to `032df92` before submission, which was sufficient for the submitted script. The worker later advanced it further. |
| Copy ignored `.external/SpectralGap` code separately | Not applicable to this job. The direct Square primal runner reads the exported MOF and does not call `.external/SpectralGap`. |
| Copy and verify ignored model artifacts | Satisfied before submission. The Gate B artifact bundle was copied to the SCNet working tree and its `gamma=0` checksum was checked there. |
| Submit from `~/quantum.harness` | Satisfied. `harness_slurm.sh` executes `cd ~/quantum.harness && sbatch ...`. |
| Use `xhacnormalb` and the proven CPU/memory request | Satisfied: 16 CPUs and `3800M` per CPU on `xhacnormalb`. |
| Set explicit Julia and Mosek paths | Satisfied by the committed batch script. A login-node load check also found Julia 1.11.5, JuMP 1.31.1, Mosek 11.2.0, and MosekTools 0.15.10. |
| Protect unset `LD_LIBRARY_PATH` under `set -u` | Satisfied with `${LD_LIBRARY_PATH:-}`. |
| Do not infer success from queue state | Satisfied. Final `sacct` rows and absence of output/result files were checked. |
| Account for buffered Julia output | Not relevant to these failures. No Slurm output file was created and the batch step was cancelled at launch, before Julia could start or buffer output. |
| Expect intermittent SSH failures and retry once | Relevant to monitoring reliability, but not to the Slurm failures. Each `sbatch` returned a valid job ID; the later `0:53` states came from Slurm accounting. |

## Wrapper versus direct submission

For this plain batch script, the wrapper's effective remote operation is:

```text
cd ~/quantum.harness &&
sbatch --exclude=<optional-node> --export=ALL \
  tracks/polyopt/solutions/sdp-gap-seekers/scripts/square_primal_smoke.sbatch
```

That is materially the same launch path as the runbook's direct `sbatch`
example. `--export=ALL` is normal and does not explain a batch step that never
starts. The second attempt excluded the first failed node and reproduced the
same exit `0:53` on a different node.

## Remaining requirements

The minimal diagnostic gate has passed. Do not submit it again.

Before the next gamma-zero smoke:

1. make the output-path fix durable in
   `scripts/square_primal_smoke.sbatch`; stdout/stderr must initially target
   the already-existing submission directory, not a gitignored directory that
   the script itself intends to create;
2. change the thread setting in `scripts/solve_square_primal_mof.jl` to a JuMP
   attribute form accepted by JuMP 1.31.1 and MosekTools 0.15.10; the direct
   raw-parameter form is:

   ```julia
   JuMP.set_optimizer_attribute(
       model,
       "MSK_IPAR_NUM_THREADS",
       options.threads,
   )
   ```

   Do not leave the current `Mosek.MSK_IPAR_NUM_THREADS` enum form in place.
3. add or update a regression check that exercises optimizer attachment and
   thread-attribute installation, not merely option parsing;
4. update the Gate B report's Sections 8.2 and 8.3 so they no longer identify
   SCNet as blocked and instead record the confirmed missing-output-directory
   cause plus jobs `22986463`, `22986467`, and `22986474`;
5. push the code commit to the SCNet bare repository, pull the SCNet working
   checkout explicitly, and verify the remote script hashes;
6. submit exactly one unchanged `gamma=0` scientific point;
7. fetch and checksum the complete result bundle and Slurm output;
8. classify raw MOI/Mosek statuses conservatively; job `22986474` contains no
   feasibility evidence because `optimize!` was never reached;
9. do not launch `gamma=1/4` until the corrected gamma-zero result is reviewed.

## Lead implementation status

Requirements 1–3 above were completed in:

```text
634f113 square-gap: fix SCNet smoke launch and Mosek threads
```

The batch script now opens stdout/stderr in the submission directory and moves
both open files into the run bundle after creating it. The solver uses the raw
string attribute `MSK_IPAR_NUM_THREADS`. A mock-optimizer regression test
checks that the attribute is installed with the requested integer value and
rejects a nonpositive thread count.

Verification:

```text
bash syntax check: passed
Julia suite:        573 passed, 0 failed, 0 errored
```

Requirements 4–9 remain the execution and evidence gate.
