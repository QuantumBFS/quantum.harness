module SpinAxisInvolutionReduction

using SHA
using ..SquareJ1J2Prototype:
    PauliWord
using ..PrimalGapSymbolics:
    ExactLinearPolynomial,
    MomentKey,
    add_term!,
    moment_key,
    moment_degree,
    canonical_polynomial_string,
    polynomial_sha256
using ..ExactSymmetryReduction:
    V4Character,
    canonical_real_equalities
using ..ReducedPrimalGapAssembly:
    ReducedPSDRow,
    ReducedPSDBlock
using ..ConjugationSymmetryReduction:
    ConjugationReducedPrimalAssembly,
    conjugation_real_block_entry,
    polynomial_row_rank

export SPIN_AXIS_INVOLUTION_SCHEMA,
       SpinAxisMomentQuotient,
       SpinAxisCombinationRow,
       SpinAxisReducedPSDBlock,
       SpinAxisReducedPrimalAssembly,
       spin_axis_involution,
       spin_axis_character,
       spin_axis_polynomial_action,
       spin_axis_quotient_projection,
       spin_axis_block_entry,
       spin_axis_reduction_truth,
       assemble_spin_axis_reduced_primal,
       spin_axis_reduced_assembly_report

const SPIN_AXIS_INVOLUTION_SCHEMA =
    "primal-gap-exact-v4-conjugation-real-spin-axis-involution-v1"

"""
The order-two global spin rotation used after conjugation realification.

It is the π rotation about `(x+z)/sqrt(2)`: `X -> Z`, `Z -> X`, and
`Y -> -Y`. The returned integer is the exact sign multiplying the transformed
canonical Pauli word.
"""
function spin_axis_involution(word::PauliWord)
    sign = isodd(count(operation -> operation[2] == 2, word.ops)) ? -1 : 1
    transformed = PauliWord([
        (
            site,
            axis == 1 ? UInt8(3) :
            axis == 3 ? UInt8(1) :
            UInt8(2),
        )
        for (site, axis) in word.ops
    ])
    return sign, transformed
end

"""
Action on the V4 character labels.

The trivial and Y character sectors are stable. The X and Z character
sectors are exchanged.
"""
spin_axis_character(character::V4Character) =
    V4Character(xor(character.rx, character.ry), character.ry)

function transformed_moment_canonical(key::MomentKey)
    isempty(key.canonical) && return ""
    symbols = split(key.canonical, '|')
    transformed = String[
        String(map(
            character ->
                character == 'X' ? 'Z' :
                character == 'Z' ? 'X' :
                character,
            collect(symbol),
        ))
        for symbol in symbols
    ]
    sort!(transformed)
    return join(transformed, "|")
end

moment_involution_sign(key::MomentKey) =
    isodd(count(==('Y'), key.canonical)) ? -1 : 1

"""
Exact orbit map on the conjugation-even, V4-invariant moment inventory.

For every nonzero orbit member, `representatives[key] == (s, rep)` means
that an invariant functional obeys `x_key = s * x_rep`. A moment fixed with
sign minus is instead listed in `forced_zero`.
"""
struct SpinAxisMomentQuotient
    action::Dict{MomentKey,Tuple{Int,MomentKey}}
    representatives::Dict{MomentKey,Tuple{Int,MomentKey}}
    forced_zero::Set{MomentKey}
    moments::Vector{MomentKey}
end

function build_spin_axis_moment_quotient(
    moments::Vector{MomentKey},
)
    length(unique(moments)) == length(moments) ||
        throw(ArgumentError("source moment inventory contains duplicates"))
    by_canonical = Dict(key.canonical => key for key in moments)
    length(by_canonical) == length(moments) ||
        throw(ArgumentError("source moment canonical strings are not unique"))

    action = Dict{MomentKey,Tuple{Int,MomentKey}}()
    for key in moments
        target_canonical = transformed_moment_canonical(key)
        haskey(by_canonical, target_canonical) ||
            error("moment inventory is not closed under the spin-axis involution")
        target = by_canonical[target_canonical]
        moment_degree(target) == moment_degree(key) ||
            error("spin-axis involution changed moment degree")
        action[key] = (moment_involution_sign(key), target)
    end
    for key in moments
        sign, target = action[key]
        target_sign, repeated = action[target]
        sign * target_sign == 1 && repeated == key ||
            error("spin-axis moment action is not an involution")
    end

    representatives = Dict{MomentKey,Tuple{Int,MomentKey}}()
    forced_zero = Set{MomentKey}()
    representative_set = Set{MomentKey}()
    for key in moments
        sign, target = action[key]
        if target == key && sign == -1
            push!(forced_zero, key)
            continue
        end
        representative = isless(target, key) ? target : key
        relation_sign = key == representative ? 1 : sign
        representatives[key] = (relation_sign, representative)
        push!(representative_set, representative)
    end
    ordered = sort!(
        collect(representative_set);
        by=key -> (moment_degree(key), key.canonical),
    )
    first(ordered) == moment_key() ||
        error("identity moment is not first after spin-axis quotient")
    return SpinAxisMomentQuotient(
        action,
        representatives,
        forced_zero,
        ordered,
    )
end

"""Apply the physical spin rotation to one exact moment polynomial."""
function spin_axis_polynomial_action(
    polynomial::ExactLinearPolynomial,
    quotient::SpinAxisMomentQuotient,
)
    result = ExactLinearPolynomial()
    for (key, coefficient) in polynomial.terms
        haskey(quotient.action, key) ||
            error("polynomial contains a moment outside the action inventory")
        sign, target = quotient.action[key]
        add_term!(result, target, sign * coefficient)
    end
    return result
end

"""Restrict one exact polynomial to invariant moment coordinates."""
function spin_axis_quotient_projection(
    polynomial::ExactLinearPolynomial,
    quotient::SpinAxisMomentQuotient,
)
    result = ExactLinearPolynomial()
    for (key, coefficient) in polynomial.terms
        key in quotient.forced_zero && continue
        haskey(quotient.representatives, key) ||
            error("polynomial contains a moment outside the quotient inventory")
        sign, representative = quotient.representatives[key]
        add_term!(result, representative, sign * coefficient)
    end
    return result
end

"""
One exact row of an involution eigenspace basis.

The integer coefficients deliberately omit normalization. Taken together,
the plus and minus rows form an invertible exact congruence, which is all PSD
equivalence requires.
"""
struct SpinAxisCombinationRow
    source_indices::Vector{Int}
    coefficients::Vector{Int}

    function SpinAxisCombinationRow(
        source_indices::Vector{Int},
        coefficients::Vector{Int},
    )
        length(source_indices) == length(coefficients) ||
            throw(ArgumentError("combination row index/coefficient mismatch"))
        length(source_indices) in (1, 2) ||
            throw(ArgumentError("involution rows contain one or two terms"))
        length(unique(source_indices)) == length(source_indices) ||
            throw(ArgumentError("combination row repeats a source index"))
        all(coefficient -> coefficient in (-1, 1), coefficients) ||
            throw(ArgumentError("involution row coefficients must be ±1"))
        new(source_indices, coefficients)
    end
end

"""
One PSD block after the exact spin-axis quotient.

`kind` is `:eigen_plus`, `:eigen_minus`, or `:orbit_representative`.
"""
struct SpinAxisReducedPSDBlock
    source_block::ReducedPSDBlock
    kind::Symbol
    rows::Vector{SpinAxisCombinationRow}

    function SpinAxisReducedPSDBlock(
        source_block::ReducedPSDBlock,
        kind::Symbol,
        rows::Vector{SpinAxisCombinationRow},
    )
        kind in (:eigen_plus, :eigen_minus, :orbit_representative) ||
            throw(ArgumentError("unsupported spin-axis block kind"))
        isempty(rows) &&
            throw(ArgumentError("empty spin-axis PSD blocks must be omitted"))
        all(
            row -> all(
                index -> 1 <= index <= length(source_block.rows),
                row.source_indices,
            ),
            rows,
        ) || throw(ArgumentError("combination row index is out of range"))
        new(source_block, kind, rows)
    end
end

block_key(block::ReducedPSDBlock) = (
    block.role,
    block.family,
    block.character.rx,
    block.character.ry,
)

function row_action(
    block::ReducedPSDBlock,
)
    indices = Dict(row.word => index for (index, row) in enumerate(block.rows))
    length(indices) == length(block.rows) ||
        error("source PSD block contains duplicate row words")
    permutation = Vector{Int}(undef, length(block.rows))
    signs = Vector{Int}(undef, length(block.rows))
    for (index, row) in enumerate(block.rows)
        sign, target = spin_axis_involution(row.word)
        haskey(indices, target) ||
            error("stable source block is not closed under row involution")
        permutation[index] = indices[target]
        signs[index] = sign
    end
    for index in eachindex(permutation)
        target = permutation[index]
        permutation[target] == index &&
            signs[index] * signs[target] == 1 ||
            error("row action is not an involution")
    end
    return signs, permutation
end

function stable_eigenspace_blocks(
    block::ReducedPSDBlock,
)
    spin_axis_character(block.character) == block.character ||
        throw(ArgumentError("requested eigenspaces for an exchanged block"))
    signs, permutation = row_action(block)
    visited = falses(length(block.rows))
    plus = SpinAxisCombinationRow[]
    minus = SpinAxisCombinationRow[]
    for index in eachindex(block.rows)
        visited[index] && continue
        target = permutation[index]
        if target == index
            destination = signs[index] == 1 ? plus : minus
            push!(
                destination,
                SpinAxisCombinationRow([index], [1]),
            )
            visited[index] = true
            continue
        end
        visited[target] &&
            error("row orbit was visited before its representative")
        sign = signs[index]
        push!(
            plus,
            SpinAxisCombinationRow([index, target], [1, sign]),
        )
        push!(
            minus,
            SpinAxisCombinationRow([index, target], [1, -sign]),
        )
        visited[index] = true
        visited[target] = true
    end
    blocks = SpinAxisReducedPSDBlock[]
    isempty(plus) || push!(
        blocks,
        SpinAxisReducedPSDBlock(block, :eigen_plus, plus),
    )
    isempty(minus) || push!(
        blocks,
        SpinAxisReducedPSDBlock(block, :eigen_minus, minus),
    )
    return blocks
end

function spin_axis_blocks(
    source_blocks::Vector{ReducedPSDBlock},
)
    by_key = Dict(block_key(block) => block for block in source_blocks)
    length(by_key) == length(source_blocks) ||
        error("source block descriptors are not unique")
    result = SpinAxisReducedPSDBlock[]
    for block in source_blocks
        target_character = spin_axis_character(block.character)
        target_key = (
            block.role,
            block.family,
            target_character.rx,
            target_character.ry,
        )
        haskey(by_key, target_key) ||
            error("source PSD blocks are not closed under spin-axis symmetry")
        target = by_key[target_key]
        length(target.rows) == length(block.rows) ||
            error("exchanged source PSD blocks have different dimensions")
        if target_character == block.character
            append!(result, stable_eigenspace_blocks(block))
        elseif isless(block.character, target_character)
            rows = SpinAxisCombinationRow[
                SpinAxisCombinationRow([index], [1])
                for index in eachindex(block.rows)
            ]
            push!(
                result,
                SpinAxisReducedPSDBlock(
                    block,
                    :orbit_representative,
                    rows,
                ),
            )
        end
    end
    return result
end

"""
Exact restriction of one congruence-block entry to invariant moments.
"""
function spin_axis_block_entry(
    assembly,
    block::SpinAxisReducedPSDBlock,
    left::SpinAxisCombinationRow,
    right::SpinAxisCombinationRow,
)
    polynomial = ExactLinearPolynomial()
    for (left_position, left_index) in enumerate(left.source_indices)
        for (right_position, right_index) in enumerate(right.source_indices)
            source_entry = conjugation_real_block_entry(
                assembly.source,
                block.source_block,
                block.source_block.rows[left_index],
                block.source_block.rows[right_index],
            )
            scale =
                left.coefficients[left_position] *
                right.coefficients[right_position]
            for (key, coefficient) in source_entry.terms
                add_term!(polynomial, key, scale * coefficient)
            end
        end
    end
    projected = spin_axis_quotient_projection(
        polynomial,
        assembly.quotient,
    )
    all(iszero ∘ imag, values(projected.terms)) ||
        error("spin-axis block entry is not exactly real")
    return projected
end

function hamiltonian_is_invariant(source)
    original = Dict{PauliWord,Any}()
    transformed = Dict{PauliWord,Any}()
    for term in source.source.source.hamiltonian_terms
        original[term.word] =
            get(original, term.word, zero(term.coefficient)) +
            term.coefficient
        sign, word = spin_axis_involution(term.word)
        transformed[word] =
            get(transformed, word, zero(term.coefficient)) +
            sign * term.coefficient
    end
    return original == transformed
end

function source_block_covariance(
    source::ConjugationReducedPrimalAssembly,
    quotient::SpinAxisMomentQuotient,
)
    blocks = [source.source.positive_blocks; source.source.gap_blocks]
    by_key = Dict(block_key(block) => block for block in blocks)
    coefficient_count = 0
    covariant = true
    for block in blocks
        target_character = spin_axis_character(block.character)
        target = by_key[(
            block.role,
            block.family,
            target_character.rx,
            target_character.ry,
        )]
        target_indices = Dict(
            row.word => index
            for (index, row) in enumerate(target.rows)
        )
        for row in eachindex(block.rows), column in row:length(block.rows)
            left_sign, left_word =
                spin_axis_involution(block.rows[row].word)
            right_sign, right_word =
                spin_axis_involution(block.rows[column].word)
            haskey(target_indices, left_word) &&
                haskey(target_indices, right_word) ||
                error("spin-axis covariance target row is missing")
            polynomial = conjugation_real_block_entry(
                source,
                block,
                block.rows[row],
                block.rows[column],
            )
            target_polynomial = conjugation_real_block_entry(
                source,
                target,
                target.rows[target_indices[left_word]],
                target.rows[target_indices[right_word]],
            )
            expected =
                (left_sign * right_sign) * target_polynomial
            covariant &=
                spin_axis_polynomial_action(polynomial, quotient) ==
                expected
            coefficient_count += 1
        end
    end
    return covariant, coefficient_count
end

function stable_cross_blocks_zero(
    source::ConjugationReducedPrimalAssembly,
    quotient::SpinAxisMomentQuotient,
)
    provisional = (
        source=source,
        quotient=quotient,
    )
    exact = true
    entry_count = 0
    for source_block in [
        source.source.positive_blocks;
        source.source.gap_blocks
    ]
        spin_axis_character(source_block.character) ==
            source_block.character || continue
        blocks = stable_eigenspace_blocks(source_block)
        plus = findfirst(block -> block.kind == :eigen_plus, blocks)
        minus = findfirst(block -> block.kind == :eigen_minus, blocks)
        if isnothing(plus) || isnothing(minus)
            continue
        end
        plus_block = blocks[something(plus)]
        minus_block = blocks[something(minus)]
        for left in plus_block.rows, right in minus_block.rows
            exact &= iszero(spin_axis_block_entry(
                provisional,
                plus_block,
                left,
                right,
            ))
            entry_count += 1
        end
    end
    return exact, entry_count
end

function equality_space_is_invariant(
    source::ConjugationReducedPrimalAssembly,
    quotient::SpinAxisMomentQuotient,
)
    transformed = ExactLinearPolynomial[
        spin_axis_polynomial_action(equality, quotient)
        for equality in source.equalities
    ]
    return polynomial_row_rank(source.equalities) ==
           polynomial_row_rank([source.equalities; transformed])
end

"""
Exhaustive exact gates for the commuting spin-axis involution.
"""
function spin_axis_reduction_truth(
    source::ConjugationReducedPrimalAssembly,
)
    quotient = build_spin_axis_moment_quotient(source.moments)
    coefficient_covariant, coefficient_count =
        source_block_covariance(source, quotient)
    cross_blocks_zero, cross_entry_count =
        stable_cross_blocks_zero(source, quotient)
    equality_invariant =
        equality_space_is_invariant(source, quotient)
    hamiltonian_invariant = hamiltonian_is_invariant(source)
    return (
        exact=hamiltonian_invariant &&
              coefficient_covariant &&
              cross_blocks_zero &&
              equality_invariant,
        hamiltonian_invariant=hamiltonian_invariant,
        coefficient_covariant=coefficient_covariant,
        coefficient_count=coefficient_count,
        stable_cross_blocks_zero=cross_blocks_zero,
        stable_cross_entry_count=cross_entry_count,
        equality_space_invariant=equality_invariant,
        quotient=quotient,
    )
end

"""
Exact real-cone representation after quotienting the spin-axis involution.
"""
struct SpinAxisReducedPrimalAssembly{A}
    schema::String
    source::A
    quotient::SpinAxisMomentQuotient
    positive_blocks::Vector{SpinAxisReducedPSDBlock}
    gap_blocks::Vector{SpinAxisReducedPSDBlock}
    equalities::Vector{ExactLinearPolynomial}
    moments::Vector{MomentKey}
    coefficient_map_sha256::String
    assembly_sha256::String
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

block_character_label(block::SpinAxisReducedPSDBlock) =
    string(
        "rx",
        Int(block.source_block.character.rx),
        "-ry",
        Int(block.source_block.character.ry),
    )

function assemble_spin_axis_reduced_primal(
    source::ConjugationReducedPrimalAssembly;
    verify_truth::Bool=true,
)
    truth = verify_truth ? spin_axis_reduction_truth(source) : nothing
    quotient = verify_truth ?
        something(truth).quotient :
        build_spin_axis_moment_quotient(source.moments)
    if verify_truth
        something(truth).exact ||
            error("spin-axis exact-reduction truth check failed")
    end

    positive_blocks = spin_axis_blocks(source.source.positive_blocks)
    gap_blocks = spin_axis_blocks(source.source.gap_blocks)
    equalities = canonical_real_equalities(ExactLinearPolynomial[
        spin_axis_quotient_projection(equality, quotient)
        for equality in source.equalities
    ])
    provisional = SpinAxisReducedPrimalAssembly(
        SPIN_AXIS_INVOLUTION_SCHEMA,
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
            polynomial = spin_axis_block_entry(
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
                        block.source_block.role,
                        block.source_block.family,
                        block_character_label(block),
                        block.kind,
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
        error("spin-axis coefficient maps do not reproduce the quotient inventory")

    coefficient_sha256 = fingerprint_records(
        "spin-axis-real-upper-triangle-coefficients-v1",
        coefficient_records,
    )
    equality_sha256 = fingerprint_records(
        "spin-axis-real-equalities-v1",
        canonical_polynomial_string.(equalities),
    )
    block_records = String[
        join(
            (
                block.source_block.role,
                block.source_block.family,
                block_character_label(block),
                block.kind,
                length(block.rows),
            ),
            ":",
        )
        for block in [positive_blocks; gap_blocks]
    ]
    final_sha256 = fingerprint_records(
        SPIN_AXIS_INVOLUTION_SCHEMA,
        [
            "source=" * source.assembly_sha256,
            "equalities=" * equality_sha256,
            "moments=" * join(
                (key.canonical for key in quotient.moments),
                "\n",
            ),
            "blocks=" * join(block_records, "\n"),
            "coefficients=" * coefficient_sha256,
        ],
    )
    return SpinAxisReducedPrimalAssembly(
        SPIN_AXIS_INVOLUTION_SCHEMA,
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

function spin_axis_reduced_assembly_report(
    assembly::SpinAxisReducedPrimalAssembly,
)
    positive_dimensions = length.(getfield.(assembly.positive_blocks, :rows))
    gap_dimensions = length.(getfield.(assembly.gap_blocks, :rows))
    all_dimensions = [positive_dimensions; gap_dimensions]
    return (
        source_moments=length(assembly.source.source.source.moments),
        v4_moments=length(assembly.source.source.moments),
        conjugation_real_moments=length(assembly.source.moments),
        spin_axis_moments=length(assembly.moments),
        eliminated_spin_axis_moments=
            length(assembly.source.moments) - length(assembly.moments),
        forced_zero_moments=length(assembly.quotient.forced_zero),
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
