from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import time
from pathlib import Path

import jsonschema
import numpy as np
import pytest

from challenge148.ed import exact_thermal_observables
from challenge148.lattice import (
    honeycomb_graph,
    triangular_graph,
    write_graph_json,
)


SOLUTION_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_ROOT = SOLUTION_ROOT / "adapters" / "qmc-sse"
MANIFEST = ADAPTER_ROOT / "Cargo.toml"
EXECUTABLE = ADAPTER_ROOT / "target" / "build" / "debug" / "qmc-sse"
SCHEMAS = SOLUTION_ROOT / "schemas"


def cargo_executable() -> str:
    configured = os.environ.get("CARGO")
    if configured:
        return configured
    discovered = shutil.which("cargo")
    if discovered:
        return discovered
    fallback = Path.home() / ".cargo" / "bin" / "cargo"
    if fallback.is_file():
        return str(fallback)
    raise RuntimeError("cargo executable was not found")


def rust_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["CARGO_HOME"] = str(ADAPTER_ROOT / "target" / "cargo-home")
    environment["CARGO_TARGET_DIR"] = str(ADAPTER_ROOT / "target" / "build")
    environment.setdefault("RUSTUP_DIST_SERVER", "https://rsproxy.cn")
    environment.setdefault("RUSTUP_UPDATE_ROOT", "https://rsproxy.cn/rustup")
    return environment


def test_qmc_sse_cli_project_builds():
    completed = subprocess.run(
        [cargo_executable(), "build", "--locked", "--manifest-path", str(MANIFEST)],
        check=False,
        capture_output=True,
        env=rust_environment(),
        text=True,
        timeout=180,
    )

    assert completed.returncode == 0, completed.stderr


def test_qmc_sse_binary_does_not_require_modern_renameat2_glibc_symbol(qmc_sse):
    readelf = shutil.which("readelf")
    assert readelf is not None, "readelf from binutils is required for the portability check"
    completed = subprocess.run(
        [readelf, "--dyn-syms", "--wide", str(qmc_sse)],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    required_symbols = [
        line
        for line in completed.stdout.splitlines()
        if " GLOBAL " in f" {line} " and " UND " in f" {line} "
    ]

    assert all("renameat2" not in line for line in required_symbols), required_symbols
    assert all("GLIBC_2.28" not in line for line in required_symbols), required_symbols


@pytest.fixture(scope="session")
def qmc_sse() -> Path:
    completed = subprocess.run(
        [cargo_executable(), "build", "--locked", "--manifest-path", str(MANIFEST)],
        check=False,
        capture_output=True,
        env=rust_environment(),
        text=True,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stderr
    assert EXECUTABLE.is_file()
    return EXECUTABLE


@pytest.fixture(scope="session")
def build_info(qmc_sse: Path) -> dict[str, object]:
    completed = subprocess.run(
        [str(qmc_sse), "--build-info"],
        check=True,
        capture_output=True,
        env=rust_environment(),
        text=True,
        timeout=10,
    )
    value = json.loads(completed.stdout)
    assert set(value) == {
        "adapter",
        "build_hash",
        "codegen_units",
        "compiler",
        "encoded_rustflags",
        "features",
        "lto",
        "panic",
        "profile",
        "qmc_revision",
        "rng",
        "source_hash",
        "seed_derivation",
        "sweep_semantics",
        "target",
    }
    assert value["adapter"] == "QMC_SSE"
    assert value["qmc_revision"] == "35f100af856f3273cc67d31962f3e67f801b0c37"
    assert value["sweep_semantics"] == (
        "one diagonal update followed by cluster_attempts_per_sweep=N "
        "cluster-update attempts; QMC_SSE does not expose cluster size"
    )
    assert len(value["build_hash"]) == 64
    assert len(value["source_hash"]) == 64
    return value


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()


def make_request(
    tmp_path: Path,
    build_info: dict[str, object],
    *,
    seed: int = 148_001,
    retained_samples: int = 8,
    bin_length: int = 2,
    checkpoint_bins: int = 2,
    thermalization_sweeps: int = 8,
    thinning: int = 1,
    beta: float = 0.75,
    coupling: float = 1.0,
    field: float = 1.2,
    lattice: str = "honeycomb",
) -> tuple[Path, dict[str, object]]:
    graph = honeycomb_graph(2) if lattice == "honeycomb" else triangular_graph(3)
    graph_path = tmp_path / "graph.json"
    tmp_path.mkdir(parents=True, exist_ok=True)
    write_graph_json(graph, graph_path)
    graph_payload = json.loads(graph_path.read_text())
    request = {
        "adapter": "QMC_SSE",
        "beta": beta,
        "bin_length": bin_length,
        "checkpoint_bins": checkpoint_bins,
        "coupling": coupling,
        "expected_build_hash": build_info["build_hash"],
        "expected_source_hash": build_info["source_hash"],
        "field": field,
        "graph_path": str(graph_path),
        "graph_sha256": graph_payload["sha256"],
        "retained_samples": retained_samples,
        "schema_version": "qmc-request-v1",
        "seed": seed,
        "serial_measurement_stride_samples": 1,
        "thermalization_sweeps": thermalization_sweeps,
        "thinning": thinning,
    }
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n")
    return request_path, request


def run_adapter(
    qmc_sse: Path,
    request_path: Path,
    output: Path,
    *,
    extra_env: dict[str, str] | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    environment = rust_environment()
    if extra_env:
        environment.update(extra_env)
    return subprocess.run(
        [str(qmc_sse), "--request", str(request_path), "--output-directory", str(output)],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
        timeout=timeout,
    )


def run_adapter_fds(
    qmc_sse: Path,
    request_path: Path,
    output: Path,
    *,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    output.mkdir(parents=True, exist_ok=True)
    request_fd = os.open(request_path, os.O_RDONLY | os.O_NOFOLLOW)
    output_fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        return subprocess.run(
            [
                str(qmc_sse),
                "--request-fd",
                str(request_fd),
                "--output-directory-fd",
                str(output_fd),
            ],
            check=False,
            capture_output=True,
            env=rust_environment(),
            pass_fds=(request_fd, output_fd),
            text=True,
            timeout=timeout,
        )
    finally:
        os.close(output_fd)
        os.close(request_fd)


def test_qmc_sse_inherited_fd_cli_is_native_and_backward_compatible(
    qmc_sse: Path, build_info: dict[str, object], tmp_path: Path
):
    request_path, _ = make_request(tmp_path / "fd-input", build_info)
    output = tmp_path / "fd-output"

    completed = run_adapter_fds(qmc_sse, request_path, output)

    assert completed.returncode == 0, completed.stderr
    assert (output / "current-generation.json").is_file()
    mixed = subprocess.run(
        [
            str(qmc_sse),
            "--request",
            str(request_path),
            "--output-directory",
            str(tmp_path / "path-output"),
            "--request-fd",
            "0",
            "--output-directory-fd",
            "1",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert mixed.returncode != 0


def start_adapter(
    qmc_sse: Path,
    request_path: Path,
    output: Path,
    *,
    extra_env: dict[str, str] | None = None,
) -> subprocess.Popen[str]:
    environment = rust_environment()
    if extra_env:
        environment.update(extra_env)
    return subprocess.Popen(
        [str(qmc_sse), "--request", str(request_path), "--output-directory", str(output)],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def wait_for_path(path: Path, process: subprocess.Popen[str], timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            pytest.fail(f"process exited before synchronization: {stdout=} {stderr=}")
        time.sleep(0.01)
    process.kill()
    pytest.fail(f"timed out waiting for {path}")


def pointer(output: Path) -> dict[str, object]:
    return json.loads((output / "current-generation.json").read_text())


def generation_chain(output: Path) -> list[tuple[str, dict[str, object]]]:
    current_hash = pointer(output)["generation_sha256"]
    reverse_chain = []
    while current_hash is not None:
        manifest_path = output / "generations" / current_hash / "manifest.json"
        payload = json.loads(manifest_path.read_text())
        reverse_chain.append((current_hash, payload))
        current_hash = payload["previous_generation_sha256"]
    return list(reversed(reverse_chain))


def retained_bin_bytes(output: Path) -> list[bytes]:
    manifest = generation_chain(output)[-1][1]
    return [(output / "bins" / f"{digest}.ndjson").read_bytes() for digest in manifest["bin_object_hashes"]]


def minimal_generation_manifest(adapter: str) -> dict[str, object]:
    return {
        "schema_version": "qmc-checkpoint-generation-v2",
        "anchor_sha256": "1" * 64,
        "request_sha256": "2" * 64,
        "adapter": adapter,
        "source_hash": "3" * 64,
        "build_hash": "4" * 64,
        "seed": 148,
        "completed_bin_count": 1,
        "bin_object_hashes": ["5" * 64],
        "previous_generation_sha256": None,
        "replay_update_count": 10,
    }


@pytest.mark.parametrize("adapter", ["QMC_SSE", "QMC_LTFIM"])
def test_shared_checkpoint_generation_v2_accepts_both_adapters(adapter):
    schema = json.loads((SCHEMAS / "qmc-checkpoint-generation.schema.json").read_text())
    jsonschema.validate(minimal_generation_manifest(adapter), schema)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda manifest: manifest.update(schema_version="qmc-checkpoint-generation-v1"),
        lambda manifest: manifest.pop("anchor_sha256"),
        lambda manifest: manifest.update(extra=True),
        lambda manifest: manifest.update(anchor_sha256="not-a-sha256"),
        lambda manifest: manifest.update(request_sha256="A" * 64),
        lambda manifest: manifest.update(adapter="QMC_UNKNOWN"),
    ],
)
def test_shared_checkpoint_generation_v2_rejects_invalid_contracts(mutation):
    schema = json.loads((SCHEMAS / "qmc-checkpoint-generation.schema.json").read_text())
    manifest = minimal_generation_manifest("QMC_SSE")
    mutation(manifest)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(manifest, schema)


def test_closed_schemas_validate_real_output(qmc_sse, build_info, tmp_path):
    request_path, request = make_request(tmp_path, build_info, retained_samples=5, bin_length=1)
    completed = run_adapter(qmc_sse, request_path, tmp_path / "run")
    assert completed.returncode == 0, completed.stderr

    request_schema = json.loads((SCHEMAS / "qmc-request.schema.json").read_text())
    generation_schema = json.loads((SCHEMAS / "qmc-checkpoint-generation.schema.json").read_text())
    bin_schema = json.loads((SCHEMAS / "qmc-sse-bin.schema.json").read_text())
    jsonschema.validate(request, request_schema)
    shared_ltfim_request = dict(request, adapter="QMC_LTFIM")
    jsonschema.validate(shared_ltfim_request, request_schema)

    chain = generation_chain(tmp_path / "run")
    assert [manifest["completed_bin_count"] for _, manifest in chain] == [2, 4, 5]
    for digest, manifest in chain:
        jsonschema.validate(manifest, generation_schema)
        manifest_bytes = canonical_bytes(manifest) + b"\n"
        assert hashlib.sha256(manifest_bytes).hexdigest() == digest
    for line in retained_bin_bytes(tmp_path / "run"):
        assert line.endswith(b"\n") and line.count(b"\n") == 1
        jsonschema.validate(json.loads(line), bin_schema)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda request: request.update(adapter="QMC_LTFIM"), "adapter"),
        (lambda request: request.update(expected_build_hash="0" * 64), "build"),
        (lambda request: request.update(expected_source_hash="0" * 64), "source"),
        (lambda request: request.update(retained_samples=3, bin_length=2), "divisible"),
        (lambda request: request.update(checkpoint_bins=0), "checkpoint"),
        (lambda request: request.update(extra=True), "unknown"),
    ],
)
def test_request_mismatches_fail_closed(qmc_sse, build_info, tmp_path, mutation, message):
    request_path, request = make_request(tmp_path, build_info)
    mutation(request)
    request_path.write_text(json.dumps(request))
    completed = run_adapter(qmc_sse, request_path, tmp_path / "run")
    assert completed.returncode != 0
    assert message in completed.stderr.lower()
    assert not (tmp_path / "run" / "bins").exists()


def test_non_finite_request_fails_closed(qmc_sse, build_info, tmp_path):
    request_path, _ = make_request(tmp_path, build_info)
    text = request_path.read_text().replace('"beta": 0.75', '"beta": NaN')
    request_path.write_text(text)
    completed = run_adapter(qmc_sse, request_path, tmp_path / "run")
    assert completed.returncode != 0
    assert "json" in completed.stderr.lower() or "finite" in completed.stderr.lower()


@pytest.mark.parametrize("damage", ["embedded", "requested", "topology"])
def test_graph_hash_and_topology_drift_fail_before_output(qmc_sse, build_info, tmp_path, damage):
    request_path, request = make_request(tmp_path, build_info)
    graph_path = Path(request["graph_path"])
    graph = json.loads(graph_path.read_text())
    if damage == "embedded":
        graph["sha256"] = "0" * 64
        graph_path.write_text(json.dumps(graph))
    elif damage == "requested":
        request["graph_sha256"] = "0" * 64
        request_path.write_text(json.dumps(request))
    else:
        graph["bonds"][0] = graph["bonds"][1]
        without_hash = {key: value for key, value in graph.items() if key != "sha256"}
        graph["sha256"] = hashlib.sha256(canonical_bytes(without_hash)).hexdigest()
        graph_path.write_text(json.dumps(graph))
        request["graph_sha256"] = graph["sha256"]
        request_path.write_text(json.dumps(request))
    completed = run_adapter(qmc_sse, request_path, tmp_path / "run")
    assert completed.returncode != 0
    assert "graph" in completed.stderr.lower()
    assert not (tmp_path / "run" / "bins").exists()


@pytest.mark.parametrize(
    ("length", "site_count", "message"),
    [
        (97, 97 * 97, "ceiling"),
        (2**64, 1, "graph"),
    ],
)
def test_graph_size_ceiling_and_integer_overflow_fail_before_allocation(
    qmc_sse, build_info, tmp_path, length, site_count, message
):
    request_path, request = make_request(tmp_path, build_info)
    graph = {
        "bonds": [],
        "lattice": "triangular",
        "length": length,
        "site_count": site_count,
    }
    graph["sha256"] = hashlib.sha256(canonical_bytes(graph)).hexdigest()
    graph_path = Path(request["graph_path"])
    graph_path.write_text(json.dumps(graph))
    request["graph_sha256"] = graph["sha256"]
    request_path.write_text(json.dumps(request))
    result = run_adapter(qmc_sse, request_path, tmp_path / "run")
    assert result.returncode != 0
    assert message in result.stderr.lower()
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda graph: graph.update(length=True),
        lambda graph: graph.update(site_count=True),
        lambda graph: graph.update(bonds=[[False, 1]]),
    ],
)
def test_graph_boolean_values_are_not_integers(qmc_sse, build_info, tmp_path, mutation):
    request_path, request = make_request(tmp_path, build_info)
    graph_path = Path(request["graph_path"])
    graph = json.loads(graph_path.read_text())
    mutation(graph)
    without_hash = {key: value for key, value in graph.items() if key != "sha256"}
    graph["sha256"] = hashlib.sha256(canonical_bytes(without_hash)).hexdigest()
    graph_path.write_text(json.dumps(graph))
    request["graph_sha256"] = graph["sha256"]
    request_path.write_text(json.dumps(request))
    result = run_adapter(qmc_sse, request_path, tmp_path / "run")
    assert result.returncode != 0
    assert "graph" in result.stderr.lower()


def test_graph_input_byte_ceiling_precedes_json_allocation(qmc_sse, build_info, tmp_path):
    request_path, request = make_request(tmp_path, build_info)
    graph_path = Path(request["graph_path"])
    graph_path.write_bytes(b" " * (2 * 1024 * 1024 + 1))
    result = run_adapter(qmc_sse, request_path, tmp_path / "run")
    assert result.returncode != 0
    assert "byte ceiling" in result.stderr.lower()


def test_seed_reproducibility_and_separation(qmc_sse, build_info, tmp_path):
    request_a, _ = make_request(tmp_path / "a", build_info, seed=91)
    request_b, _ = make_request(tmp_path / "b", build_info, seed=91)
    request_c, _ = make_request(tmp_path / "c", build_info, seed=92)
    outputs = [tmp_path / name / "run" for name in ("a", "b", "c")]
    for request, output in zip((request_a, request_b, request_c), outputs, strict=True):
        completed = run_adapter(qmc_sse, request, output)
        assert completed.returncode == 0, completed.stderr
    assert retained_bin_bytes(outputs[0]) == retained_bin_bytes(outputs[1])
    assert retained_bin_bytes(outputs[0]) != retained_bin_bytes(outputs[2])
    record = json.loads(retained_bin_bytes(outputs[0])[0])
    assert record["seed_derivation"] == "sha256:qmc-sse-seed-v1||u64be"


@pytest.mark.parametrize("kind", ["request", "graph", "output-component", "lock"])
def test_symlinked_control_paths_fail_closed(qmc_sse, build_info, tmp_path, kind):
    request_path, request = make_request(tmp_path / "fixture", build_info)
    output = tmp_path / "run"
    if kind == "request":
        alias = tmp_path / "request-link.json"
        alias.symlink_to(request_path)
        request_path = alias
    elif kind == "graph":
        graph = Path(request["graph_path"])
        real = graph.with_name("graph-real.json")
        graph.rename(real)
        graph.symlink_to(real)
    elif kind == "output-component":
        real = tmp_path / "real-output-parent"
        real.mkdir()
        linked = tmp_path / "linked-output-parent"
        linked.symlink_to(real, target_is_directory=True)
        output = linked / "run"
    else:
        output.mkdir()
        target = tmp_path / "attacker-lock"
        target.write_text("attacker")
        (output / ".qmc-sse.lock").symlink_to(target)
    result = run_adapter(qmc_sse, request_path, output)
    assert result.returncode != 0
    assert any(
        word in result.stderr.lower() for word in ("symlink", "symbolic", "resolve")
    )


def test_replacing_bins_directory_during_publication_fails_closed(
    qmc_sse, build_info, tmp_path
):
    request_path, _ = make_request(
        tmp_path / "request", build_info, retained_samples=1, bin_length=1, checkpoint_bins=1
    )
    output = tmp_path / "run"
    ready = tmp_path / "ready"
    release = tmp_path / "release"
    process = start_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={
            "QMC_SSE_TEST_PAUSE_AT": "before-bin-rename",
            "QMC_SSE_TEST_READY": str(ready),
            "QMC_SSE_TEST_RELEASE": str(release),
        },
    )
    wait_for_path(ready, process)
    original = output / "bins-original"
    (output / "bins").rename(original)
    attacker = tmp_path / "attacker-bins"
    attacker.mkdir()
    (output / "bins").symlink_to(attacker, target_is_directory=True)
    release.touch()
    _, stderr = process.communicate(timeout=20)
    assert process.returncode != 0, stderr
    assert list(attacker.iterdir()) == []


@pytest.mark.parametrize("ancestor_index", [0, 1, 2])
def test_replacing_each_output_ancestor_during_publication_fails_closed(
    qmc_sse, build_info, tmp_path, ancestor_index
):
    request_path, _ = make_request(
        tmp_path / "request", build_info, retained_samples=1, bin_length=1, checkpoint_bins=1
    )
    ancestors = [
        tmp_path / "ancestor-0",
        tmp_path / "ancestor-0" / "ancestor-1",
        tmp_path / "ancestor-0" / "ancestor-1" / "ancestor-2",
    ]
    output = ancestors[-1] / "run"
    ready = tmp_path / "ready"
    release = tmp_path / "release"
    process = start_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={
            "QMC_SSE_TEST_PAUSE_AT": "before-bin-rename",
            "QMC_SSE_TEST_READY": str(ready),
            "QMC_SSE_TEST_RELEASE": str(release),
        },
    )
    wait_for_path(ready, process)
    victim = ancestors[ancestor_index]
    original = victim.with_name(f"{victim.name}-original")
    victim.rename(original)
    victim.mkdir()
    release.touch()
    _, stderr = process.communicate(timeout=20)
    assert process.returncode != 0, stderr
    assert list(victim.iterdir()) == []


def test_atomic_noreplace_preserves_concurrent_bin_winner(qmc_sse, build_info, tmp_path):
    request_path, _ = make_request(
        tmp_path / "request", build_info, retained_samples=1, bin_length=1, checkpoint_bins=1
    )
    output = tmp_path / "run"
    ready = tmp_path / "ready"
    release = tmp_path / "release"
    process = start_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={
            "QMC_SSE_TEST_PAUSE_AT": "before-bin-rename",
            "QMC_SSE_TEST_READY": str(ready),
            "QMC_SSE_TEST_RELEASE": str(release),
        },
    )
    wait_for_path(ready, process)
    stage = next((output / "bins").glob(".stage-bin-*"))
    payload = stage.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    winner = output / "bins" / f"{digest}.ndjson"
    os.link(stage, winner)
    winning_inode = winner.stat().st_ino
    release.touch()
    _, stderr = process.communicate(timeout=20)
    assert process.returncode == 0, stderr
    assert winner.stat().st_ino == winning_inode
    assert winner.read_bytes() == payload


@pytest.mark.parametrize("corrupt", [False, True])
def test_atomic_noreplace_generation_winner_is_validated_without_overwrite(
    qmc_sse, build_info, tmp_path, corrupt
):
    request_path, _ = make_request(
        tmp_path / "request", build_info, retained_samples=1, bin_length=1, checkpoint_bins=1
    )
    output = tmp_path / "run"
    ready = tmp_path / "ready"
    release = tmp_path / "release"
    process = start_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={
            "QMC_SSE_TEST_PAUSE_AT": "before-generation-rename",
            "QMC_SSE_TEST_READY": str(ready),
            "QMC_SSE_TEST_RELEASE": str(release),
        },
    )
    wait_for_path(ready, process)
    stage = next((output / "generations").glob(".stage-generation-*"))
    identity = stage.name.split("-")[2]
    winner = output / "generations" / identity
    manifest = (stage / "manifest.json").read_bytes()
    winner.mkdir()
    (winner / "manifest.json").write_bytes(manifest)
    winning_inode = winner.stat().st_ino
    if corrupt:
        (winner / "manifest.json").write_bytes(b"{}\n")
    release.touch()
    _, stderr = process.communicate(timeout=20)
    assert winner.stat().st_ino == winning_inode
    if corrupt:
        assert process.returncode != 0
        assert (winner / "manifest.json").read_bytes() == b"{}\n"
    else:
        assert process.returncode == 0, stderr


def test_encoded_rustflag_changes_build_fingerprint(qmc_sse, build_info, tmp_path):
    environment = rust_environment()
    target = tmp_path / "flagged-target"
    environment["CARGO_TARGET_DIR"] = str(target)
    environment["CARGO_ENCODED_RUSTFLAGS"] = "-Copt-level=1"
    completed = subprocess.run(
        [cargo_executable(), "build", "--locked", "--manifest-path", str(MANIFEST)],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stderr
    flagged = subprocess.run(
        [str(target / "debug" / "qmc-sse"), "--build-info"],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
        timeout=10,
    )
    flagged_info = json.loads(flagged.stdout)
    assert flagged_info["encoded_rustflags"] == "-Copt-level=1"
    assert flagged_info["build_hash"] != build_info["build_hash"]


def test_pauli_normalization_and_transverse_offset(qmc_sse, build_info, tmp_path):
    request_path, request = make_request(
        tmp_path,
        build_info,
        beta=0.8,
        coupling=0.0,
        field=1.1,
        retained_samples=400,
        bin_length=40,
        checkpoint_bins=10,
        thermalization_sweeps=100,
        thinning=2,
    )
    completed = run_adapter(qmc_sse, request_path, tmp_path / "run", timeout=120)
    assert completed.returncode == 0, completed.stderr
    bins = [json.loads(value) for value in retained_bin_bytes(tmp_path / "run")]
    samples = sum(value["sample_count"] for value in bins)
    mx = sum(value["transverse_magnetization_sum"] for value in bins) / samples
    m2 = sum(value["m2_sum"] for value in bins) / samples
    m4 = sum(value["m4_sum"] for value in bins) / samples
    assert abs(mx - math.tanh(request["beta"] * request["field"])) < 0.12
    assert 0.0 <= m4 <= m2 <= 1.0
    assert all(value["cluster_attempts_per_sweep"] == 8 for value in bins)


def test_restart_matches_uninterrupted_across_boundaries(qmc_sse, build_info, tmp_path):
    request_path, _ = make_request(
        tmp_path / "request", build_info, retained_samples=8, bin_length=1, checkpoint_bins=2
    )
    clean = tmp_path / "clean" / "run"
    interrupted = tmp_path / "interrupted" / "run"
    assert run_adapter(qmc_sse, request_path, clean).returncode == 0

    crashed = run_adapter(
        qmc_sse,
        request_path,
        interrupted,
        extra_env={
            "QMC_SSE_FAILPOINT": "after-generation-rename",
            "QMC_SSE_FAILPOINT_OCCURRENCE": "2",
        },
    )
    assert crashed.returncode != 0
    resumed = run_adapter(qmc_sse, request_path, interrupted)
    assert resumed.returncode == 0, resumed.stderr
    assert retained_bin_bytes(interrupted) == retained_bin_bytes(clean)
    interrupted_chain = generation_chain(interrupted)
    clean_chain = generation_chain(clean)
    assert len(interrupted_chain) == len(clean_chain)
    for (_, interrupted_manifest), (_, clean_manifest) in zip(
        interrupted_chain, clean_chain, strict=True
    ):
        assert {
            key: value
            for key, value in interrupted_manifest.items()
            if key not in {"anchor_sha256", "previous_generation_sha256"}
        } == {
            key: value
            for key, value in clean_manifest.items()
            if key not in {"anchor_sha256", "previous_generation_sha256"}
        }


def test_adopts_unique_genesis_after_rename_before_first_pointer(qmc_sse, build_info, tmp_path):
    request_path, _ = make_request(
        tmp_path, build_info, retained_samples=6, bin_length=1, checkpoint_bins=3
    )
    output = tmp_path / "run"
    crashed = run_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={"QMC_SSE_FAILPOINT": "after-generation-rename"},
    )
    assert crashed.returncode != 0
    assert not (output / "current-generation.json").exists()
    assert len(list((output / "generations").iterdir())) == 1
    resumed = run_adapter(qmc_sse, request_path, output)
    assert resumed.returncode == 0, resumed.stderr
    assert [manifest["completed_bin_count"] for _, manifest in generation_chain(output)] == [3, 6]


@pytest.mark.parametrize(
    "failpoint",
    ["before-bin-rename", "before-generation-rename", "before-pointer-replace"],
)
def test_publication_failpoints_recover_without_overwrite(
    qmc_sse, build_info, tmp_path, failpoint
):
    request_path, _ = make_request(
        tmp_path, build_info, retained_samples=2, bin_length=1, checkpoint_bins=2
    )
    output = tmp_path / "run"
    failed = run_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={"QMC_SSE_FAILPOINT": failpoint},
    )
    assert failed.returncode != 0
    recovered = run_adapter(qmc_sse, request_path, output)
    assert recovered.returncode == 0, recovered.stderr
    assert len(retained_bin_bytes(output)) == 2


def publish_fabricated_generation(output: Path, manifest: dict[str, object]) -> str:
    payload = canonical_bytes(manifest) + b"\n"
    digest = hashlib.sha256(payload).hexdigest()
    directory = output / "generations" / digest
    directory.mkdir()
    (directory / "manifest.json").write_bytes(payload)
    return digest


@pytest.mark.parametrize("conflict", ["branch", "ancestry-gap"])
def test_generation_ambiguity_and_gaps_fail_closed(
    qmc_sse, build_info, tmp_path, conflict
):
    request_path, _ = make_request(
        tmp_path, build_info, retained_samples=6, bin_length=1, checkpoint_bins=2
    )
    output = tmp_path / "run"
    assert run_adapter(qmc_sse, request_path, output).returncode == 0
    chain = generation_chain(output)
    if conflict == "branch":
        altered = dict(chain[1][1])
        hashes = list(altered["bin_object_hashes"])
        hashes[-2:] = reversed(hashes[-2:])
        altered["bin_object_hashes"] = hashes
        publish_fabricated_generation(output, altered)
    else:
        altered = dict(chain[-1][1])
        altered["previous_generation_sha256"] = "0" * 64
        publish_fabricated_generation(output, altered)
    result = run_adapter(qmc_sse, request_path, output)
    assert result.returncode != 0
    assert any(
        word in result.stderr.lower()
        for word in ("genesis", "conflict", "unrelated", "gap", "ancestry")
    ), result.stderr


def test_corrupt_genesis_is_archived_before_unique_candidate_selection(
    qmc_sse, build_info, tmp_path
):
    request_path, _ = make_request(
        tmp_path, build_info, retained_samples=4, bin_length=1, checkpoint_bins=2
    )
    output = tmp_path / "run"
    assert run_adapter(qmc_sse, request_path, output).returncode == 0
    chain = generation_chain(output)
    altered = dict(chain[0][1])
    altered["bin_object_hashes"] = list(reversed(altered["bin_object_hashes"]))
    corrupt_hash = publish_fabricated_generation(output, altered)
    (output / "current-generation.json").unlink()
    result = run_adapter(qmc_sse, request_path, output)
    assert result.returncode == 0, result.stderr
    assert pointer(output)["generation_sha256"] == chain[-1][0]
    assert not (output / "generations" / corrupt_hash).exists()
    assert any(
        corrupt_hash in path.name and "invalid-genesis" in path.name
        for path in (output / "archive").iterdir()
    )


def test_orphan_adoption_and_archive(qmc_sse, build_info, tmp_path):
    request_path, _ = make_request(
        tmp_path, build_info, retained_samples=4, bin_length=1, checkpoint_bins=2
    )
    output = tmp_path / "run"
    crashed = run_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={"QMC_SSE_FAILPOINT": "after-bin-rename"},
    )
    assert crashed.returncode != 0
    orphan = output / "bins" / f"{hashlib.sha256(b'bad\n').hexdigest()}.ndjson"
    orphan.write_bytes(b"bad\n")
    resumed = run_adapter(qmc_sse, request_path, output)
    assert resumed.returncode == 0, resumed.stderr
    assert len(retained_bin_bytes(output)) == 4
    assert not orphan.exists()
    assert any("orphan" in path.name for path in (output / "archive").iterdir())


def test_orphan_audit_keeps_only_immediate_replay_bin(qmc_sse, build_info, tmp_path):
    request_path, _ = make_request(
        tmp_path / "request", build_info, retained_samples=4, bin_length=1, checkpoint_bins=2
    )
    source = tmp_path / "source"
    assert run_adapter(qmc_sse, request_path, source).returncode == 0
    payloads = retained_bin_bytes(source)
    output = tmp_path / "run"
    bins = output / "bins"
    bins.mkdir(parents=True)
    for index in (0, 2):
        digest = hashlib.sha256(payloads[index]).hexdigest()
        (bins / f"{digest}.ndjson").write_bytes(payloads[index])
    result = run_adapter(qmc_sse, request_path, output)
    assert result.returncode == 0, result.stderr
    archived_payloads = [
        path.read_bytes()
        for path in (output / "archive").iterdir()
        if path.is_file() and ".future-orphan" in path.name
    ]
    assert payloads[2] in archived_payloads
    assert retained_bin_bytes(output) == payloads


@pytest.mark.parametrize(
    "crashpoint",
    [
        "after-bin-file-fsync",
        "after-bin-rename",
        "after-bins-directory-fsync",
        "after-generation-manifest-fsync",
        "after-generation-directory-fsync",
        "after-generation-rename",
        "after-generations-directory-fsync",
        "after-pointer-file-fsync",
        "after-pointer-rename",
        "after-run-directory-fsync",
    ],
)
def test_abrupt_crash_boundaries_recover_in_fresh_process(
    qmc_sse, build_info, tmp_path, crashpoint
):
    request_path, _ = make_request(
        tmp_path / "request", build_info, retained_samples=2, bin_length=1, checkpoint_bins=2
    )
    output = tmp_path / "run"
    crashed = run_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={"QMC_SSE_CRASHPOINT": crashpoint},
    )
    assert crashed.returncode not in (0, 2)
    recovered = run_adapter(qmc_sse, request_path, output)
    assert recovered.returncode == 0, recovered.stderr
    assert len(retained_bin_bytes(output)) == 2


def test_adopted_lock_state_is_fsynced_after_rename_crash(
    qmc_sse, build_info, tmp_path
):
    request_path, _ = make_request(
        tmp_path / "request", build_info, retained_samples=1, bin_length=1, checkpoint_bins=1
    )
    output = tmp_path / "run"
    renamed = run_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={"QMC_SSE_CRASHPOINT": "after-lock-state-rename"},
    )
    assert renamed.returncode not in (0, 2)
    adopted = run_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={"QMC_SSE_CRASHPOINT": "after-adopted-lock-state-fsync"},
    )
    assert adopted.returncode not in (0, 2)
    recovered = run_adapter(qmc_sse, request_path, output)
    assert recovered.returncode == 0, recovered.stderr
    assert len(retained_bin_bytes(output)) == 1


@pytest.mark.parametrize("damage", ["bin", "manifest", "pointer", "missing-bin"])
def test_corruption_and_stale_pointer_fail_closed(qmc_sse, build_info, tmp_path, damage):
    request_path, _ = make_request(tmp_path, build_info)
    output = tmp_path / "run"
    assert run_adapter(qmc_sse, request_path, output).returncode == 0
    chain = generation_chain(output)
    bin_hash = chain[-1][1]["bin_object_hashes"][0]
    damaged_path = None
    damaged_bytes = None
    if damage == "bin":
        damaged_path = output / "bins" / f"{bin_hash}.ndjson"
        damaged_bytes = b'{"truncated":'
        damaged_path.write_bytes(damaged_bytes)
    elif damage == "manifest":
        damaged_path = output / "generations" / chain[-1][0] / "manifest.json"
        damaged_bytes = b"{}\n"
        damaged_path.write_bytes(damaged_bytes)
    elif damage == "pointer":
        (output / "current-generation.json").write_text(
            json.dumps({"generation_sha256": "0" * 64, "path": "generations/" + "0" * 64})
        )
    else:
        (output / "bins" / f"{bin_hash}.ndjson").unlink()
    rerun = run_adapter(qmc_sse, request_path, output)
    assert rerun.returncode != 0
    if damaged_path is not None:
        if damage == "manifest":
            archived = list((output / "archive").glob(f"{chain[-1][0]}.invalid-generation*"))
            assert len(archived) == 1
            assert (archived[0] / "manifest.json").read_bytes() == damaged_bytes
        else:
            assert damaged_path.read_bytes() == damaged_bytes
    assert any(word in rerun.stderr.lower() for word in ("hash", "manifest", "pointer", "missing"))


@pytest.mark.parametrize("control", ["pointer", "manifest", "bin"])
def test_symlinked_published_control_files_fail_closed(
    qmc_sse, build_info, tmp_path, control
):
    request_path, _ = make_request(tmp_path, build_info)
    output = tmp_path / "run"
    assert run_adapter(qmc_sse, request_path, output).returncode == 0
    chain = generation_chain(output)
    if control == "pointer":
        path = output / "current-generation.json"
    elif control == "manifest":
        path = output / "generations" / chain[-1][0] / "manifest.json"
    else:
        path = output / "bins" / f"{chain[-1][1]['bin_object_hashes'][0]}.ndjson"
    target = tmp_path / f"{control}-target"
    target.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(target)
    result = run_adapter(qmc_sse, request_path, output)
    assert result.returncode != 0
    assert any(
        word in result.stderr.lower()
        for word in ("symbolic", "symlink", "securely", "manifest", "bin")
    )


def test_stale_request_cannot_reuse_output(qmc_sse, build_info, tmp_path):
    first, _ = make_request(tmp_path / "first", build_info, seed=1)
    second, _ = make_request(tmp_path / "second", build_info, seed=2)
    output = tmp_path / "run"
    assert run_adapter(qmc_sse, first, output).returncode == 0
    stale = run_adapter(qmc_sse, second, output)
    assert stale.returncode != 0
    assert "request" in stale.stderr.lower() or "stale" in stale.stderr.lower()


def replace_with_self_consistent_lock_state(output: Path) -> tuple[Path, Path]:
    state = output / ".qmc-sse-lock-state"
    original = output / ".qmc-sse-lock-state-original"
    request_sha256 = json.loads((state / "identity.json").read_text())["request_sha256"]
    replacement = output / ".qmc-sse-lock-state-replacement"
    replacement.mkdir()
    lock = replacement / ".qmc-sse.lock"
    lock.touch()
    identity_path = replacement / "identity.json"
    identity_path.touch()
    state_stat = replacement.stat()
    lock_stat = lock.stat()
    identity_stat = identity_path.stat()
    identity = {
        "identity_device": identity_stat.st_dev,
        "identity_inode": identity_stat.st_ino,
        "lock_device": lock_stat.st_dev,
        "lock_inode": lock_stat.st_ino,
        "request_sha256": request_sha256,
        "schema_version": "qmc-sse-lock-identity-v1",
        "state_device": state_stat.st_dev,
        "state_inode": state_stat.st_ino,
    }
    identity_path.write_bytes(canonical_bytes(identity) + b"\n")
    state.rename(original)
    replacement.rename(state)
    return state, original


def assert_lock_anchor_is_self_bound(output: Path, request_path: Path) -> dict[str, object]:
    selection_path = output / "run-lock-anchor.json"
    selection_bytes = selection_path.read_bytes()
    selection = json.loads(selection_bytes)
    assert selection_bytes == canonical_bytes(selection) + b"\n"
    assert set(selection) == {
        "anchor_device",
        "anchor_inode",
        "anchor_sha256",
        "path",
        "schema_version",
    }
    assert selection["schema_version"] == "qmc-sse-run-lock-anchor-selection-v1"
    assert selection["path"] == f"run-lock-anchors/{selection['anchor_sha256']}.json"
    anchor_path = output / selection["path"]
    anchor_bytes = anchor_path.read_bytes()
    anchor = json.loads(anchor_bytes)
    assert anchor_bytes == canonical_bytes(anchor) + b"\n"
    assert hashlib.sha256(anchor_bytes).hexdigest() == selection["anchor_sha256"]
    assert set(anchor) == {
        "identity_device",
        "identity_inode",
        "lock_device",
        "lock_inode",
        "lock_state_identity_sha256",
        "output_namespace",
        "request_sha256",
        "schema_version",
        "state_device",
        "state_inode",
    }
    anchor_stat = anchor_path.stat()
    pin_path = anchor_path.with_suffix(".pin")
    pin_stat = pin_path.stat()
    assert pin_path.read_bytes() == anchor_bytes
    assert (pin_stat.st_dev, pin_stat.st_ino) == (
        anchor_stat.st_dev,
        anchor_stat.st_ino,
    )
    state = output / ".qmc-sse-lock-state"
    state_stat = state.stat()
    lock_stat = (state / ".qmc-sse.lock").stat()
    identity_stat = (state / "identity.json").stat()
    request = json.loads(request_path.read_text())
    assert anchor["schema_version"] == "qmc-sse-run-lock-anchor-v2"
    assert (selection["anchor_device"], selection["anchor_inode"]) == (
        anchor_stat.st_dev,
        anchor_stat.st_ino,
    )
    assert (anchor["state_device"], anchor["state_inode"]) == (
        state_stat.st_dev,
        state_stat.st_ino,
    )
    assert (anchor["lock_device"], anchor["lock_inode"]) == (
        lock_stat.st_dev,
        lock_stat.st_ino,
    )
    assert (anchor["identity_device"], anchor["identity_inode"]) == (
        identity_stat.st_dev,
        identity_stat.st_ino,
    )
    assert anchor["output_namespace"] == str(output.absolute())
    assert anchor["request_sha256"] == hashlib.sha256(canonical_bytes(request)).hexdigest()
    lock_state_identity = {
        "identity_device": identity_stat.st_dev,
        "identity_inode": identity_stat.st_ino,
        "lock_device": lock_stat.st_dev,
        "lock_inode": lock_stat.st_ino,
        "output_namespace": anchor["output_namespace"],
        "request_sha256": anchor["request_sha256"],
        "schema_version": "qmc-sse-lock-state-binding-v2",
        "state_device": state_stat.st_dev,
        "state_inode": state_stat.st_ino,
    }
    assert anchor["lock_state_identity_sha256"] == hashlib.sha256(
        canonical_bytes(lock_state_identity)
    ).hexdigest()
    if (output / "current-generation.json").exists():
        for _, manifest in generation_chain(output):
            assert manifest["anchor_sha256"] == selection["anchor_sha256"]
            assert manifest["schema_version"] == "qmc-checkpoint-generation-v2"
        current = pointer(output)
        assert current["anchor_sha256"] == selection["anchor_sha256"]
        assert current["schema_version"] == "qmc-current-generation-v2"
    return anchor


def test_durable_anchor_rejects_whole_state_replacement_across_local_lock_namespaces(
    qmc_sse, build_info, tmp_path
):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=1, bin_length=1)
    output = tmp_path / "run"
    held = tmp_path / "filesystem-lock-held"
    release = tmp_path / "release-filesystem-lock"
    process_a = start_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={
            "QMC_SSE_TEST_HOLD_LOCK_READY": str(held),
            "QMC_SSE_TEST_HOLD_LOCK_RELEASE": str(release),
            "QMC_SSE_TEST_ABSTRACT_LOCK_NAMESPACE": "namespace-a",
        },
    )
    wait_for_path(held, process_a)
    anchor = assert_lock_anchor_is_self_bound(output, request_path)
    state, _ = replace_with_self_consistent_lock_state(output)
    process_b = start_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={"QMC_SSE_TEST_ABSTRACT_LOCK_NAMESPACE": "namespace-b"},
    )
    _, stderr_b = process_b.communicate(timeout=10)
    assert process_b.returncode != 0, stderr_b
    assert "anchor" in stderr_b.lower() or "lock descriptor identity" in stderr_b.lower()
    assert not (output / "bins").exists()
    assert not (output / "current-generation.json").exists()
    assert (state / ".qmc-sse.lock").stat().st_ino != anchor["lock_inode"]
    release.touch()
    _, stderr_a = process_a.communicate(timeout=10)
    assert process_a.returncode != 0, stderr_a


def test_abstract_lock_blocks_whole_lock_state_replacement(
    qmc_sse, build_info, tmp_path
):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=1, bin_length=1)
    output = tmp_path / "run"
    held = tmp_path / "filesystem-lock-held"
    release = tmp_path / "release-filesystem-lock"
    abstract_acquired = tmp_path / "b-abstract-acquired"
    process_a = start_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={
            "QMC_SSE_TEST_HOLD_LOCK_READY": str(held),
            "QMC_SSE_TEST_HOLD_LOCK_RELEASE": str(release),
        },
    )
    wait_for_path(held, process_a)
    state, _ = replace_with_self_consistent_lock_state(output)
    process_b = start_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={"QMC_SSE_TEST_ABSTRACT_LOCK_READY": str(abstract_acquired)},
    )
    time.sleep(0.3)
    assert process_b.poll() is None
    assert not abstract_acquired.exists()
    assert not (state / "bins").exists()
    assert not (output / "bins").exists()
    release.touch()
    _, stderr_a = process_a.communicate(timeout=10)
    assert process_a.returncode != 0, stderr_a
    _, stderr_b = process_b.communicate(timeout=20)
    assert process_b.returncode != 0, stderr_b
    assert "anchor" in stderr_b.lower()
    assert abstract_acquired.is_file()
    assert not (output / "current-generation.json").exists()


def test_abstract_lock_releases_after_abrupt_holder_exit(
    qmc_sse, build_info, tmp_path
):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=1, bin_length=1)
    output = tmp_path / "run"
    held = tmp_path / "abstract-held"
    release = tmp_path / "unused-release"
    process_a = start_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={
            "QMC_SSE_TEST_HOLD_ABSTRACT_LOCK_READY": str(held),
            "QMC_SSE_TEST_HOLD_ABSTRACT_LOCK_RELEASE": str(release),
        },
    )
    wait_for_path(held, process_a)
    assert not output.exists()
    process_b = start_adapter(qmc_sse, request_path, output)
    time.sleep(0.3)
    assert process_b.poll() is None
    process_a.kill()
    process_a.communicate(timeout=5)
    _, stderr_b = process_b.communicate(timeout=20)
    assert process_b.returncode == 0, stderr_b
    assert (output / "current-generation.json").is_file()


def test_abstract_lock_timeout_is_bounded_and_diagnostic(
    qmc_sse, build_info, tmp_path
):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=1, bin_length=1)
    output = tmp_path / "run"
    held = tmp_path / "abstract-held"
    release = tmp_path / "release-abstract"
    process_a = start_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={
            "QMC_SSE_TEST_HOLD_ABSTRACT_LOCK_READY": str(held),
            "QMC_SSE_TEST_HOLD_ABSTRACT_LOCK_RELEASE": str(release),
        },
    )
    wait_for_path(held, process_a)
    started = time.monotonic()
    blocked = run_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={"QMC_SSE_ABSTRACT_LOCK_TIMEOUT_MS": "150"},
        timeout=5,
    )
    elapsed = time.monotonic() - started
    assert blocked.returncode != 0
    assert "abstract" in blocked.stderr.lower() and "timeout" in blocked.stderr.lower()
    assert 0.1 <= elapsed < 2.0
    assert not output.exists()
    release.touch()
    _, stderr_a = process_a.communicate(timeout=20)
    assert process_a.returncode == 0, stderr_a


def test_replaced_lock_path_rejects_holder_and_new_process(
    qmc_sse, build_info, tmp_path
):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=1, bin_length=1)
    output = tmp_path / "run"
    ready = tmp_path / "lock-held"
    release = tmp_path / "release-lock"
    process_a = start_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={
            "QMC_SSE_TEST_HOLD_LOCK_READY": str(ready),
            "QMC_SSE_TEST_HOLD_LOCK_RELEASE": str(release),
        },
    )
    wait_for_path(ready, process_a)
    state = output / ".qmc-sse-lock-state"
    lock = state / ".qmc-sse.lock"
    identity = state / "identity.json"
    assert lock.is_file() and identity.is_file()
    lock.rename(state / "original-lock")
    replacement_bytes = b"attacker replacement lock\n"
    lock.write_bytes(replacement_bytes)
    process_b = start_adapter(qmc_sse, request_path, output)
    time.sleep(0.3)
    assert process_b.poll() is None
    release.touch()
    _, stderr_a = process_a.communicate(timeout=10)
    assert process_a.returncode != 0, stderr_a
    _, stderr_b = process_b.communicate(timeout=10)
    assert process_b.returncode != 0, stderr_b
    assert lock.read_bytes() == replacement_bytes
    assert not (output / "bins").exists()
    assert not (output / "current-generation.json").exists()


@pytest.mark.parametrize("replacement", ["file", "symlink"])
def test_replaced_lock_identity_rejects_holder_and_new_process(
    qmc_sse, build_info, tmp_path, replacement
):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=1, bin_length=1)
    output = tmp_path / "run"
    ready = tmp_path / "lock-held"
    release = tmp_path / "release-lock"
    process_a = start_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={
            "QMC_SSE_TEST_HOLD_LOCK_READY": str(ready),
            "QMC_SSE_TEST_HOLD_LOCK_RELEASE": str(release),
        },
    )
    wait_for_path(ready, process_a)
    state = output / ".qmc-sse-lock-state"
    identity = state / "identity.json"
    original = state / "original-identity.json"
    original_bytes = identity.read_bytes()
    identity.rename(original)
    if replacement == "file":
        identity.write_bytes(original_bytes)
    else:
        identity.symlink_to(original.name)
    process_b = start_adapter(qmc_sse, request_path, output)
    time.sleep(0.3)
    assert process_b.poll() is None
    release.touch()
    _, stderr_a = process_a.communicate(timeout=10)
    assert process_a.returncode != 0, stderr_a
    _, stderr_b = process_b.communicate(timeout=10)
    assert process_b.returncode != 0, stderr_b
    assert not (output / "bins").exists()
    assert not (output / "current-generation.json").exists()


@pytest.mark.parametrize("replacement", ["file", "symlink"])
def test_replaced_lock_anchor_fails_closed(qmc_sse, build_info, tmp_path, replacement):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=1, bin_length=1)
    output = tmp_path / "run"
    assert run_adapter(qmc_sse, request_path, output).returncode == 0
    original_pointer = (output / "current-generation.json").read_bytes()
    selection = json.loads((output / "run-lock-anchor.json").read_text())
    anchor = output / selection["path"]
    original = output / "original-run-lock-anchor.json"
    anchor_bytes = anchor.read_bytes()
    anchor.rename(original)
    if replacement == "file":
        anchor.write_bytes(anchor_bytes)
    else:
        anchor.symlink_to(original.name)
    result = run_adapter(qmc_sse, request_path, output)
    assert result.returncode != 0
    assert "anchor" in result.stderr.lower() or "symbolic" in result.stderr.lower()
    assert (output / "current-generation.json").read_bytes() == original_pointer


def test_hardlinked_original_lock_inode_in_replacement_state_is_rejected(
    qmc_sse, build_info, tmp_path
):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=1, bin_length=1)
    output = tmp_path / "run"
    held = tmp_path / "filesystem-lock-held"
    release = tmp_path / "release-filesystem-lock"
    process_a = start_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={
            "QMC_SSE_TEST_HOLD_LOCK_READY": str(held),
            "QMC_SSE_TEST_HOLD_LOCK_RELEASE": str(release),
            "QMC_SSE_TEST_ABSTRACT_LOCK_NAMESPACE": "namespace-a",
        },
    )
    wait_for_path(held, process_a)
    anchor = assert_lock_anchor_is_self_bound(output, request_path)
    old_state = output / ".qmc-sse-lock-state"
    replacement = output / ".qmc-sse-lock-state-replacement"
    replacement.mkdir()
    os.link(old_state / ".qmc-sse.lock", replacement / ".qmc-sse.lock")
    identity_path = replacement / "identity.json"
    identity_path.touch()
    state_stat = replacement.stat()
    lock_stat = (replacement / ".qmc-sse.lock").stat()
    identity_stat = identity_path.stat()
    identity_path.write_bytes(
        canonical_bytes(
            {
                "identity_device": identity_stat.st_dev,
                "identity_inode": identity_stat.st_ino,
                "lock_device": lock_stat.st_dev,
                "lock_inode": lock_stat.st_ino,
                "request_sha256": anchor["request_sha256"],
                "schema_version": "qmc-sse-lock-identity-v1",
                "state_device": state_stat.st_dev,
                "state_inode": state_stat.st_ino,
            }
        )
        + b"\n"
    )
    old_state.rename(output / ".qmc-sse-lock-state-original")
    replacement.rename(old_state)
    process_b = start_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={"QMC_SSE_TEST_ABSTRACT_LOCK_NAMESPACE": "namespace-b"},
    )
    _, stderr_b = process_b.communicate(timeout=10)
    assert process_b.returncode != 0, stderr_b
    assert "anchor" in stderr_b.lower() or "lock-state" in stderr_b.lower()
    assert not (output / "current-generation.json").exists()
    release.touch()
    _, stderr_a = process_a.communicate(timeout=10)
    assert process_a.returncode != 0, stderr_a
    assert not (output / "current-generation.json").exists()


def test_same_inode_anchor_content_rewrite_fails_closed(qmc_sse, build_info, tmp_path):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=1, bin_length=1)
    output = tmp_path / "run"
    assert run_adapter(qmc_sse, request_path, output).returncode == 0
    selection = json.loads((output / "run-lock-anchor.json").read_text())
    anchor_path = output / selection["path"]
    inode = anchor_path.stat().st_ino
    anchor = json.loads(anchor_path.read_text())
    anchor["lock_inode"] += 1
    anchor_path.write_bytes(canonical_bytes(anchor) + b"\n")
    assert anchor_path.stat().st_ino == inode
    rejected = run_adapter(qmc_sse, request_path, output)
    assert rejected.returncode != 0
    assert "anchor" in rejected.stderr.lower() and "hash" in rejected.stderr.lower()


def test_distinct_second_canonical_anchor_fails_closed(qmc_sse, build_info, tmp_path):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=1, bin_length=1)
    output = tmp_path / "run"
    assert run_adapter(qmc_sse, request_path, output).returncode == 0
    selection = json.loads((output / "run-lock-anchor.json").read_text())
    anchor = json.loads((output / selection["path"]).read_text())
    anchor["state_inode"] += 1
    binding = {
        key: anchor[key]
        for key in (
            "identity_device",
            "identity_inode",
            "lock_device",
            "lock_inode",
            "output_namespace",
            "request_sha256",
            "state_device",
            "state_inode",
        )
    }
    binding["schema_version"] = "qmc-sse-lock-state-binding-v2"
    anchor["lock_state_identity_sha256"] = hashlib.sha256(canonical_bytes(binding)).hexdigest()
    anchor_bytes = canonical_bytes(anchor) + b"\n"
    second_hash = hashlib.sha256(anchor_bytes).hexdigest()
    (output / "run-lock-anchors" / f"{second_hash}.json").write_bytes(anchor_bytes)
    rejected = run_adapter(qmc_sse, request_path, output)
    assert rejected.returncode != 0
    assert "anchor" in rejected.stderr.lower() and (
        "multiple" in rejected.stderr.lower() or "exactly one" in rejected.stderr.lower()
    )


@pytest.mark.parametrize("damage", ["delete", "substitute"])
def test_canonical_anchor_delete_or_substitute_fails_closed(
    qmc_sse, build_info, tmp_path, damage
):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=1, bin_length=1)
    output = tmp_path / "run"
    assert run_adapter(qmc_sse, request_path, output).returncode == 0
    selection = json.loads((output / "run-lock-anchor.json").read_text())
    anchor_path = output / selection["path"]
    original_bytes = anchor_path.read_bytes()
    anchor_path.unlink()
    if damage == "substitute":
        anchor_path.write_bytes(original_bytes)
    rejected = run_adapter(qmc_sse, request_path, output)
    assert rejected.returncode != 0
    assert "anchor" in rejected.stderr.lower()


def test_anchor_substitution_fails_when_selection_identity_collides(
    qmc_sse, build_info, tmp_path
):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=1, bin_length=1)
    output = tmp_path / "run"
    assert run_adapter(qmc_sse, request_path, output).returncode == 0
    selection_path = output / "run-lock-anchor.json"
    selection = json.loads(selection_path.read_text())
    anchor_path = output / selection["path"]
    pin_path = anchor_path.with_suffix(".pin")
    original_bytes = anchor_path.read_bytes()
    original_inode = anchor_path.stat().st_ino
    assert pin_path.stat().st_ino == original_inode

    anchor_path.unlink()
    anchor_path.write_bytes(original_bytes)
    replacement = anchor_path.stat()
    assert replacement.st_ino != original_inode
    selection["anchor_device"] = replacement.st_dev
    selection["anchor_inode"] = replacement.st_ino
    selection_path.write_bytes(canonical_bytes(selection) + b"\n")

    rejected = run_adapter(qmc_sse, request_path, output)
    assert rejected.returncode != 0
    assert "anchor" in rejected.stderr.lower()
    assert pin_path.stat().st_ino == original_inode


def test_generation_anchor_mismatch_fails_closed(qmc_sse, build_info, tmp_path):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=1, bin_length=1)
    output = tmp_path / "run"
    assert run_adapter(qmc_sse, request_path, output).returncode == 0
    manifest = dict(generation_chain(output)[-1][1])
    manifest["anchor_sha256"] = "0" * 64
    mismatched = publish_fabricated_generation(output, manifest)
    current = pointer(output)
    current["generation_sha256"] = mismatched
    current["path"] = f"generations/{mismatched}"
    (output / "current-generation.json").write_bytes(canonical_bytes(current) + b"\n")
    rejected = run_adapter(qmc_sse, request_path, output)
    assert rejected.returncode != 0
    assert "anchor" in rejected.stderr.lower()


def test_generation_adapter_mismatch_fails_closed(qmc_sse, build_info, tmp_path):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=1, bin_length=1)
    output = tmp_path / "run"
    assert run_adapter(qmc_sse, request_path, output).returncode == 0
    manifest = dict(generation_chain(output)[-1][1])
    manifest["adapter"] = "QMC_LTFIM"
    mismatched = publish_fabricated_generation(output, manifest)
    current = pointer(output)
    current["generation_sha256"] = mismatched
    current["path"] = f"generations/{mismatched}"
    (output / "current-generation.json").write_bytes(canonical_bytes(current) + b"\n")
    rejected = run_adapter(qmc_sse, request_path, output)
    assert rejected.returncode != 0
    assert "adapter" in rejected.stderr.lower()


def test_current_pointer_anchor_mismatch_fails_closed(qmc_sse, build_info, tmp_path):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=1, bin_length=1)
    output = tmp_path / "run"
    assert run_adapter(qmc_sse, request_path, output).returncode == 0
    current = pointer(output)
    current["anchor_sha256"] = "0" * 64
    (output / "current-generation.json").write_bytes(canonical_bytes(current) + b"\n")
    rejected = run_adapter(qmc_sse, request_path, output)
    assert rejected.returncode != 0
    assert "anchor" in rejected.stderr.lower()


def test_first_lock_identity_creation_is_locally_serialized(
    qmc_sse, build_info, tmp_path
):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=1, bin_length=1)
    output = tmp_path / "run"
    ready_a = tmp_path / "ready-a"
    release_a = tmp_path / "release-a"
    process_a = start_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={
            "QMC_SSE_TEST_PAUSE_AT": "before-lock-state-rename",
            "QMC_SSE_TEST_READY": str(ready_a),
            "QMC_SSE_TEST_RELEASE": str(release_a),
        },
    )
    wait_for_path(ready_a, process_a)
    process_b = start_adapter(qmc_sse, request_path, output)
    time.sleep(0.3)
    assert process_b.poll() is None
    release_a.touch()
    _, stderr_a = process_a.communicate(timeout=30)
    _, stderr_b = process_b.communicate(timeout=30)
    assert process_a.returncode == 0, stderr_a
    assert process_b.returncode == 0, stderr_b
    state = output / ".qmc-sse-lock-state"
    assert sorted(path.name for path in state.iterdir()) == [".qmc-sse.lock", "identity.json"]
    identity = json.loads((state / "identity.json").read_text())
    lock_stat = (state / ".qmc-sse.lock").stat()
    state_stat = state.stat()
    assert (identity["lock_device"], identity["lock_inode"]) == (
        lock_stat.st_dev,
        lock_stat.st_ino,
    )
    assert (identity["state_device"], identity["state_inode"]) == (
        state_stat.st_dev,
        state_stat.st_ino,
    )
    identity_stat = (state / "identity.json").stat()
    assert (identity["identity_device"], identity["identity_inode"]) == (
        identity_stat.st_dev,
        identity_stat.st_ino,
    )
    assert_lock_anchor_is_self_bound(output, request_path)


def test_first_anchor_race_converges_across_local_lock_namespaces(
    qmc_sse, build_info, tmp_path
):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=1, bin_length=1)
    output = tmp_path / "run"
    ready_a = tmp_path / "ready-a"
    ready_b = tmp_path / "ready-b"
    release_a = tmp_path / "release-a"
    release_b = tmp_path / "release-b"
    process_a = start_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={
            "QMC_SSE_TEST_ABSTRACT_LOCK_NAMESPACE": "namespace-a",
            "QMC_SSE_TEST_PAUSE_AT": "before-lock-anchor-rename",
            "QMC_SSE_TEST_READY": str(ready_a),
            "QMC_SSE_TEST_RELEASE": str(release_a),
        },
    )
    process_b = start_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={
            "QMC_SSE_TEST_ABSTRACT_LOCK_NAMESPACE": "namespace-b",
            "QMC_SSE_TEST_PAUSE_AT": "before-lock-anchor-rename",
            "QMC_SSE_TEST_READY": str(ready_b),
            "QMC_SSE_TEST_RELEASE": str(release_b),
        },
    )
    wait_for_path(ready_a, process_a)
    wait_for_path(ready_b, process_b)
    release_a.touch()
    release_b.touch()
    _, stderr_a = process_a.communicate(timeout=30)
    _, stderr_b = process_b.communicate(timeout=30)
    assert process_a.returncode == 0, stderr_a
    assert process_b.returncode == 0, stderr_b
    assert_lock_anchor_is_self_bound(output, request_path)
    assert len(list((output / "generations").iterdir())) == 1
    assert any("lock-init-loser" in path.name for path in (output / "archive").iterdir())


def test_canonical_anchor_publication_during_staged_scan_is_adopted(
    qmc_sse, build_info, tmp_path
):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=1, bin_length=1)
    output = tmp_path / "run"
    winner_ready = tmp_path / "winner-ready"
    winner_release = tmp_path / "winner-release"
    observer_ready = tmp_path / "observer-ready"
    observer_release = tmp_path / "observer-release"
    winner = start_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={
            "QMC_SSE_TEST_ABSTRACT_LOCK_NAMESPACE": "winner",
            "QMC_SSE_TEST_PAUSE_AT": "before-canonical-lock-anchor-rename",
            "QMC_SSE_TEST_READY": str(winner_ready),
            "QMC_SSE_TEST_RELEASE": str(winner_release),
        },
    )
    wait_for_path(winner_ready, winner)
    observer = start_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={
            "QMC_SSE_TEST_ABSTRACT_LOCK_NAMESPACE": "observer",
            "QMC_SSE_TEST_PAUSE_AT": "after-selected-canonical-anchor-absent",
            "QMC_SSE_TEST_READY": str(observer_ready),
            "QMC_SSE_TEST_RELEASE": str(observer_release),
        },
    )
    wait_for_path(observer_ready, observer)

    winner_release.touch()
    _, winner_stderr = winner.communicate(timeout=30)
    assert winner.returncode == 0, winner_stderr
    observer_release.touch()
    _, observer_stderr = observer.communicate(timeout=30)
    assert observer.returncode == 0, observer_stderr
    assert_lock_anchor_is_self_bound(output, request_path)


@pytest.mark.parametrize(
    "crashpoint",
    [
        "after-lock-stage-parent-fsync",
        "after-lock-anchor-rename",
        "after-lock-anchor-pin-directory-fsync",
        "after-lock-anchor-directory-fsync",
        "after-lock-state-rename",
    ],
)
def test_lock_anchor_abrupt_crash_recovers_before_run_mutation(
    qmc_sse, build_info, tmp_path, crashpoint
):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=1, bin_length=1)
    output = tmp_path / "run"
    crashed = run_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={"QMC_SSE_CRASHPOINT": crashpoint},
    )
    assert crashed.returncode not in (0, 2)
    assert not (output / "bins").exists()
    assert not (output / "current-generation.json").exists()
    recovered = run_adapter(qmc_sse, request_path, output)
    assert recovered.returncode == 0, recovered.stderr
    assert_lock_anchor_is_self_bound(output, request_path)
    assert (output / "current-generation.json").is_file()


def test_unbound_published_lock_state_fails_closed_before_run_mutation(
    qmc_sse, build_info, tmp_path
):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=1, bin_length=1)
    output = tmp_path / "run"
    crashed = run_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={"QMC_SSE_CRASHPOINT": "after-lock-stage-parent-fsync"},
    )
    assert crashed.returncode not in (0, 2)
    staged_states = list(output.glob(".tmp-lock-state-*"))
    assert len(staged_states) == 1
    staged_states[0].rename(output / ".qmc-sse-lock-state")
    rejected = run_adapter(qmc_sse, request_path, output)
    assert rejected.returncode != 0
    assert "unbound" in rejected.stderr.lower() or "anchor" in rejected.stderr.lower()
    assert not (output / "bins").exists()
    assert not (output / "current-generation.json").exists()


def test_overlapping_processes_serialize_on_run_lock_and_converge(
    qmc_sse, build_info, tmp_path
):
    request_path, _ = make_request(tmp_path, build_info, retained_samples=4, bin_length=1)
    output = tmp_path / "run"
    ready = tmp_path / "lock-held"
    release = tmp_path / "release-lock"
    process_a = start_adapter(
        qmc_sse,
        request_path,
        output,
        extra_env={
            "QMC_SSE_TEST_HOLD_LOCK_READY": str(ready),
            "QMC_SSE_TEST_HOLD_LOCK_RELEASE": str(release),
        },
    )
    wait_for_path(ready, process_a)
    process_b = start_adapter(qmc_sse, request_path, output)
    time.sleep(0.3)
    assert process_b.poll() is None
    assert not (output / "current-generation.json").exists()
    release.touch()
    _, stderr_a = process_a.communicate(timeout=30)
    _, stderr_b = process_b.communicate(timeout=30)
    assert process_a.returncode == 0, stderr_a
    assert process_b.returncode == 0, stderr_b
    chain = generation_chain(output)
    assert len(list((output / "generations").iterdir())) == len(chain)
    assert any("identical" in path.name for path in (output / "archive").iterdir())
    for payload in retained_bin_bytes(output):
        assert payload.endswith(b"\n")
        assert hashlib.sha256(payload).hexdigest() in chain[-1][1]["bin_object_hashes"]


def test_every_durable_fsync_boundary_is_failure_atomic(qmc_sse, build_info, tmp_path):
    request_path, _ = make_request(
        tmp_path / "request",
        build_info,
        retained_samples=1,
        bin_length=1,
        checkpoint_bins=1,
        thermalization_sweeps=1,
    )
    failed = 0
    succeeded = False
    for boundary in range(1, 25):
        output = tmp_path / f"run-{boundary}"
        result = run_adapter(
            qmc_sse,
            request_path,
            output,
            extra_env={"QMC_SSE_FAIL_FSYNC_AT": str(boundary)},
        )
        if result.returncode == 0:
            succeeded = True
            break
        failed += 1
        if (output / "current-generation.json").exists():
            current = pointer(output)
            assert (output / current["path"] / "manifest.json").is_file()
        recovered = run_adapter(qmc_sse, request_path, output)
        assert recovered.returncode == 0, recovered.stderr
    assert succeeded
    assert failed >= 7


def summarize_bins(output: Path) -> tuple[dict[str, float], dict[str, float]]:
    records = [json.loads(value) for value in retained_bin_bytes(output)]
    names = ("energy", "transverse_magnetization", "m2", "m4")
    bin_means = {
        name: np.array([record[f"{name}_sum"] / record["sample_count"] for record in records])
        for name in names
    }
    means = {name: float(values.mean()) for name, values in bin_means.items()}
    errors = {
        name: float(values.std(ddof=1) / math.sqrt(len(values)))
        for name, values in bin_means.items()
    }
    means["binder_ratio"] = means["m2"] ** 2 / means["m4"]
    count = len(records)
    leave_one_out_m2 = (bin_means["m2"].sum() - bin_means["m2"]) / (count - 1)
    leave_one_out_m4 = (bin_means["m4"].sum() - bin_means["m4"]) / (count - 1)
    binder_jackknife = leave_one_out_m2**2 / leave_one_out_m4
    errors["binder_ratio"] = float(
        math.sqrt(
            (count - 1)
            / count
            * np.sum((binder_jackknife - binder_jackknife.mean()) ** 2)
        )
    )
    return means, errors


def test_fixed_seed_statistics_agree_with_thermal_ed(qmc_sse, build_info, tmp_path):
    request_path, request = make_request(
        tmp_path,
        build_info,
        seed=148_777,
        beta=0.55,
        coupling=0.7,
        field=1.3,
        retained_samples=2400,
        bin_length=120,
        checkpoint_bins=20,
        thermalization_sweeps=400,
        thinning=4,
    )
    output = tmp_path / "run"
    completed = run_adapter(qmc_sse, request_path, output, timeout=180)
    assert completed.returncode == 0, completed.stderr
    means, mc_errors = summarize_bins(output)
    exact = exact_thermal_observables(
        honeycomb_graph(2),
        coupling=request["coupling"],
        field=request["field"],
        beta=request["beta"],
    )
    expected = {
        "energy": exact.energy,
        "transverse_magnetization": exact.transverse_magnetization,
        "m2": exact.m2,
        "m4": exact.m4,
        "binder_ratio": exact.binder_ratio,
    }
    combined_errors = {
        name: math.hypot(mc_errors[name], 0.0) for name in expected
    }
    residuals = {
        name: abs(means[name] - expected[name]) / combined_errors[name]
        for name in expected
    }
    print(
        "STATISTICAL_EVIDENCE="
        + json.dumps(
            {
                "combined_errors": combined_errors,
                "exact": expected,
                "means": means,
                "residuals": residuals,
            },
            sort_keys=True,
        )
    )
    assert residuals == pytest.approx(residuals)  # Explicitly reject NaN/inf below.
    assert all(math.isfinite(value) and value <= 6.0 for value in residuals.values()), residuals
