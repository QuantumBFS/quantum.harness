module ContinuousSpinMomentReduction

using LinearAlgebra
using SHA
using ..SquareJ1J2Prototype:
    PauliWord
using ..PrimalGapSymbolics:
    ExactRational,
    ExactLinearPolynomial,
    MomentKey,
    add_term!,
    add_scaled!,
    moment_key,
    moment_degree,
    canonical_polynomial_string,
    polynomial_sha256
using ..FullSpinIsotypicReduction:
    FullSpinIsotypicPSDBlock,
    FullSpinIsotypicReducedPrimalAssembly,
    full_spin_isotypic_block_entry

export CONTINUOUS_SPIN_MOMENT_REDUCTION_SCHEMA,
       ContinuousSpinMomentQuotient,
       ContinuousSpinReducedPrimalAssembly,
       continuous_spin_moment_quotient,
       continuous_spin_quotient_projection,
       continuous_spin_moment_truth,
       continuous_spin_block_entry,
       assemble_continuous_spin_reduced_primal,
       continuous_spin_reduced_assembly_report

const CONTINUOUS_SPIN_MOMENT_REDUCTION_SCHEMA =
    "primal-gap-exact-v4-conjugation-real-full-spin-isotypic-continuous-spin-moment-v1"
const AXIS_CODE = Dict('X' => UInt8(1), 'Y' => UInt8(2), 'Z' => UInt8(3))
const RATIONAL_ROTATION = ExactRational[
    3//5 -4//5 0
    4//5  3//5 0
    0       0   1
]

function parse_moment_word(serialized::AbstractString)
    isempty(serialized) &&
        throw(ArgumentError("state-symbol word cannot be empty"))
    operations = Tuple{Int,UInt8}[]
    for factor in split(serialized, ';')
        matched = match(r"^([0-9]+)([XYZ])$", factor)
        isnothing(matched) &&
            error("malformed canonical moment factor: $factor")
        site_text, axis_text = something(matched).captures
        push!(
            operations,
            (parse(Int, site_text), AXIS_CODE[only(axis_text)]),
        )
    end
    return PauliWord(operations)
end

function moment_words(key::MomentKey)
    isempty(key.canonical) && return PauliWord[]
    return PauliWord[
        parse_moment_word(serialized)
        for serialized in split(key.canonical, '|')
    ]
end

function skeleton_words(key::MomentKey)
    words = [first.(word.ops) for word in moment_words(key)]
    sort!(words; by=sites -> Tuple(sites))
    return words
end

function skeleton_string(words::Vector{Vector{Int}})
    return join((join(sites, ",") for sites in words), "|")
end

skeleton_string(key::MomentKey) = skeleton_string(skeleton_words(key))

function assigned_moment(
    words::Vector{Vector{Int}},
    axes::Vector{UInt8},
)
    sum(length, words; init=0) == length(axes) ||
        throw(ArgumentError("axis assignment has the wrong length"))
    state_symbols = PauliWord[]
    offset = 0
    for sites in words
        push!(
            state_symbols,
            PauliWord([
                (site, axes[offset + index])
                for (index, site) in enumerate(sites)
            ]),
        )
        offset += length(sites)
    end
    return moment_key(state_symbols)
end

function axis_assignments(rank::Int)
    rank >= 0 || throw(ArgumentError("tensor rank must be nonnegative"))
    assignments = Vector{Vector{UInt8}}()
    current = fill(UInt8(1), rank)
    function enumerate!(position::Int)
        if position > rank
            push!(assignments, copy(current))
            return
        end
        for axis in UInt8(1):UInt8(3)
            current[position] = axis
            enumerate!(position + 1)
        end
    end
    enumerate!(1)
    return assignments
end

function invariant_pairing_row(axes::Vector{UInt8})
    rank = length(axes)
    if rank == 0
        return ExactRational[1]
    elseif rank == 2
        return ExactRational[axes[1] == axes[2] ? 1 : 0]
    elseif rank == 4
        return ExactRational[
            axes[1] == axes[2] && axes[3] == axes[4] ? 1 : 0,
            axes[1] == axes[3] && axes[2] == axes[4] ? 1 : 0,
            axes[1] == axes[4] && axes[2] == axes[3] ? 1 : 0,
        ]
    end
    throw(
        ArgumentError(
            "continuous-spin quotient expects tensor rank 0, 2, or 4",
        ),
    )
end

function even_axis_parities(axes::Vector{UInt8})
    return all(
        iseven(count(==(axis), axes))
        for axis in UInt8(1):UInt8(3)
    )
end

function exact_rref(matrix::AbstractMatrix{ExactRational})
    reduced = Matrix{ExactRational}(matrix)
    pivots = Int[]
    row = 1
    for column in axes(reduced, 2)
        row > size(reduced, 1) && break
        relative = findfirst(
            index -> !iszero(reduced[index, column]),
            row:size(reduced, 1),
        )
        isnothing(relative) && continue
        pivot_row = row + something(relative) - 1
        if pivot_row != row
            reduced[row, :], reduced[pivot_row, :] =
                copy(reduced[pivot_row, :]), copy(reduced[row, :])
        end
        reduced[row, :] ./= reduced[row, column]
        for other in axes(reduced, 1)
            other == row && continue
            scale = reduced[other, column]
            iszero(scale) && continue
            reduced[other, :] .-= scale .* reduced[row, :]
        end
        push!(pivots, column)
        row += 1
    end
    return reduced, pivots
end

function exact_rank(matrix::AbstractMatrix{ExactRational})
    _, pivots = exact_rref(matrix)
    return length(pivots)
end

function exact_nullspace(matrix::AbstractMatrix{ExactRational})
    reduced, pivots = exact_rref(matrix)
    free = setdiff(collect(axes(matrix, 2)), pivots)
    basis = zeros(ExactRational, size(matrix, 2), length(free))
    for (basis_column, free_column) in enumerate(free)
        basis[free_column, basis_column] = 1
        for (pivot_row, pivot_column) in enumerate(pivots)
            basis[pivot_column, basis_column] =
                -reduced[pivot_row, free_column]
        end
    end
    return basis
end

function exact_inverse(matrix::AbstractMatrix{ExactRational})
    size(matrix, 1) == size(matrix, 2) ||
        throw(ArgumentError("exact inverse requires a square matrix"))
    dimension = size(matrix, 1)
    augmented = hcat(
        Matrix{ExactRational}(matrix),
        Matrix{ExactRational}(I, dimension, dimension),
    )
    reduced, pivots = exact_rref(augmented[:, 1:dimension])
    length(pivots) == dimension ||
        error("pivot coordinate matrix is singular")

    # Replay Gauss-Jordan on the full augmented matrix.
    work = copy(augmented)
    row = 1
    for column in 1:dimension
        pivot_row = findfirst(
            index -> !iszero(work[index, column]),
            row:dimension,
        )
        isnothing(pivot_row) &&
            error("pivot coordinate matrix is singular")
        selected = row + something(pivot_row) - 1
        if selected != row
            work[row, :], work[selected, :] =
                copy(work[selected, :]), copy(work[row, :])
        end
        work[row, :] ./= work[row, column]
        for other in 1:dimension
            other == row && continue
            scale = work[other, column]
            iszero(scale) && continue
            work[other, :] .-= scale .* work[row, :]
        end
        row += 1
    end
    reduced == Matrix{ExactRational}(I, dimension, dimension) ||
        error("internal exact inverse reduction mismatch")
    return work[:, (dimension + 1):(2dimension)]
end

function independent_row_indices(matrix::AbstractMatrix{ExactRational})
    selected = Int[]
    current = zeros(ExactRational, 0, size(matrix, 2))
    rank = 0
    for row in axes(matrix, 1)
        candidate = vcat(current, reshape(matrix[row, :], 1, :))
        candidate_rank = exact_rank(candidate)
        candidate_rank == rank && continue
        push!(selected, row)
        current = candidate
        rank = candidate_rank
        rank == size(matrix, 2) && break
    end
    return selected
end

function unique_rows(rows::Vector{Vector{ExactRational}})
    result = Vector{Vector{ExactRational}}()
    for row in rows
        row in result || push!(result, row)
    end
    return result
end

"""Exact substitution of every discrete-spin moment by invariant pivots."""
struct ContinuousSpinMomentQuotient
    substitutions::Dict{MomentKey,ExactLinearPolynomial}
    moments::Vector{MomentKey}
    skeleton_count::Int
    rank_two_skeleton_count::Int
    rank_four_skeleton_count::Int
    parameter_count_by_skeleton::Dict{String,Int}
end

function skeleton_substitutions(
    source_moments::Vector{MomentKey},
    full_spin_representatives::Dict{MomentKey,MomentKey},
    words::Vector{Vector{Int}},
)
    rank = sum(length, words; init=0)
    source_set = Set(source_moments)
    rows_by_representative =
        Dict{MomentKey,Vector{Vector{ExactRational}}}()
    for axes in axis_assignments(rank)
        row = invariant_pairing_row(axes)
        all(iszero, row) && continue
        even_axis_parities(axes) ||
            error("nonzero delta pairing has odd axis parity")
        component = assigned_moment(words, axes)
        haskey(full_spin_representatives, component) ||
            error("invariant component is outside full-spin inventory")
        representative = full_spin_representatives[component]
        representative in source_set ||
            error("full-spin representative is outside isotypic inventory")
        skeleton_string(representative) == skeleton_string(words) ||
            error("spin representative changed the moment skeleton")
        push!(
            get!(
                rows_by_representative,
                representative,
                Vector{Vector{ExactRational}}(),
            ),
            row,
        )
    end

    expected = sort!(
        filter(
            key -> skeleton_string(key) == skeleton_string(words),
            source_moments,
        );
        by=key -> key.canonical,
    )
    Set(keys(rows_by_representative)) == Set(expected) ||
        error("delta pairings did not cover one moment skeleton")

    constraint_rows = Vector{Vector{ExactRational}}()
    canonical_rows = Dict{MomentKey,Vector{ExactRational}}()
    for representative in expected
        rows = unique_rows(rows_by_representative[representative])
        canonical_rows[representative] = first(rows)
        for row in Iterators.drop(rows, 1)
            push!(constraint_rows, row - first(rows))
        end
    end
    tensor_dimension = length(first(Base.values(canonical_rows)))
    constraints = isempty(constraint_rows) ?
        zeros(ExactRational, 0, tensor_dimension) :
        reduce(vcat, (reshape(row, 1, :) for row in constraint_rows))
    invariant_basis = exact_nullspace(constraints)
    parameter_dimension = size(invariant_basis, 2)
    parameter_dimension > 0 ||
        error("moment skeleton has no invariant coordinate")

    value_matrix = reduce(
        vcat,
        (
            reshape(
                transpose(canonical_rows[representative]) *
                invariant_basis,
                1,
                :,
            )
            for representative in expected
        ),
    )
    pivots = independent_row_indices(value_matrix)
    length(pivots) == parameter_dimension ||
        error("failed to select invariant pivot moments")
    pivot_moments = expected[pivots]
    pivot_matrix = value_matrix[pivots, :]
    coordinate_map = value_matrix * exact_inverse(pivot_matrix)

    substitutions = Dict{MomentKey,ExactLinearPolynomial}()
    for (row, representative) in enumerate(expected)
        polynomial = ExactLinearPolynomial()
        for (column, pivot) in enumerate(pivot_moments)
            add_term!(polynomial, pivot, coordinate_map[row, column])
        end
        substitutions[representative] = polynomial
    end
    for pivot in pivot_moments
        substitutions[pivot] ==
            ExactLinearPolynomial(Dict(
                pivot => Complex{ExactRational}(1, 0),
            )) || error("invariant pivot does not map to itself")
    end
    return substitutions, pivot_moments
end

function continuous_spin_moment_quotient(
    assembly::FullSpinIsotypicReducedPrimalAssembly,
)
    source_moments = assembly.moments
    all(moment_degree(key) in (0, 2, 4) for key in source_moments) ||
        error("continuous-spin quotient found an unsupported moment degree")
    by_skeleton = Dict{String,Vector{MomentKey}}()
    words_by_skeleton = Dict{String,Vector{Vector{Int}}}()
    for key in source_moments
        words = skeleton_words(key)
        skeleton = skeleton_string(words)
        push!(get!(by_skeleton, skeleton, MomentKey[]), key)
        words_by_skeleton[skeleton] = words
    end
    full_spin_representatives =
        assembly.source.source.quotient.representatives
    substitutions = Dict{MomentKey,ExactLinearPolynomial}()
    pivots = MomentKey[]
    parameter_count = Dict{String,Int}()
    rank_two_count = 0
    rank_four_count = 0
    for skeleton in sort!(collect(keys(by_skeleton)))
        source = sort!(
            by_skeleton[skeleton];
            by=key -> key.canonical,
        )
        local_substitutions, local_pivots = skeleton_substitutions(
            source,
            full_spin_representatives,
            words_by_skeleton[skeleton],
        )
        merge!(substitutions, local_substitutions)
        append!(pivots, local_pivots)
        parameter_count[skeleton] = length(local_pivots)
        rank = moment_degree(first(source))
        rank_two_count += rank == 2
        rank_four_count += rank == 4
    end
    Set(keys(substitutions)) == Set(source_moments) ||
        error("continuous-spin substitution is incomplete")
    ordered_pivots = sort!(
        unique(pivots);
        by=key -> (moment_degree(key), key.canonical),
    )
    first(ordered_pivots) == moment_key() ||
        error("identity is not the first continuous-spin pivot")
    return ContinuousSpinMomentQuotient(
        substitutions,
        ordered_pivots,
        length(by_skeleton),
        rank_two_count,
        rank_four_count,
        parameter_count,
    )
end

function continuous_spin_quotient_projection(
    polynomial::ExactLinearPolynomial,
    quotient::ContinuousSpinMomentQuotient,
)
    result = ExactLinearPolynomial()
    for (key, coefficient) in polynomial.terms
        haskey(quotient.substitutions, key) ||
            error("polynomial moment is outside continuous-spin quotient")
        add_scaled!(result, quotient.substitutions[key], coefficient)
    end
    return result
end

function component_polynomial(
    words::Vector{Vector{Int}},
    axes::Vector{UInt8},
    quotient::ContinuousSpinMomentQuotient,
    full_spin_representatives::Dict{MomentKey,MomentKey},
)
    even_axis_parities(axes) || return ExactLinearPolynomial()
    component = assigned_moment(words, axes)
    haskey(full_spin_representatives, component) ||
        error("rotation component is outside full-spin inventory")
    representative = full_spin_representatives[component]
    haskey(quotient.substitutions, representative) ||
        error("rotation representative lacks a substitution")
    return quotient.substitutions[representative]
end

function rational_rotation_is_invariant(
    assembly::FullSpinIsotypicReducedPrimalAssembly,
    quotient::ContinuousSpinMomentQuotient,
)
    transpose(RATIONAL_ROTATION) * RATIONAL_ROTATION ==
        Matrix{ExactRational}(I, 3, 3) ||
        error("declared rational rotation is not orthogonal")
    determinant = det(RATIONAL_ROTATION)
    determinant == 1 ||
        error("declared rational rotation is not proper")
    full_spin_representatives =
        assembly.source.source.quotient.representatives
    words_by_skeleton = Dict(
        skeleton_string(key) => skeleton_words(key)
        for key in assembly.moments
    )
    exact = true
    check_count = 0
    for skeleton in sort!(collect(keys(words_by_skeleton)))
        words = words_by_skeleton[skeleton]
        rank = sum(length, words; init=0)
        assignments = axis_assignments(rank)
        components = ExactLinearPolynomial[
            component_polynomial(
                words,
                axes,
                quotient,
                full_spin_representatives,
            )
            for axes in assignments
        ]
        for (target_index, target_axes) in enumerate(assignments)
            original = components[target_index]
            rotated = ExactLinearPolynomial()
            for (source_index, source_axes) in enumerate(assignments)
                coefficient = prod(
                    RATIONAL_ROTATION[
                        Int(target_axes[index]),
                        Int(source_axes[index]),
                    ]
                    for index in eachindex(target_axes);
                    init=one(ExactRational),
                )
                iszero(coefficient) && continue
                add_scaled!(
                    rotated,
                    components[source_index],
                    coefficient,
                )
            end
            exact &= rotated == original
            check_count += 1
        end
    end
    return (
        exact=exact,
        component_check_count=check_count,
        rotation=RATIONAL_ROTATION,
        rotation_orthogonal=true,
        rotation_determinant=determinant,
    )
end

function continuous_spin_moment_truth(
    assembly::FullSpinIsotypicReducedPrimalAssembly,
)
    quotient = continuous_spin_moment_quotient(assembly)
    rotation = rational_rotation_is_invariant(assembly, quotient)
    substitutions_complete =
        Set(keys(quotient.substitutions)) == Set(assembly.moments)
    pivots_exact = all(
        quotient.substitutions[pivot] ==
        ExactLinearPolynomial(Dict(
            pivot => Complex{ExactRational}(1, 0),
        ))
        for pivot in quotient.moments
    )
    exact =
        substitutions_complete &&
        pivots_exact &&
        rotation.exact &&
        rotation.rotation_orthogonal &&
        rotation.rotation_determinant == 1
    return (
        exact=exact,
        source_moment_count=length(assembly.moments),
        invariant_moment_count=length(quotient.moments),
        eliminated_moment_count=
            length(assembly.moments) - length(quotient.moments),
        skeleton_count=quotient.skeleton_count,
        rank_two_skeleton_count=quotient.rank_two_skeleton_count,
        rank_four_skeleton_count=quotient.rank_four_skeleton_count,
        substitutions_complete=substitutions_complete,
        pivots_exact=pivots_exact,
        rational_rotation_invariant=rotation.exact,
        rational_rotation_component_check_count=
            rotation.component_check_count,
        rational_rotation_orthogonal=rotation.rotation_orthogonal,
        rational_rotation_determinant=rotation.rotation_determinant,
        quotient=quotient,
    )
end

struct ContinuousSpinReducedPrimalAssembly{A}
    schema::String
    source::A
    quotient::ContinuousSpinMomentQuotient
    positive_blocks::Vector{FullSpinIsotypicPSDBlock}
    gap_blocks::Vector{FullSpinIsotypicPSDBlock}
    equalities::Vector{ExactLinearPolynomial}
    moments::Vector{MomentKey}
    coefficient_map_sha256::String
    assembly_sha256::String
end

function continuous_spin_block_entry(
    assembly::ContinuousSpinReducedPrimalAssembly,
    block::FullSpinIsotypicPSDBlock,
    left,
    right,
)
    source = full_spin_isotypic_block_entry(
        assembly.source,
        block,
        left,
        right,
    )
    return continuous_spin_quotient_projection(source, assembly.quotient)
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

function block_label(block::FullSpinIsotypicPSDBlock)
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

function assemble_continuous_spin_reduced_primal(
    source::FullSpinIsotypicReducedPrimalAssembly;
    verify_truth::Bool=true,
)
    truth = verify_truth ? continuous_spin_moment_truth(source) : nothing
    if verify_truth
        something(truth).exact ||
            error("continuous-spin moment truth gate failed")
    end
    quotient = verify_truth ?
        something(truth).quotient :
        continuous_spin_moment_quotient(source)
    equalities = ExactLinearPolynomial[
        continuous_spin_quotient_projection(equality, quotient)
        for equality in source.equalities
    ]
    positive_blocks = copy(source.positive_blocks)
    gap_blocks = copy(source.gap_blocks)
    provisional = ContinuousSpinReducedPrimalAssembly(
        CONTINUOUS_SPIN_MOMENT_REDUCTION_SCHEMA,
        source,
        quotient,
        positive_blocks,
        gap_blocks,
        equalities,
        quotient.moments,
        "",
        "",
    )

    used_moments = Set{MomentKey}([moment_key()])
    coefficient_records = String[]
    for block in [positive_blocks; gap_blocks]
        for row in eachindex(block.rows), column in row:length(block.rows)
            polynomial = continuous_spin_block_entry(
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
                        block_label(block),
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
    used_moments == Set(quotient.moments) ||
        error("continuous-spin coefficient maps left unused pivots")

    coefficient_sha256 = fingerprint_records(
        "continuous-spin-isotypic-real-upper-triangle-coefficients-v1",
        coefficient_records,
    )
    equality_sha256 = fingerprint_records(
        "continuous-spin-isotypic-real-equalities-v1",
        canonical_polynomial_string.(equalities),
    )
    final_sha256 = fingerprint_records(
        CONTINUOUS_SPIN_MOMENT_REDUCTION_SCHEMA,
        [
            "source=" * source.assembly_sha256,
            "moments=" * join(
                (key.canonical for key in quotient.moments),
                "\n",
            ),
            "equalities=" * equality_sha256,
            "coefficients=" * coefficient_sha256,
        ],
    )
    return ContinuousSpinReducedPrimalAssembly(
        CONTINUOUS_SPIN_MOMENT_REDUCTION_SCHEMA,
        source,
        quotient,
        positive_blocks,
        gap_blocks,
        equalities,
        quotient.moments,
        coefficient_sha256,
        final_sha256,
    )
end

triangle_count(dimension::Int) =
    dimension * (dimension + 1) ÷ 2

function continuous_spin_reduced_assembly_report(
    assembly::ContinuousSpinReducedPrimalAssembly,
)
    positive_dimensions = length.(getfield.(assembly.positive_blocks, :rows))
    gap_dimensions = length.(getfield.(assembly.gap_blocks, :rows))
    dimensions = [positive_dimensions; gap_dimensions]
    return (
        source_isotypic_moments=length(assembly.source.moments),
        continuous_spin_moments=length(assembly.moments),
        eliminated_continuous_spin_moments=
            length(assembly.source.moments) - length(assembly.moments),
        positive_block_dimensions=positive_dimensions,
        gap_block_dimensions=gap_dimensions,
        equality_count=length(assembly.equalities),
        real_psd_triangle_entries=sum(triangle_count, dimensions),
        maximum_psd_side_dimension=maximum(dimensions),
        coefficient_map_sha256=assembly.coefficient_map_sha256,
        assembly_sha256=assembly.assembly_sha256,
    )
end

end
