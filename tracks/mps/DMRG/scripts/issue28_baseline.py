#!/usr/bin/env python3
"""Issue #28 的 B0 传统 VMCRG 基线认证入口。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vmcrg_ref.baseline_certification import certify_traditional_baseline
from vmcrg_ref.issue28_protocol import load_issue28_protocol


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="认证 Issue #28 的传统 13 算符 VMCRG 基线"
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("config/issue28_easy_v1.json"),
        help="冻结的 Issue #28 总协议",
    )
    parser.add_argument(
        "--b0-config",
        type=Path,
        default=Path("config/issue28_b0_v1.json"),
        help="B0 训练、验证和自相关预算",
    )
    parser.add_argument(
        "--preset",
        choices=("smoke", "formal"),
        default="formal",
        help="smoke 只验证连通性；formal 执行完整统计认证",
    )
    parser.add_argument("--output", type=Path, required=True, help="全新输出目录")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    protocol = load_issue28_protocol(args.protocol)
    report = certify_traditional_baseline(
        protocol,
        args.output,
        preset=args.preset,
        config_path=args.b0_config,
    )
    print(
        "B0传统基线完成 "
        f"分类={report['classification']} "
        f"原因={report['reason']} "
        f"输出={args.output.resolve()}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
