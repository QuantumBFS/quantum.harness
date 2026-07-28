import hashlib
import json

from qh147.run_ed import config_digest, load_config, main


def _config(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
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
    return path


def test_rehearsal_lists_ten_cells_and_complete_dimension(tmp_path):
    config = _config(tmp_path)
    root = tmp_path / "run"
    assert main(
        [
            "--config",
            str(config),
            "--run-root",
            str(root),
            "--rehearse-all",
        ]
    ) == 0
    payload = json.loads(
        (root / "h-3" / "rehearsal.json").read_text()
    )
    assert len(payload["cells"]) == 10
    assert sum(
        cell["recovered_dimension"] for cell in payload["cells"]
    ) == 16


def test_one_cell_writes_a_hashed_success_manifest_and_reuses_it(
    tmp_path,
):
    config = _config(tmp_path)
    root = tmp_path / "run"
    args = [
        "--config",
        str(config),
        "--run-root",
        str(root),
        "--cell-index",
        "1",
    ]
    assert main(args) == 0
    cell = root / "h-3" / "A1-p+1"
    manifest = json.loads((cell / "manifest.json").read_text())
    spectrum = cell / "eigenvalues.npz"
    assert manifest["status"] == "success"
    expected = hashlib.sha256(spectrum.read_bytes()).hexdigest()
    assert manifest["provenance"]["spectrum_sha256"] == expected
    before = spectrum.stat().st_mtime_ns
    assert main(args) == 0
    assert spectrum.stat().st_mtime_ns == before


def test_config_digest_is_independent_of_json_formatting(tmp_path):
    compact = tmp_path / "compact.json"
    pretty = tmp_path / "pretty.json"
    payload = json.loads(_config(tmp_path).read_text(encoding="utf-8"))
    compact.write_text(
        json.dumps(payload, separators=(",", ":")),
        encoding="utf-8",
    )
    pretty.write_text(
        json.dumps(payload, indent=2) + "\r\n",
        encoding="utf-8",
    )
    assert config_digest(load_config(compact)) == config_digest(
        load_config(pretty)
    )
