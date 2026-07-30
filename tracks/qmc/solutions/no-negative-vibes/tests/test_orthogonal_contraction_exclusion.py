from __future__ import annotations

from oracle.orthogonal_contraction_candidate import (
    build_orthogonal_plaquette_model,
    orthogonal_plaquette_atoms,
)
from oracle.orthogonal_contraction_exclusion import (
    common_commutant_audit,
    pauli_frustration_audit,
)


def test_atoms_have_only_scalar_common_commutant_and_generate_so4() -> None:
    audit = common_commutant_audit(orthogonal_plaquette_atoms())

    assert audit.rank == 15
    assert audit.nullity == 1
    assert audit.smallest_nonzero_singular_value > 0.59
    assert audit.lie_closure_dimension == 6


def test_jw_frustration_graph_contains_an_induced_claw() -> None:
    model = build_orthogonal_plaquette_model()
    audit = pauli_frustration_audit(model.hamiltonian)

    assert len(audit.terms) == 39
    assert audit.edge_count == 288
    assert audit.minimum_degree == 0
    assert audit.maximum_degree == 16
    assert audit.claw_center is not None
    assert audit.claw_center[0] == "IIZZ"
    assert tuple(term[0] for term in audit.claw_leaves) == (
        "IXIX",
        "IYIY",
        "XIXI",
    )
