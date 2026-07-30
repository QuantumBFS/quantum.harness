#!/usr/bin/env python3
"""Run one resumable parity-sector NN TFIM validation cell."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import time

from lrtfim.checkpoints import (
    CheckpointProvenance,
    code_tree_hash,
    save_checkpoint,
)
from lrtfim.correlation_ratio import (
    physical_correlations_rotated,
    second_moment_ratio,
)
from lrtfim.dmrg_workflow import build_mpo_model, default_dmrg_options
from lrtfim.mpo import build_rotated_nearest_neighbor_tfim_mpo
from lrtfim.parity_dmrg import _run_sector


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OPERATOR_CONVENTION = "rotated-xz-parity-v1"


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        json.dump(payload, stream, indent=2)
        stream.write("\n")
        stream.flush()
    temporary.replace(path)


def exact_model_record(length: int, gamma: float) -> dict:
    payload = {
        "hamiltonian": "-sum_i Z_i Z_(i+1) - Gamma sum_i X_i",
        "length": int(length),
        "Gamma": float(gamma),
        "interaction_boundary": "periodic",
        "mps_boundary": "finite-open",
        "operator_convention": OPERATOR_CONVENTION,
        "physical_X": "TeNPy Sigmaz",
        "physical_Z": "TeNPy Sigmax",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["exact_model_hash"] = hashlib.sha256(canonical.encode()).hexdigest()
    return payload


def _state_record(state, seconds: float, requested_chi: int) -> dict:
    return {
        "requested_chi": requested_chi,
        "energy": state.energy,
        "variance": state.variance,
        "discarded_weight": state.max_discarded_weight,
        "reached_chi": state.max_chi,
        "sweeps": int(state.sweep_statistics["sweep"][-1]),
        "wall_seconds": seconds,
    }


def run_cell(args: argparse.Namespace) -> None:
    if args.length < 4:
        raise ValueError("--length must be >= 4")
    if args.chi != 64:
        raise ValueError("Phase 9 baseline NN cells require --chi 64")
    if args.sector not in {"even", "odd"}:
        raise ValueError("--sector must be even or odd")

    settings = {
        "model": "nearest-neighbor-tfim",
        "sigma": None,
        "length": args.length,
        "gamma": args.gamma,
        "sector": args.sector,
        "sectors": [args.sector],
        "chi_schedule": [args.chi],
        "max_sweeps": args.max_sweeps,
        "direct_only": True,
    }
    model_record = exact_model_record(args.length, args.gamma)
    code_hash = code_tree_hash(PROJECT_ROOT)
    summary_path = args.output_dir / "summary.json"
    if summary_path.is_file():
        existing = json.loads(summary_path.read_text())
        if (
            existing.get("status") == "success"
            and existing.get("settings") == settings
            and existing.get("model") == model_record
            and existing.get("code_hash") == code_hash
        ):
            print("reusing successful NN validation cell", flush=True)
            return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(
        f"building periodic NN MPO: L={args.length}, "
        f"Gamma={args.gamma:g}, sector={args.sector}",
        flush=True,
    )
    setup_started = time.perf_counter()
    mpo = build_rotated_nearest_neighbor_tfim_mpo(args.length, args.gamma)
    model = build_mpo_model(mpo)
    setup_seconds = time.perf_counter() - setup_started
    options = default_dmrg_options(args.chi)
    options["max_sweeps"] = args.max_sweeps

    result = {
        "status": "running",
        "settings": settings,
        "model": model_record,
        "code_hash": code_hash,
        "mpo": {
            "chi": int(max(mpo.chi)),
            "exact_zero_pruning": False,
            "approximate_compression": False,
            "setup_seconds": setup_seconds,
        },
        "direct": {},
        "raw_observables": {},
    }
    atomic_json(summary_path, result)

    print(f"starting {args.sector}-sector DMRG", flush=True)
    started = time.perf_counter()
    state = _run_sector(model, options, args.sector)
    record = _state_record(
        state,
        time.perf_counter() - started,
        args.chi,
    )
    result["direct"][args.sector] = record
    atomic_json(summary_path, result)

    provenance = CheckpointProvenance(
        sigma=None,
        length=args.length,
        gamma=args.gamma,
        num_exponentials=0,
        alpha=0.0,
        r_fit=0,
        sector=args.sector,
        requested_chi=args.chi,
        reached_chi=1,
        sweep_statistics={},
        code_hash=code_hash,
        fit_hash=model_record["exact_model_hash"],
        active_channels=(),
    )
    save_checkpoint(
        args.output_dir
        / "checkpoints"
        / args.sector
        / f"chi{args.chi}",
        state.psi,
        replace(
            provenance,
            reached_chi=state.max_chi,
            sweep_statistics=state.sweep_statistics,
        ),
        record,
    )

    if args.sector == "even":
        correlations = physical_correlations_rotated(state.psi)
        ratio = second_moment_ratio(correlations)
        result["raw_observables"] = {
            "correlations": correlations.tolist(),
            "s_zero": ratio.s_zero,
            "s_k_min": ratio.s_k_min,
            "k_min": ratio.k_min,
            "xi": ratio.xi,
            "r_xi": ratio.r_xi,
            "correlation_definition": (
                "full physical Z-Z correlation without connected subtraction; "
                "evaluated as TeNPy Sigmax-Sigmax"
            ),
        }

    result["status"] = "success"
    atomic_json(summary_path, result)
    print(f"wrote {summary_path}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument("--gamma", type=float, required=True)
    parser.add_argument("--sector", choices=["even", "odd"], required=True)
    parser.add_argument("--chi", type=int, default=64)
    parser.add_argument("--max-sweeps", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    run_cell(parse_args())


if __name__ == "__main__":
    main()
