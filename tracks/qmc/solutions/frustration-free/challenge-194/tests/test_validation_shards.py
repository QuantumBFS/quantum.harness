from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

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
    merge_validation_shards,
    run_validation_cell,
    run_validation_global_checks,
    write_validation_run_spec,
)


SOLUTION = Path(__file__).resolve().parents[1]
SCRIPT = SOLUTION / "scripts" / "validation_shard.py"
WRAPPER = SOLUTION / "scripts" / "validation_array_slurm.sh"


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
    write_validation_run_spec(_protocol(), root, run_spec_path)
    run_validation_global_checks(run_spec_path)
    for index in order:
        run_validation_cell(run_spec_path, index)
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


def test_serial_and_sharded_scientific_reports_are_canonical_equal(tmp_path: Path):
    protocol = _protocol()
    serial = run_production_validation(protocol, tmp_path / "serial.json")
    run_spec_path, _ = _prepare(tmp_path)
    sharded = merge_validation_shards(run_spec_path, tmp_path / "merged.json")
    assert payload_without_elapsed(serial) == payload_without_elapsed(sharded)
    assert canonical_scientific_report_bytes(serial) == (
        canonical_scientific_report_bytes(sharded)
    )
    assert (tmp_path / "merged.json").read_bytes() == canonical_report_bytes(sharded)


def test_cell_order_does_not_change_merged_scientific_report(tmp_path: Path):
    first_path, _ = _prepare(tmp_path / "first", order=(0, 1))
    second_path, _ = _prepare(tmp_path / "second", order=(1, 0))
    first = merge_validation_shards(first_path, tmp_path / "first.json")
    second = merge_validation_shards(second_path, tmp_path / "second.json")
    assert canonical_scientific_report_bytes(first) == (
        canonical_scientific_report_bytes(second)
    )


def test_process_scheduling_order_is_invariant(tmp_path: Path):
    reports = []
    for name, order in (("forward", (0, 1)), ("reverse", (1, 0))):
        root = tmp_path / name
        spec_path = root / "run_spec.json"
        write_validation_run_spec(_protocol(), root, spec_path)
        run_validation_global_checks(spec_path)
        for index in order:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from pathlib import Path;"
                        "from long_range_percolation.validation_shards "
                        "import run_validation_cell;"
                        f"run_validation_cell(Path({str(spec_path)!r}), {index})"
                    ),
                ],
                cwd=SOLUTION,
                capture_output=True,
                text=True,
            )
            assert completed.returncode == 0, completed.stderr
        reports.append(
            merge_validation_shards(spec_path, tmp_path / f"{name}.json")
        )
    assert canonical_scientific_report_bytes(reports[0]) == (
        canonical_scientific_report_bytes(reports[1])
    )


def test_valid_cell_is_idempotent_and_never_overwritten(tmp_path: Path):
    root = tmp_path / "idempotent"
    spec_path = root / "run_spec.json"
    write_validation_run_spec(_protocol(), root, spec_path)
    first = run_validation_cell(spec_path, 0)
    partial = root / first["partial_path"]
    before = partial.stat().st_mtime_ns
    second = run_validation_cell(spec_path, 0)
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
        merge_validation_shards(spec_path, tmp_path / "forbidden.json")
    assert not (tmp_path / "forbidden.json").exists()


def test_atomic_crash_before_cell_rename_leaves_no_valid_partial(tmp_path: Path):
    root = tmp_path / "crash"
    spec_path = root / "run_spec.json"
    write_validation_run_spec(_protocol(), root, spec_path)

    def crash(stage: str) -> None:
        if stage == "before-artifact-rename":
            raise RuntimeError("injected crash")

    with pytest.raises(RuntimeError, match="injected crash"):
        run_validation_cell(spec_path, 0, crash_hook=crash)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    assert not (root / spec["cells"][0]["partial_path"]).exists()
    assert not (root / spec["cells"][0]["manifest_path"]).exists()
    run_validation_cell(spec_path, 0)


def test_missing_manifest_is_restartable_without_overwriting_partial(tmp_path: Path):
    spec_path, spec = _prepare(tmp_path)
    root = spec_path.parent
    cell = spec["cells"][0]
    partial = root / cell["partial_path"]
    manifest = root / cell["manifest_path"]
    before = partial.stat().st_mtime_ns
    manifest.unlink()
    run_validation_cell(spec_path, 0)
    assert manifest.is_file()
    assert partial.stat().st_mtime_ns == before


def test_cli_exit_codes_for_build_cell_global_and_merge(tmp_path: Path):
    root = tmp_path / "cli"
    spec_path = root / "run_spec.json"
    build = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "build-spec",
            "--protocol",
            "production-v1",
            "--output-root",
            str(root),
            "--run-spec",
            str(spec_path),
        ],
        cwd=SOLUTION,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr
    bad_cell = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "run-cell",
            "--run-spec",
            str(spec_path),
            "--case-index",
            "120",
        ],
        cwd=SOLUTION,
        capture_output=True,
        text=True,
    )
    assert bad_cell.returncode != 0
    missing_merge = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "merge",
            "--run-spec",
            str(spec_path),
            "--output",
            str(root / "report.json"),
        ],
        cwd=SOLUTION,
        capture_output=True,
        text=True,
    )
    assert missing_merge.returncode != 0
    assert not (root / "report.json").exists()

    reduced_root = tmp_path / "reduced-cli"
    reduced_spec = reduced_root / "run_spec.json"
    write_validation_run_spec(_protocol(), reduced_root, reduced_spec)
    commands = [["run-global", "--run-spec", str(reduced_spec)]]
    commands.extend(
        [
            "run-cell",
            "--run-spec",
            str(reduced_spec),
            "--case-index",
            str(index),
        ]
        for index in range(2)
    )
    for arguments in commands:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            cwd=SOLUTION,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
    passing_output = reduced_root / "report.json"
    passing_merge = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "merge",
            "--run-spec",
            str(reduced_spec),
            "--output",
            str(passing_output),
        ],
        cwd=SOLUTION,
        capture_output=True,
        text=True,
    )
    assert passing_merge.returncode == 0, passing_merge.stderr
    assert json.loads(passing_output.read_text(encoding="utf-8"))["passed"] is True


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
        "'openblas': os.environ['OPENBLAS_NUM_THREADS']}))\n"
        "PY\n",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)
    (tmp_path / "run_spec.json").write_text("{}", encoding="utf-8")
    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "HARNESS_RUN_SPEC": str(tmp_path / "run_spec.json"),
        "SLURM_ARRAY_TASK_ID": "17",
        "CHALLENGE_194_REPO_ROOT": str(Path(__file__).parents[6]),
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
    assert recorded["args"][-2:] == ["--case-index", "17"]
    assert "17" in completed.stdout


def test_generated_shard_results_are_ignored(tmp_path: Path):
    repository = Path(__file__).parents[6]
    candidate = (
        repository
        / "tracks"
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
