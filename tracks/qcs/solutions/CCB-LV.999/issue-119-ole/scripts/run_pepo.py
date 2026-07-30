#!/usr/bin/env python3
"""Run one deterministic full 49-site Heisenberg-picture PEPO cell."""

from __future__ import annotations

import argparse
import json
import math
from numbers import Integral, Real
from pathlib import Path
import re
import time
from typing import Callable

import numpy as np

from ole_pepo import PINNED_QUIMB_COMMIT
from ole_pepo.circuits import (
    CircuitProfile,
    get_circuit_profile,
    load_circuit_protocol,
)
from ole_pepo.contraction import normalized_overlap_compressed
from ole_pepo.engine import (
    EvolutionDiagnostics,
    ProgressRecord,
    build_pepo_circuit,
)
from ole_pepo.qasm import (
    OLEProtocol,
    read_validated_qasm,
    replace_perturbations,
)
from ole_pepo.records import (
    atomic_write_json,
    confirmation_token,
    core_source_digest,
    peak_rss_bytes,
)


OLE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = OLE_ROOT.parents[4]
BASELINE_PROFILE = get_circuit_profile("baseline")
QASM_PATH = OLE_ROOT / BASELINE_PROFILE.qasm_relative_path
EXPECTED_QASM_SHA256 = BASELINE_PROFILE.qasm_sha256
EXPECTED_QASM_BYTES = BASELINE_PROFILE.qasm_bytes
DEFAULT_ORACLE_MANIFEST = WORKSPACE_ROOT / (
    f"results/{BASELINE_PROFILE.oracle_run_name}/manifest.json"
)
OBSERVABLE_SITES = (52, 59, 72)
RESULT_TOLERANCE = 1.0e-8
DEFAULT_EVOLUTION_CUTOFF = 1.0e-10
DEFAULT_CONTRACTION_CUTOFF = 1.0e-10
RUN_ROOT_PATTERN = re.compile(r"^issue119-pepo-.+$")
Z = np.diag([1.0, -1.0]).astype(np.complex128)

EvolutionFunction = Callable[..., tuple[complex, EvolutionDiagnostics]]


def _positive_integer(text: str) -> int:
    value = int(text)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def _nonnegative_finite(text: str) -> float:
    value = float(text)
    if not math.isfinite(value) or value < 0:
        raise argparse.ArgumentTypeError("must be finite and nonnegative")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dop", type=_positive_integer, required=True)
    parser.add_argument("--chi-env", type=_positive_integer, required=True)
    parser.add_argument("--delta", type=float, choices=(0.0, 0.15), required=True)
    parser.add_argument(
        "--circuit",
        choices=("baseline", "active"),
        default="baseline",
    )
    parser.add_argument(
        "--evolution-cutoff",
        type=_nonnegative_finite,
        default=DEFAULT_EVOLUTION_CUTOFF,
    )
    parser.add_argument(
        "--contraction-cutoff",
        type=_nonnegative_finite,
        default=DEFAULT_CONTRACTION_CUTOFF,
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--oracle-manifest",
        type=Path,
        default=None,
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm")
    return parser


def confined_output_path(path: str | Path) -> Path:
    """Resolve one output below repo-root results/issue119-pepo-*."""
    requested = Path(path)
    if ".." in requested.parts:
        raise ValueError("--output must not contain '..'")
    candidate = requested if requested.is_absolute() else WORKSPACE_ROOT / requested
    resolved = candidate.resolve()
    results_root = (WORKSPACE_ROOT / "results").resolve()
    try:
        relative = resolved.relative_to(results_root)
    except ValueError as error:
        raise ValueError("--output must remain under repo-root results/") from error
    if len(relative.parts) < 2 or RUN_ROOT_PATTERN.fullmatch(relative.parts[0]) is None:
        raise ValueError(
            "--output run root must match results/issue119-pepo-*"
        )
    return resolved


def validate_small_oracle(
    path: str | Path,
    profile: CircuitProfile = BASELINE_PROFILE,
) -> dict[str, object]:
    """Require a current successful small-oracle certificate."""
    certificate_path = Path(path)
    try:
        certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(
            f"small-oracle manifest does not exist: {certificate_path}"
        ) from error
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"small-oracle manifest is unreadable: {certificate_path}: {error}"
        ) from error

    if not isinstance(certificate, dict):
        raise ValueError("small-oracle manifest must contain a JSON object")
    if certificate.get("status") != "success":
        raise ValueError("small-oracle manifest status is not success")

    validation = certificate.get("validation")
    if not isinstance(validation, dict) or validation.get("success") is not True:
        raise ValueError("small-oracle validation is not successful")
    error = validation.get("max_absolute_error")
    if (
        isinstance(error, bool)
        or not isinstance(error, (int, float))
        or not math.isfinite(float(error))
        or float(error) < 0.0
        or float(error) > 1.0e-10
    ):
        raise ValueError("small-oracle maximum absolute error is invalid")

    expected = {
        "qasm_sha256": profile.qasm_sha256,
        "quimb_commit": PINNED_QUIMB_COMMIT,
        "core_source_digest": core_source_digest(OLE_ROOT),
    }
    provenance = certificate.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("small-oracle provenance is missing")
    for field, expected_value in expected.items():
        if provenance.get(field) != expected_value:
            raise ValueError(
                f"small-oracle {field} is stale: "
                f"expected {expected_value}, got {provenance.get(field)}"
            )
        if validation.get(field) != expected_value:
            raise ValueError(
                f"small-oracle validation {field} is stale: "
                f"expected {expected_value}, got {validation.get(field)}"
            )
    return certificate


def confirmation_payload(args: argparse.Namespace) -> dict[str, object]:
    """Build the exact deterministic confirmation payload."""
    profile = get_circuit_profile(args.circuit)
    return {
        "circuit": profile.name,
        "qasm_sha256": profile.qasm_sha256,
        "qasm_bytes": profile.qasm_bytes,
        "layers": profile.expected_layers,
        "cz_gates": profile.expected_cz,
        "observable_sites": list(profile.observable_sites),
        "delta": args.delta,
        "dop": args.dop,
        "chi_env": args.chi_env,
        "evolution_cutoff": args.evolution_cutoff,
        "contraction_cutoff": args.contraction_cutoff,
        "quimb_commit": PINNED_QUIMB_COMMIT,
        "core_source_digest": core_source_digest(OLE_ROOT),
        "output": str(args.output),
    }


def _protocol(args: argparse.Namespace) -> OLEProtocol:
    profile = get_circuit_profile(args.circuit)
    protocol = load_circuit_protocol(profile, OLE_ROOT)
    if args.delta == 0.0:
        protocol = replace_perturbations(
            protocol,
            source_angle=profile.perturbation_angle,
            expected_count=profile.perturbation_count,
            replacement_angle=0.0,
        )
    return protocol


def evolve_and_contract(
    protocol: OLEProtocol,
    *,
    dop: int,
    chi_env: int,
    evolution_cutoff: float,
    contraction_cutoff: float,
    observable_operators: dict[int, np.ndarray],
    progress_callback: Callable[[ProgressRecord], None],
) -> tuple[complex, EvolutionDiagnostics]:
    """Construct, evolve, and contract one full PEPO cell."""
    circuit = build_pepo_circuit(
        protocol,
        max_bond=dop,
        cutoff=evolution_cutoff,
    )
    evolved = circuit.evolve_product(
        observable_operators,
        max_bond=dop,
        cutoff=evolution_cutoff,
        progress_every=100,
        progress_callback=progress_callback,
    )
    raw_value = normalized_overlap_compressed(
        evolved.operator,
        observable_operators,
        chi_env=chi_env,
        cutoff=contraction_cutoff,
    )
    return raw_value, evolved.diagnostics


def _protocol_document(args: argparse.Namespace) -> dict[str, object]:
    profile = get_circuit_profile(args.circuit)
    return {
        "circuit": profile.name,
        "qasm_path": str(OLE_ROOT / profile.qasm_relative_path),
        "qasm_sha256": profile.qasm_sha256,
        "qasm_bytes": profile.qasm_bytes,
        "layers": profile.expected_layers,
        "cz_gates": profile.expected_cz,
        "observable_sites": list(profile.observable_sites),
        "delta": args.delta,
        "dop": args.dop,
        "chi_env": args.chi_env,
        "evolution_cutoff": args.evolution_cutoff,
        "contraction_cutoff": args.contraction_cutoff,
    }


def _provenance_document(args: argparse.Namespace) -> dict[str, object]:
    profile = get_circuit_profile(args.circuit)
    return {
        "circuit": profile.name,
        "qasm_sha256": profile.qasm_sha256,
        "source_qasm3_sha256": profile.source_qasm3_sha256,
        "canonical_equal_to_source_qasm3": (
            profile.canonical_equal_to_source_qasm3
        ),
        "quimb_commit": PINNED_QUIMB_COMMIT,
        "core_source_digest": core_source_digest(OLE_ROOT),
        "small_oracle_manifest": str(args.oracle_manifest),
    }


def _checked_result(raw_value: complex) -> tuple[float, float]:
    real = float(raw_value.real)
    imaginary = float(raw_value.imag)
    if not (math.isfinite(real) and math.isfinite(imaginary)):
        raise ValueError(f"raw PEPO result is non-finite: {raw_value}")
    if abs(imaginary) > RESULT_TOLERANCE:
        raise ValueError(
            f"raw PEPO result has imaginary part {imaginary:.3e}, "
            f"above {RESULT_TOLERANCE:.1e}"
        )
    if not -1.0 - RESULT_TOLERANCE <= real <= 1.0 + RESULT_TOLERANCE:
        raise ValueError(
            f"raw PEPO real part is outside the physical range: {real:.17g}"
        )
    return real, imaginary


def _json_component(value: float) -> float | None:
    return value if math.isfinite(value) else None


def _nonnegative_diagnostic_integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be a nonnegative integer")
    converted = int(value)
    if converted < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return converted


def _nonnegative_finite_diagnostic(
    name: str,
    value: object,
    *,
    allow_none: bool = False,
) -> float | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite nonnegative real")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} is non-finite")
    if converted < 0.0:
        raise ValueError(f"{name} must be nonnegative")
    return converted


def _progress_document(record: ProgressRecord) -> dict[str, object]:
    return {
        "processed_causal_gates": _nonnegative_diagnostic_integer(
            "processed_causal_gates", record.processed_causal_gates
        ),
        "total_causal_gates": _nonnegative_diagnostic_integer(
            "total_causal_gates", record.total_causal_gates
        ),
        "support_size": _nonnegative_diagnostic_integer(
            "support_size", record.support_size
        ),
        "max_realized_bond": _nonnegative_diagnostic_integer(
            "max_realized_bond", record.max_realized_bond
        ),
        "retained_tail_ratio": _nonnegative_finite_diagnostic(
            "retained_tail_ratio",
            record.retained_tail_ratio,
            allow_none=True,
        ),
        "elapsed_seconds": _nonnegative_finite_diagnostic(
            "elapsed_seconds", record.elapsed_seconds
        ),
    }


def _diagnostics_document(
    diagnostics: EvolutionDiagnostics,
) -> dict[str, object]:
    return {
        "causal_gates": _nonnegative_diagnostic_integer(
            "causal_gates", diagnostics.causal_gates
        ),
        "final_support_size": len(diagnostics.final_support),
        "max_realized_bond": _nonnegative_diagnostic_integer(
            "max_realized_bond", diagnostics.max_realized_bond
        ),
        "max_retained_tail_ratio": _nonnegative_finite_diagnostic(
            "max_retained_tail_ratio",
            diagnostics.max_retained_tail_ratio,
            allow_none=True,
        ),
    }


def execute(
    args: argparse.Namespace,
    token: str,
    evolution_function: EvolutionFunction,
) -> dict[str, object]:
    """Execute one confirmed cell and publish progress and terminal state atomically."""
    profile = get_circuit_profile(args.circuit)
    validate_small_oracle(args.oracle_manifest, profile)
    started = time.monotonic()
    protocol_document = _protocol_document(args)
    provenance = _provenance_document(args)
    partial_path = args.output.with_suffix(".partial.json")
    latest_progress: dict[str, object] = {
        "phase": "starting",
        "elapsed_seconds": 0.0,
    }
    raw_value: complex | None = None
    diagnostics: EvolutionDiagnostics | None = None
    safe_diagnostics: dict[str, object] | None = None

    def publish_progress(record: ProgressRecord) -> None:
        processed = record.processed_causal_gates
        if not (
            processed == 1
            or processed % 100 == 0
            or processed == record.total_causal_gates
        ):
            return
        safe_progress = _progress_document(record)
        latest_progress.clear()
        latest_progress.update(safe_progress)
        atomic_write_json(
            partial_path,
            {
                "status": "running",
                "protocol": protocol_document,
                "provenance": provenance,
                "progress": latest_progress,
            },
        )
        print(json.dumps(latest_progress, sort_keys=True), flush=True)

    atomic_write_json(
        partial_path,
        {
            "status": "running",
            "protocol": protocol_document,
            "provenance": provenance,
            "progress": latest_progress,
        },
    )

    try:
        protocol = _protocol(args)
        observable_operators = {site: Z for site in profile.observable_sites}
        raw_value, diagnostics = evolution_function(
            protocol,
            dop=args.dop,
            chi_env=args.chi_env,
            evolution_cutoff=args.evolution_cutoff,
            contraction_cutoff=args.contraction_cutoff,
            observable_operators=observable_operators,
            progress_callback=publish_progress,
        )
        safe_diagnostics = _diagnostics_document(diagnostics)
        value_real, value_imag = _checked_result(complex(raw_value))
        manifest: dict[str, object] = {
            "status": "success",
            "confirmation_token": token,
            "protocol": protocol_document,
            "provenance": provenance,
            "result": {
                "value_real": value_real,
                "value_imag": value_imag,
                "wall_seconds": time.monotonic() - started,
                "peak_rss_bytes": peak_rss_bytes(),
            },
            "diagnostics": safe_diagnostics,
        }
        atomic_write_json(args.output, manifest)
        return manifest
    except Exception as error:
        failure: dict[str, object] = {
            "status": "failure",
            "confirmation_token": token,
            "protocol": protocol_document,
            "provenance": provenance,
            "progress": latest_progress,
            "failure": {"type": type(error).__name__, "message": str(error)},
        }
        if raw_value is not None:
            raw_complex = complex(raw_value)
            failure["result"] = {
                "value_real": _json_component(float(raw_complex.real)),
                "value_imag": _json_component(float(raw_complex.imag)),
                "wall_seconds": time.monotonic() - started,
                "peak_rss_bytes": peak_rss_bytes(),
            }
        if safe_diagnostics is not None:
            failure["diagnostics"] = safe_diagnostics
        atomic_write_json(args.output, failure)
        raise


def main(
    argv: list[str] | None = None,
    *,
    evolution_function: EvolutionFunction = evolve_and_contract,
) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        profile = get_circuit_profile(args.circuit)
        if args.oracle_manifest is None:
            args.oracle_manifest = WORKSPACE_ROOT / (
                f"results/{profile.oracle_run_name}/manifest.json"
            )
        args.output = confined_output_path(args.output)
        validate_small_oracle(args.oracle_manifest, profile)
    except ValueError as error:
        parser.error(str(error))

    payload = confirmation_payload(args)
    token = confirmation_token(payload)
    print(f"circuit={profile.name}", flush=True)
    print(f"qasm_sha256={profile.qasm_sha256}", flush=True)
    print(f"qasm_bytes={profile.qasm_bytes}", flush=True)
    print(f"layers={profile.expected_layers}", flush=True)
    print(f"cz_gates={profile.expected_cz}", flush=True)
    print(
        f"observable_sites={','.join(map(str, profile.observable_sites))}",
        flush=True,
    )
    print(f"delta={args.delta:g}", flush=True)
    print(f"dop={args.dop}", flush=True)
    print(f"chi_env={args.chi_env}", flush=True)
    print(f"evolution_cutoff={args.evolution_cutoff:g}", flush=True)
    print(f"contraction_cutoff={args.contraction_cutoff:g}", flush=True)
    print(f"output={args.output}", flush=True)
    print(f"confirmation_token={token}", flush=True)
    if not args.execute:
        print("dry_run=true; no PEPO evolution was started", flush=True)
        return 0
    if args.confirm != token:
        parser.error("--execute requires --confirm matching confirmation_token")

    try:
        manifest = execute(args, token, evolution_function)
    except Exception as error:
        print(f"status=failure: {error}", flush=True)
        return 1
    print(f"status={manifest['status']}", flush=True)
    print(f"value_real={manifest['result']['value_real']:.17g}", flush=True)
    print(f"value_imag={manifest['result']['value_imag']:.17g}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
