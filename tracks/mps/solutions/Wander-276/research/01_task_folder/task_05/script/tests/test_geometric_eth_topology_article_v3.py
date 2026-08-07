"""Delivery tests for the integrated v3 article."""

from __future__ import annotations

import json

from verify_geometric_eth_topology_article_v3 import (
    AUDIT_JSON,
    FINAL_PDF,
)


def test_final_article_audit_passes() -> None:
    audit = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    assert audit["passed"] is True
    assert all(audit["checks"].values())
    assert audit["matrix_branch"] == "deformed_geometric_eth"
    assert audit["topology_branch"] == "fixed_chern_deformed_holonomy"
    assert audit["page_count"] == 17
    assert audit["main_pdf_sha256"] == audit["archived_pdf_sha256"]
    assert FINAL_PDF.exists()


def test_delivery_audit_links_all_seven_figures() -> None:
    audit = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    assert len(audit["figures"]) == 7
    assert all(item["exists"] for item in audit["figures"])
    assert all(item["source_hash_matches"] for item in audit["figures"])


def test_delivery_audit_records_every_rendered_page() -> None:
    audit = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    assert len(audit["rendered_pages"]) == audit["page_count"]
    assert all(item["sha256"] for item in audit["rendered_pages"])
