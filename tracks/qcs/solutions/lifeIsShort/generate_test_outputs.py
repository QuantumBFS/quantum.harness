#!/usr/bin/env python3
"""Generate Challenge #71 predictions from the verified public test inputs."""

from __future__ import print_function

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
import zipfile
from collections import namedtuple
from pathlib import Path

import evaluator


EXPECTED_ASSET_BYTES = 61068
EXPECTED_ASSET_SHA256 = (
    "c15f84839a365dd9daab686ccfd58a50ce286d5f1071d7f093e9fdd091ecaa1b"
)

SOLUTION_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SOLUTION_DIR / "predictions"
OUTPUT_FILE_MODE = 0o644

DatasetSpec = namedtuple(
    "DatasetSpec",
    (
        "dataset_id operation operand_width output_width expected_rows "
        "input_member candidate_filename published_commitment_sha256"
    ),
)

DATASET_SPECS = (
    DatasetSpec(
        "A",
        "addition",
        8,
        9,
        2000,
        "occam-circuit/datasets/mystery-A/test_inputs.csv",
        "mystery-A.txt",
        "51e3f026def41778ecd0d7dcaee9f970b9937488e6716891932b73824c16d4c7",
    ),
    DatasetSpec(
        "B",
        "absolute_difference",
        7,
        7,
        2000,
        "occam-circuit/datasets/mystery-B/test_inputs.csv",
        "mystery-B.txt",
        "e2c9d0e23ee36bfc0f12d7f39fdfe2ca5a8abe8eb194fec56500733694b75c28",
    ),
    DatasetSpec(
        "C",
        "multiplication",
        6,
        12,
        1500,
        "occam-circuit/datasets/mystery-C/test_inputs.csv",
        "mystery-C.txt",
        "c7b37413844bf0b10ebad0010046469f500354a22cc2ba95cbe42709f8e8337d",
    ),
    DatasetSpec(
        "D",
        "sum_of_squares",
        5,
        11,
        624,
        "occam-circuit/datasets/mystery-D/test_inputs.csv",
        "mystery-D.txt",
        "b445a717483303fa3c5d8a1f7abe81888b267b7c472121c9c464fa9766808580",
    ),
)


class PredictionGenerationError(Exception):
    """A stable user-facing failure that must not produce partial JSON."""


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def decode_lsb_bits(bits):
    value = 0
    for index, bit in enumerate(bits):
        if bit == "1":
            value |= 1 << index
    return value


def encode_lsb_bits(value, width):
    if value < 0 or value >= (1 << width):
        raise PredictionGenerationError(
            "value {} does not fit fixed output width {}".format(
                value, width
            )
        )
    return "".join(
        "1" if (value >> index) & 1 else "0"
        for index in range(width)
    )


def _operation_value(name, left, right):
    if name == "addition":
        return left + right
    if name == "absolute_difference":
        return abs(left - right)
    if name == "multiplication":
        return left * right
    if name == "sum_of_squares":
        return left * left + right * right
    raise PredictionGenerationError(
        "unsupported fixed operation {!r}".format(name)
    )


def _parse_public_inputs(raw, spec):
    source = spec.input_member
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise PredictionGenerationError(
            "{}: input CSV is not ASCII: {}".format(source, error)
        )

    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader)
    except (StopIteration, csv.Error) as error:
        raise PredictionGenerationError(
            "{}: cannot read input header: {}".format(source, error)
        )
    if header != ["input"]:
        raise PredictionGenerationError(
            "{}: header must be exactly 'input'".format(source)
        )

    inputs = []
    try:
        for row in reader:
            line_number = reader.line_num
            if not row:
                raise PredictionGenerationError(
                    "{}:{}: blank rows are not allowed".format(
                        source, line_number
                    )
                )
            if len(row) != 1:
                raise PredictionGenerationError(
                    "{}:{}: expected exactly one CSV field".format(
                        source, line_number
                    )
                )
            input_bits = row[0]
            if not input_bits or set(input_bits) - {"0", "1"}:
                raise PredictionGenerationError(
                    "{}:{}: input must be a nonempty binary string".format(
                        source, line_number
                    )
                )
            expected_width = 2 * spec.operand_width
            if len(input_bits) != expected_width:
                raise PredictionGenerationError(
                    "{}:{}: input width {} does not match expected {}".format(
                        source,
                        line_number,
                        len(input_bits),
                        expected_width,
                    )
                )
            inputs.append(input_bits)
    except csv.Error as error:
        raise PredictionGenerationError(
            "{}:{}: invalid CSV: {}".format(
                source, reader.line_num, error
            )
        )
    if not inputs:
        raise PredictionGenerationError(
            "{}: dataset must contain at least one input".format(source)
        )
    if len(inputs) != spec.expected_rows:
        raise PredictionGenerationError(
            "{}: row count {} does not match expected {}".format(
                source, len(inputs), spec.expected_rows
            )
        )
    return inputs


def _predict_rows(spec, input_bits_rows):
    rows = []
    for input_bits in input_bits_rows:
        left_bits = input_bits[: spec.operand_width]
        right_bits = input_bits[spec.operand_width :]
        left = decode_lsb_bits(left_bits)
        right = decode_lsb_bits(right_bits)
        value = _operation_value(spec.operation, left, right)
        rows.append(
            (
                input_bits,
                encode_lsb_bits(value, spec.output_width),
            )
        )
    return rows


def _render_output(rows):
    lines = ["input,output"]
    lines.extend(
        "{},{}".format(input_bits, output_bits)
        for input_bits, output_bits in rows
    )
    return ("\n".join(lines) + "\n").encode("ascii")


def _candidate_record(spec, rows):
    candidate_path = SOLUTION_DIR / spec.candidate_filename
    try:
        candidate_bytes = candidate_path.read_bytes()
        candidate_text = candidate_bytes.decode("utf-8")
    except (OSError, UnicodeError) as error:
        raise PredictionGenerationError(
            "{}: cannot read candidate circuit: {}".format(
                candidate_path, error
            )
        )
    try:
        circuit = evaluator.parse_netlist(
            candidate_text, source=str(candidate_path)
        )
    except evaluator.EvaluationError as error:
        raise PredictionGenerationError(str(error))

    expected_inputs = 2 * spec.operand_width
    if circuit.input_count != expected_inputs:
        raise PredictionGenerationError(
            "{}: candidate declares {} inputs, expected {}".format(
                candidate_path, circuit.input_count, expected_inputs
            )
        )
    if len(circuit.outputs) != spec.output_width:
        raise PredictionGenerationError(
            "{}: candidate declares {} outputs, expected {}".format(
                candidate_path, len(circuit.outputs), spec.output_width
            )
        )

    metrics = evaluator.evaluate(circuit, rows)
    all_rows_match = (
        metrics["exact_matches"] == len(rows)
        and metrics["correct_bits"] == len(rows) * spec.output_width
    )
    if not all_rows_match:
        raise PredictionGenerationError(
            "{}: candidate circuit disagrees with fixed {} semantics "
            "on the public inputs".format(candidate_path, spec.operation)
        )
    return {
        "all_public_input_rows_match": True,
        "gate_count": len(circuit.gates),
        "relative_path": spec.candidate_filename,
        "sha256": _sha256(candidate_bytes),
    }


def _prediction_record(spec, input_raw, rows, output_bytes):
    output_hash = _sha256(output_bytes)
    return {
        "candidate_circuit": _candidate_record(spec, rows),
        "dataset": "mystery-{}".format(spec.dataset_id),
        "encoding": "LSB-first fixed width",
        "input": {
            "archive_member": spec.input_member,
            "rows": len(rows),
            "sha256": _sha256(input_raw),
            "width": 2 * spec.operand_width,
        },
        "operation": spec.operation,
        "output": {
            "bytes": len(output_bytes),
            "format": "input,output CSV; ASCII; LF; trailing LF",
            "repository_relative_path": (
                "predictions/mystery-{}/test_outputs.csv".format(
                    spec.dataset_id
                )
            ),
            "rows": len(rows),
            "sha256": output_hash,
            "width": spec.output_width,
        },
        "published_commitment": {
            "algorithm": "sha256",
            "sha256": spec.published_commitment_sha256,
            "whole_file_identity_match": (
                output_hash == spec.published_commitment_sha256
            ),
        },
    }


def _validated_asset_bytes(asset_path):
    path = Path(asset_path)
    try:
        data = path.read_bytes()
    except OSError as error:
        raise PredictionGenerationError(
            "{}: cannot read official ZIP: {}".format(path, error)
        )
    actual_hash = _sha256(data)
    if (
        len(data) != EXPECTED_ASSET_BYTES
        or actual_hash != EXPECTED_ASSET_SHA256
    ):
        raise PredictionGenerationError(
            "official ZIP verification failed: expected {} bytes and "
            "sha256 {}, got {} bytes and sha256 {}".format(
                EXPECTED_ASSET_BYTES,
                EXPECTED_ASSET_SHA256,
                len(data),
                actual_hash,
            )
        )
    return data


def _atomic_write(destination, data):
    destination = Path(destination)
    temporary_path = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".{}.".format(destination.name),
            suffix=".tmp",
            dir=str(destination.parent),
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(str(temporary_path), OUTPUT_FILE_MODE)
        os.replace(str(temporary_path), str(destination))
        temporary_path = None
    except OSError as error:
        raise PredictionGenerationError(
            "{}: atomic write failed: {}".format(destination, error)
        )
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


def generate_outputs(asset_path, output_directory=DEFAULT_OUTPUT_DIR):
    asset_data = _validated_asset_bytes(asset_path)
    prepared = []
    records = []
    try:
        archive = zipfile.ZipFile(io.BytesIO(asset_data), "r")
    except zipfile.BadZipFile as error:
        raise PredictionGenerationError(
            "verified release asset is not a readable ZIP: {}".format(error)
        )

    with archive:
        for spec in DATASET_SPECS:
            try:
                input_raw = archive.read(spec.input_member)
            except (KeyError, RuntimeError, zipfile.BadZipFile) as error:
                raise PredictionGenerationError(
                    "{}: cannot read literal public input member: {}".format(
                        spec.input_member, error
                    )
                )
            inputs = _parse_public_inputs(input_raw, spec)
            rows = _predict_rows(spec, inputs)
            output_bytes = _render_output(rows)
            records.append(
                _prediction_record(spec, input_raw, rows, output_bytes)
            )
            prepared.append((spec, output_bytes))

    output_root = Path(output_directory)
    for spec, output_bytes in prepared:
        destination = (
            output_root
            / "mystery-{}".format(spec.dataset_id)
            / "test_outputs.csv"
        )
        _atomic_write(destination, output_bytes)

    return {
        "classification": (
            "public-input predictions and candidate-circuit "
            "self-consistency; not hidden-test accuracy"
        ),
        "determinism": {"randomness": "none", "seed": None},
        "official_release": {
            "bytes": len(asset_data),
            "sha256": _sha256(asset_data),
        },
        "predictions": records,
        "safety": {
            "archive_member_listing_requested": False,
            "member_payload_scope": (
                "four literal public test_inputs.csv paths"
            ),
            "non_input_member_payloads_read": False,
        },
        "schema": "challenge71-public-test-predictions/v1",
    }


def _canonical_json(value):
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--asset",
        required=True,
        help="path to the exact official occam-circuit.zip release",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="directory receiving mystery-*/test_outputs.csv",
    )
    arguments = parser.parse_args(argv)
    try:
        report = generate_outputs(
            arguments.asset, arguments.output_dir
        )
    except PredictionGenerationError as error:
        print("{}: error: {}".format(Path(__file__).name, error), file=sys.stderr)
        return 2
    sys.stdout.write(_canonical_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
