from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "aggregate_phase_scan.py"
SPEC = importlib.util.spec_from_file_location("aggregate_phase_scan", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AGGREGATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AGGREGATE)


def test_flatten_exposes_fingerprinted_source_revision() -> None:
    row = AGGREGATE._flatten(
        {
            "cell_id": "cell",
            "cell_index": 1,
            "machine": "wsl",
            "worker_id": 0,
            "seed": 123,
            "stability_retry": False,
            "stabilized": True,
            "config": {"m": 4},
            "run_spec": {"source_revision": "abc123"},
            "status": "COMPLETE",
        }
    )

    assert row["source_revision"] == "abc123"
