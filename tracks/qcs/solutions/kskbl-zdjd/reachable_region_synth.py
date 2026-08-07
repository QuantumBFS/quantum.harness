#!/usr/bin/env python3
"""Synthesize a convex region using globally unreachable boundary states as EXDC."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from abc_flow import challenge_to_bench, mapped_blif_to_challenge
from factor_abc_synth import mapped_gate_count
from score_circuits import HERE, SPECS, base_operand, evaluate, parse
from semantic_resub import all_truth_tables
from tensor_graph_windows import contract, graph_data, reachability


def write_region(source: Path, instance: str, indices: frozenset[int], path: Path):
    circuit = parse(source)
    producer, consumers, _ = graph_data(circuit)
    ancestors, descendants = reachability(circuit, producer, consumers)
    region = contract(
        circuit, indices, producer, consumers, ancestors, descendants
    )
    if region is None:
        raise ValueError("region is not topologically convex")
    aliases = {wire: f"x{i + 1}" for i, wire in enumerate(region.inputs)}

    def rename(token: str) -> str:
        complemented = token.startswith("~")
        base = aliases.get(base_operand(token), base_operand(token))
        return f"~{base}" if complemented else base

    lines = [f"INPUTS {len(region.inputs)}"]
    for index in sorted(indices):
        wire, op, left, right = circuit.gates[index]
        lines.append(f"{wire} = {op} {rename(left)} {rename(right)}")
    lines.append("OUTPUTS " + " ".join(region.outputs))
    path.write_text("\n".join(lines) + "\n", encoding="ascii")

    _, values, _ = all_truth_tables(instance, source)
    rows = 1 << circuit.ninputs
    reachable: set[int] = set()
    for row in range(rows):
        packed = 0
        for position, wire in enumerate(region.inputs):
            packed |= ((values[wire] >> row) & 1) << position
        reachable.add(packed)
    return region, reachable


def abc_environment(suite: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["PATH"] = (
        str(suite / "bin")
        + os.pathsep
        + str(suite / "lib")
        + os.pathsep
        + environment.get("PATH", "")
    )
    return environment


def add_exdc(raw_blif: Path, destination: Path, ninputs: int, reachable: set[int]):
    text = raw_blif.read_text(encoding="ascii")
    if not text.rstrip().endswith(".end"):
        raise ValueError("raw BLIF does not end with .end")
    text = text.rsplit(".end", 1)[0]
    input_names = [f"x{i + 1}" for i in range(ninputs)]
    lines = [
        text.rstrip(),
        "",
        ".exdc",
        ".inputs " + " ".join(input_names),
        ".outputs global_dc",
        ".names " + " ".join(input_names) + " global_dc",
    ]
    for packed in range(1 << ninputs):
        if packed in reachable:
            continue
        cube = "".join(str((packed >> index) & 1) for index in range(ninputs))
        lines.append(f"{cube} 1")
    lines.append(".end")
    destination.write_text("\n".join(lines) + "\n", encoding="ascii")


def reachable_correct(path: Path, region, reachable: set[int]) -> tuple[bool, int | None]:
    try:
        candidate = parse(path)
    except Exception:
        return False, None
    if candidate.ninputs != len(region.inputs):
        return False, None
    if len(candidate.outputs) != len(region.outputs):
        return False, None
    for packed in reachable:
        expected = sum(
            ((int(truth, 16) >> packed) & 1) << index
            for index, truth in enumerate(region.truths)
        )
        if evaluate(candidate, packed) != expected:
            return False, packed
    return True, None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instance", choices=tuple(SPECS))
    parser.add_argument("indices", help="comma-separated one-based gate indices")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--eslim-timeout", type=int, default=12)
    parser.add_argument("--eslim-seeds", default="1,2")
    parser.add_argument("--no-eslim", action="store_true")
    args = parser.parse_args()

    source = (args.source or (HERE / f"{args.instance}.txt")).resolve()
    indices = frozenset(
        int(value) - 1 for value in args.indices.split(",") if value
    )
    job = HERE / "abc-work" / "reachable-synth" / args.tag
    job.mkdir(parents=True, exist_ok=True)
    original = job / "original-region.txt"
    region, reachable = write_region(source, args.instance, indices, original)
    bench = job / "original-region.bench"
    challenge_to_bench(original, bench)

    suite = HERE / "tools" / "oss-cad-suite" / "oss-cad-suite"
    abc = suite / "bin" / "yosys-abc.exe"
    library = HERE / "abc-work" / "challenge-buf-free.genlib"
    environment = abc_environment(suite)

    raw = job / "original-region.blif"
    raw.unlink(missing_ok=True)
    convert = subprocess.run(
        [str(abc), "-c", f"read_bench {bench}; write_blif {raw}"],
        cwd=HERE,
        env=environment,
        capture_output=True,
        text=True,
        timeout=args.timeout,
        check=False,
    )
    if convert.returncode or not raw.exists():
        raise RuntimeError(
            f"ABC BENCH-to-BLIF conversion failed: {convert.returncode}\n"
            f"{convert.stdout}\n{convert.stderr}"
        )
    care_blif = job / "reachable-care.blif"
    add_exdc(raw, care_blif, len(region.inputs), reachable)

    flows: list[tuple[str, str]] = [
        ("exdc-fraig", "strash; fraig -e -C 1000; dc2"),
        (
            "exdc-fraig-resub",
            "strash; fraig -e -C 1000; "
            "resub -K 12 -N 3 -F 8; dc2",
        ),
        (
            "exdc-sweep",
            "strash; logic; fraig_sweep -e; strash; dc2",
        ),
        ("bdd-dc2", "strash; collapse; strash; dc2"),
        ("bdd-dch", "strash; collapse; strash; dch"),
    ]
    if not args.no_eslim:
        for seed in (
            int(value) for value in args.eslim_seeds.split(",") if value
        ):
            flows.append(
                (
                    f"bdd-eslim-z{seed}",
                    "strash; collapse; strash; &get; "
                    f"&eslim -S 6 -R 1 -T {args.eslim_timeout} "
                    f"-Z {seed} -x -i -s; &put",
                )
            )

    print(
        f"REGION gates={region.gates} inputs={len(region.inputs)} "
        f"outputs={len(region.outputs)} reachable={len(reachable)}/"
        f"{1 << len(region.inputs)}",
        flush=True,
    )
    best_local = region.gates
    best_global: Path | None = None
    for tag, body in flows:
        mapped = job / f"{tag}.blif"
        challenge = job / f"{tag}.txt"
        embedded = job / f"{tag}-embedded.txt"
        for stale in (mapped, challenge, embedded):
            stale.unlink(missing_ok=True)
        command = (
            f"read_library {library}; read_blif {care_blif}; "
            f"{body}; map -a; write_blif {mapped}"
        )
        try:
            result = subprocess.run(
                [str(abc), "-c", command],
                cwd=HERE,
                env=environment,
                capture_output=True,
                text=True,
                timeout=max(args.timeout, args.eslim_timeout + 20),
                check=False,
            )
            status = f"exit{result.returncode}"
        except subprocess.TimeoutExpired:
            print(f"RESULT {tag} status=timeout", flush=True)
            continue

        count = mapped_gate_count(mapped)
        correct = False
        mismatch = None
        global_count = None
        if count is not None:
            try:
                mapped_blif_to_challenge(mapped, challenge)
                correct, mismatch = reachable_correct(
                    challenge, region, reachable
                )
                if correct and count < region.gates:
                    embed = subprocess.run(
                        [
                            sys.executable,
                            str(HERE / "embed_tensor_region.py"),
                            args.instance,
                            args.indices,
                            str(challenge),
                            "--source",
                            str(source),
                            "--output",
                            str(embedded),
                            "--reachable-only",
                        ],
                        cwd=HERE,
                        capture_output=True,
                        text=True,
                        timeout=60,
                        check=False,
                    )
                    if embed.returncode == 0 and embedded.exists():
                        global_count = len(parse(embedded).gates)
                        if count < best_local:
                            best_local = count
                            best_global = embedded
                    else:
                        status += "-embed-failed"
            except Exception as exc:
                status += f"-{type(exc).__name__}"
        print(
            f"RESULT {tag} local={count} reachable_correct={correct} "
            f"mismatch={mismatch} global={global_count} status={status}",
            flush=True,
        )
    print(
        f"BEST original_local={region.gates} best_local={best_local} "
        f"best_global={best_global}",
        flush=True,
    )


if __name__ == "__main__":
    main()
