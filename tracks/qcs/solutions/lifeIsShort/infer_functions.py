#!/usr/bin/env python3
"""Infer the four released mystery arithmetic semantics from training CSVs."""

import argparse
import csv
import hashlib
import io
import itertools
import json
import os
import re
import sys
from fractions import Fraction


DATASET_IDS = ("A", "B", "C", "D")
OPERATION_ORDER = (
    "addition",
    "absolute_difference",
    "multiplication",
    "sum_of_squares",
)

_BINARY_PATTERN = re.compile(r"\A[01]+\Z")


class InferenceError(Exception):
    """A stable user-facing error for malformed or unavailable training data."""


def _addition(left, right):
    return left + right


def _absolute_difference(left, right):
    return abs(left - right)


def _multiplication(left, right):
    return left * right


def _sum_of_squares(left, right):
    return left * left + right * right


_OPERATIONS = (
    ("addition", _addition),
    ("absolute_difference", _absolute_difference),
    ("multiplication", _multiplication),
    ("sum_of_squares", _sum_of_squares),
)
_OPERATION_INDEX = {
    name: index for index, (name, function) in enumerate(_OPERATIONS)
}


def _data_error(source, line_number, message):
    if line_number is None:
        location = source
    else:
        location = "{}:{}".format(source, line_number)
    raise InferenceError("{}: {}".format(location, message))


def decode_lsb_bits(bits):
    """Decode b0b1... as sum(bits[i] * 2**i)."""
    value = 0
    for index, bit in enumerate(bits):
        if bit == "1":
            value |= 1 << index
    return value


def parse_training_csv(text, source="<dataset>"):
    """Strictly parse one documented input,output training CSV."""
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader)
    except StopIteration:
        _data_error(source, 1, "missing header; expected exactly 'input,output'")
    except csv.Error as error:
        _data_error(source, 1, "invalid CSV: {}".format(error))

    if header != ["input", "output"]:
        _data_error(source, 1, "header must be exactly 'input,output'")

    rows = []
    operand_width = None
    output_width = None
    while True:
        try:
            row = next(reader)
        except StopIteration:
            break
        except csv.Error as error:
            _data_error(
                source,
                reader.line_num,
                "invalid CSV: {}".format(error),
            )

        line_number = reader.line_num
        if not row:
            _data_error(source, line_number, "blank rows are not allowed")
        if len(row) != 2:
            _data_error(
                source,
                line_number,
                "expected exactly two CSV fields",
            )

        input_bits, output_bits = row
        if _BINARY_PATTERN.match(input_bits) is None:
            _data_error(
                source,
                line_number,
                "input must be a nonempty binary string",
            )
        if _BINARY_PATTERN.match(output_bits) is None:
            _data_error(
                source,
                line_number,
                "output must be a nonempty binary string",
            )
        if len(input_bits) % 2 != 0:
            _data_error(
                source,
                line_number,
                "input must contain two equal-width operands",
            )

        row_operand_width = len(input_bits) // 2
        if operand_width is None:
            operand_width = row_operand_width
        elif row_operand_width != operand_width:
            _data_error(
                source,
                line_number,
                "input width {} does not match established input width {}".format(
                    len(input_bits), operand_width * 2
                ),
            )

        if output_width is None:
            output_width = len(output_bits)
        elif len(output_bits) != output_width:
            _data_error(
                source,
                line_number,
                "output width {} does not match established output width {}".format(
                    len(output_bits), output_width
                ),
            )

        left_bits = input_bits[:row_operand_width]
        right_bits = input_bits[row_operand_width:]
        rows.append(
            (
                decode_lsb_bits(left_bits),
                decode_lsb_bits(right_bits),
                decode_lsb_bits(output_bits),
            )
        )

    if not rows:
        _data_error(source, None, "dataset must contain at least one sample")

    return {
        "operand_width": operand_width,
        "output_width": output_width,
        "rows": rows,
    }


def _read_dataset(dataset_root, dataset_id):
    relative_path = os.path.join(
        "mystery-{}".format(dataset_id), "train.csv"
    )
    path = os.path.join(dataset_root, relative_path)
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError as error:
        raise InferenceError("{}: cannot read: {}".format(path, error))

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise InferenceError(
            "{}: cannot decode strict UTF-8: {}".format(path, error)
        )

    parsed = parse_training_csv(text, source=path)
    parsed.update(
        {
            "id": dataset_id,
            "relative_path": relative_path.replace(os.sep, "/"),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    )
    return parsed


def _candidate_ranking(rows):
    total = len(rows)
    candidates = []
    for operation_index, (operation_name, operation) in enumerate(_OPERATIONS):
        correct = sum(
            operation(left, right) == expected
            for left, right, expected in rows
        )
        candidates.append(
            {
                "_operation_index": operation_index,
                "accuracy": {
                    "denominator": total,
                    "numerator": correct,
                },
                "correct": correct,
                "operation": operation_name,
                "total": total,
            }
        )

    candidates.sort(
        key=lambda candidate: (
            -candidate["correct"],
            candidate["_operation_index"],
        )
    )
    for rank, candidate in enumerate(candidates, 1):
        del candidate["_operation_index"]
        candidate["rank"] = rank
    return candidates


def _fraction_record(value):
    return {
        "denominator": value.denominator,
        "numerator": value.numerator,
    }


def _assignment_ranking(score_lookup):
    assignments = []
    for signature in itertools.permutations(OPERATION_ORDER):
        mapping = dict(zip(DATASET_IDS, signature))
        per_dataset = [
            score_lookup[dataset_id][mapping[dataset_id]]
            for dataset_id in DATASET_IDS
        ]
        score = sum(
            (
                Fraction(candidate["correct"], candidate["total"])
                for candidate in per_dataset
            ),
            Fraction(0, 1),
        )
        pooled_correct = sum(candidate["correct"] for candidate in per_dataset)
        pooled_total = sum(candidate["total"] for candidate in per_dataset)
        assignments.append(
            {
                "_score": score,
                "_tie": tuple(
                    _OPERATION_INDEX[operation_name]
                    for operation_name in signature
                ),
                "correct": pooled_correct,
                "mapping": mapping,
                "mean_accuracy": _fraction_record(
                    score / len(DATASET_IDS)
                ),
                "pooled_accuracy": _fraction_record(
                    Fraction(pooled_correct, pooled_total)
                ),
                "score": _fraction_record(score),
                "total": pooled_total,
            }
        )

    assignments.sort(
        key=lambda assignment: (
            -assignment["_score"],
            assignment["_tie"],
        )
    )
    for rank, assignment in enumerate(assignments, 1):
        del assignment["_score"]
        del assignment["_tie"]
        assignment["rank"] = rank
    return assignments


def infer(dataset_root, argv=None):
    """Load only the four fixed training paths and return the stable report."""
    dataset_root = os.fspath(dataset_root)
    if argv is None:
        argv = [dataset_root]
    else:
        argv = list(argv)

    loaded_datasets = [
        _read_dataset(dataset_root, dataset_id)
        for dataset_id in DATASET_IDS
    ]

    dataset_reports = []
    score_lookup = {}
    for dataset in loaded_datasets:
        candidates = _candidate_ranking(dataset["rows"])
        score_lookup[dataset["id"]] = {
            candidate["operation"]: candidate for candidate in candidates
        }
        dataset_reports.append(
            {
                "candidates": candidates,
                "id": dataset["id"],
                "operand_width": dataset["operand_width"],
                "output_width": dataset["output_width"],
                "relative_path": dataset["relative_path"],
                "rows": len(dataset["rows"]),
                "sha256": dataset["sha256"],
            }
        )

    return {
        "argv": argv,
        "assignments": _assignment_ranking(score_lookup),
        "dataset_root": dataset_root,
        "datasets": dataset_reports,
        "provenance": {
            "algorithm": "exhaustive_arithmetic_assignment_v1",
            "deterministic": True,
            "randomness_used": False,
            "seed": None,
            "standard_library_only": True,
        },
        "ranking_rule": {
            "assignment_primary": (
                "descending sum of exact per-dataset accuracies"
            ),
            "candidate_primary": "descending exact accuracy",
            "dataset_order": list(DATASET_IDS),
            "operation_order": list(OPERATION_ORDER),
            "rank_style": "one-based ordinal; ties do not share ranks",
            "tie_break": (
                "operation-order indices assigned in dataset order"
            ),
        },
        "schema_version": 1,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Infer fixed arithmetic semantics from four public training CSVs."
        )
    )
    parser.add_argument("dataset_root")

    if argv is None:
        arguments_to_parse = sys.argv[1:]
        recorded_argv = list(sys.argv)
    else:
        arguments_to_parse = list(argv)
        recorded_argv = list(argv)
    arguments = parser.parse_args(arguments_to_parse)

    try:
        report = infer(arguments.dataset_root, argv=recorded_argv)
    except InferenceError as error:
        print("error: {}".format(error), file=sys.stderr)
        return 2

    serialized = json.dumps(
        report,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    sys.stdout.write(serialized + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
