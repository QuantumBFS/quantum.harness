from __future__ import annotations

import ast
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
import numpy as np

import long_range_percolation.validation as validation
from long_range_percolation.trajectory import (
    TrajectoryDiagnostics,
    TrajectoryRequest,
    TrajectoryResult,
)
from long_range_percolation.validation import (
    FAMILYWISE_ALPHA,
    KAPPAS,
    LENGTHS,
    MASTER_SEEDS,
    SAMPLES_BY_LENGTH,
    SAMPLERS,
    SIGMAS,
    VALIDATION_PROTOCOL_VERSION,
    ValidationProtocol,
    canonical_report_bytes,
    run_production_validation,
)


def test_production_protocol_is_exactly_frozen():
    protocol = ValidationProtocol.production_v1()
    assert VALIDATION_PROTOCOL_VERSION == "challenge-194-validation-v1"
    assert FAMILYWISE_ALPHA == 0.001
    assert LENGTHS == (4, 6, 8, 16, 32, 64, 128, 256)
    assert SIGMAS == (0.8, 1.0, 1.1)
    assert KAPPAS == (0.0, 0.25, 0.7, 2.0, 6.0)
    assert SAMPLES_BY_LENGTH == {
        4: 32768,
        6: 32768,
        8: 32768,
        16: 16384,
        32: 8192,
        64: 4096,
        128: 2048,
        256: 1024,
    }
    assert SAMPLERS == (
        "quadratic",
        "geometric",
        "poisson-reference",
        "poisson-numba",
    )
    assert MASTER_SEEDS == tuple(range(194_000_000, 194_032_768))
    assert protocol.is_production
    assert protocol.permutation_replicates == 49_999
    assert protocol.multinomial_replicates == 49_999


def test_registry_denominators_are_frozen_before_sampling():
    protocol = ValidationProtocol.production_v1()
    registry = protocol.case_registry
    assert len(registry) == len(LENGTHS) * len(SIGMAS) * len(KAPPAS)
    assert registry[0].case_id == "L4/sigma-0x1.999999999999ap-1/kappa-0x0.0p+0"
    assert registry[-1].case_id == "L256/sigma-0x1.199999999999ap+0/kappa-0x1.8000000000000p+2"
    assert protocol.family_denominators == validation.frozen_family_denominators(
        LENGTHS, SIGMAS, KAPPAS
    )
    assert set(protocol.family_denominators) == set(validation.STATISTICAL_FAMILIES)
    assert all(value > 0 for value in protocol.family_denominators.values())


def test_reduced_constructor_cannot_masquerade_as_production():
    protocol = ValidationProtocol.reduced(
        lengths=(4,),
        sigmas=(1.0,),
        kappas=(0.0, 0.25),
        samples=4,
        replicates=7,
    )
    assert not protocol.is_production
    assert protocol.samples_by_length == {4: 4}
    assert protocol.permutation_replicates == 7
    assert protocol.multinomial_replicates == 7
    with pytest.raises(ValueError, match="production"):
        protocol.require_production()


def test_reduced_gate_writes_complete_canonical_report(tmp_path: Path):
    protocol = ValidationProtocol.reduced(
        lengths=(4,),
        sigmas=(1.0,),
        kappas=(0.0, 0.25),
        samples=8,
        replicates=31,
    )
    output = tmp_path / "nested" / "report.json"
    report = run_production_validation(protocol, output)
    assert output.read_bytes() == canonical_report_bytes(report)
    assert json.loads(output.read_bytes()) == report
    assert report["schema_version"] == VALIDATION_PROTOCOL_VERSION
    assert report["protocol"]["familywise_alpha"] == FAMILYWISE_ALPHA.hex()
    assert report["protocol"]["family_denominators"] == protocol.family_denominators
    assert report["family_count"] == len({item["family"] for item in report["checks"]})
    assert report["minimum_margin"] == min(
        float(item["margin"]) for item in report["checks"]
    )
    required = {
        "family",
        "case_id",
        "raw",
        "expected",
        "threshold",
        "margin",
        "passed",
    }
    assert report["checks"]
    assert all(required <= set(item) for item in report["checks"])
    assert all(isinstance(item["passed"], bool) for item in report["checks"])
    assert report["passed"] == all(item["passed"] for item in report["checks"])


def test_jobs_change_scheduling_only(tmp_path: Path):
    base = ValidationProtocol.reduced(
        lengths=(4,),
        sigmas=(1.0,),
        kappas=(0.0,),
        samples=2,
        replicates=3,
    )
    serial = run_production_validation(replace(base, jobs=1), tmp_path / "one.json")
    parallel = run_production_validation(replace(base, jobs=2), tmp_path / "two.json")
    assert validation.payload_without_elapsed(serial) == validation.payload_without_elapsed(
        parallel
    )


def test_backend_exception_is_published_as_failed_check(monkeypatch, tmp_path: Path):
    protocol = ValidationProtocol.reduced(
        lengths=(4,),
        sigmas=(1.0,),
        kappas=(0.25,),
        samples=2,
        replicates=3,
    )

    def broken(*args, **kwargs):
        raise RuntimeError("malformed backend")

    monkeypatch.setattr(validation, "run_poisson_numba", broken)
    report = run_production_validation(protocol, tmp_path / "failure.json")
    failures = [item for item in report["checks"] if not item["passed"]]
    assert not report["passed"]
    assert any(item["family"] == "backend-integrity" for item in failures)
    assert all(float(item["margin"]) < 0.0 for item in failures)


def test_report_publication_rejects_symlinks(tmp_path: Path):
    target = tmp_path / "target.json"
    target.write_text("unchanged", encoding="utf-8")
    output = tmp_path / "report.json"
    output.symlink_to(target)
    protocol = ValidationProtocol.reduced(
        lengths=(4,),
        sigmas=(1.0,),
        kappas=(0.0,),
        samples=1,
        replicates=1,
    )
    with pytest.raises(RuntimeError, match="symlink"):
        run_production_validation(protocol, output)
    assert target.read_text(encoding="utf-8") == "unchanged"


def test_sampler_modules_are_structurally_independent():
    root = Path(validation.__file__).parent
    modules = ("oracle.py", "geometric.py", "poisson_reference.py", "poisson_sweep.py")
    names = {Path(item).stem for item in modules}
    imports: dict[str, set[str]] = {}
    for filename in modules:
        tree = ast.parse((root / filename).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.rsplit(".", 1)[-1])
            elif isinstance(node, ast.Import):
                imported.update(alias.name.rsplit(".", 1)[-1] for alias in node.names)
        imports[Path(filename).stem] = imported & names
    assert imports["oracle"] == set()
    assert imports["geometric"] == set()
    assert imports["poisson_reference"] == set()
    assert imports["poisson_sweep"] == set()
    assert validation.assert_sampler_structure() is None


def test_sampler_import_graph_has_no_sampler_specific_paths():
    root = Path(validation.__file__).parent
    samplers = {"oracle", "geometric", "poisson_reference", "poisson_sweep"}
    module_names = {item.stem for item in root.glob("*.py")}
    graph: dict[str, set[str]] = {}
    for source in root.glob("*.py"):
        imported: set[str] = set()
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.rsplit(".", 1)[-1])
        graph[source.stem] = imported & module_names
    for source in samplers:
        pending = list(graph.get(source, ()))
        visited: set[str] = set()
        while pending:
            target = pending.pop()
            if target in visited:
                continue
            visited.add(target)
            assert target not in samplers - {source}
            pending.extend(graph.get(target, ()))


def test_neutral_trajectory_contracts_preserve_reference_reexports():
    from long_range_percolation.poisson_reference import (
        TrajectoryDiagnostics as ReferenceDiagnostics,
        TrajectoryRequest as ReferenceRequest,
        TrajectoryResult as ReferenceResult,
    )

    assert ReferenceRequest is TrajectoryRequest
    assert ReferenceResult is TrajectoryResult
    assert ReferenceDiagnostics is TrajectoryDiagnostics


def test_validation_observables_ignore_absent_union_find_labels():
    edges = np.asarray(((0, 1), (1, 2)), dtype=np.int64)
    labels = np.asarray((0, 0, 0, 3), dtype=np.int64)
    observed = validation._graph_observables(4, edges, labels)
    assert observed[1] == 2.0
    assert observed[2] == 3.0
    assert observed[3] == 1.0


def test_four_backends_are_frozen_into_every_applicable_family(tmp_path: Path):
    protocol = ValidationProtocol.reduced(
        lengths=(4,),
        sigmas=(1.0,),
        kappas=(0.25,),
        samples=8,
        replicates=31,
    )
    report = run_production_validation(protocol, tmp_path / "four-way.json")
    assert report["passed"]
    assert len(validation.PAIR_NAMES) == 6
    assert {
        pair
        for pair in validation.PAIR_NAMES
        if "poisson-reference" in pair
    } == {
        ("quadratic", "poisson-reference"),
        ("geometric", "poisson-reference"),
        ("poisson-reference", "poisson-numba"),
    }
    for family in (
        "all-graph-probability",
        "edge-class-frequency",
        "no-edge",
    ):
        case_ids = {
            check["case_id"]
            for check in report["checks"]
            if check["family"] == family
        }
        assert all(any(f"/{sampler}" in case_id for case_id in case_ids) for sampler in SAMPLERS)
    for family in (
        "bond-length",
        "component-partition",
        "open-count",
        "S1",
        "S2",
        "QG",
        "four-sector",
        "normalized-second-moment",
        "normalized-fourth-moment",
    ):
        checks = [check for check in report["checks"] if check["family"] == family]
        assert len(checks) == 6
        assert any("poisson-reference" in check["case_id"] for check in checks)


def test_component_partition_records_actual_descending_tuples(tmp_path: Path):
    protocol = ValidationProtocol.reduced(
        lengths=(4,),
        sigmas=(1.0,),
        kappas=(0.25,),
        samples=8,
        replicates=31,
    )
    report = run_production_validation(protocol, tmp_path / "partitions.json")
    checks = [
        check
        for check in report["checks"]
        if check["family"] == "component-partition"
    ]
    assert checks
    for check in checks:
        raw = check["raw"]
        assert raw["bins"]
        assert all(
            isinstance(item, list)
            and item == sorted(item, reverse=True)
            and sum(item) == 4
            for item in raw["bins"]
        )
        assert sum(raw["left_counts"]) == 8
        assert sum(raw["right_counts"]) == 8


def test_normalized_moment_schema_and_values_are_exact(tmp_path: Path):
    schema = validation.OBSERVABLE_SCHEMA
    assert schema["normalized-second-moment"] == {
        "formula": "sum_C(|C|^2)/L^2",
        "source_column": 6,
        "normalization_power": 2,
    }
    assert schema["normalized-fourth-moment"] == {
        "formula": "sum_C(|C|^4)/L^4",
        "source_column": 7,
        "normalization_power": 4,
    }
    raw = np.asarray((2.0, 0.0, 3.0, 1.0, 0.75, 0.25, 10.0, 82.0, 0.82, 0.0))
    assert validation._scalar_values(
        raw.reshape(1, -1), "normalized-second-moment", 4
    ).tolist() == [10.0 / 16.0]
    assert validation._scalar_values(
        raw.reshape(1, -1), "normalized-fourth-moment", 4
    ).tolist() == [82.0 / 256.0]
    report = run_production_validation(
        ValidationProtocol.reduced(
            lengths=(4,),
            sigmas=(1.0,),
            kappas=(0.25,),
            samples=4,
            replicates=7,
        ),
        tmp_path / "moments.json",
    )
    assert report["protocol"]["observable_schema"] == schema
    moment_check = next(
        check
        for check in report["checks"]
        if check["family"] == "normalized-second-moment"
    )
    assert "left_raw_sum" in moment_check["raw"]
    assert "right_raw_sum" in moment_check["raw"]


def test_malformed_python_reference_diagnostics_fail_closed(monkeypatch, tmp_path: Path):
    protocol = ValidationProtocol.reduced(
        lengths=(4,),
        sigmas=(1.0,),
        kappas=(0.25,),
        samples=2,
        replicates=3,
    )

    def malformed(*args, **kwargs):
        return SimpleNamespace(
            result=SimpleNamespace(
                observables=np.zeros((1, 9), dtype=np.float64),
                event_count=0,
                duplicate_count=0,
            ),
            edge_ids_by_checkpoint=(frozenset(),),
            event_times=(),
        )

    monkeypatch.setattr(
        validation, "run_poisson_reference_with_diagnostics", malformed
    )
    report = run_production_validation(protocol, tmp_path / "malformed-reference.json")
    assert not report["passed"]
    assert any(
        check["family"] == "backend-integrity"
        and "Python reference" in check["raw"]["error"]
        for check in report["checks"]
    )


def test_all_graph_exact_coverage_is_per_graph_and_four_backend(tmp_path: Path):
    report = run_production_validation(
        ValidationProtocol.reduced(
            lengths=(4,),
            sigmas=(1.0,),
            kappas=(0.25,),
            samples=8,
            replicates=31,
        ),
        tmp_path / "coverage.json",
    )
    exact = next(
        check
        for check in report["checks"]
        if check["family"] == "all-graph-exact"
    )
    assert exact["raw"]["coverage"]["L4"]["graph_count"] == 64
    assert exact["raw"]["coverage"]["L4"]["probabilities_compared"] == 64
    assert exact["raw"]["coverage"]["L4"]["maximum_product_error"] >= 0.0
    coverage = report["coverage"]["all_graph_probability"]
    assert coverage["backends"] == list(SAMPLERS)
    assert coverage["lengths"] == [4]
    assert coverage["comparison"] == "per-mask exact product-measure binomial"


def _minimal_cli_report(passed: bool = True) -> dict[str, object]:
    protocol = ValidationProtocol.production_v1()
    families = sorted(
        set(validation.EXACT_FAMILIES) | set(validation.STATISTICAL_FAMILIES)
    )
    checks = [
        {
            "family": family,
            "case_id": "cli-fixture",
            "raw": {"count": 1},
            "expected": {"count": 1},
            "threshold": 0.0,
            "margin": 0.0 if passed else -1.0,
            "passed": passed,
        }
        for family in families
    ]
    return {
        "schema_version": validation.VALIDATION_PROTOCOL_VERSION,
        "protocol": validation._protocol_document(protocol),
        "runtime_capability": {},
        "source": {},
        "coverage": {
            "all_graph_probability": {
                "backends": list(SAMPLERS),
                "lengths": [4, 6],
                "comparison": "per-mask exact product-measure binomial",
            }
        },
        "checks": checks,
        "family_count": len(families),
        "minimum_margin": 0.0 if passed else -1.0,
        "passed": passed,
        "elapsed_seconds": 0.0,
    }


def _run_cli_fixture(
    tmp_path: Path,
    report: dict[str, object] | None,
    *,
    backend_exception: bool = False,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    fixture = tmp_path / "fixture.json"
    if report is not None:
        fixture.write_bytes(validation.canonical_report_bytes(report))
    output = tmp_path / "cli-report.json"
    script = Path(__file__).parents[1] / "scripts" / "validate_production.py"
    code = """
import json
from pathlib import Path
import runpy
import sys
import long_range_percolation.validation as validation
fixture = Path(sys.argv[2])
backend_exception = sys.argv[4] == "1"
def fake(protocol, output):
    if backend_exception:
        raise RuntimeError("backend exploded")
    report = json.loads(fixture.read_text(encoding="utf-8"))
    output.write_bytes(validation.canonical_report_bytes(report))
    return report
validation.run_production_validation = fake
sys.argv = [sys.argv[1], "--protocol", "production-v1", "--jobs", "1", "--output", sys.argv[3]]
runpy.run_path(sys.argv[0], run_name="__main__")
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(script),
            str(fixture),
            str(output),
            "1" if backend_exception else "0",
        ],
        cwd=script.parents[1],
        env=dict(os.environ),
        capture_output=True,
        text=True,
    )
    return completed, output


def test_cli_subprocess_exit_zero_only_for_valid_passing_report(tmp_path: Path):
    completed, output = _run_cli_fixture(tmp_path, _minimal_cli_report())
    assert completed.returncode == 0, completed.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["passed"] is True


@pytest.mark.parametrize("failure", ("failed", "missing", "schema", "backend"))
def test_cli_subprocess_fails_closed_for_invalid_evidence(tmp_path: Path, failure: str):
    report = _minimal_cli_report(passed=failure != "failed")
    if failure == "missing":
        report["checks"] = report["checks"][1:]
        report["family_count"] -= 1
    elif failure == "schema":
        report["schema_version"] = "corrupt"
    completed, output = _run_cli_fixture(
        tmp_path,
        report,
        backend_exception=failure == "backend",
    )
    assert completed.returncode != 0
    if output.exists():
        assert json.loads(output.read_text(encoding="utf-8")).get("passed") is not True
