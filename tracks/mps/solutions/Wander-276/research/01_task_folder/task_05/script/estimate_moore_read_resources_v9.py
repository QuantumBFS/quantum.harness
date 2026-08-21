#!/usr/bin/env python3
"""Exact storage and sparse-action estimates for Moore--Read v9 cases."""

from __future__ import annotations

import argparse
import json
from math import comb
from pathlib import Path
from typing import Any

from lgeth.combinatorics import clustered_zero_mode_count


VERSION = "v9"
SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT_PATH = SCRIPT_ROOT / "output" / "moore_read_resource_estimate_v9.json"
REGISTERED_MEMORY_BYTES = 118 * 1024**3
MEMORY_FRACTION = 0.70
REGISTERED_ACTION_PRODUCTS = 50_000_000_000


def estimate_case(particles: int) -> dict[str, Any]:
    """Return exact structural counts and one block-parent-action cost."""

    N = int(particles)
    if N < 4 or N % 2:
        raise ValueError("registered Moore--Read sizes are even and at least four")
    flux = N + 2
    basis = comb(N + flux - 1, N)
    intermediate = comb((N - 3) + flux - 1, N - 3)
    rows = flux**2 * intermediate
    triples = comb(flux + 2, 3)
    nnz = rows * triples
    rank = clustered_zero_mode_count(N, flux, k=2, r=2)
    audit_width = rank + 4
    # scipy complex128 CSR with int32 indices/indptr at the registered sizes.
    csr_bytes = nnz * (16 + 4) + (rows + 1) * 4
    initial_block_bytes = basis * audit_width * 16
    factor_block_bytes = rows * audit_width * 16
    working_lower_bound = csr_bytes + initial_block_bytes + factor_block_bytes
    action_products = 2 * nnz * audit_width
    fits_memory = working_lower_bound <= MEMORY_FRACTION * REGISTERED_MEMORY_BYTES
    fits_action = action_products <= REGISTERED_ACTION_PRODUCTS
    if fits_memory and fits_action:
        classification = "registered_benchmark_candidate"
    else:
        classification = "solver_reformulation_required"
    return {
        "N": N,
        "n_flux": flux,
        "basis_dimension": basis,
        "zero_mode_rank": rank,
        "intermediate_dimension": intermediate,
        "constraint_rows": rows,
        "triples_per_row": triples,
        "constraint_nnz": nnz,
        "audit_width": audit_width,
        "csr_bytes": csr_bytes,
        "initial_block_bytes": initial_block_bytes,
        "factor_block_bytes": factor_block_bytes,
        "working_memory_lower_bound_bytes": working_lower_bound,
        "parent_action_nonzero_products": action_products,
        "registered_memory_bytes": REGISTERED_MEMORY_BYTES,
        "registered_memory_fraction": MEMORY_FRACTION,
        "registered_action_products": REGISTERED_ACTION_PRODUCTS,
        "fits_final_sparse_memory": bool(fits_memory),
        "fits_registered_action_budget": bool(fits_action),
        "classification": classification,
    }


def write_estimates(path: Path = OUTPUT_PATH) -> dict[str, Any]:
    cases = [estimate_case(N) for N in (4, 6, 8, 10)]
    result = {
        "version": VERSION,
        "model": "continuum Moore--Read three-body parent",
        "cases": cases,
        "claim_boundary": (
            "Counts are exact. Memory is a lower bound for final CSR plus one "
            "LOBPCG input/output block; wall time must be measured by a benchmark job."
        ),
        "checks": {
            "n8_is_benchmark_candidate": cases[2]["classification"]
            == "registered_benchmark_candidate",
            "n10_requires_reformulation": cases[3]["classification"]
            == "solver_reformulation_required",
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    arguments = parser.parse_args()
    print(json.dumps(write_estimates(arguments.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
