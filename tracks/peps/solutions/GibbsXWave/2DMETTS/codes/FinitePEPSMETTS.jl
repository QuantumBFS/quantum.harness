module FinitePEPSMETTS

using LinearAlgebra
using Random
using Statistics
using TensorKit

include("model.jl")
include("state.jl")
include("simple_update.jl")
include("boundary_mps.jl")
include("observables.jl")
include("metts.jl")

function default_metts_parameters(;
    J=1.0,
    h=2.9,
    beta=1 / 0.6085,
    D=3,
    chi=64,
    tau=0.05,
    burn_in=20,
    samples=100,
    thinning=1,
    seed=20260727,
)
    return Dict{Symbol,Any}(
        :J => Float64(J),
        :h => Float64(h),
        :beta => Float64(beta),
        :D => Int(D),
        :chi => Int(chi),
        :tau => Float64(tau),
        :TrotterOrder => 2,
        :burn_in => Int(burn_in),
        :samples => Int(samples),
        :thinning => Int(thinning),
        :seed => Int(seed),
        :initial_state => :all_up,
        :initial_basis => :Z,
        :measure_correlations => true,
        :verbose => 1,
    )
end

export BoundaryMPSResult,
    DenseFinitePEPS,
    DenseFinitePEPSGammaLambda,
    METTSResult,
    X,
    Z,
    boundary_mps_contract,
    collapse_basis,
    collapse_projectors,
    collapse_x_basis,
    collapse_z_basis,
    default_metts_parameters,
    exact_thermal_observables,
    exact_wavefunction,
    imaginary_time_evolve!,
    metts_observables,
    product_peps,
    run_metts,
    summarize_samples,
    validate_finite_peps

end
