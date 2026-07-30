# Preregistered confirmation stopping cycle replacement: job 6769978

Status: stopped at the public deadline after a checksum-verified cross-cluster
resume. Phase 5 is the highest atomically published and accepted analysis.
All classifications remain provisional.

This is the pre-simulation replacement for cancelled job `6769964`. It keeps
the same preregistered stopping rule, 20,000 paired bootstrap resamples, eight
physical groups, five lockstep policies, 8-CPU/32-GiB/one-GPU allocation,
12-hour wall limit, and `2026-07-30T15:20:00` Slurm deadline. The only change
is an explicit frozen-geometry binding before tests or simulation:

```text
orchestration commit:
acddcf843753b862bde3c65300c4357b1827b4da

orchestration tree:
8dfbce4b9d50c43ace19b3483246175f37d28c02

orchestration archive SHA-256:
463232fd8ba71ba28b6fd628d778b40a4766a18896de4c27b7c089492e8be648

orchestration snapshot:
bundle-confirm-cycle-acddcf8

orchestration snapshot manifest SHA-256:
939617b217f0243a27c340112219e769489403acc80237ce737b77260d6239d7

snapshot files covered by the manifest:
146

frozen instance database SHA-256:
25e286b75968232ac04f7ad964f8fd683ec1f237bfbb794f8a1e2cbb5959f751

frozen confirmation family SHA-256:
33b4ce05177179be9036a40d5e28b66dd62219a543d391750bb28ef5b4c1635a
```

The batch preflight requires that database file to exist, match its fixed
digest, and exactly equal the `instance_file` path recorded by the initial
confirmation matrix. The snapshot manifest passed all 146 entries and the two
database files passed their independent hashes before submission.

Job `6769978` started at `2026-07-29 18:24:44 CST`. The Phase-1 analysis of
the 800,000 initial shots found all 40 cells below the 1,000-failure stopping
target. It met paired precision for 26 of 32 comparisons (`0.8125`), above the
registered 80% precision fraction, but six comparisons still required more
shots. The evidence therefore remained provisional and all eight groups
continued.

Phase 2 added another 800,000 exact-replayed shots. At 40,000 cumulative shots
per cell, all 40 cells still remained below 1,000 failures and six comparisons
still required more precision. The Phase-2 result and analysis manifest hashes
are:

```text
phase-2 result-checksums.sha256:
22b342f4d9fa140bbd04ac5cc38101078f1a94f96ad7e52256552223d3ebedda

phase-2 analysis-checksums.sha256:
41f939c4e49753b15a45633fbdd94956b773100506155d68753614b67e911a54
```

Phase 3 added 1,600,000 exact-replayed shots, bringing the total to 3,200,000
cell-shots and every cell to 80,000 cumulative shots. All 40 cells still
require continuation. As in Phase 2, 26 of 32 comparisons meet paired
precision, so the registered precision fraction remains `0.8125` and passes
the 80% gate, while six comparisons continue. The manifests are:

```text
phase-3 result-checksums.sha256 SHA-256:
75c8cf968a027001a6b40dec2bf7bf2d109371d02ea45119552899d51da35c60

phase-3 analysis-checksums.sha256 SHA-256:
cd75044d810cc6913a00b4d25b8a4865446bd81ad95631afabfe37ed6f5a14cb
```

Phase 4 added 3,200,000 exact-replayed shots, bringing the accepted total to
6,400,000 cell-shots and every cell to 160,000 cumulative shots. Four cells
reached the 1,000-failure target and 36 cells continue. All 32 paired
comparisons now meet precision, so the precision fraction is `1.0`; the
cell-level stopping rule nevertheless requires all eight groups to remain
lockstep in Phase 5. The manifests are:

```text
phase-4 result-checksums.sha256 SHA-256:
f106916773f8e6cc259c7da9b3911a3cceec22d7d47e121228afbe8ef2946305

phase-4 analysis-checksums.sha256 SHA-256:
26ab71b69144f7f0d50e146f7a4fe8d8ca7e47aa16a695810ebcde610b3385ab
```

Phase 5 ran within the same allocation and requested 160,000 additional shots
for every lockstep cell, targeting 320,000 cumulative shots per cell.

Fail-closed resume job `6770285` is registered with
`afternotok:6769978`. It will not run if this cycle completes successfully; if
the allocation fails, it selects the highest atomically published analysis,
revalidates every accepted phase, and begins only the next phase. Snapshot
`bundle-confirm-resume-7fd40c7` covers 146 files with manifest SHA-256
`73e3516ef13c3082f3ff2bf17ab6b388ad0bfb1eb5dc6e6345cdae75a59c8203`.

## Accepted Phase 5 and xh5 resume

Phase 5 completed before the original allocation reached its 12-hour wall
limit. It added 6,400,000 exact-replayed shots, bringing the accepted total to
12,800,000 cell-shots and every cell to 320,000 cumulative shots. Four cells
have reached 1,000 logical failures, 36 continue, and all 32 paired
comparisons meet precision. All eight groups therefore continue in Phase 6.

```text
phase-5 result-checksums.sha256 SHA-256:
3cf868e8d6602aecb8976244041906baf2ea4922cd41271fcd164a7cab1ef945

phase-5 analysis-checksums.sha256 SHA-256:
67ab1aa9137cb1a1568617cf3979c5e60c92a2aa3e384e4955695401edd2444b
```

Job `6769978` timed out while Phase 6 was still in an unpublished `.staging`
directory. The fail-only resume `6770285` could not start because its 17-hour
request no longer fit before the Slurm deadline. Replacement SCNet job
`6771272` remained pending and was cancelled without allocation after an xh5
resume obtained a node.

The initial result, Phase 2--5 result manifests, Phase 1--5 analysis manifests,
candidate, matrix, frozen instance database, and resume snapshot were copied
to xh5 and independently passed their SHA-256 manifests. Job `23018841`
failed closed before simulation because the supplied database path differed
from the exact path frozen in the matrix. The original
`bundle-confirm-20fb57c` snapshot was then transferred and its 144-file
manifest plus instance digest passed. Job `23018885` runs the unchanged resume
cycle on one xh5 node with 120 CPUs and 450 GiB, starting from the highest
published analysis, Phase 5.

Job `23018885` reached its 3-hour-20-minute wall-time limit at
`2026-07-30 14:52:18 CST` with Slurm state `TIMEOUT`. No Phase-6 result or
analysis checksum manifest was atomically published, so the Phase-6 staging
directory is excluded. Phase 5 remains the highest accepted confirmation
artifact at the deadline.
