import csv
import hashlib
import json

import pytest

from qh147.deadline_figures import load_ed_diagnostic


def _write_ed_fixture(root):
    root.mkdir(parents=True)
    table = root / "thermodynamics.csv"
    with table.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("beta", "log_z_per_site", "f", "u", "c"))
        writer.writeheader()
        for beta in (0.1, 0.2, 0.3):
            writer.writerow({"beta": beta, "log_z_per_site": 0.7, "f": -7.0, "u": -beta, "c": beta**2})
    digest = hashlib.sha256(table.read_bytes()).hexdigest()
    (root / "manifest.json").write_text(
        json.dumps({"status": "success", "state_count": 65536, "thermodynamics_sha256": digest}),
        encoding="utf-8",
    )
    return table


def test_load_ed_diagnostic_checks_complete_state_count_and_hash(tmp_path):
    table = _write_ed_fixture(tmp_path / "assembled")

    rows = load_ed_diagnostic(tmp_path / "assembled")

    assert len(rows) == 3
    assert rows[1]["u"] == -0.2

    table.write_text(table.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_ed_diagnostic(tmp_path / "assembled")
