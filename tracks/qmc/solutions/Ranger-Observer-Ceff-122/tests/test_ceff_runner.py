import hashlib
import json
import re

import numpy as np

from ceffflow.cli import main
from ceffflow.runner import run_cell
from ceffflow.schema import CellConfig


def _clean_config() -> CellConfig:
    return CellConfig.model_validate(
        {
            "model": "clean_ising",
            "lengths": [4, 6, 8, 10],
            "channel": {"kind": "identity", "parameter": 0.0},
            "steps": 10,
            "burn_in": 0,
            "block_size": 5,
            "seed": 4,
        }
    )


def test_cell_manifest_and_replay_are_identical(tmp_path):
    output = tmp_path / "cell"
    first = run_cell(_clean_config(), output, cell_id="clean")
    first_bytes = (output / "blocks.npz").read_bytes()
    second = run_cell(_clean_config(), output, cell_id="clean")
    second_bytes = (output / "blocks.npz").read_bytes()
    assert first.blocks_sha256 == second.blocks_sha256
    assert first_bytes == second_bytes
    assert hashlib.sha256(second_bytes).hexdigest() == second.blocks_sha256
    payload = json.loads((output / "manifest.json").read_text())
    assert payload["status"] == "success"
    assert payload["normalization_ok"] is True


def test_cell_manifest_uses_declared_source_commit(tmp_path, monkeypatch):
    source_commit = "a" * 40
    monkeypatch.setenv("CEFFFLOW_SOURCE_COMMIT", source_commit)
    manifest = run_cell(_clean_config(), tmp_path / "cell", cell_id="clean")
    assert manifest.provenance["git_commit"] == source_commit


def test_cell_manifest_rejects_invalid_declared_source_commit(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("CEFFFLOW_SOURCE_COMMIT", "not-a-commit")
    with np.testing.assert_raises_regex(
        ValueError, re.escape("CEFFFLOW_SOURCE_COMMIT must be a 40-character")
    ):
        run_cell(_clean_config(), tmp_path / "cell", cell_id="clean")


def test_cell_cli_resolves_run_spec(tmp_path):
    spec = tmp_path / "run_spec.json"
    spec.write_text(
        json.dumps(
            {
                "result_root": "cells",
                "cells": [
                    {
                        "cell_id": "c0",
                        "settings": _clean_config().model_dump(mode="json"),
                    }
                ],
            }
        )
    )
    assert main(["cell", "--run-spec", str(spec), "--cell-id", "c0"]) == 0
    blocks = np.load(tmp_path / "cells" / "c0" / "blocks.npz")["blocks"]
    assert blocks.shape == (1, 4)


def test_cell_cli_defaults_to_sibling_cells_directory(tmp_path):
    spec = tmp_path / "run_spec.json"
    spec.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_id": "c0",
                        "settings": _clean_config().model_dump(mode="json"),
                    }
                ]
            }
        )
    )
    assert main(["cell", "--run-spec", str(spec), "--cell-id", "c0"]) == 0
    assert (tmp_path / "cells" / "c0" / "manifest.json").exists()


def test_benchmark_cli_writes_passing_clean_ising_result(tmp_path):
    assert main(["benchmark", "--output", str(tmp_path)]) == 0
    payload = json.loads((tmp_path / "benchmark.json").read_text())
    assert payload["clean_ising"]["passed"] is True


def test_analysis_verifies_hash_and_writes_summary(tmp_path):
    spec = tmp_path / "run_spec.json"
    spec.write_text(
        json.dumps(
            {
                "result_root": "cells",
                "cells": [
                    {
                        "cell_id": "clean",
                        "settings": _clean_config().model_dump(mode="json"),
                    }
                ],
            }
        )
    )
    run_cell(_clean_config(), tmp_path / "cells" / "clean", cell_id="clean")
    assert (
        main(
            [
                "analyze",
                "--run-spec",
                str(spec),
                "--output",
                str(tmp_path / "analysis"),
            ]
        )
        == 0
    )
    summary = json.loads((tmp_path / "analysis" / "summary.json").read_text())
    assert summary["cells_verified"] == 1
    assert (tmp_path / "analysis" / "ceff_resolution.png").exists()
    assert b"\r\n" not in (
        tmp_path / "analysis" / "ceff_resolution.csv"
    ).read_bytes()
