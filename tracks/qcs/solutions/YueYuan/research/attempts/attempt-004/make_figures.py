#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import plotting


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    paths = plotting.make_all(args.results)
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
