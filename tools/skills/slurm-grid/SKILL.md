---
name: slurm-grid
description: Use when the user wants to submit an embarrassingly-parallel parameter grid (e.g., `(L, parameter)` cells) to a Slurm cluster, collect outputs, and resume on partial completion. Generic over the grid axes; pairs with `/run-stage` for per-cell stages.
---

# slurm-grid

Submit a parameter grid to a Slurm cluster, collect per-cell outputs, and resume on partial completion. Each grid cell is a stage executed via `/run-stage`. Generic over the grid axes (sizes, parameter values, sample sizes, …).

## Existing-skill survey

Before authoring this primitive from scratch, the registry was searched (`ion search slurm`, `ion search grid`, `ion search submitit`). The relevant prior art:

- General-purpose `slurm` skills (e.g., `michaelrizvi/claude-config/skills/slurm`, `uchicago-dsi/ai-sci-skills/skills/slurm`, `kdkyum/slurm-skills/slurm-info-summary`, `heshamfs/materials-simulation-skills/slurm-job-script-generator`) cover sbatch scripting, queue inspection, and cluster discovery — useful as *executors*, but they are not parameter-grid orchestrators.
- `heshamfs/materials-simulation-skills/parameter-optimization` covers DOE / Latin-hypercube sampling for materials simulations — adjacent but optimization-focused, not grid-with-resume.
- No registry skill found that ties (i) a parameter grid to (ii) a method-card-declared stage list with (iii) resume-on-partial-completion semantics. The closest patterns are scattered across the skills above.

This primitive therefore composes existing slurm-script-generation skills (when installed) with the harness's `/run-stage` manifest mechanism. If the user has a preferred sbatch generator installed, this skill calls into it; otherwise it emits a minimal sbatch.

## When to activate

- User has a `(L, parameter)` (or higher-dimensional) grid to evaluate.
- The harness is on a Slurm-equipped cluster and the calculation is embarrassingly parallel (each cell independent).
- A previous grid run was interrupted and the user wants to resume only the failed / missing cells.

## Inputs

- *Grid axes* — list of named axes with their value lists (e.g., `L: [16, 32, 64, 128]`, `h: [0.8, 0.9, 1.0, 1.1, 1.2]`).
- *Per-cell pipeline* — a method-card-declared stage list (consumed by `/run-stage`), or a single executable command.
- *Slurm config* — partition, time limit, memory, cpu/gpu count per cell. Defaults consulted from the active cluster profile (`tools/cluster/active.md` symlink, or env var `HARNESS_CLUSTER_PROFILE=<name>` → `tools/cluster/<name>.md`); the calling skill / user overrides per-cell. See "Cluster profile" below for the convention.
- *Run root* — `results/<run>/` (the grid root).

## Cluster profile

The skill itself is *cluster-agnostic*. Cluster-specific defaults (partition, time, sbatch idiom, status commands, module preamble) live in the active profile under `tools/cluster/`. The skill reads the profile at submission time and does not hard-code any cluster's specifics.

Resolution order:

1. Env var `HARNESS_CLUSTER_PROFILE=<name>` → read `tools/cluster/<name>.md`.
2. Symlink `tools/cluster/active.md` → read its target.
3. Neither present → emit a *minimal-Slurm* sbatch (single node, single task, 1-day wall, no module loads) and surface a one-line note recommending profile creation. See `tools/cluster/README.md` for the schema.

What the skill reads from the profile:

- **Default partition** (the row tagged `default-cpu`, or `default-gpu` if the calling pipeline requires GPU).
- **Default time limit** (the profile's recommended starting wall-clock; the skill bumps if a method-card runtime estimate exceeds it).
- **Sbatch idioms** — single-cell and array-job templates, including the env-var name for the array index (typically `$SLURM_ARRAY_TASK_ID`).
- **Module-load preamble** — emitted at the top of every per-cell script.
- **Status / queue commands** — used during the Monitor step.
- **Filesystem notes** — whether `/scratch` exists, where results should land. The skill respects the profile's filesystem rules.

If the user is on a non-Slurm cluster (PBS, LSF, local-only), the same orchestrator applies once a corresponding profile is authored; the schema in `tools/cluster/README.md` is workload-manager-agnostic but currently tested only against Slurm.

## Workflow

1. **Plan**: enumerate the cells (Cartesian product of axes). Plan output: `results/<run>/grid.plan.json` listing cell ids and their parameter assignments.
2. **Resume detection**: walk `results/<run>/cells/` and identify completed cells via their manifest files. Build the *to-run* set (cells with no manifest, or manifest tagged `failed`).
3. **Submit**: emit one sbatch array job per partition, with each array index mapped to one cell. Each array element invokes `/run-stage` on the per-cell stage list, writing into `results/<run>/cells/<cell_id>/`.
4. **Monitor**: poll `squeue` (or use `--wait` if the user prefers blocking). Surface job-state transitions as compact status lines.
5. **Collect**: once all cells complete, walk `results/<run>/cells/*/` and assemble a single `results/<run>/grid.csv` with `(axis_1, axis_2, …, observable, uncertainty, runtime, status)` rows.
6. **Diagnose**: count `success` vs `failed` cells. For failures, surface the failure-mode classification (per `/run-stage`'s classification: transient / logic / OOM / convergence-out-of-budget). Offer a *retry-failed-only* re-run.
7. **Hand back** the assembled `grid.csv` to the calling skill (or `solve`).

## Output

- `results/<run>/grid.plan.json` — the plan.
- `results/<run>/cells/<cell_id>/...` — per-cell artifacts (managed by `/run-stage`).
- `results/<run>/grid.csv` — assembled table.
- `results/<run>/grid.report.md` — short status report (cell counts, runtime totals, failure classes).

## Resume semantics

- Re-running on a partially complete grid root: only cells *without* a `success`-tagged manifest are re-submitted.
- Cells tagged `failed` are *not* automatically retried — the user must ratify the retry. (Avoids wasting compute on logic errors.)
- The plan file is immutable per run id; if axes change, the user starts a new run id.

## Composition

- Each cell calls `/run-stage` to walk the method-card-declared stage list. The per-cell pipeline is therefore generic over what the calculation is.
- After completion, the `grid.csv` is the standard input to `/scaling-fit` for finite-size collapse.
- For cluster-specific defaults (partition, time, sbatch idiom, modules), the skill reads `tools/cluster/<active>.md`; for cluster discovery / sbatch script-generation skills installed via Ion, the active profile defers to whichever generator the user has if it is named in the profile.
- Common follow-ups (offered via `AskUserQuestion`):
  - `/scaling-fit` (Recommended when the grid was a `(L, parameter)` collapse target).
  - `/run-report` — assemble the writeup.
  - Retry-failed — re-submit only the failed cells.
  - Done.

## Notes

- This skill is *content-agnostic*: it does not know what an axis means physically. The calling skill (and the method card it cites) defines that.
- This skill is also *cluster-agnostic*: HPC2 / lab-cluster / cloud-Slurm specifics live in `tools/cluster/<name>.md`, not here.
- The manifest mechanism is shared with `/run-stage`; this skill does not invent a parallel format.
- For non-Slurm clusters (PBS, LSF, local-only), the same orchestrator applies once a corresponding cluster profile is authored.
- The genericness gate (Phase-2): this primitive composes for any embarrassingly-parallel grid in the harness — energy vs `(U/t, doping)`, gap vs `(L_y, J2/J1)`, magic vs `(L, h)`, etc. It is not magic-paper-specific.
