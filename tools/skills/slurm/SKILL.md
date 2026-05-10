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
- *Cell map* (optional) — for array jobs: `results/<run>/run_spec.json` with `cells = [{cell_id, params}]`; the array script maps `$SLURM_ARRAY_TASK_ID` or `HARNESS_CELL_INDEX` → a cell.
- *Ship strategy* (optional) — `git` (default; commit if dirty + push + remote pull) or `rsync` (bypass git for fast iteration).

The array interface is generic: the submitted script receives `HARNESS_RUN_SPEC=<results/run/run_spec.json>` plus either `HARNESS_CELL_ID`, `HARNESS_CELL_INDEX`, or Slurm's `$SLURM_ARRAY_TASK_ID`. The script reads the selected cell's opaque `params` and writes `results/<run>/cells/<cell_id>/manifest.json`. `/slurm` must not parse or hardcode axis names such as `L`, `h`, `U`, `χ`, or `N_S`.

## Workflow

1. **Pre-check**: cluster profile resolves (`tools/cluster/<active>.md`); ssh alias works (`ssh <alias> echo ok`); local git tree state recorded.
2. **Partition selection — probe queue, then ratify with user via Superpowers fork**: before submit, never silently default to the cluster profile's `default-cpu` row. Read the calling skill's resource-class hint (cpu / gpu / high-mem), filter candidate partitions from the profile table, then probe live queue load via `ssh <alias> 'sinfo -o "%P %a %.10l %.6D %.6t"'` (or the cluster profile's status command). Present 2–3 candidates to the user via `AskUserQuestion` — recommended option first, each option with: partition name, current load (idle/mix/alloc/down node counts), cores/memory specs, expected queue wait, one-line pro / con. The user ratifies. Defaults are not free; an idle high-core partition can be a free win, and a congested default-cpu partition can be a hidden multi-hour wait. Per AGENTS.md "warm-clear-concise UX rule".
3. **First-run bootstrap** (only if needed; idempotent):
   - Test if `<repo_path_remote>` exists on cluster. If not, `git clone` per the profile's `bootstrap_one_time` snippet.
   - Test if `<repo>/julia-env/Manifest.toml` is instantiated (use `tools/cli/setup-julia.sh verify <repo>/julia-env <smoke-pkg>` via ssh — exit code 0 means ready). If not, dispatch `/setup-julia --target remote:<alias>` to install Julia (per `bootstrap_one_time`'s module-load or juliaup recipe), configure mirror per profile's `region`, and run `Pkg.instantiate()`.
   - If the cluster's `bootstrap_one_time` declares cluster-specific quirks beyond Julia (license server, depot path, etc.), run them once, write a `~/.harness-bootstrapped` marker on the cluster.
4. **Ship**:
   - `git`: stage and commit if working tree dirty (only with user authorization for this run); `git push origin <branch>`; `ssh <alias> "cd <repo> && git fetch && git checkout <branch> && git pull"`.
   - `rsync`: `rsync -avz --exclude='/results' --exclude='/.git' . <alias>:<repo>/`.
5. **Submit**: `ssh <alias> "cd <repo> && sbatch <script>"` (with the partition picked in step 2). Capture job id. For array jobs, the run spec is rsynced first and `sbatch --array=1-N --export=ALL,HARNESS_RUN_SPEC=<path>,HARNESS_ENTRYPOINT=<script> ...` supplies the generic cell selector.
6. **Monitor**: poll `ssh <alias> "squeue -j <jobid> -h -o '%T %M %R'"`. **Critical first check — settle-time within 1–3 min of submit**: tail at least one cell's log to confirm actual compute is happening, not just "RUNNING" status. Sbatch can start a cell, hit a startup error (wrong PATH, missing module, OOM-at-init, broken sbatch.sh), and exit within seconds — but the cell may briefly show RUNNING before flipping to FAILED/COMPLETED. Catching this early prevents a fire-and-forget failure across the whole grid. Per AGENTS.md "Monitor before declaring success". After the early settle, periodically poll for state transitions (PENDING → RUNNING → COMPLETED/FAILED) and tail one log every 30–60 min for multi-hour jobs.

   **Utilization check (thread-level, NOT process-level)**: when checking "is the job actually using its allocated cores", a single `top` snapshot showing `%CPU = 100` from the process row is **not** a utilization measurement — that's one thread's instantaneous CPU on one core, which a multi-threaded process can saturate even when 7/8 cores are idle. The right inspection on the compute node is:
   - `cat /proc/<pid>/status | grep -E '^(Threads|Cpus_allowed_list)'` — confirms allocated cores AND total thread count.
   - `ps -L -p <pid> -o tid,psr,pcpu,stat` — per-thread CPU breakdown with the `psr` column showing which core each thread is on. If threads are spread across all allocated cores, BLAS / pthread parallelism is working.
   - `top -H -b -n 1 -p <pid>` — live threads view; useful for spotting one runaway thread vs spread parallelism.
   - Aggregate `%CPU` from `top` (which can exceed 100%) is the right scalar: 234% = 2.34 cores worth of work, not 234% of one core.

   For workloads with inherent serial bottlenecks (Markov chains, ED iterative solvers), 100% per-core utilization is unreachable; ~25-50% spread across N allocated cores is normal and is NOT a misconfiguration. Resist the impulse to cancel-and-resubmit based on a single `%CPU = 100` snapshot.
7. **Fetch**: when COMPLETED, `rsync -avz <alias>:<repo>/results/<run>/ results/<run>/`.
8. **Diagnose**: classify exit per cell (success / OOM / walltime / logic / convergence-out-of-budget) using `sacct -j <jobid> --format=JobID,State,ExitCode,MaxRSS,Elapsed`. Surface failures with classification.
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
- **Region** — passed to `/setup-julia` (or other language-setup skills) for mirror defaults.
- **`bootstrap_one_time`** — shell snippet for cluster-specific one-time setup (clone, module load, env setup). Run on first cluster use; marker file `~/.harness-bootstrapped` records completion.
- **Sbatch idioms** — single-cell and array-job templates.
- **Status / queue commands** — `squeue` / `sacct` dialect.

If no profile is found, the skill emits the generic array wrapper without resource directives and surfaces a one-line note recommending `/onboard`'s cluster-setup stage to create one. Resource flags must then be supplied explicitly by the submitter; the skill does not invent partition, node, task, CPU, memory, or wall-clock defaults.

## Output

- Job record: job id, sbatch command, partition, walltime requested, ship strategy, cell count.
- Final job state: COMPLETED / FAILED / TIMEOUT, runtime, peak memory (per cell when array).
- Local results: `results/<run>/` populated from the cluster.
- A 2-3 line report: success/fail counts + path + recommended next step.

## Composition

- `/parameter-scan` calls `/slurm` once with an array of cells when the user is sweeping on a cluster.
- `/reproduce-paper` calls `/slurm` for any cluster step in the figure pipeline.
- `/setup-julia` is dispatched by `/slurm`'s first-run bootstrap when the cluster's `julia-env/Manifest.toml` isn't instantiated yet.
- `/onboard` populates the cluster profile this skill reads.
- Manifest schema is per-method-card convention; the writeup-handoff close in `/reproduce-paper` consumes them at session close.

## Notes

- *Agent-on-laptop, agent-does-ssh* model. The agent runs locally and uses Bash to ssh / rsync / sbatch directly. No cluster-side agent. No MCP server (zero-star supply chain hazard).
- Cluster-agnostic: HPC2 / lab-cluster / cloud-Slurm specifics live in `tools/cluster/<name>.md`, not here.
- For non-Slurm clusters (PBS, LSF), the analog (`/pbs`, `/lsf`) follows the same shape; the cluster profile names the workload manager.
- The skill is *content-agnostic*: it does not know what an axis means or what the script computes. The calling skill (or method card) defines that.
- Do NOT bundle parameter-grid logic here — that lives in `/parameter-scan`. This skill submits whatever sbatch script is handed to it.

## Anti-patterns (auto-reject)

- Asking the user to ssh / sbatch manually when this skill is available.
- Hardcoding HPC2 specifics (partitions, modules, ssh alias) — they belong in the cluster profile.
- Submitting via an unvetted MCP server when `/slurm` (Bash + ssh) suffices.
- Bundling per-cell parameter logic into this skill — that's `/parameter-scan`'s job.
- Silent commits / pushes during the ship step without prior authorization.
