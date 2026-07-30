from __future__ import annotations

import json

from vmcrg_ref.scan import resolve_run_spec_cell


def test_resolve_run_spec_cell_uses_one_based_array_index(tmp_path) -> None:
    path = tmp_path / "run_spec.json"
    path.write_text(
        json.dumps(
            {
                "run_id": "test",
                "run_dir": "results/test",
                "settings": {"length": 45},
                "provenance": {"challenge": 28},
                "cells": [
                    {"cell_id": "cell-0001", "params": {"chi": 2, "seed": 11}},
                    {"cell_id": "cell-0002", "params": {"chi": 4, "seed": 12}},
                ],
            }
        ),
        encoding="utf-8",
    )
    resolved = resolve_run_spec_cell(path, 2)
    assert resolved.cell_id == "cell-0002"
    assert resolved.params == {"chi": 4, "seed": 12}
    assert resolved.settings == {"length": 45}
    assert resolved.provenance == {"challenge": 28}
