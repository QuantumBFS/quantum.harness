using QuantumGapHierarchy
using JSON3
using JuMP

length(ARGS) >= 2 || error("usage: dry_assemble.jl GRAPH.json SPEC.json [OUTPUT.json]")
graph = read_graph_json(ARGS[1])
data = JSON3.read(read(ARGS[2],String))
spec = LevelSpec(String(data.geometry),Int(data.L),Int(data.d),Int(data.nmax),
                 Symbol(String(data.encoding)),Symbol(String(data.basis_family)),Symbol(String(data.symmetry)))
ENV["ISSUE92_BUILD_PROGRESS"] = get(ENV,"ISSUE92_BUILD_PROGRESS","1")
println("assembling $(spec.geometry) nmax=$(spec.nmax) (L,d)=($(spec.L),$(spec.d)) $(spec.basis_family)")
flush(stdout)
started = time()
template = build_level(spec,graph)
template.metadata["assembly_seconds"] = time()-started
if get(ENV,"ISSUE92_DRY_BUILD_MODEL","0") == "1"
    println("building unsolved Clarabel/JuMP workspace")
    flush(stdout)
    model_started = time()
    workspace = QuantumGapHierarchy._build_model(
        template,ModelParams(3//100,1,1//2,0);solver=:clarabel,quiet=true,
    )
    template.metadata["model_build_seconds"] = time()-model_started
    template.metadata["jump_variable_count"] = JuMP.num_variables(workspace.model)
    template.metadata["model_build_solver"] = workspace.solver_name
    template.metadata["model_optimized"] = false
end
for key in ("window_sites","interior_sites","moment_basis_count","gap_basis_count",
            "stationarity_basis_count","moment_variable_count","real_scalar_variable_count",
            "equality_count","moment_block_sizes","gap_block_sizes","affine_term_count",
            "estimated_memory_gb","assembly_seconds")
    println("$key=$(template.metadata[key])")
end
for key in ("model_build_seconds","jump_variable_count","model_build_solver","model_optimized")
    haskey(template.metadata,key) && println("$key=$(template.metadata[key])")
end
flush(stdout)
length(ARGS) >= 3 && write_template_summary(ARGS[3],template)
