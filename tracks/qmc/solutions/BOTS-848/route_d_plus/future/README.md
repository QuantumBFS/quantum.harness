# Route D+ future-stage contracts

This directory is the Phase 6D preparation layer for Phases 7--11.  It contains
only metadata contracts, read-only verifiers, and Slurm resource templates.  It
does not import, open, or execute an ED oracle.

## Contract chain

Every stage uses four immutable JSON documents:

1. `dispatch.schema.json`: a pre-registered task graph.  Every task has a
   distinct relative run directory and immutable prerequisite hashes.
2. `task-certificate.schema.json`: one result envelope per isolated task,
   including source revision, clean-worktree proof, checkpoint/input hashes,
   Slurm GPU evidence, stdout/stderr hashes, and a domain-certificate hash.
3. `stage-gate.schema.json`: the one domain decision for the full stage.  This
   is where Phase 7 may trigger the pre-registered capacity ladder and where
   Phase 8 freezes the selected architecture.
4. `aggregate-certificate.schema.json`: the single readback gate proving that
   the dispatch, exact task set, task certificates, and stage decision agree.

The generic verifier never interprets wavefunctions or ED data.  It validates
the envelopes, hashes the referenced artifacts, checks isolated run
directories, and enforces the dependency graph.  Domain workers and their
domain-specific schemas are added only in the phase that owns them.

## Dependency rules

- Phase 7 requires a passed Phase 6 frozen-checkpoint gate.  Its dispatch must
  contain independent `M=-2..2`, overlap, and operator-span tasks.
- Phase 8 requires the Phase 7 capacity gate.  Its dispatch is valid only when
  that gate requests the pre-registered D+1/D+2 ladder.
- Phases 9, 10, and 11 require the same Phase 8 architecture-freeze artifact.
  They are separate manifests and may run concurrently after that freeze.
- Held-out and beyond-ED outputs are read-only evaluations.  Their stage gate
  must state that the architecture was not changed.

No future-stage script may be submitted before its prerequisite artifact
exists and matches the hash recorded in the dispatch.

The capacity and architecture rules are already frozen in
`phase7-capacity-protocol.json` and
`architecture-freeze-protocol.json`.  Phase 7 classifies D+0 as sufficient
only when the mandatory gap and overlap gates pass, as expression-limited only
when an operator-span ceiling is below its registered overlap target, and as
an optimization failure otherwise.  Only the expression-limited branch may
trigger the concurrently prepared D+1/D+2 runs.  Phase 8 then freezes the
smallest candidate passing every mandatory and internal gate; held-out and
beyond-ED results cannot change this selection.

## Isolated run layout

Given `ROUTE_D_PLUS_RUN_ROOT=/absolute/results/route-d-plus`, a dispatch task
with `run_dir=phase7/m-minus-2` owns only:

```text
/absolute/results/route-d-plus/phase7/m-minus-2/
```

The worker writes `task-certificate.json` there.  The stage gate and aggregate
certificate live under a separate `_gate` directory.  The verifier rejects
absolute task paths, `..`, duplicate directories, mismatched task sets, dirty
source revisions, non-GPU Slurm evidence, and changed prerequisite hashes.

## Resource templates

- `phase7_parallel.sbatch`: one GPU allocation, seven isolated tasks
  (`M=-2..2`, overlap, span ceiling) run with bounded concurrency.
- `phase8_array.sbatch`: one pre-registered D+1/D+2 seed per array element.
- `postfreeze_array.sbatch`: Phase 9, 10, or 11 tasks from separate manifests;
  the three arrays can be submitted concurrently after one architecture freeze.

The scripts require an explicit worker executable.  They run preflight before
the worker and do not supply an ED implementation.  A final aggregation job
must call `python -m route_d_plus.future.verify aggregate`; no individual task
is a phase exit certificate.
