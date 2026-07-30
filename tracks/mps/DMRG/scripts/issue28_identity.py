#!/usr/bin/env python3
"""Issue #28 N1 随机初始化 identity-RG 认证入口。"""

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

from vmcrg_ref.identity_certification import (
    classify_identity_results,
    identity_seed_records,
    run_identity_certification,
)
from vmcrg_ref.issue28_protocol import load_issue28_protocol


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="运行 Issue #28 N1 纯神经随机初始化 identity-RG 认证"
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("config/issue28_easy_v1.json"),
        help="冻结的 Issue #28 总协议",
    )
    parser.add_argument(
        "--preset",
        choices=("smoke", "pilot", "formal"),
        required=True,
        help="运行规模；pilot 和 formal 必须由 Slurm 执行",
    )
    parser.add_argument("--output", type=Path, required=True, help="全新输出目录")
    parser.add_argument("--resume", action="store_true", help="校验后读取完整结果")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_identity_certification(
        load_issue28_protocol(args.protocol),
        args.preset,
        args.output,
        resume=args.resume,
    )
    print(
        "N1 identity-RG 完成 "
        f"初始化={report['initialization']} 分类={report['classification']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
