# Benchmark v0 execution protocol

This protocol turns the Benchmark v0 reproduction into at most five short,
auditable implementation attempts. It is intentionally stricter than the
normal development workflow so that failed approaches remain useful evidence.

## Hard limits

- Attempts are numbered `01` through `05`; an attempt number is never reused.
- Every attempt runs in its own Git branch and worktree. The integration
  worktree is used only to collect verified implementation commits and attempt
  journals; implementation code is not written there.
- One attempt tests one explicit hypothesis and has at most 90 minutes of active
  implementation time. A local compute inside an attempt must remain below the
  repository's 10-minute local-compute threshold; larger work is submitted to
  the configured cluster.
- The fifth closed attempt is a hard stop. If all Benchmark v0 gates are not
  true at that point, no sixth implementation starts. Instead, produce a report
  describing the strongest result, the blocking gate(s), all five failure
  causes, and the evidence needed to justify another research direction.
- Failed worktrees, branches, concise journals, and raw run logs are not deleted
  automatically.

The 90-minute active-development timebox does not include queue waiting. A
remote smoke job should request no more than 15 minutes of wall time unless the
attempt journal states and justifies a smaller or larger bound before submit.

## Worktree layout

The coordination branch and worktree are:

```text
branch:   challenge/qmc-chiral-graviton
worktree: D:/Playground/worktrees/quantum.harness/challenge-qmc-chiral-graviton
```

Attempt `NN` uses:

```text
branch:   challenge/qmc-chiral-graviton-aNN
worktree: D:/Playground/worktrees/quantum.harness/challenge-qmc-chiral-graviton-aNN
```

Each new attempt starts from the current integration-branch HEAD. A successful
slice is integrated only after its declared tests pass. After a failed attempt,
only the standalone attempt-journal commit is brought back to the integration
branch; failed implementation commits stay on the attempt branch.

## Before an attempt starts

The attempt journal must freeze all of the following before code is changed:

1. the hypothesis being tested and why the previous evidence motivates it;
2. the smallest code and test scope that can decide that hypothesis;
3. the exact Hamiltonian, normalization, sector, system size, and target output;
4. local or remote resource choice with a cost estimate;
5. the pass condition, failure condition, and timebox;
6. the starting commit and clean baseline-test result.

No numerical computation starts until the user has explicitly confirmed the
physics setup required by the repository's `AGENTS.md`.

## Logging contract

Every attempt produces two layers of evidence.

### Tracked journal

Create
`tracks/qmc/solutions/BOTS-848/logs/attempt-NN.md` from
`logs/attempt-template.md`. It records the hypothesis, commits, exact commands,
test/run exit codes, result classification, failure mechanism, and the one
change recommended for the next attempt. Keep the journal readable and small.

The journal is committed separately from implementation code so it can be
integrated even when the code attempt fails.

### Raw local run log

Put raw output under the ignored results tree:

```text
tracks/qmc/results/BOTS-848-benchmark-v0-attempt-NN/
  commands.log
  environment.txt
  stdout.log
  stderr.log
  run.json
```

`commands.log` records the command, start/end timestamp, working directory, and
exit code. `environment.txt` records the Git commit, Python and package versions,
host/cluster identity, and Slurm job ID when applicable. `run.json` follows the
Benchmark v0 machine-readable result schema once that schema exists. Generated
data and plots remain under `tracks/qmc/results/` and are not committed.

Never write passwords, private keys, access tokens, or full sensitive SSH
configuration into either log layer.

## Closing an attempt

An attempt is closed as exactly one of:

- `benchmark-pass`: every Benchmark v0 gate is true with fresh evidence;
- `slice-pass`: the declared bounded slice passes, is integrated, but the full
  benchmark is not yet complete;
- `failed`: the declared hypothesis or test failed;
- `inconclusive`: the timebox or external resource ended before the hypothesis
  became decidable.

Closure requires fresh test output, a concise failure/lesson statement, and an
updated count of remaining attempts. A `slice-pass` still consumes one attempt.
No next attempt begins until its hypothesis differs in a concrete way from the
failure just recorded.

## Planned first attempt

Attempt 01 is limited to the `N=6`, `2Q=15` exact-diagonalization oracle and the
machine-readable result schema. It does not include the neural ansatz, VMC
training, chirality, larger sizes, or Landau-level mixing. Its purpose is to
make the Hamiltonian/normalization and `L=0` versus `L=2` identification
decidable before any expensive optimization.

