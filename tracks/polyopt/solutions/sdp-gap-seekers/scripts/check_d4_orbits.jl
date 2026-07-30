include(joinpath(@__DIR__, "..", "src", "SquareJ1J2Prototype.jl"))
using .SquareJ1J2Prototype
include(joinpath(@__DIR__, "..", "src", "GenericGapModel.jl"))
using .GenericGapModel
include(joinpath(@__DIR__, "..", "src", "SquareSymmetryD4.jl"))
using .SquareSymmetryD4

function main()
    isempty(ARGS) || error("check_d4_orbits.jl takes no arguments")
    elements = d4_matrices()
    println("d4_element_count\t$(length(elements))")
    closed, missing = is_d4_closed(elements)
    println("d4_group_closed\t$closed")
    closed || println("d4_missing_products\t$(join(missing, ","))")

    patch = square_patch_geometry(1)
    perms = d4_site_perms(patch, elements)
    println("d4_site_perms\t$(length(perms))")
    for el in elements
        perm = d4_site_perm(patch, el)
        println("perm\t$(el.name)\t$(join(perm, ","))")
    end

    model = square_j1j2_model(1 // 2)
    terms = instantiate_terms(model, patch)
    term_coeff = Dict{PauliWord,Complex{Rational{Int}}}()
    for term in terms
        term_coeff[term.word] = get(term_coeff, term.word, 0) + term.coefficient
    end
    println("hamiltonian_term_count\t$(length(terms))")
    all_invariant = true
    for el in elements
        perm = d4_site_perm(patch, el)
        mapped = Dict{PauliWord,Complex{Rational{Int}}}()
        for (word, coefficient) in term_coeff
            mapped[apply_site_perm(perm, word)] = coefficient
        end
        invariant = keys(term_coeff) == keys(mapped)
        coeff_match = invariant && all(term_coeff[w] == mapped[w] for w in keys(term_coeff))
        invariant && coeff_match || (all_invariant = false;
            println("hamiltonian_not_invariant_under\t$(el.name)"))
    end
    println("hamiltonian_d4_invariant\t$all_invariant")

    for (role, spec) in (
        ("positive_bare_operator", StructuredBasisSpec(:bare_operator, 1)),
    )
        problem = GapProblem(
            patch,
            model,
            0 // 1,
            2;
            basis_mode = :structured,
            basis_spec = spec,
        )
        manifest = basis_manifest(problem, :positive)
        orbits, histogram, escaped = basis_orbits(manifest.entries, perms)
        println("basis_role\t$role")
        println("basis_dim\t$(length(manifest.entries))")
        println("basis_orbit_fingerprint\t$(orbit_fingerprint(orbits, histogram))")
        println("basis_entries_escaping_d4\t$(length(escaped))")
        mult = irrep_multiplicities(manifest.entries, elements, perms)
        total_check = mult[:A1] + mult[:A2] + mult[:B1] + mult[:B2] + 2 * mult[:E]
        println("irrep_multiplicities\tA1=$(mult[:A1]) A2=$(mult[:A2]) B1=$(mult[:B1]) B2=$(mult[:B2]) E=$(mult[:E])")
        println("irrep_dim_sum_check\t$total_check (==$(length(manifest.entries))?)")
        largest = maximum([mult[:A1], mult[:A2], mult[:B1], mult[:B2], mult[:E]])
        println("largest_psd_block_dim\t$largest")
        println("tractability_vs_rungB\t$(round(largest / 352; digits=3)) dim fraction -> ~$(round((largest / 704)^3; digits=4)) of Rung B PSD-factor cost")
    end

    problem_gap = GapProblem(
        patch,
        model,
        0 // 1,
        2;
        basis_mode = :structured,
        basis_spec = StructuredBasisSpec(:bare_operator, 1),
    )
    gap_manifest = basis_manifest(problem_gap, :gap)
    gap_orbits, gap_histogram, gap_escaped = basis_orbits(gap_manifest.entries, perms)
    println("gap_basis_dim\t$(length(gap_manifest.entries))")
    println("gap_orbit_fingerprint\t$(orbit_fingerprint(gap_orbits, gap_histogram))")
    println("gap_entries_escaping_d4\t$(length(gap_escaped))")
    flush(stdout)
    return 0
end

exit(main())
