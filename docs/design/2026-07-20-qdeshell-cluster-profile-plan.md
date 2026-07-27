# QDES Slurm Cluster Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a public, secret-free QDES Slurm profile and teach `/using-slurm` to validate required GRES and impractical queue estimates before submitting.

**Architecture:** Keep QDES-specific facts in one additive TOML profile. Extend the generic profile reference with an optional `required_gres` field, while the skill adds a scheduler-neutral feasibility gate based on the exact proposed `sbatch --test-only` request. Add a partition-row accessor to the Python profile parser and keep Bash limited to mechanics.

**Tech Stack:** TOML, Markdown skill instructions, Python `pytest`, Bash/Slurm smoke commands, Ion skill validation.

## Global Constraints

- The public profile contains no account name, personal home path, hostname, SSH port, or identity-file path.
- The SSH handle is the locally configured alias `qdeshell`; the remote checkout is `~/quantum.harness`.
- `qdagnormal` requires `required_gres = "gpu:A800:1"`.
- Safety limits are one node, 64 CPUs, 24 hours, and 200 array cells; soft warnings start at 8 hours and 16 CPUs.
- A live job is not submitted while `sbatch --test-only` predicts an impractical start time unless the user separately ratifies it.
- PR title and body are written in English.
- This fix pass commits locally but does not push or create a PR; the controller handles publication after re-review.

---

### Task 1: Public QDES profile contract

**Files:**
- Modify: `scripts/tests/test_cluster_profile.py`
- Create: `skills/using-slurm/profiles/qdeshell.toml`

**Interfaces:**
- Consumes: `cluster_profile.load_profile(path)`, `cluster_profile.validate(profile)`, and `cluster_profile.get_limits(profile)`.
- Produces: a parseable site profile whose `partitions[0].required_gres` is `gpu:A800:1` and whose `[connection.ssh]` contains only `alias = "qdeshell"`.

- [ ] **Step 1: Write the failing profile test**

Append this focused test to `scripts/tests/test_cluster_profile.py`:

```python
def test_public_qdeshell_profile_is_safe_and_complete():
    path = cp.Path(__file__).resolve().parents[2] / (
        "skills/using-slurm/profiles/qdeshell.toml"
    )
    profile = cp.load_profile(path)

    assert cp.validate(profile) == []
    assert profile["connection"]["repo_path_remote"] == "~/quantum.harness"
    assert profile["connection"]["ssh"] == {"alias": "qdeshell"}
    assert profile["scheduler"] == {
        "type": "slurm",
        "default_partition": "qdagnormal",
    }

    partition = profile["partitions"][0]
    assert partition["name"] == "qdagnormal"
    assert partition["required_gres"] == "gpu:A800:1"
    assert partition["cores"] == 64
    assert partition["gpu"] == "A800:8"

    limits = cp.get_limits(profile)
    assert limits.hard == {
        "max_walltime": "24:00:00",
        "max_nodes": 1,
        "max_cpus": 64,
        "max_array_size": 200,
    }
    assert limits.soft["warn_walltime"] == "08:00:00"
    assert limits.soft["warn_cpus"] == 16
    assert limits.allowed_roots == ["~/quantum.harness/results", "~/scratch"]
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
python3 -m pytest scripts/tests/test_cluster_profile.py::test_public_qdeshell_profile_is_safe_and_complete -q
```

Expected: FAIL with `ProfileError: profile not found` for `qdeshell.toml`.

- [ ] **Step 3: Add the minimal public profile**

Create `skills/using-slurm/profiles/qdeshell.toml` with these exact behavioral fields and the live-probe documentation:

```toml
[identity]
name = "qdeshell"
purpose = "QDES GPU compute service"
maintainer = "QuantumBFS"

[connection]
repo_path_remote = "~/quantum.harness"
login_shell = false

[connection.ssh]
alias = "qdeshell"

[scheduler]
type = "slurm"
default_partition = "qdagnormal"

[[partitions]]
name = "qdagnormal"
class = "gpu"
cores = 64
memory = "2051791M"
max_wall = "333-08:00:00"
gpu = "A800:8"
required_gres = "gpu:A800:1"

[filesystem]
home = "~"
scratch = "~/scratch"
project = "~/quantum.harness"
quota = ""

[network]
internet_from_login = false
internet_from_compute = false

[region]
region = "mainland_china"

[limits.hard]
max_walltime = "24:00:00"
max_nodes = 1
max_cpus = 64
max_array_size = 200

[limits.soft]
warn_walltime = "08:00:00"
warn_cpus = 16
unusual_partitions = ["qdagnormal"]

[limits.paths]
allowed_roots = ["~/quantum.harness/results", "~/scratch"]

[[documentation]]
url = "https://www.hpccube.com/doc/1.0.6/11250/general-handbook/scheduler/intro.html"
documents = "scheduler overview and login-node policy"

[[documentation]]
url = "https://www.hpccube.com/doc/1.0.6/11250/general-handbook/scheduler/sinfo.html"
documents = "partition and node-state reference"

[[gotchas]]
symptom = "CPU-only jobs fail with QOSMinGRES"
cause = "partition_qdagnormal requires one GPU per job"
fix = "request --gres=gpu:A800:1 and validate the exact request with sbatch --test-only"

[[gotchas]]
symptom = "A valid smoke request has a distant estimated start"
cause = "the only visible A800 partition is heavily allocated"
fix = "show the estimate and do not queue the real job without user ratification"

[[gotchas]]
symptom = "SSH commands print C.UTF-8 locale warnings"
cause = "the remote image does not provide the forwarded C.UTF-8 locale"
fix = "ignore the warning for parsing or configure a locale installed on the remote service"

[commands]
squeue = "squeue -u $USER"
sacct = "sacct --format=JobID,State,ExitCode,MaxRSS,Elapsed"
sinfo = "sinfo -o '%P %a %.10l %.6D %.6t'"
quota_command = "sacctmgr -n -P show assoc where user=$USER format=Account,Partition,QOS,GrpTRES,MaxTRES"

[notes]
text = "Live probe found Anaconda, Apptainer, and Singularity modules. Compute-node internet is fail-closed false until a scheduled probe verifies it."
```

- [ ] **Step 4: Run the focused profile tests and verify GREEN**

Run:

```bash
python3 -m pytest scripts/tests/test_cluster_profile.py -q
```

Expected: all tests in `test_cluster_profile.py` PASS.

- [ ] **Step 5: Commit the profile contract**

```bash
git add scripts/tests/test_cluster_profile.py skills/using-slurm/profiles/qdeshell.toml
git commit -m "feat: add public qdeshell cluster profile"
```

### Task 2: Generic pre-submit feasibility guidance

**Files:**
- Modify: `skills/using-slurm/SKILL.md`
- Modify: `skills/using-slurm/references/cluster-profiles.md`

**Interfaces:**
- Consumes: optional `[[partitions]].required_gres` and the scheduler's `sbatch --test-only` response.
- Produces: a proposed `sbatch` command containing the required GRES and a stop/ratification decision before any impractically delayed real submission.

- [ ] **Step 1: Run the baseline skill scenario and record RED**

Dispatch a fresh agent without the proposed guidance. Give it the current
`skills/using-slurm/SKILL.md`, the current cluster-profile reference, and this
raw scenario:

```text
Use /using-slurm to smoke-test a cluster. SSH and Slurm work. The only visible
partition is qdagnormal. A CPU-only `sbatch --test-only` returns QOSMinGRES.
Adding `--gres=gpu:A800:1` is accepted but estimates a start six weeks away.
What exact next action do you take?
```

Expected RED: the response does not derive a reusable `required_gres` profile
field and/or it queues the accepted job without explicit ratification of the
six-week wait.

- [ ] **Step 2: Add the additive schema field**

In the `[[partitions]]` row of the schema table in
`skills/using-slurm/references/cluster-profiles.md`, add `required_gres` and
define it as an optional exact Slurm GRES request imposed by partition/QOS.
Add `required_gres = "gpu:a100:1"` to the GPU row in the full example.

- [ ] **Step 3: Add the minimal feasibility contract to the skill**

In `skills/using-slurm/SKILL.md`:

- add pre-submit feasibility to the binding checklist;
- insert it after authorized shipping/bootstrap and before real submit; and
- define the exact shape:

```text
Build the complete resource request, including optional `required_gres` from
the selected partition. After shipping/bootstrap has made the script available
remotely, run the exact request through `sbatch --test-only`. Treat QOS/resource rejection
as a profile/request mismatch. If the returned estimate is impractically far
away, present wait/change/stop and require ratification before leaving a real
job queued.
```

Keep QDES names, A800 details, and queue dates out of `SKILL.md`.

- [ ] **Step 4: Repeat the fresh-agent scenario and verify GREEN**

Run the same scenario with the revised skill and reference. Expected response:

- persists `required_gres = "gpu:A800:1"` in the profile proposal;
- previews the exact request through `sbatch --test-only`;
- reports the distant estimate; and
- stops before submitting unless the user explicitly accepts the wait.

- [ ] **Step 5: Validate the skill and commit**

Run:

```bash
ion skill validate skills/using-slurm
git diff --check
```

Expected: skill validation and whitespace checks PASS.

Commit:

```bash
git add skills/using-slurm/SKILL.md skills/using-slurm/references/cluster-profiles.md
git commit -m "docs: guard slurm submissions with feasibility checks"
```

### Task 3: Executable profile-driven feasibility guardrail

**Files:**
- Modify: `scripts/cluster_profile.py`
- Modify: `scripts/harness_slurm.sh`
- Modify: `scripts/tests/test_cluster_profile.py`
- Modify: `scripts/tests/test_harness_slurm.py`

**Interfaces:**
- Consumes: explicit `--partition` or `[scheduler].default_partition`, plus optional `required_gres` on the selected partition row.
- Produces: an exact `sbatch --test-only` request whose scheduler output is returned without job-ID parsing; real submit retains its existing job-record output.

- [ ] **Step 1: Write focused failing parser and shell tests**

Cover named partition lookup, explicit/default partition resolution, automatic
GRES inclusion, caller-supplied GRES precedence, test-only output, and absence
of real-submit job-ID parsing in test-only mode.

- [ ] **Step 2: Verify RED**

Run the new parser tests and shell tests separately. Confirm failures identify
the missing partition accessor, omitted profile-derived flags, and unrecognized
`--test-only` option.

- [ ] **Step 3: Implement the minimal mechanics**

Add `cluster_profile.get_partition` and CLI `--partition` scoping. In
`harness_slurm.sh submit`, resolve the selected partition, ask the Python parser
for its `required_gres`, add it only when `--extra` has no `--gres` request, and
support `--test-only`. Print test-only scheduler output and return before job-ID
parsing.

- [ ] **Step 4: Verify GREEN and the public-profile hardening**

Run both focused files. Extend the public-profile contract to assert portable
filesystem paths, both fail-closed network booleans, and no forbidden public
SSH/account keys.

### Task 4: End-to-end verification and controller handoff

**Files:**
- Verify: `skills/using-slurm/profiles/qdeshell.toml`
- Verify: `skills/using-slurm/SKILL.md`
- Verify: `skills/using-slurm/references/cluster-profiles.md`
- Verify: `scripts/tests/test_cluster_profile.py`
- Verify: `scripts/tests/test_harness_slurm.py`
- Verify: `scripts/cluster_profile.py`
- Verify: `scripts/harness_slurm.sh`

**Interfaces:**
- Consumes: the committed QDES profile and revised skill contract.
- Produces: evidence that the profile parses, SSH/partition probing works, the proposed GPU request is previewed without submission, and the branch is ready for review.

- [ ] **Step 1: Run the repository test suite**

```bash
make test
```

Expected: all tests PASS with the repository's coverage threshold satisfied.

- [ ] **Step 2: Run profile-driven live precheck and partition probe**

```bash
HARNESS_PROFILE_FILE=skills/using-slurm/profiles/qdeshell.toml \
  scripts/harness_slurm.sh precheck
HARNESS_PROFILE_FILE=skills/using-slurm/profiles/qdeshell.toml \
  scripts/harness_slurm.sh probe-partitions
```

Expected: `ssh_ok: true`; `qdagnormal` appears in the parsed partition table.

- [ ] **Step 3: Preview the exact resource-bearing submission**

```bash
HARNESS_PROFILE_FILE=skills/using-slurm/profiles/qdeshell.toml \
HARNESS_SLURM_DRYRUN=1 \
  scripts/harness_slurm.sh submit --test-only \
    --script scripts/smoke_test.sbatch \
    --time 00:01:00 \
    --cpus 1
```

Expected: profile resolution adds `--partition=qdagnormal` and
`--gres=gpu:A800:1` to the `sbatch --test-only` request; no job ID is created.

- [ ] **Step 4: Review the complete diff and recent commits**

```bash
git diff origin/main...HEAD --check
git diff --stat origin/main...HEAD
git log --oneline origin/main..HEAD
```

Expected: only the approved design, plan, profile, focused test, schema, and
skill guidance are present.

- [ ] **Step 5: Hand off for re-review without publishing**

Commit the tracked fixes with an English subject and provide the controller the
verification report. Do not push or create a PR during this fix pass. The later
draft PR should target `main` and use:

```text
Title: Add a public QDES Slurm cluster profile

Body sections:
- Summary
- Live validation
- Safety and privacy
- Tests

The body must explain that no live job was queued because `sbatch --test-only`
predicted a six-week wait, and that the profile contains no personal SSH data.
```
