# Challenge 15 Production VMC and Cluster Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Implement, attest, deploy, and execute a source-bound JAX x64
coordinate VMC workflow for `N=6,7,8`, with exact acceptance oracles,
append-only generations, deterministic reduction, and fail-closed cluster
ordering.

**Architecture:** Build candidate CPython 3.12 CPU/CUDA wheelhouses first, but
attest them only after all source changes are complete. Production training
publishes immutable generation chains; exact and independent coordinate
evaluations publish separate shards; reduction separates canonical scientific
payloads from execution receipts. Slurm wrappers are generated from audited
profiles and cannot submit a child size until the predecessor is synchronously
validated as semantically accepted.

**Tech Stack:** CPython 3.12; JAX/JAXlib 0.4.38 manylinux2014; bundled CUDA 12
from `jax-cuda12-plugin[with-cuda]`; Flax 0.10.2; Optax 0.2.4; NumPy 1.26.4;
SciPy 1.12.0; canonical JSON/SHA256; pytest; Slurm; glibc 2.17.

## Global Constraints

- Edit implementation only under
  `tracks/qmc/solutions/frustration-free/challenge-15/`.
- Formal training samples `|Psi_{L,M=0}|^2` on Qdeshell GPUs.
- Qdeshell `dzagnormal` rejects CPU-only work under the verified QOS; oracle,
  exact, reducer, and report stages run on LASG02/WUZH02 and cross controllers
  only through verified create-only bundles.
- `train_joint_sectors` remains smoke-only; ED remains acceptance-only.
- Preserve every immutable gate and seed/rank rule in current code.
- Five seeds `[0,1,2,3,4]` must be present at every expected rank and adjacent
  ranks must have identical paired seed sets.
- At least four final-rank seeds pass; current per-seed transition checks and
  two final consecutive doublings remain mandatory.
- Acceptance policy is code-owned and bound by one canonical policy digest.
- Every artifact binds policy, source, runtime, configuration, and parent/input
  hashes.
- Implementation Tasks 1-8 use TDD and end in focused local commits.
- Task 9 freezes source and creates target attestations. No source file may
  change afterward; a change restarts Task 9.
- Execution Tasks 10-14 create only ignored artifacts.
- `production-orchestrate-size` is the sole operator entry point for N6/N7/N8;
  low-level scripts and CLIs are internal transition contracts.
- Every transition runs recover-before-act and never resubmits when its exact
  canonical publisher output already validates.
- Orchestration metadata uses durable source-revision/state-key-addressed local
  storage plus create-only SSH backup on a distinct remote failure domain;
  sibling local copies are mirrors only and `/tmp` is disposable scratch.
- Source manifests hash `src/**/*.py`, `production/**/*.py`,
  `production/**/*.json`, `production/**/*.sh`, `production/**/*.sbatch`,
  `production/runtime/**/*.txt`, `production/runtime/**/*.in`,
  `tests/**/*.py`, `pyproject.toml`, and `uv.lock`.
- Do not push.

## Exact File Map

### Candidate runtime

- Modify `pyproject.toml`: retain `requires-python=">=3.12,<3.13"` and pin the
  accepted local dependency family.
- Modify `uv.lock`: resolve the CPython 3.12 JAX 0.4.38 local test stack.
- Create `production/runtime/cpu/requirements.in`.
- Create `production/runtime/cpu/requirements.txt`.
- Create `production/runtime/cuda12/requirements.in`.
- Create `production/runtime/cuda12/requirements.txt`.
- Create `production/runtime/build_candidate_wheelhouses.sh`.
- Create `production/runtime/install_offline.sh`.
- Create `production/runtime/verify_wheelhouse.py`.
- Create `production/runtime/runtime_smoke.py`.
- Create `tests/test_runtime_candidate.py`.
- Create `tests/test_jax_04_compat.py`.

### Policy, provenance, and append-only generations

- Create `src/challenge15/production_policy.py`.
- Create `src/challenge15/production_schema.py`.
- Create `src/challenge15/generations.py`.
- Create `src/challenge15/transfers.py`.
- Create `src/challenge15/finalization.py`.
- Create `src/challenge15/orchestrator.py`.
- Modify `src/challenge15/provenance.py`.
- Modify `src/challenge15/artifacts.py`.
- Create `tests/test_production_policy.py`.
- Create `tests/test_production_schema.py`.
- Create `tests/test_generations.py`.
- Create `tests/test_transfers.py`.
- Create `tests/test_finalization.py`.
- Create `tests/test_orchestrator_state_machine.py`.

### Reducer

- Create `src/challenge15/reducer.py`.
- Create `tests/test_reducer.py`.

### Batched model and cache

- Modify `src/challenge15/model.py`.
- Modify `src/challenge15/projector.py`.
- Modify `src/challenge15/carriers.py`.
- Create `src/challenge15/production_cache.py`.
- Create `tests/test_batched_model.py`.
- Create `tests/test_production_cache.py`.

### Production VMC

- Create `src/challenge15/production_vmc.py`.
- Modify `src/challenge15/vmc.py`.
- Create `tests/test_production_vmc.py`.
- Create `tests/test_coordinate_evaluation.py`.

### Exact evaluation

- Create `src/challenge15/exact_eval.py`.
- Modify `src/challenge15/oracle.py`.
- Modify `src/challenge15/fermions.py`.
- Create `tests/test_exact_eval_blocks.py`.
- Modify `tests/test_exact_acceptance.py`.

### CLI, cluster profiles, deployment, and Slurm

- Modify `src/challenge15/cli.py`.
- Create `src/challenge15/cluster_profile.py`.
- Create `production/config/base-n4-smoke.json`.
- Create `production/config/base-n6.json`.
- Create `production/config/base-n7.json`.
- Create `production/config/base-n8.json`.
- Create `production/slurm/profiles/qdeshell.json`.
- Create `production/slurm/profiles/lasg02.json`.
- Create `production/slurm/profiles/wuzh02.json`.
- Create `production/slurm/discover_wuzh02.py`.
- Create `production/slurm/common.sh`.
- Create `production/slurm/runtime-qdeshell.sbatch`.
- Create `production/slurm/runtime-lasg02.sbatch`.
- Create `production/slurm/oracle-lasg02.sbatch`.
- Create `production/slurm/train-qdeshell.sbatch`.
- Create `production/slurm/coordinate-qdeshell.sbatch`.
- Create `production/slurm/exact-lasg02.sbatch`.
- Create `production/slurm/render_wuzh02.py`.
- Create `production/slurm/submit_size.sh`.
- Create `production/slurm/submit_cross_size.sh`.
- Create `production/orchestrate/transfer_bundle.sh`.
- Create `production/orchestrate/transfer_bytes.sh`.
- Create `production/orchestrate/transfer_attestation_bootstrap.sh`.
- Create `production/orchestrate/transfer_runtime_set.sh`.
- Create `production/orchestrate/submit_once.sh`.
- Create `production/orchestrate/transfer_once.sh`.
- Create `production/orchestrate/backup_once.sh`.
- Create `production/orchestrate/submit_size.py`.
- Create `production/orchestrate/submit_cross_size.py`.
- Create `production/deploy/build_source_bundle.sh`.
- Create `production/deploy/upload_bundle.sh`.
- Create `production/deploy/dry_run.sh`.
- Create `production/deploy/deploy.sh`.
- Create `tests/test_cluster_profiles.py`.
- Create `tests/test_slurm_scripts.py`.
- Create `tests/test_production_cli.py`.
- Create `tests/test_orchestrator.py`.
- Modify `tests/test_end_to_end.py`.
- Modify `README.md`.

Generated wheel binaries, source manifests, attestations, numerical artifacts,
snapshots, receipts, venvs, and scheduler logs are ignored and never committed.

---

## Phase 1: Candidate Runtime Compatibility

### Task 1: Build CPython 3.12 candidate locks and local tests

**Files:** Candidate runtime files from the file map.

**Interfaces:**

- `verify_wheelhouse(profile: Literal["cpu","cuda12"], root: Path) ->
  WheelhouseReport`.
- `runtime_smoke(profile: str, expected_backend: str,
  source_manifest: Path | None) -> RuntimeSmoke`.
- This task produces no `challenge15.allowed-runtime.v1`.

- [ ] **Step 1: Write failing candidate tests**

```python
def test_candidate_is_cp312_manylinux2014_and_binary_only(candidate):
    assert candidate.python_version == "3.12"
    assert candidate.abis == ("cp312", "abi3")
    assert candidate.platform == "manylinux2014_x86_64"
    assert candidate.only_binary
    assert candidate.packages["jax"] == "0.4.38"
    assert candidate.packages["jaxlib"] == "0.4.38"
    assert not candidate.sdists


def test_cuda_lock_contains_bundled_runtime(cuda_lock):
    assert cuda_lock.requested == {"jax-cuda12-plugin[with-cuda]": "0.4.38"}
    assert "jax-cuda12-plugin" in cuda_lock.projects
    assert "jax-cuda12-pjrt" in cuda_lock.projects
    assert cuda_lock.nvidia_projects
    assert all(cuda_lock.hashes[name] for name in cuda_lock.nvidia_projects)
```

Run:

```bash
cd /home/footman/code/quantum.harness-challenge-15/tracks/qmc/solutions/frustration-free/challenge-15
uv run pytest -m "not production" \
  tests/test_runtime_candidate.py tests/test_jax_04_compat.py -q
```

Expected: RED because candidate files do not exist.

- [ ] **Step 2: Create exact input locks**

CPU `requirements.in`:

```text
jax==0.4.38
jaxlib==0.4.38
flax==0.10.2
optax==0.2.4
numpy==1.26.4
scipy==1.12.0
sympy==1.13.3
h5py==3.10.0
pytest==8.3.4
```

CUDA adds exactly:

```text
jax-cuda12-plugin[with-cuda]==0.4.38
```

Generate fully transitive `requirements.txt` files with hashes. The CUDA lock
must name and hash every NVIDIA wheel resolved by the extra.

- [ ] **Step 3: Implement constrained downloads**

`build_candidate_wheelhouses.sh` invokes:

```bash
python3.12 -m pip download \
  --dest "$OUTPUT/cpu" \
  --require-hashes \
  --requirement production/runtime/cpu/requirements.txt \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 312 \
  --abi cp312 \
  --abi abi3 \
  --only-binary=:all:
python3.12 -m pip download \
  --dest "$OUTPUT/cuda12" \
  --require-hashes \
  --requirement production/runtime/cuda12/requirements.txt \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 312 \
  --abi cp312 \
  --abi abi3 \
  --only-binary=:all:
```

The script rejects any unlisted file, sdist suffix, duplicate normalized
project, non-cp312/non-abi3 Python wheel, platform above manylinux2014, missing
hash, or dependency introduced by an unrequested extra.

- [ ] **Step 4: Build and test locally**

```bash
CANDIDATE_ROOT="$PWD/.production-build/candidate-jax-0.4.38-cp312"
test ! -e "$CANDIDATE_ROOT"
bash production/runtime/build_candidate_wheelhouses.sh \
  "$CANDIDATE_ROOT"
python production/runtime/verify_wheelhouse.py \
  --profile cpu --root "$CANDIDATE_ROOT/cpu"
python production/runtime/verify_wheelhouse.py \
  --profile cuda12 --root "$CANDIDATE_ROOT/cuda12"
uv run pytest -m "not production" \
  tests/test_runtime_candidate.py tests/test_jax_04_compat.py \
  tests/test_model.py tests/test_projector.py tests/test_pfaffian.py -q
```

Expected: both wheelhouse reports end `CANDIDATE_OK`; local API tests pass.
This is not target-node acceptance.

- [ ] **Step 5: Commit**

```bash
git -C /home/footman/code/quantum.harness-challenge-15 add \
  tracks/qmc/solutions/frustration-free/challenge-15/pyproject.toml \
  tracks/qmc/solutions/frustration-free/challenge-15/uv.lock \
  tracks/qmc/solutions/frustration-free/challenge-15/production/runtime \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_runtime_candidate.py \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_jax_04_compat.py
git commit -m "Build CPython 3.12 candidate runtimes"
```

---

## Phase 2: Policy and Append-Only Generations

### Task 2: Implement canonical policy, schemas, rank extensions, and discovery

**Files:** Policy/provenance/generation files from the file map.

**Interfaces:**

- `production_policy() -> Mapping[str, JSONValue]`.
- `policy_sha256() -> str`.
- `create_rank_extension(output_dir: Path, extension: RankExtension) -> Path`;
  filename is `<payload_sha256>.json`.
- `claim_seed_root(path: Path, owner: SeedOwner) -> Path`; creates the root and
  owner exactly once.
- `publish_snapshot(attempt: Path, snapshot: TrainingSnapshot) -> str`.
- `publish_generation(seed_root: Path, generation:
  TrainingGeneration) -> str`.
- `discover_unique_terminal_generation(seed_root: Path,
  expected_extensions: Sequence[str]) -> VerifiedGeneration`.

**Exact envelope and payload fields:**

```text
envelope: schema, payload, payload_sha256
seed-owner payload: seed, experiment_id, base_configuration_sha256,
expected_seed_set, owner_uuid, claimed_at_utc, claim_host, claim_process,
claim_nonce_sha256, policy_sha256, source_manifest_sha256,
runtime_attestations
rank-extension payload: particles, seed, experiment_id, base_configuration_sha256,
policy_sha256, source_manifest_sha256, runtime_attestations,
expected_seed_set, previous_rank, new_rank, parent_generation_sha256,
parent_parameter_sha256, parent_optimizer_state_sha256,
rank_extension_decision_sha256, embedding_algorithm, rank_growth_prng, reason,
created_by_git_revision
training-attempt payload: seed, rank, attempt_id, owner_sha256,
extension_sha256, started_from_snapshot_sha256, resource_override, status
recovery-receipt payload: seed, rank, attempt_sha256, stale_lock_sha256,
scheduler_query, scheduler_state, recovered_by, recovered_at_utc
```

`schema` is forbidden in every payload and nested payload object.

- [ ] **Step 1: Write RED policy and schema tests**

```python
def test_policy_digest_changes_for_no_acceptance_override():
    payload = production_policy()
    assert payload["seed_policy"]["seeds"] == [0, 1, 2, 3, 4]
    assert payload["rank_policy"]["required_rank_doublings"] == 2
    assert payload["vmc_diagnostics"]["minimum_effective_sample_size"] == 1000
    assert payload["vmc_diagnostics"]["maximum_split_rhat"] == 1.01
    assert payload["runtime_roles"] == [
        "training", "coordinate", "oracle", "exact", "reducer"
    ]
    assert set(payload["artifact_schemas"]) == {
        "challenge15.production-policy.v1",
        "challenge15.source-manifest.v1",
        "challenge15.allowed-runtime.v1",
        "challenge15.runtime-attestation-set.v1",
        "challenge15.runtime-set-copies.v1",
        "challenge15.runtime-set-publication-receipt.v1",
        "challenge15.attestation-bootstrap-transfer.v1",
        "challenge15.cluster-profile.v1",
        "challenge15.production-oracle.v1",
        "challenge15.seed-owner.v1",
        "challenge15.rank-extension.v1",
        "challenge15.rank-extension-decision.v1",
        "challenge15.training-attempt.v1",
        "challenge15.training-snapshot.v1",
        "challenge15.training-generation.v1",
        "challenge15.recovery-receipt.v1",
        "challenge15.resource-override.v1",
        "challenge15.identity-map.v1",
        "challenge15.submission-receipt.v1",
        "challenge15.orchestration-state-key.v1",
        "challenge15.orchestration-attempt-intent.v1",
        "challenge15.orchestration-transition.v1",
        "challenge15.orchestration-state-manifest.v1",
        "challenge15.output-promotion.v1",
        "challenge15.export-bundle.v1",
        "challenge15.import-bundle.v1",
        "challenge15.transfer-receipt.v1",
        "challenge15.dry-run-receipt.v1",
        "challenge15.deployment-receipt.v1",
        "challenge15.exact-evaluation-shard.v1",
        "challenge15.coordinate-evaluation-shard.v1",
        "challenge15.evaluation-receipt.v1",
        "challenge15.size-result.v1",
        "challenge15.reduction-receipt.v1",
        "challenge15.reduction-finalization.v1",
        "challenge15.terminal-selection.v1",
        "challenge15.cross-size-manifest.v1",
        "challenge15.final-report.v1",
        "challenge15.report-receipt.v1",
    }


def test_source_manifest_covers_all_executable_and_test_inputs(repo_root):
    manifest = build_source_manifest(repo_root)
    expected = tracked_matches(repo_root, (
        "src/**/*.py", "production/**/*.py", "production/**/*.json",
        "production/**/*.sh", "production/**/*.sbatch",
        "production/runtime/**/*.txt", "production/runtime/**/*.in",
        "tests/**/*.py", "pyproject.toml", "uv.lock",
    ))
    assert set(manifest.members) == expected


def test_extension_requires_both_parent_state_hashes(nonroot_extension):
    broken = replace(nonroot_extension, parent_optimizer_state_sha256=None)
    with pytest.raises(ValueError, match="parent optimizer"):
        validate_rank_extension(broken)


def test_every_extension_requires_matching_decision(root_extension):
    broken = replace(root_extension, rank_extension_decision_sha256=None)
    with pytest.raises(ValueError, match="rank extension decision"):
        validate_rank_extension(broken)


def test_root_decision_is_exact(root_decision):
    assert root_decision.current_rank is None
    assert root_decision.new_rank == 1
    assert root_decision.prior_reduction_sha256 is None
    assert root_decision.prior_finalization_sha256 is None
    assert root_decision.prior_import_receipt_sha256 is None
    assert root_decision.prior_transfer_receipt_sha256 is None
    assert root_decision.reason == "initial"


def test_schema_occurs_only_in_envelope(valid_envelope):
    assert set(valid_envelope) == {"schema", "payload", "payload_sha256"}
    assert "schema" not in valid_envelope["payload"]
```

- [ ] **Step 2: Write RED append/discovery adversarial tests**

Cover omitted extension, duplicate rank, skipped doubling, wrong reason, wrong
seed set, missing parent parameter hash, missing parent optimizer hash, forked
children, stale policy/source/runtime, malformed generation, symlink path,
existing destination, interrupted snapshot, a second `claim-seed`, extension
filename not equal to payload hash, and two owners. Add a full
`claim-seed -> root decision -> rank1 -> pending reduction/finalization -> decision -> rank2 ->
pending reduction/finalization -> decision -> rank4` test proving every
non-root extension validates decision seed, current/new ranks, prior reduction
and finalization, source, policy, role/controller runtime set, and base hash,
and proving `vmc-train` creates only children beneath the permanent seed root.
Assert malformed,
forked, duplicate, and stale trees raise rather than selecting a generation.

Run:

```bash
uv run pytest -m "not production" \
  tests/test_production_policy.py tests/test_production_schema.py \
  tests/test_generations.py -q
```

Expected: RED on missing modules.

- [ ] **Step 3: Implement create-only publication**

`claim-seed` uses exclusive `mkdir` for the seed and owner directories and
`O_CREAT|O_EXCL` for `owner/<payload_sha256>.json`. `vmc-train` refuses an
unclaimed root and never creates ownership. Use `mkdir` for attempt, generation,
and blob directories. Create manifests and snapshots with `O_CREAT|O_EXCL`;
`fsync` files and parent directories. Extensions are
`extensions/<payload_sha256>.json` and accept an output directory, never a
rank-named path. Do not create `shard.json`, latest pointers, aliases, symlinks,
or mutable indexes. Coordination locks are outside the artifact tree.

- [ ] **Step 4: Implement deterministic discovery**

Sort generation paths, validate every discovered generation, require one root
and one child per declared extension, reject forks/gaps/duplicates/stale
objects, and return the unique terminal rank. Ignore incomplete attempt
snapshots only because they are not generation objects.

- [ ] **Step 5: Run tests**

```bash
uv run pytest -m "not production" \
  tests/test_production_policy.py tests/test_production_schema.py \
  tests/test_generations.py tests/test_artifacts.py tests/test_cli.py -q
```

Expected: PASS; injected publication failures preserve all prior immutable
objects.

- [ ] **Step 6: Commit**

```bash
git -C /home/footman/code/quantum.harness-challenge-15 add \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/production_policy.py \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/production_schema.py \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/generations.py \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/provenance.py \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/artifacts.py \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_production_policy.py \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_production_schema.py \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_generations.py
git commit -m "Add append-only production generations"
```

---

## Phase 3: Deterministic Reducer

### Task 3: Separate canonical payloads from execution receipts

**Files:** `src/challenge15/reducer.py`, `tests/test_reducer.py`.

**Interfaces:**

- `reduce_size(expected_ranks: tuple[int,...], identity_map: Path,
  oracle: Path, generation_roots: Sequence[Path],
  exact_shards: Sequence[Path], coordinate_shards: Sequence[Path],
  prerequisite_terminal_selection: Path | None) -> Reduction`.
- `Reduction.canonical_payload: Mapping[str, JSONValue]`.
- `Reduction.execution_receipt: Mapping[str, JSONValue]`.
- `publish_reduction(result: Reduction, output_dir: Path,
  receipt_dir: Path) -> PublishedReduction`; publishes beneath
  `<output_dir>/<expected_ranks_sha256>/<payload_sha256>.json`.
- `finalize_reduction(reduction: Path, output_dir: Path) -> Path`; provisional
  output is
  `<output_dir>/N=<N>/base=<base_sha256>/expected=<expected_ranks_sha256>/<payload_sha256>.json`.
- `select_terminal(finalization: Path, output_dir: Path) -> Path`; requires an
  accepted provisional finalization and publishes
  `<output_dir>/N=<N>/base=<base_sha256>/<payload_sha256>.json`.
- `create_rank_extension_decision(prior_finalization: Path, seed: int,
  new_rank: int, output_dir: Path) -> Path`.

Exact additional payloads:

```text
identity-map: stage, particles, expected_ranks, expected_ranks_sha256,
expected_seeds, task_count, tasks, array_concurrency
submission-receipt: stage, identity_map_sha256, profile_sha256,
interpreter_sha256, submitted_at_utc, controller, scheduler_job_id,
array_spec, dependency_mode, correlation_id, scheduler_job_name,
scheduler_comment, script_sha256, input_sha256s, remote_claim_sha256
orchestration-attempt-intent: state_key_sha256,
transition_identity_sha256, attempt, action_kind, correlation_id,
source_controller, destination_controller, script_sha256,
canonical_argv_sha256, input_sha256s, profile_sha256,
deployment_receipt_sha256, runtime_set_sha256,
source_manifest_sha256, policy_sha256, base_configuration_sha256,
particles, seed, rank, parent_sha256s, expected_output_identities,
create_only_namespace_identities, scheduler_job_name, scheduler_comment,
remote_claim_path_identity, created_at_utc
orchestration-transition: state_key, state, attempt, input_sha256s,
output_sha256s, output_promotion_sha256s, import_receipt_sha256s,
transfer_receipt_sha256s,
scheduler_receipt_sha256s, outcome, created_at_utc
orchestration-state-key: particles, base_configuration_sha256, policy_sha256,
source_manifest_sha256, rank_ladder, rank_extension_policy_sha256, seed_set,
runtime_set_local_sha256, runtime_set_local_path_identity,
cpu_runtime_set_remote_sha256, cpu_runtime_set_remote_path_identity,
cpu_runtime_set_receipt_sha256, gpu_runtime_set_remote_sha256,
gpu_runtime_set_remote_path_identity, gpu_runtime_set_receipt_sha256,
prerequisite_terminal_selection_sha256,
cpu_controller, gpu_controller, cpu_profile_sha256, gpu_profile_sha256,
cpu_deployment_receipt_sha256, gpu_deployment_receipt_sha256,
cpu_results_root_identity, gpu_results_root_identity,
durable_state_root_base_identity, state_backup_uri_identity,
state_mirror_root_identity,
canonical_path_identities
orchestration-state-manifest: state_key_sha256, source_revision,
transition_receipt_sha256s, completion_marker_sha256s,
attempt_intent_sha256s, output_promotion_sha256s,
expected_remote_output_sha256s,
previous_state_manifest_sha256, backup_uri_identity, mirror_root_identity,
created_at_utc
output-promotion: state_key_sha256, transition_identity_sha256,
output_schema, output_payload_sha256, output_absolute_path_identity,
producer_intent_sha256, selector_kind, selector_namespace_identity,
candidate_computed_sha256, candidate_count, promoted_at_utc
reduction-finalization: particles, base_configuration_sha256, expected_ranks,
expected_ranks_sha256, selected_reduction_sha256, selected_reduction_path,
production_accepted, finalized_at_utc, finalized_by
terminal-selection: particles, base_configuration_sha256,
selected_expected_ranks_sha256, selected_finalization_sha256,
selected_reduction_sha256, production_accepted, selected_at_utc, selected_by
rank-extension-decision: seed, current_rank, new_rank,
prior_expected_ranks_sha256, prior_reduction_sha256,
prior_finalization_sha256, prior_import_receipt_sha256,
prior_transfer_receipt_sha256, decision, reason, decision_metrics
```

- [ ] **Step 1: Write RED classification tests**

```python
def test_missing_expected_identity_is_deterministic_pending(valid_inputs):
    result = reduce_size(expected_ranks=(1, 2, 4), **without_rank_seed(valid_inputs, 4, 3))
    assert result.canonical_payload["production_accepted"] is False
    assert result.canonical_payload["missing_identities"] == [
        {"kind": "exact", "rank": 4, "seed": 3}
    ]


@pytest.mark.parametrize("mutation", ["malformed", "duplicate", "unexpected", "stale"])
def test_invalid_input_hard_fails_without_output(tmp_path, valid_inputs, mutation):
    output_dir = tmp_path / "results"
    receipt_dir = tmp_path / "receipts"
    with pytest.raises(ValueError):
        publish_reduction(
            reduce_size(expected_ranks=(1, 2, 4), **mutate(valid_inputs, mutation)),
            output_dir,
            receipt_dir,
        )
    assert not output_dir.exists()
    assert not receipt_dir.exists()


def test_reduction_paths_are_content_addressed(tmp_path, valid_inputs):
    published = publish_reduction(
        reduce_size(expected_ranks=(1, 2, 4), **valid_inputs),
        tmp_path / "results",
        tmp_path / "receipts",
    )
    assert published.payload_path == (
        tmp_path / "results" / published.expected_ranks_sha256
        / f"{published.payload_sha256}.json"
    )
    assert published.receipt_path == (
        tmp_path / "receipts" / f"{published.receipt_sha256}.json"
    )
```

Add shuffled-input tests proving canonical payload bytes are identical while
receipts may differ. Add ambiguous-threshold tests proving pending. Add tests
that `(1,2,4)` and `(1,2,4,8)` reductions have distinct expected-rank hashes
and cannot overwrite; multiple provisional finalizations coexist under the
full `(N,base,expected-ranks)` key; terminal selection rejects pending and
selects one accepted provisional result; a
rank-extension decision must bind that prior reduction/finalization; and a
prerequisite rejects a provisional, pending, or absent terminal selection.

- [ ] **Step 2: Implement exact coverage semantics**

Require seeds exactly `(0,1,2,3,4)` at every expected rank, identical paired
sets, all declared rank extensions, current per-seed transition gates, and at
least four accepted final seeds. Recompute all gates from primitive metrics.

- [ ] **Step 3: Implement payload/receipt split**

Canonical payload excludes times, jobs, hostnames, devices, RSS, compile time,
and cache counters. Receipt includes those fields plus
`canonical_payload_sha256`. Invalid input publishes neither object.

- [ ] **Step 4: Implement versioning, finalization, and dynamic arrays**

Canonicalize the ordered expected-rank list and hash it. Build identity maps
from the exact rank/seed cross-product; derive `task_count` and Slurm array
range from map length. Rank 8 uses a distinct five-task map and submission
receipt. Publish provisional finalizations create-only, allow multiple
immutable selected-reduction hashes under one key, and let prerequisites
consume only one create-only accepted terminal selection.

- [ ] **Step 5: Run and commit**

```bash
uv run pytest -m "not production" \
  tests/test_reducer.py tests/test_finalization.py tests/test_train.py \
  tests/test_cli.py -q
git -C /home/footman/code/quantum.harness-challenge-15 add \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/reducer.py \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/finalization.py \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_reducer.py \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_finalization.py
git commit -m "Add strict deterministic production reduction"
```

Expected: PASS; only canonical payloads are byte-identical across executions.

---

## Phase 4: Batched Model and Cache

### Task 4: Define and implement the batched log-amplitude contract

**Files:** Batched model/cache files from the file map.

**Interfaces:**

```text
apply_batched(
  variables,
  spec,
  spinors: complex128[W,N,2],
  sectors: int32[2],
  valid_walkers: bool[W],
  carrier_block: int,
  quadrature_block: int
) -> BatchedLogAmplitude(
  log_amplitude: complex128[W,2],
  finite_nonzero: bool[W,2]
)
```

- [ ] **Step 1: Write RED value, derivative, zero, and mask tests**

Use `N=4`, sectors `[0,2]`, ranks `1,2`, three real walkers plus a masked
walker, and block sizes `(1,1)`, `(2,7)`, `(4,64)`. Compare complex log
amplitudes, reconstructed amplitudes, and every parameter derivative with the
scalar path. Exact zero must produce `(-inf+0j,false)` and no NaN.

- [ ] **Step 2: Implement immutable content-addressed cache**

Cache determinant blocks, orbital groups, `ProjectionGrid`, beta rotations,
alpha phases, sector tokens, and masks. Keys include particles, sectors,
orders, dtype, source digest, policy digest, and runtime profile.

- [ ] **Step 3: Implement deterministic blocked reduction**

Use padded static blocks and masks. Carrier and quadrature reductions use a
fixed pairwise tree independent of microbatch boundaries.

- [ ] **Step 4: Run and commit**

```bash
uv run pytest -m "not production" \
  tests/test_batched_model.py tests/test_production_cache.py \
  tests/test_model.py tests/test_projector.py tests/test_carriers.py -q
git -C /home/footman/code/quantum.harness-challenge-15 add \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/model.py \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/projector.py \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/carriers.py \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/production_cache.py \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_batched_model.py \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_production_cache.py
git commit -m "Add deterministic batched amplitudes"
```

Expected: PASS with metric and derivative equivalence, not only gate
equivalence.

---

## Phase 5: Production VMC and Independent Evaluation

### Task 5: Implement the complete VMC contract

**Files:** Production VMC files from the file map.

**Interfaces:**

`ProductionVMCConfig` has exactly:

```text
optimizer="adam"
learning_rate=0.001
steps=10000
weight_l0=0.5
weight_l2=0.5
chains_per_sector=32
walkers_per_chain=32
pilot_sweeps=500
burn_in_sweeps=2000
draws_per_update=16
thinning_sweeps=2
reequilibration_sweeps_after_update=4
refresh_log_amplitudes_after_update=true
checkpoint_interval_steps=100
final_evaluation_chains_per_sector=32
final_evaluation_burn_in_sweeps=5000
final_evaluation_draws_per_chain=4096
final_evaluation_thinning_sweeps=4
walker_microbatch=64
carrier_block=8
quadrature_block=64
```

`train_rank(config: ProductionVMCConfig, extension: RankExtension,
destination: Path, owner: SeedOwner) -> TrainingGeneration`; `destination`
must already be the uniquely claimed seed root. The function creates only
child attempts, snapshots, blobs, and generations with exclusive semantics.

`evaluate_coordinates(config: ProductionVMCConfig, generation:
VerifiedGeneration, destination: Path) -> CoordinateEvaluationShard`.

- [ ] **Step 1: Write RED config and ownership tests**

Test every field, positive-count validation, weights summing to one, walkers
per sector derived as `chains_per_sector*walkers_per_chain=1024`, mandatory
`--extension`, pre-existing uniquely claimed destination, rejection of an
absent or newly created seed root, owner
mismatch, parent parameter/optimizer mismatch, and root/non-root behavior.
Assert state shape `[2,32,32,N,2]`, log-amplitude shape `[2,32,32]`, proposal
state `[2,32]`, and independent per-chain PRNG/proposal streams.

- [ ] **Step 2: Write RED estimator tests**

For `D` draws, score leaf shape is `complex128[D,2,*parameter_shape]`; output
gradient exactly matches the real parameter pytree. Test:

```text
D/(D-1) * (mean(conj(O)*V) - mean(conj(O))*mean(V))
```

against a hand-computed `D=3` fixture. Assert documentation/schema calls it
`score_covariance_finite_chain`, never `unbiased_gradient`.
For the production fixture assert
`D=32*32*16=16384` per sector, lexicographic flattening of chain/walker/draw,
and split-Rhat/autocorrelation computed from 32 chain-grouped time series,
never the flattened gradient stream.

- [ ] **Step 3: Write RED lifecycle tests**

Verify pilot, burn-in, frozen widths, retained draws, update, full
log-amplitude refresh, exactly four re-equilibration sweeps, deterministic PRNG
splits, snapshot interval, resume equivalence, and independent final PRNG
namespace with no state mutation.

- [ ] **Step 4: Write RED gap-uncertainty tests**

Use independent sector-chain fixtures and assert
`Var_MC(E2-E0)=Var_MC(E2)+Var_MC(E0)`. For paired seed vectors assert
`Var(mean(E2-E0))=(s22+s00-2*s02)/K`; for rank changes assert
`SE(mean(d))=sqrt(sample_variance(d)/K)`. Reused sector chains, unpaired
optimizer seed identities, `K<2`, and nonfinite covariance must be pending.

- [ ] **Step 5: Implement code-owned gates**

Update gate: all values finite, at least two retained values per sector, and
total acceptance in `[0.20,0.80]`.

Final evaluation gates: at least four chains; converged autocorrelation;
ESS at least `1000`; split `Rhat <= 1.01`; local and total acceptance each in
`[0.20,0.80]`; finite estimates/errors/intervals/covariance; estimate inside
its 95% interval. Config/CLI cannot override these values.

Coordinate evaluation publishes a separate
`challenge15.evaluation-receipt.v1`; tests assert exact `stage`, `identity`,
`shard_sha256`, timing, controller/device, RSS, compile, elapsed, and cache
fields and prove those execution fields are absent from the canonical shard.

- [ ] **Step 6: Implement OOM-retry equivalence**

Only `walker_microbatch`, `carrier_block`, and `quadrature_block` may change.
Total walkers/draws, chains, PRNG keys, update schedule, thinning, and
accumulation tree remain fixed. Tests compare every training and evaluation
metric across block layouts. A walker-count change must change
`base_configuration_sha256`.

- [ ] **Step 7: Run and commit**

```bash
uv run pytest -m "not production" \
  tests/test_production_vmc.py tests/test_coordinate_evaluation.py \
  tests/test_batched_model.py tests/test_vmc.py tests/test_train.py -q
git -C /home/footman/code/quantum.harness-challenge-15 add \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/production_vmc.py \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/vmc.py \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_production_vmc.py \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_coordinate_evaluation.py
git commit -m "Add production coordinate VMC"
```

Expected: PASS. Statistical production tests remain marked `production` and
are not claimed by this local command.

---

## Phase 6: Exact Evaluation

### Task 6: Implement static exact shards with metric equivalence

**Files:** Exact evaluation files from the file map.

**Interfaces:**

- `evaluate_exact_shard(oracle: VerifiedOracle, generation:
  VerifiedGeneration, determinant_block: int, carrier_block: int,
  quadrature_block: int, destination: Path) -> ExactEvaluationShard`.

- [ ] **Step 1: Write RED blocked metric tests**

For `N=4`, compare determinant blocks `1,7,256`, carrier blocks `1,2`, and
quadrature blocks `1,13,64`. Compare normalized coefficients, both energies,
both `Var(H_LLL)`, both overlaps, both target-`L` residuals, all quadrature
changes, all span singular values, and span ranks. A gate-only comparison is
insufficient.

- [ ] **Step 2: Implement static padded kernels and cache**

Use ordered determinant blocks and validity masks. Never materialize a full
determinant-square Gram matrix. Publish one create-only exact shard per
`(rank,seed)`.

Publish a separate `challenge15.evaluation-receipt.v1` for every exact shard;
tests bind its `identity` and `shard_sha256` while allowing timing/device/RSS/
compile/cache values to differ across reruns.

- [ ] **Step 3: Implement ambiguous classification**

If layouts disagree beyond metric tolerance or straddle any gate threshold,
mark that identity pending. Nonfinite or malformed metrics hard fail.

- [ ] **Step 4: Run and commit**

```bash
uv run pytest -m "not production" \
  tests/test_exact_eval_blocks.py tests/test_exact_acceptance.py \
  tests/test_oracle.py tests/test_fermions.py -q
git -C /home/footman/code/quantum.harness-challenge-15 add \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/exact_eval.py \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/oracle.py \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/fermions.py \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_exact_eval_blocks.py \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_exact_acceptance.py
git commit -m "Add metric-stable exact shards"
```

---

## Phase 7: CLI, Profiles, and Slurm

### Task 7: Implement exact CLI contracts and audited wrappers

**Files:** CLI/cluster/deployment/Slurm files from the file map.

**CLI contracts:**

```text
policy --output PATH --create-only
source-manifest --root PATH --policy PATH --output PATH --require-clean
verify-execution-inputs --source-manifest PATH --runtime-set PATH
  --role {training,coordinate,oracle,exact,reducer}
  --controller {qdeshell,lasg02,wuzh02}
runtime-attest --role {training,coordinate,oracle,exact,reducer}
  --controller {qdeshell,lasg02,wuzh02}
  --profile {cpu,cuda12} --wheelhouse PATH --source-manifest PATH
  --policy PATH --expected-backend {cpu,gpu} --output-dir PATH --create-only
runtime-attestation-set --particles N
  --training-controller qdeshell --training PATH
  --coordinate-controller qdeshell --coordinate PATH
  --oracle-controller CONTROLLER --oracle PATH
  --exact-controller CONTROLLER --exact PATH
  --reducer-controller CONTROLLER --reducer PATH
  --output-dir PATH --create-only
runtime-set-verify-copies --runtime-set-local PATH
  --runtime-set-local-sha256 HEX --cpu-runtime-set-remote PATH
  --cpu-runtime-set-receipt PATH --gpu-runtime-set-remote PATH
  --gpu-runtime-set-receipt PATH --cpu-controller NAME
  --gpu-controller qdeshell
runtime-set-copy --manifest PATH
  --field {local_path,local_sha256,cpu_remote_path,cpu_receipt,
           gpu_remote_path,gpu_receipt}
runtime-set-publication-receipt --controller NAME
  --deployment-receipt PATH --controller-local-path PATH
  --runtime-set-sha256 HEX --source-manifest PATH --policy PATH
  --output-dir PATH --create-only
orchestration-attempt-intent --state-key PATH --transition-identity PATH
  --attempt INT --action-kind {slurm,transfer,backup,local}
  --source-controller NAME --destination-controller NAME
  --script PATH --canonical-argv-sha256 HEX --input-sha256 HEX
  --profile PATH --deployment-receipt PATH --runtime-set-sha256 HEX
  --source-manifest PATH --policy PATH --base-config PATH
  [--particles N --seed S --rank R] [--parent-sha256 HEX]...
  --expected-output-identity IDENTITY --create-only-namespace PATH
  --remote-claim-root PATH
  --output-dir PATH --create-only
oracle --particles N --policy PATH --source-manifest PATH
  --runtime-attestations PATH --output-dir PATH --create-only
claim-seed --particles N --seed S --base-config PATH --policy PATH
  --source-manifest PATH --runtime-attestations PATH
  --destination PATH --owner-uuid UUID --create-only
rank-extension --particles N --seed S --base-config PATH --policy PATH
  --source-manifest PATH --runtime-attestations PATH --reason REASON
  --output-dir PATH --create-only
rank-extension --particles N --seed S --base-config PATH --policy PATH
  --source-manifest PATH --runtime-attestations PATH --reason REASON
  --parent-generation PATH --decision PATH
  --output-dir PATH --create-only
rank-extension --particles N --seed S --base-config PATH --policy PATH
  --source-manifest PATH --runtime-attestations PATH
  --reason rank_convergence_pending --parent-generation PATH
  --decision PATH --output-dir PATH --create-only
rank-extension-decision --seed S --current-rank none --new-rank 1
  --base-config PATH --reason initial --policy PATH --source-manifest PATH
  --runtime-attestations PATH --output-dir PATH --create-only
rank-extension-decision --seed S --current-rank R --new-rank R2
  --base-config PATH --prior-reduction PATH --prior-finalization PATH
  --prior-import-receipt PATH --prior-transfer-receipt PATH
  --reason {scheduled_initial_ladder,rank_convergence_pending}
  --policy PATH --source-manifest PATH
  --runtime-attestations PATH --output-dir PATH --create-only
discover-generation --seed-root PATH --extension-root PATH --expected-ranks CSV
  --policy PATH --source-manifest PATH --runtime-attestations PATH
  --print-manifest
resource-override --extension PATH --attempt PATH --reason oom
  --walker-microbatch INT --carrier-block INT --quadrature-block INT
  --output-dir PATH --create-only
vmc-train --base-config PATH --extension PATH --policy PATH
  --source-manifest PATH --runtime-attestations PATH --owner PATH
  --destination PATH --create-only
vmc-train --base-config PATH --extension PATH --policy PATH
  --source-manifest PATH --runtime-attestations PATH --owner PATH
  --resource-override PATH --destination PATH --create-only
exact-shard --oracle PATH --generation PATH --policy PATH
  --source-manifest PATH --runtime-attestations PATH --destination PATH
  --receipt-dir PATH --determinant-block 256 --carrier-block 8
  --quadrature-block 64 --create-only
coordinate-shard --generation PATH --base-config PATH --policy PATH
  --source-manifest PATH --runtime-attestations PATH --destination PATH
  --receipt-dir PATH --create-only
identity-map --stage STAGE --particles N --expected-ranks CSV
  --expected-seeds 0,1,2,3,4 --array-concurrency INT
  --input-root PATH --output-dir PATH --create-only
identity-map-count --identity-map PATH
cumulative-reducer-identity-map --particles N --expected-ranks CSV
  --new-rank R --expected-seeds 0,1,2,3,4
  --new-coordinate-root PATH --new-exact-root PATH
  [--previous-cycle-receipt PATH] --output-dir PATH --create-only
cycle-ranks --previous-cycle-receipt PATH --new-rank INT --print-tsv
accepted-terminal-identity-map --terminal-selection PATH
  --provisional-finalization PATH --reduction PATH
  --runtime-attestation-set PATH --output-dir PATH --create-only
runtime-set-identity-map --runtime-attestation-set PATH
  --output-dir PATH --create-only
reduce-size --particles N --expected-ranks CSV --expected-seeds 0,1,2,3,4
  --identity-map PATH
  --oracle PATH --training-root PATH --exact-root PATH --coordinate-root PATH
  --policy PATH --source-manifest PATH --runtime-attestations PATH
  --output-dir PATH --receipt-dir PATH --create-only
reduce-size --particles N --expected-ranks CSV --expected-seeds 0,1,2,3,4
  --identity-map PATH
  --oracle PATH --training-root PATH --exact-root PATH --coordinate-root PATH
  --policy PATH --source-manifest PATH --runtime-attestations PATH
  --prerequisite-terminal-selection PATH
  --output-dir PATH --receipt-dir PATH --create-only
finalize-reduction --reduction PATH --policy PATH --source-manifest PATH
  --reduction-sha256 HEX --runtime-attestations PATH
  --output-dir PATH --create-only
select-terminal --finalization PATH --policy PATH --source-manifest PATH
  --runtime-attestations PATH --output-dir PATH --create-only
finalization-status --finalization PATH --print
validate-prerequisite --particles N --terminal-selection PATH
  --terminal-selection-sha256 HEX --policy PATH --source-manifest PATH
  --runtime-attestations PATH
export-bundle --bundle-role ROLE --source-controller NAME --source-root PATH
  --artifacts-from PATH --policy PATH --source-manifest PATH
  --runtime-attestations PATH --output-dir PATH --create-only
import-bundle --bundle PATH --destination-controller NAME
  --destination-root PATH --profile PATH --output-dir PATH --create-only
import-member --import PATH --kind KIND --print-path
transfer-import --receipt PATH --print-path
orchestration-output --transition-receipt PATH --field FIELD
output-promotion --state-key PATH --transition-intent PATH
  --canonical-output PATH --expected-identity IDENTITY
  --publisher KIND --controller NAME --output-dir PATH --create-only
select-published --transition-intent PATH --publisher KIND
  --create-only-namespace PATH --promotion-output-dir PATH
  --print {none,path}
terminal-member --terminal-selection PATH
  --kind {provisional-finalization,reduction} --print-path
verify-transfer --export PATH --import PATH --receipt PATH
  --policy PATH --source-manifest PATH --runtime-attestations PATH
transfer-receipt --export PATH --import PATH --source-controller NAME
  --destination-controller NAME --policy PATH --source-manifest PATH
  --runtime-attestations PATH --output-dir PATH --create-only
bootstrap-export --allowed-runtime PATH --source-manifest PATH --policy PATH
  --source-deployment-receipt PATH --destination-deployment-receipt PATH
  --source-controller NAME --destination-controller NAME
  --output-dir PATH --create-only
bootstrap-import --bundle PATH --allowed-runtime-sha256 HEX
  --source-manifest PATH --policy PATH --source-deployment-receipt PATH
  --destination-deployment-receipt PATH --output-dir PATH --create-only
reduce-cross-size --n6-terminal-selection PATH --n7-terminal-selection PATH
  --n8-terminal-selection PATH --runtime-attestation-set-n6 PATH
  --runtime-attestation-set-n7 PATH --runtime-attestation-set-n8 PATH
  --n8-provisional-finalization PATH --n8-reduction PATH
  --n8-import-receipt PATH --n8-transfer-receipt PATH
  --policy PATH --source-manifest PATH
  --output-dir PATH --receipt-dir PATH --create-only
report --cross-size-manifest PATH --policy PATH --source-manifest PATH
  --runtime-attestation-set-n6 PATH --runtime-attestation-set-n7 PATH
  --runtime-attestation-set-n8 PATH
  --n8-provisional-finalization PATH --n8-reduction PATH
  --n8-import-receipt PATH --n8-transfer-receipt PATH
  --output-dir PATH --receipt-dir PATH --create-only
```

For `vmc-train`, `--destination` must exist and contain the unique validated
seed-owner envelope; `--create-only` governs new child attempts, snapshots,
blobs, and generations only and never the seed root.

On success, `reduce-size` writes exactly
`<payload_sha256>\t<absolute_payload_path>\n` to stdout and all diagnostics to
stderr. `finalize-reduction` requires both returned values and rehashes the
exact path; no directory scan or uniqueness inference is implemented.

Internal-only `submit_size.sh` requires exactly:

```text
--particles N --expected-ranks CSV --expected-seeds 0,1,2,3,4
--prerequisite-terminal-selection PATH (omit only for N=6)
--prerequisite-terminal-selection-sha256 HEX (omit only for N=6)
--cpu-profile PATH --gpu-profile PATH
--runtime-attestations PATH --runtime-attestations-sha256 HEX
--cpu-deployment-receipt PATH --gpu-deployment-receipt PATH
--source-manifest PATH --source-manifest-sha256 HEX
--policy PATH --policy-sha256 HEX
--cpu-results-root PATH --gpu-results-root PATH
--transfer-work-root PATH --create-only
```

The script rejects omitted, extra, or mismatched digest arguments.
`runtime-attest` installs only from the supplied wheelhouse, then runs:

```bash
python -m pytest -m production \
  tests/test_runtime_candidate.py tests/test_jax_04_compat.py \
  tests/test_batched_model.py tests/test_production_vmc.py \
  tests/test_coordinate_evaluation.py -q
```

It stores the pytest report SHA256 in the attestation. Validation commands
elsewhere use `pytest -m "not production"` and cannot satisfy this gate.

- [ ] **Step 1: Write RED CLI tests**

Test every required flag, omission of prerequisite flags only for `N=6`,
extension omission, expected-rank omission, unexpected ranks, stale digest,
create-only conflict, prerequisite particle mismatch, pending/provisional-only
predecessor, wrong role/controller attestation, and deployment interpreter
mismatch.

```python
def test_allowed_runtime_requires_immutable_role_and_controller(attestation):
    assert attestation.payload["role"] in {
        "training", "coordinate", "oracle", "exact", "reducer"
    }
    assert attestation.payload["controller"] in {
        "qdeshell", "lasg02", "wuzh02"
    }
    assert attestation.payload["attestation_test_members"]
    assert all(
        set(member) == {"nodeid", "test_file_sha256", "result_sha256"}
        for member in attestation.payload["attestation_test_members"]
    )
```

- [ ] **Step 2: Add exact Qdeshell profile**

Profile values:

```text
partition dzagnormal
account giggleliu
qos user_jiangweiqi
nodes 1
ntasks 1
cpus-per-task 8
gres gpu:NVIDIAA80080GBPCIeLC:1
mem 60000M
time 24:00:00
training array 0-4%5
DefMemPerCPU evidence 7897M
project /work/share/giggleliu/jiangweiqi/quantum.harness
results /work/share/giggleliu/jiangweiqi/results/challenge15
```

Record `sacctmgr` evidence for account `giggleliu`, partition `dzagnormal`,
QOS `user_jiangweiqi`, and the passing exact `sbatch --test-only` GPU shape.
Add a negative profile test proving CPU-only Qdeshell stages are rejected.

```bash
ssh qdeshell 'sbatch --test-only --partition=dzagnormal --account=giggleliu --qos=user_jiangweiqi --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=60000M --time=24:00:00 --gres=gpu:NVIDIAA80080GBPCIeLC:1 --wrap=true'
```

Expected: test-only acceptance. The profile records observed
`DefMemPerCPU=7897M` as evidence, while the job request remains exactly
`--mem=60000M`. This Task 7 probe validates resources only; final wrapper
scripts are tested only after source freeze in Phase 10.

- [ ] **Step 3: Add exact LASG02 profile**

Profile values:

```text
partition ihicnormal
account chenkun2025
qos user_student090
nodes 1
ntasks 1
cpus-per-task 24
mem 80000M
time 24:00:00
exact array derived from identity-map task_count, concurrency 1
project /public/home/student090/quantum.harness
results /public/home/student090/results/challenge15
```

- [ ] **Step 4: Discover and commit WUZH02 profile before use**

```bash
ssh wuzh02 'set -euo pipefail; scontrol show partition -o; sacctmgr -n -P show assoc where user=$USER format=Account,Partition,QOS,GrpTRES,MaxTRES; nproc; free -m; pwd; python3.12 --version' \
  > /tmp/challenge15-wuzh02-facts.txt
python production/slurm/discover_wuzh02.py \
  --facts /tmp/challenge15-wuzh02-facts.txt \
  --required-cores 128 \
  --required-memory-mib 500000 \
  --output production/slurm/profiles/wuzh02.json
rm -- /tmp/challenge15-wuzh02-facts.txt
uv run pytest -m "not production" tests/test_cluster_profiles.py -q
```

The `/tmp` facts file is disposable discovery scratch; it is never an
orchestration input or state location.

Expected: a complete profile with exact partition/account/QOS/nodes/tasks/
CPUs/memory/time/project/results fields and no guessed values. If SSH, Python
3.12, approved-root, or capacity evidence is missing, stop; do not use WUZH02.

- [ ] **Step 5: Implement safe wrappers**

Qdeshell wrappers contain exact `#SBATCH` values above, array concurrency, and
thread variables set to `8`. LASG02 wrappers contain exact values above and
thread variables set to `24`. Both validate scheduler environment, approved
roots, source/policy/role-runtime hashes, unique ownership, and guarded scratch.
Every wrapper validates a deployment receipt, resolves its absolute
interpreter, re-fingerprints it, and invokes
`"$INTERPRETER" -m challenge15.cli`; tests reject bare `python`,
`python3`, and `python3.12`. WUZH02 wrappers are rendered only from its
validated profile.

- [ ] **Step 6: Implement create-only transfer boundary**

Exact payload fields:

```text
allowed-runtime: profile, role, controller, python_version, python_abi,
platform_tag, minimum_glibc, packages, wheel_sha256,
source_manifest_sha256, policy_sha256, backend, x64_enabled,
device_platforms, cuda_driver, smoke_payload_sha256,
attestation_test_members, attested_hostname_class, attested_at_utc
runtime-attestation-set: set_name, particles, roles; roles has exactly
training, coordinate, oracle, exact, reducer and each entry has controller,
allowed_runtime_sha256, deployment_receipt_sha256, backend
runtime-set-copies: particles, payload_sha256, role_map_sha256,
local_path_identity, local_sha256, cpu_controller,
cpu_remote_path_identity, cpu_remote_sha256, cpu_resolving_receipt_sha256,
gpu_controller, gpu_remote_path_identity, gpu_remote_sha256,
gpu_resolving_receipt_sha256
runtime-set-publication-receipt: controller, deployment_receipt_sha256,
controller_local_path_identity, payload_sha256, role_map_sha256,
source_manifest_sha256, policy_sha256, published_at_utc
attestation-bootstrap-transfer: source_controller, destination_controller,
role, allowed_runtime_sha256, source_manifest_sha256, policy_sha256,
source_deployment_receipt_sha256, destination_deployment_receipt_sha256,
export_bundle_sha256, import_bundle_sha256, verified_at_utc
export-bundle: bundle_role, source_controller, source_root,
source_artifact_sha256, member_manifest, sha256sums_sha256, bundle_sha256,
created_at_utc
import-bundle: bundle_sha256, destination_controller, destination_root,
member_manifest, imported_artifact_sha256, verified_at_utc
transfer-receipt: direction, export_bundle_sha256, import_bundle_sha256,
source_controller, destination_controller, source_identity,
destination_identity, partial_path, final_path, bytes,
attempt_intent_sha256, correlation_id, remote_claim_sha256,
started_at_utc, verified_at_utc
dry-run-receipt: profile_sha256, bundle_sha256, destination, interpreter,
interpreter_sha256, scheduler_test, validated_at_utc
deployment-receipt: dry_run_receipt_sha256, profile_sha256, bundle_sha256,
deployment_root, interpreter, interpreter_sha256, installed_wheel_sha256,
deployed_at_utc
evaluation-receipt: stage, identity, shard_sha256, started_at_utc,
finished_at_utc, hostname, controller, device, peak_rss_mib,
compile_seconds, elapsed_seconds, cache_counters
```

`transfer_bundle.sh` first persists the transfer attempt intent, then delegates
exactly once to remote `transfer_once.sh`; direct copy invocation is forbidden.
The remote wrapper creates sorted `SHA256SUMS`, uploads to
`.partial.<bundle_sha256>.<uuid>` with exclusive creation, remotely verifies
all members and source/destination identity, atomically renames to
`imports/<bundle_sha256>`, publishes import and transfer receipts, then
synchronously verifies the fetched receipt. Tests cover interrupted partials,
stale policy/source/runtime, duplicate final paths, corrupt members, wrong
controller/root, and successful round-trip. No cross-controller `afterok` is
permitted.

`transfer_bytes.sh` is the explicit-collation adapter: it persists attempt
intent, delegates byte movement to `transfer_once.sh`, validates that remote
receipt, and prints the destination bundle path. It never invokes a copy
primitive directly. It does not run `import-bundle`; callers still invoke
`import-bundle`, `transfer-receipt`, and `verify-transfer` explicitly.

- [ ] **Step 7: Add synchronous predecessor gate**

`submit_size.sh N=7` calls `validate-prerequisite --particles 6` on an
immutable terminal selection and submits nothing unless the selected accepted
provisional finalization and canonical payload hashes match. `N=8` similarly
validates the N7 terminal selection. Exit-zero pending or provisional-only
reductions are not accepted.

- [ ] **Step 8: Run local validation**

```bash
uv run pytest -m "not production" \
  tests/test_production_cli.py tests/test_cluster_profiles.py \
  tests/test_slurm_scripts.py tests/test_transfers.py \
  tests/test_orchestrator.py tests/test_cli.py -q
bash -n production/runtime/*.sh production/deploy/*.sh \
  production/orchestrate/*.sh production/slurm/*.sh
```

Expected: local tests and shell syntax pass. Remote `sbatch --test-only` occurs
only after the final source bundle is copied in Phase 10; testing remote
wrappers before their source commit would attest the wrong code.

- [ ] **Step 9: Commit**

```bash
git -C /home/footman/code/quantum.harness-challenge-15 add \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/cli.py \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/cluster_profile.py \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/transfers.py \
  tracks/qmc/solutions/frustration-free/challenge-15/production/config \
  tracks/qmc/solutions/frustration-free/challenge-15/production/slurm \
  tracks/qmc/solutions/frustration-free/challenge-15/production/deploy \
  tracks/qmc/solutions/frustration-free/challenge-15/production/orchestrate \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_cluster_profiles.py \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_slurm_scripts.py \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_production_cli.py \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_transfers.py \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_orchestrator.py \
  tracks/qmc/solutions/frustration-free/challenge-15/README.md
git commit -m "Add audited production cluster workflows"
```

### Task 7B: Implement the sole local production state machine

**Files:** `src/challenge15/orchestrator.py`,
`production/orchestrate/submit_size.py`,
`tests/test_orchestrator_state_machine.py`, `tests/test_orchestrator.py`, and
`src/challenge15/cli.py`.

**Interface:**

```text
challenge15 production-orchestrate-size
  --particles N --rank-ladder 1,2,4,8 --seeds 0,1,2,3,4
  --base-config PATH --policy PATH --source-manifest PATH
  --runtime-set-local PATH --runtime-set-local-sha256 HEX
  --cpu-runtime-set-remote PATH --cpu-runtime-set-receipt PATH
  --gpu-runtime-set-remote PATH --gpu-runtime-set-receipt PATH
  --cpu-controller {lasg02,wuzh02} --gpu-controller qdeshell
  --cpu-profile PATH --gpu-profile PATH
  --cpu-deployment-receipt PATH --gpu-deployment-receipt PATH
  --cpu-results-root PATH --gpu-results-root PATH
  --state-root-base PATH --state-backup-uri SSH_URI
  [--state-mirror-root PATH]
  [--prerequisite-terminal-selection PATH] --create-only
```

N6 omits the prerequisite option; N7/N8 require it. This command is the sole
operator production entry point. `submit_size.sh`, Slurm wrappers, transfer
scripts, and scientific CLIs are invoked only by this state machine.

`build_state_key(inputs: OrchestrationInputs) -> PublishedStateKey` canonicalizes
and hashes every field in the `orchestration-state-key` schema above. The local,
CPU-remote, and GPU-remote runtime envelopes must have the same payload hash
and role map; remote paths must be resolved by their supplied bootstrap/import
receipts and be local to the named controller. The durable base and backup
identities are state-keyed. The local base is an absolute nonsymlink persistent
path outside `/tmp` and `/var/tmp`; the backup is a profile-approved `ssh://`
URI on a distinct host/failure domain. Same-path/filesystem backup is rejected.
An optional local duplicate is labeled mirror only. After hashing identities,
create only `state-root-base/source=$SOURCE_REVISION/state=$STATE_KEY`.

Immediately before the first transition and on every restart,
`verify_execution_inputs` rehashes every source-manifest member, every
`attestation_test_members[].test_file_sha256`, and every recorded test-result
digest before accepting the three runtime-set copies.

`run_rank_cycle(previous_cycle: CycleOutcome | None, new_rank: int) ->
CycleOutcome` consumes `previous_expected_ranks` only from the verified prior
outcome. Root uses `[]`; rank 2 uses `[1]`; rank 4 uses `[1,2]`; rank 8 uses
`[1,2,4]`. Arithmetic/range derivation and caller-supplied previous ranks are
rejected. It executes these immutable states:

```text
VERIFY_INPUTS -> VERIFY_RUNTIME_SET_COPIES -> ENSURE_ORACLE -> CLAIM_SEEDS
-> PREPARE_RANK -> TRAIN_RANK -> COORDINATE_EVALUATE
-> EXPORT_GPU_IDENTITY_MAP -> TRANSFER_GPU_TO_CPU -> IMPORT_GPU_RESULTS
-> EXACT_EVALUATE -> REDUCE_EXACT_INPUTS -> PROVISIONAL_FINALIZE
-> CLASSIFY_FINALIZATION
```

Accepted transitions to `SELECT_TERMINAL -> EXPORT_ACCEPTED_TERMINAL ->
STOP_ACCEPTED`. Pending with an allowed next doubling transitions to
`DECIDE_EXTENSION -> PREPARE_RANK`; pending without a next rank transitions to
`STOP_PENDING`. Provenance, ownership, transfer, scheduler, or conflicting
receipt errors transition to `HARD_FAIL`.

Each state consumes only hashes/paths from verified predecessor receipts and
publishes one content-addressed transition receipt plus an exclusive completion
marker. Transfer states call `import-member`; downstream commands receive only
destination-local resolved paths and bind both import and transfer receipt
hashes. `REDUCE_EXACT_INPUTS` captures exactly the fresh tab-separated
reduction SHA/path returned by `reduce-size`; `PROVISIONAL_FINALIZE` consumes
those values directly.

Every state begins with
`recover_before_act(spec: TransitionSpec) -> RecoveryDecision`. It calls a
publisher-specific selector derived from attempt intent, output identity,
parents, source/policy/runtime/base, particles/seed/rank, controller, and exact
create-only namespace. The selector enumerates only intent-permitted filenames,
independently canonicalizes bytes and recomputes payload SHA256, and validates
schema, filename hash, provenance, parents, ownership, PRNG, and locality; a
self-declared hash is never sufficient. Zero valid candidates returns not
published, exactly one synthesizes only the output-promotion receipt with the
computed hash, and multiple valid or any tampered permitted candidate hard
fails. Stochastic selectors cover snapshots/generations and coordinate/exact
evaluation; deterministic selectors cover owner, extension, attempt metadata,
reduction, export/import/transfer, finalization, and terminal selection.

Before action, persist `OrchestrationAttemptIntent` locally and remotely.
The remote file is a create-only byte copy of the local envelope with identical
SHA256, not a regenerated receipt.
Slurm calls remote `submit-once`; transfer calls remote `transfer-once`.
Both atomically claim the deterministic correlation ID and publish their remote
receipt before returning. Recovery checks remote receipt first. Slurm then
queries `squeue`/`sacct` by deterministic job name/comment plus script/input
hashes; any evidence forbids another `sbatch`. Transfer recovery checks the
destination canonical output/receipt; any evidence forbids recopy. Ambiguous
evidence waits or hard fails. After each marker, transfer the state manifest
once to the remote backup URI and optionally refresh the local mirror.

Exact remote wrapper contracts:

```text
submit_once.sh --intent PATH --claim-root PATH --receipt-dir PATH
  --script PATH --profile PATH --runtime-set PATH --sbatch-arg ARG...
transfer_once.sh --intent PATH --claim-root PATH --receipt-dir PATH
  --source-host NAME --destination-host NAME --source PATH --destination PATH
  --expected-sha256 HEX --create-only
backup_once.sh --intent PATH --source-state-manifest PATH
  --destination-uri SSH_URI --profile PATH --receipt-dir PATH --create-only
```

`submit_once.sh` validates intent/script/argv/input hashes, checks the remote
receipt, claims `claims/$CORRELATION_ID`, checks `squeue` then `sacct` for job
name `c15-${CORRELATION_ID:0:24}` and comment `$CORRELATION_ID`, and only then
may execute `sbatch --parsable` once. It fsyncs and atomically renames the
submission receipt before stdout returns the job ID. `transfer_once.sh` follows
the same order using destination receipt and canonical imported output before
copy/promotion. `backup_once.sh` parses the SSH URI, validates its path against
the named remote profile, then delegates to transfer-once semantics.

`VERIFY_RUNTIME_SET_COPIES` is a validation/recovery boundary, not an
ambiguous path transfer. Phase 10 has already promoted the set on both
controllers and supplied the resolving receipts. The transition executes:

```bash
"$LOCAL_INTERPRETER" -m challenge15.cli runtime-set-verify-copies \
  --runtime-set-local "$RUNTIME_SET_LOCAL" \
  --runtime-set-local-sha256 "$RUNTIME_SET_LOCAL_SHA256" \
  --cpu-runtime-set-remote "$CPU_RUNTIME_SET_REMOTE" \
  --cpu-runtime-set-receipt "$CPU_RUNTIME_SET_RECEIPT" \
  --gpu-runtime-set-remote "$GPU_RUNTIME_SET_REMOTE" \
  --gpu-runtime-set-receipt "$GPU_RUNTIME_SET_RECEIPT" \
  --cpu-controller "$CPU_CONTROLLER" --gpu-controller qdeshell
```

CPU wrappers receive only `CPU_RUNTIME_SET_REMOTE`; Qdeshell wrappers receive
only `GPU_RUNTIME_SET_REMOTE`; local orchestration validates
`RUNTIME_SET_LOCAL` plus its explicit SHA256. The command rejects unequal
canonical hashes, role maps, source/policy hashes, nonlocal remote paths, or
receipts that do not bind the named deployment/controller.

`PREPARE_RANK` creates a root decision with `(current_rank=null,new_rank=1,
prior_reduction=null,prior_finalization=null,reason=initial)`, then five root
extensions using `--decision`. For ranks 2, 4, and 8 it derives the exact prior
reduction/finalization from the previous `CycleOutcome`, exports/transfers/
imports them, resolves destination-local paths with `import-member`, creates
five decisions, then five decision-bound extensions. No `PRIOR_*` operator
variables exist.

Each cycle schedules exactly five training, five coordinate, and five exact
identities for `new_rank`. `CycleOutcome` carries the verified cumulative
reducer identity map; the next map reuses prior coordinate/exact hashes and
adds only the ten new shard hashes. Its coordinate and exact sections each
contain exactly `len(expected_ranks) * 5` identities. Old ranks are never
resubmitted, retransferred, or republished.

The rank-8 cycle runs all normal states, including coordinate evaluation,
identity-map export, transfer/import, exact evaluation, fresh reduction,
provisional finalization, classification, and accepted terminal selection.
The accepted-terminal export identity map contains exactly terminal selection,
selected provisional finalization, selected reduction, and per-size runtime
set; `export-bundle` consumes that map, never a synthetic root.

- [ ] **Step 1: Write RED trace and idempotency tests**

```python
def test_rank_trace_pending_through_rank4_then_rank8_accepted(fake_clusters):
    outcome = orchestrate_size(fake_clusters.inputs(rank_outcomes={
        1: "pending", 2: "pending", 4: "pending", 8: "accepted"
    }))
    assert outcome.visited_ranks == (1, 2, 4, 8)
    assert outcome.cycle_inputs == (
        (1, ()), (2, (1,)), (4, (1, 2)), (8, (1, 2, 4)),
    )
    assert outcome.cycle_parent_sha256s[0] is None
    assert all(outcome.cycle_parent_sha256s[index] for index in (1, 2, 3))
    assert outcome.state == "STOP_ACCEPTED"
    assert outcome.terminal_selection is not None


def test_run_rank_cycle_consumes_only_verified_previous_outcome(fake_clusters):
    fake_clusters.set_rank_outcomes({
        1: "pending", 2: "pending", 4: "pending", 8: "accepted"
    })
    rank1 = run_rank_cycle(None, 1, fake_clusters=fake_clusters)
    rank2 = run_rank_cycle(rank1, 2, fake_clusters=fake_clusters)
    rank4 = run_rank_cycle(rank2, 4, fake_clusters=fake_clusters)
    rank8 = run_rank_cycle(rank4, 8, fake_clusters=fake_clusters)
    assert rank1.previous_expected_ranks == ()
    assert rank2.previous_expected_ranks == (1,)
    assert rank4.previous_expected_ranks == (1, 2)
    assert rank8.previous_expected_ranks == (1, 2, 4)


def test_rejects_tampered_previous_expected_ranks(fake_clusters):
    previous = fake_clusters.verified_cycle(expected_ranks=(1, 3))
    with pytest.raises(ValueError, match="prior CycleOutcome rank trace"):
        run_rank_cycle(previous_cycle=previous, new_rank=4)


def test_pending_never_selects_terminal(fake_clusters):
    outcome = orchestrate_size(fake_clusters.inputs(rank_outcomes={
        1: "pending", 2: "pending", 4: "pending", 8: "pending"
    }))
    assert "SELECT_TERMINAL" not in outcome.transition_names
    assert outcome.state == "STOP_PENDING"


def test_downstream_uses_imported_paths_and_receipts(fake_clusters):
    outcome = orchestrate_size(fake_clusters.inputs())
    assert all(call.path.controller == call.controller for call in outcome.downstream_calls)
    assert all(call.import_receipt_sha256 for call in outcome.transferred_calls)
    assert all(call.transfer_receipt_sha256 for call in outcome.transferred_calls)


def test_repeated_orchestration_is_idempotent(fake_clusters):
    first = orchestrate_size(fake_clusters.inputs())
    second = orchestrate_size(fake_clusters.inputs())
    assert second.submitted_job_ids == ()
    assert second.terminal_selection == first.terminal_selection


def test_runtime_set_is_local_on_every_consuming_controller(fake_clusters):
    outcome = orchestrate_size(fake_clusters.inputs())
    assert outcome.runtime_set_paths["cpu"].controller == outcome.cpu_controller
    assert outcome.runtime_set_paths["gpu"].controller == "qdeshell"


IMMUTABLE_STATE_FIELDS = (
    "particles", "base_configuration_sha256", "policy_sha256",
    "source_manifest_sha256", "rank_ladder",
    "rank_extension_policy_sha256", "seed_set",
    "runtime_set_local_sha256", "runtime_set_local_path_identity",
    "cpu_runtime_set_remote_sha256", "cpu_runtime_set_remote_path_identity",
    "cpu_runtime_set_receipt_sha256", "gpu_runtime_set_remote_sha256",
    "gpu_runtime_set_remote_path_identity", "gpu_runtime_set_receipt_sha256",
    "prerequisite_terminal_selection_sha256", "cpu_controller",
    "gpu_controller", "cpu_profile_sha256", "gpu_profile_sha256",
    "cpu_deployment_receipt_sha256", "gpu_deployment_receipt_sha256",
    "cpu_results_root_identity", "gpu_results_root_identity",
    "durable_state_root_base_identity", "state_backup_uri_identity",
    "state_mirror_root_identity",
    "canonical_path_identities",
)


@pytest.mark.parametrize("field", IMMUTABLE_STATE_FIELDS)
def test_every_immutable_input_changes_state_key(valid_inputs, field):
    original = build_state_key(valid_inputs)
    changed = build_state_key(mutate_one_canonical_field(valid_inputs, field))
    assert changed.sha256 != original.sha256


@pytest.mark.parametrize("member_kind", ["source", "attestation_test", "test_result"])
def test_execution_rehashes_every_attested_member(execution_inputs, member_kind):
    broken = mutate_each_member_once(execution_inputs, member_kind)
    for candidate in broken:
        with pytest.raises(ValueError, match="attested member hash"):
            verify_execution_inputs(candidate)


def test_next_cycle_reuses_prior_shards_without_republication(fake_clusters):
    rank1 = run_rank_cycle(None, 1, fake_clusters=fake_clusters)
    rank2 = run_rank_cycle(rank1, 2, fake_clusters=fake_clusters)
    assert fake_clusters.trained_ranks == [1] * 5 + [2] * 5
    assert fake_clusters.coordinate_ranks == [1] * 5 + [2] * 5
    assert fake_clusters.exact_ranks == [1] * 5 + [2] * 5
    assert rank2.cumulative_map.coordinate_count == 10
    assert rank2.cumulative_map.exact_count == 10
    assert rank2.cumulative_map.prior_hashes == rank1.cumulative_map.all_hashes


def test_runtime_paths_are_controller_local(runtime_copies):
    verified = verify_runtime_set_copies(runtime_copies)
    assert verified.cpu.path.controller == verified.cpu.controller
    assert verified.gpu.path.controller == "qdeshell"
    assert len({
        verified.local.payload_sha256,
        verified.cpu.payload_sha256,
        verified.gpu.payload_sha256,
    }) == 1
    assert verified.cpu.resolving_receipt.schema == (
        "challenge15.runtime-set-publication-receipt.v1"
    )
    assert verified.gpu.resolving_receipt.schema == (
        "challenge15.runtime-set-publication-receipt.v1"
    )
    assert verified.cpu.resolving_receipt.payload.controller_local_path_identity == (
        verified.cpu.path.identity
    )
    assert runtime_copies.payload.cpu_resolving_receipt_sha256 == (
        verified.cpu.resolving_receipt.envelope_sha256
    )


def test_result_and_promoted_paths_are_controller_local(valid_inputs):
    verified = verify_orchestration_paths(valid_inputs)
    assert verified.cpu_results.is_within(verified.cpu_profile.approved_results)
    assert verified.gpu_results.is_within(verified.gpu_profile.approved_results)
    assert all(p.controller == p.expected_controller for p in verified.promotions)
    assert all(p.filesystem_id == p.output.filesystem_id for p in verified.promotions)


@pytest.mark.parametrize("root", ["/tmp/challenge15", "/var/tmp/challenge15"])
def test_durable_state_root_rejects_temporary_storage(root):
    with pytest.raises(ValueError, match="durable state root"):
        validate_state_root_base(root)


def test_restore_from_backup_revalidates_without_resubmission(fake_clusters):
    first = orchestrate_size(fake_clusters.inputs())
    restored = restore_state_manifest(
        backup_uri=first.backup_uri,
        state_key_sha256=first.state_key_sha256,
        new_local_state_base=fake_clusters.second_host_same_canonical_state_base,
    )
    second = orchestrate_size(fake_clusters.inputs(restored_state=restored))
    assert second.terminal_selection == first.terminal_selection
    assert second.submitted_job_ids == ()


@pytest.mark.parametrize("uri", [
    "file:///home/footman/.local/state/challenge15-backup",
    "ssh://localhost/home/footman/.local/state/challenge15-backup",
])
def test_disaster_backup_rejects_same_failure_domain(uri, valid_inputs):
    with pytest.raises(ValueError, match="distinct durable failure domain"):
        validate_backup_uri(uri, valid_inputs.local_state_identity)


def test_local_duplicate_is_only_mirror(valid_inputs):
    mirror = publish_local_state_mirror(valid_inputs)
    assert mirror.classification == "mirror"
    assert mirror.satisfies_disaster_backup is False


def test_default_backup_uri_is_remote_and_profile_approved(valid_inputs):
    uri = default_backup_uri(valid_inputs.particles, valid_inputs.cpu_profile)
    assert uri.scheme == "ssh"
    assert uri.host != valid_inputs.local_host
    assert uri.path.is_within(valid_inputs.cpu_profile.approved_results)


TRANSITION_STATES = (
    "VERIFY_INPUTS", "VERIFY_RUNTIME_SET_COPIES", "ENSURE_ORACLE",
    "CLAIM_SEEDS", "PREPARE_RANK", "TRAIN_RANK",
    "COORDINATE_EVALUATE", "EXPORT_GPU_IDENTITY_MAP",
    "TRANSFER_GPU_TO_CPU", "IMPORT_GPU_RESULTS", "EXACT_EVALUATE",
    "REDUCE_EXACT_INPUTS", "PROVISIONAL_FINALIZE",
    "CLASSIFY_FINALIZATION", "DECIDE_EXTENSION", "SELECT_TERMINAL",
    "EXPORT_ACCEPTED_TERMINAL", "STOP_ACCEPTED", "STOP_PENDING",
    "HARD_FAIL",
)
CRASH_WINDOWS = (
    "after_canonical_publication",
    "after_transfer_promotion",
    "after_scheduler_completion", "after_receipt_publication",
    "before_completion_marker", "after_completion_marker",
)


@pytest.mark.parametrize("state", TRANSITION_STATES)
@pytest.mark.parametrize("window", CRASH_WINDOWS)
def test_recover_before_act_all_crash_windows(fake_clusters, state, window):
    fake_clusters.inject_crash(state=state, window=window)
    with pytest.raises(InjectedCrash):
        orchestrate_size(fake_clusters.inputs())
    actions_before = fake_clusters.external_action_counts()
    recovered = orchestrate_size(fake_clusters.inputs())
    assert recovered.valid_transition(state)
    assert fake_clusters.external_action_counts() == actions_before
    assert recovered.receipt_exists(state)
    assert recovered.marker_exists(state)


PUBLISHERS = (
    "seed-owner", "rank-extension", "training-attempt",
    "training-snapshot", "training-generation",
    "coordinate-evaluation-shard", "exact-evaluation-shard",
    "reduction", "export-bundle", "import-bundle", "transfer-receipt",
    "reduction-finalization", "terminal-selection",
)


@pytest.mark.parametrize("selector_kind", ["stochastic", "deterministic"])
def test_selector_zero_candidates_means_not_published(selector_harness, selector_kind):
    result = selector_harness.select(selector_kind, candidates=[])
    assert result is None
    assert not selector_harness.promotion_receipt_exists


@pytest.mark.parametrize("selector_kind", ["stochastic", "deterministic"])
def test_selector_adopts_one_and_records_computed_hash(
    selector_harness, selector_kind
):
    candidate = selector_harness.valid_candidate(selector_kind)
    result = selector_harness.select(selector_kind, candidates=[candidate])
    assert result.path == candidate.path
    assert result.promotion.payload.candidate_count == 1
    assert result.promotion.payload.candidate_computed_sha256 == (
        independently_canonicalize_and_hash(candidate.bytes)
    )


@pytest.mark.parametrize("selector_kind", ["stochastic", "deterministic"])
def test_selector_multiple_valid_candidates_hard_fail(
    selector_harness, selector_kind
):
    candidates = [
        selector_harness.valid_candidate(selector_kind, nonce="a"),
        selector_harness.valid_candidate(selector_kind, nonce="b"),
    ]
    with pytest.raises(ValueError, match="multiple intent-permitted candidates"):
        selector_harness.select(selector_kind, candidates=candidates)


@pytest.mark.parametrize(
    "tamper", ["schema", "claimed_hash", "filename_hash", "provenance", "parent"]
)
@pytest.mark.parametrize("selector_kind", ["stochastic", "deterministic"])
def test_selector_tamper_hard_fails_without_trusting_self_hash(
    selector_harness, selector_kind, tamper
):
    candidate = selector_harness.tampered_candidate(
        selector_kind=selector_kind, tamper=tamper, recompute_self_hash=True
    )
    with pytest.raises(ValueError, match="tampered intent-permitted candidate"):
        selector_harness.select(selector_kind, candidates=[candidate])


@pytest.mark.parametrize("publisher", PUBLISHERS)
@pytest.mark.parametrize("window", CRASH_WINDOWS)
def test_actual_publisher_recovery_never_republishes(
    publisher_harness, publisher, window
):
    publisher_harness.inject_crash(publisher, window)
    with pytest.raises(InjectedCrash):
        publisher_harness.run(publisher)
    canonical = publisher_harness.canonical_output(publisher)
    assert canonical.independently_validates_against_attempt_intent()
    recovered = publisher_harness.run(publisher)
    assert recovered.canonical_path == canonical.path
    assert publisher_harness.canonical_publish_calls(publisher) == 1
    assert recovered.output_promotion_receipt.validate()


def test_crash_after_sbatch_recovers_remote_job_without_resubmit(slurm_harness):
    slurm_harness.inject_crash("after_sbatch_before_remote_receipt")
    with pytest.raises(InjectedCrash):
        slurm_harness.submit_once()
    recovered = slurm_harness.submit_once()
    assert recovered.job_id == slurm_harness.sacct_job_id
    assert slurm_harness.sbatch_call_count == 1


@pytest.mark.parametrize("action_kind", ["slurm", "transfer", "backup"])
def test_attempt_intent_is_local_and_remote_before_action(action_harness, action_kind):
    action_harness.stop_before_external_action(action_kind)
    action_harness.run()
    assert action_harness.local_intent.validate()
    assert action_harness.remote_intent.validate()
    assert action_harness.remote_intent.sha256 == action_harness.local_intent.sha256
    assert action_harness.external_action_count == 0


def test_transfer_once_recovers_destination_without_recopy(transfer_harness):
    transfer_harness.inject_crash("after_destination_promotion")
    with pytest.raises(InjectedCrash):
        transfer_harness.transfer_once()
    recovered = transfer_harness.transfer_once()
    assert recovered.receipt.validate()
    assert transfer_harness.copy_call_count == 1


def test_submit_once_rejects_scheduler_hash_mismatch(slurm_harness):
    slurm_harness.seed_sacct_match(script_sha256="0" * 64)
    with pytest.raises(ValueError, match="scheduler evidence hash mismatch"):
        slurm_harness.submit_once()
    assert slurm_harness.sbatch_call_count == 0


def test_submit_once_checks_remote_receipt_before_scheduler(slurm_harness):
    slurm_harness.seed_valid_remote_receipt(job_id="812345")
    recovered = slurm_harness.submit_once()
    assert recovered.job_id == "812345"
    assert slurm_harness.scheduler_query_count == 0
    assert slurm_harness.sbatch_call_count == 0
```

Also test a missing CPU/Qdeshell runtime-set import, wrong allowed-runtime
role/controller, remote-origin path leakage, pending terminal selection
invocation, reduction directory inference, conflicting completion marker, and
corrupt receipt.

- [ ] **Step 2: Run and commit**

```bash
uv run pytest -m "not production" \
  tests/test_orchestrator_state_machine.py tests/test_orchestrator.py \
  tests/test_production_cli.py tests/test_transfers.py -q
git -C /home/footman/code/quantum.harness-challenge-15 add \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/orchestrator.py \
  tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/cli.py \
  tracks/qmc/solutions/frustration-free/challenge-15/production/orchestrate/submit_size.py \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_orchestrator_state_machine.py \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_orchestrator.py
git commit -m "Add resumable production size orchestrator"
```

---

## Phase 8: Local Smoke and Source Completion

### Task 8: Run validation pytest and bounded smoke

**Files:** `tests/test_end_to_end.py`,
`production/config/base-n4-smoke.json`, and final README updates.

- [ ] **Step 1: Add local end-to-end smoke**

Create root rank extensions for five `N=4` seeds, tiny generations, exact and
coordinate shards, then reduce expected ranks `1,2,4`. The tiny optimizer is
not expected to pass production gates; canonical output must be pending.

- [ ] **Step 2: Run validation tests**

```bash
cd /home/footman/code/quantum.harness-challenge-15/tracks/qmc/solutions/frustration-free/challenge-15
uv run pytest -m "not production" -q
uv run python -m compileall -q src tests
git -C /home/footman/code/quantum.harness-challenge-15 diff --check
```

Expected: all validation tests pass, compilation succeeds, and no whitespace
errors. This command does not claim production statistical tests.

- [ ] **Step 3: Commit final source task**

```bash
git -C /home/footman/code/quantum.harness-challenge-15 add \
  tracks/qmc/solutions/frustration-free/challenge-15/tests/test_end_to_end.py \
  tracks/qmc/solutions/frustration-free/challenge-15/production/config/base-n4-smoke.json \
  tracks/qmc/solutions/frustration-free/challenge-15/README.md
git commit -m "Complete local production validation"
```

- [ ] **Step 4: Run bounded `N=6` API smoke from committed source**

```bash
SOURCE_REVISION="$(git -C /home/footman/code/quantum.harness-challenge-15 rev-parse HEAD)"
SMOKE_ROOT="/tmp/challenge15-n6-api-smoke-$SOURCE_REVISION"
test ! -e "$SMOKE_ROOT"
mkdir -m 700 "$SMOKE_ROOT"
uv run pytest -m "not production" \
  tests/test_end_to_end.py::test_n6_bounded_api_smoke -q
```

Expected: one-step compile/schema/ownership paths pass and emit no accepted
production artifact. After this committed-source smoke, no implementation
source changes are permitted without restarting Phase 9.

---

## Phase 9: Final Source Freeze and Target Attestation

### Task 9: Generate source-bound CPU/CUDA attestations

**Files:** Generated artifacts only.

- [ ] **Step 1: Require clean source and generate policy/source manifests**

```bash
cd /home/footman/code/quantum.harness-challenge-15/tracks/qmc/solutions/frustration-free/challenge-15
git -C /home/footman/code/quantum.harness-challenge-15 diff --quiet -- \
  tracks/qmc/solutions/frustration-free/challenge-15
git -C /home/footman/code/quantum.harness-challenge-15 diff --cached --quiet -- \
  tracks/qmc/solutions/frustration-free/challenge-15
test -z "$(git -C /home/footman/code/quantum.harness-challenge-15 ls-files --others --exclude-standard -- tracks/qmc/solutions/frustration-free/challenge-15)"
SOURCE_REVISION="$(git -C /home/footman/code/quantum.harness-challenge-15 rev-parse HEAD)"
LOCAL_STATE_BASE="${XDG_STATE_HOME:-$HOME/.local/state}/challenge15"
STATE_MIRROR_ROOT="$HOME/.local/state/challenge15-mirror"
case "$(realpath -m "$LOCAL_STATE_BASE")" in /tmp/*|/var/tmp/*) exit 64;; esac
case "$(realpath -m "$STATE_MIRROR_ROOT")" in /tmp/*|/var/tmp/*) exit 64;; esac
mkdir -p "$LOCAL_STATE_BASE/source=$SOURCE_REVISION"
mkdir -p "$STATE_MIRROR_ROOT/source=$SOURCE_REVISION"
ATTEST_ROOT="$LOCAL_STATE_BASE/source=$SOURCE_REVISION/attestation"
test ! -e "$ATTEST_ROOT"
mkdir -m 700 "$ATTEST_ROOT"
uv run python -m challenge15.cli policy \
  --output "$ATTEST_ROOT/policy.json" --create-only
uv run python -m challenge15.cli source-manifest \
  --root /home/footman/code/quantum.harness-challenge-15/tracks/qmc/solutions/frustration-free/challenge-15 \
  --policy "$ATTEST_ROOT/policy.json" \
  --output "$ATTEST_ROOT/source.json" --require-clean
```

Expected: policy and source manifests bind the final revision and exactly all
matched members of `src/**/*.py`, `production/**/*.py`,
`production/**/*.json`, `production/**/*.sh`, `production/**/*.sbatch`,
`production/runtime/**/*.txt`, `production/runtime/**/*.in`,
`tests/**/*.py`, `pyproject.toml`, and `uv.lock`. Empty required patterns,
untracked matching files, omissions, and extras fail.

- [ ] **Step 2: Build immutable source/wheel bundle**

```bash
bash production/deploy/build_source_bundle.sh \
  --source-manifest "$ATTEST_ROOT/source.json" \
  --policy "$ATTEST_ROOT/policy.json" \
  --cpu-wheelhouse "$PWD/.production-build/candidate-jax-0.4.38-cp312/cpu" \
  --cuda-wheelhouse "$PWD/.production-build/candidate-jax-0.4.38-cp312/cuda12" \
  --output "$ATTEST_ROOT/bundle"
(cd "$ATTEST_ROOT/bundle" && sha256sum -c SHA256SUMS)
BUNDLE_SHA256="$(sha256sum "$ATTEST_ROOT/bundle/export.json" | awk '{print $1}')"
```

Expected: every bundled file reports `OK`; the export bundle is create-only
and content-addressed.

- [ ] **Step 3: Attest CPU on LASG02**

```bash
bash production/deploy/upload_bundle.sh \
  --bundle "$ATTEST_ROOT/bundle" --bundle-sha256 "$BUNDLE_SHA256" \
  --host lasg02-student090 \
  --destination-root /public/home/student090/results/challenge15/attestations
ssh lasg02-student090 'ROOT=/public/home/student090/results/challenge15/attestations/'"$BUNDLE_SHA256"'; bash "$ROOT/source/production/runtime/install_offline.sh" --profile cpu --wheelhouse "$ROOT/cpu" --destination "$ROOT/venv-cpu" --create-only; for ROLE in oracle exact reducer; do PYTHONPATH="$ROOT/source/src" "$ROOT/venv-cpu/bin/python" -m challenge15.cli runtime-attest --role "$ROLE" --controller lasg02 --profile cpu --wheelhouse "$ROOT/cpu" --source-manifest "$ROOT/source.json" --policy "$ROOT/policy.json" --expected-backend cpu --output-dir "$ROOT/attestations/$ROLE" --create-only; done'
```

Expected: `challenge15.allowed-runtime.v1`, CPython 3.12, glibc 2.17,
JAX/JAXlib 0.4.38, backend CPU, x64 true, and production-marked runtime tests
pass.

- [ ] **Step 4: Attest CPU on WUZH02**

```bash
WUZH_RESULTS_ROOT="$(uv run python -m challenge15.cluster_profile get --profile production/slurm/profiles/wuzh02.json --field results_root)"
bash production/deploy/upload_bundle.sh \
  --bundle "$ATTEST_ROOT/bundle" --bundle-sha256 "$BUNDLE_SHA256" \
  --host wuzh02 --destination-root "$WUZH_RESULTS_ROOT/challenge15/attestations"
ssh wuzh02 'ROOT='"$WUZH_RESULTS_ROOT"'/challenge15/attestations/'"$BUNDLE_SHA256"'; bash "$ROOT/source/production/runtime/install_offline.sh" --profile cpu --wheelhouse "$ROOT/cpu" --destination "$ROOT/venv-cpu" --create-only; for ROLE in oracle exact reducer; do PYTHONPATH="$ROOT/source/src" "$ROOT/venv-cpu/bin/python" -m challenge15.cli runtime-attest --role "$ROLE" --controller wuzh02 --profile cpu --wheelhouse "$ROOT/cpu" --source-manifest "$ROOT/source.json" --policy "$ROOT/policy.json" --expected-backend cpu --output-dir "$ROOT/attestations/$ROLE" --create-only; done'
```

Expected: the committed WUZH02 profile, CPython 3.12, glibc floor, CPU+x64,
source digest, policy digest, and production runtime tests pass. Otherwise N8
remains blocked.

- [ ] **Step 5: Attest CUDA on Qdeshell**

```bash
bash production/deploy/upload_bundle.sh \
  --bundle "$ATTEST_ROOT/bundle" --bundle-sha256 "$BUNDLE_SHA256" \
  --host qdeshell \
  --destination-root /work/share/giggleliu/jiangweiqi/results/challenge15/attestations
ssh qdeshell 'ROOT=/work/share/giggleliu/jiangweiqi/results/challenge15/attestations/'"$BUNDLE_SHA256"'; bash "$ROOT/source/production/runtime/install_offline.sh" --profile cuda12 --wheelhouse "$ROOT/cuda12" --destination "$ROOT/venv-cuda12" --create-only; for ROLE in training coordinate; do PYTHONPATH="$ROOT/source/src" "$ROOT/venv-cuda12/bin/python" -m challenge15.cli runtime-attest --role "$ROLE" --controller qdeshell --profile cuda12 --wheelhouse "$ROOT/cuda12" --source-manifest "$ROOT/source.json" --policy "$ROOT/policy.json" --expected-backend gpu --output-dir "$ROOT/attestations/$ROLE" --create-only; done'
```

Expected: bundled CUDA wheels validate, backend GPU/x64 is enabled, exact A800
device is observed, and production runtime tests pass.

- [ ] **Step 6: Define bootstrap exchange inputs**

Exact bootstrap payload fields are `source_controller`,
`destination_controller`, `role`, `allowed_runtime_sha256`,
`source_manifest_sha256`, `policy_sha256`,
`source_deployment_receipt_sha256`,
`destination_deployment_receipt_sha256`,
`export_bundle_sha256`, `import_bundle_sha256`, and `verified_at_utc`.
Bootstrap validation takes no completed runtime set. It validates the common
source manifest, policy, both deployment receipts, and the individual
allowed-runtime envelope. The commands below execute only in Phase 10 Step 5
after deployment receipts exist; Task 9 performs no bootstrap transfer.

```bash
bash production/orchestrate/transfer_attestation_bootstrap.sh \
  --source-host qdeshell --destination-host lasg02-student090 \
  --source-controller qdeshell --destination-controller lasg02 \
  --allowed-runtime "$TRAINING_ATTESTATION" --role training \
  --source-manifest "$ATTEST_ROOT/source.json" \
  --policy "$ATTEST_ROOT/policy.json" \
  --source-deployment-receipt "$QDES_DEPLOYMENT_RECEIPT" \
  --destination-deployment-receipt "$LASG_DEPLOYMENT_RECEIPT" \
  --output-dir "$ATTEST_ROOT/bootstrap/qdeshell-to-lasg02/training" \
  --create-only
```

The orchestrator executes `bootstrap-export`, unique partial upload,
`bootstrap-import`, hash verification, atomic rename, and bootstrap-receipt
verification. Tests reject scientific members, a completed-set argument,
wrong role/controller, stale source/policy, wrong deployment, corrupt
allowed-runtime bytes, duplicate destination, and partial upload.

On LASG02 create separate N6 and N7 sets with LASG02 CPU hashes; on WUZH02
create the N8 set with WUZH02 CPU hashes:

```bash
"$ROOT/venv-cpu/bin/python" -m challenge15.cli runtime-attestation-set \
  --particles "$PARTICLES" \
  --training-controller qdeshell --training "$TRAINING_ATTESTATION" \
  --coordinate-controller qdeshell --coordinate "$COORDINATE_ATTESTATION" \
  --oracle-controller "$CPU_CONTROLLER" --oracle "$ORACLE_ATTESTATION" \
  --exact-controller "$CPU_CONTROLLER" --exact "$EXACT_ATTESTATION" \
  --reducer-controller "$CPU_CONTROLLER" --reducer "$REDUCER_ATTESTATION" \
  --output-dir "$ROOT/runtime-attestation-sets" --create-only
```

Run with `(PARTICLES,CPU_CONTROLLER)=(6,lasg02),(7,lasg02),(8,wuzh02)`.
Expected: N6/N7 preserve LASG02 CPU hashes, N8 preserves WUZH02 CPU hashes,
and all preserve Qdeshell training/coordinate hashes. Validators reject
role-only maps, swapped controllers, missing roles, duplicate roles, stale
envelopes, or schema fields inside payloads.

- [ ] **Step 7: Recheck source**

```bash
test "$SOURCE_REVISION" = "$(git -C /home/footman/code/quantum.harness-challenge-15 rev-parse HEAD)"
git -C /home/footman/code/quantum.harness-challenge-15 diff --quiet -- \
  tracks/qmc/solutions/frustration-free/challenge-15
git -C /home/footman/code/quantum.harness-challenge-15 diff --cached --quiet -- \
  tracks/qmc/solutions/frustration-free/challenge-15
test -z "$(git -C /home/footman/code/quantum.harness-challenge-15 status \
  --porcelain --untracked-files=all -- \
  tracks/qmc/solutions/frustration-free/challenge-15)"
uv run python -m challenge15.cli source-manifest \
  --root /home/footman/code/quantum.harness-challenge-15/tracks/qmc/solutions/frustration-free/challenge-15 \
  --policy "$ATTEST_ROOT/policy.json" \
  --output "$ATTEST_ROOT/source-post-attestation.json" --require-clean
cmp "$ATTEST_ROOT/source.json" "$ATTEST_ROOT/source-post-attestation.json"
```

Expected: unchanged tracked and untracked source plus byte-identical member
hashes. Any difference invalidates every role attestation.

---

## Phase 10: Deployment

### Task 10: Dry-run, test-only, and deploy

- [ ] **Step 1: Qdeshell dry-run and scheduler validation**

```bash
ssh qdeshell 'ROOT=/work/share/giggleliu/jiangweiqi/results/challenge15/attestations/'"$BUNDLE_SHA256"'; cd "$ROOT/source" && bash production/deploy/dry_run.sh --profile production/slurm/profiles/qdeshell.json --bundle "$ROOT" --destination /work/share/giggleliu/jiangweiqi/results/challenge15/deployments/'"$BUNDLE_SHA256"' --receipt-dir "$ROOT/dry-run/qdeshell" --create-only && sbatch --test-only production/slurm/train-qdeshell.sbatch && sbatch --test-only production/slurm/coordinate-qdeshell.sbatch'
```

Expected: approved paths, exact GRES/CPU ratio, hashes, backend, and test-only
allocations validate.

- [ ] **Step 2: LASG02 dry-run and scheduler validation**

```bash
ssh lasg02-student090 'ROOT=/public/home/student090/results/challenge15/attestations/'"$BUNDLE_SHA256"'; cd "$ROOT/source" && bash production/deploy/dry_run.sh --profile production/slurm/profiles/lasg02.json --bundle "$ROOT" --destination /public/home/student090/results/challenge15/deployments/'"$BUNDLE_SHA256"' --receipt-dir "$ROOT/dry-run/lasg02" --create-only && sbatch --test-only production/slurm/oracle-lasg02.sbatch && sbatch --test-only production/slurm/exact-lasg02.sbatch'
```

Expected: exact partition/account/QOS/resources and approved roots validate.

- [ ] **Step 3: WUZH02 dry-run and scheduler validation**

```bash
ssh wuzh02 'ROOT='"$WUZH_RESULTS_ROOT"'/challenge15/attestations/'"$BUNDLE_SHA256"'; INTERPRETER="$ROOT/venv-cpu/bin/python"; cd "$ROOT/source" && bash production/deploy/dry_run.sh --profile production/slurm/profiles/wuzh02.json --bundle "$ROOT" --destination '"$WUZH_RESULTS_ROOT"'/challenge15/deployments/'"$BUNDLE_SHA256"' --receipt-dir "$ROOT/dry-run/wuzh02" --create-only && "$INTERPRETER" production/slurm/render_wuzh02.py --profile production/slurm/profiles/wuzh02.json --output "$ROOT/wuzh02-runtime.sbatch" --create-only && sbatch --test-only "$ROOT/wuzh02-runtime.sbatch"'
```

Expected: profile-derived resources, approved root, hashes, and test-only
allocation validate.

- [ ] **Step 4: Deploy create-only**

```bash
ssh qdeshell 'ROOT=/work/share/giggleliu/jiangweiqi/results/challenge15/attestations/'"$BUNDLE_SHA256"'; cd "$ROOT/source" && bash production/deploy/deploy.sh --profile production/slurm/profiles/qdeshell.json --bundle "$ROOT" --dry-run-receipt "$ROOT/dry-run/qdeshell" --destination /work/share/giggleliu/jiangweiqi/results/challenge15/deployments/'"$BUNDLE_SHA256"' --receipt-dir "$ROOT/deployment/qdeshell" --create-only'
ssh lasg02-student090 'ROOT=/public/home/student090/results/challenge15/attestations/'"$BUNDLE_SHA256"'; cd "$ROOT/source" && bash production/deploy/deploy.sh --profile production/slurm/profiles/lasg02.json --bundle "$ROOT" --dry-run-receipt "$ROOT/dry-run/lasg02" --destination /public/home/student090/results/challenge15/deployments/'"$BUNDLE_SHA256"' --receipt-dir "$ROOT/deployment/lasg02" --create-only'
ssh wuzh02 'ROOT='"$WUZH_RESULTS_ROOT"'/challenge15/attestations/'"$BUNDLE_SHA256"'; cd "$ROOT/source" && bash production/deploy/deploy.sh --profile production/slurm/profiles/wuzh02.json --bundle "$ROOT" --dry-run-receipt "$ROOT/dry-run/wuzh02" --destination '"$WUZH_RESULTS_ROOT"'/challenge15/deployments/'"$BUNDLE_SHA256"' --receipt-dir "$ROOT/deployment/wuzh02" --create-only'
```

`deploy.sh` requires the dry-run receipt for the same exact path tuple, creates
`<destination>.partial.<bundle_sha256>.<uuid>`, verifies `SHA256SUMS`, installs
offline, records the absolute interpreter and its fingerprint, atomically
renames to the final destination, and publishes the deployment receipt.
Existing partial or final destinations fail.

- [ ] **Step 5: Bootstrap allowed-runtime exchange and publish per-size sets**

After all three deployment receipts validate, run:

```bash
for ROLE in training coordinate; do
  if test "$ROLE" = training; then
    ALLOWED_RUNTIME="$TRAINING_ATTESTATION"
  else
    ALLOWED_RUNTIME="$COORDINATE_ATTESTATION"
  fi
  bash production/orchestrate/transfer_attestation_bootstrap.sh \
    --source-host qdeshell --destination-host lasg02-student090 \
    --source-controller qdeshell --destination-controller lasg02 \
    --allowed-runtime "$ALLOWED_RUNTIME" --role "$ROLE" \
    --source-manifest "$ATTEST_ROOT/source.json" \
    --policy "$ATTEST_ROOT/policy.json" \
    --source-deployment-receipt "$QDES_DEPLOYMENT_RECEIPT" \
    --destination-deployment-receipt "$LASG_DEPLOYMENT_RECEIPT" \
    --output-dir "$ATTEST_ROOT/bootstrap/qdeshell-to-lasg02/$ROLE" \
    --create-only
  bash production/orchestrate/transfer_attestation_bootstrap.sh \
    --source-host qdeshell --destination-host wuzh02 \
    --source-controller qdeshell --destination-controller wuzh02 \
    --allowed-runtime "$ALLOWED_RUNTIME" --role "$ROLE" \
    --source-manifest "$ATTEST_ROOT/source.json" \
    --policy "$ATTEST_ROOT/policy.json" \
    --source-deployment-receipt "$QDES_DEPLOYMENT_RECEIPT" \
    --destination-deployment-receipt "$WUZH_DEPLOYMENT_RECEIPT" \
    --output-dir "$ATTEST_ROOT/bootstrap/qdeshell-to-wuzh02/$ROLE" \
    --create-only
done
ssh lasg02-student090 '"$LASG_INTERPRETER"' -m challenge15.cli runtime-attestation-set --particles 6 --training-controller qdeshell --training '"$LASG_TRAINING_ATTESTATION"' --coordinate-controller qdeshell --coordinate '"$LASG_COORDINATE_ATTESTATION"' --oracle-controller lasg02 --oracle '"$LASG_ORACLE_ATTESTATION"' --exact-controller lasg02 --exact '"$LASG_EXACT_ATTESTATION"' --reducer-controller lasg02 --reducer '"$LASG_REDUCER_ATTESTATION"' --output-dir '"$LASG_SET_ROOT/N=6"' --create-only'
ssh lasg02-student090 '"$LASG_INTERPRETER"' -m challenge15.cli runtime-attestation-set --particles 7 --training-controller qdeshell --training '"$LASG_TRAINING_ATTESTATION"' --coordinate-controller qdeshell --coordinate '"$LASG_COORDINATE_ATTESTATION"' --oracle-controller lasg02 --oracle '"$LASG_ORACLE_ATTESTATION"' --exact-controller lasg02 --exact '"$LASG_EXACT_ATTESTATION"' --reducer-controller lasg02 --reducer '"$LASG_REDUCER_ATTESTATION"' --output-dir '"$LASG_SET_ROOT/N=7"' --create-only'
ssh wuzh02 '"$WUZH_INTERPRETER"' -m challenge15.cli runtime-attestation-set --particles 8 --training-controller qdeshell --training '"$WUZH_TRAINING_ATTESTATION"' --coordinate-controller qdeshell --coordinate '"$WUZH_COORDINATE_ATTESTATION"' --oracle-controller wuzh02 --oracle '"$WUZH_ORACLE_ATTESTATION"' --exact-controller wuzh02 --exact '"$WUZH_EXACT_ATTESTATION"' --reducer-controller wuzh02 --reducer '"$WUZH_REDUCER_ATTESTATION"' --output-dir '"$WUZH_SET_ROOT/N=8"' --create-only'
N6_RUNTIME_COPIES="$(bash production/orchestrate/transfer_runtime_set.sh --particles 6 --source-host lasg02-student090 --source-controller lasg02 --runtime-set-source "$LASG_SET_ROOT/N=6/$N6_RUNTIME_SET_SHA256.json" --source-deployment-receipt "$LASG_DEPLOYMENT_RECEIPT" --gpu-host qdeshell --gpu-controller qdeshell --gpu-deployment-receipt "$QDES_DEPLOYMENT_RECEIPT" --local-destination "$ATTEST_ROOT/runtime-set-copies/N=6/local" --gpu-destination "/work/share/giggleliu/jiangweiqi/results/challenge15/runtime-set-copies/$SOURCE_REVISION/N=6" --policy "$ATTEST_ROOT/policy.json" --source-manifest "$ATTEST_ROOT/source.json" --output-dir "$ATTEST_ROOT/runtime-set-copies/N=6" --create-only)"
N7_RUNTIME_COPIES="$(bash production/orchestrate/transfer_runtime_set.sh --particles 7 --source-host lasg02-student090 --source-controller lasg02 --runtime-set-source "$LASG_SET_ROOT/N=7/$N7_RUNTIME_SET_SHA256.json" --source-deployment-receipt "$LASG_DEPLOYMENT_RECEIPT" --gpu-host qdeshell --gpu-controller qdeshell --gpu-deployment-receipt "$QDES_DEPLOYMENT_RECEIPT" --local-destination "$ATTEST_ROOT/runtime-set-copies/N=7/local" --gpu-destination "/work/share/giggleliu/jiangweiqi/results/challenge15/runtime-set-copies/$SOURCE_REVISION/N=7" --policy "$ATTEST_ROOT/policy.json" --source-manifest "$ATTEST_ROOT/source.json" --output-dir "$ATTEST_ROOT/runtime-set-copies/N=7" --create-only)"
N8_RUNTIME_COPIES="$(bash production/orchestrate/transfer_runtime_set.sh --particles 8 --source-host wuzh02 --source-controller wuzh02 --runtime-set-source "$WUZH_SET_ROOT/N=8/$N8_RUNTIME_SET_SHA256.json" --source-deployment-receipt "$WUZH_DEPLOYMENT_RECEIPT" --gpu-host qdeshell --gpu-controller qdeshell --gpu-deployment-receipt "$QDES_DEPLOYMENT_RECEIPT" --local-destination "$ATTEST_ROOT/runtime-set-copies/N=8/local" --gpu-destination "/work/share/giggleliu/jiangweiqi/results/challenge15/runtime-set-copies/$SOURCE_REVISION/N=8" --policy "$ATTEST_ROOT/policy.json" --source-manifest "$ATTEST_ROOT/source.json" --output-dir "$ATTEST_ROOT/runtime-set-copies/N=8" --create-only)"
```

Each helper prints one local path to a create-only
`challenge15.runtime-set-copies.v1` envelope. Fetch and validate all three
envelopes before production submission.

On both CPU source and Qdeshell destination, the helper resolves the deployed
interpreter and runs:

```bash
"$CONTROLLER_INTERPRETER" -m challenge15.cli runtime-set-publication-receipt \
  --controller "$CONTROLLER" --deployment-receipt "$DEPLOYMENT_RECEIPT" \
  --controller-local-path "$CONTROLLER_RUNTIME_SET" \
  --runtime-set-sha256 "$RUNTIME_SET_SHA256" \
  --source-manifest "$CONTROLLER_SOURCE_MANIFEST" \
  --policy "$CONTROLLER_POLICY" \
  --output-dir "$CONTROLLER_RECEIPT_ROOT" --create-only
```

The returned receipt hashes, not deployment/bootstrap/transfer receipts, are
stored as `cpu_resolving_receipt_sha256` and
`gpu_resolving_receipt_sha256`.

Expected: N6/N7 sets contain LASG02 CPU hashes and Qdeshell GPU hashes; N8
contains WUZH02 CPU hashes and Qdeshell GPU hashes. No scientific transfer or
wrapper submission starts before each local/CPU-remote/GPU-remote copy has an
equal canonical payload hash and role map plus a valid resolving receipt.

---

## Phase 11: N=6 Production

### Task 11: Execute complete N=6 identities

Set exact identities on their target nodes:

```bash
SOURCE_REVISION="$(git rev-parse HEAD)"
LOCAL_STATE_BASE="${XDG_STATE_HOME:-$HOME/.local/state}/challenge15"
STATE_MIRROR_ROOT="$HOME/.local/state/challenge15-mirror"
STATE_BACKUP_URI="ssh://lasg02-student090/public/home/student090/results/challenge15/orchestration-backups"
ATTEST_ROOT="$LOCAL_STATE_BASE/source=$SOURCE_REVISION/attestation"
LASG_ROOT="/public/home/student090/results/challenge15/runs/$SOURCE_REVISION/N=6"
QDES_ROOT="/work/share/giggleliu/jiangweiqi/results/challenge15/runs/$SOURCE_REVISION/N=6"
POLICY_LASG="/public/home/student090/results/challenge15/attestations/$BUNDLE_SHA256/policy.json"
SOURCE_LASG="/public/home/student090/results/challenge15/attestations/$BUNDLE_SHA256/source.json"
POLICY_QDES="/work/share/giggleliu/jiangweiqi/results/challenge15/attestations/$BUNDLE_SHA256/policy.json"
SOURCE_QDES="/work/share/giggleliu/jiangweiqi/results/challenge15/attestations/$BUNDLE_SHA256/source.json"
POLICY_SHA256="$(sha256sum "$POLICY_LASG" | awk '{print $1}')"
SOURCE_SHA256="$(sha256sum "$SOURCE_LASG" | awk '{print $1}')"
LASG_DEPLOYMENT_RECEIPT="/public/home/student090/results/challenge15/attestations/$BUNDLE_SHA256/deployment/lasg02"
QDES_DEPLOYMENT_RECEIPT="/work/share/giggleliu/jiangweiqi/results/challenge15/attestations/$BUNDLE_SHA256/deployment/qdeshell"
RUNTIME_SET_LOCAL="$("$LOCAL_INTERPRETER" -m challenge15.cli runtime-set-copy --manifest "$N6_RUNTIME_COPIES" --field local_path)"
RUNTIME_SET_LOCAL_SHA256="$("$LOCAL_INTERPRETER" -m challenge15.cli runtime-set-copy --manifest "$N6_RUNTIME_COPIES" --field local_sha256)"
CPU_RUNTIME_SET_REMOTE="$("$LOCAL_INTERPRETER" -m challenge15.cli runtime-set-copy --manifest "$N6_RUNTIME_COPIES" --field cpu_remote_path)"
CPU_RUNTIME_SET_RECEIPT="$("$LOCAL_INTERPRETER" -m challenge15.cli runtime-set-copy --manifest "$N6_RUNTIME_COPIES" --field cpu_receipt)"
GPU_RUNTIME_SET_REMOTE="$("$LOCAL_INTERPRETER" -m challenge15.cli runtime-set-copy --manifest "$N6_RUNTIME_COPIES" --field gpu_remote_path)"
GPU_RUNTIME_SET_RECEIPT="$("$LOCAL_INTERPRETER" -m challenge15.cli runtime-set-copy --manifest "$N6_RUNTIME_COPIES" --field gpu_receipt)"
RUNTIME_ATTESTATIONS="$CPU_RUNTIME_SET_REMOTE"
QDES_RUNTIME_ATTESTATION_SET="$GPU_RUNTIME_SET_REMOTE"
```

- [ ] **Step 0: Invoke the sole N6 production entry point**

```bash
"$LOCAL_INTERPRETER" -m challenge15.cli production-orchestrate-size \
  --particles 6 --rank-ladder 1,2,4,8 --seeds 0,1,2,3,4 \
  --base-config production/config/base-n6.json \
  --policy "$ATTEST_ROOT/policy.json" \
  --source-manifest "$ATTEST_ROOT/source.json" \
  --runtime-set-local "$RUNTIME_SET_LOCAL" \
  --runtime-set-local-sha256 "$RUNTIME_SET_LOCAL_SHA256" \
  --cpu-runtime-set-remote "$CPU_RUNTIME_SET_REMOTE" \
  --cpu-runtime-set-receipt "$CPU_RUNTIME_SET_RECEIPT" \
  --gpu-runtime-set-remote "$GPU_RUNTIME_SET_REMOTE" \
  --gpu-runtime-set-receipt "$GPU_RUNTIME_SET_RECEIPT" \
  --cpu-controller lasg02 --gpu-controller qdeshell \
  --cpu-profile production/slurm/profiles/lasg02.json \
  --gpu-profile production/slurm/profiles/qdeshell.json \
  --cpu-deployment-receipt "$LASG_DEPLOYMENT_RECEIPT" \
  --gpu-deployment-receipt "$QDES_DEPLOYMENT_RECEIPT" \
  --cpu-results-root "$LASG_ROOT" --gpu-results-root "$QDES_ROOT" \
  --state-root-base "$LOCAL_STATE_BASE" \
  --state-backup-uri "$STATE_BACKUP_URI" \
  --state-mirror-root "$STATE_MIRROR_ROOT" --create-only
```

Expected: `STOP_ACCEPTED` with a terminal-selection path, or `STOP_PENDING`
with a transition-receipt path. All remaining Phase 11 commands are internal
implementation contracts executed by the state machine, not operator steps.

Every following wrapper starts with:

```bash
INTERPRETER="$(resolve_interpreter \
  --deployment-receipt "$DEPLOYMENT_RECEIPT" \
  --runtime-attestations "$CONTROLLER_LOCAL_RUNTIME_SET" --role "$ROLE")"
test "${INTERPRETER#/}" != "$INTERPRETER"
"$INTERPRETER" -m challenge15.cli verify-execution-inputs \
  --source-manifest "$CONTROLLER_LOCAL_SOURCE_MANIFEST" \
  --runtime-set "$CONTROLLER_LOCAL_RUNTIME_SET" \
  --role "$ROLE" --controller "$CONTROLLER"
```

`CONTROLLER_LOCAL_RUNTIME_SET` is exactly `CPU_RUNTIME_SET_REMOTE` on the CPU
controller or `GPU_RUNTIME_SET_REMOTE` on Qdeshell;
`CONTROLLER_LOCAL_SOURCE_MANIFEST` and `CONTROLLER` come from the same
validated deployment receipt.
`resolve_interpreter` re-fingerprints the absolute executable and fails before
scientific CLI execution on any mismatch.

After any canonical publisher returns `CANONICAL_OUTPUT`, every wrapper runs:

```bash
"$INTERPRETER" -m challenge15.cli output-promotion \
  --state-key "$STATE_KEY_ENVELOPE" \
  --transition-intent "$ATTEMPT_INTENT" \
  --canonical-output "$CANONICAL_OUTPUT" \
  --expected-identity "$EXPECTED_OUTPUT_IDENTITY" \
  --publisher "$PUBLISHER_KIND" --controller "$CONTROLLER" \
  --output-dir "$PROMOTION_RECEIPT_ROOT" --create-only
```

On restart:

```bash
"$INTERPRETER" -m challenge15.cli select-published \
  --transition-intent "$ATTEMPT_INTENT" --publisher "$PUBLISHER_KIND" \
  --create-only-namespace "$PUBLISHER_NAMESPACE" \
  --promotion-output-dir "$PROMOTION_RECEIPT_ROOT" --print path
```

This prints no path for zero candidates, prints the unique validated path after
synthesizing a missing promotion receipt, and hard fails on multiple or
tampered permitted candidates.

- [ ] **Step 1: Create oracle**

Inside `oracle-lasg02.sbatch`:

```bash
"$INTERPRETER" -m challenge15.cli oracle \
  --particles 6 --policy "$POLICY_LASG" \
  --source-manifest "$SOURCE_LASG" \
  --runtime-attestations "$RUNTIME_ATTESTATIONS" \
  --output-dir "$LASG_ROOT/oracle" --create-only
```

- [ ] **Step 2: Create root extensions and train five seeds**

For each identity-map task, read `SEED`, deterministic `OWNER_UUID`, and the
resulting content-addressed `OWNER_ENVELOPE`; the map's `task_count=5` derives
array `0-4%5`. Then:

```bash
"$INTERPRETER" -m challenge15.cli claim-seed \
  --particles 6 --seed "$SEED" \
  --base-config production/config/base-n6.json \
  --policy "$POLICY_QDES" --source-manifest "$SOURCE_QDES" \
  --runtime-attestations "$QDES_RUNTIME_ATTESTATION_SET" \
  --destination "$QDES_ROOT/training/seed=$SEED" \
  --owner-uuid "$OWNER_UUID" --create-only
ROOT_DECISION="$("$INTERPRETER" -m challenge15.cli rank-extension-decision \
  --seed "$SEED" --current-rank none --new-rank 1 \
  --base-config production/config/base-n6.json --reason initial \
  --policy "$POLICY_QDES" --source-manifest "$SOURCE_QDES" \
  --runtime-attestations "$QDES_RUNTIME_ATTESTATION_SET" \
  --output-dir "$QDES_ROOT/rank-decisions" --create-only)"
EXTENSION="$("$INTERPRETER" -m challenge15.cli rank-extension \
  --particles 6 --seed "$SEED" \
  --base-config production/config/base-n6.json \
  --policy "$POLICY_QDES" --source-manifest "$SOURCE_QDES" \
  --runtime-attestations "$QDES_RUNTIME_ATTESTATION_SET" --reason initial \
  --decision "$ROOT_DECISION" \
  --output-dir "$QDES_ROOT/training/seed=$SEED/extensions" --create-only)"
"$INTERPRETER" -m challenge15.cli vmc-train \
  --base-config production/config/base-n6.json \
  --extension "$EXTENSION" \
  --policy "$POLICY_QDES" --source-manifest "$SOURCE_QDES" \
  --runtime-attestations "$QDES_RUNTIME_ATTESTATION_SET" \
  --owner "$OWNER_ENVELOPE" \
  --destination "$QDES_ROOT/training/seed=$SEED" --create-only
```

For ranks `2`, `4`, and policy-allowed `8`, the state transition supplies
`PREVIOUS_CYCLE_RECEIPT` as the verified `CycleOutcome.transition_receipt`
returned by the immediately preceding cycle; it is not operator input. The
internal contract is:

```bash
prepare_and_train_new_rank() {
  RANK="$1"
  PREVIOUS_CYCLE_RECEIPT="$2"
  if test "$RANK" -eq 8; then
    EXTENSION_REASON=rank_convergence_pending
  else
    EXTENSION_REASON=scheduled_initial_ladder
  fi
  CYCLE_RANKS="$("$LOCAL_INTERPRETER" -m challenge15.cli cycle-ranks \
    --previous-cycle-receipt "$PREVIOUS_CYCLE_RECEIPT" \
    --new-rank "$RANK" --print-tsv)"
  IFS=$'\t' read -r PREVIOUS_RANK PREVIOUS_EXPECTED_RANKS_CSV EXPECTED_RANKS_CSV \
    <<< "$CYCLE_RANKS"
  PRIOR_DECISION_IDENTITY_MAP="$("$LOCAL_INTERPRETER" -m challenge15.cli orchestration-output \
    --transition-receipt "$PREVIOUS_CYCLE_RECEIPT" \
    --field decision-export-identity-map)"
  PRIOR_DECISION_EXPORT_BUNDLE="$(ssh lasg02-student090 '"$LASG_INTERPRETER"' -m challenge15.cli export-bundle --bundle-role rank-decision-input --source-controller lasg02 --source-root '"$LASG_ROOT"' --artifacts-from '"$PRIOR_DECISION_IDENTITY_MAP"' --policy '"$POLICY_LASG"' --source-manifest '"$SOURCE_LASG"' --runtime-attestations '"$RUNTIME_ATTESTATIONS"' --output-dir '"$LASG_ROOT/exports/rank-decisions"' --create-only')"
  PRIOR_TRANSFER_RECEIPT="$(bash production/orchestrate/transfer_bundle.sh \
    --source-host lasg02-student090 --destination-host qdeshell \
    --source-controller lasg02 --destination-controller qdeshell \
    --source-root "$PRIOR_DECISION_EXPORT_BUNDLE" \
    --destination-root "$QDES_ROOT/imports/rank-decisions" \
    --bundle-role rank-decision-input \
    --policy "$POLICY_QDES" --source-manifest "$SOURCE_QDES" \
    --runtime-attestations "$RUNTIME_ATTESTATIONS" \
    --receipt-dir "$ATTEST_ROOT/transfers/N=6/rank=$RANK-decision-input" \
    --create-only)"
  PRIOR_IMPORT_BUNDLE="$("$LOCAL_INTERPRETER" -m challenge15.cli transfer-import \
    --receipt "$PRIOR_TRANSFER_RECEIPT" --print-path)"
  PRIOR_REDUCTION="$(ssh qdeshell '"$QDES_INTERPRETER"' -m challenge15.cli import-member --import '"$PRIOR_IMPORT_BUNDLE"' --kind reduction --print-path)"
  PRIOR_PROVISIONAL_FINALIZATION="$(ssh qdeshell '"$QDES_INTERPRETER"' -m challenge15.cli import-member --import '"$PRIOR_IMPORT_BUNDLE"' --kind provisional-finalization --print-path)"
  PRIOR_IMPORT_RECEIPT="$(ssh qdeshell '"$QDES_INTERPRETER"' -m challenge15.cli import-member --import '"$PRIOR_IMPORT_BUNDLE"' --kind import-receipt --print-path)"
  DECISION="$("$INTERPRETER" -m challenge15.cli rank-extension-decision \
    --seed "$SEED" --current-rank "$PREVIOUS_RANK" --new-rank "$RANK" \
    --base-config production/config/base-n6.json \
    --prior-reduction "$PRIOR_REDUCTION" \
    --prior-finalization "$PRIOR_PROVISIONAL_FINALIZATION" \
    --prior-import-receipt "$PRIOR_IMPORT_RECEIPT" \
    --prior-transfer-receipt "$PRIOR_TRANSFER_RECEIPT" \
    --reason "$EXTENSION_REASON" \
    --policy "$POLICY_QDES" --source-manifest "$SOURCE_QDES" \
    --runtime-attestations "$QDES_RUNTIME_ATTESTATION_SET" \
    --output-dir "$QDES_ROOT/rank-decisions" --create-only)"
  PARENT_MANIFEST="$("$INTERPRETER" -m challenge15.cli discover-generation \
    --seed-root "$QDES_ROOT/training/seed=$SEED" \
    --extension-root "$QDES_ROOT/training/seed=$SEED/extensions" \
    --expected-ranks "$PREVIOUS_EXPECTED_RANKS_CSV" \
    --policy "$POLICY_QDES" --source-manifest "$SOURCE_QDES" \
    --runtime-attestations "$QDES_RUNTIME_ATTESTATION_SET" --print-manifest)"
  EXTENSION="$("$INTERPRETER" -m challenge15.cli rank-extension \
    --particles 6 --seed "$SEED" \
    --base-config production/config/base-n6.json \
    --policy "$POLICY_QDES" --source-manifest "$SOURCE_QDES" \
    --runtime-attestations "$QDES_RUNTIME_ATTESTATION_SET" \
    --reason "$EXTENSION_REASON" \
    --parent-generation "$PARENT_MANIFEST" \
    --decision "$DECISION" \
    --output-dir "$QDES_ROOT/training/seed=$SEED/extensions" \
    --create-only)"
  "$INTERPRETER" -m challenge15.cli vmc-train \
    --base-config production/config/base-n6.json \
    --extension "$EXTENSION" \
    --policy "$POLICY_QDES" --source-manifest "$SOURCE_QDES" \
    --runtime-attestations "$QDES_RUNTIME_ATTESTATION_SET" \
    --owner "$OWNER_ENVELOPE" \
    --destination "$QDES_ROOT/training/seed=$SEED" --create-only
}
```

The extension constructor reads and records the parent parameter and optimizer
hashes from `PARENT_MANIFEST` and the decision payload hash; omission or
substitution fails. Before each function invocation, the orchestrator evaluates and
reduces the currently available ranks on the CPU controller and publishes
`PRIOR_PROVISIONAL_FINALIZATION`, keyed by `(N,base,expected-ranks-sha)`, so
the decision validates its prior reduction/finalization. Discovery
requires exact expected ranks and rejects missing or extra extension files. No
direct `--rank` argument exists.

- [ ] **Step 3: Transfer CPU oracle to Qdeshell**

The local orchestrator runs these exact transfers and verifies each receipt
before the next controller submission:

```bash
bash production/orchestrate/transfer_bundle.sh \
  --source-host lasg02-student090 --destination-host qdeshell \
  --source-controller lasg02 --destination-controller qdeshell \
  --source-root "$LASG_ROOT/oracle" \
  --destination-root "$QDES_ROOT/imports/oracle" \
  --bundle-role oracle \
  --policy "$POLICY_LASG" --source-manifest "$SOURCE_LASG" \
  --runtime-attestations "$RUNTIME_ATTESTATIONS" \
  --receipt-dir "$ATTEST_ROOT/transfers/N=6/oracle-to-qdes" --create-only
```

Expected: export, import, and transfer receipts validate; partial/stale/
duplicate/corrupt transfers submit no downstream job.

- [ ] **Step 4: Publish coordinate shards**

For only the current cycle's `new_rank` cross seeds `0..4`:

```bash
"$INTERPRETER" -m challenge15.cli coordinate-shard \
  --generation "$GENERATION_ENVELOPE" \
  --base-config production/config/base-n6.json \
  --policy "$POLICY_QDES" --source-manifest "$SOURCE_QDES" \
  --runtime-attestations "$QDES_RUNTIME_ATTESTATION_SET" \
  --destination "$QDES_ROOT/coordinate/rank=$RANK/seed=$SEED" \
  --receipt-dir "$QDES_ROOT/evaluation-receipts/coordinate/rank=$RANK/seed=$SEED" \
  --create-only
```

`RANK`, `SEED`, `ORACLE_ENVELOPE`, and `GENERATION_ENVELOPE` are exact values
read from the validated identity-map task selected by `SLURM_ARRAY_TASK_ID`.
The array bound is `0..task_count-1`; no path is inferred from a rank alias.

- [ ] **Step 5: Transfer GPU outputs, reduce, finalize, and transfer back**

The state transition derives `EXPECTED_RANKS_CSV` only by validating the exact
prior `CycleOutcome.previous_expected_ranks` and appending `new_rank`. The trace
is `[] -> [1] -> [1,2] -> [1,2,4] -> [1,2,4,8]`; no arithmetic or operator CSV
is accepted.

```bash
GPU_EXPORT_BUNDLE="$("$INTERPRETER" -m challenge15.cli export-bundle \
  --bundle-role training-coordinate --source-controller qdeshell \
  --source-root "$QDES_ROOT" \
  --artifacts-from "$GPU_EXPORT_IDENTITY_MAP" \
  --policy "$POLICY_QDES" --source-manifest "$SOURCE_QDES" \
  --runtime-attestations "$QDES_RUNTIME_ATTESTATION_SET" \
  --output-dir "$QDES_ROOT/exports/training-coordinate" --create-only)"
bash production/orchestrate/transfer_bundle.sh \
  --source-host qdeshell --destination-host lasg02-student090 \
  --source-controller qdeshell --destination-controller lasg02 \
  --source-root "$GPU_EXPORT_BUNDLE" \
  --destination-root "$LASG_ROOT/imports/training-and-coordinate" \
  --bundle-role training-coordinate \
  --policy "$POLICY_QDES" --source-manifest "$SOURCE_QDES" \
  --runtime-attestations "$RUNTIME_ATTESTATIONS" \
  --receipt-dir "$ATTEST_ROOT/transfers/N=6/gpu-to-lasg" --create-only
"$INTERPRETER" -m challenge15.cli exact-shard \
  --oracle "$ORACLE_ENVELOPE" \
  --generation "$GENERATION_ENVELOPE" \
  --policy "$POLICY_LASG" --source-manifest "$SOURCE_LASG" \
  --runtime-attestations "$RUNTIME_ATTESTATIONS" \
  --destination "$LASG_ROOT/exact/rank=$RANK/seed=$SEED" \
  --receipt-dir "$LASG_ROOT/evaluation-receipts/exact/rank=$RANK/seed=$SEED" \
  --determinant-block 256 --carrier-block 8 --quadrature-block 64 --create-only
if test "$RANK" -eq 1; then
  REDUCTION_IDENTITY_MAP="$("$INTERPRETER" -m challenge15.cli cumulative-reducer-identity-map \
    --particles 6 --expected-ranks "$EXPECTED_RANKS_CSV" --new-rank "$RANK" \
    --expected-seeds 0,1,2,3,4 \
    --new-coordinate-root "$LASG_ROOT/imports/training-and-coordinate" \
    --new-exact-root "$LASG_ROOT/exact/rank=$RANK" \
    --output-dir "$LASG_ROOT/identity-maps/reducer" --create-only)"
else
  REDUCTION_IDENTITY_MAP="$("$INTERPRETER" -m challenge15.cli cumulative-reducer-identity-map \
    --particles 6 --expected-ranks "$EXPECTED_RANKS_CSV" --new-rank "$RANK" \
    --expected-seeds 0,1,2,3,4 \
    --new-coordinate-root "$LASG_ROOT/imports/training-and-coordinate" \
    --new-exact-root "$LASG_ROOT/exact/rank=$RANK" \
    --previous-cycle-receipt "$PREVIOUS_CYCLE_RECEIPT" \
    --output-dir "$LASG_ROOT/identity-maps/reducer" --create-only)"
fi
REDUCTION_REFERENCE="$("$INTERPRETER" -m challenge15.cli reduce-size \
  --particles 6 --expected-ranks "$EXPECTED_RANKS_CSV" \
  --expected-seeds 0,1,2,3,4 \
  --identity-map "$REDUCTION_IDENTITY_MAP" \
  --oracle "$ORACLE_ENVELOPE" \
  --training-root "$LASG_ROOT/imports/training-and-coordinate" \
  --exact-root "$LASG_ROOT/exact" \
  --coordinate-root "$LASG_ROOT/imports/training-and-coordinate" \
  --policy "$POLICY_LASG" --source-manifest "$SOURCE_LASG" \
  --runtime-attestations "$RUNTIME_ATTESTATIONS" \
  --output-dir "$LASG_ROOT/reductions" \
  --receipt-dir "$LASG_ROOT/reduction-receipts" --create-only)"
IFS=$'\t' read -r REDUCTION_SHA256 REDUCTION_PATH <<< "$REDUCTION_REFERENCE"
test -n "$REDUCTION_SHA256"
test -n "$REDUCTION_PATH"
PROVISIONAL_FINALIZATION="$("$INTERPRETER" -m challenge15.cli finalize-reduction \
  --reduction "$REDUCTION_PATH" --reduction-sha256 "$REDUCTION_SHA256" \
  --policy "$POLICY_LASG" \
  --source-manifest "$SOURCE_LASG" \
  --runtime-attestations "$RUNTIME_ATTESTATIONS" \
  --output-dir "$LASG_ROOT/finalizations" --create-only)"
FINALIZATION_STATUS="$("$INTERPRETER" -m challenge15.cli finalization-status \
  --finalization "$PROVISIONAL_FINALIZATION" --print)"
if test "$FINALIZATION_STATUS" = accepted; then
  TERMINAL_SELECTION="$("$INTERPRETER" -m challenge15.cli select-terminal \
    --finalization "$PROVISIONAL_FINALIZATION" \
    --policy "$POLICY_LASG" --source-manifest "$SOURCE_LASG" \
    --runtime-attestations "$RUNTIME_ATTESTATIONS" \
    --output-dir "$LASG_ROOT/terminal-selections" --create-only)"
  ACCEPTED_TERMINAL_IDENTITY_MAP="$("$INTERPRETER" -m challenge15.cli accepted-terminal-identity-map \
    --terminal-selection "$TERMINAL_SELECTION" \
    --provisional-finalization "$PROVISIONAL_FINALIZATION" \
    --reduction "$REDUCTION_PATH" \
    --runtime-attestation-set "$RUNTIME_ATTESTATIONS" \
    --output-dir "$LASG_ROOT/identity-maps/accepted-terminal" --create-only)"
  ACCEPTED_TERMINAL_BUNDLE="$("$INTERPRETER" -m challenge15.cli export-bundle \
    --bundle-role accepted-terminal-result --source-controller lasg02 \
    --source-root "$LASG_ROOT" \
    --artifacts-from "$ACCEPTED_TERMINAL_IDENTITY_MAP" \
    --policy "$POLICY_LASG" --source-manifest "$SOURCE_LASG" \
    --runtime-attestations "$RUNTIME_ATTESTATIONS" \
    --output-dir "$LASG_ROOT/exports/accepted-terminal" --create-only)"
  bash production/orchestrate/transfer_bundle.sh \
    --source-host lasg02-student090 --destination-host qdeshell \
    --source-controller lasg02 --destination-controller qdeshell \
    --source-root "$ACCEPTED_TERMINAL_BUNDLE" \
    --destination-root "$QDES_ROOT/imports/accepted-terminal" \
    --bundle-role accepted-terminal-result \
    --policy "$POLICY_LASG" --source-manifest "$SOURCE_LASG" \
    --runtime-attestations "$RUNTIME_ATTESTATIONS" \
    --receipt-dir "$ATTEST_ROOT/transfers/N=6/accepted-terminal-to-qdes" \
    --create-only
fi
```

`GPU_EXPORT_IDENTITY_MAP` contains exactly the expected generation and
coordinate-shard envelope hashes for the current rank/seed cross-product.
`export-bundle` rejects present-but-unexpected files and no synthetic aggregate
root is permitted.

`prepare_and_train_new_rank` is invoked once only after the preceding cycle
returns pending and policy permits that exact next rank. Rank 8 gets
`rank_convergence_pending`, a separate five-task identity map/array, and then
the same coordinate/export/import/exact/fresh-reduce/provisional-finalize/
classify path. Accepted rank 8 selects and exports the terminal result; pending
rank 8 stops without calling terminal selection.

For each rank-8 array identity, `train-qdeshell.sbatch` executes:

```bash
EXTENSION="$("$INTERPRETER" -m challenge15.cli rank-extension \
  --particles 6 --seed "$SEED" \
  --base-config production/config/base-n6.json \
  --policy "$POLICY_QDES" --source-manifest "$SOURCE_QDES" \
  --runtime-attestations "$QDES_RUNTIME_ATTESTATION_SET" \
  --reason rank_convergence_pending \
  --parent-generation "$PARENT_MANIFEST" --decision "$DECISION" \
  --output-dir "$QDES_ROOT/training/seed=$SEED/extensions" --create-only)"
"$INTERPRETER" -m challenge15.cli vmc-train \
  --base-config production/config/base-n6.json --extension "$EXTENSION" \
  --policy "$POLICY_QDES" --source-manifest "$SOURCE_QDES" \
  --runtime-attestations "$QDES_RUNTIME_ATTESTATION_SET" --owner "$OWNER_ENVELOPE" \
  --destination "$QDES_ROOT/training/seed=$SEED" --create-only
```

---

## Phase 12: N=7 Production

### Task 12: Validate N=6 synchronously before submission

```bash
N6_TERMINAL_SELECTION="/public/home/student090/results/challenge15/runs/$SOURCE_REVISION/N=6/terminal-selections/N=6/base=$N6_BASE_SHA256/$N6_TERMINAL_SELECTION_SHA256.json"
LOCAL_STATE_BASE="${XDG_STATE_HOME:-$HOME/.local/state}/challenge15"
STATE_MIRROR_ROOT="$HOME/.local/state/challenge15-mirror"
STATE_BACKUP_URI="ssh://lasg02-student090/public/home/student090/results/challenge15/orchestration-backups"
N7_LASG_ROOT="/public/home/student090/results/challenge15/runs/$SOURCE_REVISION/N=7"
N7_QDES_ROOT="/work/share/giggleliu/jiangweiqi/results/challenge15/runs/$SOURCE_REVISION/N=7"
N7_RUNTIME_SET_LOCAL="$("$LOCAL_INTERPRETER" -m challenge15.cli runtime-set-copy --manifest "$N7_RUNTIME_COPIES" --field local_path)"
N7_RUNTIME_SET_LOCAL_SHA256="$("$LOCAL_INTERPRETER" -m challenge15.cli runtime-set-copy --manifest "$N7_RUNTIME_COPIES" --field local_sha256)"
N7_CPU_RUNTIME_SET_REMOTE="$("$LOCAL_INTERPRETER" -m challenge15.cli runtime-set-copy --manifest "$N7_RUNTIME_COPIES" --field cpu_remote_path)"
N7_CPU_RUNTIME_SET_RECEIPT="$("$LOCAL_INTERPRETER" -m challenge15.cli runtime-set-copy --manifest "$N7_RUNTIME_COPIES" --field cpu_receipt)"
N7_GPU_RUNTIME_SET_REMOTE="$("$LOCAL_INTERPRETER" -m challenge15.cli runtime-set-copy --manifest "$N7_RUNTIME_COPIES" --field gpu_remote_path)"
N7_GPU_RUNTIME_SET_RECEIPT="$("$LOCAL_INTERPRETER" -m challenge15.cli runtime-set-copy --manifest "$N7_RUNTIME_COPIES" --field gpu_receipt)"
"$LOCAL_INTERPRETER" -m challenge15.cli production-orchestrate-size \
  --particles 7 --rank-ladder 1,2,4,8 --seeds 0,1,2,3,4 \
  --base-config production/config/base-n7.json \
  --policy "$ATTEST_ROOT/policy.json" \
  --source-manifest "$ATTEST_ROOT/source.json" \
  --runtime-set-local "$N7_RUNTIME_SET_LOCAL" \
  --runtime-set-local-sha256 "$N7_RUNTIME_SET_LOCAL_SHA256" \
  --cpu-runtime-set-remote "$N7_CPU_RUNTIME_SET_REMOTE" \
  --cpu-runtime-set-receipt "$N7_CPU_RUNTIME_SET_RECEIPT" \
  --gpu-runtime-set-remote "$N7_GPU_RUNTIME_SET_REMOTE" \
  --gpu-runtime-set-receipt "$N7_GPU_RUNTIME_SET_RECEIPT" \
  --cpu-controller lasg02 --gpu-controller qdeshell \
  --cpu-profile production/slurm/profiles/lasg02.json \
  --gpu-profile production/slurm/profiles/qdeshell.json \
  --cpu-deployment-receipt "$LASG_DEPLOYMENT_RECEIPT" \
  --gpu-deployment-receipt "$QDES_DEPLOYMENT_RECEIPT" \
  --cpu-results-root "$N7_LASG_ROOT" --gpu-results-root "$N7_QDES_ROOT" \
  --state-root-base "$LOCAL_STATE_BASE" \
  --state-backup-uri "$STATE_BACKUP_URI" \
  --state-mirror-root "$STATE_MIRROR_ROOT" \
  --prerequisite-terminal-selection "$N6_TERMINAL_SELECTION" \
  --create-only
```

Expected: prerequisite validation occurs inside the state machine before any
submission; output is `STOP_ACCEPTED` or `STOP_PENDING`.

---

## Phase 13: N=8 Production

### Task 13: Validate N=7 and require WUZH02 profile

```bash
test -s production/slurm/profiles/wuzh02.json
"$INTERPRETER" -m challenge15.cluster_profile verify \
  --profile production/slurm/profiles/wuzh02.json \
  --minimum-cores 128 --minimum-memory-mib 500000
WUZH_RESULTS_ROOT="$("$INTERPRETER" -m challenge15.cluster_profile get --profile production/slurm/profiles/wuzh02.json --field results_root)"
WUZH_DEPLOYMENT_RECEIPT="$WUZH_RESULTS_ROOT/challenge15/attestations/$BUNDLE_SHA256/deployment/wuzh02"
N8_WUZH_ROOT="$WUZH_RESULTS_ROOT/challenge15/runs/$SOURCE_REVISION/N=8"
N8_QDES_ROOT="/work/share/giggleliu/jiangweiqi/results/challenge15/runs/$SOURCE_REVISION/N=8"
N8_STATE_BACKUP_URI="ssh://wuzh02${WUZH_RESULTS_ROOT}/challenge15/orchestration-backups"
N8_RUNTIME_SET_LOCAL="$("$LOCAL_INTERPRETER" -m challenge15.cli runtime-set-copy --manifest "$N8_RUNTIME_COPIES" --field local_path)"
N8_RUNTIME_SET_LOCAL_SHA256="$("$LOCAL_INTERPRETER" -m challenge15.cli runtime-set-copy --manifest "$N8_RUNTIME_COPIES" --field local_sha256)"
N8_CPU_RUNTIME_SET_REMOTE="$("$LOCAL_INTERPRETER" -m challenge15.cli runtime-set-copy --manifest "$N8_RUNTIME_COPIES" --field cpu_remote_path)"
N8_CPU_RUNTIME_SET_RECEIPT="$("$LOCAL_INTERPRETER" -m challenge15.cli runtime-set-copy --manifest "$N8_RUNTIME_COPIES" --field cpu_receipt)"
N8_GPU_RUNTIME_SET_REMOTE="$("$LOCAL_INTERPRETER" -m challenge15.cli runtime-set-copy --manifest "$N8_RUNTIME_COPIES" --field gpu_remote_path)"
N8_GPU_RUNTIME_SET_RECEIPT="$("$LOCAL_INTERPRETER" -m challenge15.cli runtime-set-copy --manifest "$N8_RUNTIME_COPIES" --field gpu_receipt)"
N7_TERMINAL_SELECTION="/public/home/student090/results/challenge15/runs/$SOURCE_REVISION/N=7/terminal-selections/N=7/base=$N7_BASE_SHA256/$N7_TERMINAL_SELECTION_SHA256.json"
"$LOCAL_INTERPRETER" -m challenge15.cli production-orchestrate-size \
  --particles 8 --rank-ladder 1,2,4,8 --seeds 0,1,2,3,4 \
  --base-config production/config/base-n8.json \
  --policy "$ATTEST_ROOT/policy.json" \
  --source-manifest "$ATTEST_ROOT/source.json" \
  --runtime-set-local "$N8_RUNTIME_SET_LOCAL" \
  --runtime-set-local-sha256 "$N8_RUNTIME_SET_LOCAL_SHA256" \
  --cpu-runtime-set-remote "$N8_CPU_RUNTIME_SET_REMOTE" \
  --cpu-runtime-set-receipt "$N8_CPU_RUNTIME_SET_RECEIPT" \
  --gpu-runtime-set-remote "$N8_GPU_RUNTIME_SET_REMOTE" \
  --gpu-runtime-set-receipt "$N8_GPU_RUNTIME_SET_RECEIPT" \
  --cpu-controller wuzh02 --gpu-controller qdeshell \
  --cpu-profile production/slurm/profiles/wuzh02.json \
  --gpu-profile production/slurm/profiles/qdeshell.json \
  --cpu-deployment-receipt "$WUZH_DEPLOYMENT_RECEIPT" \
  --gpu-deployment-receipt "$QDES_DEPLOYMENT_RECEIPT" \
  --cpu-results-root "$N8_WUZH_ROOT" --gpu-results-root "$N8_QDES_ROOT" \
  --state-root-base "$LOCAL_STATE_BASE" \
  --state-backup-uri "$N8_STATE_BACKUP_URI" \
  --state-mirror-root "$STATE_MIRROR_ROOT" \
  --prerequisite-terminal-selection "$N7_TERMINAL_SELECTION" \
  --create-only
```

Expected: the state machine validates N7 and WUZH02 before submission, executes
the complete rank ladder including rank 8 when required, and returns
`STOP_ACCEPTED` or `STOP_PENDING`.

---

## Phase 14: Cross-Size Manifest and Report

### Task 14: Publish only after three semantic acceptances

`submit_cross_size.sh` requires exactly:

```text
--n6-terminal-selection PATH --n7-terminal-selection PATH
--n8-terminal-selection PATH --runtime-attestation-set-n6 PATH
--runtime-attestation-set-n7 PATH --runtime-attestation-set-n8 PATH
--n8-provisional-finalization PATH --n8-reduction PATH
--n8-import-receipt PATH --n8-transfer-receipt PATH
--policy PATH --source-manifest PATH
--deployment-receipt PATH --output-dir PATH --receipt-dir PATH --create-only
```

The cross-size payload fields are `n6_sha256`, `n7_sha256`, `n8_sha256`,
`n6_terminal_selection_sha256`, `n7_terminal_selection_sha256`,
`n8_terminal_selection_sha256`, `particles=[6,7,8]`,
`base_configuration_sha256_by_size`, `runtime_attestation_sets_by_size`,
`lineage`, `production_accepted_n6_n8`, and `claim`.
The final-report payload fields are `cross_size_manifest_sha256`,
`particles=[6,7,8]`, `base_configuration_sha256_by_size`, `size_summaries`,
`runtime_attestation_sets_by_size`, `source_manifest_sha256`, `policy_sha256`,
`resource_summary`, `statistical_summary`, `failed_gates`,
`production_accepted_n6_n8`, and `statement`. Aggregate schemas are exempt from
singular `particles` and `base_configuration_sha256`.

First export and import the N8 accepted terminal result from WUZH02 to LASG02:

```bash
N6_RUNTIME_ATTESTATION_SET="$LASG_SET_ROOT/N=6/$N6_RUNTIME_SET_SHA256.json"
N7_RUNTIME_ATTESTATION_SET="$LASG_SET_ROOT/N=7/$N7_RUNTIME_SET_SHA256.json"
N8_RUNTIME_ATTESTATION_SET="$WUZH_SET_ROOT/N=8/$N8_RUNTIME_SET_SHA256.json"
N8_TERMINAL_SELECTION="$N8_WUZH_ROOT/terminal-selections/N=8/base=$N8_BASE_SHA256/$N8_TERMINAL_SELECTION_SHA256.json"
N8_SET_IDENTITY_MAP="$(ssh wuzh02 '"$WUZH_INTERPRETER"' -m challenge15.cli runtime-set-identity-map --runtime-attestation-set '"$N8_RUNTIME_ATTESTATION_SET"' --output-dir '"$N8_WUZH_ROOT/identity-maps/runtime-set"' --create-only)"
N8_SET_BUNDLE="$(ssh wuzh02 '"$WUZH_INTERPRETER"' -m challenge15.cli export-bundle --bundle-role runtime-attestation-set --source-controller wuzh02 --source-root '"$N8_WUZH_ROOT"' --artifacts-from '"$N8_SET_IDENTITY_MAP"' --policy '"$POLICY_WUZH"' --source-manifest '"$SOURCE_WUZH"' --runtime-attestations '"$N8_RUNTIME_ATTESTATION_SET"' --output-dir '"$N8_WUZH_ROOT/exports/runtime-set"' --create-only)"
N8_SET_TRANSFER_RECEIPT="$(bash production/orchestrate/transfer_bundle.sh \
  --source-host wuzh02 --destination-host lasg02-student090 \
  --source-controller wuzh02 --destination-controller lasg02 \
  --source-root "$N8_SET_BUNDLE" \
  --destination-root "$LASG_FINAL_ROOT/imports/N=8-runtime-set" \
  --bundle-role runtime-attestation-set \
  --policy "$POLICY_LASG" --source-manifest "$SOURCE_LASG" \
  --runtime-attestations "$N8_RUNTIME_ATTESTATION_SET" \
  --receipt-dir "$ATTEST_ROOT/transfers/N=8/runtime-set-to-lasg02" --create-only)"
N8_SET_IMPORT="$("$LOCAL_INTERPRETER" -m challenge15.cli transfer-import \
  --receipt "$N8_SET_TRANSFER_RECEIPT" --print-path)"
N8_RUNTIME_ATTESTATION_SET_LASG="$(ssh lasg02-student090 '"$LASG_INTERPRETER"' -m challenge15.cli import-member --import '"$N8_SET_IMPORT"' --kind runtime-attestation-set --print-path)"
N8_PROVISIONAL_FINALIZATION="$(ssh wuzh02 '"$WUZH_INTERPRETER"' -m challenge15.cli terminal-member --terminal-selection '"$N8_TERMINAL_SELECTION"' --kind provisional-finalization --print-path)"
N8_REDUCTION="$(ssh wuzh02 '"$WUZH_INTERPRETER"' -m challenge15.cli terminal-member --terminal-selection '"$N8_TERMINAL_SELECTION"' --kind reduction --print-path)"
N8_ACCEPTED_EXPORT_IDENTITY_MAP="$(ssh wuzh02 '"$WUZH_INTERPRETER"' -m challenge15.cli accepted-terminal-identity-map --terminal-selection '"$N8_TERMINAL_SELECTION"' --provisional-finalization '"$N8_PROVISIONAL_FINALIZATION"' --reduction '"$N8_REDUCTION"' --runtime-attestation-set '"$N8_RUNTIME_ATTESTATION_SET"' --output-dir '"$N8_WUZH_ROOT/identity-maps/accepted-terminal"' --create-only)"
N8_EXPORT_BUNDLE="$(ssh wuzh02 '"$WUZH_INTERPRETER"' -m challenge15.cli export-bundle --bundle-role accepted-terminal-result --source-controller wuzh02 --source-root '"$N8_WUZH_ROOT"' --artifacts-from '"$N8_ACCEPTED_EXPORT_IDENTITY_MAP"' --policy '"$POLICY_WUZH"' --source-manifest '"$SOURCE_WUZH"' --runtime-attestations '"$N8_RUNTIME_ATTESTATION_SET"' --output-dir '"$N8_WUZH_ROOT/exports"' --create-only')"
N8_STAGED_BUNDLE="$(bash production/orchestrate/transfer_bytes.sh \
  --source-host wuzh02 --destination-host lasg02-student090 \
  --source-controller wuzh02 --destination-controller lasg02 \
  --bundle "$N8_EXPORT_BUNDLE" \
  --destination-root "$LASG_FINAL_ROOT/imports/N=8-accepted" \
  --create-only)"
N8_IMPORT_BUNDLE="$(ssh lasg02-student090 '"$LASG_INTERPRETER"' -m challenge15.cli import-bundle --bundle '"$N8_STAGED_BUNDLE"' --destination-controller lasg02 --destination-root '"$LASG_FINAL_ROOT/imports/N=8-accepted"' --profile production/slurm/profiles/lasg02.json --output-dir '"$LASG_FINAL_ROOT/import-receipts/N=8"' --create-only')"
N8_RUNTIME_ATTESTATION_SET_FROM_RESULT="$(ssh lasg02-student090 '"$LASG_INTERPRETER"' -m challenge15.cli import-member --import '"$N8_IMPORT_BUNDLE"' --kind runtime-attestation-set --print-path)"
test "$(ssh lasg02-student090 sha256sum '"$N8_RUNTIME_ATTESTATION_SET_FROM_RESULT"' | awk '{print $1}')" = "$(ssh lasg02-student090 sha256sum '"$N8_RUNTIME_ATTESTATION_SET_LASG"' | awk '{print $1}')"
N8_PROVISIONAL_FINALIZATION_LASG="$(ssh lasg02-student090 '"$LASG_INTERPRETER"' -m challenge15.cli import-member --import '"$N8_IMPORT_BUNDLE"' --kind provisional-finalization --print-path)"
N8_REDUCTION_LASG="$(ssh lasg02-student090 '"$LASG_INTERPRETER"' -m challenge15.cli import-member --import '"$N8_IMPORT_BUNDLE"' --kind reduction --print-path)"
N8_TRANSFER_RECEIPT="$(ssh lasg02-student090 '"$LASG_INTERPRETER"' -m challenge15.cli transfer-receipt --export '"$N8_STAGED_BUNDLE/export.json"' --import '"$N8_IMPORT_BUNDLE"' --source-controller wuzh02 --destination-controller lasg02 --policy '"$POLICY_LASG"' --source-manifest '"$SOURCE_LASG"' --runtime-attestations '"$N8_RUNTIME_ATTESTATION_SET_LASG"' --output-dir '"$LASG_FINAL_ROOT/transfer-receipts/N=8"' --create-only')"
ssh lasg02-student090 '"$LASG_INTERPRETER"' -m challenge15.cli verify-transfer --export '"$N8_STAGED_BUNDLE/export.json"' --import '"$N8_IMPORT_BUNDLE"' --receipt '"$N8_TRANSFER_RECEIPT"' --policy '"$POLICY_LASG"' --source-manifest '"$SOURCE_LASG"' --runtime-attestations '"$N8_RUNTIME_ATTESTATION_SET_LASG"'
N8_TERMINAL_SELECTION_LASG="$(ssh lasg02-student090 '"$LASG_INTERPRETER"' -m challenge15.cli import-member --import '"$N8_IMPORT_BUNDLE"' --kind terminal-selection --print-path)"
```

`N8_ACCEPTED_EXPORT_IDENTITY_MAP` names exactly the N8 terminal selection,
selected accepted provisional finalization, selected reduction, and N8 runtime
set. `import-member` resolves all four LASG02-local paths; the terminal
selection, finalization, reduction, and runtime set remain bound to
`N8_IMPORT_BUNDLE` and `N8_TRANSFER_RECEIPT`. Cross-size submission is
forbidden before `verify-transfer` exits zero.

```bash
bash production/slurm/submit_cross_size.sh \
  --n6-terminal-selection "$N6_TERMINAL_SELECTION" \
  --n7-terminal-selection "$N7_TERMINAL_SELECTION" \
  --n8-terminal-selection "$N8_TERMINAL_SELECTION_LASG" \
  --runtime-attestation-set-n6 "$N6_RUNTIME_ATTESTATION_SET" \
  --runtime-attestation-set-n7 "$N7_RUNTIME_ATTESTATION_SET" \
  --runtime-attestation-set-n8 "$N8_RUNTIME_ATTESTATION_SET_LASG" \
  --n8-provisional-finalization "$N8_PROVISIONAL_FINALIZATION_LASG" \
  --n8-reduction "$N8_REDUCTION_LASG" \
  --n8-import-receipt "$N8_IMPORT_BUNDLE" \
  --n8-transfer-receipt "$N8_TRANSFER_RECEIPT" \
  --policy "$POLICY_LASG" --source-manifest "$SOURCE_LASG" \
  --deployment-receipt "$LASG_DEPLOYMENT_RECEIPT" \
  --output-dir "/public/home/student090/results/challenge15/runs/$SOURCE_REVISION/final/cross-size" \
  --receipt-dir "/public/home/student090/results/challenge15/runs/$SOURCE_REVISION/final/submission-receipts" \
  --create-only
```

Inside the submitted reducer wrapper, after resolving and re-fingerprinting
the interpreter:

```bash
INTERPRETER="$(resolve_interpreter \
  --deployment-receipt "$LASG_DEPLOYMENT_RECEIPT" \
  --runtime-attestations "$N6_RUNTIME_ATTESTATION_SET" --role reducer)"
CROSS_SIZE_MANIFEST="$("$INTERPRETER" -m challenge15.cli reduce-cross-size \
  --n6-terminal-selection "$N6_TERMINAL_SELECTION" \
  --n7-terminal-selection "$N7_TERMINAL_SELECTION" \
  --n8-terminal-selection "$N8_TERMINAL_SELECTION_LASG" \
  --runtime-attestation-set-n6 "$N6_RUNTIME_ATTESTATION_SET" \
  --runtime-attestation-set-n7 "$N7_RUNTIME_ATTESTATION_SET" \
  --runtime-attestation-set-n8 "$N8_RUNTIME_ATTESTATION_SET_LASG" \
  --n8-provisional-finalization "$N8_PROVISIONAL_FINALIZATION_LASG" \
  --n8-reduction "$N8_REDUCTION_LASG" \
  --n8-import-receipt "$N8_IMPORT_BUNDLE" \
  --n8-transfer-receipt "$N8_TRANSFER_RECEIPT" \
  --policy "$POLICY_LASG" --source-manifest "$SOURCE_LASG" \
  --output-dir "/public/home/student090/results/challenge15/runs/$SOURCE_REVISION/final/cross-size" \
  --receipt-dir "/public/home/student090/results/challenge15/runs/$SOURCE_REVISION/final/reduction-receipts" \
  --create-only)"
"$INTERPRETER" -m challenge15.cli report \
  --cross-size-manifest "$CROSS_SIZE_MANIFEST" \
  --policy "$POLICY_LASG" --source-manifest "$SOURCE_LASG" \
  --runtime-attestation-set-n6 "$N6_RUNTIME_ATTESTATION_SET" \
  --runtime-attestation-set-n7 "$N7_RUNTIME_ATTESTATION_SET" \
  --runtime-attestation-set-n8 "$N8_RUNTIME_ATTESTATION_SET_LASG" \
  --n8-provisional-finalization "$N8_PROVISIONAL_FINALIZATION_LASG" \
  --n8-reduction "$N8_REDUCTION_LASG" \
  --n8-import-receipt "$N8_IMPORT_BUNDLE" \
  --n8-transfer-receipt "$N8_TRANSFER_RECEIPT" \
  --output-dir "/public/home/student090/results/challenge15/runs/$SOURCE_REVISION/final/reports" \
  --receipt-dir "/public/home/student090/results/challenge15/runs/$SOURCE_REVISION/final/report-receipts" \
  --create-only
```

`WUZH_RESULTS_ROOT` is read from the committed validated WUZH02 profile by
`submit_cross_size.sh`; direct operator input is rejected. The script validates
all three immutable terminal selections, their selected accepted provisional
finalizations/reductions, controller-indexed per-size attestation sets,
source/policy lineage, and exact particle sequence
before publishing a create-only submission receipt. A missing accepted terminal
selection publishes deterministic pending; malformed, stale, duplicate, or
provisional-only input publishes nothing.

Expected accepted wording only if all three payloads semantically pass:

```text
Production accepted for finite-size lowest-L=2 sector gaps at N=6,7,8 only; no chiral response or thermodynamic-limit claim is made.
```

Otherwise the canonical output is pending:

```text
Production pending; no N=6..8 production claim is made.
```

Tests invoke `submit_cross_size.sh` and `report` with accepted, pending,
provisional-only, wrong-particle-list, singular aggregate base hash,
stale-policy, swapped LASG02/WUZH02 runtime hashes, missing N8 import receipt,
duplicate, and create-only-conflict fixtures. They validate
`challenge15.report-receipt.v1` fields `particles`,
`base_configuration_sha256_by_size`, `final_report_sha256`, `markdown_sha256`,
`cross_size_manifest_sha256`, `runtime_attestation_sets_by_size`,
`source_manifest_sha256`, `policy_sha256`, `started_at_utc`,
`finished_at_utc`, `hostname`, and `interpreter_sha256`;
assert exact wording, canonical JSON byte identity under shuffled input,
receipt non-identity allowance, and no accepted wording in any pending report.

## Stop and Fallback Rules

- Candidate local compatibility never substitutes for final target attestation.
- Any source change after attestation invalidates all role/controller
  attestations and every set assembled from them;
  post-attestation tracked/untracked and member-hash checks are mandatory.
- Malformed, duplicate, unexpected, stale, or forked inputs hard fail with no
  reducer output.
- Missing expected valid identities publish deterministic pending.
- OOM changes only microbatch/carrier/quadrature block sizes; total
  walkers/draws/PRNG/update schedule remain fixed.
- Walker-count changes create a new base identity.
- Metric disagreement or threshold ambiguity is pending.
- Pending N6 submits no N7; pending N7 submits no N8.
- A partial, stale, duplicate, or corrupt transfer submits no destination job;
  cross-controller `afterok` is forbidden.
- Prerequisites consume only immutable accepted terminal selections; each
  expected-rank set has a distinct provisional-finalization namespace.
- Production wrappers never invoke a bare interpreter.
- WUZH02 is unused until its exact profile is committed and attested.
- Generated artifacts are never committed.
- A valid canonical output forbids resubmission/republication; recovery may
  synthesize only missing promotion/transition receipts and/or marker.
- `/tmp` and `/var/tmp` are forbidden for orchestration state; disaster backup
  must be a profile-approved SSH URI on a distinct remote failure domain.
- A sibling/local duplicate is a mirror and cannot satisfy backup validation.

## Plan Self-Review

- Runtime order: candidate lock first; final source-bound target attestation
  follows all eight source tasks.
- Runtime contract: CPython 3.12, JAX/JAXlib 0.4.38, bundled CUDA extra,
  hash-locked NVIDIA wheels, and exact download constraints are specified.
- VMC: every optimizer/sampler/evaluation field, score pytree, finite-chain
  correction, refresh/re-equilibration, and diagnostic gate is explicit.
- Append-only storage: no mutable pointer; ownership, snapshots, generations,
  hash-named rank extensions, seed claims, full rank-1/2/4 lifecycle, and
  unique-terminal discovery are exact.
- Reducer: invalid versus missing inputs and payload versus receipt semantics
  are unambiguous.
- Resources: Qdeshell and LASG02 directives/roots are exact; WUZH02 is blocked
  until an audited profile exists before source freeze.
- Transfer: source/destination identities, SHA256SUMS, unique partial upload,
  atomic rename, import/transfer receipts, and synchronous orchestration are
  explicit in both directions.
- Bootstrap: individual allowed-runtime envelopes move under the dedicated
  deployment/source/policy-authenticated schema before per-size sets exist.
- Runtime: role/controller-indexed per-size sets and deployment-receipt
  interpreter re-fingerprinting replace the singular runtime digest; local,
  CPU-remote, and GPU-remote copies have separate paths/receipts and equal
  canonical hashes.
- Reduction: expected-rank-hash provisional namespaces, decision-bound
  non-root extensions, five-task rank-8 arrays, accepted terminal selection,
  and terminal-only prerequisites are explicit.
- Statistics: chain/walker state layout, flattened gradient sample count,
  independent-sector Monte Carlo variance, paired-seed covariance, and rank
  change uncertainty formulas have tests.
- Commands: every CLI has a complete contract; array variables come only from
  deterministic identity-map artifacts.
- Acceptance: complete five-seed coverage, identical paired sets, four final
  passes, current transition rules, independent coordinate shards, and
  prerequisite order are preserved.
- Pytest: validation uses `-m "not production"`; target statistical/runtime
  tests use the `production` marker during attestation.
- Byte identity applies only to canonical scientific payloads, never execution
  receipts.
- Schema appears only in the three-field envelope; all payload schema
  duplication is forbidden.
- Lifecycle: rank1 reduction/provisional finalization, decision-bound ranks 2
  and 4, optional decision-bound rank 8, accepted terminal selection, and
  terminal-only N6-to-N7-to-N8 prerequisites are ordered explicitly.
- Collation: the N8 terminal result is exported from WUZH02, imported and
  verified on LASG02, and reduced with three controller-preserving per-size
  runtime sets.
- Entry point: N6, N7, and N8 are invoked only through
  `production-orchestrate-size`; every manual command is an internal transition
  contract.
- Trace: N6 executes local set verification, Qdeshell set import, oracle,
  root decision/rank1, decision-bound ranks 2/4, optional full rank8,
  destination-local exact reduction/finalization, accepted terminal export, or
  deterministic pending stop.
- Restart: every N6 transition checks its actual canonical publisher before
  acting and recovers after artifact/transfer/scheduler/
  receipt/marker crash windows without repeating an external action.
- Cycles: rank 1/2/4/8 compute only five new identities; cumulative reducer
  maps reuse verified old coordinate/exact hashes without republishing them.
- State: every immutable input changes the state key; local state is durable,
  disaster backup uses transfer-once to a distinct profile-approved SSH root,
  and local duplicates are mirrors only.
- Source: final and pre-execution verification covers source, production code,
  configs, scripts, tests, project metadata, locks, and every attestation test
  member.
- Rank trace: exact prior outcomes produce only
  `[] -> [1] -> [1,2] -> [1,2,4] -> [1,2,4,8]`; arithmetic expected-rank
  derivation is absent.
- Exactly once: attempt intent precedes action; remote submit-once and
  transfer-once claim deterministic correlation IDs and recover receipt/
  scheduler/destination evidence before any repeat action.
- Crash review: post-`sbatch` recovery finds the original job through remote
  receipt or exact scheduler evidence; post-canonical-publication recovery
  adopts exactly one intent-permitted candidate only after independently
  recomputing and validating its hash/provenance/parents, then invokes only the
  missing promotion/transition receipt and marker publishers. Zero candidates
  permits action; multiple or tampered candidates hard fail before action.
