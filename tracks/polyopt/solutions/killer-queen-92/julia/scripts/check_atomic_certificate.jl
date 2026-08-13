using QuantumGapHierarchy
using JSON3

output = length(ARGS) >= 1 ? ARGS[1] : "results/atomic/julia-hierarchy-certificate.json"
graph = RootedGraph([0,1],[(0,1)];root=0,geometry="atomic",source="exact-two-site-buffer")
spec = LevelSpec("atomic",1,2,1,:matrix,:complete,PRIMARY_SYMMETRY)
template = build_level(spec,graph)

below = solve_feasibility(template,ModelParams(0,1,1//2,49//100);solver=:clarabel)
above = solve_feasibility(template,ModelParams(0,1,1//2,51//100);solver=:clarabel)
rho_min = solve_observable(template,ModelParams(0,1,1//2,0),:rho0,:min;
                           solver=:clarabel,exact_certificate=true)
rho_max = solve_observable(template,ModelParams(0,1,1//2,0),:rho0,:max;
                           solver=:clarabel,exact_certificate=true)

payload = Dict(
    "model"=>"t=0 truncated Bose-Hubbard atomic regression through the complete hierarchy",
    "analytical_gap"=>0.5,
    "level"=>template.metadata,
    "below_gamma_0.49"=>QuantumGapHierarchy._record_dict(below),
    "above_gamma_0.51"=>QuantumGapHierarchy._record_dict(above),
    "rho0_min_gamma_0"=>QuantumGapHierarchy._record_dict(rho_min),
    "rho0_max_gamma_0"=>QuantumGapHierarchy._record_dict(rho_max),
)
mkpath(dirname(output))
temporary = output*".tmp"
open(temporary,"w") do io
    JSON3.pretty(io,payload)
    write(io,'\n')
end
mv(temporary,output;force=true)

below.classification == :FEASIBLE || error("gamma=0.49 was not verified feasible")
above.classification == :EXCLUDED || error("gamma=0.51 lacks a verified exact exclusion")
above.certificate_class == :VERIFIED_EXACT_PROJECTED || error("atomic exclusion was not exact-projected")
for record in (rho_min,rho_max)
    record.classification == :FEASIBLE || error("rho0 bound failed primal/dual checks")
    isapprox(record.objective,1.0;atol=2e-5) || error("rho0 atomic bound does not equal one")
    record.certificate_class == :VERIFIED_EXACT_PROJECTED_BOUND ||
        error("rho0 bound lacks a verified exact observable certificate")
end
println("atomic hierarchy certificate: PASS; wrote $output")
