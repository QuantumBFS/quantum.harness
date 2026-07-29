#!/usr/bin/env python3
"""Run one opaque RBIM scan cell and atomically write its manifest."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import shutil
import socket
import sys
from typing import Any

import numpy as np


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-spec", type=Path, required=True)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--cell-index", type=int)
    selector.add_argument("--cell-id")
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def choose_cell(spec: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    cells = spec["cells"]
    if args.cell_index is not None:
        if not 1 <= args.cell_index <= len(cells):
            raise ValueError(f"cell index {args.cell_index} is outside 1..{len(cells)}")
        return cells[args.cell_index - 1]
    return next(cell for cell in cells if cell["cell_id"] == args.cell_id)


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root / "src"))
    from borncritical.conventions import nishimori_coupling
    from borncritical.rbim import simulate_rbim_replica

    spec = json.loads(args.run_spec.read_text(encoding="utf-8"))
    cell = choose_cell(spec, args)
    cell_id = cell["cell_id"]
    params = cell["params"]
    settings = {**spec.get("settings", {}), **cell.get("settings", {})}
    output_root = args.output_root.resolve()
    destination = output_root / "cells" / cell_id
    temporary = output_root / "cells" / f".{cell_id}.incoming"
    if destination.exists() or temporary.exists():
        raise FileExistsError(f"refusing to overwrite cell {cell_id}")
    temporary.mkdir(parents=True)
    started_at = utc_now()

    size = int(params["size"])
    replica = int(params["replica"])
    p = float(settings["p"])
    coupling = nishimori_coupling(p)
    qr_interval = int(settings["qr_interval"])
    comparison_interval = int(settings["comparison_qr_interval"])
    burn_in = int(settings["burn_in_rows_per_size"]) * size
    measurement_rows = int(settings["measurement_rows"])
    block_size = max(
        int(settings["block_size_floor"]),
        int(settings["block_size_per_size"]) * size,
    )
    interval_multiple = math.lcm(qr_interval, comparison_interval)
    block_size = (
        (block_size + interval_multiple - 1) // interval_multiple
    ) * interval_multiple
    measurement_rows -= measurement_rows % block_size

    try:
        main_result = simulate_rbim_replica(
            size=size,
            replica=replica,
            p=p,
            coupling=coupling,
            base_seed=int(settings["base_seed"]),
            qr_interval=qr_interval,
            burn_in_rows=burn_in,
            measurement_rows=measurement_rows,
            block_size=block_size,
        )
        comparison = simulate_rbim_replica(
            size=size,
            replica=replica,
            p=p,
            coupling=coupling,
            base_seed=int(settings["base_seed"]),
            qr_interval=comparison_interval,
            burn_in_rows=burn_in,
            measurement_rows=measurement_rows,
            block_size=block_size,
        )
        block_path = temporary / "block-phi.npy"
        comparison_path = temporary / "block-phi-comparison.npy"
        np.save(block_path, main_result.block_phi, allow_pickle=False)
        np.save(comparison_path, comparison.block_phi, allow_pickle=False)
        qr_mean_difference = abs(main_result.mean_phi - comparison.mean_phi)
        manifest = {
            "schema_version": 1,
            "run_id": spec["run_id"],
            "cell_id": cell_id,
            "status": "success",
            "started_at": started_at,
            "finished_at": utc_now(),
            "hostname": socket.gethostname(),
            "params": params,
            "settings": settings,
            "provenance": spec.get("provenance", {}),
            "result": {
                "coupling": coupling,
                "burn_in_rows": burn_in,
                "measurement_rows": measurement_rows,
                "block_size": block_size,
                "n_blocks": int(main_result.block_phi.size),
                "mean_phi": main_result.mean_phi,
                "standard_error_phi": main_result.standard_error_phi,
                "adjacent_block_correlation": (
                    main_result.adjacent_block_correlation
                ),
                "qr_interval_mean_phi_absolute_difference": qr_mean_difference,
                "maximum_orthogonality_error": max(
                    main_result.maximum_orthogonality_error,
                    comparison.maximum_orthogonality_error,
                ),
                "rows_per_second": main_result.rows_per_second,
                "rng_fingerprint": main_result.rng_fingerprint,
                "max_block_phi_absolute_difference": float(
                    np.max(
                        np.abs(
                            main_result.block_phi - comparison.block_phi
                        )
                    )
                ),
            },
            "resources": {
                "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
                "slurm_array_task_id": os.environ.get("SLURM_ARRAY_TASK_ID"),
            },
            "artifacts": {
                "block_phi": block_path.name,
                "block_phi_sha256": sha256(block_path),
                "comparison_block_phi": comparison_path.name,
                "comparison_block_phi_sha256": sha256(comparison_path),
            },
        }
        atomic_json(temporary / "manifest.json", manifest)
        temporary.replace(destination)
        print(
            f"[rbim-cell] {cell_id} L={size} replica={replica} "
            f"phi={main_result.mean_phi:.12g} "
            f"se={main_result.standard_error_phi:.3e}",
            flush=True,
        )
        return 0
    except Exception as error:
        manifest = {
            "schema_version": 1,
            "run_id": spec.get("run_id"),
            "cell_id": cell_id,
            "status": "failed",
            "started_at": started_at,
            "finished_at": utc_now(),
            "hostname": socket.gethostname(),
            "params": params,
            "settings": settings,
            "provenance": spec.get("provenance", {}),
            "error": {
                "type": type(error).__name__,
                "message": str(error),
            },
        }
        atomic_json(temporary / "manifest.json", manifest)
        temporary.replace(destination)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
