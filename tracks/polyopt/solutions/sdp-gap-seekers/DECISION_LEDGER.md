# Challenge 88 decision ledger

## 2026-07-29 — preserve the exact finite relaxation

The supplied rational congruence, V4 character decomposition, and exact gap
facial reduction are treated as an equivalence transformation. No constraints,
moments, blocks, state classes, or basis words may be dropped for memory.

## 2026-07-29 — immutable input allowlist

The solver accepts only the supplied gamma=0 and gamma=1/2 MOF/runmeta pairs.
It checks the external `SHA256SUMS`, hard-coded pair hashes, all runmeta setup
and reduction fields, every recorded source-file hash, and the named cone
inventory after MOF reload.

## 2026-07-29 — numerical claim rule

A feasible solver status is promoted only to
`feasible_residual_checked_float` after normalization, all affine equalities,
and all 11 reconstructed Hermitian PSD blocks pass a declared scale-aware
`1e-7` audit. An infeasibility status remains only
`infeasibility_candidate_requires_independent_ray_replay`.

## 2026-07-29 — xH5 resource choice

Use `xhacnormalb`, one node, 16 CPUs, 60 GiB, and a two-hour allocation. This
fits xH5's per-CPU memory policy and keeps all operations that may approach or
exceed 1 GiB RSS off login/Bohrium nodes.

## 2026-07-29 — MOF Hermitian packing

Gamma=0 attempt r1 (job `22987967`) showed that MathOptFormat reload preserves
the named `HermitianPositiveSemidefiniteConeTriangle` set and side dimension
but not JuMP's original `HermitianMatrixShape`. The corrected runner validates
the cone set/dimension, then independently rebuilds each matrix from MOI's
real-upper followed by imaginary-strict-upper vector packing. No optimizer was
attached in r1 and no scientific status was produced.

## 2026-07-29 — MosekTools raw attributes

Gamma=0 attempt r2 (job `22987979`) passed the immutable-input, source-hash,
setup, count, and named-cone checks. It then stopped before `optimize!` because
MosekTools 0.15.10 accepts `MSK_IPAR_NUM_THREADS` through MOI's string-valued
raw optimizer attribute, not the Mosek.jl enum used by the older Square
runner. The Shastry runner now uses the supported raw attribute API.

## 2026-07-29 — gamma=0 truth gate passed

Attempt r3 (job `22987983`, runner commit `40b1f02`) returned Mosek
`OPTIMAL` with primal and dual feasible points. Independent reconstruction
gave normalization 1 exactly, three zero affine residuals, zero PSD violation,
and a smallest block eigenvalue of 0.0948505094335904. The gamma=1/2 solve is
therefore unblocked without changing the Hamiltonian, window, state class,
degree, reduction, solver settings, or audit tolerance.

## 2026-07-29 — gamma=1/2 is feasible in the exact finite relaxation

Gamma=1/2 attempt r1 (job `22988032`) returned Mosek `OPTIMAL` with primal and
dual feasible points. Independent reconstruction gave normalization 1, zero
affine residual, zero PSD violation, and smallest block eigenvalue
0.08943315828795756. The decision-grade conclusion is numerical feasibility
of the exact `d=2` finite relaxation at gamma=1/2. It is not a certified
physical lower bound on the bulk gap.

No infeasibility ray replay is needed because the solver did not report
infeasibility.

## 2026-07-29 — reopen exact memory reduction after bridge diagnosis

The continuation objective requires pursuing the Challenge 88 result beyond
the wrapper milestone. The Mosek log shows that MOI's generic Hermitian bridge
turns the eight positive blocks into 126,525 scalarized semidefinite
coordinates and a 1.45--1.51-billion-nonzero factor. That makes an exact
representation reduction decision-relevant even though both fixed-gamma
solves fit the original 60 GiB allocation.

The highest-value route is computational-basis conjugation averaging. The
fixed Hamiltonian is invariant; averaging preserves unrestricted
feasibility, removes conjugation-odd moments, and a fixed diagonal unitary
gauge makes every remaining block real symmetric. The predicted positive-cone
coordinate count is 31,807. This route must pass exhaustive exact coefficient
and equality-space tests under Slurm before any derived MOF is generated or
solved.

## 2026-07-29 — conjugation truth gate passed; full-suite tail dropped

Slurm job `22988127` passed all 58 assertions in the exact M/K/V4 testset,
including the exhaustive 31,810-entry coefficient gate, in 102.2 s. The same
wrapper then spent more than ten minutes in an unrelated dense-ED oracle.
Because that tail cannot change the conjugation theorem, the job was canceled
at 12:34 and the passed test log was preserved. Subsequent jobs target only
the exact reduction build/reload path instead of repeating the bottleneck.

## 2026-07-29 — derived-MOF build r1 stopped before assembly

Slurm job `22988179` stopped during Julia macro expansion: a line break left
`@timed` without its expression. No source assembly, model, MOF, or solve ran.
The next attempt moves the macro argument into the same expression and first
loads the complete script through its `--help` path.

## 2026-07-29 — derived-MOF build r2 exposed xH5 Git compatibility

Slurm job `22988194` passed Julia macro expansion and stopped in source
provenance collection before assembly. The xH5 Git version does not implement
`branch --show-current`. The builder now uses the portable plumbing command
`symbolic-ref --short HEAD`; no model or MOF was emitted by r2.

## 2026-07-29 — retain the clean-tree gate after build r3

Slurm job `22988216` reached the clean-source check and refused to build
because its own default `slurm-22988216.out` was untracked at the checkout
root. The gate is correct and remains strict. The sbatch wrapper now routes
scheduler stdout into the ignored track-results tree, so generated job logs
cannot masquerade as source dirtiness.

## 2026-07-29 — exact conjugation-reduced MOFs accepted

Slurm job `22988221` completed both clean, solver-free builds and reload
checks. The exact real model has 16,660 moments, zero surviving affine
equalities, and 31,810 real PSD triangle coordinates. This is a 2,448-moment
and 94,715-cone-coordinate reduction relative to the V4 model as presented to
Mosek's generic Hermitian bridge.

The gamma=0 and gamma=1/2 model SHA-256 values are respectively
`0a2c9166eb033a2e782ab91a062491961a5d8139a1b04e80f6f564d1a75a6e14`
and
`b50d66a48a45de0f2a25e411ab3dcc6a06f3a99b06626951277ae09686062707`.
They are immutable derived inputs. The real-cone runner must pass gamma=0
before the gamma=1/2 memory comparison is authorized.

## 2026-07-29 — real-cone gamma=0 truth gate passed

Slurm job `22988279` passed all immutable-input, fixed-setup, exact-reduction,
source-hash, variable-count, constraint-count, and named-real-cone gates
before attaching Mosek. It returned `OPTIMAL` with primal and dual feasible
points. Independent reconstruction gave normalization 1, zero PSD violation,
and minimum eigenvalue 0.09561232145445703.

The solver representation changed the factor from 1.45 billion to 111 million
nonzeros and the run from 46,385,640 KiB / 462.4 s to 5,917,112 KiB /
93.1 s process peak / total wall. This validates the exact realification
numerically at gamma=0 and authorizes the gamma=1/2 run without changing the
physical or relaxation setup.

## 2026-07-29 — real-cone gamma=1/2 passed with a 7.4x RSS reduction

Slurm job `22988295` returned `OPTIMAL` with primal and dual feasible points.
Independent reconstruction gave normalization 1, zero PSD violation, and
minimum eigenvalue 0.07713795086656225. No infeasibility ray is applicable.

Relative to the exact Hermitian-bridge gamma=1/2 run, process peak RSS fell
from 44,494,548 to 6,001,456 KiB, total wall from 425.4 to 97.9 s, and
post-factor nonzeros from 1.51 billion to 112 million. The finite-relaxation
decision is unchanged: gamma=1/2 is feasible, while the exact implementation
now fits comfortably inside a 32 GiB allocation.

## 2026-07-29 — bounded dual-form audit

The automatic real-cone solve selected Mosek's primal form. A forced dual form
is mathematically the same SDP and may change only the Newton factorization.
Test it first at gamma=0 under the same 16-CPU, 32 GiB cap. Continue to
gamma=1/2 only if factor fill or peak RSS improves; otherwise close the route
after the gamma=0 artifact instead of repeating a worse setting.

## 2026-07-29 — close the forced-dual route at gamma=0

Slurm job `22988322` passed all fail-closed gates and recorded the requested
solve form as `dual`, but Mosek reported `Optimizer - solved problem : the
primal`. Its 68.5-million-before / 111-million-after factor nonzero counts and
iterate sequence match the default real-cone gamma=0 run. It returned
`OPTIMAL`, zero audited residual and PSD violation, and minimum eigenvalue
`0.09561232145445703`.

There is no factor-fill improvement to justify a gamma=1/2 repeat. The
process peak was 6,235,104 KiB versus 5,917,112 KiB for the default, and the
preserved `result.toml` SHA-256 is
`b8007b0d9e50338cc770789a8472555b0ce1706f13f13b6e808ed4a11054ae36`.
Close this tuning route and move to an exact model-level involution:
`X↔Z, Y↦−Y`, a π spin rotation that commutes with the already-proved
conjugation symmetry.

## 2026-07-29 — spin-axis truth r1 corrects a count assumption

Slurm job `22988362` completed the dedicated exact test in 1:48 with 83 passes
and one failed count expectation. Every mathematical gate passed, including
31,810 source coefficient covariance checks, 8,460 stable plus/minus
cross-entry zero checks, Hamiltonian and equality-space invariance, all
predicted block splits, and the 16,707-entry JuMP cone reconstruction.

The failed assertion expected at least one sign-odd fixed scalar moment.
Computational-basis conjugation has already removed every odd-Y scalar moment,
while the spin-axis sign is `(-1)^(number of Y factors)`, so the correct exact
count is zero. Change only that expectation and add an explicit orbit-count
progress line before r2. The r1 `test.log` SHA-256 is
`6fd3e823ca20b335dbe779b4cd7d3b3be1993d93e5dfe0cbc32ffdd37746cba6`;
peak process RSS was 839,724 KiB.

## 2026-07-29 — spin-axis exact truth gate passed

Slurm job `22988394` passed all 107 dedicated assertions. The exhaustive
result is 8,803 moment variables, 7,857 fewer than the conjugation-real model,
12 PSD blocks, maximum side 81, and 16,707 packed real triangle entries.
All 31,810 source coefficient covariance identities and 8,460 stable
plus/minus cross-entry zeros were evaluated over exact rationals.

The passing `test.log` SHA-256 is
`f286d48a89b462b11dfbd199d22339e403b167c0672b2ac34c76ed816b39d66d`;
peak process RSS was 856,408 KiB. Proceed to clean solver-free MOF builds for
both fixed gamma values, retaining the required gamma=0-before-gamma=1/2
optimization order.

## 2026-07-29 — accept immutable spin-axis MOF inputs

Slurm job `22988427` built and reloaded both solver-free models from clean
commit `07394a1`. The gamma=0 model SHA-256 is
`9b9519a2059e718651af52a7b98e75dc046eab57be33ca3ea9d2325ba28d7fb2`;
gamma=1/2 is
`f12eaa63e64d8643e4b361d245669d013bdf853d83bda8c35499e8f42dbde485`.
Their runmeta SHA-256 values are respectively
`51dcf29d6961eb3ac0fb19d24f24dcc923f02657944b67d5cfc7b8c1d001d4aa`
and
`aae8943e21c2efc2744a65e633606474f6b5061bd183350dd7d35f8019bebe3d`.

Both reload gates confirmed 8,803 variables, 13 constraints, all 12 named
real cones, 16,707 triangle entries, and maximum side 81. These become
immutable allowlisted inputs. Use a separate runner that verifies their
checksums, full runmeta, and every recorded source hash before optimization;
run gamma=0 first.

## 2026-07-29 — spin-axis gamma=0 gate passed

Slurm job `22988457` passed the immutable-input, fixed-setup, all-reduction,
recorded-source-hash, reloaded-count, and 12-named-cone gates before attaching
Mosek. It returned `OPTIMAL` with primal and dual feasible points.
Independent reconstruction found normalization 1, zero affine and PSD
violations, and minimum eigenvalue `0.11159895759531112`.

The factor had 41.4 million nonzeros after factorization, total runner wall
was 40.568 s, and process peak RSS was 2,602,300 KiB. The preserved
`result.toml` SHA-256 is
`68d145b91ba34bec17d3c5ca5088a5a8419ee37caaaa39b60e68ab5e9d66465c`.
This passes the required gamma=0 numerical equivalence gate and authorizes
gamma=1/2 without a setup or tolerance change.

## 2026-07-29 — spin-axis gamma=1/2 remains feasible at 2.45 GiB

Slurm job `22988479` passed all fail-closed gates and returned `OPTIMAL` with
primal and dual feasible points. Independent reconstruction gave
normalization 1, zero affine and PSD violations, and minimum block eigenvalue
`0.07937511269712764`. No infeasibility ray or replay branch is applicable.

The factor had 41.2 million nonzeros after factorization, total runner wall
was 38.496 s, and process peak RSS was 2,449,480 KiB. `result.toml` SHA-256 is
`63e1f7bcc6d6bde6d9de84e226aac448941e1d1b3680e2db0364a0665f2fe50b`.
Relative to the original exact Hermitian bridge, this is an 18.2x RSS and
11.1x total-wall reduction; relative to conjugation-only realification it is
2.45x and 2.54x. The exact finite-relaxation feasibility decision is
unchanged.

## 2026-07-29 — full spin-permutation truth gate passes

Slurm job `22988498` passed all 126 assertions, including 190,860 exact
coefficient covariance identities: all six proper-rotation lifts applied to
all 31,810 V4 block entries. Hamiltonian invariance, the complete equality
row space, conjugation-inventory closure, and the unsigned retained-moment
action also passed.

The full S3 orbit quotient has 3,250 moments, removing 5,553 more variables
than the current 8,803-moment model. The passing `test.log` SHA-256 is
`8f443154dedca10ced1026770f32cfab90591e829fa119f2abea9673a58a2c56`;
peak process RSS was 876,108 KiB.

Proceed by retaining every already-proved spin-axis PSD cone and projecting
only its exact scalar coefficient maps onto the full S3 orbit inventory. This
is sufficient for equivalence by group averaging and avoids making an
unproved relation between conjugation phase gauges under permutations that
move the Y axis.

## 2026-07-29 — full-permutation derived model gate passes

Slurm job `22988509` passed all 146 assertions after adding the concrete
coefficient quotient and JuMP layer. Two independent exact builds produced
identical coefficient-map and assembly hashes. The model has 3,250 variables,
zero affine equalities, and retains the complete 12-cone spin-axis inventory
with 16,707 triangle entries and maximum side 81.

The passing `test.log` SHA-256 is
`9ef5f74de8b184d44233c2744f32a9977948c89f8f5bee5210d161cc0f67eae2`;
peak process RSS was 965,468 KiB. Proceed to clean solver-free MOF builds and
reload checks for both fixed gamma values.

## 2026-07-29 — accept immutable full-permutation MOF inputs

Slurm job `22988518` built and independently reloaded both solver-free models
from clean commit `d799a63`. The gamma=0 model/runmeta SHA-256 values are
`4f62a5e16822d2df174af8d9013bb1622c54d8c47bd2f78a59a086524ad4d67f`
and
`a0ac07d93e0101732d4d588762754f0ed4837ae2b294f53f7d6bae7573e1152f`;
the gamma=1/2 values are
`e47bf0d3146ada223bbb389920ea4ca1f79efef467ee7a81ef72d42741652e9f`
and
`39da4547ce672cc3d087db7a199adcb76e73ab81672361beffe9c06910a6f05f`.

Both reloads confirm 3,250 variables, 13 constraints, all 12 named real PSD
cones, 16,707 triangle coordinates, and maximum side 81. Treat these as
immutable inputs. The dedicated runner must replay their checksum, fixed
setup, all four exact-reduction schemas, every recorded source hash, and the
reloaded cone inventory before optimization. Preserve the mandated order:
gamma=0 first, gamma=1/2 only after its audited feasible solution.

## 2026-07-29 — full-permutation gamma=0 gate passes but factor fill grows

Slurm job `22988532` passed all fail-closed gates and returned `OPTIMAL` with
primal and dual feasible points. Independent reconstruction gave
normalization 1, zero affine and PSD violations, and minimum block eigenvalue
`0.13079207445451374`. Total runner wall was 43.098 s, process peak RSS was
2,750,960 KiB, and `result.toml` SHA-256 is
`365bef5ca2bae523fdc4903650bcf4cbbfd3c53a7b54a015dcc7b9a2b0dc542c`.

The exact quotient passes its required numerical equivalence gate and
authorizes gamma=1/2. However, reducing scalar moments from 8,803 to 3,250
increased factor fill from 41.4 million to 60.7 million nonzeros, peak RSS
from 2,602,300 to 2,750,960 KiB, and total wall from 40.568 to 43.098 s at
gamma=0. Do not infer memory improvement from moment count alone. Complete
the fixed gamma=1/2 decision run, then switch to an exact S3 row-space/cone
decomposition if its representation action can be proved.

## 2026-07-29 — full-permutation gamma=1/2 is feasible; switch to cone rows

Slurm job `22988534` passed every immutable-input and replay gate and returned
`OPTIMAL` with primal and dual feasible points. Independent reconstruction
gave normalization 1, zero affine and PSD violations, and minimum block
eigenvalue `0.09503337763320019`. Total runner wall was 37.017 s, process
peak RSS was 2,736,824 KiB, and `result.toml` SHA-256 is
`d19b811d37dcbc6229351d1642afe6cc197f072bf5c8e862a5a4989a282ff5d3`.

The scientific decision is unchanged: the exact `d=2` finite relaxation is
feasible at gamma=1/2. Relative to the spin-axis model, the full moment
quotient is 3.8% faster but uses 11.7% more process RSS and grows the factor
from 41.2 million to 60.3 million nonzeros. Keep the spin-axis model as the
measured memory baseline.

Switch routes from moment count to cone rows. Full S3 permutes all three
nontrivial V4 characters transitively. If exact coefficient replay proves
that the retained 81-side orbit representative is congruent to the stable
character's existing 36- and 45-side eigenspace blocks, drop the redundant
81-side cone in each positive family and the analogous redundant gap scalar.
Do not remove any cone until this relation is proved exhaustively over exact
coefficients.

## 2026-07-29 — cone truth r1 requires complex gauge phases

Slurm job `22988542` passed 139 of 142 assertions. The three failures were the
aggregate truth flag, the signed-real congruence flag, and its assumption that
computational-basis conjugation parity is uniform inside a V4 character
block. The orbit inventory `[1,81,81]`, 6,643-entry traversal, exact stable
basis ranks, stable plus/minus cross zeros, and the nine-cone JuMP assembly
all passed. Peak RSS was 915,688 KiB and `test.log` SHA-256 is
`11b7b016a5ca7f41b5b93a609e321bed3b7ed71cfb4b89221cb02b4e6f442baa`.

The proper correction follows from the already-fixed conjugation gauge. If a
row has gauge phase `p` and the signed spin permutation maps it to a row with
phase `p'`, the transport phase is `q = sign * conj(p') * p`, which lies in
`{±1,±i}`. Replay the congruence as
`R_orbit[i,j] = conj(q_i) q_j R_stable[p(i),p(j)]`; whenever the factor is
imaginary, both real matrix entries must vanish exactly. This changes a
consequential proof input rather than repeating the failed signed-real
assumption.

## 2026-07-29 — cone truth r2 proves the congruence and sharpens phase count

Slurm job `22988562` passed 143 of 144 assertions. The phase-corrected
6,643-entry congruence, exact stable basis ranks, all cross-block zeros, and
the concrete nine-cone model passed. The only failure was a diagnostic
expecting a positive mixed transport-phase count; the exact count was zero.
Peak RSS was 970,408 KiB and `test.log` SHA-256 is
`c3d822ceba8abf183d59cd1c50d8a1a0e5fbb349e97461351f4756aff45b4d90`.

The stronger exact statement is that, within each related character block,
all row transport phases have the same real/imaginary class even though the
individual conjugation parities vary. Thus every pairwise factor
`conj(q_i)q_j` is real. R3 changes the diagnostic to require this phase-class
alignment and an exactly zero mixed-pair count; no model or cone inventory is
changed.

## 2026-07-29 — full-spin nontrivial-character cone theorem passes

Slurm job `22988602` passed all 145 exact assertions. The truth gate replayed
all 6,643 orbit entries with their exact realification transport phases,
proved full rank of the retained stable-character bases, verified phase-class
alignment and every plus/minus cross zero, and reconstructed the concrete
JuMP model without an optimizer.

The equivalent representation removes two 81-side positive cones and one
redundant gap scalar. It retains 3,250 moments and nine real PSD cones with
10,064 packed triangle coordinates and maximum side 73. Peak process RSS was
835,316 KiB and `test.log` SHA-256 is
`6fac20b5e07a66d4fc863cdaa45f92d53a219a19e0be3b5075669d140c1ec219`.
Proceed to clean solver-free builds and reload checks for both fixed gamma
values; optimization still requires gamma=0 to pass before gamma=1/2.

## 2026-07-29 — accept immutable nine-cone MOF inputs

Slurm job `22988604` built and independently reloaded both solver-free models
from clean commit `2f87e7a`. The gamma=0 model/runmeta SHA-256 values are
`a34c629a502b515fc615467bc876f691c0494d523c32f4e1dc5323d84b235d26`
and
`0b2942005c4bae13019508484d7af35106b67fbc978b067b99e484e7b588d086`;
the gamma=1/2 values are
`ce3f4030afdc19d90b0f3a1bd2e8a2d6f3f06c19aad6c61e3b0bbbfe68de17a9`
and
`3c880055c1728faeda17c49301819b41272c5fcac0654c19db3e85da0e528ca3`.

Both reloads confirm 3,250 variables, 10 constraints, all nine named real PSD
cones, 10,064 packed triangle coordinates, and maximum side 73. Job peak RSS
was 917,940 KiB and elapsed time was 5:21; the Slurm-log SHA-256 is
`f35286e6c2083aeacc43655ceceb47a20831d3261e11bcd1159300fd1e922280`.
Treat the two bundles as immutable. The separate runner must verify the
allowlisted MOF and runmeta hashes, fixed setup, every exact reduction layer,
all recorded source hashes, and the reloaded cone inventory before Mosek is
attached. Preserve the mandated order: gamma=0 first and gamma=1/2 only after
an audited feasible gamma=0 point.

## 2026-07-29 — pursue the remaining trivial-character S3 isotypic split

Nine-cone gamma=0 job `22988753` is pending on the xH5 association job limit.
Use that scheduler wait for an independent exact derivation rather than
repeating or tuning a solve.

The trivial-V4 centered and scalar row spaces have dimensions 108 and 109:
36 axis-permutation triples, plus the scalar identity. For each triple, the
integer basis `t=(1,1,1)`, `w=(1,1,-2)`, `m=(1,-1,0)` separates the trivial
S3 irrep from two standard-irrep directions. Full-S3 invariance predicts
exactly zero cross blocks and `W=3M`; if exhaustive coefficient replay and
full-rank checks pass, only `t` and one `m` copy are needed.

This would change positive block sides from
`[72,36,36,45,73,36,36,45]` to
`[36,36,36,45,37,36,36,45]`, reducing packed cone coordinates from 10,064
to 6,104 and maximum side from 73 to 45. The route is mathematically exact,
but no solver model may rely on it until the dedicated Slurm truth gate
passes all 7,848 cross-entry and 1,332 proportionality checks.

## 2026-07-29 — prepare the fixed-window spatial involution as a later gate

A direct source-level enumeration of all eight D4 maps found exactly one
nonidentity symmetry of the fixed level-1 term set:
`(x,y)->(-y,-x)`. It preserves the 3-by-3 patch, central inner site, both
instantiated dimer bonds, and all square-nearest-neighbor bonds. The other
axis/diagonal reflections and 90/180/270-degree rotations do not preserve the
finite term multiset and are rejected.

Prepare a separate order-two quotient after the full-spin isotypic layer. Its
truth gate must establish moment closure, signed row closure within every
retained block, covariance of all 6,104 isotypic coefficients, equality-space
invariance, exact full-rank spatial eigenspace bases, and zero plus/minus
cross blocks. The first run is an inventory gate and will harden its exact
moment and block counts only after all theorem conditions pass. Keep it behind
the already-queued isotypic proof so an unproved downstream route cannot
obscure that result.

## 2026-07-29 — nine-cone gamma=0 gate passes and authorizes gamma=1/2

Slurm job `22988753` passed the immutable input, fixed setup, five-layer exact
reduction, source-hash, and reloaded nine-cone gates. Mosek returned `OPTIMAL`
with primal and dual feasible points. Independent reconstruction gave
normalization 1, zero affine and PSD violations, and minimum block eigenvalue
`0.1252658219892882`.

Solver wall was 10.661 s, total runner wall 27.593 s, process peak RSS
1,699,824 KiB, and the post-factor nonzero count was 26.3 million.
`result.toml` SHA-256 is
`f3b394aff863243aee7706f7c52f728ca303df043429e7c70245e6d79ce2e3a0`.
Relative to the spin-axis gamma=0 memory baseline, the exact cone reduction
cuts RSS by 34.7%, total wall by 32.0%, and factor fill by 36.5%. The
numerical equivalence gate passes, so gamma=1/2 is now authorized.

## 2026-07-29 — full-spin trivial isotypic theorem passes

Slurm job `22988781` passed all 177 assertions in the complete exact testset
and all 32 character checks. The gate proved the 108/109 source dimensions,
72 three-row orbits plus the scalar identity, exact full rank of both
`t,w,m` bases, zero for all 7,848 cross entries, and `W=3M` for all 1,332
standard upper-triangle entries. Two deterministic coefficient assemblies
and the optimizer-free nine-cone JuMP reconstruction also agree.

The exact representation retains all 3,250 moments with positive block sides
`[36,36,36,45,37,36,36,45]`, one scalar gap cone, 6,104 packed PSD
coordinates, and maximum side 45. `test.log` SHA-256 is
`1ec6ebdd77b6a94c04b1956c5cfd07f62ad780a2fb34f0fbed7c7351f12f2ee9`;
the process-time peak was 979,428 KiB and Slurm step MaxRSS was 821,520 KiB.
The theorem is accepted. Complete the already-authorized nine-cone
gamma=1/2 result before building solver inputs from this next reduction.

## 2026-07-29 — accept immutable full-spin isotypic MOF inputs

Slurm job `22988846` completed both clean solver-free builds and independent
MOF reload checks from commit `792e61c`. The gamma=0 model/runmeta SHA-256
values are
`990e78381e25b2be683f00d93ffc85ff543d6beed0580b660b25d8f8cf8b90d2`
and
`7fac0e27fafe3b902fc3322b880aeccce38f2ba5b0061a172e3f7057bc1e1d23`;
the gamma=1/2 values are
`22aa6d169fabbe6b9f41eeba4ddc7d37fb1f8b769427714875760ae94dc559f9`
and
`8e84bde7043d0023cbd82181d83f1a70622f222b6a706d0a36b9f45283e94e99`.

Both reloads prove 3,250 variables, 10 constraints, all nine named cone
dimensions, 6,104 packed triangle coordinates, and maximum side 45. The
build job used 897,624 KiB MaxRSS in 3:54; its Slurm-log SHA-256 is
`7036d9caa22973f63ca4b0c09113556fcecfb9e637f39b1edb101cfa3bc1834a`.
Treat the inputs as immutable and preserve the gamma=0-before-gamma=1/2
optimization order.

## 2026-07-29 — nine-cone gamma=1/2 remains feasible at 1.63 GiB

Slurm job `22988816` passed all immutable-input and replay gates and returned
`OPTIMAL` with primal and dual feasible points. Independent reconstruction
gave normalization 1, zero affine and PSD violations, and minimum block
eigenvalue `0.09098861640180578`. The process peak was 1,666,944 KiB, Slurm
MaxRSS was 1,668,768 KiB, total runner wall was 34.586 s, and the post-factor
nonzero count was 26.4 million. `result.toml` SHA-256 is
`f24c297da06061b08aa9e94e83f401967cb055e89620bb9eceb834425c16e031`.

Relative to the spin-axis gamma=1/2 result, exact redundant-cone removal cuts
process RSS by 32.0% and factor fill by 35.9%. The scientific conclusion is
unchanged: this exact `d=2` finite relaxation is feasible at gamma=1/2 and
does not exclude that candidate gap. No infeasibility certificate branch is
applicable.

## 2026-07-29 — derive a continuous-spin fallback beyond discrete S3

The fixed Hamiltonian and unrestricted relaxation are invariant under global
spin rotations, and the existing conjugation reduction permits averaging to
the corresponding `O(3)`-invariant subspace. Because every retained scalar
moment has total Pauli degree at most four and even axis parities, its spin
tensor is generated exactly by `delta_ab` at rank two and the three delta
pairings at rank four.

Prepare an inventory-only exact route after the isotypic model: enumerate
each axis-erased skeleton, account for state-symbol commutativity by rational
row reduction, choose existing moment pivots, and verify the substitution
under the rational infinite-order rotation with cosine `3/5`. Do not build or
solve a derived MOF until this separate truth gate passes and the pivot count
is decision-relevant.

## 2026-07-29 — spatial truth r1 requires orbit re-representation

Slurm job `22988821` stopped at the first moment-closure check, before any
coefficient covariance, cross-block, or model assertion. The local
site-reflection map is valid, but the full-spin moment inventory stores only
the lexicographically first member of each spin-axis orbit. Reflecting that
stored member can produce a noncanonical member of the reflected orbit.

Because spatial and global spin actions commute, the exact induced action on
the quotient is site reflection followed by the already-proved full-spin
representative map. R2 makes that composition explicit and requires that its
nontrivial use count be positive. This is a consequential action correction,
not an identical repeat. The failed log SHA-256 is
`a7e2e3ff6d9240bcbaedb5a49df7624737d1ab68277b60bfc44a7938d60982f4`;
Slurm MaxRSS was 713,484 KiB.

## 2026-07-29 — prepare the exact continuous-spin l=2 cone gate

Within each centered/scalar rank-two row skeleton, the current octahedral
decomposition retains the diagonal l=2 component `XX-ZZ` and the
off-diagonal component `XZ+ZX` as separate 36-side cones. Both have squared
component norm two. Continuous-spin invariance predicts identical
multiplicity matrices, but this prediction is not yet accepted as a model
reduction.

Encode a separate fail-closed truth gate that requires canonical component
rows, a full-rank spatial-skeleton bijection in both families, and exact
signed congruence of all 1,332 projected upper-triangle coefficients. If it
passes under Slurm after the moment-inventory gate, remove only the two
S3-standard duplicate cones. The resulting target inventory is six positive
cones with sides `[36,36,45,37,36,45]`, one scalar gap cone, and 4,772
packed PSD coordinates. Prepare optimizer-free JuMP translations for the
moment-only and six-cone assemblies so a passing truth gate can advance
without another source-design cycle; their presence does not authorize a
model build. A tiny synthetic rank-two test independently checks both
canonical l=2 components, their squared norm two, orientation reversal, and
the signed skeleton permutation; all eight assertions pass. Prepare a
solver-free builder that replays the complete reduction chain for gamma 0
and then gamma 1/2, records every source hash and layer schema, and
independently reloads all named cones. Keep it unsubmitted until both new
truth gates pass.

## 2026-07-29 — isotypic gamma=0 gate passes

Slurm job `22988910` passed the immutable MOF/runmeta manifests, fixed setup,
all six exact-reduction schemas and counts, all 17 recorded source hashes,
and the reloaded inventory of 3,250 variables and nine named cones. Mosek
returned `OPTIMAL` with primal and dual feasible points. Independent
reconstruction gave normalization 1, zero affine and PSD violations, and
minimum block eigenvalue `0.11113568782699743`.

Solve wall was 6.624 s, total runner wall 23.124 s, process peak RSS
1,016,136 KiB, Slurm MaxRSS 1,018,020 KiB, and the factor contained
8.53 million nonzeros. Relative to the preceding nine-cone gamma=0 solve,
the exact isotypic representation reduces process RSS by 40.2%, factor fill
by 67.6%, and total wall by 16.2%. `result.toml` SHA-256 is
`2fc5f7e8c5af8a3a3d1ab425ff38d24d01948361dd02e1e6af5fe9f3db65cb07`;
the Slurm-log SHA-256 is
`6758ca56c0296ab4e5194e283a7729e320fe27c5bc368419389755e3388b548e`.
The gamma=0 equivalence gate passes and authorizes isotypic gamma=1/2.
The spatial and continuous jobs from commit `2b4e3da` have now completed,
so the shared remote worktree may advance to the value-export runner before
gamma=1/2 submission.

## 2026-07-29 — define the combined spin/spatial exact route

The shared Slurm association cap is delaying all three active jobs before
launch, so do not create an identical submission. Instead, record the
mathematically next route behind the existing gates. Global spin rotations
commute with the anti-diagonal site reflection. On continuous-spin pivot
coordinates the corrected reflection induces the exact rational map
`T(y)=q_c(r(y))`; the combined invariant coordinates are the exact fixed
space of `(I-T)y=0`.

Require `T^2=I`, exhaustive intertwining on every isotypic moment,
deterministic rational fixed-space coordinates, full-rank spatial row
splits, and exact zero cross blocks after projection. Do not implement or
submit this combined model until the standalone continuous-spin and spatial
truth gates both pass, and do not assume that its smaller cone inventory
will reduce solver fill before measuring the six-cone model.

## 2026-07-29 — preserve primal values for an exact feasibility witness

The audited gamma=1/2 solutions are comfortably inside every reconstructed
PSD cone. A later exact strengthening can round the moment vector to modest
rationals, rebuild every coefficient over the original exact assembly, and
prove positive definiteness by rational LDL pivots. The existing result
artifacts record only eigenvalue diagnostics, not the moment vector.

Revise the isotypic runner to export each named primal variable using its
exact IEEE-754 binary representation and checksum that generated table. Do
not change or rerun the queued gamma=0 attempt. If it passes, use this
revision for the already-authorized gamma=1/2 solve, then attempt the
rational replay as a separate Slurm gate. Failure to rationalize is not
solver infeasibility and must not change the existing numerical conclusion.

Prepare the separate replay now, but keep it unsubmitted. It fails closed on
the allowlisted MOF/runmeta, the solve and primal-table manifests, all
recorded source hashes, the fixed setup, and every exact assembly hash. It
tries common decimal denominators `10^6`, `10^8`, `10^10`, and `10^12`;
for a candidate it rebuilds all 6,104 exact rational matrix entries and
requires every no-pivot rational LDL diagonal to be strictly positive.
Binary64 decoding, decimal rounding, and positive/indefinite LDL examples
pass all eight local synthetic assertions.

## 2026-07-29 — corrected spatial reflection passes

Slurm job `22988911` passed all 28 assertions after the induced moment action
was corrected to site reflection followed by full-spin orbit
re-representation. The exact involution maps 3,250 isotypic moments to 1,711
representatives. All 6,104 source cone coefficients are covariant, all 2,913
spatial plus/minus cross entries are exact zeros, and the nine split row
bases have full dimensions `[36,36,36,45,37,36,36,45,1]`.

The equivalent representation has 16 positive cones with sides
`[21,15,21,15,21,15,24,21,22,15,21,15,21,15,24,21]`, one scalar gap
cone, 3,191 packed PSD entries, and maximum side 24. `test.log` SHA-256 is
`3d60469de1da702d33bf6d3bee971fa4bcd99b0e0d852b2246bdd2c4803c327b`;
process peak was 896,892 KiB and Slurm MaxRSS 773,896 KiB. Accept the theorem
and authorize clean solver-free MOF generation for both fixed gamma values.

## 2026-07-29 — continuous-spin moment quotient passes

Slurm job `22988914` passed all 23 assertions. The exact delta-tensor
parameterization maps 3,250 isotypic moments to 2,458 pivots across 874
axis-erased skeletons: one rank-zero, 81 rank-two, and 792 rank-four. The
rational infinite-order rotation gate replays 64,882 components exactly,
both deterministic assemblies agree, and all 6,104 isotypic packed cone
entries reconstruct.

`test.log` SHA-256 is
`cd489366f56038bb97cc4dc208bc59ff95b5fc52622ba3e3d44002108d1f0317`;
process peak was 826,164 KiB and Slurm MaxRSS 722,980 KiB. Accept the moment
quotient and authorize the separately encoded l=2 cone-redundancy truth
gate. Do not build a continuous-spin MOF until that gate passes.

## 2026-07-29 — shared submission cap delays three authorized gates

After a fresh `xhacnormalb` queue probe, the first submission in the
authorized batch was rejected before Slurm assigned a job ID:

```text
AssocGrpSubmitJobsLimit
group max submit job limit exceeded 200 (used:200 + requested:1)
```

The fail-fast submission wrapper therefore created no isotypic gamma=1/2,
spatial-build, or continuous-spin-cone job and no result directory. This is
the same shared-account resource signature seen earlier, so an identical
submission is not repeated while the count remains saturated. Continue with
source-only preparation, then re-probe immediately before the next attempt.

## 2026-07-29 — isotypic gamma=1/2 solve and primal export pass

Slurm later accepted isotypic gamma=1/2 job `22988996`. It completed from
runner commit `5f933515f3eebbec0a4685f55df5fd20a6460773` with the allowlisted
model/runmeta SHA-256 values
`22aa6d169fabbe6b9f41eeba4ddc7d37fb1f8b769427714875760ae94dc559f9`
and
`8e84bde7043d0023cbd82181d83f1a70622f222b6a706d0a36b9f45283e94e99`.

Every fixed-setup, six-layer exact-reduction, source-file, model-count, and
named-cone check passed before optimization. Mosek returned `OPTIMAL` with
primal and dual feasible points. Independent reconstruction gave
normalization 1, zero affine and PSD violations, and minimum block eigenvalue
`0.08228797924548609`. Solver wall was 7.804 s, total runner wall 26.510 s,
process peak RSS 1,138,120 KiB, and Slurm MaxRSS 1,124,340 KiB. The result
SHA-256 is
`84ef32c708b7d26871b868faf9afdc0ef75a06d9cb8f929f79d98909407d158a`.

The runner also exported all 3,250 primal variables by exact IEEE-754 bits;
the table SHA-256 is
`8ccbb186f7c0b66e2dafa5d0e28782757b88afadba4982f1532dbb4ca77ff1be`.
The numerical conclusion remains that this exact `d=2` finite relaxation is
feasible at gamma=1/2. It does not prove a physical bulk gap.

The exported table makes the next decision gate possible: run the prepared
exact rational replay, which accepts only a common-denominator witness with
strictly positive exact LDL pivots in all nine cones.

## 2026-07-29 — remote-agent results synchronized and main agent takes over

Both remote research agents were stopped after their Codex credentials became
invalid. No Slurm job remains active. The Shastry--Sutherland branch was
fast-forwarded locally from `5e844225...` to `5f933515...`; its two immutable
isotypic MOF inputs, gamma-zero and gamma-half solve bundles, and the
isotypic/spatial/continuous exact-truth bundles all pass their copied
`SHA256SUMS`.

The independent Kagome certificate branch is preserved locally at
`1dbbb9fa0da68a4abd1c92b35ade2c944c6bbcb4`. Its canonical envelope, source
MOF, exact ray, source audit, and independent PSD audit were copied to
`background/challenge-88/remote-results/kagome-certificate-20260729/` and
match the five hashes embedded in the envelope.

Future work is performed by the main agent. The next scientific action is the
xH5-only exact rational replay of the isotypic gamma=1/2 witness; do not
restart either remote agent.

## 2026-07-29 — rational replay r1 exposes an entry-point type error

Slurm job `22990387` passed its copied input manifests and reached primal-table
loading, then failed closed before exact assembly. Julia's `split` returned
`SubString{String}` fields, but `bits_to_float` accepted only `String`.
Process peak RSS was 598,640 KiB. This attempt therefore says nothing about
the existence of the rational witness.

Broaden the parser argument to `AbstractString` and add an explicit
`SubString` regression. The focused helper suite passes 9/9 in 4.0 seconds
with 287,280 KiB peak RSS. Resubmit exactly once under a new result ID; do not
overwrite or reinterpret the r1 failure bundle.

## 2026-07-29 — corrected rational replay r2 is pending

The corrected parser was copied to xH5 with matching SHA-256
`9379ed739499f3955534085c4616ea14950e148c51bea14b322faef8875d396f`.
Slurm accepted job `22990727`, so this is distinct from a submission rejection,
but the job remains pending with `AssocGrpJobsLimit`. Do not submit another
copy while that group-limit signature is unchanged. Pending is not scientific
evidence; only the fetched replay manifest and exact LDL pivots can close the
witness claim.

## 2026-07-29 — authorize a coarse `d=2` bulk-gap scan

The exact isotypic representation makes a first boundary search cheap enough
to run in one Slurm allocation. Scan exact rational gamma values `1`, `2`, and
`4` sequentially and stop at the first infeasibility candidate. This signature
is decision-relevant because gamma `1/2` is already numerically feasible and
the next question is whether the finite relaxation has any upper transition
in a broad interval.

The scan runner accepts newly generated inputs only under an explicit dynamic
mode. It still requires a clean builder commit and tree, a contained results
directory, matching MOF/runmeta checksums, the exact fixed physical setup,
all six reduction inventories, all recorded source-file hashes, and nine
named-cone reload checks. A feasible point is residual-audited; an infeasible
solver status remains
`infeasibility_candidate_requires_independent_ray_replay`. It is not a bulk-gap
bound until that separate replay succeeds.

## 2026-07-29 — launch the coarse scan and correct wrapper paths

Coarse-scan r1, Slurm job `22990996`, was assigned a node but failed with
`JobLaunchFailure`, signal 53, at zero elapsed time. No stdout file or run
directory existed: the clean clone did not contain the gitignored parent
directory named by `#SBATCH --output`, so Slurm could not open the batch
output. Create that directory before submission and change the run signature
to r2. Job `22991011` then entered `RUNNING` on `a01r08n04` and printed the
start of the exact gamma-one build.

Rational replay r2, job `22990727`, also failed before assembly. Its wrapper
passed absolute model and solve directories, while the replay intentionally
requires repository-relative paths to keep inputs contained. Resubmit r3 with
the same checked artifacts expressed relative to the checkout. Job `22991012`
is pending under `AssocGrpJobsLimit`. Neither failure changes a mathematical
claim.

## 2026-07-29 — exact gamma-half witness passes; string boundary becomes a gate

Rational replay r3, job `22991012`, passed from the checked gamma-half
floating solution. Rounding all 3,250 moments to common denominator `10^6`
preserves exact normalization, and no-pivot rational LDL has strictly positive
pivots in all nine PSD blocks. The exact replay wall was 40.1 s; the Slurm job
used 1:17 and 614,344 KiB MaxRSS. This proves a strictly feasible exact
rational point for the current finite `d=2` relaxation at gamma `1/2`. It does
not prove that the physical bulk gap is at least `1/2`.

Coarse-scan r2, job `22991011`, built the gamma-one MOF successfully, then
failed before solver attachment because `split("1//1", "//")` produced
`SubString{String}` fields and the metadata checker accepted only `String`.
Treat this as an API-policy failure, not a one-line exception. All read-only
text boundaries in the three active solve/replay runners now accept
`AbstractString`; owned struct fields remain `String`. A dedicated regression
feeds real `SubString` values from `split`, `SubString`, and regex captures
through rational parsing and setup validation. Every future gamma-scan job
runs this regression before building 74,602 moments.

## 2026-07-29 — corrected and extended coarse scans remain feasible through gamma 32

Corrected coarse-scan r3, Slurm job `22991095`, ran from clean commit
`f1fb24ceb1a6ba110abbcb06307a9833bc90b524`. Its mandatory string-boundary
suite passed 11/11 before assembly. For each exact rational gamma `1`, `2`,
and `4`, the job rebuilt the 74,602-moment source, replayed all six exact
reductions, reloaded the 3,250-variable/nine-cone MOF, and independently
audited the returned primal. Every point is residual-checked feasible with
normalization one and zero affine and PSD violation. Minimum block
eigenvalues are `0.06341919455293454`, `0.010455807260659311`, and
`0.004514259614827765`. The job used 9:11 and 973,548 KiB Slurm MaxRSS.

Extended scan r4, Slurm job `22992336`, repeated the same complete signature
at gamma `8`, `16`, and `32`. All three are again residual-checked feasible.
Their minimum block eigenvalues are `0.0014308867937518066`,
`5.4343318096172766e-5`, and `4.915449793807536e-6`; the scalar gap-block
values are `0.01797420828848928`, `0.01368745758280987`, and
`0.007499637530884229`. It used 8:42 and 953,356 KiB Slurm MaxRSS.

Accept these as verified floating feasible points of the finite relaxation,
not as lower bounds on the physical bulk gap. The decision-changing
conclusion is that `L=1,d=2` has not produced an upper transition through
gamma 32 and is likely very weak in this model. An isotypic logarithmic scan
at gamma `64`, `128`, and `256` was submitted as job `22992662`, but it
remained pending and was cancelled at zero elapsed time once the exact
spatial representation was selected for all follow-up compute. First require
spatial gamma-zero and gamma-half A/B gates. Continue the same logarithmic
scan only with that verified 1,711-moment model; if it produces an
infeasibility candidate, require independent ray replay. If it remains
feasible or becomes numerically marginal without a ray, stop widening this
relaxation and move compute to a stronger window/order.

## 2026-07-29 — spatial representation passes deterministic A/B and gamma-half solve

Spatial builder job `22992784` completed the immutable gamma-zero and
gamma-half artifacts in 5:38 with 1,018,288 KiB Slurm MaxRSS. Independent
local builds used about 1.02--1.05 GiB and produced the exact same MOF bytes
as xH5:

- gamma zero:
  `5d770e3320ef9f2c6af7d3b763b7d05c2a316a245a114f98881c79007da2cf95`;
- gamma one-half:
  `526700018f93a1ee5bd4955f6e75a56669a805ca50e3b1671b341789409a899e`.

This closes the deterministic-build gate for the 1,711-moment, 17-cone,
3,191-packed-entry, max-side-24 spatial representation. The fail-closed
runner's 21 focused assertions pass, including dynamic-result containment and
canonical Git-blob provenance.

Solve jobs `22993015` and `22993016` then passed immutable input hashes, the
fixed physical setup, all seven exact-reduction inventories, source
provenance, MOF reload, and all 17 named cone checks. Both points are
`OPTIMAL` with primal and dual feasible points. Gamma zero solved in 8.382 s
with minimum block eigenvalue `0.12925186655108384`; gamma one-half solved in
6.993 s with minimum block eigenvalue `0.08286263095400265`. Both have exact
normalization and zero reconstructed PSD violation.

Accept this as an exact-equivalence and numerical-feasibility validation of
the smaller representation. It does not prove a physical gap of one-half.
Continue only with the spatial model. Scan r1, job `22993166`, failed in 16 s
before assembly because the wrapper exported dynamic mode before running its
canonical immutable-input tests. The gate correctly rejected that mode
mismatch; no model or optimizer ran. Commit `f5fbb1d` moves the export after
the 21-test regression. Corrected r2, job `22993230`, scans exact gamma values
`32`, `64`, `128`, and `256`; gamma 32 must reproduce the earlier isotypic
classification before later points are used. If all remain feasible, stop
widening this weak `L=1,d=2` relaxation and redirect compute to a stronger
window/order rather than interpreting arbitrarily large gamma as physics.

## 2026-07-29 — close the fixed-level gamma scan at 256

Corrected spatial scan r2, Slurm job `22993230`, passed the 21-test runner
gate, rebuilt every exact input from clean source, reloaded all 17 named
cones, and completed exact gamma values `32`, `64`, `128`, and `256`. All four
returned `OPTIMAL` with primal and dual feasible points and were promoted to
`feasible_residual_checked_float` only after zero affine and reconstructed
PSD violations.

Solve walls were `9.706`, `9.771`, `6.080`, and `6.197` seconds. Minimum
block eigenvalues were `9.378288472522944e-6`,
`9.554763007345435e-6`, `3.424375474403159e-6`, and
`1.634994035355913e-6`; scalar gap-block values were
`0.007962166397234682`, `0.0032291871095964098`,
`0.0020950778859543107`, and `0.0007716043441519105`.
The job used 18:37 and 1,092,064 KiB Slurm MaxRSS. Its bundle-manifest
SHA-256 is
`5ab5f415f117292a93f75b5232dff39dc1275decfb795ed4491052734c73ce67`.

Gamma 32 reproduces the feasibility classification of the exactly equivalent
isotypic representation. The scan therefore verifies the smaller spatial
model but does not expose a finite upper transition. The declining margins
suggest an asymptotic pseudo-moment escape face; they do not prove one and do
not imply a large physical bulk gap.

Close further gamma doubling at fixed `L=1,d=2`. Before spending compute on a
stronger relaxation, decompose the scalar gap form as `e(y)-gamma*c(y)` and
test the face `c(y)=0, e(y)>=0` under the remaining constraints. Then preflight
both `(L=1,d=3)` and `(L=2,d=2)` with nested-basis checks and choose the route
that removes the diagnosed escape face at acceptable cost.

## 2026-07-29 — complete-state gamma two remains feasible; use only proven S3 blocks

SCNet job `118147307` solved the 7,231-moment complete-state-polynomial
`L=1,d=2` spin/spatial model at exact gamma `2`. Mosek returned `OPTIMAL`
with primal and dual feasible points; the fail-closed residual audit promoted
the result to `feasible_residual_checked_float`. Solve wall was 1,031.084 s,
total runner wall 1,063.608 s, and peak process RSS 39,288,700 KiB. This is a
decision result: feasibility is monotone toward smaller gamma, so no scan of
`[0,2]` is useful at this hierarchy. Move to a stronger hierarchy.

The S3 character probe predicted that deleting two copies of each nontrivial
V4-character cone would reduce 112,387 packed entries to 32,387. Full truth
job `118153034` rejected that stronger claim before MOF construction. A
one-symbol anchor isolated the failure: every trivial-character isotypic
cross block is exactly zero and its two standard blocks obey `W=3M`, while
the proposed nontrivial positive-cone identification is not coefficientwise
exact after the current spatial/spin moment quotient. Do not delete those
cones.

The corrected reduction retains all nontrivial-character cones and applies
only the proven trivial-character decomposition. It is still exact and
reduces packed entries from 112,387 to 75,967 (32.4%) and maximum side from
198 to 135. Small truth job `118155030` passed in 1:34 with 717,092 KiB
MaxRSS. Full benchmark job `118155251` then passed the complete truth,
immutable-input, MOF reload, and residual chain. It returned `OPTIMAL` and
`feasible_residual_checked_float`. Peak process RSS fell from 39,288,700 to
23,861,984 KiB, a 39.3% reduction. Solve wall changed from 1,031.084 to
1,064.326 s, a 3.2% regression. The exact decomposition is therefore useful
for fitting stronger models in memory, but it does not speed this `L=1`
Mosek solve.

For the next hierarchy, row-only job `118155322` generated the complete
14,026-row `L=2,d=2` positive basis in 41 s. The centered minus/plus
trivial blocks have dimensions 1,320/1,455 and split into 440/485 size-three
S3 orbits. The scalar minus/plus blocks have dimensions 870/1,006 and split
into 290 size-three orbits and one singleton plus 335 triples. Thus no new
size-six orbit case is required. Full preflight `118155664` was submitted at
the maximum schedulable `kshcnormal` single-node shape, 32 CPUs and 114,000
MiB. The two rejected submissions before it performed no compute: 120,000
MiB with 32 CPUs exceeded `DefMemPerCPU=3569`, while 36 CPUs exceeded the
32-core node shape. Preserve 32 CPUs/114,000 MiB as the partition ceiling.
Preflight r1 `118155664` was cancelled after 5:37 and 3,392,068 KiB MaxRSS
because it still carried the already-disproven nontrivial-cone comparison.
Commit `767037a` removes that irrelevant work; r2 job `118156605` is the
active `L=2,d=2` preflight.

## 2026-07-29 — terminal-solve takeover preserves both baseline jobs

Source is clean branch `remote/challenge88-terminal-solve` at commit
`87be3177694bbc3db6566016eb645018cb59213d`. The exact attempted setup is the
unrestricted Shastry--Sutherland KMS relaxation with
`H=sum_dimer S_i.S_j + (4/5) sum_square_nn S_i.S_j`, no-boundary local
consistency window `L=2`, complete state-polynomial basis and complete
inner-state stationarity, `d=2`, and candidate `gamma=2`.

SCNet job `118171391` is `RUNNING` on `kshcnormal` with 32 CPUs and 114000 MiB.
At 2026-07-29T14:48Z its stdout had reached exact S3 isotypic coefficient
assembly before JuMP/Mosek, and process RSS was about 6.1 GB. xH5 job
`23011251` remains `PENDING (Priority)` on `xhacnormalb` with 64 CPUs and
240 GB. Neither job is cancelled, altered, or duplicated.

The next action changes implementation rather than repeating the signature:
inspect single-pass coefficient-to-solver construction and a fail-closed
post-solve residual/certificate export. A feasible point will be described
only as finite-relaxation feasibility; any solver-reported infeasibility will
remain a candidate until independently replayed.

## 2026-07-29 — bound the coefficient-fingerprint memory before the next build

The `L=2,d=2` coefficient inventory contains 4,446,492 PSD triangle entries.
Commit `87be317` retained one diagnostic `String` per entry and then copied the
entire framed stream into an `IOBuffer` to compute SHA-256. This data is used
only for provenance and is not solver input.

The changed route preserves the exact record order and byte framing but
computes row payloads in bounded batches, feeds them incrementally to SHA-256,
and releases each batch. Moment discovery remains exact and parallel. This is
not a repeated solve signature and does not alter either running baseline job.
The source parses under Julia 1.11, and a direct old-vs-streaming check passes
for mixed UTF-8/string/integer records. Next gate: run the existing L=1
coefficient-hash regression in the configured remote Julia environment; only
then use the route for a larger build.

The full existing regression subsequently passed locally with eight Julia
threads. The exact coefficient stage took 225.425 s and returned 7,231 moments,
75,967 PSD triangle entries, and the required unchanged SHA-256
`2a6753a6ea7c57fa43bd33e09339046206fae5217ac3ae47c0cf9cc3b2dc2679`.
This authorizes the bounded-memory fingerprint implementation for future
builds. It does not authorize duplicating either running L=2 solve.

xH5 baseline job `23011251` started at 2026-07-29T14:49:17Z from its original
commit `2de1678` on 64 CPUs / 240 GB and entered the same exact coefficient
pass. SCNet job `118171391` remains on commit `87be317`. Preserve both as
independent resource/solver comparisons.

## 2026-07-29 — make the direct solve fail closed on scientific status

The baseline `--mode solve` path records Mosek statuses but does not export the
primal moment vector or independently reconstruct its PSD blocks. Therefore a
completed baseline is operational evidence, not yet the residual-audited
finite-relaxation decision required by this track.

The changed path exports every moment as an exact IEEE-754 bit string, audits
normalization and all affine equalities, reconstructs all named real PSD cones,
computes their minimum eigenvalues and scale-normalized violations, and emits
one of three classifications: `feasible_residual_checked_float`,
`infeasibility_candidate_requires_independent_ray_replay`, or `unknown`.
Timeout and generic non-optimal statuses remain unknown. A standalone 2x2
Mosek regression covers shaped-cone reconstruction and all three classifier
branches. The next gate is that test under Slurm in the configured SCNet Julia
environment; no L=2 rerun is authorized merely to test plumbing.
