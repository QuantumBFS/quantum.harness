from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import jsonschema
import numpy as np
import pytest

from challenge148.ed import exact_thermal_observables
from challenge148.lattice import honeycomb_graph, triangular_graph, write_graph_json


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "adapters" / "qmc-ltfim"
RUNNER = ADAPTER / "run_independent.jl"
SCHEMAS = ROOT / "schemas"
JULIA = shutil.which("julia") or "julia"


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode()


@pytest.fixture(scope="session")
def build_info() -> dict[str, object]:
    result = subprocess.run(
        [JULIA, f"--project={ADAPTER}", str(RUNNER), "--build-info"],
        text=True,
        capture_output=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    info = json.loads(result.stdout)
    assert info["adapter"] == "QMC_LTFIM"
    assert info["qmc_revision"] == "524860b9c0e212ac630b0d9754075bb24198da3b"
    assert info["qmc_license"] == "Apache-2.0"
    assert info["julia"] == "1.11.6"
    assert info["seed_derivation"] == "sha256:qmc-ltfim-seed-v1||u64be"
    return info


def make_request(
    directory: Path,
    info: dict[str, object],
    *,
    graph=None,
    seed: int = 148_700,
    retained_samples: int = 4,
    bin_length: int = 2,
    checkpoint_bins: int = 1,
    thermalization_sweeps: int = 20,
    thinning: int = 1,
    beta: float = 0.75,
    coupling: float = 1.0,
    field: float = 1.2,
) -> tuple[Path, dict[str, object]]:
    directory.mkdir(parents=True)
    graph = graph or honeycomb_graph(2)
    graph_path = directory / "graph.json"
    write_graph_json(graph, graph_path)
    graph_json = json.loads(graph_path.read_text())
    request = {
        "schema_version": "qmc-request-v1",
        "adapter": "QMC_LTFIM",
        "graph_path": str(graph_path),
        "graph_sha256": graph_json["sha256"],
        "beta": beta,
        "coupling": coupling,
        "field": field,
        "seed": seed,
        "thermalization_sweeps": thermalization_sweeps,
        "retained_samples": retained_samples,
        "thinning": thinning,
        "serial_measurement_stride_samples": 1,
        "bin_length": bin_length,
        "checkpoint_bins": checkpoint_bins,
        "expected_source_hash": info["source_hash"],
        "expected_build_hash": info["build_hash"],
    }
    request_path = directory / "request.json"
    request_path.write_bytes(canonical_bytes(request))
    return request_path, request


def run(request: Path, output: Path, *, env=None, timeout=90):
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    return subprocess.run(
        [
            JULIA,
            f"--project={ADAPTER}",
            str(RUNNER),
            "--request",
            str(request),
            "--output-directory",
            str(output),
        ],
        text=True,
        capture_output=True,
        env=process_env,
        timeout=timeout,
    )


def start_paused(request: Path, output: Path, tmp_path: Path, point: str):
    ready = tmp_path / f"ready-{point}"
    release = tmp_path / f"release-{point}"
    process_env = os.environ.copy()
    process_env.update(
        {
            "QMC_LTFIM_TEST_PAUSE_AT": point,
            "QMC_LTFIM_TEST_READY": str(ready),
            "QMC_LTFIM_TEST_RELEASE": str(release),
        }
    )
    process = subprocess.Popen(
        [
            JULIA,
            f"--project={ADAPTER}",
            str(RUNNER),
            "--request",
            str(request),
            "--output-directory",
            str(output),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=process_env,
    )
    deadline = time.monotonic() + 90
    while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.02)
    assert ready.exists(), process.communicate(timeout=5)
    return process, release


def finish_paused(process: subprocess.Popen[str], release: Path):
    release.touch()
    stdout, stderr = process.communicate(timeout=90)
    return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


def pointer(output: Path) -> dict[str, object]:
    return json.loads((output / "current-generation.json").read_text())


def manifest(output: Path) -> dict[str, object]:
    digest = pointer(output)["generation_sha256"]
    return json.loads((output / "generations" / digest / "manifest.json").read_text())


def records(output: Path) -> list[dict[str, object]]:
    return [
        json.loads((output / "bins" / f"{digest}.ndjson").read_text())
        for digest in manifest(output)["bin_object_hashes"]
    ]


def generation_chain(output: Path) -> list[tuple[str, dict[str, object]]]:
    digest = pointer(output)["generation_sha256"]
    reverse = []
    while digest is not None:
        value = json.loads((output / "generations" / digest / "manifest.json").read_text())
        reverse.append((digest, value))
        digest = value["previous_generation_sha256"]
    return list(reversed(reverse))


def retained_bin_bytes(output: Path) -> list[bytes]:
    return [
        (output / "bins" / f"{digest}.ndjson").read_bytes()
        for digest in manifest(output)["bin_object_hashes"]
    ]


def publish_generation(output: Path, value: dict[str, object]) -> str:
    payload = canonical_bytes(value)
    digest = hashlib.sha256(payload).hexdigest()
    directory = output / "generations" / digest
    directory.mkdir()
    (directory / "manifest.json").write_bytes(payload)
    return digest


def test_owned_wrapper_and_closed_output_contract(build_info, tmp_path):
    request_path, request = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    result = run(request_path, output)
    assert result.returncode == 0, result.stderr
    jsonschema.validate(request, json.loads((SCHEMAS / "qmc-request.schema.json").read_text()))
    p = pointer(output)
    assert set(p) == {"schema_version", "anchor_sha256", "generation_sha256", "path"}
    assert p["schema_version"] == "qmc-current-generation-v2"
    m = manifest(output)
    jsonschema.validate(
        m, json.loads((SCHEMAS / "qmc-checkpoint-generation.schema.json").read_text())
    )
    assert m["anchor_sha256"] == p["anchor_sha256"]
    schema = json.loads((SCHEMAS / "qmc-ltfim-bin.schema.json").read_text())
    for record in records(output):
        jsonschema.validate(record, schema)
        assert record["adapter"] == "QMC_LTFIM"
        assert record["seed_namespace"].startswith("QMC_LTFIM:")
        assert "binder" not in record
        assert 0 < record["cluster_accepted_count"] <= record["cluster_attempt_count"]
        assert record["cluster_attempt_count"] == record["cluster_count_sum"]
        assert record["cluster_size_observation_count"] == record["cluster_count_sum"]
        assert record["cluster_list_size_observation_count"] == record["sweep_count"]


@pytest.mark.parametrize(
    ("mutation", "word"),
    [
        (lambda r: r.update(adapter="QMC_SSE"), "adapter"),
        (lambda r: r.update(expected_source_hash="0" * 64), "source"),
        (lambda r: r.update(expected_build_hash="0" * 64), "build"),
        (lambda r: r.update(extra=True), "unknown"),
        (lambda r: r.update(retained_samples=3, bin_length=2), "divisible"),
    ],
)
def test_request_rejections_precede_model_construction(build_info, tmp_path, mutation, word):
    request_path, request = make_request(tmp_path / "fixture", build_info)
    mutation(request)
    request_path.write_bytes(canonical_bytes(request))
    output = tmp_path / "run"
    result = run(request_path, output)
    assert result.returncode != 0
    assert word in result.stderr.lower()
    assert not (output / "bins").exists()


@pytest.mark.parametrize(
    "damage",
    ["order", "bounds", "self-loop", "duplicate", "disconnect", "site-count", "bond-count", "degree"],
)
def test_graph_contract_fails_closed(build_info, tmp_path, damage):
    request_path, request = make_request(tmp_path / "fixture", build_info)
    graph_path = Path(request["graph_path"])
    graph = json.loads(graph_path.read_text())
    if damage == "order":
        graph["bonds"] = list(reversed(graph["bonds"]))
    elif damage == "bounds":
        graph["bonds"][0] = [0, graph["site_count"]]
    elif damage == "self-loop":
        graph["bonds"][0] = [0, 0]
    elif damage == "duplicate":
        graph["bonds"][1] = graph["bonds"][0]
    elif damage == "disconnect":
        graph["bonds"] = [b for b in graph["bonds"] if 0 not in b]
    elif damage == "site-count":
        graph["site_count"] += 1
    elif damage == "bond-count":
        graph["bonds"].pop()
    else:
        graph["bonds"] = graph["bonds"][1:] + [[0, 2]]
        graph["bonds"].sort()
    unhashed = {key: value for key, value in graph.items() if key != "sha256"}
    graph["sha256"] = hashlib.sha256(
        json.dumps(unhashed, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    graph_path.write_bytes(canonical_bytes(graph))
    request["graph_sha256"] = graph["sha256"]
    request_path.write_bytes(canonical_bytes(request))
    result = run(request_path, tmp_path / "run")
    assert result.returncode != 0
    assert "graph" in result.stderr.lower()


def test_graph_topology_drift_with_preserved_degree_fails_closed(build_info, tmp_path):
    request_path, request = make_request(tmp_path / "fixture", build_info)
    graph_path = Path(request["graph_path"])
    graph = json.loads(graph_path.read_text())
    bonds = {tuple(edge) for edge in graph["bonds"]}
    replacement = None
    for left in bonds:
        for right in bonds:
            if len(set(left + right)) != 4:
                continue
            candidate = {
                tuple(sorted((left[0], right[0]))),
                tuple(sorted((left[1], right[1]))),
            }
            if len(candidate) == 2 and not candidate & bonds:
                replacement = (left, right, candidate)
                break
        if replacement is not None:
            break
    assert replacement is not None
    left, right, candidate = replacement
    bonds.remove(left)
    bonds.remove(right)
    bonds.update(candidate)
    graph["bonds"] = [list(edge) for edge in sorted(bonds)]
    unhashed = {key: value for key, value in graph.items() if key != "sha256"}
    graph["sha256"] = hashlib.sha256(
        json.dumps(unhashed, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    graph_path.write_bytes(canonical_bytes(graph))
    request["graph_sha256"] = graph["sha256"]
    request_path.write_bytes(canonical_bytes(request))
    result = run(request_path, tmp_path / "run")
    assert result.returncode != 0
    assert "topology" in result.stderr.lower()


def test_embedded_graph_hash_drift_fails_closed(build_info, tmp_path):
    request, value = make_request(tmp_path / "fixture", build_info)
    graph_path = Path(value["graph_path"])
    graph = json.loads(graph_path.read_text())
    graph["sha256"] = "0" * 64
    graph_path.write_bytes(canonical_bytes(graph))
    result = run(request, tmp_path / "run")
    assert result.returncode != 0
    assert "embedded sha256 mismatch" in result.stderr.lower()


def test_request_graph_hash_drift_fails_closed(build_info, tmp_path):
    request, value = make_request(tmp_path / "fixture", build_info)
    value["graph_sha256"] = "0" * 64
    request.write_bytes(canonical_bytes(value))
    result = run(request, tmp_path / "run")
    assert result.returncode != 0
    assert "requested sha256 mismatch" in result.stderr.lower()


def test_determinism_seed_separation_and_replay(build_info, tmp_path):
    outputs = []
    for name, seed in [("a", 91), ("b", 91), ("c", 92)]:
        request, _ = make_request(tmp_path / name, build_info, seed=seed)
        output = tmp_path / name / "run"
        result = run(request, output)
        assert result.returncode == 0, result.stderr
        outputs.append(output)
    bytes_a = [(outputs[0] / "bins" / f"{h}.ndjson").read_bytes() for h in manifest(outputs[0])["bin_object_hashes"]]
    bytes_b = [(outputs[1] / "bins" / f"{h}.ndjson").read_bytes() for h in manifest(outputs[1])["bin_object_hashes"]]
    bytes_c = [(outputs[2] / "bins" / f"{h}.ndjson").read_bytes() for h in manifest(outputs[2])["bin_object_hashes"]]
    assert bytes_a == bytes_b
    assert bytes_a != bytes_c
    assert records(outputs[0])[0]["seed_derivation"] != "sha256:qmc-sse-seed-v1||u64be"
    before = (outputs[0] / "current-generation.json").read_bytes()
    rerun = run(tmp_path / "a" / "request.json", outputs[0])
    assert rerun.returncode == 0, rerun.stderr
    assert (outputs[0] / "current-generation.json").read_bytes() == before


@pytest.mark.parametrize("point", ["after-bin-rename", "after-generation-rename", "before-pointer-replace"])
def test_crash_and_recovery_is_replay_equivalent(build_info, tmp_path, point):
    clean_request, _ = make_request(tmp_path / "clean", build_info, retained_samples=4)
    crash_request, _ = make_request(tmp_path / "crash", build_info, retained_samples=4)
    clean = tmp_path / "clean" / "run"
    interrupted = tmp_path / "crash" / "run"
    assert run(clean_request, clean).returncode == 0
    failed = run(
        crash_request,
        interrupted,
        env={"QMC_LTFIM_FAILPOINT": point, "QMC_LTFIM_FAILPOINT_OCCURRENCE": "1"},
    )
    assert failed.returncode != 0
    recovered = run(crash_request, interrupted)
    assert recovered.returncode == 0, recovered.stderr
    assert [r for r in records(clean)] == [r for r in records(interrupted)]


def test_abrupt_first_generation_crash_is_adopted_with_wide_interval(build_info, tmp_path):
    request, _ = make_request(
        tmp_path / "fixture",
        build_info,
        retained_samples=6,
        bin_length=1,
        checkpoint_bins=3,
    )
    output = tmp_path / "run"
    crashed = run(
        request,
        output,
        env={"QMC_LTFIM_CRASHPOINT": "after-generation-rename"},
    )
    assert crashed.returncode == 86
    assert not (output / "current-generation.json").exists()
    recovered = run(request, output)
    assert recovered.returncode == 0, recovered.stderr
    assert [value["completed_bin_count"] for _, value in generation_chain(output)] == [3, 6]


def test_orphan_adoption_and_archive(build_info, tmp_path):
    request, _ = make_request(
        tmp_path / "fixture", build_info, retained_samples=4, bin_length=1, checkpoint_bins=2
    )
    output = tmp_path / "run"
    crashed = run(
        request,
        output,
        env={"QMC_LTFIM_CRASHPOINT": "after-bin-rename"},
    )
    assert crashed.returncode == 86
    orphan_payload = b"not-json\n"
    orphan_hash = hashlib.sha256(orphan_payload).hexdigest()
    orphan = output / "bins" / f"{orphan_hash}.ndjson"
    orphan.write_bytes(orphan_payload)
    recovered = run(request, output)
    assert recovered.returncode == 0, recovered.stderr
    assert not orphan.exists()
    assert any("orphan" in path.name for path in (output / "archive").iterdir())
    assert len(retained_bin_bytes(output)) == 4


def test_stale_pointer_advances_unique_contiguous_descendant(build_info, tmp_path):
    request, _ = make_request(
        tmp_path / "fixture", build_info, retained_samples=4, bin_length=1, checkpoint_bins=1
    )
    output = tmp_path / "run"
    crashed = run(
        request,
        output,
        env={
            "QMC_LTFIM_FAILPOINT": "after-generation-rename",
            "QMC_LTFIM_FAILPOINT_OCCURRENCE": "2",
        },
    )
    assert crashed.returncode != 0
    stale = pointer(output)["generation_sha256"]
    recovered = run(request, output)
    assert recovered.returncode == 0, recovered.stderr
    assert pointer(output)["generation_sha256"] != stale
    assert len(generation_chain(output)) == 4


@pytest.mark.parametrize("conflict", ["branch", "ancestry-gap", "multiple-genesis"])
def test_generation_conflicts_fail_closed(build_info, tmp_path, conflict):
    request, _ = make_request(
        tmp_path / "fixture", build_info, retained_samples=4, bin_length=1, checkpoint_bins=2
    )
    output = tmp_path / "run"
    assert run(request, output).returncode == 0
    chain = generation_chain(output)
    if conflict == "branch":
        altered = dict(chain[1][1])
        altered["replay_update_count"] += 1
    elif conflict == "ancestry-gap":
        altered = dict(chain[-1][1])
        altered["previous_generation_sha256"] = "0" * 64
    else:
        altered = dict(chain[0][1])
        altered["replay_update_count"] += 1
        (output / "current-generation.json").unlink()
    publish_generation(output, altered)
    result = run(request, output)
    assert result.returncode != 0
    assert any(
        word in result.stderr.lower()
        for word in (
            "conflict",
            "gap",
            "ancestry",
            "genesis",
            "unlinked",
            "malformed",
            "replay",
        )
    ), result.stderr


def test_every_fsync_crash_boundary_recovers_to_valid_output(build_info, tmp_path):
    request, _ = make_request(
        tmp_path / "fixture",
        build_info,
        retained_samples=1,
        bin_length=1,
        checkpoint_bins=1,
        thermalization_sweeps=0,
    )
    failures = 0
    for boundary in range(1, 40):
        output = tmp_path / f"run-{boundary}"
        failed = run(
            request,
            output,
            env={"QMC_LTFIM_CRASH_FSYNC_AT": str(boundary)},
        )
        if failed.returncode == 0:
            break
        assert failed.returncode == 86
        failures += 1
        recovered = run(request, output)
        assert recovered.returncode == 0, (boundary, recovered.stderr)
    assert failures >= 8
    assert boundary < 39


def test_concurrent_runs_serialize_and_converge(build_info, tmp_path):
    request, _ = make_request(
        tmp_path / "fixture", build_info, retained_samples=2, bin_length=1, checkpoint_bins=1
    )
    output = tmp_path / "run"
    command = [
        JULIA,
        f"--project={ADAPTER}",
        str(RUNNER),
        "--request",
        str(request),
        "--output-directory",
        str(output),
    ]
    processes = [
        subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(2)
    ]
    results = [process.communicate(timeout=120) for process in processes]
    assert [process.returncode for process in processes] == [0, 0], results
    assert len(generation_chain(output)) == 2
    assert len(list((output / "generations").glob("*"))) == 2


@pytest.mark.parametrize("kind", ["bin", "missing-bin", "generation", "anchor", "v1"])
def test_corruption_and_v1_fail_closed(build_info, tmp_path, kind):
    request, _ = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    assert run(request, output).returncode == 0
    if kind in {"bin", "missing-bin"}:
        digest = manifest(output)["bin_object_hashes"][0]
        path = output / "bins" / f"{digest}.ndjson"
        if kind == "bin":
            path.write_text("{}\n")
        else:
            path.unlink()
    elif kind == "generation":
        digest = pointer(output)["generation_sha256"]
        (output / "generations" / digest / "manifest.json").write_text("{}\n")
    elif kind == "anchor":
        p = output / "run-lock-anchor.json"
        value = json.loads(p.read_text())
        value["anchor_sha256"] = "0" * 64
        p.write_bytes(canonical_bytes(value))
    else:
        p = output / "current-generation.json"
        value = json.loads(p.read_text())
        value["schema_version"] = "qmc-current-generation-v1"
        p.write_bytes(canonical_bytes(value))
    result = run(request, output)
    assert result.returncode != 0


def test_short_final_checkpoint_interval_and_replay_count(build_info, tmp_path):
    request, value = make_request(
        tmp_path / "fixture",
        build_info,
        retained_samples=6,
        bin_length=2,
        checkpoint_bins=2,
        thermalization_sweeps=3,
        thinning=2,
    )
    output = tmp_path / "run"
    result = run(request, output)
    assert result.returncode == 0, result.stderr
    chain = generation_chain(output)
    assert [item["completed_bin_count"] for _, item in chain] == [2, 3]
    assert [item["replay_update_count"] for _, item in chain] == [
        value["thermalization_sweeps"] + 4 * value["thinning"],
        value["thermalization_sweeps"] + 6 * value["thinning"],
    ]
    assert chain[0][1]["previous_generation_sha256"] is None
    assert chain[1][1]["previous_generation_sha256"] == chain[0][0]


def test_bin_no_overwrite_preserves_different_existing_bytes(build_info, tmp_path):
    request, _ = make_request(
        tmp_path / "fixture", build_info, retained_samples=1, bin_length=1
    )
    clean = tmp_path / "clean"
    assert run(request, clean).returncode == 0
    digest = manifest(clean)["bin_object_hashes"][0]
    output = tmp_path / "run"
    bins = output / "bins"
    bins.mkdir(parents=True)
    planted = bins / f"{digest}.ndjson"
    planted.write_bytes(b"different\n")
    result = run(request, output)
    assert result.returncode != 0
    assert planted.read_bytes() == b"different\n"
    assert "differs" in result.stderr.lower()


@pytest.mark.parametrize("entry", ["bins", "generations", "archive"])
def test_symlinked_critical_directory_fails_closed(build_info, tmp_path, entry):
    request, _ = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    assert run(request, output).returncode == 0
    target = output / entry
    if not target.exists():
        target.mkdir()
    moved = output / f"{entry}-moved"
    target.rename(moved)
    target.symlink_to(moved, target_is_directory=True)
    result = run(request, output)
    assert result.returncode != 0
    assert not any(path.name.startswith(".tmp-") for path in moved.iterdir())


@pytest.mark.parametrize("ancestor_index", [0, 1, 2])
def test_replacing_output_ancestor_during_bin_publication_fails_closed(
    build_info, tmp_path, ancestor_index
):
    ancestors = [
        tmp_path / "ancestor-0",
        tmp_path / "ancestor-0" / "ancestor-1",
        tmp_path / "ancestor-0" / "ancestor-1" / "ancestor-2",
    ]
    output = ancestors[-1] / "run"
    ancestors[-1].mkdir(parents=True)
    request, _ = make_request(tmp_path / "fixture", build_info)
    process, release = start_paused(request, output, tmp_path, "before-bin-rename")
    victim = ancestors[ancestor_index]
    moved = victim.with_name(victim.name + "-moved")
    victim.rename(moved)
    victim.mkdir()
    result = finish_paused(process, release)
    assert result.returncode != 0
    assert not (output / "current-generation.json").exists()


def test_replacing_bins_during_publication_fails_closed(build_info, tmp_path):
    request, _ = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    process, release = start_paused(request, output, tmp_path, "before-bin-rename")
    bins = output / "bins"
    moved = output / "bins-moved"
    bins.rename(moved)
    bins.mkdir()
    result = finish_paused(process, release)
    assert result.returncode != 0
    assert not list(bins.glob("*.ndjson"))


def test_replacing_bins_during_generation_publication_fails_closed(build_info, tmp_path):
    request, _ = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    process, release = start_paused(
        request, output, tmp_path, "before-generation-rename"
    )
    bins = output / "bins"
    moved = output / "bins-moved"
    bins.rename(moved)
    bins.mkdir()
    result = finish_paused(process, release)
    assert result.returncode != 0
    assert not list(bins.iterdir())
    assert not (output / "current-generation.json").exists()


def test_replacing_generations_during_publication_fails_closed(build_info, tmp_path):
    request, _ = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    process, release = start_paused(
        request, output, tmp_path, "before-generation-rename"
    )
    generations = output / "generations"
    moved = output / "generations-moved"
    generations.rename(moved)
    generations.mkdir()
    result = finish_paused(process, release)
    assert result.returncode != 0
    assert not list(generations.iterdir())
    assert not (output / "current-generation.json").exists()


def test_replacing_archive_during_recovery_archive_fails_closed(build_info, tmp_path):
    request, _ = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    assert run(request, output).returncode == 0
    unexpected = output / "generations" / "unexpected"
    unexpected.write_text("malicious")
    process, release = start_paused(
        request, output, tmp_path, "before-archive-rename"
    )
    archive = output / "archive"
    moved = output / "archive-moved"
    archive.rename(moved)
    archive.mkdir()
    result = finish_paused(process, release)
    assert result.returncode != 0
    assert not list(archive.iterdir())
    assert unexpected.exists()


def test_pointer_staging_replacement_fails_closed(build_info, tmp_path):
    request, _ = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    process, release = start_paused(
        request, output, tmp_path, "before-pointer-replace"
    )
    staged = list(output.glob(".tmp-current-generation-*"))
    assert len(staged) == 1
    staged[0].unlink()
    outside = tmp_path / "outside-pointer"
    outside.write_text("outside")
    staged[0].symlink_to(outside)
    result = finish_paused(process, release)
    assert result.returncode != 0
    assert outside.read_text() == "outside"
    assert not (output / "current-generation.json").is_symlink()


def test_replacing_output_at_pointer_publication_fails_closed(build_info, tmp_path):
    request, _ = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    process, release = start_paused(
        request, output, tmp_path, "before-pointer-replace"
    )
    moved = tmp_path / "run-moved"
    output.rename(moved)
    output.mkdir()
    result = finish_paused(process, release)
    assert result.returncode != 0
    assert not list(output.iterdir())


@pytest.mark.parametrize("entry", ["bins", "generations"])
def test_replacement_after_pointer_rename_fails_and_next_run_rejects(
    build_info, tmp_path, entry
):
    request, _ = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    process, release = start_paused(
        request,
        output,
        tmp_path,
        "after-pointer-replace-before-validation",
    )
    target = output / entry
    moved = output / f"{entry}-moved"
    target.rename(moved)
    target.mkdir()
    result = finish_paused(process, release)
    assert result.returncode != 0
    assert not list(target.iterdir())
    assert (output / "current-generation.json").is_file()
    diagnostics = output / "publication-failures"
    assert any(path.suffix == ".json" for path in diagnostics.iterdir())

    recovered = run(request, output)
    assert recovered.returncode != 0
    assert not list(target.iterdir())


@pytest.mark.parametrize("entry", ["generations", "bins"])
def test_replacement_at_recovery_adoption_fails_closed(build_info, tmp_path, entry):
    request, _ = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    assert run(request, output).returncode == 0
    (output / "current-generation.json").unlink()
    process, release = start_paused(request, output, tmp_path, "after-recovery-scan")
    target = output / entry
    moved = output / f"{entry}-moved"
    target.rename(moved)
    target.mkdir()
    result = finish_paused(process, release)
    assert result.returncode != 0
    assert not list(target.iterdir())
    assert not (output / "current-generation.json").exists()


@pytest.mark.parametrize("target", ["state", "anchor"])
def test_replacing_lock_anchor_inode_during_publication_fails_closed(
    build_info, tmp_path, target
):
    request, _ = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    process, release = start_paused(request, output, tmp_path, "before-bin-rename")
    if target == "state":
        state = output / ".qmc-ltfim-lock-state"
        state.rename(output / ".qmc-ltfim-lock-state-moved")
        state.mkdir()
        (state / ".qmc-ltfim.lock").touch()
    else:
        selection = json.loads((output / "run-lock-anchor.json").read_text())
        anchor = output / selection["path"]
        replacement = anchor.with_suffix(".replacement")
        replacement.write_bytes(anchor.read_bytes())
        replacement.replace(anchor)
    result = finish_paused(process, release)
    assert result.returncode != 0


def test_canonical_anchor_substitution_across_restart_fails_closed(
    build_info, tmp_path
):
    request, _ = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    assert run(request, output).returncode == 0
    selection = json.loads((output / "run-lock-anchor.json").read_text())
    anchor = output / selection["path"]
    pin = anchor.with_suffix(".pin")
    original_bytes = anchor.read_bytes()
    original_inode = anchor.stat().st_ino
    assert pin.read_bytes() == original_bytes
    assert pin.stat().st_ino == original_inode

    anchor.unlink()
    anchor.write_bytes(original_bytes)
    assert anchor.stat().st_ino != original_inode
    rejected = run(request, output)
    assert rejected.returncode != 0
    assert "anchor" in rejected.stderr.lower()
    assert pin.stat().st_ino == original_inode


def test_pointerless_corrupt_genesis_is_archived_and_fails_closed(build_info, tmp_path):
    request, _ = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    assert run(request, output).returncode == 0
    (output / "current-generation.json").unlink()
    generation = next((output / "generations").iterdir())
    (generation / "manifest.json").write_text("{corrupt")
    result = run(request, output)
    assert result.returncode != 0
    assert not generation.exists()
    assert any("invalid-generation" in path.name for path in (output / "archive").iterdir())


@pytest.mark.parametrize("name", ["junk", "A" * 64, ".tmp-not-a-generation"])
def test_unexpected_generation_entry_is_archived_and_fails_closed(
    build_info, tmp_path, name
):
    request, _ = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    assert run(request, output).returncode == 0
    unexpected = output / "generations" / name
    unexpected.write_text("unexpected")
    result = run(request, output)
    assert result.returncode != 0
    assert not unexpected.exists()
    assert any(
        "unexpected-generation-entry" in path.name
        for path in (output / "archive").iterdir()
    )


def test_generation_directory_exact_shape_is_enforced(build_info, tmp_path):
    request, _ = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    assert run(request, output).returncode == 0
    generation = output / "generations" / pointer(output)["generation_sha256"]
    (generation / "extra").write_text("unexpected")
    result = run(request, output)
    assert result.returncode != 0
    assert not generation.exists()
    assert any("invalid-generation" in path.name for path in (output / "archive").iterdir())


def test_thinning_diagnostics_share_every_update_domain(build_info, tmp_path):
    request_path, request = make_request(
        tmp_path / "fixture",
        build_info,
        retained_samples=4,
        bin_length=2,
        thinning=3,
    )
    output = tmp_path / "run"
    result = run(request_path, output)
    assert result.returncode == 0, result.stderr
    for record in records(output):
        expected_updates = record["sample_count"] * request["thinning"]
        assert record["sweep_count"] == expected_updates
        assert record["cluster_list_size_observation_count"] == expected_updates
        assert record["cluster_attempt_count"] == record["cluster_count_sum"]
        assert record["cluster_size_observation_count"] == record["cluster_count_sum"]
        assert 0 <= record["cluster_accepted_count"] <= record["cluster_attempt_count"]


def test_same_manifest_collision_archives_staging_loser(build_info, tmp_path):
    request, _ = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    process, release = start_paused(
        request, output, tmp_path, "before-generation-rename"
    )
    stages = list((output / "generations").glob(".tmp-generation-*"))
    assert len(stages) == 1
    payload = (stages[0] / "manifest.json").read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    winner = output / "generations" / digest
    winner.mkdir()
    (winner / "manifest.json").write_bytes(payload)
    result = finish_paused(process, release)
    assert result.returncode == 0, result.stderr
    assert digest in {generation for generation, _ in generation_chain(output)}
    assert any(
        "identical-generation-loser" in path.name
        for path in (output / "archive").iterdir()
    )


def test_noncanonical_pointerless_generation_fails_closed(build_info, tmp_path):
    request, _ = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    assert run(request, output).returncode == 0
    current = pointer(output)["generation_sha256"]
    generation = output / "generations" / current
    value = json.loads((generation / "manifest.json").read_text())
    payload = json.dumps(value, indent=2, sort_keys=True).encode() + b"\n"
    replacement_hash = hashlib.sha256(payload).hexdigest()
    replacement = output / "generations" / replacement_hash
    generation.rename(replacement)
    (replacement / "manifest.json").write_bytes(payload)
    (output / "current-generation.json").unlink()
    result = run(request, output)
    assert result.returncode != 0
    assert not replacement.exists()


def test_bin_cross_field_corruption_fails_closed(build_info, tmp_path):
    request, _ = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    assert run(request, output).returncode == 0
    old_manifest = manifest(output)
    old_bin_hash = old_manifest["bin_object_hashes"][0]
    record = json.loads((output / "bins" / f"{old_bin_hash}.ndjson").read_text())
    record["cluster_accepted_count"] = record["cluster_attempt_count"] + 1
    bin_payload = canonical_bytes(record)
    bin_hash = hashlib.sha256(bin_payload).hexdigest()
    (output / "bins" / f"{bin_hash}.ndjson").write_bytes(bin_payload)
    bad_manifest = dict(old_manifest)
    bad_manifest["bin_object_hashes"] = [bin_hash, *old_manifest["bin_object_hashes"][1:]]
    bad_manifest["previous_generation_sha256"] = None
    shutil.rmtree(output / "generations")
    (output / "generations").mkdir()
    publish_generation(output, bad_manifest)
    (output / "current-generation.json").unlink()
    result = run(request, output)
    assert result.returncode != 0


def julia_fd_delta(
    request: Path, output: Path, *, attempts: int, env=None
) -> subprocess.CompletedProcess[str]:
    script = """
using Challenge148LTFIM
before = length(readdir("/proc/self/fd"))
for _ in 1:parse(Int, ARGS[3])
    try
        Challenge148LTFIM.run_request(ARGS[1], ARGS[2])
    catch
    end
end
after = length(readdir("/proc/self/fd"))
println(after - before)
"""
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    return subprocess.run(
        [
            JULIA,
            f"--project={ADAPTER}",
            "-e",
            script,
            str(request),
            str(output),
            str(attempts),
        ],
        text=True,
        capture_output=True,
        env=process_env,
        timeout=180,
    )


def test_many_bin_replays_keep_file_descriptors_bounded(build_info, tmp_path):
    request, _ = make_request(
        tmp_path / "fixture",
        build_info,
        retained_samples=20,
        bin_length=1,
        checkpoint_bins=5,
        thermalization_sweeps=0,
    )
    result = julia_fd_delta(request, tmp_path / "run", attempts=8)
    assert result.returncode == 0, result.stderr
    assert int(result.stdout.strip()) <= 4


def test_repeated_failure_paths_leak_no_file_descriptors(build_info, tmp_path):
    request, _ = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    assert run(request, output).returncode == 0
    (output / "current-generation.json").write_text("{corrupt")
    result = julia_fd_delta(request, output, attempts=20)
    assert result.returncode == 0, result.stderr
    assert int(result.stdout.strip()) <= 2


def test_post_pointer_validation_failure_leaks_no_descriptors(build_info, tmp_path):
    request, _ = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    result = julia_fd_delta(
        request,
        output,
        attempts=1,
        env={
            "QMC_LTFIM_FAILPOINT": "after-pointer-replace-before-validation",
        },
    )
    assert result.returncode == 0, result.stderr
    assert int(result.stdout.strip()) <= 2
    assert (output / "current-generation.json").is_file()
    assert list((output / "publication-failures").glob("*.json"))


def test_p_zero_line_route_exposes_pinned_bounds_defect_safely(build_info):
    script = """
using Challenge148LTFIM, QMC
C = Challenge148LTFIM
H = C.build_model(8, C.honeycomb_reference_bonds(2), 1.0, 1.2)
state = QMC.BinaryThermalState(H, 64)
diagnostics = QMC.Diagnostics(QMC.RunStats(), QMC.NoTransitionMatrix())
rng = C.rng_from_seed(148_700)
for _ in 1:100
    QMC.mc_step_beta!((args...) -> nothing, rng, state, H, 0.75, diagnostics; eq=true, p=0.0)
end
"""
    result = subprocess.run(
        [
            JULIA,
            "--check-bounds=yes",
            f"--project={ADAPTER}",
            "-e",
            script,
        ],
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode != 0
    assert "boundserror" in result.stderr.lower() or "index [0]" in result.stderr.lower()


@pytest.mark.parametrize("graph", [honeycomb_graph(2), triangular_graph(3)])
def test_all_five_observables_agree_with_exact_thermal_ed(build_info, tmp_path, graph):
    beta, coupling, field = 0.6, 1.0, 1.4
    request, _ = make_request(
        tmp_path / graph.lattice,
        build_info,
        graph=graph,
        beta=beta,
        coupling=coupling,
        field=field,
        thermalization_sweeps=2_000,
        retained_samples=8_000,
        bin_length=200,
        checkpoint_bins=40,
    )
    output = tmp_path / graph.lattice / "run"
    result = run(request, output, timeout=300)
    assert result.returncode == 0, result.stderr
    bins = records(output)
    count = sum(b["sample_count"] for b in bins)
    means = {
        "energy": sum(b["energy_sum"] for b in bins) / count,
        "transverse_magnetization": sum(b["transverse_magnetization_sum"] for b in bins) / count,
        "m2": sum(b["m2_sum"] for b in bins) / count,
        "m4": sum(b["m4_sum"] for b in bins) / count,
    }
    means["binder_ratio"] = means["m2"] ** 2 / means["m4"]
    exact = exact_thermal_observables(
        graph, coupling=coupling, field=field, beta=beta
    )
    targets = {
        "energy": exact.energy,
        "transverse_magnetization": exact.transverse_magnetization,
        "m2": exact.m2,
        "m4": exact.m4,
        "binder_ratio": exact.binder_ratio,
    }
    standard_errors = {}
    for key in ("energy", "transverse_magnetization", "m2", "m4"):
        bin_means = np.asarray([item[f"{key}_sum"] / item["sample_count"] for item in bins])
        standard_errors[key] = bin_means.std(ddof=1) / np.sqrt(len(bin_means))
    m2_bins = np.asarray([item["m2_sum"] for item in bins])
    m4_bins = np.asarray([item["m4_sum"] for item in bins])
    n_bins = len(bins)
    binder_jackknife = np.asarray(
        [
            ((m2_bins.sum() - m2_bins[i]) / ((n_bins - 1) * bins[i]["sample_count"])) ** 2
            / ((m4_bins.sum() - m4_bins[i]) / ((n_bins - 1) * bins[i]["sample_count"]))
            for i in range(n_bins)
        ]
    )
    standard_errors["binder_ratio"] = np.sqrt(
        (n_bins - 1) * np.mean((binder_jackknife - binder_jackknife.mean()) ** 2)
    )
    for key in targets:
        residual = abs(means[key] - targets[key])
        assert residual <= 4 * standard_errors[key], (
            key,
            means[key],
            targets[key],
            standard_errors[key],
        )
