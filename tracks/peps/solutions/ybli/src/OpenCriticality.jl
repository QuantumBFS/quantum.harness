"""
    OpenCriticality

Julia module for computing conformal data in open quantum systems via
Born-weighted random transfer-matrix products and Lyapunov spectra.

Implements the workflow from Challenge #122:
  1. Model conventions (Conventions.jl)
  2. Model definitions: Classical Ising, Nishimori RBIM, Measured Toric Code (Models.jl)
  3. Tensor-network contraction: dense + boundary-MPS backends (Contraction.jl)
  4. Lyapunov exponents: power iteration + Householder QR (Lyapunov.jl)
  5. Samplers: direct iid, Metropolis, sequential Born (Samplers.jl)
  6. Finite-size scaling: central-charge fits, bootstrap, scaling dimensions (FiniteSizeScaling.jl)

Usage:
  using OpenCriticality
  model = ClassicalIsing(L=8)
  config = sample_config(model, Random.default_rng(), 100)
  logZ = dense_logZ(model, config)
  gamma0 = leading_lyapunov(model, config)
"""
module OpenCriticality

using Random
using LinearAlgebra
using Statistics

# Include submodules
include("Conventions.jl")
include("Models.jl")
include("Contraction.jl")
include("Lyapunov.jl")
include("Samplers.jl")
include("FiniteSizeScaling.jl")

# Convention exports
export ModelConvention, ClassicalIsingConvention, NishimoriConvention,
       MeasuredToricCodeConvention, free_energy_per_row

# Model exports
export BornModel, Configuration, ClassicalIsing, NishimoriRBIM,
       MeasuredToricCode, physical_dim, convention, width,
      sample_config, build_row_transfer_dense, build_local_mpo_tensor,
      boltzmann_matrix, sqrt_boltzmann,
      elem_sqrt_boltzmann,
      index_to_spins, spins_to_index, exact_partition_function

# Contraction exports
export dense_logZ, dense_free_energy,
       BoundaryMPS, init_boundary_mps, init_product_boundary_mps,
       apply_mpo_and_compress!, boundary_mps_logZ, boundary_mps_free_energy,
       pepskit_infinite_free_energy

# Lyapunov exports
export leading_lyapunov, lyapunov_spectrum, lyapunov_gap,
       class_d_diagnostics, scaling_dimension, svd_lyapunov_check

# Sampler exports
export SampleResult, DirectSampler, MetropolisSampler, SequentialBornSampler,
       sample!, run_direct, run_metropolis!, step!,
       propose_local, propose_row, propose_loop, propose_global,
       integrated_autocorrelation_time, block_mean

# Finite-size scaling exports
export fit_central_charge, effective_c_eff, pair_estimator_table,
       stability_envelope, bootstrap_c_eff, fit_scaling_dimension,
       free_energy_density, free_energy_densities, summarize_fit

end # module
