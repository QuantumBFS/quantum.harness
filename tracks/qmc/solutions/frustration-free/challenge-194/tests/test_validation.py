from __future__ import annotations

import ast
from dataclasses import replace
import json
from pathlib import Path

import pytest
import numpy as np

import long_range_percolation.validation as validation
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
    assert imports["poisson_sweep"] == {"poisson_reference"}
    assert validation.assert_sampler_structure() is None


def test_validation_observables_ignore_absent_union_find_labels():
    edges = np.asarray(((0, 1), (1, 2)), dtype=np.int64)
    labels = np.asarray((0, 0, 0, 3), dtype=np.int64)
    observed = validation._graph_observables(4, edges, labels)
    assert observed[1] == 2.0
    assert observed[2] == 3.0
    assert observed[3] == 1.0
