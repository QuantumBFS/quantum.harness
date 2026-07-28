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

## Conclusion

The runbook is useful and should be followed for future SCNet work, but it
does **not** presently identify a mistake that explains these two failures.
Both failures remain most consistent with a Slurm/node batch-launch problem.

The current SCNet working checkout being at `0bfd019` is not evidence about
its state when the failed jobs were submitted: the worker updated the checkout
afterward. At submission time, however, the working checkout had already been
fast-forwarded to `032df92`. That commit contains the current smoke batch
script, its proven resource request, and all required Julia/Mosek environment
settings. The commits between `032df92` and `0bfd019` only record launch
results and add operational notes; they do not change the solver or batch
script. Therefore, being behind those later note commits could not cause the
observed launch failure.

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

## Requirements for the next diagnostic

Do not change the scientific model or submit another full SDP merely because
the runbook is now available. The next diagnostic should isolate Slurm launch
from the application:

1. create a minimal tracked batch script using `xhacnormalb`, a short
   walltime, and a small valid CPU/memory request;
2. make it run only shell built-ins or standard commands such as `hostname`,
   `date`, and `env`, with explicit start and finish markers;
3. push the commit to the SCNet bare repository and explicitly update the
   SCNet working checkout;
4. verify the local and remote script SHA-256 values;
5. submit it directly with `sbatch` from `~/quantum.harness`;
6. retain the job ID, `sacct` row, stdout, stderr, and exact remote commit;
7. if it also fails with `0:53`, stop and give jobs `22986072`, `22986104`,
   and the diagnostic job to SCNet support;
8. if it executes successfully, retry the unchanged `gamma=0` smoke once,
   then verify the checksum-bound result before considering `gamma=1/4`.

Submitting this diagnostic is an external compute action and should only be
done after explicit user approval.
