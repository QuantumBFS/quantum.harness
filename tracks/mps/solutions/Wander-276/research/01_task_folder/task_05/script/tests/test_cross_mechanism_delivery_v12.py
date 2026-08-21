"""Publication-asset and delivery-audit tests for cross-mechanism v12."""

from __future__ import annotations

import json

from make_cross_mechanism_assets_v12 import OUTPUT_ROOT, make_assets
from verify_cross_mechanism_delivery_v12 import verify_delivery


def test_cross_mechanism_figure_has_vector_and_raster_outputs(tmp_path) -> None:
    manifest = make_assets(tmp_path)
    assert manifest["selected_branch"] == "domain_limited_geometric_eth"
    assert manifest["figure_pdf"] == "figure_cross_mechanism_geometric_eth_v12.pdf"
    assert manifest["figure_png"] == "figure_cross_mechanism_geometric_eth_v12.png"
    pdf = tmp_path / manifest["figure_pdf"]
    png = tmp_path / manifest["figure_png"]
    assert pdf.read_bytes().startswith(b"%PDF")
    assert png.read_bytes().startswith(b"\x89PNG")
    assert pdf.stat().st_size > 10_000
    assert png.stat().st_size > 50_000
    assert "complete-covariance" in manifest["caption"]
    assert "X-cube" in manifest["caption"]


def test_temporary_figure_build_does_not_rewrite_canonical_inference(tmp_path) -> None:
    canonical = OUTPUT_ROOT / "cross_mechanism_geometric_eth_v12.json"
    before = canonical.read_bytes()
    make_assets(tmp_path)
    assert canonical.read_bytes() == before


def test_delivery_audit_fails_closed_and_matches_hashes(tmp_path) -> None:
    make_assets(tmp_path)
    audit = verify_delivery(tmp_path)
    assert audit["passed"] is True
    assert all(audit["checks"].values())
    on_disk = json.loads(
        (tmp_path / "cross_mechanism_delivery_audit_v12.json").read_text(
            encoding="utf-8"
        )
    )
    assert on_disk == audit


def test_repository_delivery_reverification_is_byte_stable() -> None:
    audit_path = OUTPUT_ROOT / "cross_mechanism_delivery_audit_v12.json"
    before = audit_path.read_bytes()
    audit = verify_delivery()
    assert audit["passed"] is True
    assert audit_path.read_bytes() == before


def test_delivery_audit_rejects_tampered_figure(tmp_path) -> None:
    manifest = make_assets(tmp_path)
    figure = tmp_path / manifest["figure_png"]
    figure.write_bytes(figure.read_bytes() + b"tampered")
    audit = verify_delivery(tmp_path, write=False)
    assert audit["passed"] is False
    assert audit["checks"]["asset_hashes_match"] is False
