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
- Derived-MOF build attempt r4, Slurm job `22988221`, completed both gamma
  inputs from clean commit `25a8311`. The exact conjugation quotient has
  16,660 moments, eliminates 2,448 additional V4 moments, retains the same 11
  block sides, and uses 31,810 real PSD triangle coordinates. All three
  prior affine equalities restrict to exact zero. Gamma=0 model SHA-256 is
  `0a2c9166eb033a2e782ab91a062491961a5d8139a1b04e80f6f564d1a75a6e14`;
  gamma=1/2 is
  `b50d66a48a45de0f2a25e411ab3dcc6a06f3a99b06626951277ae09686062707`.
  Job peak RSS was 819,548 KiB and elapsed time was 4:09.
- Next gate: the separate real-cone runner must pass gamma=0, independently
  reconstructing all 11 packed symmetric matrices, before gamma=1/2 can run
  with the reduced memory request.
- Real-cone gamma=0 truth gate passed on attempt r1, Slurm job `22988279`.
  Mosek returned `OPTIMAL` with primal and dual feasible points;
  normalization was exactly 1, worst PSD violation was 0, and the smallest
  independently reconstructed block eigenvalue was 0.09561232145445703.
  Total runner wall was 93.057 s and peak process RSS was 5,917,112 KiB.
  Mosek's factor had 111 million nonzeros after factorization versus
  1.45 billion in the Hermitian-bridge baseline. `result.toml` SHA-256 is
  `de1b023911579f1952d7585524730c2e77b248997b98d467b9f0c9b58d50dc36`.
- The exact real representation has therefore passed its independent
  gamma=0 numerical equivalence gate; gamma=1/2 is authorized next.
- Real-cone gamma=1/2 passed on attempt r1, Slurm job `22988295`.
  Mosek returned `OPTIMAL` with primal and dual feasible points;
  normalization was exactly 1, worst PSD violation was 0, and the smallest
  independently reconstructed block eigenvalue was 0.07713795086656225.
  Total runner wall was 97.869 s and peak process RSS was 6,001,456 KiB.
  The factor had 112 million nonzeros after factorization, versus 1.51
  billion in the Hermitian-bridge run. `result.toml` SHA-256 is
  `3c5bd696a41a35939df1cd305f52d89be4b6088c5b1cc14590d9223579d6fb38`.
- Current best exact representation cuts gamma=1/2 process peak RSS by
  7.4x and total wall by 4.3x without changing the finite relaxation or its
  feasibility decision.
- Forced-dual gamma=0 audit attempt r1, Slurm job `22988322`, requested
  `MSK_SOLVE_DUAL` but Mosek still reported that it solved the primal and
  reproduced the default factor signature: 68.5 million nonzeros before and
  111 million after factorization. It returned the same residual-checked
  feasible point class and minimum eigenvalue `0.09561232145445703`, while
  process peak RSS rose to 6,235,104 KiB and total runner wall was 83.418 s.
  The route is closed without a gamma=1/2 repetition. `result.toml` SHA-256
  is `b8007b0d9e50338cc770789a8472555b0ce1706f13f13b6e808ed4a11054ae36`.
- Active exact-memory route: quotient the conjugation-real model by the
  order-two physical spin rotation `X↔Z, Y↦−Y`. This symmetry commutes with
  computational-basis conjugation, identifies the two exchanged V4
  character blocks, and exactly splits every stable block into its
  involution eigenspaces. The next step is a source-only inventory of its
  moment orbits and row-space splits before implementing a new derived model.
- Spin-axis truth attempt r1, Slurm job `22988362`, passed 83 of 84 assertions.
  Hamiltonian invariance, all 31,810 coefficient covariance checks, all 8,460
  stable cross-block zero checks, the predicted block dimensions, and the
  JuMP cone reconstruction passed. The sole failure was a test expectation
  that at least one scalar moment would be sign-odd and fixed; the exhaustive
  result was zero because conjugation realification already retained only
  even-Y scalar moments. No theorem or coefficient gate failed. The corrected
  test requires zero and prints the exact orbit count on r2. Peak process RSS
  was 839,724 KiB; `test.log` SHA-256 is
  `6fd3e823ca20b335dbe779b4cd7d3b3be1993d93e5dfe0cbc32ffdd37746cba6`.
- No decision-changing user or resource need is open.
