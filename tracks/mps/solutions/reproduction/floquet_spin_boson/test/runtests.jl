using Test

include(joinpath(@__DIR__, "..", "src", "FloquetSpinBoson.jl"))
using .FloquetSpinBoson

include("test_model.jl")
include("test_regression.jl")
