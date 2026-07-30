"""Exact spatial block transforms on the blockade action quotient."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from challenge233.sdp.algebra import (
    GaussianRational,
    NEG_I,
    NEG_ONE,
    ONE,
    POS_I,
    PauliWord,
)
from challenge233.sdp.blockade_quotient import BlockadeQuotient
from challenge233.sdp.conjugation_reduction import ConjugationReduction
from challenge233.sdp.exact_linalg import gaussian_column_basis
from challenge233.sdp.symmetry import (
    DihedralElement,
    act_on_word,
    compose,
    dihedral_elements,
    normalize,
)


@dataclass(frozen=True)
class SparseRationalTransform:
    rows: int
    columns: int
    entries: tuple[tuple[int, int, Fraction], ...]

    def __post_init__(self) -> None:
        rows = int(self.rows)
        columns = int(self.columns)
        if rows < 0 or columns < 0:
            raise ValueError(
                "rational transform dimensions must be nonnegative"
            )
        entries = []
        for raw_row, raw_column, raw_value in self.entries:
            if isinstance(raw_value, bool) or isinstance(
                raw_value,
                float,
            ):
                raise TypeError(
                    "rational transform values must be exact"
                )
            row = int(raw_row)
            column = int(raw_column)
            value = Fraction(raw_value)
            if not 0 <= row < rows or not 0 <= column < columns:
                raise ValueError(
                    "rational transform coordinate is out of range"
                )
            if not value:
                raise ValueError(
                    "rational transform entries must be nonzero"
                )
            entries.append((row, column, value))
        entries = tuple(entries)
        coordinates = tuple(
            (row, column) for row, column, _ in entries
        )
        if coordinates != tuple(sorted(set(coordinates))):
            raise ValueError(
                "rational transform coordinates must be unique and sorted"
            )
        object.__setattr__(self, "rows", rows)
        object.__setattr__(self, "columns", columns)
        object.__setattr__(self, "entries", entries)


@dataclass(frozen=True)
class SpatialBlock:
    identifier: str
    irrep_label: str
    irrep_degree: int
    dimension: int
    transform: SparseRationalTransform
    internal_group: tuple[DihedralElement, ...]
    provenance: dict

    def __post_init__(self) -> None:
        identifier = str(self.identifier)
        irrep_label = str(self.irrep_label)
        irrep_degree = int(self.irrep_degree)
        dimension = int(self.dimension)
        internal_group = tuple(self.internal_group)
        if not identifier or not irrep_label:
            raise ValueError(
                "spatial block identifier and irrep label are required"
            )
        if irrep_degree <= 0:
            raise ValueError("spatial irrep degree must be positive")
        if dimension < 0:
            raise ValueError(
                "spatial block dimension must be nonnegative"
            )
        if not isinstance(self.transform, SparseRationalTransform):
            raise TypeError(
                "spatial block transform must be SparseRationalTransform"
            )
        if self.transform.columns != dimension:
            raise ValueError(
                "spatial transform column count must equal block dimension"
            )
        if not internal_group or len(set(internal_group)) != len(
            internal_group
        ):
            raise ValueError(
                "spatial internal group must be nonempty and unique"
            )
        if any(
            not isinstance(element, DihedralElement)
            for element in internal_group
        ):
            raise TypeError(
                "spatial internal group must contain DihedralElement values"
            )
        object.__setattr__(self, "identifier", identifier)
        object.__setattr__(self, "irrep_label", irrep_label)
        object.__setattr__(self, "irrep_degree", irrep_degree)
        object.__setattr__(self, "dimension", dimension)
        object.__setattr__(self, "internal_group", internal_group)
        object.__setattr__(self, "provenance", dict(self.provenance))


def _phase(exponent: int):
    return (ONE, POS_I, NEG_ONE, NEG_I)[int(exponent) % 4]


def _physical_size(size, quotient: BlockadeQuotient) -> int:
    if size is None:
        if quotient.scope != "global":
            raise ValueError(
                "physical size is required for a local quotient action"
            )
        size = len(quotient.window_sites)
    if isinstance(size, bool) or not isinstance(size, int) or size < 3:
        raise ValueError(
            "spatial quotient action size must be an integer at least 3"
        )
    return size


def _validate_action_inputs(
    basis,
    quotient,
    gauge,
):
    basis = tuple(basis)
    if not basis or any(
        not isinstance(word, PauliWord) for word in basis
    ):
        raise TypeError(
            "spatial quotient basis must contain PauliWord values"
        )
    if len(set(basis)) != len(basis):
        raise ValueError("spatial quotient basis words must be unique")
    if not isinstance(quotient, BlockadeQuotient):
        raise TypeError("quotient must be a BlockadeQuotient")
    if not isinstance(gauge, ConjugationReduction):
        raise TypeError("gauge must be a ConjugationReduction")
    if len(quotient.reconstruction) != len(basis):
        raise ValueError(
            "quotient reconstruction does not match the spatial basis"
        )
    if len(gauge.phases) != len(basis):
        raise ValueError(
            "conjugation phases do not match the spatial basis"
        )
    if any(
        not 0 <= index < len(basis)
        for index in quotient.selected_indices
    ):
        raise ValueError(
            "quotient selected index is outside the spatial basis"
        )
    return basis


def induced_quotient_action(
    element,
    basis,
    quotient,
    gauge,
    *,
    size=None,
) -> SparseRationalTransform:
    """Return the exact real-gauged action on selected quotient columns."""
    if not isinstance(element, DihedralElement):
        raise TypeError("spatial action element must be DihedralElement")
    basis = _validate_action_inputs(
        basis,
        quotient,
        gauge,
    )
    size = _physical_size(size, quotient)
    indices = {
        word: index for index, word in enumerate(basis)
    }
    entries = []
    for source_position, source_index in enumerate(
        quotient.selected_indices
    ):
        image = act_on_word(
            element,
            basis[source_index],
            size,
        )
        if image not in indices:
            raise ValueError(
                "spatial basis is not closed under the requested action"
            )
        image_index = indices[image]
        for target_position, coefficient in (
            quotient.reconstruction[image_index]
        ):
            target_index = quotient.selected_indices[target_position]
            gauged = coefficient * _phase(
                gauge.phases[source_index]
                - gauge.phases[target_index]
            )
            if gauged.imag:
                raise ValueError(
                    "quotient action remained complex after real gauge"
                )
            if gauged.real:
                entries.append(
                    (
                        target_position,
                        source_position,
                        gauged.real,
                    )
                )
    return SparseRationalTransform(
        rows=quotient.action_rank,
        columns=quotient.action_rank,
        entries=tuple(sorted(entries)),
    )


def _transform_columns(transform: SparseRationalTransform):
    columns = [dict() for _ in range(transform.columns)]
    for row, column, value in transform.entries:
        columns[column][row] = value
    return tuple(columns)


def _multiply_transforms(
    left: SparseRationalTransform,
    right: SparseRationalTransform,
) -> SparseRationalTransform:
    if left.columns != right.rows:
        raise ValueError(
            "rational transform dimensions do not compose"
        )
    left_columns = _transform_columns(left)
    right_columns = _transform_columns(right)
    entries = []
    for column, right_values in enumerate(right_columns):
        output = {}
        for middle, right_value in right_values.items():
            for row, left_value in left_columns[middle].items():
                value = (
                    output.get(row, Fraction(0))
                    + left_value * right_value
                )
                if value:
                    output[row] = value
                else:
                    output.pop(row, None)
        entries.extend(
            (row, column, value)
            for row, value in output.items()
        )
    return SparseRationalTransform(
        rows=left.rows,
        columns=right.columns,
        entries=tuple(sorted(entries)),
    )


def _identity_transform(dimension: int) -> SparseRationalTransform:
    return SparseRationalTransform(
        rows=dimension,
        columns=dimension,
        entries=tuple(
            (index, index, Fraction(1))
            for index in range(dimension)
        ),
    )


def _linear_combination(terms) -> SparseRationalTransform:
    terms = tuple(terms)
    if not terms:
        raise ValueError(
            "rational transform combination must be nonempty"
        )
    rows = terms[0][1].rows
    columns = terms[0][1].columns
    values = {}
    for raw_coefficient, transform in terms:
        coefficient = Fraction(raw_coefficient)
        if transform.rows != rows or transform.columns != columns:
            raise ValueError(
                "rational transform combination dimensions differ"
            )
        for row, column, value in transform.entries:
            coordinate = (row, column)
            updated = (
                values.get(coordinate, Fraction(0))
                + coefficient * value
            )
            if updated:
                values[coordinate] = updated
            else:
                values.pop(coordinate, None)
    return SparseRationalTransform(
        rows=rows,
        columns=columns,
        entries=tuple(
            (row, column, value)
            for (row, column), value in sorted(values.items())
        ),
    )


def _projector_image(
    projector: SparseRationalTransform,
) -> SparseRationalTransform:
    columns = _transform_columns(projector)
    exact = gaussian_column_basis(
        tuple(
            {
                row: GaussianRational(value)
                for row, value in column.items()
            }
            for column in columns
        )
    )
    selected_columns = tuple(
        columns[index] for index in exact.selected
    )
    return SparseRationalTransform(
        rows=projector.rows,
        columns=len(selected_columns),
        entries=tuple(
            sorted(
                (
                    row,
                    column,
                    value,
                )
                for column, values in enumerate(selected_columns)
                for row, value in values.items()
            )
        ),
    )


def _require_projector(
    projector: SparseRationalTransform,
) -> None:
    if _multiply_transforms(projector, projector) != projector:
        raise ArithmeticError(
            "spatial slice formula is not an exact projector"
        )


def verify_quotient_group_action(
    size,
    basis,
    quotient,
    gauge,
    elements,
) -> dict:
    """Verify the exact representation law on a closed element set."""
    size = _physical_size(size, quotient)
    elements = tuple(
        normalize(element, size) for element in elements
    )
    if not elements or len(set(elements)) != len(elements):
        raise ValueError(
            "internal spatial group elements must be nonempty and unique"
        )
    element_set = set(elements)
    identity = DihedralElement(0, False)
    if identity not in element_set:
        raise ValueError(
            "internal spatial group must contain the identity"
        )
    actions = {
        element: induced_quotient_action(
            element,
            basis,
            quotient,
            gauge,
            size=size,
        )
        for element in elements
    }
    expected_identity = _identity_transform(
        quotient.action_rank
    )
    if actions[identity] != expected_identity:
        raise ValueError(
            "induced quotient identity action is not exact"
        )
    for left in elements:
        for right in elements:
            product = compose(left, right, size)
            if product not in element_set:
                raise ValueError(
                    "internal spatial element set is not closed"
                )
            if _multiply_transforms(
                actions[left],
                actions[right],
            ) != actions[product]:
                raise ValueError(
                    "induced quotient action violates the group law"
                )
    return {
        "status": "verified",
        "element_count": len(elements),
        "dimension": quotient.action_rank,
    }


def verify_induced_quotient_action(
    size,
    element,
    basis,
    quotient,
    gauge,
    action,
) -> dict:
    """Verify one exported exact action against the original basis."""
    if not isinstance(action, SparseRationalTransform):
        raise TypeError(
            "action must be a SparseRationalTransform"
        )
    expected = induced_quotient_action(
        element,
        basis,
        quotient,
        gauge,
        size=_physical_size(size, quotient),
    )
    if action != expected:
        raise ValueError("induced quotient action mismatch")
    return {
        "status": "verified",
        "dimension": quotient.action_rank,
    }


def build_global_d4_reduction(
    size,
    basis,
    quotient,
    gauge,
) -> tuple[SpatialBlock, ...]:
    size = _physical_size(size, quotient)
    if size != 4:
        raise ValueError(
            "global D4 reduction requires the N=4 anchor"
        )
    if quotient.scope != "global":
        raise ValueError(
            "global D4 reduction requires a global quotient"
        )
    basis = _validate_action_inputs(basis, quotient, gauge)
    group = dihedral_elements(4)
    verify_quotient_group_action(
        4,
        basis,
        quotient,
        gauge,
        group,
    )
    identity = _identity_transform(quotient.action_rank)
    translation = induced_quotient_action(
        DihedralElement(1, False),
        basis,
        quotient,
        gauge,
        size=4,
    )
    translation_squared = induced_quotient_action(
        DihedralElement(2, False),
        basis,
        quotient,
        gauge,
        size=4,
    )
    translation_cubed = induced_quotient_action(
        DihedralElement(3, False),
        basis,
        quotient,
        gauge,
        size=4,
    )
    reflection = induced_quotient_action(
        DihedralElement(0, True),
        basis,
        quotient,
        gauge,
        size=4,
    )
    specifications = (
        ("k0+", 1, 1, 1),
        ("k0-", 1, -1, 1),
        ("kpi+", -1, 1, 1),
        ("kpi-", -1, -1, 1),
    )
    blocks = []
    projectors = []
    for label, translation_sign, reflection_sign, degree in (
        specifications
    ):
        momentum_projector = _linear_combination(
            (
                (Fraction(1, 4), identity),
                (Fraction(translation_sign, 4), translation),
                (Fraction(1, 4), translation_squared),
                (
                    Fraction(translation_sign, 4),
                    translation_cubed,
                ),
            )
        )
        reflection_projector = _linear_combination(
            (
                (Fraction(1, 2), identity),
                (Fraction(reflection_sign, 2), reflection),
            )
        )
        projector = _multiply_transforms(
            momentum_projector,
            reflection_projector,
        )
        _require_projector(projector)
        transform = _projector_image(projector)
        projectors.append(projector)
        blocks.append(
            SpatialBlock(
                identifier=f"global-d4-{label}",
                irrep_label=label,
                irrep_degree=degree,
                dimension=transform.columns,
                transform=transform,
                internal_group=group,
                provenance={
                    "scope": "global",
                    "projector": (
                        "1/4(I+tT+T^2+tT^3)"
                        " 1/2(I+rR)"
                    ),
                    "translation_sign": translation_sign,
                    "reflection_sign": reflection_sign,
                },
            )
        )
    generic_projector = _multiply_transforms(
        _linear_combination(
            (
                (Fraction(1, 2), identity),
                (Fraction(-1, 2), translation_squared),
            )
        ),
        _linear_combination(
            (
                (Fraction(1, 2), identity),
                (Fraction(1, 2), reflection),
            )
        ),
    )
    _require_projector(generic_projector)
    generic_transform = _projector_image(generic_projector)
    projectors.append(generic_projector)
    blocks.append(
        SpatialBlock(
            identifier="global-d4-generic-k1-k3",
            irrep_label="generic-k1-k3",
            irrep_degree=2,
            dimension=generic_transform.columns,
            transform=generic_transform,
            internal_group=group,
            provenance={
                "scope": "global",
                "projector": "1/4(I-T^2)(I+R)",
                "carrier": "reflection-even multiplicity slice",
            },
        )
    )
    for left_index, left in enumerate(projectors):
        for right in projectors[left_index + 1 :]:
            if _multiply_transforms(left, right).entries:
                raise ArithmeticError(
                    "global D4 spatial slices are not orthogonal"
                )
    if sum(
        block.irrep_degree * block.dimension
        for block in blocks
    ) != quotient.action_rank:
        raise ArithmeticError(
            "global D4 spatial blocks do not reconstruct quotient rank"
        )
    return tuple(blocks)


def build_local_reflection_reduction(
    size,
    basis,
    window_sites,
    quotient,
    gauge,
) -> tuple[SpatialBlock, ...]:
    size = _physical_size(size, quotient)
    if quotient.scope != "local":
        raise ValueError(
            "local reflection reduction requires a local quotient"
        )
    window_sites = tuple(int(site) for site in window_sites)
    if (
        not window_sites
        or len(set(window_sites)) != len(window_sites)
        or any(not 0 <= site < size for site in window_sites)
    ):
        raise ValueError(
            "local reflection window must contain unique in-range sites"
        )
    if quotient.window_sites != window_sites:
        raise ValueError(
            "local reflection window does not match quotient window"
        )
    basis = _validate_action_inputs(basis, quotient, gauge)
    reversed_window = tuple(reversed(window_sites))
    candidates = tuple(
        element
        for element in dihedral_elements(size)
        if element.reflected
        and tuple(
            (
                element.shift - site
            )
            % size
            for site in window_sites
        )
        == reversed_window
    )
    if len(candidates) != 1:
        raise ValueError(
            "local window must have one exact midpoint reflection"
        )
    stabilizer = candidates[0]
    group = (
        DihedralElement(0, False),
        stabilizer,
    )
    verify_quotient_group_action(
        size,
        basis,
        quotient,
        gauge,
        group,
    )
    identity = _identity_transform(quotient.action_rank)
    reflection = induced_quotient_action(
        stabilizer,
        basis,
        quotient,
        gauge,
        size=size,
    )
    blocks = []
    projectors = []
    for label, sign in (
        ("reflection-even", 1),
        ("reflection-odd", -1),
    ):
        projector = _linear_combination(
            (
                (Fraction(1, 2), identity),
                (Fraction(sign, 2), reflection),
            )
        )
        _require_projector(projector)
        transform = _projector_image(projector)
        projectors.append(projector)
        blocks.append(
            SpatialBlock(
                identifier=f"local-{label}",
                irrep_label=label,
                irrep_degree=1,
                dimension=transform.columns,
                transform=transform,
                internal_group=group,
                provenance={
                    "scope": "local-window-stabilizer",
                    "window_sites": window_sites,
                    "stabilizer": {
                        "shift": stabilizer.shift,
                        "reflected": stabilizer.reflected,
                    },
                    "projector": (
                        "1/2(I+R_window)"
                        if sign == 1
                        else "1/2(I-R_window)"
                    ),
                },
            )
        )
    if _multiply_transforms(
        projectors[0],
        projectors[1],
    ).entries:
        raise ArithmeticError(
            "local reflection spatial slices are not orthogonal"
        )
    if sum(block.dimension for block in blocks) != (
        quotient.action_rank
    ):
        raise ArithmeticError(
            "local reflection blocks do not reconstruct quotient rank"
        )
    return tuple(blocks)


def _spatial_block_sequence(blocks) -> tuple[SpatialBlock, ...]:
    blocks = tuple(blocks)
    if any(
        not isinstance(block, SpatialBlock) for block in blocks
    ):
        raise TypeError(
            "spatial block inventory must contain SpatialBlock values"
        )
    return blocks


def verify_global_d4_reduction(
    size,
    basis,
    quotient,
    gauge,
    blocks,
) -> dict:
    """Verify all global D4 slices against exact reconstructed slices."""
    blocks = _spatial_block_sequence(blocks)
    expected_labels = (
        "k0+",
        "k0-",
        "kpi+",
        "kpi-",
        "generic-k1-k3",
    )
    if tuple(block.irrep_label for block in blocks) != (
        expected_labels
    ):
        raise ValueError("global D4 block inventory mismatch")
    expected_degrees = (1, 1, 1, 1, 2)
    if tuple(block.irrep_degree for block in blocks) != (
        expected_degrees
    ):
        raise ValueError("global D4 irrep degree mismatch")
    expected = build_global_d4_reduction(
        size,
        basis,
        quotient,
        gauge,
    )
    for actual, reference in zip(blocks, expected):
        if actual.transform != reference.transform:
            raise ValueError(
                "global D4 block transform mismatch"
            )
        if actual.dimension != reference.dimension:
            raise ValueError(
                "global D4 block dimension mismatch"
            )
        if actual.internal_group != reference.internal_group:
            raise ValueError(
                "global D4 internal group mismatch"
            )
        if (
            actual.identifier != reference.identifier
            or actual.provenance != reference.provenance
        ):
            raise ValueError(
                "global D4 block metadata mismatch"
            )
    degree_sum = sum(
        block.irrep_degree * block.dimension
        for block in blocks
    )
    if degree_sum != quotient.action_rank:
        raise ValueError(
            "global D4 degree-weighted dimension sum mismatch"
        )
    return {
        "status": "verified",
        "block_count": len(blocks),
        "degree_weighted_dimension": degree_sum,
    }


def verify_local_reflection_reduction(
    size,
    basis,
    window_sites,
    quotient,
    gauge,
    blocks,
) -> dict:
    """Verify the two window-stabilizer reflection slices exactly."""
    blocks = _spatial_block_sequence(blocks)
    expected_labels = (
        "reflection-even",
        "reflection-odd",
    )
    if tuple(block.irrep_label for block in blocks) != (
        expected_labels
    ):
        raise ValueError(
            "local reflection block inventory mismatch"
        )
    if tuple(block.irrep_degree for block in blocks) != (1, 1):
        raise ValueError(
            "local reflection irrep degree mismatch"
        )
    expected = build_local_reflection_reduction(
        size,
        basis,
        window_sites,
        quotient,
        gauge,
    )
    for actual, reference in zip(blocks, expected):
        if actual.internal_group != reference.internal_group:
            raise ValueError(
                "local reflection internal group mismatch"
            )
        if actual.transform != reference.transform:
            raise ValueError(
                "local reflection block transform mismatch"
            )
        if actual.dimension != reference.dimension:
            raise ValueError(
                "local reflection block dimension mismatch"
            )
        if (
            actual.identifier != reference.identifier
            or actual.provenance != reference.provenance
        ):
            raise ValueError(
                "local reflection block metadata mismatch"
            )
    dimension_sum = sum(block.dimension for block in blocks)
    if dimension_sum != quotient.action_rank:
        raise ValueError(
            "local reflection dimension sum mismatch"
        )
    return {
        "status": "verified",
        "block_count": len(blocks),
        "dimension": dimension_sum,
    }
