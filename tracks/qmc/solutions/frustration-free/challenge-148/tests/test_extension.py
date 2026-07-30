from __future__ import annotations

import copy
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import pytest

from challenge148.extension import (
    build_directed_extension_plan,
    validate_directed_extension_plan,
)
from challenge148.planning import build_coarse_plan
from challenge148.provenance import canonical_json


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION_PATH = ROOT / "preregistration" / "directed-extension-v1.json"
COARSE_PREREGISTRATION_PATH = ROOT / "preregistration" / "coarse-crossing-v1.json"
BUILD_INFO = {
    "adapter": "QMC_SSE",
    "source_hash": "a" * 64,
    "build_hash": "b" * 64,
}
EXPECTED_COORDINATES = {
    ("triangular", 4, 0.97, 1),
    ("triangular", 4, 0.98, 1),
    ("triangular", 6, 0.97, 1),
    ("triangular", 6, 0.98, 1),
    ("triangular", 6, 1.02, 2),
    ("triangular", 6, 1.03, 2),
    ("triangular", 8, 1.02, 2),
    ("triangular", 8, 1.03, 2),
    ("honeycomb", 6, 0.97, 1),
    ("honeycomb", 6, 0.98, 1),
    ("honeycomb", 8, 0.97, 1),
    ("honeycomb", 8, 0.98, 1),
}
EXPECTED_FIELDS = {
    ("triangular", 0.97): (4.6250667, "4.6250667"),
    ("triangular", 0.98): (4.6727478, "4.6727478"),
    ("triangular", 1.02): (4.8634722, "4.8634722"),
    ("triangular", 1.03): (4.9111533, "4.9111533"),
    ("honeycomb", 0.97): (2.068525, "2.068525"),
    ("honeycomb", 0.98): (2.08985, "2.08985"),
}


def _preregistration() -> dict[str, object]:
    return json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))


def _coarse_preregistration() -> dict[str, object]:
    return json.loads(COARSE_PREREGISTRATION_PATH.read_text(encoding="utf-8"))


def _relative_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*.json"))
    }


def _rehash_plan(plan: dict[str, object]) -> None:
    unsigned = copy.deepcopy(plan)
    unsigned.pop("plan_sha256", None)
    plan["plan_sha256"] = hashlib.sha256(canonical_json(unsigned)).hexdigest()


def _rehash_request(cell: dict[str, object]) -> None:
    cell["request_sha256"] = hashlib.sha256(
        canonical_json(cell["request"])
    ).hexdigest()


def test_directed_extension_expands_the_frozen_24_cells(tmp_path: Path):
    plan = build_directed_extension_plan(
        _preregistration(), BUILD_INFO, tmp_path
    )
    validate_directed_extension_plan(plan)

    assert plan["stage"] == "QMC_SSE coarse localization"
    assert plan["seed_derivation"] == (
        "sha256:challenge148-directed-extension-seed-v1||u64be"
    )
    assert plan["allocation"] == {
        "adapter_timeout_seconds": 1800,
        "cores_per_cell": 2,
        "memory_mb_per_cell": 6000,
        "max_concurrency": 16,
    }

    cells = plan["cells"]
    assert len(cells) == 24
    assert len({cell["cell_id"] for cell in cells}) == 24
    assert len({cell["seed"] for cell in cells}) == 24
    assert all(cell["cell_id"].startswith("directed-") for cell in cells)
    assert all(
        cell["request_path"].startswith("requests/directed-") for cell in cells
    )

    chains = defaultdict(set)
    actual_coordinates = set()
    for cell in cells:
        coordinate = (
            cell["lattice"],
            cell["length"],
            cell["field_factor"],
            cell["beta_ratio"],
        )
        actual_coordinates.add(coordinate)
        chains[coordinate].add(cell["chain_index"])

        center = 4.76811 if cell["lattice"] == "triangular" else 2.1325
        assert cell["field"] == pytest.approx(center * cell["field_factor"])
        assert cell["beta"] == float(cell["length"] * cell["beta_ratio"])
        assert isinstance(cell["beta"], float)

        request = cell["request"]
        assert request == json.loads((tmp_path / cell["request_path"]).read_text())
        assert request["beta"] == cell["beta"]
        assert isinstance(request["beta"], float)
        assert request["thermalization_sweeps"] == 500
        assert request["retained_samples"] == 1600
        assert request["thinning"] == 2
        assert request["serial_measurement_stride_samples"] == 1
        assert request["bin_length"] == 100
        assert request["checkpoint_bins"] == 8
        assert request["expected_source_hash"] == BUILD_INFO["source_hash"]
        assert request["expected_build_hash"] == BUILD_INFO["build_hash"]
        assert (tmp_path / request["graph_path"]).is_file()

    assert actual_coordinates == EXPECTED_COORDINATES
    assert all(chain_indices == {0, 1} for chain_indices in chains.values())

    unsigned = copy.deepcopy(plan)
    plan_sha256 = unsigned.pop("plan_sha256")
    assert plan_sha256 == hashlib.sha256(canonical_json(unsigned)).hexdigest()


def test_directed_extension_regeneration_is_byte_identical(tmp_path: Path):
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"

    first = build_directed_extension_plan(
        _preregistration(), BUILD_INFO, first_root
    )
    second = build_directed_extension_plan(
        _preregistration(), BUILD_INFO, second_root
    )

    assert canonical_json(first) == canonical_json(second)
    assert _relative_files(first_root) == _relative_files(second_root)


def test_directed_fields_use_stable_decimal_products_and_request_hashes(
    tmp_path: Path,
):
    first = build_directed_extension_plan(
        _preregistration(), BUILD_INFO, tmp_path / "first"
    )
    second = build_directed_extension_plan(
        _preregistration(), BUILD_INFO, tmp_path / "second"
    )

    observed_fields = {}
    second_hashes = {
        cell["cell_id"]: cell["request_sha256"] for cell in second["cells"]
    }
    for cell in first["cells"]:
        key = (cell["lattice"], cell["field_factor"])
        expected_field, expected_spelling = EXPECTED_FIELDS[key]
        observed_fields[key] = cell["field"]

        assert cell["field"] == expected_field
        assert canonical_json(cell["field"]).decode("ascii") == expected_spelling
        assert cell["request"]["field"] == expected_field
        assert cell["request_sha256"] == hashlib.sha256(
            canonical_json(cell["request"])
        ).hexdigest()
        assert cell["request_sha256"] == second_hashes[cell["cell_id"]]
        assert isinstance(cell["beta"], float)
        assert isinstance(cell["request"]["beta"], float)

    assert set(observed_fields) == set(EXPECTED_FIELDS)
    assert b"2.0898499999999998" not in canonical_json(first)


def test_original_and_directed_plans_share_artifact_root_without_collisions(
    tmp_path: Path,
):
    coarse = build_coarse_plan(_coarse_preregistration(), BUILD_INFO, tmp_path)
    directed = build_directed_extension_plan(
        _preregistration(), BUILD_INFO, tmp_path
    )
    first_files = _relative_files(tmp_path)

    assert {
        cell["request_path"] for cell in coarse["cells"]
    }.isdisjoint(cell["request_path"] for cell in directed["cells"])
    assert {
        graph["path"] for graph in directed["graphs"]
    }.issubset(graph["path"] for graph in coarse["graphs"])

    assert build_coarse_plan(
        _coarse_preregistration(), BUILD_INFO, tmp_path
    ) == coarse
    assert build_directed_extension_plan(
        _preregistration(), BUILD_INFO, tmp_path
    ) == directed
    assert _relative_files(tmp_path) == first_files


def test_directed_extension_inputs_fail_closed(tmp_path: Path):
    unknown_preregistration = _preregistration()
    unknown_preregistration["unknown"] = True
    with pytest.raises(ValueError, match="preregistration"):
        build_directed_extension_plan(
            unknown_preregistration, BUILD_INFO, tmp_path / "preregistration"
        )

    unknown_build = dict(BUILD_INFO, unknown=True)
    with pytest.raises(ValueError, match="build info"):
        build_directed_extension_plan(
            _preregistration(), unknown_build, tmp_path / "build"
        )


def _mutate_preregistration(plan):
    plan["preregistration"]["coordinates"][0]["lengths"][0] = 5


def _mutate_preregistration_digest(plan):
    plan["preregistration_sha256"] = "0" * 64


def _mutate_allocation(plan):
    plan["allocation"]["adapter_timeout_seconds"] = 1799


def _mutate_stage(plan):
    plan["stage"] = "other"


def _mutate_field(plan):
    cell = plan["cells"][0]
    cell["field"] += 0.1
    cell["request"]["field"] = cell["field"]
    _rehash_request(cell)


def _mutate_factor(plan):
    plan["cells"][0]["field_factor"] = 0.98


def _mutate_beta(plan):
    cell = plan["cells"][0]
    cell["beta"] += 1.0
    cell["request"]["beta"] = cell["beta"]
    _rehash_request(cell)


def _mutate_seed(plan):
    cell = plan["cells"][0]
    cell["seed"] += 1
    cell["request"]["seed"] = cell["seed"]
    _rehash_request(cell)


def _mutate_duplicate_seed(plan):
    cell = plan["cells"][1]
    cell["seed"] = plan["cells"][0]["seed"]
    cell["request"]["seed"] = cell["seed"]
    _rehash_request(cell)


def _mutate_duplicate_cell(plan):
    plan["cells"][1]["cell_id"] = plan["cells"][0]["cell_id"]


def _mutate_request(plan):
    cell = plan["cells"][0]
    cell["request"]["retained_samples"] = 1601
    _rehash_request(cell)


def _mutate_graph(plan):
    plan["graphs"][0]["content"]["bonds"][0][1] += 1


def _mutate_order(plan):
    plan["cells"][0], plan["cells"][1] = plan["cells"][1], plan["cells"][0]


def _mutate_count(plan):
    plan["cells"].pop()


@pytest.mark.parametrize(
    "mutate",
    [
        _mutate_preregistration,
        _mutate_preregistration_digest,
        _mutate_allocation,
        _mutate_stage,
        _mutate_field,
        _mutate_factor,
        _mutate_beta,
        _mutate_seed,
        _mutate_duplicate_seed,
        _mutate_duplicate_cell,
        _mutate_request,
        _mutate_graph,
        _mutate_order,
        _mutate_count,
    ],
    ids=lambda mutate: mutate.__name__.removeprefix("_mutate_"),
)
def test_rehashed_directed_extension_semantic_mutations_fail_closed(
    tmp_path: Path, mutate
):
    plan = build_directed_extension_plan(
        _preregistration(), BUILD_INFO, tmp_path
    )
    mutate(plan)
    _rehash_plan(plan)
    with pytest.raises(ValueError):
        validate_directed_extension_plan(plan)


def test_directed_extension_rejects_unknown_plan_key(tmp_path: Path):
    plan = build_directed_extension_plan(
        _preregistration(), BUILD_INFO, tmp_path
    )
    plan["unknown"] = True
    _rehash_plan(plan)
    with pytest.raises(ValueError, match="schema"):
        validate_directed_extension_plan(plan)


def test_directed_extension_identity_rejects_unrehashed_mutation(tmp_path: Path):
    plan = build_directed_extension_plan(
        _preregistration(), BUILD_INFO, tmp_path
    )
    plan["cells"][0]["field"] += 0.1
    with pytest.raises(ValueError, match="plan_sha256"):
        validate_directed_extension_plan(plan)


@pytest.mark.parametrize("location", ["cell", "request"])
def test_rehashed_equal_integer_beta_fails_semantic_validation(
    tmp_path: Path, location: str
):
    plan = build_directed_extension_plan(
        _preregistration(), BUILD_INFO, tmp_path
    )
    cell = plan["cells"][0]
    assert isinstance(cell["beta"], float)
    assert isinstance(cell["request"]["beta"], float)

    if location == "cell":
        cell["beta"] = int(cell["beta"])
    else:
        cell["request"]["beta"] = int(cell["request"]["beta"])
        _rehash_request(cell)
    _rehash_plan(plan)

    with pytest.raises(ValueError, match="beta.*float"):
        validate_directed_extension_plan(plan)


def test_directed_extension_publication_is_immutable(tmp_path: Path):
    build_directed_extension_plan(_preregistration(), BUILD_INFO, tmp_path)
    request_path = next((tmp_path / "requests").glob("*.json"))
    request_path.write_text('{"tampered":true}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="overwrite|mismatched"):
        build_directed_extension_plan(_preregistration(), BUILD_INFO, tmp_path)
