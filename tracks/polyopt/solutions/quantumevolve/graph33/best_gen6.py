"""Restart seed from experiment e77d30c4b48b45fd generation 6."""

from __future__ import annotations

PROBLEM_ID = "uncertainty-table4-graph33-v1"


def build_candidate() -> dict[str, object]:
    """Return the best independently verified sparse basis from generation 6."""
    return {
        "problem_id": PROBLEM_ID,
        "extra_basis_subsets": [
            (0, 1, 2),
            (0, 3, 4),
            (0, 5, 6),
            (1, 3, 4),
            (1, 4, 5),
            (2, 5, 6),
            (3, 4, 6),
            (2, 3, 6),
            (0, 1, 3),
            (0, 2, 3),
            (0, 4, 5),
            (0, 4, 6),
            (1, 2, 3),
            (0, 3, 6),
            (0, 2, 6),
            (4, 5, 6),
        ],
        "notes": (
            "Verified restart seed: upper=2.0003040316203746 with a 45x45 "
            "moment matrix. Candidate prose from the original run is omitted "
            "because the fixed evaluator, not the prose, defines graph semantics."
        ),
    }
