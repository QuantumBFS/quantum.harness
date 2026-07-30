#!/usr/bin/env python3
"""Issue #28 N4 local 2+2+1 formal coordinator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="在本机以 2+2+1 波次运行 Issue #28 N4 五种子正式实验"
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("config/issue28_formal_v1.json"),
        help="N3 后冻结的正式协议",
    )
    parser.add_argument("--output", type=Path, required=True, help="N4 独立输出根目录")
    parser.add_argument(
        "--workers-per-bundle",
        type=int,
        default=8,
        help="每个 formal bundle 的 Issue #28 worker 数",
    )
    parser.add_argument(
        "--max-parallel-bundles",
        type=int,
        default=2,
        help="同时运行的 formal bundle 数，最多为 2",
    )
    parser.add_argument(
        "--minimum-available-gib",
        type=float,
        default=12.0,
        help="启动第二个 bundle 所需的可用内存下限（GiB）",
    )
    parser.add_argument("--resume", action="store_true", help="哈希校验后恢复")
    parser.add_argument(
        "--allow-large-local",
        action="store_true",
        help="显式授权在本机执行大型 N4 计算",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from vmcrg_ref.local_execution import run_local_formal

    result = run_local_formal(
        args.protocol,
        args.output,
        workers_per_bundle=args.workers_per_bundle,
        max_parallel_bundles=args.max_parallel_bundles,
        minimum_available_gib=args.minimum_available_gib,
        resume=args.resume,
        allow_large_local=args.allow_large_local,
    )
    print(
        json.dumps(
            {
                "分类": result.get("classification"),
                "已完成 bundle": result.get("completed", []),
                "失败 bundle": result.get("failed", []),
                "最大并发": result.get("maximum_observed_parallel", 0),
                "执行策略": result.get("execution_policy", "LOCAL_COMPUTE_DEVIATION"),
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0 if result.get("classification") not in {"CORRECTNESS_FAILURE", "PROTOCOL_FAILURE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
