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
- *Cell map* (optional) — for array jobs: `[{cell_id, params}, ...]`. The skill writes one config file per cell into `results/<run>/cells/<cell_id>/config.json`; the array script maps `$SLURM_ARRAY_TASK_ID` → cell_id.
- *Ship strategy* (optional) — `git` (default; commit if dirty + push + remote pull) or `rsync` (bypass git for fast iteration).

## Workflow

1. **Pre-check**: cluster profile resolves; ssh alias works (`ssh <alias> echo ok`); local git tree state recorded.
2. **Ship**:
   - `git`: stage and commit if working tree dirty (with the user's ratification on the message; don't commit unless the user has authorized this run); `git push origin <branch>`; `ssh <alias> "cd <repo> && git fetch && git checkout <branch> && git pull"`.
   - `rsync`: `rsync -avz --exclude='/results' --exclude='/.git' --exclude='/julia-env' . <alias>:<repo>/`.
3. **Submit**: `ssh <alias> "cd <repo> && sbatch <script>"`. Capture job id. For array jobs, the cell map is rsynced to `results/<run>/cells/` first.
4. **Monitor**: poll `ssh <alias> "squeue -j <jobid> -h -o '%T %M %R'"` periodically. Surface state transitions (PENDING → RUNNING → COMPLETED/FAILED). For long-running cells, optional periodic `tail` of one cell's log to confirm progress.
5. **Fetch**: when COMPLETED, `rsync -avz <alias>:<repo>/results/<run>/ results/<run>/`.
6. **Diagnose**: classify exit per cell (success / OOM / walltime / logic / convergence-out-of-budget) using `sacct -j <jobid> --format=JobID,State,ExitCode,MaxRSS,Elapsed`. Surface failures with classification.
7. **Hand back**: job record + local results path + per-cell status table.

## Resume semantics

- Re-running on a partial array: only cells *without* a `success`-tagged manifest are re-submitted (manifest path: `results/<run>/cells/<cell_id>/manifest.json`).
- Cells tagged `failed` are *not* automatically retried — the user ratifies the retry. (Avoids wasting compute on logic errors.)
- The cell map is durable per run id; if cells change, the user starts a new run id.

## Cluster profile (what the skill reads)

- `ssh_alias` — the ssh config alias for the cluster login node (e.g., `hpc2`).
- `repo_path_remote` — where the harness checkout lives on the cluster.
- `default_partition` — e.g., `i64m512u`. The skill bumps if a method-card runtime estimate exceeds the partition's max.
- `default_walltime` — starting wall-clock; bumped per estimated cell wall.
- `array_template` — sbatch idiom for array jobs (`#SBATCH --array=...`, `$SLURM_ARRAY_TASK_ID`).
- `module_preamble` — lines emitted at the top of every per-cell script (e.g., `module load julia/1.10.9`).
- `status_commands` — the dialect for `squeue` / `sacct` if the cluster wraps them.
- `filesystem_notes` — whether `/scratch` exists; where results should land.

If no profile is found, the skill emits a *minimal-Slurm* sbatch (single node, single task, 1-day wall, no module loads) and surfaces a one-line note recommending profile creation.

## Output

- Job record: job id, sbatch command, partition, walltime requested, ship strategy, cell count.
- Final job state: COMPLETED / FAILED / TIMEOUT, runtime, peak memory (per cell when array).
- Local results: `results/<run>/` populated from the cluster.
- A 2-3 line report: success/fail counts + path + recommended next step.

## Composition

- `/parameter-scan` calls `/slurm` once with an array of cells when the user is sweeping on a cluster.
- `/reproduce-paper` calls `/slurm` for any cluster step in the figure pipeline.
- Manifest schema is per-method-card convention; `/run-report` consumes them at session close.

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
