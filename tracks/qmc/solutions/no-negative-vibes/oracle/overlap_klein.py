from __future__ import annotations

from dataclasses import dataclass

from oracle.fock_basis import QuadraticBasisElement, quadratic_term


@dataclass(frozen=True)
class OverlapGeometry:
    modes: int
    blocks: tuple[tuple[int, ...], ...]
    ring_edges: tuple[tuple[int, int], ...]
    diagonal_edges: tuple[tuple[int, int], ...]
    bridge_edges: tuple[tuple[int, int], ...]


_GEOMETRY = OverlapGeometry(
    modes=6,
    blocks=((0, 1, 2, 3), (2, 3, 4, 5)),
    ring_edges=(
        (0, 1),
        (0, 3),
        (1, 2),
        (2, 3),
        (2, 5),
        (3, 4),
        (4, 5),
    ),
    diagonal_edges=((0, 2), (1, 3), (2, 4), (3, 5)),
    bridge_edges=((0, 4), (1, 5)),
)


def overlap_geometry() -> OverlapGeometry:
    return _GEOMETRY


def support_edges(mask: str) -> tuple[tuple[int, int], ...]:
    geometry = overlap_geometry()
    masks = {
        "rings": geometry.ring_edges,
        "rings-bridges": geometry.ring_edges + geometry.bridge_edges,
        "rings-diagonals-bridges": (
            geometry.ring_edges
            + geometry.diagonal_edges
            + geometry.bridge_edges
        ),
    }
    try:
        return tuple(sorted(masks[mask]))
    except KeyError as error:
        raise ValueError(f"unknown support mask: {mask}") from error


def _basis_element(
    label: str, kind: str, i: int, j: int
) -> QuadraticBasisElement:
    return QuadraticBasisElement(
        label=label,
        kind=kind,
        i=i,
        j=j,
        fock=quadratic_term(_GEOMETRY.modes, kind, i, j),
    )


def quadratic_basis(
    family: str, mask: str
) -> tuple[QuadraticBasisElement, ...]:
    if family not in ("number-conserving", "bdg"):
        raise ValueError(f"unknown quadratic family: {family}")

    elements = [
        _basis_element(f"n{index}", "hop", index, index)
        for index in range(_GEOMETRY.modes)
    ]
    for i, j in support_edges(mask):
        elements.extend(
            (
                _basis_element(f"h{i}<-{j}", "hop", i, j),
                _basis_element(f"h{j}<-{i}", "hop", j, i),
            )
        )
        if family == "bdg":
            elements.extend(
                (
                    _basis_element(f"pc{i},{j}", "pair_create", i, j),
                    _basis_element(f"pa{i},{j}", "pair_annihilate", i, j),
                )
            )
    return tuple(sorted(elements, key=lambda element: element.label))


def bridge_labels(family: str) -> tuple[str, ...]:
    if family not in ("number-conserving", "bdg"):
        raise ValueError(f"unknown quadratic family: {family}")

    labels: list[str] = []
    for i, j in _GEOMETRY.bridge_edges:
        labels.extend((f"h{i}<-{j}", f"h{j}<-{i}"))
        if family == "bdg":
            labels.extend((f"pc{i},{j}", f"pa{i},{j}"))
    return tuple(sorted(labels))
