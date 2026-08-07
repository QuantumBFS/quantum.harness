# Discovery preparation and bundled phase 1

The public initial discovery phase uses the exact validated reference candidate
and does not consume one of the 24 autoresearch attempts.

## Resource preparation

Job `6760553` completed `0:0` and generated the first 280-group matrix and
snapshot. Its resource report authorized individual groups, but the subsequent
submission was rejected before job creation because the account-level
`AssocGrpSubmitJobsLimit` permits at most 200 submitted jobs and Slurm counted
all 280 array elements. No discovery simulation ran under that submission.

The deterministic bundle layout reduces the scheduler elements to 182 while
preserving all 280 physical groups:

```text
d=3, T=3:   4 groups/task, 18 tasks
d=3, T=6:   3 groups/task, 24 tasks
d=5, T=5:   1 group/task,  70 tasks
d=5, T=10:  1 group/task,  70 tasks
```

The group manifest records the actual bundle task ID. Analysis derives the
same frozen mapping from each source group index and rejects a mismatched task.

Job `6766556` reran the combined checksum, resource, deterministic matrix, and
snapshot preparation after this scheduler correction. It completed `0:0` in
31 seconds. Its report has `status=passed` and
`discovery_authorized=true` with:

```text
worst projected array task: 2639.0097798134775 s
hard wall limit:             2700 s
projected initial storage:   4522612500 bytes
storage limit:               21474836480 bytes
validated peak RSS:          322072 KiB
RSS limit:                   16777216 KiB
projected total GPU time:    97.97674237191814 h
```

## Frozen identities

```text
candidate source commit:
0a73ba334a4b85403634e710f3d768ef8831d16d

bundle orchestration commit:
40684d8142f37660a94e09d1ec9b7b545064b540

discovery matrix SHA-256:
75490cff0949dc128221bf9168138d4d813c07014f26c1c9cacac9b2ec6b9b18

bundle snapshot manifest SHA-256:
690943136179a9797b7c8e1c7b702dfbf5d0c9a3a31da1f8b05cf32088236f25
```

The formal phase-1 array is job `6766558`, range `0-181%8`, dependent on
`afterok:6766556`. It writes immutable group outputs below
`results/discovery/phase-1/6766558`.

Transfer packaging job `6766586` depends on `afterok:6766558`. It will reject
any phase layout other than the exact 280 group directories, require every
group manifest, and emit one tar archive plus SHA-256 for transfer to the
locked xh5 analysis environment. It does not run or repeat a simulation.

## Phase-1 completion and noncritical archive failure

At 2026-07-29 20:12 CST, all 182 array elements completed with exit `0:0` and
published all 280 immutable group manifests. Direct in-place analysis job
`6769992` then started through its registered `afterok:6766558` dependency.

Transfer-only job `6766586` started after the same dependency and exited
`64:0` in three seconds because the SCNet `tar` implementation rejects the
GNU-specific `--sort=name` option. It did not alter or repeat any simulation,
and it is not an input or dependency of the direct analysis. No replacement
archive job was submitted because the accepted results and analysis are
co-located on SCNet and the hard-deadline path does not require this transfer.

## Deadline scheduling adjustment

At 2026-07-29 16:02 CST, the live array throttle was raised from 8 to 32 without
changing its 182 elements, inputs, or outputs. Slurm still ran only 8--9 tasks
because of available shared-cluster resources. The throttle is reduced to 7
while the independent-seed confirmation requests one SCNet GPU allocation, so
the older discovery array cannot immediately reclaim every released GPU. After
confirmation obtains an allocation, the discovery throttle may return to 32.

At 2026-07-29 17:00 CST, the throttle was reduced again from 7 to 1 after the
confirmation start estimate moved beyond the one-day research deadline. Tasks
already running were allowed to finish and no valid discovery output was
cancelled. The pending initial confirmation start estimate subsequently moved
from 22:27 to 18:02 CST. The throttle may return to 32 after confirmation
actually starts.
