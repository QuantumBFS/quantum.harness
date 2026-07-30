# Preregistered confirmation stopping cycle: job 6769964

Status: cancelled during local/remote static preflight while the
`afterok:6769918` dependency was still unfulfilled. No allocation started, no
test or simulation ran, and no confirmation statistic or scientific claim is
recorded.

Job `6769964` is one consolidated `dzagnormal` allocation with 8 CPUs,
32 GiB, one required GPU, a 12-hour wall limit, and Slurm deadline
`2026-07-30T15:20:00`. It first runs the focused confirmation contracts and
then analyzes the initial 40 cells with 20,000 paired bootstrap resamples per
comparison. Any continuing physical group doubles cumulative shots while all
five policies remain paired. The same allocation repeats analysis, simulation,
and exact replay until every cell reaches 1,000 logical failures or the
20,000,000-shot cap and every unresolved precision comparison either passes or
reaches that cap.

```text
orchestration commit:
94d48b90f898be9f668626b4a126e8cdeb363743

orchestration tree:
7e04f1dc1dea3d7c8f15229c45fdf92f5a0628d6

orchestration archive SHA-256:
b2467e3f3fab5dca79dc6b6233cdeff3270b3f299fd55c02239812aa88d292e5

orchestration snapshot:
bundle-confirm-cycle-94d48b9

orchestration snapshot manifest SHA-256:
18bfcb1976f8fb38b4479cac496500015090eb91ed3603f46a9842818db2d1fe

snapshot files covered by the manifest:
145

initial confirmation job:
6769918

candidate commit:
0a73ba334a4b85403634e710f3d768ef8831d16d

accepted candidate tree SHA-256:
829ade4b3ab7408c9151a6a06222e6779df6c65096b8d2e2d947e26238140482
```

The first snapshot-staging command created `snapshot-checksums.sha256` before
the file traversal and therefore included the manifest in itself. Its checksum
verification failed before publication. That failed staging directory is
preserved as `.bundle-confirm-cycle-94d48b9.failed-self-reference`. The
published read-only snapshot was rebuilt from the unchanged archive with the
manifest explicitly excluded from its own traversal, and all 145 entries
passed before submission.

An initial 16-CPU/64-GiB submission request was rejected before job creation
because that node configuration was unavailable. Job `6769964` uses the
already demonstrated 8-CPU/32-GiB SCNet configuration; neither event consumed
a validator attempt or produced simulation evidence.

After submission, inspection showed that the Git orchestration snapshot did
not contain the generated `surface_code_instances.jsonl`, while the script
incorrectly exported a path beneath that snapshot. Job `6769964` was cancelled
before dependency release. Replacement job `6769978` requires an explicit
instance path, verifies its fixed SHA-256, and requires the same path in the
initial confirmation matrix.
