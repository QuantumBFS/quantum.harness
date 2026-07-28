module FiniteAbelianNCMoment

using JuMP
using LinearAlgebra
using MosekTools
const MOI = JuMP.MOI

export NCProblem, SDPResult, normalize_word, enumerate_words, moment_key,
       word_character, solve_moment_sdp, chsh_z2, pauli_z2xz2

const Word = Tuple{Vararg{Int}}

struct NCProblem
    name::String
    generators::Vector{Symbol}
    commuting_pairs::Set{Tuple{Int,Int}}
    generator_characters::Vector{UInt64}
    group_rank::Int
    hamiltonian::Dict{Word,Float64}
    order::Int
    sense::Symbol
end

struct SDPResult
    formulation::Symbol
    objective::Float64
    basis::Vector{Word}
    sectors::Dict{UInt64,Vector{Int}}
    moments::Dict{Word,Float64}
    free_moment_count::Int
    moment_matrix::Matrix{Float64}
    minimum_eigenvalue::Float64
    equality_residual::Float64
    objective_residual::Float64
    block_cubic_proxy::Float64
    termination_status::MOI.TerminationStatusCode
    primal_status::MOI.ResultStatusCode
end

function NCProblem(name::AbstractString, generators::Vector{Symbol};
                   commuting_pairs=Tuple{Symbol,Symbol}[],
                   generator_characters::Vector{<:Integer}=zeros(Int, length(generators)),
                   group_rank::Integer=0,
                   hamiltonian,
                   order::Integer,
                   sense::Symbol=:Max)
    order >= 1 || throw(ArgumentError("moment order must be positive"))
    sense in (:Max, :Min) || throw(ArgumentError("sense must be :Max or :Min"))
    length(unique(generators)) == length(generators) ||
        throw(ArgumentError("generator names must be unique"))
    length(generator_characters) == length(generators) ||
        throw(ArgumentError("one character mask is required per generator"))
    0 <= group_rank <= 63 || throw(ArgumentError("group_rank must lie in 0:63"))
    limit = group_rank == 0 ? UInt64(0) : (UInt64(1) << group_rank) - UInt64(1)
    chars = UInt64.(generator_characters)
    all(c -> (c & ~limit) == 0, chars) ||
        throw(ArgumentError("generator character lies outside Z2^group_rank"))

    index = Dict(generator => i for (i, generator) in enumerate(generators))
    commuting = Set{Tuple{Int,Int}}()
    for (left, right) in commuting_pairs
        haskey(index, left) && haskey(index, right) ||
            throw(ArgumentError("commuting pair references an unknown generator"))
        i, j = index[left], index[right]
        i == j && continue
        push!(commuting, minmax(i, j))
    end

    terms = Dict{Word,Float64}()
    for (raw_word, coefficient) in hamiltonian
        word = Tuple(index[Symbol(generator)] for generator in raw_word)
        normalized = normalize_word(word, commuting)
        terms[normalized] = get(terms, normalized, 0.0) + Float64(coefficient)
    end
    filter!(term -> !iszero(last(term)), terms)
    maximum((length(word) for word in keys(terms)); init=0) <= 2order ||
        throw(ArgumentError("Hamiltonian degree exceeds twice the moment order"))

    problem = NCProblem(String(name), copy(generators), commuting, chars,
                        Int(group_rank), terms, Int(order), sense)
    for (word, coefficient) in problem.hamiltonian
        adjoint_word = normalize_word(reverse(word), problem.commuting_pairs)
        adjoint_coefficient = get(problem.hamiltonian, adjoint_word, 0.0)
        isapprox(coefficient, adjoint_coefficient; atol=1.0e-12, rtol=1.0e-12) ||
            throw(ArgumentError("Hamiltonian is not self-adjoint: coefficients of $(word) and $(adjoint_word) differ"))
        if !iszero(coefficient) && word_character(word, problem.generator_characters) != 0
            throw(ArgumentError("Hamiltonian is not invariant under Z2^$(problem.group_rank): $(word) has nontrivial character"))
        end
    end
    return problem
end

function _word_less(left::Word, right::Word)
    length(left) != length(right) && return length(left) < length(right)
    for i in eachindex(left)
        left[i] == right[i] || return left[i] < right[i]
    end
    return false
end

"""Canonical representative under g²=1 and only the declared commutations."""
function normalize_word(word, commuting_pairs::Set{Tuple{Int,Int}})
    start = Tuple(Int(generator) for generator in word)
    queue = Word[start]
    seen = Set{Word}([start])
    best = start
    cursor = 1
    while cursor <= length(queue)
        current = queue[cursor]
        cursor += 1
        _word_less(current, best) && (best = current)
        for i in 1:max(0, length(current) - 1)
            candidates = Word[]
            if current[i] == current[i + 1]
                push!(candidates, (current[1:i-1]..., current[i+2:end]...))
            end
            if minmax(current[i], current[i + 1]) in commuting_pairs
                push!(candidates, (current[1:i-1]..., current[i + 1], current[i], current[i+2:end]...))
            end
            for candidate in candidates
                if candidate ∉ seen
                    push!(seen, candidate)
                    push!(queue, candidate)
                end
            end
        end
    end
    return best
end

function enumerate_words(problem::NCProblem)
    words = Set{Word}([()])
    frontier = Set{Word}([()])
    for _ in 1:problem.order
        next_frontier = Set{Word}()
        for word in frontier, generator in eachindex(problem.generators)
            normalized = normalize_word((word..., generator), problem.commuting_pairs)
            push!(words, normalized)
            push!(next_frontier, normalized)
        end
        frontier = next_frontier
    end
    return sort!(collect(words); lt=_word_less)
end

function moment_key(word, commuting_pairs::Set{Tuple{Int,Int}})
    return normalize_word(word, commuting_pairs)
end

function _real_moment_key(word, commuting_pairs::Set{Tuple{Int,Int}})
    normalized = moment_key(word, commuting_pairs)
    reversed = moment_key(reverse(normalized), commuting_pairs)
    return _word_less(reversed, normalized) ? reversed : normalized
end

function word_character(word, generator_characters::Vector{UInt64})
    character = UInt64(0)
    for generator in word
        character ⊻= generator_characters[generator]
    end
    return character
end

function _strict_mosek_model()
    model = Model(MosekTools.Optimizer)
    set_silent(model)
    for (attribute, value) in (
        ("MSK_DPAR_INTPNT_CO_TOL_PFEAS", 1.0e-9),
        ("MSK_DPAR_INTPNT_CO_TOL_DFEAS", 1.0e-9),
        ("MSK_DPAR_INTPNT_CO_TOL_REL_GAP", 1.0e-9),
        ("MSK_DPAR_INTPNT_CO_TOL_INFEAS", 1.0e-10),
    )
        set_optimizer_attribute(model, attribute, value)
    end
    return model
end

function solve_moment_sdp(problem::NCProblem; formulation::Symbol=:dense)
    formulation in (:dense, :reduced) ||
        throw(ArgumentError("formulation must be :dense or :reduced"))
    basis = enumerate_words(problem)
    characters = [word_character(word, problem.generator_characters) for word in basis]
    sectors = Dict{UInt64,Vector{Int}}()
    for (index, character) in enumerate(characters)
        push!(get!(sectors, character, Int[]), index)
    end

    entry_words = [moment_key((reverse(left)..., right...), problem.commuting_pairs)
                   for left in basis, right in basis]
    entry_keys = [_real_moment_key(word, problem.commuting_pairs) for word in entry_words]
    keys = sort!(unique(vec(entry_keys)); lt=_word_less)
    invariant_keys = [key for key in keys
                      if word_character(key, problem.generator_characters) == 0]

    free_keys = formulation == :dense ? keys : invariant_keys
    model = _strict_mosek_model()
    @variable(model, y[free_keys])
    @constraint(model, y[()] == 1.0)
    function affine_entry(key)
        expression = AffExpr(0.0)
        if formulation == :dense || word_character(key, problem.generator_characters) == 0
            add_to_expression!(expression, 1.0, y[key])
        end
        return expression
    end
    pencil = [affine_entry(entry_keys[i, j]) for i in eachindex(basis), j in eachindex(basis)]

    if formulation == :dense
        @constraint(model, Symmetric(pencil) in PSDCone())
    else
        for indices in values(sectors)
            @constraint(model, Symmetric(pencil[indices, indices]) in PSDCone())
        end
    end

    objective = sum(coefficient * affine_entry(_real_moment_key(word, problem.commuting_pairs))
                    for (word, coefficient) in problem.hamiltonian)
    problem.sense == :Max ? @objective(model, Max, objective) : @objective(model, Min, objective)
    optimize!(model)

    termination = termination_status(model)
    primal = primal_status(model)
    termination in (MOI.OPTIMAL, MOI.ALMOST_OPTIMAL) ||
        error("Mosek did not solve $(problem.name) ($(formulation)): $(termination), $(primal)")

    values_by_key = Dict{Word,Float64}(key => value(y[key]) for key in free_keys)
    for key in keys
        get!(values_by_key, key, 0.0)
    end
    matrix = [values_by_key[entry_keys[i, j]] for i in eachindex(basis), j in eachindex(basis)]
    matrix = Matrix(Symmetric(matrix))
    reconstructed_objective = sum(coefficient * values_by_key[_real_moment_key(word, problem.commuting_pairs)]
                                  for (word, coefficient) in problem.hamiltonian)
    equality_residual = max(abs(values_by_key[()] - 1.0), norm(matrix - matrix', Inf))
    dimensions = length.(values(sectors))
    proxy = length(basis)^3 / sum(dimension^3 for dimension in dimensions)

    return SDPResult(formulation, objective_value(model), basis, sectors,
                     values_by_key, length(free_keys), matrix,
                     eigmin(Symmetric(matrix)), equality_residual,
                     abs(objective_value(model) - reconstructed_objective),
                     proxy, termination, primal)
end

function chsh_z2(; order::Integer=2)
    generators = [:A0, :A1, :B0, :B1]
    commuting = [(alice, bob) for alice in (:A0, :A1) for bob in (:B0, :B1)]
    hamiltonian = Dict(
        (:A0, :B0) => 1.0,
        (:A0, :B1) => 1.0,
        (:A1, :B0) => 1.0,
        (:A1, :B1) => -1.0,
    )
    return NCProblem("CHSH / Z2", generators;
                     commuting_pairs=commuting,
                     generator_characters=[0x1, 0x1, 0x1, 0x1],
                     group_rank=1, hamiltonian=hamiltonian,
                     order=order, sense=:Max)
end

function pauli_z2xz2(; order::Integer=2)
    generators = [:X1, :Z1, :X2, :Z2]
    commuting = [(left, right) for left in (:X1, :Z1) for right in (:X2, :Z2)]
    hamiltonian = Dict((:X1, :X2) => 1.0, (:Z1, :Z2) => 1.0)
    return NCProblem("two-site Pauli-style / Z2xZ2", generators;
                     commuting_pairs=commuting,
                     generator_characters=[0x1, 0x2, 0x1, 0x2],
                     group_rank=2, hamiltonian=hamiltonian,
                     order=order, sense=:Max)
end

end
