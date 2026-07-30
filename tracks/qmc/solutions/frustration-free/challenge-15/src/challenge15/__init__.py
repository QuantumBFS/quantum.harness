import jax

jax.config.update("jax_enable_x64", True)

from challenge15.angular import (
    angular_operators,
    target_irrep_isometry,
    verify_ladder_multiplet,
)
from challenge15.coulomb import (
    density_multipole_integrals,
    many_body_coulomb,
    orbital_coulomb_tensor,
    pair_pseudopotentials,
    pseudopotential_coulomb_tensor,
)
from challenge15.carriers import (
    carrier_amplitudes,
    carrier_determinant_coefficients,
)
from challenge15.chiral_source import PairReducedSource, lhyr_pair_reduced_source
from challenge15.fermions import (
    DeterminantBasis,
    apply_annihilation,
    apply_creation,
    apply_one_body,
)
from challenge15.monopole import (
    north_lll_orbitals,
    normalized_spinors,
    raw_north_lll_polynomials,
    rotate_spinors,
    south_lll_orbitals,
)
from challenge15.model import (
    BatchedLogAmplitude,
    ModelConfig,
    ProjectedPfaffianNQS,
    embed_adam_state,
    embed_rank,
    gated_carrier,
)
from challenge15.nqs_bridge import DeterminantState, nqs_determinant_state
from challenge15.pfaffian import bordered_pfaffian, pfaffian
from challenge15.projector import ProjectionGrid, project_m0, project_multiplet
from challenge15.production_vmc import (
    CoordinateEvaluationShard,
    ProductionVMCConfig,
    evaluate_coordinates,
    score_covariance_finite_chain,
    train_rank,
)
from challenge15.response_operator import ResponseFamily, build_response_family
from challenge15.spec import SphereSpec
from challenge15.spectral_response import (
    ChannelSpectrum,
    ChiralSpectrum,
    PoleGroup,
    exact_chiral_spectrum,
    exact_chiral_spectrum_for_size,
    nqs_mixed_chiral_spectrum,
)
from challenge15.train import (
    RankConvergence,
    RankEvaluation,
    SeedRankEvaluation,
    TrainConfig,
    TrainResult,
    analyze_rank_convergence,
    analyze_stochastic_rank_convergence,
    train_joint_sectors,
)

__all__ = [
    "SphereSpec",
    "DeterminantBasis",
    "apply_creation",
    "apply_annihilation",
    "apply_one_body",
    "angular_operators",
    "target_irrep_isometry",
    "verify_ladder_multiplet",
    "density_multipole_integrals",
    "orbital_coulomb_tensor",
    "pair_pseudopotentials",
    "pseudopotential_coulomb_tensor",
    "many_body_coulomb",
    "pfaffian",
    "bordered_pfaffian",
    "carrier_amplitudes",
    "carrier_determinant_coefficients",
    "PairReducedSource",
    "lhyr_pair_reduced_source",
    "ResponseFamily",
    "build_response_family",
    "PoleGroup",
    "ChannelSpectrum",
    "ChiralSpectrum",
    "exact_chiral_spectrum",
    "exact_chiral_spectrum_for_size",
    "DeterminantState",
    "nqs_determinant_state",
    "nqs_mixed_chiral_spectrum",
    "BatchedLogAmplitude",
    "ModelConfig",
    "ProjectedPfaffianNQS",
    "embed_adam_state",
    "embed_rank",
    "gated_carrier",
    "ProjectionGrid",
    "project_m0",
    "project_multiplet",
    "ProductionVMCConfig",
    "CoordinateEvaluationShard",
    "score_covariance_finite_chain",
    "train_rank",
    "evaluate_coordinates",
    "normalized_spinors",
    "north_lll_orbitals",
    "raw_north_lll_polynomials",
    "south_lll_orbitals",
    "rotate_spinors",
    "TrainConfig",
    "TrainResult",
    "RankEvaluation",
    "SeedRankEvaluation",
    "RankConvergence",
    "train_joint_sectors",
    "analyze_rank_convergence",
    "analyze_stochastic_rank_convergence",
]
