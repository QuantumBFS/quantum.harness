# QuantumBFS Capsule Release Blocker Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the final three independent-audit blockers so the WangTheoPhys capsule rejects unattested candidates, exposes only standalone-proven XXZ semantics, and binds Library record kinds to exact path classes.

**Architecture:** Keep experiment validation separate from scientific acceptance: `candidate` definitions remain valid preregistrations, but `evaluate()` rejects them until a trusted runner receipt or independently checkable state certificate exists. Restrict the public infinite route to `Jxy == 1.0` because the external worker is outside this PR's trust root. Validate Library kind/path pairs before descriptor-based content verification, then keep the existing URI confinement, file identity, and SHA-256 checks.

**Tech Stack:** Python 3 standard library, JSON Schema draft 2020-12, `unittest`, optional `jsonschema`, Ruff.

## Global Constraints

- Edit only `tracks/agent-kb/solutions/WangTheoPhys/`.
- Keep `gate.py` dependency-free, deterministic, bounded, and fail closed.
- Preserve `candidate` as a valid preregistration status, but never return `accepted: true` for it without a future attestation contract.
- A scientific rejection uses exit status `3` and emits `accepted: false`.
- The standalone capsule supports infinite XXZ only when `Jxy == 1.0`.
- Repository skills and method/workflow cards use `skills/<normalized-name>/SKILL.md`; contract audits use a regular file below `docs/` or `tests/` in the team directory.
- Run every direct test from a standalone `quantum.harness` checkout; optional TN-Agent integration may skip only when the sibling dependency is absent.
- Do not stage, commit, push, or update PR #209 until every release gate in Task 4 passes.

---

### Task 1: Reject unattested candidate acceptance

**Files:**
- Modify: `gate.py`
- Modify: `contracts/reason-codes.md`
- Modify: `README.md`
- Modify: `skill/tn-agent-workflow/SKILL.md`
- Test: `tests/test_gate.py`

**Interfaces:**
- Consumes: `validate_experiment(document) -> dict[str, object]` and its `problem_status` field.
- Produces: `evaluate(...)` rejection code `SCIENTIFIC_EVIDENCE_UNATTESTED`, exit status `3`, and JSON field `accepted: false` for a validated `candidate`.

- [ ] **Step 1: Write the synthetic-candidate attack test**

```python
def test_synthetic_candidate_cannot_self_report_scientific_acceptance(self) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        shutil.copytree(self.fixture("valid-finite"), root / "fixtures/valid-finite")
        experiment_path = root / "fixtures/valid-finite/experiment.json"
        experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
        experiment["problem"]["status"] = "candidate"
        experiment_path.write_text(json.dumps(experiment), encoding="utf-8")
        regenerate = load_regenerator()
        regenerate.SOLUTION_ROOT = root
        regenerate.write_fixture("valid-finite", regenerate.CONFIG["valid-finite"])
        with self.assertRaises(gate.GateError) as caught:
            gate.evaluate(
                gate.load_json_document(experiment_path),
                gate.load_json_document(root / "fixtures/valid-finite/evidence.json"),
                artifact_root=root / "fixtures/valid-finite/artifacts",
            )
        self.assertEqual(caught.exception.reason_code, "SCIENTIFIC_EVIDENCE_UNATTESTED")
        self.assertEqual(caught.exception.exit_code, 3)
        self.assertEqual(caught.exception.as_dict()["accepted"], False)
```

- [ ] **Step 2: Run the attack test and verify the current gate accepts the rebuilt candidate**

Run: `python3 -m unittest discover -s tracks/agent-kb/solutions/WangTheoPhys/tests -p 'test_gate.py' -k test_synthetic_candidate_cannot_self_report_scientific_acceptance -v`

Expected before implementation: FAIL because `evaluate()` reaches `ACCEPTANCE_PASSED` or because `SCIENTIFIC_EVIDENCE_UNATTESTED` is unregistered.

- [ ] **Step 3: Add the explicit trust guard**

```python
if experiment_summary["problem_status"] == "candidate":
    _fail(
        "SCIENTIFIC_EVIDENCE_UNATTESTED",
        "Candidate evidence lacks a trusted execution or state certificate",
        field="$.problem.status",
        exit_code=3,
    )
```

Add `SCIENTIFIC_EVIDENCE_UNATTESTED` to `GATE_REASON_CODES`. Make `GateError.as_dict()` add `"accepted": False` whenever `exit_code == 3`.

- [ ] **Step 4: Tighten public claims**

Document that `ACCEPTANCE_PASSED` means fixture contract closure only, primary energy and convergence remain unattested worker assertions, `candidate` evaluation is rejected, and this PR achieves no success tier of issue #133.

- [ ] **Step 5: Run candidate, CLI, reason-code, and fixture tests**

Run: `python3 -m unittest discover -s tracks/agent-kb/solutions/WangTheoPhys/tests -p 'test_gate.py' -k test_synthetic_candidate_cannot_self_report_scientific_acceptance -k test_valid_finite_and_infinite_evaluations -k test_reason_code_document_covers_the_executable_registry -v`

Expected: PASS; both `test_fixture` evaluations still return `ACCEPTANCE_PASSED`.

### Task 2: Restrict standalone infinite XXZ to unit Jxy

**Files:**
- Modify: `gate.py`
- Modify: `contracts/experiment-v1.schema.json`
- Modify: `README.md`
- Modify: `skill/tn-agent-workflow/SKILL.md`
- Modify: `docs/plans/2026-07-29-capsule-trust-closure-design.md`
- Modify: `library/heuristics.jsonl`
- Test: `tests/test_gate.py`

**Interfaces:**
- Consumes: `physics.model.couplings.Jxy` for `tenpy.infinite_1d.vumps`.
- Produces: runtime `UNSUPPORTED_ROUTE` and JSON Schema rejection for every value other than numeric `1.0`.

- [ ] **Step 1: Replace the non-unit positive test with a fail-closed test**

```python
def test_nonunit_jxy_is_outside_the_standalone_capsule_trust_root(self) -> None:
    experiment = self.load("valid-infinite/experiment.json")
    experiment["physics"]["model"]["couplings"]["Jxy"] = 2.0
    self.assert_reason(
        "UNSUPPORTED_ROUTE", lambda: gate.validate_experiment(experiment)
    )
```

The optional sibling integration test must assert the fixture's unit-`Jxy` request only; it must not use sibling code to broaden this PR's public route.

- [ ] **Step 2: Run the non-unit test and confirm the existing route accepts it**

Run: `python3 -m unittest discover -s tracks/agent-kb/solutions/WangTheoPhys/tests -p 'test_gate.py' -k test_nonunit_jxy_is_outside_the_standalone_capsule_trust_root -v`

Expected before implementation: FAIL because `validate_experiment()` returns `OK`.

- [ ] **Step 3: Enforce the runtime and Schema boundary**

```python
if capability_id == "tenpy.infinite_1d.vumps" and couplings["Jxy"] != 1.0:
    _fail(
        "UNSUPPORTED_ROUTE",
        "Standalone infinite XXZ is limited to Jxy=1",
        field="$.physics.model.couplings.Jxy",
    )
```

Set the JSON Schema property to `{"type": "number", "const": 1.0}`. Keep the documented Hamiltonian convention `Jz = Jxy * Delta`, but state that this PR exposes only the unit-`Jxy` slice until an attested worker implementation is part of the trust root.

- [ ] **Step 4: Update the hashed contract-audit record**

After revising `docs/plans/2026-07-29-capsule-trust-closure-design.md`, recompute its SHA-256 and update only the `contract_audit` evidence digest in `library/heuristics.jsonl`.

- [ ] **Step 5: Run route, Schema, Library, and fixture tests**

Run: `python3 -m unittest discover -s tracks/agent-kb/solutions/WangTheoPhys/tests -p 'test_gate.py' -k test_nonunit_jxy_is_outside_the_standalone_capsule_trust_root -k test_public_json_schemas_accept_all_promoted_fixtures -k test_library_is_append_only_and_cross_references_prior_records -v`

Expected: PASS.

### Task 3: Bind Library kinds to exact path classes

**Files:**
- Modify: `gate.py`
- Modify: `library/heuristic-v1.schema.json`
- Modify: `library/README.md`
- Test: `tests/test_gate.py`

**Interfaces:**
- Consumes: `source.kind`, `source.uri`, `evidence.kind`, and `evidence.uri`.
- Produces: stable `LIBRARY_RECORD_INVALID` before file-content verification when a kind/path pair is semantically invalid.

- [ ] **Step 1: Add kind/path-confusion attack tests**

```python
for section, kind, uri, root in (
    ("source", "repository_skill", "README.md", REPOSITORY_ROOT),
    ("evidence", "method_card", "README.md", REPOSITORY_ROOT),
    ("evidence", "workflow_card", "README.md", REPOSITORY_ROOT),
    ("evidence", "contract_audit", "README.md", SOLUTION_ROOT),
):
    record = copy.deepcopy(original)
    record[section]["kind"] = kind
    record[section]["uri"] = uri
    record[section]["sha256"] = file_sha256(root / uri)
    self.assert_reason("LIBRARY_RECORD_INVALID", lambda: validate_one(record))
```

- [ ] **Step 2: Run the tests and confirm correct-SHA root README files are currently accepted**

Run: `python3 -m unittest discover -s tracks/agent-kb/solutions/WangTheoPhys/tests -p 'test_gate.py' -k test_library_kind_and_path_must_match -v`

Expected before implementation: FAIL because `validate_library()` returns `OK` for at least one mutation.

- [ ] **Step 3: Implement a single runtime kind/path validator**

```python
SKILL_URI_PATTERN = re.compile(r"^skills/[a-z0-9][a-z0-9-]{0,63}/SKILL[.]md$")
AUDIT_URI_PATTERN = re.compile(r"^(?:docs|tests)/(?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]+$")


def _validate_library_kind_uri(kind: str, uri: str, field: str) -> None:
    pattern = (
        SKILL_URI_PATTERN
        if kind in {"repository_skill", "method_card", "workflow_card"}
        else AUDIT_URI_PATTERN
    )
    if pattern.fullmatch(uri) is None:
        _fail(
            "LIBRARY_RECORD_INVALID",
            "Library kind and path do not match",
            field=f"{field}.uri",
        )
```

Call this before `_validate_grounded_library_file()` for both source and evidence.

- [ ] **Step 4: Mirror the constraint in JSON Schema**

Make `source.kind` a constant `repository_skill`; constrain source URI to the skill pattern. Make `evidence.kind` an enum and use `if/then` branches so method/workflow cards use the skill pattern and contract audits use the `docs/`/`tests/` pattern.

- [ ] **Step 5: Run Library positive and negative tests**

Run: `python3 -m unittest discover -s tracks/agent-kb/solutions/WangTheoPhys/tests -p 'test_gate.py' -k test_library_is_append_only_and_cross_references_prior_records -k test_library_grounding_rejects_tamper_traversal_and_missing_files -k test_library_kind_and_path_must_match -v`

Expected: PASS.

### Task 4: Execute the release gate

**Files:**
- Modify only if a reproducible gate failure proves a scoped defect in Tasks 1-3.

**Interfaces:**
- Consumes: the complete WangTheoPhys public capsule.
- Produces: reproducible evidence that the capsule is ready to commit and update in PR #209.

- [ ] **Step 1: Run direct capsule unittest**

Run: `python3 -m unittest discover -s tracks/agent-kb/solutions/WangTheoPhys/tests -v`

Expected: all tests pass; only explicitly optional integration dependencies may skip.

- [ ] **Step 2: Run capsule pytest with the TN-Agent integration environment**

Run: `TN_AGENT_STARTER_ROOT=/Users/thomasjwang/Documents/GitHub/Projects/Agents/Tensor_Network/tn-agent-starter TN_AGENT_INTEGRATION_PYTHON=/Users/thomasjwang/Documents/GitHub/Projects/Agents/Tensor_Network/tn-agent-starter/.venv/bin/python python3 -m pytest tracks/agent-kb/solutions/WangTheoPhys/tests -q`

Expected: all capsule tests and subtests pass.

- [ ] **Step 3: Prove deterministic fixture regeneration**

Copy the capsule to two fresh temporary directories, run `fixtures/regenerate.py` in each, and compare every regular file byte-for-byte. The checked-in capsule must equal a fresh regeneration except for the implementation-plan documents, which are not generated artifacts.

- [ ] **Step 4: Simulate a standalone checkout**

Copy the repository without the sibling TN-Agent checkout, run direct unittest, and confirm only optional TN-Agent integration checks skip; candidate, unit-`Jxy`, and Library confusion tests must still execute and pass.

- [ ] **Step 5: Run the full harness suite and static gates**

Run: `python3 -m pytest -q`

Run: `ruff check tracks/agent-kb/solutions/WangTheoPhys`

Run: `ruff format --check tracks/agent-kb/solutions/WangTheoPhys`

Run: `git diff --check`

Expected: all pass.

- [ ] **Step 6: Inspect the exact diff and commit only the capsule**

Stage only `tracks/agent-kb/solutions/WangTheoPhys/`, verify `git diff --cached --check`, and commit with message `Close WangTheoPhys capsule trust boundaries`.

- [ ] **Step 7: Update existing PR #209 only after the commit and push succeed**

Push `challenge/agent-wangtheophys`, confirm PR #209 points to the pushed commit, and state explicitly in the PR description: fixture contract closure only, no fresh trusted solve, no issue #133 success tier, and `candidate` evidence remains scientifically unattested.
