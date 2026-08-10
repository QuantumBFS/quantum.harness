#!/usr/bin/env python3
"""Build deterministic research-delivery data for Issue #230."""

from __future__ import annotations

from pathlib import Path

from xxzcert.delivery import build_delivery_bundle, write_delivery_bundle


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    bundle = build_delivery_bundle(PROJECT_ROOT)
    paths = write_delivery_bundle(
        bundle, PROJECT_ROOT, PROJECT_ROOT / "outputs/final"
    )
    gate = bundle.record_gate
    print(
        "delivery-data: "
        f"certificates={len(bundle.rows)} "
        f"width={gate.width} target={gate.target} "
        f"record_target={gate.passes}",
        flush=True,
    )
    for path in paths:
        print(path.relative_to(PROJECT_ROOT), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
