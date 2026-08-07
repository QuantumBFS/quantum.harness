#!/usr/bin/env python3
"""在通过 N3 实测试运行后冻结 Issue #28 正式协议。"""

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
    from vmcrg_ref.formal_protocol import freeze_formal_protocol

    globals()["freeze_formal_protocol"] = freeze_formal_protocol
    return freeze_formal_protocol


def __getattr__(name: str):
    if name == "freeze_formal_protocol":
        return _load_api()
    raise AttributeError(name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="冻结 Issue #28 五种子五轮正式协议")
    parser.add_argument(
        "--umbrella",
        type=Path,
        default=Path("config/issue28_easy_v1.json"),
        help="已锁定的总协议",
    )
    parser.add_argument("--pilot", type=Path, required=True, help="通过的 N3 manifest")
    parser.add_argument("--output", type=Path, required=True, help="全新正式协议路径")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    value = _load_api()(args.umbrella, args.pilot, args.output)
    print(
        "正式协议已冻结 "
        f"种子={len(value['formal_seed_bundles'])} 轮数={value['formal_rounds']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
