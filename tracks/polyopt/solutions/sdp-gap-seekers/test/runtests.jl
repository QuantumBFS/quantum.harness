using Test

include(joinpath(@__DIR__, "..", "src", "SquareJ1J2Prototype.jl"))
using .SquareJ1J2Prototype

@testset "square patch geometry" begin
    for L in 1:4
        patch = square_patch(L; g=1//2)
        side = 2L + 1
        @test length(patch.sites) == side^2
        @test length(patch.inner_ids) == (side - 2)^2
        @test count(b -> b.kind == :J1, patch.bonds) == 2side * (side - 1)
        @test count(b -> b.kind == :J2, patch.bonds) == 2(side - 1)^2
        @test validate_inner_buffer(patch)
        @test length(unique((b.kind, b.i, b.j) for b in patch.bonds)) ==
              length(patch.bonds)
    end
end

@testset "Pauli canonicalization" begin
    one, identity = pauli_word([(1, :X), (1, :X)])
    @test one == 1
    @test isempty(identity.ops)

    phase_xy, xy = pauli_word([(1, :X), (1, :Y)])
    phase_yx, yx = pauli_word([(1, :Y), (1, :X)])
    _, z = pauli_word([(1, :Z)])
    @test phase_xy == im
    @test phase_yx == -im
    @test xy == z == yx

    phase_12, word_12 = pauli_word([(1, :X), (2, :Y)])
    phase_21, word_21 = pauli_word([(2, :Y), (1, :X)])
    @test phase_12 == phase_21 == 1
    @test word_12 == word_21

    _, x = pauli_word([(1, :X)])
    _, y = pauli_word([(1, :Y)])
    phase_left, left = multiply_words(x, y)
    phase_right, right = multiply_words(y, x)
    @test phase_left == im
    @test phase_right == -im
    @test left == right == z
end

@testset "bare Pauli basis counts" begin
    for nsites in 0:6, d in 0:4
        words = enumerate_pauli_words(nsites, d)
        @test length(words) == operator_word_count(nsites, d)
        @test length(unique(words)) == length(words)
    end
    @test operator_word_count(9, 2) == 352
    @test operator_word_count(25, 2) == 2776
end

@testset "full state-polynomial formal counts" begin
    @test full_state_basis_count_by_degree(1, 0) == BigInt[1]
    @test full_state_basis_count_by_degree(1, 1) == BigInt[1, 6]
    @test full_state_basis_count_by_degree(1, 2) == BigInt[1, 6, 15]
    @test full_state_basis_count(9, 2) == 1810
    @test one_symbol_lift_count(9, 2) == 703

    for nsites in 1:8
        counts = [full_state_basis_count(nsites, d) for d in 0:4]
        @test issorted(counts)
    end
end

@testset "storage estimates" begin
    @test dense_complex_matrix_bytes(10) == 1600
    @test real_embedding_matrix_bytes(10) == 3200
end

include(joinpath(@__DIR__, "..", "src", "LocalSpinIdentities.jl"))
using .LocalSpinIdentities

@testset "exact local spin identities" begin
    checks = local_identity_checks()
    for (name, result) in checks
        if result isa Bool
            @test result
        end
    end
    @test checks["bond_projector_traces"] == (1, 3)
    @test checks["triangle_projector_traces"] == (4, 4)
    @test checks["plaquette_projector_traces"] == (2, 9, 5)
    @test checks["joint_projector_traces"] == (1, 3, 3, 1, 3, 5)
end

include(joinpath(@__DIR__, "..", "src", "GenericGapModel.jl"))
using .GenericGapModel

@testset "generic solver-free problem adapter" begin
    for (L, expected_j1_bonds, expected_j2_bonds) in (
        (1, 12, 8),
        (2, 40, 32),
        (3, 84, 72),
    )
        patch = square_patch_geometry(L)
        model = square_j1j2_model(1//2)
        @test validate_model_buffer(model, patch)
        terms = instantiate_terms(model, patch)
        @test count(term -> term.tag == :J1, terms) == 3expected_j1_bonds
        @test count(term -> term.tag == :J2, terms) == 3expected_j2_bonds
        @test all(iszero ∘ imag ∘ (term -> term.coefficient), terms)
        @test all(
            term -> real(term.coefficient) == 1//4,
            filter(term -> term.tag == :J1, terms),
        )
        @test all(
            term -> real(term.coefficient) == 1//8,
            filter(term -> term.tag == :J2, terms),
        )
    end

    patch = square_patch_geometry(1)
    model = square_j1j2_model(1//2)
    integer_model = square_j1j2_model(0)
    @test all(
        term -> term.coefficient isa ComplexF64,
        instantiate_terms(integer_model, patch),
    )
    baseline_problem = GapProblem(
        patch,
        model,
        1//10,
        2;
        basis_mode=:one_symbol,
    )
    baseline_plan = assembly_plan(baseline_problem)
    @test baseline_plan.local_terms == 60
    @test baseline_plan.positive_basis_dimension == 703
    @test baseline_plan.gap_basis_dimension == 7
    @test !baseline_plan.is_complete
    @test baseline_plan.positive_basis_sha256 === nothing
    @test baseline_plan.gap_basis_sha256 === nothing
    @test !baseline_plan.symmetry_declared
    @test baseline_plan.problem_sha256 ==
          assembly_plan(baseline_problem).problem_sha256

    complete_problem = GapProblem(
        patch,
        model,
        1//10,
        2;
        basis_mode=:full_count_only,
    )
    complete_plan = assembly_plan(complete_problem)
    @test complete_plan.positive_basis_dimension == 1810
    @test complete_plan.gap_basis_dimension == 7
    @test complete_plan.is_complete
    @test complete_plan.positive_basis_sha256 === nothing
    @test complete_plan.gap_basis_sha256 === nothing
    @test complete_plan.problem_sha256 != baseline_plan.problem_sha256

    symmetric_problem = GapProblem(
        patch,
        model,
        1//10,
        2;
        basis_mode=:one_symbol,
        symmetry=ExplicitStateSymmetry("D4", ["C4", "mirror"]),
    )
    symmetric_plan = assembly_plan(symmetric_problem)
    @test symmetric_plan.symmetry_declared
    @test symmetric_plan.problem_sha256 != baseline_plan.problem_sha256
    joined_generator_problem = GapProblem(
        patch,
        model,
        1//10,
        2;
        basis_mode=:one_symbol,
        symmetry=ExplicitStateSymmetry("D4", ["C4|mirror"]),
    )
    @test assembly_plan(joined_generator_problem).problem_sha256 !=
          symmetric_plan.problem_sha256

    supports, coefficients = legacy_ncpoly_data(baseline_problem)
    @test length(supports) == length(coefficients) == 60
    @test all(length(support) == 2 for support in supports)
    @test count(==(Float64(1//4)), coefficients) == 36
    @test count(==(Float64(1//8)), coefficients) == 24

    changed_model = square_j1j2_model(107//200)
    changed_patch = square_patch_geometry(1)
    changed_problem = GapProblem(changed_patch, changed_model, 1//10, 2)
    @test assembly_plan(changed_problem).problem_sha256 !=
          baseline_plan.problem_sha256

    bad_sites = [Site(0, 0)]
    bad_patch = LocalPatch("bad-unbuffered", 0, bad_sites, Dict(Site(0, 0) => 1), [1])
    @test !validate_model_buffer(model, bad_patch)
    @test_throws ArgumentError GapProblem(bad_patch, model, 0//1, 2)
end

@testset "structured basis manifests" begin
    patch = square_patch_geometry(1)
    model = square_j1j2_model(1//2)
    spec = StructuredBasisSpec(:one_symbol_lift, 1)

    @test_throws ArgumentError GapProblem(
        patch,
        model,
        1//10,
        2;
        basis_mode=:structured,
    )
    @test_throws ArgumentError GapProblem(
        patch,
        model,
        1//10,
        2;
        basis_mode=:one_symbol,
        basis_spec=spec,
    )

    problem = GapProblem(
        patch,
        model,
        1//10,
        2;
        basis_mode=:structured,
        basis_spec=spec,
    )
    positive = basis_manifest(problem, :positive)
    gap = basis_manifest(problem, :gap)
    plan = assembly_plan(problem)

    @test positive.role == :positive
    @test gap.role == :gap
    @test positive.family == gap.family == :one_symbol_lift
    @test positive.family_version == gap.family_version == 1
    @test !positive.is_complete
    @test gap.is_complete
    @test positive.max_degree == 2
    @test gap.max_degree == 1
    @test positive.site_ids == collect(eachindex(patch.sites))
    @test gap.site_ids == patch.inner_ids
    @test length(positive.entries) == 703
    @test length(gap.entries) == 7
    @test length(unique(positive.entries)) == length(positive.entries)
    @test length(unique(gap.entries)) == length(gap.entries)
    @test all(entry -> state_monomial_degree(entry) <= 2, positive.entries)
    @test all(entry -> state_monomial_degree(entry) <= 1, gap.entries)
    @test all(
        entry -> all(
            factor -> factor[1] in patch.inner_ids,
            Iterators.flatten((
                entry.operator_word.ops,
                (word.ops for word in entry.state_symbols)...,
            )),
        ),
        gap.entries,
    )
    @test state_monomial_string(first(positive.entries)) == "zeta=[];op=I"
    @test issorted(state_monomial_degree.(positive.entries))
    @test issubset(Set(gap.entries), Set(positive.entries))
    @test positive.sha256 == basis_manifest(problem, :positive).sha256
    @test gap.sha256 == basis_manifest(problem, :gap).sha256
    @test positive.sha256 ==
          "83befe24c09bccdc7d228fc60c606d301dd76c10688121e1e466d43a583d5c13"
    @test gap.sha256 ==
          "5be3d2db7be104d1bc431898496e8e34116787a7f14a30886fa6933924bea169"
    @test positive.sha256 != gap.sha256
    @test validate_basis_manifest(positive)
    @test validate_basis_manifest(gap)
    @test validate_basis_manifest(positive, problem, :positive)
    @test validate_basis_manifest(gap, problem, :gap)
    @test !validate_basis_manifest(positive, problem, :gap)
    @test !validate_basis_manifest(gap, problem, :positive)

    forge_manifest = function(role, site_ids, max_degree)
        entries, is_complete, selection_rule =
            GenericGapModel.structured_basis_contents(spec, site_ids, max_degree)
        fingerprint = GenericGapModel.manifest_fingerprint(
            spec,
            role,
            site_ids,
            max_degree,
            is_complete,
            selection_rule,
            entries,
        )
        return BasisManifest(
            role,
            spec.family,
            spec.version,
            site_ids,
            max_degree,
            entries,
            is_complete,
            selection_rule,
            fingerprint,
        )
    end

    role_flipped = forge_manifest(:gap, positive.site_ids, positive.max_degree)
    @test validate_basis_manifest(role_flipped)
    @test !validate_basis_manifest(role_flipped, problem, :gap)

    wrong_gap_sites = [only(gap.site_ids) + 1]
    wrong_site_manifest = forge_manifest(:gap, wrong_gap_sites, gap.max_degree)
    @test validate_basis_manifest(wrong_site_manifest)
    @test !validate_basis_manifest(wrong_site_manifest, problem, :gap)

    wrong_degree_manifest =
        forge_manifest(:gap, gap.site_ids, gap.max_degree + 1)
    @test validate_basis_manifest(wrong_degree_manifest)
    @test !validate_basis_manifest(wrong_degree_manifest, problem, :gap)

    wrong_hash_manifest = BasisManifest(
        gap.role,
        gap.family,
        gap.family_version,
        gap.site_ids,
        gap.max_degree,
        gap.entries,
        gap.is_complete,
        gap.selection_rule,
        repeat("0", 64),
    )
    @test !validate_basis_manifest(wrong_hash_manifest)
    @test !validate_basis_manifest(wrong_hash_manifest, problem, :gap)

    input_state_word = PauliWord([(1, UInt8(1))])
    input_operator_word = PauliWord([(2, UInt8(2))])
    owned_monomial = StateMonomial([input_state_word], input_operator_word)
    push!(input_state_word.ops, (3, UInt8(3)))
    push!(input_operator_word.ops, (4, UInt8(1)))
    @test state_monomial_string(owned_monomial) ==
          "zeta=[1X];op=2Y"

    tampered = deepcopy(positive)
    push!(tampered.entries, first(tampered.entries))
    @test !validate_basis_manifest(tampered)
    nested_tamper = deepcopy(gap)
    push!(nested_tamper.entries[2].operator_word.ops, (99, UInt8(1)))
    @test !validate_basis_manifest(nested_tamper)

    constructor_sites = copy(gap.site_ids)
    constructor_entries = deepcopy(gap.entries)
    owned_manifest = BasisManifest(
        gap.role,
        gap.family,
        gap.family_version,
        constructor_sites,
        gap.max_degree,
        constructor_entries,
        gap.is_complete,
        gap.selection_rule,
        gap.sha256,
    )
    push!(constructor_sites, 99)
    push!(constructor_entries, first(constructor_entries))
    push!(constructor_entries[2].operator_word.ops, (99, UInt8(1)))
    @test owned_manifest.site_ids == gap.site_ids
    @test validate_basis_manifest(owned_manifest)

    truncated_entries = positive.entries[1:1]
    truncated_sha = GenericGapModel.manifest_fingerprint(
        spec,
        positive.role,
        positive.site_ids,
        positive.max_degree,
        positive.is_complete,
        positive.selection_rule,
        truncated_entries,
    )
    truncated = BasisManifest(
        positive.role,
        positive.family,
        positive.family_version,
        positive.site_ids,
        positive.max_degree,
        truncated_entries,
        positive.is_complete,
        positive.selection_rule,
        truncated_sha,
    )
    @test !validate_basis_manifest(truncated)
    @test plan.positive_basis_dimension == length(positive.entries)
    @test plan.gap_basis_dimension == length(gap.entries)
    @test !plan.is_complete
    @test plan.positive_basis_sha256 == positive.sha256
    @test plan.gap_basis_sha256 == gap.sha256
    @test plan.problem_sha256 ==
          "f6f7cd7a0cc2e053e40ecd82f52a24438536869e3340b959cd7f68cab4467f4e"

    for nsites in (1, 2, 9), max_degree in 0:2
        site_ids = collect(1:nsites)
        entries, is_complete, _ =
            GenericGapModel.structured_basis_contents(spec, site_ids, max_degree)
        @test BigInt(length(entries)) ==
              one_symbol_lift_count(nsites, max_degree)
        @test is_complete ==
              (max_degree <= 1)
        @test is_complete ==
              (BigInt(length(entries)) ==
               full_state_basis_count(nsites, max_degree))
    end

    higher_problem = GapProblem(
        patch,
        model,
        1//10,
        3;
        basis_mode=:structured,
        basis_spec=spec,
    )
    higher_positive = basis_manifest(higher_problem, :positive)
    @test higher_positive.entries[1:length(positive.entries)] == positive.entries
    higher_gap = basis_manifest(higher_problem, :gap)
    @test higher_gap.entries[1:length(gap.entries)] == gap.entries
    @test !higher_gap.is_complete

    changed_model_problem = GapProblem(
        patch,
        square_j1j2_model(107//200),
        1//5,
        2;
        basis_mode=:structured,
        basis_spec=spec,
    )
    @test basis_manifest(changed_model_problem, :positive).sha256 == positive.sha256
    @test assembly_plan(changed_model_problem).problem_sha256 != plan.problem_sha256

    changed_gamma_problem = GapProblem(
        patch,
        model,
        1//5,
        2;
        basis_mode=:structured,
        basis_spec=spec,
    )
    @test basis_manifest(changed_gamma_problem, :positive).sha256 == positive.sha256
    @test assembly_plan(changed_gamma_problem).problem_sha256 != plan.problem_sha256

    wider_patch = square_patch_geometry(2)
    wider_problem = GapProblem(
        wider_patch,
        model,
        1//10,
        2;
        basis_mode=:structured,
        basis_spec=spec,
    )
    wider_gap = basis_manifest(wider_problem, :gap)
    @test wider_gap.site_ids == wider_patch.inner_ids
    @test wider_gap.site_ids != collect(1:length(wider_gap.site_ids))
    @test length(wider_gap.entries) == 55
    @test validate_basis_manifest(wider_gap)

    permuted_inner_ids = reverse(wider_patch.inner_ids)
    permuted_patch = LocalPatch(
        wider_patch.name,
        wider_patch.level,
        copy(wider_patch.sites),
        copy(wider_patch.site_to_id),
        copy(permuted_inner_ids),
    )
    permuted_problem = GapProblem(
        permuted_patch,
        model,
        1//10,
        2;
        basis_mode=:structured,
        basis_spec=spec,
    )
    permuted_gap = basis_manifest(permuted_problem, :gap)
    @test permuted_gap.site_ids == wider_gap.site_ids
    @test permuted_gap.entries == wider_gap.entries
    @test permuted_gap.sha256 == wider_gap.sha256
    @test permuted_problem.patch.inner_ids == permuted_inner_ids
    @test validate_basis_manifest(permuted_gap, permuted_problem, :gap)
    wider_plan = assembly_plan(wider_problem)
    permuted_plan = assembly_plan(permuted_problem)
    @test permuted_plan.problem_sha256 == wider_plan.problem_sha256
    @test all(
        getproperty(permuted_plan, field) == getproperty(wider_plan, field)
        for field in propertynames(wider_plan)
    )

    duplicate_patch = LocalPatch(
        wider_patch.name,
        wider_patch.level,
        copy(wider_patch.sites),
        copy(wider_patch.site_to_id),
        [wider_patch.inner_ids; first(wider_patch.inner_ids)],
    )
    duplicate_problem = GapProblem(
        duplicate_patch,
        model,
        1//10,
        2;
        basis_mode=:structured,
        basis_spec=spec,
    )
    @test_throws ArgumentError basis_manifest(duplicate_problem, :gap)

    invalid_patch = LocalPatch(
        wider_patch.name,
        wider_patch.level,
        copy(wider_patch.sites),
        copy(wider_patch.site_to_id),
        copy(wider_patch.inner_ids),
    )
    invalid_problem = GapProblem(
        invalid_patch,
        model,
        1//10,
        2;
        basis_mode=:structured,
        basis_spec=spec,
    )
    push!(invalid_problem.patch.inner_ids, length(invalid_patch.sites) + 1)
    @test_throws ArgumentError basis_manifest(invalid_problem, :gap)
end

include(joinpath(@__DIR__, "primal_gap_symbolics_tests.jl"))

include(joinpath(@__DIR__, "exact_symmetry_reduction_truth_tests.jl"))

include(joinpath(@__DIR__, "shastry_sutherland_tests.jl"))

include(joinpath(@__DIR__, "..", "src", "SmallEDOracle.jl"))
using .SmallEDOracle

@testset "small finite-patch ED construction oracle" begin
    comparison = compare_hamiltonian_builders(1; g=1//2)
    @test comparison.max_builder_difference == 0
    @test comparison.hermiticity_error == 0
    @test comparison.trace == 0
end

include(joinpath(@__DIR__, "legacy_inventory_format_tests.jl"))
