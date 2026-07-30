"""Sparse, detuning-independent logical Ky Fan structures."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
import hashlib
import json

from challenge233.sdp.algebra import (
    GaussianRational,
    NEG_ONE,
    PauliPolynomial,
    PauliWord,
    add_polynomials,
    scale_polynomial,
)
from challenge233.sdp.constrained_trace import (
    constrained_polynomial_trace,
    periodic_blockade_dimension,
)
from challenge233.sdp.constraints import pxp_hamiltonian_polynomial
from challenge233.sdp.hierarchy import (
    HierarchyLevel,
    clique_orbit,
    global_pauli_basis,
    local_pauli_basis,
    safe_localizer_basis,
)
from challenge233.sdp.kyfan import (
    CliqueImage,
    ComplexLinearForm,
    ComplexPSDBlock,
    LinearEquality,
    MagnitudeWitness,
    MomentVariable,
    RationalLinearForm,
    _InvariantMomentFunctional,
    _build_variable_registry,
    _fraction_coefficient,
    _localizer_equalities,
    _moment_product,
    _representative_localizer_sites,
    build_clique_images,
)
from challenge233.sdp.localizers import (
    SafeWord,
    build_safe_sandwich_localizers,
    build_support_localizers,
)


@dataclass(frozen=True)
class SparseComplexEntry:
    row: int
    column: int
    form: ComplexLinearForm

    def __post_init__(self) -> None:
        object.__setattr__(self, "row", int(self.row))
        object.__setattr__(self, "column", int(self.column))
        if not 0 <= self.row <= self.column:
            raise ValueError(
                "complex sparse entry must be upper triangular"
            )
        if not isinstance(self.form, ComplexLinearForm):
            raise TypeError("sparse entry form must be ComplexLinearForm")
        if self.form.is_zero:
            raise ValueError("sparse complex entries must be nonzero")


@dataclass(frozen=True)
class SparseComplexPSDBlock:
    identifier: str
    dimension: int
    upper_entries: tuple[SparseComplexEntry, ...]
    provenance: dict

    def __post_init__(self) -> None:
        identifier = str(self.identifier)
        dimension = int(self.dimension)
        entries = tuple(self.upper_entries)
        if not identifier:
            raise ValueError("sparse PSD identifier must be non-empty")
        if dimension <= 0:
            raise ValueError("sparse PSD dimension must be positive")
        coordinates = tuple(
            (entry.row, entry.column)
            for entry in entries
        )
        if coordinates != tuple(sorted(set(coordinates))):
            raise ValueError(
                "sparse PSD coordinates must be unique and sorted"
            )
        if any(
            entry.column >= dimension
            for entry in entries
        ):
            raise ValueError("sparse PSD coordinate is out of range")
        object.__setattr__(self, "identifier", identifier)
        object.__setattr__(self, "dimension", dimension)
        object.__setattr__(self, "upper_entries", entries)
        object.__setattr__(self, "provenance", dict(self.provenance))


@dataclass(frozen=True)
class KyFanStructure:
    size: int
    hierarchy: str
    localizer_mode: str
    moment_basis: tuple[PauliWord, ...]
    safe_basis: tuple[SafeWord, ...]
    variables: tuple[MomentVariable, ...]
    objective_components: dict
    equalities: tuple[LinearEquality, ...]
    psd_blocks: tuple[SparseComplexPSDBlock, ...]
    magnitude_witnesses: tuple[MagnitudeWitness, ...]
    clique_orbits: tuple
    clique_images: tuple[CliqueImage, ...]
    localizer_sites: tuple[int, ...]
    constrained_trace_table: tuple[
        tuple[PauliPolynomial, GaussianRational],
        ...,
    ]
    provenance: dict
    statistics: dict

    def __post_init__(self) -> None:
        size = int(self.size)
        if size < 4:
            raise ValueError("Ky Fan structure size must be at least 4")
        if self.localizer_mode not in {"sound", "none"}:
            raise ValueError(
                "localizer_mode must be 'sound' or 'none'"
            )
        if set(self.objective_components) != {
            "rabi",
            "minus-number",
        }:
            raise ValueError(
                "objective components must be rabi and minus-number"
            )
        if any(
            not isinstance(value, RationalLinearForm)
            for value in self.objective_components.values()
        ):
            raise TypeError(
                "objective components must be RationalLinearForm values"
            )
        identifiers = tuple(block.identifier for block in self.psd_blocks)
        if identifiers != ("gamma", "blockade-complement"):
            raise ValueError("logical structure must contain both effects")
        object.__setattr__(self, "size", size)
        object.__setattr__(self, "hierarchy", str(self.hierarchy))
        object.__setattr__(
            self,
            "objective_components",
            dict(self.objective_components),
        )
        object.__setattr__(self, "provenance", dict(self.provenance))
        object.__setattr__(self, "statistics", dict(self.statistics))

    def logical_fingerprint(self) -> str:
        payload = _signature_value(self)
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class KyFanInstance:
    detuning: Fraction
    objective: RationalLinearForm
    physical_contract: dict
    trial_manifest: object
    structure_fingerprint: str


def _fraction_text(value: Fraction) -> str:
    value = Fraction(value)
    return f"{value.numerator}/{value.denominator}"


def _signature_value(value):
    if isinstance(value, Fraction):
        return {"fraction": _fraction_text(value)}
    if isinstance(value, GaussianRational):
        return {
            "gaussian": {
                "real": _fraction_text(value.real),
                "imag": _fraction_text(value.imag),
            }
        }
    if isinstance(value, PauliWord):
        return {"pauli_word": [list(factor) for factor in value.factors]}
    if isinstance(value, PauliPolynomial):
        return {
            "pauli_polynomial": [
                {
                    "word": _signature_value(word),
                    "coefficient": _signature_value(coefficient),
                }
                for word, coefficient in value.terms
            ]
        }
    if isinstance(value, SafeWord):
        return {"safe_word": [list(factor) for factor in value.factors]}
    if isinstance(value, RationalLinearForm):
        return {
            "constant": _fraction_text(value.constant),
            "terms": [
                [variable, _fraction_text(coefficient)]
                for variable, coefficient in value.terms
            ],
        }
    if isinstance(value, ComplexLinearForm):
        return {
            "real": _signature_value(value.real),
            "imag": _signature_value(value.imag),
        }
    if isinstance(value, MomentVariable):
        return {
            "index": value.index,
            "representative": _signature_value(value.representative),
            "orbit": _signature_value(value.orbit),
        }
    if isinstance(value, LinearEquality):
        return {
            "identifier": value.identifier,
            "form": _signature_value(value.form),
            "provenance": _signature_value(value.provenance),
        }
    if isinstance(value, SparseComplexEntry):
        return {
            "row": value.row,
            "column": value.column,
            "form": _signature_value(value.form),
        }
    if isinstance(value, SparseComplexPSDBlock):
        return {
            "identifier": value.identifier,
            "dimension": value.dimension,
            "upper_entries": _signature_value(value.upper_entries),
            "provenance": _signature_value(value.provenance),
        }
    if isinstance(value, MagnitudeWitness):
        return {
            "variable": value.variable,
            "block": value.block,
            "row": value.row,
            "column": value.column,
            "phase": _signature_value(value.phase),
            "bound": _fraction_text(value.bound),
        }
    if isinstance(value, CliqueImage):
        return {
            "shift": value.shift,
            "reflected": value.reflected,
            "sites": list(value.sites),
            "representative_blocks": list(value.representative_blocks),
            "row_permutation": list(value.row_permutation),
            "localizer_sites": list(value.localizer_sites),
        }
    if isinstance(value, KyFanStructure):
        return {
            "size": value.size,
            "hierarchy": value.hierarchy,
            "localizer_mode": value.localizer_mode,
            "moment_basis": _signature_value(value.moment_basis),
            "safe_basis": _signature_value(value.safe_basis),
            "variables": _signature_value(value.variables),
            "objective_components": _signature_value(
                value.objective_components
            ),
            "equalities": _signature_value(value.equalities),
            "psd_blocks": _signature_value(value.psd_blocks),
            "magnitude_witnesses": _signature_value(
                value.magnitude_witnesses
            ),
            "clique_orbits": _signature_value(value.clique_orbits),
            "clique_images": _signature_value(value.clique_images),
            "localizer_sites": list(value.localizer_sites),
            "constrained_trace_table": _signature_value(
                value.constrained_trace_table
            ),
            "provenance": _signature_value(value.provenance),
            "statistics": _signature_value(value.statistics),
        }
    if isinstance(value, dict):
        return {
            str(key): _signature_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_signature_value(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(
        f"unsupported logical fingerprint value: {type(value).__name__}"
    )


def _affine_nonzeros(form: RationalLinearForm) -> int:
    return int(form.constant != 0) + len(form.terms)


def _complex_affine_nonzeros(form: ComplexLinearForm) -> int:
    return _affine_nonzeros(form.real) + _affine_nonzeros(form.imag)


def _normalized_forms(
    size: int,
    polynomial: PauliPolynomial,
    functional: _InvariantMomentFunctional,
    trace_cache,
) -> tuple[ComplexLinearForm, ComplexLinearForm]:
    ell = functional.polynomial(polynomial)
    trace = trace_cache.setdefault(
        polynomial,
        constrained_polynomial_trace(size, polynomial),
    )
    tau = ComplexLinearForm.constant(trace)
    complement_scale = Fraction(
        1,
        periodic_blockade_dimension(size) - 2,
    )
    gamma = ell.scale(_fraction_coefficient(Fraction(1, 2)))
    complement = (
        tau.scale(_fraction_coefficient(complement_scale))
        + ell.scale(_fraction_coefficient(-complement_scale))
    )
    return gamma, complement


def _build_sparse_effect_blocks(
    size,
    moment_basis,
    products,
    functional,
):
    gamma_entries = []
    complement_entries = []
    trace_cache = {}
    for row, column, polynomial in products:
        gamma, complement = _normalized_forms(
            size,
            polynomial,
            functional,
            trace_cache,
        )
        if row == column and (
            not gamma.imag.is_zero
            or not complement.imag.is_zero
        ):
            raise ValueError("Hermitian diagonal must be real")
        if not gamma.is_zero:
            gamma_entries.append(
                SparseComplexEntry(row, column, gamma)
            )
        if not complement.is_zero:
            complement_entries.append(
                SparseComplexEntry(row, column, complement)
            )
    gamma_block = SparseComplexPSDBlock(
        identifier="gamma",
        dimension=len(moment_basis),
        upper_entries=tuple(gamma_entries),
        provenance={
            "normalization": "Tr(Gamma)=2",
            "scale": "1/2",
        },
    )
    complement_block = SparseComplexPSDBlock(
        identifier="blockade-complement",
        dimension=len(moment_basis),
        upper_entries=tuple(complement_entries),
        provenance={
            "normalization": "Tr(Pi_K-Gamma)=kappa_N-2",
            "scale": (
                f"1/{periodic_blockade_dimension(size) - 2}"
            ),
        },
    )
    trace_table = tuple(
        sorted(
            trace_cache.items(),
            key=lambda item: repr(item[0]),
        )
    )
    return gamma_block, complement_block, trace_table


def _sparse_magnitude_witnesses(
    variables,
    gamma_block: SparseComplexPSDBlock,
) -> tuple[MagnitudeWitness, ...]:
    unit = RationalLinearForm(Fraction(1))
    entries = {
        (entry.row, entry.column): entry.form
        for entry in gamma_block.upper_entries
    }
    unit_diagonal = {
        row
        for row in range(gamma_block.dimension)
        if entries.get((row, row)) == ComplexLinearForm(unit)
    }
    coordinates = {}
    for entry in gamma_block.upper_entries:
        if entry.row == entry.column:
            continue
        if (
            entry.row not in unit_diagonal
            or entry.column not in unit_diagonal
            or entry.form.real.constant
            or entry.form.imag.constant
        ):
            continue
        variable_indices = {
            variable
            for variable, _ in (
                entry.form.real.terms + entry.form.imag.terms
            )
        }
        if len(variable_indices) != 1:
            continue
        variable = next(iter(variable_indices))
        real = dict(entry.form.real.terms).get(variable, Fraction(0))
        imag = dict(entry.form.imag.terms).get(variable, Fraction(0))
        if real**2 + imag**2 != Fraction(1, 4):
            continue
        coordinates.setdefault(
            variable,
            (
                entry.row,
                entry.column,
                GaussianRational(2 * real, 2 * imag),
            ),
        )
    witnesses = []
    for variable in variables:
        try:
            row, column, phase = coordinates[variable.index]
        except KeyError as error:
            raise ValueError(
                "moment variable has no sparse PSD magnitude witness"
            ) from error
        witnesses.append(
            MagnitudeWitness(
                variable=variable.index,
                block=gamma_block.identifier,
                row=row,
                column=column,
                phase=phase,
                bound=Fraction(2),
            )
        )
    return tuple(witnesses)


def _assemble_structure(
    *,
    size,
    hierarchy,
    moment_basis,
    safe_basis,
    localizer_sites,
    clique_orbits,
    clique_images,
    localizer_mode,
) -> KyFanStructure:
    if localizer_mode not in {"sound", "none"}:
        raise ValueError("localizer_mode must be 'sound' or 'none'")
    products = tuple(
        (
            row,
            column,
            _moment_product(moment_basis[row], moment_basis[column]),
        )
        for row in range(len(moment_basis))
        for column in range(row, len(moment_basis))
    )
    h_rabi = pxp_hamiltonian_polynomial(size, Fraction(0))
    h_at_one = pxp_hamiltonian_polynomial(size, Fraction(1))
    minus_number = add_polynomials(
        h_at_one,
        scale_polynomial(NEG_ONE, h_rabi),
    )
    support_rows = build_support_localizers(
        size,
        moment_basis,
        localizer_sites,
    )
    sandwich_rows = build_safe_sandwich_localizers(
        size,
        safe_basis,
        localizer_sites,
    )
    registry_polynomials = [
        polynomial
        for _, _, polynomial in products
    ]
    registry_polynomials.extend((h_rabi, minus_number))
    registry_polynomials.extend(
        row.polynomial for row in support_rows
    )
    registry_polynomials.extend(
        row.polynomial for row in sandwich_rows
    )
    variables = _build_variable_registry(size, registry_polynomials)
    functional = _InvariantMomentFunctional(size, variables)
    gamma_block, complement_block, trace_table = (
        _build_sparse_effect_blocks(
            size,
            moment_basis,
            products,
            functional,
        )
    )
    witnesses = _sparse_magnitude_witnesses(
        variables,
        gamma_block,
    )
    objective_components = {}
    for identifier, polynomial in (
        ("rabi", h_rabi),
        ("minus-number", minus_number),
    ):
        value = functional.polynomial(polynomial)
        if not value.imag.is_zero:
            raise ValueError(
                f"{identifier} objective component is not real"
            )
        objective_components[identifier] = value.real
    normalization = LinearEquality(
        identifier="trace-gamma-equals-2",
        form=RationalLinearForm(),
        provenance={
            "normalization": "ell(I)=2",
            "implementation": "identity moment eliminated exactly",
        },
    )
    sound_equalities = _localizer_equalities(
        functional,
        support_rows,
        sandwich_rows,
    )
    equalities = (
        (normalization, *sound_equalities)
        if localizer_mode == "sound"
        else (normalization,)
    )
    psd_blocks = (gamma_block, complement_block)
    statistics = {
        "moment_word_count": len(moment_basis),
        "moment_variable_count": len(variables),
        "equality_count": len(equalities),
        "support_localizer_count": (
            len(support_rows) if localizer_mode == "sound" else 0
        ),
        "safe_sandwich_count": (
            len(sandwich_rows) if localizer_mode == "sound" else 0
        ),
        "complex_psd_block_dimensions": [
            block.dimension for block in psd_blocks
        ],
        "stored_complex_upper_entry_count": sum(
            len(block.upper_entries) for block in psd_blocks
        ),
        "affine_nonzero_count": (
            sum(
                _affine_nonzeros(form)
                for form in objective_components.values()
            )
            + sum(_affine_nonzeros(row.form) for row in equalities)
            + sum(
                _complex_affine_nonzeros(entry.form)
                for block in psd_blocks
                for entry in block.upper_entries
            )
        ),
        "bounded_variable_count": len(witnesses),
        "sparse_payload_coordinate_bytes": sum(
            24 * len(block.upper_entries)
            for block in psd_blocks
        ),
    }
    if len(witnesses) != len(variables):
        raise ValueError("not every sparse moment variable is bounded")
    return KyFanStructure(
        size=size,
        hierarchy=hierarchy,
        localizer_mode=localizer_mode,
        moment_basis=tuple(moment_basis),
        safe_basis=tuple(safe_basis),
        variables=variables,
        objective_components=objective_components,
        equalities=tuple(equalities),
        psd_blocks=psd_blocks,
        magnitude_witnesses=witnesses,
        clique_orbits=tuple(clique_orbits),
        clique_images=tuple(clique_images),
        localizer_sites=tuple(localizer_sites),
        constrained_trace_table=trace_table,
        provenance={
            "boundary": "periodic",
            "local_state_convention": "0=down, 1=up",
            "symmetry": "D_N group-averaged effect, all physical sectors",
            "localizer_mode": localizer_mode,
            "identity_moment": "ell(I)=2 eliminated exactly",
            "storage": "complex sparse upper triangle",
        },
        statistics=statistics,
    )


def _validate_size(size) -> int:
    size = int(size)
    if size < 4:
        raise ValueError("Ky Fan structure size must be at least 4")
    return size


@lru_cache(maxsize=None)
def build_global_kyfan_structure(
    size: int,
    max_weight: int,
    localizer_mode: str = "sound",
) -> KyFanStructure:
    size = _validate_size(size)
    max_weight = int(max_weight)
    if max_weight < 0:
        raise ValueError("global Pauli weight must be nonnegative")
    moment_basis = global_pauli_basis(size, max_weight)
    safe_level = HierarchyLevel(
        name=f"global-d{max_weight}-safe",
        range_sites=size,
        moment_weight=max_weight,
        safe_depth=1,
    )
    safe_basis = safe_localizer_basis(size, 0, safe_level)
    return _assemble_structure(
        size=size,
        hierarchy=f"global-d{max_weight}",
        moment_basis=moment_basis,
        safe_basis=safe_basis,
        localizer_sites=tuple(range(size)),
        clique_orbits=(clique_orbit(size, 0, size),),
        clique_images=build_clique_images(size, 0, safe_level),
        localizer_mode=localizer_mode,
    )


@lru_cache(maxsize=None)
def build_local_kyfan_structure(
    size: int,
    level: HierarchyLevel,
    localizer_mode: str = "sound",
) -> KyFanStructure:
    size = _validate_size(size)
    if not isinstance(level, HierarchyLevel):
        raise TypeError("level must be a HierarchyLevel")
    moment_basis = local_pauli_basis(size, 0, level)
    safe_basis = safe_localizer_basis(size, 0, level)
    localizer_sites = _representative_localizer_sites(
        size,
        0,
        level.range_sites,
    )
    return _assemble_structure(
        size=size,
        hierarchy=level.name,
        moment_basis=moment_basis,
        safe_basis=safe_basis,
        localizer_sites=localizer_sites,
        clique_orbits=(clique_orbit(size, 0, level.range_sites),),
        clique_images=build_clique_images(size, 0, level),
        localizer_mode=localizer_mode,
    )


def _exact_detuning(value) -> Fraction:
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError("detuning must be an exact rational")
    try:
        value = Fraction(value)
    except (TypeError, ValueError, ZeroDivisionError) as error:
        raise TypeError("detuning must be an exact rational") from error
    if not Fraction(0) <= value <= Fraction(3):
        raise ValueError("detuning must lie in [0,3]")
    return value


def _physical_contract(
    structure: KyFanStructure,
    detuning: Fraction,
) -> dict:
    return {
        "hamiltonian": (
            "H_N(delta)=sum_i P_{i-1} X_i P_{i+1}"
            "-delta sum_i n_i"
        ),
        "rabi_coefficient": "1/1",
        "detuning": _fraction_text(detuning),
        "detuning_sign": "-delta",
        "projectors": {
            "P": "|0><0|=(I-Z)/2",
            "n": "|1><1|=(I+Z)/2",
        },
        "boundary": "periodic",
        "local_state_convention": "0=down, 1=up",
        "blockade_constraint": "n_i n_{i+1}=0 including wrap bond",
        "symmetry_sector": "full constrained Hilbert space",
        "target_gap": "E_1-E_0 with multiplicity, all momenta",
        "size": structure.size,
        "hierarchy": structure.hierarchy,
        "localizer_mode": structure.localizer_mode,
    }


def build_kyfan_instance(
    structure: KyFanStructure,
    detuning,
    trial_manifest=None,
) -> KyFanInstance:
    if not isinstance(structure, KyFanStructure):
        raise TypeError("structure must be a KyFanStructure")
    detuning = _exact_detuning(detuning)
    objective = (
        structure.objective_components["rabi"]
        + structure.objective_components["minus-number"].scale(detuning)
    )
    return KyFanInstance(
        detuning=detuning,
        objective=objective,
        physical_contract=_physical_contract(structure, detuning),
        trial_manifest=trial_manifest,
        structure_fingerprint=structure.logical_fingerprint(),
    )


def materialize_complex_blocks(
    blocks,
) -> tuple[ComplexPSDBlock, ...]:
    """Materialize sparse blocks for small exact compatibility tests."""
    materialized = []
    for block in blocks:
        if not isinstance(block, SparseComplexPSDBlock):
            raise TypeError(
                "materialization requires SparseComplexPSDBlock values"
            )
        matrix = [
            [ComplexLinearForm() for _ in range(block.dimension)]
            for _ in range(block.dimension)
        ]
        for entry in block.upper_entries:
            matrix[entry.row][entry.column] = entry.form
            matrix[entry.column][entry.row] = entry.form.conjugate()
        materialized.append(
            ComplexPSDBlock(
                identifier=block.identifier,
                dimension=block.dimension,
                entries=tuple(tuple(row) for row in matrix),
                provenance=dict(block.provenance),
            )
        )
    return tuple(materialized)
