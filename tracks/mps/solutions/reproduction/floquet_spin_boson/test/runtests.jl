using Test

include(joinpath(@__DIR__, "..", "src", "FloquetSpinBoson.jl"))
using .FloquetSpinBoson

include("test_model.jl")
include("test_uniform_if.jl")
include("test_uniform_if_cli.jl")
include("test_floquet_operator.jl")
include("test_regression.jl")
