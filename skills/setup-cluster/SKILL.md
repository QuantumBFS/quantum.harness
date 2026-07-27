---
name: setup-cluster
user-invocable: false
description: >-
  Use when a usable cluster connection or profile is needed and something is
  missing — a fresh account, no `skills/using-slurm/profiles/active.toml`,
  "set up my cluster", "configure HPC", a profile whose ssh alias is
  unreachable ("Could not resolve hostname", no key installed, credentials
  never provisioned), or when `/cluster-jobs` / `/onboard` / `/using-slurm`
  find no profile or fail their ssh precheck.
---

# setup-cluster

Make a cluster *usable*: one unified TOML profile per cluster under
`skills/using-slurm/profiles/<name>.toml`, plus the `active.toml` symlink. This
is the single source of truth for cluster readiness — `/onboard` delegates its
cluster stage here, and `/cluster-jobs` / `/using-slurm` route here when no
profile is found. Mirrors `/setup-julia` (dispatched on demand, not a slash
command).

Four things, in order: **bootstrap the connection → build the profile → probe
live resources → seed `[limits]`**. The schema is
`skills/using-slurm/references/cluster-profiles.md` — read it before writing;
do not invent fields.

## Idempotency

Route by state — never rebuild finished work:

First matching row wins:

| State | Action |
|---|---|
| Profile resolves, has `[limits]`, `ssh <alias> echo ok` passes | Skip entirely. |
| Profile file exists with `[limits]`, but ssh fails (whether or not anything resolves it) | Run **0. Connection bootstrap**; then, if nothing resolves the profile, activate it (§4). Do not rebuild. |
| Profile file exists, ssh passes, but nothing resolves it (no `active.toml`, no env var) | Activate it (symlink or env var, §4) — do not rebuild. |
| Profile resolves but predates `[limits]` | Jump to **3. Seed limits** and append. |
| No profile file for this cluster | Full run, §0–§4. |

The skip test includes the ssh check: a profile whose alias is unreachable is
not "already set up", however complete its TOML is.

## 0. Connection bootstrap

Skip when `ssh <alias> echo ok` already passes. Otherwise the student has no
provisioned access — a state no amount of profile-building fixes.

1. **Find the cluster's credential instructions.** Read the sibling setup notes
   `skills/using-slurm/profiles/<name>-setup.md` if they exist; otherwise use
   the profile's `[[documentation]]` URLs (or the docs crawl below) to locate
   the login/credential pages. Portal-provisioned clusters (SCNet, hpccube-family)
   issue host, port, username, and a downloadable key from a web console — the
   student must do those portal steps; walk them through, one at a time.
2. **Install key + alias.** Once the student has host/port/user/key: move the
   key under `~/.ssh/`, `chmod 600` it, and append a `Host <alias>` stanza to
   `~/.ssh/config` matching the profile's `connection.ssh.alias`. The agent
   writes the stanza; never paste a private key into the repo or the profile.
   macOS gotcha: TCC blocks agent processes from reading `~/Downloads` — have
   the student move the downloaded key themselves (`! mv ~/Downloads/<key>
   ~/.ssh/...` run from their prompt, or Finder) rather than retrying.
3. **Verify, then hand back.** `ssh <alias> echo ok` must print `ok` before
   continuing to §1. When the profile already exists, activate it first if
   nothing resolves it (§4), then return to the caller. Do not proceed on
   faith.

## 1. Build the profile

Ask the warm gate (one `AskUserQuestion`): paste the cluster's docs URL, or walk
through 4 quick questions. Either fills the schema.

**From a docs URL** — dispatch an Agent subagent (`subagent_type:
"general-purpose"`, max-effort framing) to crawl comprehensively, because one
fetch misses the sidebar sub-pages:

<brief name="cluster-docs-crawl">
- Input: the docs root URL.
- Enumerate + fetch every sub-page for: login/connection, scheduler/submission,
  partitions/queues/limits, environment/modules, filesystem, network reach.
- Extract verbatim (sbatch examples, partition tables, module loads, hostnames).
- Synthesize into the TOML schema in `cluster-profiles.md`.
- Flag harness-side gotchas not explicit in docs (non-interactive ssh not
  sourcing `/etc/profile`; two `sbatch` binaries; login-shell-only quirks).
- Output: the `[[documentation]]` URL index, the proposed `<name>.toml`, a
  `[[gotchas]]` list, and any field it could not extract (→ fall to questions
  for those fields only).
- **Coverage, not filtering** — report every partition row and gotcha, even
  uncertain ones. Silently dropping one is the failure mode.
</brief>

Display the proposed `<name>.toml` inline as a fenced block; `AskUserQuestion`:
Accept and save / Edit then save / Discard and use the walk-through. Write only
after Accept or an edit.

**Walk-through fallback (≤4 warm questions):**
1. *"Paste the ssh command you use to reach the login node (e.g. `ssh -i ~/.ssh/id_rsa user@host`), or a `~/.ssh/config` stanza."* → parse `host`/`user`/`identity_file`/`port` into `[connection.ssh]`; default `alias` to the cluster short-name.
2. `AskUserQuestion` workload manager: `Slurm` / `PBS / Torque` / `LSF` / `Plain ssh` / `Not sure — I'll probe`.
3. *"Default queue/partition? Overridable per job."*
4. `AskUserQuestion` region: `Mainland China` / `Outside mainland China` / `Air-gapped` / `Not sure`.

Per the harness UX rule, every question frames the why → states the consequence
→ offers the escape hatch.

## 2. Probe live resources (read-only)

Before seeding limits, see what the cluster actually offers — this both informs
the student and supplies real caps for `[limits]`:

```bash
scripts/harness_slurm.sh --profile <name>.toml probe-partitions   # parsed sinfo: idle/mix/alloc, cores/mem/gpu
```

If the profile carries `[commands].quota_command`, run it read-only over ssh for
the student's own allocation usage (best-effort; skip with a note if absent).
Present a compact **"what's available / your budget"** summary. Purely read-only
— no confirm gate.

## 3. Seed `[limits]`

Propose `[limits]` seeded from the probed `[[partitions]]` caps — real numbers,
not invented:

- `[limits.hard].max_walltime` ← the largest partition `max_wall` (or the
  default partition's, if the student should be fenced tighter).
- `[limits.hard].max_nodes` / `max_cpus` ← partition node/core counts.
- `[limits.hard].max_array_size` ← a conservative default (e.g. 200) unless the
  cluster documents a per-user array cap.
- `[limits.soft]` ← thresholds below the hard caps (warn before the ceiling).
- `[limits.paths].allowed_roots` ← `[filesystem].scratch` + the results dir.

Show the proposed `[limits]` block and get an explicit confirm-or-edit (the
harness "propose for ratification" rule). Students draw on individual
allocations, so these protect each student from their own mistakes.

## 4. Write + activate

Write `skills/using-slurm/profiles/<name>.toml`, symlink `active.toml → <name>.toml`.
Validate shape:

```bash
python3 scripts/cluster_profile.py --field connection.ssh.alias --profile skills/using-slurm/profiles/<name>.toml
```

Confirm one line: *"Cluster profile saved at `…/<name>.toml` with safety limits.
Future jobs use it automatically."* If the profile holds secrets (a real
identity file path is fine; an inline key is not), remind the student to
`.gitignore` it.

Do **not** bootstrap Julia/Python here — that's `/setup-julia` etc., dispatched
on demand by the submitting skill.

## Output

- `skills/using-slurm/profiles/<name>.toml` (unified: connection + scheduler +
  partitions + network + region + `[limits]`) and the `active.toml` symlink.
- A one-line "what's available / your budget" summary from the probe.
- The ratified `[limits]` block.

## Composition

- `/onboard` delegates its cluster-setup stage to this skill.
- `/cluster-jobs` and `/using-slurm` route here when no profile exists **or
  when their ssh precheck fails** (→ §0 Connection bootstrap).
- `/setup-julia` runs afterward, on demand, for language setup.
- Per-cluster credential instructions live in
  `skills/using-slurm/profiles/<name>-setup.md` (committed, secret-free), not
  in this skill.
