# Experiment log

Updated: 2026-07-28

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
