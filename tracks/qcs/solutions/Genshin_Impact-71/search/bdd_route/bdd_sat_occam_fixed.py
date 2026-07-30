#!/usr/bin/env python3
"""Run the Occam MaxSAT learner on one preregistered variable order."""

from __future__ import annotations

import argparse
from typing import Sequence

import bdd_sat_occam_v2 as implementation


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--fixed-order", required=True)
    parser.add_argument("--fixed-order-name", required=True)
    known, remaining = parser.parse_known_args(argv)
    order = [int(piece) for piece in known.fixed_order.split(",") if piece]
    if sorted(order) != list(range(len(order))):
        raise ValueError("fixed order must be a zero-based permutation")

    def only_order(n: int) -> dict[str, list[int]]:
        if 2 * n != len(order):
            raise ValueError("fixed order length does not match instance")
        return {known.fixed_order_name: list(order)}

    def no_search(
        samples: object,
        n: int,
        **kwargs: object,
    ) -> tuple[list[int], dict[str, object]]:
        if 2 * n != len(order):
            raise ValueError("fixed order length does not match instance")
        return list(order), {
            "mode": "preregistered_fixed_order",
            "name": known.fixed_order_name,
            "order": list(order),
            "seed": kwargs.get("seed", 42),
            "note": "all base/sifting orders were evaluated in the separate greedy BDD arm",
        }

    implementation.base_orders = only_order
    implementation.choose_order = no_search
    return implementation.main(remaining)


if __name__ == "__main__":
    raise SystemExit(main())
