#!/usr/bin/env python3
"""Run public Challenge #71 controls and record reproducible evidence."""

from __future__ import print_function

import argparse
import datetime
import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path


EXPECTED_ASSET_BYTES = 61068
EXPECTED_ASSET_SHA256 = (
    "c15f84839a365dd9daab686ccfd58a50ce286d5f1071d7f093e9fdd091ecaa1b"
)

SOLUTION_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SOLUTION_DIR.parents[3]
EVALUATOR = SOLUTION_DIR / "evaluator.py"
TESTS_DIR = SOLUTION_DIR / "tests"

RELEASE_MEMBERS = {
    "README.md": "occam-circuit/README.md",
    "verify.jl": "occam-circuit/verify.jl",
    "adder8.txt": "occam-circuit/adder8.txt",
    "datasets/practice-add-n4/train.csv": (
        "occam-circuit/datasets/practice-add-n4/train.csv"
    ),
    "datasets/practice-mul-n4/train.csv": (
        "occam-circuit/datasets/practice-mul-n4/train.csv"
    ),
    "datasets/mystery-A/train.csv": (
        "occam-circuit/datasets/mystery-A/train.csv"
    ),
}

PROTOCOL = {
    "name": "challenge-71-independent-python-evaluator-contract",
    "official_authority": (
        "The released verify.jl and README define official syntax and metrics; "
        "this Python evaluator independently accepts documented valid inputs "
        "and intentionally rejects undocumented Julia parser quirks."
    ),
    "syntax": {
        "declarations": [
            "INPUTS N",
            "wK = OP operand operand",
            "OUTPUTS operand ...",
        ],
        "operations": ["AND", "OR", "XOR", "NAND", "NOR", "XNOR"],
        "operand": "xK or previously defined wK, with at most one leading ~",
        "ordering": (
            "one INPUTS first, wires defined before use, one OUTPUTS last"
        ),
    },
    "metrics": {
        "exact_match_accuracy": (
            "samples whose complete predicted output equals truth / samples"
        ),
        "bit_accuracy": "correct output bits / total output bits",
        "official_free_inversion_gate_count": (
            "number of binary gate statements; ~ contributes zero"
        ),
    },
    "evaluator_seed": 0,
    "randomness": "none",
    "evidence_scope": (
        "public practice/training controls only; no withheld output is read"
    ),
}

CONTROL_DEFINITIONS = [
    {
        "name": "practice-add-n4-public-training",
        "classification": "public_practice_training_control",
        "function": "x + y (disclosed practice function)",
        "circuit": "practice-add-n4.txt",
        "dataset": "datasets/practice-add-n4/train.csv",
        "expected": {
            "samples": 120,
            "exact_matches": 120,
            "exact_match_accuracy": 1.0,
            "correct_bits": 600,
            "total_bits": 600,
            "bit_accuracy": 1.0,
            "gate_count": 17,
            "official_free_inversion_gate_count": 17,
        },
    },
    {
        "name": "practice-mul-n4-public-training",
        "classification": "public_practice_training_control",
        "function": "x * y (disclosed practice function)",
        "circuit": "practice-mul-n4.txt",
        "dataset": "datasets/practice-mul-n4/train.csv",
        "expected": {
            "samples": 120,
            "exact_matches": 120,
            "exact_match_accuracy": 1.0,
            "correct_bits": 960,
            "total_bits": 960,
            "bit_accuracy": 1.0,
            "gate_count": 128,
            "official_free_inversion_gate_count": 128,
        },
    },
    {
        "name": "official-adder8-mystery-A-public-training",
        "classification": "official_public_training_control",
        "function": "official adder8.txt quick-start control",
        "circuit": "adder8.txt",
        "dataset": "datasets/mystery-A/train.csv",
        "expected": {
            "samples": 2000,
            "exact_matches": 2000,
            "exact_match_accuracy": 1.0,
            "correct_bits": 18000,
            "total_bits": 18000,
            "bit_accuracy": 1.0,
            "gate_count": 37,
            "official_free_inversion_gate_count": 37,
        },
    },
]


class ControlRunError(Exception):
    """A user-facing control-run failure."""


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_release_asset(path):
    try:
        data = Path(path).read_bytes()
    except OSError as error:
        raise ControlRunError(
            "cannot read release asset {}: {}".format(path, error)
        )
    actual_size = len(data)
    actual_hash = _sha256_bytes(data)
    if (
        actual_size != EXPECTED_ASSET_BYTES
        or actual_hash != EXPECTED_ASSET_SHA256
    ):
        raise ControlRunError(
            "release asset verification failed: expected {} bytes and "
            "sha256 {}, got {} bytes and sha256 {}".format(
                EXPECTED_ASSET_BYTES,
                EXPECTED_ASSET_SHA256,
                actual_size,
                actual_hash,
            )
        )
    return data


def _utc_now():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _canonical_json_hash(value):
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def _absolute_path(path):
    return Path(os.path.abspath(str(path)))


def _new_run_directory(results_root):
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    base_name = "{}-lifeisshort-python-evaluator-controls".format(timestamp)
    root = _absolute_path(results_root)
    root.mkdir(parents=True, exist_ok=True)
    candidate = root / base_name
    suffix = 1
    while candidate.exists():
        candidate = root / "{}-{:02d}".format(base_name, suffix)
        suffix += 1
    candidate.mkdir()
    return candidate


def _release_files(asset_data, run_directory):
    written = {}
    try:
        archive = zipfile.ZipFile(io.BytesIO(asset_data), "r")
    except zipfile.BadZipFile as error:
        raise ControlRunError(
            "verified release bytes are not a readable ZIP: {}".format(error)
        )
    with archive:
        archive_names = archive.namelist()
        for local_name, member_name in sorted(RELEASE_MEMBERS.items()):
            if archive_names.count(member_name) != 1:
                raise ControlRunError(
                    "release ZIP must contain exactly one {!r}".format(
                        member_name
                    )
                )
            data = archive.read(member_name)
            destination = run_directory / "official" / local_name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            written[local_name] = {
                "archive_member": member_name,
                "path": str(destination),
                "bytes": len(data),
                "sha256": _sha256_bytes(data),
            }
    return written


def _copy_control_circuits(run_directory):
    written = {}
    destination_root = run_directory / "controls"
    destination_root.mkdir()
    for filename in ("practice-add-n4.txt", "practice-mul-n4.txt"):
        source = SOLUTION_DIR / "controls" / filename
        destination = destination_root / filename
        try:
            data = source.read_bytes()
        except OSError as error:
            raise ControlRunError(
                "cannot read control circuit {}: {}".format(source, error)
            )
        destination.write_bytes(data)
        written[filename] = {
            "source": str(source),
            "path": str(destination),
            "bytes": len(data),
            "sha256": _sha256_bytes(data),
        }
    return written


def _run_command(command, cwd):
    started = time.perf_counter()
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    stdout, stderr = process.communicate()
    elapsed = time.perf_counter() - started
    return {
        "command": list(command),
        "cwd": str(cwd),
        "exit_code": process.returncode,
        "wall_time_seconds": elapsed,
        "wall_time_nanoseconds": int(round(elapsed * 1000000000)),
        "stdout": stdout,
        "stderr": stderr,
    }


def _require_success(execution, label):
    if execution["exit_code"] != 0:
        raise ControlRunError(
            "{} failed with exit code {}: {}".format(
                label,
                execution["exit_code"],
                execution["stderr"].strip()
                or execution["stdout"].strip()
                or "no output",
            )
        )


def _run_focused_tests():
    command = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        str(TESTS_DIR),
        "-p",
        "test_*.py",
        "-v",
    ]
    execution = _run_command(command, REPOSITORY_ROOT)
    _require_success(execution, "focused unittest suite")
    return execution


def _control_paths(definition, run_directory):
    if definition["circuit"] == "adder8.txt":
        circuit = run_directory / "official" / "adder8.txt"
    else:
        circuit = run_directory / "controls" / definition["circuit"]
    dataset = (
        run_directory / "official" / definition["dataset"]
    )
    return circuit, dataset


def _run_python_control(definition, run_directory):
    circuit, dataset = _control_paths(definition, run_directory)
    command = [
        sys.executable,
        str(EVALUATOR),
        "--json",
        str(circuit),
        str(dataset),
    ]
    execution = _run_command(command, REPOSITORY_ROOT)
    _require_success(execution, definition["name"])
    try:
        payload = json.loads(execution["stdout"])
    except (TypeError, ValueError) as error:
        raise ControlRunError(
            "{} returned invalid JSON: {}".format(definition["name"], error)
        )

    expected = definition["expected"]
    mismatches = []
    for key, expected_value in sorted(expected.items()):
        actual_value = payload.get(key)
        if actual_value != expected_value:
            mismatches.append(
                "{} expected {!r}, got {!r}".format(
                    key, expected_value, actual_value
                )
            )
    if mismatches:
        raise ControlRunError(
            "{} metric mismatch: {}".format(
                definition["name"], "; ".join(mismatches)
            )
        )
    peak_memory = payload.get("peak_memory_bytes")
    if not isinstance(peak_memory, int) or peak_memory <= 0:
        raise ControlRunError(
            "{} did not report positive peak_memory_bytes".format(
                definition["name"]
            )
        )

    return {
        "name": definition["name"],
        "classification": definition["classification"],
        "function": definition["function"],
        "seed": 0,
        "randomness": "none",
        "command": execution["command"],
        "cwd": execution["cwd"],
        "exit_code": execution["exit_code"],
        "wall_time_seconds": execution["wall_time_seconds"],
        "wall_time_nanoseconds": execution["wall_time_nanoseconds"],
        "peak_memory_bytes": peak_memory,
        "peak_memory_measurement": payload["peak_memory_measurement"],
        "input_hashes": {
            "circuit_sha256": _sha256_file(circuit),
            "dataset_sha256": _sha256_file(dataset),
        },
        "metrics": {
            key: payload[key] for key in sorted(expected)
        },
        "expected_metrics": expected,
        "matched_expected_metrics": True,
        "stderr": execution["stderr"],
    }


def _parse_julia_metrics(stdout):
    patterns = {
        "gate_count": r"^gates:\s+([0-9]+)",
        "samples": r"^samples:\s+([0-9]+)",
        "exact_match_accuracy": r"^exact-match acc:\s+([0-9.]+)",
        "bit_accuracy": r"^bit accuracy:\s+([0-9.]+)",
    }
    metrics = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, stdout, flags=re.MULTILINE)
        if match is None:
            raise ControlRunError(
                "official Julia output is missing {}".format(key)
            )
        if key in ("gate_count", "samples"):
            metrics[key] = int(match.group(1))
        else:
            metrics[key] = float(match.group(1))
    metrics["official_free_inversion_gate_count"] = metrics["gate_count"]
    return metrics


def _official_julia_control(run_directory):
    verify_path = run_directory / "official" / "verify.jl"
    circuit_path = run_directory / "official" / "adder8.txt"
    dataset_path = (
        run_directory / "official" / "datasets/mystery-A/train.csv"
    )
    documented_command = [
        "julia",
        "verify.jl",
        "adder8.txt",
        "datasets/mystery-A/train.csv",
    ]
    documented_metrics = {
        "gate_count": 37,
        "official_free_inversion_gate_count": 37,
        "samples": 2000,
        "exact_match_accuracy": 1.0,
        "bit_accuracy": 1.0,
    }
    julia = shutil.which("julia")
    if julia is None:
        return {
            "authoritative": True,
            "status": "not_run_julia_executable_unavailable",
            "executable": None,
            "documented_command": documented_command,
            "documented_metrics": documented_metrics,
            "source_sha256": _sha256_file(verify_path),
            "note": (
                "No Julia executable was available. The released verify.jl "
                "and its documented adder8 quick-start result remain "
                "authoritative; no replacement claim is made."
            ),
        }

    command = [
        julia,
        str(verify_path),
        str(circuit_path),
        str(dataset_path),
    ]
    execution = _run_command(command, REPOSITORY_ROOT)
    _require_success(execution, "official Julia adder8 control")
    metrics = _parse_julia_metrics(execution["stdout"])
    mismatches = [
        "{} expected {!r}, got {!r}".format(
            key, value, metrics.get(key)
        )
        for key, value in sorted(documented_metrics.items())
        if metrics.get(key) != value
    ]
    if mismatches:
        raise ControlRunError(
            "official Julia adder8 result differs from its documentation: "
            + "; ".join(mismatches)
        )
    return {
        "authoritative": True,
        "status": "executed_and_matched_documented_control",
        "executable": julia,
        "documented_command": documented_command,
        "executed_command": execution["command"],
        "cwd": execution["cwd"],
        "exit_code": execution["exit_code"],
        "wall_time_seconds": execution["wall_time_seconds"],
        "wall_time_nanoseconds": execution["wall_time_nanoseconds"],
        "metrics": metrics,
        "documented_metrics": documented_metrics,
        "source_sha256": _sha256_file(verify_path),
        "stderr": execution["stderr"],
    }


def _source_hashes():
    paths = [
        EVALUATOR,
        Path(__file__).resolve(),
        SOLUTION_DIR / "README.md",
        SOLUTION_DIR / "tests" / "test_evaluator.py",
        SOLUTION_DIR / "controls" / "practice-add-n4.txt",
        SOLUTION_DIR / "controls" / "practice-mul-n4.txt",
    ]
    hashes = {}
    for path in paths:
        if path.exists():
            try:
                name = str(path.relative_to(REPOSITORY_ROOT))
            except ValueError:
                name = str(path)
            hashes[name] = _sha256_file(path)
    return hashes


def _write_manifest(path, manifest):
    temporary_path = path.with_name(path.name + ".tmp")
    with temporary_path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
        stream.write("\n")
    os.replace(str(temporary_path), str(path))


def build_invocation(script_token, arguments):
    return [sys.executable, script_token] + list(arguments)


def run_controls(asset_path, results_root, invocation):
    started_at = _utc_now()
    asset_data = validate_release_asset(asset_path)
    print(
        "[1/5] verified release asset: {} bytes, sha256 {}".format(
            len(asset_data), _sha256_bytes(asset_data)
        ),
        flush=True,
    )
    run_directory = _new_run_directory(results_root)
    release_files = _release_files(asset_data, run_directory)
    control_files = _copy_control_circuits(run_directory)
    print(
        "[2/5] staged only public control files in {}".format(run_directory),
        flush=True,
    )

    test_execution = _run_focused_tests()
    print("[3/5] focused unittest suite passed", flush=True)

    controls = []
    for definition in CONTROL_DEFINITIONS:
        result = _run_python_control(definition, run_directory)
        controls.append(result)
        print(
            "[4/5] {}: exact={}, bit={}, gates={}".format(
                result["name"],
                result["metrics"]["exact_match_accuracy"],
                result["metrics"]["bit_accuracy"],
                result["metrics"]["official_free_inversion_gate_count"],
            ),
            flush=True,
        )

    julia_control = _official_julia_control(run_directory)
    python_adder = [
        control
        for control in controls
        if control["name"]
        == "official-adder8-mystery-A-public-training"
    ][0]
    manifest = {
        "schema": "challenge71-public-control-run/v1",
        "status": "complete",
        "run_id": run_directory.name,
        "challenge": 71,
        "team": "lifeIsShort",
        "purpose": "independent Python evaluator public controls",
        "classification": (
            "public practice/training evidence; not hidden-test results"
        ),
        "started_at_utc": started_at,
        "completed_at_utc": _utc_now(),
        "invocation": {
            "command": invocation,
            "resolved_script_path": str(Path(__file__).resolve()),
            "cwd": str(Path.cwd()),
        },
        "environment": {
            "python_executable": sys.executable,
            "python_version": platform.python_version(),
            "python_full_version": sys.version,
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "seed": 0,
            "rng": None,
            "randomness": "none",
        },
        "protocol": PROTOCOL,
        "protocol_sha256": _canonical_json_hash(PROTOCOL),
        "official_release": {
            "asset_path": str(_absolute_path(asset_path)),
            "asset_bytes": len(asset_data),
            "asset_sha256": _sha256_bytes(asset_data),
            "selected_public_members": release_files,
            "official_julia_control": julia_control,
        },
        "source_hashes": _source_hashes(),
        "control_circuit_copies": control_files,
        "focused_tests": test_execution,
        "controls": controls,
        "verification": {
            "focused_tests_passed": True,
            "all_expected_metrics_matched": all(
                control["matched_expected_metrics"] for control in controls
            ),
            "python_adder8_matches_documented_official_result": (
                python_adder["metrics"]["exact_match_accuracy"] == 1.0
                and python_adder["metrics"]["bit_accuracy"] == 1.0
                and python_adder["metrics"][
                    "official_free_inversion_gate_count"
                ]
                == 37
            ),
            "official_julia_authoritative": True,
            "hidden_test_outputs_read": False,
            "mystery_test_inputs_read": False,
            "practice_or_training_called_hidden_test_results": False,
        },
    }
    manifest_path = run_directory / "run.json"
    _write_manifest(manifest_path, manifest)
    print("[5/5] wrote {}".format(manifest_path), flush=True)
    return manifest_path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run deterministic public Occam's Circuit controls."
    )
    parser.add_argument("--asset", required=True)
    parser.add_argument("--results-root", required=True)
    arguments = parser.parse_args(argv)
    invocation_arguments = list(sys.argv[1:] if argv is None else argv)
    script_token = (
        sys.argv[0] if argv is None else str(Path(__file__).resolve())
    )
    invocation = build_invocation(script_token, invocation_arguments)
    try:
        run_controls(
            arguments.asset,
            arguments.results_root,
            invocation,
        )
    except ControlRunError as error:
        print("error: {}".format(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
