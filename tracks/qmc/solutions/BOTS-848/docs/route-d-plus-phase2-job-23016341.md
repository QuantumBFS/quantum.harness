# Route D+ Phase 2 job 23016341

## Outcome

Slurm job `23016341` ran on one V100 node in `xhhgnormal02` and failed before
the Phase 2 tests or certificate executed because the leading Ruff gate found
nine static violations.

## Submission identity

- Git revision: `eb7209a69f34ac1ea51815eb5b40610a1573a9ae`
- Phase 1 manifest SHA-256:
  `eabc1a4d3fae12e2fbbe7f54813acb83102495bd6004b7ab30b390d9b6cdecc6`
- Phase 2 batch SHA-256:
  `e2c405b79825d5c68cf348fff022905ec3046cc49cfc688cfdd63e7f8626598b`
- Partition and accelerator: `xhhgnormal02`, one V100 16 GiB
- Resources: two CPUs, 6 GiB memory, five-minute limit
- Run ID: `route-d-plus-phase2-20260730-01`

## Scheduler result

```text
JobId=23016341
JobState=FAILED
Reason=NonZeroExitCode
ExitCode=1:0
RunTime=00:00:05
StartTime=2026-07-30T09:41:05
EndTime=2026-07-30T09:41:10
NodeList=v01r03
```

## Diagnosis

Ruff reported:

- `EXE001` for shebangs on two non-executable Python modules;
- `UP035` for importing `Sequence` from `typing`;
- `UP022` for explicit stdout and stderr pipes instead of
  `capture_output=True`;
- `I001` for three import-block formatting violations.

The batch script uses `set -e`, so Ruff's exit status stopped the job before
pytest or `route_d_plus.certify_phase2`. The run directory contains no
certificate. This failure therefore provides no numerical evidence about the
LLL implementation.

## Correction

Apply only the reported static corrections, commit and deploy a clean
revision, then repeat the exact V100 request with a fresh run ID. Project code,
Ruff, and pytest remain remote-only.
