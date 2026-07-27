include(joinpath(@__DIR__, "..", "src", "SquareJ1J2Prototype.jl"))
using .SquareJ1J2Prototype

configs = [(1, 2), (1, 3), (2, 2), (2, 3), (3, 2)]

println(join([
    "L",
    "d",
    "outer_sites",
    "inner_sites",
    "J1_bonds",
    "J2_bonds",
    "operator_pos",
    "one_symbol_pos",
    "full_state_pos",
    "operator_gap",
    "one_symbol_gap",
    "full_state_gap",
    "full_pos_complex_storage",
], ","))

for (L, d) in configs
    patch = square_patch(L; g=1//2)
    outer_sites = length(patch.sites)
    inner_sites = length(patch.inner_ids)
    j1_bonds = count(bond -> bond.kind == :J1, patch.bonds)
    j2_bonds = count(bond -> bond.kind == :J2, patch.bonds)

    operator_pos = operator_word_count(outer_sites, d)
    one_symbol_pos = one_symbol_lift_count(outer_sites, d)
    full_state_pos = full_state_basis_count(outer_sites, d)

    gap_degree = d - 1
    operator_gap = operator_word_count(inner_sites, gap_degree)
    one_symbol_gap = one_symbol_lift_count(inner_sites, gap_degree)
    full_state_gap = full_state_basis_count(inner_sites, gap_degree)

    println(join([
        L,
        d,
        outer_sites,
        inner_sites,
        j1_bonds,
        j2_bonds,
        operator_pos,
        one_symbol_pos,
        full_state_pos,
        operator_gap,
        one_symbol_gap,
        full_state_gap,
        format_bytes(dense_complex_matrix_bytes(full_state_pos)),
    ], ","))
end
