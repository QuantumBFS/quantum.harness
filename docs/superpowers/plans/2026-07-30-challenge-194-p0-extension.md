# Challenge 194 P0 Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, execute, verify, and analyze the approved 96-cell versioned P0 extension, then publish P1 only if the unchanged selector passes the combined-evidence gate.

**Architecture:** Add an authenticated extension protocol and run-spec schema beside the frozen P0 path, while reusing the existing cell runner, artifact verifier, restart machinery, and bounded snapshot implementation through explicit schema dispatch. Publish extension, combined-analysis, and bracket artifacts immutably; the combined schema permits a separate coupling axis per sigma and feeds the existing interval-marking and tie-break functions without relaxing them.

**Tech Stack:** Python 3.12, NumPy, h5py, pytest, Ruff, Bash, rsync, Git bundles, Slurm through `scripts/harness_slurm.sh`, and the existing `long_range_percolation` Pilot/artifact/counter-RNG APIs.

## Global Constraints

- Work from `/home/footman/code/quantum.harness-challenge-194` on `challenge/194`; do not modify `.superpowers/sdd/task-1-report.md` or `.superpowers/sdd/progress.md`.
- The approved design is `docs/superpowers/specs/2026-07-30-challenge-194-p0-extension-design.md` at commit `be57e93e7db7ce987a5643bc3ab2035d2b75dce9`.
- The committed design-file SHA256 is `5426e3007e9d83039f371ca6a9372f1868ef9d5447b66a12b1643ecf72907aba`.
- Existing P0 root: `results/challenge-194/pilot-p0-739880d`; verifier result: `{"cells":96,"status":"verified","trajectories":96}`.
- Existing P0 run-spec SHA256: `d17d3df9528a09f0d834ebe9d5ce6f283e488d2326f6cb14873a90923c5d9840`.
- Existing P0 progress SHA256: `ea29a8163a5d3e85768842d64fac4c719f5aeadf965b3318b305fb7a2cc2d15f`.
- Existing P0 analysis embedded SHA256: `e42ef6b9f82380305f80ceaba384bc29cb9fe2da0848d4c72a904f4cb4c8c7c8`.
- Existing P0 analysis canonical-file SHA256: `44083701db692304cd3aa054c8a9488b75674cead7cd6bf479c0a203cc1fa10b`.
- Existing bracket SHA256: `fb3df666044bf9531443fc00c5c2c2d489512b4162864b3a92ffc2e756832403`.
- Existing P0 source/orchestration revision: `739880d9ccdcffbfc8a15310250349bd11d63bbb`.
- Extension schemas are exactly `challenge-194-p0-extension-protocol-v1`, `challenge-194-p0-extension-run-spec-v1`, `challenge-194-p0-extension-progress-v1`, and `challenge-194-p0-extension-analysis-v1`.
- Combined schemas are exactly `challenge-194-p0-combined-analysis-v2` and `challenge-194-p1-brackets-v2`.
- Extension sigmas are exactly `0x1.ccccccccccccdp-1` and `0x1.0000000000000p+0`; lengths are exactly `1024`, `16384`, and `262144`; replicas are exactly `24..39`.
- Loop order is sigma, length, replica: exactly 96 cells, 96 trajectories, 17 checkpoints per trajectory, 1,632 trajectory checkpoints, and 102 extension estimate rows.
- Extension master seed is `19_420_262_729`, phase is `"pilot"`, and grid namespace is `"pilot-p0-extension-v1"`.
- Sigma `0.9` range is `0x1.f400000000000p-2` through `0x1.312d000000000p+0`; grid hash is `76dc7e07639ed085873a8f291cc2aaee0e8942ddac8efce3982743dd67491071`.
- Sigma `1.0` range is `0x1.3880000000000p-1` through `0x1.dcd6500000000p+0`; grid hash is `d40b4a2afac533d74965513513fff1870918831000b2e040063ca2a0e29ad091`.
- Extension replica labels, request digests, and RNG material must be disjoint from P0 replicas `0..7` and reserved P1 replicas `8..23`; any collision fails publication.
- The basic ten-column trajectory schema, scientific engine, realization policy, stopping policy, correctness registry, capability waiver, and exploratory `"pilot"` phase remain unchanged.
- The frozen selector still uses lengths `16384` and `262144`, excludes zero coupling, marks the same `Q_G` and closed `[0.25,0.75]` four-sector intervals, and uses the same narrowest/lower-coupling and maximum-slope/lower-coupling tie-breaks.
- No interpolation, uncertainty rescue, threshold change, nearest-interval fallback, manual candidate choice, adaptive extension, extended observables, P1 execution, or confirmatory use is allowed.
- Every JSON artifact is canonical finite UTF-8 JSON with sorted keys, compact separators, and one trailing newline; publication is atomic, immutable, and no-clobber.
- Heavy execution is Wuzh02-only on `wzacnormal03`: one CPU, 1800 MiB, 40 minutes, no GPU, and one private node-local Numba cache per cell.
- Existing `.partial` and `.intent` files are preserved and block restart; completed cells are deeply verified; retries use the identical run spec.
- P1 remains absent unless all six design acceptance checks pass. A scientifically unresolved extension is a valid fail-closed outcome.

---

## File Map

- Create `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_extension.py`: extension constants, range/grid derivation, protocol validation/building, and extension-analysis/combined-analysis records.
- Modify `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot.py`: schema dispatch, parameterized request reconstruction, extension run-spec construction, progress schema dispatch, and generic verified snapshots without weakening the public P0 loader.
- Modify `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_analysis.py`: extension aggregation, combined evidence, per-sigma selector normalization, bracket-v2 validation, and conditional P1 input support.
- Modify `tracks/qmc/solutions/frustration-free/challenge-194/scripts/analyze_pilot.py`: immutable extension protocol, extension analysis, combine, select, and P1 handoff commands.
- Modify `tracks/qmc/solutions/frustration-free/challenge-194/scripts/run_pilot.py`: `build-extension-spec` and production schema-dispatched cell/pending/merge/verify commands.
- Create `tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_array_slurm.sh`: exact 96-task extension worker contract.
- Create `tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_build_slurm.sh`: clean compute-node protocol/run-spec builder.
- Create `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_extension.py`: protocol, run-spec, execution, restart, schema separation, wrapper, and adversarial tests.
- Modify `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_analysis.py`: extension aggregation, combination, selector-v2, acceptance, and P1 regression tests.
- Modify `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_analyze_pilot_cli.py`: all new immutable CLI commands and failure boundaries.
- Modify `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_runtime.py`: documentation and exact cluster-command contracts.
- Modify `tracks/qmc/solutions/frustration-free/challenge-194/PILOT_PLAN.md`: freeze versioned extension identities, resources, restart, and acceptance before run-spec construction.
- Modify `tracks/qmc/solutions/frustration-free/challenge-194/README.md`: exact collaborator build, submit, fetch, analyze, combine, and conditional P1 commands.

`pilot_extension.py` may import the existing selector primitives from
`pilot_analysis.py`. New `pilot_analysis.py` functions must therefore import
extension constants and validators inside function bodies, never through a
module-scope reverse import; this keeps the dependency direction acyclic.

## Fastest Safe Execution Order

Tasks 1–4 form the submission critical path and each ends in a local commit.
Task 5 deploys the exact Task 4 commit and submits the campaign. Tasks 6–9
then proceed locally while Slurm runs. Task 10 harvests and verifies all 96
cells. Task 11 publishes combined evidence and performs the P1 gate. Do not
change `PILOT_PLAN.md`, `uv.lock`, or scientific-engine files after Task 4;
those bytes are bound into the run spec.

### Task 1: Extension Range and Protocol Core

**Files:**
- Create: `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_extension.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_extension.py`

**Interfaces:**
- Consumes: validated P0 analysis mapping and existing `periodic_kernel`, `TrajectoryRequest`, `request_digest`, `derive_stream_material`, and selector evidence functions.
- Produces: `build_p0_extension_protocol(p0_analysis: Mapping[str, object]) -> dict[str, object]` and `validate_p0_extension_protocol(p0_analysis: Mapping[str, object], protocol: Mapping[str, object]) -> None`.

- [ ] **Step 1: Add exact range, component, grid, and real-evidence tests**

Add constants for both expected grids directly in the test and construct a
source fixture from the immutable `p0_analysis.json`. The focused assertions
must include the distant `Q_G` components and prove that generated grids, not
copied output constants, produce the design hashes:

```python
P0_ANALYSIS = (
    Path(__file__).resolve().parents[5]
    / "results/challenge-194/p0_analysis.json"
)
EXPECTED_SPANS = {
    (0.9).hex(): ((4, 7), (0.48828125).hex(), float.fromhex("0x1.312d000000000p+0").hex()),
    (1.0).hex(): ((5, 9), float.fromhex("0x1.3880000000000p-1").hex(), float.fromhex("0x1.dcd6500000000p+0").hex()),
}
EXPECTED_GRIDS = {
    (0.9).hex(): [
        "0x1.f400000000000p-2", "0x1.1085a00000000p-1",
        "0x1.270b400000000p-1", "0x1.3d90e00000000p-1",
        "0x1.5416800000000p-1", "0x1.6a9c200000000p-1",
        "0x1.8121c00000000p-1", "0x1.97a7600000000p-1",
        "0x1.ae2d000000000p-1", "0x1.c4b2a00000000p-1",
        "0x1.db38400000000p-1", "0x1.f1bde00000000p-1",
        "0x1.0421c00000000p+0", "0x1.0f64900000000p+0",
        "0x1.1aa7600000000p+0", "0x1.25ea300000000p+0",
        "0x1.312d000000000p+0",
    ],
    (1.0).hex(): [
        "0x1.3880000000000p-1", "0x1.6092ca0000000p-1",
        "0x1.88a5940000000p-1", "0x1.b0b85e0000000p-1",
        "0x1.d8cb280000000p-1", "0x1.006ef90000000p+0",
        "0x1.14785e0000000p+0", "0x1.2881c30000000p+0",
        "0x1.3c8b280000000p+0", "0x1.50948d0000000p+0",
        "0x1.649df20000000p+0", "0x1.78a7570000000p+0",
        "0x1.8cb0bc0000000p+0", "0x1.a0ba210000000p+0",
        "0x1.b4c3860000000p+0", "0x1.c8cceb0000000p+0",
        "0x1.dcd6500000000p+0",
    ],
}

def test_extension_ranges_are_derived_from_exact_real_p0():
    source = json.loads(P0_ANALYSIS.read_text(encoding="utf-8"))
    derived = extension.derive_p0_extension_ranges(source)
    assert derived[(0.9).hex()]["four_sector_components"] == [[5, 5]]
    assert derived[(0.9).hex()]["q_g_components"] == [[6, 6], [13, 14]]
    assert derived[(1.0).hex()]["four_sector_components"] == [[6, 7]]
    assert derived[(1.0).hex()]["q_g_components"] == [[8, 8], [12, 14]]
    for sigma_hex, (guard_indices, lower, upper) in EXPECTED_SPANS.items():
        assert derived[sigma_hex]["guard_interval_indices"] == list(guard_indices)
        assert derived[sigma_hex]["lower_kappa_hex"] == lower
        assert derived[sigma_hex]["upper_kappa_hex"] == upper

def test_extension_grids_are_recursive_binary64_and_hash_bound():
    source = json.loads(P0_ANALYSIS.read_text(encoding="utf-8"))
    protocol = extension.build_p0_extension_protocol(source)
    entries = {entry["sigma_hex"]: entry for entry in protocol["sigma_entries"]}
    assert {sigma: entry["kappas"] for sigma, entry in entries.items()} == EXPECTED_GRIDS
    assert entries[(0.9).hex()]["grid_sha256"] == extension.EXTENSION_GRID_HASHES[(0.9).hex()]
    assert entries[(1.0).hex()]["grid_sha256"] == extension.EXTENSION_GRID_HASHES[(1.0).hex()]
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
cd /home/footman/code/quantum.harness-challenge-194/tracks/qmc/solutions/frustration-free/challenge-194
uv run --with pytest pytest tests/test_pilot_extension.py -q
```

Expected: collection fails with
`ModuleNotFoundError: No module named 'long_range_percolation.pilot_extension'`.

- [ ] **Step 3: Implement exact constants and recursive derivation**

Create these public constants and helpers. `_marked_components` must reject an
empty list only at the caller, and `_component_gap` treats touching components
as distance zero:

```python
EXTENSION_PROTOCOL_SCHEMA = "challenge-194-p0-extension-protocol-v1"
EXTENSION_RUN_SPEC_SCHEMA = "challenge-194-p0-extension-run-spec-v1"
EXTENSION_PROGRESS_SCHEMA = "challenge-194-p0-extension-progress-v1"
EXTENSION_ANALYSIS_SCHEMA = "challenge-194-p0-extension-analysis-v1"
COMBINED_ANALYSIS_SCHEMA = "challenge-194-p0-combined-analysis-v2"
COMBINED_BRACKET_SCHEMA = "challenge-194-p1-brackets-v2"
EXTENSION_SIGMAS = (0.9, 1.0)
EXTENSION_LENGTHS = (2**10, 2**14, 2**18)
EXTENSION_REPLICAS = tuple(range(24, 40))
EXTENSION_MASTER_SEED = 19_420_262_729
EXTENSION_PHASE = "pilot"
EXTENSION_GRID_NAMESPACE = "pilot-p0-extension-v1"
EXTENSION_GRID_HASHES = MappingProxyType({
    (0.9).hex(): "76dc7e07639ed085873a8f291cc2aaee0e8942ddac8efce3982743dd67491071",
    (1.0).hex(): "d40b4a2afac533d74965513513fff1870918831000b2e040063ca2a0e29ad091",
})

def _marked_components(indices: Sequence[int]) -> tuple[tuple[int, int], ...]:
    ordered = tuple(sorted(set(indices)))
    if tuple(indices) != ordered:
        raise RuntimeError("marked interval indices are not canonical")
    components: list[tuple[int, int]] = []
    for index in ordered:
        if components and index == components[-1][1] + 1:
            components[-1] = (components[-1][0], index)
        else:
            components.append((index, index))
    return tuple(components)

def _component_gap(left: tuple[int, int], right: tuple[int, int]) -> int:
    if left[1] < right[0]:
        return right[0] - left[1] - 1
    if right[1] < left[0]:
        return left[0] - right[1] - 1
    return 0

def _recursive_binary64_grid_17(lower: float, upper: float) -> tuple[float, ...]:
    if not math.isfinite(lower) or not math.isfinite(upper) or lower <= 0.0 or upper <= lower:
        raise RuntimeError("extension grid endpoints are invalid")
    points = [lower, upper]
    for _level in range(4):
        previous = sorted(points)
        points.extend(left + (right - left) / 2.0 for left, right in pairwise(previous))
    ordered = tuple(sorted({value.hex(): value for value in points}.values()))
    if len(ordered) != 17 or ordered[0] != lower or ordered[-1] != upper:
        raise RuntimeError("extension span cannot produce 17 binary64 points")
    return ordered
```

`derive_p0_extension_ranges` must call the existing validated selector parser
and `_transition_evidence`, form components, choose the lowest crossing
component and nearest/lower `Q_G` component, add one guard interval on each
side, and reject a missing guard:

```python
def derive_p0_extension_ranges(
    p0_analysis: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    sigmas, lengths, kappas, values = _selector_estimates(p0_analysis)
    selected_lengths = (lengths[-2], lengths[-1])
    result: dict[str, dict[str, object]] = {}
    for sigma in EXTENSION_SIGMAS:
        if sigma not in sigmas:
            raise RuntimeError("blocked sigma is missing from P0 analysis")
        q_indices: list[int] = []
        crossing_indices: list[int] = []
        for interval_index in range(1, len(kappas) - 1):
            q_marked, crossing_marked, _evidence = _transition_evidence(
                sigma, selected_lengths, kappas, values, interval_index
            )
            q_indices.extend([interval_index] if q_marked else [])
            crossing_indices.extend([interval_index] if crossing_marked else [])
        q_components = _marked_components(q_indices)
        crossing_components = _marked_components(crossing_indices)
        if not q_components or not crossing_components:
            raise RuntimeError("extension estimator component is missing")
        crossing = crossing_components[0]
        q_component = min(
            q_components,
            key=lambda component: (_component_gap(component, crossing), component[0]),
        )
        union_lower = min(crossing[0], q_component[0])
        union_upper = max(crossing[1], q_component[1])
        guard_lower = union_lower - 1
        guard_upper = union_upper + 1
        if guard_lower < 1 or guard_upper + 1 >= len(kappas):
            raise RuntimeError("extension range lacks adjacent P0 guards")
        lower = kappas[guard_lower]
        upper = kappas[guard_upper + 1]
        grid = _recursive_binary64_grid_17(lower, upper)
        result[sigma.hex()] = {
            "sigma_hex": sigma.hex(),
            "lengths": list(selected_lengths),
            "q_g_components": [list(component) for component in q_components],
            "four_sector_components": [list(component) for component in crossing_components],
            "selected_q_g_component": list(q_component),
            "selected_four_sector_component": list(crossing),
            "guard_interval_indices": [guard_lower, guard_upper],
            "lower_kappa_hex": lower.hex(),
            "upper_kappa_hex": upper.hex(),
            "kappas": [value.hex() for value in grid],
        }
    return result
```

- [ ] **Step 4: Implement protocol requests, identities, hashes, and validation**

`build_p0_extension_protocol` must require the exact source hashes from Global
Constraints, compute both exact grid IDs, build kernels and 96 requests in
canonical order, compare all request/RNG hashes against P0 hashes, reject
master-seed or replica overlap with P0/P1, and hash the unsigned document.
The document keys are fixed:

```python
{
    "schema_version": EXTENSION_PROTOCOL_SCHEMA,
    "source_p0_run_spec_sha256": P0_RUN_SPEC_SHA256,
    "source_p0_progress_sha256": P0_PROGRESS_SHA256,
    "source_p0_analysis_document_sha256": P0_ANALYSIS_DOCUMENT_SHA256,
    "source_p0_bracket_document_sha256": P0_BRACKET_DOCUMENT_SHA256,
    "design_sha256": _file_sha256(_design_path()),
    "source_revision": _current_revision(),
    "grid_namespace": EXTENSION_GRID_NAMESPACE,
    "master_seed": EXTENSION_MASTER_SEED,
    "phase": EXTENSION_PHASE,
    "purpose": "exploratory-p0-extension-only",
    "lengths": list(EXTENSION_LENGTHS),
    "replicas": list(EXTENSION_REPLICAS),
    "loop_order": ["sigma", "length", "replica"],
    "sigma_entries": sigma_entries,
    "cells": cells,
    "cell_count": 96,
    "rng_assignment_sha256": _sha256(_canonical_bytes({"assignments": assignments})),
    "protocol_sha256": protocol_sha256,
}
```

Each cell has the same path fields as `PilotCell`, its sigma-specific 17
couplings, and the exact grid ID from the design. Validation reconstructs
every kernel, request, stream, cell ID, path, and aggregate assignment hash;
it accepts no unknown fields.

- [ ] **Step 5: Add adversarial protocol tests**

Parameterize mutations for source hashes, component order, noncanonical
binary64, grid order, grid hash, design hash, cell order, missing/duplicate
replicas, request digest, RNG digest, P0 collision, and P1 identity overlap.
Each mutation must recompute superficial outer hashes and still fail the
semantic validator with a specific `RuntimeError`.

- [ ] **Step 6: Run focused tests and static checks**

Run:

```bash
uv run --with pytest pytest tests/test_pilot_extension.py -q
uv run --with ruff ruff check src/long_range_percolation/pilot_extension.py tests/test_pilot_extension.py
uv run --with ruff ruff format --check src/long_range_percolation/pilot_extension.py tests/test_pilot_extension.py
uv run python -m compileall -q src/long_range_percolation/pilot_extension.py tests/test_pilot_extension.py
```

Expected: every command exits `0`; pytest reports no failures, Ruff prints
`All checks passed!`, format reports both files formatted, and compileall is
silent.

- [ ] **Step 7: Commit Task 1**

```bash
git add \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_extension.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_extension.py
git commit -m "Add versioned P0 extension protocol"
```

Expected: commit succeeds with exactly the two Task 1 files.

### Task 2: Immutable Extension Protocol CLI

**Files:**
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/scripts/analyze_pilot.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_analyze_pilot_cli.py`

**Interfaces:**
- Consumes: exact canonical P0 analysis file.
- Produces: `build-p0-extension --analysis PATH --output PATH`, returning `published` or `verified-existing`.

- [ ] **Step 1: Write failing CLI publication tests**

Add a test that invokes `build-p0-extension` twice, verifies identical bytes,
then changes the generated protocol and proves the installed file is not
replaced:

```python
def test_build_p0_extension_publishes_once_and_rejects_different_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    source = _analysis_document(complete=True)
    source_path = tmp_path / "p0_analysis.json"
    output = tmp_path / "p0_extension_v1_protocol.json"
    source_path.write_bytes(_canonical_bytes(source))
    protocol = {"schema_version": extension.EXTENSION_PROTOCOL_SCHEMA, "protocol_sha256": "a" * 64}
    monkeypatch.setattr(CLI, "build_p0_extension_protocol", lambda _source: protocol)
    assert CLI.main(["build-p0-extension", "--analysis", str(source_path), "--output", str(output)]) == 0
    installed = output.read_bytes()
    assert json.loads(capsys.readouterr().out)["publication"] == "published"
    assert CLI.main(["build-p0-extension", "--analysis", str(source_path), "--output", str(output)]) == 0
    assert output.read_bytes() == installed
    assert json.loads(capsys.readouterr().out)["publication"] == "verified-existing"
    monkeypatch.setattr(CLI, "build_p0_extension_protocol", lambda _source: {**protocol, "protocol_sha256": "b" * 64})
    assert CLI.main(["build-p0-extension", "--analysis", str(source_path), "--output", str(output)]) == 1
    assert output.read_bytes() == installed
```

- [ ] **Step 2: Run the CLI test and verify RED**

Run:

```bash
uv run --with pytest pytest tests/test_analyze_pilot_cli.py::test_build_p0_extension_publishes_once_and_rejects_different_bytes -q
```

Expected: argparse exits because `build-p0-extension` is not a registered
command.

- [ ] **Step 3: Add the parser and immutable command**

Import `EXTENSION_PROTOCOL_SCHEMA` and `build_p0_extension_protocol`. Register
two required `Path` arguments and use the existing bounded canonical reader
and `_publish_or_verify`:

```python
extension = commands.add_parser("build-p0-extension")
extension.add_argument("--analysis", type=Path, required=True)
extension.add_argument("--output", type=Path, required=True)

if arguments.command == "build-p0-extension":
    source = _mapping_document(arguments.analysis.resolve(), "P0 analysis document")
    document = build_p0_extension_protocol(source)
    publication = _publish_or_verify(
        arguments.output.resolve(), document, EXTENSION_PROTOCOL_SCHEMA
    )
    result = {
        "status": "ready",
        "publication": publication,
        "output": str(arguments.output.resolve()),
        "protocol_sha256": document["protocol_sha256"],
    }
```

- [ ] **Step 4: Run CLI and protocol regressions**

Run:

```bash
uv run --with pytest pytest tests/test_analyze_pilot_cli.py tests/test_pilot_extension.py -q
```

Expected: all tests pass; the existing `build-p1` test still refuses the
unextended P0 analysis and leaves its output absent.

- [ ] **Step 5: Commit Task 2**

```bash
git add \
  tracks/qmc/solutions/frustration-free/challenge-194/scripts/analyze_pilot.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_analyze_pilot_cli.py
git commit -m "Publish immutable P0 extension protocol"
```

### Task 3: Extension Run Spec and Shared Runtime

**Files:**
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_extension.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_extension.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot.py`

**Interfaces:**
- Consumes: validated extension protocol, absolute output root, approved validation report.
- Produces: `build_p0_extension_run_spec(output_root: Path, validation_report: Path, protocol: Mapping[str, object]) -> dict[str, object]`, `load_p0_extension_run_spec(path: Path, verify_current_environment: bool = True) -> dict[str, object]`, and schema-dispatched cell/pending/merge/verify behavior.

- [ ] **Step 1: Write failing run-spec and schema-separation tests**

Cover exact outer fields, copied 96-cell assignment, correctness/runtime/design
binding, canonical paths, extension progress schema, and public loader
separation:

```python
def test_extension_run_spec_is_bound_and_p0_loader_stays_strict(tmp_path: Path):
    protocol = _extension_protocol_fixture()
    run_spec = pilot._write_test_extension_run_spec(tmp_path / "extension", protocol=protocol)
    loaded = pilot.load_p0_extension_run_spec(run_spec, verify_current_environment=False)
    assert loaded["schema_version"] == extension.EXTENSION_RUN_SPEC_SCHEMA
    assert loaded["source_extension_protocol_sha256"] == protocol["protocol_sha256"]
    assert loaded["cells"] == protocol["cells"]
    with pytest.raises(RuntimeError, match="P0 run spec"):
        pilot.load_pilot_run_spec(run_spec, verify_current_environment=False)

def test_extension_small_cell_restart_and_merge_use_extension_progress(tmp_path: Path):
    run_spec = pilot._write_test_extension_run_spec(tmp_path / "extension", tiny=True)
    first = pilot._run_test_registered_pilot_cell(run_spec, 0)
    second = pilot._run_test_registered_pilot_cell(run_spec, 0)
    assert first == second
    merged = pilot._merge_test_registered_pilot_progress(run_spec)
    assert merged["schema_version"] == extension.EXTENSION_PROGRESS_SCHEMA
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
uv run --with pytest pytest \
  tests/test_pilot_extension.py \
  tests/test_pilot.py::test_public_loader_never_downgrades_frozen_p0 -q
```

Expected: failures report missing extension run-spec builders/loaders while
the existing P0 loader test still passes.

- [ ] **Step 3: Parameterize request reconstruction without changing P0 bytes**

Change `PilotCell.request` and stream derivation to take explicit identity
parameters; update all P0 call sites with the existing constants:

```python
def request(self, *, master_seed: int, phase: str) -> TrajectoryRequest:
    return TrajectoryRequest(
        length=self.length,
        sigma=self.sigma,
        sigma_grid_id=self.sigma_grid_id,
        kappas=np.asarray(self.kappas, dtype=np.float64),
        master_seed=master_seed,
        phase=phase,
        replica=self.replica,
        kernel_sha256=self.kernel_sha256,
    )

def _stream_hashes(
    length: int,
    sigma_grid_id: str,
    replica: int,
    *,
    master_seed: int,
    phase: str,
) -> tuple[str, ...]:
    return tuple(
        derive_stream_material(
            StreamIdentity(
                master_seed=master_seed,
                phase=phase,
                length=length,
                sigma_grid_id=sigma_grid_id,
                replica=replica,
                stream_id=stream,
            )
        ).material_sha256
        for stream in range(STREAM_COUNT)
    )
```

Run the existing exact P0 registry test immediately after this mechanical
change. Expected: it passes without a changed P0 run-spec hash.

- [ ] **Step 4: Add explicit production schema dispatch**

Introduce an immutable internal contract selected only by exact schema:

```python
@dataclass(frozen=True)
class PilotRunContract:
    run_spec_schema: str
    progress_schema: str
    master_seed: int
    phase: str
    production_kind: str

P0_CONTRACT = PilotRunContract(
    RUN_SPEC_SCHEMA, MERGED_SCHEMA, PILOT_MASTER_SEED, PILOT_PHASE, "p0"
)
EXTENSION_CONTRACT = PilotRunContract(
    EXTENSION_RUN_SPEC_SCHEMA,
    EXTENSION_PROGRESS_SCHEMA,
    EXTENSION_MASTER_SEED,
    EXTENSION_PHASE,
    "p0-extension-v1",
)

def _contract_for_schema(schema: object) -> PilotRunContract:
    if schema == RUN_SPEC_SCHEMA:
        return P0_CONTRACT
    if schema == EXTENSION_RUN_SPEC_SCHEMA:
        return EXTENSION_CONTRACT
    raise RuntimeError("registered Pilot run-spec schema is not supported")
```

Keep `load_pilot_run_spec` hard-bound to `RUN_SPEC_SCHEMA`. Add
`load_p0_extension_run_spec` hard-bound to `EXTENSION_RUN_SPEC_SCHEMA`.
Internal worker, pending, merge, verify, and snapshot paths use
`_contract_for_schema`; no boolean may downgrade a production schema to a
test schema.

- [ ] **Step 5: Build and validate the extension run spec**

`build_p0_extension_run_spec` validates the protocol first, requires absolute
paths and a clean source, verifies correctness, records runtime capability,
copies the exact protocol cells, and adds only these extension-specific outer
fields:

```python
{
    "schema_version": EXTENSION_RUN_SPEC_SCHEMA,
    "artifact_root": ".",
    "protocol": protocol_without_cells,
    "cells": protocol["cells"],
    "cell_count": 96,
    "source_extension_protocol_sha256": protocol["protocol_sha256"],
    "source_p0_analysis_document_sha256": protocol["source_p0_analysis_document_sha256"],
    "design_sha256": protocol["design_sha256"],
    "correctness_report_sha256": correctness["correctness_report_sha256"],
    "correctness_run_spec_sha256": correctness["correctness_run_spec_sha256"],
    "correctness_approval_registry_sha256": correctness["correctness_approval_registry_sha256"],
    "correctness_approval_revision": CORRECTNESS_APPROVAL_REVISION,
    "validation_source_revision": correctness["validation_source_revision"],
    "validated_engine_modules": dict(correctness["validated_engine_modules"]),
    "validated_engine_sha256": correctness["validated_engine_sha256"],
    "validation_runtime_capability_sha256": correctness["validation_runtime_capability_sha256"],
    "orchestration_revision": source["source_revision"],
    "clean_tree": True,
    "uv_lock_sha256": _lock_hash(),
    "runtime_capability": runtime,
    "runtime_capability_sha256": runtime_sha256,
    "analysis_plan_sha256": _analysis_plan_hash(),
    "rng_assignment_sha256": protocol["rng_assignment_sha256"],
    "capability_waiver": capability_waiver,
    "merged_progress_path": MERGED_NAME,
    "run_spec_sha256": run_spec_sha256,
}
```

Validation reconstructs protocol semantics, each request with the contract
seed/phase, all paths, correctness evidence, runtime, analysis-plan bytes, and
outer document hash. Existing P0 expected fields and validation stay exact.

- [ ] **Step 6: Extend restart, merge, verify, and snapshot tests**

Reuse tiny extension fixtures to prove duplicate execution, trajectory/batch/
progress/outer-marker restart, `.partial` and `.intent` preservation, swapped
cell/root rejection, exactly 96 production cells, no extras at merge, and
extension progress schema. Add a P0 regression that feeds an internally
rehashed extension to `load_pilot_run_spec` and confirms rejection.

- [ ] **Step 7: Run focused and runtime regressions**

Run:

```bash
uv run --with pytest pytest tests/test_pilot_extension.py tests/test_pilot.py -q
uv run --with ruff ruff check --ignore SIM102,TRY004,UP017,PYI025,F401 \
  src/long_range_percolation/pilot.py \
  src/long_range_percolation/pilot_extension.py \
  tests/test_pilot.py tests/test_pilot_extension.py
uv run python -m compileall -q \
  src/long_range_percolation/pilot.py \
  src/long_range_percolation/pilot_extension.py
```

Expected: all tests pass, Ruff reports no new finding, and compileall is
silent.

- [ ] **Step 8: Commit Task 3**

```bash
git add \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot.py \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_extension.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_extension.py
git commit -m "Add authenticated P0 extension runtime"
```

### Task 4: Build/Worker CLIs, Slurm Wrappers, and Bound Documentation

**Files:**
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/scripts/run_pilot.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_array_slurm.sh`
- Create: `tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_build_slurm.sh`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_extension.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_runtime.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/PILOT_PLAN.md`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/README.md`

**Interfaces:**
- Consumes: extension protocol, approved validation report, exact clean checkout, Slurm array task ID.
- Produces: `build-extension-spec`; schema-dispatched worker commands; exact one-CPU/1800-MiB/40-minute wrappers.

- [ ] **Step 1: Write failing CLI and wrapper contract tests**

Tests must assert:

```python
def test_extension_wrapper_has_exact_resources_and_task_map():
    text = (ROOT / "scripts/pilot_extension_array_slurm.sh").read_text()
    assert "#SBATCH --cpus-per-task=1" in text
    assert "#SBATCH --mem=1800M" in text
    assert "#SBATCH --time=00:40:00" in text
    assert "SLURM_ARRAY_TASK_ID < 1 || SLURM_ARRAY_TASK_ID > 96" in text
    assert "CELL_INDEX=$((SLURM_ARRAY_TASK_ID - 1))" in text
    assert "scripts/run_pilot.py run-cell" in text

def test_build_extension_spec_requires_protocol_and_exact_output_path():
    parser = run_pilot_cli._parser()
    args = parser.parse_args([
        "build-extension-spec",
        "--protocol", "/tmp/p0_extension_v1_protocol.json",
        "--validation-report", "/tmp/report.json",
        "--output-root", "/tmp/pilot-p0-extension-v1",
        "--run-spec", "/tmp/pilot-p0-extension-v1/run_spec.json",
    ])
    assert args.command == "build-extension-spec"
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
uv run --with pytest pytest tests/test_pilot_extension.py tests/test_runtime.py -q
```

Expected: failures report absent wrappers and absent
`build-extension-spec`.

- [ ] **Step 3: Implement `run_pilot.py` extension construction and dispatch**

Register `build-extension-spec` with required protocol, validation report,
output root, and run-spec paths. Require
`run_spec == output_root / "run_spec.json"`, load protocol with the bounded
canonical reader, call `build_p0_extension_run_spec`, and print:

```python
{
    "status": "ready",
    "cells": 96,
    "run_spec": str(run_spec),
    "run_spec_sha256": document["run_spec_sha256"],
}
```

`run-cell`, `pending`, `merge`, and `verify` must call registered-schema
dispatch. Preserve the exact existing P0 JSON outputs.

- [ ] **Step 4: Create the extension worker wrapper**

Copy the existing environment-sanitization and safe cache logic, change only
the displayed campaign name, add exact SBATCH resources, retain task IDs
`1..96`, and execute:

```bash
#!/bin/bash
#SBATCH --cpus-per-task=1
#SBATCH --mem=1800M
#SBATCH --time=00:40:00
set -euo pipefail

: "${HARNESS_RUN_SPEC:?Set HARNESS_RUN_SPEC to the immutable extension run_spec.json}"
: "${SLURM_ARRAY_TASK_ID:?Run as a Slurm array task}"
: "${HARNESS_ENTRYPOINT:?Set the exact deployed repository root}"
: "${HARNESS_COMMAND:?Set the exact offline Python executable}"
CHALLENGE_194_REPO_ROOT="${HARNESS_ENTRYPOINT}"
CHALLENGE_194_PYTHON="${HARNESS_COMMAND}"
if [[ ! "${SLURM_ARRAY_TASK_ID}" =~ ^[0-9]+$ ]] ||
   (( SLURM_ARRAY_TASK_ID < 1 || SLURM_ARRAY_TASK_ID > 96 )); then
    exit 64
fi
CELL_INDEX=$((SLURM_ARRAY_TASK_ID - 1))
```

The remainder must be the tested P0 sanitization/cache implementation, ending
with exact deployed `PYTHONPATH` and `scripts/run_pilot.py run-cell`.

- [ ] **Step 5: Create the compute-node build wrapper**

The build wrapper requests one CPU, 1800 MiB, and ten minutes; requires
`HARNESS_RUN_SPEC` to be the exact P0 analysis path, `HARNESS_ENTRYPOINT` to
be the deployed repository root, and `HARNESS_COMMAND` to be the offline
Python. It derives all remaining fixed paths from the P0 analysis parent,
applies the same environment sanitation/cache contract, verifies the exact
canonical P0 analysis SHA256, and then runs:

```bash
P0_ANALYSIS_PATH="${HARNESS_RUN_SPEC}"
CHALLENGE_194_REPO_ROOT="${HARNESS_ENTRYPOINT}"
CHALLENGE_194_PYTHON="${HARNESS_COMMAND}"
RESULTS_ROOT="$(dirname "${P0_ANALYSIS_PATH}")"
EXTENSION_PROTOCOL_PATH="${RESULTS_ROOT}/p0_extension_v1_protocol.json"
VALIDATION_REPORT_PATH="${RESULTS_ROOT}/validation-prod-877ab93/report/report.json"
EXTENSION_ROOT="${RESULTS_ROOT}/pilot-p0-extension-v1"
"${CHALLENGE_194_PYTHON}" scripts/analyze_pilot.py build-p0-extension \
  --analysis "${P0_ANALYSIS_PATH}" \
  --output "${EXTENSION_PROTOCOL_PATH}"
"${CHALLENGE_194_PYTHON}" scripts/run_pilot.py build-extension-spec \
  --protocol "${EXTENSION_PROTOCOL_PATH}" \
  --validation-report "${VALIDATION_REPORT_PATH}" \
  --output-root "${EXTENSION_ROOT}" \
  --run-spec "${EXTENSION_ROOT}/run_spec.json"
```

All three harness paths must be absolute and canonical. The wrapper fails if
the extension root exists with different bytes.

- [ ] **Step 6: Freeze `PILOT_PLAN.md` before run-spec construction**

Document all Global Constraints, exact grids and hashes, component rule,
schemas, artifact names, one-CPU/1800-MiB/40-minute resources, restart rules,
three submission batches, and six acceptance checks. Update README with the
same commands but state that no extension data or P1 protocol exists yet.

- [ ] **Step 7: Run shell, docs, CLI, and core regressions**

Run:

```bash
bash -n scripts/pilot_extension_array_slurm.sh scripts/pilot_extension_build_slurm.sh
uv run --with pytest pytest \
  tests/test_pilot_extension.py tests/test_pilot.py \
  tests/test_runtime.py tests/test_analyze_pilot_cli.py -q
git diff --check
```

Expected: shell syntax is silent, all tests pass, and diff check is silent.

- [ ] **Step 8: Commit Task 4 and record the submission revision**

```bash
git add \
  tracks/qmc/solutions/frustration-free/challenge-194/scripts/run_pilot.py \
  tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_array_slurm.sh \
  tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_build_slurm.sh \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_extension.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_runtime.py \
  tracks/qmc/solutions/frustration-free/challenge-194/PILOT_PLAN.md \
  tracks/qmc/solutions/frustration-free/challenge-194/README.md
git commit -m "Prepare P0 extension cluster campaign"
git rev-parse HEAD
```

Expected: commit succeeds and `git rev-parse HEAD` yields the immutable
submission revision used throughout Task 5.

### Task 5: Deploy and Submit the 96-Cell Campaign

**Files:**
- Read only: `skills/using-slurm/profiles/wuzh02-jiangweiqi.toml`
- Read only: `scripts/harness_slurm.sh`
- Generated outside Git: remote bundle, remote clean deployment, extension protocol/run root, and scheduler logs.

**Interfaces:**
- Consumes: exact Task 4 commit, Wuzh02 profile, remote approved correctness report, local immutable P0 analysis.
- Produces: clean remote deployment, immutable run spec, build job record, and three resource-safe array job IDs.

- [ ] **Step 1: Define and verify exact deployment variables**

Run from repository root:

```bash
export HARNESS_CLUSTER_PROFILE=wuzh02-jiangweiqi
export SUBMIT_SHA="$(git rev-parse HEAD)"
export PROFILE="skills/using-slurm/profiles/wuzh02-jiangweiqi.toml"
export REMOTE_REPO="/work/share/giggleliu/jiangweiqi/quantum.harness-p0-extension-v2"
export REMOTE_BUNDLE="/work/share/giggleliu/jiangweiqi/challenge-194-p0-extension-v2.bundle"
export REMOTE_RESULTS="/work/share/giggleliu/jiangweiqi/results/challenge-194"
export REMOTE_ROOT="${REMOTE_RESULTS}/pilot-p0-extension-v1"
export REMOTE_ANALYSIS="${REMOTE_RESULTS}/p0_analysis.json"
export REMOTE_PROTOCOL="${REMOTE_RESULTS}/p0_extension_v1_protocol.json"
export REMOTE_VALIDATION="${REMOTE_RESULTS}/validation-prod-877ab93/report/report.json"
export REMOTE_PYTHON="/work/share/giggleliu/jiangweiqi/quantum.harness-challenge-194/.venv/bin/python"
export LOCAL_BUNDLE="/tmp/challenge-194-p0-extension-v2.bundle"
export REMOTE_BUNDLE_STAGE="${REMOTE_BUNDLE}.upload-${SUBMIT_SHA}-$(date -u +%Y%m%dT%H%M%S%N)-$$"
scripts/harness_slurm.sh precheck
scripts/harness_slurm.sh probe-partitions
```

The `v2` deployment and bundle names are fresh immutable namespaces for this
submission. Preserve the failed `v1` deployment, bundle, job logs, and all
other diagnostics without deletion or overwrite. The absent shared
`REMOTE_PROTOCOL` and `REMOTE_ROOT` result paths remain the preregistered
version-1 scientific artifact paths.

Expected: profile resolves to Wuzh02, SSH is `true`, the only dirty path is the
pre-existing `.superpowers/sdd/task-1-report.md`, and `wzacnormal03` is
available. Ratify `wzacnormal03`; stop if the dirty-path set differs.

- [ ] **Step 2: Ship only committed bytes with a Git bundle**

Run:

```bash
git bundle create "${LOCAL_BUNDLE}" challenge/194
BUNDLE_SHA256="$(sha256sum "${LOCAL_BUNDLE}" | awk '{print $1}')"
ssh wuzh02-jiangweiqi "
  set -euo pipefail
  test ! -e '${REMOTE_BUNDLE}'
  test ! -e '${REMOTE_REPO}'
  test ! -e '${REMOTE_BUNDLE_STAGE}'
"
scp "${LOCAL_BUNDLE}" "wuzh02-jiangweiqi:${REMOTE_BUNDLE_STAGE}"
ssh wuzh02-jiangweiqi "
  set -euo pipefail
  test \"\$(sha256sum '${REMOTE_BUNDLE_STAGE}' | awk '{print \$1}')\" = '${BUNDLE_SHA256}'
  ln -- '${REMOTE_BUNDLE_STAGE}' '${REMOTE_BUNDLE}'
  sync -f -- '${REMOTE_BUNDLE}'
  test \"\$(sha256sum '${REMOTE_BUNDLE}' | awk '{print \$1}')\" = '${BUNDLE_SHA256}'
  rm -- '${REMOTE_BUNDLE_STAGE}'
"
scp results/challenge-194/p0_analysis.json "wuzh02-jiangweiqi:${REMOTE_ANALYSIS}"
ssh wuzh02-jiangweiqi "
  set -euo pipefail
  test ! -e '${REMOTE_REPO}'
  git clone '${REMOTE_BUNDLE}' '${REMOTE_REPO}'
  git -C '${REMOTE_REPO}' checkout --detach '${SUBMIT_SHA}'
  test -z \"\$(git -C '${REMOTE_REPO}' status --porcelain)\"
  test \"\$(sha256sum '${REMOTE_ANALYSIS}' | awk '{print \$1}')\" = '44083701db692304cd3aa054c8a9488b75674cead7cd6bf479c0a203cc1fa10b'
  test \"\$(sha256sum '${REMOTE_VALIDATION}' | awk '{print \$1}')\" = '036b4b8a06164716aff5f40cc38ac4855a212026a556e1c5fe33ce32ce0babb8'
  test -x '${REMOTE_PYTHON}'
"
```

`ln` is the atomic no-replace publication primitive: a concurrent or existing
final bundle makes it fail without changing either object.
Preserve the staging path on any failure for diagnosis; remove it only after
hard-link installation,
file sync, and final SHA256 verification all succeed. Never delete or overwrite
an existing final bundle, deployment, staging diagnostic, or failed-attempt
artifact.

Expected: clean detached deployment at exactly `SUBMIT_SHA`; both hashes and
offline Python checks pass. Existing bundle/deployment paths fail closed.

- [ ] **Step 3: Feasibility-check and submit the build job**

Use the profile override for the new clean deployment. First run `--test-only`
with the exact environment exports in `--extra`, then submit the identical
command without `--test-only`:

```bash
HARNESS_REPO_REMOTE="${REMOTE_REPO}" scripts/harness_slurm.sh submit \
  --test-only \
  --script tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_build_slurm.sh \
  --run-spec "${REMOTE_ANALYSIS}" \
  --entrypoint "${REMOTE_REPO}" --command "${REMOTE_PYTHON}" \
  --partition wzacnormal03 --time 00:10:00 --cpus 1 \
  --extra "--mem=1800M"
```

Expected: Slurm accepts one CPU, 1800 MiB, and ten minutes. Submit only after
reviewing the estimate. Capture the real build job ID, wait for completion,
then verify remotely:

```bash
ssh wuzh02-jiangweiqi "
  set -euo pipefail
  '${REMOTE_PYTHON}' '${REMOTE_REPO}/tracks/qmc/solutions/frustration-free/challenge-194/scripts/run_pilot.py' pending \
    --run-spec '${REMOTE_ROOT}/run_spec.json'
"
```

Expected: canonical JSON with status `pending`, count `96`, and cell indices
`0..95`.

- [ ] **Step 4: Smoke-submit task IDs 1–2**

Feasibility-check, then submit:

```bash
HARNESS_REPO_REMOTE="${REMOTE_REPO}" scripts/harness_slurm.sh submit \
  --test-only \
  --script tracks/qmc/solutions/frustration-free/challenge-194/scripts/pilot_extension_array_slurm.sh \
  --run-spec "${REMOTE_ROOT}/run_spec.json" \
  --entrypoint "${REMOTE_REPO}" --command "${REMOTE_PYTHON}" \
  --partition wzacnormal03 --time 00:40:00 --cpus 1 \
  --extra "--mem=1800M --array=1-2%2"
```

Expected: feasibility succeeds. Submit the same command without
`--test-only`, capture the job ID, monitor pending-to-running, inspect one
startup log, and classify after completion. Both cells must have verified
success manifests before continuing.

- [ ] **Step 5: Submit remaining light/medium and heavy batches concurrently**

After smoke success, feasibility-check and submit these two exact arrays:

```text
Light/medium task IDs: 3-32,49-80 with concurrency cap 16
Heavy task IDs: 33-48,81-96 with concurrency cap 8
```

Use the Step 4 command with only `--array` changed to
`3-32,49-80%16` and `33-48,81-96%8`. Expected: 62 light/medium tasks and 32
heavy tasks, with at most 24 concurrent cells, 24 CPUs, and 43,200 MiB
requested across both arrays. Capture both job IDs, partition, wall time,
array expression, and submit SHA.

- [ ] **Step 6: Monitor without treating scheduler state as evidence**

For every job ID:

```bash
scripts/harness_slurm.sh status BUILD_OR_ARRAY_JOB_ID
scripts/harness_slurm.sh classify pilot-p0-extension-v1 BUILD_OR_ARRAY_JOB_ID
```

Replace `BUILD_OR_ARRAY_JOB_ID` with each captured numeric ID. Check pending
reason within three minutes, one startup log after running, and `sacct`
classification at completion. Do not retry OOM, timeout, or logic failures
without user ratification. Successful scheduler state does not satisfy the
scientific gate; Task 10 does.

### Task 6: Bounded Extension Aggregation

**Files:**
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_analysis.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_analysis.py`

**Interfaces:**
- Consumes: absolute verified extension `run_spec.json` and validated extension protocol mapping.
- Produces: `aggregate_p0_extension(run_spec: Path, protocol: Mapping[str, object]) -> dict[str, object]`.

- [ ] **Step 1: Write failing aggregation and snapshot tests**

Create tiny two-sigma, three-length, two-replica, three-coupling extension
fixtures. Assert one trajectory live at a time, exact grouping, `ddof=1`,
request order, source protocol/run/progress hashes, 102 production rows,
forged progress/manifest rejection, root/progress swap rejection, bounded
preflight, and cleanup behavior.

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run --with pytest pytest tests/test_pilot_analysis.py -q -k p0_extension
```

Expected: tests fail because `aggregate_p0_extension` is absent.

- [ ] **Step 3: Generalize the retained verified snapshot by contract**

Make `_open_verified_pilot_analysis_snapshot` dispatch the exact registered
run-spec schema and preserve all descriptor, resource, stale-owner, capacity,
global-byte-cap, and marker-last cleanup checks. Rename no version-2 stale
snapshot grammar; add the run kind to new snapshot names so P0 and extension
snapshots cannot collide.

- [ ] **Step 4: Implement extension aggregation**

Use the existing `_group_estimates` path with the per-cell sigma-specific
couplings. Emit:

```python
{
    "schema_version": EXTENSION_ANALYSIS_SCHEMA,
    "source_extension_protocol_sha256": protocol["protocol_sha256"],
    "extension_run_spec_sha256": _sha256(snapshot.run_spec_payload),
    "extension_progress_sha256": _sha256(snapshot.progress_payload),
    "source_revision": spec["orchestration_revision"],
    "analysis_plan_sha256": spec["analysis_plan_sha256"],
    "observable_columns": dict(OBSERVABLE_COLUMNS),
    "estimates": estimates,
    "analysis_document_sha256": digest,
}
```

Require exact 2×3×16 cell order and 17 finite ten-column rows per trajectory.
Retain one trajectory and one 16×17×4 group array at a time.

- [ ] **Step 5: Run focused and provenance regressions**

Run:

```bash
uv run --with pytest pytest tests/test_pilot_analysis.py tests/test_pilot.py -q
uv run --with ruff ruff check --ignore SIM102,TRY004,UP017,PYI025,F401 \
  src/long_range_percolation/pilot.py \
  src/long_range_percolation/pilot_analysis.py \
  tests/test_pilot_analysis.py
```

Expected: all tests pass and Ruff reports no new finding.

- [ ] **Step 6: Commit Task 6**

```bash
git add \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot.py \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_analysis.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_analysis.py
git commit -m "Add bounded P0 extension aggregation"
```

### Task 7: Combined Evidence and Exact Pooling

**Files:**
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_extension.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_analysis.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_analysis.py`

**Interfaces:**
- Consumes: validated P0 and extension analysis mappings.
- Produces: `combine_p0_evidence(p0_analysis: Mapping[str, object], extension_analysis: Mapping[str, object]) -> dict[str, object]`.

- [ ] **Step 1: Write failing union, pooling, and cardinality tests**

Use explicit replica arrays to derive independent expected means/SEs. Assert
16 rows for sigma `0.8` and `1.1`, 31 rows for sigma `0.9` and `1.0`, three
lengths, 282 total rows, counts 8/16/24, source order P0 then extension,
request uniqueness, and immutable source bindings.

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run --with pytest pytest tests/test_pilot_analysis.py -q -k combine_p0
```

Expected: tests fail because `combine_p0_evidence` is absent.

- [ ] **Step 3: Implement deterministic sufficient-moment pooling**

For each observable and shared endpoint, convert each source standard error
back to its sample second central moment and combine in fixed P0-then-extension
order:

```python
def _pool_estimates(
    left_n: int,
    left_mean: float,
    left_se: float,
    right_n: int,
    right_mean: float,
    right_se: float,
) -> tuple[int, float, float]:
    total = left_n + right_n
    delta = right_mean - left_mean
    mean = left_mean + delta * right_n / total
    left_m2 = (left_n - 1) * left_n * left_se * left_se
    right_m2 = (right_n - 1) * right_n * right_se * right_se
    pooled_m2 = left_m2 + right_m2 + delta * delta * left_n * right_n / total
    sample_variance = pooled_m2 / (total - 1)
    standard_error = math.sqrt(sample_variance / total)
    if not all(math.isfinite(value) for value in (mean, standard_error)):
        raise RuntimeError("combined estimate is nonfinite")
    return total, mean, standard_error
```

Tests compare this result with direct concatenated whole-replica fixtures.
No checkpoint is counted as a replica.

- [ ] **Step 4: Implement the per-sigma combined schema**

Emit ordered `sigma_entries`, each containing its exact `kappas`, lengths, and
length-major estimate rows. Preserve P0 estimates byte-for-byte for sigma
`0.8`/`1.1`, use extension-only estimates at new points, and pool only the two
shared endpoints for each blocked sigma. Bind both source analysis hashes,
run/progress hashes, source revisions, observable columns, ordered request
hashes, and unsigned canonical-document hash.

- [ ] **Step 5: Add adversarial combination tests**

Reject source hash changes, wrong extension grid, overlap other than two
endpoints, duplicate requests, missing length/replica, reordered entries,
noncanonical float hex, nonfinite moments, observable-column mismatch, and an
internally rehashed document that claims 282 rows but has a different shape.

- [ ] **Step 6: Run focused tests and commit**

Run:

```bash
uv run --with pytest pytest tests/test_pilot_analysis.py -q
git diff --check
```

Expected: all tests pass and diff check is silent.

Commit:

```bash
git add \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_extension.py \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_analysis.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_analysis.py
git commit -m "Combine verified P0 extension evidence"
```

### Task 8: Frozen Selector v2 and P1 Gate

**Files:**
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_analysis.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_analysis.py`

**Interfaces:**
- Consumes: P0-analysis-v1 or combined-analysis-v2 mapping.
- Produces: unchanged `select_p1_brackets(analysis: Mapping[str, object]) -> dict[str, object]`, bracket-v2 for combined input, and conditional `build_p1_protocol`.

- [ ] **Step 1: Write failing per-sigma selector and invariance tests**

Create combined fixtures with different coupling axes. Assert selected
nonzero common intervals for `0.9`/`1.0`, exact unchanged sigma `0.8` and
`1.1` windows, bracket-v2 source binding, byte-identical repeated selection,
and fail-closed output when one blocked sigma remains unresolved.

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run --with pytest pytest tests/test_pilot_analysis.py -q -k "combined_selector or p1_accepts_combined"
```

Expected: combined schema is rejected as unsupported.

- [ ] **Step 3: Normalize both schemas without changing selection functions**

Refactor only the input adapter. Return a tuple of per-sigma axes and values;
call existing `_transition_evidence`, `_select_transition_bracket`, and
`_select_crossover_bracket` unchanged:

```python
@dataclass(frozen=True)
class SelectorSigmaEvidence:
    sigma: float
    lengths: tuple[int, ...]
    kappas: tuple[float, ...]
    values: Mapping[tuple[float, int, float], tuple[float, float]]

def _selector_sigma_evidence(
    analysis: Mapping[str, object],
) -> tuple[SelectorSigmaEvidence, ...]:
    if analysis.get("schema_version") == ANALYSIS_SCHEMA:
        return _selector_v1_evidence(analysis)
    if analysis.get("schema_version") == COMBINED_ANALYSIS_SCHEMA:
        return _selector_v2_evidence(analysis)
    raise RuntimeError("analysis schema version is not supported")
```

For v1, retain `BRACKET_SCHEMA`; for combined v2, emit
`COMBINED_BRACKET_SCHEMA`. Both use the same evidence and tie-break payloads.

- [ ] **Step 4: Gate P1 on combined evidence**

`build_p1_protocol` accepts v1 only for backward-compatible tests and v2 for
the real handoff. For v2 it requires bracket-v2, all four statuses selected,
exact sigma `0.8` and `1.1` preserved windows, and
`requires_p0_extension is False`. P1 constants remain unchanged:
`P1_MASTER_SEED=19_420_261_729`, replicas `8..23`, four sigmas, three lengths,
nine points per selected interval, and `pilot-p1-v1`.

- [ ] **Step 5: Run original-selector and P1 regression locks**

Run:

```bash
uv run --with pytest pytest tests/test_pilot_analysis.py -q
```

Expected: all tests pass; the exact original real-P0 bracket hash remains
`fb3df666044bf9531443fc00c5c2c2d489512b4162864b3a92ffc2e756832403`,
and original P0 still blocks P1 for `0.9, 1.0`.

- [ ] **Step 6: Commit Task 8**

```bash
git add \
  tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_analysis.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_analysis.py
git commit -m "Rerun frozen selector on combined evidence"
```

### Task 9: Analysis CLI, Documentation, and Full Local Gate

**Files:**
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/scripts/analyze_pilot.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_analyze_pilot_cli.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_runtime.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/README.md`

**Interfaces:**
- Produces: `analyze-extension`, `combine`, `select`, and combined-aware `build-p1`.

- [ ] **Step 1: Write failing immutable command tests**

For each new command, test `published`, `verified-existing`, changed-byte
rejection, malformed canonical input rejection, and no output on scientific
failure. `build-p1` must leave `p1_protocol.json` absent when the combined
bracket remains unresolved.

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run --with pytest pytest tests/test_analyze_pilot_cli.py -q
```

Expected: new command names are rejected by argparse.

- [ ] **Step 3: Implement exact command dispatch**

Register and implement:

```text
analyze-extension --run-spec PATH --protocol PATH --output PATH
combine --p0-analysis PATH --extension-analysis PATH --output PATH
select --analysis PATH --output PATH
build-p1 --analysis PATH --output PATH
```

All reads use `_read_canonical_json`; all writes use `_publish_or_verify`.
`select` publishes the schema returned by `select_p1_brackets`. `build-p1`
reruns selection in memory and refuses unresolved evidence before opening its
output target.

- [ ] **Step 4: Document exact local artifact workflow**

README commands use:

```text
results/challenge-194/p0_extension_v1_protocol.json
results/challenge-194/pilot-p0-extension-v1/run_spec.json
results/challenge-194/p0_extension_v1_analysis.json
results/challenge-194/p0_combined_analysis_v2.json
results/challenge-194/p0_combined_brackets_v2.json
results/challenge-194/p1_protocol.json
```

State that source analyses must first be recomputed against their verified run
roots and return `verified-existing` before `combine`.

- [ ] **Step 5: Run the full local gate**

Run:

```bash
cd /home/footman/code/quantum.harness-challenge-194/tracks/qmc/solutions/frustration-free/challenge-194
uv run --with pytest pytest -q
uv run --with ruff ruff check --ignore SIM102,TRY004,UP017,PYI025,F401 \
  src/long_range_percolation/pilot.py \
  src/long_range_percolation/pilot_extension.py \
  src/long_range_percolation/pilot_analysis.py \
  scripts/run_pilot.py scripts/analyze_pilot.py \
  tests/test_pilot.py tests/test_pilot_extension.py \
  tests/test_pilot_analysis.py tests/test_analyze_pilot_cli.py tests/test_runtime.py
uv run --with ruff ruff format --check \
  src/long_range_percolation/pilot.py \
  src/long_range_percolation/pilot_extension.py \
  src/long_range_percolation/pilot_analysis.py \
  scripts/run_pilot.py scripts/analyze_pilot.py \
  tests/test_pilot.py tests/test_pilot_extension.py \
  tests/test_pilot_analysis.py tests/test_analyze_pilot_cli.py tests/test_runtime.py
bash -n scripts/download_pilot.sh scripts/pilot_extension_array_slurm.sh scripts/pilot_extension_build_slurm.sh
git diff --check
```

Expected: full pytest has zero failures, Ruff has no new findings, format is
clean, shell syntax is silent, and diff check is silent.

- [ ] **Step 6: Commit Task 9**

```bash
git add \
  tracks/qmc/solutions/frustration-free/challenge-194/scripts/analyze_pilot.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_analyze_pilot_cli.py \
  tracks/qmc/solutions/frustration-free/challenge-194/tests/test_runtime.py \
  tracks/qmc/solutions/frustration-free/challenge-194/README.md
git commit -m "Document P0 extension evidence workflow"
```

### Task 10: Harvest, Merge, Download, and Verify

**Files:**
- Generated outside Git: remote/local extension root, sibling transfer state, scheduler/transfer logs.

**Interfaces:**
- Consumes: three array job IDs and immutable remote run root.
- Produces: exact local verified 96-cell/96-trajectory extension root.

- [ ] **Step 1: Classify all array outcomes and list pending cells**

Run `status` and `classify` for all captured array IDs, then:

```bash
HARNESS_CLUSTER_PROFILE=wuzh02-jiangweiqi \
  scripts/harness_slurm.sh pending-cells pilot-p0-extension-v1
```

Expected: no pending cell IDs. If any cell failed, classify it as OOM,
walltime, nonzero exit, or logic failure; obtain user ratification before
resubmitting only those exact task IDs under the unchanged run spec.

- [ ] **Step 2: Merge and verify remotely**

Run:

```bash
ssh wuzh02-jiangweiqi "
  set -euo pipefail
  export PYTHONPATH='/work/share/giggleliu/jiangweiqi/quantum.harness-p0-extension-v2/tracks/qmc/solutions/frustration-free/challenge-194/src'
  '/work/share/giggleliu/jiangweiqi/quantum.harness-challenge-194/.venv/bin/python' \
    '/work/share/giggleliu/jiangweiqi/quantum.harness-p0-extension-v2/tracks/qmc/solutions/frustration-free/challenge-194/scripts/run_pilot.py' merge \
    --run-spec '/work/share/giggleliu/jiangweiqi/results/challenge-194/pilot-p0-extension-v1/run_spec.json'
  '/work/share/giggleliu/jiangweiqi/quantum.harness-challenge-194/.venv/bin/python' \
    '/work/share/giggleliu/jiangweiqi/quantum.harness-p0-extension-v2/tracks/qmc/solutions/frustration-free/challenge-194/scripts/run_pilot.py' verify \
    --run-spec '/work/share/giggleliu/jiangweiqi/results/challenge-194/pilot-p0-extension-v1/run_spec.json'
"
```

Expected final verifier JSON:
`{"cells":96,"status":"verified","trajectories":96}`.

- [ ] **Step 3: Download with hardened immutable transfer**

Run from the solution directory:

```bash
scripts/download_pilot.sh \
  wuzh02-jiangweiqi \
  /work/share/giggleliu/jiangweiqi/results/challenge-194/pilot-p0-extension-v1 \
  /home/footman/code/quantum.harness-challenge-194/results/challenge-194/pilot-p0-extension-v1 \
  /home/footman/code/quantum.harness-challenge-194/.venv/bin/python
```

Expected: checksummed transfer followed by exact 96/96 verifier JSON.
Transfer claims, logs, source, and verified completion remain sibling state
outside the immutable root.

- [ ] **Step 4: Independently reverify locally and rerun completed download**

Run local `run_pilot.py verify`, then repeat Step 3. Expected: both return
exact 96/96 JSON; the second transfer performs no rsync and does not change
the root or completion record.

### Task 11: Publish Extension/Combined Evidence and Perform P1 Handoff

**Files:**
- Generated outside Git: four immutable analysis/protocol JSON artifacts.
- Modify only after evidence exists: `tracks/qmc/solutions/frustration-free/challenge-194/README.md` if recording exact hashes.

**Interfaces:**
- Consumes: verified P0 and extension roots and exact source analyses.
- Produces: extension analysis, combined analysis, combined brackets, and conditionally P1 protocol.

- [ ] **Step 1: Recompute and byte-verify original P0 analysis**

Run:

```bash
uv run python scripts/analyze_pilot.py analyze \
  --run-spec /home/footman/code/quantum.harness-challenge-194/results/challenge-194/pilot-p0-739880d/run_spec.json \
  --output /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_analysis.json
```

Expected: `publication` is `verified-existing` and embedded hash is
`e42ef6b9f82380305f80ceaba384bc29cb9fe2da0848d4c72a904f4cb4c8c7c8`.

- [ ] **Step 2: Publish and byte-verify extension analysis**

Run `analyze-extension` twice with the local extension run spec, exact
extension protocol, and
`results/challenge-194/p0_extension_v1_analysis.json`. Expected: first result
is `published`, second is `verified-existing`, there are exactly 102 estimate
rows, and source run/progress/protocol hashes match verified inputs.

- [ ] **Step 3: Publish and byte-verify combined evidence**

Run `combine` twice with `p0_analysis.json`,
`p0_extension_v1_analysis.json`, and output
`p0_combined_analysis_v2.json`. Expected: first is `published`, second is
`verified-existing`, there are exactly 282 rows, blocked sigmas each have 31
couplings per length, and shared endpoints have replica count 24.

- [ ] **Step 4: Publish and independently rerun frozen selection**

Run `select` twice with combined analysis and output
`p0_combined_brackets_v2.json`. Expected: first is `published`, second is
`verified-existing`; compare both invocations byte-for-byte.

- [ ] **Step 5: Evaluate the six acceptance checks**

Require:

```text
1. Protocol verifies against exact P0 evidence and committed design.
2. Extension root verifies 96 cells and 96 trajectories.
3. Extension and combined analyses verify all canonical/source/semantic bindings.
4. Sigma 0.9 and 1.0 are selected on nonzero intervals marked by both estimators.
5. Sigma 0.8 remains [0x1.f400000000000p-2,0x1.3880000000000p-1] and sigma 1.1 remains [0x1.312d000000000p+0,0x1.7d78400000000p+0].
6. requires_p0_extension is false and independent bracket recomputation is byte-identical.
```

If any check fails, assert that `results/challenge-194/p1_protocol.json` is
absent, record the unresolved result, and stop. Do not alter sampling or
selection.

- [ ] **Step 6: Conditionally publish P1 protocol**

Only when all six checks pass, run:

```bash
uv run python scripts/analyze_pilot.py build-p1 \
  --analysis /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_combined_analysis_v2.json \
  --output /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p1_protocol.json
uv run python scripts/analyze_pilot.py verify \
  --analysis /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p0_combined_analysis_v2.json \
  --p1-protocol /home/footman/code/quantum.harness-challenge-194/results/challenge-194/p1_protocol.json
```

Expected on pass: first command reports `published`, second reports
`verified`, P1 still has four sigmas × three lengths × 16 replicas = 192
cells, and no P1 cell is executed.

- [ ] **Step 7: Record exact evidence hashes in one final local commit**

Update README only with observed immutable hashes and gate outcome; do not
commit generated results. Run the full Task 9 local gate, then:

```bash
git add tracks/qmc/solutions/frustration-free/challenge-194/README.md
git commit -m "Record P0 extension boundary evidence"
```

Expected: one documentation-only commit. Leave `.superpowers/sdd/task-1-report.md`
and `.superpowers/sdd/progress.md` untouched.

## Plan Completion Criteria

- Tasks 1–4 produce the shortest safe submission path and an exact clean
  submission revision.
- Task 5 submits all 96 cells in smoke, light/medium, and heavy batches without
  exceeding 24 concurrent one-core cells.
- Tasks 6–9 finish analysis code and local verification while Slurm runs.
- Task 10 closes the compute boundary with fetched semantic manifests, not
  scheduler status.
- Task 11 either publishes a verified P1 protocol without running it or
  preserves the fail-closed unresolved state.
- Every implementation task has focused RED/GREEN evidence and a local commit;
  no push is part of this plan.
