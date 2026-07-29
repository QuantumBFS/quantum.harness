module CoreMGK

using ..SquareJ1J2Prototype: PauliWord, multiply_words
using ..GenericGapModel:
    AssemblyPlan,
    BasisManifest,
    GapProblem,
    LocalPauliTerm,
    NoStateSymmetry,
    StateMonomial,
    assembly_plan,
    basis_manifest,
    canonical_word_string,
    instantiate_terms,
    validate_basis_manifest

export CoreMGKPlan,
    ExactComponent,
    ExactPairWiring,
    ExactRowCoefficient,
    GammaAffineCoefficient,
    GaussianRational,
    ScalarMoment,
    a_gamma_coefficients,
    core_mgk_pair,
    core_mgk_plan,
    gap_pair_components,
    pack_upper_coefficient,
    positive_pair_components,
    scalar_moment_string

const BigRational = Rational{BigInt}
const GaussianRational = Complex{BigRational}

exact_rational(value::Integer) = BigInt(value) // BigInt(1)
exact_rational(value::Rational) =
    BigInt(numerator(value)) // BigInt(denominator(value))
exact_rational(value::AbstractFloat) = throw(ArgumentError(
    "core_mgk requires exact rational inputs; Float coefficients are not authority",
))
exact_gaussian(value::Real) = GaussianRational(exact_rational(value), 0)
exact_gaussian(value::Complex) = GaussianRational(
    exact_rational(real(value)),
    exact_rational(imag(value)),
)

"""Canonical real scalar moment `L(ζ(w₁)…ζ(wₖ))`."""
struct ScalarMoment
    state_symbol_multiset::Vector{PauliWord}

    function ScalarMoment(symbols::Vector{PauliWord})
        any(word -> isempty(word.ops), symbols) &&
            throw(ArgumentError("identity state symbols must be removed"))
        owned = [PauliWord(copy(word.ops)) for word in symbols]
        sort!(owned; by=canonical_word_string)
        new(owned)
    end
end

Base.:(==)(left::ScalarMoment, right::ScalarMoment) =
    left.state_symbol_multiset == right.state_symbol_multiset
Base.hash(moment::ScalarMoment, h::UInt) =
    hash(Tuple(moment.state_symbol_multiset), h)

scalar_moment_string(moment::ScalarMoment) = isempty(moment.state_symbol_multiset) ?
    "zeta=[]" :
    "zeta=[" * join(canonical_word_string.(moment.state_symbol_multiset), "|") * "]"

struct ExactRowCoefficient
    row::ScalarMoment
    coefficient::GaussianRational
end

struct ExactComponent
    component::Symbol
    status::Symbol
    zero_reason::Union{Nothing,Symbol}
    coefficients::Vector{ExactRowCoefficient}
end

struct ExactPairWiring
    role::Symbol
    j_index::Int
    k_index::Int
    j_entry::StateMonomial
    k_entry::StateMonomial
    component_records::Vector{ExactComponent}
end

struct GammaAffineCoefficient
    constant::GaussianRational
    gamma::GaussianRational
end

Base.:(==)(left::GammaAffineCoefficient, right::GammaAffineCoefficient) =
    left.constant == right.constant && left.gamma == right.gamma

struct CoreMGKPlan{T<:Real}
    source_plan::AssemblyPlan
    positive_basis::BasisManifest
    gap_basis::BasisManifest
    hamiltonian_terms::Vector{LocalPauliTerm{T}}
    state_class::String
end

function add_coefficient!(
    coefficients::Dict{ScalarMoment,GaussianRational},
    row::ScalarMoment,
    coefficient::GaussianRational,
)
    iszero(coefficient) && return coefficients
    value = get(coefficients, row, zero(GaussianRational)) + coefficient
    if iszero(value)
        delete!(coefficients, row)
    else
        coefficients[row] = value
    end
    return coefficients
end

function scalarize(
    state_symbols::Vector{PauliWord},
    operator_word::PauliWord,
)
    symbols = [PauliWord(copy(word.ops)) for word in state_symbols]
    isempty(operator_word.ops) || push!(symbols, PauliWord(copy(operator_word.ops)))
    return ScalarMoment(symbols)
end

function product_moment(left::StateMonomial, right::StateMonomial)
    phase, operator_word = multiply_words(left.operator_word, right.operator_word)
    row = scalarize(
        [left.state_symbols; right.state_symbols],
        operator_word,
    )
    return exact_gaussian(phase), row
end

function scalarized_moment(monomial::StateMonomial)
    return scalarize(monomial.state_symbols, monomial.operator_word)
end

function component_record(
    name::Symbol,
    coefficients::Dict{ScalarMoment,GaussianRational};
    zero_reason::Symbol=:algebraic,
)
    rows = [
        ExactRowCoefficient(row, coefficient)
        for (row, coefficient) in coefficients
        if !iszero(coefficient)
    ]
    sort!(rows; by=record -> scalar_moment_string(record.row))
    return isempty(rows) ?
        ExactComponent(name, :computed_exact_zero, zero_reason, rows) :
        ExactComponent(name, :computed_nonzero, nothing, rows)
end

function positive_pair_components(left::StateMonomial, right::StateMonomial)
    coefficient, row = product_moment(left, right)
    coefficients = Dict{ScalarMoment,GaussianRational}()
    add_coefficient!(coefficients, row, coefficient)
    return [component_record(:M, coefficients)]
end

function commutator_polynomial(hamiltonian_terms, operator_word::PauliWord)
    result = Dict{PauliWord,GaussianRational}()
    for term in hamiltonian_terms
        h_coefficient = exact_gaussian(term.coefficient)
        left_phase, left_word = multiply_words(term.word, operator_word)
        right_phase, right_word = multiply_words(operator_word, term.word)
        left_value = get(result, left_word, zero(GaussianRational)) +
                     h_coefficient * exact_gaussian(left_phase)
        iszero(left_value) ? delete!(result, left_word) : (result[left_word] = left_value)
        right_value = get(result, right_word, zero(GaussianRational)) -
                      h_coefficient * exact_gaussian(right_phase)
        iszero(right_value) ? delete!(result, right_word) : (result[right_word] = right_value)
    end
    return result
end

function gap_pair_components(
    hamiltonian_terms,
    left::StateMonomial,
    right::StateMonomial,
)
    g_moment = Dict{ScalarMoment,GaussianRational}()
    moment_coefficient, moment_row = product_moment(left, right)
    add_coefficient!(g_moment, moment_row, moment_coefficient)

    g_product = Dict{ScalarMoment,GaussianRational}()
    covariance_row = ScalarMoment([
        scalarized_moment(left).state_symbol_multiset;
        scalarized_moment(right).state_symbol_multiset;
    ])
    add_coefficient!(g_product, covariance_row, -one(GaussianRational))

    k_coefficients = Dict{ScalarMoment,GaussianRational}()
    shared_symbols = [left.state_symbols; right.state_symbols]
    right_commutator = commutator_polynomial(
        hamiltonian_terms,
        right.operator_word,
    )
    for (word, coefficient) in right_commutator
        phase, product_word = multiply_words(left.operator_word, word)
        add_coefficient!(
            k_coefficients,
            scalarize(shared_symbols, product_word),
            coefficient * exact_gaussian(phase) / 2,
        )
    end
    left_commutator = commutator_polynomial(
        hamiltonian_terms,
        left.operator_word,
    )
    for (word, coefficient) in left_commutator
        phase, product_word = multiply_words(word, right.operator_word)
        add_coefficient!(
            k_coefficients,
            scalarize(shared_symbols, product_word),
            -coefficient * exact_gaussian(phase) / 2,
        )
    end

    return [
        component_record(:K, k_coefficients),
        component_record(:G_moment, g_moment),
        component_record(:G_product, g_product),
    ]
end

"""
Build the exact, solver-independent Square `core_mgk` plan.

Only the flat unrestricted state class is accepted. `ExplicitStateSymmetry` is
metadata in the current generic model and has not been applied to the basis,
so accepting it here would silently change the physical target.
"""
function core_mgk_plan(problem::GapProblem{T}) where {T<:Real}
    problem.basis_mode == :structured ||
        throw(ArgumentError("core_mgk requires a materialized structured basis"))
    problem.symmetry isa NoStateSymmetry || throw(ArgumentError(
        "core_mgk currently supports only the unrestricted flat state class",
    ))
    positive = basis_manifest(problem, :positive)
    gap = basis_manifest(problem, :gap)
    validate_basis_manifest(positive, problem, :positive) ||
        error("positive basis failed contextual validation")
    validate_basis_manifest(gap, problem, :gap) ||
        error("gap basis failed contextual validation")
    terms = instantiate_terms(problem.model, problem.patch)
    for term in terms
        iszero(imag(exact_gaussian(term.coefficient))) ||
            error("Hamiltonian coefficient is not exactly real")
    end
    return CoreMGKPlan(
        assembly_plan(problem),
        positive,
        gap,
        terms,
        "unrestricted infinite-volume KMS ground states; flat basis; no symmetry quotient",
    )
end

function core_mgk_pair(plan::CoreMGKPlan, role::Symbol, j::Int, k::Int)
    role in (:positive, :gap) ||
        throw(ArgumentError("role must be :positive or :gap"))
    basis = role == :positive ? plan.positive_basis : plan.gap_basis
    1 <= j <= k <= length(basis.entries) ||
        throw(ArgumentError("pair must satisfy 1 <= j <= k <= basis dimension"))
    left = basis.entries[j]
    right = basis.entries[k]
    components = role == :positive ?
        positive_pair_components(left, right) :
        gap_pair_components(plan.hamiltonian_terms, left, right)
    return ExactPairWiring(role, j, k, left, right, components)
end

function component_dictionary(component::ExactComponent)
    return Dict(record.row => record.coefficient for record in component.coefficients)
end

"""Derive symbolic `A_γ = K - γ(G_moment + G_product)` from core truth."""
function a_gamma_coefficients(wiring::ExactPairWiring)
    wiring.role == :gap || throw(ArgumentError("A_gamma exists only for a gap block"))
    components = Dict(
        component.component => component_dictionary(component)
        for component in wiring.component_records
    )
    rows = Set{ScalarMoment}()
    for component in values(components)
        union!(rows, keys(component))
    end
    result = Dict{ScalarMoment,GammaAffineCoefficient}()
    for row in rows
        constant = get(components[:K], row, zero(GaussianRational))
        g = get(components[:G_moment], row, zero(GaussianRational)) +
            get(components[:G_product], row, zero(GaussianRational))
        affine = GammaAffineCoefficient(constant, -g)
        (iszero(affine.constant) && iszero(affine.gamma)) || (result[row] = affine)
    end
    return result
end

"""Render one canonical matrix coefficient into `Tr(AQ)` upper-triangle form."""
function pack_upper_coefficient(coefficient::GaussianRational, j::Int, k::Int)
    1 <= j <= k || throw(ArgumentError("packing requires an upper-triangle pair"))
    if j == k
        iszero(imag(coefficient)) ||
            throw(ArgumentError("a Hermitian diagonal coefficient must be real"))
        return (real=real(coefficient), imag=zero(BigRational))
    end
    return (real=2 * real(coefficient), imag=2 * imag(coefficient))
end

end
