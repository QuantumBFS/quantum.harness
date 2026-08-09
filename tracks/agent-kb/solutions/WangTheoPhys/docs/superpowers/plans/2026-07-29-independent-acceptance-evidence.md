# Independent Acceptance Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove self-report and scheduler-trust loops while closing every validated route over exact request translation, artifact safety, and grounded Library evidence.

**Architecture:** The experiment locks an energy reference value, normalization, and source artifact digest. Evidence contains separately addressed primary and repeat records, but repeat consistency remains `reported_only` until a trusted scheduler receipt exists. Route-aware validation guarantees energy/variance dependencies, finite backend-fixed numerics, infinite chi closure, correct XXZ coupling semantics, grounded Library paths, and single-link artifact reads.

**Tech Stack:** Python 3 standard library, JSON Schema draft 2020-12, `unittest`, optional `jsonschema` compatibility checks.

## Global Constraints

- Edit only `tracks/agent-kb/solutions/WangTheoPhys/`.
- Keep `gate.py` dependency-free and fail closed.
- Do not claim numerical or process independence that the public artifacts cannot establish.
- Reproduction cannot enter `all_required` without a preregistered nonce, runner identity, request/experiment digests, and trusted scheduler or registry attestation.
- Direct tests must run in a standalone `quantum.harness` checkout.
- Do not stage, commit, or push.

---

### Task 1: Contract the assurance boundary

**Files:**
- Modify: `gate.py`
- Modify: `contracts/experiment-v1.schema.json`
- Modify: `contracts/evidence-v1.schema.json`
- Modify: `contracts/validator-evidence-v1.schema.json`
- Create: `contracts/energy-reference-v1.schema.json`
- Test: `tests/test_gate.py`

**Interfaces:**
- Consumes: experiment `reference`, validator `policy`, and two execution records.
- Produces: exact `required_pass`, `reported_only`, and `backend_limited` policy sets.

- [x] Add a failing test that rejects a finite experiment whose reported-only validator is placed in `required_validator_ids`.
- [x] Run the direct test and confirm `reported_only` is unsupported before implementation.
- [x] Add strict reference/source validation and exact validator-policy closure.
- [x] Run the direct policy tests and confirm they pass.

### Task 2: Validate two distinct artifact chains

**Files:**
- Modify: `gate.py`
- Modify: `contracts/evidence-v1.schema.json`
- Test: `tests/test_gate.py`

**Interfaces:**
- Consumes: primary and repeat execution evidence plus exact artifact roles.
- Produces: reconstructed primary/repeat backend bundles and their semantic digests.

- [x] Add failing tests for a missing repeat artifact, reused execution handle, and reused raw artifact identity.
- [x] Run those tests and confirm the old six-artifact contract fails the new expectations.
- [x] Validate exact primary/repeat stream bindings, rebuild both normalized bundles, and reject identical handles/raw identities.
- [x] Run the artifact-chain tests and confirm they pass.

### Task 3: Derive acceptance without self-report loops

**Files:**
- Modify: `gate.py`
- Modify: `contracts/validator-evidence-v1.schema.json`
- Test: `tests/test_gate.py`

**Interfaces:**
- Consumes: primary energy, repeat energy, preregistered reference record, and reported raw diagnostics.
- Produces: benchmark and reproduction deltas that cannot be supplied by the primary raw record.

- [x] Add a coherent full-rebuild `energy=999` attack test that rewrites every downstream digest.
- [x] Confirm the old gate accepts the coherent attack.
- [x] Compute benchmark delta only from the locked reference and reproduction delta only from the repeat raw result; label raw-only diagnostics `reported_only`.
- [x] Confirm the coherent attack fails with `VALIDATOR_THRESHOLD_FAILED`.

### Task 4: Regenerate fixtures and public documentation

**Files:**
- Modify: `fixtures/valid-finite/**`
- Modify: `fixtures/valid-infinite/**`
- Modify: `README.md`
- Modify: `skill/tn-agent-workflow/SKILL.md`
- Modify: `contracts/reason-codes.md`
- Test: `tests/test_gate.py`

**Interfaces:**
- Consumes: finite exact reference `-8.749171017567908` and infinite analytic reference `0.25-ln(2)`.
- Produces: internally closed synthetic contract fixtures with explicit non-scientific status.

- [x] Add reference records and distinct repeat raw/result/stream artifacts for both fixtures.
- [x] Regenerate every semantic and byte digest from the final files.
- [x] Remove all wording that calls reported diagnostics fresh or independent.
- [x] Run direct evaluation for both fixtures and confirm `ACCEPTANCE_PASSED`.

### Task 5: Standalone and repository gates

**Files:**
- Modify: `tests/test_gate.py`

**Interfaces:**
- Consumes: optional discoverable TN-Agent checkout and optional `jsonschema`.
- Produces: standalone direct tests with compatibility checks skipped only when dependencies are absent.

- [x] Replace hard-coded sibling `.venv` assertions with optional discovery and `skipTest`.
- [x] Run `python3 -m unittest discover -s tracks/agent-kb/solutions/WangTheoPhys/tests -v`.
- [x] Run capsule `pytest`, repository `scripts` tests, Ruff format/check, schema validation, digest validation, and `git diff --check`.
- [x] Record remaining limitations: preregistration supplies an anchor, while the gate does not independently rerun the solver or verify MPS state certificates.

### Task 6: Remove scheduler trust from acceptance

**Files:**
- Modify: `gate.py`
- Modify: `fixtures/regenerate.py`
- Modify: `README.md`
- Modify: `skill/tn-agent-workflow/SKILL.md`
- Test: `tests/test_gate.py`

**Interfaces:**
- Consumes: separately addressed repeat raw/result/execution records.
- Produces: a `reported_only` reproduction delta that never affects `ACCEPTANCE_PASSED`.

- [x] Make `reproducibility` part of the route's reported-only validator set with null operator/threshold.
- [x] Remove it from every fixture's `required_validator_ids`.
- [x] Test whitespace/warning-only repeat differences and coherent repeat rebuilds without describing them as independent execution.
- [x] Document the exact trusted receipt fields required for future promotion.

### Task 7: Close exact route translation

**Files:**
- Modify: `gate.py`
- Modify: `contracts/experiment-v1.schema.json`
- Modify: `fixtures/valid-finite/experiment.json`
- Modify: `fixtures/regenerate.py`
- Test: `tests/test_gate.py`

**Interfaces:**
- Consumes: validated finite/infinite experiment documents.
- Produces: total `_expected_request` translation accepted by the main parser and worker validators.

- [x] Require `energy` and `variance` in every promoted experiment and JSON Schema route.
- [x] Remove finite experiment `min_sweeps` and `entropy_tolerance`; translate backend-fixed values to `0` and `null`.
- [x] Require infinite `fit.max_chi == max_bond_dim == chi_schedule[-1]`.
- [x] Parameterize exact route closure and verify `Jz=Jxy*Delta` in the
      optional sibling-worker compatibility probe. The superseding release
      gate restricts this standalone capsule to `Jxy=1` until that worker is
      inside the public trust root.

### Task 8: Ground Library identities

**Files:**
- Modify: `gate.py`
- Modify: `library/heuristic-v1.schema.json`
- Modify: `library/heuristics.jsonl`
- Modify: `library/README.md`
- Test: `tests/test_gate.py`

**Interfaces:**
- Consumes: repository-skill and contract-audit `uri`/SHA-256 pairs.
- Produces: descriptor-verified, path-confined Library records.

- [x] Add `uri` and `sha256` to contract-audit evidence.
- [x] Resolve repository-skill paths only relative to the repository root and contract-audit paths only relative to the team root.
- [x] Recompute identities and reject traversal, missing, hardlinked, symlinked, or tampered sources.
- [x] Document that append-only history needs an externally frozen Git tip.

### Task 9: Reject artifact hardlinks

**Files:**
- Modify: `gate.py`
- Test: `tests/test_gate.py`

**Interfaces:**
- Consumes: descriptor-opened registered artifacts.
- Produces: rejection when either pre-read or post-read `st_nlink != 1`.

- [x] Add a hardlinked artifact regression test.
- [x] Reject multi-link files before reading and after the stability check.
- [x] Run standalone, monorepo, schema, determinism, attack, repository scripts, Ruff, and diff gates.
