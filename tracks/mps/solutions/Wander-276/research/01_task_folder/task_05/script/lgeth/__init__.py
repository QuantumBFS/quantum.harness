"""Independent numerical core for the large-scale Geometric-ETH companion."""

from .channels import (
    PhysicalChannelCache,
    build_physical_channel_cache,
    cached_channel,
    normalized_potential,
    root_response_partition,
)
from .grassmann import covariance_deformed_rows
from .form_factors import (
    FormFactorParts,
    JacobiFormFactor,
    atom_raw_decomposition,
    degenerate_energy_form_factor,
    finite_jacobi_form_factor,
    form_factor_parts,
)
from .controls import (
    FixedProjectorControl,
    FourierTangentPair,
    fixed_projector_spectral_ensemble,
    fourier_tangent_pairs,
    gram_normalize,
    scrambled_tangent_pair,
)
from .jacobi import (
    NormalizedCurvature,
    jacobi_parameters,
    normalized_curvature,
    sample_jacobi_interior,
)
from .manybody_response import (
    KernelFrame,
    ManyBodyCase,
    SiteResponseCache,
    build_site_response_cache,
    registered_fixed_two_qh_cases,
    solve_kernel_frame,
)
from .wick_channels import (
    WickResult,
    assemble_channels,
    covariance_matched_wick,
    fourier_density_panel,
    gaussian_r4_reference,
    local_density_panels,
)
from .bundle_geometry import (
    BundleGeometry,
    analyze_ambient_frame_mesh,
    analyze_frame_bundle,
    manybody_frame_overlap,
)
from .twist_bundle import (
    TwistBundle,
    build_twist_bundle,
    load_twist_bundle,
    save_twist_bundle,
)
from .holonomy import (
    ambient_unitary,
    cue_wilson_reference,
    deform_orbital_mesh,
    local_generator_pair,
    wilson_statistics,
)

__all__ = [
    "FormFactorParts",
    "BundleGeometry",
    "FixedProjectorControl",
    "FourierTangentPair",
    "JacobiFormFactor",
    "KernelFrame",
    "ManyBodyCase",
    "NormalizedCurvature",
    "PhysicalChannelCache",
    "SiteResponseCache",
    "TwistBundle",
    "WickResult",
    "atom_raw_decomposition",
    "analyze_ambient_frame_mesh",
    "analyze_frame_bundle",
    "ambient_unitary",
    "assemble_channels",
    "build_physical_channel_cache",
    "build_site_response_cache",
    "build_twist_bundle",
    "cached_channel",
    "covariance_deformed_rows",
    "covariance_matched_wick",
    "cue_wilson_reference",
    "degenerate_energy_form_factor",
    "deform_orbital_mesh",
    "finite_jacobi_form_factor",
    "fixed_projector_spectral_ensemble",
    "form_factor_parts",
    "fourier_tangent_pairs",
    "fourier_density_panel",
    "gaussian_r4_reference",
    "gram_normalize",
    "jacobi_parameters",
    "local_density_panels",
    "local_generator_pair",
    "load_twist_bundle",
    "manybody_frame_overlap",
    "normalized_curvature",
    "normalized_potential",
    "registered_fixed_two_qh_cases",
    "root_response_partition",
    "sample_jacobi_interior",
    "save_twist_bundle",
    "scrambled_tangent_pair",
    "solve_kernel_frame",
    "wilson_statistics",
]
