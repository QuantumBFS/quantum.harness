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
- While the spatial truth and isotypic builder jobs wait/run under the shared
  association cap, a later exact continuous-spin route has been derived for
  the rank-at-most-four moment inventory. It parameterizes rank-two moments
  by `delta_ab` and rank-four moments by the three delta pairings, with an
  exact rational-rotation gate. Its source-level parameterizer, synthetic
  tensor tests, and dedicated Slurm inventory gate are now prepared; all
  eight synthetic assertions pass. No model uses this candidate yet.
- No decision-changing user or resource need is open.
