using QuantumGapHierarchy
using JSON3

length(ARGS)==2 || error("usage: run_cell.jl CELL.json OUTPUT.json")
cell = JSON3.read(read(ARGS[1],String))
output = ARGS[2]
graph = read_graph_json(String(cell.graph_path))
spec = LevelSpec(String(cell.geometry),Int(cell.L),Int(cell.d),Int(cell.nmax),
                 Symbol(String(cell.encoding)),Symbol(String(cell.basis_family)),Symbol(String(cell.symmetry)))
params = ModelParams(Float64(cell.t),Float64(cell.U),Float64(cell.mu),
                     cell.gamma === nothing ? 0.0 : Float64(cell.gamma))
solver = Symbol(lowercase(get(ENV,"ISSUE92_SOLVER","mosek")))
solver in (:clarabel,:mosek) || error("ISSUE92_SOLVER must be clarabel or mosek")
println("building cell $(cell.id)")
flush(stdout)
template = build_level(spec,graph)

record_payload(record) = QuantumGapHierarchy._record_dict(record)

property(data,key::Symbol,default=nothing) = data isa AbstractDict ?
    get(data,String(key),get(data,key,default)) :
    (hasproperty(data,key) ? getproperty(data,key) : default)
finite_or_nan(value) = value === nothing ? NaN : Float64(value)

function resumed_record(item)
    data = property(item,:record)
    gamma = property(data,:gamma)
    gamma === nothing && error("saved gap checkpoint has no trial gamma and cannot be resumed safely")
    trial_params = ModelParams(params.t,params.U,params.mu,Float64(gamma))
    SolveRecord(
        Symbol(String(property(data,:classification))),
        String(property(data,:raw_status,"RESUMED")),
        String(property(data,:solver,String(solver))),
        Float64(property(data,:runtime_seconds,0.0)),
        property(data,:objective) === nothing ? nothing : Float64(property(data,:objective)),
        finite_or_nan(property(data,:primal_residual)),
        finite_or_nan(property(data,:dual_residual)),
        finite_or_nan(property(data,:min_psd_eigenvalue)),
        Symbol(String(property(data,:certificate_class,"NO_CERTIFICATE"))),
        String(property(data,:message,"resumed checkpoint")),
        Dict("params"=>trial_params),
        Dict{String,Any}(),
    )
end

function atomic_payload(payload)
    temporary = output*".tmp"
    open(temporary,"w") do io
        JSON3.pretty(io,payload)
        write(io,'\n')
    end
    mv(temporary,output;force=true)
end

saved = nothing
if get(ENV,"ISSUE92_FORCE","0") != "1" && isfile(output)
    candidate = JSON3.read(read(output,String))
    String(property(candidate,:status,"")) == "RUNNING" && (saved=candidate)
end

base = Dict("cell"=>Dict(pairs(cell)),"level"=>template.metadata,"solver_backend"=>String(solver))
if String(cell.kind)=="gap"
    history = Any[]
    resume_records = SolveRecord[]
    if saved !== nothing
        for item in property(saved,:history,Any[])
            push!(history,item)
            push!(resume_records,resumed_record(item))
        end
        println("resuming $(cell.id) after $(length(history)) completed gap trials")
        flush(stdout)
    end
    checkpoint = function (bracket,record)
        push!(history,Dict("bracket"=>collect(bracket),"record"=>record_payload(record)))
        atomic_payload(merge(copy(base),Dict("status"=>"RUNNING","history"=>history)))
        println("checkpoint $(cell.id): $(record.classification), bracket=$(bracket)")
        flush(stdout)
    end
    bracket = bisect_gap(template,params;tolerance=0.005,solver=solver,checkpoint=checkpoint,
                         resume_records=resume_records)
    function endpoint_classification(endpoint)
        for record in Iterators.reverse(bracket.records)
            trial_params = get(record.primal,"params",nothing)
            trial_params isa ModelParams || continue
            Float64(trial_params.gamma) == endpoint && return String(record.classification)
        end
        "UNKNOWN"
    end
    payload = merge(copy(base),Dict(
        "status"=>"COMPLETE","classification"=>(bracket.complete ? "EXCLUDED" : "UNKNOWN"),
        "gap_bracket"=>[bracket.lower,bracket.upper],"tolerance"=>bracket.tolerance,
        "lower_classification"=>endpoint_classification(bracket.lower),
        "upper_classification"=>endpoint_classification(bracket.upper),
        "reason"=>bracket.reason,"history"=>history,
    ))
    atomic_payload(payload)
else
    results = Any[]
    exact_observable_certificate =
        get(ENV,"ISSUE92_EXACT_OBSERVABLE_CERTIFICATE","0") == "1" ||
        Bool(property(cell,:exact_observable_certificate,false))
    finished = Set{Tuple{Symbol,Symbol}}()
    if saved !== nothing
        for item in property(saved,:results,Any[])
            key = (Symbol(String(property(item,:observable))),Symbol(String(property(item,:sense))))
            key in finished && error("duplicate saved observable checkpoint for $key")
            push!(finished,key)
            push!(results,item)
        end
        println("resuming $(cell.id) after $(length(results)) completed objectives")
        flush(stdout)
    end
    derive_hardcore_fluctuation =
        Int(cell.nmax)==1 && get(ENV,"ISSUE92_DERIVE_HARDCORE_F0","1") == "1"

    function result_item(observable::Symbol,sense::Symbol)
        matches = [
            item for item in results
            if Symbol(String(property(item,:observable)))==observable &&
               Symbol(String(property(item,:sense)))==sense
        ]
        length(matches)==1 || error("expected one saved result for $observable $sense")
        only(matches)
    end

    function derived_hardcore_fluctuation_record(source_item,sense::Symbol)
        source_sense = sense==:min ? :max : :min
        source_record = property(source_item,:record)
        source_objective = property(source_record,:objective)
        source_dual = property(source_record,:dual_data,Dict{String,Any}())
        source_report = property(source_dual,:certificate_report,nothing)
        certified_source_objective = source_report === nothing ? source_objective :
            property(source_report,:certified_objective,source_objective)
        source_classification = String(property(source_record,:classification,"UNKNOWN"))
        source_certificate = String(property(source_record,:certificate_class,"NO_CERTIFICATE"))
        derived_certificate = source_classification=="FEASIBLE" ?
            "DERIVED_EXACT_AFFINE_FROM_$(source_certificate)" : source_certificate
        Dict(
            "classification"=>source_classification,
            "raw_status"=>"DERIVED_EXACT_AFFINE",
            "solver"=>String(property(source_record,:solver,String(solver))),
            "runtime_seconds"=>0.0,
            "objective"=>(certified_source_objective===nothing ? nothing :
                1.0-Float64(certified_source_objective)),
            "primal_residual"=>property(source_record,:primal_residual),
            "dual_residual"=>property(source_record,:dual_residual),
            "min_psd_eigenvalue"=>property(source_record,:min_psd_eigenvalue),
            "certificate_class"=>derived_certificate,
            "message"=>"exact hard-core identity F0=1-rho0; derived from rho0 $(source_sense) without another SDP solve",
            "gamma"=>property(source_record,:gamma),
            "parameters_exact"=>property(source_record,:parameters_exact),
            "primal_data"=>Dict(
                "exact_identity"=>"n0^2=n0, hence (n0-1)^2=1-n0 at nmax=1",
                "source_observable"=>"rho0",
                "source_sense"=>String(source_sense),
                "source_floating_objective"=>source_objective,
                "source_certified_objective"=>certified_source_objective,
            ),
            "dual_data"=>Dict(
                "source_result_reference"=>"rho0/$(source_sense) in this cell",
                "source_certificate_class"=>source_certificate,
                "source_certificate_report"=>source_report,
            ),
        )
    end

    for observable in (:rho0,:F0,:K0), sense in (:min,:max)
        (observable,sense) in finished && continue
        if observable==:F0 && derive_hardcore_fluctuation
            source_sense = sense==:min ? :max : :min
            source = result_item(:rho0,source_sense)
            println("deriving $(cell.id) F0 $(sense) from rho0 $(source_sense)")
            flush(stdout)
            push!(results,Dict(
                "observable"=>"F0","sense"=>String(sense),
                "record"=>derived_hardcore_fluctuation_record(source,sense),
            ))
            atomic_payload(merge(copy(base),Dict("status"=>"RUNNING","results"=>results)))
            continue
        end
        println("solving $(cell.id) $(observable) $(sense)")
        flush(stdout)
        record = solve_observable(
            template,params,observable,sense;solver=solver,
            exact_certificate=exact_observable_certificate,
        )
        push!(results,Dict("observable"=>String(observable),"sense"=>String(sense),
                           "record"=>record_payload(record)))
        atomic_payload(merge(copy(base),Dict("status"=>"RUNNING","results"=>results)))
    end
    atomic_payload(merge(copy(base),Dict("status"=>"COMPLETE","results"=>results)))
end
println("finished $(cell.id)")
flush(stdout)
