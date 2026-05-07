# Cluster Profiles

Per-cluster profile cards describing the resources, partitions, scheduling idioms, and environment-setup notes needed to drive `/slurm` (and any other cluster-aware skill) without hard-coding cluster specifics into harness skills.

The harness skills are *cluster-agnostic*: they read this folder when they need to pick a partition, a time limit, a sbatch idiom, or a status command. The HPC2-specific facts live in `hpc2.md`; another cluster (HPC3, internal-lab, AWS Slurm, …) lands its own card here. Skills consult the active profile via either:

- environment variable `HARNESS_CLUSTER_PROFILE=<name>` (e.g., `HARNESS_CLUSTER_PROFILE=hpc2`);
- symlink `tools/cluster/active.md → tools/cluster/<name>.md` (preferred when the user wants the choice persisted across sessions).

A skill that needs cluster information reads `active.md` (or the env-var-picked file) and falls back to a built-in minimal-Slurm default if neither is present.

## Profile schema (every card has these sections)

Each card is markdown; skills parse the headers and tables, not free-form prose. The required sections are:

1. **Identity** — cluster name, purpose, who maintains it. One-line form.
2. **Account** — Slurm account name(s) the user has access to, default-account behavior (does `--account` need to be set explicitly, or does an empty value work?).
3. **Partitions** — table of `(name, cores/CPU, memory, max wall, GPU type, notes)`. The skill picks the *default* partition for CPU jobs from the row tagged `default-cpu` (or `default-gpu` for GPU jobs).
4. **Sbatch idioms** — the standard `#SBATCH` directive set for a single-cell job and an array job, with the cluster-specific quirks documented (e.g., array-id env var name, output-file naming).
5. **Status / queue commands** — `squeue` flavor, partition-listing command, accounting commands.
6. **Environment setup** — module-load lines, software stack notes, any cluster-specific setup steps the harness needs (e.g., a project-load on first login, a container path, a Julia depot path).
7. **Filesystem** — home, scratch, and project paths; any quotas the harness should respect; whether `/scratch` exists.
8. **Notes** — anything else a skill might need (group ownership, network egress restrictions, GPU exclusivity rules, etc.).

The schema is *additive*: new fields land as new sections; skills that don't read them ignore them.

## Picking the active profile

| Situation | Recommended action |
|---|---|
| Single-cluster user with one persistent setup | `ln -s hpc2.md tools/cluster/active.md` once; harness reads it forever after. |
| Multi-cluster user (lab + remote HPC) | Set `HARNESS_CLUSTER_PROFILE=<name>` per-shell or in the project `.envrc`; the env var wins over the symlink. |
| First-time user with no profile yet | Skills emit a minimal-Slurm sbatch and surface a one-line note suggesting profile creation. |
| Profile contains secrets (project codes, billing tokens) | Add the file to `.gitignore` locally; commit only public profiles. HPC2's profile here is public — no secrets. |

## Using a profile from a skill

Cluster-aware skills (currently `/slurm`) read the active profile and consult these sections in order:

1. Default partition / time / cores / memory from the partition table.
2. Sbatch idiom (single-cell vs array) — used to construct the submission script.
3. Module-load preamble — emitted at the top of the per-cell script.
4. Status commands — used when polling for job state.

The skill *does not* hard-code anything about HPC2 or any other cluster; it only reads the active profile. If the profile is missing a field the skill needs, the skill emits a minimal default and surfaces a one-line note.

## Authoring a new profile

1. Probe the cluster (run `sinfo`, `squeue`, `scontrol show partition`, `sacctmgr show accounts`, etc.) to fill in the schema.
2. Write `tools/cluster/<name>.md` following the section order above.
3. Test by activating it (`ln -s <name>.md active.md` or set the env var) and running `/slurm` on a tiny grid.
4. If the profile is general-interest, commit it; if it contains secrets, add to `.gitignore` and commit only the schema-shaped sections.

## Cards in this folder

- `hpc2.md` — HPC2 cluster (HKUST(GZ)). CPU-default partition `i64m512u`, no `--account` needed, `julia/1.10.9` module. Public — committed.
