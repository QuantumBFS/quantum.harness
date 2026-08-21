#!/usr/bin/env python3
"""Generate the deterministic v14 effective-channel theorem audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from copy import deepcopy
from numbers import Real
from pathlib import Path
from typing import Any, Mapping

from lgeth.geometric_eth_channel_theory import run_theory_audit


SCRIPT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_ROOT.parents[2]
DEFAULT_OUTPUT = (
    SCRIPT_ROOT
    / "output/geometric_eth_theory_v14/channel_theory_v14.json"
)
VERSION = "v14"
SCHEMA = "geometric_eth_channel_theory_v14"
CANONICAL_SIGNIFICANT_DIGITS = 10
SOURCE_PATHS = (
    "docs/plans/2026-08-17-geometric-eth-theorem-specification.md",
    "01_task_folder/task_05/script/lgeth/geometric_eth_channel_theory.py",
    "01_task_folder/task_05/script/derive_geometric_eth_channel_theory_v14.py",
    "01_task_folder/task_05/script/tests/test_geometric_eth_channel_theory_v14.py",
)


def canonical_quantize_payload(value: Any) -> Any:
    """Recursively quantize finite floats for cross-BLAS serialization.

    Raw calculations and pass/fail decisions occur before this function is
    called.  Ten significant decimal digits retain far more precision than
    the registered 0.08 relative-error gate while removing platform-dependent
    rounding in the last few binary floating-point bits.  The audited
    Python/NumPy cold starts can differ in the twelfth significant digit of
    near-zero covariance entries.
    """

    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, Real):
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError("scientific payload contains a non-finite value")
        if numeric == 0.0:
            return 0.0
        return float(format(numeric, f".{CANONICAL_SIGNIFICANT_DIGITS}g"))
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("scientific payload mapping keys must be strings")
        return {
            key: canonical_quantize_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [canonical_quantize_payload(item) for item in value]
    raise TypeError(
        f"unsupported scientific payload value: {type(value).__name__}"
    )


def canonical_scientific_json(payload: Mapping[str, Any]) -> str:
    """Quantize and serialize scientific data with stable key ordering."""

    return (
        json.dumps(
            canonical_quantize_payload(payload),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_payload(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Build and self-hash the complete deterministic theory payload."""

    raw_audit = deepcopy(run_theory_audit())
    payload: dict[str, Any] = raw_audit
    payload["version"] = VERSION
    payload["schema"] = SCHEMA
    payload["canonical_serialization"] = {
        "float_significant_decimal_digits": CANONICAL_SIGNIFICANT_DIGITS,
        "scope": "serialization and signature only",
        "raw_gate_evaluated_before_quantization": True,
        "nonfinite_policy": "reject",
    }
    payload["source_hashes"] = {
        relative: _sha256(repo_root / relative) for relative in SOURCE_PATHS
    }
    quantized = canonical_quantize_payload(payload)
    quantized["scientific_payload_sha256"] = hashlib.sha256(
        canonical_scientific_json(quantized).encode("utf-8")
    ).hexdigest()
    return quantized


def write_payload(payload: Mapping[str, Any], output: Path) -> None:
    """Atomically write a canonical JSON payload with ordinary file mode."""

    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_scientific_json(payload)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    payload = build_payload()
    write_payload(payload, arguments.output)
    print(
        f"wrote {arguments.output} "
        f"(maximum relative error={payload['maximum_relative_error']:.6f}, "
        f"pass={payload['all_checks_pass']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
