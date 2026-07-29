#!/usr/bin/env python3
"""Run all production replicas for one size using the C++ transfer kernel."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
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


def run_one(payload: dict[str, Any]) -> dict[str, Any]:
    cell = payload["cell"]
    settings = payload["settings"]
    work = Path(payload["work"])
    binary = str(payload["binary"])
    size = int(cell["params"]["size"])
    replica = int(cell["params"]["replica"])
    p = float(settings["p"])
    coupling = 0.5 * math.log((1.0 - p) / p)
    fingerprint_payload = json.dumps(
        {
            "base_seed": int(settings["base_seed"]),
            "model": "nishimori-rbim-cpp",
            "size": size,
            "replica": replica,
            "stream": "bonds",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    fingerprint = hashlib.blake2b(
        fingerprint_payload,
        digest_size=16,
        person=b"borncritical-rng",
    ).hexdigest()
    seed = int(fingerprint[:16], 16)
    measurement = int(settings["measurement_rows_by_size"][str(size)])
    block_size = int(settings["output_block_size"])
    burn_in = int(settings["burn_in_rows_per_size"]) * size
    raw_path = work / f"{cell['cell_id']}.bin"
    command = [
        binary,
        str(size),
        str(seed),
        f"{p:.17g}",
        f"{coupling:.17g}",
        str(int(settings["qr_interval"])),
        str(burn_in),
        str(measurement),
        str(block_size),
        "1",
        str(raw_path),
    ]
    started = time.perf_counter()
    process = subprocess.run(command, check=True, capture_output=True, text=True)
    elapsed = time.perf_counter() - started
    reported = {}
    for line in process.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            reported[key] = float(value)
    blocks = np.fromfile(raw_path, dtype=np.float64)
    raw_path.unlink()
    expected = measurement // block_size
    if blocks.size != expected or not np.all(np.isfinite(blocks)):
        raise RuntimeError(
            f"{cell['cell_id']} invalid block count {blocks.size} != {expected}"
        )
    correlation = float(np.corrcoef(blocks[:-1], blocks[1:])[0, 1])
    if not math.isfinite(correlation):
        correlation = 0.0
    return {
        "cell": cell,
        "blocks": blocks,
        "coupling": coupling,
        "seed": seed,
        "fingerprint": fingerprint,
        "elapsed": elapsed,
        "reported": reported,
        "correlation": correlation,
        "burn_in": burn_in,
        "measurement": measurement,
        "block_size": block_size,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--group-index", type=int, required=True)
    parser.add_argument("--groups", type=int, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--selected-size", type=int)
    parser.add_argument("--replica-min", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec = json.loads(args.run_spec.read_text(encoding="utf-8"))
    sizes = sorted({int(cell["params"]["size"]) for cell in spec["cells"]})
    if args.selected_size is None:
        if len(sizes) != args.groups or not 1 <= args.group_index <= len(sizes):
            raise ValueError("group index/count does not match run-spec sizes")
        selected_size = sizes[args.group_index - 1]
    else:
        selected_size = args.selected_size
        if selected_size not in sizes:
            raise ValueError(f"selected size {selected_size} is absent from run spec")
    cells = [
        cell for cell in spec["cells"]
        if int(cell["params"]["size"]) == selected_size
        and int(cell["params"]["replica"]) >= args.replica_min
    ]
    if not cells:
        raise ValueError("selection contains no cells")
    settings = spec["settings"]
    output_root = args.output_root.resolve()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    (output_root / "cells").mkdir(parents=True, exist_ok=True)
    failures: list[dict[str, str]] = []

    payloads = [
        {
            "cell": cell,
            "settings": settings,
            "work": str(work),
            "binary": str(args.binary.resolve()),
        }
        for cell in cells
    ]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_one, payload): payload for payload in payloads}
        for future in as_completed(futures):
            payload = futures[future]
            cell = payload["cell"]
            cell_id = cell["cell_id"]
            destination = output_root / "cells" / cell_id
            temporary = output_root / "cells" / f".{cell_id}.incoming"
            temporary.mkdir()
            started_at = utc_now()
            try:
                result = future.result()
                block_path = temporary / "block-phi.npy"
                np.save(block_path, result["blocks"], allow_pickle=False)
                blocks = result["blocks"]
                manifest = {
                    "schema_version": 1,
                    "run_id": spec["run_id"],
                    "cell_id": cell_id,
                    "status": "success",
                    "started_at": started_at,
                    "finished_at": utc_now(),
                    "params": cell["params"],
                    "settings": settings,
                    "provenance": spec["provenance"],
                    "result": {
                        "coupling": result["coupling"],
                        "burn_in_rows": result["burn_in"],
                        "measurement_rows": result["measurement"],
                        "block_size": result["block_size"],
                        "n_blocks": int(blocks.size),
                        "mean_phi": float(np.mean(blocks)),
                        "standard_error_phi": float(
                            np.std(blocks, ddof=1) / math.sqrt(blocks.size)
                        ),
                        "adjacent_block_correlation": result["correlation"],
                        "maximum_orthogonality_error": result["reported"][
                            "maximum_orthogonality_error"
                        ],
                        "rows_per_second": result["reported"]["rows_per_second"],
                        "rng_fingerprint": result["fingerprint"],
                        "rng_seed_uint64": result["seed"],
                        "wall_seconds": result["elapsed"],
                    },
                    "resources": {
                        "max_rss_kib_group_parent": resource.getrusage(
                            resource.RUSAGE_SELF
                        ).ru_maxrss,
                        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
                        "slurm_array_task_id": os.environ.get(
                            "SLURM_ARRAY_TASK_ID"
                        ),
                    },
                    "artifacts": {
                        "block_phi": block_path.name,
                        "block_phi_sha256": sha256(block_path),
                    },
                }
                atomic_json(temporary / "manifest.json", manifest)
                temporary.replace(destination)
                print(
                    f"[production] {cell_id} L={selected_size} "
                    f"replica={cell['params']['replica']} "
                    f"phi={manifest['result']['mean_phi']:.12g} "
                    f"speed={manifest['result']['rows_per_second']:.0f}",
                    flush=True,
                )
            except Exception as error:
                failures.append(
                    {"cell_id": cell_id, "error": f"{type(error).__name__}: {error}"}
                )
                atomic_json(
                    temporary / "manifest.json",
                    {
                        "schema_version": 1,
                        "run_id": spec["run_id"],
                        "cell_id": cell_id,
                        "status": "failed",
                        "params": cell["params"],
                        "settings": settings,
                        "provenance": spec["provenance"],
                        "error": failures[-1]["error"],
                    },
                )
                temporary.replace(destination)
    atomic_json(
        output_root / "group-manifest.json",
        {
            "status": "success" if not failures else "failed",
            "group_index": args.group_index,
            "size": selected_size,
            "cells": len(cells),
            "failures": failures,
        },
    )
    return 0 if not failures else 3


if __name__ == "__main__":
    raise SystemExit(main())
