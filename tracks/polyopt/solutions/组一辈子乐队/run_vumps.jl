include("VUMPSProducer.jl")
using .VUMPSProducer
using JSON

output = length(ARGS) >= 1 ? ARGS[1] : "vumps.json"
rows = Any[]
for D in 1:4
    println("VUMPS D=$D starting")
    flush(stdout)
    result = run_vumps_with_fallback(VUMPSSettings(; D, maxiter=300, tol=1e-10, seed=1000+D, verbosity=0))
    push!(rows, result.record)
    energy = result.record["energy_per_site"]
    delta = result.record["algorithm_error"]
    println("VUMPS D=$D E=$energy delta=$delta")
    flush(stdout)
end
open(output, "w") do io
    JSON.print(io, Dict("exact_energy" => 1/4-log(2), "runs" => rows), 2)
end
