#!/usr/bin/env python3
"""Issue #28 N4 五种子五轮三臂正式实验入口。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _load_api():
    from vmcrg_ref.formal import (
        build_formal_bundle_plan,
        classify_formal_root,
        run_formal_bundle,
    )

    globals().update(
        build_formal_bundle_plan=build_formal_bundle_plan,
        classify_formal_root=classify_formal_root,
        run_formal_bundle=run_formal_bundle,
    )
    return build_formal_bundle_plan, classify_formal_root, run_formal_bundle


def __getattr__(name: str):
    if name in {
        "build_formal_bundle_plan",
        "classify_formal_root",
        "run_formal_bundle",
    }:
        _load_api()
        return globals()[name]
    raise AttributeError(name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行 Issue #28 N4 五种子五轮正式实验")
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("config/issue28_formal_v1.json"),
        help="N3 后冻结的正式协议",
    )
    parser.add_argument("--bundle", required=True, help="formal-1 到 formal-5")
    parser.add_argument("--output", type=Path, required=True, help="种子独立输出目录")
    parser.add_argument(
        "--backend",
        choices=("local", "slurm"),
        default="slurm",
        help="正式实验后端；local 必须显式授权",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="每个正式 seed bundle 的最大 worker 数",
    )
    parser.add_argument(
        "--allow-large-local",
        action="store_true",
        help="显式授权在本机执行大型 N4 bundle",
    )
    parser.add_argument("--resume", action="store_true", help="哈希校验后续跑")
    parser.add_argument("--dry-run", action="store_true", help="只输出冻结计划")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from vmcrg_ref.formal_protocol import load_formal_execution_protocol

    _, _, run_formal_bundle = _load_api()
    protocol, execution = load_formal_execution_protocol(args.protocol)
    report = run_formal_bundle(
        protocol,
        args.bundle,
        args.output,
        args.backend,
        args.resume,
        formal_execution=execution,
        dry_run=args.dry_run,
        allow_large_local=args.allow_large_local,
        workers=args.workers,
    )
    print(
        f"N4 {args.bundle} {'计划' if args.dry_run else '运行'}完成 "
        f"轮数={len(report['rounds'])}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
