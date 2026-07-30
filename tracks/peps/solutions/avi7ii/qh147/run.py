from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path

from .evolve import ChainConfig, run_chain
from .measure import measure_chain


@dataclass(frozen=True)
class ProductionConfig:
    chain: ChainConfig
    boundary: str
    operator: str
    measurement_chis: tuple[int, ...]
    public_step: float


def _reject_constant(value: str):
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


def _exact_keys(
    payload: dict[str, object],
    expected: set[str],
    label: str,
) -> None:
    if set(payload) != expected:
        raise ValueError(f"unknown or missing {label} keys")


def load_production_config(path: Path) -> ProductionConfig:
    path = Path(path)
    payload = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_constant,
    )
    if not isinstance(payload, dict):
        raise ValueError("production configuration must be an object")
    _exact_keys(
        payload,
        {"model", "conventions", "evolution", "compression", "measurement"},
        "top-level",
    )
    model = payload["model"]
    conventions = payload["conventions"]
    evolution = payload["evolution"]
    compression = payload["compression"]
    measurement = payload["measurement"]
    if not all(
        isinstance(section, dict)
        for section in (model, conventions, evolution, compression, measurement)
    ):
        raise ValueError("production configuration sections must be objects")

    _exact_keys(model, {"lx", "ly", "j", "h"}, "model")
    _exact_keys(conventions, {"boundary", "operator"}, "conventions")
    _exact_keys(
        evolution,
        {"delta_beta", "beta_stop", "max_bond", "teacher_bond"},
        "evolution",
    )
    _exact_keys(
        compression,
        {
            "chi",
            "cutoff",
            "max_iterations",
            "optimizer",
            "tolerances",
            "weights",
            "hermiticity_tolerance",
            "loss_acceptance_tolerance",
        },
        "compression",
    )
    _exact_keys(measurement, {"chis", "public_step"}, "measurement")
    tolerances = compression["tolerances"]
    weights = compression["weights"]
    if not isinstance(tolerances, dict) or not isinstance(weights, dict):
        raise ValueError("compression tolerances and weights must be objects")
    _exact_keys(tolerances, {"z", "u", "contraction_noise"}, "tolerance")
    _exact_keys(weights, {"z", "u", "hermiticity"}, "weight")

    boundary = conventions["boundary"]
    operator = conventions["operator"]
    if boundary != "open":
        raise ValueError("production boundary must be open")
    if operator != "pauli":
        raise ValueError("production operator convention must be pauli")
    chis = measurement["chis"]
    if (
        not isinstance(chis, list)
        or not chis
        or any(not isinstance(chi, int) or isinstance(chi, bool) or chi < 1 for chi in chis)
        or len(set(chis)) != len(chis)
    ):
        raise ValueError("measurement chis must be distinct positive integers")
    public_step = float(measurement["public_step"])
    if not math.isfinite(public_step) or public_step <= 0:
        raise ValueError("measurement public step must be finite and positive")

    chain = ChainConfig(
        lx=int(model["lx"]),
        ly=int(model["ly"]),
        j=float(model["j"]),
        h=float(model["h"]),
        delta_beta=float(evolution["delta_beta"]),
        beta_stop=float(evolution["beta_stop"]),
        max_bond=int(evolution["max_bond"]),
        teacher_bond=int(evolution["teacher_bond"]),
        chi=int(compression["chi"]),
        cutoff=float(compression["cutoff"]),
        max_iterations=int(compression["max_iterations"]),
        optimizer=str(compression["optimizer"]),
        epsilon_z=float(tolerances["z"]),
        epsilon_u=float(tolerances["u"]),
        contraction_noise=float(tolerances["contraction_noise"]),
        lambda_z=float(weights["z"]),
        lambda_u=float(weights["u"]),
        lambda_hermiticity=float(weights["hermiticity"]),
        hermiticity_tolerance=float(compression["hermiticity_tolerance"]),
        loss_acceptance_tolerance=float(
            compression["loss_acceptance_tolerance"]
        ),
    )
    stride = round(public_step / chain.delta_beta)
    if not math.isclose(
        stride * chain.delta_beta,
        public_step,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise ValueError("public step must be an exact delta-beta multiple")
    return ProductionConfig(
        chain=chain,
        boundary=boundary,
        operator=operator,
        measurement_chis=tuple(chis),
        public_step=public_step,
    )


def _tensor_elements(lx: int, ly: int, bond: int) -> int:
    total = 0
    for x in range(lx):
        for y in range(ly):
            degree = sum(
                (
                    x > 0,
                    x + 1 < lx,
                    y > 0,
                    y + 1 < ly,
                )
            )
            total += 4 * bond**degree
    return total


def _dry_run(production: ProductionConfig) -> dict[str, object]:
    chain = production.chain
    checkpoint_count = chain.steps * 2
    one_checkpoint_bytes = 8 * _tensor_elements(
        chain.lx,
        chain.ly,
        chain.max_bond,
    )
    teacher_bytes = 8 * _tensor_elements(
        chain.lx,
        chain.ly,
        chain.teacher_bond,
    )
    return {
        "status": "dry-run",
        "model": {
            "lx": chain.lx,
            "ly": chain.ly,
            "j": chain.j,
            "h": chain.h,
            "boundary": production.boundary,
            "operator": production.operator,
        },
        "hamiltonian": "H = -J sum_<ij> Z_i Z_j - h sum_i X_i",
        "delta_beta": chain.delta_beta,
        "beta_stop": chain.beta_stop,
        "steps": chain.steps,
        "modes": ["ordinary", "thermodynamic"],
        "max_bond": chain.max_bond,
        "teacher_bond": chain.teacher_bond,
        "evolution_chi": chain.chi,
        "measurement_chis": list(production.measurement_chis),
        "checkpoint_count": checkpoint_count,
        "one_checkpoint_bytes": one_checkpoint_bytes,
        "all_checkpoint_bytes": one_checkpoint_bytes * checkpoint_count,
        "teacher_tensor_bytes_upper": teacher_bytes,
        "optimizer": chain.optimizer,
        "max_iterations": chain.max_iterations,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("dry-run", "evolve", "measure"):
        command = subparsers.add_parser(name)
        command.add_argument("--config", required=True, type=Path)
        command.add_argument("--run-root", required=True, type=Path)
        if name in {"evolve", "measure"}:
            command.add_argument(
                "--compression-mode",
                required=True,
                choices=("ordinary", "thermodynamic"),
            )
        if name == "evolve":
            command.add_argument("--stop-after-steps", type=int)
        if name == "measure":
            command.add_argument("--chi", required=True, type=int)
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    production = load_production_config(args.config)
    chain = production.chain
    if args.command == "dry-run":
        print(json.dumps(_dry_run(production), sort_keys=True), flush=True)
        return 0
    if args.command == "evolve":
        result = run_chain(
            chain,
            args.run_root,
            mode=args.compression_mode,
            stop_after_steps=args.stop_after_steps,
        )
        print(
            json.dumps(
                {
                    "status": "complete"
                    if len(result.accepted_betas) == chain.steps
                    else "partial",
                    "mode": args.compression_mode,
                    "accepted_steps": len(result.accepted_betas),
                    "resumed_from": result.resumed_from,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 0
    if args.chi not in production.measurement_chis:
        raise ValueError("measurement chi is not declared by the configuration")
    result = measure_chain(
        args.run_root / args.compression_mode / "checkpoints",
        args.run_root
        / "measurements"
        / args.compression_mode
        / f"chi-{args.chi}",
        expected_config_sha256=chain.config_sha256(),
        j=chain.j,
        h=chain.h,
        chi=args.chi,
        cutoff=chain.cutoff,
        delta_beta=chain.delta_beta,
        beta_stop=chain.beta_stop,
        public_step=production.public_step,
    )
    print(
        json.dumps(
            {
                "status": "success",
                "mode": args.compression_mode,
                "chi": args.chi,
                "dense_count": result.dense_count,
                "public_count": result.public_count,
                "output": str(result.manifest_path.parent),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
