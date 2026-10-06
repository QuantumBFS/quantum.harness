# Cluster Profiles

Per-cluster profile describing **generic remote-execution conventions** — ssh access, scheduler, partitions, filesystem, internet reach, region, and the student safety **limits** — needed to drive `/using-slurm`, `/cluster-jobs`, and any other cluster-aware skill without hard-coding cluster specifics into harness skills. Language-specific setup (Julia, Python, R, …) is *not* in this schema; that's `/setup-julia`, `/setup-python`, etc., which read this profile and apply language-specific recipes downstream.

**One unified file per cluster, in TOML.** Each cluster (HPC2, HPC3, internal-lab, AWS Slurm, …) gets its own `skills/using-slurm/profiles/<name>.toml`. The harness reads it through one parser — `scripts/cluster_profile.py` — so skills never parse TOML by hand. `harness_slurm.sh` shells out to that parser for the few fields it needs; Python code imports it.

Skills consult the active profile via either:

- environment variable `HARNESS_CLUSTER_PROFILE=<name>` (→ `<name>.toml`);
- symlink `skills/using-slurm/profiles/active.toml → <name>.toml` (preferred when the user wants the choice persisted across sessions).

A skill that needs cluster information resolves the active profile (`cluster_profile.resolve_profile_path`) and falls back to a built-in minimal-Slurm default if neither is present.

## Profile schema (TOML tables)

The schema is **additive**: new fields land as new keys/tables; parsers that don't read them ignore them. Required anchors (`cluster_profile.validate` warns if absent): `[identity]`, `[connection]`, `[scheduler]`.

| Table | Keys | Purpose |
|---|---|---|
| `[identity]` | `name`, `purpose`, `maintainer` | One-line who/what. |
| `[connection]` | `repo_path_remote` | Where the harness checkout lives on the cluster. |
| `[connection.ssh]` | `alias`, `host`, `user`, `identity_file`, `port` | ssh handle + the source-of-truth fields to reconstruct `~/.ssh/config`. The harness uses `alias` as the handle. |
| `[scheduler]` | `type` (`slurm`/`pbs`/`lsf`/`none`), `default_partition` | How jobs are submitted. |
| `[[partitions]]` | `name`, `class`, `cores`, `memory`, `max_wall`, `gpu`, `required_gres`, `whole_node`, `def_mem_per_cpu_mb`, `max_mem_per_cpu_mb`, `qos`, `user_caps` | Array of partition rows — only partitions the user's accounts can submit to. `class` (`default-cpu`, `gpu`, `long-gpu`, `high-mem`, `debug`, `long-cpu`, `emergency`, `preemptible`) is how skills pick, not by name. `cores` / `memory` are the largest node type. `required_gres` is an optional exact Slurm GRES request imposed by partition/QOS. `whole_node = true` means a job gets entire nodes whatever it asks for (site policy or `OverSubscribe=EXCLUSIVE`), so `/cluster-jobs` counts `nodes × cores`. `def_mem_per_cpu_mb` / `max_mem_per_cpu_mb` are Slurm's `DefMemPerCPU` / `MaxMemPerCPU` in MB — the partition's own value, else the cluster-wide one (many sites set them only per partition). A job asking for more than `cpus × max_mem_per_cpu_mb` is not rejected: Slurm raises its cpu count to fit and bills every one. `qos` is the partition QOS; `user_caps` (inline table: `max_cpus`, `max_nodes`, `max_gpus`, `max_jobs`, `max_submit`, `max_wall`) are the per-user limits that QOS enforces. |
| `[[partitions.node_types]]` | `cores`, `memory`, `gpu`, `features`, `nodes` | Present when one partition mixes hardware. `features` are the Slurm node features a job selects with `--constraint`; the guardrail uses them to count the cores of the node type a constrained job lands on. |
| `[filesystem]` | `home`, `scratch`, `project`, `quota` | Paths + whether `/scratch` exists. |
| `[network]` | `internet_from_login`, `internet_from_compute` | Booleans controlling ship strategy + in-job installs. |
| `[region]` | `region` (`mainland_china` / blank) | Downstream mirror defaults. |
| `[limits]` | see below | **Student safety ceilings** (consumed by `/cluster-jobs` via `cluster_guardrail.py`). |
| `[[documentation]]` | `url`, `documents` | Array of every relevant docs sub-page (login, scheduler, partitions, modules, filesystem, network). Built by `/setup-cluster`'s docs crawl; the table is the spec, not a fallback. |
| `[[gotchas]]` | `symptom`, `cause`, `fix` | Harness-side issues not explicit in cluster docs (e.g., non-interactive ssh not sourcing `/etc/profile`; two `sbatch` binaries). |
| `[bootstrap]` | `one_time` (multi-line string) | Cluster-specific first-checkout quirks; idempotent. |
| `[sbatch]` | `single`, `array` (multi-line templates), `array_id_var`, `output_pattern` | Submission idioms. |
| `[commands]` | `squeue`, `sacct`, `sinfo`, `quota_command` | Scheduler-flavor + the optional read-only allocation/quota probe `/cluster-jobs` runs at setup. |
| `[notes]` | `text` | Anything else (group ownership, GPU exclusivity, egress). |

Language-specific tooling (`julia.provider`, `python.distribution`, …) does **not** belong here.

## The `[limits]` section (student safety)

Seeded by `/setup-cluster` from the default partition's **per-user QOS caps** (`sacctmgr show qos` via `user_caps`) — the limits a user actually hits — bounded by the partition's `max_wall`; partition node counts are only the fallback when no QOS cap exists. Then student-editable. Two tiers + path roots:

```toml
[limits.hard]            # exceed → /cluster-jobs refuses; student must lower to submit
max_walltime = "24:00:00"
max_nodes = 4
max_cpus = 256
max_array_size = 200

[limits.soft]            # exceed → warn + explicit confirm; may proceed
warn_walltime = "08:00:00"
warn_cpus = 64
unusual_partitions = ["gpu-large"]

[limits.paths]           # download/delete confined to these roots
allowed_roots = ["~/scratch", "~/results"]
```

`cluster_guardrail.py inspect` grades a job script against `[limits.hard]`/`[limits.soft]`; `check-path` enforces `[limits.paths].allowed_roots`. `expect` uses the same partition fields to predict the `sacct` allocation of a job before it is submitted, and `check-alloc` compares a running job against that prediction. On a `whole_node` partition (or with `#SBATCH --exclusive`) the CPU figure it grades is the allocated `nodes × cores-per-node`, not the typed task count. Likewise a `--mem` / `--mem-per-cpu` above the partition's `max_mem_per_cpu_mb` is graded at the cpu count Slurm will actually allocate, with a soft `memory` verdict. A profile with **no** `[limits]` is treated fail-closed (the guardrail warns rather than silently allowing).

## Full example

```toml
[identity]
name = "demohpc"
purpose = "teaching cluster"
maintainer = "hpc-help@example.edu"

[connection]
repo_path_remote = "/home/student07/quantum.harness"
[connection.ssh]
alias = "demohpc"
host = "login.demohpc.example.edu"
user = "student07"
identity_file = "~/.ssh/id_ed25519"
port = 22

[scheduler]
type = "slurm"
default_partition = "cpu"

[[partitions]]
name = "cpu"
class = "default-cpu"
cores = 64
memory = "256G"
max_wall = "24:00:00"
gpu = ""

[[partitions]]
name = "gpu-large"
class = "gpu"
cores = 32
memory = "512G"
max_wall = "12:00:00"
gpu = "a100:4"
required_gres = "gpu:a100:1"

[network]
internet_from_login = true
internet_from_compute = false

[region]
region = ""

[limits.hard]
max_walltime = "24:00:00"
max_nodes = 4
max_cpus = 256
max_array_size = 200
[limits.soft]
warn_walltime = "08:00:00"
warn_cpus = 64
unusual_partitions = ["gpu-large"]
[limits.paths]
allowed_roots = ["~/scratch", "~/results"]

[commands]
quota_command = "sshare -U -u student07"
```

## Picking the active profile

| Situation | Action |
|---|---|
| Single-cluster user | `ln -s <name>.toml skills/using-slurm/profiles/active.toml` once. |
| Multi-cluster user | `HARNESS_CLUSTER_PROFILE=<name>` per shell or in `.envrc`; env var wins over the symlink. |
| First-time user | `/setup-cluster` builds the profile (docs crawl → ratify, or ≤4 questions) and seeds `[limits]`. |
| Profile contains secrets | Nothing to do — every profile and card is gitignored by default; only allow-listed public profiles are committed. |

## Authoring a new profile

The recommended path is `/setup-cluster`. For manual authoring: probe the cluster (`python3 scripts/cluster_probe.py --alias <alias> --emit toml` gathers `sinfo`, `scontrol show partition`, your associations and QOS caps, and dry-runs a 1-task job per partition to detect whole-node allocation), write `skills/using-slurm/profiles/<name>.toml` following the tables above, activate it (`ln -s <name>.toml active.toml` or the env var), and test with a tiny job. Validate shape with `python3 scripts/cluster_profile.py --field connection.ssh.alias --profile <name>.toml`. Read a partition-scoped value with `python3 scripts/cluster_profile.py --partition <name> --field required_gres --profile <name>.toml`; `harness_slurm.sh submit` uses this interface instead of parsing TOML in Bash. Submission resource precedence is CLI/`--extra`, then the script's `#SBATCH` directives, then profile defaults, so profile values fill omissions without overriding script intent.

## Per-cluster setup notes (`<name>-setup.md`)

A profile may ship a committed, secret-free sibling `skills/using-slurm/profiles/<name>-setup.md` describing how a new user provisions credentials for that cluster: portal steps to obtain host/port/username, key download and install, and the `~/.ssh/config` stanza template. `/setup-cluster`'s connection bootstrap reads it when the profile's alias is unreachable. Keep it instructions-only — never a real hostname-for-a-user, username, port, or key; those stay in each user's own ssh config.

## Cards in this folder

Profiles are optional and user/site-specific. `.gitignore` ignores every `*.toml` and `*.md` in this folder and allow-lists the public examples, so a newly written profile or card stays local without any extra step. To publish a secret-free profile, add a `!skills/using-slurm/profiles/<name>.toml` line. Setup-notes siblings (`<name>-setup.md`) are always committable — they describe the provisioning process, not any user's credentials.
