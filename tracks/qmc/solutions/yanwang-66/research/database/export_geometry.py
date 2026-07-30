"""Export Stim's rotated-surface-code geometry for validator provenance.

This script is executed only by an SCNet Slurm job in the pinned environment.
It derives roles and check supports from Stim's generated circuit instead of
duplicating the geometry by hand.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import stim


MEASUREMENT_GATES = {"M", "MX", "MY", "MR", "MRX", "MRY"}


def qubit_targets(instruction: stim.CircuitInstruction) -> list[int]:
    return [target.value for target in instruction.targets_copy() if target.is_qubit_target]


def export_instance(
    distance: int,
    basis: str,
    rounds: int,
    *,
    generator_commit: str,
    generator_source_sha256: str,
) -> dict[str, Any]:
    task = f"surface_code:rotated_memory_{basis.lower()}"
    circuit = stim.Circuit.generated(task, distance=distance, rounds=max(rounds, 2))
    flat = circuit.flattened()
    coordinates = circuit.get_final_qubit_coordinates()

    measurement_counts: Counter[int] = Counter()
    hadamard_qubits: set[int] = set()
    measurement_history: list[int] = []
    observable_support: set[int] = set()
    two_qubit_pairs: list[tuple[int, int]] = []

    for instruction in flat:
        name = instruction.name
        targets = instruction.targets_copy()
        if name in MEASUREMENT_GATES:
            measured = qubit_targets(instruction)
            for qubit in measured:
                measurement_counts[qubit] += 1
                measurement_history.append(qubit)
        elif name in {"H", "H_XY", "H_YZ"}:
            hadamard_qubits.update(qubit_targets(instruction))
        elif name in {"CX", "CZ"}:
            if len(targets) % 2 != 0:
                raise ValueError(f"{name} has an odd target count")
            for left, right in zip(targets[::2], targets[1::2], strict=True):
                if left.is_qubit_target and right.is_qubit_target:
                    two_qubit_pairs.append((left.value, right.value))
        elif name == "OBSERVABLE_INCLUDE":
            for target in targets:
                if not target.is_measurement_record_target:
                    continue
                index = len(measurement_history) + target.value
                if not 0 <= index < len(measurement_history):
                    raise ValueError(f"invalid record target {target} at history {len(measurement_history)}")
                observable_support.add(measurement_history[index])

    all_qubits = sorted(coordinates)
    data_qubits = {qubit for qubit in all_qubits if measurement_counts[qubit] == 1}
    ancilla_qubits = set(all_qubits) - data_qubits
    expected_data = distance * distance
    expected_ancilla = distance * distance - 1
    if len(data_qubits) != expected_data or len(ancilla_qubits) != expected_ancilla:
        raise AssertionError(
            f"d={distance}: derived data/ancilla={len(data_qubits)}/{len(ancilla_qubits)}, "
            f"expected {expected_data}/{expected_ancilla}"
        )

    support_by_ancilla: dict[int, set[int]] = defaultdict(set)
    for left, right in two_qubit_pairs:
        if left in data_qubits and right in ancilla_qubits:
            support_by_ancilla[right].add(left)
        elif right in data_qubits and left in ancilla_qubits:
            support_by_ancilla[left].add(right)

    qubit_to_site = {qubit: site for site, qubit in enumerate(all_qubits)}
    sites = []
    for qubit in all_qubits:
        coord = coordinates[qubit]
        role = "data" if qubit in data_qubits else "ancilla"
        sites.append(
            {
                "site_id": qubit_to_site[qubit],
                "stim_qubit": qubit,
                "role": role,
                "coord": [float(value) for value in coord],
            }
        )

    checks = []
    for ancilla in sorted(ancilla_qubits):
        support = support_by_ancilla.get(ancilla, set())
        if not support:
            raise AssertionError(f"ancilla {ancilla} has no data support")
        checks.append(
            {
                "check_id": len(checks),
                "ancilla_site_id": qubit_to_site[ancilla],
                "pauli": "X" if ancilla in hadamard_qubits else "Z",
                "support": sorted(qubit_to_site[qubit] for qubit in support),
            }
        )

    check_types = Counter(check["pauli"] for check in checks)
    expected_per_type = expected_ancilla // 2
    if check_types != Counter({"X": expected_per_type, "Z": expected_per_type}):
        raise AssertionError(f"d={distance}: unexpected X/Z check counts {dict(check_types)}")
    invalid_supports = [check for check in checks if len(check["support"]) not in {2, 4}]
    if invalid_supports:
        raise AssertionError(f"d={distance}: checks with invalid support sizes {invalid_supports}")

    logical_sites = sorted(
        qubit_to_site[qubit] for qubit in observable_support if qubit in data_qubits
    )
    if len(logical_sites) != distance:
        raise AssertionError(
            f"d={distance} basis={basis}: logical support length {len(logical_sites)} != {distance}"
        )

    return {
        "instance_id": f"rotated-d{distance}-{basis.lower()}-t{rounds}",
        "schema_version": "q66-surface-code-instance-v1",
        "distance": distance,
        "rounds": rounds,
        "basis": basis,
        "sites": sites,
        "checks": checks,
        "logical_support": logical_sites,
        "provenance": {
            "generator": task,
            "generator_commit": generator_commit,
            "generator_source_sha256": generator_source_sha256,
            "stim_version": stim.__version__,
            "stim_circuit_sha256": hashlib.sha256(
                str(circuit).encode("utf-8")
            ).hexdigest(),
            "geometry_probe_rounds": max(rounds, 2),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--generator-commit-file",
        type=Path,
        default=Path(__file__).with_name("generator_commit.txt"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generator_commit = args.generator_commit_file.read_text(encoding="ascii").strip()
    if len(generator_commit) != 40 or any(
        character not in "0123456789abcdef" for character in generator_commit
    ):
        raise ValueError("generator commit must be a full lowercase 40-character Git hash")
    generator_source_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    records = [
        export_instance(
            distance,
            basis,
            rounds,
            generator_commit=generator_commit,
            generator_source_sha256=generator_source_sha256,
        )
        for distance in (3, 5)
        for rounds in (distance, 2 * distance)
        for basis in ("X", "Z")
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
    print(json.dumps({"records": len(records), "out": str(args.out)}, sort_keys=True))


if __name__ == "__main__":
    main()
