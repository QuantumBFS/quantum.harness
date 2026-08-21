#!/usr/bin/env python3
"""Generate manuscript-facing v3 macros, tables, and provenance."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_ROOT.parents[2]
OUTPUT = SCRIPT_ROOT / "output"
MATRIX_JSON = OUTPUT / "matrix_element_geometric_eth_v3.json"
TOPOLOGY_JSON = OUTPUT / "topological_holonomy_v3.json"
MATRIX_AUDIT = OUTPUT / "matrix_element_delivery_audit_v3.json"
TOPOLOGY_AUDIT = OUTPUT / "topological_holonomy_delivery_audit_v3.json"
FIGURE_6 = OUTPUT / "figure_6_wick_factorization_v3.pdf"
FIGURE_7 = OUTPUT / "figure_7_topological_holonomy_v3.pdf"
NUMBERS = OUTPUT / "generated_numbers_v3.tex"
TABLES = OUTPUT / "generated_tables_v3.tex"
MANIFEST = OUTPUT / "geometric_eth_topology_assets_v3.json"
OVERLEAF_GENERATED = (
    REPO_ROOT / "overleaf_sync" / "geometric_eth_large_scale" / "generated"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_text(path, json.dumps(payload, indent=2, sort_keys=True))


def _fmt(value: float, digits: int = 5) -> str:
    return f"{float(value):.{digits}f}"


def _macro(name: str, value: str) -> str:
    return rf"\newcommand{{\{name}}}{{{value}}}"


def generate_assets() -> dict[str, Any]:
    matrix = json.loads(MATRIX_JSON.read_text(encoding="utf-8"))
    topology = json.loads(TOPOLOGY_JSON.read_text(encoding="utf-8"))
    matrix_audit = json.loads(MATRIX_AUDIT.read_text(encoding="utf-8"))
    topology_audit = json.loads(
        TOPOLOGY_AUDIT.read_text(encoding="utf-8")
    )
    if not matrix_audit["passed"] or not topology_audit["passed"]:
        raise RuntimeError("independent v3 audits must pass before assets")
    largest = matrix["cases"][-1]
    top3, top4 = topology["sizes"]
    macros = [
        "% Generated from audited v3 artifacts by the release pipeline.",
        _macro(
            "MatrixElementBranch",
            matrix["result_branch"].replace("_", r"\_"),
        ),
        _macro(
            "MatrixElementBranchText",
            (
                "The four-channel residual decreases along the genuine "
                "many-body sequence and retains a resolved connected "
                "component at the largest size."
            ),
        ),
        _macro("LargestManyBodyN", str(largest["N"])),
        _macro("LargestManyBodyRank", str(largest["rank"])),
        _macro("LargestManyBodyDimension", str(largest["basis_dimension"])),
        _macro("LargestNRFour", _fmt(largest["physical_R4_median"])),
        _macro("LargestGaussianRFour", _fmt(largest["gaussian_R4_interval"][1])),
        _macro(
            "LargestGaussianRFourLow",
            _fmt(largest["gaussian_R4_interval"][0]),
        ),
        _macro(
            "LargestGaussianRFourHigh",
            _fmt(largest["gaussian_R4_interval"][2]),
        ),
        _macro(
            "LargestRFourExcess",
            _fmt(largest["physical_excess"]),
        ),
        _macro(
            "TopologyBranch",
            topology["result_branch"].replace("_", r"\_"),
        ),
        _macro(
            "TopologyBranchText",
            (
                "The Chern class and complete spectrum remain fixed while "
                "Wilson statistics change significantly and occupy a "
                "structured class distinct from the circular-unitary "
                "reference."
            ),
        ),
        _macro("TopologyPrimaryMesh", str(topology["configuration"]["primary_mesh"])),
        _macro(
            "TopologyConvergenceMesh",
            str(topology["configuration"]["convergence_mesh"]),
        ),
        _macro("TopologyNThreeChern", str(top3["base_chern_integer"])),
        _macro("TopologyNFourChern", str(top4["base_chern_integer"])),
        _macro("TopologyNThreeGap", _fmt(top3["minimum_external_gap"], 6)),
        _macro("TopologyNFourGap", _fmt(top4["minimum_external_gap"], 6)),
        _macro(
            "TopologyNThreeGapChangeLow",
            _fmt(top3["gap_change_interval"][0]),
        ),
        _macro(
            "TopologyNThreeGapChangeHigh",
            _fmt(top3["gap_change_interval"][2]),
        ),
        _macro(
            "TopologyNFourGapChangeLow",
            _fmt(top4["gap_change_interval"][0]),
        ),
        _macro(
            "TopologyNFourGapChangeHigh",
            _fmt(top4["gap_change_interval"][2]),
        ),
        _macro(
            "TopologyNThreeFinalGapRatio",
            _fmt(top3["final_gap_ratio_interval"][1]),
        ),
        _macro(
            "TopologyNFourFinalGapRatio",
            _fmt(top4["final_gap_ratio_interval"][1]),
        ),
        _macro(
            "TopologyNThreeCUERatio",
            _fmt(top3["cue_gap_ratio_interval"][1]),
        ),
        _macro(
            "TopologyNFourCUERatio",
            _fmt(top4["cue_gap_ratio_interval"][1]),
        ),
        _macro(
            "TopologyMinimumBranchMargin",
            _fmt(
                min(
                    top3["minimum_branch_margin"],
                    top4["minimum_branch_margin"],
                )
            ),
        ),
        _macro(
            "TopologyMinimumOverlap",
            _fmt(
                min(
                    top3["minimum_overlap_singular_value"],
                    top4["minimum_overlap_singular_value"],
                )
            ),
        ),
        _macro(
            "TopologyGaugeError",
            f"{topology['random_gauge_errors']['wilson_phase_error']:.2e}",
        ),
        "",
    ]
    matrix_rows = []
    for case in matrix["cases"]:
        matrix_rows.append(
            " & ".join(
                [
                    str(case["N"]),
                    str(case["n_flux"]),
                    str(case["rank"]),
                    str(case["basis_dimension"]),
                    _fmt(case["external_gap"], 6),
                    _fmt(case["physical_R4_median"]),
                    _fmt(case["gaussian_R4_interval"][1]),
                    _fmt(case["physical_excess"]),
                ]
            )
            + r" \\"
        )
    topology_rows = []
    for size in topology["sizes"]:
        topology_rows.append(
            " & ".join(
                [
                    str(size["N"]),
                    str(size["rank"]),
                    str(size["base_chern_integer"]),
                    _fmt(size["minimum_external_gap"], 6),
                    _fmt(size["minimum_branch_margin"]),
                    _fmt(size["minimum_overlap_singular_value"]),
                    _fmt(size["final_gap_ratio_interval"][1]),
                    _fmt(size["cue_gap_ratio_interval"][1]),
                ]
            )
            + r" \\"
        )
    tables = "\n".join(
        [
            "% Generated from audited v3 artifacts by the release pipeline.",
            r"\newcommand{\MatrixElementResultRows}{%",
            *matrix_rows,
            "}",
            r"\newcommand{\TopologyResultRows}{%",
            *topology_rows,
            "}",
            "",
        ]
    )
    number_text = "\n".join(macros)
    _atomic_text(NUMBERS, number_text)
    _atomic_text(TABLES, tables)
    _atomic_text(OVERLEAF_GENERATED / NUMBERS.name, number_text)
    _atomic_text(OVERLEAF_GENERATED / TABLES.name, tables)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    inputs = (
        MATRIX_JSON,
        TOPOLOGY_JSON,
        MATRIX_AUDIT,
        TOPOLOGY_AUDIT,
        FIGURE_6,
        FIGURE_7,
    )
    result = {
        "version": "v3",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "matrix_branch": matrix["result_branch"],
        "topology_branch": topology["result_branch"],
        "input_hashes": {
            str(path.relative_to(SCRIPT_ROOT)): _sha256(path)
            for path in inputs
        },
        "output_hashes": {
            str(path.relative_to(SCRIPT_ROOT)): _sha256(path)
            for path in (NUMBERS, TABLES)
        },
        "overleaf_hashes": {
            str(path.relative_to(REPO_ROOT)): _sha256(path)
            for path in (
                OVERLEAF_GENERATED / NUMBERS.name,
                OVERLEAF_GENERATED / TABLES.name,
            )
        },
        "source_sha256": _sha256(Path(__file__)),
    }
    _atomic_json(MANIFEST, result)
    return result


def main() -> None:
    print(json.dumps(generate_assets(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
