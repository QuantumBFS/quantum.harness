"""Exact real gauge induced by complex-conjugation symmetry."""

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
from challenge233.sdp.kyfan import (
    ComplexLinearForm,
    LinearEquality,
    RationalLinearForm,
)
from challenge233.sdp.kyfan_sparse import (
    KyFanStructure,
    SparseComplexPSDBlock,
)


@dataclass(frozen=True)
class SparseRationalEntry:
    row: int
    column: int
    form: RationalLinearForm

    def __post_init__(self) -> None:
        row = int(self.row)
        column = int(self.column)
        if not 0 <= row <= column:
            raise ValueError(
                "real sparse entry must be upper triangular"
            )
        if not isinstance(self.form, RationalLinearForm):
            raise TypeError(
                "real sparse entry form must be RationalLinearForm"
            )
        if self.form.is_zero:
            raise ValueError("real sparse entries must be nonzero")
        object.__setattr__(self, "row", row)
        object.__setattr__(self, "column", column)


@dataclass(frozen=True)
class SparseRationalPSDBlock:
    identifier: str
    dimension: int
    upper_entries: tuple[SparseRationalEntry, ...]
    provenance: dict

    def __post_init__(self) -> None:
        identifier = str(self.identifier)
        dimension = int(self.dimension)
        entries = tuple(self.upper_entries)
        if not identifier:
            raise ValueError("real sparse PSD identifier is empty")
        if dimension <= 0:
            raise ValueError(
                "real sparse PSD dimension must be positive"
            )
        coordinates = tuple(
            (entry.row, entry.column) for entry in entries
        )
        if coordinates != tuple(sorted(set(coordinates))):
            raise ValueError(
                "real sparse PSD coordinates must be unique and sorted"
            )
        if any(column >= dimension for _, column in coordinates):
            raise ValueError(
                "real sparse PSD coordinate is out of range"
            )
        object.__setattr__(self, "identifier", identifier)
        object.__setattr__(self, "dimension", dimension)
        object.__setattr__(self, "upper_entries", entries)
        object.__setattr__(self, "provenance", dict(self.provenance))


@dataclass(frozen=True)
class ConjugationReduction:
    phases: tuple[int, ...]
    odd_variables: tuple[int, ...]
    odd_equalities: tuple[LinearEquality, ...]
    real_blocks: tuple[SparseRationalPSDBlock, ...]

    def __post_init__(self) -> None:
        phases = tuple(int(value) for value in self.phases)
        odd_variables = tuple(int(value) for value in self.odd_variables)
        if any(value not in {0, 1} for value in phases):
            raise ValueError(
                "conjugation phases must be binary Y parities"
            )
        if odd_variables != tuple(sorted(set(odd_variables))):
            raise ValueError(
                "odd-Y variables must be unique and sorted"
            )
        object.__setattr__(self, "phases", phases)
        object.__setattr__(self, "odd_variables", odd_variables)
        object.__setattr__(
            self,
            "odd_equalities",
            tuple(self.odd_equalities),
        )
        object.__setattr__(self, "real_blocks", tuple(self.real_blocks))


def word_y_parity(word: PauliWord) -> int:
    if not isinstance(word, PauliWord):
        raise TypeError("Y parity requires a PauliWord")
    return sum(
        label == "Y" for _, label in word.factors
    ) % 2


def _phase(exponent: int) -> GaussianRational:
    return (ONE, POS_I, NEG_ONE, NEG_I)[int(exponent) % 4]


def _zero_variables(
    form: RationalLinearForm,
    variables,
) -> RationalLinearForm:
    zero = frozenset(int(variable) for variable in variables)
    return RationalLinearForm(
        constant=form.constant,
        terms=tuple(
            (variable, coefficient)
            for variable, coefficient in form.terms
            if variable not in zero
        ),
    )


def _zero_complex_variables(
    form: ComplexLinearForm,
    variables,
) -> ComplexLinearForm:
    return ComplexLinearForm(
        real=_zero_variables(form.real, variables),
        imag=_zero_variables(form.imag, variables),
    )


def _odd_equalities(
    structure: KyFanStructure,
    odd_variables,
) -> tuple[LinearEquality, ...]:
    by_index = {
        variable.index: variable for variable in structure.variables
    }
    return tuple(
        LinearEquality(
            identifier=f"conjugation-odd-y-{index}",
            form=RationalLinearForm(
                terms=((index, Fraction(1)),)
            ),
            provenance={
                "kind": "complex-conjugation",
                "representative": by_index[index].representative.factors,
            },
        )
        for index in odd_variables
    )


def _real_block(
    block: SparseComplexPSDBlock,
    phases,
    odd_variables,
) -> SparseRationalPSDBlock:
    entries = []
    for entry in block.upper_entries:
        phase = (
            _phase(-phases[entry.row])
            * _phase(phases[entry.column])
        )
        gauged = _zero_complex_variables(
            entry.form.scale(phase),
            odd_variables,
        )
        if not gauged.imag.is_zero:
            raise ValueError(
                "conjugation gauge did not produce a real entry"
            )
        if not gauged.real.is_zero:
            entries.append(
                SparseRationalEntry(
                    row=entry.row,
                    column=entry.column,
                    form=gauged.real,
                )
            )
    return SparseRationalPSDBlock(
        identifier=block.identifier,
        dimension=block.dimension,
        upper_entries=tuple(entries),
        provenance={
            **block.provenance,
            "gauge": "D[u,u]=i^Y-parity(u); D^* M D",
            "odd_y_variables": "set to zero by explicit equalities",
        },
    )


def build_conjugation_reduction(
    structure: KyFanStructure,
) -> ConjugationReduction:
    if not isinstance(structure, KyFanStructure):
        raise TypeError("structure must be a KyFanStructure")
    phases = tuple(
        word_y_parity(word)
        for word in structure.moment_basis
    )
    odd_variables = tuple(
        variable.index
        for variable in structure.variables
        if word_y_parity(variable.representative)
    )
    return ConjugationReduction(
        phases=phases,
        odd_variables=odd_variables,
        odd_equalities=_odd_equalities(
            structure,
            odd_variables,
        ),
        real_blocks=tuple(
            _real_block(
                block,
                phases,
                odd_variables,
            )
            for block in structure.psd_blocks
        ),
    )


def verify_conjugation_reduction(
    structure: KyFanStructure,
    reduction: ConjugationReduction,
) -> dict:
    """Verify the exact phase inventory and inverse block round trip."""
    if not isinstance(structure, KyFanStructure):
        raise TypeError("structure must be a KyFanStructure")
    if not isinstance(reduction, ConjugationReduction):
        raise TypeError(
            "reduction must be a ConjugationReduction"
        )
    expected_phases = tuple(
        word_y_parity(word)
        for word in structure.moment_basis
    )
    if reduction.phases != expected_phases:
        raise ValueError("conjugation phase inventory mismatch")
    expected_odd = tuple(
        variable.index
        for variable in structure.variables
        if word_y_parity(variable.representative)
    )
    if reduction.odd_variables != expected_odd:
        raise ValueError("odd-Y variable inventory mismatch")
    expected_equalities = _odd_equalities(structure, expected_odd)
    if reduction.odd_equalities != expected_equalities:
        raise ValueError("odd-Y equality inventory mismatch")
    if len(reduction.real_blocks) != len(structure.psd_blocks):
        raise ValueError("conjugation block inventory mismatch")

    for source, gauged_block in zip(
        structure.psd_blocks,
        reduction.real_blocks,
    ):
        if (
            gauged_block.identifier != source.identifier
            or gauged_block.dimension != source.dimension
        ):
            raise ValueError(
                "conjugation block identifier or dimension mismatch"
            )
        actual = {
            (entry.row, entry.column): entry.form
            for entry in gauged_block.upper_entries
        }
        expected_coordinates = set()
        for entry in source.upper_entries:
            coordinate = (entry.row, entry.column)
            phase = (
                _phase(-expected_phases[entry.row])
                * _phase(expected_phases[entry.column])
            )
            source_modulo_odd = _zero_complex_variables(
                entry.form,
                expected_odd,
            )
            gauged = _zero_complex_variables(
                entry.form.scale(phase),
                expected_odd,
            )
            if not gauged.imag.is_zero:
                raise ValueError(
                    "conjugation gauge did not produce a real entry"
                )
            if gauged.real.is_zero:
                if coordinate in actual:
                    raise ValueError(
                        "conjugation gauge retained a zero entry"
                    )
                continue
            expected_coordinates.add(coordinate)
            if actual.get(coordinate) != gauged.real:
                raise ValueError(
                    "conjugation gauged real entry mismatch"
                )
            inverse = ComplexLinearForm(
                real=actual[coordinate]
            ).scale(phase.conjugate())
            if inverse != source_modulo_odd:
                raise ValueError(
                    "conjugation inverse phase round trip mismatch"
                )
        if set(actual) != expected_coordinates:
            raise ValueError(
                "conjugation block sparse coordinate mismatch"
            )
    return {
        "status": "verified",
        "checked_block_count": len(structure.psd_blocks),
        "odd_variable_count": len(expected_odd),
        "complex_dimension_preserved": True,
    }
