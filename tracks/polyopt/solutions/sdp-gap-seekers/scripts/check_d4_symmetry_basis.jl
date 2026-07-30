include(joinpath(@__DIR__, "..", "src", "SquareJ1J2Prototype.jl"))
using .SquareJ1J2Prototype
include(joinpath(@__DIR__, "..", "src", "GenericGapModel.jl"))
using .GenericGapModel
include(joinpath(@__DIR__, "..", "src", "SquareSymmetryD4.jl"))
using .SquareSymmetryD4
include(joinpath(@__DIR__, "..", "src", "SquareSymmetryBlock.jl"))
using .SquareSymmetryBlock

function main()
    isempty(ARGS) || error("check_d4_symmetry_basis.jl takes no arguments")
    patch = square_patch_geometry(1)
    model = square_j1j2_model(1 // 2)
    problem = GapProblem(
        patch,
        model,
        0 // 1,
        2;
        basis_mode = :structured,
        basis_spec = StructuredBasisSpec(:bare_operator, 1),
    )
    positive = basis_manifest(problem, :positive)
    entries = positive.entries
    println("basis_dim\t$(length(entries))")

    elements = d4_matrices()
    perms = d4_site_perms(patch, elements)

    elapsed = @elapsed sym = symmetry_adapted_basis(entries, elements, perms)
    println("Q_build_seconds\t$(round(elapsed; digits=3))")
    println("Q_shape\t$(size(sym.Q))")
    println("block_label\t$(block_label(sym))")
    println("rank_total\t$(sym.rank_total)")

    verify = verify_block_structure(sym, elements, perms)
    println("Q_is_square\t$(verify.Q_is_square)")
    println("block_diagonal_for_all_g\t$(verify.block_diagonal_for_all_g)")
    println("max_off_block_abs\t$(verify.max_off_block_abs)")

    mult = irrep_multiplicities(entries, elements, perms)
    println("predicted_irrep_mult\tA1=$(mult[:A1]) A2=$(mult[:A2]) B1=$(mult[:B1]) B2=$(mult[:B2]) E_isotypic=$(2*mult[:E])")

    cube_sum = 0
    for r in sym.block_ranges
        cube_sum += length(r)^3
    end
    println("sum_block_dim_cubed\t$cube_sum  (vs full 352^3 = $(352^3))")
    println("cost_fraction_vs_unsymmetric\t$(round(cube_sum / 352^3; digits=4))")
    flush(stdout)
    return 0
end

exit(main())
