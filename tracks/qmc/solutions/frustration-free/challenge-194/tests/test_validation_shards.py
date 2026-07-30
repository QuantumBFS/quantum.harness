from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

import long_range_percolation.validation as validation_module
import long_range_percolation.validation_shards as shards
from long_range_percolation.validation import (
    ValidationProtocol,
    canonical_report_bytes,
    payload_without_elapsed,
    run_production_validation,
)
from long_range_percolation.validation_shards import (
    RUN_SPEC_SCHEMA,
    build_validation_run_spec,
    canonical_scientific_report_bytes,
)


SOLUTION = Path(__file__).resolve().parents[1]
SCRIPT = SOLUTION / "scripts" / "validation_shard.py"
WRAPPER = SOLUTION / "scripts" / "validation_array_slurm.sh"
CLI_SPEC = importlib.util.spec_from_file_location("validation_shard_cli", SCRIPT)
assert CLI_SPEC is not None and CLI_SPEC.loader is not None
CLI = importlib.util.module_from_spec(CLI_SPEC)
CLI_SPEC.loader.exec_module(CLI)


@pytest.fixture(autouse=True)
def clean_source(monkeypatch: pytest.MonkeyPatch):
    revision = validation_module._repository_state()["source_revision"]
    source = {
        "source_revision": revision,
        "clean_tree": True,
        "provenance_error": None,
    }
    monkeypatch.setattr(shards, "_repository_state", lambda: source)
    monkeypatch.setattr(validation_module, "_repository_state", lambda: source)


def _protocol(jobs: int = 1) -> ValidationProtocol:
    return ValidationProtocol.reduced(
        lengths=(4,),
        sigmas=(1.0,),
        kappas=(0.0, 0.25),
        samples=4,
        replicates=7,
        jobs=jobs,
    )


def _prepare(
    tmp_path: Path,
    *,
    order: tuple[int, ...] = (0, 1),
) -> tuple[Path, dict[str, object]]:
    root = tmp_path / "shards"
    run_spec_path = root / "run_spec.json"
    shards._write_test_run_spec(_protocol(), root, run_spec_path)
    shards._run_test_global_checks(run_spec_path)
    for index in order:
        shards._run_test_cell(run_spec_path, index)
    return run_spec_path, json.loads(run_spec_path.read_text(encoding="utf-8"))


def test_production_run_spec_has_exact_120_opaque_cells(tmp_path: Path):
    spec = build_validation_run_spec(
        ValidationProtocol.production_v1(), tmp_path / "production"
    )
    assert spec["schema_version"] == RUN_SPEC_SCHEMA
    assert len(spec["cells"]) == 120
    assert [cell["case_index"] for cell in spec["cells"]] == list(range(120))
    assert len({cell["case_id"] for cell in spec["cells"]}) == 120
    assert len({cell["cell_sha256"] for cell in spec["cells"]}) == 120
    assert all(cell["partial_path"].startswith("cells/") for cell in spec["cells"])
    assert all(
        cell["manifest_path"].startswith("manifests/") for cell in spec["cells"]
    )
    assert spec["protocol"]["name"] == "production-v1"
    assert spec["protocol"]["sha256"]
    assert spec["source_revision"]
    assert spec["runtime_capability_sha256"]
    assert spec["uv_lock_sha256"]
    assert len(spec["global_expected_checks"]) == 15
    assert all(
        check["scope"] == "global" and check["case_id"] is None
        for check in spec["global_expected_checks"]
    )
    all_check_ids = [
        check["check_id"] for check in spec["global_expected_checks"]
    ]
    for cell in spec["cells"]:
        assert cell["expected_checks"]
        assert all(
            check["scope"] == "cell"
            and check["case_id"] == cell["case_id"]
            for check in cell["expected_checks"]
        )
        all_check_ids.extend(
            check["check_id"] for check in cell["expected_checks"]
        )
    assert len(all_check_ids) == len(set(all_check_ids))


def test_serial_and_sharded_scientific_reports_are_canonical_equal(tmp_path: Path):
    protocol = _protocol()
    serial = run_production_validation(protocol, tmp_path / "serial.json")
    run_spec_path, _ = _prepare(tmp_path)
    sharded = shards._merge_test_shards(run_spec_path)
    assert payload_without_elapsed(serial) == payload_without_elapsed(sharded)
    assert canonical_scientific_report_bytes(serial) == (
        canonical_scientific_report_bytes(sharded)
    )
    assert (
        run_spec_path.parent / "report" / "report.json"
    ).read_bytes() == canonical_report_bytes(sharded)


def test_cell_order_does_not_change_merged_scientific_report(tmp_path: Path):
    first_path, _ = _prepare(tmp_path / "first", order=(0, 1))
    second_path, _ = _prepare(tmp_path / "second", order=(1, 0))
    first = shards._merge_test_shards(first_path)
    second = shards._merge_test_shards(second_path)
    assert canonical_scientific_report_bytes(first) == (
        canonical_scientific_report_bytes(second)
    )


def test_process_scheduling_order_is_invariant(tmp_path: Path):
    reports = []
    revision = validation_module._repository_state()["source_revision"]
    for name, order in (("forward", (0, 1)), ("reverse", (1, 0))):
        root = tmp_path / name
        spec_path = root / "run_spec.json"
        shards._write_test_run_spec(_protocol(), root, spec_path)
        shards._run_test_global_checks(spec_path)
        for index in order:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from pathlib import Path;"
                        "import long_range_percolation.validation_shards as s;"
                        f"s._repository_state=lambda:{{'source_revision':"
                        f"{revision!r},'clean_tree':True,"
                        "'provenance_error':None};"
                        f"s._run_test_cell(Path({str(spec_path)!r}), {index})"
                    ),
                ],
                cwd=SOLUTION,
                capture_output=True,
                text=True,
            )
            assert completed.returncode == 0, completed.stderr
        reports.append(
            shards._merge_test_shards(spec_path)
        )
    assert canonical_scientific_report_bytes(reports[0]) == (
        canonical_scientific_report_bytes(reports[1])
    )


def test_valid_cell_is_idempotent_and_never_overwritten(tmp_path: Path):
    root = tmp_path / "idempotent"
    spec_path = root / "run_spec.json"
    shards._write_test_run_spec(_protocol(), root, spec_path)
    first = shards._run_test_cell(spec_path, 0)
    partial = root / first["partial_path"]
    before = partial.stat().st_mtime_ns
    second = shards._run_test_cell(spec_path, 0)
    assert second == first
    assert partial.stat().st_mtime_ns == before


@pytest.mark.parametrize(
    "failure", ("missing", "corrupt", "stale", "extra", "extra-dir")
)
def test_merge_rejects_incomplete_or_noncanonical_cell_sets(
    tmp_path: Path, failure: str
):
    spec_path, spec = _prepare(tmp_path)
    root = spec_path.parent
    cell = spec["cells"][0]
    partial = root / cell["partial_path"]
    if failure == "missing":
        partial.unlink()
    elif failure == "corrupt":
        partial.write_text("{broken", encoding="utf-8")
    elif failure == "stale":
        document = json.loads(partial.read_text(encoding="utf-8"))
        document["protocol_sha256"] = "0" * 64
        partial.write_text(json.dumps(document), encoding="utf-8")
    elif failure == "extra":
        (root / "cells" / "extra.json").write_text("{}", encoding="utf-8")
    else:
        (root / "cells" / "unexpected").mkdir()
    with pytest.raises(RuntimeError):
        shards._merge_test_shards(spec_path)
    assert not (tmp_path / "forbidden.json").exists()


def test_atomic_crash_before_cell_rename_leaves_no_valid_partial(tmp_path: Path):
    root = tmp_path / "crash"
    spec_path = root / "run_spec.json"
    shards._write_test_run_spec(_protocol(), root, spec_path)

    def crash(stage: str) -> None:
        if stage == "before-artifact-rename":
            raise RuntimeError("injected crash")

    with pytest.raises(RuntimeError, match="injected crash"):
        shards._run_test_cell(spec_path, 0, crash_hook=crash)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    assert not (root / spec["cells"][0]["partial_path"]).exists()
    assert not (root / spec["cells"][0]["manifest_path"]).exists()
    shards._run_test_cell(spec_path, 0)


def test_missing_manifest_is_restartable_without_overwriting_partial(tmp_path: Path):
    spec_path, spec = _prepare(tmp_path)
    root = spec_path.parent
    cell = spec["cells"][0]
    partial = root / cell["partial_path"]
    manifest = root / cell["manifest_path"]
    before = partial.stat().st_mtime_ns
    manifest.unlink()
    shards._run_test_cell(spec_path, 0)
    assert manifest.is_file()
    assert partial.stat().st_mtime_ns == before


def test_cli_exit_codes_for_build_cell_global_and_merge(tmp_path: Path):
    root = tmp_path / "cli"
    spec_path = root / "run_spec.json"
    build = CLI.main(
        [
            "build-spec",
            "--protocol",
            "production-v1",
            "--output-root",
            str(root),
            "--run-spec",
            str(spec_path),
        ]
    )
    assert build == 0
    bad_cell = CLI.main(
        [
            "run-cell",
            "--run-spec",
            str(spec_path),
            "--case-index",
            "120",
        ]
    )
    assert bad_cell != 0
    missing_merge = CLI.main(
        [
            "merge",
            "--run-spec",
            str(spec_path),
            "--output",
            str(root / "report" / "report.json"),
        ],
    )
    assert missing_merge != 0
    assert not (root / "report" / "report.json").exists()


def test_spool_copied_slurm_wrapper_uses_explicit_solution_root(tmp_path: Path):
    spool = tmp_path / "slurm-spool-copy.sh"
    shutil.copy2(WRAPPER, spool)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    invocation = tmp_path / "invocation.json"
    fake_uv = bindir / "uv"
    fake_uv.write_text(
        "#!/bin/bash\n"
        "python3 - \"$@\" <<'PY'\n"
        "import json, os, sys\n"
        f"open({str(invocation)!r}, 'w').write(json.dumps({{'cwd': os.getcwd(), "
        "'args': sys.argv[1:], 'omp': os.environ['OMP_NUM_THREADS'], "
        "'openblas': os.environ['OPENBLAS_NUM_THREADS'], "
        "'pythonpath': os.environ.get('PYTHONPATH')}))\n"
        "PY\n",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)
    (tmp_path / "run_spec.json").write_text("{}", encoding="utf-8")
    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "HARNESS_RUN_SPEC": str(tmp_path / "run_spec.json"),
        "HARNESS_ENTRYPOINT": str(Path(__file__).parents[6]),
        "SLURM_ARRAY_TASK_ID": "17",
        "PYTHONPATH": "/caller/uv/path",
    }
    completed = subprocess.run(
        ["/bin/bash", str(spool)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    recorded = json.loads(invocation.read_text(encoding="utf-8"))
    assert recorded["cwd"] == str(SOLUTION)
    assert recorded["omp"] == "1"
    assert recorded["openblas"] == "1"
    assert recorded["pythonpath"] == "/caller/uv/path"
    assert recorded["args"][:3] == [
        "run",
        "scripts/validation_shard.py",
        "run-cell",
    ]
    assert recorded["args"][-2:] == ["--case-index", "17"]
    assert "17" in completed.stdout


def _offline_wrapper_environment(
    tmp_path: Path,
    *,
    python: Path | str,
) -> tuple[Path, Path, dict[str, str]]:
    spool = tmp_path / "slurm-spool-copy.sh"
    shutil.copy2(WRAPPER, spool)
    invocation = tmp_path / "offline-invocation.json"
    run_spec = tmp_path / "run_spec.json"
    run_spec.write_text("{}", encoding="utf-8")
    environment = {
        **os.environ,
        "PATH": "/usr/bin:/bin",
        "HARNESS_RUN_SPEC": str(run_spec),
        "HARNESS_ENTRYPOINT": str(Path(__file__).parents[6]),
        "SLURM_ARRAY_TASK_ID": "23",
        "CHALLENGE_194_PYTHON": str(python),
        "PYTHONPATH": "/hostile/caller/path",
        "OFFLINE_INVOCATION": str(invocation),
    }
    return spool, invocation, environment


def test_spool_wrapper_uses_direct_offline_interpreter_and_clean_pythonpath(
    tmp_path: Path,
):
    interpreter = tmp_path / "offline-python"
    interpreter.write_text(
        "#!/bin/bash\n"
        "/usr/bin/python3 - \"$@\" <<'PY'\n"
        "import json, os, sys\n"
        "with open(os.environ['OFFLINE_INVOCATION'], 'w') as stream:\n"
        "    json.dump({'args': sys.argv[1:], "
        "'pythonpath': os.environ.get('PYTHONPATH')}, stream)\n"
        "PY\n",
        encoding="utf-8",
    )
    interpreter.chmod(0o755)
    spool, invocation, environment = _offline_wrapper_environment(
        tmp_path, python=interpreter
    )
    completed = subprocess.run(
        ["/bin/bash", str(spool)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    recorded = json.loads(invocation.read_text(encoding="utf-8"))
    assert recorded["args"] == [
        "scripts/validation_shard.py",
        "run-cell",
        "--run-spec",
        str(tmp_path / "run_spec.json"),
        "--case-index",
        "23",
    ]
    assert recorded["pythonpath"] == str(SOLUTION / "src")
    assert "/hostile/caller/path" not in recorded["pythonpath"]


def test_spool_wrapper_isolates_numba_cache_per_array_cell(tmp_path: Path):
    interpreter = tmp_path / "offline-python"
    interpreter.write_text(
        "#!/bin/bash\n"
        "/usr/bin/python3 - \"$@\" <<'PY'\n"
        "import json, os\n"
        "with open(os.environ['OFFLINE_INVOCATION'], 'w') as stream:\n"
        "    json.dump({'numba_cache_dir': os.environ.get('NUMBA_CACHE_DIR')}, stream)\n"
        "PY\n",
        encoding="utf-8",
    )
    interpreter.chmod(0o755)
    spool, invocation, environment = _offline_wrapper_environment(
        tmp_path, python=interpreter
    )
    node_local = tmp_path / "node-local"
    node_local.mkdir()
    environment["SLURM_TMPDIR"] = str(node_local)
    environment["SLURM_ARRAY_JOB_ID"] = "12345"
    environment["SLURM_ARRAY_TASK_ID"] = "23"

    completed = subprocess.run(
        ["/bin/bash", str(spool)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    recorded = json.loads(invocation.read_text(encoding="utf-8"))
    expected = node_local / "challenge-194-numba-12345-23"
    assert recorded["numba_cache_dir"] == str(expected)
    assert expected.is_dir()


def test_spool_wrapper_preserves_venv_launcher_identity(tmp_path: Path):
    venv = tmp_path / "worker-venv"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "venv",
            "--without-pip",
            "--system-site-packages",
            str(venv),
        ],
        check=True,
    )
    launcher = venv / "bin" / "python"
    resolved = launcher.resolve()
    assert launcher != resolved

    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    site_packages = venv / "lib" / version / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)
    (site_packages / "wrapper_venv_marker.py").write_text(
        "VALUE = 'venv-site-packages'\n",
        encoding="utf-8",
    )

    repository = tmp_path / "repository"
    solution = (
        repository
        / "tracks"
        / "qmc"
        / "solutions"
        / "frustration-free"
        / "challenge-194"
    )
    scripts = solution / "scripts"
    scripts.mkdir(parents=True)
    invocation = tmp_path / "venv-invocation.json"
    (scripts / "validation_shard.py").write_text(
        "import json, os, sys\n"
        "import wrapper_venv_marker\n"
        "with open(os.environ['OFFLINE_INVOCATION'], 'w') as stream:\n"
        "    json.dump({\n"
        "        'executable': sys.executable,\n"
        "        'prefix': sys.prefix,\n"
        "        'marker': wrapper_venv_marker.VALUE,\n"
        "        'pythonpath': os.environ.get('PYTHONPATH'),\n"
        "    }, stream)\n",
        encoding="utf-8",
    )
    run_spec = tmp_path / "run_spec.json"
    run_spec.write_text("{}", encoding="utf-8")
    environment = {
        **os.environ,
        "PATH": "/usr/bin:/bin",
        "HARNESS_RUN_SPEC": str(run_spec),
        "CHALLENGE_194_REPO_ROOT": str(repository),
        "SLURM_ARRAY_TASK_ID": "23",
        "CHALLENGE_194_PYTHON": str(launcher),
        "PYTHONPATH": "/hostile/caller/path",
        "OFFLINE_INVOCATION": str(invocation),
    }

    completed = subprocess.run(
        ["/bin/bash", str(WRAPPER)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    recorded = json.loads(invocation.read_text(encoding="utf-8"))
    assert recorded == {
        "executable": str(launcher),
        "prefix": str(venv),
        "marker": "venv-site-packages",
        "pythonpath": str(solution / "src"),
    }


def test_spool_wrapper_uses_valid_harness_command_as_interpreter(tmp_path: Path):
    interpreter = tmp_path / "harness-python"
    interpreter.write_text(
        "#!/bin/bash\n"
        "/usr/bin/python3 - \"$@\" <<'PY'\n"
        "import json, os, sys\n"
        "with open(os.environ['OFFLINE_INVOCATION'], 'w') as stream:\n"
        "    json.dump({'args': sys.argv[1:]}, stream)\n"
        "PY\n",
        encoding="utf-8",
    )
    interpreter.chmod(0o755)
    spool, invocation, environment = _offline_wrapper_environment(
        tmp_path, python=interpreter
    )
    environment.pop("CHALLENGE_194_PYTHON")
    environment["HARNESS_COMMAND"] = str(interpreter)
    completed = subprocess.run(
        ["/bin/bash", str(spool)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    recorded = json.loads(invocation.read_text(encoding="utf-8"))
    assert recorded["args"][0:2] == [
        "scripts/validation_shard.py",
        "run-cell",
    ]


def test_offline_interpreter_rejects_conflicting_explicit_candidates(
    tmp_path: Path,
):
    challenge_python = tmp_path / "challenge-python"
    harness_python = tmp_path / "harness-python"
    for interpreter in (challenge_python, harness_python):
        interpreter.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
        interpreter.chmod(0o755)
    spool, invocation, environment = _offline_wrapper_environment(
        tmp_path, python=challenge_python
    )
    environment["HARNESS_COMMAND"] = str(harness_python)
    completed = subprocess.run(
        ["/bin/bash", str(spool)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "conflict" in completed.stderr
    assert not invocation.exists()


def test_offline_interpreter_rejects_distinct_launchers_with_same_target(
    tmp_path: Path,
):
    interpreter = tmp_path / "offline-python"
    interpreter.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    interpreter.chmod(0o755)
    alias = tmp_path / "python-alias"
    alias.symlink_to(interpreter)
    spool, _, environment = _offline_wrapper_environment(
        tmp_path, python=alias
    )
    environment["HARNESS_COMMAND"] = str(interpreter)
    completed = subprocess.run(
        ["/bin/bash", str(spool)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "conflict" in completed.stderr


def test_offline_interpreter_may_be_valid_absolute_symlink(tmp_path: Path):
    interpreter = tmp_path / "offline-python"
    interpreter.write_text(
        "#!/bin/bash\nexit 0\n",
        encoding="utf-8",
    )
    interpreter.chmod(0o755)
    alias = tmp_path / "python-alias"
    alias.symlink_to(interpreter)
    spool, _, environment = _offline_wrapper_environment(
        tmp_path, python=alias
    )
    completed = subprocess.run(
        ["/bin/bash", str(spool)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    "kind",
    ("relative", "missing", "directory", "non-executable", "broken-symlink"),
)
def test_offline_interpreter_fails_closed_when_invalid(
    tmp_path: Path,
    kind: str,
):
    candidate = tmp_path / "candidate"
    if kind == "relative":
        python: Path | str = "relative/python"
    elif kind == "missing":
        python = candidate
    elif kind == "directory":
        candidate.mkdir()
        python = candidate
    elif kind == "non-executable":
        candidate.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
        candidate.chmod(0o644)
        python = candidate
    else:
        candidate.symlink_to(tmp_path / "absent-target")
        python = candidate
    spool, invocation, environment = _offline_wrapper_environment(
        tmp_path, python=python
    )
    completed = subprocess.run(
        ["/bin/bash", str(spool)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "CHALLENGE_194_PYTHON" in completed.stderr
    assert not invocation.exists()


def test_generated_shard_results_are_ignored(tmp_path: Path):
    repository = Path(__file__).parents[6]
    candidate = (
        repository
        / "tracks"
        / "qmc"
        / "results"
        / "frustration-free"
        / "challenge-194"
        / "validation-sharded"
        / "run_spec.json"
    )
    completed = subprocess.run(
        ["git", "check-ignore", str(candidate)],
        cwd=repository,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
