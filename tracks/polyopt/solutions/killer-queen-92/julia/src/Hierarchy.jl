struct MatrixBlock
    kind::Symbol
    charge::Int
    basis::Vector{StateMonomial}
    entries::Matrix{MomentExpr}
    parent_indices::Vector{Int}
end

struct HierarchyTemplate
    spec::LevelSpec
    graph::RootedGraph
    window::Vector{Int}
    interior::Vector{Int}
    induced_edges::Vector{Tuple{Int,Int}}
    hamiltonian_degree::Int
    local_algebra::LocalBasisData
    ladder_degrees::Dict{LocalAtom,Int}
    hamiltonian::StatePoly
    moment_basis::Vector{StateMonomial}
    gap_basis::Vector{StateMonomial}
    stationarity_basis::Vector{StateMonomial}
    moment_blocks::Vector{MatrixBlock}
    gap_blocks::Vector{MatrixBlock}
    stationarity::Vector{MomentExpr}
    objectives::Dict{Symbol,MomentExpr}
    moment_keys::Vector{PureStateMonomial}
    metadata::Dict{String,Any}
    solver_cache::Dict{Tuple{Symbol,Bool},Any}
end

hamiltonian_degree(spec::LevelSpec) = spec.encoding == :matrix ? 2 : (spec.nmax == 1 ? 2 : 4)

function _word(site_atoms::Vector{NTuple{3,Int}})
    sort!(site_atoms; by=first)
    OperatorWord(site_atoms)
end

function _add_operator_term!(poly::StatePoly, word::OperatorWord, coefficient::ParamCoeff)
    _add_term!(poly,StateMonomial(PureStateMonomial(),word),coefficient)
end

function _add_raw_operator_term!(poly::StatePoly,word::OperatorWord,
                                 coefficient::ParamCoeff,basis::LocalBasisData)
    for (rebased,coordinate) in rebase_word(word,basis)
        _add_operator_term!(poly,rebased,coefficient*coordinate)
    end
end

function bose_hubbard_hamiltonian(spec::LevelSpec,window,edges,
                                  basis::LocalBasisData=local_basis_data(spec.nmax,spec.encoding))
    h = StatePoly()
    for site in window, r in 1:spec.nmax
        onsite = PARAM_U*aq(Q23(r*(r-1)//2)) - PARAM_MU*aq(Q23(r))
        _add_raw_operator_term!(h,OperatorWord([(site,r,r)]),onsite,basis)
    end
    for (i,j) in edges, r in 1:spec.nmax, s in 1:spec.nmax
        amplitude = _sqrt_occupation(r)*_sqrt_occupation(s)
        forward = _word([(i,r,r-1),(j,s-1,s)])
        backward = _word([(i,r-1,r),(j,s,s-1)])
        coefficient = -PARAM_T*aq(amplitude)
        _add_raw_operator_term!(h,forward,coefficient,basis)
        _add_raw_operator_term!(h,backward,coefficient,basis)
    end
    h
end

function _moment_entry(s::StateMonomial,t::StateMonomial,spec::LevelSpec,
                       basis::LocalBasisData=local_basis_data(spec.nmax,spec.encoding))
    product = multiply_poly(adjoint_poly(monomial_poly(s)),monomial_poly(t),basis)
    varsigma_poly(product,spec.symmetry)
end

function _commutator(left::StatePoly,right::StatePoly,basis::LocalBasisData)
    add_poly(multiply_poly(left,right,basis),multiply_poly(right,left,basis); scale=ParamCoeff(-1))
end

function _gap_entry(s::StateMonomial,t::StateMonomial,h::StatePoly,spec::LevelSpec,
                    basis::LocalBasisData=local_basis_data(spec.nmax,spec.encoding))
    sp = adjoint_poly(monomial_poly(s))
    tp = monomial_poly(t)
    ht = _commutator(h,tp,basis)
    hs = _commutator(h,sp,basis)
    energy = add_poly(multiply_poly(sp,ht,basis),multiply_poly(hs,tp,basis); scale=ParamCoeff(-1))
    result = scale_expr(varsigma_poly(energy,spec.symmetry),ParamCoeff(Q23(1//2)))
    moment = _moment_entry(s,t,spec,basis)
    covariance_product = pure_product_expr(adjoint(s),t,spec.symmetry)
    result = add_expr(result,moment; scale=-PARAM_GAMMA)
    add_expr(result,covariance_product; scale=PARAM_GAMMA)
end

function _stationarity_entry(w::StateMonomial,h::StatePoly,spec::LevelSpec,
                             basis::LocalBasisData=local_basis_data(spec.nmax,spec.encoding))
    varsigma_poly(_commutator(h,monomial_poly(w),basis),spec.symmetry)
end

function _charge_groups(basis::Vector{StateMonomial},symmetry::Symbol)
    if symmetry == UNRESTRICTED_SYMMETRY
        return [(0,collect(eachindex(basis)))]
    end
    groups = Dict{Int,Vector{Int}}()
    for (index,monomial) in enumerate(basis)
        push!(get!(groups,charge(monomial),Int[]),index)
    end
    [(q,groups[q]) for q in sort!(collect(keys(groups)))]
end

function _dense_blocks(kind::Symbol,statebasis::Vector{StateMonomial},spec::LevelSpec,h::StatePoly,
                       algebra::LocalBasisData)
    blocks = MatrixBlock[]
    for (q,indices) in _charge_groups(statebasis,spec.symmetry)
        localbasis = statebasis[indices]
        entries = Matrix{MomentExpr}(undef,length(indices),length(indices))
        for i in eachindex(localbasis), j in eachindex(localbasis)
            entries[i,j] = kind == :moment ? _moment_entry(localbasis[i],localbasis[j],spec,algebra) :
                                             _gap_entry(localbasis[i],localbasis[j],h,spec,algebra)
        end
        push!(blocks,MatrixBlock(kind,q,localbasis,entries,indices))
    end
    blocks
end

_block_entry(kind,s,t,spec,h,algebra) = kind == :moment ?
    _moment_entry(s,t,spec,algebra) : _gap_entry(s,t,h,spec,algebra)

_expr_support(expr::MomentExpr) = Set(keys(expr))

function _hierarchy_progress(message)
    get(ENV,"ISSUE92_BUILD_PROGRESS","0") == "1" || return
    println("hierarchy progress: ",message)
    flush(stdout)
end

function _maximal_chordal_cliques(adjacency::BitMatrix)
    n = size(adjacency,1)
    work = copy(adjacency)
    active = trues(n)
    # Degrees include the diagonal, exactly as the former Set/count
    # implementation did.  Maintaining them across fill and elimination
    # removes an O(n^3) repeated full-graph scan from large TS2 assemblies.
    degrees = [count(work[vertex,u] for u in 1:n) for vertex in 1:n]
    candidates = Vector{Vector{Int}}()
    for _ in 1:n
        # Select the current minimum active degree with the vertex index as a
        # deterministic tie-breaker.  This is the same ordering rule as the
        # previous implementation, but each selection is O(n), not O(n^2).
        vertex = 0
        vertex_key = (typemax(Int),typemax(Int))
        for candidate in 1:n
            active[candidate] || continue
            candidate_key = (degrees[candidate],candidate)
            if candidate_key < vertex_key
                vertex = candidate
                vertex_key = candidate_key
            end
        end
        vertex == 0 && break
        nbrs = [u for u in 1:n if active[u] && u != vertex && work[vertex,u]]
        push!(candidates,sort!([vertex;nbrs]))
        for i in eachindex(nbrs), j in i+1:length(nbrs)
            left,right = nbrs[i],nbrs[j]
            work[left,right] && continue
            work[left,right] = true
            work[right,left] = true
            degrees[left] += 1
            degrees[right] += 1
        end
        active[vertex] = false
        for neighbor in nbrs
            degrees[neighbor] -= 1
        end
        degrees[vertex] = 0
    end
    unique!(candidates)
    candidate_sets = BitSet.(candidates)
    [
        candidates[index]
        for index in eachindex(candidates)
        if !any(
            length(candidates[index]) < length(candidates[other]) &&
            issubset(candidate_sets[index],candidate_sets[other])
            for other in eachindex(candidates)
        )
    ]
end

"""Two deterministic support/chordal closure iterations, retaining all lower edges."""
function term_sparsity_cliques(block::MatrixBlock,seed::Set{PureStateMonomial}; iterations=2)
    n = length(block.basis)
    adjacency = falses(n,n)
    for i in 1:n
        adjacency[i,i] = true
    end
    active_support = copy(seed)
    cliques = [[i] for i in 1:n]
    for _ in 1:iterations
        for i in 1:n, j in i:n
            !isempty(intersect(_expr_support(block.entries[i,j]),active_support)) || continue
            adjacency[i,j] = adjacency[j,i] = true
        end
        cliques = _maximal_chordal_cliques(adjacency)
        for clique in cliques, i in clique, j in clique
            union!(active_support,_expr_support(block.entries[i,j]))
            adjacency[i,j] = adjacency[j,i] = true
        end
    end
    sort!(cliques; by=c->(first(c),length(c),Tuple(c)))
end

function _sparsify_blocks(blocks::Vector{MatrixBlock},seed::Set{PureStateMonomial})
    result = MatrixBlock[]
    for block in blocks
        for clique in term_sparsity_cliques(block,seed;iterations=2)
            push!(result,MatrixBlock(block.kind,block.charge,block.basis[clique],
                                     block.entries[clique,clique],block.parent_indices[clique]))
        end
    end
    result
end

function _term_sparsity_cliques_lazy(kind,localbasis,seed,spec,h,algebra;iterations=2)
    n = length(localbasis)
    adjacency = falses(n,n)
    for i in 1:n
        adjacency[i,i] = true
    end
    active_support = copy(seed)
    # Retain supports only for graph edges (including chordal fill edges), not
    # for every O(n^2) candidate pair.  This avoids the dense-parent memory
    # failure while also preventing repeated algebra for embedded lower-level
    # edges during the second support-closure iteration.
    edge_support = Dict{Tuple{Int,Int},Set{PureStateMonomial}}()
    pair(i,j) = i <= j ? (i,j) : (j,i)
    entry_support(i,j) = _expr_support(_block_entry(kind,localbasis[i],localbasis[j],spec,h,algebra))
    cliques = [[i] for i in 1:n]
    for iteration in 1:iterations
        # Entry algebra is independent for every candidate pair while
        # `active_support` and `adjacency` are fixed.  Compute rows in parallel,
        # then merge in lexicographic (i,j) order to keep the support graph and
        # every downstream clique exactly deterministic.
        candidate_rows = Vector{Vector{Tuple{Int,Set{PureStateMonomial}}}}(undef,n)
        scan_row(i) = begin
            row = Tuple{Int,Set{PureStateMonomial}}[]
            for j in i:n
                adjacency[i,j] && continue
                support = entry_support(i,j)
                any(item->item in active_support,support) || continue
                push!(row,(j,support))
            end
            row
        end
        _hierarchy_progress("$(kind) support closure $(iteration)/$(iterations), basis $(n)")
        if Threads.nthreads() > 1 && n >= 32
            # Interleave rows across threads.  Contiguous static chunks are
            # badly imbalanced for an upper triangle because early rows have
            # O(n) candidates while the final rows have only a few.
            thread_count = min(Threads.nthreads(),n)
            Threads.@threads :static for slot in 1:thread_count
                for i in slot:thread_count:n
                    candidate_rows[i] = scan_row(i)
                end
            end
        else
            for i in 1:n
                candidate_rows[i] = scan_row(i)
            end
        end
        for i in 1:n,(j,support) in candidate_rows[i]
            adjacency[i,j] = adjacency[j,i] = true
            edge_support[(i,j)] = support
        end
        cliques = _maximal_chordal_cliques(adjacency)
        for clique in cliques,i in clique,j in clique
            key = pair(i,j)
            support = get!(edge_support,key) do
                entry_support(key...)
            end
            union!(active_support,support)
            adjacency[i,j] = adjacency[j,i] = true
        end
        _hierarchy_progress(
            "$(kind) support closure $(iteration)/$(iterations) complete: " *
            "$(length(cliques)) cliques, $(length(edge_support)) retained pairs",
        )
    end
    sort!(cliques;by=c->(first(c),length(c),Tuple(c)))
end

"""Build only final TS2 clique entries; never retain a dense parent block."""
function _term_sparse_blocks(kind,basis,spec,h,seed,algebra)
    result = MatrixBlock[]
    for (q,indices) in _charge_groups(basis,spec.symmetry)
        localbasis = basis[indices]
        _hierarchy_progress("TS2 $(kind) charge $(q): $(length(localbasis)) basis elements")
        cliques = _term_sparsity_cliques_lazy(kind,localbasis,seed,spec,h,algebra;iterations=2)
        blocks = Vector{MatrixBlock}(undef,length(cliques))
        build_block(index) = begin
            clique = cliques[index]
            entries = Matrix{MomentExpr}(undef,length(clique),length(clique))
            for i in eachindex(clique),j in eachindex(clique)
                entries[i,j] = _block_entry(kind,localbasis[clique[i]],localbasis[clique[j]],spec,h,algebra)
            end
            MatrixBlock(kind,q,localbasis[clique],entries,indices[clique])
        end
        # Every clique owns its matrix and the algebra inputs are read-only.
        # Interleaved static lanes balance differently sized cliques while the
        # indexed output vector preserves the exact deterministic clique order.
        if Threads.nthreads() > 1 && length(cliques) >= 32
            thread_count = min(Threads.nthreads(),length(cliques))
            _hierarchy_progress(
                "TS2 $(kind) charge $(q): materializing $(length(cliques)) blocks on $(thread_count) threads",
            )
            Threads.@threads :static for slot in 1:thread_count
                for index in slot:thread_count:length(cliques)
                    blocks[index] = build_block(index)
                end
            end
        else
            for index in eachindex(cliques)
                blocks[index] = build_block(index)
            end
        end
        append!(result,blocks)
        _hierarchy_progress("TS2 $(kind) charge $(q): built $(length(cliques)) blocks")
    end
    result
end

function _operator_observables(spec::LevelSpec,graph::RootedGraph,window,
                               basis::LocalBasisData)
    rho = StatePoly()
    fluctuation = StatePoly(StateMonomial()=>ParamCoeff(1))
    for r in 1:spec.nmax
        word = OperatorWord([(graph.root,r,r)])
        _add_raw_operator_term!(rho,word,ParamCoeff(Q23(r)),basis)
        _add_raw_operator_term!(fluctuation,word,ParamCoeff(Q23(r*r-2r)),basis)
    end
    windowset = Set(window)
    root_neighbors = neighbors(graph,graph.root;vertices=windowset)
    isempty(root_neighbors) && throw(ArgumentError("root has no neighbours in Lambda(L)"))
    hopping = StatePoly()
    z = length(root_neighbors)
    for j in root_neighbors, r in 1:spec.nmax, s in 1:spec.nmax
        amplitude = _sqrt_occupation(r)*_sqrt_occupation(s)/Q23(z)
        _add_raw_operator_term!(hopping,_word([(graph.root,r,r-1),(j,s-1,s)]),ParamCoeff(amplitude),basis)
        _add_raw_operator_term!(hopping,_word([(graph.root,r-1,r),(j,s,s-1)]),ParamCoeff(amplitude),basis)
    end
    Dict(:rho0=>rho,:F0=>fluctuation,:K0=>hopping)
end

function _collect_moment_keys(blocks,stationarity,objectives)
    keys_set = Set{PureStateMonomial}([PureStateMonomial()])
    for block in blocks, entry in block.entries
        union!(keys_set,keys(entry))
    end
    for entry in stationarity
        union!(keys_set,keys(entry))
    end
    for entry in values(objectives)
        union!(keys_set,keys(entry))
    end
    sort!(collect(keys_set))
end

function _term_sparsity_seed(moment_basis,gap_basis,h,spec,stationarity,objectives,
                             algebra::LocalBasisData=local_basis_data(spec.nmax,spec.encoding))
    seed = Set{PureStateMonomial}([PureStateMonomial()])
    union!(seed,keys(varsigma_poly(h,spec.symmetry)))
    for expression in stationarity
        union!(seed,keys(expression))
    end
    for expression in values(objectives)
        union!(seed,keys(expression))
    end
    for monomial in moment_basis
        union!(seed,keys(_moment_entry(monomial,monomial,spec,algebra)))
    end
    for (_,indices) in _charge_groups(gap_basis,spec.symmetry), index in indices
        union!(seed,keys(_gap_entry(gap_basis[index],gap_basis[index],h,spec,algebra)))
    end
    seed
end

function _memory_estimate_gb(moment_blocks,gap_blocks)
    blocks = [moment_blocks;gap_blocks]
    cone_entries = sum((2length(b.basis))^2 for b in blocks;init=0)
    affine_terms = sum(length(entry) for b in blocks for entry in b.entries;init=0)
    unique_moments = Set{PureStateMonomial}()
    for b in blocks, entry in b.entries
        union!(unique_moments,keys(entry))
    end
    # A conservative structural estimate: affine storage, real cone matrices,
    # and a dense moment-variable Schur proxy, all with an 8x solver/workspace
    # factor plus a 0.5-GiB runtime baseline.  SCNet dry runs must still record
    # actual MaxRSS before the nmax=3 gate is accepted.
    bytes = 8*(64affine_terms + 16cone_entries + 8length(unique_moments)^2)
    0.5 + bytes/1024^3
end

function build_level(spec::LevelSpec,graph::RootedGraph)
    graph.geometry == "unknown" || graph.geometry == spec.geometry ||
        throw(ArgumentError("LevelSpec geometry $(spec.geometry) does not match graph $(graph.geometry)"))
    window,interior,edges = graph_window(graph,spec.L)
    algebra = local_basis_data(spec.nmax,spec.encoding)
    ladder = spec.encoding == :ladder ? copy(algebra.degrees) : ladder_degrees(spec.nmax)
    hdegree = hamiltonian_degree(spec)
    2spec.d >= hdegree || throw(ArgumentError("level requires 2d >= deg(H)"))
    h = bose_hubbard_hamiltonian(spec,window,edges,algebra)
    moment_basis = state_basis(window,spec.d,spec.nmax,spec.encoding,ladder,spec.symmetry)
    stationarity_degree = 2spec.d-hdegree
    gap_degree = spec.d-cld(hdegree,2)
    stationarity_basis = state_basis(interior,stationarity_degree,spec.nmax,spec.encoding,ladder,spec.symmetry)
    gap_basis = state_basis(interior,gap_degree,spec.nmax,spec.encoding,ladder,spec.symmetry)
    stationarity = [_stationarity_entry(w,h,spec,algebra) for w in stationarity_basis]
    operator_objectives = _operator_observables(spec,graph,window,algebra)
    objectives = Dict(name=>varsigma_poly(poly,spec.symmetry) for (name,poly) in operator_objectives)
    if spec.basis_family == :ts2
        seed = _term_sparsity_seed(moment_basis,gap_basis,h,spec,stationarity,objectives,algebra)
        moment_blocks = _term_sparse_blocks(:moment,moment_basis,spec,h,seed,algebra)
        gap_blocks = _term_sparse_blocks(:gap,gap_basis,spec,h,seed,algebra)
    else
        moment_blocks = _dense_blocks(:moment,moment_basis,spec,h,algebra)
        gap_blocks = _dense_blocks(:gap,gap_basis,spec,h,algebra)
    end
    moment_keys = _collect_moment_keys([moment_blocks;gap_blocks],stationarity,objectives)
    orbit = _moment_orbits(moment_keys)
    equality_count = 1
    for expression in stationarity
        realrow,imagrow = _expr_parametric_coefficients(expression,orbit)
        equality_count += !isempty(realrow)+!isempty(imagrow)
    end
    allblocks = [moment_blocks;gap_blocks]
    real_psd_block_sizes = 2 .* length.(getfield.(allblocks,:basis))
    certificate_coordinate_count = equality_count+sum(
        size*(size+1)÷2 for size in real_psd_block_sizes;init=0,
    )
    metadata = Dict{String,Any}(
        "geometry"=>spec.geometry,"L"=>spec.L,"d"=>spec.d,"nmax"=>spec.nmax,
        "graph_source"=>graph.source,"graph_known_radius"=>graph.known_radius,
        "encoding"=>String(spec.encoding),"basis_family"=>uppercase(String(spec.basis_family)),
        "local_basis_convention"=>(spec.encoding == :matrix ?
            "independent matrix units" : "exact charge-adapted graded ladder-word combinations"),
        "local_basis_degrees"=>Dict("$(atom.r),$(atom.s)"=>algebra.degrees[atom] for atom in algebra.atoms),
        "symmetry"=>String(spec.symmetry),"window_sites"=>length(window),
        "interior_sites"=>length(interior),"induced_edges"=>length(edges),
        "hamiltonian_degree"=>hdegree,"moment_basis_count"=>length(moment_basis),
        "gap_basis_count"=>length(gap_basis),"stationarity_basis_count"=>length(stationarity_basis),
        "normalization_count"=>1,"stationarity_expression_count"=>length(stationarity),
        "equality_count"=>equality_count,
        "moment_block_sizes"=>length.(getfield.(moment_blocks,:basis)),
        "gap_block_sizes"=>length.(getfield.(gap_blocks,:basis)),
        "moment_block_charges"=>getfield.(moment_blocks,:charge),
        "gap_block_charges"=>getfield.(gap_blocks,:charge),
        "moment_psd_block_count"=>length(moment_blocks),
        "gap_psd_block_count"=>length(gap_blocks),
        "real_psd_block_sizes"=>real_psd_block_sizes,
        "certificate_coordinate_count"=>certificate_coordinate_count,
        "moment_variable_count"=>length(moment_keys),
        "real_scalar_variable_count"=>_nvariables(orbit),
        "support_convention"=>"Lambda_G(L) induced Hamiltonian; excitation/stationarity interior Lambda_G(L-1)",
        "affine_term_count"=>sum(length(entry) for b in [moment_blocks;gap_blocks] for entry in b.entries;init=0),
        "estimated_memory_gb"=>_memory_estimate_gb(moment_blocks,gap_blocks),
    )
    HierarchyTemplate(spec,graph,window,interior,edges,hdegree,algebra,ladder,h,moment_basis,gap_basis,
                      stationarity_basis,moment_blocks,gap_blocks,stationarity,objectives,moment_keys,
                      metadata,Dict{Tuple{Symbol,Bool},Any}())
end

function level_fingerprint(template::HierarchyTemplate)
    (template.window,template.interior,template.induced_edges,
     length(template.moment_basis),length(template.gap_basis),
     sort!(collect(keys(template.hamiltonian))))
end
