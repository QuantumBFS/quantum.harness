"""Apply globally valid reductions to Sergeev's 158-gate multiplier."""

from __future__ import annotations

import argparse
from pathlib import Path

from score_circuits import parse


def optimize_most_significant_carry(source: Path, destination: Path) -> None:
    circuit = parse(source)
    expected_cone = {"g150", "g156", "g157", "g158"}
    present = {wire for wire, _, _, _ in circuit.gates}
    if not expected_cone <= present:
        raise ValueError("source is not the expected Sergeev-158 topology")

    # On unrestricted boundary variables, the old four-gate cone is needed.
    # On a multiplier's reachable states, its output simplifies to
    #
    #   g36 AND (g29 OR g154).
    #
    # NAND(~a, ~b) realizes a OR b in one allowed challenge gate.
    gates = [
        gate for gate in circuit.gates
        if gate[0] not in expected_cone
    ]
    gates.extend(
        [
            ("g159", "NAND", "~g29", "~g154"),
            ("g160", "AND", "g159", "g36"),
        ]
    )
    outputs = ["g160" if output == "g158" else output for output in circuit.outputs]

    lines = [f"INPUTS {circuit.ninputs}"]
    lines.extend(f"{wire} = {op} {a} {b}" for wire, op, a, b in gates)
    lines.append("OUTPUTS " + " ".join(outputs))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {destination.resolve()}")
    print(f"gates: {len(gates)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("abc-work") / "sergeev-158" / "mystery-C.txt",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("abc-work") / "sergeev-156" / "mystery-C.txt",
    )
    args = parser.parse_args()
    optimize_most_significant_carry(args.source, args.output)


if __name__ == "__main__":
    main()
