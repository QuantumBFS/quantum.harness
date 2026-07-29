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
    isempty(ARGS) || error("check_d4_coefficient_gates.jl takes no arguments")
    patch = square_patch_geometry(1)
    model = square_j1j2_model(1 // 2)
    problem = GapProblem(patch, model, 1 // 10, 2;
        basis_mode = :structured, basis_spec = StructuredBasisSpec(:bare_operator, 1))
    assembly = assemble_square_conic(problem)
    elements = d4_matrices()
    perms = d4_site_perms(patch, elements)

    println("=== gate 1: group closure + Hamiltonian D4-invariant (from check_d4_orbits) ===")
    closed, missing = is_d4_closed(elements)
    println("d4_group_closed\t$closed")
    term_coeff = Dict{PauliWord,Complex{Rational{Int}}}()
    for term in instantiate_terms(model, patch)
        term_coeff[term.word] = get(term_coeff, term.word, 0) + term.coefficient
    end
    h_inv = true
    for el in elements
        perm = d4_site_perm(patch, el)
        mapped = Dict(apply_site_perm(perm, w) => c for (w, c) in term_coeff)
        keys(term_coeff) == keys(mapped) && all(w -> term_coeff[w] == mapped[w], keys(term_coeff)) || (h_inv = false)
    end
    println("hamiltonian_d4_invariant\t$h_inv")

    println("=== gate 2: moment inventory D4-closed ===")
    g2 = gate_moment_closure(assembly.moments, perms)
    println("moment_closure\tclosed=$(g2.closed) missing=$(g2.missing)")

    println("=== gate 3: positive M coefficient-map D4-covariance (exact) ===")
    g3 = gate_positive_m_covariance(assembly.plan, perms)
    println("positive_m_covariance\tchecked=$(g3.checked) violations=$(g3.violations)")
    isempty(g3.first_violation) || println("first_m_violation\t$(g3.first_violation[1])")

    println("=== gate 4: gap K/G_moment/G_product D4-covariance (exact) ===")
    g4 = gate_gap_covariance(assembly.plan, perms)
    println("gap_covariance\tchecked=$(g4.checked) violations=$(g4.violations)")
    isempty(g4.first_violation) || println("first_gap_violation\t$(g4.first_violation[1])")

    println("=== gate 6: off-irrep Q' M Q cancellation (sampled, exact) ===")
    sym = symmetry_adapted_basis(assembly.plan.positive_basis.entries, elements, perms)
    g6 = gate_off_irrep_cancellation(assembly, sym, perms)
    println("off_irrep_cancellation\tpairs=$(g6.off_irrep_pairs) entries_checked=$(g6.entries_checked) violations=$(g6.violations)")

    println("=== summary ===")
    all_pass = closed && h_inv && g2.closed && g3.violations == 0 && g4.violations == 0 && g6.violations == 0
    println("ALL_D4_COEFFICIENT_GATES_PASS\t$all_pass")
    flush(stdout)
    return 0
end

exit(main())
