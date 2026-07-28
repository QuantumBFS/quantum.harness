module FullSpinPermutationReduction

using ..SquareJ1J2Prototype:
    PauliWord
using ..PrimalGapSymbolics:
    ExactLinearPolynomial,
    MomentKey,
    add_term!,
    moment_degree
using ..ExactSymmetryReduction:
    V4Character
using ..ReducedPrimalGapAssembly:
    ReducedPSDBlock,
    reduced_block_entry
using ..ConjugationSymmetryReduction:
    ConjugationReducedPrimalAssembly,
    conjugation_odd,
    polynomial_row_rank

export SpinAxisPermutation,
       SPIN_AXIS_PERMUTATIONS,
       FullSpinMomentQuotient,
       permutation_sign,
       full_spin_permutation,
       full_spin_character,
       full_spin_polynomial_action,
       full_spin_quotient_projection,
       build_full_spin_moment_quotient,
       full_spin_permutation_truth

const SpinAxisPermutation = NTuple{3,UInt8}
const SPIN_AXIS_PERMUTATIONS = SpinAxisPermutation[
    (0x01, 0x02, 0x03),
    (0x01, 0x03, 0x02),
    (0x02, 0x01, 0x03),
    (0x02, 0x03, 0x01),
    (0x03, 0x01, 0x02),
    (0x03, 0x02, 0x01),
]

function permutation_sign(permutation::SpinAxisPermutation)
    inversions = count(
        left > right
        for left_index in 1:2
        for left in (permutation[left_index],)
        for right in permutation[(left_index + 1):3]
    )
    return isodd(inversions) ? -1 : 1
end

"""
Proper-rotation lift of one axis permutation.

Even permutations use their permutation matrix. Odd permutations use its
negative. The lift is a homomorphism into SO(3), and an odd permutation
therefore contributes one minus sign per Pauli factor.
"""
function full_spin_permutation(
    word::PauliWord,
    permutation::SpinAxisPermutation,
)
    parity = permutation_sign(permutation)
    sign = parity == -1 && isodd(length(word)) ? -1 : 1
    transformed = PauliWord([
        (site, permutation[Int(axis)])
        for (site, axis) in word.ops
    ])
    return sign, transformed
end

const TRIVIAL_CHARACTER = V4Character(false, false)
const AXIS_CHARACTERS = (
    V4Character(false, true),
    V4Character(true, false),
    V4Character(true, true),
)

function full_spin_character(
    character::V4Character,
    permutation::SpinAxisPermutation,
)
    character == TRIVIAL_CHARACTER && return character
    source_axis = findfirst(==(character), AXIS_CHARACTERS)
    isnothing(source_axis) &&
        error("unknown nontrivial V4 character")
    return AXIS_CHARACTERS[Int(permutation[something(source_axis)])]
end

function transformed_moment_canonical(
    key::MomentKey,
    permutation::SpinAxisPermutation,
)
    isempty(key.canonical) && return ""
    axis_names = ('X', 'Y', 'Z')
    axis_map = Dict(
        axis_names[index] => axis_names[Int(permutation[index])]
        for index in 1:3
    )
    symbols = split(key.canonical, '|')
    transformed = String[
        String(map(
            character -> get(axis_map, character, character),
            collect(symbol),
        ))
        for symbol in symbols
    ]
    sort!(transformed)
    return join(transformed, "|")
end

function moment_permutation_sign(
    key::MomentKey,
    permutation::SpinAxisPermutation,
)
    return permutation_sign(permutation) == -1 &&
           isodd(moment_degree(key)) ? -1 : 1
end

function build_actions(moments::Vector{MomentKey})
    length(unique(moments)) == length(moments) ||
        throw(ArgumentError("source moment inventory contains duplicates"))
    by_canonical = Dict(key.canonical => key for key in moments)
    length(by_canonical) == length(moments) ||
        throw(ArgumentError("source moment canonical strings are not unique"))
    actions = Vector{Dict{MomentKey,Tuple{Int,MomentKey}}}()
    for permutation in SPIN_AXIS_PERMUTATIONS
        action = Dict{MomentKey,Tuple{Int,MomentKey}}()
        for key in moments
            canonical =
                transformed_moment_canonical(key, permutation)
            haskey(by_canonical, canonical) ||
                error("moment inventory is not closed under full spin permutations")
            target = by_canonical[canonical]
            moment_degree(target) == moment_degree(key) ||
                error("spin permutation changed moment degree")
            action[key] = (
                moment_permutation_sign(key, permutation),
                target,
            )
        end
        push!(actions, action)
    end
    return actions
end

"""
Unsigned orbit quotient on the conjugation-even V4 moment inventory.

All retained moments have even X, Y, and Z parities. Consequently their total
degree is even and the proper-rotation lift has sign plus for all six axis
permutations.
"""
struct FullSpinMomentQuotient
    actions::Vector{Dict{MomentKey,Tuple{Int,MomentKey}}}
    representatives::Dict{MomentKey,MomentKey}
    moments::Vector{MomentKey}
end

function build_full_spin_moment_quotient(
    moments::Vector{MomentKey},
)
    actions = build_actions(moments)
    all(
        sign == 1
        for action in actions
        for (sign, _) in values(action)
    ) || error("conjugation-even spin-permutation quotient acquired a sign")

    representatives = Dict{MomentKey,MomentKey}()
    representative_set = Set{MomentKey}()
    for key in moments
        orbit = MomentKey[
            action[key][2]
            for action in actions
        ]
        representative = minimum(orbit)
        representatives[key] = representative
        push!(representative_set, representative)
    end
    ordered = sort!(
        collect(representative_set);
        by=key -> (moment_degree(key), key.canonical),
    )
    return FullSpinMomentQuotient(
        actions,
        representatives,
        ordered,
    )
end

function full_spin_polynomial_action(
    polynomial::ExactLinearPolynomial,
    action::Dict{MomentKey,Tuple{Int,MomentKey}},
)
    result = ExactLinearPolynomial()
    for (key, coefficient) in polynomial.terms
        haskey(action, key) ||
            error("polynomial contains a moment outside the action inventory")
        sign, target = action[key]
        add_term!(result, target, sign * coefficient)
    end
    return result
end

function full_spin_quotient_projection(
    polynomial::ExactLinearPolynomial,
    quotient::FullSpinMomentQuotient,
)
    result = ExactLinearPolynomial()
    for (key, coefficient) in polynomial.terms
        haskey(quotient.representatives, key) ||
            error("polynomial contains a moment outside the quotient inventory")
        add_term!(
            result,
            quotient.representatives[key],
            coefficient,
        )
    end
    return result
end

block_key(block::ReducedPSDBlock) = (
    block.role,
    block.family,
    block.character.rx,
    block.character.ry,
)

function hamiltonian_is_invariant(
    source::ConjugationReducedPrimalAssembly,
)
    terms = source.source.source.hamiltonian_terms
    original = Dict{PauliWord,Any}()
    for term in terms
        original[term.word] =
            get(original, term.word, zero(term.coefficient)) +
            term.coefficient
    end
    for permutation in SPIN_AXIS_PERMUTATIONS
        transformed = Dict{PauliWord,Any}()
        for term in terms
            sign, word =
                full_spin_permutation(term.word, permutation)
            transformed[word] =
                get(transformed, word, zero(term.coefficient)) +
                sign * term.coefficient
        end
        transformed == original || return false
    end
    return true
end

function source_coefficient_covariance(
    source::ConjugationReducedPrimalAssembly,
)
    v4 = source.source
    blocks = [v4.positive_blocks; v4.gap_blocks]
    by_key = Dict(block_key(block) => block for block in blocks)
    actions = build_actions(v4.moments)
    exact = true
    check_count = 0
    for (
        permutation_index,
        permutation,
    ) in enumerate(SPIN_AXIS_PERMUTATIONS)
        action = actions[permutation_index]
        for block in blocks
            target_character =
                full_spin_character(block.character, permutation)
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
            for row in eachindex(block.rows)
                for column in row:length(block.rows)
                    left_sign, left_word = full_spin_permutation(
                        block.rows[row].word,
                        permutation,
                    )
                    right_sign, right_word = full_spin_permutation(
                        block.rows[column].word,
                        permutation,
                    )
                    haskey(target_indices, left_word) &&
                        haskey(target_indices, right_word) ||
                        error("spin-permutation covariance target row is missing")
                    polynomial = reduced_block_entry(
                        v4,
                        block,
                        block.rows[row],
                        block.rows[column],
                    )
                    target_polynomial = reduced_block_entry(
                        v4,
                        target,
                        target.rows[target_indices[left_word]],
                        target.rows[target_indices[right_word]],
                    )
                    expected =
                        (left_sign * right_sign) *
                        target_polynomial
                    exact &=
                        full_spin_polynomial_action(
                            polynomial,
                            action,
                        ) == expected
                    check_count += 1
                end
            end
        end
    end
    return exact, check_count, actions
end

function equality_space_is_invariant(
    source::ConjugationReducedPrimalAssembly,
    v4_actions,
)
    equalities = source.source.equalities
    transformed = ExactLinearPolynomial[
        full_spin_polynomial_action(equality, action)
        for action in v4_actions
        for equality in equalities
    ]
    return polynomial_row_rank(equalities) ==
           polynomial_row_rank([equalities; transformed])
end

"""
Exhaustive truth and inventory gate for full spin-axis permutation averaging.

The covariance check is performed before conjugation realification, where the
proper-rotation lift is a signed row permutation and no gauge phases need to
be inferred. The conjugation-even inventory is then checked to be a closed,
unsigned subrepresentation.
"""
function full_spin_permutation_truth(
    source::ConjugationReducedPrimalAssembly,
)
    coefficient_covariant, coefficient_check_count, v4_actions =
        source_coefficient_covariance(source)
    conjugation_actions = build_actions(source.moments)
    conjugation_inventory_closed = all(
        !conjugation_odd(target)
        for action in conjugation_actions
        for (_, target) in values(action)
    )
    conjugation_action_unsigned = all(
        sign == 1
        for action in conjugation_actions
        for (sign, _) in values(action)
    )
    quotient = build_full_spin_moment_quotient(source.moments)
    equality_invariant =
        equality_space_is_invariant(source, v4_actions)
    hamiltonian_invariant = hamiltonian_is_invariant(source)
    return (
        exact=hamiltonian_invariant &&
              coefficient_covariant &&
              conjugation_inventory_closed &&
              conjugation_action_unsigned &&
              equality_invariant,
        hamiltonian_invariant=hamiltonian_invariant,
        coefficient_covariant=coefficient_covariant,
        coefficient_check_count=coefficient_check_count,
        conjugation_inventory_closed=conjugation_inventory_closed,
        conjugation_action_unsigned=conjugation_action_unsigned,
        equality_space_invariant=equality_invariant,
        source_moment_count=length(source.moments),
        quotient_moment_count=length(quotient.moments),
        eliminated_moment_count=
            length(source.moments) - length(quotient.moments),
        quotient=quotient,
    )
end

end
