using Test

const SOURCE_ROOT = normpath(joinpath(@__DIR__, "..", "src"))

include(joinpath(SOURCE_ROOT, "SquareJ1J2Prototype.jl"))
using .SquareJ1J2Prototype
include(joinpath(SOURCE_ROOT, "GenericGapModel.jl"))
using .GenericGapModel
include(joinpath(SOURCE_ROOT, "PrimalGapSymbolics.jl"))
using .PrimalGapSymbolics
include(joinpath(SOURCE_ROOT, "PrimalGapAssembly.jl"))
using .PrimalGapAssembly
include(joinpath(SOURCE_ROOT, "PrimalGapJuMP.jl"))
using .PrimalGapJuMP

include(joinpath(@__DIR__, "exact_symmetry_reduction_truth_tests.jl"))
