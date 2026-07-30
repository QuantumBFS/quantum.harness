module QuantumMCMethodsMinimal

using LinearAlgebra
using Random
using Statistics

const SOURCE_DIRECTORY = normpath(joinpath(@__DIR__, "..", "src"))

include(joinpath(SOURCE_DIRECTORY, "models.jl"))
include(joinpath(SOURCE_DIRECTORY, "sse.jl"))
include(joinpath(SOURCE_DIRECTORY, "analysis.jl"))
include(joinpath(SOURCE_DIRECTORY, "diagnostics.jl"))

end
