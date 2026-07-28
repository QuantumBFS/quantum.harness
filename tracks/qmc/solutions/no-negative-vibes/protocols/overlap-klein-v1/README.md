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

Run one preregistered cell from the solution directory:

```bash
PYTHONPATH=. python -m oracle.overlap_klein \
  --family number-conserving \
  --mask rings-bridges \
  --workers 1 \
  --source-commit 0123456789abcdef0123456789abcdef01234567 \
  --output result.json
```

Use the source commit of the code being run.  The runner rejects abbreviated or
non-hex provenance and atomically writes sorted UTF-8 JSON.
