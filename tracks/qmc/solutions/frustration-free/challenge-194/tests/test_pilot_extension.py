from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

import long_range_percolation.pilot_extension as extension
from long_range_percolation import pilot

P0_ANALYSIS = (
    Path(__file__).resolve().parents[6] / "results/challenge-194/p0_analysis.json"
)
EXPECTED_SPANS = {
    (0.9).hex(): (
        (4, 7),
        (0.48828125).hex(),
        float.fromhex("0x1.312d000000000p+0").hex(),
    ),
    (1.0).hex(): (
        (5, 9),
        float.fromhex("0x1.3880000000000p-1").hex(),
        float.fromhex("0x1.dcd6500000000p+0").hex(),
    ),
}
EXPECTED_GRIDS = {
    (0.9).hex(): [
        "0x1.f400000000000p-2",
        "0x1.1085a00000000p-1",
        "0x1.270b400000000p-1",
        "0x1.3d90e00000000p-1",
        "0x1.5416800000000p-1",
        "0x1.6a9c200000000p-1",
        "0x1.8121c00000000p-1",
        "0x1.97a7600000000p-1",
        "0x1.ae2d000000000p-1",
        "0x1.c4b2a00000000p-1",
        "0x1.db38400000000p-1",
        "0x1.f1bde00000000p-1",
        "0x1.0421c00000000p+0",
        "0x1.0f64900000000p+0",
        "0x1.1aa7600000000p+0",
        "0x1.25ea300000000p+0",
        "0x1.312d000000000p+0",
    ],
    (1.0).hex(): [
        "0x1.3880000000000p-1",
        "0x1.6092ca0000000p-1",
        "0x1.88a5940000000p-1",
        "0x1.b0b85e0000000p-1",
        "0x1.d8cb280000000p-1",
        "0x1.006ef90000000p+0",
        "0x1.14785e0000000p+0",
        "0x1.2881c30000000p+0",
        "0x1.3c8b280000000p+0",
        "0x1.50948d0000000p+0",
        "0x1.649df20000000p+0",
        "0x1.78a7570000000p+0",
        "0x1.8cb0bc0000000p+0",
        "0x1.a0ba210000000p+0",
        "0x1.b4c3860000000p+0",
        "0x1.c8cceb0000000p+0",
        "0x1.dcd6500000000p+0",
    ],
}


def _source() -> dict[str, object]:
    return json.loads(P0_ANALYSIS.read_text(encoding="utf-8"))


def _extension_protocol_fixture() -> dict[str, object]:
    return extension.build_p0_extension_protocol(_source())


def _rehash(protocol: dict[str, object]) -> None:
    unsigned = dict(protocol)
    unsigned.pop("protocol_sha256", None)
    protocol["protocol_sha256"] = hashlib.sha256(
        extension._canonical_bytes(unsigned)
    ).hexdigest()


def test_extension_run_spec_is_bound_and_p0_loader_stays_strict(tmp_path: Path):
    protocol = _extension_protocol_fixture()
    run_spec = pilot._write_test_extension_run_spec(
        tmp_path / "extension", protocol=protocol
    )
    loaded = pilot.load_p0_extension_run_spec(
        run_spec, verify_current_environment=False
    )
    assert loaded["schema_version"] == extension.EXTENSION_RUN_SPEC_SCHEMA
    assert (
        loaded["source_extension_protocol_sha256"]
        == protocol["protocol_sha256"]
    )
    assert loaded["cells"] == protocol["cells"]
    with pytest.raises(RuntimeError, match="P0 run spec"):
        pilot.load_pilot_run_spec(run_spec, verify_current_environment=False)


def test_extension_small_cell_restart_and_merge_use_extension_progress(
    tmp_path: Path,
):
    run_spec = pilot._write_test_extension_run_spec(
        tmp_path / "extension", tiny=True
    )
    first = pilot._run_test_registered_pilot_cell(run_spec, 0)
    second = pilot._run_test_registered_pilot_cell(run_spec, 0)
    assert first == second
    merged = pilot._merge_test_registered_pilot_progress(run_spec)
    assert merged["schema_version"] == extension.EXTENSION_PROGRESS_SCHEMA


def test_extension_run_spec_has_only_bound_outer_fields(tmp_path: Path):
    protocol = _extension_protocol_fixture()
    path = pilot._write_test_extension_run_spec(
        tmp_path / "extension", protocol=protocol
    )
    document = json.loads(path.read_text())
    assert set(document) == {
        "schema_version",
        "artifact_root",
        "protocol",
        "cells",
        "cell_count",
        "source_extension_protocol_sha256",
        "source_p0_analysis_document_sha256",
        "design_sha256",
        "correctness_report_sha256",
        "correctness_run_spec_sha256",
        "correctness_approval_registry_sha256",
        "correctness_approval_revision",
        "validation_source_revision",
        "validated_engine_modules",
        "validated_engine_sha256",
        "validation_runtime_capability_sha256",
        "orchestration_revision",
        "clean_tree",
        "uv_lock_sha256",
        "runtime_capability",
        "runtime_capability_sha256",
        "analysis_plan_sha256",
        "rng_assignment_sha256",
        "capability_waiver",
        "merged_progress_path",
        "run_spec_sha256",
    }
    assert "cells" not in document["protocol"]
    assert document["protocol"]["protocol_sha256"] == protocol["protocol_sha256"]
    assert document["cell_count"] == len(document["cells"]) == 96
    assert all(
        not Path(cell[field]).is_absolute()
        and ".." not in Path(cell[field]).parts
        for cell in document["cells"]
        for field in ("cell_path", "run_path", "manifest_path")
    )


def test_public_extension_builder_binds_approved_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    protocol = _extension_protocol_fixture()
    approval = pilot._load_approval_registry()
    modules = pilot._scientific_hashes()
    monkeypatch.setattr(
        pilot,
        "_current_source",
        lambda **_: {
            "source_revision": protocol["source_revision"],
            "clean_tree": True,
            "provenance_error": None,
        },
    )
    monkeypatch.setattr(
        pilot,
        "_verified_correctness",
        lambda _path: {
            "correctness_report_sha256": approval["report_sha256"],
            "correctness_run_spec_sha256": approval["run_spec_sha256"],
            "correctness_approval_registry_sha256": pilot._approval_registry_digest(),
            "validation_source_revision": approval["validation_source_revision"],
            "validated_engine_modules": modules,
            "validated_engine_sha256": approval["scientific_engine_sha256"],
            "validation_runtime_capability_sha256": "3" * 64,
        },
    )
    output_root = (tmp_path / "extension").resolve()
    document = pilot.build_p0_extension_run_spec(
        output_root,
        (tmp_path / "correctness" / "report.json").resolve(),
        protocol,
    )
    assert document["cells"] == protocol["cells"]
    assert document["design_sha256"] == protocol["design_sha256"]
    assert document["correctness_report_sha256"] == approval["report_sha256"]
    assert (output_root / pilot.RUN_SPEC_NAME).read_bytes() == pilot._canonical_bytes(
        document
    )
    with pytest.raises(RuntimeError, match="absolute"):
        pilot.build_p0_extension_run_spec(
            Path("relative"),
            Path("relative-report.json"),
            protocol,
        )


@pytest.mark.parametrize(
    "stage",
    ("after-trajectory", "after-batch", "after-progress", "after-manifest"),
)
def test_extension_cell_resumes_every_publication_boundary(
    tmp_path: Path, stage: str
):
    path = pilot._write_test_extension_run_spec(
        tmp_path / "extension", tiny=True
    )

    def stop(actual: str) -> None:
        if actual == stage:
            raise RuntimeError("injected extension stop")

    with pytest.raises(RuntimeError, match="injected extension stop"):
        pilot._run_test_registered_pilot_cell(path, 0, crash_hook=stop)
    run = path.parent / json.loads(path.read_text())["cells"][0]["run_path"]
    published_path: Path | None = None
    published_payload: bytes | None = None
    if stage == "after-batch":
        published_path = next((run / "batches").glob("batch-*.json"))
        published_payload = published_path.read_bytes()
        assert not (run / "progress.json").exists()
    if stage == "after-manifest":
        manifest_path = json.loads(path.read_text())["cells"][0]["manifest_path"]
        published_path = path.parent / manifest_path
        published_payload = published_path.read_bytes()
    result = pilot._run_test_registered_pilot_cell(path, 0)
    assert (path.parent / result["manifest_path"]).is_file()
    if published_path is not None:
        assert published_path.read_bytes() == published_payload
    assert pilot._run_test_registered_pilot_cell(path, 0) == result


@pytest.mark.parametrize("suffix", (".partial", ".intent"))
def test_extension_cell_preserves_stale_publication_markers(
    tmp_path: Path, suffix: str
):
    path = pilot._write_test_extension_run_spec(
        tmp_path / "extension", tiny=True
    )
    pilot._run_test_registered_pilot_cell(path, 0)
    cell = next((path.parent / "cells").iterdir())
    marker = cell / f"stale{suffix}"
    marker.write_text("preserve", encoding="utf-8")
    with pytest.raises(RuntimeError, match="publication marker"):
        pilot._run_test_registered_pilot_cell(path, 0)
    assert marker.read_text(encoding="utf-8") == "preserve"


def test_extension_pending_merge_and_snapshot_share_exact_schema(tmp_path: Path):
    path = pilot._write_test_extension_run_spec(
        tmp_path / "extension", tiny=True
    )
    assert pilot._pending_test_registered_pilot_cells(path) == [0]
    result = pilot._run_test_registered_pilot_cell(path, 0)
    assert pilot._pending_test_registered_pilot_cells(path) == []
    request = json.loads(
        (
            path.parent
            / json.loads(path.read_text())["cells"][0]["run_path"]
            / "request.json"
        ).read_text()
    )
    assert request["master_seed"] == extension.EXTENSION_MASTER_SEED
    assert request["phase"] == extension.EXTENSION_PHASE
    merged = pilot._merge_test_registered_pilot_progress(path)
    assert merged["cells"][0]["trajectory_sha256"] == result["trajectory_sha256"]
    with pilot._open_verified_registered_pilot_analysis_snapshot(path) as snapshot:
        assert snapshot.spec["schema_version"] == pilot.TEST_EXTENSION_RUN_SPEC_SCHEMA
        assert snapshot.progress["schema_version"] == extension.EXTENSION_PROGRESS_SCHEMA


def test_extension_merge_rejects_extra_cell_directory(tmp_path: Path):
    path = pilot._write_test_extension_run_spec(
        tmp_path / "extension", tiny=True
    )
    pilot._run_test_registered_pilot_cell(path, 0)
    (path.parent / "cells" / "extra").mkdir()
    with pytest.raises(RuntimeError, match="extra"):
        pilot._merge_test_registered_pilot_progress(path)


def test_extension_cell_root_swap_fails_closed(tmp_path: Path):
    path = pilot._write_test_extension_run_spec(
        tmp_path / "extension", tiny=True
    )
    cell_root = path.parent / json.loads(path.read_text())["cells"][0]["cell_path"]

    def replace(stage: str) -> None:
        if stage == "after-trajectory":
            cell_root.rename(path.parent / "detached-cell")
            cell_root.mkdir()

    with pytest.raises(RuntimeError, match="identity|generation"):
        pilot._run_test_registered_pilot_cell(path, 0, crash_hook=replace)


def test_production_extension_schema_cannot_be_downgraded_to_test(
    tmp_path: Path,
):
    path = pilot._write_test_extension_run_spec(
        tmp_path / "extension", tiny=True
    )
    document = json.loads(path.read_text())
    document["schema_version"] = extension.EXTENSION_RUN_SPEC_SCHEMA
    document["run_spec_sha256"] = pilot._document_hash(
        document, "run_spec_sha256"
    )
    path.write_bytes(pilot._canonical_bytes(document))
    with pytest.raises(RuntimeError):
        pilot._run_test_registered_pilot_cell(path, 0)


@pytest.mark.parametrize(
    ("source_class", "maximum_size"),
    (
        ("design", extension.DESIGN_MAX_BYTES),
        ("progress", extension.P0_PROGRESS_MAX_BYTES),
        ("registry", extension.P0_RUN_SPEC_MAX_BYTES),
        ("analysis", extension.P0_ANALYSIS_MAX_BYTES),
    ),
)
def test_extension_sources_reject_oversize_before_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_class: str,
    maximum_size: int,
):
    source = tmp_path / f"{source_class}.json"
    with source.open("wb") as stream:
        stream.truncate(maximum_size + 1)
    if source_class == "design":
        invoke = lambda: extension._file_sha256(source)
    elif source_class == "progress":
        monkeypatch.setattr(extension, "_p0_progress_path", lambda: source)
        invoke = extension._validate_frozen_progress
    elif source_class == "registry":
        monkeypatch.setattr(extension, "_p0_run_spec_path", lambda: source)
        invoke = extension._p0_identity_hashes
    else:
        monkeypatch.setattr(extension, "_p0_analysis_path", lambda: source)
        invoke = extension.load_frozen_p0_analysis
    with pytest.raises(RuntimeError, match="byte-size|bounded"):
        invoke()


@pytest.mark.parametrize(
    "source_class",
    ("design", "progress", "registry", "analysis"),
)
def test_extension_sources_reject_pathname_swap_after_descriptor_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_class: str,
):
    if source_class == "design":
        source = tmp_path / "design.md"
        source.write_bytes(b"original\n")
        replacement = tmp_path / "replacement.md"
        replacement.write_bytes(b"changed!\n")
        invoke = lambda: extension._file_sha256(source)
    else:
        actual = {
            "progress": extension._p0_progress_path(),
            "registry": extension._p0_run_spec_path(),
            "analysis": extension._p0_analysis_path(),
        }[source_class]
        source = tmp_path / actual.name
        source.write_bytes(actual.read_bytes())
        replacement = tmp_path / f"replacement-{actual.name}"
        payload = bytearray(source.read_bytes())
        payload[0] = ord("[") if payload[0] != ord("[") else ord("{")
        replacement.write_bytes(payload)
        if source_class == "progress":
            monkeypatch.setattr(extension, "_p0_progress_path", lambda: source)
            invoke = extension._validate_frozen_progress
        elif source_class == "registry":
            monkeypatch.setattr(extension, "_p0_run_spec_path", lambda: source)
            invoke = extension._p0_identity_hashes
        else:
            monkeypatch.setattr(extension, "_p0_analysis_path", lambda: source)
            invoke = extension.load_frozen_p0_analysis
    real_read = pilot._read_descriptor_bounded
    swapped = False

    def swapping_read(
        descriptor: int, maximum_size: int, description: str
    ) -> bytes:
        nonlocal swapped
        result = real_read(descriptor, maximum_size, description)
        if not swapped:
            swapped = True
            replacement.replace(source)
        return result

    monkeypatch.setattr(pilot, "_read_descriptor_bounded", swapping_read)
    with pytest.raises(RuntimeError, match="identity|generation|changed"):
        invoke()


def test_extension_ranges_are_derived_from_exact_real_p0():
    derived = extension.derive_p0_extension_ranges(_source())
    assert derived[(0.9).hex()]["four_sector_components"] == [[5, 5]]
    assert derived[(0.9).hex()]["q_g_components"] == [[6, 6], [13, 14]]
    assert derived[(1.0).hex()]["four_sector_components"] == [[6, 7]]
    assert derived[(1.0).hex()]["q_g_components"] == [[8, 8], [12, 14]]
    for sigma_hex, (guard_indices, lower, upper) in EXPECTED_SPANS.items():
        assert derived[sigma_hex]["guard_interval_indices"] == list(guard_indices)
        assert derived[sigma_hex]["lower_kappa_hex"] == lower
        assert derived[sigma_hex]["upper_kappa_hex"] == upper


def test_extension_grids_are_recursive_binary64_and_hash_bound():
    protocol = extension.build_p0_extension_protocol(_source())
    entries = {entry["sigma_hex"]: entry for entry in protocol["sigma_entries"]}
    assert {
        sigma: entry["kappas"] for sigma, entry in entries.items()
    } == EXPECTED_GRIDS
    assert (
        entries[(0.9).hex()]["grid_sha256"]
        == extension.EXTENSION_GRID_HASHES[(0.9).hex()]
    )
    assert (
        entries[(1.0).hex()]["grid_sha256"]
        == extension.EXTENSION_GRID_HASHES[(1.0).hex()]
    )


def test_protocol_has_exact_axes_fresh_identities_and_canonical_cells():
    source = _source()
    protocol = extension.build_p0_extension_protocol(source)
    extension.validate_p0_extension_protocol(source, protocol)
    assert protocol["schema_version"] == extension.EXTENSION_PROTOCOL_SCHEMA
    assert protocol["master_seed"] == 19_420_262_729
    assert protocol["lengths"] == [2**10, 2**14, 2**18]
    assert protocol["replicas"] == list(range(24, 40))
    assert protocol["cell_count"] == 96
    assert sum(len(cell["kappas"]) for cell in protocol["cells"]) == 1632
    assert [
        (cell["sigma"], cell["length"], cell["replica"]) for cell in protocol["cells"]
    ] == [
        (sigma.hex(), length, replica)
        for sigma in (0.9, 1.0)
        for length in (2**10, 2**14, 2**18)
        for replica in range(24, 40)
    ]
    assert len({cell["cell_id"] for cell in protocol["cells"]}) == 96
    assert len({cell["request_sha256"] for cell in protocol["cells"]}) == 96
    assert (
        len(
            {
                digest
                for cell in protocol["cells"]
                for digest in cell["rng_material_sha256"]
            }
        )
        == 96 * 4
    )


def test_protocol_rejects_actual_frozen_progress_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = _source()
    protocol = extension.build_p0_extension_protocol(source)
    drifted = tmp_path / "progress.json"
    drifted.write_bytes(b"{}\n")
    monkeypatch.setattr(extension, "_p0_progress_path", lambda: drifted)
    with pytest.raises(RuntimeError, match="progress"):
        extension.build_p0_extension_protocol(source)
    with pytest.raises(RuntimeError, match="progress"):
        extension.validate_p0_extension_protocol(source, protocol)


def test_protocol_rejects_recomputed_bracket_mismatch(
    monkeypatch: pytest.MonkeyPatch,
):
    source = _source()
    protocol = extension.build_p0_extension_protocol(source)
    forged = copy.deepcopy(extension.select_p1_brackets(source))
    forged["requires_p0_extension"] = False
    assert forged["bracket_document_sha256"] == extension.P0_BRACKET_DOCUMENT_SHA256
    monkeypatch.setattr(extension, "select_p1_brackets", lambda _source: forged)
    with pytest.raises(RuntimeError, match="bracket"):
        extension.build_p0_extension_protocol(source)
    with pytest.raises(RuntimeError, match="bracket"):
        extension.validate_p0_extension_protocol(source, protocol)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("request_sha256", [], "request"),
        ("rng_material_sha256", [{}, "0" * 64, "1" * 64, "2" * 64], "RNG"),
    ],
)
def test_validator_normalizes_malformed_digest_types(
    field: str, value: object, message: str
):
    source = _source()
    protocol = copy.deepcopy(extension.build_p0_extension_protocol(source))
    protocol["cells"][0][field] = value
    _rehash(protocol)
    with pytest.raises(RuntimeError, match=message):
        extension.validate_p0_extension_protocol(source, protocol)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update(source_p0_run_spec_sha256="0" * 64), "source"),
        (
            lambda value: value["sigma_entries"][0]["q_g_components"].reverse(),
            "component",
        ),
        (
            lambda value: value["sigma_entries"][0]["kappas"].__setitem__(
                0, "0X1.F400000000000P-2"
            ),
            "binary64",
        ),
        (lambda value: value["sigma_entries"][0]["kappas"].reverse(), "grid"),
        (
            lambda value: value["sigma_entries"][0].update(grid_sha256="0" * 64),
            "grid",
        ),
        (lambda value: value.update(design_sha256="0" * 64), "design"),
        (lambda value: value["cells"].reverse(), "canonical"),
        (lambda value: value["replicas"].pop(), "replica"),
        (
            lambda value: value["replicas"].__setitem__(1, value["replicas"][0]),
            "replica",
        ),
        (
            lambda value: value["cells"][0].update(request_sha256="0" * 64),
            "request",
        ),
        (
            lambda value: value["cells"][0]["rng_material_sha256"].__setitem__(
                0, "0" * 64
            ),
            "RNG",
        ),
        (
            lambda value: value["cells"][0].update(
                request_sha256=extension._p0_identity_hashes()[0][0]
            ),
            "collision",
        ),
    ],
)
def test_semantic_validator_rejects_superficially_rehashed_mutations(
    mutation, message: str
):
    source = _source()
    protocol = copy.deepcopy(extension.build_p0_extension_protocol(source))
    mutation(protocol)
    _rehash(protocol)
    with pytest.raises(RuntimeError, match=message):
        extension.validate_p0_extension_protocol(source, protocol)


def test_protocol_rejects_unknown_fields_and_p1_identity_overlap(
    monkeypatch: pytest.MonkeyPatch,
):
    source = _source()
    protocol = extension.build_p0_extension_protocol(source)
    forged = copy.deepcopy(protocol)
    forged["unknown"] = True
    _rehash(forged)
    with pytest.raises(RuntimeError, match="fields"):
        extension.validate_p0_extension_protocol(source, forged)

    monkeypatch.setattr(extension, "EXTENSION_REPLICAS", tuple(range(8, 24)))
    with pytest.raises(RuntimeError, match="P1|overlap"):
        extension.build_p0_extension_protocol(source)


def test_component_and_grid_helpers_fail_closed():
    with pytest.raises(RuntimeError, match="canonical"):
        extension._marked_components([2, 1])
    assert extension._component_gap((2, 3), (3, 5)) == 0
    with pytest.raises(RuntimeError, match="endpoints"):
        extension._recursive_binary64_grid_17(1.0, 1.0)
