from __future__ import annotations

from typing import Any

from .orderings import OrderingError, validate_ordering


class ResultSchemaError(ValueError):
    """A result cannot support the stated variational claim."""


def _require(document: dict[str, Any], key: str, expected_type: type) -> Any:
    value = document.get(key)
    if not isinstance(value, expected_type):
        raise ResultSchemaError(f"{key} must be {expected_type.__name__}")
    return value


def validate_result_document(document: dict[str, Any]) -> dict[str, Any]:
    if document.get("schema_version") != 1:
        raise ResultSchemaError("schema_version must equal 1")
    if document.get("method") != "block2-dmrg":
        raise ResultSchemaError("method must be block2-dmrg")

    sector = _require(document, "sector", dict)
    n_orbitals = sector.get("norb")
    if not isinstance(n_orbitals, int) or n_orbitals < 1:
        raise ResultSchemaError("sector.norb must be a positive integer")

    ordering = _require(document, "ordering", dict)
    try:
        validate_ordering(ordering.get("permutation"), n_orbitals)
    except OrderingError as exc:
        raise ResultSchemaError(str(exc)) from exc

    stages = _require(document, "stages", list)
    if not stages:
        raise ResultSchemaError("stages must contain at least one finite-M result")
    previous_bond_dimension = -1
    previous_energy: float | None = None
    for stage in stages:
        if not isinstance(stage, dict):
            raise ResultSchemaError("every stage must be an object")
        bond_dimension = stage.get("bond_dimension")
        energy = stage.get("energy_hartree")
        if not isinstance(bond_dimension, int) or bond_dimension <= previous_bond_dimension:
            raise ResultSchemaError("bond dimensions must be strictly increasing")
        if not isinstance(energy, (int, float)):
            raise ResultSchemaError("every stage needs energy_hartree")
        energy = float(energy)
        if previous_energy is not None and energy > previous_energy + 1.0e-10:
            raise ResultSchemaError(
                "finite-M variational energies must be non-increasing"
            )
        previous_bond_dimension = bond_dimension
        previous_energy = energy

    headline = _require(document, "headline", dict)
    if headline.get("kind") != "finite_m_mps_expectation":
        raise ResultSchemaError("headline must be a finite-M MPS expectation value")
    last = stages[-1]
    if headline.get("bond_dimension") != last.get("bond_dimension"):
        raise ResultSchemaError("headline bond dimension must equal the final stage")
    if headline.get("energy_hartree") != last.get("energy_hartree"):
        raise ResultSchemaError("headline energy must equal the final finite-M stage")
    return document
