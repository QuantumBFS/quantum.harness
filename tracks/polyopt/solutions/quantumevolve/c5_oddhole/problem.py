"""Immutable definition of the five-cycle (C5) anti-commutation graph.

C5 is the smallest graph with alpha = 2 and Lovasz theta = sqrt(5) > alpha.
It is the canonical "open Bell constant" from Table 4 of arXiv:2310.00612.

The odd-hole inequality (Eq. 25) applies directly: since C5 itself is an
induced odd cycle, sum_i <A_i>^2 <= floor(5/2) = 2.
"""

from __future__ import annotations

PROBLEM_ID = "uncertainty-c5-oddhole-v1"
VERTICES = tuple(range(5))

# C5 = 5-cycle: edges form a pentagon.
EDGES = frozenset({(0, 1), (1, 2), (2, 3), (3, 4), (0, 4)})

KNOWN_LOWER_BOUND = 2.0  # alpha(C5) = 2
ODD_HOLE = VERTICES  # The entire graph is an induced C5
ODD_HOLE_BOUND = 2  # floor(5/2) = 2
