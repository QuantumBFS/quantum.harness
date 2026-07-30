mutable struct DenseGammaLambdaSite{T<:Number}
    gamma::Array{T,5}
    left::Vector{Float64}
    top::Vector{Float64}
    right::Vector{Float64}
    bottom::Vector{Float64}
end

struct DenseFinitePEPSGammaLambda{T<:Number}
    sites::Matrix{DenseGammaLambdaSite{T}}
    Lx::Int
    Ly::Int
end

struct DenseFinitePEPS{T<:Number}
    sites::Matrix{Array{T,5}}
    Lx::Int
    Ly::Int
end

Base.getindex(state::Union{DenseFinitePEPSGammaLambda,DenseFinitePEPS}, x::Integer, y::Integer) =
    state.sites[x, y]

function product_peps(
    configuration::AbstractMatrix{<:Integer};
    basis::Symbol=:Z,
    dtype::Type=Float64,
)
    Lx, Ly = size(configuration)
    Lx >= 2 || throw(ArgumentError("Lx must be at least 2"))
    Ly >= 2 || throw(ArgumentError("Ly must be at least 2"))
    sites = Matrix{DenseGammaLambdaSite{dtype}}(undef, Lx, Ly)
    for y in 1:Ly, x in 1:Lx
        spin = configuration[x, y]
        spin in (1, -1) || throw(ArgumentError("product-state outcomes must be +1 or -1"))
        gamma = zeros(dtype, 1, 1, 2, 1, 1)
        if basis === :Z
            gamma[1, 1, spin == 1 ? 1 : 2, 1, 1] = one(dtype)
        elseif basis === :X
            gamma[1, 1, 1, 1, 1] = inv(sqrt(dtype(2)))
            gamma[1, 1, 2, 1, 1] = spin * inv(sqrt(dtype(2)))
        else
            throw(ArgumentError("product-state basis must be :Z or :X"))
        end
        sites[x, y] = DenseGammaLambdaSite(
            gamma,
            ones(1),
            ones(1),
            ones(1),
            ones(1),
        )
    end
    return DenseFinitePEPSGammaLambda(sites, Lx, Ly)
end

function multiply_leg(tensor::Array{T,5}, weights::AbstractVector, leg::Integer) where {T}
    size(tensor, leg) == length(weights) || throw(DimensionMismatch("leg and weight dimensions differ"))
    shape = ntuple(index -> index == leg ? length(weights) : 1, 5)
    return tensor .* reshape(weights, shape)
end

function remove_leg_weight(
    tensor::Array{T,5},
    weights::AbstractVector,
    leg::Integer;
    cutoff::Real=1e-12,
) where {T}
    scale = maximum(abs, weights; init=0.0)
    threshold = cutoff * max(scale, 1.0)
    inverse_weights = map(value -> abs(value) > threshold ? inv(value) : 0.0, weights)
    return multiply_leg(tensor, inverse_weights, leg)
end

function DenseFinitePEPS(state::DenseFinitePEPSGammaLambda)
    tensors = Matrix{Array{eltype(state[1, 1].gamma),5}}(undef, state.Lx, state.Ly)
    for y in 1:state.Ly, x in 1:state.Lx
        site = state[x, y]
        tensor = copy(site.gamma)
        tensor = multiply_leg(tensor, sqrt.(site.left), 1)
        tensor = multiply_leg(tensor, sqrt.(site.top), 2)
        tensor = multiply_leg(tensor, sqrt.(site.right), 4)
        tensor = multiply_leg(tensor, sqrt.(site.bottom), 5)
        tensor_norm = norm(tensor)
        tensor_norm > 0 || error("zero PEPS tensor at ($x,$y)")
        tensors[x, y] = tensor / tensor_norm
    end
    return DenseFinitePEPS(tensors, state.Lx, state.Ly)
end

function validate_finite_peps(state::Union{DenseFinitePEPSGammaLambda,DenseFinitePEPS})
    for y in 1:state.Ly, x in 1:state.Lx
        tensor = state isa DenseFinitePEPS ? state[x, y] : state[x, y].gamma
        ndims(tensor) == 5 || error("site tensor at ($x,$y) must have five legs")
        size(tensor, 3) == 2 || error("physical dimension at ($x,$y) must be two")
        x == 1 && size(tensor, 1) != 1 && error("left boundary at ($x,$y) is not trivial")
        y == 1 && size(tensor, 2) != 1 && error("top boundary at ($x,$y) is not trivial")
        x == state.Lx && size(tensor, 4) != 1 && error("right boundary at ($x,$y) is not trivial")
        y == state.Ly && size(tensor, 5) != 1 && error("bottom boundary at ($x,$y) is not trivial")
        if x < state.Lx
            neighbor = state isa DenseFinitePEPS ? state[x + 1, y] : state[x + 1, y].gamma
            size(tensor, 4) == size(neighbor, 1) || error("horizontal bond mismatch at ($x,$y)")
        end
        if y < state.Ly
            neighbor = state isa DenseFinitePEPS ? state[x, y + 1] : state[x, y + 1].gamma
            size(tensor, 5) == size(neighbor, 2) || error("vertical bond mismatch at ($x,$y)")
        end
    end
    return true
end

function exact_wavefunction(state::DenseFinitePEPS)
    (state.Lx, state.Ly) == (2, 2) || throw(ArgumentError("exact_wavefunction currently requires a 2x2 state"))
    upper_left = dropdims(state[1, 1]; dims=(1, 2))
    upper_right = dropdims(state[2, 1]; dims=(2, 4))
    lower_left = dropdims(state[1, 2]; dims=(1, 5))
    lower_right = dropdims(state[2, 2]; dims=(4, 5))
    @tensor wavefunction[p1, p2, p3, p4] :=
        upper_left[p1, horizontal_top, vertical_left] *
        upper_right[horizontal_top, p2, vertical_right] *
        lower_left[vertical_left, p3, horizontal_bottom] *
        lower_right[horizontal_bottom, vertical_right, p4]
    return wavefunction
end
