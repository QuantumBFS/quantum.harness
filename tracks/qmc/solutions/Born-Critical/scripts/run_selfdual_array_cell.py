#!/usr/bin/env python3
"""Execute one opaque Stage-4 self-dual run-spec cell."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import socket
import sys


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--cell-index", type=int, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from borncritical.selfdual import run_selfdual_trajectory

    spec = json.loads(args.run_spec.read_text())
    if not 1 <= args.cell_index <= len(spec["cells"]):
        raise ValueError("cell index outside run spec")
    cell = spec["cells"][args.cell_index - 1]
    params = cell["params"]
    settings = spec["settings"]
    cell_id = cell["cell_id"]
    destination = args.output_root / "cells" / cell_id
    temporary = args.output_root / "cells" / f".{cell_id}.incoming"
    if destination.exists() or temporary.exists():
        raise FileExistsError(f"refusing to overwrite {cell_id}")
    temporary.mkdir(parents=True)
    started = utc_now()
    size = int(params["size"])
    block_rows = max(
        int(settings["block_rows_floor"]),
        int(settings["block_rows_per_size"]) * size,
    )
    measurement_rows = int(
        params.get("measurement_rows", settings.get("measurement_rows", 0))
    )
    if measurement_rows < 1:
        raise ValueError("measurement_rows must be positive")
    measurement_rows -= measurement_rows % block_rows
    try:
        result = run_selfdual_trajectory(
            size=size,
            replica=int(params["replica"]),
            seed=int(params["seed"]),
            burnin_rows=int(settings["burnin_rows_per_size"]) * size,
            measurement_rows=measurement_rows,
            block_rows=block_rows,
            qr_interval=int(params["qr_interval"]),
        )
        observables_path = temporary / "observables.json"
        atomic_json(observables_path, result.to_dict())
        means = {}
        for name in (
            "shannon_rate",
            "rao_blackwell_shannon_rate",
            "log_norm_rate",
            "e_density",
            "m_density",
        ):
            values = [getattr(block, name) for block in result.blocks]
            means[f"mean_{name}"] = sum(values) / len(values)
            means[f"standard_error_{name}"] = (
                float("nan")
                if len(values) < 2
                else math.sqrt(
                    sum((value - means[f"mean_{name}"]) ** 2 for value in values)
                    / (len(values) * (len(values) - 1))
                )
            )
        manifest = {
            "schema_version": 1,
            "run_id": spec["run_id"],
            "cell_id": cell_id,
            "status": "success",
            "started_at": started,
            "finished_at": utc_now(),
            "hostname": socket.gethostname(),
            "params": params,
            "settings": settings,
            "result": {
                **means,
                "n_blocks": len(result.blocks),
                "measurement_rows": result.measurement_rows,
                "burnin_rows": result.burnin_rows,
                "block_rows": result.block_rows,
                "rows_per_second": result.rows_per_second,
                "maximum_probability_normalization_error": result.maximum_probability_normalization_error,
                "maximum_covariance_purity_residual": result.maximum_covariance_purity_residual,
                "maximum_qr_orthogonality_error": result.maximum_qr_orthogonality_error,
            },
            "resources": {
                "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
                "slurm_array_task_id": os.environ.get("SLURM_ARRAY_TASK_ID"),
            },
            "observables_sha256": hashlib.sha256(
                observables_path.read_bytes()
            ).hexdigest(),
        }
        atomic_json(temporary / "manifest.json", manifest)
        temporary.replace(destination)
        print(
            f"[selfdual] {cell_id} h={means['mean_shannon_rate']:.12g} "
            f"e={means['mean_e_density']:.6f} "
            f"m={means['mean_m_density']:.6f}",
            flush=True,
        )
        return 0
    except Exception as error:
        atomic_json(
            temporary / "manifest.json",
            {
                "schema_version": 1,
                "run_id": spec.get("run_id"),
                "cell_id": cell_id,
                "status": "failed",
                "started_at": started,
                "finished_at": utc_now(),
                "hostname": socket.gethostname(),
                "params": params,
                "error": {"type": type(error).__name__, "message": str(error)},
            },
        )
        temporary.replace(destination)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
