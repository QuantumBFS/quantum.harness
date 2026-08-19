module ExactSymmetryReduction

using ..SquareJ1J2Prototype:
    PauliWord
using ..GenericGapModel:
    BasisManifest,
    StateMonomial
using ..PrimalGapSymbolics:
    ExactLinearPolynomial,
    MomentKey,
    positive_entry,
    covariance_product_entry,
    gap_entry,
    real_part_polynomial,
    imag_part_polynomial,
    normalize_real_equality,
    canonical_polynomial_string
using ..PrimalGapAssembly:
    PrimalAssembly

export V4Character,
       V4_CHARACTERS,
       v4_character,
       v4_invariant_projection,
       manifest_pauli_words,
       bare_row,
       scalar_row,
       centered_positive_entry,
       scalar_positive_entry,
       centered_scalar_positive_entry,
       positive_reduction_truth,
       gap_facial_reduction_truth,
       invariant_moment_inventory

"""
Character under global pi rotations about the x and y spin axes.

The two bits record the signs under `R_x(pi)` and `R_y(pi)`. Their product is
the sign under `R_z(pi)`, so this labels all four irreducible characters of the
Klein four group.
"""
struct V4Character
    rx::Bool
    ry::Bool
end

Base.:(==)(left::V4Character, right::V4Character) =
    left.rx == right.rx && left.ry == right.ry
Base.hash(character::V4Character, seed::UInt) =
    hash(character.ry, hash(character.rx, seed))
Base.isless(left::V4Character, right::V4Character) =
    (left.rx, left.ry) < (right.rx, right.ry)

const V4_CHARACTERS = (
    V4Character(false, false),
    V4Character(false, true),
    V4Character(true, false),
    V4Character(true, true),
)
const V4_TRIVIAL = first(V4_CHARACTERS)

character_product(left::V4Character, right::V4Character) =
    V4Character(xor(left.rx, right.rx), xor(left.ry, right.ry))

function v4_character(word::PauliWord)
    x_count = count(operation -> operation[2] == 1, word.ops)
    y_count = count(operation -> operation[2] == 2, word.ops)
    z_count = count(operation -> operation[2] == 3, word.ops)
    return V4Character(
        isodd(y_count + z_count),
        isodd(x_count + z_count),
    )
end

function v4_character(monomial::StateMonomial)
    character = v4_character(monomial.operator_word)
    for word in monomial.state_symbols
        character = character_product(character, v4_character(word))
    end
    return character
end

function v4_character(key::MomentKey)
    x_count = count(==('X'), key.canonical)
    y_count = count(==('Y'), key.canonical)
    z_count = count(==('Z'), key.canonical)
    return V4Character(
        isodd(y_count + z_count),
        isodd(x_count + z_count),
    )
end

"""Reynolds projection of one exact polynomial onto V4-invariant moments."""
function v4_invariant_projection(polynomial::ExactLinearPolynomial)
    return ExactLinearPolynomial(Dict(
        key => coefficient
        for (key, coefficient) in polynomial.terms
        if v4_character(key) == V4_TRIVIAL
    ))
end

"""Return the bare Pauli words and verify every nonidentity scalar companion."""
function manifest_pauli_words(manifest::BasisManifest)
    bare_words = PauliWord[]
    scalar_words = Set{PauliWord}()
    for entry in manifest.entries
        if isempty(entry.state_symbols)
            push!(bare_words, entry.operator_word)
        elseif (
            length(entry.state_symbols) == 1 &&
            isempty(entry.operator_word.ops)
        )
            push!(scalar_words, only(entry.state_symbols))
        else
            throw(
                ArgumentError(
                    "exact reduction requires the one-symbol-lift basis",
                ),
            )
        end
    end
    isempty(bare_words) &&
        throw(ArgumentError("basis has no bare identity row"))
    count(word -> isempty(word.ops), bare_words) == 1 ||
        throw(ArgumentError("basis must contain exactly one bare identity"))
    length(unique(bare_words)) == length(bare_words) ||
        throw(ArgumentError("basis contains duplicate bare words"))
    nonidentity_words = filter(word -> !isempty(word.ops), bare_words)
    Set(nonidentity_words) == scalar_words ||
        throw(ArgumentError("bare/scalar Pauli-word inventories disagree"))
    return bare_words
end

bare_row(word::PauliWord) =
    StateMonomial(PauliWord[], word)

scalar_row(word::PauliWord) =
    isempty(word.ops) ?
    bare_row(word) :
    StateMonomial([word], PauliWord())

"""
Entry on centered rows `c_w = w - zeta(w) I`.

It is exactly the operator moment minus the product of scalar moments.
"""
centered_positive_entry(left::PauliWord, right::PauliWord) =
    positive_entry(bare_row(left), bare_row(right)) -
    covariance_product_entry(bare_row(left), bare_row(right))

"""Entry on scalar rows `{I, zeta(w) I}`."""
scalar_positive_entry(left::PauliWord, right::PauliWord) =
    covariance_product_entry(bare_row(left), bare_row(right))

"""Cross entry between `c_w` and a scalar row; it must vanish identically."""
centered_scalar_positive_entry(
    centered_word::PauliWord,
    scalar_word::PauliWord,
) =
    positive_entry(bare_row(centered_word), scalar_row(scalar_word)) -
    positive_entry(scalar_row(centered_word), scalar_row(scalar_word))

upper_triangle_count(dimension::Int) =
    dimension * (dimension + 1) ÷ 2

function character_block_sizes(words::Vector{PauliWord})
    return Dict(
        character => count(word -> v4_character(word) == character, words)
        for character in V4_CHARACTERS
    )
end

"""
Exhaustive symbolic truth checks for the positive-matrix reduction.

Every centered/scalar cross entry is checked as an exact zero polynomial.
Every entry projected between distinct V4 characters is also checked as an
exact zero polynomial. No floating-point evaluation is used.
"""
function positive_reduction_truth(manifest::BasisManifest)
    words = manifest_pauli_words(manifest)
    nonidentity_words = filter(word -> !isempty(word.ops), words)

    centered_formula_exact = all(
        centered_positive_entry(left, right) ==
        (
            positive_entry(bare_row(left), bare_row(right)) -
            positive_entry(bare_row(left), scalar_row(right)) -
            positive_entry(scalar_row(left), bare_row(right)) +
            positive_entry(scalar_row(left), scalar_row(right))
        )
        for left in nonidentity_words
        for right in nonidentity_words
    )
    scalar_formula_exact = all(
        scalar_positive_entry(left, right) ==
        positive_entry(scalar_row(left), scalar_row(right))
        for left in words
        for right in words
    )
    centered_scalar_zero = all(
        iszero(centered_scalar_positive_entry(centered, scalar))
        for centered in nonidentity_words
        for scalar in words
    )

    centered_sizes = character_block_sizes(nonidentity_words)
    scalar_sizes = character_block_sizes(words)
    centered_v4_cross_zero = all(
        left_character == right_character ||
        iszero(v4_invariant_projection(centered_positive_entry(left, right)))
        for left in nonidentity_words
        for right in nonidentity_words
        for left_character in (v4_character(left),)
        for right_character in (v4_character(right),)
    )
    scalar_v4_cross_zero = all(
        left_character == right_character ||
        iszero(v4_invariant_projection(scalar_positive_entry(left, right)))
        for left in words
        for right in words
        for left_character in (v4_character(left),)
        for right_character in (v4_character(right),)
    )

    original_dimension = length(manifest.entries)
    centered_dimension = length(nonidentity_words)
    scalar_dimension = length(words)
    v4_upper_entries = sum(
        upper_triangle_count(centered_sizes[character]) +
        upper_triangle_count(scalar_sizes[character])
        for character in V4_CHARACTERS
    )

    return (
        exact=centered_formula_exact &&
              scalar_formula_exact &&
              centered_scalar_zero &&
              centered_v4_cross_zero &&
              scalar_v4_cross_zero,
        original_dimension=original_dimension,
        centered_dimension=centered_dimension,
        scalar_dimension=scalar_dimension,
        centered_formula_exact=centered_formula_exact,
        scalar_formula_exact=scalar_formula_exact,
        centered_scalar_cross_zero=centered_scalar_zero,
        centered_v4_cross_zero=centered_v4_cross_zero,
        scalar_v4_cross_zero=scalar_v4_cross_zero,
        centered_block_sizes=centered_sizes,
        scalar_block_sizes=scalar_sizes,
        original_upper_entries=upper_triangle_count(original_dimension),
        centered_scalar_upper_entries=
            upper_triangle_count(centered_dimension) +
            upper_triangle_count(scalar_dimension),
        v4_upper_entries=v4_upper_entries,
    )
end

function canonical_real_equalities(
    polynomials::Vector{ExactLinearPolynomial},
)
    by_serialization = Dict{String,ExactLinearPolynomial}()
    for polynomial in polynomials
        for component in (
            real_part_polynomial(polynomial),
            imag_part_polynomial(polynomial),
        )
            iszero(component) && continue
            normalized = normalize_real_equality(component)
            serialized = canonical_polynomial_string(normalized)
            by_serialization[serialized] = normalized
        end
    end
    return ExactLinearPolynomial[
        by_serialization[serialized]
        for serialized in sort!(collect(keys(by_serialization)))
    ]
end

"""
Exhaustive symbolic truth checks for facial reduction of the gap matrix.

Rows whose operator word is identity have identically zero diagonal. Their
entire rows are therefore converted into exact real equalities, leaving the
bare nonidentity operator rows as the reduced PSD block.
"""
function gap_facial_reduction_truth(assembly::PrimalAssembly)
    entries = assembly.gap_basis.entries
    null_rows = filter(entry -> isempty(entry.operator_word.ops), entries)
    active_rows = filter(entry -> !isempty(entry.operator_word.ops), entries)
    terms = assembly.hamiltonian_terms
    gamma = assembly.problem.gamma

    null_block_zero = all(
        iszero(gap_entry(left, right, terms, gamma))
        for left in null_rows
        for right in null_rows
    )
    cross_polynomials = ExactLinearPolynomial[
        gap_entry(null_row, active_row, terms, gamma)
        for null_row in null_rows
        for active_row in active_rows
    ]
    cross_equalities = canonical_real_equalities(cross_polynomials)

    return (
        exact=null_block_zero,
        original_dimension=length(entries),
        active_dimension=length(active_rows),
        null_dimension=length(null_rows),
        null_block_zero=null_block_zero,
        cross_polynomial_count=count(!iszero, cross_polynomials),
        cross_equality_count=length(cross_equalities),
        active_rows=active_rows,
        null_rows=null_rows,
        cross_polynomials=cross_polynomials,
        cross_equalities=cross_equalities,
    )
end

function invariant_moment_inventory(moments::Vector{MomentKey})
    invariant = filter(key -> v4_character(key) == V4_TRIVIAL, moments)
    by_character = Dict(
        character => count(key -> v4_character(key) == character, moments)
        for character in V4_CHARACTERS
    )
    return (
        moments=invariant,
        original_count=length(moments),
        invariant_count=length(invariant),
        eliminated_count=length(moments) - length(invariant),
        by_character=by_character,
    )
end

end
