# Challenge #15 Route A Slurm-First Amendment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every A03-A05 and final-audit executable check with an evidence-bound SCNet Slurm compute-node job while preserving the approved Route A physics, TDD order, seed budgets, and ED barrier.

**Architecture:** The Windows worktree is the source and review authority.  Each clean or dirty TDD snapshot is packed into a new immutable remote attempt directory, then a Slurm job runs the exact command on a compute node and writes a compute manifest.  After `sacct`, the controller fetches all artifacts and creates a final machine-readable manifest that joins source identity, scientific checks, hashes, and scheduler resources.

**Tech Stack:** PowerShell and Git on Windows; SSH/SCP or scoped archive transfer; Bash, Slurm, Python 3.11+, NumPy, SciPy, and pytest on SCNet compute nodes; JSON/JSONL and SHA-256 receipts.

---

## Authority and supersession

- Parent plan: `2026-07-29-challenge-15-route-a-logpsi-completion.md`.
- Reviewed A02 closeout terminal: `7d983e81f94ca45eeef66bcc51665d9cf2291cea`.
- A03 branches from the clean local HEAD that contains this amendment; record that exact execution-base SHA in the A03 journal at worktree creation.  The reviewed A02 closeout terminal above must remain an ancestor.
- Comparison SHA: `5aa9219f4cd24bc2274f0514b621c2f9b47cead7`.
- Protocol SHA-256: `2435cd2e72ffae88117ee194f45b15451c8653dafa755b732005b6a199251d38`.
- Fixed production seeds: `848`, `1848`, `2848`; N=8 smoke seed: `4848`.
- This amendment changes placement and evidence transport only.  It does not change the Hamiltonian, sectors, tower, objective, samples, updates, width, layers, checkpoint rule, or acceptance gates.
- From A03 onward, Windows and the login node may edit, inspect, hash, archive, transfer, submit, query, tail, and fetch.  They must not run Python tests, Python smoke/performance code, training, or final executable validation.
- Every Python/pytest action from A03 onward runs inside `sbatch` on a compute node.  A login-node Python, pytest, pip, conda, smoke, performance, or training command is a protocol violation.
- The parent plan's A04 instruction to run `test_scalable_evaluator.py` is superseded: the common scalable evaluator is forbidden before all four routes freeze.  Static production scans and route-specific tests replace it for Route A.
- No push, PR, candidate ED reveal, overlap, ED-based selection, full physical basis enumeration, dense Hamiltonian/L2, projector, or Ritz path is authorized.

The canonical complete Route A pytest command for every baseline, GREEN, and
audit job is:

```bash
python -m pytest tracks/qmc/solutions/BOTS-848/tests -q \
  --ignore=tracks/qmc/solutions/BOTS-848/tests/test_scalable_evaluator.py
```

This explicit ignore is mandatory until the four-route barrier.  A job manifest
must contain the exact expanded command so an accidental evaluator invocation
cannot be hidden behind the phrase "full suite."

## File and artifact map

- Create per-job launch material under `D:/Playground/output/BOTS-848/scalable-v1/route-a/slurm-jobs/<job-key>/`; do not commit source bundles, stdout, stderr, checkpoints, or optimizer state.
- Stage each snapshot at `~/quantum.harness-worktrees/route-a-<slice>-<attempt>-<head12>-<bundle12>`; never reuse or overwrite an earlier attempt directory.
- Fetch scientific results to `D:/Playground/output/BOTS-848/scalable-v1/route-a/<slice>/<job-key>/` or the fixed seed directories required by the parent plan.
- Commit only source/tests, nonsecret journals, final receipt, configuration, and artifact hashes under `tracks/qmc/solutions/BOTS-848/`.
- Keep the private SSH key, local absolute key path, checkpoint bytes, optimizer bytes, and credentials out of source bundles, manifests, logs, and commits.

## Binding manifest contract

Every job key is `<slice>-<phase>-<utc-or-local-stamp>-<head12>-<bundle12>`.  Before transfer, record:

```text
local_branch
local_head_sha
git_status_porcelain
dirty_boolean
source_bundle_sha256
comparison_sha
protocol_sha256
remote_attempt_dir
exact_command
compute_working_directory
requested_partition
requested_cpus
requested_memory
requested_walltime
```

The compute job writes `manifest.compute.json` and includes:

```text
schema = bots848-route-a-slurm-compute-v1
status = ok | expected-red | failed
slurm_job_id, slurm_array_task_id, partition, node
python_version, numpy_version, scipy_version, pytest_version
exact_command, working_directory
local_branch, local_head_sha, dirty_boolean, source_bundle_sha256
comparison_sha, protocol_sha256
started_at, finished_at, command_exit_code
stdout_path, stderr_path
artifact list with relative path, byte size, sha256
scientific counters, sample counts, NaN count, Inf count, checkpoint sha256 when applicable
```

After the job leaves the queue, query `sacct` for
`JobID,JobName,Partition,NodeList,AllocCPUS,ReqMem,State,ExitCode,Elapsed,MaxRSS`.
Fetch the compute manifest, stdout, stderr, and artifacts, then use PowerShell
`ConvertFrom-Json`, `Get-FileHash`, and `ConvertTo-Json` locally to write
`manifest.json`.  The final manifest embeds the compute manifest plus the exact
`sacct` row and local re-hashes.  It is valid only if all identities agree and
every listed artifact exists at the fetched path with the declared byte size
and SHA-256.

`COMPLETED`, a zero `sbatch` return, or a present checkpoint is never enough.
The controller must reject missing artifacts, wrong command/source/protocol,
wrong seed/update/sample count, any NaN/Inf, a checkpoint hash mismatch, an
unexpected RED failure, or a nonzero GREEN/scientific command.

## Reusable snapshot and job procedure

For each RED, GREEN, baseline, smoke, performance, training, or audit job:

- [ ] **Step 1: Capture the exact local snapshot identity**

Run only Git and PowerShell metadata commands locally:

```powershell
$branch = git branch --show-current
$head = git rev-parse HEAD
$status = git status --porcelain=v1
$head12 = $head.Substring(0, 12)
```

For a dirty TDD snapshot, include tracked changes and untracked in-scope tests.
Build a scoped archive excluding `.git`, caches, `results`, `output`, private
keys, and checkpoints.  Calculate its SHA-256 with `Get-FileHash`.  The archive
is immutable after hashing; any edit requires a new bundle and job key.

- [ ] **Step 2: Create a new isolated remote directory and transfer**

Use `ssh -o BatchMode=yes scnet` only to create the new directory and `scp` or
an equivalent scoped archive transfer to copy the bundle.  Extract with remote
shell `tar` on the login node.  Never run Python while staging.  Verify the
remote archive with `sha256sum` and stop if it differs from the local hash.

- [ ] **Step 3: Live-probe resources and test the exact request**

Use the SCNet profile explicitly:

```bash
bash scripts/harness_slurm.sh --profile skills/using-slurm/profiles/scnet.toml precheck
bash scripts/harness_slurm.sh --profile skills/using-slurm/profiles/scnet.toml probe-partitions
```

If only `hx1hdnormal01` is visible, choose it and record that it is the sole
associated partition.  CPU jobs request no GRES.  Run an `sbatch --test-only`
equivalent with the exact script, partition, time, CPUs, and memory before real
submission.  A request must stay within one node, 32 CPUs, 64 GiB, and 24 h;
smaller measured requests are preferred.

- [ ] **Step 4: Submit and monitor through scientific startup**

Submit from the isolated remote directory, capture the numeric job id, then
query pending/running state.  Once RUNNING, tail the generated stdout until the
environment fingerprint and first test/progress record appear.  For long jobs,
poll every 30-60 minutes and retain progress pulses.  Do not cancel a real job
without new user authority.

- [ ] **Step 5: Fetch, join `sacct`, and verify the final manifest**

After the job leaves the queue, fetch all evidence, create the final joined
`manifest.json`, re-hash every artifact, inspect full stdout/stderr, and verify
scientific counters.  Only then may the job be called expected-RED or GREEN.

## Task 1: SCNet preflight and compute environment

**Files:**
- Read: `skills/using-slurm/profiles/scnet.toml`
- Read: `skills/using-slurm/profiles/scnet-setup.md`
- Use: `scripts/harness_slurm.sh`
- Create outside Git: `D:/Playground/output/BOTS-848/scalable-v1/route-a/slurm-jobs/environment-probe/`

- [ ] **Step 1: Verify SSH without exposing key material**

Check only that `C:/Users/TaiS/.ssh/scnet_key` exists and has restricted ACL,
that SSH config contains one effective `Host scnet`, and that BatchMode
`echo ok && hostname` succeeds.  If alias or key installation is not ready,
follow `skills/setup-cluster/SKILL.md` and the SCNet setup notes.  Never print or
hash the private-key contents into task output.

- [ ] **Step 2: Probe partition and account association**

Run `precheck`, `probe-partitions`, the profile quota command, and a direct
read-only `sinfo`/`sacctmgr` query.  Record the available partition, state,
account/QOS, hard limits, and why the selected CPU request needs no DCU/GRES.

- [ ] **Step 3: Submit a minimal compute-node environment probe**

The job prints `hostname`, `SLURM_*` identity, module availability, and versions
for Python, NumPy, SciPy, and pytest, then imports all three packages and writes
the binding manifests.  It must request one CPU, at most 4 GiB, and at most five
minutes.  No Python command runs on the login node.

- [ ] **Step 4: Bootstrap only if the compute probe proves a dependency gap**

If NumPy, SciPy, or pytest is absent, prepare a Linux wheelhouse locally under
the job output root, transfer it, and submit a Slurm setup job that creates an
isolated venv inside the remote attempt namespace with `pip --no-index`.  Do not
install on the login node.  Re-run the environment probe and bind later jobs to
the verified interpreter path.

## Task 2: A03.1 model RED, GREEN, and reviews

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/model.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_training.py`

- [ ] **Step 1: Create the A03 worktree from the reviewed A02 terminal**

Use branch `challenge/qmc-chiral-graviton-scalable-v1-s02a-a03-logpsi` and path
`D:/Playground/worktrees/quantum.harness/challenge-qmc-cg-s02a-a03`, with
`git -c core.longpaths=true worktree add`.  Branch from the clean HEAD that
contains this amendment; record that exact parent, verify reviewed A02 closeout
`7d983e81f94ca45eeef66bcc51665d9cf2291cea` is an ancestor, and record clean
status plus the protocol hash.

- [ ] **Step 2: Run the clean A03 baseline through Slurm**

Submit the canonical complete Route A pytest command above, compileall, and
static forbidden scans in one compute job.  The Python/pytest parts run only
inside the allocation; local static Git/`rg` inspection may be repeated after
fetch.

- [ ] **Step 3: Write only the A03.1 tests and prove RED remotely**

Cover tiny-support normalization, shared-trunk object identity, seed-848
deterministic initialization and sampling, infeasible-state rejection,
parameter-cap rejection, and every flat parameter's analytic log derivative
against central difference.  Transfer the dirty test snapshot and submit the
focused pytest command.  Accept RED only when the expected missing
`model.py`/API behavior is named in the fetched manifest and output.

- [ ] **Step 4: Implement minimal GREEN and verify remotely**

Implement the exact two-layer conditional model from the parent plan.  Transfer
a new dirty bundle and submit focused tests, full BOTS-848 tests, compileall,
and production forbidden scans.  Fetch and verify every manifest, then commit
tests and production code only after GREEN.

- [ ] **Step 5: Review in the required order**

The implementer self-reviews, a fresh specification reviewer checks the full
A03.1 contract, then a fresh quality reviewer inspects the actual diff.  Any
Critical/Important returns to the same implementer with a regression-first
Slurm RED/GREEN job and both applicable re-reviews.  The main agent performs a
fresh Slurm verification job before marking A03.1 reviewed.

## Task 3: A03.2 training and deterministic smoke

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/train.py`
- Create: `tracks/qmc/solutions/BOTS-848/train_occupation_autoregressive.py`
- Modify: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_training.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a03.md`

- [ ] **Step 1: Prove the A03.2 RED contract in Slurm**

Write tests for covariance, clipping, the hand-calculated Adam step, exact two
sector samples per update, JSONL updates 1..16, final-update selection, atomic
checkpoint replacement, and two byte-identical seed-848 smoke checkpoints.
Submit the dirty test snapshot and accept only the expected missing behavior.

- [ ] **Step 2: Implement and run GREEN in Slurm**

Implement the reduced M=0 objective and CLI without early stop/oracle.  Submit
focused tests, full BOTS-848 tests, compileall, forbidden scans, and two separate
16-update smoke commands.  Fetch both run directories; require equal checkpoint
SHA-256, exact updates and samples, finite objective/gradient/L2, and recorded
Elapsed/MaxRSS before commit.

- [ ] **Step 3: Close A03 with two reviews and main verification**

Record all job ids, manifests, hashes, resource rows, RED/GREEN evidence, and
review results in `s02a-a03.md`.  Follow implementer -> specification -> quality
-> main-agent fresh Slurm verification; branch A04 only from the clean reviewed
A03 terminal.

## Task 4: A04 tower, sampler, and diagnostics

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/tower.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/diagnostics.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_tower.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a04.md`

- [ ] **Step 1: Create A04 and run a clean Slurm baseline**

Create a short-path independent worktree from the reviewed A03 terminal.  Run
the full BOTS-848 baseline, compileall, and forbidden scans on a compute node.

- [ ] **Step 2: Execute A04.1 RED/GREEN in Slurm**

Prove RED for the exact L=2 fixture, five norms, local L2 residual below
`1e-12`, and analytic tower scores.  Implement inverse sparse ladder neighbors,
bounded log sums, analytic spin-2 coefficients, exact `-inf` zeros, and score
propagation; prove focused/full GREEN remotely before commit.

- [ ] **Step 3: Execute A04.2 RED/GREEN in Slurm**

Prove RED for detailed balance, all five sectors, burn-in reporting,
deterministic seeds, ladder residual below `1e-12`, and eight rotation residuals
below `1e-10`.  Implement the symmetric two-pair proposal and exactly the four
diagnostic fields.  Production rotation diagnostics use seeded importance
samples, never a physical full-basis enumeration.

- [ ] **Step 4: Close A04 without the common evaluator**

Run route-specific tests, the canonical complete Route A pytest command,
compileall, static forbidden scans, and performance measurements through Slurm.
Fetch evidence, complete specification review, quality review, main-agent fresh
Slurm verification, and journal closeout.

## Task 5: A05.1 adapter, factory, and N=8 smoke

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/adapter.py`
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/factory.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_adapter.py`
- Modify: `tracks/qmc/solutions/BOTS-848/train_occupation_autoregressive.py`

- [ ] **Step 1: Create A05 and prove adapter RED in Slurm**

Create the short-path worktree from the reviewed A04 terminal.  Tests cover the
three runtime protocols, five multiplet keys, artifact/source/protocol/seed
binding, tamper rejection, the sole `BOTS848_SCALABLE_RUN_DIR` factory input,
and absence of capacity overrides.  Accept only the expected remote RED.

- [ ] **Step 2: Implement GREEN and run N=8 smoke in Slurm**

Implement strict adapters/factory/manifests, then submit focused/full GREEN.
Submit N=8, 2Q=21, seed-4848, batch-256 no-training smoke with two warmups and
five measured repetitions.  Exercise support, logpsi, sparse energy/L2, tower,
and adapter batching.  Record N=8/N=6 time and RSS ratios from the same node and
interpreter fingerprint; fetch and verify before commit.

- [ ] **Step 3: Review A05.1**

Use specification review, then quality review, then a fresh main-agent Slurm
verification.  Critical/Important issues use a new dirty-bundle RED/GREEN cycle
under the attempt policy.

## Task 6: A05.2 tower-aware three-seed freeze

**Files:**
- Modify: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/occupation_autoregressive/train.py`
- Modify: `tracks/qmc/solutions/BOTS-848/train_occupation_autoregressive.py`
- Modify: `tracks/qmc/solutions/BOTS-848/tests/routes/test_occupation_adapter.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02a-a05.md`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/freezes/route-a-receipt.json`

- [ ] **Step 1: Prove the full-objective RED contract in Slurm**

Test exactly 512 ground samples and 512 for each of five tower components per
update, arithmetic five-state excited energy, tower-score covariance, exactly
2048 updates with final-update selection, and no ED/open-oracle path.

- [ ] **Step 2: Implement full GREEN and estimate resources**

Implement the fixed full objective without changing batch, seeds, updates, or
early stopping.  Run focused/full GREEN in Slurm.  Use fetched A03/A04/A05.1
Elapsed/MaxRSS to estimate 2048 updates; choose no more than 32 CPUs/64 GiB and
avoid surplus cores for serial code.

- [ ] **Step 3: Submit three independent seed jobs**

Use distinct remote directories and result roots for `848`, `1848`, and `2848`.
Each manifest binds the same reviewed source and protocol, its exact seed,
2048 updates, final-selection rule, sample counts, hashes, and resource request.
Monitor pending -> running -> first scientific progress -> periodic pulses ->
completion.  Never treat one seed's success as evidence for another.

- [ ] **Step 4: Fetch and classify each freeze**

Fetch to `D:/Playground/output/BOTS-848/scalable-v1/route-a/seed-<seed>`.
Verify full JSONL length, exact per-update counts, final update, finite values,
checkpoint and optimizer hashes, source/protocol/seed identity, scheduler row,
and artifact completeness.  Preserve failures; do not overwrite or silently
retry them.

- [ ] **Step 5: Write receipt, journal, reviews, and terminal commit**

The receipt contains only nonsecret identities, three seed manifest hashes,
artifact sizes, resource fingerprints, N=8 status, and `route-frozen`.  Complete
specification review, quality review, and main-agent fresh Slurm verification
before committing the terminal journal/receipt.

## Task 7: Final independent Route A audit

**Files:**
- Verify tracked source/tests/journals/receipt.
- Amend only missing or inaccurate A05 evidence.

- [ ] **Step 1: Submit a fresh final executable audit job**

On the clean reviewed A05 terminal, run all focused Route A tests, the canonical
complete Route A pytest command, compileall, and executable static-audit helpers
inside Slurm.  Fetch and validate the final manifest and `sacct` row.

- [ ] **Step 2: Perform local read-only integrity and scope checks**

Use Git, PowerShell, and `rg` locally to verify protocol/source/manifest hashes,
three fetched seed directories, N=8 evidence, no forbidden production path,
clean status, and `origin/master...HEAD` scope.  Do not run local Python.

- [ ] **Step 3: Run final specification and quality reviews**

Independent reviewers compare code, tests, journals, manifests, receipts, and
the amendment line by line.  Any Critical/Important returns to the same task's
implementer and attempt ledger, followed by re-review and fresh Slurm evidence.

- [ ] **Step 4: Stop at the four-route barrier**

When all gates pass, report Route A `route-frozen` and wait for Routes B/C/D.
Do not run the common ED evaluator and do not push or create a PR.  Mark the
goal complete only if the active goal is scoped to Route A alone; otherwise
leave it at the explicit four-route barrier state.  If one blocker reaches five
root-cause-driven implementation failures, preserve all local/remote evidence
and mark the goal blocked rather than starting attempt six.

## Self-review checklist

- [ ] Every parent-plan local Python/pytest/smoke/training action from A03 onward is redirected to a compute-node Slurm job.
- [ ] Login-node allowed actions are staging, read-only scheduler queries, submission, tail, fetch, and shell extraction/hash only.
- [ ] Dirty RED/GREEN snapshots have immutable source-bundle hashes and distinct remote directories.
- [ ] Every job returns source, protocol, command, environment, scheduler, artifact, sample, finite-value, and hash evidence.
- [ ] `COMPLETED` is never equated with scientific success.
- [ ] Seeds, sample budgets, updates, N=8 parameters, physics, and ED barrier are unchanged.
- [ ] No push, PR, private key, credential, checkpoint overwrite, or common evaluator is introduced.
