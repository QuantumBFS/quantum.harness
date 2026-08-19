include(joinpath(@__DIR__, "..", "src", "SquareJ1J2Prototype.jl"))
using .SquareJ1J2Prototype

include(joinpath(@__DIR__, "..", "src", "GenericGapModel.jl"))
using .GenericGapModel

include(joinpath(@__DIR__, "..", "src", "SmallEDOracle.jl"))
using .SmallEDOracle

result = run_small_ed_oracle(1; g=1//2)
for key in keys(result)
    println(key, " = ", getproperty(result, key))
end
