module MinimalFinitePEPSMETTS

using LinearAlgebra
using Random
using Statistics
using TensorKit

const I2 = Matrix{Float64}(I, 2, 2)
const X = [0.0 1.0; 1.0 0.0]
const Z = [1.0 0.0; 0.0 -1.0]
const Z_PROJECTORS = ([1.0 0.0; 0.0 0.0], [0.0 0.0; 0.0 1.0])
const X_PROJECTORS = (0.5 .* (I2 + X), 0.5 .* (I2 - X))

Base.@kwdef struct Params
    J::Float64 = 1.0
    h::Float64 = 0.5
    beta::Float64 = 1.0
    D::Int = 2
    chi::Int = 16
    tau::Float64 = 0.05
    chain_length::Int = 110
    burn_in::Int = 10
    seed::Int = 20260728
end

mutable struct Site
    gamma::Array{Float64,5}
    left::Vector{Float64}
    top::Vector{Float64}
    right::Vector{Float64}
    bottom::Vector{Float64}
end

struct GammaLambdaPEPS
    sites::Matrix{Site}
    Lx::Int
    Ly::Int
end

struct FinitePEPS
    sites::Matrix{Array{Float64,5}}
    Lx::Int
    Ly::Int
end

Base.getindex(state::Union{GammaLambdaPEPS,FinitePEPS}, x::Int, y::Int) = state.sites[x, y]

function product_peps(configuration::Matrix{Int}, basis::Symbol)
    Lx, Ly = size(configuration)
    sites = Matrix{Site}(undef, Lx, Ly)
    for y in 1:Ly, x in 1:Lx
        outcome = configuration[x, y]
        outcome in (-1, 1) || throw(ArgumentError("collapse outcomes must be ±1"))
        gamma = zeros(1, 1, 2, 1, 1)
        if basis === :Z
            gamma[1, 1, outcome == 1 ? 1 : 2, 1, 1] = 1.0
        elseif basis === :X
            gamma[1, 1, 1, 1, 1] = inv(sqrt(2.0))
            gamma[1, 1, 2, 1, 1] = outcome / sqrt(2.0)
        else
            throw(ArgumentError("basis must be :Z or :X"))
        end
        sites[x, y] = Site(gamma, ones(1), ones(1), ones(1), ones(1))
    end
    return GammaLambdaPEPS(sites, Lx, Ly)
end

function multiply_leg(tensor::Array{Float64,5}, weights::Vector{Float64}, leg::Int)
    shape = ntuple(index -> index == leg ? length(weights) : 1, 5)
    return tensor .* reshape(weights, shape)
end

function remove_leg_weight(tensor::Array{Float64,5}, weights::Vector{Float64}, leg::Int)
    scale = maximum(abs, weights; init=0.0)
    cutoff = 1e-12 * max(scale, 1.0)
    inverse = map(value -> abs(value) > cutoff ? inv(value) : 0.0, weights)
    return multiply_leg(tensor, inverse, leg)
end

function FinitePEPS(state::GammaLambdaPEPS)
    tensors = Matrix{Array{Float64,5}}(undef, state.Lx, state.Ly)
    for y in 1:state.Ly, x in 1:state.Lx
        site = state[x, y]
        tensor = multiply_leg(site.gamma, sqrt.(site.left), 1)
        tensor = multiply_leg(tensor, sqrt.(site.top), 2)
        tensor = multiply_leg(tensor, sqrt.(site.right), 4)
        tensor = multiply_leg(tensor, sqrt.(site.bottom), 5)
        tensors[x, y] = tensor / norm(tensor)
    end
    return FinitePEPS(tensors, state.Lx, state.Ly)
end

site_degree(Lx, Ly, x, y) = (x > 1) + (x < Lx) + (y > 1) + (y < Ly)

function bond_hamiltonian(Lx, Ly, x, y, direction::Symbol, params::Params)
    x2, y2 = direction === :right ? (x + 1, y) : (x, y + 1)
    degree1 = site_degree(Lx, Ly, x, y)
    degree2 = site_degree(Lx, Ly, x2, y2)
    return -params.J * kron(Z, Z) -
           (params.h / degree1) * kron(X, I2) -
           (params.h / degree2) * kron(I2, X)
end

function trotter_gate(Lx, Ly, x, y, direction, delta, params)
    matrix = exp(-delta * bond_hamiltonian(Lx, Ly, x, y, direction, params))
    return permutedims(reshape(matrix, 2, 2, 2, 2), (2, 1, 4, 3))
end

function normalized_singular_values(values)
    normalization = norm(values)
    normalization > 0 || error("two-site update produced a zero state")
    return collect(values ./ normalization)
end

function update_horizontal!(state, x, y, gate, D)
    left, right = state[x, y], state[x + 1, y]
    left_tensor = multiply_leg(left.gamma, left.left, 1)
    left_tensor = multiply_leg(left_tensor, left.top, 2)
    left_tensor = multiply_leg(left_tensor, left.bottom, 5)
    left_tensor = multiply_leg(left_tensor, left.right, 4)
    right_tensor = multiply_leg(right.gamma, right.top, 2)
    right_tensor = multiply_leg(right_tensor, right.right, 4)
    right_tensor = multiply_leg(right_tensor, right.bottom, 5)

    @tensor theta[l, t1, b1, p1, p2, t2, r, b2] :=
        left_tensor[l, t1, q1, bond, b1] *
        right_tensor[bond, t2, q2, r, b2] * gate[p1, p2, q1, q2]
    left_dims, right_dims = size(theta)[1:4], size(theta)[5:8]
    factorization = svd(reshape(theta, prod(left_dims), prod(right_dims)))
    kept = min(D, length(factorization.S))
    singular_values = normalized_singular_values(factorization.S[1:kept])

    new_left = reshape(factorization.U[:, 1:kept], left_dims..., kept)
    new_left = permutedims(new_left, (1, 2, 4, 5, 3))
    new_left = remove_leg_weight(new_left, left.left, 1)
    new_left = remove_leg_weight(new_left, left.top, 2)
    new_left = remove_leg_weight(new_left, left.bottom, 5)

    new_right = reshape(factorization.Vt[1:kept, :], kept, right_dims...)
    new_right = permutedims(new_right, (1, 3, 2, 4, 5))
    new_right = remove_leg_weight(new_right, right.top, 2)
    new_right = remove_leg_weight(new_right, right.right, 4)
    new_right = remove_leg_weight(new_right, right.bottom, 5)

    left.gamma, right.gamma = new_left, new_right
    left.right = right.left = singular_values
    return nothing
end

function update_vertical!(state, x, y, gate, D)
    upper, lower = state[x, y], state[x, y + 1]
    upper_tensor = multiply_leg(upper.gamma, upper.left, 1)
    upper_tensor = multiply_leg(upper_tensor, upper.top, 2)
    upper_tensor = multiply_leg(upper_tensor, upper.right, 4)
    upper_tensor = multiply_leg(upper_tensor, upper.bottom, 5)
    lower_tensor = multiply_leg(lower.gamma, lower.left, 1)
    lower_tensor = multiply_leg(lower_tensor, lower.right, 4)
    lower_tensor = multiply_leg(lower_tensor, lower.bottom, 5)

    @tensor theta[l1, t, r1, p1, p2, l2, r2, b] :=
        upper_tensor[l1, t, q1, r1, bond] *
        lower_tensor[l2, bond, q2, r2, b] * gate[p1, p2, q1, q2]
    upper_dims, lower_dims = size(theta)[1:4], size(theta)[5:8]
    factorization = svd(reshape(theta, prod(upper_dims), prod(lower_dims)))
    kept = min(D, length(factorization.S))
    singular_values = normalized_singular_values(factorization.S[1:kept])

    new_upper = reshape(factorization.U[:, 1:kept], upper_dims..., kept)
    new_upper = permutedims(new_upper, (1, 2, 4, 3, 5))
    new_upper = remove_leg_weight(new_upper, upper.left, 1)
    new_upper = remove_leg_weight(new_upper, upper.top, 2)
    new_upper = remove_leg_weight(new_upper, upper.right, 4)

    new_lower = reshape(factorization.Vt[1:kept, :], kept, lower_dims...)
    new_lower = permutedims(new_lower, (3, 1, 2, 4, 5))
    new_lower = remove_leg_weight(new_lower, lower.left, 1)
    new_lower = remove_leg_weight(new_lower, lower.right, 4)
    new_lower = remove_leg_weight(new_lower, lower.bottom, 5)

    upper.gamma, lower.gamma = new_upper, new_lower
    upper.bottom = lower.top = singular_values
    return nothing
end

function trotter_step!(state, delta, params)
    half_delta = delta / 2
    horizontal = [trotter_gate(state.Lx, state.Ly, x, y, :right, half_delta, params)
                  for x in 1:(state.Lx - 1), y in 1:state.Ly]
    vertical = [trotter_gate(state.Lx, state.Ly, x, y, :down, half_delta, params)
                for x in 1:state.Lx, y in 1:(state.Ly - 1)]
    for y in 1:state.Ly, x in 1:(state.Lx - 1)
        update_horizontal!(state, x, y, horizontal[x, y], params.D)
    end
    for x in 1:state.Lx, y in 1:(state.Ly - 1)
        update_vertical!(state, x, y, vertical[x, y], params.D)
    end
    for x in state.Lx:-1:1, y in (state.Ly - 1):-1:1
        update_vertical!(state, x, y, vertical[x, y], params.D)
    end
    for y in state.Ly:-1:1, x in (state.Lx - 1):-1:1
        update_horizontal!(state, x, y, horizontal[x, y], params.D)
    end
    return nothing
end

function imaginary_time_evolve!(state, params)
    target_time = params.beta / 2
    steps = max(1, ceil(Int, target_time / params.tau))
    delta = target_time / steps
    for _ in 1:steps
        trotter_step!(state, delta, params)
    end
    return state
end

function double_layer(tensor, operator=nothing)
    left, top, physical, right, bottom = size(tensor)
    if operator === nothing
        @tensor raw[l, lb, t, tb, r, rb, b, bb] :=
            tensor[l, t, p, r, b] * conj(tensor[lb, tb, p, rb, bb])
    else
        @tensor raw[l, lb, t, tb, r, rb, b, bb] :=
            tensor[l, t, p, r, b] * conj(tensor[lb, tb, q, rb, bb]) * operator[q, p]
    end
    return reshape(raw, left^2, top^2, right^2, bottom^2)
end

function absorb_row(boundary, row)
    result = Vector{Array}(undef, length(row))
    for x in eachindex(row)
        boundary_tensor, layer = boundary[x], row[x]
        @tensor combined[a, l, b; c, r] := boundary_tensor[a, t, c] * layer[l, t, r, b]
        result[x] = reshape(
            combined,
            size(boundary_tensor, 1) * size(layer, 1),
            size(layer, 4),
            size(boundary_tensor, 3) * size(layer, 3),
        )
    end
    return result
end

function compress_boundary!(boundary, chi)
    for x in 1:(length(boundary) - 1)
        left, physical, right = size(boundary[x])
        factorization = svd(reshape(boundary[x], left * physical, right))
        kept = min(chi, length(factorization.S))
        boundary[x] = reshape(factorization.U[:, 1:kept], left, physical, kept)
        carry = Diagonal(factorization.S[1:kept]) * factorization.Vt[1:kept, :]
        next_left, next_physical, next_right = size(boundary[x + 1])
        boundary[x + 1] = reshape(
            carry * reshape(boundary[x + 1], next_left, next_physical * next_right),
            kept,
            next_physical,
            next_right,
        )
    end
    return boundary
end

function contract_peps(state; chi, insertions=Dict{CartesianIndex{2},Matrix{Float64}}())
    boundary = nothing
    for y in 1:state.Ly
        row = [double_layer(state[x, y], get(insertions, CartesianIndex(x, y), nothing))
               for x in 1:state.Lx]
        if boundary === nothing
            boundary = [ones(eltype(row[x]), 1, 1, 1) for x in 1:state.Lx]
        end
        boundary = absorb_row(boundary, row)
        compress_boundary!(boundary, chi)
    end
    transfer = boundary[1][:, 1, :]
    for x in 2:length(boundary)
        transfer *= boundary[x][:, 1, :]
    end
    return transfer[1, 1]
end

function expectation(state, insertions; chi, norm_value)
    return real(contract_peps(state; chi, insertions) / norm_value)
end

function energy(state, params)
    normalization = contract_peps(state; chi=params.chi)
    zz_sum = 0.0
    x_sum = 0.0
    for y in 1:state.Ly, x in 1:(state.Lx - 1)
        insertions = Dict(CartesianIndex(x, y) => Z, CartesianIndex(x + 1, y) => Z)
        zz_sum += expectation(state, insertions; chi=params.chi, norm_value=normalization)
    end
    for x in 1:state.Lx, y in 1:(state.Ly - 1)
        insertions = Dict(CartesianIndex(x, y) => Z, CartesianIndex(x, y + 1) => Z)
        zz_sum += expectation(state, insertions; chi=params.chi, norm_value=normalization)
    end
    for y in 1:state.Ly, x in 1:state.Lx
        insertions = Dict(CartesianIndex(x, y) => X)
        x_sum += expectation(state, insertions; chi=params.chi, norm_value=normalization)
    end
    return -params.J * zz_sum - params.h * x_sum
end

function collapse(state, basis, chi, rng)
    positive, negative = basis === :Z ? Z_PROJECTORS : X_PROJECTORS
    insertions = Dict{CartesianIndex{2},Matrix{Float64}}()
    configuration = Matrix{Int}(undef, state.Lx, state.Ly)
    for y in 1:state.Ly, x in 1:state.Lx
        site = CartesianIndex(x, y)
        positive_insertions = copy(insertions)
        negative_insertions = copy(insertions)
        positive_insertions[site] = positive
        negative_insertions[site] = negative
        weights = max.(0.0, real.([
            contract_peps(state; chi, insertions=positive_insertions),
            contract_peps(state; chi, insertions=negative_insertions),
        ]))
        probabilities = weights ./ sum(weights)
        if rand(rng) < probabilities[1]
            configuration[x, y] = 1
            insertions[site] = positive
        else
            configuration[x, y] = -1
            insertions[site] = negative
        end
    end
    return configuration
end

function validate(params, Lx, Ly)
    Lx >= 2 && Ly >= 2 || throw(ArgumentError("Lx and Ly must be at least 2"))
    params.D >= 1 || throw(ArgumentError("D must be positive"))
    params.chi >= 1 || throw(ArgumentError("chi must be positive"))
    params.beta > 0 || throw(ArgumentError("beta must be positive"))
    params.tau > 0 || throw(ArgumentError("tau must be positive"))
    0 <= params.burn_in < params.chain_length ||
        throw(ArgumentError("require 0 ≤ burn_in < chain_length"))
end

function run_metts(params::Params=Params(); Lx::Int=2, Ly::Int=2, verbose::Bool=true)
    validate(params, Lx, Ly)
    rng = MersenneTwister(params.seed)
    configuration = ones(Int, Lx, Ly)
    product_basis = :Z
    samples = Float64[]

    for transition in 1:params.chain_length
        gamma_lambda = product_peps(configuration, product_basis)
        imaginary_time_evolve!(gamma_lambda, params)
        state = FinitePEPS(gamma_lambda)
        transition > params.burn_in && push!(samples, energy(state, params))

        collapse_basis = isodd(transition) ? :Z : :X
        configuration = collapse(state, collapse_basis, params.chi, rng)
        product_basis = collapse_basis
        verbose && println("transition $transition/$(params.chain_length), collapse=$collapse_basis")
    end

    mean_energy = mean(samples)
    standard_error = length(samples) > 1 ? std(samples) / sqrt(length(samples)) : NaN
    return (; samples, energy=mean_energy, energy_per_site=mean_energy / (Lx * Ly), standard_error)
end

export Params, run_metts

end

if abspath(PROGRAM_FILE) == @__FILE__
    using .MinimalFinitePEPSMETTS
    params = Params(chain_length=12, burn_in=2)
    result = run_metts(params; Lx=2, Ly=2)
    println("mean energy = ", result.energy)
    println("energy/site = ", result.energy_per_site)
    println("naive standard error = ", result.standard_error)
end
