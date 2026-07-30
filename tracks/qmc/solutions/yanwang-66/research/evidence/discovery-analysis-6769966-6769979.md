# SCNet direct Phase-1 discovery analysis

No scientific result is recorded yet. Both jobs depend on completion of the
formal discovery array `6766558` and neither is a validator attempt.

Job `6769966` was submitted with an input path under the generic Git snapshot,
which does not contain the generated discovery matrix. The path check failed
immediately after submission while the dependency was unfulfilled, and the
pending job was cancelled before allocation.

Replacement job `6769979` used the frozen matrix already generated on SCNet,
but was cancelled while its dependency remained unfulfilled. Static review
showed that the generic analysis script did not emit the registered
continuation bundle summary and did not verify the outer orchestration snapshot
or matrix digest inside the allocation.

Final replacement job `6769992` uses the same matrix and results, with those
gates combined into the same allocation:

```text
matrix:
/work/home/hesicheng5/quantum-harness-ch66/research/requests/discovery/discovery-matrix-v1.json

matrix SHA-256:
75490cff0949dc128221bf9168138d4d813c07014f26c1c9cacac9b2ec6b9b18

analysis code snapshot:
bundle-analysis-6f17b2c

analysis snapshot manifest SHA-256:
9673112e122253840ff4faa4a30b25cf13d58f9a89aed0561c2a107073ddf167

analysis commit:
6f17b2c8dcf46addb0071c05907ae1688d62574d

analysis tree:
f8d4f5a762f050bc1bfe8e464b1ca58972dce310

dependency:
afterok:6766558

Slurm deadline:
2026-07-30T15:20:00
```

The 8-CPU/32-GiB/one-GPU allocation verifies all 148 snapshot files, the
matrix, frozen contract geometry and confirmation family, and the combined
experiment/discovery/confirmation/sensitivity contracts. It then reads the
original immutable SCNet phase root, performs the registered 20,000-resample
analysis, creates the continuation bundle summary, and verifies both analysis
and bundle checksums before atomically publishing the directory. This removes
the transfer/import copy from the critical path without changing any matrix
request, result artifact, checksum, or statistical rule. Acceptance still
requires an exit `0:0`, exactly 280 groups/2,240 cells, complete manifest and
shard validation, and checksummed analysis outputs.

## Accepted Phase-1 analysis

Job `6769992` completed in 21 minutes 18 seconds with exit `0:0`; all 37
contracts passed before analysis. The checksummed result contains exactly 280
groups, 2,240 cells, 1,960 paired comparisons, and 44,800,000 cumulative
cell-shots. Eight cells reached the failure target, while 2,232 cells and all
280 groups require continuation. The 348 `helpful` and 1,612
`no_significant_difference` classifications are therefore all provisional.

```text
status:
provisional

analysis-checksums.sha256 SHA-256:
2b85f3da6a5c55a5c397bfb40ababa9094953f05e9140fd05791f130ac4dea08

continuation-bundles.json.sha256 SHA-256:
90060f78c5fbc2d5fead3936bdba97730fd2dbf1da68a13588c8d71cdf3e5928

continuation-plan.json SHA-256:
ded977b2646a3f7704a2408ab856df4af611641c1f88133035ad061afe2cd215
```

The bundle summary contains five disjoint long-running tasks covering source
groups 0--279 exactly once. Its recorded plan pathname retains the atomic
staging name used before publication; Phase-2 job `6770290` uses the published
plan at `analysis/phase-1/6769992/continuation-plan.json` and requires the same
SHA-256. Dependent incremental analysis job `6770292` will run only after all
five array elements complete.

## Accepted Phase-2 analysis and Phase-3 continuation

Array `6770290` completed all 280 groups with exit `0:0`. Its dependent
analysis `6770292` failed before analysis because the generated matrix was not
inside the immutable Git snapshot. Replacement `6771280` also failed closed
before analysis because the newer Git archive did not contain the generated
instance database required by its live-versus-snapshot geometry gate. Neither
failure changed or reread a result shard.

Job `6771281` used a snapshot derived from `bundle-analysis-6f17b2c` with only
the matrix path fix from commit `612235f` plus the frozen instance database
whose SHA-256 is
`25e286b75968232ac04f7ad964f8fd683ec1f237bfbb794f8a1e2cbb5959f751`.
The 150-file snapshot manifest SHA-256 is
`cfb333bdde2887d173e29d4bb45752ad5fd79728981595d3c6d247353fe28292`.
Job `6771281` completed in 21 minutes 20 seconds with exit `0:0` and both
published checksum manifests passed.

The accepted Phase-2 analysis contains 2,240 cells, 1,960 comparisons and
89,600,000 cumulative cell-shots. Twenty-seven cells reached the registered
failure target; 2,213 cells and all 280 lockstep groups continue. The 436
`helpful` and 1,524 `no_significant_difference` classifications remain
provisional.

```text
status:
provisional

analysis-checksums.sha256 SHA-256:
945f798bbfefe7e85c5730cebd65f3fe48501d39cb76602c56e1ff338cc292bd

continuation-bundles.json.sha256 SHA-256:
10eb092ec3f1e68058c27041356020d3a3d7431dc2d3021d4009291b2fa0319e

continuation-plan.json SHA-256:
c2183dcaa8aad272d7eb77050aedefb38ad24f85e78687ba965e943ebe753519
```

The new bundle manifest covers source groups 0--279 exactly once in seven
large tasks. SCNet Phase-3 array `6771697` reached its scheduler deadline
without allocation, and dependent analysis `6771699` was cancelled without
allocation. The two validated analysis snapshots and Phase-2 analysis were
copied to xh5, where all snapshot, analysis, bundle and plan checksums passed.
xh5 Phase-3 array `23019121` used range `0-6%7`; all seven elements completed
with exit `0:0`. Dependent analysis `23019135` failed closed before publishing
because the transferred tree lacked the Phase-1 continuation plan. The missing
Phase-1 analysis was then transferred and its checksum manifest passed.
Replacement analysis `23020995` ran for 45 minutes but reached its wall-time
limit at `2026-07-30 15:12:20 CST` without atomically publishing a Phase-3
manifest. The Phase-3 array data remain archived, but Phase 2 is therefore the
highest accepted discovery analysis at the deadline.
