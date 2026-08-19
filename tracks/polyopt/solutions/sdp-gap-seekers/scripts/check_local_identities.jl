include(joinpath(@__DIR__, "..", "src", "LocalSpinIdentities.jl"))
using .LocalSpinIdentities

checks = local_identity_checks()
for key in sort(collect(keys(checks)))
    println(key, " = ", checks[key])
end

boolean_checks = [value for value in values(checks) if value isa Bool]
all(boolean_checks) || error("at least one exact local identity failed")
