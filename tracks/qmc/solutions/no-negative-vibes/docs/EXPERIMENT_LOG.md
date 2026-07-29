# Experiment log

Updated: 2026-07-29

Every completed scientific experiment is appended here whether it succeeds,
fails, or only exposes an infrastructure defect. Large outputs live under the
ignored results tree; the committed entry carries enough provenance to rerun
and interpret them.

## DEV-EXTCONE-RED-001 -- exterior-cone interface characterization

- Proposal ID: exterior-cone-throughput-loop / Task 1
- Question: Do the new exterior-power characterization tests fail before the
  requested public oracle exists?
- Prediction: collection stops only because `oracle.exterior_cone` is absent.
- Source commit: `92e367791232fe33da6d456db6191303e1bbe272`
- Protocol/config: focused pytest collection from the solution directory;
  `PYTHONPATH` was the absolute solution directory and all BLAS thread counts
  were fixed to one.
- Host role and resources: WSL verification environment; one pytest process.
- Command: `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
  PYTHONPATH=/home/zibojin/code/nnv-zibo/tracks/qmc/solutions/no-negative-vibes
  /home/zibojin/miniforge3/envs/quantum_harness/bin/python -m pytest
  tests/test_exterior_cone.py -q`
- Result: exit 2; collection error in `0.15s`.
- Evidence paths and hashes: local
  `tests/test_exterior_cone.py` SHA-256
  `BB61553EF022C3A270E9DC07403392014D9BECB79D17EDA89B809B9CB87F2A91`;
  the WSL test file was copied from that exact content.
- Interpretation: the sole collection root cause was
  `ModuleNotFoundError: No module named 'oracle.exterior_cone'`. The test
  contract is therefore a valid RED state, not a test or environment typo.
- Transferable lesson: test the fixed exterior-minor convention and certificate
  serialization before adding scan integration; this keeps the high-throughput
  search oracle independently checkable.
- Decision / next experiment: implement only the requested exterior-cone
  functions, then replay focused and weight/scan regression tests.

## DEV-EXTCONE-GREEN-001 -- replayable numeric certificate boundary

- Proposal ID: exterior-cone-throughput-loop / Task 1 review amendment
- Question: Does the numerical exterior-cone oracle reject a serialized
  singular real transform and nonfinite multiplication/solve intermediates
  while still enforcing one transform for every atom at a grade?
- Prediction: the first implementation exposes both false-certificate
  boundaries; the hardened implementation rejects them without regressing the
  frozen weight/scan tests.
- Source commits: characterization `d5b5fa6110af212264b9cb20427f1a801344d629`;
  fix `ea616ea3580731d315e3c95c92342f2b8ba3d74b`.
- Protocol/config: WSL Python 3.11, absolute solution `PYTHONPATH`, one pytest
  process, and `OMP_NUM_THREADS=MKL_NUM_THREADS=OPENBLAS_NUM_THREADS=1`.
- RED result: exit 1, `2 failed, 12 passed, 1 warning in 0.13s`. The failures
  were exactly an overflow reported as an infinite margin and a
  tolerance-small complex transform whose serialized real projection was
  singular. The discriminating shared-transform I/H case already passed.
- GREEN result: focused exterior module `14 passed in 0.10s`; frozen
  weight/scan regression `11 passed in 0.38s`.
- Evidence hashes: final implementation SHA-256
  `60855BE4275A954B1BDB6C679E3190C8BA462BBC3506FEDE8D0B78E12E5E71A8`;
  amended tests SHA-256
  `66A850EC9C4057A315EBCE899E3D49134C15AE9955A0BA7163A6C16F2F8F9B7C`.
- Independent review: PASS. The reviewer replayed all three counterexamples
  and independently obtained `14 passed in 0.08s` plus
  `11 passed in 0.28s`.
- Repository-wide boundary: the whole solution test directory was attempted
  once after the first GREEN and stopped during collection with exit 1,
  `1 error in 1.29s`, because `tests/test_overlap_klein.py` imports the
  intentionally absent Task 9 RED interface `classify_r01_fixture`. This is
  the pre-existing frozen R01 RED, not a Task 1 regression; it is not repaired
  in this discovery loop.
- Interpretation: Task 1 is accepted only as a replayable
  `numeric-cone-fit` oracle. It is not an exact arbitrary-depth theorem.
- Transferable lesson: validate the exact object that will be serialized and
  fail closed on every nonfinite intermediate; finite inputs do not imply
  finite linear-algebra outputs.
- Decision / next experiment: construct float-free exact atom cards, then run
  the shallow mixed-word scan before building the larger certificate pipeline.

## Required entry schema

```text
Experiment ID:
Proposal ID:
Question:
Prediction:
Source commit:
Protocol/config:
Host role and resources:
Command:
Result:
Evidence paths and hashes:
Interpretation:
Transferable lesson:
Decision / next experiment:
```

## ENV-0001 — common-baseline verification

- Proposal ID: infrastructure prerequisite
- Question: Does merged common baseline `04e72bd` pass before new research?
- Prediction: all solution tests pass in the documented scientific environment.
- Source commit: `04e72bd8fb70d448647ba57c14ca412559ccde0d`
- Protocol/config: full `tracks/qmc/solutions/no-negative-vibes/tests`, BLAS
  threads fixed to one.
- Host role and resources: WSL worker, 16 logical CPUs, 31 GiB RAM; one test
  process.
- Result: `199 passed, 379 warnings in 6.77s`.
- Evidence: terminal transcript from the goal task; no large artifact.
- Interpretation: the merged teammate branch is a clean functional baseline.
  All warnings originate from the mpmath deprecated `bitcount` helper.
- Transferable lesson: run pytest from the solution root with `PYTHONPATH=.`;
  invoking it from an arbitrary directory produces false
  `ModuleNotFoundError: oracle`. The dedicated conda environment also required
  `pandas` for the report tests.
- Decision: new failures can be attributed to this branch after the same
  command is rerun at each checkpoint.

## ALG-0001 — exact occupation-basis algebra replay

- Proposal ID: `R01`
- Question: Does the exact Jordan--Wigner occupation-basis implementation obey
  the fermionic anticommutation, parity, and quadratic-operator conventions
  needed by later Klein/Fock calculations?
- Prediction: all exact Task 1 identities pass without floating tolerances.
- Source commit: `616dc4b32d6d2c0bf2e68793c3b229de6a4309ee`
- Protocol/config: focused `tests/test_fock_basis.py`, followed by the full
  solution test suite; `PYTHONPATH=.` and all BLAS thread counts fixed to one.
- Host role and resources: WSL verification worker; one pytest process.
- Command: `python -m pytest tests/test_fock_basis.py -q`, then
  `python -m pytest tests -q`.
- Result: focused `7 passed in 3.99s`; full `206 passed, 383 warnings in
  11.18s`.
- Evidence paths and hashes: exact implementation and replay tests at commit
  `616dc4b`; independent Task 1 review found zero Critical or Important issues.
- Interpretation: the low-bit occupation convention and exact sparse
  quadratic algebra are suitable as a trusted compiler layer. This result
  makes no positivity or novelty claim.
- Transferable lesson: exact SymPy identities should establish sign and basis
  conventions before any floating LP or random scan; otherwise a basis-order
  mistake can masquerade as a new cone.
- Decision / next experiment: freeze this convention and construct the exact
  Klein--Hodge gate.

## ALG-0002 — fixed Klein--Hodge gate and four-mode seed

- Proposal ID: `R01`
- Question: Can one fixed, non-one-particle-induced Fock-space basis transform
  map the preregistered four-mode one-body seed to exact Metzler matrices in
  both parity sectors?
- Prediction: the fixed six-row Hodge block is exactly orthogonal, preserves
  number sectors, has a nonzero Pluecker obstruction, and makes both parity
  blocks Metzler.
- Source commit: `ff3759e20ba00bc6101203e7c8943c371a2f24f4`
- Protocol/config: exact SymPy tests for the gate, basis rows, identity sectors,
  contiguous low-bit embedding, Pluecker quadric, seed, return types, and
  rejection behavior; followed by the full solution suite.
- Host role and resources: WSL verification worker; one pytest process.
- Command: `python -m pytest tests/test_fock_basis.py
  tests/test_klein_hodge.py -q`, then `python -m pytest tests -q`.
- Result: focused `15 passed in 0.51s`; full `214 passed, 382 warnings in
  3.16s`.
- Evidence paths and hashes: `oracle/klein_hodge.py` and
  `tests/test_klein_hodge.py` at `ff3759e`; independent Task 2 review:
  specification PASS, quality APPROVED, zero Critical/Important/Minor findings.
- Interpretation: this is an exact existence witness for a single four-mode
  transformed quadratic generator and a rigorously non-induced Fock transform.
  It is not yet evidence that an open cone survives the overlapping six-mode
  circuit or that the construction has a positive physical HS decomposition.
- Transferable lesson: tests for a change of basis must pin literal rows,
  identity action outside the active sector, and bit-index embedding
  independently. Orthogonality-only and helper-vs-helper tests permit
  convention mutations to pass.
- Decision / next experiment: compile the six-mode support masks, then ask
  exact LP feasibility for cross-block noncommuting rays.

## ENV-0002 — teammate integration replay at the R01 checkpoint

- Proposal ID: infrastructure prerequisite
- Question: Does merging shared integration head `5cfcfa2` into the verified
  R01 Task 2 state preserve the complete test baseline?
- Prediction: all existing and new tests pass after retaining both sides of the
  documentation index conflict.
- Source commit: `acc947d6a6ced37692332d3e818ea97b2ba4a359`
- Protocol/config: full solution test suite in the same WSL environment.
- Host role and resources: WSL verification worker; one pytest process.
- Command: `python -m pytest tests -q`.
- Result: `245 passed, 381 warnings in 3.54s`.
- Evidence paths and hashes: merge commit `acc947d`; exact bundle
  `nnv-sync-acc947d.bundle` was verified before replay.
- Interpretation: the merged repository is a valid base for Task 3. No
  scientific endorsement of the teammate directions is inferred from this
  integration-only test.
- Transferable lesson: when a documentation-only merge conflict consists of
  disjoint navigation entries, retain both sets, then rerun the complete suite
  at the merge SHA. Do not conflate integration success with content review.
- Decision / next experiment: stop periodic teammate-PR handling and focus
  compute/review capacity on our own R01 program.

## ALG-0003 — six-mode support geometry and BdG basis compiler

- Proposal ID: `R01`
- Question: Can the two overlapping Klein plaquettes be assigned a fixed,
  non-complete six-mode support graph with deterministic number-conserving and
  BdG quadratic bases suitable for exact inequality compilation?
- Prediction: the preregistered masks contain 7 ring, 2 bridge, and 4 diagonal
  edges; directed hopping and pairing labels map to the intended exact Fock
  operators.
- Source commit: `550b629f87e1882ea1195ab9fff3d546703bdd32`
- Protocol/config: exact geometry, mask nesting, edge exclusion, dimension,
  label, operator, API rejection, immutability, and hand-derived fermionic
  phase tests.
- Host role and resources: WSL verification worker; one pytest process.
- Command: `python -m pytest tests/test_overlap_klein.py -q`, then
  `python -m pytest tests -q`.
- Result: focused `16 passed in 0.59s`; full `261 passed, 382 warnings in
  3.78s`.
- Evidence paths and hashes: `oracle/overlap_klein.py` and
  `tests/test_overlap_klein.py` at `550b629`; final independent review:
  specification PASS, quality APPROVED, zero findings.
- Interpretation: the six-mode search space is now fixed and reproducible,
  including two genuine cross-block bridge edges. No feasibility, positivity,
  noncommutativity, or physical-model claim has yet been made.
- Transferable lesson: comparing a generated BdG matrix to the same production
  constructor is circular. Pin creation/annihilation matrix elements by hand,
  including a spectator-occupation Jordan--Wigner minus sign, and require
  annihilation to equal the transpose of creation.
- Decision / next experiment: compile every within-parity off-diagonal Metzler
  inequality exactly in `Q(sqrt(2))`.

## ENV-0003 — nested CPU-worker key-authentication readiness probe

- Proposal ID: infrastructure prerequisite
- Question: Is the dedicated public key already installed on the nested CPU
  worker so unattended parameter cells can start safely?
- Prediction: a strict-host-key, password-disabled `BatchMode` probe returns
  the logical CPU count.
- Source commit: `71661db1bd269faa573ac2559abc2969ef8da3dc`
- Protocol/config: dedicated key, strict host-key checking, eight-second
  connect timeout, and no password fallback.
- Host role and resources: WSL gateway to the CPU worker.
- Command: secret-free `ssh -o BatchMode=yes ... nproc` readiness probe.
- Result: failed with `Permission denied (publickey,password)`; no remote
  command ran.
- Evidence paths and hashes: terminal transcript in the active goal task; the
  public-key and host fingerprints remain only in the private handoff.
- Interpretation: the worker is reachable but unattended authentication is
  not configured. Small exact tasks remain unblocked on WSL.
- Transferable lesson: never place an initial password in a command, script,
  environment variable, or log. Install the dedicated public key once through
  an interactive `ssh-copy-id`, then re-run a password-disabled probe.
- Decision / next experiment: continue exact compiler work on WSL; before the
  first broad parameter scan, complete the one-time interactive key install.

## ENV-0004 — nested CPU-worker scientific-environment bootstrap

- Proposal ID: infrastructure prerequisite
- Question: Can the nested CPU worker become a reproducible, unattended second
  compute environment without administrator privileges or direct GitHub
  access?
- Prediction: dedicated key authentication, a checksum-verified user-space
  Python distribution, a mirrored scientific environment, and exact Git
  bundle transport reproduce a committed focused test.
- Source commit: `550b629f87e1882ea1195ab9fff3d546703bdd32`
- Protocol/config: password entered once through an interactive
  `ssh-copy-id`; strict host-key and password-disabled verification; Miniforge
  `26.3.2-3` downloaded from the NJU release mirror; packages from the TUNA
  conda-forge mirror; one BLAS thread.
- Host role and resources: CPU worker, 64 logical CPUs and 503 GiB RAM; future
  process limit 62.
- Command: key-authentication probe, installer SHA-256 comparison, isolated
  environment creation, bundle clone, and
  `pytest tests/test_overlap_klein.py -q`.
- Result: public-key login succeeded; installer digest matched
  `848194851a98903134187fbb4ab50efe87b003e0c0f808f97644b7524a62bf2c`;
  Python 3.11.15 environment created; exact clone HEAD `550b629`; focused
  smoke test `16 passed in 0.78s`.
- Evidence paths and hashes: active goal transcript and private handoff; no
  credentials or private host data are committed.
- Interpretation: both authorized machines are now usable. The CPU worker can
  run 62 independent cells while WSL retains two logical CPUs for system
  responsiveness.
- Transferable lesson: the system Python lacked `ensurepip`, and direct GitHub
  timed out. Avoid sudo and repeated network retries: install a
  checksum-verified user-space distribution through a reachable mirror, use
  `--override-channels` for conda, and move exact commits as Git bundles.
- Decision / next experiment: replay exact compiler tests on both machines,
  then allocate disjoint Task 8 parameter cells.

## ALG-0004 — exact six-mode Metzler inequality compilation

- Proposal ID: `R01`
- Question: Can the overlapping six-mode transform and each allowed quadratic
  basis be compiled into a complete, provenance-preserving system of exact
  within-parity Metzler inequalities over `Q(sqrt(2))`?
- Prediction: exact and independent floating conjugations agree; the
  number-conserving `rings-bridges` basis has 24 labels and exactly 560
  nonzero ordered off-diagonal constraint rows.
- Source commit: `55205c2505534e0c15bcd198caac5c1f11b49934`
- Protocol/config: exact transform/basis/parity validation, hand-derived
  two-mode fixture, exact algebraic sign cases, unsupported-domain rejection,
  empty-system shape, six-mode NumPy value cross-check, and an independent
  exact all-row provenance audit.
- Host role and resources: WSL primary verification plus CPU-worker
  cross-environment verification; one pytest process and one BLAS thread on
  each.
- Command: `python -m pytest tests/test_metzler_system.py -q`, followed on WSL
  by `python -m pytest tests -q`.
- Result: final WSL focused `35 passed, 624 warnings in 6.91s`; WSL full
  `296 passed, 1003 warnings in 10.29s`; CPU production-HEAD focused replay
  `34 passed, 624 warnings in 4.66s`.
- Evidence paths and hashes: `oracle/metzler_system.py` and
  `tests/test_metzler_system.py` at `55205c2`; final independent review:
  specification, production, and quality APPROVED with zero findings.
- Interpretation: the exact linear-inequality oracle is complete for the fixed
  support and transform conventions. The count `560` is a compiler invariant,
  not evidence that the anchored cone is feasible.
- Transferable lesson: a numerical comparison over compiler-retained rows
  cannot detect omitted constraints. Independently enumerate all direct
  within-parity nonzero rows, lock their provenance and count, then compare
  values.
- Decision / next experiment: solve anchored number-conserving and BdG LPs,
  rationalize candidate rays, and replay exact primal or dual certificates.

## ALG-0005 — anchored LP and exact primal/double-dual replay

- Proposal ID: `R01`
- Question: Can numerical anchored feasibility be upgraded, without hidden
  coefficient bounds, to exact `Q(sqrt(2))` primal certificates or exact
  two-sided Farkas certificates proving an anchor is identically zero?
- Prediction: synthetic feasible, infeasible, unbounded-coefficient,
  degenerate-support, empty, structural-zero, and positively rescaled systems
  are classified without a false certificate; JSON replay is canonical and
  system-bound.
- Source commit: `5c7b3293e199f6e6dbb8832c30f8188659801675`
- Protocol/config: HiGHS discovery with unbounded variables; forced exact
  anchor; exact full-cone replay; positive and negative dual identities;
  `N=10^5` / `N=10^12` row-scaling tests; malformed and malicious JSON tests.
- Host role and resources: WSL primary replay and CPU-worker independent
  environment replay; one test process and one BLAS thread.
- Command: `python -m pytest tests/test_overlap_klein.py -q`, followed on WSL
  by `python -m pytest tests -q`.
- Result: the initial `b310b4a` replay failed 4 focused tests because
  SymPy/mpmath `full=True` reconstruction crashed at exact/near integer one.
  After the narrow compatibility fix and review-completeness fixes, final WSL
  focused `44 passed, 12 warnings in 1.21s`; WSL full `324 passed, 1020
  warnings in 10.68s`; CPU focused `44 passed, 12 warnings in 1.73s`.
- Evidence paths and hashes: Task 5 production/fix commits `b310b4a`,
  `98e6cbf`, and `5c7b329`; final independent review approved specification,
  production, and quality with zero findings.
- Interpretation: the certificate layer is now conservative and complete for
  the tested exact cases. It cannot turn a floating success into a theorem
  without exact replay, and its proof power is invariant under positive
  rescaling in the tested `10^12` range. No actual R01 anchor has yet been
  classified.
- Transferable lesson: third-party symbolic reconstruction may fail at simple
  boundary values; isolate the version-specific failure and keep the
  nontrivial mandated algorithm. More importantly, never threshold away
  positive Farkas weights or impose an undeclared denominator cap: both change
  theorem-proving power under harmless row scaling.
- Decision / next experiment: run the versioned real six-mode protocol for
  all support/family cells and persist exact certificates before interpreting
  feasibility.

## R01-E001 — number-conserving six-mode bridge gate

- Proposal ID: `R01`
- Question: For the fixed overlapping Klein circuit
  `U = U_[2,3,4,5] U_[0,1,2,3]`, can any directed hopping coefficient on
  either cross-cluster bridge survive the exact Metzler cone when the
  quadratic basis is number conserving?
- Prediction: at least one bridge direction and sign survives after the ring
  terms are admitted; adding the preregistered diagonal terms may enlarge the
  cone if the smaller mask fails.
- Scientific source commit:
  `24c80c4e1c1f182278e799b7f5de53deb65bf2f4`.
- Protocol/config: `overlap-klein-v1`, exact field `Q(sqrt(2))`; independent
  `workers=1` smoke followed by `workers=14` production for each mask; spawn
  process start; `OMP_NUM_THREADS=MKL_NUM_THREADS=OPENBLAS_NUM_THREADS=1`.
- Host role and resources: WSL scientific worker, Linux
  `4.4.0-26100-Microsoft`, Python `3.11.15`, Intel Core i9-11900K, 16 logical
  CPUs and 31 GiB RAM. Production used 14 processes and retained two logical
  CPUs. The 64-CPU worker was intentionally not used because these were the
  same scientific cells, not an independent verification request.
- Package versions: oracle `0.1.0`, NumPy `2.4.6`, SciPy `1.17.1`, SymPy
  `1.14.0`.

Commands, run from `tracks/qmc/solutions/no-negative-vibes`:

```text
SOURCE_COMMIT=24c80c4e1c1f182278e799b7f5de53deb65bf2f4
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=. python -m oracle.overlap_klein --family number-conserving --mask rings-bridges --workers 1 --source-commit $SOURCE_COMMIT --output ../../results/no-negative-vibes/overlap-klein-v1/R01-E001-smoke-rings-bridges-attempt-01.json
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=. python -m oracle.overlap_klein --family number-conserving --mask rings-diagonals-bridges --workers 1 --source-commit $SOURCE_COMMIT --output ../../results/no-negative-vibes/overlap-klein-v1/R01-E001-smoke-rings-diagonals-bridges-attempt-01.json
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=. python -m oracle.overlap_klein --family number-conserving --mask rings-bridges --workers 14 --source-commit $SOURCE_COMMIT --output ../../results/no-negative-vibes/overlap-klein-v1/R01-E001-rings-bridges-attempt-01.json
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=. python -m oracle.overlap_klein --family number-conserving --mask rings-diagonals-bridges --workers 14 --source-commit $SOURCE_COMMIT --output ../../results/no-negative-vibes/overlap-klein-v1/R01-E001-rings-diagonals-bridges-attempt-01.json
```

Every scientific runner attempt in this experiment succeeded and produced a
new attempt-numbered JSON:

| Role / mask | Workers | Wall (s) | Raw path | SHA-256 |
|---|---:|---:|---|---|
| smoke / `rings-bridges` | 1 | 34.5008 | `tracks/qmc/results/no-negative-vibes/overlap-klein-v1/R01-E001-smoke-rings-bridges-attempt-01.json` | `42ce1da95f7cdf4f3c9b7339001518265aa619ef1b654975ae03cdf932804da1` |
| smoke / `rings-diagonals-bridges` | 1 | 59.9634 | `tracks/qmc/results/no-negative-vibes/overlap-klein-v1/R01-E001-smoke-rings-diagonals-bridges-attempt-01.json` | `777d4ea88fb1ae4c83b20017b17e15aefeab1d8dd38650ebcc6d23f154ad0129` |
| production / `rings-bridges` | 14 | 29.2986 | `tracks/qmc/results/no-negative-vibes/overlap-klein-v1/R01-E001-rings-bridges-attempt-01.json` | `5317ca436b30bd734ad917cfe32c2c74b3436cb9f5b6165eb80dc14637a2859d` |
| production / `rings-diagonals-bridges` | 14 | 46.0726 | `tracks/qmc/results/no-negative-vibes/overlap-klein-v1/R01-E001-rings-diagonals-bridges-attempt-01.json` | `37d175bb701c573fdba433614765fe58302ee37f764393824c89cd38ebb68e36` |

For each mask, the complete smoke and production scientific payloads are
equal after removing only the top-level `execution` object. All eight
production exact certificates and all eight smoke exact certificates replayed
against the independently rebuilt exact system; no solver branch reported
`status="error"`.

### Exact classifications

`rings-bridges` has system shape `560 x 24`. Its compact certificate pointers
are under
`fixtures/overlap_klein_r01.json#/experiments/0/cells/0/anchors`:

| Directed bridge anchor | `+1` survives? / status | `-1` survives? / status | Classification | Exact certificate |
|---|---|---|---|---|
| `h0<-4` | no / `infeasible` | no / `infeasible` | `certified-zero` | `/experiments/0/cells/0/anchors/0/zero_certificate` |
| `h1<-5` | no / `infeasible` | no / `infeasible` | `certified-zero` | `/experiments/0/cells/0/anchors/1/zero_certificate` |
| `h4<-0` | no / `infeasible` | no / `infeasible` | `certified-zero` | `/experiments/0/cells/0/anchors/2/zero_certificate` |
| `h5<-1` | no / `infeasible` | no / `infeasible` | `certified-zero` | `/experiments/0/cells/0/anchors/3/zero_certificate` |

`rings-diagonals-bridges` has system shape `748 x 32`. Its compact certificate
pointers are under
`fixtures/overlap_klein_r01.json#/experiments/0/cells/1/anchors`:

| Directed bridge anchor | `+1` survives? / status | `-1` survives? / status | Classification | Exact certificate |
|---|---|---|---|---|
| `h0<-4` | no / `infeasible` | no / `infeasible` | `certified-zero` | `/experiments/0/cells/1/anchors/0/zero_certificate` |
| `h1<-5` | no / `infeasible` | no / `infeasible` | `certified-zero` | `/experiments/0/cells/1/anchors/1/zero_certificate` |
| `h4<-0` | no / `infeasible` | no / `infeasible` | `certified-zero` | `/experiments/0/cells/1/anchors/2/zero_certificate` |
| `h5<-1` | no / `infeasible` | no / `infeasible` | `certified-zero` | `/experiments/0/cells/1/anchors/3/zero_certificate` |

For every row above, the committed certificate supplies nonnegative exact
weights with `C^T y_+ = e_a` and `C^T y_- = -e_a`. Therefore every
`x` satisfying the fixed exact Metzler inequalities `C x >= 0` obeys both
`x_a >= 0` and `x_a <= 0`, hence `x_a = 0`. This proves that all four
directed cross-cluster hopping coordinates vanish throughout each of the two
fixed number-conserving cones. In particular, a nonzero Hermitian bridge
hopping cannot be assembled inside either cone.

- Interpretation: the preregistered prediction failed, but it failed
  rigorously. Adding all four allowed diagonal edges enlarged the basis from
  24 to 32 coordinates and the constraint system from 560 to 748 rows without
  rescuing any directed bridge hopping.
- Scope: this no-go is only for the fixed six-mode transform, the stated
  number-conserving quadratic families, and the two stated support masks. It
  does not exclude a larger BdG cone, Gaussian micro-words, another transform,
  an open cone elsewhere, or a positive-coefficient physical HS
  decomposition. It is not a no-go theorem for the full `R01` program or for
  arbitrary physical Hamiltonians.
- Committed evidence:
  `fixtures/overlap_klein_r01.json#/experiments/0` contains the original two
  E001 cells, raw hashes, execution provenance, sign-local statuses, and
  replayable exact certificates inside fixture schema v2. The compact branch
  schema deliberately renames raw
  `exact_primal_certificate` to `certificate`; zero certificates retain the
  raw `zero_certificate` name.
- Transferable lesson: a two-sided exact Farkas pair proves a cone coordinate
  is identically zero, whereas a one-sided numerical `infeasible` status only
  says that sign had no numerical primal in that run. Never upgrade the latter
  to an exact exclusion.
- Decision / next experiment: run Task 8 on the BdG expansion, testing whether
  pairing terms rescue a hopping bridge or produce a certified `pc`/`pa`
  bridge coordinate. Keep the two masks as distinct cells and allocate them
  disjointly across the authorized workers after matching one-worker smokes.

## R01-E002 — BdG six-mode bridge gate

- Proposal ID: `R01`
- Question: For the same fixed overlapping Klein circuit
  `U = U_[2,3,4,5] U_[0,1,2,3]`, does enlarging the real quadratic basis from
  number-conserving hopping to BdG hopping plus pair creation and pair
  annihilation permit any nonzero cross-cluster bridge coordinate?
- Prediction: at least one bridge coordinate and sign survives exactly after
  pairing terms are admitted, leaving a candidate cross-cluster BdG cone for
  a later common-element/noncommutativity test.
- Scientific source commit:
  `d42786ae8a47899c90ac4811424c66aad2910713`.
- Frozen-source evidence: complete bundle
  `r01-task8-source-d42786a.bundle`, SHA-256
  `6bce3dbe9609c234879d2eeeceb4a4a5ad64ac1f82ed49af3f14a6d0edcd4838`.
  The local, WSL-worker, and CPU-worker clones were clean at the same full SHA
  before any runner started.
- Protocol/config: `overlap-klein-v1`, raw schema v1, exact field
  `Q(sqrt(2))`; one matching `workers=1` smoke per assigned cell; production
  only after both smokes had no error branches and every certificate replayed;
  spawn process start; `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, and
  `OPENBLAS_NUM_THREADS` each set to `1`.
- Package versions on both scientific hosts: oracle `0.1.0`, NumPy `2.4.6`,
  SciPy `1.17.1`, SymPy `1.14.0`.

Public host assignment and readiness:

| Host role | Assigned cell | OS | Logical CPUs / production workers | RAM (bytes) | Python | Scheduler |
|---|---|---|---:|---:|---|---|
| WSL worker | `bdg/rings-bridges` | `Linux 4.4.0-26100-Microsoft x86_64` | 16 / 14 | 34113646592 | 3.11.15 | plain SSH |
| CPU worker | `bdg/rings-diagonals-bridges` | `Linux 6.8.0-111-generic x86_64` | 64 / 62 | 540659666944 | 3.11.15 | plain SSH through the authenticated gateway |

Each command ran from its assigned solution directory with that host's
dedicated Python:

```text
SOURCE_COMMIT=d42786ae8a47899c90ac4811424c66aad2910713
SOLUTION=<assigned absolute solution directory>
PYTHON=<assigned dedicated interpreter>
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH="$SOLUTION" "$PYTHON" -m oracle.overlap_klein --family bdg --mask rings-bridges --workers 1 --source-commit "$SOURCE_COMMIT" --output ../../results/no-negative-vibes/overlap-klein-v1/R01-E002-smoke-rings-bridges-attempt-01.json
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH="$SOLUTION" "$PYTHON" -m oracle.overlap_klein --family bdg --mask rings-diagonals-bridges --workers 1 --source-commit "$SOURCE_COMMIT" --output ../../results/no-negative-vibes/overlap-klein-v1/R01-E002-smoke-rings-diagonals-bridges-attempt-01.json
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH="$SOLUTION" "$PYTHON" -m oracle.overlap_klein --family bdg --mask rings-bridges --workers 14 --source-commit "$SOURCE_COMMIT" --output ../../results/no-negative-vibes/overlap-klein-v1/R01-E002-rings-bridges-attempt-01.json
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH="$SOLUTION" "$PYTHON" -m oracle.overlap_klein --family bdg --mask rings-diagonals-bridges --workers 62 --source-commit "$SOURCE_COMMIT" --output ../../results/no-negative-vibes/overlap-klein-v1/R01-E002-rings-diagonals-bridges-attempt-01.json
```

### Attempt ledger

All scientific runner attempts succeeded. The failed rows below are
operational or test-authoring attempts; none started an extra scientific cell
or changed an existing raw.

| Attempt | Kind | Result and preserved evidence |
|---|---|---|
| source sync | operation | PASS: the complete source bundle was verified, both isolated worker clones fast-forwarded to the pinned full SHA, and both worktrees checked clean. |
| readiness probe 1 | operation | FAIL before Python: a combined nested-SSH `python -c` probe lost its quoting. No runner and no raw. |
| readiness probe 2 | operation | PASS: simple argv-only probes verified BatchMode authentication, public resources, versions, schedulers, clean trees, and exact source identities. |
| local WSL preflight | operation | FAIL before remote access: this Codex host has no local WSL, so the already-authorized Windows gateway route was used. No runner and no raw. |
| attempt-path preflight | operation | WSL PASS with no E002 raw; CPU `find` exited 1 because its results directory did not yet exist. All four `attempt-01` names remained unused. |
| helper egress | operation | DENIED locally before transfer by the execution sandbox; the controller performed the already-authorized remote work. No remote change, runner, or raw. |
| smoke / `rings-bridges` | science | PASS, WSL worker, `workers=1`; raw and hash are in the table below. |
| smoke / `rings-diagonals-bridges` | science | PASS, CPU worker, `workers=1`; raw and hash are in the table below. |
| smoke validator 1 | operation | FAIL before certificate replay: helper assumed BLAS-thread values were integers rather than strings. Both raws and hashes unchanged. |
| smoke validator 2 | operation | FAIL before certificate replay: helper looked for `system.shape` instead of `system.system_shape`. Both raws and hashes unchanged. |
| schema probe 1 | operation | FAIL before JSON inspection with `ModuleNotFoundError: oracle` because the probe omitted the absolute solution `PYTHONPATH`. Raws unchanged. |
| smoke validator 3 | operation | WSL PASS; CPU outer control timed out with exit 124 while its read-only replay PID remained active. The PID was allowed to finish and confirmed absent before retry; this was not a certificate verdict. |
| smoke validator 4 | operation | PASS: CPU replay reran with a longer timeout. Both smokes then had complete terminal/non-error and exact-certificate gates. |
| production / `rings-bridges` | science | PASS, WSL worker, `workers=14`; raw and hash are in the table below. |
| production / `rings-diagonals-bridges` | science | PASS, CPU worker, `workers=62`; raw and hash are in the table below. |
| production validation | operation | PASS on both hosts: all certificates replayed and each smoke/production pair had equal complete payloads after deleting only top-level `execution`. |
| raw return | operation | PASS: the CPU pair moved to WSL, then all four files moved through the gateway to the local ignored tree using unique `.part`, SHA-256 verification at every hop, and atomic rename. |
| RED attempt 1 | test authoring | INVALID: pytest collected zero tests because of an `IndentationError` in the new test. Only test indentation changed afterward. |
| RED attempt 2 | test authoring | VALID RED: WSL exit 1, `1 failed in 0.66s`; schema v1 reported actual `1` against required fixture schema `2`. |
| GREEN monitor 1 | operation | A read-only `pgrep` pattern containing spaces was split by the remote shell and exited 1; argv-only `pgrep -af pytest` then confirmed the unaffected pytest process. |
| GREEN migration replay | verification | PASS: WSL exit 0, `4 passed in 437.84s`; schema/order, exact raw provenance, all compact certificates, anchor kinds, and the number-conserving inclusion guard passed. |

The four scientific raws:

| Host / role / mask | Workers | Raw wall (s) | Raw path | SHA-256 |
|---|---:|---:|---|---|
| WSL / smoke / `rings-bridges` | 1 | 197.2485009000011 | `tracks/qmc/results/no-negative-vibes/overlap-klein-v1/R01-E002-smoke-rings-bridges-attempt-01.json` | `e86f5e96a879f1deaab8ad4aac38d8e66aa8bf23807060b53aee14c215729788` |
| CPU / smoke / `rings-diagonals-bridges` | 1 | 563.7972104456276 | `tracks/qmc/results/no-negative-vibes/overlap-klein-v1/R01-E002-smoke-rings-diagonals-bridges-attempt-01.json` | `dc4699c3df42720d3c4cce720124699c885d2b782ec85e9934635e5a529e8bb7` |
| WSL / production / `rings-bridges` | 14 | 137.92176029999973 | `tracks/qmc/results/no-negative-vibes/overlap-klein-v1/R01-E002-rings-bridges-attempt-01.json` | `ece5bc0595ffedba6633adf9afb0c19cfbfcbb9197e119929528b4297dbdf1c9` |
| CPU / production / `rings-diagonals-bridges` | 62 | 384.1710428921506 | `tracks/qmc/results/no-negative-vibes/overlap-klein-v1/R01-E002-rings-diagonals-bridges-attempt-01.json` | `c5e62e1cd2c8af829c7b003d36a13460a0d965360f6c9ab8af98ccec06dcc3e3` |

For each mask, smoke and production were exactly equal after removing only
the top-level `execution` object. The WSL production replay took 124.8 s and
the CPU production replay 345.0 s. Every one of the 16 production anchors and
16 smoke anchors had terminal, non-error sign branches; every embedded exact
double-dual certificate replayed. There were no `numerical-only` branches or
diagnostics to promote into a theorem.

### Exact classifications

The `rings-bridges` BdG system has shape `1052 x 42`; its pointers begin at
`fixtures/overlap_klein_r01.json#/experiments/1/cells/0/anchors`.
The `rings-diagonals-bridges` system has shape `1456 x 58`; its pointers begin
at `/experiments/1/cells/1/anchors`.

| Mask | Anchor / kind | `+1` status | `-1` status | Classification | Exact certificate pointer |
|---|---|---|---|---|---|
| `rings-bridges` | `h0<-4` / hopping | `infeasible` | `infeasible` | `certified-zero` | `/experiments/1/cells/0/anchors/0/zero_certificate` |
| `rings-bridges` | `h1<-5` / hopping | `infeasible` | `infeasible` | `certified-zero` | `/experiments/1/cells/0/anchors/1/zero_certificate` |
| `rings-bridges` | `h4<-0` / hopping | `infeasible` | `infeasible` | `certified-zero` | `/experiments/1/cells/0/anchors/2/zero_certificate` |
| `rings-bridges` | `h5<-1` / hopping | `infeasible` | `infeasible` | `certified-zero` | `/experiments/1/cells/0/anchors/3/zero_certificate` |
| `rings-bridges` | `pa0,4` / pair annihilation | `infeasible` | `infeasible` | `certified-zero` | `/experiments/1/cells/0/anchors/4/zero_certificate` |
| `rings-bridges` | `pa1,5` / pair annihilation | `infeasible` | `infeasible` | `certified-zero` | `/experiments/1/cells/0/anchors/5/zero_certificate` |
| `rings-bridges` | `pc0,4` / pair creation | `infeasible` | `infeasible` | `certified-zero` | `/experiments/1/cells/0/anchors/6/zero_certificate` |
| `rings-bridges` | `pc1,5` / pair creation | `infeasible` | `infeasible` | `certified-zero` | `/experiments/1/cells/0/anchors/7/zero_certificate` |
| `rings-diagonals-bridges` | `h0<-4` / hopping | `infeasible` | `infeasible` | `certified-zero` | `/experiments/1/cells/1/anchors/0/zero_certificate` |
| `rings-diagonals-bridges` | `h1<-5` / hopping | `infeasible` | `infeasible` | `certified-zero` | `/experiments/1/cells/1/anchors/1/zero_certificate` |
| `rings-diagonals-bridges` | `h4<-0` / hopping | `infeasible` | `infeasible` | `certified-zero` | `/experiments/1/cells/1/anchors/2/zero_certificate` |
| `rings-diagonals-bridges` | `h5<-1` / hopping | `infeasible` | `infeasible` | `certified-zero` | `/experiments/1/cells/1/anchors/3/zero_certificate` |
| `rings-diagonals-bridges` | `pa0,4` / pair annihilation | `infeasible` | `infeasible` | `certified-zero` | `/experiments/1/cells/1/anchors/4/zero_certificate` |
| `rings-diagonals-bridges` | `pa1,5` / pair annihilation | `infeasible` | `infeasible` | `certified-zero` | `/experiments/1/cells/1/anchors/5/zero_certificate` |
| `rings-diagonals-bridges` | `pc0,4` / pair creation | `infeasible` | `infeasible` | `certified-zero` | `/experiments/1/cells/1/anchors/6/zero_certificate` |
| `rings-diagonals-bridges` | `pc1,5` / pair creation | `infeasible` | `infeasible` | `certified-zero` | `/experiments/1/cells/1/anchors/7/zero_certificate` |

For every row, nonnegative exact weights satisfy
`C^T y_+ = e_a` and `C^T y_- = -e_a`. Thus every listed hopping,
pair-annihilation, and pair-creation coordinate is identically zero throughout
its fixed BdG cone.

The exact inclusion from the number-conserving cone into the BdG cone sets all
pairing coefficients to zero. Consequently, a BdG hopping primal with
all-zero pairing support would contradict the E001 hopping-coordinate no-go.
No BdG hopping primal exists here, so the inclusion check is consistent. The
pairing anchors are independently zero as well.

- Interpretation: the preregistered prediction failed exactly. Both fixed BdG
  cones have a coordinate-wise directed bridge no-go: all four hopping, two
  pair-creation, and two pair-annihilation bridge coordinates vanish. Because
  there are no separate directed survivors, this also excludes a nonzero
  Hermitian hopping-adjoint or `pc=pa` bridge target in either cone; no later
  functional-anchor combination is needed for these two cells.
- Scope: this is only a theorem about the fixed six-mode transform, exact
  field, real quadratic BdG basis, and the two stated support masks. It does
  not cover another transform, another support, Gaussian micro-words, an open
  cone elsewhere, arbitrary Hamiltonians, a physical positive-coefficient HS
  decomposition, or an `N=8` construction.
- Committed evidence:
  `fixtures/overlap_klein_r01.json#/experiments/1` records both BdG cells with
  per-cell public host/package metadata, exact raw roles/hashes/worker counts,
  sign-local statuses, anchor kinds, and replayable double-dual certificates.
  Fixture schema v2 retains the full reviewed E001 experiment at
  `/experiments/0`.
- Transferable lesson: hopping, pair-creation, and pair-annihilation anchors
  are distinct directed coordinates. Separate survivors would not alone
  construct one Hermitian cone element; the hopping adjoint pair or `pc=pa`
  must be imposed in a common functional-anchor test. Here every coordinate
  is exactly zero, so that later test is unnecessary.
- Decision / next experiment: treat the two preregistered six-mode masks as a
  fixed-structure no-go and change structure rather than inventing a survivor.
  A later task may update the proposal status; this experiment does not launch
  an `N=8` scan or claim a general BdG/HS no-go.

### Candidate verification chronology

The first tracked candidate was
`8ad45535644743e3c3826ae6dbb3be21e46762a4`. Its complete bundle
`r01-task8-candidate-8ad4553.bundle` had SHA-256
`6c19183f54a5f4959fba5ed09918e43f7dfc057036553aeaf4e11d14f859223b`.
The hash matched at the local, gateway, WSL, and CPU stages; both workers
verified complete bundle history, fast-forwarded to the exact full SHA, and
were clean before tests.

| Attempt | Result |
|---|---|
| candidate verification 1 | INVALID/no verdict: both long-lived outer SSH controls reset at about 300 s after printing only partial pytest dots. The WSL and CPU pytest processes remained active; they were not duplicated and were allowed to exit naturally. |
| candidate monitor poll 1 | FAIL in the poll only: a combined nested `bash -lc` command lost quoting and raised a shell syntax error. No pytest process or candidate state changed. |
| candidate verification 2 / WSL focused | PASS through a detached fail-closed wrapper with unique atomic log/status artifacts: `71 passed in 538.41s (0:08:58)`. |
| candidate verification 2 / CPU fixture | PASS through the same wrapper protocol: the five committed schema/provenance/replay/inclusion tests reported `5 passed in 690.35s (0:11:30)`. |
| candidate verification 2 / WSL full | PASS through the same wrapper protocol: `351 passed, 1003 warnings in 542.14s (0:09:02)`. The warnings were the known mpmath bit-count deprecations from exact fixtures (101), Majorana exact tests (278), and Metzler-system tests (624). |

The tracked documentation update that records this chronology is a later
docs-only commit. Its exact SHA and any final bundle/replay evidence belong in
the Task 8 implementation report so the commit does not claim to contain its
own hash.

### Review-fix candidate gate

Final review found that the tracked fixture test trusted the recorded
`scientific_payload_equal_after_removing_only_top_level_execution` boolean
without independently opening the ignored raws. The review fix adds a
separate candidate gate; the ordinary suite remains hermetic and uses only
synthetic `tmp_path` raw pairs.

| Attempt | Result |
|---|---|
| candidate-gate RED 1 | VALID RED at `1fc9342`: the five happy/hash/execution/scientific/CLI nodes exited 1 with `5 failed in 0.74s`, each solely because `oracle.r01_evidence` was absent. |
| exact-inclusion characterization | PASS before production changes: both support masks passed the exact ordered BdG-to-number-conserving row/column restriction, `2 passed in 19.20s`. This was characterization evidence, not RED. |
| candidate-gate RED 2 | VALID RED before the implementation was restored: the four containment/missing-file/role/incomplete-provenance nodes exited 1 with `4 failed in 0.69s`, each at the missing validator assertion. The expanded contract was committed at `b049bed`. |
| candidate-gate GREEN 1 | PASS: the original five nodes reported `5 passed in 0.64s`. |
| candidate-gate GREEN 2 | PASS: the complete hermetic module reported `11 passed in 18.64s`. |
| real ignored-raw candidate gate | PASS: all eight local raw files were required, contained, byte-hashed, provenance-matched, and paired; stdout was `validated R01 evidence: experiments=2 cells=4 raw_results=8`. |
| independent local raw check | PASS: a read-only PowerShell hash/execution/payload comparison reported `powershell-independent-gate raw_results=8`. |

The WSL commands, run from
`tracks/qmc/solutions/no-negative-vibes`, were:

```text
pytest -q tests/test_r01_evidence.py::test_raw_evidence_validator_accepts_a_complete_matching_pair tests/test_r01_evidence.py::test_raw_evidence_cli_accepts_explicit_repository_and_fixture_paths tests/test_r01_evidence.py::test_raw_evidence_validator_recomputes_each_raw_sha256 tests/test_r01_evidence.py::test_raw_evidence_validator_requires_exact_execution_provenance tests/test_r01_evidence.py::test_raw_evidence_validator_compares_payloads_after_only_execution_removal

pytest -q tests/test_r01_evidence.py::test_raw_evidence_validator_rejects_a_raw_path_outside_repository_root tests/test_r01_evidence.py::test_raw_evidence_validator_requires_every_referenced_raw_file tests/test_r01_evidence.py::test_raw_evidence_validator_requires_one_smoke_and_one_production_role tests/test_r01_evidence.py::test_raw_evidence_validator_rejects_incomplete_raw_provenance

pytest -q tests/test_r01_evidence.py::test_bdg_system_contains_number_conserving_rows_without_mixed_support

pytest -q tests/test_r01_evidence.py

python -m oracle.r01_evidence --repository-root ../../../.. --fixture fixtures/overlap_klein_r01.json
```

The validator does not accept the fixture boolean as evidence. It resolves
every referenced path within an explicit repository root, requires the file,
recomputes SHA-256 from its bytes, enforces exact raw/record/execution schemas,
checks experiment/cell/raw identity and the complete execution object, and
then deletes exactly the top-level `execution` member before deep equality.
The eight tracked `wall_time_seconds` values were restored to the exact JSON
literals in their corresponding raw files. No scientific runner was started,
no raw was changed, and the R01-E001/E002 conclusions are unchanged.

A second controller review found that raw-pair validation alone did not yet
bind the compact fixture anchors or top-level transform metadata to those
raws, and that two different path spellings could name one canonical file.
That gap was closed in a separate RED/GREEN cycle:

| Attempt | Result |
|---|---|
| fixture-binding RED | VALID RED: fixture-anchor mutation, `exact_field`, `transform`, canonical path alias, and missing raw-system key produced `FFFFF`, exit 1, `5 failed in 0.77s`. The first four did not raise; the missing `geometry` case reached only the later generic scientific-payload mismatch. |
| fixture-binding GREEN | PASS: the full expanded hermetic module reported `16 passed in 18.73s`. |
| fixture-binding real gate | PASS: exit 0 with exact stdout `validated R01 evidence: experiments=2 cells=4 raw_results=8`. |

The additional RED command was:

```text
pytest -q tests/test_r01_evidence.py::test_raw_evidence_validator_binds_fixture_anchors_to_raw_anchors tests/test_r01_evidence.py::test_raw_evidence_validator_binds_fixture_metadata_to_raw_system tests/test_r01_evidence.py::test_raw_evidence_validator_rejects_two_paths_to_the_same_raw_file tests/test_r01_evidence.py::test_raw_evidence_validator_requires_exact_raw_system_keys
```

The final validator requires exact raw-system keys, binds
`system.exact_field` and `system.transform` to fixture scope, rejects canonical
raw-path aliases, and mechanically converts the common raw anchors to the
compact fixture schema before exact comparison. The conversion adds the
derived anchor kind, retains sign statuses, maps raw
`exact_primal_certificate` to compact `certificate`, and retains the exact
zero certificate or numerical-only diagnostics as applicable.

## 2026-07-29 — Exterior exact-card Stage 1

The immutable run `exterior-thin-first-v1` screened all 2,304 exact rational
two-atom cards with the unchanged determinant oracle.  It exhaustively tested
all mixed words at depths 2, 3, and 4 (22 words for a zero-failure card) and
stopped at the first stable negative, complex, or uncertain result.

- source commit:
  `b90a506d0aaa38a87163be06b83f6de380a3e970`;
- protocol hash:
  `e7d4a3223a383687db462b582f0c675a443a620cc16f74181df5782fbd21aa43`;
- plan hash:
  `debbc510ac886ed26b7640bf0b09de5672f529c34c30aa21cdcd1e430564595a`;
- execution: WSL shards 00--13 with 14 processes and CPU shards 14--75
  with 62 processes, all BLAS thread limits one;
- terminal accounting: 2,304 terminal, zero missing, stale, duplicate, or
  unresolved operational candidates.

| N | planned | stable negative | uncertain | shallow survivor |
|---:|---:|---:|---:|---:|
| 3 | 512 | 18 | 9 | 485 |
| 4 | 1,024 | 249 | 104 | 671 |
| 5 | 512 | 111 | 17 | 384 |
| 6 | 256 | 76 | 7 | 173 |
| total | 2,304 | 454 | 137 | 1,713 |

There were zero complex classifications.  Stable failures concentrated at
depth-3 word `[0,0,1]`, with a smaller depth-4 `[0,0,0,1]` population.
Uncertain results often appeared at alternating word `[0,1,0,1]`.  The
diagonal odd-cycle template was a known control and passed 256/256; it is not
a novelty promotion.  The strongest discovery-yield templates were
`exact4-graded-shear-pair` (199 survivors, no stable negatives, 57 uncertain)
and `exact5-oddcycle-block-pair` (218 survivors, 25 stable negatives,
13 uncertain).

Interpretation: Stage 1 was an efficient falsifier but not a theorem.  The
1,713 zero-failure cards are only finite-depth survivors, while all 137
uncertain cards require exact-card high-precision replay and cannot be counted
as survivors.  The transferable lesson is to preserve exact candidate
identity and widen word depth before spending on random histories: the
complete depth-5..8 mixed-word tranche costs only 808,536 classifications and
fits one 76-process pass.

Decision: freeze `exterior-survivor-pressure-v1`, select exactly the 1,713
parent survivors, enumerate all mixed words at depths `[5,6,7,8]`, and retain
the same first-failure early stop.  Run the 137 uncertain candidates in a
disjoint high-precision replay queue.  In parallel, prioritize exact
shared-exterior-cone search for the graded-shear and odd-cycle-block survivor
families; exact certificates promote immediately, while finite-depth survival
never supports an arbitrary-depth claim.

## 2026-07-29 — Task 9 exact R01 classifier

### Plan amendment and RED

- Task 9 base:
  `408266c3c85bc8466683364f545a16e0d79559f0`.
- The branch-gated classifier plan was independently reviewed. Three
  Important defects were corrected before implementation: incomplete RED
  ordering, missing exact `N`/`F` output schemas, and a self-invalidating
  tracked-log/final-verification cycle. The final amendment was committed and
  shared as
  `6a608c10e078802e36639a4c3ace8a12694e9ed4`.
- Local Windows RED probe: no pytest process started because `python` was not
  installed on the outer client. This is an environment/operational attempt,
  not a scientific or test verdict.
- First combined gateway/WSL preflight: INVALID/no scientific verdict. Remote
  PowerShell pipeline quoting made `ForEach-Object` reach `cmd.exe`, and a
  shell-composed WSL `git -C` probe lost its command boundary. No repository
  or test state changed. The retry used one argv-only command per probe and
  confirmed WSL at clean `408266c`.
- Synchronization: a complete bundle for the plan commit had SHA-256
  `f19b213e983ddfe0114e9a3c3c18ed7e15f50d9852c910f87a598ba32d6df7c8`.
  The local and WSL hashes matched, bundle fetch/fast-forward put the WSL
  clone at exact `6a608c10e078802e36639a4c3ace8a12694e9ed4`, and the only dirty
  tracked file was the transferred RED test module. Its end-to-end SHA-256
  was
  `49fd85247ab7f65bf95453698f4fbd1584e4f9ca28132c8da87e24a70078ee0b`.
- RED command, using Python 3.11 with `PYTHONPATH` equal to the absolute
  solution directory and all three BLAS limits set to one:

  ```text
  python -m pytest tests/test_overlap_klein.py -q
  ```

- RED result: VALID, exit `1`, `1 error in 0.83s`. Collection failed only at
  `from oracle.overlap_klein import classify_r01_fixture` because that public
  interface did not yet exist. This is the preregistered failure for the
  complete happy-path, fail-closed mutation, non-mutation, incomplete,
  primal/dual corruption, and four-build/24-parse call-count test surface.
- Interpretation: implementation may now add only the fixture classifier and
  private helpers. It must not weaken the structural failures, implement
  survivor-only audits, or interpret any exact dual as a primal ray.

## 2026-07-29 — Exterior survivor pressure Stage 2

The immutable run `exterior-survivor-pressure-v1` selected exactly the 1,713
zero-failure Stage-1 manifests and exhaustively tested all 472 mixed two-atom
words at depths 5, 6, 7, and 8, with first-failure early stopping.

- source commit:
  `c4919c411881ab680b8655c4cedb50dbe7d75fc5`;
- bundle SHA-256:
  `a2d7b34b9d2c15b04d9240d7ed7fcca38620b56f24bb081171e2e894dea04189`;
- parent plan hash:
  `debbc510ac886ed26b7640bf0b09de5672f529c34c30aa21cdcd1e430564595a`;
- plan hash:
  `17191af2702ab5dfcfd272fd4a436604a75ad4d56ecb73b58fd39c6f9475347a`;
- protocol hash:
  `29c578cd44f453fa27855bc22406968d5435585b7d01f3bf5d07c4f7df63e880`;
- execution: four smoke candidates passed, then WSL shards 00--13 used
  14 processes and CPU shards 14--75 used 62 processes, all BLAS limits one;
- accounting: 1,713 terminal, zero missing, stale, duplicate, operational
  errors, or unresolved candidates; 553,261 word products were actually
  evaluated after early stopping.

| N | planned | stable negative | uncertain | depth-8 survivor |
|---:|---:|---:|---:|---:|
| 3 | 485 | 8 | 89 | 388 |
| 4 | 671 | 43 | 244 | 384 |
| 5 | 384 | 74 | 119 | 191 |
| 6 | 173 | 23 | 62 | 88 |
| total | 1,713 | 148 | 514 | 1,051 |

The pressure pass removed 148 apparent Stage-1 survivors with stable negative
weights. The strongest numerical control was
`exact3-diagonal-oddcycle-pair`: 235 of 256 survived and the remaining 21
were conditioning-limited rather than stable negative. The most promising
non-control counts after depth 8 were `exact3-oddcycle-shear-pair` 153,
`exact4-block-shear-pair` 114, `exact4-shear-loop-pair` 100,
`exact4-graded-shear-pair` 98, `exact5-shear-loop-pair` 98,
`exact5-oddcycle-block-pair` 93, and `exact6-graded-shear-pair` 88.

Interpretation: the Stage-2 scan is a successful high-throughput falsifier,
not an arbitrary-depth certificate. The 1,051 survivors advance to depths
9--12. The 514 conditioning-limited first failures form a disjoint
high-precision replay queue; none is counted as positive or negative before
replay. The full result Markdown and plan summary are preserved in the local
SDD evidence directory with SHA-256 values
`2949219bf76965a83c7711982bf6afa1310c7c13832377fd9a417e2927ed77f1`
and
`2d55df696df3317d92778d2d7bbc22e135a23d4d8a1771e66de9bec5065cadcb`.

Transferable execution lesson: for this oracle, elaborate distributed
infrastructure costs more than the science. One immutable plan, independent
candidate directories, deterministic shard ownership, thread-limited
processes, and a final merge completed the 76-shard pass in seconds. Future
screening rounds should retain only the smoke gate, exact source/plan hashes,
first-failure evidence, and final terminal accounting.

### Hamiltonian reverse-construction scope amendment

Once a new sign-free matrix semigroup or cone is certified, reverse
construction may target any Hermitian Hamiltonian, including a nonlocal one.
Locality is no longer a promotion prerequisite. A second research branch may
then ask whether a similarity transform maps that nonlocal Hermitian model to
a local non-Hermitian Hamiltonian with real spectrum. This enlarges the
constructive search space without weakening the required Hermiticity of the
primary Hamiltonian or the positivity of the auxiliary-field weights.

## 2026-07-29 — Stage-2 high-precision first-failure replay

The 514 Stage-2 `uncertain-high-precision` first-failure words were replayed
from exact rational cards with an 80/120/180 precision ladder, conditional
260-digit escalation, and exact rational determinant adjudication.

- source commit:
  `216e1bb8185ef17193f8c29ee924b16793b8cfed`;
- run id:
  `exterior-survivor-pressure-v1-high-precision-v1`;
- replay plan hash:
  `43c137244b5ae67d5d35240def5166d056e78a3c053665db7493e0a53bd6656c`;
- WSL workers 0--13 and CPU workers 14--75, one BLAS thread each;
- terminal 514/514, zero missing or stale.

| adjudication | count |
|---|---:|
| confirmed nonnegative | 511 |
| confirmed negative | 3 |
| unresolved high precision | 0 |

Interpretation: the conditioning gate was conservative and correctly avoided
false numerical claims. The 511 confirmed-nonnegative records prove only the
sign of the first word that stopped the Stage-2 float scan; they are not yet
depth-8 survivors because the remaining words were never visited. They enter
a separate exact-fallback continuation over the full depth-5--8 tranche. The
three exact negatives are terminal rejections.

Local evidence SHA-256:

- replay plan:
  `55671ca5181a6dc09dfc229658b43d98377b54342b0761df6d07c31d4e7a01da`;
- compact summary:
  `bdc6c107729660315324b56756fff7c33444d88f3da7f66febbed7ced5ceb53a`;
- CPU candidate archive:
  `e83e34a44fa7771ca49952d7fad8465f9d980c2a4a7c97aeb046e9f7a68d5326`.

## 2026-07-29 — Exterior survivor depth-12 Stage 3

The 1,051 candidates that had completed every Stage-2 word without a failure
were screened over every mixed two-atom word at depths 9, 10, 11, and 12.
There are 7,672 words per complete candidate and 8,063,272 possible
classifications before early stopping.

- source commit:
  `30f6df97bb0f9152ddd615e977d713e23b284c59`;
- run id:
  `exterior-survivor-depth12-v1`;
- protocol hash:
  `3f6a44131b03c58e5e3006bff678e41c7b59e35676c4324606e657543aa4ce26`;
- parent protocol hash:
  `29c578cd44f453fa27855bc22406968d5435585b7d01f3bf5d07c4f7df63e880`;
- WSL workers 0--13 and CPU workers 14--75, one BLAS thread each;
- 1,051/1,051 terminal, zero missing or stale, 5,830,398 words actually
  evaluated after early stopping.

| status | count |
|---|---:|
| stable negative | 52 |
| uncertain, exact replay required | 307 |
| depth-12 zero-failure survivor | 692 |

The 692 zero-failure cards advance to a deeper word tranche and exact
shared-cone/certificate search. The 307 uncertain first failures enter a
disjoint high-precision replay; they are not survivors. Local evidence
SHA-256 is
`5b41795ca29e84ab5bad4ec326ce10d29de6501a6736897817e1ee8a0a0cc8d1`
for the Markdown summary and
`eaf062df9f8b3dee430b5bdd4ef96da06955c8e611e23ddce3cfb715a065dd05`
for the complete JSON summary.

Transferable scientific lesson: alternating and near-alternating long words
dominate the conditioning-limited queue, while stable negatives still appear
as late as depth 12. Finite survival must therefore be paired with exact cone
structure; simply extending random histories is less informative than
exhaustive mixed-word tranches plus exact replay.

## 2026-07-29 — Depth-8 exact-fallback continuation

The 511 candidates whose original Stage-2 stopping word was exactly confirmed
nonnegative were restarted over the complete 472-word depth-5--8 tranche.
Well-conditioned words used the frozen determinant classifier; every
conditioning-limited word used the 80/120/180/260 ladder and exact rational
determinant adjudication.

- source commit:
  `859347d4e1c2550b05626b44bbf49ec5a6892a86`;
- run id:
  `exterior-depth8-exact-fallback-v1`;
- continuation plan hash:
  `9ac22a1b7e7cbcf376f777906f0f89c9ecdd232886b33456c850a8b84f89eaff`;
- parent high-precision plan hash:
  `43c137244b5ae67d5d35240def5166d056e78a3c053665db7493e0a53bd6656c`;
- 511/511 terminal, zero missing or stale;
- 232,551 tested words and 114,666 exact fallbacks.

| result | count |
|---|---:|
| exact-fallback negative | 13 |
| stable negative | 10 |
| depth-8 exact-fallback survivor | 488 |

The continuation demonstrates why first-failure replay alone is insufficient:
23 additional negatives appeared later in the same finite tranche. The 488
complete survivors now form a second, disjoint depth-9--12 queue using the
same exact-aware fallback. Together with the 1,051 ordinary Stage-2
survivors, the fully adjudicated depth-8 survivor population is 1,539.

Local evidence SHA-256:

- Markdown summary:
  `2acd155f16b1d660979462dd667094a61a36ce5dc897c6ff2a2b1816e9c16ca7`;
- collection JSON:
  `4afe95c7838b449391c8693b60bf75bbfe3caf1bf8a6224bcdaf9fa73e7c7a01`;
- CPU result archive:
  `2414c52b466d2345376fef7211c79bc58db6a3a032d31eb3689ca696f041e52b`.

## 2026-07-29 — Stage-3 high-precision first-failure replay

All 307 conditioning-limited first failures from the ordinary depth-9--12
scan were reconstructed from their exact cards and replayed with the same
precision ladder and exact rational determinant adjudication.

- source commit:
  `070cca4a6757a5aef7d275da7e99eb6f15aa9afe`;
- run id:
  `exterior-survivor-depth12-high-precision-v1`;
- replay plan hash:
  `173b2f436cdecf1827c14165a23a6c6ed5e234da6415dd172c5c1dea399f5a56`;
- 307/307 terminal, zero missing or stale;
- 307 confirmed nonnegative, zero confirmed negative, zero unresolved.

As in the earlier replay, these verdicts apply to the saved stopping word,
not to the unvisited suffix of the complete depth-9--12 tranche. All 307
records therefore enter an exact-aware continuation rather than the survivor
set. Local evidence SHA-256:

- summary:
  `1ffc24ccb18739853b08d82f7d77e1a8c605153b81a8f9c6b3b554449ab50255`;
- replay plan:
  `dc805c266cbc96e76fea76042a27695c7fb09b8b184bfd41553f47fa7cd066f0`;
- CPU candidate archive:
  `429b58ebd3175d76905e0d71d744bd9c662e52da8153c97c2bede8726a0b65ef`.

## 2026-07-29 — Ordinary-survivor depth-16 Stage 4

The 692 ordinary candidates that completed every depth-9--12 word without a
failure were screened exhaustively over mixed two-atom words at depths 13,
14, 15, and 16. The tranche contains 122,872 words per complete candidate;
85,027,424 classifications were possible before early stopping.

- source commit:
  `77acaf21e28d55979682257b69102e1408dda972`;
- run id:
  `exterior-survivor-depth16-v1`;
- WSL workers 0--13 and CPU workers 14--75, one BLAS thread each;
- 692/692 terminal, zero missing or stale;
- 64,617,517 words actually evaluated after early stopping.

| status | count |
|---|---:|
| stable negative | 22 |
| uncertain, high-precision replay required | 179 |
| depth-16 zero-failure survivor | 491 |

The 491 zero-failure cards advance immediately to structural certificate and
targeted deeper-survivor tests. The 179 uncertain first failures enter a
separate exact high-precision replay and are not counted as survivors.

Local evidence SHA-256:

- Markdown summary:
  `770d803cdf149fc178fef77a1aba4f0646e00c4a24a25f1bc1b10bcb8b22394c`;
- JSON summary:
  `0c60fad79565e5b96cb9f1b9ddec32b5aaea94412bd1556aeb890b1f7e40ba53`;
- CPU result archive:
  `4939df58d81fcb1543d48d9a5e826f04cf684693d23e85d11f4cf9bb9c39adac`.

Transferable lesson: exhaustive finite-word pressure remains productive at
depth 16—22 stable counterexamples appeared after depth 12—but the survivor
fraction remains large. The next high-value step is not a blind universal
depth increase: replay the 179 conditioning-limited words, then rank the 491
survivors by exact structural obstructions and concentrate deeper tests on
the trace-clean, non-control subset.

## 2026-07-29 — Exact structural triage of the 491 depth-16 survivors

The complete Stage-4 survivor population was reconstructed from exact cards
and ranked with three inexpensive exact gates: sector traces for all mixed
words through depth 4, a shared signed-gauge/all-minors induced-TN check, and
the existing odd-monomial control reduction.

- source commit:
  `427c52df5590ba0be9e61f586d037ac4ee8b3f8b`;
- input survivors: 491;
- output:
  `/home/zibojin/runs/exterior-structural-rank-427c52d/ranking.json`;
- output SHA-256:
  `325a5b03cc1d844946a163a223384987a66834dd2e9c8eb305305aa3b0bf8762`.

| priority class | count |
|---|---:|
| exact5 trace-clean non-control | 6 |
| other trace-clean non-control | 165 |
| known control reduction | 178 |
| sector-trace obstructed | 142 |

The six highest-priority cards are all
`exact5-oddcycle-block-pair`, at seeds
`61, 97, 100, 124, 211, 244`. Each is a depth-16 survivor, has no exact
control reduction in the fast library, and has 96 exact sector traces over
24 mixed words nonnegative through depth 4. The
`exact5-shear-loop-pair` seed 61 is an additional trace-clean non-control
depth-16 survivor in the second priority tier. These seven cards now receive
the grade-2/3 shared exact-cone search; the 320 obstruction/control cards do
not consume deeper theorem-search resources.

Transferable lesson: a cheap exact structure gate reduced the first theorem
search from 491 cards to six primary and one secondary target without
proving no-go results for every rejected family.

## 2026-07-29 — Exact Hermitian inverse HS construction

Every transpose-paired exact card now has a closed physical reverse map. For
a real atom `B`, its transpose partner, and a shared rational `q > 0`, define
on complete number-conserving Fock space

`H_B = -q [Gamma(B) + Gamma(B^T)]`.

Because exterior powers commute with transposition, `H_B` is exactly real
Hermitian, although generally nonlocal and up to `N`-body. Moreover,
`-H_B` is the sum of two positive-coefficient Gaussian/CT-HS branches. For
each ordered auxiliary history,

`Tr_Fock Gamma(B_s1 ... B_sL) = det(I + B_s1 ... B_sL)`,

so the production determinant oracle is exactly the CT expansion weight of
this Hamiltonian rather than an unrelated matrix proxy.

- source commit:
  `78bc5116a6f6b11c3b0c71df251198218c66486f`;
- focused exact tests: 2 passed;
- all eleven original exact5 trace-clean oddcycle seeds pass Hermiticity and
  positive-branch reconstruction;
- seed 13 passes the exact determinant/Taylor identity for orders 0--4.

This closes the Hermitian-Hamiltonian and positive-auxiliary-coefficient
parts of the challenge for any eventual card certificate. It deliberately
does not claim arbitrary-order nonnegativity: one all-grade shared cone (or
an equivalent semigroup theorem) is still required. The construction is
documented in `docs/EXTERIOR_INVERSE_HS_CONSTRUCTION.md`.

## 2026-07-29 — Stage-4 high-precision first-failure replay

All 179 conditioning-limited first failures from the ordinary depth-13--16
scan were reconstructed from exact cards and replayed with the frozen
80/120/180/260 precision ladder and exact rational determinant adjudication.

- source commit:
  `5de0ee592e42ea3dfc3ca9443aba0aa6afb3accf`;
- replay plan hash:
  `bdfb891c49f2fa8a2fd28e1b2f6c5f603ab82fd76ef9f7305383b39028f8b129`;
- Stage-4 protocol hash:
  `8ea98348aca95a5c069ba4fc3005c34dead213e19607acbc1e8d6e4c972deebc`;
- 179/179 terminal, zero missing or stale;
- 179 confirmed nonnegative, zero confirmed negative or unresolved.

As in earlier first-failure replays, these records are not yet complete
depth-16 survivors: they must traverse the suffix skipped by the original
early stop. A dedicated exact-aware continuation is the next queue.

Local evidence SHA-256:

- Markdown summary:
  `25fc354d4300a6af5620242a0e3261da33f78a35c5bafca1603565bdb2ed85d5`;
- collection JSON:
  `f1f630f11010317734656aeb930c442fc894e3e0a32f91e36410842eb5781761`.

## 2026-07-29 — Exact5 grade-2/3 shared-cone triage

The six primary oddcycle-block cards and the secondary shear-loop seed 61
were tested on the two middle exterior grades, which are the only nontrivial
unresolved sectors for dimension five after the transpose/duality
relations. The fast exact library completely checks shared signed gauges
and positive-diagonal transforms; a multi-start L-BFGS search probes general
simplicial changes of basis and exact-replays every rationalized hit.

- source commit:
  `8ac2cfe`;
- six `exact5-oddcycle-block-pair` seeds
  `61,97,100,124,211,244`:
  grade 2 has an exact inconsistent-sign-cycle obstruction and grade 3 has
  an exact negative-diagonal obstruction within the restricted transform
  library;
- `exact5-shear-loop-pair` seed 61:
  grade 3 has the exact shared signed gauge
  `diag(1,1,1,-1,-1,-1,-1,-1,-1,1)`;
- the same shear-loop grade 2 has conflicting entry signs and no exact
  simplicial hit after 32 starts x 2000 iterations; the best objective was
  `3.728208e-4` at condition number `4.53356e5`.

The near-zero, high-condition-number grade-2 optimum is a success-oriented
signal: the next search should allow a redundant, non-simplicial
polyhedral cone rather than spend more starts forcing an invertible
ten-ray basis. The restricted obstructions do not prove that no general
shared cone exists.

Local result SHA-256:

- seven-card triage:
  `68b6bef1f6bff956991e2c82d932e64b1bf10641b10377d2919f188c4ea829de`;
- shear-loop seed-61 deep simplicial search:
  `c3fd3dba2c8571c00a0ccf87fce9c7d95fbed47e21aa35214fdc3e8a3a927d39`.

## 2026-07-29 — Exact non-simplicial cone hit for shear-loop seed 61

The high-condition-number simplicial optimum was used as a seed for a
redundant-ray invariant-cone search in the unresolved grade-2 sector of
`exact5-shear-loop-pair:61`. Worst-image/word-orbit column generation found
an exact rational certificate with twelve rays in the ten-dimensional
sector.

- search commit:
  `e786783`;
- normalization fix:
  `f47ef2e`;
- exact ray matrix:
  `R in Q^(10 x 12)`, `rank(R) = 10`;
- two exact action matrices:
  `P_0,P_1 in Q_+^(12 x 12)`;
- exact replay:
  `A_i R = R P_i` for both grade-2 atoms;
- minimum action entry: zero;
- serialized result SHA-256:
  `42bda8a820d6f3edf5fe0bac069a84da995684396637f67fc815f5672cda18eb`.

This is the first exact shared non-simplicial exterior-cone hit in the
search. Together with the already exact grade-3 shared signed gauge
`diag(1,1,1,-1,-1,-1,-1,-1,-1,1)`, it closes the *invariance* search in
both middle exterior sectors for the same seed. A redundant positive lift
does not automatically preserve trace: from `A R = R P` with rectangular
`R`, `P >= 0` alone does not yet imply `tr(A_w) >= 0`. An independent audit
must additionally find a trace-compatible positive lift/dual frame (or
control the action on `ker(R)`) before binding the certificate to
arbitrary-word `det(I + B_{s_1}...B_{s_L}) >= 0` and promoting it to the
paper's main theorem.

Transferable numerical lesson: the near-singular simplicial transform was
not a dead end; it encoded a cone needing redundant rays. Each tiny transform
column must be normalized before bounded-denominator rationalization.
Otherwise a whole valid ray rounds to zero and the exact replay falsely
misses the certificate.

### Independent trace audit — invariant cone is not yet a sign-free theorem

Independent exact reconstruction confirms the serialized grade-2 equations,
the rank of `R`, and nonnegativity of both `P_i`. It also identifies two
decisive promotion blockers:

1. the linear program over every right inverse `C` satisfying `R C = I`
   cannot make `C R` entrywise nonnegative; its best numerical margin is
   approximately `-0.2100681259`. Thus the sufficient identity
   `tr(A_w) = tr(C R P_w) >= 0` is unavailable for this lift;
2. the exact single-atom word `B^6` already has both
   `tr(wedge^2 B^6) < 0` and `tr(wedge^4 B^6) < 0`.

Therefore the rectangular grade-2 invariant cone plus the grade-3 gauge
cannot be promoted to a sector-by-sector arbitrary-depth determinant proof.
The hit remains useful structure rather than a failed experiment: finite
determinants survive through depth 16 despite a negative grade-4 sector, so
the next success-oriented search must allow cancellations between exterior
grades. The immediate replacement target is a trace-compatible cone/lift on
the combined complete-Fock direct sum
`Gamma(B) = direct_sum_k wedge^k B`, with rays allowed to couple grades.

The independent implementation at commit `c375720` rebuilds every exterior
matrix directly from exact minors rather than calling the search helper. For
the same `B^6` witness it finds the complete determinant remains exactly
positive:

`122524522219495391811877920628466510041 /
2694726010543561845443237792672907264`.

This proves that the observed survival uses cancellation between exterior
sectors and makes a combined-Fock or direct positive-realization search a
concrete target rather than speculation.

## 2026-07-29 — Exact-aware depth-12 continuation of 488 survivors

The 488 fully adjudicated depth-8 exact-fallback survivors completed the
entire depth-9--12 tranche with exact fallback on every conditioning-limited
word.

- source commit:
  `8f4a388d44d073c40c0241c1f49851f892cd6b88`;
- continuation plan:
  `ff201d576c16547ec7088702cc91f5875acaa027da9799a07ef4f63f8e126ec2`;
- 488/488 terminal, zero missing or stale;
- 3,654,713 tested words and 3,012,064 exact fallbacks;
- 12 exact-fallback negatives, 2 stable negatives, and 474 complete
  `survivor-depth12-exact-fallback` cards.

The very high exact-fallback fraction validates the exact-aware branch:
ordinary floating conditioning gates would have discarded most of this
population. These 474 survivors can now join the 692 ordinary depth-12
survivors for structural ranking, while remaining distinct in provenance.

Local evidence SHA-256:

- Markdown summary:
  `c9af3a1a754cde1623e8051ec36326a58866dbfb4619de47be0f140fe9f23705`;
- collection JSON:
  `4e1908f32f92ab596acea6f5acba3b55627fe14c40d785cc727786036d0f8b11`;
- CPU archive:
  `e871413c097991dac50dcbce7514070c994b8efd611f79a200d4a5ad058d61aa`.

## 2026-07-29 — Exact-aware suffix completion of 307 Stage-3 HP cards

The 307 cards whose original depth-9--12 stopping word was exactly confirmed
nonnegative were resumed after that word and completed the previously
unvisited suffix of the same tranche.

- source commit:
  `bb99ca53d1a0dc44e4caace884a68970dfa32051`;
- continuation plan:
  `a3eeb3a148de74f89037f9ae306eb3be05f3d04344261611388d11bf9331178c`;
- 307/307 terminal, zero missing or stale;
- 2,331,133 newly tested words;
- 694,345 exact fallbacks and 307 reused exact first-failure proofs;
- 1 exact-fallback negative, 3 stable negatives, and 303 complete
  `survivor-depth12-hp-continuation` cards.

Combined depth-12 populations now available for structure-first triage are
692 ordinary survivors, 474 depth-8-fallback descendants, and 303
Stage-3-HP descendants, each with disjoint provenance.

Local evidence SHA-256:

- Markdown summary:
  `90cc9e1fbfa841a290dc39cca8b9192bd974c79eb0e54eaa20c234536eab05d3`;
- collection JSON:
  `f19ff959d72d97d5e8e7d7cf763934ca2150ca8350b5e98ad92f102e0d1e3de9`;
- CPU archive:
  `7f2e36d96a4f393940cd136d36e9a870dd3c28ef2ed574705b8a7f1c2a7ecb55`.

## 2026-07-29 — Structural ranking of the two depth-12 continuations

The continuation-aware ranker at commits `d8dc6f4`, `a06a1c5`, and
`82bdf48` applied the same exact structural gates to both newly completed
populations. Two focused tests passed on WSL.

- Exact-fallback population: 474 survivors, of which 351 already require
  cancellation between exterior sectors, 122 are known controls, and only
  seeds 132 and 147 are exact5 trace-clean non-control candidates.
  Result SHA-256:
  `285e2e26b11a0c54c625deae55c66fe1dbefa98ebedcd0b077f787c5e0fc02f8`.
- Stage-3-HP continuation: 303 survivors, of which 201 already require
  cancellation, 97 are known controls, and seed 117 is the only exact5
  trace-clean non-control candidate.
  Result SHA-256:
  `34c6ee1836c8f211baa391849ba739de2b12b43d6dfea24f6c10352ff7e53ece`.

Most cancellation witnesses occur at depth one or two. This changes the
search policy: do not spend arbitrary-depth cone effort on every numerical
survivor. Keep seeds 132, 147, and 117 as the small trace-clean comparison
set, while using seed 61 as the primary full-Fock cancellation target.

## 2026-07-29 — Seed-61 positive rational-series audit

Commit `40ad5c4` probes the exact series
`f(w) = det(I + B_w)` through its two-letter Hankel matrices. Two focused
tests passed on WSL.

- exact Hankel ranks through total lengths 0, 2, 4, 6, and 8 are
  `1, 3, 7, 15, 31`, confirmed over two large prime fields;
- every square Hankel matrix is strictly positive and full rank, so its
  nonnegative rank is also exactly `1, 3, 7, 15, 31`;
- the exact transpose-reversal/complement symmetry holds;
- both canonical rank-31 exact-NMF gauges fail one-symbol nonnegative
  closure, with hundreds of robustly negative transition entries and NNLS
  relative residuals between about 2.1% and 3.3%.

This is a successful early stop, not a no-go theorem: it rules out spending
time on positive realizations below dimension 31 and rejects the two
canonical gauges, but it does not exclude a larger positive dilation. The
next numerical target is therefore a coupled dimension-32 or dimension-40
realization with transpose-reversal tying, promoted only if its residual
reaches machine zero and an exact rational replay succeeds.

## 2026-07-29 — Full-Fock dimensional gates and affine-\(A_4\) audit

The full-Fock search tool at commits `3f018b2` and `bee8a1d` independently
replayed the exact `B^6` traces before numerical optimization. It proves an
additional early stop:

`tr((Lambda^2 direct_sum Lambda^4)(B^6)) < 0`.

Therefore no trace-positive cone on the proposed 15-dimensional combined
sector can exist. Together with the exact Hankel rank 31, this fixes the
smallest credible numerical target at the complete 32-dimensional exterior
algebra; redundant 36- and 40-ray lifts remain allowed.

The separate affine-\(A_4\) audit at commit `860603a` exactly maps the
gauge-fixed seed-61 atom and its transpose to products of positive affine
Chevalley generators. Thus every lifted word is loop-TNN and has a
nonnegative cylindric-network realization. However, this does not prove the
required full-Fock character:

`det(I + X(1)) = chi_(Lambda^bullet)(X(1))`.

Lam--Pylyavskyy's folded-determinant theorem controls `det X(t)`, while the
loop-TNN semigroup is not closed under the addition `I + X(t)`. The gap is
decisive, because for positive shear parameters

`det(I + E(t)) = 32 - (a1 a2 a3 a4 a5) t`.

Taking all `a_i=3` gives the exact negative one-letter value `-211`, so no
parameter-uniform affine-total-positivity theorem is possible. The fixed
seed remains viable: its product is `11011/1179648`, its one-letter weight
is `37737725/1179648 > 0`, and an additional 6,000 exact integer words of
length 17--120 produced no negative value. This long-word replay is evidence
only, not a proof.

Operational response: stop the automatic affine-theorem route and run only
fixed-seed full-Fock searches. One WSL start and 20 independent CPU-machine
starts now cover 32, 36, and 40 rays with single-threaded BLAS; only a
machine-zero residual followed by exact rational replay can be promoted.

The first WSL full-32 start finished normally at commit `83e7b36` with no
exact certificate:

- best 32-ray simplicial objective `0.3927446645`, minimum transformed entry
  `-0.1187775776`, condition number `768.11`;
- redundant milestones: maximum closure residual `0.355639` at 32 rays and
  `0.356151` at 36 rays;
- column generation stopped at 39 rays after repeating the worst image;
- every best transform column couples grades, but the cycle-basis diagnostic
  still has 466 negative entries and therefore gives no cheap winding basis.

The result is a clean numerical miss, not a theorem-level obstruction. Its
JSON SHA-256 is
`e5e67d9ff3853e2cfbfbe9d16edee55e8b1887e092222ff2df25d7951ba13bc9`;
stdout SHA-256 is
`9db234646655ec21dbaa65467c280f6f2294dad735eff97397ab68439e191d67`;
stderr is empty. The 20 independent CPU starts continue rather than
repeating this initialization.

## 2026-07-29 — Seed-61 Hodge/spinor structured-cone audit

Commit `083751f` tests the natural cross-grade basis changes before spending
more random-cone effort. The exact Hodge reduction is

`Gamma(B) ~ diag(E, E^(-T))`,

with the transpose atom acting as `diag(E^T, E^(-1))`. The preserved Mukai
form has inertia `(16,16)`, so its positive locus has no convex
Lorentz-style future sheet. The self/anti-Hodge basis has 122 negative
entries and an exact reciprocal sign conflict; particle-hole and
Jordan--Wigner changes are signed permutations and inherit another exact
two-cycle sign conflict. These facts reject the simplest orthant and
Lorentz/particle-hole cones, not arbitrary nonlinear cones.

Complementary grades also cannot be certified independently:

`chi_14(B^7) = tr(B^7) + tr(B^(-7)) < 0`,

while `chi_23(B^7) > 0` and the complete determinant remains positive.
Thus a successful structured inequality must couple both Hodge pairs. The
next focused analytic target is the seed-specific bound

`chi_23(W) >= -2 - chi_14(W)`.

## 2026-07-29 — New oddcycle exact5 cone triage

The three new trace-clean depth-12 candidates
`exact5-oddcycle-block-pair:{117,132,147}` were searched simultaneously in
grades 1--4 with 16 starts per numerical sector. Grade 4 has an exact shared
cone certificate for every seed. No complete sectorwise theorem was found
because grades 1--3 did not exact-replay.

The near-boundary objectives justify immediate continuation rather than
discarding the candidates:

- seed 117: grades 1/2/3 objectives approximately
  `1.00e-4 / 3.49e-3 / 7.10e-4`;
- seed 132: `5.96e-7 / 1.05e-5 / 3.18e-6`;
- seed 147: `3.80e-7 / 6.03e-5 / 1.09e-6`.

Result SHA-256 values are respectively
`bc0caeba46c384fc683ca4b22172e7d30aa576ce26f9bf14003985550fc5b7ba`,
`91aa3e814f8e38319ef0cab666e3e2bd72afd5122d71e6155e62faed70528e90`,
and
`dc7db0f130c7d03127af4e57e056dfc2325ab3484b431b1e4b39c4b8b027ff11`.
Seeds 132 and 147 now receive a 128-start simplicial continuation in
parallel with a generalized redundant-ray search. Any rectangular hit must
also pass exact `RC=I, CR>=0`; `AR=RP, P>=0` alone is not promotable.

### 128-start simplicial continuation

The deeper seed-132 and seed-147 runs finished without a complete exact
certificate.  This is an early stop for the simplicial route, not evidence
against a larger polyhedral cone:

- seed 132 best grade-1/2/3 objectives:
  `1.079102e-7 / 9.843185e-6 / 1.813196e-6`;
- seed 147 best grade-1/2/3 objectives:
  `3.670594e-7 / 3.941678e-5 / 4.083955e-7`.

The result JSON SHA-256 values are
`85bbc11d9cae40a063e8c1fa6f8bfcf0b3acafd83f6acc8fa3572237b5de28ee`
and
`ff4b3b90e33e2977e472778826aa92cecedcd413d1716856d5e593febeb4f909`.
Further simplicial restarts are stopped; the active continuation is the
trace-compatible redundant-cone search with exact replay.

### Trace-compatible redundant-cone continuation

Commit `0eac2ad` generalized the exact-gated search to arbitrary
template/seed/grade targets.  Every promotable result must satisfy exact
`AR=RP`, `P>=0`, `RC=I`, and `CR>=0`; the focused regression set reported
8 passing tests.

Nine 64-start searches (seeds 117/132/147, grades 1/2/3, up to 40 rays)
then completed on WSL.  No certificate was found.  More decisively,
seed 132 and seed 147 both hit an exact grade-3 negative-trace early stop
at diagnostic word power 6:

- seed 132:
  `-337058501890662715329123629102795636 /
  114934804865416265625`;
- seed 147:
  `-450129988188568437799315011797002270580670464 /
  1068217223883341580726260009765625`.

All other searches stopped on a repeated worst image at 7--20 rays.
Consequently, a theorem that certifies these candidates grade by grade is
impossible for seeds 132 and 147, while additional restarts for seed 117
are not justified by the present margins.  The full result archive has
SHA-256
`f6158d8efb2a0a26d3102ac3871f11ce082ae6a306eec5e15003c98b63bdbab9`;
its internal `SHA256SUMS` records every JSON.  The oddcycle sector-cone
route is stopped and compute is redirected to the seed-61 coupled spectral
inequality.

## 2026-07-29 — Seed-61 exact lower spectral-band certificate

Commit `c915a68` replaces long-word eigensolver evidence for half of the
remaining determinant sign with a finite exact certificate.  In the fixed
signed gauge, strict positivity of the first and third compounds splits the
spectrum into

`[lambda_1] [lambda_2,lambda_3] [lambda_4,lambda_5]`.

Exact enumeration of all `2^10` blocks with fixed rational weighted
norm/conorm vectors gives

`U/L = 0.699644632507996... < 1`.

Ten exact residue inequalities then prove that every word of length
`n>=24` has `|lambda_4|<1`.  Therefore, if the lower pair is real and
negative, both roots lie in `(-1,0)` and their factor
`(1+lambda_4)(1+lambda_5)` is positive.  Two focused new tests plus the
adjacent survivor/Hodge checks reported 6 passes.

The remaining arbitrary-length theorem is now only the upper quadratic

`h_+ = (1+lambda_2)(1+lambda_3) > 0`.

A 200,000-word numerical reconnaissance through length 40 found no
straddle of `-1`; the smallest observed upper factor was about
`25.8985028294`, at a cyclic representative such as `11011111111`, with
roots about `-9.97367` and `-3.88605`.  This margin guides the next exact
block certificate but is not itself used as proof.

### Exact long-word counterexample and retirement of seed 61

The unresolved `A=tr(W)-rho(W)<0` branch is not merely a proof gap.
Commit `c98b913` freezes the following length-150 word:

```text
000000110010101100101011010101100101010101100101100101011001010100110100110011010101001010101010110101010010110010101101010011010011010011010010100000
```

Its word SHA-256 is
`e36ea7ebf0c2038acc3f2a2e0cc97c5fed4a497c8fc9aafa12b61fb24ff4d072`.
With `A=768 B` and integer product `M`, direct exact evaluation gives

`det(I+B_w) = det(M+768^150 I)/768^750 < 0`.

The unreduced integer numerator has 2,223 decimal digits and SHA-256
`3ac8e5c102e147edfda33c646a43b1bef3118977f234f7c6a61996e056d69bfe`.
An independent call through the frozen rational determinant oracle reduces
to exactly the same fraction and also returns a negative numerator
(reduced-numerator SHA-256
`8b04e0cda7c1a8c7c0a12655db674cce4e66b7c6e315d84b53eaea6fde414956`).
The two counterexample tests and the adjacent spectral-tail tests report
4 passes.

High-precision eigenvalues are diagnostic only: the straddling root is
approximately `lambda_3=-0.9805654650`.  The exact acceptance gate is the
integer determinant above.  Seed 61 is therefore permanently retired as
an arbitrary-word sign-free candidate, and all 60 active full-Fock searches
for it were stopped immediately.

For provenance, commit `bf2aeef` also contains a correct exact conditional
lemma: a five-letter weighted first/third-compound ratio
`0.8899447041...<1` proves `lambda_2 lambda_3>1` for every length at least
18, and together with the lower-band certificate proves positivity of the
`A>=0` branch from length 24.  The counterexample lies exactly in the
remaining `A<0` branch, so this lemma is retained as methodology but cannot
rescue the candidate.

Commit `38e04a5` adds an exact, safely symmetry-reduced short-word verifier.
Only cyclic rotation and transpose-reversal are quotiented; a concrete
six-letter mismatch rejects the tempting but invalid bit-complement
quotient.  Its protocol is being generalized to the next surviving
candidates rather than spending production time on the now-retired seed.

## 2026-07-29 — Final Stage-4 HP suffix continuation

The two-machine continuation completed all 179 planned cards with no
missing or stale result.  It tested 21,771,547 suffix words, invoked
3,675,889 exact fallbacks, reused all 179 parent HP proofs, and returned:

- 176 `survivor-depth16-hp-continuation`;
- 1 `rejected-negative-exact-fallback`;
- 2 `rejected-negative-stable`.

The three new rejections are:

- `exact5-oddcycle-block-pair:58`, stable negative at depth 16 on
  `0000000000000001`;
- `exact4-block-shear-pair:238`, exact negative at depth 16 on
  `0001010101010101`, with numerator
  `-106234836889408659473558270533318603945192755703060019561657739`;
- `exact4-block-shear-pair:49`, stable negative at depth 15 on
  `000010101010101`.

The continuation plan hash is
`92b07019f51d65e6427b55aea99aeee21d2c1a464d9bff68abeb5eff32887d5c`.
Final `collect.json` SHA-256 is
`3cd82533cc3601adb104fe0e0c831c2f79b82755e22c2cc8bd0d2a0e8e11a726`;
the Markdown summary SHA-256 is
`a3b3c36ad3460d27708e26e45b0f72543e59a76ddfb7381aba159fe5d89130e7`;
the CPU candidate archive SHA-256 is
`2f43bc4103390e959cfe41398e7a265a5d92ad9308f2b3ee2c4e67ac51de203a`.

Operationally, the full 76-core budget is now reassigned to complete
depth-23 exact scans for oddcycle seeds 117, 132, and 147 in parallel.

## 2026-07-29 — Complete exact depth-23 oddcycle scan

Commit `ffa609d` generalized the exact integer/Bareiss short-word verifier
to arbitrary frozen transpose-paired candidate cards.  The 76 available
single-threaded processes were split concurrently across
`exact5-oddcycle-block-pair:{117,132,147}`.  All three collectors report:

- `complete=true`;
- `status=strictly-positive`;
- 384,359 safe cyclic/transpose-reversal classes;
- 16,777,214 covered raw words (every nonempty binary word through
  length 23);
- no nonpositive witness.

For every seed, the global exact minimum occurs at the one-letter pure
word; the depth-23 minimum within that length is likewise the pure word.
The final `collect.json` SHA-256 values are:

- seed 117:
  `8a726c606f942d7300088c2eda5689bb67e13d616ba206c7773a50559c43dd82`;
- seed 132:
  `2d0cafe768a44e9847cada60360c3e7c2131aadc239f53a06a112024550367f0`;
- seed 147:
  `c7ee334574b4f098bb85d5a7d48b14378f96a11bf6757b2ead9b352ec2bf1a01`.

The CPU shard archive SHA-256 is
`b70e6dc0a76792e8c9f0c0a597402cb6454ae53b6b501edbc8620f29bb814921`.
These are now the leading finite-depth survivors.  All 76 cores immediately
continue with independent exact-gated adversarial searches at lengths
60, 80, 100, and 150.

### First long-word adversarial campaign

Commit `4daabad` supplied a generic discovery scanner whose acceptance gate
is always the frozen exact rational determinant.  The 76 independent runs
used 128 restarts each at lengths 60, 80, 100, and 150, split
25/25/26 across seeds 117/132/147.  The resulting 304 exact replays were
all strictly positive:

- seed 117: 25/25 runs, 100 exact winners, no negative;
- seed 132: 25/25 runs, 100 exact winners, no negative;
- seed 147: 26/26 runs, 104 exact winners, no negative.

The complete merged result archive SHA-256 is
`9d9a0d3fd48687ee1cdf9b6a9dee61d9d43a40924feec937b6833d9e351a3920`
(the CPU-only archive is
`33225234d71dcecf2ff00f74e8175b5470a993191dd651d1bcbbf212ed950a23`).

This campaign also exposed a useful numerical failure mode: the
double-precision rescaled-determinant fallback marked many winning words as
negative, but every exact replay was positive.  The exact gate prevented a
false rejection, and identical restarts are stopped.  The next campaign
must rank words with a high-precision objective before exploring lengths
250, 400, and 600.  In parallel, proof search now targets the common
coupled oddcycle structure rather than independent exterior-grade cones.

### Complete exact depths 24--27

The exact short-word continuation completed for all three leading seeds.
For each seed it checked 4,800,038 safe cyclic/transpose-reversal classes,
covering all 251,658,240 binary words of lengths 24 through 27, and found
no nonpositive determinant.  Combined with the preceding round, each seed
is therefore exactly positive on all 268,435,454 nonempty binary words
through length 27.  The minimum at every newly checked length is a pure
word.  The continuation `collect.json` SHA-256 values are:

- seed 117:
  `79b415d12265df85da46d564ddbd0a70ea3991cbf739bc25f2106c5ede4c825c`;
- seed 132:
  `1a334bc291c0ba40aa9ad9e9455a28908aed1274c1416510efcf03368f014041`;
- seed 147:
  `9bbbb65b3cb3a9d41053d92219a0eae92a4efee0baa94b1731cc2d1a3387b620`.

The CPU shard archive SHA-256 is
`e8a263d1f7f19f7829978324f3d1bb1e0031516c03f3701781fb8f4a62e09218`.
This is finite-depth evidence, not an arbitrary-word theorem.

### High-precision long-word serialization incident

Commit `2ae03be` changed long-word discovery to use float search only as a
prefilter, rerank finalists with `mpmath`, and retain the exact rational
determinant as the sole hit gate.  The first 72-run production plan used
lengths 250/400/600, 32 restarts, 16 search rounds, 8 proposals per round,
and 1400/2200/3200 decimal digits respectively.

All length-250 and length-400 jobs completed, but every length-600 job
failed only while converting the already-computed exact integer numerator
to a decimal JSON string.  Python 3.11's default 4,300-digit conversion
guard was the cause; no numerical or oracle result was lost or accepted.
Commit `10bfc6a` disables that guard in this trusted standalone research
CLI and adds a length-600 regression replay.  The focused verification is
3/3 passing.  Only the 24 failed length-600 shards are being rerun; all
successful 250/400 outputs are preserved.  Operational lesson: exact gates
must be tested through final artifact serialization at the largest planned
word length, not merely through determinant evaluation.

The selective rerun completed, yielding a complete 72/72 result grid:
eight independent runs for every seed/length pair in
`{117,132,147} x {250,400,600}`.  All stderr files are empty; all JSON
artifacts parse; all word hashes, lengths, RNG assignments, and exact-gate
fields replay consistently.  Every one of the 72 high-precision finalists
and every one of the 72 exact rational determinants is strictly positive.
Conversely, the double-precision prefilter incorrectly suggests a negative
sign for all 72 finalists, quantitatively confirming that it must never be
used as an acceptance gate.

The WSL archive SHA-256 is
`240198516e9856b9bea7c100368ce9cfea64078e38b2ffc2b3cd31680c6ffc04`;
the CPU archive SHA-256 is
`05618ca1e16f3f4a6d12ca6b1f97a5e90106917b4c9f63ae704d7f6e693dce3b`.
With no rejection, the next independent campaign advances to lengths
800/1200/1800 at 4500/6500/9500 digits on 12 WSL plus 60 CPU processes.

## 2026-07-29 -- Symmetric-oddcycle cone branch

A deliberately symmetric two-parameter pattern was tested with generators
`{B(x,y), B(x,y)^T}`.  The broad conjecture `x>y>0` is false: at `y=1`,
the exact word `000000110011` is negative for the interval between the
positive roots approximately `0.9995421691` and `1.0847617744`.  The
parameter-chamber claim is retired, while the fixed integer point
`(x,y)=(2,1)` remains a survivor.

Commit `b4e2185` freezes three exact results for this fixed point:

- a symbolic signed-monomial cone proving `chi_4(W)>=0`;
- a rational 10-dimensional common cone proving
  `chi_1(W)+chi_4(W)>=0`;
- a rational 15-dimensional common cone proving
  `chi_2(W)+chi_4(W)>=0`.

The compact certificate SHA-256 values are
`f13915705d792899cb36580f67bc36dae691ee33f6fba989e090f979cef81f5a`
and
`af9b881a5cc6e6065d58f4588e2631fc46a692391feb829a25757b90334f4264`.
Both stored transforms are independently replayed as exact rational
similarities with entrywise-nonnegative transformed generators; the
focused tests report 2/2 passes.

These are partial lemmas, not a sign-free theorem.  The tempting
complementary cone on grades `{2,3}` is exactly impossible already at
`W=B^7`, where `chi_2=13875`, `chi_3=-171633`, and their sum is `-157758`.
Since `det(B)=8`, the active complete target paired with the first cone is
instead `chi_0+chi_2+chi_3+chi_5>=0`, retaining the positive
`chi_5=8^n` sector.  Search is redirected to a coupled cone for grades
`{0,2,3,5}` or a finite-depth exact check plus a grade-five tail bound.

### Deep long-word stop condition

The independent 72-run continuation at lengths 800/1200/1800 is complete.
Every seed/length pair has eight distinct RNG assignments; all 72 JSON
files parse, all stderr files are empty, and all word lengths and SHA-256
digests replay.  All 72 mpmath finalists and all 72 exact rational
determinants are strictly positive; the double-precision prefilter again
misclassifies every finalist as negative.

The WSL archive SHA-256 is
`7e6f9dea4dd21e52c06839eae3d10db9b113f64b6295518c484e4628f3eff3e9`;
the CPU archive SHA-256 is
`219aa6e419bc9106c27b47c74ba0191a81eb6e8e81b4d29c1a28566d4cd04a00`.
Together with the previous campaign, this gives 144 independent
high-precision/exact winners spanning lengths 250 through 1800, in
addition to exhaustive exact coverage through depth 27.  Repeating the
same local-search objective at still greater length is now stopped:
it has supplied strong survivor evidence but no proof and no
counterexample.  Compute is reassigned to structurally different
coupled-cone and tail-bound searches.

### Fixed symmetric point: exact depth 27 and partition obstructions

Commit `23bbe4a` connected the fixed integer point `B(2,1)` to the existing
exact short-word oracle without changing its Bareiss determinant gate or
safe cyclic/transpose-reversal quotient.  Fourteen WSL shards completed
with empty stderr and the collector reports:

- `complete=true`, `status=strictly-positive`;
- 5,184,397 canonical classes;
- all 268,435,454 nonempty binary words through length 27;
- no nonpositive witness;
- global minimum `35` at the one-letter pure word.

At every checked length the exact minimum is again the pure word.  The
`collect.json` SHA-256 is
`a2dbe54da4c30bfdcd9e1018c8e6ba54d5cc0a0cad0a1bf71c6748846758aea9`;
the complete shard archive SHA-256 is
`13cfbf7f2fe1b119f401cca7219d9aba1fdcad28066ed90a506e75cbec169eeb`.
This is strong finite-depth evidence, not an arbitrary-word proof.

Exact audits then removed several attractive but invalid proof splits:

- `chi_2+chi_3` is negative already for `B^7`;
- a length-30 word makes `chi_1+chi_3+chi_5` negative while the full
  determinant remains positive, so the exact `{2,4}` cone cannot be paired
  with an odd-sector complement;
- a second length-30 word makes
  `chi_0+chi_2+chi_3+chi_5` negative while the full determinant remains
  positive, so the exact `{1,4}` cone cannot be paired with that
  complement either.

Both corresponding CPU cone campaigns were stopped immediately after
their exact obstructions arrived.  The positive full weights on the same
words prove that compensation crosses these proposed block boundaries;
future work must use the full 32-dimensional Fock character or a genuinely
coupled domination inequality.

The parameter-family audit also distinguishes two claims that must not be
conflated.  The open two-invariant chamber `D>0,-D<T<0` is false as a full
sign-free theorem: at `(D,T)=(10,-9)`, the exact length-11 word
`00100110011` has determinant `-86709610990738`.  By contrast, the
polynomial that becomes negative at fixed `D=8,z=4` is only the detached
`{0,2,3,5}` complement; the full determinant at that pure fourth power is
positive, so it is not a full-family counterexample.

Finally, all 98,304 exact Bernstein coefficients for the 8,190 orientation
words through depth 12 are nonnegative on the common-amplitude interval
`0<=z<=1`, with minimum 17.  This useful fixed-amplitude margin does not
extend to independently varying endpoint amplitudes: a frozen length-120
four-endpoint word has exact negative complementary trace.  The
four-generator cone route therefore early-stops before numerical work,
while the common fixed `z=1` pair remains the main theorem candidate.

### Arbitrary-length subclasses and full-Fock search

Commit `0aa0e3c` proves two infinite word subclasses exactly:

- every pure power `B^n` and `(B^T)^n` has strictly positive determinant
  weight; the characteristic polynomial has one positive real root, no
  negative real root, two conjugate pairs, and an exact reciprocal-polynomial
  gcd gate excludes roots on the unit circle;
- every reflection-square word `u complement(reverse(u))` is exactly of
  the form `X^T X`, hence has positive spectrum and positive
  `det(I+X^T X)` for arbitrary length.

These cover the zero-transition and a large reflection-symmetric part of
the semigroup but not every word.  With every tested complementary
partition now exactly obstructed, commit `9ca0c3d` exposes a fixed-pair
full-32 Fock cone search that replays the known split-obstruction words as
full-positive before optimization and emits a result only after exact
trace-compatible promotion.  A first 12-start reconnaissance had no
certificate (`best objective=0.0281503860`, minimum transformed entry
about `-0.31275`).  Sixty independent one-start, 4000-iteration searches
are now running; this is the first numerical cone campaign that has not
already been invalidated by a negative subcharacter word.

### Full-Fock preconditioning and arbitrary-word theorem

The original 60-way random full-32 search was stopped before completion
after structured initializations proved decisively more efficient.  A
block basis containing the exact grade-`{1,4}` cone reduced the best
objective to `0.0013721487870580061`.  Replacing it by the exact
grade-`{2,4}` cone reduced the objective further to
`0.00035961518605738394`, a factor of about 78 relative to the random
baseline.  Three-stage warm continuation at weights
`1e-7,1e-9,1e-11` reached objective `6.50e-9` and minimum transformed
entry `-2.93091e-4` in the best scratch run.  A separate 60-way CPU batch
over `0.001<=epsilon<=0.01` completed without errors and without an exact
cone: its best result was seed `950010048`, epsilon
`0.009653059951179559`, objective `2.564980403020742e-8`, and minimum
entry `-4.767167046731235e-4`.  This confirms the preconditioner while
also showing that further identical basin polishing is lower priority.
The complete 60-way JSON/log archive SHA-256 is
`0b0fbb8c9448ff03157aeb8a8cf14a3adb7e9af30225bb324b801f8855a1a534`.

More importantly, commit `84d757e` closes the fixed-pair arbitrary-word
problem without a full-32 cone.  For every word `W in <B,B^T>`, it proves
exactly `det(I+W)>0`.

The certificate combines two independent strict tail bounds:

- after the common grade-four sign gauge, both grade-four atoms are
  entrywise nonnegative and share a weight-8 loop; exhaustive exact
  enumeration of all 8,192 length-13 blocks gives
  `100*||Lambda^3 W||_F^2 < (Lambda^4 W)[0,0]^2`, with raw worst-case
  integer margin `7557346070286518140205276`;
- exact enumeration of all remainders through length 12 gives squared
  ratio at most 10, hence Frobenius submultiplicativity proves
  `chi_3(W)+chi_4(W)>0` for every length at least 13;
- Sylvester certificates for `6I-B^T B` and
  `29I-(Lambda^2 B)^T(Lambda^2 B)` are positive definite.  Consequently
  the grade-one and grade-two trace bounds are dominated by `8^n` from
  length 6 onward; the conservative integer margin at length 6 is 17,174;
- lengths 1 through 12 are closed by the existing exact common-amplitude
  Bernstein audit and exact grade-`{1,4}` cone.  The smallest stored
  Bernstein margin is 17.

All gates are strict, so continuity already implies a nonempty open
parameter neighborhood of the fixed matrix, although an explicit
human-readable neighborhood remains to be extracted.  The immediate
research target is now the physical completion: an exact positive
auxiliary-field decomposition and a Hermitian interacting Hamiltonian.
The active construction is the full-Fock transfer
`T_c=c I+Gamma(B)+Gamma(B)^T`; if an exact integer `c` makes it positive
definite, then `H=-log(T_c)` is Hermitian and generally nonlocal, while
the expansion of `Tr(T_c^N)` has positive coefficients and every
configuration weight reduces to the proved `{I,B,B^T}` determinant
semigroup.  This route is being checked before any further cone polishing.

### Explicit continuum alphabet

Commit `a39f59d` upgrades the fixed theorem to the continuum alphabet

`A={B(z),B(z)^T : 99/100<=z<=101/100}`,

where every letter may choose its orientation and parameter `z_i`
independently.  Exact rational interval propagation proves
`det(I+W)>0` for every finite word in this uncountable alphabet.

The finite verifier covers all 8,190 nonempty binary orientation words
through length 12 simultaneously over all independent parameter choices;
the global full-determinant lower bound is `3499/100`.  The length-13
grade-three/four block certificate covers all 8,192 orientations.  Its
worst word is `0000001111111`, and its strict raw interval numerator is
`17885432888260091992976094678617191678771759066816123079705733862324608427900`
over denominator `100^26`.  Every nonempty short remainder has positive
margin, while the empty remainder saturates the allowed factor 10.
Uniform interval Sylvester gates retain lower leading-minor bounds 2 and
13, so the same low-sector tail starts at length 6 with margin 17,174.
The real-log gate also holds throughout the interval because the
characteristic polynomial has no negative real root for `z<8`.

This is the desired structured set rather than an isolated survivor.
The proof is stronger than a shared-coupling statement: it allows
time-slice-dependent auxiliary fields `z_i`.  Focused independent replay
of the interval-family and fixed-point tests reports 13/13 passing.

### Hermitian interacting transfer and minimal novelty filter

Commit `b54837c` gives an exact physical realization at the fixed member.
In the orthonormal occupation basis let
`Gamma(B)=directsum_{k=0}^5 Lambda^k(B)`.  Exact row arithmetic for
`S=Gamma(B)+Gamma(B)^T` gives maximum diagonal-dominance requirement 18,
attained at zero-based rows 19, 23, 29, and 30.  Therefore

`T=19 I+Gamma(B)+Gamma(B)^T`

is real symmetric positive definite with minimum exact row margin 1.
The normalized transfer

`exp(-H)=T/21`

defines a Hermitian, number-conserving five-mode Hamiltonian and has the
positive three-field decomposition with coefficients `(19,1,1)/21` and
one-particle propagators `{I,B,B^T}`.  For every integer time depth, its
Fock trace expands into positive scalar coefficients times the already
proved determinant weights.  The characteristic polynomial has no root
on the nonpositive real axis, so `A=Log(B)` is real and each nontrivial
field is an exponential of a real one-body bilinear.

The model is strictly interacting, not a disguised quadratic Hamiltonian:
a Gaussian transfer would obey `(c+2)T_2=Lambda^2(T_1)`, whereas the exact
difference has 58 nonzero entries and first entry 42.  The construction is
grand-canonical and generally nonlocal with up to five-body terms; no
canonical fixed-filling or connected-lattice claim is made.

Commit `bb44271` freezes a deliberately conservative novelty audit.  Exact
invariants exclude a split-orthogonal group reduction
(`det(B)=8`, common bilinear-invariant nullity zero), standard
five-dimensional Kramers pairing (odd dimension and scalar-only common
commutant), simultaneous block decomposition (words through length five
span all 25 dimensions of `M_5(R)`), diagonal sign/positive gauges (a
directed cycle has invariant product `-1`), and similarity to a totally
nonnegative alphabet (four eigenvalues are nonreal).  It does not yet
exclude the most general 10-Majorana Wei-2024 contraction condition,
complex Majorana reflection positivity, or a literature-level
fermion-bag/loop equivalence.  These open checks must be resolved before
claiming novelty beyond every known Majorana/semigroup class.

### Full common-metric audit overturns the oddcycle novelty hypothesis

The previously open Wei/semigroup check has now produced a simple exact
reduction.  With

`w=(4,4,1,-5,5)^T` and `R=2 w w^T/83-I_5`,

the metric is symmetric, satisfies `R^2=I`, and has signature `(1,4)`.
For every `99/100<=z<=101/100`, both

`R-B(z)^T R B(z)` and `R-B(z) R B(z)^T`

are positive definite.  Exact leading principal minors and Bernstein
lower bounds are being frozen in the dedicated replay oracle; the smallest
nonconstant Bernstein numerators already obtained are
`1523807019/68890000`, `397103913/68890000`, and
`475092321/68890000`.  Thus the entire independently varying continuum
alphabet lies in one known strict real split-contraction semigroup.

The exterior-power theorem and interacting Hermitian transfer remain valid,
but this family is not the novel completion of Challenge #121.  The key
operational lesson is that failures of invariant-form, diagonal-gauge, or
one preselected metric tests do not exclude the full Wei contraction class.
A full common-metric feasibility gate must precede exact promotion of every
future survivor.

### General `(p,q,r)` probe: fixed-metric failure is a false novelty signal

A three-parameter discovery screen was added for

`B(p,q,r)=[[0,0,2,0,0],[2,0,0,0,0],[0,2,0,p,0],`
`[0,0,0,1,q],[0,0,-r,0,1]]`.

It applies the existing short-word, grade-four gauge, 13-block,
short-remainder, and low-sector norm gates in about 0.15 seconds per fixed
point.  A second discovery gate solves the full convex common-Lyapunov SDP
over a symmetric metric `R`, maximizing `t` subject to

`R-B^T R B >= t I`, `R-B R B^T >= t I`, and `||R||_F<=1`.

The first boundary probe tested
`(1,1,1)`, `(0.3,1,1)`, `(2.8,1,1)`, `(1,0.3,1)`,
`(1,2.8,1)`, `(1,1,0.3)`, and `(1,1,2.8)`.  Every point has a
strict common metric.  The normalized optimal margins were respectively
approximately `0.13608012`, `0.04915609`, `0.13903211`,
`0.03658843`, `0.13058284`, `0.04915609`, and `0.13903211`;
all returned nonsingular inertia `(1,4)`.

This invalidates the earlier inference from failure of the single rational
metric near `p,q,r=0.3` or `2.8`: the feasible metric moves with the
parameters.  Subsequent scans must retain only points where the *full* SDP
margin collapses, and even those are discovery survivors rather than exact
no-go theorems.

### Dual-machine `(p,q,r)` scan and the multi-point pivot

Protocol `oddcycle-pqr-discovery-v1` evaluated a 14-by-14-by-14 Cartesian
grid, 2,744 cells total.  The WSL workstation ran one 1,372-cell shard with
14 workers and the 64-core CPU machine ran the other 1,372-cell shard with
62 workers, leaving two cores free on each host.  All 2,744 atomic manifests
completed with zero compute errors; the generic collector found no failed,
missing, or pending cells and confirmed constant settings.  The proof screen
used exact word depth 12 numerically, a low-sector tail start of 12, and the
frozen grade-three/four gates.

Classification:

- 2,729 points failed the current exterior sufficient certificate;
- 15 points passed all exterior gates;
- all 15 exterior survivors had a strict single-point common metric;
- no single-point novelty survivor remained.

Failure-stage counts were 1,734 at the grade-(3,4) short-remainder gate,
783 at the length-13 block gate, 211 at a nonpositive short-word
determinant, and one at the low-sector norm tail.  The strong certificate
therefore defines a narrow region rather than evidence that all other points
have a sign problem.

The 15 exterior survivors range from `(0.7,1,1.4)` through
`(1.4,1.4,1.4)`.  Their individual SDP margins range from about `0.1046`
to `0.1889`.  Pair probes within this region, and even the joint alphabet
containing all 15 points and their transposes, still share one strict metric;
the 15-point joint normalized margin is approximately `0.07118979`.
Therefore simply unioning points inside the present Frobenius certificate
does not escape the known semigroup.

A separate probe supplied the useful counter-direction: distant pairs such
as `(0.1,1,1)` with `(4,1,1)`, the corresponding `q` and `r` pairs, and
crossed pairs like `(0.2,4,1)` with `(4,0.2,1)` have full joint SDP margin
numerically zero (about `1e-10` residual scale), even though each point
separately has a strict metric.  These points do not pass the old
grade-(3,4) Frobenius tail, so the next certificate must replace that loose
norm.  The next route is a common quadratic contraction metric on exterior
grades 1, 2, and 3, normalized by the positive grade-four loop of weight 8.
This targets exactly the desired mechanism: stable exterior sectors without
a common base-space Wei metric.

### Joint-alphabet boundary search and exterior-CQLF early stop

Along the one-axis family with `q=r=1`, the full joint base-space SDP remains
strict for moderate pairs such as `(p_low,p_high)=(0.5,2.0)` with margin
about `0.0470` and `(0.4,2.5)` with margin about `0.0135`.  It collapses
numerically to zero for `(0.4,3.0)`, `(0.3,2.5)`, and `(0.5,3.5)`.
These pairs realize the desired incompatibility at the base-space level:
each point separately has a strict metric, while the pair has no numerical
strict common metric.

A new common-quadratic exterior oracle tested grades 1, 2, and 3 after
normalization by determinant growth 8.  It validates every SDP metric
directly and reports the induced-norm condition number and trace prefactor.
The extreme `(0.1,4.0)` pair fails quickly with effective one-letter
gammas approximately `0.572`, `1.315`, and `2.629`.  More importantly,
even the fixed baseline has grade-three one-step gamma about `1.329`.
Therefore a one-letter common quadratic norm is too weak to recover the
already proved fixed theorem and cannot be used as the final discriminator.

For the zero-base-metric boundary pairs, the one-letter grade-three gammas
remain above one: approximately `1.906` for `(0.3,2.5)`, `2.137` for
`(0.4,3.0)`, and `2.379` for `(0.5,3.5)`.  This is a certificate failure,
not evidence of negative weights.  The correct next refinement is a
block-product quadratic metric with explicit residue bounds, analogous to
the successful length-13 fixed-point proof.

### Joint-word survivor tests and mandatory exact replay

The pair `{p=0.3,p=2.5}` at `q=r=1`, including both transposes, first
survived all 349,524 words through depth 9 and 100,000 independent random
words through depth 40.  The CPU machine then exhausted all 22,369,620
nonempty words through depth 12 in 13.8 seconds.  Every tested determinant
is strictly positive and the global minimum remains `33.5`, attained by a
one-letter word.  This gives the prospective block theorem the same finite
depth as the fixed theorem while the new four-letter tail certificate is
developed.

The `{p=0.4,p=3.0}` random stress initially returned a floating-point
negative at depth 39 for word
`201123223230303322300301233223323232302`.  Exact rational replay showed
that determinant is positive: the apparent negative was catastrophic
floating-point cancellation at large word norm.  The oracle now requires
exact rational replay before classifying any floating nonpositive witness;
an exact-positive replay terminates with
`floating-point-resolution-limit`, never with a counterexample label.
This prevents long-word overflow/cancellation from steering the search
away from a genuine survivor.

### Coupled exterior profile and multi-direction early stop

The plain grade-three normalization
`||Lambda^3(W)||_F^2 / 8^(2|W|)` is not the fixed proof's denominator and
was discarded.  The corrected diagnostic divides by the square of the
positive grade-four path weight.  For the fixed alphabet its worst ratio
falls from about `4.52` at depth 1 to `0.319` at depth 8.  For the leading
joint pair `{(0.3,1,1),(2.5,1,1)}` it rises to about `23.23` at depth 4
and then falls to `3.898` at depth 12.  Thus the candidate is still alive
but does not yet satisfy the existing finite-tail gate; the next theorem
must use a state-dependent/coupled positive-automaton bound rather than a
single Frobenius norm.

To search for a less distorted no-common-metric alphabet, cyclic triples
and six-direction unions were tested at reciprocal scales
`s in {0.5,0.6,0.7}`.  All six alphabets were rejected immediately by the
full joint common-metric SDP.  Their verified normalized margins ranged
from `0.01534` to `0.08662`.  No word enumeration was launched for these
known-class cases.  This validates the early-stop policy and keeps the
two-machine budget focused on the surviving two-point mechanism.

### Exact dual exclusion of a common Wei metric

For the leading rational pair
`{(3/10,1,1),(5/2,1,1)}`, a Gordan--Stiemke dual SDP was added for the
four strict Lyapunov inequalities.  A random linear objective exposed four
numerical rank-one PSD multipliers with cancellation residual about
`1.11e-10`.  Forcing each forward multiplier to equal its transpose
multiplier was infeasible, so that tempting symmetry reduction was
discarded.

Solving the normalized dual with zero objective instead produced an
interior point: all four multipliers have numerical rank five, minimum
eigenvalue approximately `3.3287e-5`, and cancellation residual
`1.446e-16`.  Rounding the free affine coordinates at denominator
`10^8` and solving the 16 rational equality pivots exactly preserved
positive definiteness.  The frozen certificate now verifies:

- exact adjoint cancellation;
- exact trace normalization one;
- all 20 leading principal minors strictly positive by integer Bareiss
  determinants.

Consequently no real symmetric `R` can make the forward and transpose
Lyapunov gaps strict for both points.  Unlike the earlier zero SDP margin,
this is an exact exclusion of the tested common split-contraction/Wei
mechanism.  The reusable lesson is to rationalize an interior dual rather
than an exposed rank-one boundary point: the positive eigenvalue margin
makes exact affine projection robust.

### Exact physical target for the leading pair

The leading pair was lifted to the 32-dimensional number-conserving Fock
space before the arbitrary-word theorem was finished, so physical
realizability would not become a late blocker.  Exact row arithmetic for

`Gamma(B0)+Gamma(B0)^T+Gamma(B1)+Gamma(B1)^T`

has maximum diagonal-dominance requirement 44.  Therefore

`T=45I+Gamma(B0)+Gamma(B0)^T+Gamma(B1)+Gamma(B1)^T`

is real symmetric positive definite with minimum row margin one.  After
normalization by 49 it gives five strictly positive auxiliary-field
coefficients `(45,1,1,1,1)/49` and a Hermitian
`H=-Log(T/49)`.  Both atoms avoid the negative real spectral axis and
admit real one-particle logarithms.  The Gaussian block identity fails in
58 entries, first by 196 at `(0,0)`, proving that the target Hamiltonian is
interacting.  This closes the physical and positive-field gates
conditionally; sign-freeness still requires the independent arbitrary-word
determinant theorem.

### Exact Hodge reduction of the coupled tail

The signed grade-three sector is not an independent 10-state process.
For the common nonnegative grade-four gauge
`P=D wedge^4(B) D`, exact symbolic algebra found one fixed signed
permutation `H` such that, for every positive `p` and either orientation,

`wedge^2(P)=8 H wedge^3(B) H^T`.

Consequently every length-`n` word satisfies

`wedge^2(P_w)=8^n H wedge^3(W) H^T`

and

`chi3(W)+chi4(W)=8^(-n)[e2(P_w)+8^n trace(P_w)]`.

The symbolic atom identity and a mixed four-letter word replay both pass
exactly.  This replaces the loose Frobenius comparison by a five-state
nonnegative path problem.  A direct diagonal sign gauge of the equivalent
15-dimensional atoms `wedge^2(diag(P_i,8))` was tested and rejected:
the signed support graph contains inconsistent cycles (including a
negative diagonal entry), so a richer polyhedral/path-complete cone or a
path injection is required.  The reduction itself is exact and remains
the basis of subsequent tail searches.

### Boundary-first joint scan and the new rational pair

A boundary-focused two-point scan replaced the earlier
`{p=3/10,p=5/2}` lead with

`{(1/1000,1,1),(4/5,1,1)}`,

again including both transposes.  Each endpoint separately has a strict
common metric, but the four-letter joint common-metric optimum is
numerically zero.  The pair survived all 22,369,620 nonempty words through
depth 12; its exact minimum is `176/5`, already attained by the one-letter
high atom.  Its coupled Frobenius ratios remain too large for the old
single-norm tail proof, so that route was stopped.

The Hodge scalar profile was then exhausted through depth 14.  Depths
7--14 have relative minima

`1.0123978, 1.0040135, 1.0053965, 0.9969818, 0.9972372, 0.9984097,
0.9980791, 0.9986729`.

Every minimizer is a pure high word, up to the exact transpose tie.  The
depth-14 pass covered 268,435,456 words in about 304 seconds on ten
single-threaded workers while leaving two logical cores free.  No negative
Hodge scalar was found.

The degenerate anchor `p=0` was also exhausted through depth 20 for the
two-letter transpose alphabet.  Its determinant remained positive, and
the grade-three/four relative margin approached one from above.  However,
the lower-sector sum `chi1+chi2` is already negative at depth four for word
`1000`; individual exterior-sector positivity is therefore false and was
discarded as a proof route.

### Failed finite positive-state tail cones

Several cheap coupled-tail constructions were tested on the earlier
two-point pair and rejected before further optimization:

- one-letter and two-letter positive weighted-automaton simulations had
  unusably large growth factors;
- the direct 15-dimensional simplicial cone had negative entries;
- a two-state parity cone was infeasible;
- the exact chip factorization exposed a negative signed cycle, so no
  diagonal sign gauge can make the compound dynamics nonnegative.

These failures motivated metrics indexed by the current letter rather than
another enlarged entrywise-positive cone.

### Exact last-letter path metric and arbitrary-word positivity

For the new rational pair, an SDP with four symmetric metrics found margin
approximately `4.8273e-5` for all 16 labelled inequalities

`R_i-A_j^T R_j A_j > 0`.

Rounding every metric to denominator `10^9` preserved a wide exact
interior.  The frozen solver-independent certificate verifies, using
integer/rational arithmetic:

- all four metrics have inertia `(1,4)`;
- all 16 transition gaps are positive definite by Sylvester's criterion;
- four stored rational time vectors are timelike;
- all 16 inverse transitions preserve a coherent future orientation;
- every letter has determinant eight.

For a word `W=A_sn...A_s1`, the labelled inequalities telescope around the
cycle beginning at state `sn`, giving

`R_sn-W^T R_sn W > 0`.

The strict Stein inertia theorem gives exactly one simple eigenvalue of
`W` inside the unit disk.  Coherent Lorentz time orientation makes that
eigenvalue positive.  The other four eigenvalues are outside the unit
disk, and `det(W)=8^n>0`, hence

`det(I+W)>0`

for every nonempty word.  This is the first exact arbitrary-depth theorem
for the genuinely joint four-letter candidate.  It is a finite-state,
indefinite/path-complete extension of the common split-contraction
certificate; the coherent time-orientation determinant lemma is essential,
because contraction plus positive determinant alone does not fix the sign.
