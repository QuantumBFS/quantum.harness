#!/usr/bin/env python3
"""Exact finite-field tensor-network route for OCCAM issue 71.

The discovery boundary is deliberately narrow: this program consumes the
train-only ``discovery.json`` manifests produced by the symbolic route and the
``train.csv`` file named in each manifest.  It never reads a generator, public
test input, commitment, hidden output, or competitor contribution.

For every frozen Boolean function it:

* computes minimal exact GF(2) tensor-train ranks for every output bit under
  several input-variable orders;
* computes exact GF(2) ranks of the sparse graph tensor
  T(input, output) = [output == f(input)] under arithmetic and grouped orders;
* writes an explicit exact TT decomposition for the best fixed input order;
* compiles that TT contraction to the challenge AND/XOR gate language; and
* exhaustively audits the compiled circuit on both training rows and the full
  frozen semantic domain.

All rank factorizations use bit-exact Gaussian elimination over GF(2).
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


ROOT_SEED = 42
SCHEMA = "occam71-exact-gf2-tensor-train-v1"
INSTANCES = ("mystery-A", "mystery-B", "mystery-C", "mystery-D")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def import_symbolic_routes(route_dir: Path):
    route_dir = route_dir.resolve()
    sys.path.insert(0, str(route_dir))
    try:
        import routes  # type: ignore
    finally:
        sys.path.pop(0)
    return routes


def validate_discovery(discovery: dict[str, object], instance: str) -> None:
    if int(discovery.get("root_seed", -1)) != ROOT_SEED:
        raise ValueError(f"{instance}: discovery root seed is not {ROOT_SEED}")
    if "train-only" not in str(discovery.get("schema", "")):
        raise ValueError(f"{instance}: expected a train-only discovery manifest")
    boundary = discovery.get("read_boundary")
    if not isinstance(boundary, dict):
        raise ValueError(f"{instance}: missing discovery read boundary")
    allowed = boundary.get("allowed")
    if not isinstance(allowed, list) or len(allowed) != 1:
        raise ValueError(f"{instance}: discovery must name exactly one allowed input")
    train_path = str(discovery.get("train_path", ""))
    if str(allowed[0]) != train_path:
        raise ValueError(f"{instance}: manifest train path/read boundary disagree")
    selection = discovery.get("selected")
    if not isinstance(selection, dict) or "expr_id" not in selection:
        raise ValueError(f"{instance}: no frozen selected expression")


def validate_train_rows(
    rows: Sequence[tuple[str, str]], input_width: int, output_width: int
) -> None:
    if not rows:
        raise ValueError("training set is empty")
    for input_bits, output_bits in rows:
        if (
            len(input_bits) != input_width
            or len(output_bits) != output_width
            or set(input_bits) - {"0", "1"}
            or set(output_bits) - {"0", "1"}
        ):
            raise ValueError("training CSV must contain fixed-width binary strings only")


def gf2_rank_factor(rows: Sequence[int]) -> tuple[list[int], list[int]]:
    """Return A rows and B rows such that M = A B over GF(2).

    ``rows`` are bit-packed rows of M.  Each returned A row is a bit mask of
    coefficients in the echelon-row basis B.  B contains independent
    bit-packed rows.  The construction is exact and deterministic.
    """

    pivot_basis: dict[int, tuple[int, int]] = {}
    basis_rows: list[int] = []
    for original in rows:
        value = original
        while value:
            pivot = value.bit_length() - 1
            existing = pivot_basis.get(pivot)
            if existing is None:
                basis_index = len(basis_rows)
                pivot_basis[pivot] = (value, basis_index)
                basis_rows.append(value)
                break
            value ^= existing[0]

    coefficients: list[int] = []
    for original in rows:
        value = original
        coefficient = 0
        while value:
            pivot = value.bit_length() - 1
            basis_row, basis_index = pivot_basis[pivot]
            value ^= basis_row
            coefficient ^= 1 << basis_index
        coefficients.append(coefficient)
    return coefficients, basis_rows


@dataclass(frozen=True)
class TTCore:
    left_rank: int
    right_rank: int
    # rows[2*a + physical_bit] is a bit mask over the right bond.
    rows: tuple[int, ...]

    @property
    def ones(self) -> int:
        return sum(row.bit_count() for row in self.rows)


@dataclass(frozen=True)
class TTDecomposition:
    variable_order: tuple[int, ...]
    ranks: tuple[int, ...]
    cores: tuple[TTCore, ...]

    @property
    def dense_entries(self) -> int:
        return sum(
            2 * self.ranks[index] * self.ranks[index + 1]
            for index in range(len(self.variable_order))
        )

    @property
    def nonzero_entries(self) -> int:
        return sum(core.ones for core in self.cores)

    @property
    def peak_rank(self) -> int:
        return max(self.ranks)


def tt_decompose(truth: int, variable_order: Sequence[int]) -> TTDecomposition:
    """Exact tensor-train factorization of a binary truth tensor over GF(2)."""

    nvariables = len(variable_order)
    if nvariables == 0:
        raise ValueError("at least one variable is required")
    if truth == 0:
        raise ValueError("the all-zero tensor is not used by this benchmark")
    if truth.bit_length() > (1 << nvariables):
        raise ValueError("truth tensor exceeds declared variable count")

    bond_rows = [truth]
    left_rank = 1
    ranks = [1]
    cores: list[TTCore] = []
    for position in range(nvariables):
        tail_width = 1 << (nvariables - position - 1)
        mask = (1 << tail_width) - 1
        unfolded_rows: list[int] = []
        for row in bond_rows:
            unfolded_rows.append(row & mask)
            unfolded_rows.append((row >> tail_width) & mask)
        coefficients, basis_rows = gf2_rank_factor(unfolded_rows)
        right_rank = len(basis_rows)
        if right_rank == 0:
            raise AssertionError("nonzero TT unexpectedly acquired zero bond rank")
        cores.append(
            TTCore(
                left_rank=left_rank,
                right_rank=right_rank,
                rows=tuple(coefficients),
            )
        )
        ranks.append(right_rank)
        bond_rows = basis_rows
        left_rank = right_rank

    if ranks[-1] != 1 or bond_rows != [1]:
        raise AssertionError(
            f"invalid terminal factor: rank={ranks[-1]}, rows={bond_rows[:4]}"
        )
    return TTDecomposition(
        variable_order=tuple(variable_order),
        ranks=tuple(ranks),
        cores=tuple(cores),
    )


def contract_tt(decomposition: TTDecomposition, ordered_bits: Sequence[int]) -> int:
    if len(ordered_bits) != len(decomposition.cores):
        raise ValueError("assignment width mismatch")
    state = 1
    for bit, core in zip(ordered_bits, decomposition.cores):
        next_state = 0
        active = state
        while active:
            least = active & -active
            left_index = least.bit_length() - 1
            next_state ^= core.rows[2 * left_index + int(bit)]
            active ^= least
        state = next_state
    if state not in (0, 1):
        raise AssertionError(f"invalid scalar TT contraction {state}")
    return state


def permute_truth(
    canonical_truth: int, input_width: int, variable_order: Sequence[int]
) -> int:
    """Permute a challenge truth table into lexicographic TT physical order."""

    if sorted(variable_order) != list(range(input_width)):
        raise ValueError("input variable order is not a permutation")
    packed = bytearray((1 << input_width) // 8)
    for canonical_assignment in range(1 << input_width):
        if not ((canonical_truth >> canonical_assignment) & 1):
            continue
        ordered_assignment = 0
        for original_index in variable_order:
            bit = (canonical_assignment >> (input_width - 1 - original_index)) & 1
            ordered_assignment = (ordered_assignment << 1) | bit
        packed[ordered_assignment >> 3] |= 1 << (ordered_assignment & 7)
    return int.from_bytes(packed, "little")


def input_orders(operand_width: int) -> dict[str, tuple[int, ...]]:
    n = operand_width
    return {
        "grouped_lsb": tuple(range(2 * n)),
        "grouped_msb": tuple(range(n - 1, -1, -1))
        + tuple(range(2 * n - 1, n - 1, -1)),
        "interleaved_lsb": tuple(
            index for bit in range(n) for index in (bit, n + bit)
        ),
        "interleaved_msb": tuple(
            index for bit in range(n - 1, -1, -1) for index in (bit, n + bit)
        ),
    }


def relation_orders(
    operand_width: int, output_width: int
) -> dict[str, tuple[tuple[str, int], ...]]:
    n = operand_width
    grouped_inputs = tuple(("i", index) for index in range(2 * n))
    grouped_outputs = tuple(("o", index) for index in range(output_width))
    interleaved_inputs = tuple(
        ("i", index) for bit in range(n) for index in (bit, n + bit)
    )
    digit_lsb: list[tuple[str, int]] = []
    for bit in range(max(n, output_width)):
        if bit < n:
            digit_lsb.extend((("i", bit), ("i", n + bit)))
        if bit < output_width:
            digit_lsb.append(("o", bit))
    digit_msb: list[tuple[str, int]] = []
    for bit in range(max(n, output_width) - 1, -1, -1):
        if bit < n:
            digit_msb.extend((("i", bit), ("i", n + bit)))
        if bit < output_width:
            digit_msb.append(("o", bit))
    return {
        "inputs_then_outputs_lsb": grouped_inputs + grouped_outputs,
        "interleaved_inputs_then_outputs_lsb": interleaved_inputs + grouped_outputs,
        "digit_lsb": tuple(digit_lsb),
        "digit_msb": tuple(digit_msb),
    }


def graph_truth(
    routes,
    selection: dict[str, object],
    input_width: int,
    output_width: int,
    order: Sequence[tuple[str, int]],
) -> int:
    total_variables = input_width + output_width
    if len(order) != total_variables or len(set(order)) != total_variables:
        raise ValueError("relation order does not cover every graph variable")
    packed = bytearray((1 << total_variables) // 8)
    for canonical_assignment in range(1 << input_width):
        input_bits = format(canonical_assignment, f"0{input_width}b")
        output_bits = routes.encode_hypothesis(
            selection, input_bits, output_width
        )
        ordered_assignment = 0
        for kind, index in order:
            bit = input_bits[index] if kind == "i" else output_bits[index]
            ordered_assignment = (ordered_assignment << 1) | int(bit)
        packed[ordered_assignment >> 3] |= 1 << (ordered_assignment & 7)
    return int.from_bytes(packed, "little")


def stats(decomposition: TTDecomposition) -> dict[str, object]:
    return {
        "ranks": list(decomposition.ranks),
        "peak_rank": decomposition.peak_rank,
        "dense_core_entries": decomposition.dense_entries,
        "nonzero_core_entries": decomposition.nonzero_entries,
    }


Signal = int | str


class ChallengeCompiler:
    def __init__(self, input_width: int):
        self.input_width = input_width
        self.gates: list[tuple[str, str, str, str]] = []
        self.cache: dict[tuple[str, str, str], str] = {}

    @staticmethod
    def toggle(signal: str) -> str:
        return signal[1:] if signal.startswith("~") else "~" + signal

    @staticmethod
    def complements(left: str, right: str) -> bool:
        return ChallengeCompiler.toggle(left) == right

    def emit(self, operation: str, left: str, right: str) -> str:
        if operation in {"AND", "XOR"} and right < left:
            left, right = right, left
        key = (operation, left, right)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        output = f"w{len(self.gates) + 1}"
        self.gates.append((output, operation, left, right))
        self.cache[key] = output
        return output

    def conjunction(self, left: Signal, right: Signal) -> Signal:
        if left == 0 or right == 0:
            return 0
        if left == 1:
            return right
        if right == 1:
            return left
        assert isinstance(left, str) and isinstance(right, str)
        if left == right:
            return left
        if self.complements(left, right):
            return 0
        return self.emit("AND", left, right)

    def xor_many(self, terms: Iterable[Signal]) -> Signal:
        parity = 0
        bases: dict[str, int] = {}
        for term in terms:
            if term == 0:
                continue
            if term == 1:
                parity ^= 1
                continue
            assert isinstance(term, str)
            if term.startswith("~"):
                parity ^= 1
                term = term[1:]
            bases[term] = bases.get(term, 0) ^ 1
        active = sorted(base for base, coefficient in bases.items() if coefficient)
        if not active:
            return parity
        result = active[0]
        for term in active[1:]:
            result = self.emit("XOR", result, term)
        return self.toggle(result) if parity else result

    @staticmethod
    def selector(input_token: str, at_zero: int, at_one: int) -> Signal:
        pair = (at_zero, at_one)
        if pair == (0, 0):
            return 0
        if pair == (1, 1):
            return 1
        if pair == (0, 1):
            return input_token
        if pair == (1, 0):
            return ChallengeCompiler.toggle(input_token)
        raise AssertionError(pair)

    def compile_tt(self, decomposition: TTDecomposition) -> Signal:
        state: list[Signal] = [1]
        for original_input, core in zip(
            decomposition.variable_order, decomposition.cores
        ):
            if len(state) != core.left_rank:
                raise AssertionError("TT/compiler bond-rank disagreement")
            input_token = f"x{original_input + 1}"
            next_state: list[Signal] = []
            for right_index in range(core.right_rank):
                terms: list[Signal] = []
                for left_index, left_signal in enumerate(state):
                    at_zero = (
                        core.rows[2 * left_index] >> right_index
                    ) & 1
                    at_one = (
                        core.rows[2 * left_index + 1] >> right_index
                    ) & 1
                    selector = self.selector(input_token, at_zero, at_one)
                    terms.append(self.conjunction(left_signal, selector))
                next_state.append(self.xor_many(terms))
            state = next_state
        if len(state) != 1:
            raise AssertionError("TT did not contract to a scalar")
        return state[0]

    def materialize_constant(self, signal: Signal) -> str:
        if isinstance(signal, str):
            return signal
        zero = self.emit("XOR", "x1", "x1")
        return zero if signal == 0 else self.toggle(zero)

    def write(self, path: Path, outputs: Sequence[Signal]) -> None:
        output_tokens = [self.materialize_constant(signal) for signal in outputs]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(f"INPUTS {self.input_width}\n")
            for output, operation, left, right in self.gates:
                handle.write(f"{output} = {operation} {left} {right}\n")
            handle.write("OUTPUTS " + " ".join(output_tokens) + "\n")


def serialize_tt(
    path: Path,
    instance: str,
    output_index: int,
    decomposition: TTDecomposition,
) -> None:
    payload = {
        "schema": SCHEMA,
        "field": "GF(2)",
        "instance": instance,
        "output_index": output_index,
        "variable_order": list(decomposition.variable_order),
        "ranks": list(decomposition.ranks),
        "dense_core_entries": decomposition.dense_entries,
        "nonzero_core_entries": decomposition.nonzero_entries,
        "cores": [
            {
                "shape": [core.left_rank, 2, core.right_rank],
                "rows_hex": [hex(row) for row in core.rows],
            }
            for core in decomposition.cores
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as handle:
            handle.write(encoded)
    os.replace(temporary, path)


def audit_circuit(
    routes,
    discovery: dict[str, object],
    circuit_path: Path,
    train_rows: Sequence[tuple[str, str]],
) -> dict[str, object]:
    actual, universe, gate_count = routes.simulate_challenge_bitparallel(circuit_path)
    expected = routes.expected_tables(
        dict(discovery["selected"]),
        int(discovery["input_width"]),
        int(discovery["output_width"]),
    )
    if len(actual) != len(expected):
        raise AssertionError("compiled circuit output width mismatch")
    bit_mismatches = [(a ^ b).bit_count() for a, b in zip(actual, expected)]
    mismatch_union = 0
    for actual_bit, expected_bit in zip(actual, expected):
        mismatch_union |= actual_bit ^ expected_bit
    train_mismatches = 0
    for input_bits, output_bits in train_rows:
        assignment = int(input_bits, 2)
        predicted = "".join(
            "1" if ((table >> assignment) & 1) else "0" for table in actual
        )
        train_mismatches += predicted != output_bits
    return {
        "schema": "occam71-exact-tn-challenge-audit-v1",
        "circuit": str(circuit_path),
        "circuit_sha256": sha256_file(circuit_path),
        "gates": gate_count,
        "domain": universe.bit_count(),
        "train_rows": len(train_rows),
        "train_vector_mismatches": train_mismatches,
        "train_accuracy": 1 - train_mismatches / len(train_rows),
        "full_domain_vector_mismatches": mismatch_union.bit_count(),
        "full_domain_accuracy": 1 - mismatch_union.bit_count() / universe.bit_count(),
        "output_bit_mismatches": bit_mismatches,
        "exact_full_domain": mismatch_union == 0,
    }


def run_instance(
    instance: str,
    symbolic_root: Path,
    route_dir: Path,
    output_root: Path,
) -> dict[str, object]:
    started = time.monotonic()
    routes = import_symbolic_routes(route_dir)
    symbolic_instance = symbolic_root / instance
    discovery_path = symbolic_instance / "discovery.json"
    discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
    validate_discovery(discovery, instance)
    input_width = int(discovery["input_width"])
    operand_width = int(discovery["operand_width"])
    output_width = int(discovery["output_width"])
    selection = dict(discovery["selected"])
    train_path = Path(str(discovery["train_path"])).resolve()
    train_rows = routes.read_csv_exact(train_path, ("input", "output"))
    validate_train_rows(train_rows, input_width, output_width)
    expected_tables = routes.expected_tables(selection, input_width, output_width)

    instance_dir = output_root / instance
    instance_dir.mkdir(parents=True, exist_ok=True)
    print(
        f"[{instance}] expr={selection['expr_id']} input={input_width} "
        f"output={output_width} train={len(train_rows)}",
        flush=True,
    )

    order_map = input_orders(operand_width)
    output_profiles: dict[str, object] = {}
    aggregate_scores: dict[str, dict[str, int]] = {
        name: {"dense_core_entries": 0, "peak_rank": 0, "nonzero_core_entries": 0}
        for name in order_map
    }
    for output_index, canonical_truth in enumerate(expected_tables):
        per_order: dict[str, object] = {}
        for order_name, order in order_map.items():
            ordered_truth = permute_truth(canonical_truth, input_width, order)
            decomposition = tt_decompose(ordered_truth, order)
            profile = stats(decomposition)
            per_order[order_name] = profile
            aggregate_scores[order_name]["dense_core_entries"] += int(
                profile["dense_core_entries"]
            )
            aggregate_scores[order_name]["nonzero_core_entries"] += int(
                profile["nonzero_core_entries"]
            )
            aggregate_scores[order_name]["peak_rank"] = max(
                aggregate_scores[order_name]["peak_rank"],
                int(profile["peak_rank"]),
            )
        output_profiles[str(output_index)] = per_order
        print(f"[{instance}] output bit {output_index + 1}/{output_width}", flush=True)

    best_order_name = min(
        order_map,
        key=lambda name: (
            aggregate_scores[name]["dense_core_entries"],
            aggregate_scores[name]["nonzero_core_entries"],
            aggregate_scores[name]["peak_rank"],
            name,
        ),
    )
    best_order = order_map[best_order_name]
    print(
        f"[{instance}] best output-TT order={best_order_name} "
        f"dense={aggregate_scores[best_order_name]['dense_core_entries']}",
        flush=True,
    )

    compiler = ChallengeCompiler(input_width)
    compiled_outputs: list[Signal] = []
    decompositions: list[TTDecomposition] = []
    for output_index, canonical_truth in enumerate(expected_tables):
        ordered_truth = permute_truth(canonical_truth, input_width, best_order)
        decomposition = tt_decompose(ordered_truth, best_order)
        # Deterministic exact contraction spot/full check.  Full contraction is
        # cheap for these domains and independent of the later gate simulator.
        for canonical_assignment in range(1 << input_width):
            ordered_bits = [
                (canonical_assignment >> (input_width - 1 - original)) & 1
                for original in best_order
            ]
            actual = contract_tt(decomposition, ordered_bits)
            expected = (canonical_truth >> canonical_assignment) & 1
            if actual != expected:
                raise AssertionError(
                    f"{instance} bit {output_index}: TT contraction mismatch"
                )
        serialize_tt(
            instance_dir / f"output-{output_index:02d}-best-tt.json.gz",
            instance,
            output_index,
            decomposition,
        )
        compiled_outputs.append(compiler.compile_tt(decomposition))
        decompositions.append(decomposition)

    circuit_path = instance_dir / "exact-gf2-tt.txt"
    compiler.write(circuit_path, compiled_outputs)
    audit = audit_circuit(routes, discovery, circuit_path, train_rows)
    if not audit["exact_full_domain"] or audit["train_vector_mismatches"]:
        raise RuntimeError(f"{instance}: exact TT circuit audit failed")
    atomic_json(instance_dir / "circuit-audit.json", audit)

    relation_profiles: dict[str, object] = {}
    for relation_name, relation_order in relation_orders(
        operand_width, output_width
    ).items():
        relation = graph_truth(
            routes, selection, input_width, output_width, relation_order
        )
        # TT variable identifiers are positional here; the human-readable
        # relation_order beside the profile carries the semantic labels.
        decomposition = tt_decompose(relation, range(len(relation_order)))
        relation_profiles[relation_name] = {
            "variable_order": [
                f"{kind}{index}" for kind, index in relation_order
            ],
            **stats(decomposition),
        }
        print(
            f"[{instance}] graph order={relation_name} "
            f"peak={decomposition.peak_rank}",
            flush=True,
        )

    manifest = {
        "schema": SCHEMA,
        "root_seed": ROOT_SEED,
        "instance": instance,
        "frozen_expression": selection,
        "input_width": input_width,
        "operand_width": operand_width,
        "output_width": output_width,
        "train_rows": len(train_rows),
        "discovery_manifest": str(discovery_path.resolve()),
        "discovery_sha256": sha256_file(discovery_path),
        "train_path": str(train_path),
        "train_sha256": sha256_file(train_path),
        "read_boundary": {
            "recognition_inputs": [str(discovery_path.resolve()), str(train_path)],
            "post_discovery_semantic_audit": "frozen selected expression only",
            "never_read": [
                "generator source",
                "test_inputs.csv",
                "commitment.sha256",
                "test_outputs.csv",
                "competitor PR content",
            ],
        },
        "field": "GF(2)",
        "output_bit_tt": {
            "orders": {name: list(order) for name, order in order_map.items()},
            "profiles": output_profiles,
            "aggregate": aggregate_scores,
            "selected_order": best_order_name,
            "selected_order_indices": list(best_order),
        },
        "graph_relation_tt": relation_profiles,
        "explicit_decompositions": [
            {
                "output_index": index,
                "path": str(
                    (instance_dir / f"output-{index:02d}-best-tt.json.gz").resolve()
                ),
                "sha256": sha256_file(
                    instance_dir / f"output-{index:02d}-best-tt.json.gz"
                ),
                **stats(decomposition),
            }
            for index, decomposition in enumerate(decompositions)
        ],
        "compiled_challenge": audit,
        "runtime_seconds": time.monotonic() - started,
    }
    atomic_json(instance_dir / "tn-summary.json", manifest)
    print(
        f"[{instance}] exact gates={audit['gates']} "
        f"runtime={manifest['runtime_seconds']:.1f}s",
        flush=True,
    )
    return manifest


def write_report(
    output_root: Path,
    results: Sequence[dict[str, object]],
    baseline_root: Path | None,
) -> None:
    rows: list[dict[str, object]] = []
    for result in results:
        instance = str(result["instance"])
        output_tt = dict(result["output_bit_tt"])
        selected = str(output_tt["selected_order"])
        aggregate = dict(dict(output_tt["aggregate"])[selected])
        relation = dict(result["graph_relation_tt"])
        best_relation_name = min(
            relation,
            key=lambda name: (
                int(dict(relation[name])["peak_rank"]),
                int(dict(relation[name])["dense_core_entries"]),
                name,
            ),
        )
        baseline_gates: int | None = None
        if baseline_root is not None:
            baseline_path = baseline_root / instance / "abc-flow-summary.json"
            if baseline_path.is_file():
                baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
                baseline_gates = int(dict(baseline["best"])["gates"])
        tn_gates = int(dict(result["compiled_challenge"])["gates"])
        rows.append(
            {
                "instance": instance,
                "expression": dict(result["frozen_expression"])["expression"],
                "selected_output_order": selected,
                "output_peak_rank": int(aggregate["peak_rank"]),
                "output_dense_entries": int(aggregate["dense_core_entries"]),
                "output_nonzero_entries": int(aggregate["nonzero_core_entries"]),
                "best_graph_order": best_relation_name,
                "best_graph_peak_rank": int(
                    dict(relation[best_relation_name])["peak_rank"]
                ),
                "tn_challenge_gates": tn_gates,
                "symbolic_bdd_gates": baseline_gates,
                "tn_to_bdd_gate_ratio": (
                    tn_gates / baseline_gates if baseline_gates else None
                ),
                "exact_full_domain": bool(
                    dict(result["compiled_challenge"])["exact_full_domain"]
                ),
            }
        )

    summary = {
        "schema": "occam71-exact-tn-summary-v1",
        "root_seed": ROOT_SEED,
        "instances": rows,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
        },
    }
    atomic_json(output_root / "summary.json", summary)

    lines = [
        "# Issue 71 exact finite-field tensor-network route",
        "",
        "This route uses only each train-only discovery manifest and its `train.csv` "
        "during recognition.  Every expression is frozen before full-domain "
        "enumeration.  No generator, test input, commitment, hidden output, or "
        "competitor contribution is read.",
        "",
        "All decompositions and ranks are exact over GF(2).  The per-output TT "
        "cores are serialized, independently contracted over the full input "
        "domain, compiled to the challenge AND/XOR language, and exhaustively "
        "audited again with a bit-parallel gate simulator.",
        "",
        "| Instance | Frozen function | Best input order | Peak output rank | "
        "Dense TT entries | Exact TN gates | Exact BDD gates | Ratio | "
        "Best graph order / peak |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        baseline = (
            str(row["symbolic_bdd_gates"])
            if row["symbolic_bdd_gates"] is not None
            else "n/a"
        )
        ratio = (
            f"{float(row['tn_to_bdd_gate_ratio']):.2f}×"
            if row["tn_to_bdd_gate_ratio"] is not None
            else "n/a"
        )
        lines.append(
            f"| {row['instance']} | `{row['expression']}` | "
            f"{row['selected_output_order']} | {row['output_peak_rank']} | "
            f"{row['output_dense_entries']} | {row['tn_challenge_gates']} | "
            f"{baseline} | {ratio} | {row['best_graph_order']} / "
            f"{row['best_graph_peak_rank']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "For a fixed physical-variable order, every listed cut rank is the "
            "minimal possible TT bond dimension over GF(2).  Thus the rank "
            "profiles quantify both the useful arithmetic locality and the "
            "obstruction: where multiplication or sum-of-squares produces a "
            "large middle bond, no exact GF(2) TT with that order can use a "
            "smaller bond.",
            "",
            "The explicit TT-to-gate compiler is a direct contraction compiler, "
            "not a logic optimizer.  A gate count above the exact BDD baseline "
            "therefore means the TN remains a valuable structural diagnostic but "
            "does not itself beat the current circuit route.  A smaller count is "
            "an immediately usable exact challenge circuit.",
            "",
            "See each `tn-summary.json` for every cut rank, every variable order, "
            "the exact circuit audit, discovery/train hashes, and serialized-core "
            "hashes.",
        ]
    )
    (output_root / "REPORT.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )


def write_hash_manifest(output_root: Path, code_paths: Sequence[Path]) -> None:
    excluded = {"SHA256SUMS", "RUN_COMPLETE"}
    paths = [
        path
        for path in output_root.rglob("*")
        if (
            path.is_file()
            and path.name not in excluded
            and "logs" not in path.relative_to(output_root).parts
            and not path.name.startswith("run-metadata-")
        )
    ]
    paths.extend(path.resolve() for path in code_paths)
    unique = sorted(set(paths), key=lambda path: str(path))
    lines = [f"{sha256_file(path)}  {path}" for path in unique]
    (output_root / "SHA256SUMS").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbolic-root", required=True, type=Path)
    parser.add_argument("--route-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--baseline-root", type=Path)
    parser.add_argument(
        "--instances",
        nargs="+",
        default=list(INSTANCES),
        choices=list(INSTANCES),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if ROOT_SEED != 42:
        raise AssertionError("canonical root seed changed")
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    results = [
        run_instance(
            instance,
            args.symbolic_root.resolve(),
            args.route_dir.resolve(),
            output_root,
        )
        for instance in args.instances
    ]
    write_report(
        output_root,
        results,
        args.baseline_root.resolve() if args.baseline_root else None,
    )
    code_paths = [Path(__file__).resolve()]
    slurm_path = Path(__file__).with_name("slurm_exact_tn.sh").resolve()
    if slurm_path.is_file():
        code_paths.append(slurm_path)
    write_hash_manifest(output_root, code_paths)
    (output_root / "RUN_COMPLETE").write_text(
        "exact GF(2) tensor-network route complete\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"RUN_COMPLETE {output_root}", flush=True)


if __name__ == "__main__":
    main()
