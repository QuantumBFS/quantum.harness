# Challenge 88 active state

Updated: 2026-07-29 UTC.

- Fixed setup: Shastry--Sutherland `J_dimer=1`, `J_square=4/5`,
  level-1 local-consistency window, unrestricted KMS class, `d=2`.
- Exact finite-relaxation reduction remains unchanged: 74,602 source moments
  to 19,108 invariant moments; 11 PSD blocks; maximum side 109.
- Active branch: `bohr/challenge88-ss-reduced-runner`, based on
  `5e84422586c8de8acb58699a1102a28353291562`.
- Gamma=0 truth gate: passed on attempt r3, Slurm job `22987983`.
- Attempt `ss-reduced-g0p8-gamma0-xh5-20260729-r1`, Slurm job `22987967`,
  validated both input hashes, all runmeta fields, and every source-file hash,
  then stopped before Mosek because MOF reload exposes the Hermitian cone value
  in packed-vector form. Peak process RSS was 736,680 KiB.
- The next runner revision explicitly reconstructs Hermitian matrices from
  MOI's real-upper/imaginary-upper packing. This is a consequential decoding
  change; the failed attempt is not being repeated unchanged.
- Attempt `ss-reduced-g0p8-gamma0-xh5-20260729-r2`, Slurm job `22987979`,
  passed the complete MOF structure gate, then stopped before `optimize!`
  because MosekTools 0.15.10 requires the raw string attribute
  `MSK_IPAR_NUM_THREADS`, not Mosek.jl's enum. Peak process RSS was
  667,068 KiB. The next revision changes that optimizer API call.
- Attempt `ss-reduced-g0p8-gamma0-xh5-20260729-r3` returned `OPTIMAL` with
  primal and dual `FEASIBLE_POINT`. Normalization was exactly 1; all three
  affine residuals and the worst PSD violation were 0 at the declared `1e-7`
  audit tolerance. The smallest eigenvalue across all 11 reconstructed blocks
  was 0.0948505094335904. Solver wall was 444.861 s; peak process RSS was
  46,385,640 KiB. `result.toml` SHA-256 is
  `ec362cdf456a7ad7f180ce2418bcea1b547f831c8d0c21cfc827844b2e06258e`.
- Gamma=1/2 target: passed on attempt r1, Slurm job `22988032`. Mosek returned
  `OPTIMAL` with primal and dual `FEASIBLE_POINT`; normalization was exactly 1,
  all three affine residuals and the worst PSD violation were 0, and the
  smallest block eigenvalue was 0.08943315828795756. Solver wall was
  407.505 s; peak process RSS was 44,494,548 KiB. `result.toml` SHA-256 is
  `63c3ed036605c9ed15e67e762115bf73f67b1724b7e6ea6281cf21559b1dc021`.
- Terminal status: the requested exact finite relaxation is numerically
  feasible at gamma=1/2. This does not prove a physical bulk gap; it says this
  `d=2` relaxation does not exclude gamma=1/2.
- Required solve order was satisfied: gamma=1/2 ran only after the
  residual-checked gamma=0 result.
- Compute boundary: all MOF reload/solve work runs through Slurm on xH5;
  Bohrium and xH5 login are limited to source checks, Git, transfer, queue
  inspection, and artifact collection.
- The generic Hermitian-to-real solver bridge scalarizes the eight positive
  blocks into 126,525 semidefinite coordinates and produces a
  1.45--1.51-billion-nonzero factor. This representation, rather than the
  maximum side dimension 109, explains the 44--46 GiB solve peak.
- Active exact-memory route: computational-basis conjugation averaging plus
  a diagonal phase gauge. If its exhaustive xH5 truth gate passes, the same
  finite relaxation uses real PSD blocks with 31,807 positive-cone
  coordinates, plus three scalar gap blocks. No immutable source file or
  supplied MOF is modified.
- Conjugation truth attempt r1, Slurm job `22988127`, passed all 58 assertions
  in the exact M/K/V4 testset in 102.2 s. The broader wrapper was then
  canceled during an unrelated dense-ED tail after 12:34; its truth-log
  SHA-256 is
  `db7d0326ad6079cad348cfc8c504e3841545a76237742fc7c21feae5cd78b70f`.
- Derived-MOF build attempt r1, Slurm job `22988179`, failed before assembly
  because a line-broken `@timed` macro call did not expand. Peak RSS was
  532,916 KiB. The corrected builder places the macro argument on the same
  expression and receives a local load/`--help` check before r2.
- Derived-MOF build attempt r2, Slurm job `22988194`, passed macro expansion
  and stopped in provenance collection before assembly because xH5's older
  Git does not support `branch --show-current`. Peak RSS was 642,716 KiB.
  The next revision uses portable `symbolic-ref --short HEAD`.
- Derived-MOF build attempt r3, Slurm job `22988216`, then failed closed
  before assembly because Slurm created its stdout file as an untracked file
  at the repository root. Peak RSS was 626,716 KiB. Scheduler stdout is now
  directed into the ignored track-results tree so the clean-source gate
  measures code rather than its own job log.
- No decision-changing user or resource need is open.
