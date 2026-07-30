"""Export the learned integer polynomial without inserting a target formula."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--network", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--module", default="learned_polynomial")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    network = json.loads(args.network.read_text(encoding="utf-8"))
    active = network["active_features"]
    lines = [
        f"module {args.module}(input wire [11:0] i, output wire [11:0] o);"
    ]
    terms = []
    for index, feature in enumerate(active):
        bits = feature["input_bits"]
        coefficient = int(feature["coefficient"]) % 4096
        if len(bits) != 2 or coefficient == 0:
            raise ValueError("expected nonzero pairwise learned features")
        lines.append(
            f"  wire f{index} = i[{bits[0]}] & i[{bits[1]}];"
        )
        terms.append(
            f"(f{index} ? 12'd{coefficient} : 12'd0)"
        )
    lines.append("  assign o = " + " + ".join(terms) + ";")
    lines.append("endmodule")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "module": args.module,
                "active_learned_features": len(active),
                "target_formula_inserted": False,
                "output": args.output.as_posix(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
