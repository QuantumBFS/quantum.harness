struct GeneratorSystem
    names::Tuple{Vararg{Symbol}}
    adjoint::Tuple{Vararg{Int}}
    function GeneratorSystem(names; adjoint=nothing)
        symbols = Tuple(Symbol.(names))
        length(unique(symbols)) == length(symbols) ||
            throw(ArgumentError("generator names must be unique"))
        map = adjoint === nothing ? Tuple(eachindex(symbols)) : Tuple(Int.(adjoint))
        length(map) == length(symbols) ||
            throw(ArgumentError("one adjoint image is required per generator"))
        all(i -> i in eachindex(symbols), map) ||
            throw(ArgumentError("adjoint map references an unknown generator"))
        all(i -> map[map[i]] == i, eachindex(map)) ||
            throw(ArgumentError("generator adjoint map must be involutive"))
        new(symbols, map)
    end
end

struct NCWord
    letters::Tuple{Vararg{Int}}
end
NCWord() = NCWord(())
NCWord(letters::AbstractVector{<:Integer}) = NCWord(Tuple(Int.(letters)))
NCWord(letters::Vararg{Int}) = NCWord(letters)
Base.length(word::NCWord) = length(word.letters)
Base.isempty(word::NCWord) = isempty(word.letters)
Base.iterate(word::NCWord, state...) = iterate(word.letters, state...)
Base.getindex(word::NCWord, index::Int) = word.letters[index]
Base.reverse(word::NCWord) = NCWord(reverse(word.letters))
Base.show(io::IO, word::NCWord) = print(io, "NCWord", word.letters)

function _word_less(left::NCWord, right::NCWord)
    length(left) != length(right) && return length(left) < length(right)
    return left.letters < right.letters
end

struct ReducedMonomial
    phase::ComplexF64
    word::NCWord
end

abstract type StarAlgebraBackend end
generators(::StarAlgebraBackend) = error("backend must implement generators")
reduce_word(::StarAlgebraBackend, ::NCWord) = error("backend must implement reduce_word")

struct LegacyInvolutionBackend <: StarAlgebraBackend
    system::GeneratorSystem
    commuting_pairs::Set{Tuple{Int,Int}}
end
generators(backend::LegacyInvolutionBackend) = backend.system

function LegacyInvolutionBackend(names; adjoint=nothing, commuting_pairs=Tuple{Symbol,Symbol}[])
    system = GeneratorSystem(names; adjoint=adjoint)
    index = Dict(name => i for (i, name) in enumerate(system.names))
    pairs = Set{Tuple{Int,Int}}()
    for (left, right) in commuting_pairs
        haskey(index, Symbol(left)) && haskey(index, Symbol(right)) ||
            throw(ArgumentError("commuting pair references an unknown generator"))
        i, j = index[Symbol(left)], index[Symbol(right)]
        i == j || push!(pairs, minmax(i, j))
    end
    return LegacyInvolutionBackend(system, pairs)
end

"""Legacy canonical representative under g²=1 and declared partial commutations."""
function normalize_word(word, commuting_pairs::Set{Tuple{Int,Int}})
    start = NCWord(Tuple(Int.(word)))
    queue = NCWord[start]
    seen = Set{NCWord}([start])
    best = start
    cursor = 1
    while cursor <= length(queue)
        current = queue[cursor]
        cursor += 1
        _word_less(current, best) && (best = current)
        letters = current.letters
        for i in 1:max(0, length(letters) - 1)
            candidates = NCWord[]
            if letters[i] == letters[i + 1]
                push!(candidates, NCWord((letters[1:i-1]..., letters[i+2:end]...)))
            end
            if minmax(letters[i], letters[i + 1]) in commuting_pairs
                push!(candidates, NCWord((letters[1:i-1]..., letters[i + 1], letters[i], letters[i+2:end]...)))
            end
            for candidate in candidates
                if candidate ∉ seen
                    push!(seen, candidate)
                    push!(queue, candidate)
                end
            end
        end
    end
    return best.letters
end

function reduce_word(backend::LegacyInvolutionBackend, word::NCWord)
    all(i -> i in eachindex(backend.system.names), word) ||
        throw(ArgumentError("word references an unknown generator"))
    return ReducedMonomial(1.0 + 0.0im, NCWord(normalize_word(word.letters, backend.commuting_pairs)))
end

struct PauliBackend <: StarAlgebraBackend
    system::GeneratorSystem
    sites::Tuple{Vararg{Int}}
    axes::Tuple{Vararg{Symbol}}
    lookup::Dict{Tuple{Int,Symbol},Int}
end
generators(backend::PauliBackend) = backend.system

function PauliBackend(specifications)
    names = Symbol[first(spec) for spec in specifications]
    sites = Tuple(Int(spec[2]) for spec in specifications)
    axes = Tuple(Symbol(spec[3]) for spec in specifications)
    all(axis -> axis in (:X, :Y, :Z), axes) ||
        throw(ArgumentError("Pauli axes must be X, Y, or Z"))
    system = GeneratorSystem(names)
    lookup = Dict{Tuple{Int,Symbol},Int}()
    for i in eachindex(names)
        key = (sites[i], axes[i])
        haskey(lookup, key) && throw(ArgumentError("duplicate Pauli site/axis generator"))
        lookup[key] = i
    end
    for site in unique(sites), axis in (:X, :Y, :Z)
        haskey(lookup, (site, axis)) ||
            throw(ArgumentError("Pauli backend requires X, Y, and Z generators at every site"))
    end
    return PauliBackend(system, sites, axes, lookup)
end

const _PAULI_PRODUCT = Dict{Tuple{Symbol,Symbol},Tuple{ComplexF64,Union{Nothing,Symbol}}}(
    (:X, :X) => (1.0 + 0.0im, nothing),
    (:Y, :Y) => (1.0 + 0.0im, nothing),
    (:Z, :Z) => (1.0 + 0.0im, nothing),
    (:X, :Y) => (0.0 + 1.0im, :Z),
    (:Y, :Z) => (0.0 + 1.0im, :X),
    (:Z, :X) => (0.0 + 1.0im, :Y),
    (:Y, :X) => (0.0 - 1.0im, :Z),
    (:Z, :Y) => (0.0 - 1.0im, :X),
    (:X, :Z) => (0.0 - 1.0im, :Y),
)

function reduce_word(backend::PauliBackend, word::NCWord)
    all(i -> i in eachindex(backend.system.names), word) ||
        throw(ArgumentError("word references an unknown generator"))
    phase = 1.0 + 0.0im
    by_site = Dict{Int,Symbol}()
    for generator in word
        site, incoming = backend.sites[generator], backend.axes[generator]
        if !haskey(by_site, site)
            by_site[site] = incoming
        else
            factor, output = _PAULI_PRODUCT[(by_site[site], incoming)]
            phase *= factor
            output === nothing ? delete!(by_site, site) : (by_site[site] = output)
        end
    end
    letters = Tuple(backend.lookup[(site, by_site[site])] for site in sort!(collect(keys(by_site))))
    return ReducedMonomial(ComplexF64(phase), NCWord(letters))
end

function star_word(backend::StarAlgebraBackend, word::NCWord)
    system = generators(backend)
    mapped = NCWord(Tuple(system.adjoint[i] for i in reverse(word.letters)))
    return reduce_word(backend, mapped)
end

struct NCPolynomial
    terms::Dict{NCWord,ComplexF64}
end
NCPolynomial() = NCPolynomial(Dict{NCWord,ComplexF64}())

function polynomial(backend::StarAlgebraBackend, raw_terms)
    system = generators(backend)
    index = Dict(name => i for (i, name) in enumerate(system.names))
    terms = Dict{NCWord,ComplexF64}()
    for (raw_word, coefficient) in raw_terms
        letters = raw_word isa NCWord ? raw_word : NCWord(Tuple(index[Symbol(name)] for name in raw_word))
        reduced = reduce_word(backend, letters)
        terms[reduced.word] = get(terms, reduced.word, 0.0 + 0.0im) + ComplexF64(coefficient) * reduced.phase
    end
    filter!(pair -> abs(last(pair)) > 1.0e-14, terms)
    return NCPolynomial(terms)
end

coefficient(poly::NCPolynomial, word::NCWord) = get(poly.terms, word, 0.0 + 0.0im)

function star(backend::StarAlgebraBackend, poly::NCPolynomial)
    terms = Dict{NCWord,ComplexF64}()
    for (word, coefficient) in poly.terms
        reduced = star_word(backend, word)
        terms[reduced.word] = get(terms, reduced.word, 0.0 + 0.0im) + conj(coefficient) * reduced.phase
    end
    return NCPolynomial(terms)
end

function _isapprox_polynomial(left::NCPolynomial, right::NCPolynomial; atol=1.0e-12)
    words = union(keys(left.terms), keys(right.terms))
    return all(word -> abs(coefficient(left, word) - coefficient(right, word)) <= atol, words)
end

function _multiply(backend::StarAlgebraBackend, left::NCWord, right::NCWord)
    return reduce_word(backend, NCWord((left.letters..., right.letters...)))
end

moment_key(word, commuting_pairs::Set{Tuple{Int,Int}}) = normalize_word(word, commuting_pairs)

function word_character(word, generator_characters::AbstractVector{UInt64})
    character = UInt64(0)
    for generator in word
        character ⊻= generator_characters[generator]
    end
    return character
end
