"""Tests for generated v3 manuscript assets."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = SCRIPT_ROOT / "output"
NUMBERS = OUTPUT / "generated_numbers_v3.tex"
TABLES = OUTPUT / "generated_tables_v3.tex"
MANIFEST = OUTPUT / "geometric_eth_topology_assets_v3.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _macros() -> dict[str, str]:
    pattern = re.compile(r"\\newcommand\{\\([^}]+)\}\{(.*)\}")
    result: dict[str, str] = {}
    for line in NUMBERS.read_text(encoding="utf-8").splitlines():
        match = pattern.fullmatch(line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def test_generated_macros_match_raw_v3_results() -> None:
    matrix = json.loads(
        (OUTPUT / "matrix_element_geometric_eth_v3.json").read_text()
    )
    topology = json.loads(
        (OUTPUT / "topological_holonomy_v3.json").read_text()
    )
    macros = _macros()
    assert float(macros["LargestNRFour"]) == pytest.approx(
        matrix["cases"][-1]["physical_R4_median"],
        abs=5e-6,
    )
    assert int(macros["TopologyNFourChern"]) == topology["sizes"][-1][
        "base_chern_integer"
    ]
    assert macros["MatrixElementBranch"].replace(r"\_", "_") == matrix[
        "result_branch"
    ]
    assert macros["TopologyBranch"].replace(r"\_", "_") == topology[
        "result_branch"
    ]


def test_generated_tables_contain_all_registered_rows() -> None:
    text = TABLES.read_text(encoding="utf-8")
    assert "3 & 8 & 16 & 120" in text
    assert "5 & 12 & 36 & 4368" in text
    assert "4 & 25 & 10" in text


def test_asset_manifest_hashes_all_outputs() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["output_hashes"]["output/generated_numbers_v3.tex"] == _sha256(
        NUMBERS
    )
    assert manifest["output_hashes"]["output/generated_tables_v3.tex"] == _sha256(
        TABLES
    )
    assert manifest["matrix_branch"] == "deformed_geometric_eth"
    assert manifest["topology_branch"] == "fixed_chern_deformed_holonomy"
