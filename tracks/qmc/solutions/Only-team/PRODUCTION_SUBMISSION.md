# Challenge production submission

Submission date: 2026-07-29

## Physical and statistical setup

```text
H = J1 Σ_<i,j> σᶻ_i σᶻ_j − hTrfd Σ_i σˣ_i
J1 = −1
J2 = 0
periodic boundaries
BetaT = L/hTrfd
nLocal = 1
nWolff = 5
nWarm = 10000
NmBin = 32
NSwep = 2000
NmMeaConfg = 10
MPI ranks per cell = 32
```

The submitted work contains 149 new cells:

| Lattice | Intermediate grid | Time-step grid | Total |
|---|---:|---:|---:|
| triangular | 42 | 36 | 78 |
| honeycomb | 35 | 36 | 71 |
| total | 77 | 72 | 149 |

The time-step grid uses requested `FixedDltau = 0.013, 0.016, 0.020`.
The 12 half-field-step cells missing from the completed `0.013` main grid
are included.  Completed extreme-size cells at matching fields are reused
rather than submitted again.

## SCNet jobs

Remote root:

```text
/work/home/acyv3xww1l/qmc-tfim-challenge-production-20260729-a
```

| Coverage | Job ID | Slurm form | State at settle check |
|---|---:|---|---|
| triangular cells 1–78 | 22989492 | array `1-78%8` | running |
| honeycomb cells 1–10 | 22989502 | array `1-10%8` | running |
| honeycomb cells 11–71, bundles 1–7 | 22989546 | array `1-7%7` | queued |
| honeycomb cells 11–71, bundle 8 | 22989553 | array task `8` | queued |

The account group allowed at most 200 submitted tasks and approximately
11 simultaneous running tasks at submission time.  The remaining 61
honeycomb cells therefore use eight round-robin sequential bundles.  Each
scientific cell still runs with 32 MPI ranks and writes an independent
configuration, native output set, and manifest.  The bundle mapping covers
every run-spec index from 11 through 71 exactly once.

## Submission verification

- The local and remote source and run-spec SHA-256 lists matched.
- The complete local Julia test suite passed, including the MPI smoke test.
- The normal triangular and honeycomb Slurm scripts passed resource and
  secret guardrails.
- Remote Julia and MPI package loading passed.
- The first eight triangular cells completed successfully while settling
  the submission.
- The first recorded cell used 32 distinct rank seeds and produced all
  32 bins:

```text
triangular L=12 hTrfd=4.76511 FixedDltau=0.013
binder_Q = 0.5468845892096384
binder_Q_error = 0.0002827249083401224
wall time = 164.60963582992554 s
```

No Git commit, push, or pull request was created.

## Handoff for a later commit

Before committing:

1. Fetch and validate all remote manifests; the result directories remain
   gitignored and must not be force-added.
2. Run the complete Julia test suite:

   ```bash
   julia --project=tracks/qmc/solutions/Only-team \
       tracks/qmc/solutions/Only-team/test/runtests.jl
   ```

3. Review and stage only explicit paths under
   `tracks/qmc/solutions/Only-team/`; do not use `git add .`.
4. Keep the pre-existing `.knowledge/` changes out of the code commit unless
   they are reviewed and intentionally committed separately.
5. Confirm `git diff --cached` contains no result files, credentials, Windows
   absolute paths, or unrelated changes before creating the commit.

The production-specific additions to retain are the explicit scan-cell
interface, scan-spec generator, normal and bundled Slurm runners, their
tests, and this submission record.  At the time of this handoff the Git
staging area is empty.
