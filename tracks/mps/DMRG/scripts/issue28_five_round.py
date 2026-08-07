#!/usr/bin/env python3
"""Issue #28 N3 单种子 neural-to-neural 多轮试运行入口。"""

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
    from vmcrg_ref.five_round import five_round_pilot_bundle, run_five_round_chain

    globals().update(
        five_round_pilot_bundle=five_round_pilot_bundle,
        run_five_round_chain=run_five_round_chain,
    )
    return five_round_pilot_bundle, run_five_round_chain


def __getattr__(name: str):
    if name in {"five_round_pilot_bundle", "run_five_round_chain"}:
        _load_api()
        return globals()[name]
    raise AttributeError(name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="运行 Issue #28 N3 单种子 neural-to-neural 五轮试运行"
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("config/issue28_easy_v1.json"),
        help="冻结的 Issue #28 总协议",
    )
    parser.add_argument(
        "--preset",
        choices=("smoke", "pilot"),
        required=True,
        help="smoke 可本地短跑；五轮 pilot 必须使用 Slurm",
    )
    parser.add_argument("--rounds", type=int, default=5, help="连续 RG 轮数")
    parser.add_argument(
        "--backend",
        choices=("local", "slurm"),
        required=True,
        help="五轮计算必须选择 slurm",
    )
    parser.add_argument("--output", type=Path, required=True, help="输出目录")
    parser.add_argument("--resume", action="store_true", help="校验哈希后续跑")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="每个种子 bundle 的最大 Issue #28 worker 数",
    )
    parser.add_argument(
        "--allow-large-local",
        action="store_true",
        help="显式授权在本机执行大型 N3 计算",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from vmcrg_ref.issue28_protocol import load_issue28_protocol

    five_round_pilot_bundle, run_five_round_chain = _load_api()
    report = run_five_round_chain(
        load_issue28_protocol(args.protocol),
        five_round_pilot_bundle(),
        args.output,
        backend=args.backend,
        resume=args.resume,
        preset=args.preset,
        rounds=args.rounds,
        allow_large_local=args.allow_large_local,
        workers=args.workers,
    )
    print(
        f"N3 完成 轮数={report['requested_rounds']} 分类={report['classification']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
