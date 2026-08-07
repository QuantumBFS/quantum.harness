"""Compose exact, detuning-independent Ky Fan solver reductions."""

from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
import hashlib
from pathlib import Path

from challenge233.sdp.algebra import GaussianRational
from challenge233.sdp.blockade_quotient import (
    BlockadeQuotient,
    build_blockade_quotient,
    exact_ldlt_pivots,
    kernel_localizer_rows,
    slater_gram,
)
from challenge233.sdp.conjugation_reduction import (
    ConjugationReduction,
    SparseRationalEntry,
    SparseRationalPSDBlock,
    build_conjugation_reduction,
)
from challenge233.sdp.equality_reduction import (
    EqualityReduction,
    compress_equalities,
)
from challenge233.sdp.hierarchy import LOCAL_LEVELS
from challenge233.sdp.kyfan import (
    LinearEquality,
    RationalLinearForm,
)
from challenge233.sdp.kyfan_sparse import KyFanStructure
from challenge233.sdp.kyfan_v2_artifact import (
    canonical_json_bytes,
    logical_structure_sha256,
)
from challenge233.sdp.spatial_reduction import (
    SparseRationalTransform,
    SpatialBlock,
    build_global_d4_reduction,
    build_local_reflection_reduction,
)


REDUCTION_SOURCE_PATHS = (
    "src/challenge233/sdp/exact_linalg.py",
    "src/challenge233/sdp/conjugation_reduction.py",
    "src/challenge233/sdp/blockade_quotient.py",
    "src/challenge233/sdp/equality_reduction.py",
    "src/challenge233/sdp/spatial_reduction.py",
    "src/challenge233/sdp/kyfan_presolve.py",
    "src/challenge233/sdp/kyfan_v2_artifact.py",
    "src/challenge233/sdp/verify_kyfan_structure.py",
    "src/challenge233/sdp/verify_kyfan_reduction.py",
)


@dataclass(frozen=True)
class ReducedRealPSDBlock:
    identifier: str
    dimension: int
    upper_entries: tuple[SparseRationalEntry, ...]
    source_block: str
    spatial_block: str

    def __post_init__(self) -> None:
        identifier = str(self.identifier)
        source_block = str(self.source_block)
        spatial_block = str(self.spatial_block)
        dimension = int(self.dimension)
        entries = tuple(self.upper_entries)
        if not identifier or not source_block or not spatial_block:
            raise ValueError(
                "reduced PSD identifiers must be non-empty"
            )
        if dimension <= 0:
            raise ValueError(
                "reduced PSD dimension must be positive"
            )
        coordinates = tuple(
            (entry.row, entry.column) for entry in entries
        )
        if coordinates != tuple(sorted(set(coordinates))):
            raise ValueError(
                "reduced PSD coordinates must be unique and sorted"
            )
        if any(column >= dimension for _, column in coordinates):
            raise ValueError(
                "reduced PSD coordinate is out of range"
            )
        object.__setattr__(self, "identifier", identifier)
        object.__setattr__(self, "dimension", dimension)
        object.__setattr__(self, "upper_entries", entries)
        object.__setattr__(self, "source_block", source_block)
        object.__setattr__(self, "spatial_block", spatial_block)


@dataclass(frozen=True)
class KyFanSolverReduction:
    structure_sha256: str
    conjugation: ConjugationReduction
    quotient: BlockadeQuotient
    spatial: tuple[SpatialBlock, ...]
    equality: EqualityReduction
    kept_equalities: tuple[LinearEquality, ...]
    selected_view: str
    psd_blocks: tuple[ReducedRealPSDBlock, ...]
    objective_components: dict[str, RationalLinearForm]
    statistics: dict
    resource_estimate: dict
    source_hashes: dict[str, str]

    def __post_init__(self) -> None:
        digest = _sha256(self.structure_sha256, "structure_sha256")
        spatial = tuple(self.spatial)
        kept_equalities = tuple(self.kept_equalities)
        psd_blocks = tuple(self.psd_blocks)
        if not isinstance(self.conjugation, ConjugationReduction):
            raise TypeError(
                "conjugation must be a ConjugationReduction"
            )
        if not isinstance(self.quotient, BlockadeQuotient):
            raise TypeError("quotient must be a BlockadeQuotient")
        if any(not isinstance(block, SpatialBlock) for block in spatial):
            raise TypeError("spatial must contain SpatialBlock values")
        if not isinstance(self.equality, EqualityReduction):
            raise TypeError("equality must be an EqualityReduction")
        if any(
            not isinstance(row, LinearEquality)
            for row in kept_equalities
        ):
            raise TypeError(
                "kept_equalities must contain LinearEquality values"
            )
        if self.selected_view != self.equality.selected_view:
            raise ValueError(
                "selected view does not match equality reduction"
            )
        if any(
            not isinstance(block, ReducedRealPSDBlock)
            for block in psd_blocks
        ):
            raise TypeError(
                "psd_blocks must contain ReducedRealPSDBlock values"
            )
        if set(self.objective_components) != {
            "rabi",
            "minus-number",
        }:
            raise ValueError(
                "reduced objective component inventory mismatch"
            )
        object.__setattr__(self, "structure_sha256", digest)
        object.__setattr__(self, "spatial", spatial)
        object.__setattr__(
            self,
            "kept_equalities",
            kept_equalities,
        )
        object.__setattr__(self, "psd_blocks", psd_blocks)
        object.__setattr__(
            self,
            "objective_components",
            dict(self.objective_components),
        )
        object.__setattr__(self, "statistics", dict(self.statistics))
        object.__setattr__(
            self,
            "resource_estimate",
            dict(self.resource_estimate),
        )
        object.__setattr__(
            self,
            "source_hashes",
            dict(self.source_hashes),
        )


def _sha256(value, component):
    value = str(value)
    if len(value) != 64 or any(
        character not in "0123456789abcdef"
        for character in value
    ):
        raise ValueError(f"{component} must be a lowercase SHA-256")
    return value


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _source_hashes() -> dict[str, str]:
    root = _project_root()
    return {
        relative: hashlib.sha256(
            (root / relative).read_bytes()
        ).hexdigest()
        for relative in REDUCTION_SOURCE_PATHS
    }


def _window_sites(structure: KyFanStructure):
    if structure.hierarchy.startswith("global-d"):
        return None
    levels = {
        level.name: level for level in LOCAL_LEVELS
    }
    try:
        level = levels[structure.hierarchy]
    except KeyError as error:
        raise ValueError(
            "unknown hierarchy for solver reduction"
        ) from error
    return tuple(range(level.range_sites))


def _compose_full_transform(
    basis_dimension: int,
    quotient: BlockadeQuotient,
    block: SpatialBlock,
) -> SpatialBlock:
    if block.transform.rows != quotient.action_rank:
        raise ValueError(
            "spatial transform does not match quotient rank"
        )
    entries = tuple(
        (
            quotient.selected_indices[row],
            column,
            value,
        )
        for row, column, value in block.transform.entries
    )
    transform = SparseRationalTransform(
        rows=basis_dimension,
        columns=block.transform.columns,
        entries=entries,
    )
    return SpatialBlock(
        identifier=block.identifier,
        irrep_label=block.irrep_label,
        irrep_degree=block.irrep_degree,
        dimension=block.dimension,
        transform=transform,
        internal_group=block.internal_group,
        provenance={
            **block.provenance,
            "transform_codomain": (
                "phase-gauged-full-test-index-basis"
            ),
            "quotient_selected_indices": (
                quotient.selected_indices
            ),
        },
    )


def _transform_columns(transform: SparseRationalTransform):
    columns = [dict() for _ in range(transform.columns)]
    for row, column, value in transform.entries:
        columns[column][row] = value
    return tuple(columns)


def _congruence_block(
    source: SparseRationalPSDBlock,
    spatial: SpatialBlock,
) -> ReducedRealPSDBlock:
    if spatial.transform.rows != source.dimension:
        raise ValueError(
            "composed spatial transform does not match source block"
        )
    source_entries = {
        (entry.row, entry.column): entry.form
        for entry in source.upper_entries
    }
    columns = _transform_columns(spatial.transform)
    entries = []
    for row in range(spatial.dimension):
        for column in range(row, spatial.dimension):
            form = RationalLinearForm()
            for source_row, left in columns[row].items():
                for source_column, right in columns[
                    column
                ].items():
                    coordinate = tuple(
                        sorted((source_row, source_column))
                    )
                    source_form = source_entries.get(coordinate)
                    if source_form is not None:
                        form = form + source_form.scale(left * right)
            if not form.is_zero:
                entries.append(
                    SparseRationalEntry(row, column, form)
                )
    return ReducedRealPSDBlock(
        identifier=f"{source.identifier}::{spatial.identifier}",
        dimension=spatial.dimension,
        upper_entries=tuple(entries),
        source_block=source.identifier,
        spatial_block=spatial.identifier,
    )


def _substitute_form(
    form: RationalLinearForm,
    equality: EqualityReduction,
) -> RationalLinearForm:
    if equality.selected_view == "row-reduced":
        return form
    parameterization = equality.parameterization
    offset = dict(parameterization.offset)
    nullspace = tuple(
        dict(column) for column in parameterization.nullspace
    )
    coefficients = dict(form.terms)
    constant = form.constant + sum(
        coefficient * offset.get(variable, Fraction(0))
        for variable, coefficient in coefficients.items()
    )
    terms = []
    for free_position, column in enumerate(nullspace):
        value = sum(
            coefficient * column.get(variable, Fraction(0))
            for variable, coefficient in coefficients.items()
        )
        if value:
            terms.append((free_position, value))
    return RationalLinearForm(
        constant=constant,
        terms=tuple(terms),
    )


def _apply_equality_view_block(
    block: ReducedRealPSDBlock,
    equality: EqualityReduction,
) -> ReducedRealPSDBlock:
    entries = []
    for entry in block.upper_entries:
        form = _substitute_form(entry.form, equality)
        if not form.is_zero:
            entries.append(
                SparseRationalEntry(
                    entry.row,
                    entry.column,
                    form,
                )
            )
    return replace(block, upper_entries=tuple(entries))


def clarabel_hs_bytes(dimensions) -> int:
    """Return Clarabel's calibrated packed-cone Hs allocation."""
    result = 0
    for raw_dimension in dimensions:
        if (
            isinstance(raw_dimension, bool)
            or not isinstance(raw_dimension, int)
            or raw_dimension < 0
        ):
            raise ValueError(
                "PSD cone dimension must be a nonnegative integer"
            )
        triangular = raw_dimension * (raw_dimension + 1) // 2
        result += 8 * triangular**2
    return result


def estimate_reduced_resources(
    reduction: KyFanSolverReduction,
    serialized_bytes,
) -> dict:
    if not isinstance(reduction, KyFanSolverReduction):
        raise TypeError(
            "reduction must be a KyFanSolverReduction"
        )
    if (
        isinstance(serialized_bytes, bool)
        or not isinstance(serialized_bytes, int)
        or serialized_bytes < 0
    ):
        raise ValueError(
            "serialized byte count must be a nonnegative integer"
        )
    hs = clarabel_hs_bytes(
        block.dimension for block in reduction.psd_blocks
    )
    return {
        "clarabel_hs_bytes": hs,
        "estimated_rss_bytes": (
            8 * hs + 2 * serialized_bytes + (1 << 30)
        ),
        "requires_wall_benchmark": True,
    }


def _fraction_text(value) -> str:
    value = Fraction(value)
    return f"{value.numerator}/{value.denominator}"


def _encode_gaussian(value: GaussianRational) -> dict:
    return {
        "real": _fraction_text(value.real),
        "imag": _fraction_text(value.imag),
    }


def _encode_form(form: RationalLinearForm) -> dict:
    return {
        "constant": _fraction_text(form.constant),
        "terms": [
            [variable, _fraction_text(coefficient)]
            for variable, coefficient in form.terms
        ],
    }


def _json_value(value):
    if isinstance(value, Fraction):
        return _fraction_text(value)
    if isinstance(value, GaussianRational):
        return _encode_gaussian(value)
    if isinstance(value, dict):
        return {
            str(key): _json_value(item)
            for key, item in sorted(
                value.items(),
                key=lambda pair: str(pair[0]),
            )
        }
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(
        "reduction value is not canonically JSON encodable: "
        f"{type(value).__name__}"
    )


def _encode_equality(row: LinearEquality) -> dict:
    return {
        "identifier": row.identifier,
        "form": _encode_form(row.form),
        "provenance": _json_value(row.provenance),
    }


def _encode_transform(transform: SparseRationalTransform) -> dict:
    return {
        "rows": transform.rows,
        "columns": transform.columns,
        "entries": [
            [row, column, _fraction_text(value)]
            for row, column, value in transform.entries
        ],
    }


def _encode_spatial(block: SpatialBlock) -> dict:
    return {
        "identifier": block.identifier,
        "irrep_label": block.irrep_label,
        "irrep_degree": block.irrep_degree,
        "dimension": block.dimension,
        "transform": _encode_transform(block.transform),
        "internal_group": [
            {
                "shift": element.shift,
                "reflected": element.reflected,
            }
            for element in block.internal_group
        ],
        "provenance": _json_value(block.provenance),
    }


def _encode_reduced_block(block: ReducedRealPSDBlock) -> dict:
    return {
        "identifier": block.identifier,
        "dimension": block.dimension,
        "source_block": block.source_block,
        "spatial_block": block.spatial_block,
        "upper_entries": [
            {
                "row": entry.row,
                "column": entry.column,
                "form": _encode_form(entry.form),
            }
            for entry in block.upper_entries
        ],
    }


def _encode_equality_reduction(
    reduction: EqualityReduction,
    kept_rows,
) -> dict:
    parameterization = reduction.parameterization
    return {
        "kept_rows": [
            _encode_equality(row) for row in kept_rows
        ],
        "kept_identifiers": list(
            reduction.kept_identifiers
        ),
        "duplicate_map": _json_value(reduction.duplicate_map),
        "span_map": _json_value(reduction.span_map),
        "pivot_columns": list(reduction.pivot_columns),
        "row_rank": reduction.row_rank,
        "parameterization": {
            "offset": _json_value(parameterization.offset),
            "nullspace": _json_value(
                parameterization.nullspace
            ),
            "free_variables": list(
                parameterization.free_variables
            ),
            "affine_nonzeros": (
                parameterization.affine_nonzeros
            ),
        },
        "selected_view": reduction.selected_view,
        "statistics": _json_value(reduction.statistics),
    }


def solver_reduction_payload(
    reduction: KyFanSolverReduction,
) -> dict:
    """Encode one structure-only exact solver reduction."""
    if not isinstance(reduction, KyFanSolverReduction):
        raise TypeError(
            "reduction must be a KyFanSolverReduction"
        )
    return {
        "schema_version": 2,
        "purpose": "finite-N-ky-fan-solver-reduction",
        "structure_sha256": reduction.structure_sha256,
        "configuration": {
            "composition_order": [
                "logical-sparse-structure",
                "complex-conjugation-real-gauge",
                "blockade-action-quotient",
                "internal-spatial-blocks",
                "exact-equality-compression",
                "selected-equality-view",
                "sparse-reduced-affine-triplets",
            ],
            "equality_fill_cap": "2/1",
        },
        "conjugation": {
            "phases": list(reduction.conjugation.phases),
            "odd_variables": list(
                reduction.conjugation.odd_variables
            ),
            "odd_equalities": [
                _encode_equality(row)
                for row in reduction.conjugation.odd_equalities
            ],
        },
        "quotient": {
            "selected_indices": list(
                reduction.quotient.selected_indices
            ),
            "reconstruction": [
                [
                    [index, _encode_gaussian(coefficient)]
                    for index, coefficient in row
                ]
                for row in reduction.quotient.reconstruction
            ],
            "kernel": [
                [
                    [index, _encode_gaussian(coefficient)]
                    for index, coefficient in row
                ]
                for row in reduction.quotient.kernel
            ],
            "legal_inputs": list(
                reduction.quotient.legal_inputs
            ),
            "output_count": reduction.quotient.output_count,
            "action_rank": reduction.quotient.action_rank,
            "scope": reduction.quotient.scope,
            "window_sites": list(
                reduction.quotient.window_sites
            ),
        },
        "spatial": [
            _encode_spatial(block)
            for block in reduction.spatial
        ],
        "equality": _encode_equality_reduction(
            reduction.equality,
            reduction.kept_equalities,
        ),
        "selected_view": reduction.selected_view,
        "psd_blocks": [
            _encode_reduced_block(block)
            for block in reduction.psd_blocks
        ],
        "objective_components": {
            identifier: _encode_form(form)
            for identifier, form in sorted(
                reduction.objective_components.items()
            )
        },
        "statistics": _json_value(reduction.statistics),
        "resource_estimate": _json_value(
            reduction.resource_estimate
        ),
        "source_file_sha256": dict(
            sorted(reduction.source_hashes.items())
        ),
    }


def _resource_fixed_point(
    reduction: KyFanSolverReduction,
) -> KyFanSolverReduction:
    current = reduction
    for _ in range(16):
        serialized_bytes = len(
            canonical_json_bytes(
                solver_reduction_payload(current)
            )
        )
        estimate = estimate_reduced_resources(
            current,
            serialized_bytes,
        )
        if estimate == current.resource_estimate:
            return current
        current = replace(
            current,
            resource_estimate=estimate,
        )
    raise ArithmeticError(
        "reduction resource estimate did not reach a byte fixed point"
    )


def build_kyfan_solver_reduction(
    structure: KyFanStructure,
    structure_sha256: str,
) -> KyFanSolverReduction:
    """Compose all exact presolve stages in the accepted fixed order."""
    if not isinstance(structure, KyFanStructure):
        raise TypeError("structure must be a KyFanStructure")
    structure_sha256 = _sha256(
        structure_sha256,
        "structure_sha256",
    )
    if structure_sha256 != logical_structure_sha256(structure):
        raise ValueError(
            "structure SHA-256 does not match logical structure"
        )

    conjugation = build_conjugation_reduction(structure)
    window_sites = _window_sites(structure)
    quotient = build_blockade_quotient(
        structure.size,
        structure.moment_basis,
        window_sites=window_sites,
    )
    exact_ldlt_pivots(slater_gram(structure, quotient))
    if quotient.scope == "global":
        spatial_slices = build_global_d4_reduction(
            structure.size,
            structure.moment_basis,
            quotient,
            conjugation,
        )
    else:
        spatial_slices = build_local_reflection_reduction(
            structure.size,
            structure.moment_basis,
            quotient.window_sites,
            quotient,
            conjugation,
        )
    spatial = tuple(
        _compose_full_transform(
            len(structure.moment_basis),
            quotient,
            block,
        )
        for block in spatial_slices
    )
    unreduced_blocks = tuple(
        _congruence_block(source, block)
        for source in conjugation.real_blocks
        for block in spatial
    )
    all_equalities = (
        *structure.equalities,
        *conjugation.odd_equalities,
        *kernel_localizer_rows(structure, quotient),
    )
    equality = compress_equalities(
        all_equalities,
        len(structure.variables),
        (
            *unreduced_blocks,
            *structure.objective_components.values(),
        ),
        fill_cap=Fraction(2),
    )
    by_identifier = {
        row.identifier: row for row in all_equalities
    }
    kept_equalities = tuple(
        by_identifier[identifier]
        for identifier in equality.kept_identifiers
    )
    psd_blocks = tuple(
        _apply_equality_view_block(block, equality)
        for block in unreduced_blocks
    )
    objective_components = {
        identifier: _substitute_form(form, equality)
        for identifier, form in (
            structure.objective_components.items()
        )
    }
    statistics = {
        "original_test_dimension": len(structure.moment_basis),
        "quotient_action_rank": quotient.action_rank,
        "spatial_dimensions": [
            {
                "identifier": block.identifier,
                "irrep_degree": block.irrep_degree,
                "dimension": block.dimension,
            }
            for block in spatial
        ],
        "original_variable_count": len(structure.variables),
        "solver_variable_count": (
            len(equality.parameterization.free_variables)
            if equality.selected_view == "parameterized"
            else len(structure.variables)
        ),
        "equality_row_rank": equality.row_rank,
        "reduced_psd_nonzeros": sum(
            len(block.upper_entries) for block in psd_blocks
        ),
        "objective_nonzeros": sum(
            int(form.constant != 0) + len(form.terms)
            for form in objective_components.values()
        ),
    }
    initial = KyFanSolverReduction(
        structure_sha256=structure_sha256,
        conjugation=conjugation,
        quotient=quotient,
        spatial=spatial,
        equality=equality,
        kept_equalities=kept_equalities,
        selected_view=equality.selected_view,
        psd_blocks=psd_blocks,
        objective_components=objective_components,
        statistics=statistics,
        resource_estimate={},
        source_hashes=_source_hashes(),
    )
    return _resource_fixed_point(initial)
