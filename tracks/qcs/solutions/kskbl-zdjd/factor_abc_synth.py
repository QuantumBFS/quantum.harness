#!/usr/bin/env python3
"""Heuristically synthesize a small multi-output truth tensor with ABC."""

from __future__ import annotations

import argparse
import math
import os
import subprocess
from pathlib import Path

from score_circuits import HERE


FLOWS = {
    "resyn2": (
        "strash; balance; rewrite; refactor; balance; rewrite; "
        "rewrite -z; balance; refactor -z; rewrite -z; balance"
    ),
    "compress2": (
        "strash; balance; rewrite -l; rewrite -l -z; balance; "
        "rewrite -l; rewrite -l -z; balance"
    ),
    "dc2": "strash; dc2; balance; dc2",
    "mfs": (
        "strash; balance; rewrite; refactor; rewrite -z; balance; "
        "dc2; &get; &dc2; &put"
    ),
}


def write_pla(
    destination: Path, ninputs: int, truths: tuple[int, ...]
) -> None:
    lines = [
        f".i {ninputs}",
        f".o {len(truths)}",
        ".ilb " + " ".join(f"x{index}" for index in range(ninputs)),
        ".ob " + " ".join(f"y{index}" for index in range(len(truths))),
    ]
    for packed in range(1 << ninputs):
        input_bits = "".join(
            "1" if (packed >> index) & 1 else "0"
            for index in range(ninputs)
        )
        output_bits = "".join(
            "1" if (truth >> packed) & 1 else "0" for truth in truths
        )
        lines.append(f"{input_bits} {output_bits}")
    lines.append(".e")
    destination.write_text("\n".join(lines) + "\n", encoding="ascii")


def mapped_gate_count(path: Path) -> int | None:
    if not path.exists():
        return None
    count = 0
    for raw in path.read_text(encoding="ascii").splitlines():
        line = raw.strip()
        if not line.startswith(".gate "):
            continue
        cell = line.split()[1]
        if cell not in {"inv", "buf", "zero", "one"}:
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ninputs", type=int)
    parser.add_argument("truths", nargs="+")
    parser.add_argument("--tag", default="factor")
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    truths = tuple(int(value, 16) for value in args.truths)
    mask = (1 << (1 << args.ninputs)) - 1
    if any(value & ~mask for value in truths):
        raise ValueError("truth table is wider than ninputs")

    work = HERE / "abc-work" / "factor-synth"
    work.mkdir(parents=True, exist_ok=True)
    pla = work / f"{args.tag}.pla"
    write_pla(pla, args.ninputs, truths)

    root = HERE / "tools" / "oss-cad-suite" / "oss-cad-suite"
    abc = root / "bin" / "yosys-abc.exe"
    library = HERE / "abc-work" / "challenge-buf-free.genlib"
    environment = os.environ.copy()
    environment["PATH"] = (
        str(root / "bin")
        + os.pathsep
        + str(root / "lib")
        + os.pathsep
        + environment.get("PATH", "")
    )

    results = []
    for name, flow in FLOWS.items():
        output = work / f"{args.tag}-{name}.blif"
        if output.exists():
            output.unlink()
        command = (
            f"read_library {library}; read_pla {pla}; {flow}; "
            f"map -a; write_blif {output}"
        )
        try:
            subprocess.run(
                [str(abc), "-c", command],
                cwd=HERE,
                env=environment,
                capture_output=True,
                text=True,
                timeout=args.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            results.append((None, name, "timeout", output))
            continue
        count = mapped_gate_count(output)
        results.append((count, name, "ok" if count is not None else "failed", output))

    results.sort(key=lambda item: math.inf if item[0] is None else item[0])
    for count, name, status, output in results:
        print(f"{name}: gates={count}, status={status}, output={output}")


if __name__ == "__main__":
    main()
