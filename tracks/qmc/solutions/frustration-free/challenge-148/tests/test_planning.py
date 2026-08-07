from __future__ import annotations

import copy
import hashlib
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from challenge148.planning import _write_immutable, build_coarse_plan, validate_plan
from challenge148.provenance import canonical_json


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION_PATH = ROOT / "preregistration" / "coarse-crossing-v1.json"
BUILD_INFO = {
    "adapter": "QMC_SSE",
    "source_hash": "a" * 64,
    "build_hash": "b" * 64,
}


def _preregistration() -> dict[str, object]:
    return json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))


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


def test_coarse_plan_expands_the_frozen_72_cells(tmp_path: Path):
    plan = build_coarse_plan(_preregistration(), BUILD_INFO, tmp_path)
    validate_plan(plan)

    cells = plan["cells"]
    assert len(cells) == 72
    assert len({cell["cell_id"] for cell in cells}) == 72
    assert {cell["lattice"] for cell in cells} == {"honeycomb", "triangular"}
    assert {cell["length"] for cell in cells} == {4, 6, 8}
    assert {cell["beta_ratio"] for cell in cells} == {1, 2}
    assert plan["allocation"] == {
        "cores_per_cell": 2,
        "memory_mb_per_cell": 6000,
        "max_concurrency": 16,
    }
    unsigned = copy.deepcopy(plan)
    plan_sha256 = unsigned.pop("plan_sha256")
    assert plan_sha256 == hashlib.sha256(canonical_json(unsigned)).hexdigest()

    fields = defaultdict(list)
    seeds = defaultdict(set)
    for cell in cells:
        coordinate = (
            cell["lattice"],
            cell["length"],
            cell["field"],
            cell["beta_ratio"],
        )
        fields[cell["lattice"]].append(cell["field"])
        seeds[coordinate].add(cell["seed"])

        request = cell["request"]
        assert request == json.loads((tmp_path / cell["request_path"]).read_text())
        assert request["adapter"] == "QMC_SSE"
        assert request["beta"] == cell["length"] * cell["beta_ratio"]
        assert isinstance(request["beta"], float)
        assert request["coupling"] == 1.0
        assert request["thermalization_sweeps"] == 500
        assert request["retained_samples"] == 1600
        assert request["thinning"] == 2
        assert request["serial_measurement_stride_samples"] == 1
        assert request["bin_length"] == 100
        assert request["checkpoint_bins"] == 8
        assert request["expected_source_hash"] == BUILD_INFO["source_hash"]
        assert request["expected_build_hash"] == BUILD_INFO["build_hash"]
        assert (tmp_path / request["graph_path"]).is_file()

    assert sorted(set(fields["triangular"])) == pytest.approx(
        [4.76811 * 0.99, 4.76811, 4.76811 * 1.01]
    )
    assert sorted(set(fields["honeycomb"])) == pytest.approx(
        [2.13250 * 0.99, 2.13250, 2.13250 * 1.01]
    )
    assert all(len(point_seeds) == 2 for point_seeds in seeds.values())
    assert len({cell["seed"] for cell in cells}) == 72
    ordered_fields = [
        cell["field"]
        for cell in cells
        if cell["lattice"] == "triangular"
        and cell["length"] == 4
        and cell["beta_ratio"] == 1
        and cell["chain_index"] == 0
    ]
    assert ordered_fields == pytest.approx(
        [4.76811 * 0.99, 4.76811, 4.76811 * 1.01]
    )


def test_coarse_plan_regeneration_is_byte_identical(tmp_path: Path):
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"

    first = build_coarse_plan(_preregistration(), BUILD_INFO, first_root)
    second = build_coarse_plan(_preregistration(), BUILD_INFO, second_root)

    assert canonical_json(first) == canonical_json(second)
    assert _relative_files(first_root) == _relative_files(second_root)


def test_planning_inputs_and_plan_fail_closed(tmp_path: Path):
    unknown_preregistration = _preregistration()
    unknown_preregistration["unknown"] = True
    with pytest.raises(ValueError, match="preregistration"):
        build_coarse_plan(unknown_preregistration, BUILD_INFO, tmp_path / "unknown")

    unknown_build = dict(BUILD_INFO, unknown=True)
    with pytest.raises(ValueError, match="build info"):
        build_coarse_plan(_preregistration(), unknown_build, tmp_path / "build")

    plan = build_coarse_plan(_preregistration(), BUILD_INFO, tmp_path / "valid")
    duplicate = copy.deepcopy(plan)
    duplicate["cells"][1]["cell_id"] = duplicate["cells"][0]["cell_id"]
    _rehash_plan(duplicate)
    with pytest.raises(ValueError, match="duplicate cell_id"):
        validate_plan(duplicate)

    extra = copy.deepcopy(plan)
    extra["unknown"] = True
    with pytest.raises(ValueError, match="schema"):
        validate_plan(extra)


def _mutate_preregistration_digest(plan):
    plan["preregistration_sha256"] = "0" * 64


def _mutate_preregistration_allocation(plan):
    plan["preregistration"]["allocation"]["cores_per_cell"] = 3


def _mutate_plan_allocation(plan):
    plan["allocation"]["memory_mb_per_cell"] = 5999


def _mutate_field(plan):
    cell = plan["cells"][0]
    cell["field"] += 0.1
    cell["request"]["field"] = cell["field"]
    _rehash_request(cell)


def _mutate_field_factor(plan):
    plan["cells"][0]["field_factor"] = 1.0


def _mutate_field_index(plan):
    plan["cells"][0]["field_index"] = 1


def _mutate_beta_ratio(plan):
    plan["cells"][0]["beta_ratio"] = 2


def _mutate_beta(plan):
    cell = plan["cells"][0]
    cell["beta"] += 1
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


def _mutate_graph_filename(plan):
    plan["graphs"][0]["path"] = f"graphs/{'0' * 64}.json"


def _mutate_graph_hash(plan):
    plan["graphs"][0]["sha256"] = "0" * 64


def _mutate_graph_content(plan):
    plan["graphs"][0]["content"]["bonds"][0][1] += 1


def _mutate_request_filename(plan):
    plan["cells"][0]["request_path"] = "requests/tampered.json"


def _mutate_request_hash(plan):
    plan["cells"][0]["request_sha256"] = "0" * 64


def _mutate_request_coordinate(plan):
    cell = plan["cells"][0]
    cell["request"]["field"] += 0.1
    _rehash_request(cell)


def _mutate_request_build_binding(plan):
    cell = plan["cells"][0]
    cell["request"]["expected_build_hash"] = "c" * 64
    _rehash_request(cell)


def _mutate_request_source_binding(plan):
    cell = plan["cells"][0]
    cell["request"]["expected_source_hash"] = "c" * 64
    _rehash_request(cell)


def _mutate_request_graph_path(plan):
    cell = plan["cells"][0]
    cell["request"]["graph_path"] = f"graphs/{'0' * 64}.json"
    _rehash_request(cell)


def _mutate_request_graph_hash(plan):
    cell = plan["cells"][0]
    cell["request"]["graph_sha256"] = "0" * 64
    _rehash_request(cell)


def _mutate_order(plan):
    plan["cells"][0], plan["cells"][1] = plan["cells"][1], plan["cells"][0]


def _mutate_count(plan):
    plan["cells"].pop()


@pytest.mark.parametrize(
    "mutate",
    [
        _mutate_preregistration_digest,
        _mutate_preregistration_allocation,
        _mutate_plan_allocation,
        _mutate_field,
        _mutate_field_factor,
        _mutate_field_index,
        _mutate_beta_ratio,
        _mutate_beta,
        _mutate_seed,
        _mutate_duplicate_seed,
        _mutate_graph_filename,
        _mutate_graph_hash,
        _mutate_graph_content,
        _mutate_request_filename,
        _mutate_request_hash,
        _mutate_request_coordinate,
        _mutate_request_build_binding,
        _mutate_request_source_binding,
        _mutate_request_graph_path,
        _mutate_request_graph_hash,
        _mutate_order,
        _mutate_count,
    ],
    ids=lambda mutate: mutate.__name__.removeprefix("_mutate_"),
)
def test_plan_mutations_fail_closed(tmp_path: Path, mutate):
    plan = build_coarse_plan(_preregistration(), BUILD_INFO, tmp_path)
    mutate(plan)
    _rehash_plan(plan)
    with pytest.raises(ValueError):
        validate_plan(plan)


def test_plan_identity_rejects_tampering_without_rehash(tmp_path: Path):
    plan = build_coarse_plan(_preregistration(), BUILD_INFO, tmp_path)
    plan["cells"][0]["field"] += 0.1
    with pytest.raises(ValueError, match="plan_sha256"):
        validate_plan(plan)


@pytest.mark.parametrize(
    ("key", "replacement"),
    [
        ("adapter", "QMC_LTFIM"),
        ("beta", 99),
        ("bin_length", 101),
        ("checkpoint_bins", 9),
        ("coupling", 0.5),
        ("field", 9.9),
        ("retained_samples", 1601),
        ("schema_version", "qmc-request-v2"),
        ("seed", 1),
        ("serial_measurement_stride_samples", 2),
        ("thermalization_sweeps", 501),
        ("thinning", 3),
    ],
)
def test_every_request_coordinate_and_sampling_binding_fails_closed(
    tmp_path: Path, key: str, replacement: object
):
    plan = build_coarse_plan(_preregistration(), BUILD_INFO, tmp_path)
    cell = plan["cells"][0]
    cell["request"][key] = replacement
    _rehash_request(cell)
    _rehash_plan(plan)
    with pytest.raises(ValueError):
        validate_plan(plan)


def test_atomic_publication_accepts_concurrent_identical_bytes(tmp_path: Path):
    path = tmp_path / "artifact.json"
    payload = b'{"complete":true}\n'
    barrier = Barrier(8)

    def publish():
        barrier.wait()
        _write_immutable(path, payload)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(publish) for _ in range(8)]
        for future in futures:
            future.result()

    assert path.read_bytes() == payload
    assert sorted(item.name for item in tmp_path.iterdir()) == ["artifact.json"]


def test_atomic_publication_rejects_mismatch_without_overwrite(tmp_path: Path):
    path = tmp_path / "artifact.json"
    original = b'{"complete":"original"}\n'
    path.write_bytes(original)

    with pytest.raises(ValueError, match="mismatched"):
        _write_immutable(path, b'{"complete":"replacement"}\n')

    assert path.read_bytes() == original


def test_atomic_publication_race_never_truncates_winner(tmp_path: Path, monkeypatch):
    path = tmp_path / "artifact.json"
    payloads = [b'{"writer":1}\n', b'{"writer":2}\n']
    barrier = Barrier(2)
    existence_barrier = Barrier(2)
    real_exists = Path.exists

    def synchronized_absence(candidate):
        if candidate == path:
            existence_barrier.wait()
            return False
        return real_exists(candidate)

    monkeypatch.setattr(Path, "exists", synchronized_absence)

    def publish(payload):
        barrier.wait()
        try:
            _write_immutable(path, payload)
            return "published"
        except ValueError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(publish, payloads))

    assert sorted(outcomes) == ["published", "rejected"]
    assert path.read_bytes() in payloads
