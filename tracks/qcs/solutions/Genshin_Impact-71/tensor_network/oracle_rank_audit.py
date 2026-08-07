#!/usr/bin/env python3
"""Audit-only exact full-domain TT ranks for one instance/order."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from tn_common import INSTANCE_SPECS, ORDER_NAMES, atomic_json, variable_order
from tn_truth import enumerate_full_domain, tt_rank_vectors


def summarize(vectors: list[list[int]]) -> dict:
    values = np.asarray(vectors, dtype=np.int64)
    return {
        "per_output": vectors,
        "max_across_outputs_by_cut": np.max(values, axis=0).astype(int).tolist(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", required=True, choices=sorted(INSTANCE_SPECS))
    parser.add_argument("--order", required=True, choices=ORDER_NAMES)
    parser.add_argument("--report-out", required=True, type=Path)
    args = parser.parse_args()
    n = int(INSTANCE_SPECS[args.instance]["n"])
    order = variable_order(n, args.order)
    _, y_bits = enumerate_full_domain(args.instance)
    report = {
        "schema": "occam71-oracle-tt-rank-audit-v1",
        "instance": args.instance,
        "order_name": args.order,
        "order_original_axes": order,
        "domain_rows": int(y_bits.shape[0]),
        "boolean_01": summarize(
            tt_rank_vectors(y_bits.astype(np.float64), order)
        ),
        "signed_pm1": summarize(
            tt_rank_vectors(2.0 * y_bits.astype(np.float64) - 1.0, order)
        ),
        "selection_firewall": (
            "Computed only in audit process; unavailable to rank completion "
            "and MPS training."
        ),
    }
    atomic_json(args.report_out, report)
    print(json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
