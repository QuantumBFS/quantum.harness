#!/usr/bin/env python3
"""Audit untrusted reference netlists without importing or executing them."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from circuit import Circuit, verify_formula


FAMILIES = {
    "mystery-A": ("add", 37),
    "mystery-B": ("absdiff", 49),
    "mystery-C": ("mul", 156),
    "mystery-D": ("sos", 113),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference_dir", type=Path)
    args = parser.parse_args()
    results = []
    for instance, (family, claimed_gates) in FAMILIES.items():
        path = args.reference_dir / f"{instance}.txt"
        circuit = Circuit.parse(path)
        formula = verify_formula(circuit, family)
        record = {
            "instance": instance,
            "family": family,
            "path": str(path),
            "claimed_gates": claimed_gates,
            "observed_gates": len(circuit.gates),
            "gate_count_match": len(circuit.gates) == claimed_gates,
            "formula": formula,
            "structure": circuit.structural_audit(),
        }
        if not record["gate_count_match"] or formula["failures"]:
            raise RuntimeError(f"reference audit failed for {instance}")
        results.append(record)
    print(json.dumps({"results": results}, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
