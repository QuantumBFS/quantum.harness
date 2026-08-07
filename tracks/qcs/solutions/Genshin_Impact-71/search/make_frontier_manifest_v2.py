#!/usr/bin/env python3
"""Create a deterministic audited manifest for an Occam frontier directory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("frontier", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expected-total", type=int, required=True)
    parser.add_argument("--c-source", required=True)
    parser.add_argument("--c-synthesis", required=True)
    args = parser.parse_args()

    origins = {
        "A": {
            "source": "reference-355/mystery-A.txt",
            "synthesis": "37-gate ripple-carry adder; independently audited",
        },
        "B": {
            "source": "reference-355/mystery-B.txt",
            "synthesis": "49-gate absolute-difference circuit; independently audited",
        },
        "C": {
            "source": args.c_source,
            "synthesis": args.c_synthesis,
        },
        "D": {
            "source": "eSLIM pilot job 42633",
            "synthesis": "relation-SAT local resynthesis, size 6, seed 42",
        },
    }
    instances: dict[str, object] = {}
    total = 0
    total_rows = 0
    total_bits = 0
    for name in ("A", "B", "C", "D"):
        netlist = args.frontier / "netlists" / f"mystery-{name}.txt"
        audit_path = args.frontier / f"audit-{name}.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        netlist_hash = sha256(netlist)
        if audit["instance"] != name:
            raise ValueError(f"audit instance mismatch for {name}")
        if audit["candidate_sha256"] != netlist_hash:
            raise ValueError(f"audit/netlist hash mismatch for {name}")
        if audit["equivalent"] is not True or audit["mismatches"]:
            raise ValueError(f"formula audit failed for {name}")
        structure = audit["structure"]
        for key in (
            "dead_gates",
            "constant_gates",
            "duplicate_gate_functions",
            "complement_gate_functions",
        ):
            if structure[key]:
                raise ValueError(f"{name} has nonempty structural issue {key}")
        gates = int(audit["gates"])
        total += gates
        total_rows += int(audit["assignments"])
        total_bits += int(audit["output_bits_checked"])
        instances[name] = {
            **origins[name],
            "formula": audit["formula"],
            "inputs": int(audit["inputs"]),
            "outputs": int(audit["outputs"]),
            "gates": gates,
            "assignments_exhaustively_checked": int(audit["assignments"]),
            "output_bits_checked": int(audit["output_bits_checked"]),
            "netlist_sha256": netlist_hash,
            "formula_audit_sha256": sha256(audit_path),
        }

    payload = {
        "challenge": "QuantumBFS/quantum.harness issue 71",
        "root_seed": 42,
        "gate_basis": ["AND", "OR", "XOR", "NAND", "NOR", "XNOR"],
        "inverters_free": True,
        "instances": instances,
        "total_gates": total,
        "total_assignments_exhaustively_checked": total_rows,
        "total_output_bits_checked": total_bits,
        "all_formula_audits_exact": True,
        "trust_boundary": (
            "Competitor material was never executed. Pure netlists were parsed "
            "as strict ASCII data and all frontier circuits were exhaustively "
            "checked directly against independently encoded arithmetic formulas."
        ),
    }
    if total != args.expected_total:
        raise ValueError(
            f"expected frontier total {args.expected_total}, got {total}"
        )
    output = args.output or args.frontier / "manifest.json"
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(output)
    print(
        json.dumps(
            {
                "manifest": str(output),
                "manifest_sha256": sha256(output),
                "total_gates": total,
                "total_assignments": total_rows,
                "total_output_bits_checked": total_bits,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
