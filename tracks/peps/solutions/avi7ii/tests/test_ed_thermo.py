import csv
import json

import numpy as np
import pytest

from qh147.ed_thermo import assemble
from qh147.exact import thermal_from_spectrum
from qh147.model import tfim_dense
from qh147.run_ed import main as run_ed


def _complete_run(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "l": 2,
                "j": 1.0,
                "field": 3.0,
                "boundary": "open",
                "operator": "pauli",
                "irreps": ["A1", "A2", "B1", "B2", "E"],
                "parities": [1, -1],
                "beta_grid": {
                    "start": 0.025,
                    "stop": 0.1,
                    "step": 0.025,
                },
            }
        ),
        encoding="utf-8",
    )
    root = tmp_path / "run"
    for index in range(1, 11):
        assert run_ed(
            [
                "--config",
                str(config),
                "--run-root",
                str(root),
                "--cell-index",
                str(index),
            ]
        ) == 0
    return config, root


def test_complete_assembly_matches_direct_thermodynamics(tmp_path):
    config, root = _complete_run(tmp_path)
    output = tmp_path / "assembled"
    assert assemble(config, root, output) == 0
    with (output / "thermodynamics.csv").open(
        newline="",
        encoding="utf-8",
    ) as handle:
        rows = list(csv.DictReader(handle))
    spectrum = np.linalg.eigvalsh(
        tfim_dense(2, 2, j=1.0, h=3.0)
    )
    for row in rows:
        direct = thermal_from_spectrum(
            spectrum,
            beta=float(row["beta"]),
            nsites=4,
        )
        assert np.isclose(
            float(row["log_z_per_site"]),
            direct.log_z / 4,
        )
        assert np.isclose(float(row["u"]), direct.u)
        assert np.isclose(float(row["c"]), direct.c)


def test_assembly_rejects_a_missing_sector(tmp_path):
    config, root = _complete_run(tmp_path)
    (root / "h-3" / "E-p-1" / "manifest.json").unlink()
    with pytest.raises(ValueError, match="missing successful sector"):
        assemble(config, root, tmp_path / "assembled")


def test_assembly_rejects_a_corrupt_spectrum(tmp_path):
    config, root = _complete_run(tmp_path)
    path = root / "h-3" / "A1-p+1" / "eigenvalues.npz"
    path.write_bytes(path.read_bytes() + b"corrupt")
    with pytest.raises(ValueError, match="hash mismatch"):
        assemble(config, root, tmp_path / "assembled")


def test_assembly_rejects_a_convention_mismatch(tmp_path):
    config, root = _complete_run(tmp_path)
    path = root / "h-3" / "A1-p+1" / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["settings"]["j"] = 0.5
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="sector convention mismatch"):
        assemble(config, root, tmp_path / "assembled")


def test_assembly_rejects_duplicate_logical_sectors(tmp_path):
    config, root = _complete_run(tmp_path)
    payload = json.loads(config.read_text(encoding="utf-8"))
    payload["irreps"] = ["A1", "A1", "A2", "B1", "B2", "E"]
    config.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate logical sector"):
        assemble(config, root, tmp_path / "assembled")
