from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import long_range_percolation.artifacts  # Preload before worker subprocess mocks.
import long_range_percolation.benchmark as benchmark
from long_range_percolation.benchmark import (
    BENCHMARK_KAPPAS,
    BENCHMARK_LENGTHS,
    BENCHMARK_SIGMAS,
    GATE_LENGTH,
    RSS_LIMIT_BYTES,
    STEADY_RUNS,
    WALL_LIMIT_SECONDS,
    BenchmarkProtocol,
    run_benchmark,
)


def _validation_report() -> dict[str, object]:
    return {
        "schema_version": "challenge-194-validation-v1",
        "passed": True,
        "checks": [{"passed": True}],
        "source": {"clean_tree": True, "source_revision": "a" * 40},
        "runtime_capability": {
            "schema_version": "challenge-194-runtime-v1",
            "python": "3.12.0",
            "implementation": "cpython",
            "platform": "test-platform",
            "machine": "x86_64",
            "numpy": "2.2.6",
            "scipy": "1.15.3",
            "h5py": "3.14.0",
            "numba": "0.66.0",
            "llvmlite": "0.48.0",
            "cpu_name": "",
            "cpu_features": "",
            "threading_layer": "",
            "numba_disable_jit": False,
            "fastmath": False,
            "boundscheck": True,
        },
    }


def _worker_payload(
    *,
    mode: str,
    backend: str = "poisson-numba",
    length: int = 8,
    sigma: float = 1.0,
    run_id: str = "run-id",
) -> dict[str, object]:
    return {
        "schema_version": "challenge-194-benchmark-worker-v1",
        "run_id": run_id,
        "mode": mode,
        "backend": backend,
        "length": length,
        "sigma": sigma.hex(),
        "kappas": [value.hex() for value in (0.25, 0.5)],
        "status": "passed",
        "failure": None,
        "timings_ns": {
            "startup": 1,
            "cache_load_warmup": 2,
            "compile": 3 if mode == "compile" else 0,
            "sampling": 4,
            "observable": 5,
            "artifact_serialization": 6,
            "wall": 15,
            "cpu": 12,
        },
        "metrics": {
            "events": 10,
            "unique_edges": 8,
            "unions": 7,
            "duplicates": 2,
            "total_probes": 12,
            "maximum_probe": 3,
            "rehashes": 2,
            "bytes": 4096,
        },
        "peak_rss_bytes": 8192,
        "selected_cpu": 0,
        "affinity": [0],
        "warmup": {
            "length": 2,
            "completed_before_timing": True,
        },
        "runtime_capability": dict(_validation_report()["runtime_capability"]),
        "process": {
            "pid": 123,
            "ppid": 1,
            "python": sys.executable,
            "platform": sys.platform,
        },
    }


def _reduced_protocol(validation_report: Path) -> BenchmarkProtocol:
    return BenchmarkProtocol.reduced(
        lengths=(8,),
        sigmas=(1.0,),
        kappas=(0.25, 0.5),
        steady_runs=2,
        gate_length=8,
        wall_limit_seconds=1.0,
        rss_limit_bytes=1024,
        backends=("poisson-numba",),
        validation_report=validation_report,
    )


def test_production_protocol_is_exactly_frozen_and_hex_serialized():
    protocol = BenchmarkProtocol.production_v1()
    assert BENCHMARK_LENGTHS == (2**10, 2**14, 2**18)
    assert BENCHMARK_SIGMAS == (0.8, 0.9, 1.0, 1.1)
    assert BENCHMARK_KAPPAS == tuple(
        value for value in (0.25 * 1.25**j for j in range(32)) if value <= 6.0
    )
    assert STEADY_RUNS == 5
    assert WALL_LIMIT_SECONDS == 120.0
    assert RSS_LIMIT_BYTES == 4 * 1024**3
    assert GATE_LENGTH == 2**18
    assert protocol.is_production
    document = protocol.to_document()
    assert document["sigmas"] == [value.hex() for value in BENCHMARK_SIGMAS]
    assert document["kappas"] == [value.hex() for value in BENCHMARK_KAPPAS]
    assert document["wall_limit_seconds"] == WALL_LIMIT_SECONDS.hex()
    assert document["backends"] == ["quadratic", "geometric", "poisson-numba"]
    assert document["quadratic_max_length"] == 256


def test_reduced_protocol_cannot_masquerade_as_production(tmp_path: Path):
    protocol = _reduced_protocol(tmp_path / "validation.json")
    assert not protocol.is_production
    with pytest.raises(ValueError, match="production"):
        protocol.require_production()


def test_cli_accepts_only_validation_report_and_output():
    parser = benchmark.cli_parser()
    parsed = parser.parse_args(
        ["--validation-report", "validation.json", "--output", "benchmark.json"]
    )
    assert parsed.validation_report == Path("validation.json")
    assert parsed.output == Path("benchmark.json")
    for forbidden in (
        "--length",
        "--sigma",
        "--kappa",
        "--repeat",
        "--wall-limit",
        "--rss-limit",
    ):
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "--validation-report",
                    "validation.json",
                    "--output",
                    "benchmark.json",
                    forbidden,
                    "1",
                ]
            )


@pytest.mark.parametrize(
    ("report", "error", "expected"),
    [
        ({"passed": True, "infrastructure_passed": True}, None, 0),
        ({"passed": False, "infrastructure_passed": True}, None, 2),
        (None, RuntimeError("broken worker"), 1),
    ],
)
def test_cli_exit_codes_distinguish_gate_and_infrastructure(
    monkeypatch: pytest.MonkeyPatch,
    report: dict[str, object] | None,
    error: Exception | None,
    expected: int,
):
    def fake_run(protocol, output):
        if error is not None:
            raise error
        return report

    monkeypatch.setattr(benchmark, "run_benchmark", fake_run)
    assert (
        benchmark.main(
            [
                "--validation-report",
                "validation.json",
                "--output",
                "benchmark.json",
            ]
        )
        == expected
    )


def test_parent_uses_fresh_compile_and_steady_processes_with_separate_caches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    validation_path = tmp_path / "validation.json"
    validation_path.write_text(json.dumps(_validation_report()), encoding="utf-8")
    calls: list[tuple[list[str], dict[str, str]]] = []
    pids = iter((101, 102, 103, 104, 105, 106))

    def fake_run(command, **kwargs):
        env = kwargs["env"]
        mode = command[command.index("--worker-mode") + 1]
        run_id = command[command.index("--run-id") + 1]
        payload = _worker_payload(mode=mode, run_id=run_id)
        payload["process"]["pid"] = next(pids)
        calls.append((command, env))
        cache = Path(env["NUMBA_CACHE_DIR"])
        if mode == "compile":
            assert list(cache.iterdir()) == []
            (cache / "compiled.nbc").write_bytes(b"cache")
        else:
            assert (cache / "compiled.nbc").read_bytes() == b"cache"
            assert not os.access(cache / "compiled.nbc", os.W_OK)
        return subprocess.CompletedProcess(
            command, 0, json.dumps(payload) + "\n", ""
        )

    monkeypatch.setattr(benchmark.subprocess, "run", fake_run)
    protocol = replace(_reduced_protocol(validation_path), steady_runs=5)
    report = run_benchmark(protocol, tmp_path / "report.json")
    assert [command[command.index("--worker-mode") + 1] for command, _ in calls] == [
        "compile",
        "steady",
        "steady",
        "steady",
        "steady",
        "steady",
    ]
    assert len({env["NUMBA_CACHE_DIR"] for _, env in calls}) == 6
    for _, env in calls:
        for name in benchmark.ONE_THREAD_ENVIRONMENT:
            assert env[name] == benchmark.ONE_THREAD_ENVIRONMENT[name]
    assert report["runs"][0]["process"]["pid"] == 101
    assert [run["process"]["pid"] for run in report["runs"][1:]] == [
        102,
        103,
        104,
        105,
        106,
    ]


def test_nonzero_exit_and_timeout_are_visible_failed_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    validation_path = tmp_path / "validation.json"
    validation_path.write_text(json.dumps(_validation_report()), encoding="utf-8")
    call_index = 0

    def fake_run(command, **kwargs):
        nonlocal call_index
        call_index += 1
        if call_index == 1:
            run_id = command[command.index("--run-id") + 1]
            (Path(kwargs["env"]["NUMBA_CACHE_DIR"]) / "compiled.nbc").write_bytes(
                b"cache"
            )
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps(_worker_payload(mode="compile", run_id=run_id)),
                "",
            )
        if call_index == 2:
            return subprocess.CompletedProcess(command, 7, "partial", "crashed")
        raise subprocess.TimeoutExpired(
            command, timeout=1.0, output="slow", stderr="hung"
        )

    monkeypatch.setattr(benchmark.subprocess, "run", fake_run)
    report = run_benchmark(_reduced_protocol(validation_path), tmp_path / "report.json")
    failures = [run for run in report["runs"] if run["status"] == "failed"]
    assert [run["failure"]["kind"] for run in failures] == [
        "nonzero-exit",
        "timeout",
    ]
    assert failures[0]["stderr"] == "crashed"
    assert failures[1]["stdout"] == "slow"
    assert not report["passed"]


def test_worker_payload_requires_separated_timings_raw_metrics_and_identity():
    payload = _worker_payload(mode="steady")
    benchmark.validate_worker_payload(
        payload,
        expected_mode="steady",
        expected_backend="poisson-numba",
        expected_length=8,
        expected_sigma=1.0,
        expected_kappas=(0.25, 0.5),
        expected_run_id="run-id",
    )
    for field in (
        "startup",
        "cache_load_warmup",
        "compile",
        "sampling",
        "observable",
        "artifact_serialization",
        "wall",
        "cpu",
    ):
        broken = json.loads(json.dumps(payload))
        del broken["timings_ns"][field]
        with pytest.raises(RuntimeError, match="timings"):
            benchmark.validate_worker_payload(
                broken,
                expected_mode="steady",
                expected_backend="poisson-numba",
                expected_length=8,
                expected_sigma=1.0,
                expected_kappas=(0.25, 0.5),
                expected_run_id="run-id",
            )
    for field in (
        "events",
        "unique_edges",
        "unions",
        "duplicates",
        "total_probes",
        "maximum_probe",
        "rehashes",
        "bytes",
    ):
        broken = json.loads(json.dumps(payload))
        del broken["metrics"][field]
        with pytest.raises(RuntimeError, match="metrics"):
            benchmark.validate_worker_payload(
                broken,
                expected_mode="steady",
                expected_backend="poisson-numba",
                expected_length=8,
                expected_sigma=1.0,
                expected_kappas=(0.25, 0.5),
                expected_run_id="run-id",
            )
    for key, value in (
        ("run_id", "stale"),
        ("mode", "compile"),
        ("length", 10),
        ("sigma", float(0.9).hex()),
    ):
        broken = json.loads(json.dumps(payload))
        broken[key] = value
        with pytest.raises(RuntimeError, match="mismatch"):
            benchmark.validate_worker_payload(
                broken,
                expected_mode="steady",
                expected_backend="poisson-numba",
                expected_length=8,
                expected_sigma=1.0,
                expected_kappas=(0.25, 0.5),
                expected_run_id="run-id",
            )


def test_gate_uses_maxima_without_dropping_outliers():
    runs = []
    for wall, rss in ((0.1, 100), (0.2, 200), (1.1, 900)):
        payload = _worker_payload(mode="steady", length=8)
        payload["timings_ns"]["wall"] = int(wall * 1e9)
        payload["timings_ns"]["cpu"] = int(wall * 0.5e9)
        payload["metrics"]["events"] = int(wall * 100)
        payload["peak_rss_bytes"] = rss
        runs.append(payload)
    aggregate = benchmark.aggregate_steady_runs(runs)
    assert aggregate["median_wall_seconds"] == pytest.approx(0.2)
    assert aggregate["max_wall_seconds"] == pytest.approx(1.1)
    assert aggregate["median_cpu_seconds"] == pytest.approx(0.1)
    assert aggregate["max_cpu_seconds"] == pytest.approx(0.55)
    assert aggregate["max_peak_rss_bytes"] == 900
    assert aggregate["metric_aggregates"]["events"] == {
        "median": 20,
        "maximum": 110,
    }
    gate = benchmark.evaluate_gate(
        aggregates=[
            {
                "backend": "poisson-numba",
                "length": 8,
                "sigma": float(1.0).hex(),
                **aggregate,
            }
        ],
        sigmas=(1.0,),
        gate_length=8,
        wall_limit_seconds=1.0,
        rss_limit_bytes=1024,
        correctness_passed=True,
    )
    assert not gate["passed"]
    assert gate["cells"][0]["wall_passed"] is False
    assert gate["cells"][0]["rss_passed"] is True


@pytest.mark.parametrize(
    "mutate",
    [
        lambda report: report.update(schema_version="hostile"),
        lambda report: report.update(passed=False),
        lambda report: report["checks"].append({"passed": False}),
        lambda report: report.update(source={"clean_tree": False}),
    ],
)
def test_validation_report_fails_closed(
    tmp_path: Path, mutate
):
    report = _validation_report()
    mutate(report)
    path = tmp_path / "validation.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(RuntimeError, match="validation"):
        benchmark.load_correctness_report(path)


def test_worker_rejects_affinity_that_is_not_exactly_one_cpu():
    payload = _worker_payload(mode="steady")
    payload["affinity"] = [0, 1]
    with pytest.raises(RuntimeError, match="affinity"):
        benchmark.validate_worker_payload(
            payload,
            expected_mode="steady",
            expected_backend="poisson-numba",
            expected_length=8,
            expected_sigma=1.0,
            expected_kappas=(0.25, 0.5),
            expected_run_id="run-id",
        )


def test_worker_rejects_incomplete_runtime_provenance():
    payload = _worker_payload(mode="steady")
    payload["runtime_capability"] = {
        "schema_version": "challenge-194-runtime-v1"
    }
    with pytest.raises(RuntimeError, match="runtime provenance"):
        benchmark.validate_worker_payload(
            payload,
            expected_mode="steady",
            expected_backend="poisson-numba",
            expected_length=8,
            expected_sigma=1.0,
            expected_kappas=(0.25, 0.5),
            expected_run_id="run-id",
        )


def test_timeout_byte_streams_are_decoded_and_publishable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    validation_path = tmp_path / "validation.json"
    validation_path.write_text(json.dumps(_validation_report()), encoding="utf-8")
    call_index = 0

    def fake_run(command, **kwargs):
        nonlocal call_index
        call_index += 1
        if call_index == 1:
            run_id = command[command.index("--run-id") + 1]
            (Path(kwargs["env"]["NUMBA_CACHE_DIR"]) / "compiled.nbc").write_bytes(
                b"cache"
            )
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps(_worker_payload(mode="compile", run_id=run_id)),
                "",
            )
        raise subprocess.TimeoutExpired(
            command,
            timeout=1.0,
            output=b"partial-\xff",
            stderr=b"hung-\xfe",
        )

    monkeypatch.setattr(benchmark.subprocess, "run", fake_run)
    protocol = replace(_reduced_protocol(validation_path), steady_runs=1)
    output = tmp_path / "report.json"
    report = run_benchmark(protocol, output)
    assert report["runs"][1]["stdout"] == "partial-\\xff"
    assert report["runs"][1]["stderr"] == "hung-\\xfe"
    assert report["infrastructure_passed"] is True
    assert report["passed"] is False
    assert output.read_bytes() == benchmark.canonical_report_bytes(report)


def test_report_is_canonical_immutable_and_not_published_on_infrastructure_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    validation_path = tmp_path / "validation.json"
    validation_path.write_text(json.dumps(_validation_report()), encoding="utf-8")
    output = tmp_path / "nested" / "benchmark.json"
    worker_pid = 100

    def successful(command, **kwargs):
        nonlocal worker_pid
        worker_pid += 1
        mode = command[command.index("--worker-mode") + 1]
        run_id = command[command.index("--run-id") + 1]
        if mode == "compile":
            (Path(kwargs["env"]["NUMBA_CACHE_DIR"]) / "compiled.nbc").write_bytes(
                b"cache"
            )
        payload = _worker_payload(mode=mode, run_id=run_id)
        payload["process"]["pid"] = worker_pid
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(payload) + "\n",
            "",
        )

    monkeypatch.setattr(benchmark.subprocess, "run", successful)
    report = run_benchmark(_reduced_protocol(validation_path), output)
    assert output.read_bytes() == benchmark.canonical_report_bytes(report)
    with pytest.raises(FileExistsError, match="immutable"):
        run_benchmark(_reduced_protocol(validation_path), output)

    broken_output = tmp_path / "broken.json"
    monkeypatch.setattr(
        benchmark.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            ["worker"], 0, "{}\nextra\n", ""
        ),
    )
    with pytest.raises(RuntimeError, match="one JSON object"):
        run_benchmark(_reduced_protocol(validation_path), broken_output)
    assert not broken_output.exists()


def test_worker_smoke_reports_warmup_affinity_rss_and_timed_work(tmp_path: Path):
    cache = tmp_path / "cache"
    cache.mkdir()
    command = [
        sys.executable,
        "-m",
        "long_range_percolation.benchmark",
        "--worker-mode",
        "steady",
        "--backend",
        "poisson-numba",
        "--length",
        "8",
        "--sigma-hex",
        float(1.0).hex(),
        "--kappas-hex",
        ",".join(value.hex() for value in (0.25, 0.5)),
        "--run-id",
        "smoke",
    ]
    env = os.environ.copy() | benchmark.ONE_THREAD_ENVIRONMENT
    env["NUMBA_CACHE_DIR"] = str(cache)
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    payload = json.loads(completed.stdout)
    assert payload["warmup"] == {
        "length": 2,
        "completed_before_timing": True,
    }
    assert payload["selected_cpu"] in payload["affinity"]
    assert payload["peak_rss_bytes"] > 0
    assert payload["metrics"]["events"] >= payload["metrics"]["unique_edges"]
    assert payload["metrics"]["unique_edges"] >= payload["metrics"]["unions"]
    assert payload["metrics"]["duplicates"] == (
        payload["metrics"]["events"] - payload["metrics"]["unique_edges"]
    )
    assert payload["timings_ns"]["wall"] >= (
        payload["timings_ns"]["sampling"]
        + payload["timings_ns"]["observable"]
        + payload["timings_ns"]["artifact_serialization"]
    )
