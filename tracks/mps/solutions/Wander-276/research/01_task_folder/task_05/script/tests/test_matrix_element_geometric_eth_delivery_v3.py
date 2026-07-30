"""Fail-closed delivery tests for the matrix-element extension."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from run_matrix_element_geometric_eth_v3 import OUTPUT_JSON
from verify_matrix_element_geometric_eth_v3 import (
    AUDIT_JSON,
    audit_payload,
)


def test_matrix_element_delivery_audit_passes_all_gates() -> None:
    audit = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    assert audit["passed"] is True
    assert all(audit["checks"].values())
    assert audit["result_branch"] == "deformed_geometric_eth"
    assert audit["registered_cases"] == [[3, 8, 16], [4, 10, 25], [5, 12, 36]]


def test_audit_rejects_branch_metric_mismatch() -> None:
    payload = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
    corrupted = copy.deepcopy(payload)
    corrupted["result_branch"] = "wick_compatible_trend"
    corrupted["cases"][-1]["physical_R4_median"] = 100.0
    with pytest.raises(AssertionError):
        audit_payload(corrupted)


def test_audit_records_figure_and_checkpoint_hashes() -> None:
    audit = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    assert len(audit["checkpoint_hashes"]) == 6
    assert audit["figure"]["pdf_sha256"]
    assert audit["figure"]["png_sha256"]
    assert Path(audit["figure"]["pdf"]).name == "figure_6_wick_factorization_v3.pdf"
