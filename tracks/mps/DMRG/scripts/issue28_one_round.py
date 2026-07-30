#!/usr/bin/env python3
"""Issue #28 N2 单轮纯神经 VMCRG 入口。"""

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
    from vmcrg_ref.one_round import one_round_seed_bundle, run_one_round

    globals().update(
        one_round_seed_bundle=one_round_seed_bundle,
        run_one_round=run_one_round,
    )
    return one_round_seed_bundle, run_one_round


def __getattr__(name: str):
    if name in {"one_round_seed_bundle", "run_one_round"}:
        _load_api()
        return globals()[name]
    raise AttributeError(name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行 Issue #28 N2 单轮纯神经 VMCRG")
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from vmcrg_ref.issue28_protocol import load_issue28_protocol

    one_round_seed_bundle, run_one_round = _load_api()
    protocol = load_issue28_protocol(args.protocol)
    bundle = one_round_seed_bundle(args.preset)
    report = run_one_round(protocol, bundle, args.preset, args.output)
    print(
        "N2 单轮纯神经 VMCRG 完成 "
        f"格点={report['stage_setup']['length']} 分类={report['classification']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
