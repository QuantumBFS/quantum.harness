from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("matplotlib")

from src.render_comparison import render_ordering_comparison


def _result(method: str, energies: list[float]) -> dict:
    return {
        "schema_version": 1,
        "status": "completed",
        "instance": "anderson",
        "method": "block2-dmrg",
        "sector": {"norb": 2, "nelec": 2, "ms2": 0, "spin": 0},
        "input": {"sha256": "a" * 64},
        "ordering": {"method": method, "permutation": [0, 1]},
        "stages": [
            {
                "bond_dimension": bond_dimension,
                "energy_hartree": energy,
                "discarded_weight": 1.0e-4 / index,
            }
            for index, (bond_dimension, energy) in enumerate(
                zip([100, 200], energies),
                start=1,
            )
        ],
        "headline": {
            "kind": "finite_m_mps_expectation",
            "bond_dimension": 200,
            "energy_hartree": energies[-1],
        },
        "references": {"skqd": -1.5, "cas4": -1.0, "rhf": 0.0},
    }


def test_render_ordering_comparison_writes_plot_and_table(tmp_path: Path) -> None:
    run_dirs = []
    for method, energies in (
        ("fiedler", [-1.1, -1.4]),
        ("ga", [-1.3, -1.6]),
    ):
        run_dir = tmp_path / method
        run_dir.mkdir()
        (run_dir / "result.json").write_text(
            json.dumps(_result(method, energies)),
            encoding="utf-8",
        )
        run_dirs.append(run_dir)

    plot, report = render_ordering_comparison(run_dirs, tmp_path / "comparison")

    assert plot.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    text = report.read_text(encoding="utf-8")
    assert "| ga | 200 |" in text
    assert "−100.000000000" in text
