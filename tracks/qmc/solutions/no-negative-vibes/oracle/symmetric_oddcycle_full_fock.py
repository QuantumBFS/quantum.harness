"""Warm-started full-Fock cone search for the fixed symmetric-oddcycle matrix.

The search embeds one already certified nonnegative grade block, keeps the
uncertified complementary grades in their native basis, and perturbs only
the cross-block entries.  Numerical optimization is discovery-only.  A hit
is emitted only after exact rational replay and the trace-compatible gate.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import sympy as sp
from scipy.optimize import minimize

from .exterior_exact5_full_fock_cone import (
    combined_grade_lift,
    exact_trace_compatible_certificate,
)
from .exterior_exact5_shared_cone import (
    _negative_objective_and_gradient,
    exact_simplicial_certificate,
)
from .symmetric_oddcycle_cones import (
    fixed_candidate_matrix,
    load_certificate,
)


SCHEMA = "symmetric-oddcycle-full-fock-warm-v1"
DEFAULT_WEIGHTS = (1.0e-7, 1.0e-9, 1.0e-11)


def _rational_matrix(payload: Sequence[Sequence[Mapping[str, object]]]) -> sp.ImmutableMatrix:
    return sp.ImmutableMatrix(
        [
            [
                sp.Rational(int(entry["numerator"]), int(entry["denominator"]))
                for entry in row
            ]
            for row in payload
        ]
    )


def _known_configuration(known: str) -> tuple[tuple[int, ...], int, int, str]:
    if known == "14":
        return (0, 1, 4, 5, 2, 3), 11, 12, "symmetric_oddcycle_grade14_certificate.json"
    if known == "24":
        return (0, 2, 4, 5, 1, 3), 16, 17, "symmetric_oddcycle_grade24_certificate.json"
    raise ValueError("known must be '14' or '24'")


def preconditioned_problem(
    *,
    known: str = "24",
    certificate_path: str | Path | None = None,
) -> tuple[tuple[sp.ImmutableMatrix, ...], np.ndarray, int, tuple[int, ...]]:
    """Build exact atoms and the certified block-diagonal initial basis."""

    grades, known_stop, split, fixture_name = _known_configuration(known)
    if certificate_path is None:
        certificate_path = Path(__file__).parents[1] / "fixtures" / fixture_name
    payload = load_certificate(certificate_path)
    if tuple(int(grade) for grade in payload["grades"]) != tuple(int(c) for c in known):
        raise ValueError("the supplied certificate does not match the requested known block")
    certified = np.asarray(_rational_matrix(payload["transform"]).tolist(), dtype=float)
    matrix = fixed_candidate_matrix()
    atoms = tuple(combined_grade_lift(atom, grades) for atom in (matrix, matrix.T))
    base = np.eye(32)
    base[1:known_stop, 1:known_stop] = certified
    base /= np.linalg.norm(base, axis=0)[None, :]
    return atoms, base, split, grades


def cross_perturbed_initial(
    base: np.ndarray,
    *,
    split: int,
    epsilon: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Perturb only couplings between the certified and native blocks."""

    if base.shape != (32, 32) or not 0 < split < 32:
        raise ValueError("invalid full-Fock base or split")
    if epsilon < 0.0:
        raise ValueError("epsilon must be nonnegative")
    if epsilon == 0.0:
        return np.array(base, copy=True)
    cross = np.zeros((32, 32))
    cross[:split, split:] = rng.normal(size=(split, 32 - split))
    cross[split:, :split] = rng.normal(size=(32 - split, split))
    candidate = base @ (np.eye(32) + epsilon * cross)
    if np.linalg.matrix_rank(candidate) != 32:
        raise ArithmeticError("cross perturbation produced a singular initial basis")
    return candidate


def _exact_promote(
    atoms: tuple[sp.ImmutableMatrix, ...],
    transform: np.ndarray,
    *,
    max_denominator: int,
    tolerance: float,
) -> dict[str, object] | None:
    certificate = exact_simplicial_certificate(
        atoms,
        transform,
        max_denominator=max_denominator,
    )
    if certificate is None:
        return None
    rational = _rational_matrix(certificate["transform"])
    rays = tuple(sp.ImmutableMatrix(rational[:, column]) for column in range(32))
    promoted = exact_trace_compatible_certificate(
        atoms,
        rays,
        max_denominator=max_denominator,
        tolerance=tolerance,
    )
    if promoted is None:
        raise RuntimeError("exact simplicial hit failed the trace-compatible gate")
    return {
        "status": "exact-trace-compatible-certificate",
        "method": certificate["method"],
        "max_denominator": certificate["max_denominator"],
        "minimum_entry": certificate["minimum_entry"],
        "transform": certificate["transform"],
        "trace_gate": True,
    }


def warm_full_fock_search(
    *,
    known: str,
    certificate_path: str | Path | None,
    attempts: int,
    maxiter: int,
    rng_seed: int,
    weights: Sequence[float] = DEFAULT_WEIGHTS,
    epsilon_min: float = 1.0e-5,
    epsilon_max: float = 1.0e-2,
    include_base: bool = False,
    tolerance: float = 1.0e-9,
    max_denominator: int = 1_048_576,
    resume_transform: Sequence[Sequence[float]] | None = None,
) -> dict[str, object]:
    """Run cross-block starts with warm objective-weight continuation."""

    if attempts < 1 or maxiter < 1:
        raise ValueError("attempts and maxiter must be positive")
    if not weights or any(weight < 0.0 for weight in weights):
        raise ValueError("weights must be nonempty and nonnegative")
    if not 0.0 < epsilon_min <= epsilon_max:
        raise ValueError("invalid epsilon interval")

    exact_atoms, base, split, grades = preconditioned_problem(
        known=known,
        certificate_path=certificate_path,
    )
    float_atoms = tuple(np.asarray(atom.tolist(), dtype=float) for atom in exact_atoms)
    scaled = tuple(
        atom / max(1.0, float(np.max(np.abs(atom)))) for atom in float_atoms
    )
    rng = np.random.default_rng(rng_seed)
    best: dict[str, object] | None = None
    exact: dict[str, object] | None = None

    for attempt in range(attempts):
        if attempt == 0 and resume_transform is not None:
            transform = np.asarray(resume_transform, dtype=float)
            epsilon = None
        elif attempt == 0 and include_base:
            transform = np.array(base, copy=True)
            epsilon = 0.0
        else:
            epsilon = float(
                np.exp(rng.uniform(np.log(epsilon_min), np.log(epsilon_max)))
            )
            transform = cross_perturbed_initial(
                base,
                split=split,
                epsilon=epsilon,
                rng=rng,
            )

        for stage, weight in enumerate(weights):
            result = minimize(
                lambda flat: _negative_objective_and_gradient(
                    flat,
                    scaled,
                    target_margin=0.0,
                    orthogonality_weight=float(weight),
                ),
                transform.ravel(),
                method="L-BFGS-B",
                jac=True,
                options={"maxiter": maxiter, "ftol": 1.0e-15, "gtol": 1.0e-10},
            )
            transform = np.asarray(result.x).reshape((32, 32))
            condition = float(np.linalg.cond(transform))
            transformed = tuple(
                np.linalg.solve(transform, atom @ transform) for atom in float_atoms
            )
            margin = float(min(np.min(atom) for atom in transformed))
            objective = float(result.fun)
            record: dict[str, object] = {
                "attempt": attempt,
                "stage": stage,
                "epsilon": epsilon,
                "orthogonality_weight": float(weight),
                "objective": objective,
                "minimum_entry": margin,
                "condition_number": condition,
                "optimizer_success": bool(result.success),
                "transform": transform.tolist(),
            }
            if best is None or objective < float(best["objective"]):
                best = record
                print(
                    json.dumps(
                        {key: value for key, value in record.items() if key != "transform"},
                        sort_keys=True,
                    ),
                    flush=True,
                )
            if margin >= -tolerance and np.isfinite(condition) and condition < 1.0e10:
                exact = _exact_promote(
                    exact_atoms,
                    transform,
                    max_denominator=max_denominator,
                    tolerance=tolerance,
                )
            if exact is not None:
                break
        if exact is not None:
            break

    assert best is not None
    return {
        "schema": SCHEMA,
        "candidate": "symmetric-oddcycle-fixed-2-1",
        "known_preconditioner": known,
        "grades": list(grades),
        "attempts": attempts,
        "maxiter_per_stage": maxiter,
        "rng_seed": rng_seed,
        "weights": [float(weight) for weight in weights],
        "epsilon_interval": [epsilon_min, epsilon_max],
        "status": (
            "exact-trace-compatible-certificate"
            if exact is not None
            else "no-exact-certificate-found"
        ),
        "best": best,
        "certificate": exact,
    }


def _parse_floats(value: str) -> tuple[float, ...]:
    return tuple(float(item) for item in value.split(","))


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--known", choices=("14", "24"), default="24")
    parser.add_argument("--certificate-path")
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--maxiter", type=int, default=2500)
    parser.add_argument("--rng-seed", type=int, required=True)
    parser.add_argument("--weights", type=_parse_floats, default=DEFAULT_WEIGHTS)
    parser.add_argument("--epsilon-min", type=float, default=1.0e-5)
    parser.add_argument("--epsilon-max", type=float, default=1.0e-2)
    parser.add_argument("--include-base", action="store_true")
    parser.add_argument("--tolerance", type=float, default=1.0e-9)
    parser.add_argument("--max-denominator", type=int, default=1_048_576)
    parser.add_argument("--resume")
    parser.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    resume_transform = None
    if args.resume:
        resume_payload = json.loads(Path(args.resume).read_text(encoding="utf-8"))
        resume_transform = resume_payload["best"]["transform"]
    result = warm_full_fock_search(
        known=args.known,
        certificate_path=args.certificate_path,
        attempts=args.attempts,
        maxiter=args.maxiter,
        rng_seed=args.rng_seed,
        weights=args.weights,
        epsilon_min=args.epsilon_min,
        epsilon_max=args.epsilon_max,
        include_base=args.include_base,
        tolerance=args.tolerance,
        max_denominator=args.max_denominator,
        resume_transform=resume_transform,
    )
    _write_json_atomic(Path(args.output), result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": args.output,
                "best": {
                    key: value
                    for key, value in result["best"].items()
                    if key != "transform"
                },
            },
            allow_nan=False,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "SCHEMA",
    "cross_perturbed_initial",
    "preconditioned_problem",
    "warm_full_fock_search",
]
