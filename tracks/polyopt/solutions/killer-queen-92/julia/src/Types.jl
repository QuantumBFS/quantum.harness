const PRIMARY_SYMMETRY = :U1_INVARIANT_KMS_STATES
const UNRESTRICTED_SYMMETRY = :UNRESTRICTED_KMS_STATES

struct LevelSpec
    geometry::String
    L::Int
    d::Int
    nmax::Int
    encoding::Symbol
    basis_family::Symbol
    symmetry::Symbol
    function LevelSpec(geometry, L, d, nmax, encoding=:matrix,
                       basis_family=:complete, symmetry=PRIMARY_SYMMETRY)
        L >= 1 || throw(ArgumentError("L must be at least one"))
        d >= 1 || throw(ArgumentError("d must be positive"))
        nmax in 1:3 || throw(ArgumentError("certified coefficient field supports nmax=1,2,3"))
        enc = Symbol(lowercase(String(encoding)))
        enc in (:matrix,:ladder) || throw(ArgumentError("unknown encoding $encoding"))
        family = Symbol(lowercase(String(basis_family)))
        family in (:complete,:ts2) || throw(ArgumentError("basis_family must be complete or TS2"))
        sym = Symbol(uppercase(String(symmetry)))
        sym in (PRIMARY_SYMMETRY,UNRESTRICTED_SYMMETRY) ||
            throw(ArgumentError("unknown symmetry/state class $symmetry"))
        new(String(geometry), Int(L), Int(d), Int(nmax), enc, family, sym)
    end
end

struct ModelParams
    t::Q23
    U::Q23
    mu::Q23
    gamma::Q23
end

Base.:(==)(x::ModelParams,y::ModelParams) =
    x.t == y.t && x.U == y.U && x.mu == y.mu && x.gamma == y.gamma
Base.hash(x::ModelParams,h::UInt) = hash((x.t,x.U,x.mu,x.gamma),h)

_exact_parameter(x::Q23) = x
_exact_parameter(x::Integer) = Q23(x)
_exact_parameter(x::Rational) = Q23(x)
_exact_parameter(x::AbstractFloat) = Q23(rationalize(BigInt, x, tol=1e-12))
ModelParams(t::Real, U::Real, mu::Real, gamma::Real=0) =
    ModelParams(_exact_parameter(t), _exact_parameter(U), _exact_parameter(mu), _exact_parameter(gamma))

"""Finite induced rooted graph known through at least the requested radius."""
struct RootedGraph
    vertices::Vector{Int}
    edges::Vector{Tuple{Int,Int}}
    root::Int
    distance::Dict{Int,Int}
    geometry::String
    source::String
    known_radius::Union{Nothing,Int}
end

function RootedGraph(vertices, edges; root=0, geometry="unknown", source="unspecified",known_radius=nothing)
    verts = sort!(unique(Int.(collect(vertices))))
    Int(root) in verts || throw(ArgumentError("root is not a graph vertex"))
    edgevec = Tuple{Int,Int}[]
    adjacency = Dict(v => Int[] for v in verts)
    for edge in edges
        u, v = Int(edge[1]), Int(edge[2])
        u == v && continue
        haskey(adjacency,u) && haskey(adjacency,v) ||
            throw(ArgumentError("edge ($u,$v) has an unknown endpoint"))
        canonical = u < v ? (u,v) : (v,u)
        push!(edgevec, canonical)
        push!(adjacency[u],v)
        push!(adjacency[v],u)
    end
    sort!(unique!(edgevec))
    distances = Dict(Int(root) => 0)
    queue = [Int(root)]
    cursor = 1
    while cursor <= length(queue)
        u = queue[cursor]
        cursor += 1
        for v in adjacency[u]
            if !haskey(distances,v)
                distances[v] = distances[u] + 1
                push!(queue,v)
            end
        end
    end
    length(distances) == length(verts) || throw(ArgumentError("rooted graph must be connected"))
    radius = known_radius === nothing ? nothing : Int(known_radius)
    radius === nothing || radius >= 0 || throw(ArgumentError("known_radius must be nonnegative"))
    radius === nothing || maximum(values(distances)) >= radius ||
        throw(ArgumentError("declared known_radius=$radius exceeds the supplied graph"))
    RootedGraph(verts, edgevec, Int(root), distances, String(geometry), String(source),radius)
end

function graph_window(graph::RootedGraph, L::Int)
    graph.known_radius === nothing || graph.known_radius >= L ||
        throw(ArgumentError("graph $(graph.geometry) declares radius $(graph.known_radius), below requested L=$L"))
    maximum(values(graph.distance)) >= L ||
        throw(ArgumentError("graph $(graph.geometry) is not known through requested radius L=$L"))
    window = sort!([v for v in graph.vertices if graph.distance[v] <= L])
    interior = sort!([v for v in graph.vertices if graph.distance[v] <= L-1])
    selected = Set(window)
    edges = [edge for edge in graph.edges if edge[1] in selected && edge[2] in selected]
    window, interior, edges
end

function neighbors(graph::RootedGraph, vertex::Int; vertices=Set(graph.vertices))
    result = Int[]
    for (u,v) in graph.edges
        u == vertex && v in vertices && push!(result,v)
        v == vertex && u in vertices && push!(result,u)
    end
    sort!(result)
end

struct SolveRecord
    classification::Symbol
    raw_status::String
    solver::String
    runtime_seconds::Float64
    objective::Union{Nothing,Float64}
    primal_residual::Float64
    dual_residual::Float64
    min_psd_eigenvalue::Float64
    certificate_class::Symbol
    message::String
    primal::Dict{String,Any}
    dual::Dict{String,Any}
end

struct GapBracket
    lower::Float64
    upper::Float64
    tolerance::Float64
    records::Vector{SolveRecord}
    complete::Bool
    reason::String
end

struct CertificateReport
    classification::Symbol
    certificate_kind::Symbol
    projected::Bool
    psd_verified::Bool
    affine_verified::Bool
    margin_verified::Bool
    objective_gap_verified::Bool
    precision_bits::Int
    min_eigenvalue_lower::Float64
    max_affine_residual::Float64
    farkas_margin_lower::Float64
    certified_objective::Union{Nothing,Float64}
    normalized_objective_gap::Float64
    message::String
end
