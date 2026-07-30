from decimal import Decimal
import json
from pathlib import Path

from xxzcert.delivery import (
    build_delivery_bundle,
    evaluate_record_gate,
    write_delivery_bundle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_record_gate_uses_exact_decimal_strings():
    gate = evaluate_record_gate(
        Decimal("-0.443976567"),
        Decimal("-0.4428702958784947210360110613724028607783"),
    )
    assert gate.width == Decimal(
        "0.0011062711215052789639889386275971392217"
    )
    assert gate.target == Decimal("0.0003")
    assert gate.required_lower == Decimal(
        "-0.4431702958784947210360110613724028607783"
    )
    assert not gate.passes


def test_record_gate_rejects_reversed_endpoints():
    try:
        evaluate_record_gate(Decimal("0"), Decimal("-1"))
    except ValueError as error:
        assert "exceeds" in str(error)
    else:
        raise AssertionError("reversed certified endpoints must be rejected")


def test_build_delivery_bundle_covers_the_selected_frontier():
    bundle = build_delivery_bundle(PROJECT_ROOT)
    assert len(bundle.grid_rows) == 27
    assert len(bundle.rows) == 28
    assert bundle.strongest_xxx.level == 47
    assert bundle.strongest_xxx.delta == Decimal("1")
    assert bundle.strongest_xxx.lower_method == "rg-lti-rational-dual"
    assert bundle.strongest_xxx.upper_method == "rational-mps-repeated-block"
    assert {row.delta for row in bundle.grid_rows} == {
        Decimal("-2"),
        Decimal("-1"),
        Decimal("-0.5"),
        Decimal("0"),
        Decimal("0.5"),
        Decimal("0.9"),
        Decimal("1"),
        Decimal("1.1"),
        Decimal("2"),
    }


def test_delivery_bundle_writes_stable_machine_readable_artifacts(tmp_path):
    bundle = build_delivery_bundle(PROJECT_ROOT)
    paths = write_delivery_bundle(bundle, PROJECT_ROOT, tmp_path)
    assert {path.name for path in paths} == {
        "certificate-summary.csv",
        "record-gate.json",
        "DATA_MANIFEST.txt",
    }
    first = {path.name: path.read_bytes() for path in paths}
    second_paths = write_delivery_bundle(bundle, PROJECT_ROOT, tmp_path)
    second = {path.name: path.read_bytes() for path in second_paths}
    assert first == second

    gate = json.loads((tmp_path / "record-gate.json").read_text())
    assert gate["target_width"] == "0.0003"
    assert gate["certified_width"] == (
        "0.0011062711215052789639889386275971392217"
    )
    assert gate["passes_record_target"] is False

    manifest = (tmp_path / "DATA_MANIFEST.txt").read_text()
    assert "level_47_rg_d6_mps_d32_block_1000.json" in manifest
    assert "upper-contraction-frontier.csv" in manifest
    assert str(PROJECT_ROOT) not in manifest
