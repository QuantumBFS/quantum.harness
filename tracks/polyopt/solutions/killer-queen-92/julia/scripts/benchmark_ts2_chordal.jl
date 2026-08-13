using QuantumGapHierarchy

function reference_cliques(adjacency::BitMatrix)
    n = size(adjacency,1)
    work = copy(adjacency)
    remaining = Set(1:n)
    candidates = Vector{Vector{Int}}()
    while !isempty(remaining)
        vertex = first(remaining)
        vertex_key = (count(u->u in remaining && work[vertex,u],1:n),vertex)
        for candidate in remaining
            candidate_key = (count(u->u in remaining && work[candidate,u],1:n),candidate)
            if candidate_key < vertex_key
                vertex = candidate
                vertex_key = candidate_key
            end
        end
        neighbours = sort!([u for u in remaining if u != vertex && work[vertex,u]])
        push!(candidates,sort!([vertex;neighbours]))
        for i in eachindex(neighbours),j in i+1:length(neighbours)
            work[neighbours[i],neighbours[j]] = true
            work[neighbours[j],neighbours[i]] = true
        end
        delete!(remaining,vertex)
    end
    unique!(candidates)
    [
        clique for clique in candidates
        if !any(other != clique && issubset(Set(clique),Set(other)) for other in candidates)
    ]
end

function deterministic_adjacency(n)
    adjacency = falses(n,n)
    for i in 1:n
        adjacency[i,i] = true
        for j in i+1:n
            if (7i+11j+3n) % 31 in (0,1,4)
                adjacency[i,j] = adjacency[j,i] = true
            end
        end
    end
    adjacency
end

n = isempty(ARGS) ? 220 : parse(Int,ARGS[1])
n >= 0 || error("matrix size must be nonnegative")
adjacency = deterministic_adjacency(n)

# Warm both methods on a bounded prefix so compilation does not dominate the
# reported kernel timing.
warm = adjacency[1:min(n,32),1:min(n,32)]
reference_cliques(warm)
QuantumGapHierarchy._maximal_chordal_cliques(warm)

reference_seconds = @elapsed expected = reference_cliques(adjacency)
incremental_seconds = @elapsed observed =
    QuantumGapHierarchy._maximal_chordal_cliques(adjacency)
expected == observed || error("incremental closure changed the deterministic clique sequence")

println("vertices=",n)
println("cliques=",length(observed))
println("reference_seconds=",reference_seconds)
println("incremental_seconds=",incremental_seconds)
println("speedup=",reference_seconds/incremental_seconds)
