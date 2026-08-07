#!/usr/bin/env python3
"""Run the native ABC audit matrix on the current exact C152/D109 frontier."""

from __future__ import annotations

import run_frontier_abc as base


base.INSTANCES["C"] = {
    "expected_sha256": (
        "67540307369fedfffdb2b1a6473eff5e0bbfeb0e4873d03fddbeceb653cd071c"
    ),
    "expected_gates": 152,
    "discovery_dir": "mystery-C",
}


if __name__ == "__main__":
    base.main()
