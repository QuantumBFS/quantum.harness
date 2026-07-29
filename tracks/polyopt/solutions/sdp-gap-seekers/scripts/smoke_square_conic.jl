using JuMP

include(joinpath(@__DIR__, "..", "src", "SquareJ1J2Prototype.jl"))
using .SquareJ1J2Prototype
include(joinpath(@__DIR__, "..", "src", "GenericGapModel.jl"))
using .GenericGapModel
include(joinpath(@__DIR__, "..", "src", "CoreMGK.jl"))
using .CoreMGK
include(joinpath(@__DIR__, "..", "src", "SquareGapConic.jl"))
using .SquareGapConic

function main()
    isempty(ARGS) || error("smoke_square_conic.jl takes no arguments")

    problem = GapProblem(
        square_patch_geometry(1),
        square_j1j2_model(1 // 2),
        0 // 1,
        2;
        basis_mode = :structured,
        basis_spec = StructuredBasisSpec(:bare_weight_one, 1),
    )

    assembly = assemble_square_conic(problem)
    println("schema\t", assembly.schema)
    println("positive_basis_rows\t", length(assembly.plan.positive_basis.entries))
    println("gap_basis_rows\t", length(assembly.plan.gap_basis.entries))
    println("hamiltonian_terms\t", length(assembly.plan.hamiltonian_terms))
    println("stationarity_equalities\t", length(assembly.stationarity_equalities))
    println("scalar_moments\t", length(assembly.moments))
    println("identity_moment_first\t", first(assembly.moments) == ScalarMoment(PauliWord[]))
    println("positive_basis_sha256\t", assembly.plan.positive_basis.sha256)
    println("gap_basis_sha256\t", assembly.plan.gap_basis.sha256)
    println("problem_sha256\t", assembly.problem_sha256)
    println("moments_sha256\t", assembly.moments_sha256)
    println("coefficient_map_sha256\t", assembly.coefficient_map_sha256)
    println("assembly_sha256\t", assembly.assembly_sha256)
    println("gamma\t", assembly.gamma)
    println("state_class\t", assembly.plan.state_class)

    jump_model = build_square_conic_jump(assembly)
    model = jump_model.model
    println("jump_variable_count\t", JuMP.num_variables(model))
    println("jump_objective_sense\t", JuMP.objective_sense(model))
    constraint_count = JuMP.num_constraints(
        model;
        count_variable_in_set_constraints = false,
    )
    println("jump_constraint_count_excluding_variable_sets\t", constraint_count)
    println("jump_normalization_name\t", JuMP.name(jump_model.normalization_constraint))
    println("jump_stationarity_count\t", length(jump_model.stationarity_constraints))
    println("jump_positive_psd_name\t", JuMP.name(jump_model.positive_constraint))
    println("jump_gap_psd_name\t", JuMP.name(jump_model.gap_constraint))
    println("first_variable_name\t", JuMP.name(JuMP.all_variables(model)[1]))

    positive_object = JuMP.constraint_object(jump_model.positive_constraint)
    gap_object = JuMP.constraint_object(jump_model.gap_constraint)
    println("positive_cone_type\t", typeof(positive_object.set))
    println("gap_cone_type\t", typeof(gap_object.set))
    flush(stdout)
    return 0
end

exit(main())
