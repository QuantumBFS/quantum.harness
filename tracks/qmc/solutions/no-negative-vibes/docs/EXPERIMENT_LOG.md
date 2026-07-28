# Experiment log

Updated: 2026-07-29

Every completed scientific experiment is appended here whether it succeeds,
fails, or only exposes an infrastructure defect. Large outputs live under the
ignored results tree; the committed entry carries enough provenance to rerun
and interpret them.

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
