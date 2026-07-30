# Official Challenge-113 sync plan

## Current PR #184 synchronization

Status: prepared on 2026-07-30 for teammate review before merge

This section supersedes the historical path and branch names below. The
registered submission is:

```text
Pull request: https://github.com/QuantumBFS/quantum.harness/pull/184
Head branch: thy10817/quantum.harness:challenge/qcs-sim-to-real-gates
Solution root: tracks/qcs/solutions/gpt-5.6/
Team package source: thy10817/Sim-to-real-simulation main at 23d301b
```

The synchronized solution contains exactly the 109 entries in
`team_submission_allowlist.txt`. Its root `README.md` is the human entry point;
`final/report.html` is the organizer-compatible four-section offline report.
The registration-era prototype remains available in Git history and is
replaced in the visible solution tree by the independently audited package.

The pull request must remain open and unmerged until the team reviews the
rendered report, claims, commands, and staged file list. No operation in this
sync marks a PR ready, approves it, or merges it.

---

## Historical preparation record

Status: prepared but not executed
Validated scientific package source: `2f1b987`
Submission day: the team-agreed Thursday

## Why a clean sync is required

The existing local official checkout is intentionally left untouched. It
contains a modified registration README plus many untracked historical files.
It also contains the protected upstream notebook
`neural_schrodinger.ipynb`, whose audited SHA-256 is:

```text
555C20BA0D5E95F81A714D55E8AD3D55B09FF849C2C7C535E07E15EC9A8B2F9E
```

Attempting to clean that checkout or using broad staging would create
unnecessary risk. The final sync must use a fresh clone or clean worktree of
the existing official challenge branch.

## Source-to-destination mapping

Public sources:

```text
<entry in team_submission_allowlist.txt>
```

Official destination:

```text
tracks/other/solutions/QL1F/<same entry>
```

The authoritative fallback whitelist is `team_submission_allowlist.txt` (109
files). It includes the exact 61-entry core whitelist plus the validated
robustness package. Keep the core package under
`QL1F/core-sim-to-real/`; do not flatten it into the solution root. The
registration README already present on the official branch must be merged
with the team README rather than blindly overwritten.

## Minimal-package validation already completed

A 37-file baseline candidate built from public commit `925e2d3a` was extracted
outside the public repository and tested without access to other historical
attempts. It passed:

- simulator-free final audit: 18/18;
- final artifact contract tests: 5/5;
- MWE: 7/7 with all 66/166/166 query rows;
- full public replay: 15/15 and 288/288 runs; and
- exact archived Attempt-49 summary reproduction.

The current 61-entry core closure was independently archived from public
commit `2f1b987` and extracted outside the repository. It passed compilation,
18/18 Attempt-50 checks, 11/11 Attempt-51 checks, 22/22 Attempt-52 checks,
7/7 final-contract tests, MWE 7/7, and full replay 15/15 with 288/288
completed runs and exact archived-summary equality.

The original 111-entry team archive from the same scientific commit contained
exactly the reviewed files, no protected notebook, and no personal absolute
path. The later 112-entry closure added
`tools/validate_team_package.py`, a standard-library machine check for that
contract. The current 109-entry fallback closure additionally includes the
robustness validator, scientific comparator, provenance record, fresh-run
seal, and the small self-contained fresh scientific evidence needed to rerun
that comparison.
The optional paper-reconstruction workspace is excluded unless PR #2 closes
all G1–G8 review gates before the Thursday cutoff.
Independent Python-3.12 environments passed the paper-reproduction MWE and
the robustness baseline and full runs. The full robustness run reproduced
3,951 numerical and 402 categorical scientific values with zero mismatches.

The 116-entry candidate built from public commit `b5cac3c` passed all 23 team
checks under strict closure. Its archive SHA-256 is
`3B6D9614E036166ADC07ADF595E2B0C94982EE4238D1E0CED85DEAED255F3821`.
`TEAM_SUBMISSION_PLAN.md` records the package separation and the three claim
boundaries.

## Thursday procedure

1. Fetch the official fork and upstream repository.
2. Create a fresh worktree or clone at
   `challenge/other-sim-to-real-quantum-gates`.
3. Confirm the tracked registration README and the existing PR number.
4. Copy the team-allowlisted public files from the latest reviewed public `main`
   that contains this plan. The scientific result remains sealed to the
   provenance recorded in the final artifacts.
5. Manually merge team names, roles, `Addresses #113`, and reproduction
   commands into the official README.
6. Verify no notebook, `run_outputs/`, cache, virtual environment, proxy,
   credential, or personal absolute path is present.
7. Run:

   ```bash
   python tracks/other/solutions/QL1F/tools/validate_team_package.py \
     --root tracks/other/solutions/QL1F
   python tracks/other/solutions/QL1F/core-sim-to-real/code/attempt50_result_audit.py \
     --verify-only
   python tracks/other/solutions/QL1F/core-sim-to-real/code/attempt51_queries_to_target.py \
     --verify-only
   python tracks/other/solutions/QL1F/core-sim-to-real/code/attempt52_gap_invariant_audit.py \
     --verify-only
   python tracks/other/solutions/QL1F/core-sim-to-real/run_challenge.py --mwe
   python tracks/other/solutions/QL1F/core-sim-to-real/tests/test_final_contract.py
   ```

8. Render the core report with the organizer's UTF-8-capable report workflow
   and verify the four sections and all three embedded figures.
9. Stage only explicit allowlisted paths.
10. Inspect `git diff --cached --name-status` and
    `git diff --cached --check`.
11. Commit and push the existing challenge branch.
12. Update the existing PR description and team metadata. Mark it ready for
    review only after the team checks the rendered report.

## Hard stop conditions

Stop rather than improvise if:

- the official branch or PR changed unexpectedly;
- a teammate has edits under the same destination paths;
- the protected notebook appears in staged changes;
- a formal Attempt-49 hash differs;
- any static audit, MWE, test, or report check fails; or
- final team names/roles are still unresolved when the PR metadata is edited.
