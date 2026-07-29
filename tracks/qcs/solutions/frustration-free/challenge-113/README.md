# Challenge 113: frustration-free sim-to-real control

This directory contains the pinned JAX implementation, restartable artifact
store, paired analysis, publication figures, and guarded production runners for
Challenge 113. Generated outputs belong under `results/` and are never tracked.

## Local verification and development

```bash
uv sync --frozen --group dev
uv run python -m pytest -q
bash scripts/run_development.sh
uv run python run.py validate --output results/development
```

The development runner explicitly selects JAX CPU with x64 enabled and writes
only to `results/development`. Override the device only by setting
`CHALLENGE113_JAX_PLATFORM` to the exact platform expected from JAX.

## Production safety gate

Local production requires a clean checkout, an exact revision match, an
explicit JAX platform, and acknowledgement:

```bash
CHALLENGE113_ACK_PRODUCTION=1 \
CHALLENGE113_EXPECTED_REVISION="$(git rev-parse HEAD)" \
CHALLENGE113_JAX_PLATFORM=cpu \
bash scripts/run_production.sh
```

The production plan contains 9,500 canonical trials. `run.py sweep` also
accepts `--shard-index I --shard-count N`; each shard binds the complete plan
but runs only positions whose canonical zero-based index is congruent to `I`
modulo `N`. Task 8 claims and atomic publication make retries restartable.

## Cluster gate

`scripts/calibrate_pilot.py` measures the representative two-qubit, 80-parameter
setup with a bounded 20–100-query sample. `scripts/slurm_pilot.sh` runs one full
budget-2,000 representative trial. Only after that artifact validates should
`scripts/slurm_production_array.sh` be submitted with an explicitly measured
array concurrency and resource class:

```bash
sbatch --array=0-9499%CONCURRENCY \
  --account=ACCOUNT --qos=QOS --partition=PARTITION \
  --export=ALL,CHALLENGE113_ACK_PRODUCTION=1,CHALLENGE113_DEPLOYMENT=DEPLOYMENT,CHALLENGE113_RUN_ROOT=RUN_ROOT,CHALLENGE113_EXPECTED_REVISION=REVISION,CHALLENGE113_UV=UV \
  scripts/slurm_production_array.sh
```

Deploy only `git archive` output from a committed revision, add a
`.source-revision` file containing that revision, and use a revision/run-ID
output directory shared by all array elements. The deployment and output paths
are runtime inputs and are intentionally not committed.
