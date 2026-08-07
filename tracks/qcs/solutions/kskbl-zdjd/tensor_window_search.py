#!/usr/bin/env python3
"""Tensor-network window contraction and multi-output exact resynthesis.

Each gate is treated as a rank-3 Boolean tensor.  A contiguous subnetwork is
contracted exactly, leaving a tensor over its boundary inputs and outputs.
ABC's multi-output exact synthesizer is then asked for a smaller realization.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from score_circuits import HERE, base_operand, parse


@dataclass(frozen=True)
class Window:
    start: int
    stop: int
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    truths: tuple[str, ...]

    @property
    def gates(self) -> int:
        return self.stop - self.start


def apply_gate(op: str, a: bool, b: bool) -> bool:
    if op == "AND":
        return a and b
    if op == "OR":
        return a or b
    if op == "XOR":
        return a != b
    if op == "NAND":
        return not (a and b)
    if op == "NOR":
        return not (a or b)
    return a == b


def contract_window(circuit, start: int, stop: int) -> Window | None:
    gates = circuit.gates
    region = {wire for wire, _, _, _ in gates[start:stop]}
    inputs: set[str] = set()
    for wire, _, a, b in gates[start:stop]:
        for operand in (a, b):
            base = base_operand(operand)
            if base not in region:
                inputs.add(base)

    consumers: dict[str, set[str]] = defaultdict(set)
    for wire, _, a, b in gates:
        consumers[base_operand(a)].add(wire)
        consumers[base_operand(b)].add(wire)
    final_outputs = {base_operand(output) for output in circuit.outputs}
    outputs = [
        wire
        for wire, _, _, _ in gates[start:stop]
        if wire in final_outputs or any(user not in region for user in consumers[wire])
    ]
    if not outputs:
        return None

    ordered_inputs = tuple(
        sorted(inputs, key=lambda token: (not token.startswith("x"), token))
    )
    ordered_outputs = tuple(outputs)
    truth_values = [0] * len(ordered_outputs)
    for packed in range(1 << len(ordered_inputs)):
        values = {
            wire: bool((packed >> index) & 1)
            for index, wire in enumerate(ordered_inputs)
        }

        def get(token: str) -> bool:
            value = values[base_operand(token)]
            return not value if token.startswith("~") else value

        for wire, op, a, b in gates[start:stop]:
            values[wire] = apply_gate(op, get(a), get(b))
        for index, output in enumerate(ordered_outputs):
            truth_values[index] |= int(values[output]) << packed

    digits = max(1, 1 << max(0, len(ordered_inputs) - 2))
    truths = tuple(f"{value:0{digits}X}" for value in truth_values)
    return Window(start, stop, ordered_inputs, ordered_outputs, truths)


def enumerate_windows(
    circuit,
    min_gates: int,
    max_gates: int,
    max_inputs: int,
    max_outputs: int,
) -> list[Window]:
    windows: list[Window] = []
    for size in range(min_gates, max_gates + 1):
        for start in range(len(circuit.gates) - size + 1):
            window = contract_window(circuit, start, start + size)
            if window is None:
                continue
            if not (2 <= len(window.inputs) <= max_inputs):
                continue
            if not (1 <= len(window.outputs) <= max_outputs):
                continue
            windows.append(window)
    return windows


def exact_gate_count(
    abc: Path,
    window: Window,
    work: Path,
    conflicts: int,
    timeout: float,
    start_saving: int,
) -> tuple[int | None, str]:
    # ABC's `exact` SAT model and the returned gate count are correct.  In the
    # bundled ABC revision, however, the default SOP-network exporter reverses
    # the two local truth-table axes of asymmetric gates.  Consequently the
    # BLIF is safe for counting, but a replacement must swap the two fanins of
    # every asymmetric exported node before it is embedded and verified.
    key = (
        f"i{len(window.inputs)}-o{len(window.outputs)}-"
        + "-".join(value.lower() for value in window.truths)
    )
    output = work / f"tensor-exact-{key}.blif"
    if output.exists():
        output.unlink()
    start_gates = max(1, window.gates - start_saving)
    command = (
        f"exact -S {start_gates} -C {conflicts} "
        + " ".join(window.truths)
        + f"; ps; write_blif {output}"
    )
    environment = os.environ.copy()
    bin_dir = str(abc.parent)
    lib_dir = str(abc.parent.parent / "lib")
    environment["PATH"] = (
        bin_dir + os.pathsep + lib_dir + os.pathsep + environment.get("PATH", "")
    )
    try:
        result = subprocess.run(
            [str(abc), "-c", command],
            cwd=HERE,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, "timeout"
    if not output.exists():
        return None, f"no-network(exit={result.returncode})"
    count = 0
    for line in output.read_text(encoding="ascii").splitlines():
        if line.startswith(".names "):
            fields = line.split()
            if len(fields) >= 4:
                count += 1
    return count, str(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instance")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--min-gates", type=int, default=4)
    parser.add_argument("--max-gates", type=int, default=9)
    parser.add_argument("--max-inputs", type=int, default=6)
    parser.add_argument("--max-outputs", type=int, default=4)
    parser.add_argument("--run-exact", action="store_true")
    parser.add_argument("--conflicts", type=int, default=100_000)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--start-saving", type=int, default=2)
    parser.add_argument("--skip", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    source = args.source or (HERE / f"{args.instance}.txt")
    circuit = parse(source)
    windows = enumerate_windows(
        circuit,
        args.min_gates,
        args.max_gates,
        args.max_inputs,
        args.max_outputs,
    )
    unique: dict[tuple[int, tuple[str, ...]], Window] = {}
    for window in windows:
        key = (len(window.inputs), window.truths)
        previous = unique.get(key)
        if previous is None or window.gates > previous.gates:
            unique[key] = window
    representatives = sorted(
        unique.values(),
        key=lambda window: (
            -window.gates,
            len(window.inputs),
            len(window.outputs),
            window.start,
        ),
    )
    representatives = representatives[args.skip :]
    if args.limit:
        representatives = representatives[: args.limit]
    print(
        f"windows={len(windows)}, unique_tensors={len(unique)}, "
        f"representatives={len(representatives)}"
    )

    abc = (
        HERE
        / "tools"
        / "oss-cad-suite"
        / "oss-cad-suite"
        / "bin"
        / "yosys-abc.exe"
    )
    work = HERE / "abc-work" / "tensor-windows"
    work.mkdir(parents=True, exist_ok=True)
    for index, window in enumerate(representatives, 1):
        prefix = (
            f"{index:03d}: gates={window.gates}, "
            f"range={window.start + 1}:{window.stop}, "
            f"inputs={len(window.inputs)}, outputs={len(window.outputs)}"
        )
        if not args.run_exact:
            print(
                f"{prefix}, boundary_in={','.join(window.inputs)}, "
                f"boundary_out={','.join(window.outputs)}, "
                f"truths={','.join(window.truths)}"
            )
            continue
        count, detail = exact_gate_count(
            abc,
            window,
            work,
            args.conflicts,
            args.timeout,
            args.start_saving,
        )
        status = "IMPROVE" if count is not None and count < window.gates else "no"
        print(f"{prefix}, exact={count}, status={status}, detail={detail}")


if __name__ == "__main__":
    main()
