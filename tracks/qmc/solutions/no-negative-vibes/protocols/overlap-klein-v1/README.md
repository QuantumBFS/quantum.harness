# Overlapping Klein cone v1

This preregistered protocol probes the two fixed overlapping four-mode
Klein-Hodge blocks `(0,1,2,3)` and `(2,3,4,5)` on six fermion modes.  The
four cells are the number-conserving and Bogoliubov-de Gennes families crossed
with the two declared support masks in `axes.json`.

For every bridge generator, the runner solves both fixed anchor signs and
replays any numerical witness exactly over `Q(sqrt(2))`.  A result is
`certified-feasible` only when at least one sign has a replaying exact primal
certificate.  It is `certified-zero` only when both signs are numerically
infeasible and the two exact nonnegative dual identities replay.  All other
outcomes are `numerical-only`: this is a diagnostic state, **not a scientific
conclusion**.

The scientific payload is deterministic across worker counts: its anchors are
ordered by bridge label and contain solver diagnostics plus replayable
certificates.  Process count and elapsed wall time are separate `execution`
metadata written by the CLI, so they cannot change the scientific payload.

Before a production run with `workers > 1`, complete and retain a matching
one-worker smoke result for the same family, mask, and source commit.  The
Task 7/8 experiment log is the durable record of that smoke evidence; the
runner intentionally keeps no additional persistent state.

For the production stage, the required worker policy is exactly
`max(1, logical_cpus-2)`.  On Windows, macOS, and Unix-like systems, calculate
the integer with:

```bash
python -c "import os; print(max(1, (os.cpu_count() or 1) - 2))"
```

Use that printed value only after the matching one-worker smoke is recorded.

The CLI fails closed unless all three thread limits are the literal string
`1`: `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, and `OPENBLAS_NUM_THREADS`.  It
records the validated limits and its `spawn` process start method in the
separate `execution` metadata.

First run the one-worker smoke from the solution directory:

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=. \
python -m oracle.overlap_klein \
  --family number-conserving \
  --mask rings-bridges \
  --workers 1 \
  --source-commit 0123456789abcdef0123456789abcdef01234567 \
  --output smoke-result.json
```

After the matching smoke is recorded, repeat the same command with the printed
`max(1, logical_cpus-2)` worker count and a distinct output path.  Use the
source commit of the code being run.  The runner rejects abbreviated or non-hex
provenance and atomically writes sorted UTF-8 JSON.
