include(joinpath(@__DIR__, "..", "src", "ShastrySutherlandOracle.jl"))
using .ShastrySutherlandOracle

@testset "periodic interaction anchors" begin
    template = PauliInteractionTemplate(
        [Site(0, 0), Site(1, 1)],
        [:X, :X],
        1//4,
        :test;
        anchor_period=Site(2, 2),
        anchor_residues=[Site(0, 1), Site(2, -1)],
    )
    @test template.anchor_residues == [Site(0, 1)]
    @test anchor_allowed(template, Site(0, 1))
    @test anchor_allowed(template, Site(-2, -1))
    @test !anchor_allowed(template, Site(1, 1))
    @test_throws ArgumentError PauliInteractionTemplate(
        [Site(0, 0)],
        [:X],
        1//4,
        :test;
        anchor_period=Site(0, 2),
    )
end

@testset "Shastry-Sutherland orthogonal dimer geometry" begin
    representatives = [Site(x, y) for x in -4:3 for y in -4:3]
    @test validate_dimer_covering(representatives)

    dimers = unique(canonical_dimer(site) for site in representatives)
    @test all(
        dimer -> abs(dimer[2].x - dimer[1].x) == 1 &&
                 abs(dimer[2].y - dimer[1].y) == 1,
        dimers,
    )
    @test Set(
        sign(dimer[2].x - dimer[1].x) *
        sign(dimer[2].y - dimer[1].y)
        for dimer in dimers
    ) == Set((-1, 1))

    for L in 1:3
        patch = square_patch_geometry(L)
        model = shastry_sutherland_model(0//1)
        @test validate_model_buffer(model, patch)
        terms = instantiate_terms(model, patch)
        @test all(
            term -> real(term.coefficient) == 1//4,
            filter(term -> term.tag == :dimer, terms),
        )
        @test all(
            term -> iszero(term.coefficient),
            filter(term -> term.tag == :square, terms),
        )
        dimer_terms = filter(term -> term.tag == :dimer, terms)
        @test length(dimer_terms) % 3 == 0
        @test all(dimer_terms) do term
            first_site = patch.sites[term.word.ops[1][1]]
            second_site = patch.sites[term.word.ops[2][1]]
            dimer_partner(first_site) == second_site ||
                dimer_partner(second_site) == first_site
        end
        @test sum(
            real(term.coefficient) *
            dimer_product_moment(term.word, patch)
            for term in dimer_terms
        ) == -3//4 * (length(dimer_terms) ÷ 3)
    end
end

@testset "exact g=0 dimer-product oracle" begin
    patch = square_patch_geometry(2)
    site_id(site) = patch.site_to_id[site]
    a = Site(0, 0)
    b = dimer_partner(a)
    c = Site(0, 1)
    d = dimer_partner(c)

    for axis in (:X, :Y, :Z)
        phase, word = pauli_word([(site_id(a), axis), (site_id(b), axis)])
        @test phase == 1
        @test dimer_product_moment(word, patch) == -1
    end

    _, cross_axis = pauli_word([(site_id(a), :X), (site_id(b), :Y)])
    _, one_site = pauli_word([(site_id(a), :Z)])
    _, two_dimers = pauli_word([
        (site_id(a), :X),
        (site_id(b), :X),
        (site_id(c), :Y),
        (site_id(d), :Y),
    ])
    @test dimer_product_moment(cross_axis, patch) == 0
    @test dimer_product_moment(one_site, patch) == 0
    @test dimer_product_moment(two_dimers, patch) == 1
    @test dimer_product_moment(PauliWord(), patch) == 1

    @test dimer_product_energy_density() == -3//8
    @test isolated_dimer_gap() == 1//1
    @test singlet_projector_expectation() == 1//1
end

@testset "Shastry-Sutherland problem adapter" begin
    patch = square_patch_geometry(1)
    model = shastry_sutherland_model(0//1)
    problem = GapProblem(patch, model, 0//1, 2)
    plan = assembly_plan(problem)

    @test plan.local_terms ==
          length(instantiate_terms(model, patch))
    @test plan.problem_sha256 == assembly_plan(problem).problem_sha256
    @test plan.problem_sha256 != assembly_plan(
        GapProblem(patch, square_j1j2_model(0//1), 0//1, 2),
    ).problem_sha256
end

include(joinpath(@__DIR__, "..", "src", "ShastrySutherlandPrimalOracle.jl"))
using .ShastrySutherlandPrimalOracle
include(joinpath(@__DIR__, "..", "src", "ShastrySutherlandReducedOracle.jl"))
using .ShastrySutherlandReducedOracle
include(joinpath(
    @__DIR__,
    "..",
    "src",
    "ShastryFullStateSpatialOracle.jl",
))
using .ShastryFullStateSpatialOracle

@testset "exact dimer state in assembled M/G/K constraints" begin
    patch = square_patch_geometry(1)
    model = shastry_sutherland_model(0//1)
    problem = GapProblem(
        patch,
        model,
        1//1,
        2;
        basis_mode=:structured,
        basis_spec=StructuredBasisSpec(:one_symbol_lift, 1),
    )
    assembled = assemble_primal_gap(problem)
    evaluated = evaluate_dimer_primal(assembled)

    @test evaluated.stationarity_exact_zero
    @test evaluated.positive_min_eigenvalue >= -1e-10
    @test evaluated.gap_min_eigenvalue >= -1e-10
    @test maximum(
        abs,
        evaluated.positive_matrix - evaluated.positive_matrix',
    ) == 0
    @test maximum(abs, evaluated.gap_matrix - evaluated.gap_matrix') == 0

    overclaimed = GapProblem(
        patch,
        model,
        11//10,
        2;
        basis_mode=:structured,
        basis_spec=StructuredBasisSpec(:one_symbol_lift, 1),
    )
    overclaim_evaluation = evaluate_dimer_primal(assemble_primal_gap(overclaimed))
    @test overclaim_evaluation.gap_min_eigenvalue < -1e-6

    nonzero_g = GapProblem(
        patch,
        shastry_sutherland_model(4//5),
        1//2,
        2;
        basis_mode=:structured,
        basis_spec=StructuredBasisSpec(:one_symbol_lift, 1),
    )
    @test_throws ArgumentError evaluate_dimer_primal(assemble_primal_gap(nonzero_g))
end

@testset "exact dimer state in V4-reduced M/G/K constraints" begin
    patch = square_patch_geometry(1)
    model = shastry_sutherland_model(0//1)
    spec = StructuredBasisSpec(:one_symbol_lift, 1)
    exact_problem = GapProblem(
        patch,
        model,
        1//1,
        2;
        basis_mode=:structured,
        basis_spec=spec,
    )
    exact_reduced = assemble_reduced_primal(
        assemble_primal_gap(exact_problem);
        verify_truth=false,
    )
    exact_evaluation = evaluate_reduced_dimer_primal(exact_reduced)
    @test exact_evaluation.equalities_exact_zero
    @test exact_evaluation.positive_minimum >= -1e-10
    @test exact_evaluation.gap_minimum >= -1e-10

    exact_full_state_spatial =
        assemble_shastry_full_state_spatial_reduced_primal(
            assemble_full_state_real_reduced_primal(
                assemble_full_state_v4_reduced_primal(
                    exact_reduced.source;
                    verify_truth=false,
                );
                verify_truth=false,
            );
            verify_truth=false,
        )
    exact_spatial_evaluation =
        evaluate_shastry_spatial_dimer_primal(
            exact_full_state_spatial,
        )
    @test exact_spatial_evaluation.equalities_exact_zero
    @test exact_spatial_evaluation.positive_minimum >= -1e-10
    @test exact_spatial_evaluation.gap_minimum >= -1e-10

    overclaim_problem = GapProblem(
        patch,
        model,
        11//10,
        2;
        basis_mode=:structured,
        basis_spec=spec,
    )
    overclaim_reduced = assemble_reduced_primal(
        assemble_primal_gap(overclaim_problem);
        verify_truth=false,
    )
    overclaim_evaluation = evaluate_reduced_dimer_primal(overclaim_reduced)
    @test overclaim_evaluation.equalities_exact_zero
    @test isapprox(
        overclaim_evaluation.gap_minimum,
        -0.1;
        atol=1e-12,
        rtol=0,
    )
end
