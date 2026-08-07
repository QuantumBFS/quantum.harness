"""Best sparse-basis candidate from experiment db6f0742e33b4781 generation 9."""

from __future__ import annotations


def build_candidate() -> dict[str, object]:
    return {
        "problem_id": "uncertainty-table4-graph33-v1",
        "extra_basis_subsets": [
            (0, 1, 2),
            (0, 1, 3),
            (0, 1, 4),
            (0, 2, 3),
            (0, 2, 5),
            (0, 3, 4),
            (0, 3, 5),
            (0, 4, 5),
            (1, 2, 3),
            (1, 2, 4),
            (1, 2, 5),
            (1, 3, 4),
            (1, 4, 5),
            (2, 3, 5),
            (2, 4, 5),
            (3, 4, 5),
        ],
        "notes": (
            "Verified numerical best: upper=2.000171933567948 with a 45x45 "
            "moment matrix; used as the source basis for dual export."
        ),
    }
