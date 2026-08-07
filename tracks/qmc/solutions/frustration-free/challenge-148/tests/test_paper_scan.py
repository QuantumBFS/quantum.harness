from __future__ import annotations

import copy
import hashlib
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pytest

from challenge148.paper_scan import build_paper_scan_plan, validate_paper_scan_plan
from challenge148.provenance import canonical_json


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION = ROOT / "preregistration" / "paper-scan-v1.json"
BUILD_INFO = {
    "adapter": "QMC_SSE",
    "source_hash": "a" * 64,
    "build_hash": "b" * 64,
}


def _preregistration() -> dict[str, object]:
    return json.loads(PREREGISTRATION.read_text(encoding="utf-8"))


def _rehash(plan: dict[str, object]) -> None:
    unsigned = copy.deepcopy(plan)
    unsigned.pop("plan_sha256", None)
    plan["plan_sha256"] = hashlib.sha256(canonical_json(unsigned)).hexdigest()


def test_paper_plan_expands_exact_decimal_140_cell_contract(tmp_path: Path):
    plan = build_paper_scan_plan(_preregistration(), BUILD_INFO, tmp_path)
    validate_paper_scan_plan(plan)

    assert plan["schema_version"] == "challenge148-paper-scan-plan-v1"
    assert plan["stage"] == "paper-aligned QMC_SSE finite-size reproduction"
    assert plan["allocation"] == {
        "adapter_timeout_seconds": 3600,
        "cores_per_cell": 2,
        "memory_mb_per_cell": 6000,
        "max_concurrency": 16,
    }
    cells = plan["cells"]
    assert len(cells) == 140
    assert len({cell["cell_id"] for cell in cells}) == 140
    assert len({cell["seed"] for cell in cells}) == 140
    assert all(cell["cell_id"].startswith("paper-") for cell in cells)

    expected_lengths = {
        "triangular": set(range(6, 21, 2)),
        "honeycomb": set(range(10, 21, 2)),
    }
    expected_factors = {"0.995", "0.9975", "1.0", "1.0025", "1.005"}
    observed_lengths = defaultdict(set)
    observed_factors = defaultdict(set)
    chains = defaultdict(set)
    for cell in cells:
        lattice = cell["lattice"]
        observed_lengths[lattice].add(cell["length"])
        observed_factors[lattice].add(cell["field_factor_decimal"])
        coordinate = (
            lattice,
            cell["length"],
            cell["field_factor_decimal"],
        )
        chains[coordinate].add(cell["chain_index"])
        field = Decimal(cell["field_decimal"])
        beta = Decimal(cell["beta_decimal"])
        assert field == Decimal(cell["field_center_decimal"]) * Decimal(
            cell["field_factor_decimal"]
        )
        assert abs(beta * field - Decimal(cell["length"])) < Decimal("1e-45")
        assert cell["field"] == float(field)
        assert cell["beta"] == float(beta)
        assert cell["request"]["field"] == float(field)
        assert cell["request"]["beta"] == float(beta)
        assert cell["request"]["thermalization_sweeps"] == 500
        assert cell["request"]["retained_samples"] == 1600
        assert cell["request"]["thinning"] == 2
        assert cell["request"]["serial_measurement_stride_samples"] == 1
        assert cell["request"]["bin_length"] == 100
        assert cell["request"]["checkpoint_bins"] == 8
        assert json.loads((tmp_path / cell["request_path"]).read_text()) == cell[
            "request"
        ]

    assert dict(observed_lengths) == expected_lengths
    assert all(factors == expected_factors for factors in observed_factors.values())
    assert len(chains) == 70
    assert all(indices == {0, 1} for indices in chains.values())


def test_paper_plan_regeneration_is_byte_identical(tmp_path: Path):
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first = build_paper_scan_plan(_preregistration(), BUILD_INFO, first_root)
    second = build_paper_scan_plan(_preregistration(), BUILD_INFO, second_root)
    assert canonical_json(first) == canonical_json(second)
    assert {
        path.relative_to(first_root): path.read_bytes()
        for path in first_root.rglob("*.json")
    } == {
        path.relative_to(second_root): path.read_bytes()
        for path in second_root.rglob("*.json")
    }


@pytest.mark.parametrize(
    "mutation",
    [
        lambda plan: plan["preregistration"]["lattices"][0].update(
            field_center_decimal="4.76812"
        ),
        lambda plan: plan["cells"][0].update(beta_decimal="1"),
        lambda plan: plan["cells"][0].update(field_decimal="1"),
        lambda plan: plan["cells"][0]["request"].update(retained_samples=1601),
        lambda plan: plan["cells"].reverse(),
        lambda plan: plan["cells"].pop(),
        lambda plan: plan.update(unknown=True),
    ],
)
def test_rehashed_paper_semantic_mutations_fail_closed(tmp_path: Path, mutation):
    plan = build_paper_scan_plan(_preregistration(), BUILD_INFO, tmp_path)
    mutation(plan)
    if plan["cells"]:
        cell = plan["cells"][0]
        cell["request_sha256"] = hashlib.sha256(
            canonical_json(cell["request"])
        ).hexdigest()
    _rehash(plan)
    with pytest.raises(ValueError):
        validate_paper_scan_plan(plan)


def test_paper_preregistration_is_closed(tmp_path: Path):
    preregistration = _preregistration()
    preregistration["unknown"] = True
    with pytest.raises(ValueError, match="preregistration"):
        build_paper_scan_plan(preregistration, BUILD_INFO, tmp_path)
