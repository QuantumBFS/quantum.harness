"""Export a learned AND/OR/XOR JSON network as synthesizable Verilog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--network", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--module", default="learned_network")
    return parser.parse_args()


def expression(token: str) -> str:
    inverted = token.startswith("~")
    source = token[1:] if inverted else token
    if source == "c0":
        result = "1'b0"
    elif source == "c1":
        result = "1'b1"
    elif source.startswith("i") and source[1:].isdigit():
        result = f"i[{int(source[1:])}]"
    else:
        result = source
    return f"~({result})" if inverted else result


def operator(op: str) -> str:
    return {"AND": "&", "OR": "|", "XOR": "^"}[op]


def export(network: dict[str, Any], module: str) -> str:
    gate_names = [gate["out"] for gate in network["gates"]]
    lines = [
        f"module {module}(input wire [11:0] i, output wire [11:0] o);",
        "  wire " + ", ".join(gate_names) + ";",
    ]
    for gate in network["gates"]:
        lines.append(
            f"  assign {gate['out']} = "
            f"{expression(gate['a'])} {operator(gate['op'])} "
            f"{expression(gate['b'])};"
        )
    for index, token in enumerate(network["outputs"]):
        lines.append(f"  assign o[{index}] = {expression(token)};")
    lines.append("endmodule")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    network = json.loads(args.network.read_text(encoding="utf-8"))
    text = export(network, args.module)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(
        json.dumps(
            {
                "source_gates": len(network["gates"]),
                "output": args.output.as_posix(),
                "module": args.module,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
