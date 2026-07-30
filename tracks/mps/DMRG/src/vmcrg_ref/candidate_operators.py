from __future__ import annotations

from typing import Literal

from .operators import EVEN_SHAPES, OperatorShape, Vertex, d4_orbit


PairTie = Literal["axis5", "generic43"]


_CONFIRMED_PAIRS = EVEN_SHAPES[:7]

_RECONSTRUCTED_PAIRS = (
    OperatorShape("candidate_two_08_32", ((0, 0), (3, 2)), "even"),
    OperatorShape("candidate_two_09_axis4", ((0, 0), (4, 0)), "even"),
    OperatorShape("candidate_two_10_41", ((0, 0), (4, 1)), "even"),
    OperatorShape("candidate_two_11_33", ((0, 0), (3, 3)), "even"),
    OperatorShape("candidate_two_12_42", ((0, 0), (4, 2)), "even"),
)

_PAIR_TIES: dict[PairTie, OperatorShape] = {
    "axis5": OperatorShape(
        "candidate_two_13_axis5", ((0, 0), (5, 0)), "even"
    ),
    "generic43": OperatorShape(
        "candidate_two_13_43", ((0, 0), (4, 3)), "even"
    ),
}


# The ordering is the explicit reconstruction ordering documented in
# docs/original_26_coordinate_reconstruction.md. Published survivors keep their
# Supplement names; the other seven shapes remain visibly marked as candidates.
_RECONSTRUCTED_FOURS = (
    OperatorShape(
        "even_08_square", ((0, 0), (0, 1), (1, 0), (1, 1)), "even"
    ),
    OperatorShape(
        "even_10_t", ((0, 0), (0, 1), (0, 2), (1, 1)), "even"
    ),
    OperatorShape(
        "even_09_diamond", ((0, 1), (1, 0), (1, 2), (2, 1)), "even"
    ),
    OperatorShape(
        "even_12_four", ((0, 0), (0, 1), (1, 1), (1, 2)), "even"
    ),
    OperatorShape(
        "even_11_four", ((0, 0), (0, 1), (0, 2), (1, 0)), "even"
    ),
    OperatorShape(
        "candidate_four_06", ((0, 0), (0, 1), (1, 0), (1, 2)), "even"
    ),
    OperatorShape(
        "even_13_four", ((0, 0), (1, 1), (1, 2), (2, 1)), "even"
    ),
    OperatorShape(
        "candidate_four_08", ((0, 0), (0, 1), (1, 2), (2, 1)), "even"
    ),
    OperatorShape(
        "candidate_four_09", ((0, 0), (0, 2), (1, 1), (2, 1)), "even"
    ),
    OperatorShape(
        "candidate_four_10", ((0, 0), (0, 1), (0, 2), (2, 1)), "even"
    ),
    OperatorShape(
        "candidate_four_11", ((0, 0), (0, 1), (2, 0), (2, 1)), "even"
    ),
    OperatorShape(
        "candidate_four_12", ((0, 0), (0, 1), (1, 2), (2, 0)), "even"
    ),
    OperatorShape(
        "candidate_four_13", ((0, 0), (0, 1), (1, 1), (2, 2)), "even"
    ),
)


def _canonical(vertices: tuple[Vertex, ...]) -> tuple[Vertex, ...]:
    return min(d4_orbit(vertices))


def candidate_even_shapes(pair_tie: PairTie) -> tuple[OperatorShape, ...]:
    """Return one explicitly labeled reconstruction of the initial 26 terms."""
    if pair_tie not in _PAIR_TIES:
        choices = ", ".join(sorted(_PAIR_TIES))
        raise ValueError(f"pair_tie must be one of: {choices}")
    shapes = (
        *_CONFIRMED_PAIRS,
        *_RECONSTRUCTED_PAIRS,
        _PAIR_TIES[pair_tie],
        *_RECONSTRUCTED_FOURS,
    )
    canonical = [_canonical(shape.vertices) for shape in shapes]
    if len(shapes) != 26 or len(set(canonical)) != 26:
        raise AssertionError("candidate basis must contain 26 distinct D4 orbits")
    return shapes


def candidate_basis_metadata(pair_tie: PairTie) -> list[dict[str, object]]:
    published = {_canonical(shape.vertices) for shape in EVEN_SHAPES}
    result = []
    for index, shape in enumerate(candidate_even_shapes(pair_tie), start=1):
        result.append(
            {
                "index": index,
                "name": shape.name,
                "vertices": [list(vertex) for vertex in shape.vertices],
                "arity": len(shape.vertices),
                "evidence": (
                    "published_retained"
                    if _canonical(shape.vertices) in published
                    else "reconstructed_candidate"
                ),
            }
        )
    return result


def published_survivor_indices(
    shapes: tuple[OperatorShape, ...],
) -> tuple[int, ...]:
    published = {_canonical(shape.vertices) for shape in EVEN_SHAPES}
    return tuple(
        index
        for index, shape in enumerate(shapes)
        if _canonical(shape.vertices) in published
    )
