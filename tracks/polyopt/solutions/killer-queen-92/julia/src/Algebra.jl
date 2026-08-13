const QQ = Rational{BigInt}

"""An exact element of Q(sqrt(2),sqrt(3)) in the basis 1,sqrt2,sqrt3,sqrt6."""
struct Q23 <: Real
    a::QQ
    b::QQ
    c::QQ
    d::QQ
end

Q23(a::Rational, b::Rational=0//1, c::Rational=0//1, d::Rational=0//1) =
    Q23(QQ(a), QQ(b), QQ(c), QQ(d))
Q23(a::Integer=0) = Q23(QQ(a), QQ(0), QQ(0), QQ(0))
Q23(a::AbstractFloat) = Q23(rationalize(BigInt, a))

const SQRT2 = Q23(0//1, 1//1)
const SQRT3 = Q23(0//1, 0//1, 1//1)
const AQ = Complex{Q23}

Base.zero(::Type{Q23}) = Q23(0)
Base.zero(::Q23) = Q23(0)
Base.one(::Type{Q23}) = Q23(1)
Base.one(::Q23) = Q23(1)
Base.iszero(x::Q23) = iszero(x.a) && iszero(x.b) && iszero(x.c) && iszero(x.d)
Base.:(==)(x::Q23, y::Q23) = x.a == y.a && x.b == y.b && x.c == y.c && x.d == y.d
Base.hash(x::Q23, h::UInt) = hash((x.a, x.b, x.c, x.d), h)
Base.:+(x::Q23, y::Q23) = Q23(x.a+y.a, x.b+y.b, x.c+y.c, x.d+y.d)
Base.:-(x::Q23, y::Q23) = Q23(x.a-y.a, x.b-y.b, x.c-y.c, x.d-y.d)
Base.:-(x::Q23) = Q23(-x.a, -x.b, -x.c, -x.d)
function Base.:*(x::Q23, y::Q23)
    Q23(
        x.a*y.a + 2*x.b*y.b + 3*x.c*y.c + 6*x.d*y.d,
        x.a*y.b + x.b*y.a + 3*x.c*y.d + 3*x.d*y.c,
        x.a*y.c + x.c*y.a + 2*x.b*y.d + 2*x.d*y.b,
        x.a*y.d + x.d*y.a + x.b*y.c + x.c*y.b,
    )
end
function _field_conjugate(x::Q23, sqrt2_sign::Int, sqrt3_sign::Int)
    Q23(x.a, sqrt2_sign*x.b, sqrt3_sign*x.c, sqrt2_sign*sqrt3_sign*x.d)
end
function Base.inv(x::Q23)
    iszero(x) && throw(DivideError())
    numerator = _field_conjugate(x, -1, 1) * _field_conjugate(x, 1, -1) *
                _field_conjugate(x, -1, -1)
    denominator = x * numerator
    @assert iszero(denominator.b) && iszero(denominator.c) && iszero(denominator.d)
    numerator * Q23(inv(denominator.a))
end
Base.:/(x::Q23, y::Q23) = x * inv(y)
Base.:^(x::Q23, n::Integer) = n < 0 ? inv(x^(-n)) : Base.power_by_squaring(x, n)
Base.abs2(x::Q23) = x*x
Base.abs(x::Q23) = abs(Float64(x))
Base.real(x::Q23) = x
Base.imag(::Q23) = Q23(0)
Base.conj(x::Q23) = x
Base.convert(::Type{Q23}, x::Integer) = Q23(x)
Base.convert(::Type{Q23}, x::Rational) = Q23(x)
Base.convert(::Type{Q23}, x::AbstractFloat) = Q23(x)
Base.convert(::Type{Float64}, x::Q23) =
    Float64(x.a) + Float64(x.b)*sqrt(2.0) + Float64(x.c)*sqrt(3.0) + Float64(x.d)*sqrt(6.0)
Base.Float64(x::Q23) = convert(Float64, x)
Base.promote_rule(::Type{Q23}, ::Type{<:Integer}) = Q23
Base.promote_rule(::Type{Q23}, ::Type{<:Rational}) = Q23
Base.promote_rule(::Type{Q23}, ::Type{<:AbstractFloat}) = Q23

function _q23_arb(x::Q23,precision::Int=256)
    q(v) = Arblib.Arb(numerator(v);prec=precision)/Arblib.Arb(denominator(v);prec=precision)
    q(x.a)+q(x.b)*sqrt(Arblib.Arb(2;prec=precision))+
    q(x.c)*sqrt(Arblib.Arb(3;prec=precision))+
    q(x.d)*sqrt(Arblib.Arb(6;prec=precision))
end

function _q23_sign(x::Q23;precision=256)
    iszero(x) && return 0
    value = _q23_arb(x,precision)
    Arblib.ispositive(value) && return 1
    Arblib.isnegative(value) && return -1
    precision >= 4096 && error("Arb could not isolate the sign of a nonzero Q(sqrt2,sqrt3) element")
    _q23_sign(x;precision=2precision)
end

Base.isless(x::Q23, y::Q23) = _q23_sign(x-y)<0
Base.:<(x::Q23,y::Q23) = isless(x,y)
Base.signbit(x::Q23) = x < Q23(0)

function Base.show(io::IO, x::Q23)
    parts = String[]
    for (coefficient, radical) in ((x.a, ""), (x.b, "sqrt(2)"),
                                   (x.c, "sqrt(3)"), (x.d, "sqrt(6)"))
        iszero(coefficient) && continue
        push!(parts, isempty(radical) ? string(coefficient) : "$(coefficient)*$(radical)")
    end
    print(io, isempty(parts) ? "0" : join(parts, " + "))
end

aq(x::Q23) = AQ(x, Q23(0))
aq(x::Integer) = aq(Q23(x))
aq(x::Rational) = aq(Q23(x))

"""A nonidentity local basis element E_rs."""
struct LocalAtom
    r::Int
    s::Int
end

"""Exact filtered coordinates for one copy of the cutoff matrix algebra.

`LocalAtom` values are stable coordinate labels.  In the matrix encoding the
label `(r,s)` denotes `E_rs`.  In the ladder encoding it denotes an exact,
charge-homogeneous linear combination of matrix units chosen by graded row
reduction.  The label transpose always denotes the adjoint combination.
"""
struct LocalBasisData
    nmax::Int
    encoding::Symbol
    atoms::Vector{LocalAtom}
    degrees::Dict{LocalAtom,Int}
    matrices::Dict{LocalAtom,Matrix{Q23}}
    coordinate_inverse::Matrix{Q23}
    products::Dict{Tuple{LocalAtom,LocalAtom},Vector{Tuple{Union{Nothing,LocalAtom},Q23}}}
    raw_expansions::Dict{LocalAtom,Vector{Tuple{Union{Nothing,LocalAtom},Q23}}}
end

charge(a::LocalAtom) = a.r - a.s
Base.adjoint(a::LocalAtom) = LocalAtom(a.s, a.r)
Base.isless(a::LocalAtom, b::LocalAtom) = (a.r, a.s) < (b.r, b.s)

"""Canonical tensor-product word, with factors `(site,r,s)` sorted by site."""
struct OperatorWord
    factors::Tuple{Vararg{NTuple{3,Int}}}
    function OperatorWord(factors::Tuple{Vararg{NTuple{3,Int}}}=())
        issorted(factors; by=first) || throw(ArgumentError("operator factors must be site sorted"))
        length(unique(first.(factors))) == length(factors) ||
            throw(ArgumentError("at most one local factor is allowed per site"))
        new(factors)
    end
end

OperatorWord(factors::AbstractVector{<:NTuple{3,Int}}) = OperatorWord(tuple(factors...))
Base.isless(a::OperatorWord, b::OperatorWord) = isless(a.factors, b.factors)
Base.show(io::IO, w::OperatorWord) = print(io, isempty(w.factors) ? "I" : join(("E$(r)$(s)@$(i)" for (i,r,s) in w.factors), "*"))
isidentity(w::OperatorWord) = isempty(w.factors)
support(w::OperatorWord) = Tuple(f[1] for f in w.factors)
charge(w::OperatorWord) = sum(f[2]-f[3] for f in w.factors; init=0)
Base.adjoint(w::OperatorWord) = OperatorWord([(i,s,r) for (i,r,s) in w.factors])

function local_basis(nmax::Int)
    nmax >= 1 || throw(ArgumentError("nmax must be positive"))
    atoms = LocalAtom[LocalAtom(r,r) for r in 1:nmax]
    append!(atoms, LocalAtom(r,s) for r in 0:nmax for s in 0:nmax if r != s)
    sort!(atoms)
    atoms
end

function _multiply_atoms(a::Union{Nothing,LocalAtom}, b::Union{Nothing,LocalAtom}, nmax::Int)
    a === nothing && return [(b, Q23(1))]
    b === nothing && return [(a, Q23(1))]
    a.s == b.r || return Tuple{Union{Nothing,LocalAtom},Q23}[]
    if a.r == 0 && b.s == 0
        result = Tuple{Union{Nothing,LocalAtom},Q23}[(nothing, Q23(1))]
        append!(result, (LocalAtom(r,r), Q23(-1)) for r in 1:nmax)
        return result
    end
    [(LocalAtom(a.r,b.s), Q23(1))]
end

"""Multiply canonical words in a common exact local coordinate basis."""
function multiply_words(a::OperatorWord, b::OperatorWord, basis::LocalBasisData)
    amap = Dict(i => LocalAtom(r,s) for (i,r,s) in a.factors)
    bmap = Dict(i => LocalAtom(r,s) for (i,r,s) in b.factors)
    sites = sort!(collect(union(keys(amap), keys(bmap))))
    partial = [(NTuple{3,Int}[], Q23(1))]
    for site in sites
        left = get(amap,site,nothing)
        right = get(bmap,site,nothing)
        choices = if left === nothing
            [(right,Q23(1))]
        elseif right === nothing
            [(left,Q23(1))]
        else
            basis.products[(left,right)]
        end
        isempty(choices) && return Dict{OperatorWord,AQ}()
        next = Tuple{Vector{NTuple{3,Int}},Q23}[]
        for (factors, coefficient) in partial, (atom, local_coefficient) in choices
            newfactors = copy(factors)
            atom === nothing || push!(newfactors, (site,atom.r,atom.s))
            push!(next, (newfactors, coefficient*local_coefficient))
        end
        partial = next
    end
    result = Dict{OperatorWord,AQ}()
    for (factors, coefficient) in partial
        word = OperatorWord(factors)
        result[word] = get(result, word, aq(0)) + aq(coefficient)
    end
    filter!(p -> !iszero(last(p)), result)
    result
end

function _sqrt_occupation(r::Int)
    r == 0 && return Q23(0)
    r == 1 && return Q23(1)
    r == 2 && return SQRT2
    r == 3 && return SQRT3
    throw(ArgumentError("Q(sqrt2,sqrt3) supports ladder coefficients only through nmax=3"))
end

function _matmul(a::Matrix{Q23}, b::Matrix{Q23})
    size(a,2) == size(b,1) || throw(DimensionMismatch())
    c = fill(Q23(0), size(a,1), size(b,2))
    for i in axes(a,1), k in axes(a,2), j in axes(b,2)
        iszero(a[i,k]) || iszero(b[k,j]) || (c[i,j] += a[i,k]*b[k,j])
    end
    c
end

function ladder_matrices(nmax::Int)
    d = nmax + 1
    b = fill(Q23(0), d, d)
    for occupation in 1:nmax
        b[occupation, occupation+1] = _sqrt_occupation(occupation)
    end
    b, permutedims(b)
end

function _row_rank(rows::Vector{Vector{Q23}})
    isempty(rows) && return 0
    a = reduce(vcat, (permutedims(row) for row in rows))
    m, n = size(a)
    rank = 0
    pivot_col = 1
    while rank < m && pivot_col <= n
        pivot = findfirst(i -> !iszero(a[i,pivot_col]), rank+1:m)
        if pivot === nothing
            pivot_col += 1
            continue
        end
        pivot += rank
        a[rank+1,:], a[pivot,:] = copy(a[pivot,:]), copy(a[rank+1,:])
        scale = inv(a[rank+1,pivot_col])
        a[rank+1,:] .*= scale
        for i in 1:m
            i == rank+1 && continue
            factor = a[i,pivot_col]
            iszero(factor) || (a[i,:] .-= factor .* a[rank+1,:])
        end
        rank += 1
        pivot_col += 1
    end
    rank
end

_flatten(a::Matrix{Q23}) = collect(vec(a))
_in_span(target::Vector{Q23}, rows::Vector{Vector{Q23}}) =
    _row_rank(rows) == _row_rank([rows; [target]])

function _identity_q23(dim::Int)
    matrix = fill(Q23(0),dim,dim)
    for index in 1:dim
        matrix[index,index] = Q23(1)
    end
    matrix
end

function _matrix_unit(nmax::Int,atom::LocalAtom)
    matrix = fill(Q23(0),nmax+1,nmax+1)
    matrix[atom.r+1,atom.s+1] = Q23(1)
    matrix
end

function _inverse_exact(matrix::Matrix{Q23})
    rows,columns = size(matrix)
    rows == columns || throw(DimensionMismatch("exact inverse requires a square matrix"))
    augmented = [copy(matrix) _identity_q23(rows)]
    for column in 1:columns
        pivot = findfirst(row -> !iszero(augmented[row,column]),column:rows)
        pivot === nothing && throw(ArgumentError("local coordinate basis is linearly dependent"))
        pivot += column-1
        if pivot != column
            augmented[column,:],augmented[pivot,:] =
                copy(augmented[pivot,:]),copy(augmented[column,:])
        end
        augmented[column,:] .*= inv(augmented[column,column])
        for row in 1:rows
            row == column && continue
            coefficient = augmented[row,column]
            iszero(coefficient) || (augmented[row,:] .-= coefficient .* augmented[column,:])
        end
    end
    augmented[:,columns+1:end]
end

function _coordinate_vector(inverse::Matrix{Q23},matrix::Matrix{Q23})
    target = _flatten(matrix)
    size(inverse,2) == length(target) || throw(DimensionMismatch())
    coordinates = fill(Q23(0),size(inverse,1))
    for row in axes(inverse,1),column in axes(inverse,2)
        iszero(inverse[row,column]) || iszero(target[column]) ||
            (coordinates[row] += inverse[row,column]*target[column])
    end
    coordinates
end

function _coordinate_expansion(coordinates::Vector{Q23},atoms::Vector{LocalAtom})
    length(coordinates) == length(atoms)+1 || throw(DimensionMismatch())
    expansion = Tuple{Union{Nothing,LocalAtom},Q23}[]
    iszero(coordinates[1]) || push!(expansion,(nothing,coordinates[1]))
    for (atom,coefficient) in zip(atoms,coordinates[2:end])
        iszero(coefficient) || push!(expansion,(atom,coefficient))
    end
    expansion
end

function _finish_local_basis(nmax::Int,encoding::Symbol,atoms::Vector{LocalAtom},
                             degrees::Dict{LocalAtom,Int},
                             matrices::Dict{LocalAtom,Matrix{Q23}})
    dim = nmax+1
    coordinate_matrix = Matrix{Q23}(undef,dim^2,dim^2)
    coordinate_matrix[:,1] = _flatten(_identity_q23(dim))
    for (column,atom) in enumerate(atoms)
        coordinate_matrix[:,column+1] = _flatten(matrices[atom])
    end
    inverse = _inverse_exact(coordinate_matrix)
    products = Dict{Tuple{LocalAtom,LocalAtom},
                    Vector{Tuple{Union{Nothing,LocalAtom},Q23}}}()
    for left in atoms,right in atoms
        coordinates = _coordinate_vector(inverse,_matmul(matrices[left],matrices[right]))
        products[(left,right)] = _coordinate_expansion(coordinates,atoms)
    end
    raw_expansions = Dict{LocalAtom,Vector{Tuple{Union{Nothing,LocalAtom},Q23}}}()
    for atom in atoms
        coordinates = _coordinate_vector(inverse,_matrix_unit(nmax,atom))
        raw_expansions[atom] = _coordinate_expansion(coordinates,atoms)
    end
    LocalBasisData(nmax,encoding,atoms,degrees,matrices,inverse,products,raw_expansions)
end

function _matrix_basis_data(nmax::Int)
    atoms = local_basis(nmax)
    degrees = Dict(atom=>1 for atom in atoms)
    matrices = Dict(atom=>_matrix_unit(nmax,atom) for atom in atoms)
    _finish_local_basis(nmax,:matrix,atoms,degrees,matrices)
end

function _normalize_direction(matrix::Matrix{Q23})
    pivot = findfirst(!iszero,matrix)
    pivot === nothing && return matrix
    matrix .* inv(matrix[pivot])
end

"""A charge-adapted basis selected by exact graded row reduction of ladder words."""
function _ladder_basis_data(nmax::Int)
    b, bd = ladder_matrices(nmax)
    dim = nmax + 1
    identity_matrix = _identity_q23(dim)
    frontier = Tuple{Matrix{Q23},Int}[(identity_matrix,0)]
    selected = Dict{Int,Vector{Tuple{Int,Matrix{Q23}}}}(
        q=>Tuple{Int,Matrix{Q23}}[] for q in 0:nmax
    )
    selected_dimension() = 1+length(selected[0])+
        2sum(length(selected[q]) for q in 1:nmax;init=0)

    for word_degree in 1:4nmax+4
        next_frontier = Tuple{Matrix{Q23},Int}[]
        seen = Set{Tuple{Int,Tuple}}()
        for (word,word_charge) in frontier,(generator,generator_charge) in ((b,-1),(bd,1))
            candidate = _matmul(word,generator)
            all(iszero,candidate) && continue
            candidate = _normalize_direction(candidate)
            candidate_charge = word_charge+generator_charge
            abs(candidate_charge) <= nmax || continue
            key = (candidate_charge,Tuple(_flatten(candidate)))
            key in seen && continue
            push!(seen,key)
            push!(next_frontier,(candidate,candidate_charge))
        end
        frontier = next_frontier

        # Charge conjugation maps the positive and negative sectors exactly,
        # so select the nonnegative sector and add its adjoint partner below.
        for q in 0:nmax
            target_count = q == 0 ? nmax : dim-q
            length(selected[q]) >= target_count && continue
            rows = Vector{Vector{Q23}}()
            q == 0 && push!(rows,_flatten(identity_matrix))
            append!(rows,_flatten(matrix) for (_,matrix) in selected[q])
            for (candidate,candidate_charge) in frontier
                candidate_charge == q || continue
                direction = _flatten(candidate)
                _in_span(direction,rows) && continue
                q == 0 && candidate != permutedims(candidate) &&
                    error("neutral ladder word was not self-adjoint")
                push!(selected[q],(word_degree,candidate))
                push!(rows,direction)
                length(selected[q]) == target_count && break
            end
        end
        selected_dimension() == dim^2 && break
    end
    selected_dimension() == dim^2 || error(
        "graded ladder words span only $(selected_dimension()) of $(dim^2) local directions",
    )

    atoms = local_basis(nmax)
    degrees = Dict{LocalAtom,Int}()
    matrices = Dict{LocalAtom,Matrix{Q23}}()
    diagonal_labels = sort!([atom for atom in atoms if charge(atom)==0])
    for (label,(word_degree,matrix)) in zip(diagonal_labels,selected[0])
        degrees[label] = word_degree
        matrices[label] = matrix
    end
    for q in 1:nmax
        positive_labels = sort!([atom for atom in atoms if charge(atom)==q])
        length(positive_labels) == length(selected[q]) || error("charge-$q basis dimension mismatch")
        for (label,(word_degree,matrix)) in zip(positive_labels,selected[q])
            partner = adjoint(label)
            degrees[label] = degrees[partner] = word_degree
            matrices[label] = matrix
            matrices[partner] = permutedims(matrix)
        end
    end
    length(matrices) == length(atoms) || error("incomplete adapted ladder basis")
    _finish_local_basis(nmax,:ladder,atoms,degrees,matrices)
end

const _LOCAL_BASIS_CACHE = Dict{Tuple{Int,Symbol},LocalBasisData}()
const _LOCAL_BASIS_LOCK = ReentrantLock()

function local_basis_data(nmax::Int,encoding::Symbol)
    encoding in (:matrix,:ladder) || throw(ArgumentError("encoding must be :matrix or :ladder"))
    lock(_LOCAL_BASIS_LOCK) do
        get!(_LOCAL_BASIS_CACHE,(nmax,encoding)) do
            encoding == :matrix ? _matrix_basis_data(nmax) : _ladder_basis_data(nmax)
        end
    end
end

"""Filtered degrees of the exact local ladder-adapted basis directions."""
ladder_degrees(nmax::Int) = copy(local_basis_data(nmax,:ladder).degrees)

"""Expand a word written in raw matrix units into the selected coordinates."""
function rebase_word(word::OperatorWord,basis::LocalBasisData)
    partial = Dict(OperatorWord()=>Q23(1))
    for (site,r,s) in word.factors
        choices = basis.raw_expansions[LocalAtom(r,s)]
        next = Dict{OperatorWord,Q23}()
        for (prefix,prefix_coefficient) in partial,(label,coefficient) in choices
            factors = NTuple{3,Int}[prefix.factors...]
            label === nothing || push!(factors,(site,label.r,label.s))
            rebased = OperatorWord(factors)
            next[rebased] = get(next,rebased,Q23(0))+prefix_coefficient*coefficient
        end
        filter!(pair->!iszero(last(pair)),next)
        partial = next
    end
    partial
end

"""Compatibility path: integer cutoff means the raw independent matrix basis."""
multiply_words(a::OperatorWord,b::OperatorWord,nmax::Int) =
    multiply_words(a,b,local_basis_data(nmax,:matrix))

function atom_degree(atom::LocalAtom, encoding::Symbol, ladder::Dict{LocalAtom,Int})
    encoding == :matrix && return 1
    encoding == :ladder && return ladder[atom]
    throw(ArgumentError("encoding must be :matrix or :ladder"))
end

function degree(w::OperatorWord, encoding::Symbol, ladder::Dict{LocalAtom,Int})
    sum(atom_degree(LocalAtom(r,s),encoding,ladder) for (_,r,s) in w.factors; init=0)
end
