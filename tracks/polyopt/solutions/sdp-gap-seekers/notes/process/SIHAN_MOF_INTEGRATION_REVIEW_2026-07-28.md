# Work packet 0 — Sihan MOF integration review (BLOCKED)

Date: 2026-07-28
Work packet: 0 (Sihan integration inventory)
Stop-gate result: **BLOCKED — inputs not visible**
Claim level: N/A (inventory/blocker; no scientific claim advanced)

## Worker handoff header

```
Starting SHA: 5a2425a13881658eae0cc2e9c7f33171db5612e0  (challenge/polyopt-sdp-gap)
Ending SHA:   (this note only; see commit)
Pre-existing dirty files preserved: Ion.lock (modified), ADVISOR_PROJECT_DIRECTION_AND_WORKER_PLAN_2026-07-28.md (untracked), ADVISOR_RECHECK_2026-07-28_COMMIT_5a2425a.md (untracked)
Work packet: 0
Stop-gate result: BLOCKED — Sihan's referenced commits and MOF/ray/metadata/verifier artifacts are not visible in any accessible git ref or PR
Claim level: N/A
```

## Bottom line

Per the packet's explicit instruction:

> If those inputs are not visible, stop. Do not recreate or guess them.
> If Sihan's branch/artifacts are not visible, report that exact blocker … and stop. Do not compensate by editing more TFIM verifier code or beginning a competing Square/MOF implementation.

**The referenced commits and all seven listed input artifacts are absent from every
accessible ref.** Tasks 2–8 cannot be executed without them, and the packet forbids
guessing or recreating them. This note records the exhaustive visibility check and
stops at the review gate. No ledger, `.jls`, merge, or new implementation work was
performed.

## What the packet requires as inputs

From the packet's "Inputs" section:

- Sihan's visible branch/PR containing the reported commits;
- MOF model; ray; run metadata; verifier; verifier output; boundary-scan output.

The four referenced commits (from `ADVISOR_FEISHU_REVIEW_SIHAN_UPDATE_2026-07-28.md`):

```
b1a1cad  solver/export source
8c6106f  independent verifier
59f4b09  dense boundary scan
c1ae6f7  baseline
```

## Visibility check (task 1) — exhaustive and negative

### 1. Local refs

```
git cat-file -t b1a1cad  ->  fatal: Not a valid object name   (×4)
```

None of the four resolve in the local object database.

### 2. origin (iintSjds/quantum.harness fork — where PRs land)

`git fetch origin` completed; the four commits still do not resolve. No branch on
origin contains them.

### 3. flyingwagner's own fork (Sihan = flyingwagner / shhu)

Added `flyingwagner/quantum.harness` as a remote. Raw `git fetch` over HTTPS failed
with a transient TLS error (`gnutls_handshake() failed`), so the check was completed
through the GitHub REST API via `gh` (which has a working transport):

```
gh api repos/flyingwagner/quantum.harness/git/commits/<sha>
  b1a1cad -> HTTP 404 Not Found
  8c6106f -> HTTP 404 Not Found
  59f4b09 -> HTTP 404 Not Found
  c1ae6f7 -> HTTP 404 Not Found
```

The four commits are **not present on flyingwagner's fork either**. They are not
reachable from any branch on that fork:

```
flyingwagner branches include: feature/square-j1j2-gap-foundation,
  feature/structured-basis-assembly, fix/legacy-inventory-freeze-contract,
  feature/xh5-status-runner, main, … (standard set; no certificate/mof branch)
```

### 4. The three visible Sihan PRs do not contain this work

All PRs authored by flyingwagner on the iintSjds fork (`gh pr list`):

| PR | branch | single commit | subject |
|---|---|---|---|
| #1 | feature/square-j1j2-gap-foundation | `553f2e0` | polyopt: add Square J1-J2 bulk-gap foundation |
| #3 | feature/structured-basis-assembly | `7bacf01` | feat(polyopt): add reproducible structured basis manifests |
| #4 | fix/legacy-inventory-freeze-contract | `46726ab` | fix(polyopt): make legacy inventory freeze auditable |

None of `553f2e0 / 7bacf01 / 46726ab` matches any referenced SHA, and none of their
subjects covers the MOF model, independent verifier, or dense boundary scan.

### Conclusion of task 1

The four referenced commits are unreachable from local refs, origin, flyingwagner's
fork, or any open/closed PR. The most likely explanations are: (a) the SHAs were
reported from Sihan's local working tree and never pushed (or were reset/rebased
away), or (b) they live on a remote/location not among the three checked. Either
way the inputs are not visible.

## Tasks 2–8 — not executed (blocked)

Each requires the absent inputs:

- **Task 2** (TFIM config from artifact): no run-metadata artifact present.
- **Task 3** (`N=7,g=1,d=3` vs `N=9,g=0.5,d=2`): cannot be settled from
  machine-readable metadata; only the Feishu chat exists. The prior advisor Feishu
  review already showed the block inventory `[211,50]/[11,14]` matches `N=9,d=2`
  (not `N=7,d=3` → `[194,108]/[66,26]`), strongly suggesting a summary typo — but
  this remains provisional until the artifact is visible.
- **Task 4** (SHA-256 of MOF/ray/metadata/verifier/manifest): no files to hash.
- **Task 5** (static verifier one-ray binding): no verifier source.
- **Task 6** (normalization/tolerance formulas): no verifier source.
- **Task 7** (malformed-schema handling + negative tests): no verifier source/tests.
- **Task 8** (ADOPT_MOF / KEEP_LOCAL_TEMPORARILY / BLOCKED_ON_DEFECT): cannot be
  assessed without inspecting the MOF verifier. **Provisional marker: BLOCKED_ON_DEFECT
  (defect = unavailability)**, to be revisited once Sihan pushes.

## The only record of Sihan's MOF work

`ADVISOR_FEISHU_REVIEW_SIHAN_UPDATE_2026-07-28.md` captures the two Feishu messages
(≈18:27 and 18:42 on 2026-07-28). From that file, the reported numerical facts
(unverifiable here) are:

- TFIM: 23,949 vars; 2,705 affine equalities; four PSD blocks; normalized equality
  residual 2.28e-15; PSD violation 1.68e-21; normalized objective improvement 7.03e-6.
- Kagome: rejected by the same verifier (normalized equality residual 6.62e-11 vs
  declared 1e-12) — a scientifically responsible negative.
- Boundary scan: TFIM transition window (0.25075, 0.25125] with γ=0.251 unknown;
  kagome window (1.270, 1.272].

These numbers cannot be confirmed, hashed, or re-derived from any committed artifact.

## Files changed / commands run

**Files changed:** this review note only. No ledger, `.jls`, source, or merge
edits (per packet constraint).

**Commands actually run (read-only inventory):**

```
git rev-parse HEAD                                   -> 5a2425a…
git status --short                                   -> Ion.lock + 2 untracked advisor .md
git remote -v                                        -> origin / scnet / upstream
git cat-file -t <4 SHAs>                             -> all "Not a valid object name"
git fetch --all                                      -> HTTPS/SSH transient failures (network)
git fetch origin                                     -> ok; 4 SHAs still absent
git remote add flyingwagner …; git fetch             -> HTTPS TLS failure
gh pr list --repo iintSjds/quantum.harness           -> PRs #1/#3/#4 by flyingwagner
gh api repos/flyingwagner/…/git/commits/<4 SHAs>     -> all HTTP 404
gh api repos/flyingwagner/…/branches                 -> no mof/cert branch
gh pr view {1,3,4} --json commits                    -> none contain the 4 SHAs
```

**Tests run:** none (no inputs to test against; no code changed).

**Tests not run:** all of tasks 2–8 (blocked).

## Known failures / unknown statuses

- GitHub HTTPS git transport is intermittently failing from this host
  (`gnutls_handshake() failed`); the API checks via `gh` succeeded and are
  authoritative for the 404 findings.
- SCNet `ssh` hit "No route to host" once during `fetch --all`; not relevant to
  the visibility conclusion (GitHub API is the source of truth for the 404s).

## What was deliberately not done

- Did **not** poll the Feishu group for newer messages. The packet's inputs are
  commits/branch/artifacts, not chat; the relevant chat is already captured in
  `ADVISOR_FEISHU_REVIEW_SIHAN_UPDATE_2026-07-28.md`. Re-checking chat is outside
  packet 0's task list.
- Did **not** recreate or guess the MOF model, ray, verifier, or metadata
  (packet-forbidden).
- Did **not** begin a competing Square/MOF implementation (packet-forbidden).
- Did **not** modify the ledger, delete `.jls`, or merge/cherry-pick anything
  (packet-forbidden for this packet).
- Did **not** touch `Ion.lock` or the two pre-existing untracked advisor notes
  (preserved per worker-contract rule 3).

## Decision requested from advisor

The packet's stop gate is: "Stop after the review note. The advisor decides whether
the MOF path becomes the canonical contract."

This packet cannot inform that decision because the implementation is not
inspectable. The concrete unblock is the advisor's **Priority A, item 1**:

> Sihan pushes a visible branch or PR containing the referenced commits.

Recommended coordination ask to Sihan (for the advisor to approve/send, not this
worker):

1. Push `b1a1cad` / `8c6106f` / `59f4b09` / `c1ae6f7` (or their current successors
   if rebased) to a visible branch or PR on the iintSjds or flyingwagner fork, with
   the MOF model, ray, run metadata, verifier source, verifier output, and
   boundary-scan output attached.
2. Confirm the exact TFIM configuration (`N, g, d, lso, gamma`, symmetry,
   normalization) from the machine-readable run metadata — specifically whether the
   audited case is `N=9,g=0.5,d=2,γ=0.25125` (matches the block inventory) or
   `N=7,g=1,d=3` (does not).
3. State the normalization formulas behind "normalized equality residual",
   "PSD violation", "normalized objective improvement", and the `1e-12` tolerance.
4. Confirm the verifier binds one variable ordering to MOF columns, ray, objective,
   and every PSD cone block, and rejects missing/extra/malformed blocks.

Once the branch/PR is visible, packet 0 tasks 1–8 can be completed in a single
follow-up pass, after which the advisor can decide ADOPT_MOF vs KEEP_LOCAL vs repair.

## Stop

Stopping at the Work packet 0 review gate as instructed. No further work packets
will be started.
