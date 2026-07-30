using Test
using LinearAlgebra
using JSON3
using QuantumGapHierarchy

@testset "exact Q(sqrt2,sqrt3) arithmetic" begin
    @test SQRT2*SQRT2 == Q23(2)
    @test SQRT3*SQRT3 == Q23(3)
    @test inv(Q23(1)+SQRT2)*(Q23(1)+SQRT2) == Q23(1)
end

@testset "sparse exact certificate projection" begin
    columns = [
        Dict(1=>Q23(1)),
        Dict(1=>Q23(1),2=>Q23(1)),
        Dict(2=>Q23(1),3=>Q23(1)),
        Dict(3=>Q23(2)),
    ]
    rhs = Q23[3,4,5]
    correction = QuantumGapHierarchy._solve_exact_sparse_columns(columns,rhs)
    @test correction !== nothing
    values = fill(Q23(0),length(columns))
    for (index,value) in correction
        values[index] = value
    end
    @test QuantumGapHierarchy._matvec(columns,values,length(rhs))==rhs

    margin_preserving = QuantumGapHierarchy._solve_exact_sparse_columns(
        columns,rhs;excluded=Set([1]),
    )
    @test margin_preserving !== nothing
    @test !haskey(margin_preserving,1)
    inconsistent = QuantumGapHierarchy._solve_exact_sparse_columns(
        [Dict(1=>Q23(1))],Q23[0,1],
    )
    @test inconsistent === nothing
    psd_ok,psd_lower = QuantumGapHierarchy._exact_psd(Q23[1 1; 1 1])
    @test psd_ok
    @test psd_lower == 0.0
    @test !first(QuantumGapHierarchy._exact_psd(Q23[1 2; 2 1]))
    @test first(QuantumGapHierarchy._exact_psd(fill(Q23(0),3,3)))
    @test !first(QuantumGapHierarchy._exact_psd(Q23[0 1; 1 0]))
    rectangular = Q23[1 0 1 2; 0 1 1 -1; 1 1 2 1]
    singular_psd = transpose(rectangular)*rectangular
    @test first(QuantumGapHierarchy._exact_psd(singular_psd))
    singular_psd[4,4] -= Q23(20)
    @test !first(QuantumGapHierarchy._exact_psd(singular_psd))
    @test QuantumGapHierarchy._arb_strictly_positive_definite(Q23[2 1; 1 2])
    @test !QuantumGapHierarchy._arb_strictly_positive_definite(Q23[1 1; 1 1])
    @test !QuantumGapHierarchy._arb_strictly_positive_definite(Q23[1 2; 2 1])
    @test QuantumGapHierarchy._exact_negative_witness(Q23[1 2; 2 1])
    @test !QuantumGapHierarchy._exact_negative_witness(Q23[1 1; 1 1])
end

@testset "pinned NCTSSoS unipotent moment-matrix cross-check" begin
    # QuantumSOS/NCTSSoS.jl@5b355f1 records dense order-one oracles
    # side=2,nuniq=2 and side=3,nuniq=4 for one/two unipotent generators in
    # test/data/expectations/relaxations_sparsity.toml.  At nmax=1 the exact
    # projector P=E11 is affinely equivalent to a unipotent generator through
    # u=1-2P, so the moment matrices must have the same structural counts.
    spec = LevelSpec("nctssos-toy",1,1,1,:matrix,:complete,PRIMARY_SYMMETRY)
    algebra = local_basis_data(1,:matrix)
    identity = StateMonomial()
    projector(site) = StateMonomial(
        PureStateMonomial(),OperatorWord([(site,1,1)]),
    )
    function moment_entries(basis)
        [QuantumGapHierarchy._moment_entry(left,right,spec,algebra)
         for left in basis,right in basis]
    end
    function unique_keys(entries)
        result = Set{PureStateMonomial}()
        for entry in entries
            union!(result,keys(entry))
        end
        result
    end

    p1 = projector(1)
    one_generator = moment_entries([identity,p1])
    @test size(one_generator) == (2,2)
    @test length(unique_keys(one_generator)) == 2
    @test one_generator[2,2] == one_generator[1,2] # P^2=P exactly

    p2 = projector(2)
    two_generators = moment_entries([identity,p1,p2])
    @test size(two_generators) == (3,3)
    @test length(unique_keys(two_generators)) == 4
    @test two_generators == permutedims(two_generators)
end

@testset "JSON-safe records and resumable gap state machine" begin
    params = ModelParams(3//100,1,1//2,0)
    raw = SolveRecord(
        :UNKNOWN,"TEST","test",0.0,nothing,NaN,NaN,NaN,:NO_CERTIFICATE,"test",
        Dict("params"=>params,"moments"=>[1.0,0.5]),
        Dict("available"=>true,"psd_matrices"=>[[1.0 0.0; 0.0 1.0]]),
    )
    payload = QuantumGapHierarchy._record_dict(raw)
    @test payload["primal_residual"] === nothing
    @test payload["dual_data"]["psd_matrices"][1]["shape"] == [2,2]
    @test JSON3.read(JSON3.write(payload)).gamma == 0.0

    graph = RootedGraph([0,1],[(0,1)];root=0,geometry="resume-test",source="test")
    template = build_level(LevelSpec("resume-test",1,1,1,:matrix,:complete,PRIMARY_SYMMETRY),graph)
    calls = Ref(0)
    fake_solver = function (trial_params)
        calls[] += 1
        classification = Float64(trial_params.gamma) <= 0.5 ? :FEASIBLE : :EXCLUDED
        SolveRecord(classification,"FAKE","fake",0.0,nothing,0.0,0.0,0.0,
                    classification == :FEASIBLE ? :PRIMAL_CHECKED : :VERIFIED_EXACT_PROJECTED,
                    "fake",Dict("params"=>trial_params),Dict{String,Any}())
    end
    first = bisect_gap(template,params;tolerance=0.25,trial_solver=fake_solver)
    @test first.complete
    @test (first.lower,first.upper) == (0.5,0.75)
    @test calls[] == 4

    calls[] = 0
    checkpoints = Ref(0)
    resumed = bisect_gap(
        template,params;tolerance=0.25,trial_solver=fake_solver,
        resume_records=first.records[1:2],checkpoint=(bracket,record)->(checkpoints[] += 1),
    )
    @test (resumed.lower,resumed.upper) == (first.lower,first.upper)
    @test calls[] == 2
    @test checkpoints[] == 2

    unknown_calls = Ref(0)
    unknown_solver = function (trial_params)
        unknown_calls[] += 1
        classification = iszero(trial_params.gamma) ? :FEASIBLE : :UNKNOWN
        SolveRecord(classification,"FAKE","fake",0.0,nothing,0.0,0.0,0.0,
                    :NO_CERTIFICATE,"fake",Dict("params"=>trial_params),Dict{String,Any}())
    end
    unknown = bisect_gap(template,params;tolerance=0.25,trial_solver=unknown_solver)
    @test !unknown.complete
    @test (unknown.lower,unknown.upper) == (0.0,1.0)
    @test unknown_calls[] == 2
end

@testset "cutoff algebra, adjoint, charge, and filtrations" begin
    for nmax in 1:3
        b,bd = ladder_matrices(nmax)
        identity_matrix = Matrix{Q23}(I,nmax+1,nmax+1)
        top = fill(Q23(0),nmax+1,nmax+1)
        top[end,end] = Q23(nmax+1)
        @test b*bd-bd*b == identity_matrix-top
        filtration = ladder_degrees(nmax)
        @test length(filtration)==(nmax+1)^2-1
        @test all(value>=1 for value in values(filtration))
        @test hamiltonian_degree(LevelSpec("toy",1,2,nmax,:matrix))==2
        @test hamiltonian_degree(LevelSpec("toy",1,nmax==1 ? 2 : 3,nmax,:ladder))==(nmax==1 ? 2 : 4)

        adapted = local_basis_data(nmax,:ladder)
        @test adapted.degrees == filtration
        @test length(adapted.matrices) == (nmax+1)^2-1

        expansion_matrix = function (expansion)
            result = fill(Q23(0),nmax+1,nmax+1)
            for (atom,coefficient) in expansion
                direction = atom === nothing ? identity_matrix : adapted.matrices[atom]
                result .+= coefficient .* direction
            end
            result
        end
        for atom in adapted.atoms
            matrix = adapted.matrices[atom]
            @test adapted.matrices[adjoint(atom)] == permutedims(matrix)
            @test all(iszero(matrix[row,column]) || row-column == charge(atom)
                      for row in axes(matrix,1),column in axes(matrix,2))
            @test expansion_matrix(adapted.raw_expansions[atom]) ==
                  QuantumGapHierarchy._matrix_unit(nmax,atom)
        end
        for left in adapted.atoms,right in adapted.atoms
            @test expansion_matrix(adapted.products[(left,right)]) ==
                  QuantumGapHierarchy._matmul(adapted.matrices[left],adapted.matrices[right])
        end

        # At every degree, selected basis directions span exactly all ladder
        # words of length at most that degree.
        word_rows = [QuantumGapHierarchy._flatten(identity_matrix)]
        frontier = [identity_matrix]
        for filtered_degree in 0:maximum(values(filtration))
            if filtered_degree > 0
                frontier = [QuantumGapHierarchy._matmul(word,generator)
                            for word in frontier for generator in (b,bd)]
                append!(word_rows,QuantumGapHierarchy._flatten(word) for word in frontier)
            end
            basis_rows = [QuantumGapHierarchy._flatten(identity_matrix)]
            append!(basis_rows,QuantumGapHierarchy._flatten(adapted.matrices[atom])
                    for atom in adapted.atoms if adapted.degrees[atom] <= filtered_degree)
            @test QuantumGapHierarchy._row_rank(word_rows) ==
                  QuantumGapHierarchy._row_rank(basis_rows)
        end
        if nmax >= 2
            @test any(count(value->!iszero(value),adapted.matrices[atom]) > 1
                      for atom in adapted.atoms if adapted.degrees[atom] == 1)
        end
    end
    word = OperatorWord([(0,0,1),(2,2,0)])
    @test charge(word)==1
    @test adjoint(adjoint(word))==word
    expansion = multiply_words(OperatorWord([(0,0,1)]),OperatorWord([(0,1,0)]),1)
    @test expansion[OperatorWord()]==complex(Q23(1),Q23(0))
    @test expansion[OperatorWord([(0,1,1)])]==complex(Q23(-1),Q23(0))
end

@testset "complete state-polynomial bases" begin
    ladder = ladder_degrees(1)
    operators = operator_basis([0],1,1,:matrix,ladder)
    @test length(operators)==4
    basis = state_basis([0],1,1,:matrix,ladder,PRIMARY_SYMMETRY)
    @test length(basis)==5
    @test basis==sort(unique(basis);by=m->(degree(m,:matrix,ladder),charge(m),m))
    larger = state_basis([0,1],2,1,:matrix,ladder,PRIMARY_SYMMETRY)
    @test all(item in larger for item in basis)

    adapted = ladder_degrees(2)
    ladder_basis_d3 = state_basis([0],3,2,:ladder,adapted,PRIMARY_SYMMETRY)
    ladder_basis_d4 = Set(state_basis([0],4,2,:ladder,adapted,PRIMARY_SYMMETRY))
    @test all(adjoint(item) in ladder_basis_d4 for item in ladder_basis_d3)
    @test all(item in ladder_basis_d4 for item in ladder_basis_d3)
    @test length(operator_basis([0],1,2,:ladder,adapted)) == 3 # 1, b, bdag
end

function path_graph(radius)
    vertices = collect(-radius:radius)
    edges = [(i,i+1) for i in -radius:radius-1]
    RootedGraph(vertices,edges;root=0,geometry="path",source="test")
end

@testset "windows, interiors, and commutator buffer" begin
    graph = path_graph(3)
    window,interior,edges = graph_window(graph,2)
    @test window==collect(-2:2)
    @test interior==collect(-1:1)
    @test length(edges)==4
    larger_edges = graph_window(graph,3)[3]
    for site in interior
        @test Set(edge for edge in edges if site in edge)==Set(edge for edge in larger_edges if site in edge)
    end

    # A graph may contain diagnostic vertices beyond the radius certified by
    # its exporter, but hierarchy assembly must honor the declared boundary.
    certified = RootedGraph(
        graph.vertices,graph.edges;root=0,geometry="path",source="test",known_radius=2,
    )
    @test graph_window(certified,2)[1] == window
    @test_throws ArgumentError graph_window(certified,3)
    @test_throws ArgumentError RootedGraph(
        collect(-2:2),[(i,i+1) for i in -2:1];
        root=0,geometry="path",source="test",known_radius=3,
    )

    exported_path = normpath(joinpath(@__DIR__,"..","..","results","graphs","83-L2.json"))
    exported = read_graph_json(exported_path)
    @test exported.known_radius == 2
    @test exported.geometry == "83"
    @test all(length(neighbors(exported,vertex)) == 3
              for vertex in exported.vertices if exported.distance[vertex] < 2)
end

@testset "level assembly, charge blocks, and geometry sensitivity" begin
    graph = RootedGraph(0:2,[(0,1),(1,2)];root=0,geometry="toy",source="test")
    small = build_level(LevelSpec("toy",1,2,1,:matrix,:complete,PRIMARY_SYMMETRY),graph)
    @test small.window==[0,1]
    @test small.interior==[0]
    @test sum(length(block.basis) for block in small.moment_blocks)==length(small.moment_basis)
    @test Set(getfield.(small.moment_blocks,:charge))==Set(charge.(small.moment_basis))
    @test haskey(small.objectives,:rho0)
    @test small.metadata["certificate_coordinate_count"] ==
          small.metadata["equality_count"] + sum(
              size*(size+1)÷2 for size in small.metadata["real_psd_block_sizes"];init=0,
          )
    sparse = build_level(LevelSpec("toy",1,2,1,:matrix,:ts2,PRIMARY_SYMMETRY),graph)
    @test all(!isempty(block.parent_indices) for block in sparse.moment_blocks)
    @test Set(vcat(getfield.(sparse.moment_blocks,:parent_indices)...))==Set(eachindex(sparse.moment_basis))
    @test maximum(length.(getfield.(sparse.moment_blocks,:basis))) <=
          maximum(length.(getfield.(small.moment_blocks,:basis)))
    seed = QuantumGapHierarchy._term_sparsity_seed(
        sparse.moment_basis,sparse.gap_basis,sparse.hamiltonian,sparse.spec,
        sparse.stationarity,sparse.objectives,
    )
    @test all(
        issubset(keys(QuantumGapHierarchy._moment_entry(item,item,sparse.spec)),seed)
        for item in sparse.moment_basis
    )
    reference_moment = QuantumGapHierarchy._sparsify_blocks(small.moment_blocks,seed)
    reference_gap = QuantumGapHierarchy._sparsify_blocks(small.gap_blocks,seed)
    signature(blocks) = [(block.charge,block.parent_indices) for block in blocks]
    @test signature(sparse.moment_blocks)==signature(reference_moment)
    @test signature(sparse.gap_blocks)==signature(reference_gap)

    # Complete bases embed along the two production tightening directions.
    larger_window = state_basis([0,1,2],2,1,:matrix,small.ladder_degrees,PRIMARY_SYMMETRY)
    higher_degree = state_basis([0,1],3,1,:matrix,small.ladder_degrees,PRIMARY_SYMMETRY)
    @test all(item in larger_window for item in small.moment_basis)
    @test all(item in higher_degree for item in small.moment_basis)

    # The L=1 interaction buffer makes every root-supported gap entry equal to
    # the same entry assembled from the larger L=2 Hamiltonian.
    window2,_,edges2 = graph_window(graph,2)
    hamiltonian2 = QuantumGapHierarchy.bose_hubbard_hamiltonian(
        LevelSpec("toy",2,2,1,:matrix,:complete,PRIMARY_SYMMETRY),window2,edges2,
    )
    for left in small.gap_basis,right in small.gap_basis
        @test QuantumGapHierarchy._gap_entry(left,right,small.hamiltonian,small.spec) ==
              QuantumGapHierarchy._gap_entry(left,right,hamiltonian2,small.spec)
    end

    # The second support closure retains every edge of TS1.
    clique_edges(cliques) = Set(
        minmax(i,j) for clique in cliques for i in clique for j in clique
    )
    for block in small.moment_blocks
        ts1 = term_sparsity_cliques(block,seed;iterations=1)
        ts2 = term_sparsity_cliques(block,seed;iterations=2)
        @test issubset(clique_edges(ts1),clique_edges(ts2))
    end

    # Same coordination at the root, but the radius-one interiors have
    # different local connectivity at L=2.
    squarelike = RootedGraph(0:6,[(0,1),(0,2),(0,3),(0,4),(1,5),(2,6)];
                             root=0,geometry="g124-test",source="test")
    linelike = RootedGraph(0:6,[(0,1),(0,2),(0,3),(0,4),(1,2),(3,4),(1,5),(2,6)];
                           root=0,geometry="line-test",source="test")
    a = build_level(LevelSpec("g124-test",2,1,1,:matrix,:complete,PRIMARY_SYMMETRY),squarelike)
    b = build_level(LevelSpec("line-test",2,1,1,:matrix,:complete,PRIMARY_SYMMETRY),linelike)
    @test a.induced_edges != b.induced_edges
    @test level_fingerprint(a) != level_fingerprint(b)
end

@testset "incremental chordal closure matches the reference ordering" begin
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
            nbrs = sort!([u for u in remaining if u != vertex && work[vertex,u]])
            push!(candidates,sort!([vertex;nbrs]))
            for i in eachindex(nbrs),j in i+1:length(nbrs)
                work[nbrs[i],nbrs[j]] = true
                work[nbrs[j],nbrs[i]] = true
            end
            delete!(remaining,vertex)
        end
        unique!(candidates)
        [
            clique for clique in candidates
            if !any(other != clique && issubset(Set(clique),Set(other)) for other in candidates)
        ]
    end

    for n in 0:18
        adjacency = falses(n,n)
        for i in 1:n
            adjacency[i,i] = true
            for j in i+1:n
                if (7i+11j+3n) % 9 in (0,1,4)
                    adjacency[i,j] = adjacency[j,i] = true
                end
            end
        end
        @test QuantumGapHierarchy._maximal_chordal_cliques(adjacency) ==
              reference_cliques(adjacency)
    end
end

@testset "Clarabel primal checks and corrupted-certificate rejection" begin
    withenv("ISSUE92_CLARABEL_PROFILE"=>"deadline-balanced") do
        _,profile = QuantumGapHierarchy._make_optimizer(:clarabel,true)
        @test profile=="Clarabel[deadline-balanced]"
    end
    withenv(
        "ISSUE92_CLARABEL_PROFILE"=>"presentation-fast",
        "ISSUE92_CLARABEL_DIRECT_SOLVER"=>"mkl",
        "ISSUE92_CLARABEL_MAX_THREADS"=>"2",
    ) do
        _,profile = QuantumGapHierarchy._make_optimizer(:clarabel,true)
        @test profile=="Clarabel[presentation-fast;mkl,2t]"
    end
    graph = RootedGraph([0,1],[(0,1)];root=0,geometry="atomic-test",source="test")
    template = build_level(LevelSpec("atomic-test",1,2,1,:matrix,:complete,PRIMARY_SYMMETRY),graph)
    @test QuantumGapHierarchy.add_expr(template.objectives[:rho0],template.objectives[:F0]) ==
          QuantumGapHierarchy.MomentExpr(PureStateMonomial()=>QuantumGapHierarchy.ParamCoeff(1))
    feasible = solve_feasibility(template,ModelParams(0,1,1//2,49//100);solver=:clarabel)
    @test feasible.classification==:FEASIBLE
    @test feasible.primal_residual<=1e-6
    @test length(template.solver_cache)==1
    workspace = only(values(template.solver_cache))
    rho = solve_observable(template,ModelParams(0,1,1//2,0),:rho0,:min;solver=:clarabel)
    @test rho.classification==:FEASIBLE
    @test rho.objective !== nothing
    @test isapprox(rho.objective,1.0;atol=2e-5)
    @test rho.certificate_class==:PRIMAL_DUAL_CHECKED
    @test rho.dual_residual<=1e-6
    @test get(rho.dual,"available",false)
    rho_report = verify_certificate(template,rho)
    @test rho_report.classification==:VERIFIED_LOWER_BOUND
    @test rho_report.certificate_kind==:LOWER_BOUND
    @test rho_report.projected
    @test rho_report.psd_verified
    @test rho_report.affine_verified
    @test rho_report.objective_gap_verified
    @test 1-2e-6 <= rho_report.certified_objective <= 1
    @test abs(rho_report.normalized_objective_gap)<=1e-6
    rho_max = solve_observable(template,ModelParams(0,1,1//2,0),:rho0,:max;solver=:clarabel)
    @test rho_max.classification==:FEASIBLE
    @test isapprox(rho_max.objective,1.0;atol=2e-5)
    @test rho_max.certificate_class==:PRIMAL_DUAL_CHECKED
    @test rho_max.dual_residual<=1e-6
    rho_max_report = verify_certificate(template,rho_max)
    @test rho_max_report.classification==:VERIFIED_UPPER_BOUND
    @test rho_max_report.certificate_kind==:UPPER_BOUND
    @test rho_max_report.psd_verified
    @test rho_max_report.affine_verified
    @test rho_max_report.objective_gap_verified
    @test 1 <= rho_max_report.certified_objective <= 1+2e-6
    @test abs(rho_max_report.normalized_objective_gap)<=1e-6
    @test only(values(template.solver_cache)) === workspace
    @test workspace.solve_count==3
    @test workspace.parameter_update_count>=1
    @test workspace.params.gamma==Q23(0)
    feasible_report = verify_certificate(template,feasible)
    @test feasible_report.classification==:UNVERIFIED
    @test occursin("cannot be checked as an exclusion",feasible_report.message)

    corrupted = SolveRecord(:UNKNOWN,"INFEASIBLE","test",0.0,nothing,NaN,NaN,NaN,
                            :FLOATING_CANDIDATE,"corrupted",Dict("params"=>ModelParams(0,1,1//2,51//100)),
                            Dict("available"=>true,"equality_multipliers"=>[1.0],"psd_matrices"=>Matrix{Float64}[]))
    report = verify_certificate(template,corrupted)
    @test report.classification==:UNVERIFIED
end
