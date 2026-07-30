using JuMP

include(joinpath(@__DIR__, "..", "src", "SquareJ1J2Prototype.jl"))
using .SquareJ1J2Prototype
include(joinpath(@__DIR__, "..", "src", "GenericGapModel.jl"))
using .GenericGapModel
include(joinpath(@__DIR__, "..", "src", "CoreMGK.jl"))
using .CoreMGK
include(joinpath(@__DIR__, "..", "src", "SquareSymmetryD4.jl"))
using .SquareSymmetryD4
include(joinpath(@__DIR__, "..", "src", "SquareSymmetryBlock.jl"))
using .SquareSymmetryBlock
include(joinpath(@__DIR__, "..", "src", "SquareGapConic.jl"))
using .SquareGapConic

function main()
    isempty(ARGS) || error("smoke_d4_conic.jl takes no arguments")
    patch = square_patch_geometry(1)
    model_h = square_j1j2_model(1 // 2)
    problem = GapProblem(
        patch,
        model_h,
        0 // 1,
        2;
        basis_mode = :structured,
        basis_spec = StructuredBasisSpec(:bare_operator, 1),
    )

    assembly = assemble_square_conic(problem)
    println("moments\t$(length(assembly.moments))")
    println("stationarity\t$(length(assembly.stationarity_equalities))")
    println("positive_dim\t$(length(assembly.plan.positive_basis.entries))")
    println("gap_dim\t$(length(assembly.plan.gap_basis.entries))")

    elements = d4_matrices()
    perms = d4_site_perms(patch, elements)
    sym = symmetry_adapted_basis(assembly.plan.positive_basis.entries, elements, perms)
    println("Q_shape\t$(size(sym.Q))")
    println("block_label\t$(block_label(sym))")

    verify = verify_block_structure(sym, elements, perms)
    println("block_diag_all_g\t$(verify.block_diagonal_for_all_g)")
    println("max_off_block\t$(verify.max_off_block_abs)")

    elapsed = @elapsed d4model = build_square_d4_conic_jump(assembly, sym, perms)
    quotient = d4_moment_quotient(assembly.moments, perms)
    println("moment_quotient\t$(quotient.original_count)->$(quotient.quotient_count) (orbit histogram: $(quotient.orbit_histogram))")
    println("d4_jump_build_seconds\t$(round(elapsed; digits=3))")
    m = d4model.model
    println("jump_variables\t$(JuMP.num_variables(m))")
    println("jump_objective_sense\t$(JuMP.objective_sense(m))")
    cc = JuMP.num_constraints(m; count_variable_in_set_constraints = false)
    println("jump_constraints_excl_varsets\t$cc")
    println("positive_block_count\t$(length(d4model.positive_block_constraints))")
    block_dims = Int[]
    for c in d4model.positive_block_constraints
        obj = JuMP.constraint_object(c)
        push!(block_dims, obj.set.side_dimension)
    end
    println("positive_block_side_dims\t$(join(block_dims, ","))")
    println("positive_block_irreps\t$(join(d4model.positive_block_irreps, ","))")
    gap_obj = JuMP.constraint_object(d4model.gap_constraint)
    println("gap_side_dim\t$(gap_obj.set.side_dimension)")
    flush(stdout)
    return 0
end

exit(main())
