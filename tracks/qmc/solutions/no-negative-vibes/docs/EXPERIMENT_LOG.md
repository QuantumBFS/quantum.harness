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
