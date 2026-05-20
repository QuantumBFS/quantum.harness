---
name: slurm
description: Use when the agent needs to ship code, submit a Slurm job (single or array), monitor it, and fetch results — all from the local laptop via Bash + ssh + rsync. Generic over what is submitted; reads cluster specifics from `tools/cluster/<active>.md`. Pure mechanism — for parameter sweeps compose with `/parameter-scan`.
---

# slurm

Submit a Slurm job to a remote cluster from the local agent. Mechanism only — agent does ssh / rsync / sbatch / squeue / sacct itself via Bash. No cluster-side agent, no MCP server, no manual user relay.

For parameter sweeps that map onto an array of cells, compose with `/parameter-scan` (which handles the per-cell decomposition; this skill submits the resulting array job).

## When to activate

- A computation has been authored locally and needs cluster compute (CPU- or GPU-heavy beyond laptop budget).
- A multi-cell array job has been planned and the agent needs to submit + track + fetch.
- A previously-submitted job needs status / monitoring / cancel / log-tail.
- Resume on a partial run (re-submit only failed cells).

## Inputs

- *Script* — path to an sbatch script (or a compute script + the array template `tools/cluster/<active>.md` provides).
- *Cluster profile* — auto-resolved from `tools/cluster/active.md` symlink or `HARNESS_CLUSTER_PROFILE=<name>` env var. Profile provides ssh alias, default partition, modules, sbatch idiom, queue commands.
- *Software stack* (optional) — stack id and profile from `tools/software/stacks/*.toml` chosen by the calling method card, such as `itensors:cpu`, `sse:cpu_mpi`, or `netket:gpu`.
- *Cell map* (optional) — for array jobs: `results/<run>/run_spec.json` with `cells = [{cell_id, params}]`; the array script maps `$SLURM_ARRAY_TASK_ID` or `HARNESS_CELL_INDEX` → a cell.
- *Ship strategy* (optional) — `git` (default; commit if dirty + push + remote pull) or `rsync` (bypass git for fast iteration).

The array interface is generic. **Every** array-job script the calling skill hands to `/slurm` receives `HARNESS_RUN_SPEC=<results/run/run_spec.json>` plus either `HARNESS_CELL_ID`, `HARNESS_CELL_INDEX`, or Slurm's `$SLURM_ARRAY_TASK_ID`. **Every** such script reads the selected cell's opaque `params` and writes `results/<run>/cells/<cell_id>/manifest.json`. `/slurm` MUST NOT parse or hardcode axis names.

## Workflow

1. **Pre-check** — three binary items, **all** MUST pass before continuing:

   <checklist name="precheck">
   - (a) `tools/cluster/active.md` symlink resolves to a readable cluster profile file.
   - (b) `ssh <alias> echo ok` exits 0 within 10 s.
   - (c) `git status --porcelain` output is captured to the job record (empty → clean ship; non-empty → user authorization REQUIRED before ship).
   </checklist>
2. **Partition selection — probe queue, then ratify with user via Superpowers fork.** NEVER silently default to the cluster profile's `default-cpu` row. Defaults are not free; an idle high-core partition can be a free win, and a congested default-cpu partition can be a hidden multi-hour wait. Per AGENTS.md "warm-clear-concise UX rule".

   - **2a. Probe.** Run `ssh <alias> 'sinfo -o "%P %a %.10l %.6D %.6t"'` (or the cluster profile's status command).
   - **2b. Filter.** Read the calling skill's resource-class hint (cpu / gpu / high-mem) and filter candidate partitions from the profile's partitions table.
   - **2c. Surface options.** User-facing fork → [AGENTS.md → Output norms](../../../AGENTS.md#ui-ux) (AskUserQuestion; 2–3 options; recommended first; Done always real). Skill-specific per-option payload: partition name, current load (idle/mix/alloc/down node counts), cores/memory specs, expected queue wait, one-line pro/con.
   - **2d. Ratify.** The user clicks; submission uses the ratified partition.

   <example name="partition bad">
   Submitting to default-cpu...
   </example>

   <example name="partition good">
   Pick a partition (Recommended first):
   - default-cpu (Recommended) — 64 cores, 256 GB, idle 4 / mix 12 / alloc 18, ~5 min wait. Pro: matches the profile's default. Con: shared with the lab's running grid.
   - high-throughput — 32 cores, 128 GB, idle 14 / mix 6 / alloc 4, ~0 min wait. Pro: idle now, fastest start. Con: half the cores per node.
   - gpu-share — 16 cores + 1 A100, 64 GB, idle 1 / mix 0 / alloc 0, ~0 min wait. Pro: free GPU. Con: only one job at a time.
   </example>
3. **First-run bootstrap** (only if needed; idempotent):
   - Test if `<repo_path_remote>` exists on cluster. If not, `git clone` per the profile's `bootstrap_one_time` snippet.
   - Read the selected stack contract when one is supplied. For `language = "julia"`, ensure Julia is usable first (`/setup-julia --target remote:<alias>` if needed), then run the stack profile's install command. For non-Julia stacks, run the declared install command or hand off to the language setup primitive if one exists.
   - Run the stack profile's smoke test in the declared place. `where = "login"` can run by ssh before submit; `where = "compute"` must run through a small scheduler allocation. GPU NetKet is compute-only: do not test CUDA/JAX devices on the login node.
   - If the cluster's `bootstrap_one_time` declares cluster-specific quirks (license server, module load, depot/cache path, etc.), run them once, write a `~/.harness-bootstrapped` marker on the cluster.
4. **Ship**:
   - `git`: stage and commit if working tree dirty (only with user authorization for this run); `git push origin <branch>`; `ssh <alias> "cd <repo> && git fetch && git checkout <branch> && git pull"`.
   - `rsync`: `rsync -avz --exclude='/results' --exclude='/.git' . <alias>:<repo>/`.
5. **Submit**: `ssh <alias> "cd <repo> && sbatch <script>"` (with the partition picked in step 2). Capture job id. For array jobs, the run spec is rsynced first and `sbatch --array=1-N --export=ALL,HARNESS_RUN_SPEC=<path>,HARNESS_COMMAND='<command>' ...` supplies the generic cell selector and command. `HARNESS_ENTRYPOINT=<script>` remains a convenience fallback for executable scripts and Julia entrypoints.
6. **Monitor**: poll `ssh <alias> "squeue -j <jobid> -h -o '%T %M %R'"`. Scheduler / `ssh` exit status ≠ evidence — see [AGENTS.md → Audit dispatch](../../../AGENTS.md#audit-dispatch) and [Output norms → Monitor before declaring success](../../../AGENTS.md#ui-ux). Skill-specific settle-time discipline below.

   - **6a. Settle-time layered checks** — three binary items, in order:

   <checklist name="settle">
   - **PENDING → RUNNING transition (1–3 min after `sbatch`).** Re-check `squeue -j <jid>`: state must be `R` (or `CG` cleaning-up if the job was instantaneous). If still `PD`, read the reason in parentheses (see PD-reason table below) and surface to the user.
   - **Startup health (1–3 min after first observed `R`).** Tail at least one cell's log to confirm actual compute is happening, not just "RUNNING" status. Sbatch can start a cell, hit a startup error (wrong PATH, missing module, OOM-at-init, broken sbatch.sh), and exit within seconds — the cell briefly shows `R` before flipping to `FAILED` / `COMPLETED`. Catching this early prevents a fire-and-forget failure across the whole grid.
   - **Long-run pulse (every 30–60 min for multi-hour jobs).** Poll state transitions (RUNNING → COMPLETED / FAILED / TIMEOUT) and tail one log periodically. Surface progress to the user via short status lines, not silence.
   </checklist>

   PD-reason table:
   - `PD (Priority)` / `PD (Resources)` / `PD (BeginTime)` → job is queued behind others. Surface this to the user immediately with the queue depth from `squeue -p <partition> -t PD | head -10`. The user chooses to wait or switch partitions (re-enter step 2). DO NOT silently let a PD job sit while pretending compute has started.
   - `PD (AssocMaxJobsLimit)` / `PD (QOSMaxJobsPerUserLimit)` → account / quota throttle. Surface immediately; cannot be unstuck by waiting.
   - `PD (Dependency)` → another job must complete first. Verify the dependency is real.

   <example name="pd bad">
   sbatch returned 0, job 41273 submitted ✓
   </example>

   <example name="pd good">
   Job 41273 submitted but currently PENDING (Resources): 14 jobs ahead of it on default-cpu. Choose: wait, switch to gpu-share (idle), or stop.
   </example>

   Settle-time scales with how far the job has to go before producing meaningful output:

   | job class | first check | second check | pulse |
   |---|---|---|---|
   | env setup / install / single ssh | tail output live | silence > 30 s → suspect | n/a |
   | single-cell sbatch (< 1 h wall) | PD → R within 1–3 min | first log line within 1–3 min of R | n/a |
   | array job / multi-hour sbatch | PD → R within 1–3 min | first log line per cell within 1–3 min of R | every 30–60 min |

   The cost of these checks is minutes; the cost of skipping them is the entire wall budget if the job stalls in `PD` or aborts at startup.

   - **6b. Utilization inspection (thread-level, NOT process-level).** A single `top` snapshot showing `%CPU = 100` from the process row is NOT a utilization measurement — that's one thread's instantaneous CPU on one core, which a multi-threaded process can saturate even when 7/8 cores are idle. The right inspection on the compute node:

   <checklist name="utilization">

   | command | what it answers | how to read it |
   |---|---|---|
   | `cat /proc/<pid>/status \| grep -E '^(Threads\|Cpus_allowed_list)'` | allocated cores AND total thread count | `Cpus_allowed_list` matches Slurm's cpu binding; `Threads` ≥ number of allocated cores |
   | `ps -L -p <pid> -o tid,psr,pcpu,stat` | per-thread CPU breakdown | `psr` shows which core each thread is on; spread across allocated cores → BLAS / pthread parallelism is working |
   | `top -H -b -n 1 -p <pid>` | live threads view | spotting one runaway thread vs spread parallelism |

   </checklist>

   **Rule: aggregate `%CPU` from `top` (which can exceed 100%) is the right scalar.** `234%` = 2.34 cores worth of work, not 234% of one core.

   For workloads with inherent serial bottlenecks, 100% per-core utilization is unreachable; partial spread across allocated cores can be normal and is NOT automatically a misconfiguration. Resist the impulse to cancel-and-resubmit based on a single `%CPU = 100` snapshot.
7. **Fetch**: when COMPLETED, `rsync -avz <alias>:<repo>/results/<run>/ results/<run>/`.
8. **Diagnose**: classify exit per cell (success / OOM / walltime / logic / convergence-out-of-budget) using `sacct -j <jobid> --format=JobID,State,ExitCode,MaxRSS,Elapsed`. Render a per-cell status table with columns `cell_id | state | exit-code | maxRSS | elapsed | classification`. Print the table; DO NOT collapse cells of the same class.
9. **Hand back**: job record + local results path + per-cell status table.

## Resume semantics

- Re-running on a partial array: only cells *without* a `success`-tagged manifest are re-submitted (manifest path: `results/<run>/cells/<cell_id>/manifest.json`).
- Cells tagged `failed` are *not* automatically retried — the user ratifies the retry. (Avoids wasting compute on logic errors.)
- The cell map is durable per run id; if cells change, the user starts a new run id.

## Cluster profile (what the skill reads)

Schema is declared in `tools/cluster/README.md`. This skill consults:

- **Connection**: `ssh.alias`, `repo_path_remote`.
- **Scheduler**: `scheduler.type` (only `slurm` for this skill), `scheduler.default_queue`.
- **Partitions table** — picks the row by `class` (`default-cpu`, `gpu`, `high-mem`, …) per the calling skill's resource-class hint.
- **Network**: `internet.from_login` (decides `git clone` vs pre-staged tarball ship), `internet.from_compute` (decides whether package install can happen during a job).
- **Region** — passed to the relevant language-setup skill for mirror defaults.
- **`bootstrap_one_time`** — shell snippet for cluster-specific one-time setup (clone, module load, env setup). Run on first cluster use; marker file `~/.harness-bootstrapped` records completion.
- **Sbatch idioms** — single-cell and array-job templates.
- **Status / queue commands** — `squeue` / `sacct` dialect.

If no profile is found, the skill emits the generic array wrapper without resource directives and surfaces a one-line note recommending `/onboard`'s cluster-setup stage to create one. Resource flags must then be supplied explicitly by the submitter; the skill does not invent partition, node, task, CPU, memory, or wall-clock defaults.

## Output

- Job record: job id, sbatch command, partition, walltime requested, ship strategy, cell count.
- Final job state: COMPLETED / FAILED / TIMEOUT, runtime, peak memory (per cell when array).
- Local results: `results/<run>/` populated from the cluster.
- A 2-3 line report: success/fail counts + path + recommended next step.

<example name="final bad">
Job 41273 finished with 9 successes and 3 failures. Results are at results/run-A/. Suggest investigating the failed cells.
</example>

<example name="final good">
Run-A: 9/12 cells succeeded, 3 failed (OOM at L=32). Results: results/run-A/. Next: increase --mem to 64G and resubmit failed cells via /slurm resume run-A.
</example>

## Composition

**Callers** (descriptive — who calls `/slurm`):

- `/parameter-scan` calls `/slurm` once with an array of cells when the user is sweeping on a cluster.
- `/reproduce-paper` calls `/slurm` for any cluster step in the figure pipeline.
- `/onboard` populates the cluster profile this skill reads.

**Composition rules** (prescriptive — how `/slurm` composes with others):

- `/slurm` dispatches `/setup-julia` from its first-run bootstrap ONLY when the submitted command requires Julia AND the profile/check reports the environment is not ready. No speculative installs.
- Software-stack installs are driven by `tools/software/stacks/*.toml`: the profile is user-visible runtime intent (CPU, GPU, multi-process CPU, multi-node GPU), while install strategies are implementation details. `/slurm` reads the declared stack contract; it does not invent stack names.
- Manifest schema is per-method-card convention; the writeup-handoff close in `/reproduce-paper` consumes them at session close. `/slurm` does NOT define the manifest schema.

## Notes

- *Agent-on-laptop, agent-does-ssh* model. The agent runs locally and uses Bash to ssh / rsync / sbatch directly. No cluster-side agent. No MCP server (zero-star supply chain hazard).
- This skill does NOT spawn subagents — the main agent drives ssh / sbatch directly per the agent-on-laptop model. `/verify` may be composed externally for protocol audits.
- Cluster-agnostic: HPC2 / lab-cluster / cloud-Slurm specifics live in `tools/cluster/<name>.md`, not here.
- For non-Slurm clusters (PBS, LSF), the analog (`/pbs`, `/lsf`) follows the same shape; the cluster profile names the workload manager.
- The skill is *content-agnostic*: it does not know what an axis means or what the script computes. The calling skill (or method card) defines that.
- DO NOT bundle parameter-grid logic here — that lives in `/parameter-scan`. This skill submits whatever sbatch script is handed to it.

## Anti-patterns (auto-reject)

<checklist name="reject">
- Asking the user to ssh / sbatch manually when this skill is available.
- Hardcoding HPC2 specifics (partitions, modules, ssh alias) — they belong in the cluster profile.
- Submitting via an unvetted MCP server when `/slurm` (Bash + ssh) suffices.
- Bundling per-cell parameter logic into this skill — that's `/parameter-scan`'s job.
- Silent commits / pushes during the ship step without prior authorization.
</checklist>

<example name="silent bad">
git tree is dirty — let me commit and push, then submit the job.
</example>

<example name="silent good">
Local tree has 3 modified files. Ship strategy: commit + push? (options: commit-and-push, rsync-bypass-git, abort)
</example>
