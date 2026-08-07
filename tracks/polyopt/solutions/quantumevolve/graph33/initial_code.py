"""Evolution seed for #232 graph 33: discover a sparse strong SDP basis."""

from __future__ import annotations

PROBLEM_ID = "uncertainty-table4-graph33-v1"


def build_candidate() -> dict[str, object]:
    """Return extra square-free words added to the immutable degree-2 basis.

    The evaluator validates every word and reconstructs every moment identity
    itself.  Evolve at most 16 degree-3/4 subsets: the goal is to approach the
    full degree-3 upper bound with a much smaller PSD matrix.
    """
    return {
        "problem_id": PROBLEM_ID,
        "extra_basis_subsets": [],
        "notes": "Degree-2 calibrated baseline; search for high-value triples.",
    }
