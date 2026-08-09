#!/usr/bin/env python3
"""Fail-closed, standard-library gate for the WangTheoPhys public capsule."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import NoReturn

EXPERIMENT_SCHEMA = "wangtheophys.tn-experiment.v1"
EVIDENCE_SCHEMA = "wangtheophys.tn-evidence.v1"
HEURISTIC_SCHEMA = "wangtheophys.tn-heuristic.v1"
BACKEND_RESULT_SCHEMA = "tn-agent.backend-result.v1"
MAX_DOCUMENT_BYTES = 4 * 1024 * 1024
MAX_ARTIFACT_BYTES = 1024 * 1024
MAX_ARTIFACT_TOTAL_BYTES = 8 * 1024 * 1024
MAX_ARTIFACTS = 64
MAX_LIBRARY_RECORDS = 10_000
READ_CHUNK_BYTES = 64 * 1024
TEAM_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = TEAM_ROOT.parents[3]
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}$")
TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)
SKILL_URI_PATTERN = re.compile(r"^skills/[a-z0-9][a-z0-9-]{0,63}/SKILL[.]md$")
AUDIT_URI_PATTERN = re.compile(r"^(?:docs|tests)/(?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]+$")
GATE_REASON_CODES = frozenset(
    {
        "ACCEPTANCE_CONTRACT_INVALID",
        "ARTIFACT_DIGEST_MISMATCH",
        "ARTIFACT_IO_ERROR",
        "ARTIFACT_LIMIT_EXCEEDED",
        "ARTIFACT_TOO_LARGE",
        "ARTIFACT_UNSAFE_PATH",
        "BINDING_MISMATCH",
        "CLI_USAGE_ERROR",
        "DOCUMENT_DUPLICATE_KEY",
        "DOCUMENT_INVALID_JSON",
        "DOCUMENT_INVALID_UTF8",
        "DOCUMENT_IO_ERROR",
        "DOCUMENT_NONFINITE",
        "DOCUMENT_NOT_CANONICAL",
        "DOCUMENT_TOO_LARGE",
        "DOCUMENT_UNSAFE_PATH",
        "EVIDENCE_ARTIFACT_MISSING",
        "EXECUTION_NOT_SUCCEEDED",
        "EXPERIMENT_DIGEST_MISMATCH",
        "INTERNAL_ERROR",
        "LIBRARY_RECORD_INVALID",
        "LIBRARY_RECORD_LIMIT",
        "LIBRARY_SEQUENCE_INVALID",
        "MISSING_FIELD",
        "OBSERVABLE_SET_MISMATCH",
        "OBSERVABLE_STATUS_INVALID",
        "PROVENANCE_MISMATCH",
        "RESULT_DIGEST_MISMATCH",
        "SCIENTIFIC_EVIDENCE_UNATTESTED",
        "SCHEMA_VERSION_UNSUPPORTED",
        "SECURE_FILE_IO_UNAVAILABLE",
        "TYPE_MISMATCH",
        "UNKNOWN_FIELD",
        "UNSUPPORTED_ROUTE",
        "VALIDATOR_FAILED",
        "VALIDATOR_POLICY_MISMATCH",
        "VALIDATOR_SET_MISMATCH",
        "VALIDATOR_STATUS_INVALID",
        "VALIDATOR_THRESHOLD_FAILED",
        "VALUE_INVALID",
    }
)

VALIDATOR_IDS = frozenset(
    {
        "parse_consistency",
        "convergence",
        "variance",
        "canonical_form",
        "symmetry_check",
        "benchmark_compare",
        "reproducibility",
        "artifact_completeness",
    }
)
REPORTED_ONLY_VALIDATOR_IDS = frozenset(
    {
        "variance",
        "canonical_form",
        "symmetry_check",
        "reproducibility",
    }
)

VALIDATOR_RULES: dict[str, tuple[str | None, str | None, str]] = {
    "parse_consistency": (None, None, "none"),
    "convergence": ("energy_drift", "max", "nonnegative_number"),
    "variance": ("variance", "max", "nonnegative_number"),
    "canonical_form": ("canonical_residual", "max", "nonnegative_number"),
    "symmetry_check": ("symmetry_residual", "max", "nonnegative_number"),
    "benchmark_compare": ("benchmark_delta", "max", "nonnegative_number"),
    "reproducibility": ("reproduction_delta", "max", "nonnegative_number"),
    "artifact_completeness": (
        "missing_artifacts",
        "equals",
        "nonnegative_integer",
    ),
}

ROUTES: dict[str, dict[str, object]] = {
    "tenpy.finite_1d.dmrg": {
        "maturity": "stable",
        "known_limitations": [
            "Only the finite spin-1/2 TFIM open-chain route is promoted.",
            "The fixture does not count as a generated challenge problem.",
        ],
        "task_family": "ground_state_1d_finite",
        "binding": {
            "schema_version": "tn-agent.backend-binding.v1",
            "capability_id": "tenpy.finite_1d.dmrg",
            "adapter_id": "tenpy.v1",
            "backend_id": "tenpy",
            "request_schema": "tn-agent.tenpy.finite-tfim-dmrg.v1",
            "result_schema": "tn-agent.backend-result.v1",
        },
        "model_family": "tfim",
        "operators": frozenset(
            {
                "sigma_x_i*sigma_x_i+1",
                "sigma_z_i",
            }
        ),
        "couplings": frozenset({"J", "g"}),
        "boundary": "open",
        "length": "positive",
        "unit_cell": 1,
        "symmetry": {
            "U1_Sz": False,
            "parity": False,
            "translation": False,
            "target_sector": None,
        },
        "algorithm": "dmrg",
        "variant": "two_site",
        "initial_state": "all_z_plus",
        "observables": frozenset(
            {
                "energy",
                "variance",
                "magnetization_z",
                "entanglement_entropy",
                "correlator_sigma_x",
                "correlator_sz",
            }
        ),
        "backend_limited_observables": frozenset(),
        "observable_statuses": {
            "energy": "measured",
            "variance": "measured",
            "magnetization_z": "measured",
            "entanglement_entropy": "measured",
            "correlator_sigma_x": "measured",
            "correlator_sz": "measured",
        },
        "backend_limited_validators": frozenset(),
    },
    "tenpy.infinite_1d.vumps": {
        "maturity": "experimental",
        "known_limitations": [
            "TeNPy UniformMPS is experimental.",
            "Energy variance is backend-limited on this route.",
            "The fixture does not count as a generated challenge problem.",
        ],
        "task_family": "ground_state_1d_infinite",
        "binding": {
            "schema_version": "tn-agent.backend-binding.v1",
            "capability_id": "tenpy.infinite_1d.vumps",
            "adapter_id": "tenpy.v1",
            "backend_id": "tenpy",
            "request_schema": "tn-agent.tenpy.infinite-xxz-vumps.v1",
            "result_schema": "tn-agent.backend-result.v1",
        },
        "model_family": "xxz",
        "operators": frozenset(
            {
                "Sx_i*Sx_i+1",
                "Sy_i*Sy_i+1",
                "Sz_i*Sz_i+1",
                "Sz_i",
            }
        ),
        "couplings": frozenset({"Jxy", "Delta", "h"}),
        "boundary": "infinite",
        "length": None,
        "unit_cell": 2,
        "symmetry": {
            "U1_Sz": True,
            "parity": False,
            "translation": True,
            "target_sector": {"total_Sz": 0},
        },
        "algorithm": "vumps",
        "variant": "two_site",
        "initial_state": "neel",
        "observables": frozenset(
            {
                "energy",
                "variance",
                "magnetization_z",
                "entanglement_entropy",
                "transfer_spectrum",
                "central_charge_fit",
            }
        ),
        "backend_limited_observables": frozenset({"variance"}),
        "observable_statuses": {
            "energy": "measured",
            "variance": "backend_limited",
            "magnetization_z": "measured",
            "entanglement_entropy": "measured",
            "transfer_spectrum": "measured",
            "central_charge_fit": "derived",
        },
        "backend_limited_validators": frozenset({"variance"}),
    },
}


class GateError(Exception):
    """A sanitized, stable rejection at a public contract boundary."""

    def __init__(
        self,
        reason_code: str,
        message: str,
        *,
        field: str | None = None,
        exit_code: int = 2,
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.field = field
        self.exit_code = exit_code

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "ok": False,
            "reason_code": self.reason_code,
            "message": self.message,
        }
        if self.exit_code == 3:
            payload["accepted"] = False
        if self.field is not None:
            payload["field"] = self.field
        return payload


def _fail(
    reason_code: str,
    message: str,
    *,
    field: str | None = None,
    exit_code: int = 2,
) -> NoReturn:
    if reason_code not in GATE_REASON_CODES:
        raise RuntimeError("Unregistered public reason code")
    raise GateError(
        reason_code,
        message,
        field=field,
        exit_code=exit_code,
    )


def canonical_digest(value: object) -> str:
    """Return the stable SHA-256 of canonical UTF-8 JSON."""

    try:
        serialized = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, UnicodeError, ValueError):
        _fail("DOCUMENT_NOT_CANONICAL", "Document is not canonical JSON")
    return "sha256:" + hashlib.sha256(serialized).hexdigest()


def load_json_document(path: Path) -> object:
    """Read one bounded regular file and parse strict JSON."""

    raw = _read_regular_file(path, MAX_DOCUMENT_BYTES, artifact=False)
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        _fail("DOCUMENT_INVALID_UTF8", "Document is not valid UTF-8")
    return _strict_json_loads(text)


def _strict_json_loads(text: str) -> object:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                _fail(
                    "DOCUMENT_DUPLICATE_KEY",
                    "Document contains a duplicate object key",
                )
            result[key] = value
        return result

    def reject_nonfinite(_value: str) -> NoReturn:
        _fail("DOCUMENT_NONFINITE", "Document contains a non-finite number")

    def parse_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            _fail("DOCUMENT_NONFINITE", "Document contains a non-finite number")
        return parsed

    try:
        return json.loads(
            text,
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_nonfinite,
            parse_float=parse_float,
        )
    except GateError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError):
        _fail("DOCUMENT_INVALID_JSON", "Document is not valid JSON")


def _read_regular_file(path: Path, limit: int, *, artifact: bool) -> bytes:
    prefix = "ARTIFACT" if artifact else "DOCUMENT"
    try:
        before = path.lstat()
    except (OSError, ValueError, UnicodeError):
        _fail(f"{prefix}_IO_ERROR", f"{prefix.title()} cannot be read")
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        _fail(
            f"{prefix}_UNSAFE_PATH",
            f"{prefix.title()} must be a regular non-symlink file",
        )
    if before.st_size > limit:
        _fail(f"{prefix}_TOO_LARGE", f"{prefix.title()} exceeds the byte limit")
    if not hasattr(os, "O_NOFOLLOW"):
        _fail(
            "SECURE_FILE_IO_UNAVAILABLE",
            "Secure no-follow reads are unavailable on this platform",
        )
    flags = (
        os.O_RDONLY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except (OSError, ValueError, UnicodeError):
        _fail(f"{prefix}_IO_ERROR", f"{prefix.title()} cannot be opened safely")
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_size > limit:
            _fail(
                f"{prefix}_UNSAFE_PATH",
                f"{prefix.title()} changed before it was opened",
            )
        if not _same_file(before, opened):
            _fail(
                f"{prefix}_UNSAFE_PATH",
                f"{prefix.title()} changed before it was opened",
            )
        chunks: list[bytes] = []
        remaining = limit + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, READ_CHUNK_BYTES))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        final = os.fstat(descriptor)
    except OSError:
        _fail(f"{prefix}_IO_ERROR", f"{prefix.title()} cannot be read safely")
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    if len(raw) > limit:
        _fail(f"{prefix}_TOO_LARGE", f"{prefix.title()} exceeds the byte limit")
    if not _stable_file(opened, final):
        _fail(
            f"{prefix}_UNSAFE_PATH",
            f"{prefix.title()} changed while it was read",
        )
    return raw


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        stat.S_IFMT(left.st_mode) == stat.S_IFMT(right.st_mode)
        and left.st_dev == right.st_dev
        and left.st_ino == right.st_ino
    )


def _stable_file(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        _same_file(left, right)
        and left.st_nlink == 1
        and right.st_nlink == 1
        and left.st_size == right.st_size
        and getattr(left, "st_mtime_ns", left.st_mtime)
        == getattr(right, "st_mtime_ns", right.st_mtime)
        and getattr(left, "st_ctime_ns", left.st_ctime)
        == getattr(right, "st_ctime_ns", right.st_ctime)
    )


def _object(
    value: object,
    expected_fields: frozenset[str],
    field: str,
) -> dict[str, object]:
    if type(value) is not dict:
        _fail("TYPE_MISMATCH", "Expected a JSON object", field=field)
    typed = value
    unknown = sorted(set(typed) - expected_fields)
    if unknown:
        _fail(
            "UNKNOWN_FIELD",
            "Object contains an unknown field",
            field=f"{field}.{unknown[0]}",
        )
    missing = sorted(expected_fields - set(typed))
    if missing:
        _fail(
            "MISSING_FIELD",
            "Object is missing a required field",
            field=f"{field}.{missing[0]}",
        )
    return typed


def _array(value: object, field: str, *, minimum: int = 0) -> list[object]:
    if type(value) is not list:
        _fail("TYPE_MISMATCH", "Expected a JSON array", field=field)
    if len(value) < minimum:
        _fail("VALUE_INVALID", "Array has too few items", field=field)
    return value


def _string(value: object, field: str, *, identifier: bool = False) -> str:
    if type(value) is not str:
        _fail("TYPE_MISMATCH", "Expected a string", field=field)
    if not value.strip():
        _fail("VALUE_INVALID", "String must not be empty", field=field)
    if identifier and IDENTIFIER_PATTERN.fullmatch(value) is None:
        _fail("VALUE_INVALID", "Identifier has an invalid shape", field=field)
    return value


def _boolean(value: object, field: str) -> bool:
    if type(value) is not bool:
        _fail("TYPE_MISMATCH", "Expected a boolean", field=field)
    return value


def _integer(
    value: object,
    field: str,
    *,
    minimum: int | None = None,
) -> int:
    if type(value) is not int:
        _fail("TYPE_MISMATCH", "Expected an integer", field=field)
    if minimum is not None and value < minimum:
        _fail("VALUE_INVALID", "Integer is below the allowed minimum", field=field)
    return value


def _number(
    value: object,
    field: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if type(value) not in {int, float}:
        _fail("TYPE_MISMATCH", "Expected a finite number", field=field)
    try:
        result = float(value)
    except (OverflowError, ValueError):
        _fail(
            "VALUE_INVALID",
            "Number is outside the supported finite range",
            field=field,
        )
    if not math.isfinite(result):
        _fail(
            "DOCUMENT_NONFINITE", "Document contains a non-finite number", field=field
        )
    if minimum is not None and result < minimum:
        _fail("VALUE_INVALID", "Number is below the allowed minimum", field=field)
    if maximum is not None and result > maximum:
        _fail("VALUE_INVALID", "Number is above the allowed maximum", field=field)
    return result


def _nullable_number(value: object, field: str) -> float | None:
    return None if value is None else _number(value, field)


def _digest(value: object, field: str) -> str:
    result = _string(value, field)
    if DIGEST_PATTERN.fullmatch(result) is None:
        _fail("VALUE_INVALID", "Expected a sha256: digest", field=field)
    return result


def _timestamp(value: object, field: str) -> str:
    result = _string(value, field)
    if TIMESTAMP_PATTERN.fullmatch(result) is None:
        _fail("VALUE_INVALID", "Expected a UTC RFC 3339 timestamp", field=field)
    try:
        datetime.fromisoformat(result[:-1] + "+00:00")
    except ValueError:
        _fail("VALUE_INVALID", "Expected a UTC RFC 3339 timestamp", field=field)
    return result


def _unique_strings(
    value: object,
    field: str,
    *,
    minimum: int = 0,
    identifiers: bool = False,
) -> list[str]:
    items = _array(value, field, minimum=minimum)
    result = [
        _string(item, f"{field}[{index}]", identifier=identifiers)
        for index, item in enumerate(items)
    ]
    if len(result) != len(set(result)):
        _fail("VALUE_INVALID", "Array values must be unique", field=field)
    return result


def _expect(value: object, expected: object, field: str) -> None:
    if value != expected:
        _fail("UNSUPPORTED_ROUTE", "Value is outside the promoted route", field=field)


def _validate_binding(value: object, field: str) -> dict[str, object]:
    binding = _object(
        value,
        frozenset(
            {
                "schema_version",
                "capability_id",
                "adapter_id",
                "backend_id",
                "request_schema",
                "result_schema",
            }
        ),
        field,
    )
    _expect(
        binding["schema_version"],
        "tn-agent.backend-binding.v1",
        f"{field}.schema_version",
    )
    for name in (
        "capability_id",
        "adapter_id",
        "backend_id",
        "request_schema",
        "result_schema",
    ):
        _string(binding[name], f"{field}.{name}", identifier=True)
    return binding


def validate_experiment(document: object) -> dict[str, object]:
    """Validate one versioned experiment and its exact promoted route."""

    root = _object(
        document,
        frozenset(
            {
                "schema_version",
                "problem",
                "physics",
                "capability",
                "backend_binding",
                "numerics",
                "observables",
                "validators",
                "acceptance",
                "reference",
                "provenance",
            }
        ),
        "$",
    )
    if root["schema_version"] != EXPERIMENT_SCHEMA:
        _fail(
            "SCHEMA_VERSION_UNSUPPORTED",
            "Experiment schema version is unsupported",
            field="$.schema_version",
        )

    problem = _object(
        root["problem"],
        frozenset(
            {
                "problem_id",
                "title",
                "research_question",
                "novelty_claim",
                "status",
                "task_family",
            }
        ),
        "$.problem",
    )
    _string(problem["problem_id"], "$.problem.problem_id", identifier=True)
    for name in ("title", "research_question", "novelty_claim"):
        _string(problem[name], f"$.problem.{name}")
    if problem["status"] not in {"candidate", "test_fixture"}:
        _fail("VALUE_INVALID", "Problem status is invalid", field="$.problem.status")
    task_family = _string(
        problem["task_family"], "$.problem.task_family", identifier=True
    )

    physics = _object(
        root["physics"],
        frozenset({"model", "lattice", "symmetry", "ansatz"}),
        "$.physics",
    )
    model = _object(
        physics["model"],
        frozenset(
            {
                "representation",
                "family",
                "operators",
                "couplings",
                "onsite_terms",
                "neighbor_range",
            }
        ),
        "$.physics.model",
    )
    _string(model["representation"], "$.physics.model.representation", identifier=True)
    model_family = _string(model["family"], "$.physics.model.family", identifier=True)
    operators = _unique_strings(
        model["operators"],
        "$.physics.model.operators",
        minimum=1,
    )
    couplings = _object(
        model["couplings"],
        frozenset(model["couplings"])
        if type(model["couplings"]) is dict
        else frozenset(),
        "$.physics.model.couplings",
    )
    for name, value in couplings.items():
        _string(name, "$.physics.model.couplings.<key>", identifier=True)
        _number(value, f"$.physics.model.couplings.{name}")
    onsite_terms = _array(model["onsite_terms"], "$.physics.model.onsite_terms")
    _integer(model["neighbor_range"], "$.physics.model.neighbor_range", minimum=1)

    lattice = _object(
        physics["lattice"],
        frozenset({"type", "length", "boundary", "local_dim", "unit_cell"}),
        "$.physics.lattice",
    )
    _string(lattice["type"], "$.physics.lattice.type", identifier=True)
    if lattice["length"] is not None:
        _integer(lattice["length"], "$.physics.lattice.length", minimum=1)
    _string(lattice["boundary"], "$.physics.lattice.boundary", identifier=True)
    _integer(lattice["local_dim"], "$.physics.lattice.local_dim", minimum=1)
    _integer(lattice["unit_cell"], "$.physics.lattice.unit_cell", minimum=1)

    symmetry = _object(
        physics["symmetry"],
        frozenset({"U1_Sz", "parity", "translation", "target_sector"}),
        "$.physics.symmetry",
    )
    for name in ("U1_Sz", "parity", "translation"):
        _boolean(symmetry[name], f"$.physics.symmetry.{name}")
    if symmetry["target_sector"] is not None:
        target = _object(
            symmetry["target_sector"],
            frozenset({"total_Sz"}),
            "$.physics.symmetry.target_sector",
        )
        _integer(target["total_Sz"], "$.physics.symmetry.target_sector.total_Sz")

    ansatz = _object(
        physics["ansatz"],
        frozenset(
            {
                "family",
                "algorithm",
                "variant",
                "initial_state",
                "allow_bond_growth",
                "target_precision",
            }
        ),
        "$.physics.ansatz",
    )
    for name in ("family", "algorithm", "variant", "initial_state"):
        _string(ansatz[name], f"$.physics.ansatz.{name}", identifier=True)
    _boolean(ansatz["allow_bond_growth"], "$.physics.ansatz.allow_bond_growth")
    _number(
        ansatz["target_precision"],
        "$.physics.ansatz.target_precision",
        minimum=0.0,
    )
    if float(ansatz["target_precision"]) <= 0.0:
        _fail(
            "VALUE_INVALID",
            "Target precision must be positive",
            field="$.physics.ansatz.target_precision",
        )

    capability = _object(
        root["capability"],
        frozenset({"capability_id", "maturity", "known_limitations"}),
        "$.capability",
    )
    capability_id = _string(
        capability["capability_id"],
        "$.capability.capability_id",
        identifier=True,
    )
    route = ROUTES.get(capability_id)
    if route is None:
        _fail(
            "UNSUPPORTED_ROUTE",
            "Capability is not an executable promoted route",
            field="$.capability.capability_id",
        )
    _string(capability["maturity"], "$.capability.maturity", identifier=True)
    _unique_strings(
        capability["known_limitations"],
        "$.capability.known_limitations",
        minimum=1,
    )
    binding = _validate_binding(root["backend_binding"], "$.backend_binding")

    numerics = _validate_numerics(root["numerics"], capability_id=capability_id)
    observables = _unique_strings(
        root["observables"],
        "$.observables",
        minimum=1,
        identifiers=True,
    )
    validators = _validate_validator_specs(root["validators"])
    acceptance = _validate_acceptance(root["acceptance"])
    reference = _validate_reference(root["reference"])
    _validate_provenance(root["provenance"])

    _expect(task_family, route["task_family"], "$.problem.task_family")
    _expect(capability["maturity"], route["maturity"], "$.capability.maturity")
    _expect(
        capability["known_limitations"],
        route["known_limitations"],
        "$.capability.known_limitations",
    )
    _expect(binding, route["binding"], "$.backend_binding")
    _expect(model["representation"], "operator_sum", "$.physics.model.representation")
    _expect(model_family, route["model_family"], "$.physics.model.family")
    if set(operators) != route["operators"] or len(operators) != len(
        route["operators"]
    ):
        _fail(
            "UNSUPPORTED_ROUTE",
            "Operator set is outside the promoted route",
            field="$.physics.model.operators",
        )
    if set(couplings) != route["couplings"]:
        _fail(
            "UNSUPPORTED_ROUTE",
            "Coupling set is outside the promoted route",
            field="$.physics.model.couplings",
        )
    if capability_id == "tenpy.infinite_1d.vumps" and couplings["Jxy"] != 1.0:
        _fail(
            "UNSUPPORTED_ROUTE",
            "Standalone infinite XXZ is limited to Jxy=1",
            field="$.physics.model.couplings.Jxy",
        )
    _expect(onsite_terms, [], "$.physics.model.onsite_terms")
    _expect(model["neighbor_range"], 1, "$.physics.model.neighbor_range")
    _expect(lattice["type"], "chain", "$.physics.lattice.type")
    _expect(lattice["boundary"], route["boundary"], "$.physics.lattice.boundary")
    route_length = route["length"]
    if route_length == "positive":
        if type(lattice["length"]) is not int or lattice["length"] <= 0:
            _fail(
                "UNSUPPORTED_ROUTE",
                "Finite route requires a positive chain length",
                field="$.physics.lattice.length",
            )
    else:
        _expect(lattice["length"], route_length, "$.physics.lattice.length")
    _expect(lattice["local_dim"], 2, "$.physics.lattice.local_dim")
    _expect(lattice["unit_cell"], route["unit_cell"], "$.physics.lattice.unit_cell")
    _expect(symmetry, route["symmetry"], "$.physics.symmetry")
    _expect(ansatz["family"], "mps", "$.physics.ansatz.family")
    _expect(ansatz["algorithm"], route["algorithm"], "$.physics.ansatz.algorithm")
    _expect(ansatz["variant"], route["variant"], "$.physics.ansatz.variant")
    _expect(
        ansatz["initial_state"],
        route["initial_state"],
        "$.physics.ansatz.initial_state",
    )
    _expect(ansatz["allow_bond_growth"], True, "$.physics.ansatz.allow_bond_growth")

    supported_observables = route["observables"]
    if not set(observables).issubset(supported_observables):  # type: ignore[arg-type]
        _fail(
            "UNSUPPORTED_ROUTE",
            "Observable is outside the promoted route",
            field="$.observables",
        )
    if not {"energy", "variance"}.issubset(observables):
        _fail(
            "OBSERVABLE_SET_MISMATCH",
            "Promoted acceptance requires energy and variance observables",
            field="$.observables",
        )
    backend_limited_validators = route["backend_limited_validators"]
    expected_required = (
        VALIDATOR_IDS - REPORTED_ONLY_VALIDATOR_IDS - backend_limited_validators  # type: ignore[operator]
    )
    expected_limited = backend_limited_validators
    expected_reported = REPORTED_ONLY_VALIDATOR_IDS - backend_limited_validators  # type: ignore[operator]
    actual_required = {
        item["id"] for item in validators if item["policy"] == "required_pass"
    }
    actual_limited = {
        item["id"] for item in validators if item["policy"] == "backend_limited"
    }
    actual_reported = {
        item["id"] for item in validators if item["policy"] == "reported_only"
    }
    if (
        actual_required != expected_required
        or actual_limited != expected_limited
        or actual_reported != expected_reported
    ):
        _fail(
            "VALIDATOR_POLICY_MISMATCH",
            "Validator policy does not match the promoted route",
            field="$.validators",
        )
    if set(acceptance["required_validator_ids"]) != actual_required:
        _fail(
            "ACCEPTANCE_CONTRACT_INVALID",
            "Acceptance required validators do not match validator policy",
            field="$.acceptance.required_validator_ids",
        )
    if set(acceptance["allowed_backend_limited_ids"]) != actual_limited:
        _fail(
            "ACCEPTANCE_CONTRACT_INVALID",
            "Acceptance backend-limited validators do not match validator policy",
            field="$.acceptance.allowed_backend_limited_ids",
        )
    if set(acceptance["reported_only_validator_ids"]) != actual_reported:
        _fail(
            "ACCEPTANCE_CONTRACT_INVALID",
            "Acceptance reported-only validators do not match validator policy",
            field="$.acceptance.reported_only_validator_ids",
        )
    expected_normalization = (
        "total" if capability_id == "tenpy.finite_1d.dmrg" else "per-site"
    )
    if reference["normalization"] != expected_normalization:
        _fail(
            "VALUE_INVALID",
            "Reference normalization does not match the promoted route",
            field="$.reference.normalization",
        )
    _validate_route_numerics(capability_id, numerics, observables)
    return {
        "ok": True,
        "reason_code": "OK",
        "schema_version": EXPERIMENT_SCHEMA,
        "problem_id": problem["problem_id"],
        "problem_status": problem["status"],
        "capability_id": capability_id,
        "experiment_digest": canonical_digest(root),
    }


def _validate_numerics(
    value: object,
    *,
    capability_id: str,
) -> dict[str, object]:
    common_fields = frozenset(
        {
            "max_bond_dim",
            "cutoff",
            "max_sweeps",
            "mixer",
            "lanczos_maxiter",
            "checkpoint_every",
            "finite_entanglement_fit",
            "transfer_matrix",
            "seed",
        }
    )
    infinite_fields = frozenset({"min_sweeps", "entropy_tolerance"})
    numerics = _object(
        value,
        common_fields
        | (
            infinite_fields
            if capability_id == "tenpy.infinite_1d.vumps"
            else frozenset()
        ),
        "$.numerics",
    )
    for name in (
        "max_bond_dim",
        "max_sweeps",
        "lanczos_maxiter",
        "checkpoint_every",
    ):
        _integer(numerics[name], f"$.numerics.{name}", minimum=1)
    _integer(numerics["seed"], "$.numerics.seed", minimum=0)
    _number(numerics["cutoff"], "$.numerics.cutoff", minimum=0.0)
    _boolean(numerics["mixer"], "$.numerics.mixer")
    if capability_id == "tenpy.infinite_1d.vumps":
        _integer(numerics["min_sweeps"], "$.numerics.min_sweeps", minimum=1)
        entropy = _number(
            numerics["entropy_tolerance"],
            "$.numerics.entropy_tolerance",
            minimum=0.0,
        )
        if entropy <= 0:
            _fail(
                "VALUE_INVALID",
                "Entropy tolerance must be positive",
                field="$.numerics.entropy_tolerance",
            )
    fit = _object(
        numerics["finite_entanglement_fit"],
        frozenset({"enabled", "min_chi", "max_chi"}),
        "$.numerics.finite_entanglement_fit",
    )
    _boolean(fit["enabled"], "$.numerics.finite_entanglement_fit.enabled")
    _integer(fit["min_chi"], "$.numerics.finite_entanglement_fit.min_chi", minimum=1)
    _integer(fit["max_chi"], "$.numerics.finite_entanglement_fit.max_chi", minimum=1)
    transfer = _object(
        numerics["transfer_matrix"],
        frozenset({"compute", "num_eigs"}),
        "$.numerics.transfer_matrix",
    )
    _boolean(transfer["compute"], "$.numerics.transfer_matrix.compute")
    _integer(transfer["num_eigs"], "$.numerics.transfer_matrix.num_eigs", minimum=1)
    if (
        capability_id == "tenpy.infinite_1d.vumps"
        and numerics["min_sweeps"] > numerics["max_sweeps"]  # type: ignore[operator]
    ):
        _fail(
            "VALUE_INVALID",
            "Minimum sweeps exceed maximum sweeps",
            field="$.numerics.min_sweeps",
        )
    if fit["min_chi"] > fit["max_chi"]:  # type: ignore[operator]
        _fail(
            "VALUE_INVALID",
            "Finite-entanglement chi range is reversed",
            field="$.numerics.finite_entanglement_fit",
        )
    return numerics


def _validate_route_numerics(
    capability_id: str,
    numerics: Mapping[str, object],
    observables: Sequence[str],
) -> None:
    fit = numerics["finite_entanglement_fit"]
    transfer = numerics["transfer_matrix"]
    assert isinstance(fit, dict)
    assert isinstance(transfer, dict)
    if capability_id == "tenpy.finite_1d.dmrg":
        _expect(numerics["mixer"], True, "$.numerics.mixer")
        _expect(fit["enabled"], False, "$.numerics.finite_entanglement_fit.enabled")
        _expect(transfer["compute"], False, "$.numerics.transfer_matrix.compute")
    else:
        _expect(numerics["mixer"], False, "$.numerics.mixer")
        if (
            type(numerics["entropy_tolerance"]) not in {int, float}
            or float(numerics["entropy_tolerance"]) <= 0
        ):
            _fail(
                "UNSUPPORTED_ROUTE",
                "Infinite route requires an explicit positive entropy tolerance",
                field="$.numerics.entropy_tolerance",
            )
        _expect(fit["enabled"], True, "$.numerics.finite_entanglement_fit.enabled")
        _expect(transfer["compute"], True, "$.numerics.transfer_matrix.compute")
        if fit["max_chi"] != numerics["max_bond_dim"]:
            _fail(
                "UNSUPPORTED_ROUTE",
                "Fit maximum chi must equal the maximum bond dimension",
                field="$.numerics.finite_entanglement_fit.max_chi",
            )
        if "central_charge_fit" in observables and fit["min_chi"] == fit["max_chi"]:
            _fail(
                "UNSUPPORTED_ROUTE",
                "Central-charge fitting requires at least two chi points",
                field="$.numerics.finite_entanglement_fit",
            )


def _validate_validator_specs(value: object) -> list[dict[str, object]]:
    items = _array(value, "$.validators", minimum=1)
    validators: list[dict[str, object]] = []
    for index, raw in enumerate(items):
        field = f"$.validators[{index}]"
        item = _object(
            raw,
            frozenset({"id", "policy", "metric", "operator", "threshold"}),
            field,
        )
        validator_id = _string(item["id"], f"{field}.id", identifier=True)
        if validator_id not in VALIDATOR_IDS:
            _fail(
                "UNSUPPORTED_ROUTE",
                "Validator is outside the promoted route",
                field=f"{field}.id",
            )
        if item["policy"] not in {
            "required_pass",
            "reported_only",
            "backend_limited",
        }:
            _fail(
                "VALUE_INVALID", "Validator policy is invalid", field=f"{field}.policy"
            )
        if item["metric"] is None:
            if item["operator"] is not None or item["threshold"] is not None:
                _fail(
                    "VALUE_INVALID",
                    "Metric-free validator must not define an operator or threshold",
                    field=field,
                )
        else:
            _string(item["metric"], f"{field}.metric", identifier=True)
            if item["policy"] == "reported_only":
                if item["operator"] is not None or item["threshold"] is not None:
                    _fail(
                        "VALIDATOR_POLICY_MISMATCH",
                        "Reported-only diagnostics cannot define acceptance thresholds",
                        field=field,
                    )
            elif item["operator"] not in {"max", "min", "equals"}:
                _fail(
                    "VALUE_INVALID",
                    "Validator operator is invalid",
                    field=f"{field}.operator",
                )
            else:
                _number(item["threshold"], f"{field}.threshold")
        if item["policy"] == "backend_limited" and item["metric"] is not None:
            _fail(
                "VALUE_INVALID",
                "Backend-limited validator must not claim a metric threshold",
                field=field,
            )
        expected_metric, expected_operator, domain = VALIDATOR_RULES[validator_id]
        if item["policy"] == "backend_limited":
            expected_metric = None
            expected_operator = None
        elif item["policy"] == "reported_only":
            expected_operator = None
        if item["metric"] != expected_metric or item["operator"] != expected_operator:
            _fail(
                "VALIDATOR_POLICY_MISMATCH",
                "Validator metric or operator does not match its public contract",
                field=field,
            )
        if item["policy"] == "required_pass" and expected_metric is not None:
            if domain == "nonnegative_integer":
                if type(item["threshold"]) is not int or item["threshold"] != 0:
                    _fail(
                        "VALIDATOR_POLICY_MISMATCH",
                        "Artifact completeness requires an exact integer zero threshold",
                        field=f"{field}.threshold",
                    )
            else:
                _number(item["threshold"], f"{field}.threshold", minimum=0.0)
        validators.append(item)
    ids = [str(item["id"]) for item in validators]
    if len(ids) != len(set(ids)):
        _fail(
            "VALUE_INVALID",
            "Validator identifiers must be unique",
            field="$.validators",
        )
    if set(ids) != VALIDATOR_IDS:
        _fail(
            "VALIDATOR_SET_MISMATCH",
            "Experiment must declare the complete public validator set",
            field="$.validators",
        )
    return validators


def _validate_acceptance(value: object) -> dict[str, object]:
    acceptance = _object(
        value,
        frozenset(
            {
                "mode",
                "required_validator_ids",
                "allowed_backend_limited_ids",
                "reported_only_validator_ids",
                "require_execution_success",
            }
        ),
        "$.acceptance",
    )
    if acceptance["mode"] != "all_required":
        _fail(
            "ACCEPTANCE_CONTRACT_INVALID",
            "Only all_required acceptance is supported",
            field="$.acceptance.mode",
        )
    acceptance["required_validator_ids"] = _unique_strings(
        acceptance["required_validator_ids"],
        "$.acceptance.required_validator_ids",
        minimum=1,
        identifiers=True,
    )
    acceptance["allowed_backend_limited_ids"] = _unique_strings(
        acceptance["allowed_backend_limited_ids"],
        "$.acceptance.allowed_backend_limited_ids",
        identifiers=True,
    )
    acceptance["reported_only_validator_ids"] = _unique_strings(
        acceptance["reported_only_validator_ids"],
        "$.acceptance.reported_only_validator_ids",
        identifiers=True,
    )
    if set(acceptance["required_validator_ids"]) & set(
        acceptance["allowed_backend_limited_ids"]
    ):
        _fail(
            "ACCEPTANCE_CONTRACT_INVALID",
            "Required and backend-limited validators overlap",
            field="$.acceptance",
        )
    policy_sets = (
        set(acceptance["required_validator_ids"]),
        set(acceptance["allowed_backend_limited_ids"]),
        set(acceptance["reported_only_validator_ids"]),
    )
    if any(
        policy_sets[index] & policy_sets[other]
        for index in range(3)
        for other in range(index + 1, 3)
    ):
        _fail(
            "ACCEPTANCE_CONTRACT_INVALID",
            "Required, reported-only, and backend-limited validator sets overlap",
            field="$.acceptance",
        )
    if (
        _boolean(
            acceptance["require_execution_success"],
            "$.acceptance.require_execution_success",
        )
        is not True
    ):
        _fail(
            "ACCEPTANCE_CONTRACT_INVALID",
            "Successful execution must be required",
            field="$.acceptance.require_execution_success",
        )
    return acceptance


def _validate_reference(value: object) -> dict[str, object]:
    reference = _object(
        value,
        frozenset({"observable", "value", "units", "normalization", "source"}),
        "$.reference",
    )
    _expect(reference["observable"], "energy", "$.reference.observable")
    _number(reference["value"], "$.reference.value")
    _expect(reference["units"], "J", "$.reference.units")
    if reference["normalization"] not in {"total", "per-site"}:
        _fail(
            "VALUE_INVALID",
            "Reference normalization is invalid",
            field="$.reference.normalization",
        )
    source = _object(
        reference["source"],
        frozenset({"kind", "uri", "sha256"}),
        "$.reference.source",
    )
    _expect(source["kind"], "registered_artifact", "$.reference.source.kind")
    uri = _string(source["uri"], "$.reference.source.uri")
    _validate_relative_path(uri, "$.reference.source.uri")
    _digest(source["sha256"], "$.reference.source.sha256")
    return reference


def _validate_provenance(value: object) -> None:
    provenance = _object(
        value,
        frozenset(
            {
                "created_by",
                "created_at",
                "sources",
                "generation_log_uri",
                "human_gatekeeper_role",
            }
        ),
        "$.provenance",
    )
    _string(provenance["created_by"], "$.provenance.created_by")
    _timestamp(provenance["created_at"], "$.provenance.created_at")
    _string(provenance["generation_log_uri"], "$.provenance.generation_log_uri")
    _string(provenance["human_gatekeeper_role"], "$.provenance.human_gatekeeper_role")
    sources = _array(provenance["sources"], "$.provenance.sources", minimum=1)
    identities: list[tuple[str, str, str]] = []
    for index, raw in enumerate(sources):
        field = f"$.provenance.sources[{index}]"
        source = _object(raw, frozenset({"kind", "uri", "sha256"}), field)
        kind = _string(source["kind"], f"{field}.kind", identifier=True)
        uri = _string(source["uri"], f"{field}.uri")
        digest = _digest(source["sha256"], f"{field}.sha256")
        identities.append((kind, uri, digest))
    if len(identities) != len(set(identities)):
        _fail(
            "VALUE_INVALID",
            "Provenance sources must be unique",
            field="$.provenance.sources",
        )


def _validate_evidence(document: object) -> dict[str, object]:
    root = _object(
        document,
        frozenset(
            {
                "schema_version",
                "experiment_digest",
                "binding",
                "execution",
                "repeat_execution",
                "artifacts",
                "observables",
                "validator_results",
                "provenance",
                "result_digest",
            }
        ),
        "$",
    )
    if root["schema_version"] != EVIDENCE_SCHEMA:
        _fail(
            "SCHEMA_VERSION_UNSUPPORTED",
            "Evidence schema version is unsupported",
            field="$.schema_version",
        )
    _digest(root["experiment_digest"], "$.experiment_digest")
    _validate_binding(root["binding"], "$.binding")
    execution = _validate_execution(root["execution"], "$.execution")
    repeat_execution = _validate_execution(
        root["repeat_execution"],
        "$.repeat_execution",
    )
    if not isinstance(execution["execution_handle"], str) or not isinstance(
        repeat_execution["execution_handle"], str
    ):
        _fail(
            "PROVENANCE_MISMATCH",
            "Successful primary and repeat evidence requires explicit handles",
            field="$.execution",
        )
    if execution["execution_handle"] == repeat_execution["execution_handle"]:
        _fail(
            "PROVENANCE_MISMATCH",
            "Primary and repeat executions require distinct handles",
            field="$.repeat_execution.execution_handle",
        )

    artifacts = _array(root["artifacts"], "$.artifacts", minimum=1)
    if len(artifacts) > MAX_ARTIFACTS:
        _fail("ARTIFACT_LIMIT_EXCEEDED", "Artifact count exceeds the limit")
    artifact_paths: list[str] = []
    artifact_roles: list[str] = []
    expected_media_types = {
        "backend_request": "application/json",
        "backend_raw_result": "application/json",
        "backend_result": "application/json",
        "backend_repeat_raw_result": "application/json",
        "backend_repeat_result": "application/json",
        "energy_reference": "application/json",
        "validator_evidence": "application/json",
        "backend_stdout": "text/plain",
        "backend_stderr": "text/plain",
        "backend_repeat_stdout": "text/plain",
        "backend_repeat_stderr": "text/plain",
    }
    for index, raw in enumerate(artifacts):
        field = f"$.artifacts[{index}]"
        item = _object(
            raw,
            frozenset(
                {
                    "relative_path",
                    "digest",
                    "size_bytes",
                    "media_type",
                    "role",
                }
            ),
            field,
        )
        relative = _string(item["relative_path"], f"{field}.relative_path")
        _validate_relative_path(relative, f"{field}.relative_path")
        artifact_paths.append(relative)
        _digest(item["digest"], f"{field}.digest")
        _integer(item["size_bytes"], f"{field}.size_bytes", minimum=0)
        media_type = _string(item["media_type"], f"{field}.media_type")
        role = _string(item["role"], f"{field}.role", identifier=True)
        if role not in expected_media_types:
            _fail(
                "VALUE_INVALID",
                "Artifact role is not part of the public contract",
                field=f"{field}.role",
            )
        if media_type != expected_media_types[role]:
            _fail(
                "VALUE_INVALID",
                "Artifact media type does not match its required role",
                field=f"{field}.media_type",
            )
        artifact_roles.append(role)
    if len(artifact_paths) != len(set(artifact_paths)):
        _fail("VALUE_INVALID", "Artifact paths must be unique", field="$.artifacts")
    required_roles = set(expected_media_types)
    if (
        len(artifact_roles) != len(required_roles)
        or set(artifact_roles) != required_roles
    ):
        _fail(
            "VALUE_INVALID",
            "Evidence must register exactly one artifact for every required role",
            field="$.artifacts",
        )

    observable_items = _array(root["observables"], "$.observables", minimum=1)
    observable_names: list[str] = []
    for index, raw in enumerate(observable_items):
        field = f"$.observables[{index}]"
        item = _object(
            raw,
            frozenset({"name", "status", "evidence_digest"}),
            field,
        )
        observable_names.append(_string(item["name"], f"{field}.name", identifier=True))
        if item["status"] not in {"measured", "derived", "backend_limited"}:
            _fail(
                "VALUE_INVALID", "Observable status is invalid", field=f"{field}.status"
            )
        _digest(item["evidence_digest"], f"{field}.evidence_digest")
    if len(observable_names) != len(set(observable_names)):
        _fail("VALUE_INVALID", "Observable names must be unique", field="$.observables")

    result_items = _array(
        root["validator_results"],
        "$.validator_results",
        minimum=1,
    )
    result_ids: list[str] = []
    for index, raw in enumerate(result_items):
        field = f"$.validator_results[{index}]"
        item = _object(
            raw,
            frozenset(
                {
                    "id",
                    "status",
                    "reason_code",
                    "metric_value",
                    "evidence_digest",
                }
            ),
            field,
        )
        result_ids.append(_string(item["id"], f"{field}.id", identifier=True))
        if item["status"] not in {
            "pass",
            "fail",
            "reported_only",
            "backend_limited",
        }:
            _fail(
                "VALUE_INVALID", "Validator status is invalid", field=f"{field}.status"
            )
        _string(item["reason_code"], f"{field}.reason_code", identifier=True)
        _nullable_number(item["metric_value"], f"{field}.metric_value")
        _digest(item["evidence_digest"], f"{field}.evidence_digest")
    if len(result_ids) != len(set(result_ids)):
        _fail(
            "VALUE_INVALID",
            "Validator result identifiers must be unique",
            field="$.validator_results",
        )

    provenance = _object(
        root["provenance"],
        frozenset(
            {
                "plan_id",
                "request_digest",
                "backend_result_digest",
                "repeat_backend_result_digest",
                "generated_by",
                "generated_at",
            }
        ),
        "$.provenance",
    )
    for name in (
        "plan_id",
        "request_digest",
        "backend_result_digest",
        "repeat_backend_result_digest",
    ):
        _digest(provenance[name], f"$.provenance.{name}")
    _string(provenance["generated_by"], "$.provenance.generated_by")
    _timestamp(provenance["generated_at"], "$.provenance.generated_at")
    _digest(root["result_digest"], "$.result_digest")
    return root


def _validate_execution(value: object, field: str) -> dict[str, object]:
    execution = _object(
        value,
        frozenset(
            {
                "schema_version",
                "status",
                "return_code",
                "execution_handle",
                "retryable",
                "stdout_digest",
                "stderr_digest",
                "stdout_truncated",
                "stderr_truncated",
            }
        ),
        field,
    )
    if execution["schema_version"] != "tn-agent.execution-evidence.v1":
        _fail(
            "SCHEMA_VERSION_UNSUPPORTED",
            "Execution evidence schema version is unsupported",
            field=f"{field}.schema_version",
        )
    if execution["status"] not in {
        "succeeded",
        "failed",
        "timed_out",
        "cancelled",
        "not_executed",
    }:
        _fail("VALUE_INVALID", "Execution status is invalid", field=f"{field}.status")
    if execution["return_code"] is not None:
        _integer(execution["return_code"], f"{field}.return_code")
    if execution["execution_handle"] is not None:
        _string(execution["execution_handle"], f"{field}.execution_handle")
    _boolean(execution["retryable"], f"{field}.retryable")
    _digest(execution["stdout_digest"], f"{field}.stdout_digest")
    _digest(execution["stderr_digest"], f"{field}.stderr_digest")
    _boolean(execution["stdout_truncated"], f"{field}.stdout_truncated")
    _boolean(execution["stderr_truncated"], f"{field}.stderr_truncated")
    return execution


def _expected_plan_id(
    experiment: Mapping[str, object],
    experiment_digest: str,
) -> str:
    return canonical_digest(
        {
            "schema_version": "tn-agent.execution-plan.v1",
            "experiment_digest": experiment_digest,
            "binding": experiment["backend_binding"],
            "physics": experiment["physics"],
            "numerics": experiment["numerics"],
            "observables": experiment["observables"],
            "validators": experiment["validators"],
        }
    )


def _expected_request(
    experiment: Mapping[str, object],
    experiment_digest: str,
    plan_id: str,
) -> dict[str, object]:
    binding = experiment["backend_binding"]
    physics = experiment["physics"]
    numerics = experiment["numerics"]
    validators = experiment["validators"]
    assert isinstance(binding, dict)
    assert isinstance(physics, dict)
    assert isinstance(numerics, dict)
    assert isinstance(validators, list)
    model = physics["model"]
    lattice = physics["lattice"]
    symmetry = physics["symmetry"]
    ansatz = physics["ansatz"]
    fit = numerics["finite_entanglement_fit"]
    transfer = numerics["transfer_matrix"]
    assert isinstance(model, dict)
    assert isinstance(lattice, dict)
    assert isinstance(symmetry, dict)
    assert isinstance(ansatz, dict)
    assert isinstance(fit, dict)
    assert isinstance(transfer, dict)
    thresholds = {
        str(item["id"]): item["threshold"]
        for item in validators
        if isinstance(item, dict)
    }
    acceptance = {
        # The backend fields are execution/tuning inputs. Scientific acceptance
        # is owned by this public gate, and raw-only diagnostics are never
        # promoted merely because a worker reports a small value.
        "require_all_validators": False,
        "energy_drift_max": float(thresholds["convergence"]),
        "variance_max": 0.0,
        "canonical_residual_max": float(ansatz["target_precision"]),
        "symmetry_residual_max": 0.0,
        # The current worker schema requires this compatibility field, but the
        # public gate deliberately gives repeat consistency no acceptance
        # threshold until a trusted scheduler/registry receipt is available.
        "reproducibility_max": 0.0,
    }
    max_bond_dim = int(numerics["max_bond_dim"])
    capability_id = str(binding["capability_id"])
    if capability_id == "tenpy.finite_1d.dmrg":
        chi_schedule = [max_bond_dim]
        effective_svd_min: float | None = float(numerics["cutoff"])
        engine_cutoff = float(numerics["cutoff"])
        minimum_sweeps = 0
        entropy_tolerance: float | None = None
        lanczos_n_max = int(numerics["lanczos_maxiter"])
    else:
        minimum_chi = int(fit["min_chi"])
        chi_schedule = []
        current = minimum_chi
        while current < max_bond_dim:
            chi_schedule.append(current)
            current *= 2
        chi_schedule.append(max_bond_dim)
        chi_schedule = sorted(set(chi_schedule))
        effective_svd_min = None
        engine_cutoff = 0.0
        minimum_sweeps = int(numerics["min_sweeps"])
        entropy_tolerance = float(numerics["entropy_tolerance"])
        lanczos_n_max = int(numerics["lanczos_maxiter"]) * 4
    common: dict[str, object] = {
        "schema_version": binding["request_schema"],
        "capability_id": capability_id,
        "plan_id": plan_id,
        "model_family": model["family"],
        "representation": model["representation"],
        "operators": sorted(model["operators"]),  # type: ignore[arg-type]
        "boundary": lattice["boundary"],
        "local_dimension": lattice["local_dim"],
        "unit_cell": lattice["unit_cell"],
        "algorithm": ansatz["algorithm"],
        "variant": ansatz["variant"],
        "active_sites": 2,
        "initial_state": ansatz["initial_state"],
        "allow_bond_growth": ansatz["allow_bond_growth"],
        "target_precision": float(ansatz["target_precision"]),
        "seed": numerics["seed"],
        "numerics": {
            "max_bond_dim": max_bond_dim,
            "chi_schedule": chi_schedule,
            "requested_cutoff": float(numerics["cutoff"]),
            "effective_svd_min": effective_svd_min,
            "engine_cutoff": engine_cutoff,
            "max_sweeps": numerics["max_sweeps"],
            "min_sweeps": minimum_sweeps,
            "entropy_tolerance": entropy_tolerance,
            "mixer": numerics["mixer"],
            "lanczos_maxiter": numerics["lanczos_maxiter"],
            "lanczos_n_max": lanczos_n_max,
            "checkpoint_every": numerics["checkpoint_every"],
            "diagonal_gauge_frequency": 0,
            "check_overlap": False,
        },
        "finite_entanglement_fit": {
            **fit,
            "entropy_statistic": "center",
        },
        "transfer_matrix": transfer,
        "acceptance": acceptance,
        "requested_observables": sorted(experiment["observables"]),  # type: ignore[arg-type]
    }
    couplings = model["couplings"]
    assert isinstance(couplings, dict)
    if capability_id == "tenpy.finite_1d.dmrg":
        request = {
            **common,
            "length": lattice["length"],
            "coupling_j": float(couplings["J"]),
            "transverse_field_g": float(couplings["g"]),
            "conserve": None,
            "target_total_sz": None,
        }
    else:
        target_sector = symmetry["target_sector"]
        assert isinstance(target_sector, dict)
        request = {
            **common,
            "coupling_jxy": float(couplings["Jxy"]),
            "anisotropy_delta": float(couplings["Delta"]),
            "field_h": float(couplings["h"]),
            "conserve": "Sz",
            "target_total_sz": target_sector["total_Sz"],
        }
    return request


def _strict_json_bytes(raw: bytes, label: str) -> object:
    try:
        return _strict_json_loads(raw.decode("utf-8", errors="strict"))
    except UnicodeDecodeError:
        _fail(
            "DOCUMENT_INVALID_UTF8",
            f"{label} is not valid UTF-8",
            exit_code=3,
        )


def _validate_metric_domain(
    validator_id: str,
    value: object,
    field: str,
) -> None:
    _metric, _operator, domain = VALIDATOR_RULES[validator_id]
    if domain == "none":
        if value is not None:
            _fail(
                "VALIDATOR_STATUS_INVALID",
                "Metric-free validator must have a null value",
                field=field,
                exit_code=3,
            )
    elif domain == "nonnegative_integer":
        if type(value) is not int or value < 0:
            _fail(
                "VALIDATOR_STATUS_INVALID",
                "Artifact count must be an exact nonnegative integer",
                field=field,
                exit_code=3,
            )
    else:
        observed = _number(value, field)
        if observed < 0.0:
            _fail(
                "VALIDATOR_STATUS_INVALID",
                "Validator metric must be nonnegative",
                field=field,
                exit_code=3,
            )


def _validate_json_value(value: object, field: str) -> None:
    if value is None or type(value) in {str, bool}:
        return
    if type(value) in {int, float}:
        _number(value, field)
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _validate_json_value(item, f"{field}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            _string(key, f"{field}.key")
            _validate_json_value(item, f"{field}.{key}")
        return
    _fail("TYPE_MISMATCH", "Expected a JSON value", field=field)


def _validate_reconstructed_shape(
    value: object,
    expected: object,
    field: str,
) -> None:
    """Fail closed on shape and JSON domains before comparing canonical values."""

    if type(expected) is dict:
        expected_object = expected
        actual = _object(value, frozenset(expected_object), field)
        for name, expected_value in expected_object.items():
            _validate_reconstructed_shape(
                actual[name],
                expected_value,
                f"{field}.{name}",
            )
        return
    if type(expected) is list:
        actual = _array(value, field)
        expected_list = expected
        if len(actual) != len(expected_list):
            _fail(
                "VALUE_INVALID",
                "Array length differs from the canonical reconstruction",
                field=field,
                exit_code=3,
            )
        for index, (item, expected_item) in enumerate(
            zip(actual, expected_list, strict=True)
        ):
            _validate_reconstructed_shape(item, expected_item, f"{field}[{index}]")
        return
    if expected is None:
        if value is not None:
            _fail(
                "TYPE_MISMATCH",
                "Expected null in the canonical reconstruction",
                field=field,
                exit_code=3,
            )
        return
    if type(expected) is str:
        _string(value, field)
        return
    if type(expected) is bool:
        _boolean(value, field)
        return
    if type(expected) is int:
        _integer(value, field)
        return
    if type(expected) is float:
        if type(value) is not float:
            _fail(
                "TYPE_MISMATCH",
                "Expected an exact floating-point number",
                field=field,
                exit_code=3,
            )
        _number(value, field)
        return
    _fail("TYPE_MISMATCH", "Unsupported reconstructed JSON value", field=field)


def _validate_raw_result(
    raw: bytes,
    *,
    request: Mapping[str, object],
    request_digest: str,
    binding: Mapping[str, object],
    route: Mapping[str, object],
) -> dict[str, object]:
    document = _strict_json_bytes(raw, "Backend raw result")
    result = _object(
        document,
        frozenset(
            {
                "schema_version",
                "request_digest",
                "plan_id",
                "capability_id",
                "backend_id",
                "backend_version",
                "adapter_id",
                "adapter_version",
                "status",
                "environment",
                "observables",
                "convergence",
                "warnings",
                "known_limitations",
            }
        ),
        "$raw",
    )
    expected_identity = {
        "schema_version": "tn-agent.tenpy.raw-result.v1",
        "request_digest": request_digest,
        "plan_id": request["plan_id"],
        "capability_id": binding["capability_id"],
        "backend_id": binding["backend_id"],
        "backend_version": "1.1.0",
        "adapter_id": binding["adapter_id"],
        "adapter_version": "1.0.0",
        "status": "succeeded",
    }
    for name, expected in expected_identity.items():
        if result[name] != expected:
            _fail(
                "PROVENANCE_MISMATCH",
                "Raw result identity or execution status is inconsistent",
                field=f"$raw.{name}",
                exit_code=3,
            )
    environment = _object(
        result["environment"],
        frozenset(
            {
                "schema_version",
                "environment_digest",
                "runtime_id",
                "runtime_version",
                "dependencies",
            }
        ),
        "$raw.environment",
    )
    if environment["schema_version"] != "tn-agent.tenpy.environment.v1":
        _fail(
            "SCHEMA_VERSION_UNSUPPORTED",
            "Raw environment schema version is unsupported",
            field="$raw.environment.schema_version",
            exit_code=3,
        )
    _digest(environment["environment_digest"], "$raw.environment.environment_digest")
    _string(environment["runtime_id"], "$raw.environment.runtime_id", identifier=True)
    _string(environment["runtime_version"], "$raw.environment.runtime_version")
    dependencies = _object(
        environment["dependencies"],
        frozenset({"numpy", "tenpy"}),
        "$raw.environment.dependencies",
    )
    for name, version in dependencies.items():
        _string(version, f"$raw.environment.dependencies.{name}")
    environment_content = {
        key: value for key, value in environment.items() if key != "environment_digest"
    }
    if environment["environment_digest"] != canonical_digest(environment_content):
        _fail(
            "PROVENANCE_MISMATCH",
            "Raw environment digest does not match canonical content",
            field="$raw.environment.environment_digest",
            exit_code=3,
        )

    observables = _object(
        result["observables"],
        frozenset(request["requested_observables"]),  # type: ignore[arg-type]
        "$raw.observables",
    )
    statuses = route["observable_statuses"]
    assert isinstance(statuses, dict)
    for name, raw_observable in observables.items():
        field = f"$raw.observables.{name}"
        observable = _object(
            raw_observable,
            frozenset({"status", "value", "units", "normalization", "reason"}),
            field,
        )
        expected_status = statuses[name]
        if observable["status"] != expected_status:
            _fail(
                "OBSERVABLE_STATUS_INVALID",
                "Raw observable status violates the exact route contract",
                field=f"{field}.status",
                exit_code=3,
            )
        if observable["units"] is not None:
            _string(observable["units"], f"{field}.units")
        if observable["normalization"] is not None:
            _string(observable["normalization"], f"{field}.normalization")
        if expected_status == "backend_limited":
            if observable["value"] is not None or not isinstance(
                observable["reason"], str
            ):
                _fail(
                    "OBSERVABLE_STATUS_INVALID",
                    "Backend-limited raw evidence requires a reason and no value",
                    field=field,
                    exit_code=3,
                )
        else:
            if observable["value"] is None or observable["reason"] is not None:
                _fail(
                    "OBSERVABLE_STATUS_INVALID",
                    "Measured or derived raw evidence requires a value and no reason",
                    field=field,
                    exit_code=3,
                )
            _validate_json_value(observable["value"], f"{field}.value")

    convergence = _array(result["convergence"], "$raw.convergence", minimum=2)
    prior_step: int | None = None
    for index, raw_point in enumerate(convergence):
        field = f"$raw.convergence[{index}]"
        point = _object(raw_point, frozenset({"step", "metrics"}), field)
        step = _integer(point["step"], f"{field}.step", minimum=0)
        if prior_step is not None and step <= prior_step:
            _fail(
                "VALUE_INVALID",
                "Raw convergence steps must be strictly increasing",
                field=f"{field}.step",
                exit_code=3,
            )
        prior_step = step
        metrics = point["metrics"]
        if type(metrics) is not dict or not metrics:
            _fail(
                "TYPE_MISMATCH",
                "Raw convergence metrics must be a nonempty object",
                field=f"{field}.metrics",
                exit_code=3,
            )
        for name, value in metrics.items():
            _string(name, f"{field}.metrics.key", identifier=True)
            if type(value) is not float:
                _fail(
                    "TYPE_MISMATCH",
                    "Raw convergence metrics must be exact floats",
                    field=f"{field}.metrics.{name}",
                    exit_code=3,
                )
            _number(value, f"{field}.metrics.{name}")
    for name in ("warnings", "known_limitations"):
        _unique_strings(result[name], f"$raw.{name}")
    if result["known_limitations"] != route["known_limitations"]:
        _fail(
            "PROVENANCE_MISMATCH",
            "Raw result limitations do not match the promoted route",
            field="$raw.known_limitations",
            exit_code=3,
        )
    return result


def _reconstruct_backend_bundle(
    *,
    request_digest: str,
    binding: Mapping[str, object],
    raw: Mapping[str, object],
    execution: Mapping[str, object],
    raw_artifact: Mapping[str, object],
) -> dict[str, object]:
    raw_observables = raw["observables"]
    raw_convergence = raw["convergence"]
    environment = raw["environment"]
    assert isinstance(raw_observables, dict)
    assert isinstance(raw_convergence, list)
    assert isinstance(environment, dict)
    observables = {
        name: {
            "schema_version": "tn-agent.observable-evidence.v1",
            "name": name,
            **value,
        }
        for name, value in sorted(raw_observables.items())
        if isinstance(value, dict)
    }
    convergence = [
        {
            "schema_version": "tn-agent.convergence-point.v1",
            "step": point["step"],
            "metrics": point["metrics"],
        }
        for point in raw_convergence
        if isinstance(point, dict)
    ]
    limited = [
        name
        for name, value in sorted(raw_observables.items())
        if isinstance(value, dict) and value["status"] == "backend_limited"
    ]
    content: dict[str, object] = {
        "schema_version": BACKEND_RESULT_SCHEMA,
        "request_digest": request_digest,
        "binding": binding,
        "backend": {
            "schema_version": "tn-agent.backend-identity.v1",
            "backend_id": raw["backend_id"],
            "backend_version": raw["backend_version"],
            "adapter_id": raw["adapter_id"],
            "adapter_version": raw["adapter_version"],
        },
        "environment": {
            "schema_version": "tn-agent.environment-identity.v1",
            "environment_digest": environment["environment_digest"],
            "runtime_id": environment["runtime_id"],
            "runtime_version": environment["runtime_version"],
            "dependencies": environment["dependencies"],
        },
        "execution": execution,
        "observables": observables,
        "convergence": convergence,
        "diagnostics": [],
        "provenance": {
            "schema_version": "tn-agent.provenance-evidence.v1",
            "plan_id": raw["plan_id"],
            "capability_id": binding["capability_id"],
            "adapter_id": binding["adapter_id"],
            "raw_result_relative": raw_artifact["relative_path"],
        },
        "artifacts": [
            {
                "schema_version": "tn-agent.result-artifact.v1",
                "relative_path": raw_artifact["relative_path"],
                "digest": raw_artifact["digest"],
                "media_type": raw_artifact["media_type"],
                "size_bytes": raw_artifact["size_bytes"],
            }
        ],
        "warnings": raw["warnings"],
        "known_limitations": raw["known_limitations"],
        "backend_limited_fields": limited,
    }
    return {**content, "result_digest": canonical_digest(content)}


def _run_energy_metrics(
    raw: Mapping[str, object],
    *,
    field: str,
) -> tuple[float, float]:
    observables = raw["observables"]
    convergence = raw["convergence"]
    assert isinstance(observables, dict)
    assert isinstance(convergence, list)
    previous = convergence[-2]
    latest = convergence[-1]
    assert isinstance(previous, dict)
    assert isinstance(latest, dict)
    previous_metrics = previous["metrics"]
    latest_metrics = latest["metrics"]
    assert isinstance(previous_metrics, dict)
    assert isinstance(latest_metrics, dict)
    energy_observable = observables["energy"]
    assert isinstance(energy_observable, dict)
    energy = _number(
        energy_observable["value"],
        f"{field}.observables.energy.value",
    )
    latest_energy = _number(
        latest_metrics.get("energy"),
        f"{field}.convergence[-1].metrics.energy",
    )
    previous_energy = _number(
        previous_metrics.get("energy"),
        f"{field}.convergence[-2].metrics.energy",
    )
    if energy != latest_energy:
        _fail(
            "VALIDATOR_STATUS_INVALID",
            "Final convergence energy does not match the energy observable",
            field=f"{field}.convergence[-1].metrics.energy",
            exit_code=3,
        )
    energy_drift = abs(latest_energy - previous_energy)
    reported_energy_drift = latest_metrics.get("energy_drift")
    if reported_energy_drift is not None:
        reported = _number(
            reported_energy_drift,
            f"{field}.convergence[-1].metrics.energy_drift",
            minimum=0.0,
        )
        if reported != energy_drift:
            _fail(
                "VALIDATOR_STATUS_INVALID",
                "Reported energy drift conflicts with the derived energy delta",
                field=f"{field}.convergence[-1].metrics.energy_drift",
                exit_code=3,
            )
    return energy, energy_drift


def _validate_energy_reference(
    raw: bytes,
    *,
    experiment: Mapping[str, object],
) -> dict[str, object]:
    document = _strict_json_bytes(raw, "Energy reference")
    reference = experiment["reference"]
    binding = experiment["backend_binding"]
    assert isinstance(reference, dict)
    assert isinstance(binding, dict)
    content = _object(
        document,
        frozenset(
            {
                "schema_version",
                "reference_id",
                "capability_id",
                "physics_digest",
                "observable",
                "value",
                "units",
                "normalization",
                "method",
                "citation",
                "result_digest",
            }
        ),
        "$energy_reference",
    )
    _expect(
        content["schema_version"],
        "wangtheophys.tn-energy-reference.v1",
        "$energy_reference.schema_version",
    )
    _string(content["reference_id"], "$energy_reference.reference_id", identifier=True)
    _expect(
        content["capability_id"],
        binding["capability_id"],
        "$energy_reference.capability_id",
    )
    _expect(
        content["physics_digest"],
        canonical_digest(experiment["physics"]),
        "$energy_reference.physics_digest",
    )
    for name in ("observable", "value", "units", "normalization"):
        _expect(
            content[name],
            reference[name],
            f"$energy_reference.{name}",
        )
    _number(content["value"], "$energy_reference.value")
    _string(content["method"], "$energy_reference.method", identifier=True)
    _string(content["citation"], "$energy_reference.citation")
    semantic_content = {
        key: value for key, value in content.items() if key != "result_digest"
    }
    if content["result_digest"] != canonical_digest(semantic_content):
        _fail(
            "RESULT_DIGEST_MISMATCH",
            "Energy-reference semantic digest is inconsistent",
            field="$energy_reference.result_digest",
            exit_code=3,
        )
    return content


def _derived_validator_results(
    raw: Mapping[str, object],
    *,
    repeat_raw: Mapping[str, object],
    reference: Mapping[str, object],
) -> list[dict[str, object]]:
    observables = raw["observables"]
    convergence = raw["convergence"]
    assert isinstance(observables, dict)
    assert isinstance(convergence, list)
    latest = convergence[-1]
    assert isinstance(latest, dict)
    latest_metrics = latest["metrics"]
    assert isinstance(latest_metrics, dict)
    variance_observable = observables["variance"]
    assert isinstance(variance_observable, dict)
    energy, energy_drift = _run_energy_metrics(raw, field="$raw")
    repeat_energy, _repeat_energy_drift = _run_energy_metrics(
        repeat_raw,
        field="$repeat_raw",
    )

    def residual(name: str) -> float:
        value = _number(
            latest_metrics.get(name),
            f"$raw.convergence[-1].metrics.{name}",
            minimum=0.0,
        )
        return value

    reference_energy = _number(
        reference["value"],
        "$energy_reference.value",
    )
    variance_value: object
    variance_metric: object
    if variance_observable["status"] == "backend_limited":
        variance_metric = None
        variance_value = None
    else:
        variance_metric = "variance"
        variance_value = _number(
            variance_observable["value"],
            "$raw.observables.variance.value",
            minimum=0.0,
        )
    return [
        {
            "id": "parse_consistency",
            "metric": None,
            "value": None,
            "source": "gate.primary_and_repeat_bundle_reconstruction",
        },
        {
            "id": "convergence",
            "metric": "energy_drift",
            "value": energy_drift,
            "source": "gate.primary_raw.convergence.energy_delta",
        },
        {
            "id": "variance",
            "metric": variance_metric,
            "value": variance_value,
            "source": "reported.primary_raw.observables.variance",
        },
        {
            "id": "canonical_form",
            "metric": "canonical_residual",
            "value": residual("canonical_residual"),
            "source": "reported.primary_raw.convergence.canonical_residual",
        },
        {
            "id": "symmetry_check",
            "metric": "symmetry_residual",
            "value": residual("symmetry_residual"),
            "source": "reported.primary_raw.convergence.symmetry_residual",
        },
        {
            "id": "benchmark_compare",
            "metric": "benchmark_delta",
            "value": abs(energy - reference_energy),
            "source": "gate.primary_energy_vs_preregistered_reference",
        },
        {
            "id": "reproducibility",
            "metric": "reproduction_delta",
            "value": abs(energy - repeat_energy),
            "source": "reported.primary_energy_vs_repeat_raw",
        },
        {
            "id": "artifact_completeness",
            "metric": "missing_artifacts",
            "value": 0,
            "source": "verified.required_artifact_roles",
        },
    ]


def _validate_validator_evidence(
    raw: bytes,
    *,
    request_digest: str,
    backend_result_digest: str,
    repeat_backend_result_digest: str,
    reference_artifact_digest: str,
    derived_results: list[dict[str, object]],
) -> dict[str, object]:
    document = _strict_json_bytes(raw, "Validator evidence")
    evidence = _object(
        document,
        frozenset(
            {
                "schema_version",
                "request_digest",
                "backend_result_digest",
                "repeat_backend_result_digest",
                "reference_artifact_digest",
                "results",
                "result_digest",
            }
        ),
        "$validator_evidence",
    )
    expected_content = {
        "schema_version": "wangtheophys.tn-validator-evidence.v1",
        "request_digest": request_digest,
        "backend_result_digest": backend_result_digest,
        "repeat_backend_result_digest": repeat_backend_result_digest,
        "reference_artifact_digest": reference_artifact_digest,
        "results": derived_results,
    }
    expected = {
        **expected_content,
        "result_digest": canonical_digest(expected_content),
    }
    if canonical_digest(evidence) != canonical_digest(expected):
        _fail(
            "VALIDATOR_STATUS_INVALID",
            "Validator evidence does not match the gate-derived evaluation",
            field="$validator_evidence",
            exit_code=3,
        )
    return expected


def _evaluate_artifact_chain(
    *,
    experiment: Mapping[str, object],
    experiment_digest: str,
    evidence: Mapping[str, object],
    artifacts_by_role: Mapping[str, Mapping[str, object]],
    verified_artifacts: Mapping[str, bytes],
) -> dict[str, object]:
    binding = experiment["backend_binding"]
    assert isinstance(binding, dict)
    expected_plan_id = _expected_plan_id(experiment, experiment_digest)
    expected_request = _expected_request(
        experiment,
        experiment_digest,
        expected_plan_id,
    )
    request_artifact = artifacts_by_role["backend_request"]
    request_document = _strict_json_bytes(
        verified_artifacts[str(request_artifact["digest"])],
        "Backend request",
    )
    if canonical_digest(request_document) != canonical_digest(expected_request):
        _fail(
            "PROVENANCE_MISMATCH",
            "Backend request does not match the canonical promoted request",
            field="$request",
            exit_code=3,
        )
    request_digest = canonical_digest(expected_request)
    raw_artifact = artifacts_by_role["backend_raw_result"]
    route = ROUTES[str(binding["capability_id"])]
    raw_result = _validate_raw_result(
        verified_artifacts[str(raw_artifact["digest"])],
        request=expected_request,
        request_digest=request_digest,
        binding=binding,
        route=route,
    )
    execution = evidence["execution"]
    repeat_execution = evidence["repeat_execution"]
    assert isinstance(execution, dict)
    assert isinstance(repeat_execution, dict)
    stdout_artifact = artifacts_by_role["backend_stdout"]
    stderr_artifact = artifacts_by_role["backend_stderr"]
    if (
        execution["stdout_digest"] != stdout_artifact["digest"]
        or execution["stderr_digest"] != stderr_artifact["digest"]
    ):
        _fail(
            "PROVENANCE_MISMATCH",
            "Execution stream identities do not match verified artifacts",
            field="$.execution",
            exit_code=3,
        )
    repeat_stdout_artifact = artifacts_by_role["backend_repeat_stdout"]
    repeat_stderr_artifact = artifacts_by_role["backend_repeat_stderr"]
    if (
        repeat_execution["stdout_digest"] != repeat_stdout_artifact["digest"]
        or repeat_execution["stderr_digest"] != repeat_stderr_artifact["digest"]
    ):
        _fail(
            "PROVENANCE_MISMATCH",
            "Repeat execution stream identities do not match verified artifacts",
            field="$.repeat_execution",
            exit_code=3,
        )
    reconstructed = _reconstruct_backend_bundle(
        request_digest=request_digest,
        binding=binding,
        raw=raw_result,
        execution=execution,
        raw_artifact=raw_artifact,
    )
    backend_artifact = artifacts_by_role["backend_result"]
    submitted = _strict_json_bytes(
        verified_artifacts[str(backend_artifact["digest"])],
        "Normalized backend result",
    )
    _validate_reconstructed_shape(submitted, reconstructed, "$backend_result")
    if canonical_digest(submitted) != canonical_digest(reconstructed):
        _fail(
            "RESULT_DIGEST_MISMATCH",
            "Normalized backend result does not match gate reconstruction",
            field="$backend_result",
            exit_code=3,
        )

    repeat_raw_artifact = artifacts_by_role["backend_repeat_raw_result"]
    if repeat_raw_artifact["digest"] == raw_artifact["digest"]:
        _fail(
            "PROVENANCE_MISMATCH",
            "Repeat evidence cannot reuse the primary raw-result identity",
            field="$.artifacts.backend_repeat_raw_result",
            exit_code=3,
        )
    repeat_raw_result = _validate_raw_result(
        verified_artifacts[str(repeat_raw_artifact["digest"])],
        request=expected_request,
        request_digest=request_digest,
        binding=binding,
        route=route,
    )
    repeat_reconstructed = _reconstruct_backend_bundle(
        request_digest=request_digest,
        binding=binding,
        raw=repeat_raw_result,
        execution=repeat_execution,
        raw_artifact=repeat_raw_artifact,
    )
    repeat_backend_artifact = artifacts_by_role["backend_repeat_result"]
    repeat_submitted = _strict_json_bytes(
        verified_artifacts[str(repeat_backend_artifact["digest"])],
        "Repeat normalized backend result",
    )
    _validate_reconstructed_shape(
        repeat_submitted,
        repeat_reconstructed,
        "$repeat_backend_result",
    )
    if canonical_digest(repeat_submitted) != canonical_digest(repeat_reconstructed):
        _fail(
            "RESULT_DIGEST_MISMATCH",
            "Repeat normalized result does not match gate reconstruction",
            field="$repeat_backend_result",
            exit_code=3,
        )

    reference_artifact = artifacts_by_role["energy_reference"]
    experiment_reference = experiment["reference"]
    assert isinstance(experiment_reference, dict)
    reference_source = experiment_reference["source"]
    assert isinstance(reference_source, dict)
    if (
        reference_source["uri"] != reference_artifact["relative_path"]
        or reference_source["sha256"] != reference_artifact["digest"]
    ):
        _fail(
            "PROVENANCE_MISMATCH",
            "Energy-reference artifact does not match preregistered source identity",
            field="$.reference.source",
            exit_code=3,
        )
    energy_reference = _validate_energy_reference(
        verified_artifacts[str(reference_artifact["digest"])],
        experiment=experiment,
    )

    derived_results = _derived_validator_results(
        raw_result,
        repeat_raw=repeat_raw_result,
        reference=energy_reference,
    )
    validator_artifact = artifacts_by_role["validator_evidence"]
    validator_evidence = _validate_validator_evidence(
        verified_artifacts[str(validator_artifact["digest"])],
        request_digest=request_digest,
        backend_result_digest=str(reconstructed["result_digest"]),
        repeat_backend_result_digest=str(repeat_reconstructed["result_digest"]),
        reference_artifact_digest=str(reference_artifact["digest"]),
        derived_results=derived_results,
    )
    provenance = evidence["provenance"]
    assert isinstance(provenance, dict)
    if (
        provenance["plan_id"] != expected_plan_id
        or provenance["request_digest"] != request_digest
        or provenance["backend_result_digest"] != backend_artifact["digest"]
        or provenance["repeat_backend_result_digest"]
        != repeat_backend_artifact["digest"]
    ):
        _fail(
            "PROVENANCE_MISMATCH",
            "Evidence provenance does not match the reconstructed artifact chains",
            field="$.provenance",
            exit_code=3,
        )
    return {
        "observables": reconstructed["observables"],
        "validator_metrics": {str(item["id"]): item for item in derived_results},
        "backend_artifact_digest": backend_artifact["digest"],
        "validator_artifact_digest": validator_artifact["digest"],
        "backend_result_digest": reconstructed["result_digest"],
        "validator_result_digest": validator_evidence["result_digest"],
    }


def evaluate(
    experiment: object,
    evidence: object,
    *,
    artifact_root: Path,
) -> dict[str, object]:
    """Evaluate normalized evidence against the preregistered experiment."""

    experiment_summary = validate_experiment(experiment)
    if experiment_summary["problem_status"] == "candidate":
        _fail(
            "SCIENTIFIC_EVIDENCE_UNATTESTED",
            "Candidate evidence lacks a trusted execution or state certificate",
            field="$.problem.status",
            exit_code=3,
        )
    experiment_root = experiment
    assert isinstance(experiment_root, dict)
    evidence_root = _validate_evidence(evidence)
    if evidence_root["experiment_digest"] != experiment_summary["experiment_digest"]:
        _fail(
            "EXPERIMENT_DIGEST_MISMATCH",
            "Evidence does not bind the canonical experiment",
            field="$.experiment_digest",
            exit_code=3,
        )
    if evidence_root["binding"] != experiment_root["backend_binding"]:
        _fail(
            "BINDING_MISMATCH",
            "Evidence binding does not match the experiment",
            field="$.binding",
            exit_code=3,
        )
    digest_content = {
        key: value for key, value in evidence_root.items() if key != "result_digest"
    }
    if evidence_root["result_digest"] != canonical_digest(digest_content):
        _fail(
            "RESULT_DIGEST_MISMATCH",
            "Evidence result digest does not match canonical content",
            field="$.result_digest",
            exit_code=3,
        )

    acceptance = experiment_root["acceptance"]
    execution = evidence_root["execution"]
    repeat_execution = evidence_root["repeat_execution"]
    assert isinstance(acceptance, dict)
    assert isinstance(execution, dict)
    assert isinstance(repeat_execution, dict)
    if acceptance["require_execution_success"]:
        for label, execution_record in (
            ("Primary", execution),
            ("Repeat", repeat_execution),
        ):
            if not (
                execution_record["status"] == "succeeded"
                and execution_record["return_code"] == 0
                and execution_record["retryable"] is False
            ):
                _fail(
                    "EXECUTION_NOT_SUCCEEDED",
                    f"{label} execution evidence is not a successful terminal result",
                    exit_code=3,
                )

    verified_artifacts = _verify_artifacts(
        evidence_root["artifacts"],
        artifact_root,
    )
    artifacts = evidence_root["artifacts"]
    assert isinstance(artifacts, list)
    artifacts_by_role = {
        str(item["role"]): item for item in artifacts if isinstance(item, dict)
    }
    evaluated_chain = _evaluate_artifact_chain(
        experiment=experiment_root,
        experiment_digest=str(experiment_summary["experiment_digest"]),
        evidence=evidence_root,
        artifacts_by_role=artifacts_by_role,
        verified_artifacts=verified_artifacts,
    )
    normalized_observables = evaluated_chain["observables"]
    normalized_metrics = evaluated_chain["validator_metrics"]
    backend_artifact_digest = evaluated_chain["backend_artifact_digest"]
    validator_artifact_digest = evaluated_chain["validator_artifact_digest"]
    assert isinstance(normalized_observables, dict)
    assert isinstance(normalized_metrics, dict)
    assert isinstance(backend_artifact_digest, str)
    assert isinstance(validator_artifact_digest, str)

    expected_observables = experiment_root["observables"]
    observable_results = evidence_root["observables"]
    assert isinstance(expected_observables, list)
    assert isinstance(observable_results, list)
    actual_observables = {
        str(item["name"]): item for item in observable_results if isinstance(item, dict)
    }
    if set(actual_observables) != set(expected_observables):
        _fail(
            "OBSERVABLE_SET_MISMATCH",
            "Evidence observable set does not match the experiment",
            exit_code=3,
        )
    capability = experiment_root["capability"]
    assert isinstance(capability, dict)
    route = ROUTES[str(capability["capability_id"])]
    observable_statuses = route["observable_statuses"]
    assert isinstance(observable_statuses, dict)
    for name, item in actual_observables.items():
        expected_status = observable_statuses[name]
        normalized_item = normalized_observables[name]
        assert isinstance(normalized_item, dict)
        if (
            item["status"] != expected_status
            or item["status"] != normalized_item["status"]
        ):
            _fail(
                "OBSERVABLE_STATUS_INVALID",
                "Observable status violates the route contract",
                field=f"$.observables.{name}",
                exit_code=3,
            )
        if item["evidence_digest"] != backend_artifact_digest:
            _fail(
                "EVIDENCE_ARTIFACT_MISSING",
                "Observable evidence must identify the normalized backend result",
                field=f"$.observables.{name}.evidence_digest",
                exit_code=3,
            )

    validator_specs = experiment_root["validators"]
    validator_results = evidence_root["validator_results"]
    assert isinstance(validator_specs, list)
    assert isinstance(validator_results, list)
    spec_by_id = {
        str(item["id"]): item for item in validator_specs if isinstance(item, dict)
    }
    result_by_id = {
        str(item["id"]): item for item in validator_results if isinstance(item, dict)
    }
    if set(result_by_id) != set(spec_by_id):
        _fail(
            "VALIDATOR_SET_MISMATCH",
            "Validator result set does not match the experiment",
            exit_code=3,
        )
    for validator_id, spec in spec_by_id.items():
        result = result_by_id[validator_id]
        normalized_metric = normalized_metrics[validator_id]
        assert isinstance(normalized_metric, dict)
        if result["evidence_digest"] != validator_artifact_digest:
            _fail(
                "EVIDENCE_ARTIFACT_MISSING",
                "Validator result must identify the separate validator evidence",
                field=f"$.validator_results.{validator_id}.evidence_digest",
                exit_code=3,
            )
        if spec["policy"] == "backend_limited":
            if not (
                result["status"] == "backend_limited"
                and result["reason_code"] == "BACKEND_LIMITED"
                and result["metric_value"] is None
            ):
                _fail(
                    "VALIDATOR_STATUS_INVALID",
                    "Backend-limited validator evidence is inconsistent",
                    field=f"$.validator_results.{validator_id}",
                    exit_code=3,
                )
            continue
        if spec["policy"] == "reported_only":
            _validate_metric_domain(
                validator_id,
                result["metric_value"],
                f"$.validator_results.{validator_id}.metric_value",
            )
            if (
                type(result["metric_value"]) is not type(normalized_metric["value"])
                or result["metric_value"] != normalized_metric["value"]
                or result["status"] != "reported_only"
                or result["reason_code"] != "REPORTED_ONLY"
            ):
                _fail(
                    "VALIDATOR_STATUS_INVALID",
                    "Reported-only diagnostic does not match the bound raw report",
                    field=f"$.validator_results.{validator_id}",
                    exit_code=3,
                )
            continue
        _validate_metric_domain(
            validator_id,
            result["metric_value"],
            f"$.validator_results.{validator_id}.metric_value",
        )
        if (
            type(result["metric_value"]) is not type(normalized_metric["value"])
            or result["metric_value"] != normalized_metric["value"]
        ):
            _fail(
                "VALIDATOR_STATUS_INVALID",
                "Validator metric does not match the gate-derived evaluation",
                field=f"$.validator_results.{validator_id}.metric_value",
                exit_code=3,
            )
        if not (
            result["status"] == "pass" and result["reason_code"] == "VALIDATOR_PASS"
        ):
            _fail(
                "VALIDATOR_FAILED",
                "A required validator did not pass",
                field=f"$.validator_results.{validator_id}",
                exit_code=3,
            )
        _evaluate_threshold(validator_id, spec, result)

    return {
        "ok": True,
        "accepted": True,
        "reason_code": "ACCEPTANCE_PASSED",
        "problem_id": experiment_summary["problem_id"],
        "problem_status": experiment_summary["problem_status"],
        "capability_id": experiment_summary["capability_id"],
        "experiment_digest": experiment_summary["experiment_digest"],
        "result_digest": evidence_root["result_digest"],
        "verified_artifacts": len(artifacts),
    }


def _evaluate_threshold(
    validator_id: str,
    spec: Mapping[str, object],
    result: Mapping[str, object],
) -> None:
    metric = spec["metric"]
    value = result["metric_value"]
    if metric is None:
        if value is not None:
            _fail(
                "VALIDATOR_STATUS_INVALID",
                "Metric-free validator supplied a metric value",
                field=f"$.validator_results.{validator_id}.metric_value",
                exit_code=3,
            )
        return
    if type(value) not in {int, float}:
        _fail(
            "VALIDATOR_STATUS_INVALID",
            "Validator metric value is missing",
            field=f"$.validator_results.{validator_id}.metric_value",
            exit_code=3,
        )
    _validate_metric_domain(
        validator_id,
        value,
        f"$.validator_results.{validator_id}.metric_value",
    )
    threshold = float(spec["threshold"])  # type: ignore[arg-type]
    observed = float(value)
    operator = spec["operator"]
    passed = (
        (operator == "max" and observed <= threshold)
        or (operator == "min" and observed >= threshold)
        or (operator == "equals" and observed == threshold)
    )
    if not passed:
        _fail(
            "VALIDATOR_THRESHOLD_FAILED",
            "Validator metric violates its preregistered threshold",
            field=f"$.validator_results.{validator_id}.metric_value",
            exit_code=3,
        )


def _verify_artifacts(value: object, artifact_root: Path) -> dict[str, bytes]:
    artifacts = _array(value, "$.artifacts", minimum=1)
    root_descriptor = _open_artifact_root(artifact_root)
    total = 0
    artifacts_by_digest: dict[str, bytes] = {}
    try:
        for item in artifacts:
            assert isinstance(item, dict)
            relative = str(item["relative_path"])
            _validate_relative_path(relative, "$.artifacts.relative_path")
            declared_size = int(item["size_bytes"])
            if declared_size > MAX_ARTIFACT_BYTES:
                _fail(
                    "ARTIFACT_LIMIT_EXCEEDED",
                    "Declared artifact size exceeds the limit",
                    exit_code=3,
                )
            raw = _read_artifact_file(
                root_descriptor,
                relative,
                MAX_ARTIFACT_BYTES,
            )
            total += len(raw)
            if total > MAX_ARTIFACT_TOTAL_BYTES:
                _fail(
                    "ARTIFACT_LIMIT_EXCEEDED",
                    "Artifact aggregate size exceeds the limit",
                    exit_code=3,
                )
            observed = "sha256:" + hashlib.sha256(raw).hexdigest()
            if len(raw) != declared_size or observed != item["digest"]:
                _fail(
                    "ARTIFACT_DIGEST_MISMATCH",
                    "Artifact bytes do not match the declared identity",
                    exit_code=3,
                )
            artifacts_by_digest[observed] = raw
    finally:
        os.close(root_descriptor)
    return artifacts_by_digest


def _validate_relative_path(value: str, field: str) -> None:
    path = PurePosixPath(value)
    if (
        not value
        or value == "."
        or not path.parts
        or path.is_absolute()
        or value != path.as_posix()
        or "\\" in value
        or value.startswith("/")
        or any(
            ord(character) < 0x20
            or ord(character) == 0x7F
            or 0xD800 <= ord(character) <= 0xDFFF
            for character in value
        )
        or any(part in {"", ".", ".."} for part in path.parts)
        or (len(value) >= 2 and value[0].isalpha() and value[1] == ":")
    ):
        _fail(
            "ARTIFACT_UNSAFE_PATH",
            "Artifact path must be normalized and relative",
            field=field,
        )


def _open_artifact_root(root: Path) -> int:
    if (
        not hasattr(os, "O_NOFOLLOW")
        or not hasattr(os, "O_DIRECTORY")
        or os.open not in os.supports_dir_fd
    ):
        _fail(
            "SECURE_FILE_IO_UNAVAILABLE",
            "Secure component-wise artifact reads are unavailable",
            exit_code=3,
        )
    try:
        before = root.lstat()
    except (OSError, ValueError, UnicodeError):
        _fail("ARTIFACT_IO_ERROR", "Artifact root cannot be inspected", exit_code=3)
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISDIR(before.st_mode):
        _fail(
            "ARTIFACT_UNSAFE_PATH",
            "Artifact root must be a non-symlink directory",
            exit_code=3,
        )
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(root, flags)
        opened = os.fstat(descriptor)
    except (OSError, ValueError, UnicodeError):
        if descriptor is not None:
            os.close(descriptor)
        _fail("ARTIFACT_IO_ERROR", "Artifact root cannot be opened safely", exit_code=3)
    assert descriptor is not None
    if not stat.S_ISDIR(opened.st_mode) or not _same_file(before, opened):
        os.close(descriptor)
        _fail(
            "ARTIFACT_UNSAFE_PATH",
            "Artifact root changed before it was opened",
            exit_code=3,
        )
    return descriptor


def _read_artifact_file(root: int | Path, relative: str, limit: int) -> bytes:
    """Open every artifact path component relative to directory descriptors."""

    _validate_relative_path(relative, "$.artifacts.relative_path")
    if (
        not hasattr(os, "O_NOFOLLOW")
        or not hasattr(os, "O_DIRECTORY")
        or os.open not in os.supports_dir_fd
    ):
        _fail(
            "SECURE_FILE_IO_UNAVAILABLE",
            "Secure component-wise artifact reads are unavailable",
            exit_code=3,
        )
    directory_descriptors: list[int] = []
    file_descriptor: int | None = None
    owned_root: int | None = None
    root_descriptor = root
    if isinstance(root, Path):
        owned_root = _open_artifact_root(root)
        root_descriptor = owned_root
    flags = (
        os.O_RDONLY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        current = os.dup(root_descriptor)
        directory_descriptors.append(current)
        components = PurePosixPath(relative).parts
        for component in components[:-1]:
            current = os.open(
                component,
                flags | os.O_DIRECTORY,
                dir_fd=current,
            )
            directory_descriptors.append(current)
        file_descriptor = os.open(
            components[-1],
            flags,
            dir_fd=current,
        )
        opened = os.fstat(file_descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            _fail(
                "ARTIFACT_UNSAFE_PATH",
                "Artifact must be a regular single-link non-symlink file",
                exit_code=3,
            )
        if opened.st_size > limit:
            _fail(
                "ARTIFACT_TOO_LARGE",
                "Artifact exceeds the byte limit",
                exit_code=3,
            )
        chunks: list[bytes] = []
        remaining = limit + 1
        while remaining:
            chunk = os.read(file_descriptor, min(remaining, READ_CHUNK_BYTES))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        final = os.fstat(file_descriptor)
    except GateError:
        raise
    except (OSError, ValueError, UnicodeError):
        _fail("ARTIFACT_IO_ERROR", "Artifact cannot be opened safely", exit_code=3)
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        for descriptor in reversed(directory_descriptors):
            os.close(descriptor)
        if owned_root is not None:
            os.close(owned_root)
    raw = b"".join(chunks)
    if len(raw) > limit:
        _fail(
            "ARTIFACT_TOO_LARGE",
            "Artifact exceeds the byte limit",
            exit_code=3,
        )
    if not _stable_file(opened, final):
        _fail(
            "ARTIFACT_UNSAFE_PATH",
            "Artifact changed while it was read",
            exit_code=3,
        )
    return raw


def validate_library(path: Path) -> dict[str, object]:
    """Validate an append-only JSONL heuristics library."""

    raw = _read_regular_file(path, MAX_DOCUMENT_BYTES, artifact=False)
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        _fail("DOCUMENT_INVALID_UTF8", "Library is not valid UTF-8")
    lines = text.splitlines()
    if not lines or any(not line.strip() for line in lines):
        _fail(
            "LIBRARY_RECORD_INVALID",
            "Library must contain one non-empty JSON object per line",
        )
    if len(lines) > MAX_LIBRARY_RECORDS:
        _fail("LIBRARY_RECORD_LIMIT", "Library record count exceeds the limit")
    records: list[dict[str, object]] = []
    for index, line in enumerate(lines):
        value = _strict_json_loads(line)
        try:
            record = _validate_heuristic_record(value, index)
        except GateError as error:
            if error.reason_code.startswith("DOCUMENT_"):
                raise
            _fail(
                "LIBRARY_RECORD_INVALID",
                "Library contains an invalid heuristic record",
                field=f"$line[{index + 1}]",
            )
        records.append(record)
    _validate_library_sequence(records)
    return {
        "ok": True,
        "reason_code": "OK",
        "schema_version": HEURISTIC_SCHEMA,
        "records": len(records),
        "heuristics": len({str(record["heuristic_id"]) for record in records}),
        "library_digest": canonical_digest(records),
    }


def _validate_heuristic_record(value: object, index: int) -> dict[str, object]:
    field = f"$line[{index + 1}]"
    record = _object(
        value,
        frozenset(
            {
                "schema_version",
                "record_id",
                "heuristic_id",
                "revision",
                "recorded_at",
                "applies_to",
                "claim",
                "action",
                "source",
                "evidence",
                "confidence",
                "contradicts",
                "supersedes",
                "claim_status",
            }
        ),
        field,
    )
    if record["schema_version"] != HEURISTIC_SCHEMA:
        _fail(
            "SCHEMA_VERSION_UNSUPPORTED",
            "Heuristic schema version is unsupported",
            field=f"{field}.schema_version",
        )
    record_id = _string(record["record_id"], f"{field}.record_id", identifier=True)
    heuristic_id = _string(
        record["heuristic_id"],
        f"{field}.heuristic_id",
        identifier=True,
    )
    revision = _integer(record["revision"], f"{field}.revision", minimum=1)
    if record_id != f"{heuristic_id}@{revision}":
        _fail(
            "VALUE_INVALID",
            "Record identity must be heuristic_id@revision",
            field=f"{field}.record_id",
        )
    _timestamp(record["recorded_at"], f"{field}.recorded_at")
    applies_to = _unique_strings(
        record["applies_to"],
        f"{field}.applies_to",
        minimum=1,
        identifiers=True,
    )
    if any(route != "*" and route not in ROUTES for route in applies_to):
        _fail(
            "VALUE_INVALID",
            "Heuristic names an unknown route",
            field=f"{field}.applies_to",
        )
    _string(record["claim"], f"{field}.claim")
    _string(record["action"], f"{field}.action")
    source = _object(
        record["source"],
        frozenset({"kind", "uri", "sha256", "citation"}),
        f"{field}.source",
    )
    if source["kind"] != "repository_skill":
        _fail(
            "VALUE_INVALID",
            "Heuristic source must be a repository-grounded skill",
            field=f"{field}.source.kind",
        )
    source_uri = _string(source["uri"], f"{field}.source.uri")
    _validate_library_kind_uri(
        kind="repository_skill",
        uri=source_uri,
        field=f"{field}.source",
    )
    source_digest = _digest(source["sha256"], f"{field}.source.sha256")
    _validate_grounded_library_file(
        root=REPOSITORY_ROOT,
        uri=source_uri,
        declared_digest=source_digest,
        field=f"{field}.source",
    )
    _string(source["citation"], f"{field}.source.citation")
    evidence = _object(
        record["evidence"],
        frozenset({"kind", "summary", "uri", "sha256"}),
        f"{field}.evidence",
    )
    evidence_kind = _string(
        evidence["kind"],
        f"{field}.evidence.kind",
        identifier=True,
    )
    if evidence_kind in {"method_card", "workflow_card"}:
        evidence_root = REPOSITORY_ROOT
    elif evidence_kind == "contract_audit":
        evidence_root = TEAM_ROOT
    else:
        _fail(
            "VALUE_INVALID",
            "Heuristic evidence kind is not grounded by this contract",
            field=f"{field}.evidence.kind",
        )
    _string(evidence["summary"], f"{field}.evidence.summary")
    evidence_uri = _string(evidence["uri"], f"{field}.evidence.uri")
    _validate_library_kind_uri(
        kind=evidence_kind,
        uri=evidence_uri,
        field=f"{field}.evidence",
    )
    evidence_digest = _digest(
        evidence["sha256"],
        f"{field}.evidence.sha256",
    )
    _validate_grounded_library_file(
        root=evidence_root,
        uri=evidence_uri,
        declared_digest=evidence_digest,
        field=f"{field}.evidence",
    )
    confidence = _object(
        record["confidence"],
        frozenset({"level", "score", "basis"}),
        f"{field}.confidence",
    )
    if confidence["level"] not in {"low", "medium", "high"}:
        _fail(
            "VALUE_INVALID",
            "Confidence level is invalid",
            field=f"{field}.confidence.level",
        )
    score = _number(
        confidence["score"],
        f"{field}.confidence.score",
        minimum=0.0,
        maximum=1.0,
    )
    expected_level = "low" if score < 0.5 else "medium" if score < 0.8 else "high"
    if confidence["level"] != expected_level:
        _fail(
            "VALUE_INVALID",
            "Confidence level does not match its score",
            field=f"{field}.confidence",
        )
    _string(confidence["basis"], f"{field}.confidence.basis")
    record["contradicts"] = _unique_strings(
        record["contradicts"],
        f"{field}.contradicts",
        identifiers=True,
    )
    record["supersedes"] = _unique_strings(
        record["supersedes"],
        f"{field}.supersedes",
        identifiers=True,
    )
    if set(record["contradicts"]) & set(record["supersedes"]):
        _fail(
            "VALUE_INVALID",
            "A record cannot both contradict and supersede the same record",
            field=field,
        )
    if record["claim_status"] not in {"working", "retired"}:
        _fail(
            "VALUE_INVALID",
            "Claim status is invalid",
            field=f"{field}.claim_status",
        )
    return record


def _validate_library_kind_uri(*, kind: str, uri: str, field: str) -> None:
    if kind in {"repository_skill", "method_card", "workflow_card"}:
        pattern = SKILL_URI_PATTERN
    elif kind == "contract_audit":
        pattern = AUDIT_URI_PATTERN
    else:
        _fail(
            "LIBRARY_RECORD_INVALID",
            "Library kind is not associated with a public path class",
            field=f"{field}.kind",
        )
    if pattern.fullmatch(uri) is None:
        _fail(
            "LIBRARY_RECORD_INVALID",
            "Library kind and path do not match",
            field=f"{field}.uri",
        )


def _validate_grounded_library_file(
    *,
    root: Path,
    uri: str,
    declared_digest: str,
    field: str,
) -> None:
    _validate_relative_path(uri, f"{field}.uri")
    raw = _read_artifact_file(root, uri, MAX_ARTIFACT_BYTES)
    observed_digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    if observed_digest != declared_digest:
        _fail(
            "LIBRARY_RECORD_INVALID",
            "Grounded Library file digest does not match its content",
            field=f"{field}.sha256",
        )


def _validate_library_sequence(records: Sequence[dict[str, object]]) -> None:
    seen: set[str] = set()
    latest_revision: dict[str, int] = {}
    latest_record: dict[str, str] = {}
    latest_timestamp: str | None = None
    for record in records:
        record_id = str(record["record_id"])
        heuristic_id = str(record["heuristic_id"])
        revision = int(record["revision"])
        recorded_at = str(record["recorded_at"])
        if latest_timestamp is not None and recorded_at < latest_timestamp:
            _fail(
                "LIBRARY_SEQUENCE_INVALID",
                "Library timestamps must be nondecreasing in append order",
            )
        if record_id in seen:
            _fail(
                "LIBRARY_SEQUENCE_INVALID",
                "Library record identifiers must be unique",
            )
        expected_revision = latest_revision.get(heuristic_id, 0) + 1
        if revision != expected_revision:
            _fail(
                "LIBRARY_SEQUENCE_INVALID",
                "Heuristic revisions must start at one and remain consecutive",
            )
        supersedes = set(record["supersedes"])  # type: ignore[arg-type]
        contradictions = set(record["contradicts"])  # type: ignore[arg-type]
        if not supersedes.issubset(seen) or not contradictions.issubset(seen):
            _fail(
                "LIBRARY_SEQUENCE_INVALID",
                "Contradiction and supersession references must point backward",
            )
        prior_record = latest_record.get(heuristic_id)
        if prior_record is None and supersedes:
            _fail(
                "LIBRARY_SEQUENCE_INVALID",
                "First revision cannot supersede another revision of itself",
            )
        if prior_record is not None and supersedes != {prior_record}:
            _fail(
                "LIBRARY_SEQUENCE_INVALID",
                "A new revision must supersede exactly its immediately prior revision",
            )
        seen.add(record_id)
        latest_revision[heuristic_id] = revision
        latest_record[heuristic_id] = record_id
        latest_timestamp = recorded_at


def _emit(payload: Mapping[str, object]) -> None:
    sys.stdout.write(
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )


class _GateArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        _fail("CLI_USAGE_ERROR", "Command-line arguments are invalid")


def _parser() -> argparse.ArgumentParser:
    parser = _GateArgumentParser(
        prog="tn-public-gate",
        description="Validate and evaluate the WangTheoPhys public TN contracts.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser(
        "validate", help="validate an experiment JSON file"
    )
    validate.add_argument("experiment", type=Path)
    evaluate_parser = subparsers.add_parser(
        "evaluate",
        help="evaluate evidence against a preregistered experiment",
    )
    evaluate_parser.add_argument("experiment", type=Path)
    evaluate_parser.add_argument("evidence", type=Path)
    evaluate_parser.add_argument("--artifact-root", type=Path, required=True)
    library = subparsers.add_parser(
        "validate-library",
        help="validate the append-only heuristics JSONL library",
    )
    library.add_argument("library", type=Path)
    digest = subparsers.add_parser("digest", help="print a strict document digest")
    digest.add_argument("document", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.command == "validate":
            result = validate_experiment(load_json_document(args.experiment))
        elif args.command == "evaluate":
            result = evaluate(
                load_json_document(args.experiment),
                load_json_document(args.evidence),
                artifact_root=args.artifact_root,
            )
        elif args.command == "validate-library":
            result = validate_library(args.library)
        else:
            result = {
                "ok": True,
                "reason_code": "OK",
                "digest": canonical_digest(load_json_document(args.document)),
            }
        _emit(result)
        return 0
    except GateError as error:
        _emit(error.as_dict())
        return error.exit_code
    # The public CLI is a fail-closed JSON boundary: unexpected implementation
    # failures are deliberately sanitized instead of exposing a traceback.
    except Exception:  # noqa: BLE001
        error = GateError(
            "INTERNAL_ERROR",
            "Gate encountered an unexpected internal error",
            exit_code=2,
        )
        _emit(error.as_dict())
        return error.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
