module FullSpinConeReduction

using SHA
using ..PrimalGapSymbolics:
    ExactRational,
    ExactLinearPolynomial,
    MomentKey,
    moment_key,
    moment_degree,
    canonical_polynomial_string,
    polynomial_sha256
using ..ExactSymmetryReduction:
    V4Character,
    canonical_real_equalities
using ..ReducedPrimalGapAssembly:
    ReducedPSDBlock
using ..ConjugationSymmetryReduction:
    conjugation_odd,
    conjugation_real_block_entry
using ..SpinAxisInvolutionReduction:
    SpinAxisCombinationRow,
    SpinAxisReducedPSDBlock
using ..FullSpinPermutationReduction:
    SPIN_AXIS_PERMUTATIONS,
    FullSpinReducedPrimalAssembly,
    full_spin_permutation,
    full_spin_character,
    full_spin_quotient_projection,
    full_spin_block_entry

export FULL_SPIN_CONE_REDUCTION_SCHEMA,
       FullSpinConeReducedPrimalAssembly,
       full_spin_nontrivial_cone_redundancy_truth,
       full_spin_cone_block_entry,
       assemble_full_spin_cone_reduced_primal,
       full_spin_cone_reduced_assembly_report

const FULL_SPIN_CONE_REDUCTION_SCHEMA =
    "primal-gap-exact-v4-conjugation-real-full-spin-cone-orbit-reduction-v1"
const TRIVIAL_CHARACTER = V4Character(false, false)

block_identity(block::SpinAxisReducedPSDBlock) = (
    block.source_block.role,
    block.source_block.family,
)

is_nontrivial(block::SpinAxisReducedPSDBlock) =
    block.source_block.character != TRIVIAL_CHARACTER

function exact_matrix_rank(matrix::Matrix{ExactRational})
    reduced = copy(matrix)
    rank = 0
    for column in axes(reduced, 2)
        pivot = findfirst(
            row -> !iszero(reduced[row, column]),
            (rank + 1):size(reduced, 1),
        )
        isnothing(pivot) && continue
        pivot_row = rank + something(pivot)
        rank += 1
        if pivot_row != rank
            reduced[rank, :], reduced[pivot_row, :] =
                copy(reduced[pivot_row, :]), copy(reduced[rank, :])
        end
        pivot_value = reduced[rank, column]
        reduced[rank, :] ./= pivot_value
        for row in axes(reduced, 1)
            row == rank && continue
            scale = reduced[row, column]
            iszero(scale) && continue
            reduced[row, :] .-= scale .* reduced[rank, :]
        end
        rank == min(size(reduced)...) && break
    end
    return rank
end

function combination_basis_rank(
    blocks::Vector{SpinAxisReducedPSDBlock},
)
    isempty(blocks) && return 0
    dimension = length(first(blocks).source_block.rows)
    rows = reduce(vcat, getfield.(blocks, :rows))
    matrix = zeros(ExactRational, length(rows), dimension)
    for (row_index, row) in enumerate(rows)
        for (source_index, coefficient) in
            zip(row.source_indices, row.coefficients)
            matrix[row_index, source_index] = coefficient
        end
    end
    return exact_matrix_rank(matrix)
end

function projected_source_block_entry(
    assembly::FullSpinReducedPrimalAssembly,
    block::ReducedPSDBlock,
    left_index::Int,
    right_index::Int,
)
    polynomial = conjugation_real_block_entry(
        assembly.source.source,
        block,
        block.rows[left_index],
        block.rows[right_index],
    )
    return full_spin_quotient_projection(
        polynomial,
        assembly.quotient,
    )
end

function stable_blocks_for(
    assembly::FullSpinReducedPrimalAssembly,
    orbit_block::SpinAxisReducedPSDBlock,
)
    identity = block_identity(orbit_block)
    candidates = filter(
        block ->
            block_identity(block) == identity &&
            is_nontrivial(block) &&
            block.kind != :orbit_representative,
        [
            assembly.source.positive_blocks;
            assembly.source.gap_blocks
        ],
    )
    isempty(candidates) &&
        error("missing stable nontrivial character blocks for $identity")
    source_characters = unique([
        block.source_block.character
        for block in candidates
    ])
    length(source_characters) == 1 ||
        error("stable nontrivial blocks do not share one source character")
    source_block = first(candidates).source_block
    all(block -> block.source_block === source_block, candidates) ||
        error("stable nontrivial blocks do not share one source block")
    return candidates
end

function mapping_to_stable_block(
    orbit_block::SpinAxisReducedPSDBlock,
    stable_source::ReducedPSDBlock,
)
    permutation_index = findfirst(
        permutation ->
            full_spin_character(
                orbit_block.source_block.character,
                permutation,
            ) == stable_source.character,
        SPIN_AXIS_PERMUTATIONS,
    )
    isnothing(permutation_index) &&
        error("no full-spin permutation maps the orbit block to the stable block")
    permutation = SPIN_AXIS_PERMUTATIONS[something(permutation_index)]
    target_indices = Dict(
        row.word => index
        for (index, row) in enumerate(stable_source.rows)
    )
    signs = Int[]
    indices = Int[]
    for row in orbit_block.source_block.rows
        sign, target = full_spin_permutation(row.word, permutation)
        haskey(target_indices, target) ||
            error("full-spin target row is missing from the stable block")
        push!(signs, sign)
        push!(indices, target_indices[target])
    end
    length(unique(indices)) == length(indices) ||
        error("full-spin row mapping is not injective")
    sort(indices) == collect(eachindex(stable_source.rows)) ||
        error("full-spin row mapping is not surjective")
    return signs, indices
end

realification_phase(row) =
    conjugation_odd(row.word) ?
    Complex{Int}(0, 1) :
    Complex{Int}(1, 0)

function realification_transport_phases(
    orbit_block::SpinAxisReducedPSDBlock,
    stable_source::ReducedPSDBlock,
    signs::Vector{Int},
    target_indices::Vector{Int},
)
    return Complex{Int}[
        signs[index] *
        conj(realification_phase(
            stable_source.rows[target_indices[index]],
        )) *
        realification_phase(orbit_block.source_block.rows[index])
        for index in eachindex(signs)
    ]
end

"""
Prove that the full-S3 quotient makes each orbit-representative cone redundant.

The three nontrivial V4 characters form one S3 orbit. A chosen character
block is exactly congruent, by a signed row permutation followed by exact row
phases in `{±1,±i}`, to the stable nontrivial character block. The latter
already has an exact invertible involution basis and zero plus/minus cross
block, so its retained eigenspace cones imply the orbit-representative cone
and conversely.
"""
function full_spin_nontrivial_cone_redundancy_truth(
    assembly::FullSpinReducedPrimalAssembly,
)
    all_blocks = [
        assembly.source.positive_blocks;
        assembly.source.gap_blocks
    ]
    orbit_blocks = filter(
        block -> block.kind == :orbit_representative,
        all_blocks,
    )

    orbit_projection_exact = true
    orbit_congruence_exact = true
    stable_cross_blocks_zero = true
    stable_bases_invertible = true
    gauge_phases_well_formed = true
    gauge_mixed_entries_zero = true
    orbit_entry_count = 0
    stable_cross_entry_count = 0
    gauge_mixed_entry_count = 0
    stable_basis_dimensions = Int[]

    for orbit_block in orbit_blocks
        stable_blocks = stable_blocks_for(assembly, orbit_block)
        stable_source = first(stable_blocks).source_block
        dimension = length(stable_source.rows)
        length(orbit_block.rows) == dimension ||
            error("orbit and stable source dimensions differ")

        basis_rank = combination_basis_rank(stable_blocks)
        push!(stable_basis_dimensions, basis_rank)
        stable_bases_invertible &= basis_rank == dimension

        signs, target_indices =
            mapping_to_stable_block(orbit_block, stable_source)
        transport_phases = realification_transport_phases(
            orbit_block,
            stable_source,
            signs,
            target_indices,
        )
        gauge_phases_well_formed &= all(
            phase -> phase in (
                Complex{Int}(1, 0),
                Complex{Int}(-1, 0),
                Complex{Int}(0, 1),
                Complex{Int}(0, -1),
            ),
            transport_phases,
        )
        for left in 1:dimension, right in left:dimension
            orbit_projected = projected_source_block_entry(
                assembly,
                orbit_block.source_block,
                left,
                right,
            )
            orbit_entry = full_spin_block_entry(
                assembly,
                orbit_block,
                orbit_block.rows[left],
                orbit_block.rows[right],
            )
            orbit_projection_exact &= orbit_entry == orbit_projected

            stable_projected = projected_source_block_entry(
                assembly,
                stable_source,
                target_indices[left],
                target_indices[right],
            )
            gauge_factor =
                conj(transport_phases[left]) *
                transport_phases[right]
            orbit_congruence_exact &=
                orbit_projected ==
                gauge_factor * stable_projected
            if !iszero(imag(gauge_factor))
                gauge_mixed_entries_zero &=
                    iszero(orbit_projected) &&
                    iszero(stable_projected)
                gauge_mixed_entry_count += 1
            end
            orbit_entry_count += 1
        end

        plus_blocks = filter(block -> block.kind == :eigen_plus, stable_blocks)
        minus_blocks = filter(block -> block.kind == :eigen_minus, stable_blocks)
        for plus in plus_blocks, minus in minus_blocks
            for left in plus.rows, right in minus.rows
                stable_cross_blocks_zero &=
                    iszero(full_spin_block_entry(
                        assembly,
                        plus,
                        left,
                        right,
                    ))
                stable_cross_entry_count += 1
            end
        end
    end

    expected_orbit_dimensions = sort([
        length(block.rows)
        for block in orbit_blocks
    ])
    exact =
        length(orbit_blocks) == 3 &&
        expected_orbit_dimensions == [1, 81, 81] &&
        orbit_projection_exact &&
        orbit_congruence_exact &&
        stable_cross_blocks_zero &&
        stable_bases_invertible &&
        gauge_phases_well_formed &&
        gauge_mixed_entries_zero
    return (
        exact=exact,
        orbit_block_count=length(orbit_blocks),
        orbit_block_dimensions=expected_orbit_dimensions,
        orbit_projection_exact=orbit_projection_exact,
        orbit_congruence_exact=orbit_congruence_exact,
        orbit_entry_count=orbit_entry_count,
        stable_cross_blocks_zero=stable_cross_blocks_zero,
        stable_cross_entry_count=stable_cross_entry_count,
        stable_bases_invertible=stable_bases_invertible,
        stable_basis_dimensions=sort(stable_basis_dimensions),
        gauge_phases_well_formed=gauge_phases_well_formed,
        gauge_mixed_entries_zero=gauge_mixed_entries_zero,
        gauge_mixed_entry_count=gauge_mixed_entry_count,
    )
end

struct FullSpinConeReducedPrimalAssembly{A}
    schema::String
    source::A
    positive_blocks::Vector{SpinAxisReducedPSDBlock}
    gap_blocks::Vector{SpinAxisReducedPSDBlock}
    equalities::Vector{ExactLinearPolynomial}
    moments::Vector{MomentKey}
    coefficient_map_sha256::String
    assembly_sha256::String
end

function full_spin_cone_block_entry(
    assembly::FullSpinConeReducedPrimalAssembly,
    block::SpinAxisReducedPSDBlock,
    left::SpinAxisCombinationRow,
    right::SpinAxisCombinationRow,
)
    return full_spin_block_entry(
        assembly.source,
        block,
        left,
        right,
    )
end

function write_framed!(io::IO, value)
    serialized = string(value)
    write(io, string(ncodeunits(serialized)), ":", serialized)
    return io
end

function fingerprint_records(schema::String, records)
    io = IOBuffer()
    write_framed!(io, schema)
    for record in records
        write_framed!(io, record)
    end
    return bytes2hex(sha256(take!(io)))
end

function source_block_label(block::SpinAxisReducedPSDBlock)
    source = block.source_block
    return join(
        (
            source.role,
            source.family,
            "rx" * string(Int(source.character.rx)),
            "ry" * string(Int(source.character.ry)),
            block.kind,
        ),
        ":",
    )
end

function assemble_full_spin_cone_reduced_primal(
    source::FullSpinReducedPrimalAssembly;
    verify_truth::Bool=true,
)
    truth = verify_truth ?
        full_spin_nontrivial_cone_redundancy_truth(source) :
        nothing
    if verify_truth
        something(truth).exact ||
            error("full-spin cone-redundancy truth check failed")
    end

    positive_blocks = filter(
        block -> block.kind != :orbit_representative,
        source.source.positive_blocks,
    )
    gap_blocks = filter(
        block -> block.kind != :orbit_representative,
        source.source.gap_blocks,
    )
    equalities = canonical_real_equalities(copy(source.equalities))
    provisional = FullSpinConeReducedPrimalAssembly(
        FULL_SPIN_CONE_REDUCTION_SCHEMA,
        source,
        positive_blocks,
        gap_blocks,
        equalities,
        MomentKey[],
        "",
        "",
    )

    used_moments = Set{MomentKey}([moment_key()])
    coefficient_records = String[]
    for block in [positive_blocks; gap_blocks]
        for row in eachindex(block.rows), column in row:length(block.rows)
            polynomial = full_spin_cone_block_entry(
                provisional,
                block,
                block.rows[row],
                block.rows[column],
            )
            union!(used_moments, keys(polynomial.terms))
            push!(
                coefficient_records,
                join(
                    (
                        source_block_label(block),
                        row,
                        column,
                        polynomial_sha256(polynomial),
                    ),
                    ":",
                ),
            )
        end
    end
    for equality in equalities
        union!(used_moments, keys(equality.terms))
    end
    moments = sort!(
        collect(used_moments);
        by=key -> (moment_degree(key), key.canonical),
    )
    first(moments) == moment_key() ||
        error("identity moment is not first after cone reduction")

    coefficient_sha256 = fingerprint_records(
        "full-spin-cone-real-upper-triangle-coefficients-v1",
        coefficient_records,
    )
    equality_sha256 = fingerprint_records(
        "full-spin-cone-real-equalities-v1",
        canonical_polynomial_string.(equalities),
    )
    block_records = String[
        source_block_label(block) * ":" * string(length(block.rows))
        for block in [positive_blocks; gap_blocks]
    ]
    final_sha256 = fingerprint_records(
        FULL_SPIN_CONE_REDUCTION_SCHEMA,
        [
            "source=" * source.assembly_sha256,
            "equalities=" * equality_sha256,
            "moments=" * join(
                (key.canonical for key in moments),
                "\n",
            ),
            "blocks=" * join(block_records, "\n"),
            "coefficients=" * coefficient_sha256,
        ],
    )
    return FullSpinConeReducedPrimalAssembly(
        FULL_SPIN_CONE_REDUCTION_SCHEMA,
        source,
        positive_blocks,
        gap_blocks,
        equalities,
        moments,
        coefficient_sha256,
        final_sha256,
    )
end

triangle_count(dimension::Int) =
    dimension * (dimension + 1) ÷ 2

function full_spin_cone_reduced_assembly_report(
    assembly::FullSpinConeReducedPrimalAssembly,
)
    positive_dimensions = length.(getfield.(assembly.positive_blocks, :rows))
    gap_dimensions = length.(getfield.(assembly.gap_blocks, :rows))
    all_dimensions = [positive_dimensions; gap_dimensions]
    return (
        source_full_spin_moments=length(assembly.source.moments),
        cone_reduced_moments=length(assembly.moments),
        eliminated_unused_moments=
            length(assembly.source.moments) - length(assembly.moments),
        removed_orbit_cones=
            length(assembly.source.source.positive_blocks) +
            length(assembly.source.source.gap_blocks) -
            length(all_dimensions),
        positive_block_dimensions=positive_dimensions,
        gap_block_dimensions=gap_dimensions,
        equality_count=length(assembly.equalities),
        real_psd_triangle_entries=sum(triangle_count, all_dimensions),
        maximum_psd_side_dimension=maximum(all_dimensions),
        coefficient_map_sha256=assembly.coefficient_map_sha256,
        assembly_sha256=assembly.assembly_sha256,
    )
end

end
