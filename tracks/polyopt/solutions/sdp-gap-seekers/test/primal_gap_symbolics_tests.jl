include(joinpath(@__DIR__, "..", "src", "PrimalGapSymbolics.jl"))
using .PrimalGapSymbolics

@testset "exact primal gap-SDP symbolic entries" begin
    _, x = pauli_word([(1, :X)])
    _, y = pauli_word([(1, :Y)])
    _, z = pauli_word([(1, :Z)])
    identity = PauliWord()

    bare_x = StateMonomial(PauliWord[], x)
    bare_y = StateMonomial(PauliWord[], y)
    scalar_x = StateMonomial([x], identity)
    scalar_y = StateMonomial([y], identity)

    z_moment = moment_key([z])
    xy_moment = moment_key([x, y])

    xy_positive = positive_entry(bare_x, bare_y)
    yx_positive = positive_entry(bare_y, bare_x)
    @test polynomial_coefficient(xy_positive, z_moment) == im
    @test polynomial_coefficient(yx_positive, z_moment) == -im
    @test yx_positive == adjoint_polynomial(xy_positive)

    covariance = covariance_product_entry(bare_x, bare_y)
    @test polynomial_coefficient(covariance, xy_moment) == 1
    @test polynomial_coefficient(covariance, z_moment) == 0
    @test covariance == covariance_product_entry(scalar_x, scalar_y)

    @test moment_key([y, x]) == xy_moment
    @test moment_key_string(moment_key()) == "moment=[]"
    @test moment_key_string(xy_moment) == "moment=[1X|1Y]"
    @test moment_degree(xy_moment) == 2
end

@testset "one-site Hamiltonian hand checks" begin
    _, x = pauli_word([(1, :X)])
    _, y = pauli_word([(1, :Y)])
    _, z = pauli_word([(1, :Z)])
    identity = PauliWord()

    hamiltonian = [
        LocalPauliTerm(1//1 + 0//1 * im, z, :test, Site(0, 0)),
    ]
    bare_x = StateMonomial(PauliWord[], x)
    bare_identity = StateMonomial(PauliWord[], identity)

    # [Z,X] = 2iY.
    stationarity = stationarity_entry(bare_x, hamiltonian)
    @test polynomial_coefficient(stationarity, moment_key([y])) == 2im
    @test length(stationarity.terms) == 1

    # 1/2 (X[Z,X] - [Z,X]X) = -2Z.
    energy_xx = gap_energy_entry(bare_x, bare_x, hamiltonian)
    @test polynomial_coefficient(energy_xx, moment_key([z])) == -2
    @test length(energy_xx.terms) == 1

    # The variance part is -gamma * (1 - ζ(X)^2).
    gap_xx = gap_entry(bare_x, bare_x, hamiltonian, 1//3)
    @test polynomial_coefficient(gap_xx, moment_key([z])) == -2
    @test polynomial_coefficient(gap_xx, moment_key()) == -1//3
    @test polynomial_coefficient(gap_xx, moment_key([x, x])) == 1//3
    @test length(gap_xx.terms) == 3

    # The identity direction has zero energy and zero variance.
    @test iszero(gap_entry(
        bare_identity,
        bare_identity,
        hamiltonian,
        1//3,
    ))
end

include(joinpath(@__DIR__, "..", "src", "PrimalGapAssembly.jl"))
using .PrimalGapAssembly
include(joinpath(@__DIR__, "..", "src", "PrimalGapJuMP.jl"))
using .PrimalGapJuMP
using JuMP

@testset "canonical stationarity equality handling" begin
    _, x = pauli_word([(1, :X)])
    _, y = pauli_word([(1, :Y)])
    _, z = pauli_word([(1, :Z)])
    hamiltonian = [
        LocalPauliTerm(1//1 + 0//1 * im, z, :test, Site(0, 0)),
    ]
    identity = StateMonomial(PauliWord[], PauliWord())
    bare_x = StateMonomial(PauliWord[], x)
    duplicate_x = StateMonomial([y], x)

    equalities = canonical_stationarity_equalities(
        [identity, bare_x, bare_x],
        hamiltonian,
    )
    @test length(equalities) == 1
    @test polynomial_coefficient(only(equalities), moment_key([y])) == 1

    # Multiplication by the scalar state symbol ζ(Y) is a distinct constraint.
    with_scalar_multiplier = canonical_stationarity_equalities(
        [bare_x, duplicate_x],
        hamiltonian,
    )
    @test length(with_scalar_multiplier) == 2
    @test any(
        polynomial_coefficient(equality, moment_key([y, y])) == 1
        for equality in with_scalar_multiplier
    )
end

@testset "small exact primal assembly manifest" begin
    site = Site(0, 0)
    patch = LocalPatch(
        "one-site-algebra-test",
        0,
        [site],
        Dict(site => 1),
        [1],
    )
    template = PauliInteractionTemplate(
        [site],
        [:Z],
        1//1,
        :test,
    )
    model = TranslationInvariantPauliModel(
        "one-site-z-test",
        [template],
    )
    problem = GapProblem(
        patch,
        model,
        1//3,
        2;
        basis_mode=:structured,
        basis_spec=StructuredBasisSpec(:one_symbol_lift, 1),
    )

    assembled = assemble_primal_gap(problem)
    repeated = assemble_primal_gap(problem)
    @test assembled.schema == "primal-gap-assembly-v1"
    @test length(assembled.positive_basis.entries) == 7
    @test length(assembled.gap_basis.entries) == 7
    @test length(assembled.hamiltonian_terms) == 1
    @test length(assembled.stationarity_equalities) == 2
    @test first(assembled.moments) == moment_key()
    @test all(key -> moment_degree(key) <= 4, assembled.moments)
    @test assembled.moments_sha256 == repeated.moments_sha256
    @test assembled.coefficient_map_sha256 ==
          repeated.coefficient_map_sha256
    @test assembled.assembly_sha256 == repeated.assembly_sha256

    changed_gamma = GapProblem(
        patch,
        model,
        1//2,
        2;
        basis_mode=:structured,
        basis_spec=StructuredBasisSpec(:one_symbol_lift, 1),
    )
    changed = assemble_primal_gap(changed_gamma)
    @test changed.problem_sha256 != assembled.problem_sha256
    @test changed.coefficient_map_sha256 !=
          assembled.coefficient_map_sha256
    @test changed.assembly_sha256 != assembled.assembly_sha256

    jump_model = build_jump_primal(assembled)
    @test JuMP.num_variables(jump_model.model) == length(assembled.moments)
    @test JuMP.num_constraints(
        jump_model.model;
        count_variable_in_set_constraints=false,
    ) == 5
    @test JuMP.name(jump_model.normalization_constraint) == "normalization"
    @test JuMP.name(jump_model.positive_constraint) == "positive_psd"
    @test JuMP.name(jump_model.gap_constraint) == "gap_psd"
    @test JuMP.name.(jump_model.stationarity_constraints) ==
          ["stationarity[1]", "stationarity[2]"]
    @test jump_model.assembly_sha256 == assembled.assembly_sha256
    @test JuMP.constraint_object(jump_model.positive_constraint).set isa
          JuMP.MOI.HermitianPositiveSemidefiniteConeTriangle
    @test JuMP.constraint_object(jump_model.gap_constraint).set isa
          JuMP.MOI.HermitianPositiveSemidefiniteConeTriangle
    @test JuMP.constraint_object(
        jump_model.positive_constraint,
    ).set.side_dimension == 7
    @test JuMP.constraint_object(
        jump_model.gap_constraint,
    ).set.side_dimension == 7
end

@testset "exactness and Hermitian matrix relations" begin
    patch = square_patch_geometry(1)
    model = square_j1j2_model(1//2)
    terms = instantiate_terms(model, patch)
    problem = GapProblem(
        patch,
        model,
        1//10,
        2;
        basis_mode=:structured,
        basis_spec=StructuredBasisSpec(:one_symbol_lift, 1),
    )
    positive_basis = basis_manifest(problem, :positive).entries
    gap_basis = basis_manifest(problem, :gap).entries

    selected_positive = positive_basis[1:12]
    for left in selected_positive, right in selected_positive
        @test positive_entry(right, left) ==
              adjoint_polynomial(positive_entry(left, right))
    end

    for left in gap_basis, right in gap_basis
        @test gap_entry(right, left, terms, problem.gamma) ==
              adjoint_polynomial(gap_entry(left, right, terms, problem.gamma))
    end

    @test_throws ArgumentError gap_entry(
        first(gap_basis),
        first(gap_basis),
        terms,
        0.1,
    )
end
