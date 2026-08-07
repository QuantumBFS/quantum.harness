# YueYuan Challenge 113 Submission Package Design

**Date:** 2026-07-30
**Status:** Approved for implementation
**Pull request:** QuantumBFS/quantum.harness#203

## Goal

Turn the existing challenge #113 solution into a judge-ready submission that
satisfies two requirements:

1. A reviewer has enough information to reproduce the reported results.
2. A reviewer has one clear, human-readable file explaining why the results
   are useful and technically credible.

The finished pull request will be marked ready for review only after the
documented commands have been verified from a clean environment.

## Submission Structure

### Human-facing argument

Add `tracks/qcs/solutions/YueYuan/SUBMISSION.md` as the primary judging entry
point. It will contain:

- a one-sentence verdict;
- the research question and the answer supported by the experiment;
- a compact table of the strongest numerical evidence;
- an explanation of practical usefulness;
- an explanation of correctness, including the sealed black-box boundary,
  finite-shot accounting, fair optimizer budgets, holdout split, uncertainty,
  and automated tests;
- the strongest negative result and the resulting claim boundary;
- direct links to the implementation, detailed report, and reproduction guide.

The file will distinguish demonstrated software black-box calibration from
future real-hardware validation.

### Reproduction guide

Add
`tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPRODUCE.md`.
It will specify:

- supported Python and tested package versions;
- creation of a clean virtual environment from a fresh checkout;
- a quick reproduction tier for tests and a small sealed benchmark;
- a moderate tier that reproduces the 48-shard sealed holdout study;
- the full sweep entry points used for the broader report;
- expected output files, record counts, and headline aggregate values;
- CPU and memory expectations;
- the fact that generated data belongs under `tracks/qcs/results/` and remains
  outside git.

No private cluster identity, hostname, credential, key path, or login command
will appear in the guide.

### One-command quick check

Add a small executable script under the attempt-004 directory that:

1. runs the focused attempt-004 tests;
2. runs the validator self-test;
3. runs the fast sealed black-box holdout benchmark;
4. checks the expected output files and row counts;
5. exits nonzero when any step fails.

The script will accept an output directory and write only generated files under
that directory. The default output location will be inside the ignored results
tree.

## Evidence Model

The submission will make three evidence levels explicit:

1. **Automated correctness evidence:** unit and integration tests, validator
   controls, complete-shard checks, and the optimizer/scorer separation.
2. **Fast reproducible evidence:** a small deterministic-seed sealed
   black-box run that finishes locally and checks the end-to-end data path.
3. **Research evidence:** the completed moderate and full sweeps, with exact
   configurations, seed counts, aggregate metrics, uncertainty, and honest
   failure cases recorded in the report.

The quick tier is not presented as statistically equivalent to the larger
sweeps. It verifies the pipeline. The moderate and full tiers reproduce the
reported statistical claims.

## Dependency Strategy

Keep the short dependency list for readability and add a tested, pinned
environment file for exact reproduction. The pinned versions will come from
the environment used to rerun the submission checks, not from guessed version
numbers.

The reproduction guide will explain both paths:

- pinned installation for exact checking;
- ordinary requirements installation for compatible development.

## Verification

Before publication:

1. Create a fresh temporary virtual environment.
2. Install the pinned dependencies.
3. Run the one-command quick check.
4. Run the complete YueYuan attempt test suite.
5. Run the validator self-test.
6. Check repository formatting.
7. Scan the public submission paths for private HPC markers.
8. Confirm that `Ion.lock` and unrelated files are not included.

If fresh-environment installation exposes a compatibility problem, fix the
reproduction package and rerun the checks before updating GitHub.

## Pull Request Update

Update PR #203 so its first screen contains:

- the verdict and strongest numbers;
- links to `SUBMISSION.md` and `REPRODUCE.md`;
- the exact quick reproduction command;
- the real-hardware claim boundary;
- current verification results.

Publish only the intended solution and design files to the existing PR branch.
Because the local branch contains historical commits not meant to replace the
clean public branch history, use the established clean-tree snapshot publishing
method instead of pushing the local commit chain directly.

After confirming that the remote tree matches the intended local tree and that
the PR body renders correctly, convert PR #203 from draft to ready for review.

## Acceptance Criteria

The submission is complete when:

- a new reader can find the main claim in one click;
- a fresh environment can execute the quick path successfully;
- the moderate and full commands are fully specified;
- expected outputs and reported metrics are stated beside the commands;
- usefulness, correctness, and limitations are argued in plain language;
- no generated results or private HPC details are committed;
- PR #203 is open and ready for review.
