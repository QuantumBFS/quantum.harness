"""Coefficient affine in the four run-time parameters."""
struct ParamCoeff
    constant::AQ
    t::AQ
    U::AQ
    mu::AQ
    gamma::AQ
end

ParamCoeff() = ParamCoeff(aq(0),aq(0),aq(0),aq(0),aq(0))
ParamCoeff(x::AQ) = ParamCoeff(x,aq(0),aq(0),aq(0),aq(0))
ParamCoeff(x::Q23) = ParamCoeff(aq(x))
ParamCoeff(x::Integer) = ParamCoeff(aq(x))
Base.zero(::Type{ParamCoeff}) = ParamCoeff()
Base.zero(::ParamCoeff) = ParamCoeff()
Base.iszero(x::ParamCoeff) = all(iszero, (x.constant,x.t,x.U,x.mu,x.gamma))
Base.:(==)(x::ParamCoeff,y::ParamCoeff) =
    x.constant == y.constant && x.t == y.t && x.U == y.U &&
    x.mu == y.mu && x.gamma == y.gamma
Base.:+(x::ParamCoeff,y::ParamCoeff) = ParamCoeff(x.constant+y.constant,x.t+y.t,x.U+y.U,x.mu+y.mu,x.gamma+y.gamma)
Base.:-(x::ParamCoeff,y::ParamCoeff) = ParamCoeff(x.constant-y.constant,x.t-y.t,x.U-y.U,x.mu-y.mu,x.gamma-y.gamma)
Base.:-(x::ParamCoeff) = ParamCoeff(-x.constant,-x.t,-x.U,-x.mu,-x.gamma)
Base.:*(x::ParamCoeff,y::AQ) = ParamCoeff(x.constant*y,x.t*y,x.U*y,x.mu*y,x.gamma*y)
Base.:*(y::AQ,x::ParamCoeff) = x*y
Base.:*(x::ParamCoeff,y::Q23) = x*aq(y)
Base.:*(y::Q23,x::ParamCoeff) = x*y
Base.:/(x::ParamCoeff,y::Integer) = x*aq(Q23(1//y))
function Base.:*(x::ParamCoeff,y::ParamCoeff)
    xparam = !all(iszero,(x.t,x.U,x.mu,x.gamma))
    yparam = !all(iszero,(y.t,y.U,y.mu,y.gamma))
    xparam && yparam && throw(ArgumentError("non-affine parameter product requested"))
    xparam ? x*y.constant : y*x.constant
end

const PARAM_T = ParamCoeff(aq(0),aq(1),aq(0),aq(0),aq(0))
const PARAM_U = ParamCoeff(aq(0),aq(0),aq(1),aq(0),aq(0))
const PARAM_MU = ParamCoeff(aq(0),aq(0),aq(0),aq(1),aq(0))
const PARAM_GAMMA = ParamCoeff(aq(0),aq(0),aq(0),aq(0),aq(1))

function evaluate(x::ParamCoeff, params::ModelParams)
    x.constant + x.t*aq(params.t) + x.U*aq(params.U) +
    x.mu*aq(params.mu) + x.gamma*aq(params.gamma)
end

"""A commutative product of formal state symbols varsigma(w)."""
struct PureStateMonomial
    factors::Tuple{Vararg{OperatorWord}}
    function PureStateMonomial(factors::Tuple{Vararg{OperatorWord}}=())
        cleaned = [w for w in factors if !isidentity(w)]
        sort!(cleaned)
        new(tuple(cleaned...))
    end
end
PureStateMonomial(factors::AbstractVector) =
    PureStateMonomial(tuple((factor::OperatorWord for factor in factors)...))
Base.isless(a::PureStateMonomial,b::PureStateMonomial) = isless(a.factors,b.factors)
Base.adjoint(m::PureStateMonomial) = PureStateMonomial([adjoint(w) for w in m.factors])
Base.:*(a::PureStateMonomial,b::PureStateMonomial) = PureStateMonomial([a.factors...; b.factors...])
Base.show(io::IO,m::PureStateMonomial) = print(io, isempty(m.factors) ? "1" : join(("s($(w))" for w in m.factors),"*"))

"""A commutative state part times one canonical noncommutative operator word."""
struct StateMonomial
    states::PureStateMonomial
    operator::OperatorWord
end
StateMonomial() = StateMonomial(PureStateMonomial(),OperatorWord())
Base.isless(a::StateMonomial,b::StateMonomial) =
    a.states == b.states ? isless(a.operator,b.operator) : isless(a.states,b.states)
Base.adjoint(m::StateMonomial) = StateMonomial(adjoint(m.states),adjoint(m.operator))
Base.show(io::IO,m::StateMonomial) = print(io,m.states," | ",m.operator)

function support(m::PureStateMonomial)
    result = Int[]
    for word in m.factors
        append!(result,support(word))
    end
    sort!(unique!(result))
end
support(m::StateMonomial) = sort!(unique!([support(m.states); collect(support(m.operator))]))
charge(m::PureStateMonomial) = sum(charge(w) for w in m.factors; init=0)
charge(m::StateMonomial) = charge(m.states)+charge(m.operator)
degree(m::PureStateMonomial,encoding::Symbol,ladder) =
    sum(degree(w,encoding,ladder) for w in m.factors; init=0)
degree(m::StateMonomial,encoding::Symbol,ladder) =
    degree(m.states,encoding,ladder)+degree(m.operator,encoding,ladder)

const StatePoly = Dict{StateMonomial,ParamCoeff}
const MomentExpr = Dict{PureStateMonomial,ParamCoeff}

function _add_term!(poly::Dict{K,ParamCoeff}, key::K, coefficient::ParamCoeff) where K
    iszero(coefficient) && return poly
    poly[key] = get(poly,key,ParamCoeff()) + coefficient
    iszero(poly[key]) && delete!(poly,key)
    poly
end

monomial_poly(m::StateMonomial, c::ParamCoeff=ParamCoeff(1)) = StatePoly(m=>c)

function add_poly(a::StatePoly,b::StatePoly; scale=ParamCoeff(1))
    result = copy(a)
    for (m,c) in b
        _add_term!(result,m,c*scale)
    end
    result
end

function scale_poly(a::StatePoly,c::ParamCoeff)
    result = StatePoly()
    for (m,x) in a
        _add_term!(result,m,x*c)
    end
    result
end

function adjoint_poly(a::StatePoly)
    result = StatePoly()
    for (m,c) in a
        coefficient = ParamCoeff(conj(c.constant),conj(c.t),conj(c.U),conj(c.mu),conj(c.gamma))
        _add_term!(result,adjoint(m),coefficient)
    end
    result
end

function multiply_monomials(a::StateMonomial,b::StateMonomial,basis)
    states = a.states*b.states
    Dict(StateMonomial(states,w)=>ParamCoeff(c) for (w,c) in multiply_words(a.operator,b.operator,basis))
end

function multiply_poly(a::StatePoly,b::StatePoly,basis)
    result = StatePoly()
    for (ma,ca) in a, (mb,cb) in b
        for (m,cword) in multiply_monomials(ma,mb,basis)
            _add_term!(result,m,ca*cb*cword)
        end
    end
    result
end

"""Apply varsigma linearly, treating existing state symbols as scalars."""
function varsigma_poly(a::StatePoly,symmetry::Symbol)
    result = MomentExpr()
    for (m,c) in a
        if symmetry == PRIMARY_SYMMETRY && charge(m.operator) != 0
            continue
        end
        states = isidentity(m.operator) ? m.states : PureStateMonomial([m.states.factors...; m.operator])
        _add_term!(result,states,c)
    end
    result
end

function add_expr(a::MomentExpr,b::MomentExpr; scale=ParamCoeff(1))
    result = copy(a)
    for (m,c) in b
        _add_term!(result,m,c*scale)
    end
    result
end

function scale_expr(a::MomentExpr,c::ParamCoeff)
    result = MomentExpr()
    for (m,x) in a
        _add_term!(result,m,x*c)
    end
    result
end

function operator_basis(sites::Vector{Int}, maxdegree::Int, nmax::Int,
                        encoding::Symbol, ladder::Dict{LocalAtom,Int})
    maxdegree < 0 && return OperatorWord[]
    atoms = local_basis(nmax)
    result = OperatorWord[]
    factors = NTuple{3,Int}[]
    function visit(position::Int, used_degree::Int)
        if position > length(sites)
            push!(result,OperatorWord(copy(factors)))
            return
        end
        visit(position+1,used_degree)
        site = sites[position]
        for atom in atoms
            next_degree = used_degree + atom_degree(atom,encoding,ladder)
            next_degree <= maxdegree || continue
            push!(factors,(site,atom.r,atom.s))
            visit(position+1,next_degree)
            pop!(factors)
        end
    end
    visit(1,0)
    sort!(unique!(result); by=w->(degree(w,encoding,ladder),w))
    result
end

function state_factor_basis(generators::Vector{OperatorWord},maxdegree::Int,
                            encoding::Symbol,ladder)
    result = PureStateMonomial[]
    current = OperatorWord[]
    function visit(start::Int,used_degree::Int)
        push!(result,PureStateMonomial(copy(current)))
        for i in start:length(generators)
            word = generators[i]
            next_degree = used_degree + degree(word,encoding,ladder)
            next_degree <= maxdegree || continue
            push!(current,word)
            visit(i,next_degree)
            pop!(current)
        end
    end
    visit(1,0)
    sort!(unique!(result); by=m->(degree(m,encoding,ladder),m))
    result
end

"""Complete B_S(R,k) monomial basis in the exact quotient algebra."""
function state_basis(sites::Vector{Int},maxdegree::Int,nmax::Int,encoding::Symbol,
                     ladder,symmetry::Symbol)
    maxdegree < 0 && return StateMonomial[]
    operators = operator_basis(sites,maxdegree,nmax,encoding,ladder)
    generators = [w for w in operators if !isidentity(w) &&
                  (symmetry != PRIMARY_SYMMETRY || charge(w)==0)]
    factors = state_factor_basis(generators,maxdegree,encoding,ladder)
    basis = StateMonomial[]
    for statepart in factors, operator in operators
        degree(statepart,encoding,ladder)+degree(operator,encoding,ladder) <= maxdegree || continue
        push!(basis,StateMonomial(statepart,operator))
    end
    sort!(unique!(basis); by=m->(degree(m,encoding,ladder),charge(m),m))
    basis
end

function pure_product_expr(a::StateMonomial,b::StateMonomial,symmetry::Symbol)
    va = varsigma_poly(monomial_poly(a),symmetry)
    vb = varsigma_poly(monomial_poly(b),symmetry)
    result = MomentExpr()
    for (ma,ca) in va, (mb,cb) in vb
        _add_term!(result,ma*mb,ca*cb)
    end
    result
end
