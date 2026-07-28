#!/usr/bin/env python3
"""Bounded direct-versus-staged Phase 6 DMRG benchmark."""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from lrtfim.checkpoints import (
    CheckpointProvenance,
    code_tree_hash,
    load_initialization_checkpoint,
    mps_lattice_fingerprint,
    save_checkpoint,
)
from lrtfim.correlation_ratio import (
    physical_correlations_rotated,
    second_moment_ratio,
)
from lrtfim.dmrg_workflow import build_mpo_model, default_dmrg_options
from lrtfim.mpo import (
    active_exponential_channels,
    build_rotated_periodized_mpo,
)
from lrtfim.parity_dmrg import _initial_state, _run_sector
from lrtfim.staged_dmrg import run_staged_sector


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fit-summary", type=Path, required=True)
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument("--gamma", type=float, required=True)
    parser.add_argument("--num-exponentials", type=int, default=24)
    parser.add_argument("--alpha", type=float, default=0.5)
    parser.add_argument("--r-fit", type=int, default=2048)
    parser.add_argument(
        "--chi-schedule",
        type=int,
        nargs="+",
        default=[32, 64, 128],
    )
    parser.add_argument("--run-direct", action="store_true")
    parser.add_argument("--direct-only", action="store_true")
    parser.add_argument(
        "--sectors",
        nargs="+",
        choices=["even", "odd"],
        default=["even", "odd"],
    )
    parser.add_argument("--max-sweeps", type=int, default=30)
    parser.add_argument("--initial-checkpoint-root", type=Path)
    parser.add_argument("--initial-chi", type=int, default=128)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def select_fit(
    summary: dict,
    num_exponentials: int,
    alpha: float,
    r_fit: int,
) -> dict:
    """Select one exact (K, alpha, r_fit) tuple without fallback."""
    if "primary" in summary:
        matches = [
            item
            for item in summary["fits"]
            if item["num_exponentials"] == num_exponentials
            and item["alpha"] == alpha
            and item["r_fit"] == r_fit
        ]
        if len(matches) != 1:
            raise ValueError(
                "fit tuple not found: "
                f"K={num_exponentials}, alpha={alpha}, r_fit={r_fit}"
            )
        return matches[0]
    legacy = {
        "num_exponentials": int(summary["K"]),
        "alpha": float(summary["min_rate_scale"]),
        "r_fit": int(summary["r_fit"]),
        "lambdas": summary["lambdas"],
        "coefficients": summary["coefficients"],
    }
    if (
        legacy["num_exponentials"] != num_exponentials
        or legacy["alpha"] != alpha
        or legacy["r_fit"] != r_fit
    ):
        raise ValueError(
            "fit tuple not found: "
            f"K={num_exponentials}, alpha={alpha}, r_fit={r_fit}"
        )
    return legacy


def _normalize(
    summary: dict,
    num_exponentials: int,
    alpha: float,
    r_fit: int,
) -> dict:
    fit = select_fit(summary, num_exponentials, alpha, r_fit)
    sigma = (
        float(summary["sigma"])
        if "sigma" in summary
        else float(summary["p"]) - 1.0
    )
    return {
        "sigma": sigma,
        "primary": {
            "num_exponentials": fit["num_exponentials"],
            "alpha": fit["alpha"],
            "r_fit": fit["r_fit"],
        },
        "fit": fit,
    }


def _state_record(state, seconds: float) -> dict:
    return {
        "requested_chi": state.max_chi,
        "energy": state.energy,
        "variance": state.variance,
        "discarded_weight": state.max_discarded_weight,
        "reached_chi": state.max_chi,
        "sweeps": int(state.sweep_statistics["sweep"][-1]),
        "wall_seconds": seconds,
    }


def main() -> None:
    args = parse_args()
    sectors = tuple(dict.fromkeys(args.sectors))
    if not args.direct_only and sectors != ("even", "odd"):
        raise ValueError("--sectors is supported only with --direct-only")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fit_bytes = args.fit_summary.read_bytes()
    fit_hash = hashlib.sha256(fit_bytes).hexdigest()
    normalized = _normalize(
        json.loads(fit_bytes),
        args.num_exponentials,
        args.alpha,
        args.r_fit,
    )
    primary = normalized["primary"]
    fit = normalized["fit"]
    lambdas = np.asarray(fit["lambdas"], dtype=float)
    coefficients = np.asarray(fit["coefficients"], dtype=float)
    coefficient_hash = hashlib.sha256(
        np.asarray(coefficients, dtype="<f8").tobytes()
    ).hexdigest()
    _, _, active = active_exponential_channels(lambdas, coefficients)

    setup_started = time.perf_counter()
    mpo = build_rotated_periodized_mpo(
        args.length,
        lambdas,
        coefficients,
        args.gamma,
        prune_zero_channels=True,
    )
    model = build_mpo_model(mpo)
    setup_seconds = time.perf_counter() - setup_started
    options = default_dmrg_options(max(args.chi_schedule))
    options["max_sweeps"] = args.max_sweeps
    code_hash = code_tree_hash(PROJECT_ROOT)
    settings = {
        "sigma": normalized["sigma"],
        "length": args.length,
        "gamma": args.gamma,
        "num_exponentials": args.num_exponentials,
        "alpha": args.alpha,
        "r_fit": args.r_fit,
        "chi_schedule": args.chi_schedule,
        "max_sweeps": args.max_sweeps,
        "sectors": list(sectors),
        "direct_only": args.direct_only,
        "initial_checkpoint_root": (
            str(args.initial_checkpoint_root.resolve())
            if args.initial_checkpoint_root is not None
            else None
        ),
        "initial_chi": args.initial_chi,
    }
    summary_path = args.output_dir / "summary.json"
    if summary_path.is_file():
        existing = json.loads(summary_path.read_text())
        if (
            existing.get("status") == "success"
            and existing.get("settings") == settings
            and existing.get("code_hash") == code_hash
            and existing.get("fit", {}).get("fit_hash") == fit_hash
        ):
            print("reusing successful benchmark", flush=True)
            return

    result = {
        "status": "running",
        "settings": settings,
        "fit": {
            "K": primary["num_exponentials"],
            "alpha": primary["alpha"],
            "r_fit": primary["r_fit"],
            "fit_hash": fit_hash,
        },
        "code_hash": code_hash,
        "mpo": {
            "pruned": True,
            "active_channels": active.tolist(),
            "chi": int(max(mpo.chi)),
            "setup_seconds": setup_seconds,
            "approximate_compression": False,
        },
        "direct": {},
        "staged": {},
        "initialization": {},
    }
    summary_path.write_text(json.dumps(result, indent=2) + "\n")

    def provenance_for(sector: str) -> CheckpointProvenance:
        return CheckpointProvenance(
            sigma=normalized["sigma"],
            length=args.length,
            gamma=args.gamma,
            num_exponentials=primary["num_exponentials"],
            alpha=primary["alpha"],
            r_fit=primary["r_fit"],
            sector=sector,
            requested_chi=max(args.chi_schedule),
            reached_chi=1,
            sweep_statistics={},
            code_hash=code_hash,
            fit_hash=fit_hash,
            active_channels=tuple(int(index) for index in active),
        )

    direct_states = {}
    if args.run_direct or args.direct_only:
        for sector in sectors:
            initial_psi = None
            if args.initial_checkpoint_root is not None:
                expected = provenance_for(sector)
                current_initial = _initial_state(model, sector)
                print(f"auditing {sector} initialization checkpoint", flush=True)
                initial_psi, audit = load_initialization_checkpoint(
                    args.initial_checkpoint_root
                    / sector
                    / f"chi{args.initial_chi}",
                    expected,
                    coefficient_hash=coefficient_hash,
                    operator_convention="rotated-xz-periodized-v1",
                    lattice_fingerprint=mps_lattice_fingerprint(current_initial),
                )
                result["initialization"][sector] = audit
                summary_path.write_text(json.dumps(result, indent=2) + "\n")
            print(f"starting direct {sector} DMRG", flush=True)
            started = time.perf_counter()
            state = _run_sector(model, options, sector, initial_psi=initial_psi)
            direct_states[sector] = state
            result["direct"][sector] = _state_record(
                state,
                time.perf_counter() - started,
            )
            result["direct"][sector]["requested_chi"] = max(args.chi_schedule)
            if args.direct_only:
                checkpoint_directory = (
                    args.output_dir
                    / "checkpoints"
                    / sector
                    / f"chi{max(args.chi_schedule)}"
                )
                save_checkpoint(
                    checkpoint_directory,
                    state.psi,
                    replace(
                        provenance_for(sector),
                        reached_chi=state.max_chi,
                        sweep_statistics=state.sweep_statistics,
                    ),
                    result["direct"][sector],
                )
            print(f"direct {sector} complete", flush=True)
            summary_path.write_text(json.dumps(result, indent=2) + "\n")

    staged_states = {}
    if not args.direct_only:
        for sector in sectors:
            staged = run_staged_sector(
                model,
                sector,
                args.chi_schedule,
                options,
                checkpoint_root=args.output_dir / "checkpoints" / sector,
                provenance=provenance_for(sector),
            )
            staged_states[sector] = staged.final
            result["staged"][sector] = {
                "stages": [asdict(stage) for stage in staged.stages],
                "total_wall_seconds": sum(
                    stage.wall_seconds for stage in staged.stages
                ),
            }
            print(f"staged {sector} complete", flush=True)
            summary_path.write_text(json.dumps(result, indent=2) + "\n")

    selected_states = direct_states if args.direct_only else staged_states
    raw = {}
    if "even" in selected_states:
        correlations = physical_correlations_rotated(selected_states["even"].psi)
        ratio = second_moment_ratio(correlations)
        raw.update(
            {
                "correlations": correlations.tolist(),
                "s_zero": ratio.s_zero,
                "s_k_min": ratio.s_k_min,
                "k_min": ratio.k_min,
                "xi": ratio.xi,
                "r_xi": ratio.r_xi,
            }
        )
    if set(selected_states) == {"even", "odd"}:
        raw["gap"] = (
            selected_states["odd"].energy - selected_states["even"].energy
        )
    result["raw_observables"] = raw
    result["status"] = "success"
    summary_path.write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {summary_path}", flush=True)


if __name__ == "__main__":
    main()
