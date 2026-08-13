# Challenge 194 Standalone Coarse-Grid P0 Extension v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, submit, verify, and analyze the preregistered 192-cell standalone coarse-grid P0 extension v2, then publish an exploratory P1-v2 protocol only if all seven fail-closed authorization checks pass.

**Architecture:** Generalize the release-ready v1 extension contracts, builders, runners, immutable publication, verified snapshots, and transfer machinery around an explicit versioned campaign contract; do not fork the scientific engine or selector. Finish the protocol/run-spec/worker critical path first and deploy that exact clean commit, then implement bounded v2 aggregation and authenticated authorization evidence locally while Slurm runs. Authorization v3 copies untouched authenticated P0 controls, uses only standalone v2 blocked-sigma rows, deeply recomputes every source, and feeds the byte-identical selector physics through a new schema adapter.

**Tech Stack:** Python 3.12, NumPy, h5py, pytest, Ruff 0.16.0, Bash, Git bundles, rsync, Slurm via `scripts/harness_slurm.sh`, and the existing `long_range_percolation` Pilot/artifact/counter-RNG APIs.

## Global Constraints

- Repository: `/home/footman/code/quantum.harness-challenge-194`, branch `challenge/194`.
- Approved design: `docs/superpowers/specs/2026-07-30-challenge-194-p0-extension-v2-design.md` at commit `b67725339a1b0bb9a86a0b8711ae2bb980188f1c`.
- Design-file SHA256: `724403246992a9b31d462a85c69aa893aaf5dea2244451e58685c2c2994a917a`.
- Never modify or stage `.superpowers/sdd/task-1-report.md`, `.superpowers/sdd/progress.md`, generated `results/`, or unrelated dirty files.
- Original P0 hashes: run spec `d17d3df9528a09f0d834ebe9d5ce6f283e488d2326f6cb14873a90923c5d9840`, progress `ea29a8163a5d3e85768842d64fac4c719f5aeadf965b3318b305fb7a2cc2d15f`, analysis document `e42ef6b9f82380305f80ceaba384bc29cb9fe2da0848d4c72a904f4cb4c8c7c8`, analysis file `44083701db692304cd3aa054c8a9488b75674cead7cd6bf479c0a203cc1fa10b`, bracket document `fb3df666044bf9531443fc00c5c2c2d489512b4162864b3a92ffc2e756832403`, source revision `739880d9ccdcffbfc8a15310250349bd11d63bbb`.
- V1 hashes: protocol document `a37ab41f3224594e61f4eebbe292975aeec449b9ecb7893e3e54f18d82d53321`, protocol file `e363a60f842b11b32972c7a68ec1c5f237741bc45bc79ab8bf93f51f6760d84d`, run spec `c1ca9b6c8ba751919c6d9337fe1cd4c09a57ed9b99abbb9d3ebfed7f89c3d32e`, progress `c78d1fb03daf19297ef9e0617410c68a6a364bffc2f2888dfa9067e7e8d6b65f`, analysis document `79232574d314348c29a40cd2fbb7690e96f3cae5f26843bd4f1cf07cb6a1f45b`, analysis file `d8fdd60a6de83cf3818349d4440f49f4a38bb5acd7fff1dab9b56ded4da913e5`, source revision `9308087c5c609519234da48136b88cdd60f79667`.
- Combined-v2 hashes: analysis document `36f85c40e9159ef2e69742672c261769fb28d2f3c947780ba63e4ef5fe5975c3`, analysis file `6c38e3e18a4577da41bc70c5610b5449e0316b1588291cb178e437099fb78929`, bracket document `098f19d8883097d5f1f274ce759416328c086958fa5301c034a0b46dcbd562df`, bracket file `7a84d545b4526d94aa6f93ca4f0d264dcf01e518f2f9b04383921634786c9962`.
- Correctness hashes: report `036b4b8a06164716aff5f40cc38ac4855a212026a556e1c5fe33ce32ce0babb8`, validation run spec `5b3eea4c460e14a57aec9df606447137d787a5c66dd7e98e1dffdcf566f430e2`, protocol `c7e980eeadaf8ed75e4d20cebb1e2c5d5f57a1cfc329afa7678ae586f5b7f488`, check registry `6e25ea41899544f2a9de3589beb1ee94b1f3dc505638b8f8e5164a4322b56a1d`, scientific engine `457fa669da897e59b03681039db6121fde4d7be9295bb46a743c8448875b3ee9`.
- V2 schemas: `challenge-194-p0-extension-protocol-v2`, `challenge-194-p0-extension-run-spec-v2`, `challenge-194-p0-extension-progress-v2`, `challenge-194-p0-extension-analysis-v2`, `challenge-194-p0-authorization-analysis-v3`, `challenge-194-p1-brackets-v3`, and conditional `challenge-194-p1-protocol-v2`.
- Sigmas: `0x1.ccccccccccccdp-1`, `0x1.0000000000000p+0`; lengths: `1024`, `16384`, `262144`; replicas: integers `40..71`; loop order: sigma, length, replica.
- Master seed `19_420_263_729`; phase `"pilot"`; namespace `"pilot-p0-extension-v2"`.
- Sigma `0.9` grid: `["0x0.0p+0","0x1.270b400000000p-1","0x1.5416800000000p-1","0x1.97a7600000000p-1","0x1.e848000000000p-1"]`; grid SHA256 `28155d7f982584787089f4a80d617783bd82b84e2ed833df3dcaa98955254d24`.
- Sigma `1.0` grid: `["0x0.0p+0","0x1.b0b85e0000000p-1","0x1.d8cb280000000p-1","0x1.14785e0000000p+0","0x1.3c8b280000000p+0"]`; grid SHA256 `b9abfff153302b8556312fbc5a59e6a8e7c98d8bd3c301cb90252c85a5c473f4`.
- Cardinality: 192 cells, 192 trajectories, five checkpoints each, 960 checkpoints, 30 v2 estimate rows, and 126 authorization rows.
- V2 identities must be disjoint from P0 replicas `0..7`, P1 `8..23`, and v1 `24..39`; compare complete request and stream-material registries, not labels alone.
- Preserve every v1 schema, artifact byte, public v1 function, exact P0/combined bracket output, and selector physics function body. Schema adapters may change; `_transition_evidence`, `_select_transition_bracket`, `_select_crossover_bracket`, thresholds, candidate ordering, tie-breaks, and zero rule may not.
- Authorization uses P0 sigma `0.8`/`1.1` rows byte-for-byte and standalone v2 sigma `0.9`/`1.0` rows only. Never union, pool, or interpolate P0/v1 blocked-sigma points.
- Canonical finite JSON, exact `float.hex()`, bounded descriptor reads, atomic no-clobber publication, immutable restart, external transfer state/logs, and fail-closed path/ABA checks remain mandatory.
- Wuzh02 only: `wzacnormal03`, one CPU, 1800 MiB, 40 minutes, no GPU, private node-local Numba cache, at most 40 concurrent cells with a lower account-limit cap when required.
- V2 and any P1 are exploratory only. This plan may publish a P1-v2 protocol but must not execute a P1 cell.

---

## File Map

- Modify `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_extension.py`: immutable v1/v2 campaign contracts, authenticated v2 protocol builder, exact source-axis grid copy, and shared protocol validation.
- Modify `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot.py`: exact-schema contract registry and generic extension run-spec/cell/pending/merge/verify operations while preserving v1 public wrappers.
- Modify `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_analysis.py`: generic contract-bound extension aggregation and authorization-v3 selector adapter; selector physics bodies remain unchanged.
- Create `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_authorization.py`: deep source authentication, authorization-analysis-v3, bracket-v3, seven-check evaluation, and P1-protocol-v2 construction.
- Modify `tracks/qmc/solutions/frustration-free/challenge-194/scripts/analyze_pilot.py`: v2 protocol, analysis, authorization, selection, and conditional P1 commands.
- Modify `tracks/qmc/solutions/frustration-free/challenge-194/scripts/run_pilot.py`: v2 run-spec build and exact-schema runtime dispatch.
- Create `tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_slurm_common.sh`: shared sanitization/cache/launcher functions used by v1 and v2 wrappers.
- Modify `tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_array_slurm.sh` and `pilot_extension_build_slurm.sh`: delegate common mechanics without changing v1 behavior.
- Create `tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_v2_array_slurm.sh` and `pilot_extension_v2_build_slurm.sh`: thin v2 resource/task/path wrappers over the common shell library.
- Modify `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_extension.py`, `test_pilot.py`, `test_pilot_analysis.py`, `test_analyze_pilot_cli.py`, and `test_runtime.py`: v2 TDD plus exact v1/P0 regression locks.
- Modify `tracks/qmc/solutions/frustration-free/challenge-194/PILOT_PLAN.md` before submission: frozen v2 execution contract.
- Modify `tracks/qmc/solutions/frustration-free/challenge-194/README.md`: exact build, submit, harvest, authorization, and conditional handoff commands.

Dependency direction remains acyclic: `pilot_extension.py` may import selector parsing primitives from `pilot_analysis.py`; `pilot_analysis.py` imports extension constants only inside functions; `pilot_authorization.py` orchestrates both modules and neither imports it.

## Critical Path

Tasks 1–2 produce the exact submission revision. Task 3 deploys and submits immediately. Tasks 4–6 run locally while Slurm executes the frozen Task 2 commit. Task 7 harvests and verifies immutable evidence. Task 8 executes the seven-check gate and conditionally publishes P1-v2 without executing it. Task 9 records the separate post-pass P1-execution handoff.

Do not modify `PILOT_PLAN.md`, scientific-engine files, v2 protocol/run-spec logic, shell worker logic, or the Task 2 submission commit after remote run-spec construction. Local Tasks 4–6 may add analysis-only code that authenticates the historical submission revision.

### Task 1: Generalized Campaign Contract and Authenticated V2 Protocol

**Files:**
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_extension.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/scripts/analyze_pilot.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_extension.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_analyze_pilot_cli.py`

**Interfaces:**
- Produces `P0ExtensionCampaign`, `V1_EXTENSION`, and `V2_EXTENSION`.
- Produces `build_p0_extension_v2_protocol(sources: V2ProtocolSources) -> dict[str, object]`.
- Produces `validate_p0_extension_v2_protocol(protocol: Mapping[str, object], sources: V2ProtocolSources, *, expected_source_revision: str) -> None`.
- Produces CLI `build-p0-extension-v2` with explicit P0/v1/combined trust inputs.

- [ ] **Step 1: Write exact failing contract and source-authentication tests**

Add:

```python
@dataclass(frozen=True)
class V2ProtocolSources:
    p0_analysis: Mapping[str, object]
    p0_evidence_root: Path
    v1_analysis: Mapping[str, object]
    v1_run_spec: Path
    v1_protocol: Mapping[str, object]
    combined_v2_analysis: Mapping[str, object]

def test_v2_protocol_copies_exact_authenticated_axes_and_is_disjoint():
    sources = _real_v2_protocol_sources()
    protocol = extension.build_p0_extension_v2_protocol(sources)
    assert protocol["schema_version"] == "challenge-194-p0-extension-protocol-v2"
    assert protocol["replicas"] == list(range(40, 72))
    assert protocol["cell_count"] == 192
    entries = {entry["sigma_hex"]: entry for entry in protocol["sigma_entries"]}
    assert entries[(0.9).hex()]["kappas"] == V2_GRIDS[(0.9).hex()]
    assert entries[(1.0).hex()]["kappas"] == V2_GRIDS[(1.0).hex()]
    assert {cell["request_sha256"] for cell in protocol["cells"]}.isdisjoint(
        _all_p0_v1_p1_request_hashes(sources)
    )
```

Add validly rehashed mutations for every source/file/document hash, source
revision, design hash, grid string/order/hash, sigma/length/replica order,
seed/phase/namespace, request, stream material, and cell path. Each must reach
the intended semantic validator and raise a field-specific `RuntimeError`.

- [ ] **Step 2: Run RED**

```bash
cd /home/footman/code/quantum.harness-challenge-194/tracks/qmc/solutions/frustration-free/challenge-194
uv run --with pytest pytest \
  tests/test_pilot_extension.py -q -k "v2_protocol or v2_source"
```

Expected: FAIL because `V2ProtocolSources` and
`build_p0_extension_v2_protocol` do not exist; existing v1 tests remain green.

- [ ] **Step 3: Generalize v1 protocol mechanics without changing v1 output**

Implement:

```python
@dataclass(frozen=True)
class P0ExtensionCampaign:
    protocol_schema: str
    run_spec_schema: str
    progress_schema: str
    analysis_schema: str
    production_kind: str
    sigmas: tuple[float, ...]
    lengths: tuple[int, ...]
    replicas: tuple[int, ...]
    master_seed: int
    phase: str
    grid_namespace: str
    grids: Mapping[str, tuple[str, ...]]
    grid_hashes: Mapping[str, str]
    cell_count: int

V2_EXTENSION = P0ExtensionCampaign(
    protocol_schema="challenge-194-p0-extension-protocol-v2",
    run_spec_schema="challenge-194-p0-extension-run-spec-v2",
    progress_schema="challenge-194-p0-extension-progress-v2",
    analysis_schema="challenge-194-p0-extension-analysis-v2",
    production_kind="p0-extension-v2",
    sigmas=(0.9, 1.0),
    lengths=(2**10, 2**14, 2**18),
    replicas=tuple(range(40, 72)),
    master_seed=19_420_263_729,
    phase="pilot",
    grid_namespace="pilot-p0-extension-v2",
    grids=V2_GRIDS,
    grid_hashes=V2_GRID_HASHES,
    cell_count=192,
)
```

Move repeated cell/request/stream construction into private helpers accepting
`P0ExtensionCampaign`. Keep `build_p0_extension_protocol` and
`validate_p0_extension_protocol` as v1 wrappers and assert their real protocol
bytes/hash remain unchanged.

- [ ] **Step 4: Authenticate v2 inputs and build the protocol**

`build_p0_extension_v2_protocol` must:

1. deeply verify P0 root and exact P0 analysis;
2. deeply verify v1 root, recompute v1 analysis, and require byte identity;
3. semantically recompute combined-v2 and require byte identity;
4. copy the five exact strings from authenticated combined axes;
5. verify the two fixed grid hashes and exact design hash;
6. reconstruct P0/v1/reserved-P1 identities before assigning 192 v2 cells;
7. emit purpose `exploratory-grid-topology-sensitivity-and-p1-authorization-only`.

No caller-provided digest may substitute for a verified source.

- [ ] **Step 5: Add immutable CLI publication**

Register:

```text
build-p0-extension-v2
  --p0-analysis PATH
  --p0-evidence-root DIR
  --v1-analysis PATH
  --v1-run-spec PATH
  --v1-protocol PATH
  --combined-v2-analysis PATH
  --output PATH
```

All paths are required, absolute after resolution, canonical, and non-symlink.
First invocation returns `published`; byte-identical retry returns
`verified-existing`; changed installed bytes fail without replacement.

- [ ] **Step 6: Run GREEN and commit**

```bash
uv run --with pytest pytest \
  tests/test_pilot_extension.py tests/test_analyze_pilot_cli.py -q
uv run --with ruff==0.16.0 ruff check --ignore SIM102,TRY004,UP017,PYI025,F401 \
  src/long_range_percolation/pilot_extension.py \
  scripts/analyze_pilot.py tests/test_pilot_extension.py tests/test_analyze_pilot_cli.py
uv run python -m compileall -q \
  src/long_range_percolation/pilot_extension.py scripts/analyze_pilot.py
git diff --check
```

Expected: all commands exit 0; v1 real protocol hash remains
`a37ab41...`; original and combined bracket hashes remain exact.

```bash
git add \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_extension.py \
  tracks/qmc/solutions/frustration-free/challenge-194/scripts/analyze_pilot.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_extension.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_analyze_pilot_cli.py
git commit -m "Add authenticated P0 extension v2 protocol"
```

### Task 2: V2 Runtime, Shared Slurm Wrappers, and Submission Release Gate

**Files:**
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_extension.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/scripts/run_pilot.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_slurm_common.sh`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_array_slurm.sh`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_build_slurm.sh`
- Create: `tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_v2_array_slurm.sh`
- Create: `tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_v2_build_slurm.sh`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_extension.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_runtime.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/PILOT_PLAN.md`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/README.md`

**Interfaces:**
- Produces `build_registered_extension_run_spec(..., campaign: P0ExtensionCampaign, sources: V2ProtocolSources)`.
- Preserves all v1 public run functions; adds `load/run/pending/merge/verify_p0_extension_v2`.
- Produces CLI `build-extension-v2-spec`.
- Produces exact 192-task v2 build/worker wrappers sharing v1 shell mechanics.

- [ ] **Step 1: Write RED runtime and wrapper tests**

```python
def test_v2_run_spec_and_runtime_dispatch_are_exact(tmp_path: Path):
    path = pilot._write_test_extension_run_spec(
        tmp_path / "v2", campaign=extension.V2_EXTENSION
    )
    spec = pilot.load_p0_extension_v2_run_spec(
        path, verify_current_environment=False
    )
    assert spec["schema_version"] == extension.V2_EXTENSION.run_spec_schema
    assert spec["cell_count"] == 192
    assert pilot.pending_p0_extension_v2_cells(
        path, verify_current_environment=False
    ) == list(range(192))
    with pytest.raises(RuntimeError, match="v1"):
        pilot.load_p0_extension_run_spec(path, verify_current_environment=False)

def test_v2_worker_contract():
    text = (SCRIPTS / "pilot_extension_v2_array_slurm.sh").read_text()
    assert "#SBATCH --cpus-per-task=1" in text
    assert "#SBATCH --mem=1800M" in text
    assert "#SBATCH --time=00:40:00" in text
    assert "SLURM_ARRAY_TASK_ID > 192" in text
```

Test complete restart boundaries, duplicate workers, `.partial`/`.intent`,
swapped cells, unknown fields, exact progress schema, 192-only merge, and v1
96-cell behavior.

- [ ] **Step 2: Run RED**

```bash
uv run --with pytest pytest \
  tests/test_pilot.py tests/test_pilot_extension.py tests/test_runtime.py -q \
  -k "extension_v2 or v2_worker or v1_extension_regression"
```

Expected: FAIL for missing v2 runtime/wrappers; all selected v1 regression
tests pass.

- [ ] **Step 3: Register the exact v2 runtime contract**

Extend `_contract_for_schema` with `V2_EXTENSION` and refactor extension public
functions through private contract-taking operations. Keep:

```python
def build_p0_extension_v2_run_spec(
    output_root: Path,
    validation_report: Path,
    protocol: Mapping[str, object],
    sources: V2ProtocolSources,
) -> dict[str, object]: ...

def load_p0_extension_v2_run_spec(
    path: Path, verify_current_environment: bool = True
) -> dict[str, object]: ...
```

Add corresponding run/pending/merge/verify wrappers. Never infer version from
filename or accept a boolean downgrade to test schema.

- [ ] **Step 4: Add `build-extension-v2-spec`**

Require the protocol, validation report, all `V2ProtocolSources` paths,
output root, and exact `output_root / "run_spec.json"`. The test parses stdout
and requires `status == "ready"`, `cells == 192`, the exact resolved run-spec
path, a 64-character lowercase hexadecimal `run_spec_sha256`, and equality
between that digest and a fresh SHA256 of the canonical unsigned run spec. It
does not hard-code a hash that cannot exist before the future submission
revision is known.

- [ ] **Step 5: Share shell mechanics and create thin v2 wrappers**

Move environment removal, thread pins, canonical path checks, private cache
creation, and exact Python launch into `pilot_extension_slurm_common.sh`.
V1 wrappers source it and retain their exact scientific paths and `1..96`
mapping. V2 worker accepts canonical decimal IDs `1..192`, maps `ID-1`, and
executes `run-cell` against the authenticated run spec.

V2 build wrapper derives these fixed paths from the results root:

```text
p0_analysis.json
pilot-p0-739880d
p0_extension_v1_protocol.json
pilot-p0-extension-v1/run_spec.json
p0_extension_v1_analysis.json
p0_combined_analysis_v2.json
p0_extension_v2_protocol.json
pilot-p0-extension-v2/run_spec.json
validation-prod-877ab93/report/report.json
```

It runs `build-p0-extension-v2` then `build-extension-v2-spec`. Existing
different bytes or any missing/hash-mismatched input fail closed.

- [ ] **Step 6: Freeze docs before run-spec construction**

Add exact constants, schemas, artifacts, resources, smoke IDs
`1,65,97,161`, remaining array, concurrency cap, restart, transfer, seven
checks, and exploratory boundary to `PILOT_PLAN.md` and README. State no v2
data or P1-v2 protocol exists yet.

- [ ] **Step 7: Run the submission release gate**

```bash
bash -n \
  scripts/pilot_extension_slurm_common.sh \
  scripts/pilot_extension_array_slurm.sh \
  scripts/pilot_extension_build_slurm.sh \
  scripts/pilot_extension_v2_array_slurm.sh \
  scripts/pilot_extension_v2_build_slurm.sh
uv run --with pytest pytest -q
uv run --with ruff==0.16.0 ruff check --ignore SIM102,TRY004,UP017,PYI025,F401 \
  src/long_range_percolation/pilot.py \
  src/long_range_percolation/pilot_extension.py \
  scripts/run_pilot.py scripts/analyze_pilot.py \
  tests/test_pilot.py tests/test_pilot_extension.py \
  tests/test_analyze_pilot_cli.py tests/test_runtime.py
uv run --with ruff==0.16.0 ruff format --check \
  src/long_range_percolation/pilot.py \
  src/long_range_percolation/pilot_extension.py \
  scripts/run_pilot.py scripts/analyze_pilot.py \
  tests/test_pilot.py tests/test_pilot_extension.py \
  tests/test_analyze_pilot_cli.py tests/test_runtime.py
git diff --check
```

Expected: shell checks silent, pytest zero failures, Ruff `All checks passed!`,
format clean, diff check silent. Verify selector function-source bytes and all
four immutable analysis/bracket files remain unchanged.

- [ ] **Step 8: Commit and record the immutable submission revision**

```bash
git add \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot.py \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_extension.py \
  tracks/qmc/solutions/frustration-free/challenge-194/scripts/run_pilot.py \
  tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_slurm_common.sh \
  tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_array_slurm.sh \
  tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_build_slurm.sh \
  tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_v2_array_slurm.sh \
  tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_v2_build_slurm.sh \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_extension.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_runtime.py \
  tracks/qmc/solutions/frustration-free/challenge-194/PILOT_PLAN.md \
  tracks/qmc/solutions/frustration-free/challenge-194/README.md
git commit -m "Prepare standalone P0 extension v2 campaign"
git rev-parse HEAD
```

Expected: one clean submission commit; record its full SHA as `SUBMIT_SHA`.

### Task 3: Clean Wuzh02 Deployment, Smoke Gate, and Early Submission

**Files:**
- Read only: `skills/using-slurm/profiles/wuzh02-jiangweiqi.toml`
- Read only: `scripts/harness_slurm.sh`
- Generated outside Git: bundle/deployment, immutable v2 root, and external scheduler logs.

**Interfaces:**
- Consumes exact Task 2 `SUBMIT_SHA`.
- Produces build job ID, smoke job ID, full-array job ID, immutable remote run spec, and external no-clobber logs.

- [ ] **Step 1: Set exact paths and precheck**

```bash
cd /home/footman/code/quantum.harness-challenge-194
export HARNESS_CLUSTER_PROFILE=wuzh02-jiangweiqi
export SUBMIT_SHA="$(git rev-parse HEAD)"
export SHORT_SHA="${SUBMIT_SHA:0:7}"
export REMOTE_RESULTS="/work/share/giggleliu/jiangweiqi/results/challenge-194"
export REMOTE_REPO="/work/share/giggleliu/jiangweiqi/quantum.harness-p0-extension-v2-${SHORT_SHA}"
export REMOTE_BUNDLE="/work/share/giggleliu/jiangweiqi/challenge-194-p0-extension-v2-${SHORT_SHA}.bundle"
export LOCAL_BUNDLE="/tmp/challenge-194-p0-extension-v2-${SHORT_SHA}.bundle"
export REMOTE_ROOT="${REMOTE_RESULTS}/pilot-p0-extension-v2"
export REMOTE_PYTHON="/work/share/giggleliu/jiangweiqi/quantum.harness-challenge-194/.venv/bin/python"
scripts/harness_slurm.sh precheck
scripts/harness_slurm.sh probe-partitions
```

Expected: Wuzh02 SSH passes, `wzacnormal03` is available, and the only local
dirty path is the protected pre-existing scratch report. Stop on any other
dirty path.

- [ ] **Step 2: Ship committed bytes and required immutable inputs no-clobber**

Create and install the Git bundle:

```bash
git bundle create "${LOCAL_BUNDLE}" challenge/194
BUNDLE_SHA256="$(sha256sum "${LOCAL_BUNDLE}" | awk '{print $1}')"
BUNDLE_STAGE="${REMOTE_BUNDLE}.upload-${SUBMIT_SHA}-$(date -u +%Y%m%dT%H%M%S%N)-$$"
ssh wuzh02-jiangweiqi "test ! -e '${REMOTE_BUNDLE}' && test ! -e '${REMOTE_REPO}' && test ! -e '${BUNDLE_STAGE}'"
scp "${LOCAL_BUNDLE}" "wuzh02-jiangweiqi:${BUNDLE_STAGE}"
ssh wuzh02-jiangweiqi "
  set -euo pipefail
  test \"\$(sha256sum '${BUNDLE_STAGE}' | awk '{print \$1}')\" = '${BUNDLE_SHA256}'
  ln -- '${BUNDLE_STAGE}' '${REMOTE_BUNDLE}'
  sync -f -- '${REMOTE_BUNDLE}'
  test \"\$(sha256sum '${REMOTE_BUNDLE}' | awk '{print \$1}')\" = '${BUNDLE_SHA256}'
  rm -- '${BUNDLE_STAGE}'
  git clone '${REMOTE_BUNDLE}' '${REMOTE_REPO}'
  git -C '${REMOTE_REPO}' checkout --detach '${SUBMIT_SHA}'
  test -z \"\$(git -C '${REMOTE_REPO}' status --porcelain)\"
"
```

Use this exact no-clobber helper for required JSON files:

```bash
publish_remote_file() {
  local local_path="$1" remote_path="$2" expected_sha="$3"
  local stage
  test "$(sha256sum "${local_path}" | awk '{print $1}')" = "${expected_sha}"
  if ssh wuzh02-jiangweiqi "test -e '${remote_path}'"; then
    ssh wuzh02-jiangweiqi \
      "test \"\$(sha256sum '${remote_path}' | awk '{print \$1}')\" = '${expected_sha}'"
    return
  fi
  stage="${remote_path}.upload-${SUBMIT_SHA}-$(date -u +%Y%m%dT%H%M%S%N)-$$"
  ssh wuzh02-jiangweiqi "test ! -e '${stage}'"
  scp "${local_path}" "wuzh02-jiangweiqi:${stage}"
  ssh wuzh02-jiangweiqi "
    set -euo pipefail
    test \"\$(sha256sum '${stage}' | awk '{print \$1}')\" = '${expected_sha}'
    ln -- '${stage}' '${remote_path}'
    sync -f -- '${remote_path}'
    test \"\$(sha256sum '${remote_path}' | awk '{print \$1}')\" = '${expected_sha}'
    rm -- '${stage}'
  "
}

publish_remote_file results/challenge-194/p0_analysis.json \
  "${REMOTE_RESULTS}/p0_analysis.json" \
  44083701db692304cd3aa054c8a9488b75674cead7cd6bf479c0a203cc1fa10b
publish_remote_file results/challenge-194/p0_extension_v1_protocol.json \
  "${REMOTE_RESULTS}/p0_extension_v1_protocol.json" \
  e363a60f842b11b32972c7a68ec1c5f237741bc45bc79ab8bf93f51f6760d84d
publish_remote_file results/challenge-194/p0_extension_v1_analysis.json \
  "${REMOTE_RESULTS}/p0_extension_v1_analysis.json" \
  d8fdd60a6de83cf3818349d4440f49f4a38bb5acd7fff1dab9b56ded4da913e5
publish_remote_file results/challenge-194/p0_combined_analysis_v2.json \
  "${REMOTE_RESULTS}/p0_combined_analysis_v2.json" \
  6c38e3e18a4577da41bc70c5610b5449e0316b1588291cb178e437099fb78929
```

Existing final paths with different bytes and failed staging paths remain
preserved outside immutable run roots and fail closed.

Verify exact remote roots, correctness input, and offline interpreter:

```bash
ssh wuzh02-jiangweiqi "
  set -euo pipefail
  test \"\$(sha256sum '${REMOTE_RESULTS}/pilot-p0-739880d/run_spec.json' | awk '{print \$1}')\" = d17d3df9528a09f0d834ebe9d5ce6f283e488d2326f6cb14873a90923c5d9840
  test \"\$(sha256sum '${REMOTE_RESULTS}/pilot-p0-739880d/progress.json' | awk '{print \$1}')\" = ea29a8163a5d3e85768842d64fac4c719f5aeadf965b3318b305fb7a2cc2d15f
  test \"\$(sha256sum '${REMOTE_RESULTS}/pilot-p0-extension-v1/run_spec.json' | awk '{print \$1}')\" = c1ca9b6c8ba751919c6d9337fe1cd4c09a57ed9b99abbb9d3ebfed7f89c3d32e
  test \"\$(sha256sum '${REMOTE_RESULTS}/pilot-p0-extension-v1/progress.json' | awk '{print \$1}')\" = c78d1fb03daf19297ef9e0617410c68a6a364bffc2f2888dfa9067e7e8d6b65f
  test \"\$(sha256sum '${REMOTE_RESULTS}/validation-prod-877ab93/report/report.json' | awk '{print \$1}')\" = 036b4b8a06164716aff5f40cc38ac4855a212026a556e1c5fe33ce32ce0babb8
  test -x '${REMOTE_PYTHON}'
"
```

- [ ] **Step 3: Build the remote protocol and run spec**

Feasibility-check, then submit:

```bash
HARNESS_REPO_REMOTE="${REMOTE_REPO}" scripts/harness_slurm.sh submit \
  --test-only \
  --script tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_v2_build_slurm.sh \
  --run-spec "${REMOTE_RESULTS}/p0_combined_analysis_v2.json" \
  --entrypoint "${REMOTE_REPO}" --command "${REMOTE_PYTHON}" \
  --partition wzacnormal03 --time 00:10:00 --cpus 1 \
  --extra "--mem=1800M"
```

Submit the identical command without `--test-only`, capture `BUILD_JOB_ID`,
wait for success, then run remote `pending`. Parse its canonical JSON and
require `status == "pending"`, `count == 192`, and
`cell_indices == list(range(192))`.

- [ ] **Step 4: Run the exact four-cell smoke gate**

```bash
HARNESS_REPO_REMOTE="${REMOTE_REPO}" scripts/harness_slurm.sh submit \
  --test-only \
  --script tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_v2_array_slurm.sh \
  --run-spec "${REMOTE_ROOT}/run_spec.json" \
  --entrypoint "${REMOTE_REPO}" --command "${REMOTE_PYTHON}" \
  --partition wzacnormal03 --time 00:40:00 --cpus 1 \
  --extra "--mem=1800M --array=1,65,97,161%4"
```

Submit only after feasibility succeeds. Capture `SMOKE_JOB_ID`. All four jobs
must exit 0, publish verified complete trajectories/manifests, leave no
partial/intent files, and pass deep `pending`/cell verification. Otherwise
stop; retry only infrastructure failure under identical identities.

- [ ] **Step 5: Determine safe concurrency and submit remaining cells**

Set `ACCOUNT_CAP` from the profile/account limit. Use:

```bash
if (( ACCOUNT_CAP < 1 )); then exit 64; fi
if (( ACCOUNT_CAP > 40 )); then ARRAY_CAP=40; else ARRAY_CAP="${ACCOUNT_CAP}"; fi
ARRAY_EXPR="2-64,66-96,98-160,162-192%${ARRAY_CAP}"
HARNESS_REPO_REMOTE="${REMOTE_REPO}" scripts/harness_slurm.sh submit \
  --test-only \
  --script tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_v2_array_slurm.sh \
  --run-spec "${REMOTE_ROOT}/run_spec.json" \
  --entrypoint "${REMOTE_REPO}" --command "${REMOTE_PYTHON}" \
  --partition wzacnormal03 --time 00:40:00 --cpus 1 \
  --extra "--mem=1800M --array=${ARRAY_EXPR}"
```

After feasibility succeeds, rerun the displayed command without
`--test-only`. Capture `ARRAY_JOB_ID`. Expected: 188 remaining tasks, no more
than `ARRAY_CAP` concurrent cells; lowering the cap changes no scientific
identity.

- [ ] **Step 6: Monitor without treating scheduler success as evidence**

Use `status` and `classify` for all three IDs. Inspect pending reason, one
startup log, memory/time classification, and final `sacct`. Do not delete logs,
resubmit altered resources, or infer scientific acceptance. Task 7 performs
the evidence gate.

### Task 4: Bounded Standalone V2 Aggregation While Slurm Runs

**Files:**
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_analysis.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_analysis.py`

**Interfaces:**
- Produces `aggregate_p0_extension_v2(run_spec: Path, protocol: Mapping[str, object]) -> dict[str, object]`.
- Produces test-only `_aggregate_test_registered_extension(run_spec: Path, protocol: Mapping[str, object], *, campaign: P0ExtensionCampaign) -> dict[str, object]`.
- Preserves `aggregate_p0_extension` v1 bytes/output.

- [ ] **Step 1: Add RED bounded aggregation tests**

Use tiny contract fixtures and assert exact sigma/length/kappa/request order,
`ddof=1`, one live trajectory at a time, 32 replicas, 30 production rows,
protocol/run/progress hashes, retained verified snapshot, and rejection of
swaps, stale markers, forged progress, extras, and unknown schema.

```python
def test_v2_aggregation_has_exact_standalone_shape(tmp_path: Path):
    protocol, run_spec = _write_test_v2_extension(tmp_path)
    analysis = pilot_analysis._aggregate_test_registered_extension(
        run_spec, protocol, campaign=extension.V2_EXTENSION
    )
    assert analysis["schema_version"] == extension.V2_EXTENSION.analysis_schema
    assert len(analysis["estimates"]) == 30
    assert {
        row["replica_count"] for row in analysis["estimates"]
    } == {32}
    assert [
        (row["sigma_hex"], row["length"], row["kappa_hex"])
        for row in analysis["estimates"]
    ] == [
        (sigma.hex(), length, kappa)
        for sigma in extension.V2_EXTENSION.sigmas
        for length in extension.V2_EXTENSION.lengths
        for kappa in extension.V2_EXTENSION.grids[sigma.hex()]
    ]
```

- [ ] **Step 2: Run RED**

```bash
uv run --with pytest pytest tests/test_pilot_analysis.py -q -k extension_v2
```

Expected: FAIL because `aggregate_p0_extension_v2` is absent.

- [ ] **Step 3: Generalize the internal aggregator by campaign**

Implement private `_aggregate_registered_extension(..., campaign)` and keep
separate exact public v1/v2 wrappers. V2 requires shape `(32, 5, 4)` per
sigma/length group, five ten-column checkpoints per trajectory, 30 rows, and
schema `challenge-194-p0-extension-analysis-v2`.

- [ ] **Step 4: Run GREEN and commit**

```bash
uv run --with pytest pytest tests/test_pilot_analysis.py tests/test_pilot.py -q
uv run --with ruff==0.16.0 ruff check --ignore SIM102,TRY004,UP017,PYI025,F401 \
  src/long_range_percolation/pilot_analysis.py tests/test_pilot_analysis.py
git diff --check
git add \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_analysis.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_analysis.py
git commit -m "Add bounded P0 extension v2 aggregation"
```

Expected: all tests pass; v1 analysis recomputation remains byte-identical.

### Task 5: Authenticated Authorization Evidence, Selector V3, and P1-V2 Builder

**Files:**
- Create: `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_authorization.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_analysis.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_analysis.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_authorization.py`

**Interfaces:**
- Produces `AuthorizationSources`.
- Produces `build_p0_authorization_evidence(sources: AuthorizationSources) -> dict[str, object]`.
- Produces `select_authorized_p1_brackets(analysis: Mapping[str, object], sources: AuthorizationSources) -> dict[str, object]`.
- Produces `build_authorized_p1_v2_protocol(analysis, brackets, sources) -> dict[str, object]`.

- [ ] **Step 1: Write RED source-recomputation and no-union tests**

```python
@dataclass(frozen=True)
class AuthorizationSources:
    p0_analysis: Mapping[str, object]
    p0_evidence_root: Path
    v1_analysis: Mapping[str, object]
    v1_run_spec: Path
    v1_protocol: Mapping[str, object]
    combined_v2_analysis: Mapping[str, object]
    v2_analysis: Mapping[str, object]
    v2_run_spec: Path
    v2_protocol: Mapping[str, object]

def test_authorization_uses_controls_and_standalone_v2_only():
    result = build_p0_authorization_evidence(_authorization_sources())
    entries = {entry["sigma_hex"]: entry for entry in result["sigma_entries"]}
    assert entries[(0.8).hex()]["source_role"] == "p0-control"
    assert entries[(0.9).hex()]["source_role"] == "v2-standalone"
    assert entries[(1.0).hex()]["source_role"] == "v2-standalone"
    assert entries[(1.1).hex()]["source_role"] == "p0-control"
    assert result["estimate_count"] == 126
    assert all(
        row["replica_count"] == 32
        for sigma in ((0.9).hex(), (1.0).hex())
        for row in entries[sigma]["estimates"]
    )
```

Add a malicious self-signed authorization JSON with valid outer digest but
forged P0 controls/v2 means; validation must recompute sources and reject it.
Add P0/v1 blocked-point injection and pooling tests; both must fail before
selection.

- [ ] **Step 2: Run RED**

```bash
uv run --with pytest pytest tests/test_pilot_authorization.py -q
```

Expected: collection fails because `pilot_authorization` is absent.

- [ ] **Step 3: Implement deep source authentication**

Reverify P0 root/analysis, v1 root/protocol/analysis, semantic combined-v2,
v2 root/protocol/analysis, exact design, source revisions, request
disjointness, and all fixed hashes. Recompute analyses from roots and require
canonical byte identity before constructing any authorization row.

- [ ] **Step 4: Build authorization-analysis-v3**

Copy P0 `0.8`/`1.1` entries byte-for-byte and v2 `0.9`/`1.0` entries
byte-for-byte into ordered per-sigma entries with explicit source roles.
Require 16/5/5/16 couplings per length and exactly 126 rows. Record every
source file/document/run/progress/protocol hash and unsigned canonical digest.

- [ ] **Step 5: Add schema adapter without changing selector physics**

Add only authorization-v3 normalization in `pilot_analysis.py`; call unchanged
selection bodies. Emit bracket schema `challenge-194-p1-brackets-v3`.
Regression tests compare exact function source bytes and exact historical
bracket documents before/after.

- [ ] **Step 6: Implement conditional P1-v2 construction**

Require four selected statuses, exact control windows, bracket-v3 byte
identity, `requires_p0_extension is False`, and all trusted sources.
Preserve P1 seed `19_420_261_729`, replicas `8..23`, phase `"pilot"`, four
sigmas, three lengths, and nine selector-derived points. Emit
`challenge-194-p1-protocol-v2`; do not execute cells.

- [ ] **Step 7: Run GREEN and commit**

```bash
uv run --with pytest pytest \
  tests/test_pilot_authorization.py tests/test_pilot_analysis.py -q
uv run --with ruff==0.16.0 ruff check --ignore SIM102,TRY004,UP017,PYI025,F401 \
  src/long_range_percolation/pilot_authorization.py \
  src/long_range_percolation/pilot_analysis.py \
  tests/test_pilot_authorization.py tests/test_pilot_analysis.py
git diff --check
git add \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_authorization.py \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_analysis.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_authorization.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_analysis.py
git commit -m "Add authenticated P0 authorization evidence"
```

### Task 6: Analysis CLI, Documentation, and Full Local Analysis Gate

**Files:**
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/scripts/analyze_pilot.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_analyze_pilot_cli.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_runtime.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/README.md`

**Interfaces:**
- Produces `analyze-extension-v2`, `authorize-v2`, `select-authorization-v3`, and `build-p1-v2`.

- [ ] **Step 1: Add RED immutable CLI tests**

For every command test required explicit trusted paths, canonical bounded
reads, first publish, byte-identical retry, changed-byte refusal, self-signed
source refusal, missing output on scientific failure, and no legacy mixed
arguments.

```python
@pytest.mark.parametrize(
    "command",
    [
        "analyze-extension-v2",
        "authorize-v2",
        "select-authorization-v3",
        "build-p1-v2",
    ],
)
def test_v2_commands_publish_once_and_require_trusted_sources(
    command: str, tmp_path: Path
):
    arguments = _complete_v2_cli_arguments(command, tmp_path)
    assert analyze_cli.main(arguments) == 0
    output = Path(arguments[arguments.index("--output") + 1])
    installed = output.read_bytes()
    assert analyze_cli.main(arguments) == 0
    assert output.read_bytes() == installed
    tampered = _validly_rehashed_self_signed_source(arguments, tmp_path)
    assert analyze_cli.main(tampered) == 1
    assert output.read_bytes() == installed
```

- [ ] **Step 2: Run RED**

```bash
uv run --with pytest pytest tests/test_analyze_pilot_cli.py -q -k "v2 or authorization"
```

Expected: argparse rejects the four absent commands.

- [ ] **Step 3: Implement exact commands**

```text
analyze-extension-v2 --run-spec PATH --protocol PATH --output PATH
authorize-v2 --p0-analysis PATH --p0-evidence-root DIR --v1-analysis PATH --v1-run-spec PATH --v1-protocol PATH --combined-v2-analysis PATH --v2-analysis PATH --v2-run-spec PATH --v2-protocol PATH --output PATH
select-authorization-v3 --analysis PATH --p0-analysis PATH --p0-evidence-root DIR --v1-analysis PATH --v1-run-spec PATH --v1-protocol PATH --combined-v2-analysis PATH --v2-analysis PATH --v2-run-spec PATH --v2-protocol PATH --output PATH
build-p1-v2 --analysis PATH --brackets PATH --p0-analysis PATH --p0-evidence-root DIR --v1-analysis PATH --v1-run-spec PATH --v1-protocol PATH --combined-v2-analysis PATH --v2-analysis PATH --v2-run-spec PATH --v2-protocol PATH --output PATH
```

No command trusts `--analysis` or `--brackets` alone. Each rebuilds trusted
evidence in memory before publication.

- [ ] **Step 4: Document exact local workflow**

Use artifact names from the design. State prominently that v1 points are
preserved but not unioned, all data are exploratory, and P1 execution is a
separate reviewed plan.

- [ ] **Step 5: Run full local gate and commit**

```bash
uv run --with pytest pytest -q
uv run --with ruff==0.16.0 ruff check --ignore SIM102,TRY004,UP017,PYI025,F401 \
  src/long_range_percolation/pilot.py \
  src/long_range_percolation/pilot_extension.py \
  src/long_range_percolation/pilot_analysis.py \
  src/long_range_percolation/pilot_authorization.py \
  scripts/run_pilot.py scripts/analyze_pilot.py \
  tests/test_pilot.py tests/test_pilot_extension.py \
  tests/test_pilot_analysis.py tests/test_pilot_authorization.py \
  tests/test_analyze_pilot_cli.py tests/test_runtime.py
uv run --with ruff==0.16.0 ruff format --check \
  src/long_range_percolation/pilot.py \
  src/long_range_percolation/pilot_extension.py \
  src/long_range_percolation/pilot_analysis.py \
  src/long_range_percolation/pilot_authorization.py \
  scripts/run_pilot.py scripts/analyze_pilot.py \
  tests/test_pilot.py tests/test_pilot_extension.py \
  tests/test_pilot_analysis.py tests/test_pilot_authorization.py \
  tests/test_analyze_pilot_cli.py tests/test_runtime.py
bash -n scripts/pilot_extension*.sh scripts/download_pilot.sh
git diff --check
```

Expected: zero failures, Ruff clean, formatting clean, shell checks and diff
check silent.

```bash
git add \
  tracks/qmc/solutions/frustration-free/challenge-194/scripts/analyze_pilot.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_analyze_pilot_cli.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_runtime.py \
  tracks/qmc/solutions/frustration-free/challenge-194/README.md
git commit -m "Document P0 extension v2 authorization workflow"
```

### Task 7: Harvest, Merge, Download, and Deep Verify

**Files:**
- Generated outside Git: remote/local v2 roots and sibling transfer/scheduler logs.

**Interfaces:**
- Consumes `BUILD_JOB_ID`, `SMOKE_JOB_ID`, `ARRAY_JOB_ID`, `SUBMIT_SHA`.
- Produces exact local verified 192-cell/192-trajectory v2 root.

- [ ] **Step 1: Classify jobs and query pending cells**

Run `status` and `classify` for all IDs, then remote `pending`. Expected count
0. For infrastructure failures only, obtain approval and resubmit exact failed
task IDs under the unchanged run spec; never alter resources/science silently.

- [ ] **Step 2: Merge and verify remotely**

```bash
ssh wuzh02-jiangweiqi "
  set -euo pipefail
  export PYTHONPATH='${REMOTE_REPO}/tracks/qmc/solutions/frustration-free/challenge-194/src'
  '${REMOTE_PYTHON}' '${REMOTE_REPO}/tracks/qmc/solutions/frustration-free/challenge-194/scripts/run_pilot.py' merge \
    --run-spec '${REMOTE_ROOT}/run_spec.json'
  '${REMOTE_PYTHON}' '${REMOTE_REPO}/tracks/qmc/solutions/frustration-free/challenge-194/scripts/run_pilot.py' verify \
    --run-spec '${REMOTE_ROOT}/run_spec.json'
"
```

Expected:
`{"cells":192,"status":"verified","trajectories":192}`.

- [ ] **Step 3: Download through hardened external state**

```bash
cd /home/footman/code/quantum.harness-challenge-194/tracks/qmc/solutions/frustration-free/challenge-194
scripts/download_pilot.sh \
  wuzh02-jiangweiqi \
  /work/share/giggleliu/jiangweiqi/results/challenge-194/pilot-p0-extension-v2 \
  /home/footman/code/quantum.harness-challenge-194/results/challenge-194/pilot-p0-extension-v2 \
  /home/footman/code/quantum.harness-challenge-194/.venv/bin/python
```

Expected exact 192/192 verifier JSON. Claims, source/completion records,
diagnostics, and uniquely named logs remain siblings outside the root.

- [ ] **Step 4: Reverify and repeat completed download**

Run local `run_pilot.py verify`, record run/progress hashes, then repeat the
download command. Expected: verifier succeeds, no rsync runs, and root,
completion record, and immutable bytes remain unchanged.

### Task 8: Publish Evidence, Execute Seven Checks, and Conditionally Publish P1-V2

**Files:**
- Generated outside Git: `p0_extension_v2_analysis.json`, `p0_authorization_analysis_v3.json`, `p0_authorization_brackets_v3.json`, and conditional `p1_protocol_v2.json`.
- Modify after evidence only: `tracks/qmc/solutions/frustration-free/challenge-194/README.md`.

**Interfaces:**
- Consumes every authenticated source and the verified v2 root.
- Produces a recorded seven-check decision and, only on pass, an immutable P1-v2 protocol.

Set the exact local paths once:

```bash
cd /home/footman/code/quantum.harness-challenge-194/tracks/qmc/solutions/frustration-free/challenge-194
RESULTS=/home/footman/code/quantum.harness-challenge-194/results/challenge-194
P0_ANALYSIS="${RESULTS}/p0_analysis.json"
P0_ROOT="${RESULTS}/pilot-p0-739880d"
V1_ANALYSIS="${RESULTS}/p0_extension_v1_analysis.json"
V1_RUN_SPEC="${RESULTS}/pilot-p0-extension-v1/run_spec.json"
V1_PROTOCOL="${RESULTS}/p0_extension_v1_protocol.json"
COMBINED_V2="${RESULTS}/p0_combined_analysis_v2.json"
V2_ROOT="${RESULTS}/pilot-p0-extension-v2"
V2_RUN_SPEC="${V2_ROOT}/run_spec.json"
V2_PROTOCOL="${RESULTS}/p0_extension_v2_protocol.json"
V2_ANALYSIS="${RESULTS}/p0_extension_v2_analysis.json"
AUTH_ANALYSIS="${RESULTS}/p0_authorization_analysis_v3.json"
AUTH_BRACKETS="${RESULTS}/p0_authorization_brackets_v3.json"
P1_V2="${RESULTS}/p1_protocol_v2.json"
AUTH_ARGS=(
  --p0-analysis "${P0_ANALYSIS}"
  --p0-evidence-root "${P0_ROOT}"
  --v1-analysis "${V1_ANALYSIS}"
  --v1-run-spec "${V1_RUN_SPEC}"
  --v1-protocol "${V1_PROTOCOL}"
  --combined-v2-analysis "${COMBINED_V2}"
  --v2-analysis "${V2_ANALYSIS}"
  --v2-run-spec "${V2_RUN_SPEC}"
  --v2-protocol "${V2_PROTOCOL}"
)
```

- [ ] **Step 1: Publish and byte-verify v2 analysis**

Run twice:

```bash
uv run python scripts/analyze_pilot.py analyze-extension-v2 \
  --run-spec "${V2_RUN_SPEC}" --protocol "${V2_PROTOCOL}" \
  --output "${V2_ANALYSIS}"
```

Expected: `published`, then
`verified-existing`; exactly 30 rows, replica count 32, and exact
protocol/run/progress/source bindings.

- [ ] **Step 2: Publish and byte-verify authorization analysis**

Run twice:

```bash
uv run python scripts/analyze_pilot.py authorize-v2 \
  "${AUTH_ARGS[@]}" --output "${AUTH_ANALYSIS}"
```

Expected:
`published`, then `verified-existing`; exactly 126 rows; source roles
P0/v2/v2/P0; 16/5/5/16 coupling axes; no P0/v1 blocked-sigma request ID.

- [ ] **Step 3: Publish and independently reproduce bracket-v3**

Run twice:

```bash
uv run python scripts/analyze_pilot.py select-authorization-v3 \
  --analysis "${AUTH_ANALYSIS}" "${AUTH_ARGS[@]}" \
  --output "${AUTH_BRACKETS}"
```

Expected: identical canonical bytes and
`verified-existing` on retry. Independently reconstruct in a fresh process
from all trusted roots; require byte identity.

- [ ] **Step 4: Evaluate the seven checks conjunctively**

```text
1. Protocol/design/implementation/correctness/P0/v1/combined inputs authenticate.
2. V2 root verifies exactly 192 cells and 192 trajectories.
3. V2 analysis recomputes byte-identically with 30 rows and replica count 32.
4. Authorization recomputes byte-identically with untouched controls, standalone v2 blocked sigmas, 126 rows, and no blocked-sigma union.
5. Sigma 0.9 and 1.0 are selected on nonzero intervals marked by both estimators.
6. Sigma 0.8 is [0x1.f400000000000p-2,0x1.3880000000000p-1] and sigma 1.1 is [0x1.312d000000000p+0,0x1.7d78400000000p+0].
7. requires_p0_extension is false and independent bracket recomputation is byte-identical.
```

If any check fails, assert `p1_protocol_v2.json` is absent, record unresolved,
and stop. No post-hoc change is allowed.

- [ ] **Step 5: Conditionally publish P1-v2 protocol only**

Only on all-seven pass, run twice:

```bash
uv run python scripts/analyze_pilot.py build-p1-v2 \
  --analysis "${AUTH_ANALYSIS}" --brackets "${AUTH_BRACKETS}" \
  "${AUTH_ARGS[@]}" --output "${P1_V2}"
```

Run with every trusted source and
bracket. Expected: `published`, then `verified-existing`; schema
`challenge-194-p1-protocol-v2`; 192 P1 cells; replicas `8..23`; seed
`19_420_261_729`; no P1 cell executed.

- [ ] **Step 6: Record evidence in one documentation-only commit**

Add exact observed hashes, job IDs, seven-check outcomes, and P1
present/absent status to README. Run Task 6 full gate, then:

```bash
git add tracks/qmc/solutions/frustration-free/challenge-194/README.md
git commit -m "Record P0 extension v2 boundary evidence"
```

Expected: only README committed; generated results and protected scratch files
remain unstaged.

### Task 9: Post-Pass P1 Execution Handoff

**Files:**
- Modify only on all-seven pass: `tracks/qmc/solutions/frustration-free/challenge-194/README.md`
- Future separate plan path: `docs/superpowers/plans/2026-07-30-challenge-194-p1-v2-execution.md`

**Interfaces:**
- Consumes verified `p1_protocol_v2.json` identity and Task 8 evidence hashes.
- Produces a handoff boundary, not P1 execution.

- [ ] **Step 1: Record the next-plan prerequisites**

Document that the future separate P1 plan must bind:

1. exact P1-v2 protocol file/document hashes;
2. authorization-analysis-v3 and bracket-v3 hashes;
3. four selector-derived nine-point grids;
4. P1 seed `19_420_261_729`, replicas `8..23`, phase `"pilot"`;
5. clean deployment, cell cardinality, resources, restart/transfer;
6. extended-observable implementation and tests if required by the existing
   production design;
7. exploratory-only claim boundary and untouched confirmatory RNG phase.

- [ ] **Step 2: Stop before P1 execution**

Do not build a P1 run spec, submit a P1 job, create a P1 cell root, or run any
P1 trajectory in this plan. If Task 8 fails, record that the handoff is
inapplicable because P1-v2 is absent.

## Plan Completion Criteria

- Tasks 1–2 produce and fully test the shortest safe submission revision.
- Task 3 deploys that exact clean commit, passes four-cell smoke, and submits
  all 188 remaining cells at concurrency `min(40, account limit)`.
- Tasks 4–6 complete local analysis/authorization code while Slurm runs.
- Task 7 proves 192/192 evidence independently of scheduler status.
- Task 8 either publishes a verified P1-v2 protocol after all seven checks or
  preserves the fail-closed unresolved state.
- Task 9 defines the separate next execution boundary and executes no P1 cell.
- Every implementation task has focused RED/GREEN evidence and a local commit;
  no push, protected-file edit, generated-result commit, post-hoc scientific
  change, or confirmatory claim is part of this plan.
