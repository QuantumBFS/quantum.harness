---
name: cluster-jobs
user-invocable: true
description: >-
  Use when a student wants to run their own job on the cluster and have it kept
  safe — "submit my job", "send this script to the cluster", "check my job",
  "is my job done", "cancel my job", "download my results", "get my data back".
  Guards against runaway compute, credential leaks, and destructive file ops via
  preview-and-confirm. For harness array sweeps the agent drives, use
  `/using-slurm` instead.
---

# cluster-jobs

A safe, plain-English way for students to **submit, check, cancel, and download**
their own cluster jobs through the agent. The student brings a job script (any
language); this skill cannot reason about the computation, so it guards the
three things it *can* check — **how much compute is asked for, where files go,
and whether credentials leak** — and confirms every risky step before acting.

Mechanics are reused, not reinvented: `scripts/harness_slurm.sh` does the
ssh/sbatch/squeue/rsync; `scripts/cluster_guardrail.py` makes the safety calls.
This skill owns the conversation and the confirmations.

> Distinct from `/using-slurm` (agent-facing, harness array sweeps with run-spec
> manifests). Students who run arbitrary scripts use `/cluster-jobs`.

## The cardinal rule

**Status is the only action that runs without a confirm.** Submit, cancel, and
download each follow: **preview → (block or confirm) → act**. Never act on a
hard-block. Never echo key material. State the cluster + account before doing
anything that touches them.

No profile yet (`skills/using-slurm/profiles/active.toml` absent)? Route to
`/setup-cluster` first; never invent ssh details or partitions.

## 1. Connect / verify

```bash
scripts/harness_slurm.sh precheck          # resolve profile, ssh echo ok, git dirty status
```

- **State the target, get one confirm:** "About to act on **cluster `<alias>`**
  as **`<user>`**." This single line is the main defense against acting on the
  wrong account.
- **Show what's available (read-only, no gate):**
  ```bash
  scripts/harness_slurm.sh probe-partitions    # usable partitions: idle/total, hardware, whole-node, per-user caps
  ```
  plus the profile's `[commands].quota_command` if present → a compact "your
  budget / what's free" line before the first submit.

## 2. Submit — guards runaway compute + credential leak

Inspect the student's script before anything leaves the laptop:

```bash
python3 scripts/cluster_guardrail.py inspect <script>     # exit 0 clean · 1 soft · 2 hard
```

Read the JSON and the exit code:

- **Exit 2 (hard-block)** — over a `[limits.hard]` ceiling, or a secret found in
  the script. **Refuse.** Name the exact field + ceiling (or the secret rule +
  line), have the student edit. Do not submit.
- **Exit 1 (soft-warn)** — over a `[limits.soft]` threshold, an unusual
  partition, a `memory` verdict (`--mem` above the partition's per-cpu memory,
  so Slurm adds and bills cores the job will not use — offer the lower `--mem`),
  or an unverifiable field. Show the resource table + the warning,
  get an **explicit confirm**.
- **Exit 0 (clean)** — show the resource table, proceed.

On pass/confirm, preview the exact command, then submit:

```bash
HARNESS_SLURM_DRYRUN=1 scripts/harness_slurm.sh submit --script <script> --partition <p> --time <t>   # preview
scripts/harness_slurm.sh submit --script <script> --partition <p> --time <t>                          # real; captures job id
```

## 3. Manage

- **Status (un-gated):**
  ```bash
  scripts/harness_slurm.sh status <jobid>
  ```
- **Cancel (gated):** show the matched job id(s) + name first, then confirm,
  then `scancel`. Never cancel by pattern without showing the matched list.

## 4. Download — guards destructive / clobbering transfer

Before fetching, preview **source** (remote path + `du -sh` size), **dest**
(local path), and whether the dest already exists. Then confine the path:

```bash
python3 scripts/cluster_guardrail.py check-path <local-dest>   # exit 0 under allowed roots · 2 refused
```

- **Exit 2** — outside `[limits.paths].allowed_roots`, or none configured.
  Refuse; ask the student to choose an allowed location.
- **Exit 0** — proceed with a **non-clobbering** fetch by default. Overwriting
  existing files needs an explicit confirm with the affected file list. Never a
  blind `rm -rf` or a clobbering sync.

```bash
scripts/harness_slurm.sh fetch <run>       # rsync results back
```

## Output norms

Lead with the answer, plain English, terse. After a submit: job id + the
resource summary + verification that it passed limits, in ≤3 lines. After a
download: what landed where + size. Internal vocabulary (manifest, run-spec)
stays out of student messages.

## Anti-patterns

<checklist name="reject">
- Submitting a script the guardrail hard-blocked.
- Acting on a cluster/account without stating it and confirming first.
- Echoing ssh key material or pasting secrets back to the student.
- Downloading/deleting outside the allowed roots, or clobbering files without showing the list.
- Reinventing ssh/sbatch/rsync instead of driving `harness_slurm.sh`.
- Treating `sbatch` success or a `RUNNING` state as "it worked" — only fetched output is evidence.
</checklist>

## Composition

- `/setup-cluster` creates the profile + limits this skill reads.
- `scripts/cluster_guardrail.py` makes the safety calls; `scripts/harness_slurm.sh` does mechanics.
- For agent-driven harness array sweeps, use `/using-slurm` + `/parameter-scan`.
