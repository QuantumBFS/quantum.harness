#!/usr/bin/env python3
"""Generate safe per-realization Gaussian null banks without opening outcomes."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from lgeth.hodge_wick import hodge_gaussian_r4_reference
from lgeth.wick_channels import gaussian_r4_reference
from run_susy_hodge_geometric_eth_v7 import (
    CHECKPOINT_ROOT,
    NULL_DRAWS_PER_REALIZATION,
    PANEL_SIZE,
    REGISTERED_PANEL_KINDS,
    REGISTERED_SECTORS,
    SCRIPT_ROOT,
    VERSION,
    _atomic_json,
    _atomic_npz,
    _derived_seed,
    _positive_covariance_spectrum,
    _signature_from_safe,
    panel_paths,
    sha256,
)


OUTPUT_ROOT = SCRIPT_ROOT / "output" / "susy_hodge_v7_null_banks"
FORBIDDEN_SAFE_TOKENS = ("r4", "four_point", "connected")


def _array_hash(values: np.ndarray) -> str:
    array = np.ascontiguousarray(values)
    return hashlib.sha256(array.view(np.uint8)).hexdigest()


def _source_hashes() -> dict[str, str]:
    paths = (
        Path(__file__).resolve(),
        SCRIPT_ROOT / "run_susy_hodge_geometric_eth_v7.py",
        SCRIPT_ROOT / "lgeth" / "hodge_response.py",
        SCRIPT_ROOT / "lgeth" / "hodge_wick.py",
        SCRIPT_ROOT / "lgeth" / "wick_channels.py",
    )
    return {str(path.relative_to(SCRIPT_ROOT)): sha256(path) for path in paths}


def null_bank_paths(
    output_root: Path,
    N: int,
    sector: str,
    realization: int,
    panel_kind: str,
) -> tuple[Path, Path]:
    stem = Path(output_root) / (
        f"N{int(N)}_{sector}_seed{int(realization):03d}_{panel_kind}_{VERSION}_null"
    )
    return stem.with_suffix(".json"), stem.with_suffix(".npz")


def write_null_bank(
    N: int,
    sector: str,
    realization: int,
    panel_kind: str,
    *,
    checkpoint_root: Path = CHECKPOINT_ROOT,
    output_root: Path = OUTPUT_ROOT,
    draws: int = NULL_DRAWS_PER_REALIZATION,
    force: bool = False,
) -> dict[str, Any]:
    """Write collapsed and Hodge null draws using only safe covariance data."""

    count = int(draws)
    if count < 1:
        raise ValueError("null bank requires at least one draw")
    safe_path, safe_arrays_path, _ = panel_paths(
        checkpoint_root,
        N,
        sector,
        realization,
        panel_kind,
    )
    if not safe_path.is_file() or not safe_arrays_path.is_file():
        raise FileNotFoundError("missing safe panel data for null bank")
    safe = json.loads(safe_path.read_text(encoding="utf-8"))
    if safe.get("arrays_sha256") != sha256(safe_arrays_path):
        raise ValueError("safe panel array hash mismatch")
    if not all(safe.get("checks", {}).values()):
        raise ValueError("safe panel contains a failed gate")
    metadata_path, arrays_path = null_bank_paths(
        output_root,
        N,
        sector,
        realization,
        panel_kind,
    )
    identity = {
        "version": VERSION,
        "N": int(N),
        "sector": str(sector),
        "realization": int(realization),
        "panel_kind": str(panel_kind),
        "draws": count,
        "safe_identity_hash": safe["identity_hash"],
        "safe_arrays_sha256": safe["arrays_sha256"],
        "sources": _source_hashes(),
    }
    identity_hash = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if not force and metadata_path.is_file() and arrays_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if (
            metadata.get("identity") == identity
            and metadata.get("identity_hash") == identity_hash
            and metadata.get("arrays_sha256") == sha256(arrays_path)
            and all(metadata.get("checks", {}).values())
        ):
            return metadata
        raise ValueError("null bank checkpoint identity mismatch")
    with np.load(safe_arrays_path) as loaded:
        copied = {key: np.asarray(loaded[key]) for key in loaded.files}
    signature = _signature_from_safe(safe, copied)
    collapsed = gaussian_r4_reference(
        _positive_covariance_spectrum(copied["total_target_eigenvalues"]),
        _positive_covariance_spectrum(copied["total_external_eigenvalues"]),
        PANEL_SIZE,
        count,
        _derived_seed(N, sector, realization, panel_kind, "collapsed_bank"),
    )
    hodge = hodge_gaussian_r4_reference(
        signature,
        PANEL_SIZE,
        count,
        _derived_seed(N, sector, realization, panel_kind, "hodge_bank"),
    )
    _atomic_npz(
        arrays_path,
        collapsed_null=collapsed,
        hodge_null=hodge,
    )
    checks = {
        "finite_collapsed_null": bool(np.all(np.isfinite(collapsed))),
        "finite_hodge_null": bool(np.all(np.isfinite(hodge))),
        "registered_draw_count": collapsed.shape == (count,)
        and hodge.shape == (count,),
        "safe_source_hash": safe["arrays_sha256"] == sha256(safe_arrays_path),
    }
    metadata = {
        "identity": identity,
        "identity_hash": identity_hash,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "draws": count,
        "collapsed_sha256": _array_hash(collapsed),
        "hodge_sha256": _array_hash(hodge),
        "arrays_sha256": sha256(arrays_path),
        "checks": checks,
        "passed": all(checks.values()),
    }
    serialized = json.dumps(metadata, sort_keys=True).lower()
    metadata["checks"]["no_outcome_leakage"] = not any(
        token in serialized for token in FORBIDDEN_SAFE_TOKENS
    )
    metadata["passed"] = all(metadata["checks"].values())
    if not metadata["passed"]:
        raise RuntimeError(f"null bank audit failed: {metadata['checks']}")
    _atomic_json(metadata_path, metadata)
    return metadata


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--N", type=int, required=True)
    parser.add_argument("--sector", choices=REGISTERED_SECTORS, required=True)
    parser.add_argument("--realization", type=int, required=True)
    parser.add_argument("--panel-kind", choices=REGISTERED_PANEL_KINDS, required=True)
    parser.add_argument("--draws", type=int, default=NULL_DRAWS_PER_REALIZATION)
    parser.add_argument("--force", action="store_true")
    return parser


def main() -> None:
    args = _parser().parse_args()
    payload = write_null_bank(
        args.N,
        args.sector,
        args.realization,
        args.panel_kind,
        draws=args.draws,
        force=args.force,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
