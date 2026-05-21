# slurm cluster operations reference

Read for submission, monitoring, resume, or diagnosis. The parent `SKILL.md` carries the binding rules.

## Partition Ratification

Probe before choosing:

```bash
ssh <alias> 'sinfo -o "%P %a %.10l %.6D %.6t"'
```

Filter candidate partitions by the calling skill's resource hint: CPU, GPU, high-memory, multi-node, etc. Present 2-3 real options with:

- partition name
- current load: idle/mix/alloc/down
- cores/memory/GPU specs
- expected queue wait
- one-line pro/con

Recommended first, but alternatives must be real. Submission uses the ratified partition.

## First-run Bootstrap

Run only when needed:

- Test whether `<repo_path_remote>` exists. If absent, clone or stage according to the profile.
- Read the selected stack contract in `tools/software/stacks/*.toml`.
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

Use rsync for fast iteration only when the user understands it bypasses git history.

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
2. **Startup health.** Within 1-3 min after first `RUNNING`, tail at least one log to confirm actual compute has started.
3. **Long-run pulse.** For multi-hour jobs, poll every 30-60 min and tail one log periodically.

Pending reasons:

- `Priority`, `Resources`, `BeginTime` — queued; show queue depth and offer wait/switch/stop.
- `AssocMaxJobsLimit`, `QOSMaxJobsPerUserLimit` — account/quota throttle; waiting may not help.
- `Dependency` — verify dependency exists and is intended.

Do not report "submitted = computing" while a job is pending.

## Utilization Inspection

A process-row `%CPU = 100` in `top` means one core's worth of instantaneous CPU, not full node utilization. Inspect threads:

```bash
cat /proc/<pid>/status | grep -E '^(Threads|Cpus_allowed_list)'
ps -L -p <pid> -o tid,psr,pcpu,stat
top -H -b -n 1 -p <pid>
```

Read aggregate `%CPU` as cores worth of work: `234%` is about 2.34 cores. For serial bottlenecks, partial spread can be normal; do not cancel from one snapshot.

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

Do not collapse cells of the same class; the calling workflow needs exact failed cells.

## Cluster Profile Fields

Read from `tools/cluster/<name>.md`:

- `ssh.alias`, `repo_path_remote`
- scheduler type and default queue
- partitions table
- login/compute internet availability
- region for mirror defaults
- `bootstrap_one_time`
- sbatch idioms
- queue/status commands

If no profile exists, emit a generic array wrapper without resource directives and recommend `/onboard` cluster setup. Do not invent partitions, CPUs, memory, or walltime.
