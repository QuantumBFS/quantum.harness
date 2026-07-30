import json
from pathlib import Path

from oracle.oddcycle_local_hs_runner import expand_settings, run_batch


def test_batch_resume_does_not_repeat_completed_cells(tmp_path):
    settings = {
        "schema": "oddcycle-local-hs-settings-v1",
        "seed": 20260730,
        "cells": [
            {
                "id": "free-l2-path-edge",
                "mode": "free",
                "max_word_length": 2,
                "locality": "path-edge",
            },
            {
                "id": "portfolio-l1",
                "mode": "portfolio",
                "max_word_length": 1,
                "sample_count": 2,
            },
        ],
    }

    first = run_batch(settings, tmp_path, workers=1, resume=True)
    second = run_batch(settings, tmp_path, workers=1, resume=True)

    assert first.completed == 2
    assert second.completed == 0
    assert second.skipped == 2
    records = [
        json.loads(line)
        for line in (tmp_path / "manifest.jsonl").read_text().splitlines()
    ]
    assert len(records) == 2
    assert {record["cell_id"] for record in records} == {
        "free-l2-path-edge",
        "portfolio-l1",
    }


def test_frozen_settings_expand_to_40_stable_cells():
    settings = json.loads(
        Path("protocols/oddcycle-local-hs-v1/settings.json").read_text()
    )

    cells = expand_settings(settings)

    assert len(cells) == 40
    assert len({cell.id for cell in cells}) == 40
    assert cells == tuple(sorted(cells, key=lambda cell: cell.id))
