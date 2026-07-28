"""Independent numerical verifier for sparse graph-33 SDP bases."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from itertools import combinations
from pathlib import Path

from problem import EDGES, KNOWN_LOWER_BOUND, PROBLEM_ID, VERTICES
from theta_relaxation import basis_subsets, solve_theta_basis

PREFIX = "OMNIEVOLVE_GRAPH33_RESULT="
BASELINE_UPPER = 2.002487136812566
FULL_DEGREE3_UPPER = 2.000057479970073
MAX_EXTRA = 16


def load_candidate(path: str) -> dict[str, object]:
    candidate_path = Path(path).resolve()
    spec = importlib.util.spec_from_file_location("evolved_graph33_candidate", candidate_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import candidate {candidate_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    builder = getattr(module, "build_candidate", None)
    if not callable(builder):
        raise AttributeError("candidate must define build_candidate()")
    candidate = builder()
    if not isinstance(candidate, dict):
        raise TypeError("build_candidate() must return a dictionary")
    return candidate


def validate_extra_basis(raw: object) -> tuple[tuple[int, ...], ...]:
    if not isinstance(raw, list):
        raise TypeError("extra_basis_subsets must be a list")
    if len(raw) > MAX_EXTRA:
        raise ValueError(f"at most {MAX_EXTRA} extra basis subsets are allowed")
    parsed: list[tuple[int, ...]] = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or not all(isinstance(x, int) for x in item):
            raise TypeError("each extra basis subset must be a list of integer vertices")
        subset = tuple(sorted(item))
        if len(subset) not in {3, 4}:
            raise ValueError("extra basis subsets must have degree 3 or 4")
        if len(set(subset)) != len(subset) or any(x not in VERTICES for x in subset):
            raise ValueError(f"invalid square-free graph subset {item!r}")
        parsed.append(subset)
    if len(set(parsed)) != len(parsed):
        raise ValueError("extra basis subsets must be unique")
    return tuple(parsed)


def evaluate(candidate: dict[str, object]) -> dict[str, object]:
    if candidate.get("problem_id") != PROBLEM_ID:
        raise ValueError(f"problem_id must remain {PROBLEM_ID!r}")
    extra = validate_extra_basis(candidate.get("extra_basis_subsets"))
    base = basis_subsets(len(VERTICES), 2)
    result = solve_theta_basis(len(VERTICES), EDGES, base + extra)
    upper = float(result["value"])
    if not math.isfinite(upper) or upper < KNOWN_LOWER_BOUND - 2e-7:
        raise RuntimeError("solver returned an invalid upper/lower ordering")
    gap = max(upper - KNOWN_LOWER_BOUND, 0.0)
    baseline_gap = BASELINE_UPPER - KNOWN_LOWER_BOUND
    improvement = max(0.0, min(1.0, (baseline_gap - gap) / baseline_gap))
    # Quality dominates, with a mild incentive to find a sparse certificate.
    size_penalty = 0.04 * len(extra) / MAX_EXTRA
    score = max(0.0, min(0.999, 0.50 + 0.49 * improvement - size_penalty))
    signature = hashlib.sha256(json.dumps(extra).encode("utf-8")).hexdigest()[:16]
    return {
        "valid": True,
        "passed": True,
        "score": score,
        "problem_id": PROBLEM_ID,
        "upper_bound": upper,
        "known_lower_bound": KNOWN_LOWER_BOUND,
        "gap": gap,
        "improvement_fraction": improvement,
        "extra_basis_count": len(extra),
        "extra_basis_subsets": extra,
        "matrix_size": result["matrix_size"],
        "constraint_count": result["constraint_count"],
        "min_eigenvalue": result["min_eigenvalue"],
        "solver_status": result["status"],
        "beats_paper_theta7": upper < 2.0013,
        "numerically_closed": gap <= 1e-7,
        # Numerical SDP output is a search result, not yet an exact rational SOHS.
        "exact_certificate": False,
        "behavior_signature": signature,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: verify_candidate.py CANDIDATE.py", file=sys.stderr)
        return 2
    try:
        result = evaluate(load_candidate(sys.argv[1]))
    except Exception as exc:
        result = {
            "valid": False,
            "passed": False,
            "score": 0.0,
            "error": f"{type(exc).__name__}: {exc}",
        }
    print(PREFIX + json.dumps(result, sort_keys=True))
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
