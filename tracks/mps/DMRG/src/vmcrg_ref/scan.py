"""Opaque run-spec cell resolution for local and Slurm parameter scans."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunSpecCell:
    run_id: str
    run_dir: str
    cell_id: str
    params: dict[str, Any]
    settings: dict[str, Any]
    provenance: dict[str, Any]


def resolve_run_spec_cell(path: str | Path, array_index: int) -> RunSpecCell:
    if array_index < 1:
        raise ValueError("array_index is one-based and must be positive")
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    cells = payload.get("cells", [])
    if array_index > len(cells):
        raise IndexError("array_index exceeds the run-spec cell count")
    cell = cells[array_index - 1]
    return RunSpecCell(
        run_id=str(payload["run_id"]),
        run_dir=str(payload["run_dir"]),
        cell_id=str(cell["cell_id"]),
        params=dict(cell.get("params", {})),
        settings=dict(payload.get("settings", {})) | dict(cell.get("settings", {})),
        provenance=dict(payload.get("provenance", {})),
    )
