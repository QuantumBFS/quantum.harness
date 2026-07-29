import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "run_cell.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("issue147_run_cell", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dispatcher_does_not_import_pepo_stack_at_module_load():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "from qh147 import qmc, run" not in source
    assert "from qh147 import run" not in source.split("def _load_pepo_stack", 1)[0]


def _spec(tmp_path):
    return {
        "run_id": "fixture",
        "run_dir": str(tmp_path / "run"),
        "settings": {"shared": 1},
        "provenance": {"protocol": "fixture-v1"},
        "cells": [
            {"cell_id": "cell-0001", "params": {"h": 3.0, "beta": 0.5, "M": 64, "chain": 2}},
            {"cell_id": "cell-0002", "params": {"h": 3.0, "beta": 0.8, "M": 128, "chain": 3}, "settings": {"cell": 2}},
        ],
    }


def test_qmc_dry_run_selects_one_based_cell_and_echoes_payload(tmp_path, monkeypatch):
    module = _load_module()
    run_spec = tmp_path / "run-spec.json"
    run_spec.write_text(json.dumps(_spec(tmp_path)), encoding="utf-8")
    monkeypatch.setenv("HARNESS_RUN_SPEC", str(run_spec))
    monkeypatch.setenv("HARNESS_CELL_INDEX", "2")

    assert module.main(["--kind", "qmc", "--dry-run"]) == 0

    manifest_path = tmp_path / "run" / "cells" / "cell-0002" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "rehearsed"
    assert manifest["params"] == _spec(tmp_path)["cells"][1]["params"]
    assert manifest["settings"] == {"shared": 1, "cell": 2}
    assert manifest["provenance"] == {"protocol": "fixture-v1"}


def test_exact_cell_id_overrides_array_index(tmp_path, monkeypatch):
    module = _load_module()
    run_spec = tmp_path / "run-spec.json"
    run_spec.write_text(json.dumps(_spec(tmp_path)), encoding="utf-8")
    monkeypatch.setenv("HARNESS_RUN_SPEC", str(run_spec))
    monkeypatch.setenv("HARNESS_CELL_ID", "cell-0001")
    monkeypatch.setenv("HARNESS_CELL_INDEX", "2")

    assert module.main(["--kind", "qmc", "--dry-run"]) == 0
    assert (tmp_path / "run" / "cells" / "cell-0001" / "manifest.json").is_file()


def test_windows_run_dir_is_portable_on_cluster(tmp_path, monkeypatch):
    module = _load_module()
    payload = _spec(tmp_path)
    payload["run_dir"] = "nested\\qmc-run"
    run_spec = tmp_path / "run-spec.json"
    run_spec.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HARNESS_RUN_SPEC", str(run_spec))
    monkeypatch.setenv("HARNESS_CELL_INDEX", "1")

    assert module.main(["--kind", "qmc", "--dry-run"]) == 0
    assert (
        tmp_path / "nested" / "qmc-run" / "cells" / "cell-0001" / "manifest.json"
    ).is_file()


def test_success_manifest_is_never_replaced(tmp_path, monkeypatch):
    module = _load_module()
    payload = _spec(tmp_path)
    run_spec = tmp_path / "run-spec.json"
    run_spec.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "run" / "cells" / "cell-0001"
    output.mkdir(parents=True)
    original = '{"status":"success","marker":"keep"}\n'
    (output / "manifest.json").write_text(original, encoding="utf-8")
    monkeypatch.setenv("HARNESS_RUN_SPEC", str(run_spec))
    monkeypatch.setenv("HARNESS_CELL_ID", "cell-0001")

    assert module.main(["--kind", "qmc", "--dry-run"]) == 0
    assert (output / "manifest.json").read_text(encoding="utf-8") == original


def test_pepo_dry_run_validates_current_production_modes(tmp_path, monkeypatch):
    module = _load_module()
    payload = {
        "run_id": "pepo-fixture",
        "run_dir": str(tmp_path / "pepo"),
        "settings": {},
        "provenance": {},
        "cells": [{"cell_id": "cell-0001", "params": {"compression_mode": "thermodynamic"}}],
    }
    run_spec = tmp_path / "run-spec.json"
    run_spec.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("HARNESS_RUN_SPEC", str(run_spec))
    monkeypatch.setenv("HARNESS_CELL_INDEX", "1")

    assert module.main(["--kind", "pepo", "--dry-run"]) == 0
    manifest = json.loads((tmp_path / "pepo" / "cells" / "cell-0001" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "rehearsed"
    assert manifest["params"]["compression_mode"] == "thermodynamic"
