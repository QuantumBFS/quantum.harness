import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from qh147.validate import assemble


BETAS = np.arange(0.025, 0.1501, 0.025)
M_VALUES = (32, 64, 128)
CHAINS = range(4)
MODES = ("ordinary", "thermodynamic")
CHIS = (16, 32)
SETTINGS = {
    "lx": 10,
    "ly": 10,
    "J": 1.0,
    "h": 3.0,
    "boundary": "open",
    "operator": "pauli",
    "D": 4,
    "delta_beta": 0.025,
}
PROVENANCE = {"protocol": "issue147-h3-fixture"}


def _json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _run_spec(root: Path, run_id: str, settings: dict, cells: list[dict]) -> None:
    _json(
        root / "run_spec.json",
        {
            "run_id": run_id,
            "run_dir": str(root),
            "settings": settings,
            "provenance": PROVENANCE,
            "cells": cells,
        },
    )


def _qmc_fixture(root: Path) -> None:
    cells = []
    offsets = np.linspace(-2e-3, 2e-3, 40)
    index = 0
    for beta in BETAS:
        for m_value in M_VALUES:
            for chain in CHAINS:
                index += 1
                cell_id = f"cell-{index:04d}"
                params = {
                    "h": 3.0,
                    "beta": float(beta),
                    "M": m_value,
                    "chain": chain,
                }
                cells.append({"cell_id": cell_id, "params": params})
                output = root / "cells" / cell_id
                output.mkdir(parents=True)
                central = -2.0 * beta + 0.2 * (beta / m_value) ** 2
                np.savez(output / "bins.npz", energy=central + offsets)
                _json(
                    output / "manifest.json",
                    {
                        "status": "success",
                        "params": params,
                        "settings": {**SETTINGS, "bins": len(offsets)},
                        "provenance": PROVENANCE,
                        "resources": {"wall_seconds": 1.0 + chain},
                    },
                )
    _run_spec(
        root,
        "qmc-fixture",
        {**SETTINGS, "bins": len(offsets)},
        cells,
    )


def _measurement_artifact(root: Path, mode: str, chi: int) -> Path:
    artifact = root / "artifacts" / mode / f"chi-{chi}"
    rows = []
    mode_shift = 0.002 if mode == "ordinary" else 0.0
    chi_shift = 2e-5 if chi == 16 else 0.0
    for beta in BETAS:
        u = -2.0 * beta + mode_shift + chi_shift
        z = np.log(2.0) + beta**2 - beta * (mode_shift + chi_shift)
        rows.append(
            {
                "beta": float(beta),
                "z": z,
                "f": -z / beta,
                "u": u,
                "c": 2.0 * beta**2,
                "hermiticity_residual": 1e-10,
                "mode": mode,
                "chi": chi,
                "cutoff": 1e-12,
            }
        )
    dense = artifact / "dense.csv"
    public = artifact / "thermodynamics.csv"
    _csv(dense, rows)
    _csv(public, rows)
    _json(
        artifact / "manifest.json",
        {
            "status": "success",
            "config_sha256": "fixture",
            "mode": mode,
            "chi": chi,
            "cutoff": 1e-12,
            "dense_count": len(rows),
            "public_count": len(rows),
            "dense_sha256": hashlib.sha256(dense.read_bytes()).hexdigest(),
            "thermodynamics_sha256": hashlib.sha256(public.read_bytes()).hexdigest(),
        },
    )
    return artifact


def _pepo_fixture(evolution: Path, measurement: Path) -> None:
    evolution_cells = []
    for index, mode in enumerate(MODES, start=1):
        cell_id = f"cell-{index:04d}"
        params = {"compression_mode": mode}
        evolution_cells.append({"cell_id": cell_id, "params": params})
        _json(
            evolution / "cells" / cell_id / "manifest.json",
            {
                "status": "success",
                "params": params,
                "settings": SETTINGS,
                "provenance": PROVENANCE,
                "resources": {
                    "wall_seconds": 12.0,
                    "peak_memory_bytes": 1024,
                },
            },
        )
    _run_spec(evolution, "pepo-fixture", SETTINGS, evolution_cells)

    measure_cells = []
    index = 0
    for source_index, mode in enumerate(MODES, start=1):
        for chi in CHIS:
            index += 1
            cell_id = f"cell-{index:04d}"
            params = {
                "source_cell": f"cell-{source_index:04d}",
                "chi": chi,
            }
            artifact = _measurement_artifact(measurement, mode, chi)
            measure_cells.append({"cell_id": cell_id, "params": params})
            _json(
                measurement / "cells" / cell_id / "manifest.json",
                {
                    "status": "success",
                    "params": params,
                    "settings": SETTINGS,
                    "provenance": PROVENANCE,
                    "artifacts": {"measurement_root": str(artifact)},
                },
            )
    _run_spec(measurement, "pepo-measure-fixture", SETTINGS, measure_cells)


def _ed_fixture(root: Path) -> None:
    rows = []
    for beta in BETAS:
        z = np.log(2.0) + beta**2
        rows.append(
            {
                "beta": float(beta),
                "log_z_per_site": z,
                "f": -z / beta,
                "u": -2.0 * beta,
                "c": 2.0 * beta**2,
            }
        )
    table = root / "thermodynamics.csv"
    _csv(table, rows)
    _json(
        root / "manifest.json",
        {
            "status": "success",
            "state_count": 65536,
            "field": 3.0,
            "thermodynamics_sha256": hashlib.sha256(table.read_bytes()).hexdigest(),
        },
    )


@pytest.fixture
def complete_fixture(tmp_path):
    qmc = tmp_path / "qmc"
    pepo = tmp_path / "pepo"
    measure = tmp_path / "pepo-measure"
    ed = tmp_path / "ed"
    _qmc_fixture(qmc)
    _pepo_fixture(pepo, measure)
    _ed_fixture(ed)
    return qmc, pepo, measure, ed


def test_assemble_complete_h3_evidence(complete_fixture, tmp_path):
    qmc, pepo, measure, ed = complete_fixture
    output = tmp_path / "validation"

    assert (
        assemble(
            qmc,
            pepo,
            measure,
            output,
            ed_root=ed,
            bootstrap_samples=32,
        )
        == 0
    )

    expected = {
        "thermodynamics.csv",
        "convergence.csv",
        "resources.csv",
        "comparison.png",
        "comparison.pdf",
        "convergence.png",
        "convergence.pdf",
        "summary.json",
    }
    assert expected.issubset({path.name for path in output.iterdir()})
    assert all((output / name).stat().st_size > 0 for name in expected)
    with (output / "thermodynamics.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["method"] for row in rows} == {"QMC", "PEPO", "ED 4x4"}
    assert {row["mode"] for row in rows if row["method"] == "PEPO"} == set(MODES)
    assert {row["status"] for row in rows if row["method"] == "PEPO"} == {
        "chi_converged;D_not_assessed;trotter_not_assessed"
    }
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["setup"]["h"] == 3.0
    assert summary["completeness"] == {
        "qmc_cells": len(BETAS) * len(M_VALUES) * len(tuple(CHAINS)),
        "pepo_evolution_cells": 2,
        "pepo_measurement_cells": 4,
    }


def test_assemble_rejects_a_missing_qmc_chain(complete_fixture, tmp_path):
    qmc, pepo, measure, _ = complete_fixture
    (qmc / "cells" / "cell-0001" / "manifest.json").unlink()

    with pytest.raises(ValueError, match="missing successful QMC cell"):
        assemble(qmc, pepo, measure, tmp_path / "output", bootstrap_samples=8)


def test_assemble_rejects_a_missing_pepo_measurement(complete_fixture, tmp_path):
    qmc, pepo, measure, _ = complete_fixture
    (measure / "cells" / "cell-0001" / "manifest.json").unlink()

    with pytest.raises(ValueError, match="missing successful PEPO measurement cell"):
        assemble(qmc, pepo, measure, tmp_path / "output", bootstrap_samples=8)


def test_assemble_rejects_tampered_ed_table(complete_fixture, tmp_path):
    qmc, pepo, measure, ed = complete_fixture
    with (ed / "thermodynamics.csv").open("a", encoding="utf-8") as handle:
        handle.write("tampered\n")

    with pytest.raises(ValueError, match="ED thermodynamics hash mismatch"):
        assemble(
            qmc,
            pepo,
            measure,
            tmp_path / "output",
            ed_root=ed,
            bootstrap_samples=8,
        )
