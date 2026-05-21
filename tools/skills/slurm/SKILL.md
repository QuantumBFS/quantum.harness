---
name: slurm
description: Use when a computation needs to run on a remote Slurm cluster (CPU- or GPU-heavy beyond laptop budget), when a multi-cell array job is ready to submit, when a submitted job needs status / monitoring / cancel / log-tail, or when only a few cells failed and the user wants to resume — phrases like "send this to the cluster", "sbatch this", "submit on HPC2", "check job status", "resubmit failed cells".
---

# slurm

Submit and monitor Slurm jobs from the local agent via `ssh`, `rsync`/`git`, `sbatch`, `squeue`, and `sacct`. Mechanism only: no cluster-side agent, no MCP server, no manual user relay.

For parameter grids, compose with `/parameter-scan`. `/parameter-scan` owns cell decomposition; `/slurm` submits the resulting job or array.

## Binding Rules

<checklist name="binding">
- Pre-checks must pass before submit: readable cluster profile, `ssh <alias> echo ok`, and captured local `git status --porcelain`.
- Dirty worktree shipping requires user authorization. Do not silently commit, push, or rsync user changes.
- Partition choice is ratified after queue probing. Do not blindly use the profile default when alternatives are viable.
- Scheduler state is not scientific evidence. `sbatch` success, `squeue COMPLETED`, and `ssh` exit status do not close reproduction claims; fetched manifests and `flow` checks do.
- Array jobs receive an opaque run spec and write one manifest per cell. `/slurm` never parses or hardcodes axis names.
- This skill does not spawn audit subagents. `/verify` is composed externally when a protocol/result needs audit.
</checklist>

## References

Consult [references/cluster-ops.md](references/cluster-ops.md) when doing anything beyond a simple status check. It contains partition ratification, first-run bootstrap, shipping modes, settle-time checks, utilization inspection, resume semantics, and output format.

## Inputs

- *Script* — sbatch script or compute script plus the active cluster profile's array template.
- *Cluster profile* — `tools/cluster/active.md` or `HARNESS_CLUSTER_PROFILE=<name>`, providing ssh alias, remote repo path, scheduler idioms, partitions, modules, queue commands.
- *Software stack* — optional stack id/profile from `tools/software/stacks/*.toml`.
- *Cell map* — optional `results/<run>/run_spec.json`.
- *Ship strategy* — `git` or `rsync`.

## Workflow

1. **Pre-check.** Resolve profile, test ssh, capture dirty status.
2. **Probe and ratify partition.** Inspect queue state and present 2-3 viable options with recommended first.
3. **Bootstrap only if needed.** Ensure remote repo and declared stack are usable; dispatch `/setup-julia` only for Julia commands when Julia is not ready.
4. **Ship.** Use authorized `git` flow or explicit `rsync`.
5. **Submit.** Run `sbatch` on the remote repo and capture job id, partition, walltime, and cell count.
6. **Monitor.** Check pending/running transitions, startup logs, and long-run pulses. If the job remains pending or fails at startup, surface choices rather than waiting silently.
7. **Fetch.** On completion, sync `results/<run>/` back locally.
8. **Diagnose.** Use `sacct` plus per-cell artifacts to classify success, OOM, walltime, logic failure, and convergence-out-of-budget.
9. **Hand back.** Print per-cell status table and local results path.

## Array Contract

Every array job receives `HARNESS_RUN_SPEC=<results/run/run_spec.json>` plus one of `HARNESS_CELL_ID`, `HARNESS_CELL_INDEX`, or Slurm's `$SLURM_ARRAY_TASK_ID`. The script reads the selected cell's opaque `params` and writes:

```text
results/<run>/cells/<cell_id>/manifest.json
```

The manifest schema belongs to the calling workflow/method card. `/slurm` only submits, monitors, fetches, and classifies operational state.

## Resume

- Re-submit only cells without a success-tagged manifest.
- Failed cells require user ratification before retry.
- If the cell map changes, start a new run id.

## Output

- Job record: job id, sbatch command, partition, walltime, ship strategy, cell count.
- Final job state: completed/failed/timeout, runtime, peak memory per cell when available.
- Local results path: `results/<run>/`.
- Per-cell table: `cell_id | state | exit-code | maxRSS | elapsed | classification`.
- 2-3-line report with success/fail counts and the recommended next step.

## Composition

- `/parameter-scan` calls `/slurm` once for array sweeps.
- `/reproduce-paper` calls `/slurm` through evidence-producing primitives.
- `/onboard` creates the cluster profile this skill reads.
- `/setup-julia` is called only from first-run bootstrap when the submitted command requires Julia and Julia is not usable.

## Anti-patterns

<checklist name="reject">
- Asking the user to ssh or sbatch manually when this skill can do it.
- Hardcoding cluster specifics into this skill.
- Submitting via an unvetted cluster-side service.
- Bundling parameter-grid logic into `/slurm`.
- Silent commits, pushes, or broad rsync of dirty local changes.
</checklist>
