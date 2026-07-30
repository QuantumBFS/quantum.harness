"""Theorem-independent PXP SDP constraint foundations."""

from importlib import import_module

from challenge233.sdp.algebra import (
    GaussianRational,
    PauliPolynomial,
    PauliTerm,
    PauliWord,
    add_polynomials,
    adjoint_polynomial,
    canonical_relation_table_json,
    canonicalize_word,
    expand_word,
    multiply_polynomials,
    polynomial_from_word,
    scale_polynomial,
)
from challenge233.sdp.artifact import export_constraint_map
from challenge233.sdp.basis import close_word_basis
from challenge233.sdp.blockade_quotient import (
    BlockadeQuotient,
    build_blockade_quotient,
    exact_ldlt_pivots,
    kernel_localizer_rows,
    literal_pauli_action,
    slater_gram,
    verify_blockade_quotient,
)
from challenge233.sdp.constraints import (
    ConstraintMap,
    IndexOrbit,
    MomentEntry,
    ZeroLocalizerRow,
    blockade_polynomial,
    build_constraint_map,
    expand_moment_entry_orbits,
    expand_zero_localizer_orbits,
    pxp_hamiltonian_polynomial,
)
from challenge233.sdp.constrained_trace import (
    constrained_pauli_trace,
    constrained_polynomial_trace,
    periodic_blockade_dimension,
)
from challenge233.sdp.conjugation_reduction import (
    ConjugationReduction,
    SparseRationalEntry,
    SparseRationalPSDBlock,
    build_conjugation_reduction,
    verify_conjugation_reduction,
    word_y_parity,
)
from challenge233.sdp.localizers import (
    SAFE_LABELS,
    SafeWord,
    SandwichLocalizer,
    SupportLocalizer,
    build_safe_sandwich_localizers,
    build_support_localizers,
    expand_safe_word,
)
from challenge233.sdp.hierarchy import (
    LOCAL_LEVELS,
    HierarchyLevel,
    clique_orbit,
    global_pauli_basis,
    local_pauli_basis,
    safe_localizer_basis,
    validate_nested_levels,
)
from challenge233.sdp.exact_linalg import (
    ExactColumnBasis,
    ExactRowBasis,
    gaussian_column_basis,
    primitive_integer_row,
    rational_row_basis,
    verify_column_reconstruction,
    verify_row_reconstruction,
)
from challenge233.sdp.equality_reduction import (
    AffineParameterization,
    EqualityReduction,
    compress_equalities,
    verify_equality_reduction,
)
from challenge233.sdp.kyfan import (
    CliqueImage,
    ComplexLinearForm,
    ComplexPSDBlock,
    KyFanProblem,
    LinearEquality,
    MagnitudeWitness,
    MomentVariable,
    RationalLinearForm,
    RealPSDBlock,
    build_global_kyfan_problem,
    build_clique_images,
    build_local_kyfan_problem,
    build_magnitude_witnesses,
    realify_hermitian_matrix,
)
from challenge233.sdp.kyfan_artifact import export_kyfan_problem
from challenge233.sdp.kyfan_sparse import (
    KyFanInstance,
    KyFanStructure,
    SparseComplexEntry,
    SparseComplexPSDBlock,
    build_global_kyfan_structure,
    build_kyfan_instance,
    build_local_kyfan_structure,
    materialize_complex_blocks,
)
from challenge233.sdp.kyfan_v2_artifact import (
    ReductionBinding,
    StructureBinding,
    canonical_json_bytes,
    export_kyfan_instance,
    export_solver_reduction,
    export_shared_structure,
    instance_payload,
    logical_structure_sha256,
    structure_payload,
)
from challenge233.sdp.kyfan_presolve import (
    KyFanSolverReduction,
    ReducedRealPSDBlock,
    build_kyfan_solver_reduction,
    clarabel_hs_bytes,
    estimate_reduced_resources,
    solver_reduction_payload,
)
from challenge233.sdp.spatial_reduction import (
    SparseRationalTransform,
    SpatialBlock,
    build_global_d4_reduction,
    build_local_reflection_reduction,
    induced_quotient_action,
    verify_global_d4_reduction,
    verify_induced_quotient_action,
    verify_local_reflection_reduction,
    verify_quotient_group_action,
)
from challenge233.sdp.verify_kyfan_reduction import (
    verify_kyfan_reduction,
)
from challenge233.sdp.symmetry import (
    DihedralIrrep,
    DihedralElement,
    SectorMultiplicity,
    TranslationOrbit,
    act_on_polynomial,
    act_on_site,
    act_on_word,
    compose,
    dihedral_irrep_catalog,
    dihedral_elements,
    normalize,
    representation_permutation,
    sector_multiplicities,
    translation_orbits,
    word_orbit,
)


def verify_kyfan_problem(output_directory):
    """Lazily invoke the independent checker without preloading its CLI."""
    from challenge233.sdp.verify_kyfan_problem import (
        verify_kyfan_problem as checker,
    )

    return checker(output_directory)


def validate_structure_payload(payload):
    """Lazily invoke the independent schema-v2 logical validator."""
    from challenge233.sdp.verify_kyfan_structure import (
        validate_structure_payload as checker,
    )

    return checker(payload)


def verify_kyfan_structure(path):
    """Lazily verify one shared schema-v2 logical structure."""
    from challenge233.sdp.verify_kyfan_structure import (
        verify_kyfan_structure as checker,
    )

    return checker(path)


def verify_bound_kyfan_structure(problem_directory, run_root):
    """Lazily verify a cell binding to shared schema-v2 structure."""
    from challenge233.sdp.verify_kyfan_structure import (
        verify_bound_kyfan_structure as checker,
    )

    return checker(problem_directory, run_root)


def verify_kyfan_certificate(cell_directory):
    """Lazily invoke the independent exact certificate checker."""
    from challenge233.sdp.verify_kyfan_certificate import (
        verify_kyfan_certificate as checker,
    )

    return checker(cell_directory)


def __getattr__(name):
    if name in {
        "TrialVector",
        "exact_rayleigh_quotient",
        "generate_quspin_trial",
        "round_trial_vector",
        "write_trial_vector",
    }:
        module = import_module(
            "challenge233.sdp.variational_upper"
        )
        return getattr(module, name)
    if name in {
        "DyadicFactor",
        "ExactDualIdentity",
        "build_dual_certificate",
        "exact_dual_identity",
        "positive_dyadic_factor",
    }:
        module = import_module(
            "challenge233.sdp.dual_certificate"
        )
        return getattr(module, name)
    if name in {
        "ExactLiftedIdentity",
        "WeightedFactorOrbit",
        "build_weighted_factor_orbit",
        "exact_lifted_psd_contribution",
        "lift_reduced_duals",
        "literal_dense_residual_norm_bound",
        "moment_residual_correction",
        "physical_residual_correction",
        "reconstruct_equality_multipliers",
    }:
        module = import_module("challenge233.sdp.dual_lift")
        return getattr(module, name)
    if name in {
        "CellSelection",
        "assembly_probe",
        "build_problem_for_cell",
        "build_structure_for_cell",
        "certify_cell",
        "certify_run",
        "estimate_solve_resources",
        "estimate_v2_solve_resources",
        "plan_escalation",
        "plan_v2_run",
        "prepare_cell",
        "prepare_run",
        "prepare_v2_cell",
        "prepare_v2_run",
        "remote_solve_command",
        "select_cell",
        "solve_local_cell",
    }:
        module = import_module("challenge233.sdp.run_kyfan")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = (
    "GaussianRational",
    "PauliPolynomial",
    "PauliTerm",
    "PauliWord",
    "add_polynomials",
    "adjoint_polynomial",
    "canonical_relation_table_json",
    "canonicalize_word",
    "expand_word",
    "multiply_polynomials",
    "polynomial_from_word",
    "scale_polynomial",
    "export_constraint_map",
    "close_word_basis",
    "BlockadeQuotient",
    "build_blockade_quotient",
    "exact_ldlt_pivots",
    "kernel_localizer_rows",
    "literal_pauli_action",
    "slater_gram",
    "verify_blockade_quotient",
    "ConstraintMap",
    "IndexOrbit",
    "MomentEntry",
    "ZeroLocalizerRow",
    "blockade_polynomial",
    "build_constraint_map",
    "expand_moment_entry_orbits",
    "expand_zero_localizer_orbits",
    "pxp_hamiltonian_polynomial",
    "constrained_pauli_trace",
    "constrained_polynomial_trace",
    "periodic_blockade_dimension",
    "ConjugationReduction",
    "SparseRationalEntry",
    "SparseRationalPSDBlock",
    "build_conjugation_reduction",
    "verify_conjugation_reduction",
    "word_y_parity",
    "SAFE_LABELS",
    "SafeWord",
    "SandwichLocalizer",
    "SupportLocalizer",
    "build_safe_sandwich_localizers",
    "build_support_localizers",
    "expand_safe_word",
    "LOCAL_LEVELS",
    "HierarchyLevel",
    "clique_orbit",
    "global_pauli_basis",
    "local_pauli_basis",
    "safe_localizer_basis",
    "validate_nested_levels",
    "ExactColumnBasis",
    "ExactRowBasis",
    "gaussian_column_basis",
    "primitive_integer_row",
    "rational_row_basis",
    "verify_column_reconstruction",
    "verify_row_reconstruction",
    "AffineParameterization",
    "EqualityReduction",
    "compress_equalities",
    "verify_equality_reduction",
    "ComplexLinearForm",
    "CliqueImage",
    "ComplexPSDBlock",
    "KyFanProblem",
    "LinearEquality",
    "MagnitudeWitness",
    "MomentVariable",
    "RationalLinearForm",
    "RealPSDBlock",
    "build_global_kyfan_problem",
    "build_clique_images",
    "build_local_kyfan_problem",
    "build_magnitude_witnesses",
    "realify_hermitian_matrix",
    "export_kyfan_problem",
    "KyFanInstance",
    "KyFanStructure",
    "SparseComplexEntry",
    "SparseComplexPSDBlock",
    "build_global_kyfan_structure",
    "build_kyfan_instance",
    "build_local_kyfan_structure",
    "materialize_complex_blocks",
    "StructureBinding",
    "ReductionBinding",
    "canonical_json_bytes",
    "export_kyfan_instance",
    "export_solver_reduction",
    "export_shared_structure",
    "instance_payload",
    "logical_structure_sha256",
    "structure_payload",
    "KyFanSolverReduction",
    "ReducedRealPSDBlock",
    "build_kyfan_solver_reduction",
    "clarabel_hs_bytes",
    "estimate_reduced_resources",
    "solver_reduction_payload",
    "SparseRationalTransform",
    "SpatialBlock",
    "build_global_d4_reduction",
    "build_local_reflection_reduction",
    "induced_quotient_action",
    "verify_global_d4_reduction",
    "verify_induced_quotient_action",
    "verify_local_reflection_reduction",
    "verify_quotient_group_action",
    "validate_structure_payload",
    "verify_kyfan_structure",
    "verify_bound_kyfan_structure",
    "verify_kyfan_reduction",
    "verify_kyfan_problem",
    "TrialVector",
    "exact_rayleigh_quotient",
    "generate_quspin_trial",
    "round_trial_vector",
    "write_trial_vector",
    "DyadicFactor",
    "ExactDualIdentity",
    "build_dual_certificate",
    "exact_dual_identity",
    "positive_dyadic_factor",
    "ExactLiftedIdentity",
    "WeightedFactorOrbit",
    "build_weighted_factor_orbit",
    "exact_lifted_psd_contribution",
    "lift_reduced_duals",
    "literal_dense_residual_norm_bound",
    "moment_residual_correction",
    "physical_residual_correction",
    "reconstruct_equality_multipliers",
    "verify_kyfan_certificate",
    "CellSelection",
    "assembly_probe",
    "build_problem_for_cell",
    "build_structure_for_cell",
    "certify_cell",
    "certify_run",
    "estimate_solve_resources",
    "estimate_v2_solve_resources",
    "plan_escalation",
    "plan_v2_run",
    "prepare_cell",
    "prepare_run",
    "prepare_v2_cell",
    "prepare_v2_run",
    "remote_solve_command",
    "select_cell",
    "solve_local_cell",
    "DihedralIrrep",
    "DihedralElement",
    "SectorMultiplicity",
    "TranslationOrbit",
    "act_on_polynomial",
    "act_on_site",
    "act_on_word",
    "compose",
    "dihedral_irrep_catalog",
    "dihedral_elements",
    "normalize",
    "representation_permutation",
    "sector_multiplicities",
    "translation_orbits",
    "word_orbit",
)
