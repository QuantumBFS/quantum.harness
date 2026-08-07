# Challenge #15 Route A acceptance amendment

- Date: `2026-07-29` (`Asia/Shanghai`)
- Applies to: A02 through the final Route A audit
- Parent terminal SHA: `af46912cdb961ef405b338f93168b929fe716a3c`
- Comparison base SHA: `5aa9219f4cd24bc2274f0514b621c2f9b47cead7`
- Protocol SHA-256: `2435cd2e72ffae88117ee194f45b15451c8653dafa755b732005b6a199251d38`

## Approved contract revision

The user explicitly approved resuming Route A with the following acceptance
policy:

1. Numerical correctness remains a hard gate.  The exact-dyadic, subnormal,
   halfway, order-invariance, global-shift, zero, and coefficient-boundary
   regressions may not be weakened or bypassed.
2. The N=6 local-energy timing ratio remains mandatory evidence, but it is a
   resource metric and optimization backlog item rather than a blocking gate.
3. The measured try-5 ratio, `2.139495843x`, is acceptable for A02 when the
   correctness tests and all other A02 gates pass.  It must be reported without
   rounding it below `2x`.
4. Reconstructing the already-tested try-5 correctness implementation under
   this revised contract is not an unauthorized sixth numerical rescue.  The
   prior five worktrees and journals remain the complete history of the retired
   joint correctness-plus-`2x` contract.
5. Any newly discovered, independent blocking bug starts its own bounded
   root-cause series: one worktree and journal per implementation attempt,
   at most 90 minutes per attempt, and at most five attempts.

The common ED evaluator remains behind the four-route barrier.  No push is
authorized.

## Worktree setup note

The first requested checkout path was 118 characters long; one tracked
literature filename made the full Windows path 261 characters while the host
had `LongPathsEnabled=0`.  Git therefore aborted before registering a worktree.
No implementation began and Git removed the partial checkout automatically.
The same branch was then checked out at the shorter path
`D:/Playground/worktrees/quantum.harness/challenge-qmc-cg-s02a-a02-accepted`
with per-command `core.longpaths=true`.  This environmental setup failure is
not an A02 implementation attempt.
