from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

import long_range_percolation.pilot_extension as extension

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


def _rehash(protocol: dict[str, object]) -> None:
    unsigned = dict(protocol)
    unsigned.pop("protocol_sha256", None)
    protocol["protocol_sha256"] = hashlib.sha256(
        extension._canonical_bytes(unsigned)
    ).hexdigest()


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
