#!/usr/bin/env python3
"""Validate the PEPO path against the audited seven-site dense oracle."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import math
from pathlib import Path
import time

import numpy as np

from ole_pepo import PINNED_QUIMB_COMMIT
from ole_pepo.contraction import normalized_overlap_exact
from ole_pepo.engine import ProgressRecord, build_pepo_circuit
from ole_pepo.exact import normalized_ole_dense, seven_site_oracle_protocol
from ole_pepo.qasm import read_validated_qasm
from ole_pepo.records import (
    SmallOracleStatus,
    atomic_write_json,
    confirmation_token,
    core_source_digest,
    peak_rss_bytes,
)


OLE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = OLE_ROOT.parents[4]
DEFAULT_OUTPUT_DIR = WORKSPACE_ROOT / "results/issue119-pepo-small-oracle"
QASM_PATH = OLE_ROOT / "inputs/49Q_OLE_circuit_L_3_b_0.25_delta0.15.qasm"
QASM_SHA256 = "1705197e7b1ebb02266600b3ddaba0d2c47a96de84c5895e2bb530728b815455"
QASM_BYTES = 150686
SITES = (33, 39, 49, 50, 51, 52, 53)
OBSERVABLE_SITE = 52
EXACT_TOLERANCE = 1e-10
TRUNCATED_DOP = (1, 2, 4)
Z = np.diag([1.0, -1.0]).astype(np.complex128)


def _confirmation_document() -> dict[str, object]:
    return {
        "core_source_digest": core_source_digest(OLE_ROOT),
        "delta_modes": [0, 0.15],
        "exact_tolerance": EXACT_TOLERANCE,
        "observable": "Z52",
        "qasm_sha256": QASM_SHA256,
        "quimb_commit": PINNED_QUIMB_COMMIT,
        "sites": list(SITES),
        "truncated_dop": list(TRUNCATED_DOP),
    }


def _real_checked(name: str, value: complex) -> float:
    if not (math.isfinite(value.real) and math.isfinite(value.imag)):
        raise RuntimeError(f"{name} is non-finite: {value}")
    if abs(value.imag) > EXACT_TOLERANCE:
        raise RuntimeError(f"{name} has imaginary part {value.imag:.3e}")
    if not -1.0 - EXACT_TOLERANCE <= value.real <= 1.0 + EXACT_TOLERANCE:
        raise RuntimeError(f"{name} is outside the physical range: {value.real:.17g}")
    return float(value.real)


def _exact_pepo_value(protocol, progress_callback=None) -> float:
    circuit = build_pepo_circuit(protocol, max_bond=None, cutoff=0.0)
    evolved = circuit.evolve_product(
        {OBSERVABLE_SITE: Z},
        max_bond=None,
        cutoff=0.0,
        progress_every=100,
        progress_callback=progress_callback,
    )
    return _real_checked(
        "untruncated PEPO value",
        normalized_overlap_exact(evolved.operator, {OBSERVABLE_SITE: Z}),
    )


def _truncated_pepo_value(protocol, dop: int, progress_callback=None) -> float:
    circuit = build_pepo_circuit(protocol, max_bond=dop, cutoff=0.0)
    evolved = circuit.evolve_product(
        {OBSERVABLE_SITE: Z},
        max_bond=dop,
        cutoff=0.0,
        progress_every=100,
        progress_callback=progress_callback,
    )
    return _real_checked(
        f"truncated PEPO value at Dop={dop}",
        normalized_overlap_exact(evolved.operator, {OBSERVABLE_SITE: Z}),
    )


def _render_report(
    manifest: dict[str, object], report_path: Path, confirmation: str, output_dir: Path
) -> None:
    validation = manifest["validation"]
    timings = manifest["timings"]
    resources = manifest["resources"]
    provenance = manifest["provenance"]
    assert isinstance(validation, dict)
    assert isinstance(timings, dict)
    assert isinstance(resources, dict)
    assert isinstance(provenance, dict)
    lines = [
        "# PEPO small-oracle validation",
        "",
        "Status: success — the seven-site PEPO result agrees with the independent dense oracle within 1e-10.",
        "",
        "## Commands",
        "",
        "```bash",
        "OLE_ROOT=tracks/qcs/solutions/CCB-LV.999/issue-119-ole",
        'uv run --project "$OLE_ROOT/pepo" python "$OLE_ROOT/scripts/validate_pepo_small.py"',
        (
            'uv run --project "$OLE_ROOT/pepo" python '
            f'"$OLE_ROOT/scripts/validate_pepo_small.py" --execute --confirm "{confirmation}" '
            f'--output-dir "{output_dir}"'
        ),
        "```",
        "",
        "## Results",
        "",
        "| quantity | value |",
        "| --- | ---: |",
        f"| dense δ=0 | {validation['dense_delta_zero']:.17g} |",
        f"| PEPO δ=0 | {validation['pepo_delta_zero']:.17g} |",
        f"| dense δ=0.15 | {validation['dense_delta_015']:.17g} |",
        f"| PEPO δ=0.15 | {validation['pepo_delta_015']:.17g} |",
        f"| exact error δ=0 | {validation['exact_errors']['delta_zero']:.3e} |",
        f"| exact error δ=0.15 | {validation['exact_errors']['delta_015']:.3e} |",
        f"| maximum exact error | {validation['max_absolute_error']:.3e} |",
        "",
        "## Truncated δ=0.15 contractions",
        "",
        "| Dop | value | absolute error from dense |",
        "| ---: | ---: | ---: |",
        *(
            f"| {dop} | {record['value']:.17g} | {record['absolute_error']:.3e} |"
            for dop, record in validation["truncated_delta_015"].items()
        ),
        "",
        "## Provenance and resources",
        "",
        f"- QASM SHA-256: `{provenance['qasm_sha256']}`",
        f"- quimb revision: `{provenance['quimb_commit']}`",
        f"- numerical-core digest: `{provenance['core_source_digest']}`",
        f"- wall time: {timings['wall_seconds']:.3f} s",
        f"- peak RSS: {resources['peak_rss_bytes']} bytes",
        "",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def _report_path(output_dir: Path) -> Path:
    if output_dir.resolve() == DEFAULT_OUTPUT_DIR.resolve():
        return OLE_ROOT / "PEPO_SMALL_VALIDATION.md"
    return output_dir / "PEPO_SMALL_VALIDATION.md"


def _execute(output_dir: Path, confirmation: str) -> dict[str, object]:
    started = time.monotonic()
    provenance = {
        "qasm_sha256": QASM_SHA256,
        "quimb_commit": PINNED_QUIMB_COMMIT,
        "core_source_digest": core_source_digest(OLE_ROOT),
    }
    protocol = {
        "sites": list(SITES),
        "observable": "Z52",
        "delta_modes": [0, 0.15],
        "exact_tolerance": EXACT_TOLERANCE,
    }
    partial_validation: dict[str, object] = {}
    progress: dict[str, object] = {"phase": "starting", "elapsed_seconds": 0.0}

    def publish_running(phase: str, record: ProgressRecord | None = None) -> None:
        progress.clear()
        progress.update({"phase": phase, "elapsed_seconds": time.monotonic() - started})
        if record is not None:
            progress.update(
                {
                    "processed_causal_gates": record.processed_causal_gates,
                    "total_causal_gates": record.total_causal_gates,
                    "support_size": record.support_size,
                    "max_realized_bond": record.max_realized_bond,
                    "retained_tail_ratio": record.retained_tail_ratio,
                }
            )
            print(
                f"{phase}: causal_gates={record.processed_causal_gates}/{record.total_causal_gates}",
                flush=True,
            )
        atomic_write_json(
            output_dir / "manifest.json",
            {
                "status": "running",
                "protocol": protocol,
                "provenance": provenance,
                "progress": progress,
                "validation": partial_validation,
            },
        )

    def progress_callback(phase: str):
        return lambda record: publish_running(phase, record)

    publish_running("validating_qasm")
    try:
        print("validating_qasm", flush=True)
        full_protocol = read_validated_qasm(QASM_PATH, QASM_SHA256, QASM_BYTES)
        publish_running("building_seven_site_protocols")
        print("building_seven_site_protocols", flush=True)
        zero_protocol = seven_site_oracle_protocol(full_protocol, delta_zero=True)
        delta_protocol = seven_site_oracle_protocol(full_protocol, delta_zero=False)

        publish_running("computing_dense_delta_zero")
        print("computing_dense_delta_zero", flush=True)
        dense_zero = _real_checked(
            "dense delta-zero value", normalized_ole_dense(zero_protocol, (OBSERVABLE_SITE,))
        )
        partial_validation["dense_delta_zero"] = dense_zero
        publish_running("computing_pepo_delta_zero")
        print("computing_pepo_delta_zero", flush=True)
        pepo_zero = _exact_pepo_value(
            zero_protocol, progress_callback("computing_pepo_delta_zero")
        )
        partial_validation["pepo_delta_zero"] = pepo_zero
        publish_running("computing_dense_delta_015")
        print("computing_dense_delta_015", flush=True)
        dense_delta = _real_checked(
            "dense delta-0.15 value", normalized_ole_dense(delta_protocol, (OBSERVABLE_SITE,))
        )
        partial_validation["dense_delta_015"] = dense_delta
        publish_running("computing_pepo_delta_015")
        print("computing_pepo_delta_015", flush=True)
        pepo_delta = _exact_pepo_value(
            delta_protocol, progress_callback("computing_pepo_delta_015")
        )
        partial_validation["pepo_delta_015"] = pepo_delta

        print("computing_truncated_delta_015", flush=True)
        truncated = {}
        for dop in TRUNCATED_DOP:
            phase = f"computing_truncated_delta_015_dop_{dop}"
            publish_running(phase)
            truncated[str(dop)] = {
                "value": _truncated_pepo_value(delta_protocol, dop, progress_callback(phase)),
                "absolute_error": 0.0,
            }
        for record in truncated.values():
            record["absolute_error"] = abs(record["value"] - dense_delta)

        errors = {
            "delta_zero": abs(pepo_zero - dense_zero),
            "delta_015": abs(pepo_delta - dense_delta),
        }
        max_error = max(errors.values())
        if abs(dense_zero - 1.0) > EXACT_TOLERANCE or abs(pepo_zero - 1.0) > EXACT_TOLERANCE:
            raise RuntimeError("delta-zero control differs from one beyond exact tolerance")
        if max_error > EXACT_TOLERANCE:
            raise RuntimeError(f"untruncated PEPO exact error {max_error:.3e} exceeds tolerance")

        status = SmallOracleStatus(
            success=True,
            qasm_sha256=QASM_SHA256,
            quimb_commit=PINNED_QUIMB_COMMIT,
            core_source_digest=provenance["core_source_digest"],
            dense_delta_zero=dense_zero,
            pepo_delta_zero=pepo_zero,
            dense_delta_015=dense_delta,
            pepo_delta_015=pepo_delta,
            max_absolute_error=max_error,
        )
        manifest: dict[str, object] = {
            "status": "success",
            "protocol": protocol,
            "provenance": provenance,
            "validation": {
                **asdict(status),
                "exact_errors": errors,
                "truncated_delta_015": truncated,
            },
            "timings": {"wall_seconds": time.monotonic() - started},
            "resources": {"peak_rss_bytes": peak_rss_bytes()},
        }
        _render_report(manifest, _report_path(output_dir), confirmation, output_dir)
        atomic_write_json(output_dir / "manifest.json", manifest)
        return manifest
    except Exception as error:
        atomic_write_json(
            output_dir / "manifest.json",
            {
                "status": "failure",
                "protocol": protocol,
                "provenance": provenance,
                "progress": progress,
                "validation": partial_validation,
                "failure": {"type": type(error).__name__, "message": str(error)},
            },
        )
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="run the numerical validation")
    parser.add_argument("--confirm", help="confirmation token printed by inspect mode")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    confirmation_document = _confirmation_document()
    token = confirmation_token(confirmation_document)
    print("sites=33,39,49,50,51,52,53", flush=True)
    print("observable=Z52", flush=True)
    print("delta_modes=0,0.15", flush=True)
    print("exact_tolerance=1e-10", flush=True)
    print(f"confirmation_token={token}", flush=True)
    if not args.execute:
        return 0
    if args.confirm != token:
        parser.error("--execute requires --confirm matching confirmation_token")

    try:
        manifest = _execute(args.output_dir, token)
    except Exception as error:
        print(f"status=failure: {error}", flush=True)
        return 1
    print(f"status={manifest['status']}", flush=True)
    print(
        f"max_absolute_error={manifest['validation']['max_absolute_error']:.3e}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
