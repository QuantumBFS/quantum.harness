#!/usr/bin/env python3
"""Benchmark naive m² determinant and tensor-square factorized weight paths."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy.linalg import expm

from tensor_square.dqmc import direct_log_weight, structured_log_weight


def timed(callable_, repeats: int) -> float:
    start = perf_counter()
    for _ in range(repeats):
        callable_()
    return (perf_counter() - start) / repeats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=200)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for m in (3, 4, 6, 8):
        rng = np.random.default_rng(8100 + m)
        x = np.eye(m)
        for _slice in range(10):
            x = expm(rng.normal(scale=0.12, size=(m, m))) @ x
        sign, direct = direct_log_weight(x)
        structured = structured_log_weight(x)
        direct_time = timed(lambda: direct_log_weight(x), args.repeats)
        structured_time = timed(
            lambda: structured_log_weight(x), args.repeats
        )
        wedge_dimension = m * (m - 1) // 2
        naive_bytes = (m * m) ** 2 * 8
        structured_bytes = m * m * 16 + wedge_dimension**2 * 8
        rows.append(
            {
                "m": m,
                "direct_sign": sign,
                "log_weight_error": abs(direct - structured),
                "direct_seconds": direct_time,
                "structured_seconds": structured_time,
                "time_speedup": direct_time / structured_time,
                "naive_matrix_bytes": naive_bytes,
                "structured_matrix_bytes": structured_bytes,
                "memory_ratio": naive_bytes / structured_bytes,
            }
        )
        print(
            f"m={m} speedup={direct_time / structured_time:.2f} "
            f"memory_ratio={naive_bytes / structured_bytes:.2f}",
            flush=True,
        )
    with (args.output_dir / "table.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    (args.output_dir / "summary.json").write_text(
        json.dumps(
            {
                "repeats": args.repeats,
                "blas_threads": 1,
                "rows": rows,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
