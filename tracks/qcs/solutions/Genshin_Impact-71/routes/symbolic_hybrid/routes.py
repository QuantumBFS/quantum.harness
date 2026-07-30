#!/usr/bin/env python3
"""Reproducible non-leaking baselines for quantum.harness issue 71.

The discovery subcommand reads *only* explicitly supplied train.csv files.
Auditing against public commitments and exhaustive semantic/circuit checks is a
separate subcommand and consumes a frozen discovery manifest.

Only Python's standard library is used.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence


INSTANCE_NAMES = (
    "practice-add-n4",
    "practice-mul-n4",
    "mystery-A",
    "mystery-B",
    "mystery-C",
    "mystery-D",
)
ROOT_SEED = 42


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(tmp, path)


def read_csv_exact(path: Path, header: Sequence[str]) -> list[tuple[str, ...]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        actual = next(reader, None)
        if actual != list(header):
            raise ValueError(f"{path}: expected header {list(header)!r}, got {actual!r}")
        rows: list[tuple[str, ...]] = []
        for lineno, row in enumerate(reader, start=2):
            if len(row) != len(header):
                raise ValueError(f"{path}:{lineno}: malformed row")
            for field in row:
                if not field or set(field) - {"0", "1"}:
                    raise ValueError(f"{path}:{lineno}: non-binary field {field!r}")
            rows.append(tuple(row))
    if not rows:
        raise ValueError(f"{path}: empty dataset")
    return rows


def bits_to_int(bits: str, endian: str) -> int:
    if endian == "lsb":
        return sum((ch == "1") << idx for idx, ch in enumerate(bits))
    if endian == "msb":
        return int(bits, 2)
    raise ValueError(endian)


def int_to_bits(value: int, width: int, endian: str) -> str:
    if value < 0 or value >= (1 << width):
        raise ValueError(f"value {value} does not fit {width} bits")
    msb = f"{value:0{width}b}"
    if endian == "msb":
        return msb
    if endian == "lsb":
        return msb[::-1]
    raise ValueError(endian)


def decode_operands(bits: str, layout: str, endian: str) -> tuple[int, int]:
    if len(bits) % 2:
        raise ValueError("input width must be even")
    if layout == "grouped":
        half = len(bits) // 2
        left, right = bits[:half], bits[half:]
    elif layout == "interleaved":
        left, right = bits[0::2], bits[1::2]
    else:
        raise ValueError(layout)
    return bits_to_int(left, endian), bits_to_int(right, endian)


@dataclass(frozen=True)
class Expression:
    expr_id: str
    display: str
    complexity: int
    function: Callable[[int, int], int]


def _safe_lcm(x: int, y: int) -> int:
    return math.lcm(x, y)


def expression_library() -> tuple[Expression, ...]:
    """A generic, preregistered arithmetic/bitwise hypothesis library.

    This library contains no instance-name dispatch and is applied identically
    to every dataset and every candidate bit encoding.
    """

    entries = (
        ("zero", "0", 0, lambda x, y: 0),
        ("one", "1", 0, lambda x, y: 1),
        ("x", "x", 1, lambda x, y: x),
        ("y", "y", 1, lambda x, y: y),
        ("x_plus_y", "x + y", 3, lambda x, y: x + y),
        ("abs_x_minus_y", "|x - y|", 4, lambda x, y: abs(x - y)),
        ("x_times_y", "x * y", 3, lambda x, y: x * y),
        ("x_xor_y", "x XOR y", 3, lambda x, y: x ^ y),
        ("x_and_y", "x AND y", 3, lambda x, y: x & y),
        ("x_or_y", "x OR y", 3, lambda x, y: x | y),
        ("min_x_y", "min(x, y)", 3, min),
        ("max_x_y", "max(x, y)", 3, max),
        ("gcd_x_y", "gcd(x, y)", 4, math.gcd),
        ("lcm_x_y", "lcm(x, y)", 4, _safe_lcm),
        ("x_squared", "x^2", 3, lambda x, y: x * x),
        ("y_squared", "y^2", 3, lambda x, y: y * y),
        ("sum_of_squares", "x^2 + y^2", 7, lambda x, y: x * x + y * y),
        ("square_of_sum", "(x + y)^2", 7, lambda x, y: (x + y) ** 2),
        (
            "abs_difference_of_squares",
            "|x^2 - y^2|",
            8,
            lambda x, y: abs(x * x - y * y),
        ),
        ("x_squared_plus_y", "x^2 + y", 5, lambda x, y: x * x + y),
        ("x_plus_y_squared", "x + y^2", 5, lambda x, y: x + y * y),
        ("triangular_x_plus_y", "x(x+1)/2 + y", 7, lambda x, y: x * (x + 1) // 2 + y),
        ("x_plus_triangular_y", "x + y(y+1)/2", 7, lambda x, y: x + y * (y + 1) // 2),
        ("x_times_x_plus_y", "x(x+y)", 6, lambda x, y: x * (x + y)),
        ("y_times_x_plus_y", "y(x+y)", 6, lambda x, y: y * (x + y)),
    )
    return tuple(Expression(*entry) for entry in entries)


EXPRESSION_BY_ID = {expr.expr_id: expr for expr in expression_library()}


def evaluate_hypothesis(selection: dict[str, object], input_bits: str) -> int:
    x, y = decode_operands(
        input_bits,
        str(selection["layout"]),
        str(selection["input_endian"]),
    )
    return EXPRESSION_BY_ID[str(selection["expr_id"])].function(x, y)


def encode_hypothesis(
    selection: dict[str, object], input_bits: str, output_width: int
) -> str:
    value = evaluate_hypothesis(selection, input_bits)
    if selection["range_mode"] == "modulo":
        value %= 1 << output_width
    elif selection["range_mode"] != "exact":
        raise ValueError(selection["range_mode"])
    return int_to_bits(value, output_width, str(selection["output_endian"]))


def discover_one(train_path: Path) -> dict[str, object]:
    rows = read_csv_exact(train_path, ("input", "output"))
    input_width = len(rows[0][0])
    output_width = len(rows[0][1])
    if input_width % 2:
        raise ValueError(f"{train_path}: odd input width")
    if any(len(inp) != input_width or len(out) != output_width for inp, out in rows):
        raise ValueError(f"{train_path}: inconsistent widths")
    if len({inp for inp, _ in rows}) != len(rows):
        raise ValueError(f"{train_path}: duplicate training input")

    exact: list[dict[str, object]] = []
    ranked: list[dict[str, object]] = []
    semantic_vectors: set[tuple[int, ...]] = set()
    tested = 0
    for layout, input_endian, output_endian, range_mode in itertools.product(
        ("grouped", "interleaved"),
        ("lsb", "msb"),
        ("lsb", "msb"),
        ("exact", "modulo"),
    ):
        decoded = [
            decode_operands(inp, layout, input_endian) for inp, _ in rows
        ]
        expected = [bits_to_int(out, output_endian) for _, out in rows]
        for expr in expression_library():
            tested += 1
            raw = [expr.function(x, y) for x, y in decoded]
            if range_mode == "modulo":
                predicted = [value % (1 << output_width) for value in raw]
            else:
                predicted = raw
            vector = tuple(predicted)
            semantic_vectors.add(vector)
            mismatches = sum(a != b for a, b in zip(predicted, expected))
            mean_abs = (
                sum(abs(a - b) for a, b in zip(predicted, expected)) / len(rows)
            )
            candidate = {
                "expr_id": expr.expr_id,
                "expression": expr.display,
                "complexity": expr.complexity,
                "layout": layout,
                "input_endian": input_endian,
                "output_endian": output_endian,
                "range_mode": range_mode,
                "mismatches": mismatches,
                "mean_absolute_error": mean_abs,
            }
            ranked.append(candidate)
            if mismatches == 0:
                exact.append(candidate)

    if not exact:
        top = sorted(
            ranked,
            key=lambda item: (
                item["mismatches"],
                item["mean_absolute_error"],
                item["complexity"],
                item["expr_id"],
            ),
        )[:10]
        raise RuntimeError(f"{train_path}: no exact hypothesis; top={top!r}")

    exact.sort(
        key=lambda item: (
            item["complexity"],
            item["expr_id"],
            item["layout"],
            item["input_endian"],
            item["output_endian"],
            item["range_mode"],
        )
    )
    # Exact and modulo modes coincide when the expression never overflows.
    # Prefer the stronger non-wrapping claim in a deterministic tie.
    exact.sort(key=lambda item: item["range_mode"] != "exact")
    selected = exact[0]
    return {
        "schema": "occam71-train-only-discovery-v1",
        "root_seed": ROOT_SEED,
        "read_boundary": {
            "allowed": [str(train_path.resolve())],
            "forbidden_during_discovery": [
                "generator source",
                "test_inputs.csv",
                "commitment.sha256",
                "test_outputs.csv",
                "competitor PR content",
            ],
        },
        "train_path": str(train_path.resolve()),
        "train_sha256": sha256_file(train_path),
        "train_rows": len(rows),
        "input_width": input_width,
        "operand_width": input_width // 2,
        "output_width": output_width,
        "candidates_tested": tested,
        "distinct_prediction_vectors": len(semantic_vectors),
        "exact_hypothesis_count": len(exact),
        "exact_hypotheses": exact,
        "selected": selected,
        "training": {
            "matched": len(rows),
            "total": len(rows),
            "accuracy": 1.0,
        },
    }


def command_discover(args: argparse.Namespace) -> None:
    root = Path(args.datasets_root).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    index: dict[str, object] = {
        "schema": "occam71-train-only-index-v1",
        "root_seed": ROOT_SEED,
        "instances": {},
    }
    # Paths are constructed explicitly; there is no recursive directory scan.
    for name in INSTANCE_NAMES:
        result = discover_one(root / name / "train.csv")
        target = out / name / "discovery.json"
        atomic_json(target, result)
        index["instances"][name] = {
            "manifest": str(target),
            "train_sha256": result["train_sha256"],
            "selected": result["selected"],
        }
        print(
            f"{name}: {result['selected']['expression']} "
            f"({result['selected']['layout']}, "
            f"{result['selected']['input_endian']} -> "
            f"{result['selected']['output_endian']}), "
            f"train={result['train_rows']}/{result['train_rows']}"
        )
    atomic_json(out / "discovery-index.json", index)


def load_discovery(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "occam71-train-only-discovery-v1":
        raise ValueError(f"{path}: unsupported manifest")
    train = Path(str(data["train_path"]))
    actual = sha256_file(train)
    if actual != data["train_sha256"]:
        raise ValueError(f"{path}: train file changed after discovery")
    return data


def write_prediction_csv(
    path: Path,
    inputs: Iterable[str],
    selection: dict[str, object],
    output_width: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        # The withheld file mirrors train.csv and retains the supplied input.
        handle.write("input,output\n")
        for input_bits in inputs:
            output_bits = encode_hypothesis(selection, input_bits, output_width)
            handle.write(f"{input_bits},{output_bits}\n")
    os.replace(tmp, path)


def command_audit_commitments(args: argparse.Namespace) -> None:
    datasets = Path(args.datasets_root).resolve()
    root = Path(args.work).resolve()
    summary: dict[str, object] = {
        "schema": "occam71-post-freeze-commitment-audit-v1",
        "instances": {},
    }
    for name in INSTANCE_NAMES:
        discovery_path = root / name / "discovery.json"
        discovery = load_discovery(discovery_path)
        test_path = datasets / name / "test_inputs.csv"
        inputs = [row[0] for row in read_csv_exact(test_path, ("input",))]
        if any(len(bits) != discovery["input_width"] for bits in inputs):
            raise ValueError(f"{test_path}: width mismatch")
        prediction_path = root / name / "test_outputs.predicted.csv"
        write_prediction_csv(
            prediction_path,
            inputs,
            dict(discovery["selected"]),
            int(discovery["output_width"]),
        )
        actual_hash = sha256_file(prediction_path)
        commitment_path = datasets / name / "commitment.sha256"
        commitment = commitment_path.read_text(encoding="utf-8").split()[0]
        matched = actual_hash == commitment
        result = {
            "discovery_manifest": str(discovery_path),
            "prediction_path": str(prediction_path),
            "test_rows": len(inputs),
            "prediction_sha256": actual_hash,
            "published_commitment_sha256": commitment,
            "commitment_match": matched,
        }
        atomic_json(root / name / "commitment-audit.json", result)
        summary["instances"][name] = result
        print(f"{name}: test commitment {'MATCH' if matched else 'MISMATCH'} ({actual_hash})")
        if not matched:
            raise RuntimeError(f"{name}: frozen train-only hypothesis failed commitment")
    atomic_json(root / "commitment-audit-summary.json", summary)


def all_bitstrings(width: int) -> Iterator[str]:
    for value in range(1 << width):
        yield f"{value:0{width}b}"


def write_train_pla(
    path: Path, rows: Sequence[tuple[str, str]], input_width: int, output_width: int
) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(f".i {input_width}\n")
        handle.write(f".o {output_width}\n")
        handle.write(".ilb " + " ".join(f"i{i}" for i in range(input_width)) + "\n")
        handle.write(".ob " + " ".join(f"o{i}" for i in range(output_width)) + "\n")
        # In Espresso semantics, FR gives explicit ON and OFF sets; minterms
        # absent from both sets are the don't-care set.
        handle.write(".type fr\n")
        handle.write(f".p {len(rows)}\n")
        for input_bits, output_bits in rows:
            handle.write(f"{input_bits} {output_bits}\n")
        handle.write(".e\n")


def write_full_pla(
    path: Path,
    selection: dict[str, object],
    input_width: int,
    output_width: int,
) -> None:
    domain = 1 << input_width
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(f".i {input_width}\n")
        handle.write(f".o {output_width}\n")
        handle.write(".ilb " + " ".join(f"i{i}" for i in range(input_width)) + "\n")
        handle.write(".ob " + " ".join(f"o{i}" for i in range(output_width)) + "\n")
        handle.write(".type fr\n")
        handle.write(f".p {domain}\n")
        for input_bits in all_bitstrings(input_width):
            output_bits = encode_hypothesis(selection, input_bits, output_width)
            handle.write(f"{input_bits} {output_bits}\n")
        handle.write(".e\n")


def write_train_exdc_blif(
    path: Path, rows: Sequence[tuple[str, str]], input_width: int, output_width: int
) -> tuple[list[int], int]:
    observed = {input_bits: output_bits for input_bits, output_bits in rows}
    if len(observed) != len(rows):
        raise ValueError("duplicate training inputs")
    unseen = [bits for bits in all_bitstrings(input_width) if bits not in observed]
    on_counts: list[int] = []
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(".model train_incomplete\n")
        inputs = " ".join(f"i{i}" for i in range(input_width))
        outputs = " ".join(f"o{i}" for i in range(output_width))
        handle.write(f".inputs {inputs}\n")
        handle.write(f".outputs {outputs}\n")
        for output_idx in range(output_width):
            handle.write(f".names {inputs} o{output_idx}\n")
            count = 0
            for input_bits, output_bits in rows:
                if output_bits[output_idx] == "1":
                    handle.write(f"{input_bits} 1\n")
                    count += 1
            on_counts.append(count)
        # A .names cover alone makes absent minterms OFF.  The .exdc network
        # below explicitly changes exactly the unseen minterms to don't-care,
        # leaving every observed 0 and 1 fixed.
        handle.write(".exdc\n")
        # ABC external DC is a separate one-output global-care network.
        handle.write(f".inputs {inputs}\n")
        handle.write(".outputs exdc\n")
        handle.write(f".names {inputs} exdc\n")
        for input_bits in unseen:
            handle.write(f"{input_bits} 1\n")
        handle.write(".end\n")
    return on_counts, len(unseen)


def audit_generated_specs(
    train_pla: Path,
    train_blif: Path,
    rows: Sequence[tuple[str, str]],
    input_width: int,
    output_width: int,
    on_counts: Sequence[int],
    unseen_count: int,
) -> dict[str, object]:
    pla_lines = train_pla.read_text(encoding="utf-8").splitlines()
    if ".type fr" not in pla_lines:
        raise AssertionError("PLA is not .type fr")
    cube_lines = [line for line in pla_lines if line and line[0] in "01-"]
    parsed = {}
    for line in cube_lines:
        left, right = line.split()
        if len(left) != input_width or len(right) != output_width:
            raise AssertionError("malformed PLA cube")
        if "-" in left or "-" in right:
            raise AssertionError("training PLA should explicitly fix every observed bit")
        parsed[left] = right
    expected = dict(rows)
    if parsed != expected:
        raise AssertionError("PLA observed relation differs from train.csv")
    if (1 << input_width) - len(parsed) != unseen_count:
        raise AssertionError("PLA don't-care count mismatch")

    # Audit the generated BLIF structurally instead of trusting the writer.
    main_seen = [set() for _ in range(output_width)]
    exdc_seen: set[str] = set()
    in_exdc = False
    current: tuple[str, int] | None = None
    for raw in train_blif.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == ".exdc":
            in_exdc = True
            current = None
        elif line.startswith(".names "):
            out_name = line.split()[-1]
            if in_exdc:
                if out_name != "exdc":
                    raise AssertionError("EXDC must have one global output")
                current = ("dc", 0)
            else:
                if not out_name.startswith("o"):
                    raise AssertionError("unexpected BLIF output name")
                current = ("main", int(out_name[1:]))
        elif line.startswith("."):
            current = None
        elif current is not None:
            pattern, value = line.split()
            if value != "1" or len(pattern) != input_width:
                raise AssertionError("malformed BLIF cube")
            if current[0] == "dc":
                exdc_seen.add(pattern)
            else:
                main_seen[current[1]].add(pattern)

    observed = dict(rows)
    unseen = set(all_bitstrings(input_width)) - set(observed)
    for output_idx in range(output_width):
        expected_on = {
            inp for inp, out in rows if out[output_idx] == "1"
        }
        if main_seen[output_idx] != expected_on:
            raise AssertionError(f"BLIF ON-set mismatch for output {output_idx}")
        if main_seen[output_idx] & exdc_seen:
            raise AssertionError("observed ON set overlaps EXDC")
    if exdc_seen != unseen:
        raise AssertionError("BLIF global EXDC differs from unseen input set")
    return {
        "pla_type": "fr",
        "observed_minterms": len(rows),
        "unseen_dont_care_minterms_per_output": unseen_count,
        "domain_minterms": 1 << input_width,
        "on_minterms_per_output": list(on_counts),
        "pla_sha256": sha256_file(train_pla),
        "blif_sha256": sha256_file(train_blif),
        "checks": {
            "all_training_outputs_fixed": True,
            "all_and_only_unseen_inputs_are_dont_care": True,
            "pla_blif_relation_agree": True,
        },
    }


def command_specs(args: argparse.Namespace) -> None:
    root = Path(args.work).resolve()
    for name in INSTANCE_NAMES:
        directory = root / name
        discovery = load_discovery(directory / "discovery.json")
        rows = [
            (row[0], row[1])
            for row in read_csv_exact(Path(str(discovery["train_path"])), ("input", "output"))
        ]
        input_width = int(discovery["input_width"])
        output_width = int(discovery["output_width"])
        train_pla = directory / "train-incomplete.pla"
        train_blif = directory / "train-incomplete-exdc.blif"
        full_pla = directory / "semantic-full.pla"
        write_train_pla(train_pla, rows, input_width, output_width)
        on_counts, unseen_count = write_train_exdc_blif(
            train_blif, rows, input_width, output_width
        )
        write_full_pla(
            full_pla,
            dict(discovery["selected"]),
            input_width,
            output_width,
        )
        audit = audit_generated_specs(
            train_pla,
            train_blif,
            rows,
            input_width,
            output_width,
            on_counts,
            unseen_count,
        )
        audit["semantic_full_pla_sha256"] = sha256_file(full_pla)
        atomic_json(directory / "spec-audit.json", audit)
        print(
            f"{name}: PLA/BLIF audited; observed={len(rows)}, "
            f"DC={unseen_count}, domain={1 << input_width}"
        )


@dataclass
class BddBuild:
    nodes: dict[int, tuple[int, int, int, int]]
    unique: dict[tuple[int, int, int], int]

    def __init__(self) -> None:
        self.nodes = {}
        self.unique = {}

    def build(
        self,
        level: int,
        order: Sequence[int],
        assignments: Sequence[tuple[str, str]],
        output_idx: int,
    ) -> int:
        first = assignments[0][1][output_idx]
        if all(output[output_idx] == first for _, output in assignments):
            return 1 if first == "1" else 0
        if level >= len(order):
            raise AssertionError("nonconstant BDD leaf")
        var = order[level]
        low = [pair for pair in assignments if pair[0][var] == "0"]
        high = [pair for pair in assignments if pair[0][var] == "1"]
        if not low or not high:
            raise AssertionError("incomplete full-domain partition")
        low_id = self.build(level + 1, order, low, output_idx)
        high_id = self.build(level + 1, order, high, output_idx)
        if low_id == high_id:
            return low_id
        key = (level, low_id, high_id)
        known = self.unique.get(key)
        if known is not None:
            return known
        node_id = len(self.nodes) + 2
        self.nodes[node_id] = (level, var, low_id, high_id)
        self.unique[key] = node_id
        return node_id


def variable_orders(operand_width: int) -> dict[str, list[int]]:
    n = operand_width
    return {
        "grouped_lsb": list(range(2 * n)),
        "grouped_msb": list(range(n - 1, -1, -1))
        + list(range(2 * n - 1, n - 1, -1)),
        "interleaved_lsb": [item for idx in range(n) for item in (idx, n + idx)],
        "interleaved_msb": [
            item for idx in range(n - 1, -1, -1) for item in (idx, n + idx)
        ],
    }


def write_bdd_blif(
    path: Path,
    input_width: int,
    output_width: int,
    build: BddBuild,
    roots: Sequence[int],
) -> None:
    def signal(node_id: int) -> str:
        if node_id == 0:
            return "__zero"
        if node_id == 1:
            return "__one"
        return f"n{node_id}"

    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(".model semantic_bdd\n")
        handle.write(".inputs " + " ".join(f"i{i}" for i in range(input_width)) + "\n")
        handle.write(".outputs " + " ".join(f"o{i}" for i in range(output_width)) + "\n")
        handle.write(".names __zero\n")
        handle.write(".names __one\n1\n")
        for node_id in sorted(build.nodes):
            _level, var, low, high = build.nodes[node_id]
            # n = (not select and low) or (select and high)
            handle.write(
                f".names i{var} {signal(low)} {signal(high)} {signal(node_id)}\n"
            )
            handle.write("01- 1\n")
            handle.write("1-1 1\n")
        for output_idx, root in enumerate(roots):
            handle.write(f".names {signal(root)} o{output_idx}\n1 1\n")
        handle.write(".end\n")


def command_bdd(args: argparse.Namespace) -> None:
    root = Path(args.work).resolve()
    for name in INSTANCE_NAMES:
        directory = root / name
        discovery = load_discovery(directory / "discovery.json")
        input_width = int(discovery["input_width"])
        output_width = int(discovery["output_width"])
        selection = dict(discovery["selected"])
        assignments = [
            (bits, encode_hypothesis(selection, bits, output_width))
            for bits in all_bitstrings(input_width)
        ]
        metrics: dict[str, object] = {
            "schema": "occam71-shared-robdd-cofactor-v1",
            "input_width": input_width,
            "output_width": output_width,
            "orders": {},
        }
        candidates: list[tuple[int, str, Path]] = []
        for order_name, order in variable_orders(int(discovery["operand_width"])).items():
            build = BddBuild()
            roots = [
                build.build(0, order, assignments, output_idx)
                for output_idx in range(output_width)
            ]
            blif_path = directory / f"semantic-bdd-{order_name}.blif"
            write_bdd_blif(
                blif_path, input_width, output_width, build, roots
            )
            data = {
                "variable_order": order,
                "nonterminal_nodes": len(build.nodes),
                "roots": roots,
                "blif_path": str(blif_path),
                "blif_sha256": sha256_file(blif_path),
            }
            metrics["orders"][order_name] = data
            candidates.append((len(build.nodes), order_name, blif_path))
        node_count, selected_order, selected_path = min(candidates)
        metrics["selected"] = {
            "order_name": selected_order,
            "nonterminal_nodes": node_count,
            "blif_path": str(selected_path),
        }
        atomic_json(directory / "bdd-metrics.json", metrics)
        print(f"{name}: selected {selected_order}, shared ROBDD nodes={node_count}")


@dataclass(frozen=True)
class BlifNode:
    fanins: tuple[str, ...]
    output: str
    cubes: tuple[tuple[str, str], ...]


def logical_blif_lines(path: Path) -> list[str]:
    result: list[str] = []
    pending = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.endswith("\\"):
            pending += line[:-1].strip() + " "
            continue
        result.append((pending + line).strip())
        pending = ""
    if pending:
        raise ValueError(f"{path}: dangling continuation")
    return result


def parse_blif(path: Path) -> tuple[list[str], list[str], list[BlifNode]]:
    inputs: list[str] = []
    outputs: list[str] = []
    nodes: list[BlifNode] = []
    current_header: list[str] | None = None
    current_cubes: list[tuple[str, str]] = []
    in_exdc = False

    def finish() -> None:
        nonlocal current_header, current_cubes
        if current_header is not None:
            if len(current_header) < 1:
                raise AssertionError
            fanins = tuple(current_header[:-1])
            output = current_header[-1]
            nodes.append(BlifNode(fanins, output, tuple(current_cubes)))
        current_header = None
        current_cubes = []

    for line in logical_blif_lines(path):
        if line.startswith("."):
            finish()
            fields = line.split()
            directive = fields[0]
            if directive == ".exdc":
                in_exdc = True
            elif in_exdc:
                # ABC may preserve the now-unused external DC network.
                pass
            elif directive == ".inputs":
                inputs.extend(fields[1:])
            elif directive == ".outputs":
                outputs.extend(fields[1:])
            elif directive == ".names":
                current_header = fields[1:]
            elif directive in (".model", ".end"):
                pass
            elif directive in (".latch", ".subckt", ".gate"):
                raise ValueError(f"{path}: unsupported sequential/hierarchical directive {directive}")
        elif current_header is not None and not in_exdc:
            fields = line.split()
            fanin_count = len(current_header) - 1
            if fanin_count == 0:
                if fields != ["1"]:
                    raise ValueError(f"{path}: malformed constant cube {line!r}")
                current_cubes.append(("", "1"))
            elif len(fields) == 1:
                current_cubes.append((fields[0], "1"))
            elif len(fields) == 2:
                current_cubes.append((fields[0], fields[1]))
            else:
                raise ValueError(f"{path}: malformed cube {line!r}")
    finish()
    return inputs, outputs, nodes


def simulate_blif_bitparallel(
    path: Path,
) -> tuple[list[str], list[str], dict[str, int], int]:
    inputs, outputs, nodes = parse_blif(path)
    width = len(inputs)
    domain = 1 << width
    universe = (1 << domain) - 1
    values: dict[str, int] = {}
    for position, name in enumerate(inputs):
        table = 0
        shift = width - 1 - position
        for assignment in range(domain):
            if (assignment >> shift) & 1:
                table |= 1 << assignment
        values[name] = table

    pending = list(nodes)
    while pending:
        progress = False
        remaining: list[BlifNode] = []
        for node in pending:
            if any(name not in values for name in node.fanins):
                remaining.append(node)
                continue
            one_cubes = [cube for cube in node.cubes if cube[1] == "1"]
            zero_cubes = [cube for cube in node.cubes if cube[1] == "0"]
            if one_cubes and zero_cubes:
                raise ValueError(f"{path}: mixed output phases at {node.output}")
            default = universe if zero_cubes else 0
            result = default
            cubes = zero_cubes or one_cubes
            for pattern, _phase in cubes:
                if len(pattern) != len(node.fanins):
                    raise ValueError(f"{path}: cube width mismatch at {node.output}")
                term = universe
                for char, fanin in zip(pattern, node.fanins):
                    if char == "1":
                        term &= values[fanin]
                    elif char == "0":
                        term &= values[fanin] ^ universe
                    elif char != "-":
                        raise ValueError(f"{path}: invalid cube character {char!r}")
                if zero_cubes:
                    result &= term ^ universe
                else:
                    result |= term
            values[node.output] = result
            progress = True
        if not progress:
            missing = sorted(
                {
                    fanin
                    for node in remaining
                    for fanin in node.fanins
                    if fanin not in values
                }
            )
            raise ValueError(f"{path}: unresolved/cyclic signals {missing[:20]}")
        pending = remaining
    if any(name not in values for name in outputs):
        raise ValueError(f"{path}: undriven output")
    return inputs, outputs, values, universe


def truth_signature(
    function: Callable[[bool, bool], bool],
) -> tuple[int, int, int, int]:
    return tuple(
        int(function(bool(a), bool(b)))
        for a, b in ((0, 0), (0, 1), (1, 0), (1, 1))
    )


BASE_OPS: dict[str, Callable[[bool, bool], bool]] = {
    "AND": lambda a, b: a and b,
    "OR": lambda a, b: a or b,
    "XOR": lambda a, b: a != b,
    "NAND": lambda a, b: not (a and b),
    "NOR": lambda a, b: not (a or b),
    "XNOR": lambda a, b: a == b,
}


def canonical_gate_for_signature(
    signature: tuple[int, int, int, int]
) -> tuple[str, bool, bool, bool]:
    candidates: list[tuple[str, bool, bool, bool]] = []
    for op_name, op in BASE_OPS.items():
        for neg_a, neg_b, neg_out in itertools.product((False, True), repeat=3):
            def represented(a: bool, b: bool) -> bool:
                value = op(a ^ neg_a, b ^ neg_b)
                return value ^ neg_out

            if truth_signature(represented) == signature:
                candidates.append((op_name, neg_a, neg_b, neg_out))
    if not candidates:
        raise ValueError(f"no challenge-gate representation for {signature}")
    preference = {"XOR": 0, "XNOR": 1, "AND": 2, "OR": 3, "NAND": 4, "NOR": 5}
    return min(
        candidates,
        key=lambda item: (
            sum(item[1:]),
            preference[item[0]],
            item,
        ),
    )


def toggle(token: str) -> str:
    return token[1:] if token.startswith("~") else "~" + token


def blif_node_signature(node: BlifNode) -> tuple[int, ...]:
    width = len(node.fanins)
    result: list[int] = []
    for assignment in itertools.product((0, 1), repeat=width):
        one_cubes = [cube for cube in node.cubes if cube[1] == "1"]
        zero_cubes = [cube for cube in node.cubes if cube[1] == "0"]
        if one_cubes and zero_cubes:
            raise ValueError(f"mixed phases at {node.output}")
        value = 1 if zero_cubes else 0
        for pattern, _phase in zero_cubes or one_cubes:
            matched = all(
                char == "-" or int(char) == bit
                for char, bit in zip(pattern, assignment)
            )
            if matched:
                value = 0 if zero_cubes else 1
        result.append(value)
    return tuple(result)


def command_convert_k2(args: argparse.Namespace) -> None:
    source = Path(args.blif).resolve()
    destination = Path(args.out).resolve()
    inputs, outputs, nodes = parse_blif(source)
    aliases: dict[str, str] = {
        name: f"x{idx + 1}" for idx, name in enumerate(inputs)
    }
    gates: list[tuple[str, str, str, str]] = []
    const_zero: str | None = None

    def constant(value: int) -> str:
        nonlocal const_zero
        if const_zero is None:
            wire = f"w{len(gates) + 1}"
            gates.append((wire, "XOR", "x1", "x1"))
            const_zero = wire
        return const_zero if value == 0 else toggle(const_zero)

    pending = list(nodes)
    while pending:
        progress = False
        remaining: list[BlifNode] = []
        for node in pending:
            if any(name not in aliases for name in node.fanins):
                remaining.append(node)
                continue
            signature = blif_node_signature(node)
            if len(node.fanins) == 0:
                aliases[node.output] = constant(signature[0])
            elif len(node.fanins) == 1:
                source_token = aliases[node.fanins[0]]
                if signature == (0, 0):
                    aliases[node.output] = constant(0)
                elif signature == (1, 1):
                    aliases[node.output] = constant(1)
                elif signature == (0, 1):
                    aliases[node.output] = source_token
                elif signature == (1, 0):
                    aliases[node.output] = toggle(source_token)
                else:
                    raise AssertionError(signature)
            elif len(node.fanins) == 2:
                op, neg_a, neg_b, neg_out = canonical_gate_for_signature(signature)
                left = aliases[node.fanins[0]]
                right = aliases[node.fanins[1]]
                if neg_a:
                    left = toggle(left)
                if neg_b:
                    right = toggle(right)
                wire = f"w{len(gates) + 1}"
                gates.append((wire, op, left, right))
                aliases[node.output] = toggle(wire) if neg_out else wire
            else:
                raise ValueError(
                    f"{source}: node {node.output} has {len(node.fanins)} fanins; expected K<=2"
                )
            progress = True
        if not progress:
            raise ValueError(f"{source}: unresolved nodes during conversion")
        pending = remaining

    output_tokens = [aliases[name] for name in outputs]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(f"INPUTS {len(inputs)}\n")
        for wire, op, left, right in gates:
            handle.write(f"{wire} = {op} {left} {right}\n")
        handle.write("OUTPUTS " + " ".join(output_tokens) + "\n")
    metadata = {
        "source_blif": str(source),
        "source_blif_sha256": sha256_file(source),
        "challenge_path": str(destination),
        "challenge_sha256": sha256_file(destination),
        "inputs": len(inputs),
        "outputs": len(outputs),
        "gates": len(gates),
        "all_logic_nodes_at_most_two_fanins": True,
    }
    atomic_json(destination.with_suffix(".conversion.json"), metadata)
    print(f"{destination}: {len(gates)} challenge gates")


def parse_challenge(path: Path) -> tuple[int, list[tuple[str, str, str, str]], list[str]]:
    ninputs: int | None = None
    gates: list[tuple[str, str, str, str]] = []
    outputs: list[str] | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        if fields[0] == "INPUTS":
            ninputs = int(fields[1])
        elif fields[0] == "OUTPUTS":
            outputs = fields[1:]
        else:
            if len(fields) != 5 or fields[1] != "=":
                raise ValueError(f"{path}: malformed challenge line {line!r}")
            gates.append((fields[0], fields[2], fields[3], fields[4]))
    if ninputs is None or outputs is None:
        raise ValueError(f"{path}: missing header/output")
    return ninputs, gates, outputs


def simulate_challenge_bitparallel(path: Path) -> tuple[tuple[int, ...], int, int]:
    ninputs, gates, outputs = parse_challenge(path)
    domain = 1 << ninputs
    universe = (1 << domain) - 1
    values: dict[str, int] = {}
    for input_idx in range(ninputs):
        table = 0
        # Challenge x1 is the first character and also the LSB of the
        # benchmark operand; enumeration here follows string order.
        shift = ninputs - 1 - input_idx
        for assignment in range(domain):
            if (assignment >> shift) & 1:
                table |= 1 << assignment
        values[f"x{input_idx + 1}"] = table

    def value(token: str) -> int:
        inverted = token.startswith("~")
        base = token[1:] if inverted else token
        result = values[base]
        return result ^ universe if inverted else result

    for output, op, left_token, right_token in gates:
        left, right = value(left_token), value(right_token)
        if op == "AND":
            result = left & right
        elif op == "OR":
            result = left | right
        elif op == "XOR":
            result = left ^ right
        elif op == "NAND":
            result = (left & right) ^ universe
        elif op == "NOR":
            result = (left | right) ^ universe
        elif op == "XNOR":
            result = (left ^ right) ^ universe
        else:
            raise ValueError(f"{path}: unsupported gate {op}")
        values[output] = result
    return tuple(value(token) for token in outputs), universe, len(gates)


def expected_tables(
    selection: dict[str, object], input_width: int, output_width: int
) -> tuple[int, ...]:
    tables = [0] * output_width
    for assignment, input_bits in enumerate(all_bitstrings(input_width)):
        output_bits = encode_hypothesis(selection, input_bits, output_width)
        for idx, char in enumerate(output_bits):
            if char == "1":
                tables[idx] |= 1 << assignment
    return tuple(tables)


def command_verify(args: argparse.Namespace) -> None:
    discovery = load_discovery(Path(args.discovery).resolve())
    circuit_path = Path(args.circuit).resolve()
    actual, universe, gates = simulate_challenge_bitparallel(circuit_path)
    expected = expected_tables(
        dict(discovery["selected"]),
        int(discovery["input_width"]),
        int(discovery["output_width"]),
    )
    if len(actual) != len(expected):
        raise ValueError("output width mismatch")
    output_bit_mismatches = [(a ^ e).bit_count() for a, e in zip(actual, expected)]
    any_mismatch = 0
    for a, e in zip(actual, expected):
        any_mismatch |= a ^ e
    vector_mismatches = any_mismatch.bit_count()
    domain = universe.bit_count()

    train_rows = read_csv_exact(Path(str(discovery["train_path"])), ("input", "output"))
    train_mismatches = 0
    for input_bits, output_bits in train_rows:
        assignment = int(input_bits, 2)
        predicted = "".join(
            "1" if (table >> assignment) & 1 else "0" for table in actual
        )
        if predicted != output_bits:
            train_mismatches += 1
    result = {
        "schema": "occam71-challenge-circuit-exhaustive-audit-v1",
        "circuit": str(circuit_path),
        "circuit_sha256": sha256_file(circuit_path),
        "gates": gates,
        "domain": domain,
        "train_rows": len(train_rows),
        "train_vector_mismatches": train_mismatches,
        "train_accuracy": 1 - train_mismatches / len(train_rows),
        "full_domain_vector_mismatches": vector_mismatches,
        "full_domain_accuracy": 1 - vector_mismatches / domain,
        "output_bit_mismatches": output_bit_mismatches,
        "exact_full_domain": vector_mismatches == 0,
    }
    output = Path(args.out).resolve()
    atomic_json(output, result)
    print(
        f"{circuit_path.name}: gates={gates}, train mismatches={train_mismatches}, "
        f"full mismatches={vector_mismatches}/{domain}"
    )
    if args.require_exact and vector_mismatches:
        raise RuntimeError("circuit is not exact over the full domain")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover")
    discover.add_argument("--datasets-root", required=True)
    discover.add_argument("--out", required=True)
    discover.set_defaults(func=command_discover)

    audit = sub.add_parser("audit-commitments")
    audit.add_argument("--datasets-root", required=True)
    audit.add_argument("--work", required=True)
    audit.set_defaults(func=command_audit_commitments)

    specs = sub.add_parser("specs")
    specs.add_argument("--work", required=True)
    specs.set_defaults(func=command_specs)

    bdd = sub.add_parser("bdd")
    bdd.add_argument("--work", required=True)
    bdd.set_defaults(func=command_bdd)

    convert = sub.add_parser("convert-k2")
    convert.add_argument("--blif", required=True)
    convert.add_argument("--out", required=True)
    convert.set_defaults(func=command_convert_k2)

    verify = sub.add_parser("verify")
    verify.add_argument("--discovery", required=True)
    verify.add_argument("--circuit", required=True)
    verify.add_argument("--out", required=True)
    verify.add_argument("--require-exact", action="store_true")
    verify.set_defaults(func=command_verify)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
