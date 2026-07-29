"""Command-line interface for ED, projected NQS, and result validation."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

import numpy as np

from . import __version__
from .basis import SphereSystem
from .ed import neutral_gap
from .nqs import SharedProjectedMLP


def _write_json(path: str | Path, payload: dict) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _metadata(seed: int) -> dict:
    return {
        "schema_version": 1,
        "seed": seed,
        "software": {
            "chiral_graviton": __version__,
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
        "conventions": {
            "flux": "2Q=3(N-1)",
            "geometry": "Haldane sphere",
            "interaction_distance": "3D chord",
            "background_constant": "excluded; cancels in same-N gap",
        },
    }


def command_ed(args: argparse.Namespace) -> int:
    system = SphereSystem.from_electron_count(args.n)
    result = neutral_gap(system, args.interaction).to_dict()
    result.update(_metadata(args.seed))
    result["method"] = "ed"
    _write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def command_nqs(args: argparse.Namespace) -> int:
    system = SphereSystem.from_electron_count(args.n)
    model = SharedProjectedMLP.build(
        system, args.interaction, hidden_width=args.hidden_width, seed=args.seed
    )
    fitted = model.fit(max_iterations=args.max_iterations)
    payload = {
        **_metadata(args.seed),
        "method": "symmetry_projected_mlp_nqs",
        "n_electrons": args.n,
        "two_q": system.two_q,
        "interaction": args.interaction,
        "energy_unit": "e^2/(epsilon*l_B)",
        "e_l0": fitted.ground.energy,
        "e_l2": fitted.graviton.energy,
        "gap": fitted.gap,
        "l2_ground": fitted.ground.l2_expectation,
        "l2_excited": fitted.graviton.l2_expectation,
        "variance_l0": fitted.ground.variance,
        "variance_l2": fitted.graviton.variance,
        "optimizer_success": fitted.success,
        "optimizer_message": fitted.message,
        "optimizer_iterations": fitted.iterations,
        "hidden_width": args.hidden_width,
    }
    _write_json(args.output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if model.equivariance_error(fitted.parameters) < 1e-7 else 3


def command_validate(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.result).read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "method",
        "n_electrons",
        "two_q",
        "e_l0",
        "e_l2",
        "gap",
        "l2_excited",
        "energy_unit",
    }
    missing = sorted(required - payload.keys())
    if missing:
        print(f"CG006: missing result keys: {missing}", file=sys.stderr)
        return 6
    if payload["two_q"] != 3 * (payload["n_electrons"] - 1):
        print("CG001: invalid Laughlin flux", file=sys.stderr)
        return 3
    if abs(payload["gap"] - (payload["e_l2"] - payload["e_l0"])) > 1e-10:
        print("CG006: inconsistent gap", file=sys.stderr)
        return 6
    if abs(payload["l2_excited"] - 6.0) > 1e-7:
        print("CG006: excited state is not clean L=2", file=sys.stderr)
        return 3
    print("valid")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chiral-graviton")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, handler in (("ed", command_ed), ("nqs", command_nqs)):
        sub = subparsers.add_parser(name)
        sub.add_argument("--n", type=int, required=True)
        sub.add_argument("--interaction", choices=("v1", "coulomb"), default="coulomb")
        sub.add_argument("--seed", type=int, default=1729)
        sub.add_argument("--output", required=True)
        if name == "nqs":
            sub.add_argument("--hidden-width", type=int, default=24)
            sub.add_argument("--max-iterations", type=int, default=400)
        sub.set_defaults(handler=handler)

    validate = subparsers.add_parser("validate")
    validate.add_argument("result")
    validate.set_defaults(handler=command_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
