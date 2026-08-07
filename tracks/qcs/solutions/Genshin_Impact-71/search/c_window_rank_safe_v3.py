#!/usr/bin/env python3
"""Rank complete, acyclic two-root exact-resynthesis windows in mystery C.

A valid fixed-boundary window must meet two independent conditions:
1. no boundary divisor lies in either replacement root's fanout cone; and
2. the retained boundary uniquely determines both root values.
The second condition rejects ancestor/descendant root pairs whose downstream
root needs a surviving internal signal that cannot safely be used as a divisor.
"""

from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import sys
from pathlib import Path


DEFAULT_MODULE = Path(
    "/home/user_milksang/private/homefile/quantum_harness/issue71_occam/"
    "tracks/qcs/solutions/Genshin_Impact-71/search/window_search.py"
)
DEFAULT_NETLIST = Path(
    "/home/user_milksang/private/homefile/quantum_harness/issue71_occam/"
    "results/occam71/reference-355/mystery-C.txt"
)


def load_window_module(path: Path):
    spec = importlib.util.spec_from_file_location("c_window_generic_safe_rank_v3", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load audited module {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def natural_name_key(name: str) -> tuple[int, int]:
    if len(name) < 2 or name[0] not in {"x", "w"}:
        raise ValueError(f"unexpected signal name {name!r}")
    return (0 if name[0] == "x" else 1, int(name[1:]))


def functional_relation_size(
    boundary: tuple[str, ...],
    roots: tuple[str, str],
    values: dict[str, int],
    rows: int,
) -> int | None:
    relation: dict[int, int] = {}
    for row in range(rows):
        boundary_code = 0
        for bit, name in enumerate(boundary):
            boundary_code |= ((values[name] >> row) & 1) << bit
        root_code = 0
        for bit, name in enumerate(roots):
            root_code |= ((values[name] >> row) & 1) << bit
        previous = relation.setdefault(boundary_code, root_code)
        if previous != root_code:
            return None
    return len(relation)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", type=Path, default=DEFAULT_MODULE)
    parser.add_argument("--netlist", type=Path, default=DEFAULT_NETLIST)
    parser.add_argument("--min-removed", type=int, default=6)
    parser.add_argument("--max-removed", type=int, default=18)
    parser.add_argument("--max-boundary", type=int, default=12)
    parser.add_argument("--structural-limit", type=int, default=3000)
    parser.add_argument("--output-limit", type=int, default=100)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if not (2 <= args.min_removed <= args.max_removed):
        raise ValueError("invalid removed-gate bounds")
    if not (1 <= args.max_boundary <= 16):
        raise ValueError("invalid boundary bound")
    if args.structural_limit <= 0 or args.output_limit <= 0:
        raise ValueError("limits must be positive")

    dws = load_window_module(args.module)
    circuit = dws.parse_circuit(args.netlist)
    _, values, _ = dws.evaluate(circuit)
    gate_by_out, _ = dws.structural_maps(circuit)
    gate_index = {gate.out: index for index, gate in enumerate(circuit.gates)}
    rows = 1 << circuit.n_inputs

    structural: list[dict[str, object]] = []
    gate_names = tuple(gate.out for gate in circuit.gates)
    for roots_untyped in itertools.combinations(gate_names, 2):
        roots = (roots_untyped[0], roots_untyped[1])
        removed, descendants = dws.removable_closure(circuit, roots)
        removed_count = len(removed)
        if not args.min_removed <= removed_count <= args.max_removed:
            continue
        boundary: set[str] = set()
        for name in removed:
            gate = gate_by_out[name]
            for token in (gate.left, gate.right):
                if token.name not in removed and token.name not in descendants:
                    boundary.add(token.name)
        if len(boundary) > args.max_boundary:
            continue
        ordered_boundary = tuple(sorted(boundary, key=natural_name_key))
        relation_size = functional_relation_size(
            ordered_boundary, roots, values, rows
        )
        if relation_size is None:
            continue
        structural.append(
            {
                "roots": roots,
                "removed_count": removed_count,
                "boundary": ordered_boundary,
                "boundary_count": len(ordered_boundary),
                "removed": tuple(sorted(removed, key=gate_index.__getitem__)),
                "descendant_count": len(descendants),
                "reachable_patterns": relation_size,
            }
        )

    structural.sort(
        key=lambda record: (
            -int(record["removed_count"]),
            int(record["boundary_count"]),
            tuple(record["roots"]),
        )
    )
    structural = structural[: args.structural_limit]

    records: list[dict[str, object]] = []
    for record in structural:
        patterns = int(record["reachable_patterns"])
        removed_count = int(record["removed_count"])
        candidate_gates = removed_count - 1
        boundary_count = int(record["boundary_count"])
        effort_proxy = patterns * candidate_gates * (
            boundary_count + candidate_gates
        ) ** 2
        records.append(
            {
                **record,
                "candidate_gates": candidate_gates,
                "effort_proxy": effort_proxy,
            }
        )

    records.sort(
        key=lambda record: (
            int(record["effort_proxy"]),
            -int(record["removed_count"]),
            int(record["boundary_count"]),
            tuple(record["roots"]),
        )
    )
    payload = {
        "netlist": str(args.netlist),
        "inputs": circuit.n_inputs,
        "gates": len(circuit.gates),
        "rows": rows,
        "safety": {
            "acyclic_boundary": True,
            "boundary_excludes_removed": True,
            "boundary_excludes_root_descendants": True,
            "roots_functional_of_boundary": True,
        },
        "filters": {
            "min_removed": args.min_removed,
            "max_removed": args.max_removed,
            "max_boundary": args.max_boundary,
            "structural_limit": args.structural_limit,
        },
        "valid_structural_candidates": len(structural),
        "records": records[: args.output_limit],
    }
    rendered = json.dumps(payload, indent=2)
    if args.output is None:
        print(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(args.output)


if __name__ == "__main__":
    main()
