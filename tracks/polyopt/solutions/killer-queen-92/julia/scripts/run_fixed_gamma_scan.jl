using QuantumGapHierarchy
using JSON3

length(ARGS)==2 || error("usage: run_fixed_gamma_scan.jl CELL.json OUTPUT.json")
cell = JSON3.read(read(ARGS[1],String))
output = ARGS[2]
String(cell.kind)=="gap_scan" || error("fixed-gamma runner requires kind=gap_scan")

property(data,key::Symbol,default=nothing) = data isa AbstractDict ?
    get(data,String(key),get(data,key,default)) :
    (hasproperty(data,key) ? getproperty(data,key) : default)

function atomic_payload(payload)
    temporary = output*".tmp"
    open(temporary,"w") do io
        JSON3.pretty(io,payload)
        write(io,'\n')
    end
    mv(temporary,output;force=true)
end

graph = read_graph_json(String(cell.graph_path))
spec = LevelSpec(
    String(cell.geometry),Int(cell.L),Int(cell.d),Int(cell.nmax),
    Symbol(String(cell.encoding)),Symbol(String(cell.basis_family)),Symbol(String(cell.symmetry)),
)
solver = Symbol(lowercase(get(ENV,"ISSUE92_SOLVER","clarabel")))
solver in (:clarabel,:mosek) || error("ISSUE92_SOLVER must be clarabel or mosek")
println("building fixed-gamma scan $(cell.id)")
flush(stdout)
template = build_level(spec,graph)
base = Dict(
    "cell"=>Dict(pairs(cell)),
    "level"=>template.metadata,
    "solver_backend"=>String(solver),
    "scan_type"=>"independent_fixed_gamma_nonadaptive",
)

trials = Any[]
finished = Set{Float64}()
if get(ENV,"ISSUE92_FORCE","0") != "1" && isfile(output)
    saved = JSON3.read(read(output,String))
    if String(property(saved,:status,"")) == "RUNNING"
        for item in property(saved,:trials,Any[])
            gamma = Float64(property(item,:gamma))
            gamma in finished && error("duplicate saved fixed-gamma checkpoint at gamma=$gamma")
            push!(finished,gamma)
            push!(trials,item)
        end
        println("resuming $(cell.id) after $(length(trials)) completed trials")
        flush(stdout)
    end
end
atomic_payload(merge(copy(base),Dict("status"=>"RUNNING","trials"=>trials)))

function feasible_anchor(gamma::Float64)
    gamma==0.0 || return nothing
    hasproperty(cell,:feasible_anchor_path) || return nothing
    path = String(cell.feasible_anchor_path)
    isfile(path) || return nothing
    payload = JSON3.read(read(path,String))
    for item in property(payload,:results,Any[])
        record = property(item,:record)
        String(property(record,:classification,"UNKNOWN"))=="FEASIBLE" || continue
        record_gamma = property(record,:gamma)
        record_gamma===nothing && continue
        abs(Float64(record_gamma)-gamma)<=1e-12 || continue
        anchored = Dict(String(key)=>value for (key,value) in pairs(record))
        anchored["anchor_source"] = path
        anchored["message"] = String(property(record,:message,"")) *
            "; reused as a feasibility anchor from an independently checked observable solve"
        return anchored
    end
    nothing
end

for raw_gamma in cell.gamma_trials
    gamma = Float64(raw_gamma)
    gamma in finished && continue
    anchor = feasible_anchor(gamma)
    if anchor !== nothing
        push!(trials,Dict("gamma"=>gamma,"record"=>anchor,"source"=>"observable_feasible_anchor"))
        push!(finished,gamma)
        atomic_payload(merge(copy(base),Dict("status"=>"RUNNING","trials"=>trials)))
        println("checkpoint $(cell.id) gamma=$(gamma): FEASIBLE anchor reused")
        flush(stdout)
        continue
    end
    params = ModelParams(Float64(cell.t),Float64(cell.U),Float64(cell.mu),gamma)
    println("solving $(cell.id) gamma=$(gamma)")
    flush(stdout)
    record = solve_feasibility(template,params;solver=solver)
    push!(trials,Dict("gamma"=>gamma,"record"=>QuantumGapHierarchy._record_dict(record)))
    push!(finished,gamma)
    atomic_payload(merge(copy(base),Dict("status"=>"RUNNING","trials"=>trials)))
    println(
        "checkpoint $(cell.id) gamma=$(gamma): $(record.classification), " *
        "raw=$(record.raw_status), runtime=$(round(record.runtime_seconds;digits=2))s",
    )
    flush(stdout)
end

classifications = [String(property(property(item,:record),:classification)) for item in trials]
workspace = isempty(template.solver_cache) ? nothing : only(values(template.solver_cache))
payload = merge(copy(base),Dict(
    "status"=>"COMPLETE",
    "trials"=>trials,
    "classification_counts"=>Dict(
        label=>count(==(label),classifications) for label in ("FEASIBLE","EXCLUDED","UNKNOWN")
    ),
    "workspace_solve_count"=>(workspace===nothing ? 0 : workspace.solve_count),
    "workspace_parameter_update_count"=>(workspace===nothing ? 0 : workspace.parameter_update_count),
))
atomic_payload(payload)
println("finished fixed-gamma scan $(cell.id)")
flush(stdout)
