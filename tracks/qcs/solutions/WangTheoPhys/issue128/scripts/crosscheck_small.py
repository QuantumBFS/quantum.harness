#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from fractions import Fraction

from trottercert.crosscheck import small_exact_crosscheck


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--length", type=int, default=2)
    parser.add_argument("--tolerance", type=int, default=10**6)
    args = parser.parse_args()
    print(
        json.dumps(
            small_exact_crosscheck(args.length, Fraction(1, args.tolerance)),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
