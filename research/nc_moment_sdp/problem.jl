struct NCProblem{B<:StarAlgebraBackend}
    name::String
    backend::B
    objective::NCPolynomial
    equalities::Tuple{Vararg{NCPolynomial}}
    inequalities::Tuple{Vararg{NCPolynomial}}
    order::Int
    sense::Symbol
    generator_characters::Tuple{Vararg{UInt64}}
    group_rank::Int
end

function NCProblem(name::AbstractString, backend::B;
                   objective, equalities=NCPolynomial[], inequalities=NCPolynomial[],
                   order::Integer, sense::Symbol=:Max,
                   generator_characters=zeros(UInt64, length(generators(backend).names)),
                   group_rank::Integer=0) where {B<:StarAlgebraBackend}
    order >= 1 || throw(ArgumentError("moment order must be positive"))
    sense in (:Max, :Min) || throw(ArgumentError("sense must be :Max or :Min"))
    objective isa NCPolynomial || throw(ArgumentError("objective must be an NCPolynomial"))
    characters = Tuple(UInt64.(generator_characters))
    length(characters) == length(generators(backend).names) ||
        throw(ArgumentError("one character mask is required per generator"))
    0 <= group_rank <= 63 || throw(ArgumentError("group_rank must lie in 0:63"))
    limit = group_rank == 0 ? UInt64(0) : (UInt64(1) << group_rank) - UInt64(1)
    all(character -> (character & ~limit) == 0, characters) ||
        throw(ArgumentError("generator character lies outside Z2^group_rank"))
    problem = NCProblem{B}(String(name), backend, objective, Tuple(equalities),
                           Tuple(inequalities), Int(order), sense, characters,
                           Int(group_rank))
    _validate_problem(problem)
    return problem
end

function _polynomial_degree(poly::NCPolynomial)
    return maximum((length(word) for word in keys(poly.terms)); init=0)
end

function _validate_problem(problem::NCProblem)
    _isapprox_polynomial(problem.objective, star(problem.backend, problem.objective)) ||
        throw(ArgumentError("objective is not self-adjoint"))
    for (kind, polynomials) in (("equality", problem.equalities),
                                ("inequality", problem.inequalities))
        for poly in polynomials
            _isapprox_polynomial(poly, star(problem.backend, poly)) ||
                throw(ArgumentError("$kind polynomial is not self-adjoint"))
            _polynomial_degree(poly) <= 2problem.order ||
                throw(ArgumentError("$kind polynomial degree exceeds hierarchy closure"))
        end
    end
    _polynomial_degree(problem.objective) <= 2problem.order ||
        throw(ArgumentError("objective degree exceeds twice the moment order"))
    for poly in (problem.objective, problem.equalities..., problem.inequalities...)
        for word in keys(poly.terms)
            reduced = reduce_word(problem.backend, word)
            reduced.word == word && reduced.phase == 1.0 + 0.0im ||
                throw(ArgumentError("polynomial contains a noncanonical word"))
            adjoint = star_word(problem.backend, word)
            abs(abs(adjoint.phase) - 1.0) <= 1.0e-12 ||
                throw(ArgumentError("adjoint reduction has a non-unit phase"))
        end
    end
    return problem
end

# Compatibility constructor for the original real involution API.
function NCProblem(name::AbstractString, names::Vector{Symbol};
                   commuting_pairs=Tuple{Symbol,Symbol}[],
                   generator_characters::Vector{<:Integer}=zeros(Int, length(names)),
                   group_rank::Integer=0, hamiltonian, order::Integer,
                   sense::Symbol=:Max)
    backend = LegacyInvolutionBackend(names; commuting_pairs=commuting_pairs)
    objective = polynomial(backend, hamiltonian)
    return NCProblem(name, backend; objective=objective, order=order, sense=sense,
                     generator_characters=generator_characters, group_rank=group_rank)
end

function enumerate_words(backend::StarAlgebraBackend, order::Integer)
    words = Set{NCWord}([NCWord()])
    frontier = Set{NCWord}([NCWord()])
    for _ in 1:order
        next_frontier = Set{NCWord}()
        for word in frontier, generator in eachindex(generators(backend).names)
            reduced = reduce_word(backend, NCWord((word.letters..., generator)))
            push!(words, reduced.word)
            push!(next_frontier, reduced.word)
        end
        frontier = next_frontier
    end
    return sort!(collect(words); lt=_word_less)
end
enumerate_words(problem::NCProblem) = enumerate_words(problem.backend, problem.order)

word_character(word::NCWord, characters::Tuple{Vararg{UInt64}}) =
    word_character(word.letters, collect(characters))
