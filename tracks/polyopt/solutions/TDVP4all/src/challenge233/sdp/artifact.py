from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from pathlib import Path

from challenge233.sdp.algebra import (
    GaussianRational,
    PauliPolynomial,
    PauliWord,
    canonical_relation_table_json,
)
from challenge233.sdp.constraints import (
    ConstraintMap,
    IndexOrbit,
    MomentEntry,
    ZeroLocalizerRow,
)
from challenge233.sdp.symmetry import (
    DihedralElement,
    DihedralIrrep,
    SectorMultiplicity,
)


def _encode_fraction(value: Fraction) -> str:
    value = Fraction(value)
    return f"{value.numerator}/{value.denominator}"


def _encode_coefficient(
    value: GaussianRational,
) -> dict:
    return {
        "real": _encode_fraction(value.real),
        "imag": _encode_fraction(value.imag),
    }


def _encode_word(word: PauliWord) -> list:
    return [
        [site, label]
        for site, label in word.factors
    ]


def _encode_polynomial(
    polynomial: PauliPolynomial,
) -> list:
    return [
        {
            "word": _encode_word(word),
            "coefficient": _encode_coefficient(coefficient),
        }
        for word, coefficient in polynomial.terms
    ]


def _encode_moment_entry(entry: MomentEntry) -> dict:
    return {
        "row": entry.row,
        "column": entry.column,
        "polynomial": _encode_polynomial(entry.polynomial),
    }


def _encode_zero_localizer(
    entry: ZeroLocalizerRow,
) -> dict:
    return {
        "site": entry.site,
        "row": entry.row,
        "column": entry.column,
        "polynomial": _encode_polynomial(entry.polynomial),
    }


def _encode_group_element(element: DihedralElement) -> dict:
    return {
        "shift": element.shift,
        "reflected": element.reflected,
    }


def _encode_irrep(irrep: DihedralIrrep) -> dict:
    return {
        "label": irrep.label,
        "dimension": irrep.dimension,
        "momenta": list(irrep.momenta),
        "reflection_parity": irrep.reflection_parity,
    }


def _encode_sector(item: SectorMultiplicity) -> dict:
    return {
        "label": item.irrep.label,
        "multiplicity": item.multiplicity,
    }


def _encode_orbit(orbit: IndexOrbit) -> dict:
    return {
        "representative": orbit.representative,
        "members": list(orbit.members),
    }


def _json_bytes(value) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def export_constraint_map(
    constraint_map: ConstraintMap,
    output_directory,
) -> Path:
    """Export a deterministic structural map and provenance manifest."""
    if not isinstance(constraint_map, ConstraintMap):
        raise TypeError("constraint_map must be a ConstraintMap")
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)

    payload = {
        "size": constraint_map.size,
        "moment_basis": [
            _encode_word(word)
            for word in constraint_map.moment_basis
        ],
        "localizer_basis": [
            _encode_word(word)
            for word in constraint_map.localizer_basis
        ],
        "moment_entries": [
            _encode_moment_entry(entry)
            for entry in constraint_map.moment_entries
        ],
        "zero_localizers": [
            _encode_zero_localizer(entry)
            for entry in constraint_map.zero_localizers
        ],
        "group_elements": [
            _encode_group_element(element)
            for element in constraint_map.group_elements
        ],
        "moment_basis_permutations": [
            list(permutation)
            for permutation in (
                constraint_map.moment_basis_permutations
            )
        ],
        "localizer_basis_permutations": [
            list(permutation)
            for permutation in (
                constraint_map.localizer_basis_permutations
            )
        ],
        "moment_entry_permutations": [
            list(permutation)
            for permutation in (
                constraint_map.moment_entry_permutations
            )
        ],
        "zero_localizer_permutations": [
            list(permutation)
            for permutation in (
                constraint_map.zero_localizer_permutations
            )
        ],
        "irrep_catalog": [
            _encode_irrep(irrep)
            for irrep in constraint_map.irrep_catalog
        ],
        "moment_sector_multiplicities": [
            _encode_sector(item)
            for item in (
                constraint_map.moment_sector_multiplicities
            )
        ],
        "localizer_sector_multiplicities": [
            _encode_sector(item)
            for item in (
                constraint_map.localizer_sector_multiplicities
            )
        ],
        "moment_entry_orbits": [
            _encode_orbit(orbit)
            for orbit in constraint_map.moment_entry_orbits
        ],
        "zero_localizer_orbits": [
            _encode_orbit(orbit)
            for orbit in constraint_map.zero_localizer_orbits
        ],
        "assembly_statistics": dict(
            constraint_map.assembly_statistics
        ),
    }
    data_path = output_directory / "constraint-map.json"
    data_bytes = _json_bytes(payload)
    data_path.write_bytes(data_bytes)

    project_root = Path(__file__).resolve().parents[3]
    design_path = (
        project_root
        / "docs/superpowers/specs/"
        / "2026-07-29-pxp-sdp-algebra-symmetry-design.md"
    )
    source_paths = (
        "src/challenge233/sdp/algebra.py",
        "src/challenge233/sdp/symmetry.py",
        "src/challenge233/sdp/basis.py",
        "src/challenge233/sdp/constraints.py",
        "src/challenge233/sdp/artifact.py",
    )
    manifest = {
        "schema_version": 1,
        "canonicalizer_schema_version": 1,
        "purpose": (
            "legacy-structural-arbitrary-sandwich-not-solver-input"
        ),
        "localizer_semantics": "unsound-for-state-support",
        "boundary": "periodic",
        "state_convention": "0=down, 1=up",
        "rabi_coefficient": "1",
        "detuning_uniform": True,
        "algebra": "pauli-xz-derived-y-p-n",
        "spatial_group": "D_N",
        "data_file": data_path.name,
        "data_sha256": hashlib.sha256(data_bytes).hexdigest(),
        "relation_table_sha256": hashlib.sha256(
            canonical_relation_table_json().encode("utf-8")
        ).hexdigest(),
        "design_sha256": hashlib.sha256(
            design_path.read_bytes()
        ).hexdigest(),
        "source_file_sha256": {
            relative_path: hashlib.sha256(
                (project_root / relative_path).read_bytes()
            ).hexdigest()
            for relative_path in source_paths
        },
    }
    (output_directory / "manifest.json").write_bytes(
        _json_bytes(manifest)
    )
    return output_directory
