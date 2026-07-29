# xH5 / Slurm failure lessons

This is the compact operational memory for Challenge 88. It records reusable
failure signatures and changed actions, not credentials or routine logs.

## Shipping source

- The default xH5 Git is `1.8.3.1` and rejects `git -C`. Use
  `cd <repo> && git ...`, or load `git/2.30.2-gcc-7.3.1` when newer Git
  behavior is required.
- Push local commits to the private bare remote; do not make the compute host
  fetch GitHub. If an NFS-backed checkout update stalls and the scientific
  run needs only one audited fix, copy that explicit file, compare SHA-256 on
  both sides, and retain `runner-commit.txt` plus `git-status.txt` in the run.
  Do not broad-rsync a dirty tree.
- Locale warnings about missing `C.UTF-8` are non-critical. Ignore them only
  after the command exit status and machine-readable output are checked.

## Submission state

- `AssocGrpSubmitJobsLimit` can reject `sbatch` before a job ID exists. That
  attempt is not submitted and must not be reported as queued.
- `AssocGrpJobsLimit` can leave an accepted job pending. A real job ID exists,
  but no compute has started. Do not submit a duplicate; recheck `squeue` and
  `sacct` until the group slot changes.
- A delayed SSH or `sbatch` response is not permission to retry. Wait for an
  explicit exit status or job ID, then query the scheduler separately.
- Always export every fail-closed input explicitly. The rational replay needs
  `SS_INPUT_POINT`, `SS_SOLVE_POINT`, and a unique `SS_RUN_ID`; a new run ID
  is mandatory after any failed attempt.
- Create the parent directory named by `#SBATCH --output` before submitting
  from a clean clone. Gitignored `results/` directories are absent from a
  fresh checkout; Slurm otherwise fails with `JobLaunchFailure`, signal 53,
  before the batch script can print anything.
- Preserve the path contract of each runner. The rational replay accepts
  repository-relative paths so containment can be checked; passing absolute
  paths fails before assembly even when the files exist.

## Preflight and interpretation

- Test parsers with the concrete types produced by file APIs. Julia `split`
  returns `SubString{String}`; a helper restricted to `String` caused job
  `22990387` to fail before assembly. The fix accepts `AbstractString` and has
  a dedicated regression.
- Keep the cheap focused test local only while measured peak RSS stays below
  the user threshold. The helper suite used 287,280 KiB; the full replay stays
  on xH5 because it may exceed 1 GiB.
- `sbatch` success, `PENDING`, `RUNNING`, and even scheduler `COMPLETED` are
  operational states, not a certificate. Fetch checksummed artifacts and
  inspect the replay exit code plus all exact rational LDL pivots before
  claiming an exact witness.
