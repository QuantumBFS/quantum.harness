module PrimalGapSymbolics

using SHA
using ..SquareJ1J2Prototype:
    PauliWord,
    multiply_words
using ..GenericGapModel:
    LocalPauliTerm,
    StateMonomial

export ExactRational,
       ExactCoefficient,
       MomentKey,
       ExactLinearPolynomial,
       moment_key,
       moment_key_string,
       moment_degree,
       polynomial_coefficient,
       canonical_polynomial_string,
       polynomial_sha256,
       real_part_polynomial,
       imag_part_polynomial,
       normalize_real_equality,
       positive_entry,
       covariance_product_entry,
       stationarity_entry,
       gap_energy_entry,
       gap_entry,
       adjoint_polynomial

const ExactRational = Rational{BigInt}
const ExactCoefficient = Complex{ExactRational}

function exact_rational(value::Integer)
    return ExactRational(BigInt(value), BigInt(1))
end

function exact_rational(value::Rational)
    return ExactRational(BigInt(numerator(value)), BigInt(denominator(value)))
end

function exact_rational(value::AbstractFloat)
    throw(
        ArgumentError(
            "exact primal assembly rejects floating-point coefficients; " *
            "construct the model and gamma with integers or rationals",
        ),
    )
end

function exact_coefficient(value::Real)
    return ExactCoefficient(exact_rational(value), zero(ExactRational))
end

function exact_coefficient(value::Complex)
    return ExactCoefficient(
        exact_rational(real(value)),
        exact_rational(imag(value)),
    )
end

function canonical_word_string(word::PauliWord)
    axis_names = ("X", "Y", "Z")
    return isempty(word.ops) ? "I" : join(
        (
            string(site) * axis_names[Int(axis)]
            for (site, axis) in word.ops
        ),
        ";",
    )
end

"""
Canonical scalar moment `ℒ(ζ(w₁)…ζ(wₖ))`.

Every canonical Pauli word is Hermitian, so its individual state symbol is
real. The state symbols commute and are therefore stored as a sorted multiset.
Identity factors are removed using `ζ(I)=1`.
"""
struct MomentKey
    canonical::String
    degree::Int

    function MomentKey(state_symbols::Vector{PauliWord})
        symbols = PauliWord[
            PauliWord(copy(word.ops))
            for word in state_symbols
            if !isempty(word.ops)
        ]
        sort!(symbols; by=canonical_word_string)
        canonical = join(canonical_word_string.(symbols), "|")
        degree = sum(length, symbols; init=0)
        new(canonical, degree)
    end
end

moment_key(state_symbols::Vector{PauliWord}=PauliWord[]) =
    MomentKey(state_symbols)

moment_key_string(key::MomentKey) =
    isempty(key.canonical) ? "moment=[]" : "moment=[" * key.canonical * "]"

moment_degree(key::MomentKey) =
    key.degree

Base.:(==)(left::MomentKey, right::MomentKey) =
    left.canonical == right.canonical
Base.hash(key::MomentKey, h::UInt) = hash(key.canonical, h)
Base.isless(left::MomentKey, right::MomentKey) =
    left.canonical < right.canonical

"""Sparse exact affine polynomial in real scalar moment variables."""
struct ExactLinearPolynomial
    terms::Dict{MomentKey,ExactCoefficient}
end

ExactLinearPolynomial() =
    ExactLinearPolynomial(Dict{MomentKey,ExactCoefficient}())

Base.iszero(polynomial::ExactLinearPolynomial) = isempty(polynomial.terms)

function Base.:(==)(
    left::ExactLinearPolynomial,
    right::ExactLinearPolynomial,
)
    return left.terms == right.terms
end

function add_term!(
    polynomial::ExactLinearPolynomial,
    key::MomentKey,
    coefficient,
)
    exact = exact_coefficient(coefficient)
    iszero(exact) && return polynomial
    updated = get(polynomial.terms, key, zero(ExactCoefficient)) + exact
    if iszero(updated)
        delete!(polynomial.terms, key)
    else
        polynomial.terms[key] = updated
    end
    return polynomial
end

function add_scaled!(
    destination::ExactLinearPolynomial,
    source::ExactLinearPolynomial,
    scale,
)
    exact_scale = exact_coefficient(scale)
    for (key, coefficient) in source.terms
        add_term!(destination, key, exact_scale * coefficient)
    end
    return destination
end

function Base.:+(
    left::ExactLinearPolynomial,
    right::ExactLinearPolynomial,
)
    result = ExactLinearPolynomial(copy(left.terms))
    return add_scaled!(result, right, one(ExactRational))
end

function Base.:-(
    left::ExactLinearPolynomial,
    right::ExactLinearPolynomial,
)
    result = ExactLinearPolynomial(copy(left.terms))
    return add_scaled!(result, right, -one(ExactRational))
end

function Base.:*(scale::Number, polynomial::ExactLinearPolynomial)
    result = ExactLinearPolynomial()
    return add_scaled!(result, polynomial, scale)
end

Base.:*(polynomial::ExactLinearPolynomial, scale::Number) =
    scale * polynomial

function adjoint_polynomial(polynomial::ExactLinearPolynomial)
    return ExactLinearPolynomial(
        Dict(key => conj(coefficient) for (key, coefficient) in polynomial.terms),
    )
end

Base.adjoint(polynomial::ExactLinearPolynomial) =
    adjoint_polynomial(polynomial)

polynomial_coefficient(
    polynomial::ExactLinearPolynomial,
    key::MomentKey,
) = get(polynomial.terms, key, zero(ExactCoefficient))

function write_framed!(io::IO, value)
    serialized = string(value)
    write(io, string(ncodeunits(serialized)), ":", serialized)
    return io
end

function write_exact_coefficient!(
    io::IO,
    coefficient::ExactCoefficient,
)
    write_framed!(io, numerator(real(coefficient)))
    write_framed!(io, denominator(real(coefficient)))
    write_framed!(io, numerator(imag(coefficient)))
    write_framed!(io, denominator(imag(coefficient)))
    return io
end

"""Injective deterministic serialization of one exact affine polynomial."""
function canonical_polynomial_string(
    polynomial::ExactLinearPolynomial,
)
    ordered_keys = sort!(
        collect(Base.keys(polynomial.terms));
        by=key -> (moment_degree(key), key.canonical),
    )
    io = IOBuffer()
    write(io, "exact-linear-polynomial-v1")
    write_framed!(io, length(ordered_keys))
    for key in ordered_keys
        write_framed!(io, moment_key_string(key))
        write_exact_coefficient!(io, polynomial.terms[key])
    end
    return String(take!(io))
end

polynomial_sha256(polynomial::ExactLinearPolynomial) =
    bytes2hex(sha256(canonical_polynomial_string(polynomial)))

function real_part_polynomial(
    polynomial::ExactLinearPolynomial,
)
    result = ExactLinearPolynomial()
    for (key, coefficient) in polynomial.terms
        add_term!(result, key, real(coefficient))
    end
    return result
end

function imag_part_polynomial(
    polynomial::ExactLinearPolynomial,
)
    result = ExactLinearPolynomial()
    for (key, coefficient) in polynomial.terms
        add_term!(result, key, imag(coefficient))
    end
    return result
end

"""
Normalize a nonzero real equality up to multiplication by a nonzero scalar.

The coefficient of the first canonical moment becomes `+1`, so duplicate
stationarity equalities can be removed deterministically.
"""
function normalize_real_equality(
    polynomial::ExactLinearPolynomial,
)
    iszero(polynomial) &&
        throw(ArgumentError("cannot normalize a zero equality"))
    all(iszero ∘ imag, values(polynomial.terms)) ||
        throw(ArgumentError("equality normalization requires real coefficients"))
    first_key = first(
        sort!(
            collect(Base.keys(polynomial.terms));
            by=key -> (moment_degree(key), key.canonical),
        ),
    )
    pivot = real(polynomial.terms[first_key])
    iszero(pivot) && error("sparse polynomial retained a zero coefficient")
    return (inv(pivot)) * polynomial
end

function multiply_sequence(words::PauliWord...)
    coefficient = Complex{Int}(1, 0)
    product = PauliWord()
    for word in words
        phase, product = multiply_words(product, word)
        coefficient *= phase
    end
    return exact_coefficient(coefficient), product
end

function scalar_key(
    state_symbols::Vector{PauliWord},
    operator_word::PauliWord,
)
    symbols = copy(state_symbols)
    isempty(operator_word.ops) || push!(symbols, operator_word)
    return MomentKey(symbols)
end

function shared_state_symbols(
    left::StateMonomial,
    right::StateMonomial,
)
    return [left.state_symbols; right.state_symbols]
end

"""
Exact entry `ℒ(ζ(s†t))` of the positivity matrix.

The state-symbol factors are central and real. Only the two operator words are
multiplied in the noncommutative Pauli algebra.
"""
function positive_entry(
    left::StateMonomial,
    right::StateMonomial,
)
    phase, product = multiply_sequence(
        left.operator_word,
        right.operator_word,
    )
    result = ExactLinearPolynomial()
    add_term!(
        result,
        scalar_key(shared_state_symbols(left, right), product),
        phase,
    )
    return result
end

"""
Exact entry `ℒ(ζ(s†)ζ(t))` in the variance subtraction.

Unlike `positive_entry`, the two operator words become two separate commuting
state symbols. They must not be Pauli-multiplied into one word.
"""
function covariance_product_entry(
    left::StateMonomial,
    right::StateMonomial,
)
    symbols = shared_state_symbols(left, right)
    isempty(left.operator_word.ops) || push!(symbols, left.operator_word)
    isempty(right.operator_word.ops) || push!(symbols, right.operator_word)
    result = ExactLinearPolynomial()
    add_term!(result, MomentKey(symbols), one(ExactRational))
    return result
end

function validate_hamiltonian_terms(terms::AbstractVector)
    all(term -> term isa LocalPauliTerm, terms) ||
        throw(ArgumentError("Hamiltonian entries must be LocalPauliTerm values"))
    return terms
end

function add_hamiltonian_product!(
    result::ExactLinearPolynomial,
    state_symbols::Vector{PauliWord},
    term,
    prefactor,
    words::PauliWord...,
)
    phase, product = multiply_sequence(words...)
    add_term!(
        result,
        scalar_key(state_symbols, product),
        exact_coefficient(prefactor) *
        exact_coefficient(term.coefficient) *
        phase,
    )
    return result
end

"""Exact stationarity polynomial `ℒ(ζ([H,q]))`."""
function stationarity_entry(
    q::StateMonomial,
    terms::AbstractVector,
)
    validate_hamiltonian_terms(terms)
    result = ExactLinearPolynomial()
    state_symbols = copy(q.state_symbols)
    for term in terms
        add_hamiltonian_product!(
            result,
            state_symbols,
            term,
            one(ExactRational),
            term.word,
            q.operator_word,
        )
        add_hamiltonian_product!(
            result,
            state_symbols,
            term,
            -one(ExactRational),
            q.operator_word,
            term.word,
        )
    end
    return result
end

"""
Exact Hermitian gap-energy entry

`1/2 ℒ(ζ(s†[H,t] - [H,s†]t))`.
"""
function gap_energy_entry(
    left::StateMonomial,
    right::StateMonomial,
    terms::AbstractVector,
)
    validate_hamiltonian_terms(terms)
    result = ExactLinearPolynomial()
    state_symbols = shared_state_symbols(left, right)
    half = ExactRational(BigInt(1), BigInt(2))
    for term in terms
        # Algebraically:
        #   s† H t - 1/2 s† t H - 1/2 H s† t.
        add_hamiltonian_product!(
            result,
            state_symbols,
            term,
            one(ExactRational),
            left.operator_word,
            term.word,
            right.operator_word,
        )
        add_hamiltonian_product!(
            result,
            state_symbols,
            term,
            -half,
            left.operator_word,
            right.operator_word,
            term.word,
        )
        add_hamiltonian_product!(
            result,
            state_symbols,
            term,
            -half,
            term.word,
            left.operator_word,
            right.operator_word,
        )
    end
    return result
end

"""
Exact gap-matrix entry

`energy(s,t) - γ(ℒ(ζ(s†t)) - ℒ(ζ(s†)ζ(t)))`.
"""
function gap_entry(
    left::StateMonomial,
    right::StateMonomial,
    terms::AbstractVector,
    gamma::Real,
)
    exact_gamma = exact_rational(gamma)
    result = gap_energy_entry(left, right, terms)
    add_scaled!(result, positive_entry(left, right), -exact_gamma)
    add_scaled!(
        result,
        covariance_product_entry(left, right),
        exact_gamma,
    )
    return result
end

end
