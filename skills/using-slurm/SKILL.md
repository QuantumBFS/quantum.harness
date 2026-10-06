---
name: using-slurm
user-invocable: false
description: Use when a computation needs to run on a remote Slurm cluster (CPU- or GPU-heavy beyond laptop budget), when a multi-cell array job is ready to submit, when a submitted job needs status / monitoring / cancel / log-tail, or when only a few cells failed and the user wants to resume — phrases like "send this to the cluster", "sbatch this", "submit on HPC2", "check job status", "resubmit failed cells".
---

# slurm

Submit and monitor Slurm jobs from the local agent via `ssh`, `rsync`/`git`, `sbatch`, `squeue`, and `sacct`. Mechanism only: no cluster-side agent, no MCP server, no manual user relay.

For parameter grids, compose with `/parameter-scan`. `/parameter-scan` owns cell decomposition; `/using-slurm` submits the resulting job or array.

This skill is agent-facing (harness array sweeps with run-spec manifests). **Students running their own scripts should use `/cluster-jobs`**, which adds preview-and-confirm guardrails on resources, paths, and credentials.

## Binding Rules

<checklist name="binding">
- Pre-checks must pass before submit: readable cluster profile, `ssh <alias> echo ok`, and captured local `git status --porcelain`.
- Dirty worktree shipping requires user authorization. Do not silently commit, push, or rsync user changes.
- Partition choice is ratified after queue probing. Do not blindly use the profile default when alternatives are viable.
- Memory is sized against the partition's per-cpu memory before the job script is written (see **Sizing memory**).
- Pre-submit feasibility is ratified before a real job is left queued.
- The allocation is predicted before submit and checked against `sacct` once tasks run. A mismatch is investigated and explained before any further submission.
- Scheduler state is not scientific evidence. `sbatch` success, `squeue COMPLETED`, and `ssh` exit status do not close reproduction claims; fetched manifests do.
- Array jobs receive an opaque run spec and write one manifest per cell. `/using-slurm` never parses or hardcodes axis names.
</checklist>

## Inputs

- *Script* — sbatch script or compute script plus the active cluster profile's array template.
- *Cluster profile* — `skills/using-slurm/profiles/active.toml` or `HARNESS_CLUSTER_PROFILE=<name>`, providing ssh alias, remote repo path, scheduler idioms, partitions, modules, queue commands.
- *Software stack* — optional stack id/profile from `skills/<stack>/stack.toml`.
- *Cell map* — optional `results/<run>/run_spec.json`.
- *Ship strategy* — `git` or `rsync`.

## Workflow

**The ssh/sbatch/squeue/sacct mechanics are implemented by `scripts/harness_slurm.sh`; drive it rather than typing remote commands by hand.** It hard-codes no cluster specifics — connection comes from the active profile or `--alias`/`--repo` overrides, and `--dry-run` previews any remote command before it leaves the laptop. The *judgment* stays with the agent: which partition (binding rule below), whether to ship a dirty tree, whether to retry a failed cell. Scheduler state is still not evidence — fetched manifests close claims.

```bash
scripts/harness_slurm.sh precheck                       # resolve profile, ssh echo ok, git dirty status
scripts/harness_slurm.sh probe-partitions               # usable partitions + whole-node + per-user caps — agent ratifies the choice
scripts/harness_slurm.sh submit --test-only --script <local-script> \
    --time <t> --cpus <n>                               # local-inspected script, exact scheduler feasibility output
scripts/harness_slurm.sh submit --array N --run-spec results/<run>/run_spec.json \
    --command '<cmd>' --partition <p> --time <t> --cpus <n>   # captures the job id
scripts/harness_slurm.sh status <jobid>                 # squeue state + pending-reason category
scripts/harness_slurm.sh fetch <run>                    # rsync results/<run>/ back
scripts/harness_slurm.sh alloc-check <jobid>            # sacct vs the allocation predicted at submit
scripts/harness_slurm.sh classify <run> <jobid>         # sacct + manifests -> per-cell outcome table
scripts/harness_slurm.sh pending-cells <run> [--success-field F --success-value V]
```

1. **Pre-check.** Resolve profile, test ssh, capture dirty status.
2. **Probe and ratify partition.** Inspect queue state and present 2-3 viable options with recommended first.
3. **Ship.** Use authorized `git` flow or explicit `rsync` so the submitted script exists at its remote path.
4. **Bootstrap only if needed.** Ensure the remote repo and declared stack are usable; dispatch `/setup-julia` only for Julia commands when Julia is not ready.
5. **Pre-submit feasibility.** Size memory first (see **Sizing memory**). After shipping/bootstrap, run the exact request with `harness_slurm.sh submit --test-only ...`. The `--script` path must be a locally readable regular file so the helper can inspect its `#SBATCH` directives before adding command-line defaults. Partition precedence is the last partition option in `--extra`, then dedicated `--partition`, then the script's `#SBATCH --partition`, then `scheduler.default_partition`. The helper adds optional `required_gres` for the effective partition only when neither `--extra --gres` nor the script supplies `#SBATCH --gres`. Print and inspect the scheduler response. Treat QOS/resource rejection as a profile/request mismatch. If the returned estimate is impractically far away, present wait/change/stop and require ratification before leaving a real job queued.
6. **Submit.** Run `sbatch` on the remote repo and capture job id, partition, walltime, and cell count. `submit` first prints the predicted `sacct` allocation (see **Predicted allocation**) and saves it as `results/.slurm/<jobid>.expect.json`; show it with the preview.
7. **Monitor.** Check pending/running transitions, startup logs, and long-run pulses. If the job remains pending or fails at startup, surface choices rather than waiting silently.
8. **Fetch.** On completion, sync `results/<run>/` back locally.
9. **Diagnose.** Use `sacct` plus per-cell artifacts to classify success, OOM, walltime, logic failure, and convergence-out-of-budget.
10. **Hand back.** Print per-cell status table and local results path.

## Cluster Profile

Consult the active profile from `skills/using-slurm/profiles/active.toml` or
`HARNESS_CLUSTER_PROFILE=<name>` before submission. Required fields:

- `ssh.alias`, `repo_path_remote`
- scheduler type and default queue
- partitions table
- login/compute internet availability
- region for mirror defaults
- `bootstrap_one_time`
- sbatch idioms
- queue/status commands

The profile schema lives in `skills/using-slurm/references/cluster-profiles.md`.
Read it before creating or editing a profile.

If no profile exists, emit a generic array wrapper without resource directives
and recommend `/onboard` cluster setup. Do not invent partitions, CPUs, memory,
or walltime.

If a profile exists but the precheck ssh test fails (unresolvable alias,
missing key, never-provisioned credentials), dispatch `/setup-cluster` — its
connection bootstrap owns credential acquisition, guided by the profile's
sibling `profiles/<name>-setup.md` notes. Do not stop at "check ~/.ssh/config",
and do not rebuild the profile.

## Partition Ratification

Probe before choosing:

```bash
ssh <alias> 'sinfo -o "%P %a %.10l %.6D %.6t"'
```

Filter candidate partitions by the calling skill's resource hint: CPU, GPU,
high-memory, multi-node, etc. Present 2-3 real options with:

- partition name
- current load: idle/mix/alloc/down
- cores/memory/GPU specs
- expected queue wait
- one-line pro/con

Recommended first, but alternatives must be real. Submission uses the ratified
partition.

## Sizing memory

Before writing `--mem` / `--mem-per-cpu` into a job, read the partition's
per-cpu memory:

```bash
python3 scripts/cluster_profile.py --partition <p> --field max_mem_per_cpu_mb --profile <profile>
```

Slurm does not reject a request above `cpus × max_mem_per_cpu_mb`; it raises
the cpu count to `ceil(mem / max_mem_per_cpu_mb)` and bills all of them. A
single-threaded cell asking `--mem=3G` on a 2764 MB/cpu partition runs on one
core and pays for two. So:

- Request `--mem ≤ cpus × max_mem_per_cpu_mb` unless the cell really needs more.
- Size from a measured peak (`sacct -j <jid> -o MaxRSS` of a test cell) plus a
  margin, not a round guess.
- If the field is absent, re-probe (`/setup-cluster`) or read
  `scontrol show partition <p>` directly — do not assume it is unlimited.
- In the `--test-only` output, `using N processors` must equal the intended
  cpus per cell; a larger N means memory (or a whole-node policy) is buying cores.

## First-run Bootstrap

Run only when needed:

- Test whether `<repo_path_remote>` exists. If absent, clone or stage according to the profile.
- Inspect the selected stack contract in `skills/<stack>/stack.toml`.
- For `language = "julia"`, ensure Julia is usable first; call `/setup-julia --target remote:<alias>` only when needed.
- Run the stack smoke test in the declared place. `where = "login"` can run by ssh; `where = "compute"` needs a scheduler allocation.
- Apply cluster `bootstrap_one_time` snippets once and write a `~/.harness-bootstrapped` marker.

GPU NetKet or CUDA/JAX device tests are compute-node tests, not login-node tests.

## Shipping

`git` strategy:

1. Capture dirty status.
2. With user authorization, stage/commit/push.
3. Remote: `git fetch`, checkout branch, pull.

`rsync` strategy:

```bash
rsync -avz --exclude='/results' --exclude='/.git' . <alias>:<repo>/
```

Use rsync for fast iteration only when the user understands it bypasses git
history.

## Submit

Single job:

```bash
ssh <alias> "cd <repo> && sbatch <script>"
```

Array job:

- Sync `run_spec.json` first.
- Use `sbatch --array=1-N --export=ALL,HARNESS_RUN_SPEC=<path>,HARNESS_COMMAND='<command>' ...`.
- `HARNESS_ENTRYPOINT=<script>` is a convenience fallback for executable scripts and Julia entrypoints.

## Monitoring Discipline

Settle-time checks are ordered:

1. **Pending to running.** Within 1-3 min after `sbatch`, re-check `squeue -j <jid>`. If still pending, read the reason and surface options.
2. **Startup health.** Within 1-3 min after first `RUNNING`, tail at least one log to confirm actual compute has started, and run `alloc-check <jobid>` (see **Predicted allocation**).
3. **Long-run pulse.** For multi-hour jobs, poll every 30-60 min and tail one log periodically.

Pending reasons:

- `Priority`, `Resources`, `BeginTime` — queued; show queue depth and offer wait/switch/stop.
- `AssocMaxJobsLimit`, `QOSMaxJobsPerUserLimit` — account/quota throttle; waiting may not help.
- `Dependency` — verify dependency exists and is intended.

Do not report "submitted = computing" while a job is pending.

## Utilization Inspection

A process-row `%CPU = 100` in `top` means one core's worth of instantaneous CPU,
not full node utilization. Inspect threads:

```text
cat /proc/<pid>/status | grep -E '^(Threads|Cpus_allowed_list)'
ps -L -p <pid> -o tid,psr,pcpu,stat
top -H -b -n 1 -p <pid>
```

Interpret aggregate `%CPU` as cores worth of work: `234%` is about 2.34 cores. For
serial bottlenecks, partial spread can be normal; do not cancel from one
snapshot.

## Predicted allocation

What `sacct` reports for a job is fixed by the request and the partition
policy, so it is written down before submitting and checked afterwards:

```bash
python3 scripts/cluster_guardrail.py expect <script> [--partition P --time T --cpus N --array 1-N --extra=...]
scripts/harness_slurm.sh alloc-check <jobid>      # after the first task is RUNNING; again after completion
```

`submit` runs `expect` itself. The prediction holds, per task: partition, task count, cpus (including any raised by
memory above `max_mem_per_cpu_mb` or by a whole-node partition), nodes,
memory (`--mem`, or `def_mem_per_cpu_mb × cpus`), time limit, and billing
(one unit per cpu). `alloc-check` compares each started task with it and exits
1 on any difference; after completion it also reports peak RSS as a fraction
of the request.

A mismatch means the scheduler applied a policy the profile does not record,
a profile field is wrong, or the submitted script differs from the one
predicted. Before submitting anything else:

1. Read `scontrol show job <jobid>` and `scontrol show partition <p>` for the
   field that differs (`MaxMemPerCPU`, `DefMemPerCPU`, `OverSubscribe`,
   `TRESBillingWeights`, QOS limits, `JobDefaults`).
2. Name the cause in one line to the user (e.g. "`--mem=3G` above 2764M/cpu →
   2 cpus billed per 1-thread task").
3. Fix the source: lower the request, or correct the profile (re-run
   `/setup-cluster`'s probe). Do not just widen the prediction to match.
4. If the running job wastes allocation, offer cancel-and-resubmit vs let it finish, with the cost of each.

A peak RSS far below the request (`peak_frac` ≪ 1) is not a mismatch, but the
next submission should request less.

## Fetch and Diagnose

After completion:

```bash
rsync -avz <alias>:<repo>/results/<run>/ results/<run>/
sacct -j <jobid> --format=JobID,State,ExitCode,MaxRSS,Elapsed
```

Classify every cell:

```text
cell_id | state | exit-code | maxRSS | elapsed | classification
```

Do not collapse cells of the same class; the calling workflow needs exact
failed cells.

## Array Contract

Every array job receives `HARNESS_RUN_SPEC=<results/run/run_spec.json>` plus one of `HARNESS_CELL_ID`, `HARNESS_CELL_INDEX`, or Slurm's `$SLURM_ARRAY_TASK_ID`. The script reads the selected cell's opaque `params` and writes:

```text
results/<run>/cells/<cell_id>/manifest.json
```

The manifest schema belongs to the calling workflow/method card. `/using-slurm` only submits, monitors, fetches, and classifies operational state.

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

- `/parameter-scan` calls `/using-slurm` once for array sweeps.
- `/reproduce-paper` calls `/using-slurm` through evidence-producing primitives.
- `/onboard` creates the cluster profile this skill reads.
- `/setup-julia` is called only from first-run bootstrap when the submitted command requires Julia and Julia is not usable.

## Anti-patterns

<checklist name="reject">
- Asking the user to ssh or sbatch manually when this skill can do it.
- Hardcoding cluster specifics into this skill.
- Submitting via an unvetted cluster-side service.
- Bundling parameter-grid logic into `/using-slurm`.
- Silent commits, pushes, or broad rsync of dirty local changes.
</checklist>
