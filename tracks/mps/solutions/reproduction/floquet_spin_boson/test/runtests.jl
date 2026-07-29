using Test

include(joinpath(@__DIR__, "..", "src", "FloquetSpinBoson.jl"))
using .FloquetSpinBoson

include("test_model.jl")
include("test_uniform_if.jl")
include("test_uniform_if_cli.jl")
include("test_floquet_operator.jl")
include("test_steady_state.jl")
include("test_correlations.jl")
include("test_correlation_decomposition.jl")
include("test_heat_current.jl")
include("test_fig5.jl")
include("test_convergence.jl")
include("test_regression.jl")
