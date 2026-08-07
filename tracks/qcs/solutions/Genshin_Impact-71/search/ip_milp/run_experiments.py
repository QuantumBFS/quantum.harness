"""Run the issue #71 IP/MILP experiment arm and persist auditable artifacts."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

import numpy as np
import scipy

from exact_milp import MilpResult, SynthGate, evaluate_synth, solve_exact, zero_gate_literal


OPS = {"AND", "OR", "XOR", "NAND", "NOR", "XNOR"}


@dataclass(frozen=True)
class Gate:
    output: str
    op: str
    left: str
    right: str


@dataclass(frozen=True)
class Circuit:
    ninputs: int
    gates: tuple[Gate, ...]
    outputs: tuple[str, ...]


def split_token(token: str) -> tuple[str, bool]:
    negated = token.startswith("~")
    base = token[1:] if negated else token
    if not base or base[0] not in {"x", "w"} or not base[1:].isdigit():
        raise ValueError(f"invalid token {token!r}")
    return base, negated


def parse_netlist(path: Path) -> Circuit:
    """Parse netlist as inert ASCII data; never import or execute submissions."""
    ninputs = None
    gates: list[Gate] = []
    outputs = None
    defined: set[str] = set()
    for line_number, raw in enumerate(path.read_text("ascii").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        if fields[0] == "INPUTS":
            if ninputs is not None or len(fields) != 2:
                raise ValueError(f"{path}:{line_number}: bad INPUTS")
            ninputs = int(fields[1])
        elif fields[0] == "OUTPUTS":
            if outputs is not None or ninputs is None:
                raise ValueError(f"{path}:{line_number}: bad OUTPUTS")
            outputs = tuple(fields[1:])
        else:
            if ninputs is None or outputs is not None or len(fields) != 5:
                raise ValueError(f"{path}:{line_number}: bad gate")
            output, equals, op, left, right = fields
            if equals != "=" or op not in OPS or output in defined:
                raise ValueError(f"{path}:{line_number}: invalid gate")
            for token in (left, right):
                base, _ = split_token(token)
                if base.startswith("w") and base not in defined:
                    raise ValueError(f"{path}:{line_number}: forward reference")
                if base.startswith("x") and not 1 <= int(base[1:]) <= ninputs:
                    raise ValueError(f"{path}:{line_number}: input range")
            gates.append(Gate(output, op, left, right))
            defined.add(output)
    if ninputs is None or outputs is None:
        raise ValueError(f"{path}: incomplete")
    return Circuit(ninputs, tuple(gates), outputs)


def apply_bits(op: str, left: int, right: int, mask: int) -> int:
    if op == "AND":
        return left & right
    if op == "OR":
        return left | right
    if op == "XOR":
        return left ^ right
    if op == "NAND":
        return mask ^ (left & right)
    if op == "NOR":
        return mask ^ (left | right)
    if op == "XNOR":
        return mask ^ (left ^ right)
    raise ValueError(op)


def circuit_tables(circuit: Circuit) -> tuple[dict[str, int], tuple[int, ...], int]:
    count = 1 << circuit.ninputs
    mask = (1 << count) - 1
    values: dict[str, int] = {}
    for input_index in range(circuit.ninputs):
        table = 0
        for assignment in range(count):
            table |= ((assignment >> input_index) & 1) << assignment
        values[f"x{input_index + 1}"] = table

    def literal(token: str) -> int:
        base, negated = split_token(token)
        return values[base] ^ (mask if negated else 0)

    for gate in circuit.gates:
        values[gate.output] = apply_bits(
            gate.op, literal(gate.left), literal(gate.right), mask
        )
    return (
        values,
        tuple(literal(token) for token in circuit.outputs),
        mask,
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evaluate_result(
    result: MilpResult,
    signals: dict[str, np.ndarray],
    target: np.ndarray,
) -> bool | None:
    if result.gates is None:
        return None
    return bool(np.array_equal(evaluate_synth(result.gates, signals), target))


def warmup_experiments(output_dir: Path, time_limit: float) -> list[dict]:
    rows = np.arange(16, dtype=np.uint16)
    signals = {
        "x0": ((rows >> 0) & 1).astype(bool),
        "x1": ((rows >> 1) & 1).astype(bool),
        "y0": ((rows >> 2) & 1).astype(bool),
        "y1": ((rows >> 3) & 1).astype(bool),
    }
    targets = {
        "add_bit0": signals["x0"] ^ signals["y0"],
        "add_bit1": signals["x1"] ^ signals["y1"] ^ (signals["x0"] & signals["y0"]),
        "mul_bit0": signals["x0"] & signals["y0"],
        "mul_bit1": (signals["x1"] & signals["y0"])
        ^ (signals["x0"] & signals["y1"]),
    }
    plans = {
        "add_bit0": (0, 1),
        "add_bit1": (2, 3),
        "mul_bit0": (0, 1),
        "mul_bit1": (2, 3),
    }
    records: list[dict] = []
    for name, counts in plans.items():
        target = targets[name]
        for gate_count in counts:
            print(f"WARMUP name={name} gates={gate_count}", flush=True)
            if gate_count == 0:
                literal = zero_gate_literal(signals, target)
                record = {
                    "kind": "warmup",
                    "name": name,
                    "gate_count": 0,
                    "status": (
                        "OPTIMAL_FEASIBLE" if literal is not None else "PROVEN_INFEASIBLE"
                    ),
                    "zero_gate_literal": literal,
                    "rows": 16,
                    "independent_truth_audit": literal is not None,
                }
            else:
                result = solve_exact(
                    signals, target, gate_count, time_limit=time_limit
                )
                record = {
                    "kind": "warmup",
                    "name": name,
                    "gate_count": gate_count,
                    "rows": 16,
                    **result.as_dict(),
                    "independent_truth_audit": evaluate_result(
                        result, signals, target
                    ),
                }
            records.append(record)
            print(
                f"RESULT name={name} gates={gate_count} "
                f"status={record['status']} audit={record['independent_truth_audit']}",
                flush=True,
            )
            (output_dir / "warmup_incremental.json").write_text(
                json.dumps(records, indent=2, sort_keys=True) + "\n"
            )
    return records


def structural_maps(circuit: Circuit) -> tuple[dict[str, Gate], dict[str, set[str]]]:
    by_output = {gate.output: gate for gate in circuit.gates}
    fanout: dict[str, set[str]] = {}
    for gate in circuit.gates:
        for token in (gate.left, gate.right):
            base, _ = split_token(token)
            fanout.setdefault(base, set()).add(gate.output)
    for token in circuit.outputs:
        base, _ = split_token(token)
        fanout.setdefault(base, set()).add("$OUTPUT")
    return by_output, fanout


def mffc(circuit: Circuit, root: str) -> set[str]:
    by_output, fanout = structural_maps(circuit)
    removed = {root}
    changed = True
    while changed:
        changed = False
        for wire in tuple(removed):
            gate = by_output[wire]
            for token in (gate.left, gate.right):
                base, _ = split_token(token)
                if base in by_output and base not in removed:
                    if fanout.get(base, set()) <= removed:
                        removed.add(base)
                        changed = True
    return removed


def choose_windows(circuit: Circuit, limit: int) -> list[tuple[str, set[str]]]:
    candidates = []
    for gate_index, gate in enumerate(circuit.gates):
        removed = mffc(circuit, gate.output)
        if 2 <= len(removed) <= 4:
            # Prefer larger MFFCs, then earlier roots (fewer divisors).
            candidates.append(((-len(removed), gate_index), gate.output, removed))
    candidates.sort(key=lambda item: item[0])
    return [(root, removed) for _, root, removed in candidates[:limit]]


def witness_assignments(ninputs: int, count: int, stage_index: int) -> np.ndarray:
    domain = 1 << ninputs
    if domain <= count:
        return np.arange(domain, dtype=np.int64)
    seed = np.random.SeedSequence([42, stage_index])
    rng = np.random.default_rng(seed)
    chosen = rng.choice(domain, size=count, replace=False)
    chosen.sort()
    return chosen


def bits_from_table(table: int, assignments: np.ndarray) -> np.ndarray:
    return np.fromiter(
        ((table >> int(assignment)) & 1 for assignment in assignments),
        dtype=bool,
        count=len(assignments),
    )


def canonical_prune(
    named_tables: list[tuple[str, int]], assignments: np.ndarray
) -> dict[str, np.ndarray]:
    kept: dict[bytes, str] = {}
    signals: dict[str, np.ndarray] = {}
    for name, table in named_tables:
        values = bits_from_table(table, assignments)
        packed = np.packbits(values, bitorder="little").tobytes()
        complement = np.packbits(~values, bitorder="little").tobytes()
        key = min(packed, complement)
        if key in kept:
            continue
        kept[key] = name
        signals[name] = values
    return signals


def remap_synth_gates(
    synth: list[SynthGate], root: str, existing: set[str]
) -> tuple[list[Gate], dict[str, str]]:
    max_wire = max(
        (int(name[1:]) for name in existing if name.startswith("w")), default=0
    )
    mapping: dict[str, str] = {}
    for index in range(len(synth)):
        mapping[f"g{index}"] = (
            root if index == len(synth) - 1 else f"w{max_wire + index + 1}"
        )

    def token(raw: str) -> str:
        negated = raw.startswith("~")
        base = raw[1:] if negated else raw
        mapped = mapping.get(base, base)
        return f"~{mapped}" if negated else mapped

    gates = [
        Gate(mapping[f"g{index}"], gate.op, token(gate.left), token(gate.right))
        for index, gate in enumerate(synth)
    ]
    return gates, mapping


def splice(circuit: Circuit, root: str, removed: set[str], synth: list[SynthGate]) -> Circuit:
    replacements, _ = remap_synth_gates(
        synth,
        root,
        {gate.output for gate in circuit.gates},
    )
    rewritten: list[Gate] = []
    inserted = False
    for gate in circuit.gates:
        if gate.output == root:
            rewritten.extend(replacements)
            inserted = True
        if gate.output not in removed:
            rewritten.append(gate)
    if not inserted:
        raise ValueError(root)
    return Circuit(circuit.ninputs, tuple(rewritten), circuit.outputs)


def write_netlist(circuit: Circuit, path: Path) -> None:
    lines = [f"INPUTS {circuit.ninputs}"]
    lines.extend(
        f"{gate.output} = {gate.op} {gate.left} {gate.right}"
        for gate in circuit.gates
    )
    lines.append("OUTPUTS " + " ".join(circuit.outputs))
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def local_experiments(
    reference_dir: Path,
    output_dir: Path,
    time_limit: float,
    witness_count: int,
    windows_per_circuit: int,
) -> list[dict]:
    records: list[dict] = []
    for label_index, label in enumerate("ABCD"):
        path = reference_dir / f"mystery-{label}.txt"
        circuit = parse_netlist(path)
        tables, reference_outputs, _ = circuit_tables(circuit)
        gate_index = {gate.output: index for index, gate in enumerate(circuit.gates)}
        assignments = witness_assignments(
            circuit.ninputs, witness_count, label_index
        )
        windows = choose_windows(circuit, windows_per_circuit)
        print(
            f"LOCAL label={label} gates={len(circuit.gates)} "
            f"windows={len(windows)} witness_rows={len(assignments)}",
            flush=True,
        )
        for window_index, (root, removed) in enumerate(windows):
            root_index = gate_index[root]
            static_names = [f"x{i + 1}" for i in range(circuit.ninputs)]
            static_names.extend(
                gate.output
                for gate in circuit.gates[:root_index]
                if gate.output not in removed
            )
            static = canonical_prune(
                [(name, tables[name]) for name in static_names], assignments
            )
            target = bits_from_table(tables[root], assignments)
            gate_count = len(removed) - 1
            print(
                f"WINDOW label={label} index={window_index} root={root} "
                f"mffc={len(removed)} replacement={gate_count} "
                f"divisors={len(static)}",
                flush=True,
            )
            result = solve_exact(
                static, target, gate_count, time_limit=time_limit
            )
            record = {
                "kind": "local_window",
                "label": label,
                "window_index": window_index,
                "root": root,
                "removed": sorted(removed, key=lambda x: int(x[1:])),
                "removed_gate_count": len(removed),
                "replacement_gate_count": gate_count,
                "witness_rows": len(assignments),
                "witness_assignment_sha256": hashlib.sha256(
                    assignments.astype("<i8").tobytes()
                ).hexdigest(),
                "static_divisor_count_after_phase_dedup": len(static),
                **result.as_dict(),
                "witness_truth_audit": evaluate_result(result, static, target),
                "full_root_truth_audit": None,
                "full_circuit_truth_audit": None,
                "candidate_path": None,
            }
            if result.gates is not None:
                # Independently evaluate the candidate root on the entire domain.
                domain_assignments = np.arange(1 << circuit.ninputs, dtype=np.int64)
                full_static = {
                    name: bits_from_table(tables[name], domain_assignments)
                    for name in static
                }
                full_target = bits_from_table(tables[root], domain_assignments)
                root_ok = bool(
                    np.array_equal(
                        evaluate_synth(result.gates, full_static), full_target
                    )
                )
                record["full_root_truth_audit"] = root_ok
                if root_ok:
                    candidate = splice(circuit, root, removed, result.gates)
                    _, candidate_outputs, _ = circuit_tables(candidate)
                    circuit_ok = candidate_outputs == reference_outputs
                    record["full_circuit_truth_audit"] = circuit_ok
                    if circuit_ok:
                        candidate_path = (
                            output_dir
                            / "candidates"
                            / f"mystery-{label}-window-{window_index}.txt"
                        )
                        candidate_path.parent.mkdir(parents=True, exist_ok=True)
                        write_netlist(candidate, candidate_path)
                        record["candidate_path"] = str(candidate_path)
                        record["candidate_sha256"] = sha256(candidate_path)
                        record["candidate_gate_count"] = len(candidate.gates)
            records.append(record)
            print(
                f"RESULT label={label} root={root} status={result.status} "
                f"witness_audit={record['witness_truth_audit']} "
                f"full_audit={record['full_circuit_truth_audit']}",
                flush=True,
            )
            (output_dir / "local_incremental.json").write_text(
                json.dumps(records, indent=2, sort_keys=True) + "\n"
            )
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--time-limit", type=float, default=300.0)
    parser.add_argument("--witness-count", type=int, default=128)
    parser.add_argument("--windows-per-circuit", type=int, default=3)
    parser.add_argument(
        "--mode", choices=("warmup", "local", "all"), default="all"
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    manifest = {
        "schema": "issue71-ip-milp-v1",
        "root_seed": 42,
        "mode": args.mode,
        "reference_dir": str(args.reference_dir),
        "reference_sha256": {
            label: sha256(args.reference_dir / f"mystery-{label}.txt")
            for label in "ABCD"
        },
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "scipy_milp_backend": "HiGHS bundled with SciPy",
        "environment": {
            key: os.environ.get(key)
            for key in ("SLURM_JOB_ID", "SLURM_ARRAY_TASK_ID", "HOSTNAME")
        },
        "parameters": {
            "time_limit": args.time_limit,
            "witness_count": args.witness_count,
            "windows_per_circuit": args.windows_per_circuit,
        },
    }
    manifest["source_sha256"] = {
        path.name: sha256(path)
        for path in (Path(__file__), Path(__file__).with_name("exact_milp.py"))
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    results: dict[str, list[dict]] = {}
    if args.mode in {"warmup", "all"}:
        results["warmup"] = warmup_experiments(
            args.output_dir, args.time_limit
        )
    if args.mode in {"local", "all"}:
        results["local"] = local_experiments(
            args.reference_dir,
            args.output_dir,
            args.time_limit,
            args.witness_count,
            args.windows_per_circuit,
        )
    results["wall_seconds"] = time.time() - started
    (args.output_dir / "results.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n"
    )
    (args.output_dir / "COMPLETE").write_text(
        f"IP_MILP_COMPLETE wall_seconds={results['wall_seconds']:.6f}\n"
    )
    print(
        f"COMPLETE output={args.output_dir} "
        f"wall_seconds={results['wall_seconds']:.3f}",
        flush=True,
    )


if __name__ == "__main__":
    main()
