function read_graph_json(path::AbstractString)
    data = JSON3.read(read(path,String))
    vertices = Int.(data.vertices)
    edges = [(Int(edge[1]),Int(edge[2])) for edge in data.edges]
    radius = hasproperty(data,:radius) ? Int(data.radius) : nothing
    graph = RootedGraph(
        vertices,edges;root=Int(data.root),geometry=String(data.geometry),
        source=String(data.source),known_radius=radius,
    )
    expected_degree = get(Dict("83"=>3,"124"=>4,"line83"=>4),graph.geometry,nothing)
    if expected_degree !== nothing && radius !== nothing
        for vertex in graph.vertices
            graph.distance[vertex] < radius || continue
            length(neighbors(graph,vertex)) == expected_degree || throw(ArgumentError(
                "graph export is incomplete inside its declared radius: vertex $vertex has " *
                "degree $(length(neighbors(graph,vertex))), expected $expected_degree",
            ))
        end
    end
    graph
end

_json_scalar(value::AbstractFloat) = isfinite(value) ? value : nothing
_json_scalar(value) = value

_rational_string(value::Rational) = "$(numerator(value))//$(denominator(value))"

function _q23_dict(value::Q23)
    Dict(
        "field"=>"Q(sqrt(2),sqrt(3))",
        "a"=>_rational_string(value.a),
        "b"=>_rational_string(value.b),
        "c"=>_rational_string(value.c),
        "d"=>_rational_string(value.d),
        "float64"=>Float64(value),
    )
end

function _params_dict(params::ModelParams)
    Dict(
        "t"=>_q23_dict(params.t),
        "U"=>_q23_dict(params.U),
        "mu"=>_q23_dict(params.mu),
        "gamma"=>_q23_dict(params.gamma),
    )
end

function _json_data(value)
    value === nothing && return nothing
    value isa AbstractFloat && return _json_scalar(value)
    value isa Q23 && return _q23_dict(value)
    value isa ModelParams && return _params_dict(value)
    value isa Symbol && return String(value)
    if value isa AbstractMatrix
        return Dict(
            "shape"=>[size(value,1),size(value,2)],
            "column_major_data"=>[_json_data(item) for item in vec(value)],
        )
    elseif value isa AbstractVector || value isa Tuple
        return [_json_data(item) for item in value]
    elseif value isa AbstractDict
        return Dict(String(key)=>_json_data(item) for (key,item) in value)
    end
    value
end

"""JSON-safe solve record, including every preserved primal and dual value."""
function _record_dict(record::SolveRecord)
    params = get(record.primal,"params",nothing)
    primal = Dict(String(key)=>_json_data(value) for (key,value) in record.primal if key != "params")
    Dict(
        "classification"=>String(record.classification),"raw_status"=>record.raw_status,
        "solver"=>record.solver,"runtime_seconds"=>record.runtime_seconds,
        "objective"=>_json_data(record.objective),"primal_residual"=>_json_scalar(record.primal_residual),
        "dual_residual"=>_json_scalar(record.dual_residual),
        "min_psd_eigenvalue"=>_json_scalar(record.min_psd_eigenvalue),
        "certificate_class"=>String(record.certificate_class),"message"=>record.message,
        "gamma"=>(params isa ModelParams ? Float64(params.gamma) : nothing),
        "parameters_exact"=>(params isa ModelParams ? _params_dict(params) : nothing),
        "primal_data"=>primal,
        "dual_data"=>_json_data(record.dual),
    )
end

function write_record_json(path::AbstractString,record::SolveRecord;metadata=Dict())
    payload = merge(Dict("record"=>_record_dict(record)),Dict("metadata"=>metadata))
    temporary = path*".tmp"
    open(temporary,"w") do io
        JSON3.pretty(io,payload)
        write(io,'\n')
    end
    mv(temporary,path;force=true)
    path
end

function write_template_summary(path::AbstractString,template::HierarchyTemplate)
    temporary = path*".tmp"
    open(temporary,"w") do io
        JSON3.pretty(io,template.metadata)
        write(io,'\n')
    end
    mv(temporary,path;force=true)
    path
end
