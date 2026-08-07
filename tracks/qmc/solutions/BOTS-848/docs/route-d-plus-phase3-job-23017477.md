# Route D+ Phase 3 job 23017477

## Outcome

Slurm job `23017477` received immediate V100 backfill on node `v01r03` but
failed at the leading Ruff gate after three seconds. Pytest and the Phase 3
certificate did not run.

## Identity

- Code revision: `30042502e0450dec6a1ef6bf554a25bc50908d95`
- Run ID: `route-d-plus-phase3-20260730-01`
- Phase 2 certificate SHA-256:
  `a3c81299666a738b0602e0a3cee94918890cf68adbc7fded09994a00720bec40`
- Slurm state and exit code: `FAILED`, `1:0`
- Runtime and node: three seconds, `v01r03`

## Diagnosis

Ruff reported one `UP033` finding in `route_d_plus/tensor.py`: Python 3.11
provides `functools.cache`, which should replace
`lru_cache(maxsize=None)`.

The run directory contains no certificate, so this job provides no numerical
tensor-algebra evidence.

## Correction

Replace only the cache decorator and import, commit and deploy the clean
revision, then repeat the exact remote V100 gate under a fresh run ID.
