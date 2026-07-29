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
- Spin-axis truth attempt r2, Slurm job `22988394`, passed all 107 assertions
  in 1:13.6 of test time. The exact quotient has 8,803 moments, eliminating
  7,857 from the conjugation-real inventory, and zero sign-odd fixed moments.
  It has 12 real PSD blocks with dimensions
  `[72,36,81,36,45,73,36,81,36,45]` plus `[1,1]`, maximum side 81, and
  16,707 triangle entries. Peak process RSS was 856,408 KiB. `test.log`
  SHA-256 is
  `f286d48a89b462b11dfbd199d22339e403b167c0672b2ac34c76ed816b39d66d`.
- Next gate: build and reload immutable solver-free spin-axis MOFs for both
  gamma values, then solve gamma=0 before authorizing gamma=1/2.
- Spin-axis MOF build attempt r1, Slurm job `22988427`, completed both clean
  exact builds and independent reload checks from commit `07394a1`. Each model
  has 8,803 variables, 13 constraints, 12 named real PSD cones, 16,707
  triangle entries, and maximum side 81. Gamma=0 model/runmeta SHA-256 values
  are `9b9519a2059e718651af52a7b98e75dc046eab57be33ca3ea9d2325ba28d7fb2`
  and `51dcf29d6961eb3ac0fb19d24f24dcc923f02657944b67d5cfc7b8c1d001d4aa`;
  gamma=1/2 values are
  `f12eaa63e64d8643e4b361d245669d013bdf853d83bda8c35499e8f42dbde485`
  and `aae8943e21c2efc2744a65e633606474f6b5061bd183350dd7d35f8019bebe3d`.
  Job peak RSS was 815,816 KiB and elapsed time was 2:36.
- The separate spin-axis runner allowlists those four hashes and validates all
  setup, reduction-layer, source-file, variable, constraint, named-cone, and
  side-dimension fields before attaching Mosek. Gamma=0 remains the next
  numerical gate.
- Spin-axis gamma=0 truth gate attempt r1, Slurm job `22988457`, passed every
  preflight and returned `OPTIMAL` with primal and dual feasible points.
  Normalization was exactly 1, maximum affine residual and worst PSD violation
  were 0, and the smallest eigenvalue across all 12 independently
  reconstructed blocks was `0.11159895759531112`. Solver wall was 22.250 s,
  total runner wall 40.568 s, process peak RSS 2,602,300 KiB, and the factor
  had 41.4 million nonzeros after factorization. `result.toml` SHA-256 is
  `68d145b91ba34bec17d3c5ca5088a5a8419ee37caaaa39b60e68ab5e9d66465c`.
- The additional exact representation has passed its gamma=0 numerical
  equivalence gate. Gamma=1/2 is authorized next with the same runner and
  solver settings.
- Spin-axis gamma=1/2 attempt r1, Slurm job `22988479`, passed every preflight
  and returned `OPTIMAL` with primal and dual feasible points. Normalization
  was exactly 1, maximum affine residual and worst PSD violation were 0, and
  the smallest eigenvalue across the 12 reconstructed blocks was
  `0.07937511269712764`. Solver wall was 21.650 s, total runner wall 38.496 s,
  process peak RSS 2,449,480 KiB, and the factor had 41.2 million nonzeros
  after factorization. `result.toml` SHA-256 is
  `63e1f7bcc6d6bde6d9de84e226aac448941e1d1b3680e2db0364a0665f2fe50b`.
- The current best exact gamma=1/2 representation cuts process peak RSS by
  18.2x and total wall by 11.1x relative to the original Hermitian bridge,
  and by 2.45x / 2.54x relative to the conjugation-only real model. The
  scientific decision remains that this exact `d=2` relaxation is feasible at
  gamma=1/2; it does not prove a physical bulk gap.
- Full spin-permutation truth attempt r1, Slurm job `22988498`, passed all 126
  assertions. All six proper-rotation lifts preserve the Hamiltonian,
  conjugation-even inventory, and equality space; all 190,860 source
  coefficient covariance identities passed. The exact S3 orbit inventory has
  3,250 moments, eliminating 13,410 from conjugation-only and 5,553 from the
  current spin-axis representation. Peak process RSS was 876,108 KiB;
  `test.log` SHA-256 is
  `8f443154dedca10ced1026770f32cfab90591e829fa119f2abea9673a58a2c56`.
- Active route: retain all 12 already-proved spin-axis PSD cones and restrict
  only their scalar coefficient maps to the 3,250 full-permutation orbit
  variables. This is an exact feasible-set quotient and avoids assuming a new
  complex phase-gauge block congruence.
- Full spin-permutation model truth attempt r2, Slurm job `22988509`, passed
  all 146 assertions, including two deterministic exact coefficient-map
  builds and optimizer-free JuMP reconstruction. The derived model has 3,250
  variables, zero affine equalities, the same 12 proved cone dimensions,
  16,707 triangle entries, and maximum side 81. Peak process RSS was 965,468
  KiB; `test.log` SHA-256 is
  `9ef5f74de8b184d44233c2744f32a9977948c89f8f5bee5210d161cc0f67eae2`.
- Next gate: clean solver-free full-permutation MOF builds and reloads for
  gamma=0 and gamma=1/2.
- Full spin-permutation MOF build attempt r1, Slurm job `22988518`, completed
  both clean exact builds and independent reload checks from commit
  `d799a63`. Each model has 3,250 variables, 13 constraints, the complete 12
  named real PSD cones, 16,707 triangle entries, and maximum side 81.
  Gamma=0 model/runmeta SHA-256 values are
  `4f62a5e16822d2df174af8d9013bb1622c54d8c47bd2f78a59a086524ad4d67f`
  and
  `a0ac07d93e0101732d4d588762754f0ed4837ae2b294f53f7d6bae7573e1152f`;
  gamma=1/2 values are
  `e47bf0d3146ada223bbb389920ea4ca1f79efef467ee7a81ef72d42741652e9f`
  and
  `39da4547ce672cc3d087db7a199adcb76e73ab81672361beffe9c06910a6f05f`.
  Job peak RSS was 919,912 KiB and elapsed time was 4:49.
- The separate full-permutation runner allowlists those inputs and fails
  closed on all four reduction layers, the complete source-hash inventory,
  and the reloaded 3,250-variable/12-cone schema before attaching Mosek.
  Gamma=0 is the next numerical truth gate; gamma=1/2 remains unauthorized
  until it passes.
- Full spin-permutation gamma=0 truth gate attempt r1, Slurm job `22988532`,
  passed every preflight and returned `OPTIMAL` with primal and dual feasible
  points. Normalization was exactly 1, maximum affine residual and worst PSD
  violation were 0, and the smallest eigenvalue across all 12 independently
  reconstructed blocks was `0.13079207445451374`. Solver wall was 20.941 s,
  total runner wall 43.098 s, process peak RSS 2,750,960 KiB, and the factor
  had 60.7 million nonzeros after factorization. `result.toml` SHA-256 is
  `365bef5ca2bae523fdc4903650bcf4cbbfd3c53a7b54a015dcc7b9a2b0dc542c`.
- The quotient is numerically valid, so gamma=1/2 is authorized. Its denser
  factor makes it slightly worse than the 8,803-variable spin-axis model at
  gamma=0; after the fixed gamma=1/2 run, pursue a true full-S3 row-space
  decomposition rather than treating variable count alone as a memory proxy.
- Full spin-permutation gamma=1/2 attempt r1, Slurm job `22988534`, passed
  every fail-closed gate and returned `OPTIMAL` with primal and dual feasible
  points. Normalization was exactly 1, maximum affine residual and worst PSD
  violation were 0, and the smallest reconstructed block eigenvalue was
  `0.09503337763320019`. Solver wall was 18.648 s, total runner wall 37.017 s,
  process peak RSS 2,736,824 KiB, and the factor had 60.3 million nonzeros.
  `result.toml` SHA-256 is
  `d19b811d37dcbc6229351d1642afe6cc197f072bf5c8e862a5a4989a282ff5d3`.
- The finite-relaxation decision remains feasible at gamma=1/2. The
  3,250-variable quotient is 3.8% faster but uses 11.7% more RSS than the
  spin-axis representation at this point, so the 8,803-variable model remains
  the best measured memory representation.
- Active exact-memory route: under full S3 invariance, the three nontrivial
  V4 character blocks form one orbit. Prove whether one stable-character
  `36+45` decomposition makes each retained 81-side orbit-representative cone
  redundant, including the analogous gap scalar. This removes cone rows
  rather than only moment variables and is the next decision-relevant gate.
- Full-spin cone truth attempt r1, Slurm job `22988542`, passed 139 of 142
  assertions. The expected `[1,81,81]` redundant-cone inventory, all exact
  basis ranks and cross-block zeros, and the concrete nine-cone/10,064-entry
  JuMP assembly passed. The three failures share one cause: conjugation parity
  is not uniform within a V4 character block, so the realification transport
  is not a purely signed real permutation. The correct exact congruence has
  row phases in `{±1,±i}`; mixed-phase entries must vanish. The r1 `test.log`
  SHA-256 is
  `11b7b016a5ca7f41b5b93a609e321bed3b7ed71cfb4b89221cb02b4e6f442baa`;
  peak process RSS was 915,688 KiB. R2 tests the phase-corrected congruence
  without changing the proposed cone inventory.
- Full-spin cone truth attempt r2, Slurm job `22988562`, passed 143 of 144
  assertions. All phase-corrected congruences and every mathematical gate
  passed. The sole failure expected at least one mixed transport-phase pair;
  the exact count was zero because all source-to-target phase changes within
  each related block share one real/imaginary class. R3 requires that stronger
  phase-class alignment and zero count. Peak process RSS was 970,408 KiB;
  `test.log` SHA-256 is
  `c3d822ceba8abf183d59cd1c50d8a1a0e5fbb349e97461351f4756aff45b4d90`.
- Full-spin cone truth attempt r3, Slurm job `22988602`, passed all 145
  assertions. All 6,643 phase-corrected orbit congruences, exact stable basis
  ranks, phase-class alignment, plus/minus cross zeros, deterministic
  coefficient assembly, and optimizer-free JuMP reconstruction passed. The
  equivalent model retains 3,250 moments and nine real PSD cones with
  dimensions `[72,36,36,45,73,36,36,45]` plus `[1]`, 10,064 packed triangle
  entries, and maximum side 73. Peak process RSS was 835,316 KiB;
  `test.log` SHA-256 is
  `6fac20b5e07a66d4fc863cdaa45f92d53a219a19e0be3b5075669d140c1ec219`.
- Next gate: build and independently reload clean solver-free cone-reduced
  MOFs for both gamma values, then preserve the required gamma=0-before-
  gamma=1/2 optimization order.
- Full-spin cone-reduced MOF build attempt r1, Slurm job `22988604`,
  completed both exact builds and independent reload checks from clean commit
  `2f87e7a`. Each model has 3,250 variables, 10 constraints, nine named real
  PSD cones, 10,064 triangle entries, and maximum side 73. Gamma=0
  model/runmeta SHA-256 values are
  `a34c629a502b515fc615467bc876f691c0494d523c32f4e1dc5323d84b235d26`
  and
  `0b2942005c4bae13019508484d7af35106b67fbc978b067b99e484e7b588d086`;
  gamma=1/2 values are
  `ce3f4030afdc19d90b0f3a1bd2e8a2d6f3f06c19aad6c61e3b0bbbfe68de17a9`
  and
  `3c880055c1728faeda17c49301819b41272c5fcac0654c19db3e85da0e528ca3`.
  Job peak RSS was 917,940 KiB and elapsed time was 5:21.
- The dedicated nine-cone runner allowlists those four hashes and fails
  closed on the fixed setup, all five exact-reduction layers, the complete
  15-file source inventory, and the reloaded model counts and named cone
  sides.
- Nine-cone gamma=0 attempt r1, Slurm job `22988753`, passed every preflight
  and returned `OPTIMAL` with primal and dual feasible points. Normalization,
  maximum affine residual, and worst PSD violation were exactly 1, 0, and 0;
  the smallest eigenvalue across all nine reconstructed blocks was
  `0.1252658219892882`. Solver wall was 10.661 s, total runner wall
  27.593 s, process peak RSS 1,699,824 KiB, and the factor had 26.3 million
  nonzeros after factorization. `result.toml` SHA-256 is
  `f3b394aff863243aee7706f7c52f728ca303df043429e7c70245e6d79ce2e3a0`.
  The gate authorizes the nine-cone gamma=1/2 run.
- Full-spin trivial-isotypic truth attempt r1, Slurm job `22988781`, passed
  all 177 main assertions plus 32 character tests. On each of 72
  three-row axis orbits, the exact integer basis
  `t=(1,1,1)`, `w=(1,1,-2)`, `m=(1,-1,0)` has full rank; all 7,848 cross
  entries vanish and all 1,332 standard entries obey `W=3M`. Two coefficient
  builds and optimizer-free JuMP reconstruction agree. The equivalent model
  retains 3,250 moments and nine cones, reduces packed PSD entries from
  10,064 to 6,104, and reduces maximum side from 73 to 45. `test.log`
  SHA-256 is
  `1ec6ebdd77b6a94c04b1956c5cfd07f62ad780a2fb34f0fbed7c7351f12f2ee9`.
- Full-spin isotypic MOF build attempt r1, Slurm job `22988846`, completed
  both clean exact builds and independent reload gates from source commit
  `792e61c`. Each input has 3,250 variables, 10 constraints, nine named real
  PSD cones, 6,104 packed triangle entries, and maximum side 45. Gamma=0
  model/runmeta SHA-256 values are
  `990e78381e25b2be683f00d93ffc85ff543d6beed0580b660b25d8f8cf8b90d2`
  and
  `7fac0e27fafe3b902fc3322b880aeccce38f2ba5b0061a172e3f7057bc1e1d23`;
  gamma=1/2 values are
  `22aa6d169fabbe6b9f41eeba4ddc7d37fb1f8b769427714875760ae94dc559f9`
  and
  `8e84bde7043d0023cbd82181d83f1a70622f222b6a706d0a36b9f45283e94e99`.
  Job MaxRSS was 897,624 KiB and elapsed time was 3:54.
- The dedicated isotypic runner now allowlists those four hashes and checks
  all six exact-reduction layers, all 17 recorded source hashes, and the
  reloaded nine-cone inventory before Mosek is attached. Gamma=0 is the next
  numerical gate; gamma=1/2 remains unauthorized until it passes.
- Isotypic gamma=0 gate job `22988910` and corrected spatial truth r2 job
  `22988911` cleared the shared association cap and completed.
- Isotypic gamma=0 attempt r1, Slurm job `22988910`, subsequently passed
  every immutable-input, six-layer reduction, source-hash, and nine-cone
  reload gate. Mosek returned `OPTIMAL` with primal and dual feasible
  points. Normalization was exactly 1, affine and PSD violations were zero,
  and the minimum reconstructed eigenvalue was `0.11113568782699743`.
  Solve wall was 6.624 s, total runner wall 23.124 s, process peak RSS
  1,016,136 KiB, Slurm MaxRSS 1,018,020 KiB, and factor fill 8.53 million
  nonzeros. `result.toml` SHA-256 is
  `2fc5f7e8c5af8a3a3d1ab425ff38d24d01948361dd02e1e6af5fe9f3db65cb07`;
  the Slurm log SHA-256 is
  `6758ca56c0296ab4e5194e283a7729e320fe27c5bc368419389755e3388b548e`.
  This gate authorizes isotypic gamma=1/2 after the two old-source truth jobs
  finish and the remote worktree can safely advance.
- Nine-cone gamma=1/2 attempt r1, Slurm job `22988816`, passed every
  fail-closed input, setup, reduction, source-hash, and reloaded-cone gate.
  Mosek returned `OPTIMAL` with primal and dual feasible points.
  Normalization was exactly 1, maximum affine residual and worst PSD
  violation were 0, and the smallest eigenvalue across all nine independently
  reconstructed blocks was `0.09098861640180578`. Solver wall was 11.817 s,
  total runner wall 34.586 s, process peak RSS 1,666,944 KiB, Slurm MaxRSS
  1,668,768 KiB, and the factor had 26.4 million nonzeros after
  factorization. `result.toml` SHA-256 is
  `f24c297da06061b08aa9e94e83f401967cb055e89620bb9eceb834425c16e031`.
- The exact nine-cone representation therefore cuts gamma=1/2 process RSS
  by 32.0% and factor fill by 35.9% relative to the spin-axis model. The
  finite-relaxation conclusion remains feasible at gamma=1/2; no
  infeasibility ray exists to replay.
- A subsequent independent candidate is now source-complete but unproved:
  the anti-diagonal site reflection `(x,y)->(-y,-x)` is the only nonidentity
  D4 map that preserves the actual level-1 Shastry--Sutherland Hamiltonian
  term multiset. A separate exact gate checks its site/moment involution,
  all 6,104 isotypic coefficients, equality space, eigenspace ranks, and
  every spatial plus/minus cross entry. It remains behind the authorized
  nine-cone gamma=1/2 decision run, which is now complete.
- Spatial-reflection truth attempt r1, Slurm job `22988821`, stopped after
  1:18 at the moment-closure gate, before any coefficient, cone, or model
  claim. A reflected full-spin orbit representative need not itself be the
  lexicographic representative of the reflected spin orbit. The corrected
  action composes site reflection with the already-proved full-spin
  representative map and explicitly requires a positive count of such
  re-representations on r2. Peak Slurm RSS was 713,484 KiB; `test.log`
  SHA-256 is
  `a7e2e3ff6d9240bcbaedb5a49df7624737d1ab68277b60bfc44a7938d60982f4`.
- While the spatial and isotypic jobs were queued under the shared
  association cap, a later exact continuous-spin route was derived for
  the rank-at-most-four moment inventory. It parameterizes rank-two moments
  by `delta_ab` and rank-four moments by the three delta pairings, with an
  exact rational-rotation gate. Its source-level parameterizer, synthetic
  tensor tests, and dedicated Slurm inventory gate were prepared; all eight
  synthetic assertions pass. Inventory job `22988914` has now passed. No
  model uses this candidate yet.
- Corrected spatial-reflection truth r2, Slurm job `22988911`, passed all 28
  assertions. Composing site reflection with full-spin re-representation
  closes the 3,250-moment inventory and leaves 1,711 moments. All 6,104
  source coefficients are covariant, all 2,913 plus/minus cross entries
  vanish, and every row split has full rank. The exact model has 16 positive
  cone sides `[21,15,21,15,21,15,24,21,22,15,21,15,21,15,24,21]`,
  one scalar gap cone, 3,191 packed entries, and maximum side 24.
  `test.log` SHA-256 is
  `3d60469de1da702d33bf6d3bee971fa4bcd99b0e0d852b2246bdd2c4803c327b`;
  process peak was 896,892 KiB and Slurm MaxRSS 773,896 KiB.
- Continuous-spin moment truth r1, Slurm job `22988914`, passed all 23
  assertions. It maps 3,250 moments to 2,458 pivots across 874 skeletons and
  replays 64,882 exact rational-rotation components while reconstructing all
  6,104 cone entries deterministically. `test.log` SHA-256 is
  `cd489366f56038bb97cc4dc208bc59ff95b5fc52622ba3e3d44002108d1f0317`;
  process peak was 826,164 KiB and Slurm MaxRSS 722,980 KiB. The separate
  l=2 cone-redundancy gate is now authorized.
- The next continuous-spin cone theorem is encoded and now authorized by
  the passing inventory gate. For each of the 36 spatial rank-two skeletons in both
  positive families it pairs the S3-standard component `XX-ZZ` with the
  nontrivial-character component `XZ+ZX`, proves the skeleton map has rank
  36, and will compare all 1,332 projected upper-triangle coefficients under
  the induced exact signed congruence. Only its passing Slurm truth run may
  remove the two duplicate 36-side cones and reach the predicted 4,772
  packed PSD coordinates. Optimizer-free JuMP mappings for both the
  moment-only fallback and the gated six-cone candidate are source-prepared;
  neither is authorized for MOF generation before its truth gate passes.
  A separate one-skeleton synthetic test passes all eight row-orientation,
  norm, and signed-permutation assertions locally. A clean, solver-free
  two-gamma MOF builder is also prepared with every preceding exact truth
  gate and independent named-cone reload, but it remains unsubmitted.
- If both the continuous-spin and corrected spatial gates pass, the next
  route is their exact commuting composition. The induced reflection on
  continuous pivots is `T(y)=q_c(r(y))`; its rational fixed space, complete
  intertwining test, and spatial cone cross-zero proof are specified in
  `EXACT_CONTINUOUS_SPIN_REDUCTION_PLAN.md`. No combined source or job is
  authorized yet.
- The next isotypic solver revision exports every primal variable as its
  exact IEEE-754 bit pattern and includes the generated table in the run
  manifest. This does not alter the queued gamma=0 job. If that gate passes,
  the authorized gamma=1/2 run can preserve enough information for a
  separate rational positive-definiteness replay. That replay is now
  source-prepared: it verifies all input/source/assembly hashes, tries common
  decimal denominators `10^6` through `10^12`, and accepts only strictly
  positive exact rational LDL pivots for all nine cones. Its eight helper
  assertions pass locally; no certificate job is yet authorized.
- Submission attempt `2026-07-29T-current` for the authorized isotypic
  gamma=1/2 job was rejected by Slurm before a job ID or output directory was
  created: account `giggleliu` was at its 200-job
  `AssocGrpSubmitJobsLimit`. Because the submission command was fail-fast,
  neither the spatial builder nor the continuous-spin cone truth job was
  submitted. Do not repeat while the association signature is unchanged;
  use the interval for source work and probe the account before the next
  submission.
- No decision-changing user or resource need is open.
- Isotypic gamma=1/2 attempt r1, Slurm job `22988996`, completed after the
  remote research agent stopped. Every immutable-input, six-layer reduction,
  source-hash, and nine-cone reload gate passed. Mosek returned `OPTIMAL`
  with primal and dual feasible points. Normalization was exactly 1, maximum
  affine residual and worst PSD violation were 0, and the smallest
  reconstructed block eigenvalue was `0.08228797924548609`. Solver wall was
  7.804 s, total runner wall 26.510 s, process peak RSS 1,138,120 KiB, and
  Slurm MaxRSS 1,124,340 KiB. The result and exported 3,250-value IEEE-754
  table have SHA-256 values
  `84ef32c708b7d26871b868faf9afdc0ef75a06d9cb8f929f79d98909407d158a`
  and
  `8ccbb186f7c0b66e2dafa5d0e28782757b88afadba4982f1532dbb4ca77ff1be`.
- The isotypic gamma=1/2 representation reduces measured process peak RSS by
  39.1x and solver wall by 52.2x relative to the original exact Hermitian
  bridge while preserving the same finite-relaxation feasibility decision.
- The main/local agent has taken over execution. Both remote research agents
  are stopped. Private branch `5f933515f3eebbec0a4685f55df5fd20a6460773`
  and all seven decision-relevant isotypic/spatial/continuous result bundles
  are synchronized locally and their manifests pass.
- Exact rational-witness replay r1, Slurm job `22990387`, failed closed before
  assembly at 598,640 KiB. The exported primal table is parsed with `split`,
  which returns `SubString{String}`, while `bits_to_float` unnecessarily
  required `String`. This is an entry-point type error, not a model, input, or
  mathematical failure. The helper now accepts `AbstractString`; the targeted
  regression suite passes 9/9 locally at 287,280 KiB peak RSS.
- Corrected rational-witness replay r2, Slurm job `22990727`, reached the
  wrapper after its queue delay but failed before assembly because the
  wrapper passed absolute input paths to a replay that deliberately accepts
  only repository-relative paths. The shipped parser SHA-256 was
  `9379ed739499f3955534085c4616ea14950e148c51bea14b322faef8875d396f`,
  matching the committed local source. Corrected r3, job `22991012`, used
  repository-relative paths and passed. At common denominator `10^6`, all
  3,250 rational moments normalize exactly and all nine reconstructed rational
  matrices have strictly positive exact LDL pivots. Wall time was 40.1 s
  inside a 1:17 Slurm job; MaxRSS was 614,344 KiB. The checksummed result
  bundle is synchronized locally.
- The next bulk-gap run is a single-slot, sequential `d=2` coarse scan at
  exact rational gamma values `1`, `2`, and `4`, stopping at the first
  solver-reported infeasibility candidate. Each point rebuilds the exact
  74,602-moment source assembly, replays all six exact reductions, reloads the
  nine named real PSD cones, and audits any primal solution. Dynamic scan
  inputs remain fail-closed to a clean builder commit/tree, a repository-local
  results path, source-file hashes, and the generated SHA256SUMS. Any
  infeasible status is only a candidate until an independent ray replay
  passes.
- Coarse-scan r1, job `22990996`, failed at launch with signal 53 before the
  batch script started because the clean clone lacked the parent directory of
  its Slurm output file. No model code ran. After creating the ignored results
  directory, r2 job `22991011` entered `RUNNING` on `a01r08n04` and began the
  exact gamma-one build. That build passed in 2:48, but the solve preflight
  exposed another over-narrow string signature: canonical-gamma `split`
  fields are `SubString{String}`, while `require_rational_metadata` required
  `String`. No optimizer was attached. Runner-facing read-only text APIs are
  now generalized to `AbstractString`, and the scan now runs a dedicated
  split/regex-capture regression before any assembly.
- Corrected coarse-scan r3, job `22991095`, passed the 11/11 string-boundary
  preflight and every immutable-input, six-reduction, named-cone reload, and
  primal audit at exact rational gamma values `1`, `2`, and `4`. All three
  points are `feasible_residual_checked_float`: normalization is exactly one,
  maximum affine residual and worst PSD violation are zero, and the minimum
  reconstructed block eigenvalues are respectively
  `0.06341919455293454`, `0.010455807260659311`, and
  `0.004514259614827765`. The job completed in 9:11 with Slurm MaxRSS
  973,548 KiB. The fetched bundle passes all recorded checksums; its
  `SHA256SUMS` file hashes to
  `d3fc0484649ade9d6246db39e6da6c65e151d883da19e0de961a0998ee947044`.
- Extended coarse-scan r4, job `22992336`, repeated the complete exact build
  and audit at gamma `8`, `16`, and `32`. All three remain
  `feasible_residual_checked_float` with zero affine and PSD violations. The
  minimum reconstructed block eigenvalues decrease to
  `0.0014308867937518066`, `5.4343318096172766e-5`, and
  `4.915449793807536e-6`; the scalar gap-block values are
  `0.01797420828848928`, `0.01368745758280987`, and
  `0.007499637530884229`. The job completed in 8:42 with Slurm MaxRSS
  953,356 KiB. The fetched bundle passes all recorded checksums; its
  `SHA256SUMS` file hashes to
  `a3b5cc33067d130c02b14c3aa1abcae52cb9853c0906f05c724a97f686a5e337`.
  This does not imply a large physical gap: it shows that the present
  `L=1,d=2` relaxation is still too weak to exclude gamma 32.
- Extended isotypic scan r5, job `22992662`, was submitted for gamma `64`,
  `128`, and `256` but never started: it remained pending under the
  shared-account `AssocGrpJobsLimit` and was cancelled at zero elapsed time
  after the exact spatial representation became the authorized next compute
  target. Do not spend additional solve capacity on the superseded
  3,250-moment representation. First complete the spatial runner's
  gamma-zero and gamma-half A/B gates, then continue the scan with its
  1,711-moment/3,191-packed-entry/max-side-24 model.
- Spatial-reflection builder r3, job `22992784`, completed both immutable
  gamma-zero and gamma-half inputs in 5:38 with 1,018,288 KiB Slurm MaxRSS.
  Independent local builds used about 1.02--1.05 GiB and produced
  byte-identical MOF hashes:
  `5d770e3320ef9f2c6af7d3b763b7d05c2a316a245a114f98881c79007da2cf95`
  and
  `526700018f93a1ee5bd4955f6e75a56669a805ca50e3b1671b341789409a899e`.
  The deterministic A/B gate and all exact spatial truth gates therefore pass.
- Fail-closed spatial solve jobs `22993015` and `22993016` completed at gamma
  zero and gamma one-half. Both are `OPTIMAL` with primal and dual feasible
  points, exact normalization, zero reconstructed PSD violation, and
  `feasible_residual_checked_float` classification. Solver walls were 8.382 s
  and 6.993 s; minimum reconstructed block eigenvalues were
  `0.12925186655108384` and `0.08286263095400265`. This verifies the exact
  smaller representation but still does not exclude gamma one-half.
- Spatial logarithmic scan r1, job `22993166`, failed in 16 s before any
  model build because the wrapper exported dynamic mode before its canonical
  immutable-input tests. The test correctly rejected the mode mismatch; no
  physics code or solver ran. Commit `f5fbb1d` moves the export after the
  21-test gate.
- Corrected spatial scan r2, job `22993230`, completed gamma `32`, `64`,
  `128`, and `256` in 18:37 with 1,092,064 KiB Slurm MaxRSS. All four points
  are `feasible_residual_checked_float`, with zero audited affine and PSD
  violations. Their minimum reconstructed block eigenvalues are
  `9.378288472522944e-6`, `9.554763007345435e-6`,
  `3.424375474403159e-6`, and `1.634994035355913e-6`; their scalar gap-block
  values are `0.007962166397234682`, `0.0032291871095964098`,
  `0.0020950778859543107`, and `0.0007716043441519105`.
- Gamma 32 reproduces the earlier isotypic feasibility classification, so the
  exact-representation control passes. The shrinking cone margins and gap
  slack through gamma 256 show that fixed `L=1,d=2` is approaching a
  pseudo-moment boundary rather than a useful finite transition. Stop widening
  gamma at this level. The next decision is an asymptotic-face diagnostic,
  followed by count/memory preflights for stronger `d` or `L`.
- The complete-state-polynomial `L=1,d=2` spin/spatial model at gamma `2`
  completed as SCNet job `118147307`: `OPTIMAL`, primal/dual feasible, and
  `feasible_residual_checked_float`. Solve wall was 1,031.084 s, total runner
  wall 1,063.608 s, and process peak RSS 39,288,700 KiB. Therefore this
  stronger 7,231-moment relaxation also remains feasible at gamma `2`; do not
  scan smaller gamma values at this level.
- The first S3 cone attempt correctly failed its truth gate in job `118153034`.
  A 1:35 small-instance diagnostic proved the trivial-character isotypic
  blocks exactly but disproved the proposed deletion of nontrivial V4
  character blocks. The corrected exact reduction keeps those blocks and
  reduces packed real PSD entries from 112,387 to 75,967 (32.4%) and the
  maximum side from 198 to 135. Small truth anchor job `118155030` passes.
- `L=2,d=2` row-structure probe job `118155322` completed in 41 s at
  488,780 KiB. The positive basis has 14,026 rows. All four target
  trivial-character blocks contain only size-1/3 S3 row orbits, so the proven
  exact isotypic reduction extends without a new orbit case.
- Full corrected isotypic benchmark job `118155251` passed all truth, MOF,
  source-hash, named-cone, and residual gates. It is `OPTIMAL` and
  `feasible_residual_checked_float` at gamma `2`. Versus the 7,231-moment
  unsplit spin/spatial solve, peak process RSS fell from 39,288,700 to
  23,861,984 KiB (39.3%), but solve wall increased from 1,031.084 to
  1,064.326 s (3.2%). Treat this as a memory-enabling reduction, not a speed
  optimization.
- `L=2,d=2` preflight r1 job `118155664` was cancelled after 5:37 and
  3,392,068 KiB MaxRSS because it still carried the disproven, unused
  nontrivial-block diagnostic. Preflight r2 job `118156605` removes that
  work and is running on 32 CPUs / 114,000 MiB.
- Remote terminal-solve takeover uses clean branch
  `remote/challenge88-terminal-solve` at commit `87be317`. SCNet baseline job
  `118171391` is preserved and was `RUNNING` at 2026-07-29T14:48Z on 32 CPUs /
  114000 MiB. Its log shows exact `L=2,d=2` coefficient/isotypic assembly,
  before JuMP/Mosek; process RSS was about 6.1 GB. xH5 baseline job `23011251`
  is also preserved and remained `PENDING (Priority)` at 64 CPUs / 240 GB.
- The next changed action is not another gamma scan. While both baselines
  continue, audit a single-pass solver export and add a fail-closed numerical
  result audit so any terminal feasibility or infeasibility statement is tied
  to residual/certificate evidence.
- Bounded-memory coefficient fingerprinting is verified locally on the exact
  `L=1,d=2` regression: the coefficient stage completed in 225.425 s with
  7,231 moments, 75,967 PSD entries, and unchanged SHA-256
  `2a6753a6ea7c57fa43bd33e09339046206fae5217ac3ae47c0cf9cc3b2dc2679`.
  The new route removes the all-entry diagnostic-string inventory without
  changing exact coefficients or their provenance fingerprint.
- xH5 job `23011251` began running at 2026-07-29T14:49:17Z from immutable
  commit `2de1678`; both it and SCNet job `118171391` remain in their original
  coefficient pass and have not been modified.
- The fail-closed direct-solve audit is verified on SCNet. Synthetic job
  `118172573` passed 9/9 PSD/status assertions; extended job `118172627`
  passed 14/14 including exact IEEE-754 primal export and file hashing. The
  changed source is commit `4227ec2` (with its import fix in `1c339e5`). Use it
  only for the next decision-relevant solve or independent audit rerun; do not
  duplicate the two immutable L=2 baselines while they are active.
- Raw solver-artifact regression job `118172817` passed 23/23 assertions in
  41 seconds with 509,788 KiB MaxRSS. Commit `c0b2c64` therefore preserves a
  hashed Mosek interior solution after every solve and a compressed task for
  an infeasibility candidate. These files make an independent ray replay
  possible; their existence alone is not a certificate.
- The native solution-file formats did not meet the replay gate: text `.sol`
  reloaded as `UNKNOWN` with zero vectors, while JSOL and binary-solution
  reloads raised Mosek error 1050 even when paired with serialized or binary
  tasks. These are closed implementation branches, not scientific results.
- Commit `1b08236` replaces them with a versioned binary export of every
  scalar, affine-conic, and semidefinite dual-ray component plus source status
  codes. The reader inserts those exact Float64 values into a fresh binary
  task and asks Mosek to recompute dual objective and violations. After small
  fixture corrections in `623c070` and `451fd33`, job `118173664` passed all
  29 scalar-ray tests with dual objective 1, normalized separation 1, and zero
  violation. Semidefinite fixture r15, job `118173766`, replayed successfully
  but rejected its own storage assertion: MosekTools represents the affine PSD
  cone through an affine-conic dual (`doty`), not a bar variable. Corrected r16
  job `118173855` passed 36/36 tests. Its three-component PSD ray has dual
  objective 0.7526914264023223, normalized separation
  0.5981688276525166, and zero recomputed dual violation. The floating ray
  preservation/replay path is now authorized for the scientific model.
- The native direct-Mosek route merged at `e50da6c` passed the post-merge
  scalar/PSD Farkas replay in job `118174144` (36/36). Its corrected L=1
  construction truth gate, job `118174309`, passed in 1:12 with 1,468,728 KiB
  MaxRSS: 7,231 moments, 23 affine PSD cones, 75,967 packed entries, 233,206
  scalar terms, and exact coefficient SHA-256
  `2a6753a6ea7c57fa43bd33e09339046206fae5217ac3ae47c0cf9cc3b2dc2679`.
- Commit `6aa430b` enables bounded native coefficient fingerprinting for the
  target L=2 solve and aborts unless it reproduces the known exact coefficient
  SHA-256 `935aab36220ec3f0b2bfaa92ea7527463c9dc1a2d579014798e4fe5534b6b1b4`.
  SCNet native job `118174488` started at 2026-07-29T16:13:27Z on 32 CPUs /
  114000 MiB. It is decision-relevant because it streams directly into Mosek
  in one coefficient pass; protected JuMP jobs `118171391` and `23011251`
  remain untouched and had still not entered optimization at 16:14Z.
- Native launch r1, job `118174488`, stopped before model construction because
  the isolated checkout was detached and the provenance guard requires a
  symbolic branch. Reattach the same clean branch and resubmit once; this was
  not a scientific run and does not change the planned signature.
- The branch was reattached and verified clean at `4f33981`; native L=2 r2 is
  SCNet job `118174638`, started 2026-07-29T16:17:15Z on 32 CPUs / 114000 MiB.
- Job `118174638` passed its complete native construction gate in 1,733.452 s:
  461,186 moments, 26 affine PSD cones / 4,446,492 packed rows, 15,802,343
  scalar terms, zero remaining equalities, and exact expected coefficient hash
  `935aab36220ec3f0b2bfaa92ea7527463c9dc1a2d579014798e4fe5534b6b1b4`.
  Stage RSS was 13,829,968 KiB. Mosek is now running; presolve took 6.28 s.
  No feasibility or spectral-gap conclusion is available yet.
- Protected xH5 baseline `23011251` ended `OUT_OF_MEMORY` after 1:48:50 during
  JuMP→Mosek transfer, before solver iterations. Slurm MaxRSS was 234,603,960
  KiB (`/usr/bin/time`: 251,835,816 KiB) against 240 GB. Its coefficient and
  JuMP stages had completed in 1,835.530 s and 3,991.145 s. This is not a
  physics result; do not repeat that signature. Native job `118174638`
  remains the active exact decision solve.
- Dual-certificate replay code is committed at `09729d7`. Its first synthetic
  SCNet test, job `118177325`, never launched (`JobLaunchFailure`, zero
  runtime, no log). Resubmit this unchanged tiny test once on another node.
- Audit r2 `118177473` exposed the actual common launch error: the new clone
  lacks its gitignored `results/_slurm` output directory. Create only that
  directory and use a fail-closed path preflight for r3.
- Dual audit r3 `118177590` ran and passed 43/46 checks. Its new native
  certificate had valid source status and RHS structure, but fresh-task
  violation was 1.0 because the artifact omitted constraint activities. The
  artifact now stores their exact Float64 bits for a complete replay in r4.
- Corrected dual audit r4 `118177811` passed 46/46 in 1:07 at 514,500 KiB
  MaxRSS. Fresh-task native bar-certificate replay has exact RHS structure and
  zero recomputed primal violation.
- Native primal `118174638` ended `OUT_OF_MEMORY` after 52:21 during
  post-presolve factorization, before iterations: 104,717,420 KiB Slurm MaxRSS
  (`/usr/bin/time`: 116,125,540 KiB) versus 114000 MiB. It is not a physics
  result. Next changed solve: native bar-variable dual on xH5, 64 CPUs /
  240 GB, with hash gate and replayable output.
