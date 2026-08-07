module KullCGRDM

using LinearAlgebra
using SHA
using Random
using Serialization
using JuMP
const MOI = JuMP.MOI

const Sx = ComplexF64[0 1; 1 0] / 2
const Sy = ComplexF64[0 -im; im 0] / 2
const Sz = ComplexF64[1 0; 0 -1] / 2
const HEISENBERG_H = kron(Sx, Sx) + kron(Sy, Sy) + kron(Sz, Sz)
const EXACT_ENERGY = 1 / 4 - log(2)

"Two-site spin-1/2 XXZ interaction in the convention SˣSˣ + SʸSʸ + ΔSᶻSᶻ."
xxz_hamiltonian(delta::Real) = kron(Sx, Sx) + kron(Sy, Sy) + delta * kron(Sz, Sz)

"Nearest-neighbour XXZ energy per two-spin cell, acting on two adjacent cells."
function blocked_xxz_hamiltonian(delta::Real)
    h = xxz_hamiltonian(delta)
    identity2 = Matrix{ComplexF64}(I, 2, 2)
    0.5 * kron(h, identity2, identity2) +
        kron(identity2, h, identity2) +
        0.5 * kron(identity2, identity2, h)
end

"U(1) basis charges for one physical site and one virtual bond."
struct U1Symmetry
    physical_charges::Vector{Int}
    virtual_charges::Vector{Int}
end

"Explicit on-site and virtual-bond representations of spin-flip Z₂."
struct SpinFlipSymmetry
    physical_flip::Matrix{ComplexF64}
    virtual_flip::Matrix{ComplexF64}
    physical_permutation::Vector{Int}
    virtual_permutation::Vector{Int}
    SpinFlipSymmetry(physical_flip::Matrix{ComplexF64}, virtual_flip::Matrix{ComplexF64},
        physical_permutation::Vector{Int}, virtual_permutation::Vector{Int},
        ::Val{:validated}) = new(physical_flip, virtual_flip,
            physical_permutation, virtual_permutation)
end

function permutation_matrix(permutation::AbstractVector{<:Integer})
    n = length(permutation)
    sort(Int.(permutation)) == collect(1:n) ||
        throw(ArgumentError("flip permutation must contain each basis index exactly once"))
    F = zeros(ComplexF64, n, n)
    for source in 1:n
        F[permutation[source], source] = 1
    end
    F
end

function _matrix_permutation(F::AbstractMatrix; atol::Real=1e-12)
    size(F, 1) == size(F, 2) || throw(DimensionMismatch("flip matrix must be square"))
    permutation = Int[]
    for column in axes(F, 2)
        rows = findall(value -> abs(value) > atol, F[:,column])
        length(rows) == 1 && abs(F[only(rows),column] - 1) <= atol ||
            throw(ArgumentError("flip matrix is not a permutation matrix"))
        push!(permutation, only(rows))
    end
    sort(permutation) == collect(1:size(F, 1)) ||
        throw(ArgumentError("flip matrix is not a permutation matrix"))
    permutation
end

function SpinFlipSymmetry(physical_permutation::AbstractVector{<:Integer},
        virtual_permutation::AbstractVector{<:Integer}; atol::Real=1e-12)
    physical = Int.(physical_permutation)
    virtual = Int.(virtual_permutation)
    SpinFlipSymmetry(permutation_matrix(physical), permutation_matrix(virtual),
        physical, virtual; atol)
end

function SpinFlipSymmetry(physical_flip::AbstractMatrix, virtual_flip::AbstractMatrix;
        atol::Real=1e-12)
    SpinFlipSymmetry(physical_flip, virtual_flip,
        _matrix_permutation(physical_flip; atol), _matrix_permutation(virtual_flip; atol); atol)
end

function SpinFlipSymmetry(physical_flip::AbstractMatrix, virtual_flip::AbstractMatrix,
        physical_permutation::AbstractVector{<:Integer},
        virtual_permutation::AbstractVector{<:Integer}; atol::Real=1e-12)
    atol >= 0 || throw(ArgumentError("atol must be nonnegative"))
    physical = Int.(physical_permutation)
    virtual = Int.(virtual_permutation)
    Fp = Matrix{ComplexF64}(physical_flip)
    Fv = Matrix{ComplexF64}(virtual_flip)
    size(Fp) == (length(physical), length(physical)) ||
        throw(DimensionMismatch("physical flip matrix and permutation dimensions differ"))
    size(Fv) == (length(virtual), length(virtual)) ||
        throw(DimensionMismatch("virtual flip matrix and permutation dimensions differ"))
    norm(Fp - permutation_matrix(physical), Inf) <= atol ||
        throw(ArgumentError("physical flip matrix does not realize its declared permutation"))
    norm(Fv - permutation_matrix(virtual), Inf) <= atol ||
        throw(ArgumentError("virtual flip matrix does not realize its declared permutation"))
    symmetry = SpinFlipSymmetry(Fp, Fv, physical, virtual, Val(:validated))
    validate_spin_flip(symmetry; atol)
    symmetry
end

function validate_spin_flip(symmetry::SpinFlipSymmetry; atol::Real=1e-12)
    atol >= 0 || throw(ArgumentError("atol must be nonnegative"))
    dp, dv = size(symmetry.physical_flip, 1), size(symmetry.virtual_flip, 1)
    checks = Dict{String,Float64}(
        "physical_involution" => norm(symmetry.physical_flip^2 - Matrix{ComplexF64}(I, dp, dp), Inf),
        "physical_unitarity" => norm(symmetry.physical_flip' * symmetry.physical_flip - Matrix{ComplexF64}(I, dp, dp), Inf),
        "virtual_involution" => norm(symmetry.virtual_flip^2 - Matrix{ComplexF64}(I, dv, dv), Inf),
        "virtual_unitarity" => norm(symmetry.virtual_flip' * symmetry.virtual_flip - Matrix{ComplexF64}(I, dv, dv), Inf))
    maximum(values(checks)) <= atol ||
        throw(ArgumentError("spin-flip matrices must be unitary involutions; residuals=$checks"))
    all(symmetry.physical_permutation[symmetry.physical_permutation[i]] == i
        for i in eachindex(symmetry.physical_permutation)) ||
        throw(ArgumentError("physical flip permutation is not an involution"))
    all(symmetry.virtual_permutation[symmetry.virtual_permutation[i]] == i
        for i in eachindex(symmetry.virtual_permutation)) ||
        throw(ArgumentError("virtual flip permutation is not an involution"))
    checks
end

function validate_charge_reversal(symmetry::SpinFlipSymmetry, u1::U1Symmetry)
    length(u1.physical_charges) == length(symmetry.physical_permutation) ||
        throw(DimensionMismatch("physical charge and flip dimensions differ"))
    length(u1.virtual_charges) == length(symmetry.virtual_permutation) ||
        throw(DimensionMismatch("virtual charge and flip dimensions differ"))
    all(u1.physical_charges[symmetry.physical_permutation[i]] == -u1.physical_charges[i]
        for i in eachindex(u1.physical_charges)) ||
        throw(ArgumentError("physical spin flip does not map charge q to -q"))
    all(u1.virtual_charges[symmetry.virtual_permutation[i]] == -u1.virtual_charges[i]
        for i in eachindex(u1.virtual_charges)) ||
        throw(ArgumentError("virtual spin flip does not map charge q to -q"))
    true
end

const AXIS_CONTRACT = (
    A = (:virtual_left, :physical, :virtual_right),
    omega = (:physical_left, :virtual_left, :virtual_right, :physical_right),
)

struct FrozenUniformMPS{T<:Number}
    tensors::Vector{Array{T,3}}
    physical_dimension::Int
    bond_dimensions::Vector{Tuple{Int,Int}}
    unit_cell_length::Int
    canonical_gauge::Symbol
    left_fixed_points::Vector{Matrix{T}}
    right_fixed_points::Vector{Matrix{T}}
    canonical_residual::Float64
    normalization_residual::Float64
    source_energy::Float64
    vumps_settings::Dict{String,Any}
    fingerprint::String
end

function frozen_fingerprint(tensors, gauge, coefficient_type=eltype(first(tensors)))
    io = IOBuffer()
    serialize(io, (AXIS_CONTRACT, tensors, gauge, string(coefficient_type), length(tensors)))
    bytes2hex(sha256(take!(io)))
end

function FrozenUniformMPS(tensors::Vector{Array{T,3}}; canonical_gauge=:left,
        left_fixed_points=Matrix{T}[], right_fixed_points=Matrix{T}[],
        canonical_residual=Inf, normalization_residual=Inf, source_energy=NaN,
        vumps_settings=Dict{String,Any}()) where {T<:Number}
    isempty(tensors) && throw(ArgumentError("at least one unit-cell tensor is required"))
    d = size(first(tensors), 2)
    all(size(A,2) == d for A in tensors) || throw(DimensionMismatch("physical dimensions differ"))
    bonds = [(size(A,1), size(A,3)) for A in tensors]
    all(bonds[i][2] == bonds[mod1(i+1,length(bonds))][1] for i in eachindex(bonds)) ||
        throw(DimensionMismatch("cyclic virtual bonds do not match"))
    fingerprint = frozen_fingerprint(tensors, canonical_gauge, T)
    FrozenUniformMPS{T}(tensors, d, bonds, length(tensors), canonical_gauge,
        left_fixed_points, right_fixed_points, canonical_residual,
        normalization_residual, source_energy, vumps_settings, fingerprint)
end

"Create and freeze a normalized one-site product tensor."
function product_frozen_mps(state::AbstractVector{T}) where {T<:Number}
    norm(state) > 0 || throw(ArgumentError("product state must be nonzero"))
    ψ = ComplexF64.(state ./ norm(state))
    A = reshape(ψ, 1, length(ψ), 1)
    onefp = [ones(ComplexF64, 1, 1)]
    FrozenUniformMPS([A]; left_fixed_points=onefp,
        right_fixed_points=copy(onefp), canonical_residual=0.0,
        normalization_residual=abs(sum(abs2, A) - 1),
        vumps_settings=Dict("source" => "manual_product"))
end

"Create a reproducible random complex left-canonical one-site tensor."
function random_canonical_frozen_mps(d::Int, D::Int; seed::Int=1234)
    d > 0 && D > 0 || throw(ArgumentError("d and D must be positive"))
    rng = MersenneTwister(seed)
    Q = Matrix(qr(randn(rng, ComplexF64, d * D, D)).Q[:, 1:D])
    A = permutedims(reshape(Q, d, D, D), (2, 1, 3))
    gauge_residual = norm(sum((@view A[:,s,:])' * (@view A[:,s,:]) for s in 1:d) - I)
    FrozenUniformMPS([A]; canonical_gauge=:left,
        left_fixed_points=[Matrix{ComplexF64}(I, D, D)],
        canonical_residual=gauge_residual,
        normalization_residual=gauge_residual,
        vumps_settings=Dict("source" => "manual_random", "seed" => seed))
end

"Flatten named ket axes in column-major order; inverse is `unflatten_ket`."
flatten_ket(x::AbstractArray, axes::NTuple{N,Symbol}) where {N} = begin
    ndims(x) == N || throw(DimensionMismatch("$(axes) requires $N axes"))
    vec(x)
end

unflatten_ket(x::AbstractVector, dims::NTuple{N,Int}, axes::NTuple{N,Symbol}) where {N} = begin
    length(x) == prod(dims) || throw(DimensionMismatch("$(axes) dimensions do not match vector"))
    reshape(x, dims)
end

function matrix_to_named_operator(X::AbstractMatrix, dims::NTuple{N,Int}, axes::NTuple{N,Symbol}) where {N}
    size(X) == (prod(dims), prod(dims)) || throw(DimensionMismatch("operator dimensions do not match $(axes)"))
    reshape(X, dims..., dims...)
end

function named_operator_to_matrix(X::AbstractArray, dims::NTuple{N,Int}, axes::NTuple{N,Symbol}) where {N}
    size(X) == (dims..., dims...) || throw(DimensionMismatch("operator axes do not match $(axes)"))
    reshape(X, prod(dims), prod(dims))
end

"Return the unit-cell tensor at a one-based, periodically wrapped site."
site_tensor(frozen::FrozenUniformMPS, site::Int) = frozen.tensors[mod1(site, frozen.unit_cell_length)]

"Contract `m ≥ 1` MPS tensors into `Wₘ : physical^m → virtual_left⊗virtual_right`."
function direct_Wm(frozen::FrozenUniformMPS, m::Int; start_site::Int=1)
    m >= 1 || throw(ArgumentError("m must be positive"))
    d = frozen.physical_dimension
    tensors = [site_tensor(frozen, start_site + j - 1) for j in 1:m]
    Dl = size(first(tensors), 1)
    Dr = size(last(tensors), 3)
    T = promote_type(map(eltype, tensors)...)
    W = zeros(T, Dl * Dr, d^m)
    physical_index = LinearIndices(ntuple(_ -> d, m))
    output_index = LinearIndices((Dl, Dr))
    for physical in CartesianIndices(ntuple(_ -> d, m))
        block = Matrix(@view tensors[1][:, physical[1], :])
        for j in 2:m
            block = block * (@view tensors[j][:, physical[j], :])
        end
        for right in 1:Dr, left in 1:Dl
            W[output_index[left, right], physical_index[physical]] = block[left, right]
        end
    end
    W
end

"Production two-site coarse grainer, with rows `(virtual_left,virtual_right)` and columns `(physical_1,physical_2)`."
W2(frozen::FrozenUniformMPS; start_site::Int=1) = direct_Wm(frozen, 2; start_site)

"Matrix `L : physical_left⊗virtual_left_old → virtual_left_new` that absorbs one tensor from the left."
function left_absorption(frozen::FrozenUniformMPS; site::Int=1)
    A = site_tensor(frozen, site)
    Dl, d, Dr = size(A)
    L = zeros(eltype(A), Dl, d * Dr)
    input_index = LinearIndices((d, Dr))
    for old_left in 1:Dr, physical in 1:d, new_left in 1:Dl
        L[new_left, input_index[physical, old_left]] = A[new_left, physical, old_left]
    end
    L
end

"Matrix `R : virtual_right_old⊗physical_right → virtual_right_new` that absorbs one tensor from the right."
function right_absorption(frozen::FrozenUniformMPS; site::Int=1)
    A = site_tensor(frozen, site)
    Dl, d, Dr = size(A)
    R = zeros(eltype(A), Dr, Dl * d)
    input_index = LinearIndices((Dl, d))
    for physical in 1:d, old_right in 1:Dl, new_right in 1:Dr
        R[new_right, input_index[old_right, physical]] = A[old_right, physical, new_right]
    end
    R
end

"Build a full operator by applying `K` to selected input axes and preserving the rest in their original order."
function boundary_extension(K::AbstractMatrix, input_dims::Tuple, axes::Tuple, output_dims::Tuple)
    length(unique(axes)) == length(axes) || throw(ArgumentError("selected axes must be unique"))
    all(1 <= axis <= length(input_dims) for axis in axes) || throw(BoundsError(input_dims, axes))
    prod(input_dims[collect(axes)]) == size(K, 2) || throw(DimensionMismatch("K input does not match selected axes"))
    prod(output_dims) == size(K, 1) || throw(DimensionMismatch("K output dimensions do not match its rows"))
    first_axis = minimum(axes)
    axes == Tuple(first_axis:first_axis + length(axes) - 1) ||
        throw(ArgumentError("selected axes must be contiguous and ordered"))
    full_output_dims = (input_dims[1:first_axis-1]..., output_dims..., input_dims[first_axis+length(axes):end]...)
    T = eltype(K)
    full = zeros(T, prod(full_output_dims), prod(input_dims))
    input_linear = LinearIndices(input_dims)
    local_input_linear = LinearIndices(Tuple(input_dims[collect(axes)]))
    output_linear = LinearIndices(full_output_dims)
    local_output_cartesian = CartesianIndices(output_dims)
    for input_cartesian in CartesianIndices(input_dims)
        local_input = local_input_linear[Tuple(input_cartesian)[collect(axes)]...]
        prefix = Tuple(input_cartesian)[1:first_axis-1]
        suffix = Tuple(input_cartesian)[first_axis+length(axes):end]
        for local_output in local_output_cartesian
            output_cartesian = (prefix..., Tuple(local_output)..., suffix...)
            full[output_linear[output_cartesian...], input_linear[input_cartesian]] =
                K[LinearIndices(output_dims)[local_output], local_input]
        end
    end
    full, full_output_dims
end

"Apply the congruence map `X ↦ K X K†`."
function congruence(K::AbstractMatrix, X::AbstractMatrix)
    size(X) == (size(K, 2), size(K, 2)) || throw(DimensionMismatch("congruence input has the wrong size"))
    K * X * K'
end

"Hilbert–Schmidt adjoint of `X ↦ K X K†`, namely `Y ↦ K† Y K`."
function congruence_adjoint(K::AbstractMatrix, Y::AbstractMatrix)
    size(Y) == (size(K, 1), size(K, 1)) || throw(DimensionMismatch("adjoint input has the wrong size"))
    K' * Y * K
end

forward_map(K::AbstractMatrix, X::AbstractMatrix) = congruence(K, X)
forward_map_adjoint(K::AbstractMatrix, Y::AbstractMatrix) = congruence_adjoint(K, Y)

"Trace one named tensor-product axis from a matrix, preserving all other axes in order."
function partial_trace(X::AbstractMatrix, dims::Tuple, axis::Int)
    1 <= axis <= length(dims) || throw(BoundsError(dims, axis))
    size(X) == (prod(dims), prod(dims)) || throw(DimensionMismatch("operator does not match subsystem dimensions"))
    kept = Tuple(i for i in eachindex(dims) if i != axis)
    output_dims = Tuple(dims[i] for i in kept)
    Y = zeros(eltype(X), prod(output_dims), prod(output_dims))
    full_linear = LinearIndices(dims)
    output_linear = LinearIndices(output_dims)
    for ket_kept in CartesianIndices(output_dims), bra_kept in CartesianIndices(output_dims)
        value = zero(eltype(X))
        for traced in 1:dims[axis]
            ket = ntuple(i -> i == axis ? traced : ket_kept[findfirst(==(i), kept)], length(dims))
            bra = ntuple(i -> i == axis ? traced : bra_kept[findfirst(==(i), kept)], length(dims))
            value += X[full_linear[ket...], full_linear[bra...]]
        end
        Y[output_linear[ket_kept], output_linear[bra_kept]] = value
    end
    Y
end

"Hilbert–Schmidt adjoint of tracing `axis`: insert an identity on that axis."
function partial_trace_adjoint(Y::AbstractMatrix, dims::Tuple, axis::Int)
    1 <= axis <= length(dims) || throw(BoundsError(dims, axis))
    kept = Tuple(i for i in eachindex(dims) if i != axis)
    output_dims = Tuple(dims[i] for i in kept)
    size(Y) == (prod(output_dims), prod(output_dims)) || throw(DimensionMismatch("adjoint input has the wrong size"))
    X = zeros(eltype(Y), prod(dims), prod(dims))
    full_linear = LinearIndices(dims)
    output_linear = LinearIndices(output_dims)
    for ket_kept in CartesianIndices(output_dims), bra_kept in CartesianIndices(output_dims), traced in 1:dims[axis]
        ket = ntuple(i -> i == axis ? traced : ket_kept[findfirst(==(i), kept)], length(dims))
        bra = ntuple(i -> i == axis ? traced : bra_kept[findfirst(==(i), kept)], length(dims))
        X[full_linear[ket...], full_linear[bra...]] = Y[output_linear[ket_kept], output_linear[bra_kept]]
    end
    X
end

"Compile the two bottom maps from `ρ^(k0+1)` to the traces of `ω_k0`; `V0 = W_k0`."
function bottom_bridge_operators(frozen::FrozenUniformMPS; k0::Int=2, start_site::Int=1)
    k0 >= 1 || throw(ArgumentError("k0 must be positive"))
    d = frozen.physical_dimension
    rho_dims = ntuple(_ -> d, k0 + 1)
    V0 = direct_Wm(frozen, k0; start_site=start_site + 1)
    output_dims = (size(site_tensor(frozen, start_site + 1), 1),
        size(site_tensor(frozen, start_site + k0), 3))
    to_trace_physical_left, left_dims = boundary_extension(V0, rho_dims,
        Tuple(1:k0), output_dims)
    to_trace_physical_right, right_dims = boundary_extension(V0, rho_dims,
        Tuple(2:k0+1), output_dims)
    (; V0, to_trace_physical_left, to_trace_physical_right, left_dims, right_dims)
end

"Compile the fixed-size flow maps from `ω_m` (physical support `m+2`) to traces of `ω_(m+1)`."
function flow_operators(frozen::FrozenUniformMPS, m::Int; start_site::Int=1)
    m >= 1 || throw(ArgumentError("omega key m must be positive"))
    d = frozen.physical_dimension
    interior_first = start_site + 1
    interior_last = start_site + m
    Dl = size(site_tensor(frozen, interior_first), 1)
    Dr = size(site_tensor(frozen, interior_last), 3)
    input_dims = (d, Dl, Dr, d)
    L = left_absorption(frozen; site=interior_first)
    R = right_absorption(frozen; site=interior_last + 1)
    to_trace_physical_left, left_dims = boundary_extension(L, input_dims, (1, 2), (size(L, 1),))
    to_trace_physical_right, right_dims = boundary_extension(R, input_dims, (3, 4), (size(R, 1),))
    (; to_trace_physical_left, to_trace_physical_right, left_dims, right_dims)
end

"Recursively construct `Wₘ` using only the fixed right-absorption maps."
function recursive_Wm(frozen::FrozenUniformMPS, m::Int; start_site::Int=1)
    m >= 1 || throw(ArgumentError("m must be positive"))
    d = frozen.physical_dimension
    W = direct_Wm(frozen, 1; start_site)
    output_dims = (size(site_tensor(frozen, start_site), 1), size(site_tensor(frozen, start_site), 3))
    for length_so_far in 1:m-1
        old_output_dims = output_dims
        R = right_absorption(frozen; site=start_site + length_so_far)
        extended, output_dims = boundary_extension(R, (old_output_dims..., d), (2, 3), (size(R, 1),))
        lifted_W, _ = boundary_extension(W, ntuple(_ -> d, length_so_far + 1),
            Tuple(1:length_so_far), old_output_dims)
        W = extended * lifted_W
    end
    W
end

"Compress an explicit physical m-site RDM into `ωᵐ = (I⊗Wₘ₋₂⊗I)ρᵐ(I⊗Wₘ₋₂†⊗I)`."
function compress_physical_rdm(frozen::FrozenUniformMPS, rho::AbstractMatrix, m::Int; start_site::Int=1)
    m >= 3 || throw(ArgumentError("compression requires at least three physical sites"))
    d = frozen.physical_dimension
    size(rho) == (d^m, d^m) || throw(DimensionMismatch("ρᵐ has the wrong size"))
    W = direct_Wm(frozen, m - 2; start_site=start_site + 1)
    first_interior = site_tensor(frozen, start_site + 1)
    last_interior = site_tensor(frozen, start_site + m - 2)
    K, dims = boundary_extension(W, ntuple(_ -> d, m), Tuple(2:m-1),
        (size(first_interior, 1), size(last_interior, 3)))
    congruence(K, rho), dims
end

struct KullResourceInventory
    psd_block_dimensions::Vector{Int}
    psd_block_count::Int
    real_scalar_variables::Int
    linear_equalities::Int
    coefficient_storage_bytes::Int
    peak_memory_bytes::Int
    estimated_wall_seconds::Float64
    local_feasible::Bool
end

Base.:(==)(left::KullResourceInventory, right::KullResourceInventory) =
    all(getfield(left, field) == getfield(right, field) for field in fieldnames(KullResourceInventory))

struct KullPrimalProblem
    model::JuMP.Model
    rho3
    omegas::Dict{Any,Any}
    constraints::Dict{Symbol,Vector{Any}}
    inventory::KullResourceInventory
    metadata::Dict{String,Any}
end

struct KullSolverResult
    lower_bound_candidate::Float64
    termination_status::MOI.TerminationStatusCode
    primal_status::MOI.ResultStatusCode
    dual_status::MOI.ResultStatusCode
    relative_gap::Float64
    constraint_residual::Float64
    minimum_psd_eigenvalue::Float64
    runtime_seconds::Float64
    map_fingerprint::Union{Nothing,String}
    vumps_upper_endpoint::Float64
    clean::Bool
    classification::String
end

struct KullDualCertificate
    normalization_multiplier::Float64
    equality_multipliers::Dict{String,Matrix{ComplexF64}}
    psd_duals::Dict{String,Matrix{ComplexF64}}
    projected_psd_duals::Dict{String,Matrix{ComplexF64}}
    stationarity_residuals::Dict{String,Matrix{ComplexF64}}
    minimum_dual_eigenvalue::Float64
    maximum_stationarity_residual::Float64
    residual_correction::Float64
    corrected_lower_bound::Float64
    trace_nonincreasing::Bool
    trace_envelope::Float64
    coefficient_policy::Dict{String,Any}
    map_fingerprint::Union{Nothing,String}
    classification::String
end

function _jump_partial_trace(X, dims::Tuple, axis::Int)
    kept = Tuple(i for i in eachindex(dims) if i != axis)
    output_dims = Tuple(dims[i] for i in kept)
    full_linear = LinearIndices(dims)
    output_linear = LinearIndices(output_dims)
    Y = Matrix{Any}(undef, prod(output_dims), prod(output_dims))
    for ket_kept in CartesianIndices(output_dims), bra_kept in CartesianIndices(output_dims)
        ket_tuple, bra_tuple = Tuple(ket_kept), Tuple(bra_kept)
        Y[output_linear[ket_kept], output_linear[bra_kept]] = sum(begin
            ket = ntuple(i -> i == axis ? traced : ket_tuple[findfirst(==(i), kept)], length(dims))
            bra = ntuple(i -> i == axis ? traced : bra_tuple[findfirst(==(i), kept)], length(dims))
            X[full_linear[ket...], full_linear[bra...]]
        end for traced in 1:dims[axis])
    end
    Y
end

"Trace one axis while materializing only charge-preserving output entries."
function _jump_charge_partial_trace(X, dims::Tuple, axis::Int,
        output_charges::AbstractVector{<:Integer})
    kept = Tuple(i for i in eachindex(dims) if i != axis)
    output_dims = Tuple(dims[i] for i in kept)
    length(output_charges) == prod(output_dims) ||
        throw(DimensionMismatch("output charge count does not match partial trace"))
    full_linear = LinearIndices(dims)
    output_linear = LinearIndices(output_dims)
    Y = Matrix{Any}(zeros(ComplexF64, prod(output_dims), prod(output_dims)))
    for ket_kept in CartesianIndices(output_dims), bra_kept in CartesianIndices(output_dims)
        ket_linear = output_linear[ket_kept]
        bra_linear = output_linear[bra_kept]
        output_charges[ket_linear] == output_charges[bra_linear] || continue
        ket_tuple, bra_tuple = Tuple(ket_kept), Tuple(bra_kept)
        Y[ket_linear,bra_linear] = sum(begin
            ket = ntuple(i -> i == axis ? traced : ket_tuple[findfirst(==(i), kept)], length(dims))
            bra = ntuple(i -> i == axis ? traced : bra_tuple[findfirst(==(i), kept)], length(dims))
            X[full_linear[ket...], full_linear[bra...]]
        end for traced in 1:dims[axis])
    end
    Y
end

function _jump_congruence(K::AbstractMatrix, X)
    rows, cols = size(K)
    size(X) == (cols, cols) || throw(DimensionMismatch("congruence input has the wrong size"))
    [sum(K[i,a] * conj(K[j,b]) * X[a,b] for a in 1:cols, b in 1:cols)
        for i in 1:rows, j in 1:rows]
end

"Apply a numerical congruence using only the nonzero support of an equivariant map."
function _jump_sparse_congruence(K::AbstractMatrix, X, output_charges::AbstractVector{<:Integer})
    rows, cols = size(K)
    size(X) == (cols, cols) || throw(DimensionMismatch("congruence input has the wrong size"))
    length(output_charges) == rows || throw(DimensionMismatch("output charge count does not match map"))
    support = [[(column, K[row,column]) for column in 1:cols if !iszero(K[row,column])]
        for row in 1:rows]
    Y = Matrix{Any}(zeros(ComplexF64, rows, rows))
    for j in 1:rows, i in 1:rows
        output_charges[i] == output_charges[j] || continue
        (isempty(support[i]) || isempty(support[j])) && continue
        Y[i,j] = sum(value_i * conj(value_j) * X[column_i,column_j]
            for (column_i,value_i) in support[i], (column_j,value_j) in support[j])
    end
    Y
end

"Convert scalar real/imag equality duals back to one Hermitian multiplier."
function _hermitian_multiplier(refs::AbstractVector, dimension::Int, offset::Int=0)
    expected = dimension^2
    offset + expected <= length(refs) || throw(BoundsError(refs, offset + expected))
    Y = zeros(ComplexF64, dimension, dimension)
    cursor = offset
    for j in 1:dimension, i in 1:j
        yr = Float64(dual(refs[cursor += 1]))
        if i == j
            Y[i,j] = yr
        else
            yi = Float64(dual(refs[cursor += 1]))
            Y[i,j] = (yr + im * yi) / 2
            Y[j,i] = conj(Y[i,j])
        end
    end
    Y, cursor
end

"Reconstruct a Hermitian equality multiplier from charge-sector constraints."
function _charge_hermitian_multiplier(refs::AbstractVector,
        charges::AbstractVector{<:Integer}, offset::Int=0; real_sdp::Bool=false)
    Y = zeros(ComplexF64, length(charges), length(charges))
    cursor = offset
    for (_, indices) in charge_sectors(charges)
        for local_j in eachindex(indices), local_i in 1:local_j
            i, j = indices[local_i], indices[local_j]
            yr = Float64(dual(refs[cursor += 1]))
            if i == j
                Y[i,j] = yr
            elseif real_sdp
                Y[i,j] = yr / 2
                Y[j,i] = yr / 2
            else
                yi = Float64(dual(refs[cursor += 1]))
                Y[i,j] = (yr + im * yi) / 2
                Y[j,i] = conj(Y[i,j])
            end
        end
    end
    Y, cursor
end

function _add_hermitian_equalities!(model::JuMP.Model, lhs, rhs)
    size(lhs) == size(rhs) || throw(DimensionMismatch("Hermitian equality dimensions differ"))
    size(lhs, 1) == size(lhs, 2) || throw(DimensionMismatch("Hermitian equality must be square"))
    refs = Any[]
    for j in axes(lhs, 2), i in 1:j
        difference = lhs[i,j] - rhs[i,j]
        push!(refs, @constraint(model, real(difference) == 0))
        i == j || push!(refs, @constraint(model, imag(difference) == 0))
    end
    refs
end

"Add only the charge-preserving Hermitian equalities and retain their sector layout."
function _add_charge_equalities!(model::JuMP.Model, lhs, rhs,
        charges::AbstractVector{<:Integer}; real_sdp::Bool=false)
    size(lhs) == size(rhs) || throw(DimensionMismatch("Hermitian equality dimensions differ"))
    size(lhs) == (length(charges), length(charges)) ||
        throw(DimensionMismatch("charge count does not match Hermitian equality"))
    refs = Any[]
    for (_, indices) in charge_sectors(charges)
        for local_j in eachindex(indices), local_i in 1:local_j
            i, j = indices[local_i], indices[local_j]
            difference = lhs[i,j] - rhs[i,j]
            push!(refs, @constraint(model, real(difference) == 0))
            !real_sdp && i != j && push!(refs, @constraint(model, imag(difference) == 0))
        end
    end
    refs
end

"Total additive charge of every tensor-product basis state, in column-major order."
function product_charges(charges::Vararg{AbstractVector})
    dims = Tuple(length(q) for q in charges)
    vec([sum(charges[axis][state[axis]] for axis in eachindex(charges))
        for state in CartesianIndices(dims)])
end

"Group basis indices by U(1) charge."
function charge_sectors(charges::AbstractVector{<:Integer})
    sectors = Dict{Int,Vector{Int}}()
    for (index, charge) in pairs(charges)
        push!(get!(sectors, Int(charge), Int[]), index)
    end
    sort(collect(sectors); by=first)
end

"Largest matrix element violating output_charge == input_charge."
function equivariance_residual(K::AbstractMatrix, output_charges, input_charges)
    size(K) == (length(output_charges), length(input_charges)) ||
        throw(DimensionMismatch("map and charge dimensions differ"))
    maximum((abs(K[i,j]) for i in axes(K,1), j in axes(K,2)
        if output_charges[i] != input_charges[j]); init=0.0)
end

function mps_charge_residual(frozen::FrozenUniformMPS, symmetry::U1Symmetry)
    frozen.physical_dimension == length(symmetry.physical_charges) ||
        throw(DimensionMismatch("physical charge count does not match MPS"))
    D = _uniform_bond_dimension(frozen)
    D == length(symmetry.virtual_charges) ||
        throw(DimensionMismatch("virtual charge count does not match MPS"))
    maximum((abs(A[left, physical, right])
        for A in frozen.tensors, left in 1:D, physical in 1:frozen.physical_dimension, right in 1:D
        if symmetry.virtual_charges[right] != symmetry.virtual_charges[left] + symmetry.physical_charges[physical]); init=0.0)
end

"Tensor-product spin flip in the column-major subsystem convention used by this module."
function product_flip(flips::AbstractMatrix...)
    isempty(flips) && return ones(ComplexF64, 1, 1)
    foldl((acc, flip) -> kron(flip, acc), flips;
        init=ones(ComplexF64, 1, 1))
end

"Residual of K Fᵢₙ = Fₒᵤₜ K for a spin-flip intertwiner."
function spin_flip_equivariance_residual(K::AbstractMatrix,
        output_flip::AbstractMatrix, input_flip::AbstractMatrix)
    size(K) == (size(output_flip, 1), size(input_flip, 1)) ||
        throw(DimensionMismatch("map and spin-flip dimensions differ"))
    size(output_flip, 1) == size(output_flip, 2) ||
        throw(DimensionMismatch("output spin flip must be square"))
    size(input_flip, 1) == size(input_flip, 2) ||
        throw(DimensionMismatch("input spin flip must be square"))
    norm(K * input_flip - output_flip * K, Inf)
end

"Largest tensor-level spin-flip intertwiner residual, without modifying the frozen tensors."
function mps_spin_flip_residual(frozen::FrozenUniformMPS, symmetry::SpinFlipSymmetry)
    frozen.physical_dimension == size(symmetry.physical_flip, 1) ||
        throw(DimensionMismatch("physical spin-flip dimension does not match MPS"))
    D = _uniform_bond_dimension(frozen)
    D == size(symmetry.virtual_flip, 1) ||
        throw(DimensionMismatch("virtual spin-flip dimension does not match MPS"))
    maximum((spin_flip_equivariance_residual(
        reshape(permutedims(A, (1, 3, 2)), D^2, frozen.physical_dimension),
        product_flip(conj(symmetry.virtual_flip), symmetry.virtual_flip),
        symmetry.physical_flip) for A in frozen.tensors); init=0.0)
end

function parity_basis(flip::AbstractMatrix; atol::Real=1e-12)
    size(flip, 1) == size(flip, 2) || throw(DimensionMismatch("spin flip must be square"))
    isapprox(flip, flip'; atol, rtol=0) || throw(ArgumentError("spin flip must be Hermitian"))
    decomposition = eigen(Hermitian(Matrix{ComplexF64}(flip)))
    all(abs(abs(value) - 1) <= atol for value in decomposition.values) ||
        throw(ArgumentError("spin-flip eigenvalues must be ±1"))
    minus = findall(<(0), decomposition.values)
    plus = findall(>(0), decomposition.values)
    U = decomposition.vectors[:, [plus; minus]]
    (; U, plus=collect(1:length(plus)),
        minus=collect(length(plus)+1:size(flip, 1)))
end

spin_flip_invariance_residual(X::AbstractMatrix, flip::AbstractMatrix) =
    norm(X * flip - flip * X, Inf)

function spin_flip_map_residuals(frozen::FrozenUniformMPS,
        symmetry::SpinFlipSymmetry; k0::Int=2, m::Int=k0, start_site::Int=1)
    Fp, Fv = symmetry.physical_flip, symmetry.virtual_flip
    rho_flip = product_flip(ntuple(_ -> Fp, k0 + 1)...)
    omega_flip = product_flip(Fp, conj(Fv), Fv, Fp)
    bridge = bottom_bridge_operators(frozen; k0, start_site)
    flow = flow_operators(frozen, m; start_site)
    Dict{String,Float64}(
        "mps" => mps_spin_flip_residual(frozen, symmetry),
        "Wm" => spin_flip_equivariance_residual(direct_Wm(frozen, m; start_site),
            product_flip(conj(Fv), Fv), product_flip(ntuple(_ -> Fp, m)...)),
        "bottom_left" => spin_flip_equivariance_residual(bridge.to_trace_physical_left,
            product_flip(conj(Fv), Fv, Fp), rho_flip),
        "bottom_right" => spin_flip_equivariance_residual(bridge.to_trace_physical_right,
            product_flip(Fp, conj(Fv), Fv), rho_flip),
        "flow_left" => spin_flip_equivariance_residual(flow.to_trace_physical_left,
            product_flip(conj(Fv), Fv, Fp), omega_flip),
        "flow_right" => spin_flip_equivariance_residual(flow.to_trace_physical_right,
            product_flip(Fp, conj(Fv), Fv), omega_flip))
end

function partial_trace_spin_flip_residual(X::AbstractMatrix, dims::Tuple, axis::Int,
        subsystem_flips::Tuple)
    length(dims) == length(subsystem_flips) ||
        throw(DimensionMismatch("one spin flip is required per subsystem"))
    input_flip = product_flip(subsystem_flips...)
    kept_flips = Tuple(subsystem_flips[i] for i in eachindex(dims) if i != axis)
    output_flip = product_flip(kept_flips...)
    norm(partial_trace(input_flip * X * input_flip', dims, axis) -
        output_flip * partial_trace(X, dims, axis) * output_flip', Inf)
end

function congruence_spin_flip_residual(K::AbstractMatrix, X::AbstractMatrix,
        output_flip::AbstractMatrix, input_flip::AbstractMatrix)
    norm(congruence(K, input_flip * X * input_flip') -
        output_flip * congruence(K, X) * output_flip', Inf)
end

function _parity_psd_matrix(model::JuMP.Model, flip::AbstractMatrix, base_name::String)
    basis = parity_basis(flip)
    dimension = size(flip, 1)
    transformed = Matrix{Any}(zeros(ComplexF64, dimension, dimension))
    blocks = Dict{Int,Any}()
    for (parity, indices) in ((1, basis.plus), (-1, basis.minus))
        isempty(indices) && continue
        n = length(indices)
        block = @variable(model, [1:n, 1:n] in HermitianPSDCone(),
            base_name="$(base_name)_parity_$(parity == 1 ? "plus" : "minus")")
        blocks[parity] = block
        transformed[indices, indices] = block
    end
    matrix = [sum(basis.U[i,a] * transformed[a,b] * conj(basis.U[j,b])
        for a in 1:dimension, b in 1:dimension)
        for i in 1:dimension, j in 1:dimension]
    matrix, blocks, basis
end

function _block_psd_matrix(model::JuMP.Model, charges::AbstractVector{<:Integer}, base_name::String;
        real_sdp::Bool=false)
    dimension = length(charges)
    matrix = Matrix{Any}(zeros(ComplexF64, dimension, dimension))
    blocks = Dict{Int,Any}()
    for (charge, indices) in charge_sectors(charges)
        n = length(indices)
        block = real_sdp ?
            @variable(model, [1:n, 1:n] in PSDCone(),
                base_name="$(base_name)_q$(charge)") :
            @variable(model, [1:n, 1:n] in HermitianPSDCone(),
                base_name="$(base_name)_q$(charge)")
        blocks[charge] = block
        for local_j in 1:n, local_i in 1:n
            matrix[indices[local_i], indices[local_j]] = block[local_i,local_j]
        end
    end
    matrix, blocks
end

function _embed_charge_blocks(blocks::AbstractDict, charges::AbstractVector{<:Integer}, transform)
    full = zeros(ComplexF64, length(charges), length(charges))
    for (charge, indices) in charge_sectors(charges)
        block = transform(blocks[charge])
        full[indices, indices] = block
    end
    full
end

function _project_charge_algebra(X::AbstractMatrix, charges::AbstractVector{<:Integer})
    projected = zeros(ComplexF64, size(X))
    for (_, indices) in charge_sectors(charges)
        projected[indices, indices] = X[indices, indices]
    end
    projected
end

function _uniform_bond_dimension(frozen::FrozenUniformMPS)
    dimensions = unique(vcat([[left, right] for (left, right) in frozen.bond_dimensions]...))
    length(dimensions) == 1 || throw(ArgumentError("coarse levels require one fixed virtual bond dimension"))
    only(dimensions)
end

function author_default_k0(d::Int, D::Int)
    d > 1 || throw(ArgumentError("physical dimension must exceed one"))
    D > 0 || throw(ArgumentError("bond dimension must be positive"))
    k0 = floor(Int, 2 * log(D) / log(d)) + 1
    d^k0 > D^2 || error("internal error: author k0 must satisfy d^k0 > D^2")
    k0
end

function resource_inventory(d::Int, D::Union{Nothing,Int}, depth::Int; k0::Int=2,
        start_parities::Int=1)
    k0 >= 1 || throw(ArgumentError("k0 must be positive"))
    depth >= k0 || throw(ArgumentError("hierarchy depth n must satisfy n ≥ k0"))
    start_parities in (1, 2) || throw(ArgumentError("only one-site and two-site frozen cells are supported"))
    coarse_levels = isnothing(D) ? 0 : start_parities * (depth - k0 + 1)
    rho_dimension = d^(k0 + 1)
    q = isnothing(D) ? 0 : d^2 * D^2
    marginal_dimension = isnothing(D) ? 0 : d * D^2
    blocks = [rho_dimension; fill(q, coarse_levels)]
    variables = sum(block^2 for block in blocks)
    equalities = 1 + d^(2k0) + 2 * coarse_levels * marginal_dimension^2
    coefficient_entries = rho_dimension^2 +
        2 * coarse_levels * marginal_dimension^2 * max(q^2, rho_dimension^2)
    coefficient_bytes = 16 * coefficient_entries
    peak_bytes = coefficient_bytes + 8 * equalities^2 + 16 * variables
    cubic_work = sum(block^3 for block in blocks) + equalities^3
    wall_seconds = max(1.0, cubic_work / 2.0e7)
    KullResourceInventory(blocks, length(blocks), variables, equalities,
        coefficient_bytes, peak_bytes, wall_seconds,
        peak_bytes < 16 * 1024^3 && wall_seconds < 600)
end

function _jump_edge_marginal(X, dims::Tuple, keep::Int, side::Symbol)
    Y, current_dims = X, dims
    while length(current_dims) > keep
        axis = side === :right ? 1 : length(current_dims)
        Y = _jump_partial_trace(Y, current_dims, axis)
        current_dims = Tuple(current_dims[i] for i in eachindex(current_dims) if i != axis)
    end
    Y
end

"Charge-sparse edge marginal for a tensor product with explicit subsystem charges."
function _jump_charge_edge_marginal(X, subsystem_charges::Tuple, keep::Int, side::Symbol)
    Y = X
    current = subsystem_charges
    while length(current) > keep
        axis = side === :right ? 1 : length(current)
        dims = Tuple(length(charges) for charges in current)
        remaining = Tuple(current[i] for i in eachindex(current) if i != axis)
        Y = _jump_charge_partial_trace(Y, dims, axis, product_charges(remaining...))
        current = remaining
    end
    Y
end

function _edge_marginal(X::AbstractMatrix, dims::Tuple, keep::Int, side::Symbol)
    Y, current_dims = X, dims
    while length(current_dims) > keep
        axis = side === :right ? 1 : length(current_dims)
        Y = partial_trace(Y, current_dims, axis)
        current_dims = Tuple(current_dims[i] for i in eachindex(current_dims) if i != axis)
    end
    Y
end

_start_parities(frozen::FrozenUniformMPS) = begin
    frozen.unit_cell_length in (1, 2) ||
        throw(ArgumentError("coarse-RDM fallback supports only one-site or two-site frozen cells"))
    1:frozen.unit_cell_length
end

_omega_key(frozen::FrozenUniformMPS, depth::Int, parity::Int=1) =
    frozen.unit_cell_length == 1 ? depth : (depth, parity)
_omega_name(frozen::FrozenUniformMPS, depth::Int, parity::Int=1) =
    frozen.unit_cell_length == 1 ? "omega_$depth" : "omega_$(depth)_p$(parity)"
_switch_parity(parity::Int) = 3 - parity

function _edge_marginal_adjoint(Y::AbstractMatrix, dims::Tuple, keep::Int, side::Symbol)
    traced = length(dims) - keep
    X = Y
    if side === :right
        for remaining in keep+1:length(dims)
            X = partial_trace_adjoint(X, dims[end-remaining+1:end], 1)
        end
    else
        for remaining in keep+1:length(dims)
            X = partial_trace_adjoint(X, dims[1:remaining], remaining)
        end
    end
    X
end

"Build the independent Hermitian Kull primal without running VUMPS or `optimize!`."
function build_kull_primal(h::AbstractMatrix; frozen::Union{Nothing,FrozenUniformMPS}=nothing,
        depth::Int=3, k0::Union{Nothing,Int}=nothing, optimizer=nothing,
        solver_settings=Dict{String,Any}(), vumps_upper_endpoint::Real=NaN,
        symmetry=nothing, real_sdp::Bool=false)
    size(h, 1) == size(h, 2) || throw(DimensionMismatch("h must be square"))
    d = isqrt(size(h, 1))
    d^2 == size(h, 1) || throw(DimensionMismatch("h must act on two equal-dimensional sites"))
    isapprox(h, h'; atol=1e-12, rtol=1e-12) || throw(ArgumentError("h must be Hermitian"))

    symmetry isa Tuple && throw(ArgumentError(
        "combined U(1)⋊Z2 symmetry is unsupported; use standalone U(1) or standalone Z2"))
    symmetry isa Union{Nothing,U1Symmetry,SpinFlipSymmetry} ||
        throw(ArgumentError("symmetry must be nothing, U1Symmetry, or standalone SpinFlipSymmetry"))
    real_sdp && !(symmetry isa U1Symmetry) &&
        throw(ArgumentError("real SDP representation currently requires standalone U(1) block structure"))
    real_sdp && maximum(abs, imag.(h); init=0.0) > 1e-12 &&
        throw(ArgumentError("real SDP representation requires a real Hamiltonian"))
    real_sdp && !isnothing(frozen) &&
        maximum((abs(imag(value)) for A in frozen.tensors for value in A); init=0.0) > 1e-12 &&
        throw(ArgumentError("real SDP representation requires a real frozen coarse map"))

    D = isnothing(frozen) ? nothing : _uniform_bond_dimension(frozen)
    parities = isnothing(frozen) ? (1:1) : _start_parities(frozen)
    !isnothing(frozen) && frozen.physical_dimension != d &&
        throw(DimensionMismatch("h and frozen map physical dimensions differ"))
    !isnothing(D) && D < 1 &&
        throw(ArgumentError("coarse-RDM bond dimension must be positive"))
    selected_k0 = isnothing(k0) ? (isnothing(D) ? 2 : author_default_k0(d, D)) : k0
    selected_k0 >= 2 || throw(ArgumentError("k0 must be at least 2 for a two-site objective"))
    depth >= selected_k0 || throw(ArgumentError("hierarchy depth n must satisfy n ≥ k0"))

    rho_support = selected_k0 + 1
    rho_dims = ntuple(_ -> d, rho_support)
    rho_dimension = d^rho_support
    is_u1 = symmetry isa U1Symmetry
    is_z2 = symmetry isa SpinFlipSymmetry
    if is_u1
        length(symmetry.physical_charges) == d ||
            throw(DimensionMismatch("physical charge count must equal d"))
        hcharges = product_charges(symmetry.physical_charges, symmetry.physical_charges)
        equivariance_residual(h, hcharges, hcharges) <= 1e-12 ||
            throw(ArgumentError("Hamiltonian does not conserve the supplied U(1) charge"))
        !isnothing(frozen) && mps_charge_residual(frozen, symmetry) > 1e-12 &&
            throw(ArgumentError("frozen MPS is not an intertwiner for the supplied U(1) charges"))
    elseif is_z2
        size(symmetry.physical_flip) == (d, d) ||
            throw(DimensionMismatch("physical spin-flip dimension must equal d"))
        hflip = product_flip(symmetry.physical_flip, symmetry.physical_flip)
        spin_flip_invariance_residual(h, hflip) <= 1e-12 ||
            throw(ArgumentError("Hamiltonian is not invariant under the supplied standalone Z2 spin flip"))
        if !isnothing(frozen)
            size(symmetry.virtual_flip) == (D, D) ||
                throw(DimensionMismatch("virtual spin-flip dimension must equal the coarse bond dimension"))
            mps_spin_flip_residual(frozen, symmetry) <= 1e-12 ||
                throw(ArgumentError("frozen MPS is not a spin-flip intertwiner"))
            for parity in parities, m in selected_k0:depth
                residuals = spin_flip_map_residuals(frozen, symmetry;
                    k0=selected_k0, m, start_site=parity)
                maximum(values(residuals)) <= 1e-12 ||
                    throw(ArgumentError("coarse maps are not spin-flip equivariant; residuals=$residuals"))
            end
        end
    end
    model = isnothing(optimizer) ? Model() : Model(optimizer)
    for (attribute, value) in solver_settings
        set_optimizer_attribute(model, attribute, value)
    end
    symmetry_blocks = Dict{String,Any}()
    symmetry_charges = Dict{String,Vector{Int}}()
    parity_bases = Dict{String,Any}()
    rho_charges = Int[]
    if isnothing(symmetry)
        @variable(model, rho3[1:rho_dimension, 1:rho_dimension] in HermitianPSDCone())
    elseif is_u1
        rho_charges = product_charges(ntuple(_ -> symmetry.physical_charges, rho_support)...)
        rho3, symmetry_blocks["rho3"] = _block_psd_matrix(model, rho_charges, "rho"; real_sdp)
        symmetry_charges["rho3"] = rho_charges
    else
        rho_flip = product_flip(ntuple(_ -> symmetry.physical_flip, rho_support)...)
        rho3, symmetry_blocks["rho3"], parity_bases["rho3"] =
            _parity_psd_matrix(model, rho_flip, "rho")
    end
    constraints = Dict{Symbol,Vector{Any}}(
        :normalization => Any[], :lti => Any[], :bottom => Any[], :flow => Any[])
    push!(constraints[:normalization], @constraint(model,
        real(sum(rho3[i,i] for i in 1:rho_dimension)) == 1))
    if is_u1
        rho_subsystems = ntuple(_ -> symmetry.physical_charges, rho_support)
        marginal_charges = product_charges(ntuple(_ -> symmetry.physical_charges,
            selected_k0)...)
        left_marginal = _jump_charge_edge_marginal(rho3, rho_subsystems,
            selected_k0, :left)
        right_marginal = _jump_charge_edge_marginal(rho3, rho_subsystems,
            selected_k0, :right)
        append!(constraints[:lti], _add_charge_equalities!(model,
            left_marginal, right_marginal, marginal_charges; real_sdp))
        objective_marginal = _jump_charge_edge_marginal(rho3, rho_subsystems, 2, :right)
    else
        left_marginal = _jump_edge_marginal(rho3, rho_dims, selected_k0, :left)
        right_marginal = _jump_edge_marginal(rho3, rho_dims, selected_k0, :right)
        append!(constraints[:lti], _add_hermitian_equalities!(model,
            left_marginal, right_marginal))
        objective_marginal = _jump_edge_marginal(rho3, rho_dims, 2, :right)
    end
    @objective(model, Min, real(sum(h[i,j] * objective_marginal[j,i]
        for i in 1:d^2, j in 1:d^2)))

    omegas = Dict{Any,Any}()
    if !isnothing(frozen)
        q = d^2 * D^2
        omega_dims = (d, D, D, d)
        omega_charges = is_u1 ? product_charges(symmetry.physical_charges,
            -symmetry.virtual_charges, symmetry.virtual_charges,
            symmetry.physical_charges) : Int[]
        omega_flip = is_z2 ? product_flip(symmetry.physical_flip,
            conj(symmetry.virtual_flip), symmetry.virtual_flip,
            symmetry.physical_flip) : zeros(ComplexF64, 0, 0)
        for m in selected_k0:depth, parity in parities
            key = _omega_key(frozen, m, parity)
            name = _omega_name(frozen, m, parity)
            if isnothing(symmetry)
                omegas[key] = @variable(model, [1:q, 1:q] in HermitianPSDCone(), base_name=name)
            elseif is_u1
                omegas[key], symmetry_blocks[name] = _block_psd_matrix(model, omega_charges, name; real_sdp)
                symmetry_charges[name] = omega_charges
            else
                omegas[key], symmetry_blocks[name], parity_bases[name] =
                    _parity_psd_matrix(model, omega_flip, name)
            end
        end
        for parity in parities
            key = _omega_key(frozen, selected_k0, parity)
            bridge = bottom_bridge_operators(frozen; k0=selected_k0, start_site=parity)
            if !is_u1
                append!(constraints[:bottom], _add_hermitian_equalities!(model,
                    _jump_congruence(bridge.to_trace_physical_left, rho3),
                    _jump_partial_trace(omegas[key], omega_dims, 1)))
                append!(constraints[:bottom], _add_hermitian_equalities!(model,
                    _jump_congruence(bridge.to_trace_physical_right, rho3),
                    _jump_partial_trace(omegas[key], omega_dims, 4)))
            else
                left_charges = product_charges(-symmetry.virtual_charges,
                    symmetry.virtual_charges, symmetry.physical_charges)
                right_charges = product_charges(symmetry.physical_charges,
                    -symmetry.virtual_charges, symmetry.virtual_charges)
                append!(constraints[:bottom], _add_charge_equalities!(model,
                    _jump_sparse_congruence(bridge.to_trace_physical_left, rho3, left_charges),
                    _jump_charge_partial_trace(omegas[key], omega_dims, 1, left_charges),
                    left_charges; real_sdp))
                append!(constraints[:bottom], _add_charge_equalities!(model,
                    _jump_sparse_congruence(bridge.to_trace_physical_right, rho3, right_charges),
                    _jump_charge_partial_trace(omegas[key], omega_dims, 4, right_charges),
                    right_charges; real_sdp))
            end
        end
        for m in selected_k0:depth-1, parity in parities
            next_key = _omega_key(frozen, m + 1, parity)
            right_source = _omega_key(frozen, m, parity)
            left_parity = frozen.unit_cell_length == 1 ? parity : _switch_parity(parity)
            left_source = _omega_key(frozen, m, left_parity)
            flow = flow_operators(frozen, m; start_site=parity)
            if !is_u1
                append!(constraints[:flow], _add_hermitian_equalities!(model,
                    _jump_congruence(flow.to_trace_physical_left, omegas[left_source]),
                    _jump_partial_trace(omegas[next_key], omega_dims, 1)))
                append!(constraints[:flow], _add_hermitian_equalities!(model,
                    _jump_congruence(flow.to_trace_physical_right, omegas[right_source]),
                    _jump_partial_trace(omegas[next_key], omega_dims, 4)))
            else
                left_charges = product_charges(-symmetry.virtual_charges,
                    symmetry.virtual_charges, symmetry.physical_charges)
                right_charges = product_charges(symmetry.physical_charges,
                    -symmetry.virtual_charges, symmetry.virtual_charges)
                append!(constraints[:flow], _add_charge_equalities!(model,
                    _jump_sparse_congruence(flow.to_trace_physical_left,
                        omegas[left_source], left_charges),
                    _jump_charge_partial_trace(omegas[next_key], omega_dims, 1, left_charges),
                    left_charges; real_sdp))
                append!(constraints[:flow], _add_charge_equalities!(model,
                    _jump_sparse_congruence(flow.to_trace_physical_right,
                        omegas[right_source], right_charges),
                    _jump_charge_partial_trace(omegas[next_key], omega_dims, 4, right_charges),
                    right_charges; real_sdp))
            end
        end
    end

    inventory = resource_inventory(d, D, depth; k0=selected_k0,
        start_parities=length(parities))
    if is_u1
        rho_sizes = last.(charge_sectors(product_charges(ntuple(_ -> symmetry.physical_charges, rho_support)...))) .|> length
        omega_sizes = isnothing(D) ? Int[] :
            last.(charge_sectors(product_charges(symmetry.physical_charges,
                -symmetry.virtual_charges, symmetry.virtual_charges,
                symmetry.physical_charges))) .|> length
        block_sizes = [rho_sizes; repeat(omega_sizes,
            length(parities) * (depth - selected_k0 + 1))]
        variables = real_sdp ? sum(n * (n + 1) ÷ 2 for n in block_sizes) :
            sum(abs2, block_sizes)
        sparse_equalities = sum(length, values(constraints))
        coefficient_bytes = 16 * (variables + 8 * sparse_equalities)
        peak_bytes = coefficient_bytes + 8 * sparse_equalities^2 + 16 * variables
        wall_seconds = max(1.0,
            sum(block^3 for block in block_sizes) / 2.0e7 +
            sparse_equalities^2 / 2.0e7)
        local_feasible = peak_bytes < 16 * 1024^3 && wall_seconds < 600
        inventory = KullResourceInventory(block_sizes, length(block_sizes), variables,
            sparse_equalities, coefficient_bytes, peak_bytes, wall_seconds, local_feasible)
    elseif is_z2
        rho_basis = parity_bases["rho3"]
        rho_sizes = filter(>(0), [length(rho_basis.plus), length(rho_basis.minus)])
        omega_sizes = Int[]
        if !isnothing(D)
            omega_basis = parity_bases[_omega_name(frozen, selected_k0, first(parities))]
            omega_sizes = filter(>(0), [length(omega_basis.plus), length(omega_basis.minus)])
        end
        block_sizes = [rho_sizes; repeat(omega_sizes,
            length(parities) * (depth - selected_k0 + 1))]
        variables = sum(abs2, block_sizes)
        equalities = sum(length, values(constraints))
        coefficient_bytes = 16 * (variables + 8 * equalities)
        peak_bytes = coefficient_bytes + 8 * equalities^2 + 16 * variables
        wall_seconds = max(1.0, sum(block^3 for block in block_sizes) / 2.0e7 +
            equalities^2 / 2.0e7)
        inventory = KullResourceInventory(block_sizes, length(block_sizes), variables,
            equalities, coefficient_bytes, peak_bytes, wall_seconds,
            peak_bytes < 16 * 1024^3 && wall_seconds < 600)
    end
    metadata = Dict{String,Any}(
        "depth" => depth, "n" => depth, "k0" => selected_k0,
        "rho_support" => rho_support, "omega_physical_support_offset" => 2,
        "omega_start_parities" => collect(parities),
        "omega_key_scheme" => isnothing(frozen) || frozen.unit_cell_length == 1 ?
            "depth" : "(depth,start_parity)",
        "physical_dimension" => d, "bond_dimension" => D, "hamiltonian" => Matrix{ComplexF64}(h),
        "map_fingerprint" => isnothing(frozen) ? nothing : frozen.fingerprint,
        "frozen_map" => frozen, "vumps_upper_endpoint" => Float64(vumps_upper_endpoint),
        "representation" => isnothing(symmetry) ? "JuMP HermitianPSDCone" :
            (is_u1 ? (real_sdp ? "U(1) block SymmetricPSDCone" :
                "U(1) block HermitianPSDCone") :
                "standalone Z2 parity-block HermitianPSDCone"),
        "symmetry_mode" => isnothing(symmetry) ? "none" :
            (is_u1 ? "standalone U(1)" : "standalone Z2"),
        "semidirect_product_supported" => false,
        "real_sdp" => real_sdp,
        "symmetry" => symmetry, "symmetry_blocks" => symmetry_blocks,
        "symmetry_charges" => symmetry_charges, "parity_bases" => parity_bases,
        "optimized" => false,
        "coefficient_policy" => isnothing(frozen) ?
            Dict{String,Any}("mode" => "exact-hamiltonian-only", "complete_interval_enclosure" => true) :
            coefficient_enclosure_policy(frozen))
    KullPrimalProblem(model, rho3, omegas, constraints, inventory, metadata)
end

function _numeric_constraint_residual(problem::KullPrimalProblem)
    d = problem.metadata["physical_dimension"]
    depth = problem.metadata["depth"]
    k0 = problem.metadata["k0"]
    rho_support = problem.metadata["rho_support"]
    rho_dims = ntuple(_ -> d, rho_support)
    rho = value.(problem.rho3)
    residual = max(abs(real(tr(rho)) - 1),
        norm(_edge_marginal(rho, rho_dims, k0, :left) -
            _edge_marginal(rho, rho_dims, k0, :right), Inf))
    if !isempty(problem.omegas)
        frozen = problem.metadata["frozen_map"]::FrozenUniformMPS
        D = problem.metadata["bond_dimension"]
        dims = (d,D,D,d)
        parities = _start_parities(frozen)
        for parity in parities
            bridge = bottom_bridge_operators(frozen; k0, start_site=parity)
            omega0 = value.(problem.omegas[_omega_key(frozen, k0, parity)])
            residual = max(residual,
                norm(forward_map(bridge.to_trace_physical_left, rho) - partial_trace(omega0, dims, 1), Inf),
                norm(forward_map(bridge.to_trace_physical_right, rho) - partial_trace(omega0, dims, 4), Inf))
        end
        for m in k0:depth-1, parity in parities
            flow = flow_operators(frozen, m; start_site=parity)
            left_parity = frozen.unit_cell_length == 1 ? parity : _switch_parity(parity)
            left_source = value.(problem.omegas[_omega_key(frozen, m, left_parity)])
            right_source = value.(problem.omegas[_omega_key(frozen, m, parity)])
            following = value.(problem.omegas[_omega_key(frozen, m + 1, parity)])
            residual = max(residual,
                norm(forward_map(flow.to_trace_physical_left, left_source) - partial_trace(following, dims, 1), Inf),
                norm(forward_map(flow.to_trace_physical_right, right_source) - partial_trace(following, dims, 4), Inf))
        end
    end
    Float64(residual)
end

"State the coefficient policy without overstating floating-point certification."
function coefficient_enclosure_policy(frozen::FrozenUniformMPS; denominator_limit::Int=10^9)
    denominator_limit > 0 || throw(ArgumentError("denominator_limit must be positive"))
    errors = Float64[]
    for A in frozen.tensors, value in A
        zr = rationalize(real(value); tol=0)
        zi = rationalize(imag(value); tol=0)
        rr = denominator(zr) <= denominator_limit ? zr : rationalize(real(value); tol=1/denominator_limit)
        ri = denominator(zi) <= denominator_limit ? zi : rationalize(imag(value); tol=1/denominator_limit)
        push!(errors, abs(value - ComplexF64(rr, ri)))
    end
    Dict{String,Any}(
        "mode" => "floating-map-with-rationalization-diagnostic",
        "denominator_limit" => denominator_limit,
        "maximum_tensor_coefficient_error" => maximum(errors; init=0.0),
        "complete_interval_enclosure" => false,
        "policy" => "Rational approximants are diagnostics only; certify only after outward-rounded interval propagation through every assembled map coefficient.")
end

function _trace_nonincreasing_diagnostic(problem::KullPrimalProblem; tolerance::Real=1e-10)
    isempty(problem.omegas) && return (true, 1.0, Dict{String,Float64}())
    frozen = problem.metadata["frozen_map"]::FrozenUniformMPS
    k0 = problem.metadata["k0"]
    envelopes = Dict{String,Float64}()
    for parity in _start_parities(frozen)
        suffix = frozen.unit_cell_length == 1 ? "" : "_p$parity"
        bridge = bottom_bridge_operators(frozen; k0, start_site=parity)
        envelopes["bottom_left$suffix"] = maximum(real.(eigvals(Hermitian(bridge.to_trace_physical_left' * bridge.to_trace_physical_left))))
        envelopes["bottom_right$suffix"] = maximum(real.(eigvals(Hermitian(bridge.to_trace_physical_right' * bridge.to_trace_physical_right))))
        for m in k0:problem.metadata["depth"]-1
            flow = flow_operators(frozen, m; start_site=parity)
            envelopes["flow_$(m)_left$suffix"] = maximum(real.(eigvals(Hermitian(flow.to_trace_physical_left' * flow.to_trace_physical_left))))
            envelopes["flow_$(m)_right$suffix"] = maximum(real.(eigvals(Hermitian(flow.to_trace_physical_right' * flow.to_trace_physical_right))))
        end
    end
    envelope = maximum(values(envelopes); init=1.0)
    envelope <= 1 + tolerance, envelope, envelopes
end

_project_psd(X::AbstractMatrix) = begin
    decomposition = eigen(Hermitian((X + X') / 2))
    decomposition.vectors * Diagonal(max.(decomposition.values, 0.0)) * decomposition.vectors'
end

"Return finite trace bounds for every PSD block by propagating congruence envelopes."
function _trace_bounds(problem::KullPrimalProblem)
    bounds = Dict{String,Float64}("rho3" => 1.0)
    isempty(problem.omegas) && return bounds
    frozen = problem.metadata["frozen_map"]::FrozenUniformMPS
    k0 = problem.metadata["k0"]
    depth = problem.metadata["depth"]
    parities = _start_parities(frozen)
    for parity in parities
        name = _omega_name(frozen, k0, parity)
        bridge = bottom_bridge_operators(frozen; k0, start_site=parity)
        bounds[name] = min(opnorm(bridge.to_trace_physical_left)^2,
            opnorm(bridge.to_trace_physical_right)^2)
    end
    for m in k0:depth-1, parity in parities
        flow = flow_operators(frozen, m; start_site=parity)
        left_parity = frozen.unit_cell_length == 1 ? parity : _switch_parity(parity)
        bounds[_omega_name(frozen, m + 1, parity)] = min(
            bounds[_omega_name(frozen, m, left_parity)] * opnorm(flow.to_trace_physical_left)^2,
            bounds[_omega_name(frozen, m, parity)] * opnorm(flow.to_trace_physical_right)^2)
    end
    bounds
end

"Export all cone/equality duals and reconstruct stationarity with the shared map adjoints."
function reconstruct_dual_certificate(problem::KullPrimalProblem)
    problem.metadata["symmetry"] isa SpinFlipSymmetry &&
        throw(ArgumentError("dual-certificate reconstruction for standalone Z2 parity blocks is unsupported"))
    problem.metadata["optimized"] || throw(ArgumentError("solve the primal before exporting its dual"))
    dual_status(problem.model) in (MOI.FEASIBLE_POINT, MOI.NEARLY_FEASIBLE_POINT) ||
        throw(ArgumentError("the solver did not return a dual point"))
    d = problem.metadata["physical_dimension"]
    depth = problem.metadata["depth"]
    k0 = problem.metadata["k0"]
    rho_support = problem.metadata["rho_support"]
    rho_dims = ntuple(_ -> d, rho_support)
    normalization = Float64(dual(only(problem.constraints[:normalization])))
    symmetry = problem.metadata["symmetry"]
    multipliers = Dict{String,Matrix{ComplexF64}}()
    if isnothing(symmetry)
        multipliers["lti"], cursor = _hermitian_multiplier(problem.constraints[:lti], d^k0)
    else
        lti_charges = product_charges(ntuple(_ -> symmetry.physical_charges, k0)...)
        multipliers["lti"], cursor = _charge_hermitian_multiplier(
            problem.constraints[:lti], lti_charges; real_sdp=problem.metadata["real_sdp"])
    end
    cursor == length(problem.constraints[:lti]) || error("unconsumed LTI multipliers")
    if !isempty(problem.omegas)
        D = problem.metadata["bond_dimension"]
        marginal_dimension = d * D^2
        frozen = problem.metadata["frozen_map"]::FrozenUniformMPS
        refs = problem.constraints[:bottom]
        cursor = 0
        for parity in _start_parities(frozen)
            suffix = frozen.unit_cell_length == 1 ? "" : "_p$parity"
            if isnothing(symmetry)
                multipliers["bottom_left$suffix"], cursor = _hermitian_multiplier(
                    refs, marginal_dimension, cursor)
                multipliers["bottom_right$suffix"], cursor = _hermitian_multiplier(
                    refs, marginal_dimension, cursor)
            else
                left_charges = product_charges(-symmetry.virtual_charges,
                    symmetry.virtual_charges, symmetry.physical_charges)
                right_charges = product_charges(symmetry.physical_charges,
                    -symmetry.virtual_charges, symmetry.virtual_charges)
                multipliers["bottom_left$suffix"], cursor = _charge_hermitian_multiplier(
                    refs, left_charges, cursor; real_sdp=problem.metadata["real_sdp"])
                multipliers["bottom_right$suffix"], cursor = _charge_hermitian_multiplier(
                    refs, right_charges, cursor; real_sdp=problem.metadata["real_sdp"])
            end
        end
        cursor == length(refs) || error("unconsumed bottom multipliers")
        refs = problem.constraints[:flow]
        cursor = 0
        for m in k0:depth-1, parity in _start_parities(frozen)
            suffix = frozen.unit_cell_length == 1 ? "" : "_p$parity"
            if isnothing(symmetry)
                multipliers["flow_$(m)_left$suffix"], cursor = _hermitian_multiplier(
                    refs, marginal_dimension, cursor)
                multipliers["flow_$(m)_right$suffix"], cursor = _hermitian_multiplier(
                    refs, marginal_dimension, cursor)
            else
                left_charges = product_charges(-symmetry.virtual_charges,
                    symmetry.virtual_charges, symmetry.physical_charges)
                right_charges = product_charges(symmetry.physical_charges,
                    -symmetry.virtual_charges, symmetry.virtual_charges)
                multipliers["flow_$(m)_left$suffix"], cursor = _charge_hermitian_multiplier(
                    refs, left_charges, cursor; real_sdp=problem.metadata["real_sdp"])
                multipliers["flow_$(m)_right$suffix"], cursor = _charge_hermitian_multiplier(
                    refs, right_charges, cursor; real_sdp=problem.metadata["real_sdp"])
            end
        end
        cursor == length(refs) || error("unconsumed flow multipliers")
    end

    if isnothing(symmetry)
        psd_duals = Dict{String,Matrix{ComplexF64}}(
            "rho3" => Matrix{ComplexF64}(dual(JuMP.VariableInSetRef(problem.rho3))))
        frozen = problem.metadata["frozen_map"]::FrozenUniformMPS
        for m in k0:depth, parity in _start_parities(frozen)
            key = _omega_key(frozen, m, parity)
            psd_duals[_omega_name(frozen, m, parity)] =
                Matrix{ComplexF64}(dual(JuMP.VariableInSetRef(problem.omegas[key])))
        end
    else
        blocks = problem.metadata["symmetry_blocks"]
        charges = problem.metadata["symmetry_charges"]
        psd_duals = Dict(name => _embed_charge_blocks(blocks[name], charges[name],
                block -> Matrix{ComplexF64}(dual(JuMP.VariableInSetRef(block))))
            for name in keys(blocks))
    end
    projected = Dict(name => _project_psd(slack) for (name, slack) in psd_duals)

    objective_rho = _edge_marginal_adjoint(problem.metadata["hamiltonian"], rho_dims, 2, :right)
    rho_stationarity = objective_rho - normalization * I
    Y = multipliers["lti"]
    rho_stationarity -= _edge_marginal_adjoint(Y, rho_dims, k0, :left) -
        _edge_marginal_adjoint(Y, rho_dims, k0, :right)
    omega_stationarity = Dict{Any,Matrix{ComplexF64}}()
    if !isempty(problem.omegas)
        frozen = problem.metadata["frozen_map"]::FrozenUniformMPS
        D = problem.metadata["bond_dimension"]
        dims = (d,D,D,d)
        parities = _start_parities(frozen)
        q = prod(dims)
        for m in k0:depth, parity in parities
            omega_stationarity[_omega_key(frozen, m, parity)] = zeros(ComplexF64, q, q)
        end
        for parity in parities
            suffix = frozen.unit_cell_length == 1 ? "" : "_p$parity"
            bridge = bottom_bridge_operators(frozen; k0, start_site=parity)
            left_Y = multipliers["bottom_left$suffix"]
            right_Y = multipliers["bottom_right$suffix"]
            rho_stationarity -= forward_map_adjoint(bridge.to_trace_physical_left, left_Y)
            rho_stationarity -= forward_map_adjoint(bridge.to_trace_physical_right, right_Y)
            omega_stationarity[_omega_key(frozen, k0, parity)] +=
                partial_trace_adjoint(left_Y, dims, 1) + partial_trace_adjoint(right_Y, dims, 4)
        end
        for m in k0:depth-1, parity in parities
            suffix = frozen.unit_cell_length == 1 ? "" : "_p$parity"
            flow = flow_operators(frozen, m; start_site=parity)
            left_Y = multipliers["flow_$(m)_left$suffix"]
            right_Y = multipliers["flow_$(m)_right$suffix"]
            left_parity = frozen.unit_cell_length == 1 ? parity : _switch_parity(parity)
            omega_stationarity[_omega_key(frozen, m, left_parity)] -=
                forward_map_adjoint(flow.to_trace_physical_left, left_Y)
            omega_stationarity[_omega_key(frozen, m, parity)] -=
                forward_map_adjoint(flow.to_trace_physical_right, right_Y)
            omega_stationarity[_omega_key(frozen, m + 1, parity)] +=
                partial_trace_adjoint(left_Y, dims, 1) + partial_trace_adjoint(right_Y, dims, 4)
        end
    end
    affine_slacks = Dict{String,Matrix{ComplexF64}}("rho3" => rho_stationarity)
    if !isempty(omega_stationarity)
        frozen = problem.metadata["frozen_map"]::FrozenUniformMPS
        for m in k0:depth, parity in _start_parities(frozen)
            affine_slacks[_omega_name(frozen, m, parity)] =
                omega_stationarity[_omega_key(frozen, m, parity)]
        end
    end
    if !isnothing(symmetry)
        charges = problem.metadata["symmetry_charges"]
        affine_slacks = Dict(name => _project_charge_algebra(slack, charges[name])
            for (name, slack) in affine_slacks)
    end
    projected = Dict(name => _project_psd(slack) for (name, slack) in affine_slacks)
    residuals = Dict(name => affine_slacks[name] - projected[name] for name in keys(affine_slacks))
    residual_norms = Dict(name => opnorm(Hermitian((R + R') / 2)) for (name,R) in residuals)
    trace_ok, trace_envelope, _ = _trace_nonincreasing_diagnostic(problem)
    trace_bounds = _trace_bounds(problem)
    correction = sum(residual_norms[name] * trace_bounds[name] for name in keys(residual_norms))
    corrected = normalization - correction
    minimum_dual_eigenvalue = minimum(minimum(real.(eigvals(Hermitian(Z)))) for Z in values(psd_duals))
    policy = problem.metadata["coefficient_policy"]
    classification = get(policy, "complete_interval_enclosure", false) ?
        "residual-corrected-exact-coefficients" : "residual-corrected-floating-coefficients"
    KullDualCertificate(normalization, multipliers, psd_duals, projected, residuals,
        minimum_dual_eigenvalue, maximum(values(residual_norms); init=0.0), correction,
        corrected, trace_ok, trace_envelope, policy, problem.metadata["map_fingerprint"], classification)
end

function dual_certificate_dict(certificate::KullDualCertificate)
    encode_matrix(X) = Dict("real" => real.(X), "imag" => imag.(X))
    Dict{String,Any}(
        "normalization_multiplier" => certificate.normalization_multiplier,
        "equality_multipliers" => Dict(k => encode_matrix(v) for (k,v) in certificate.equality_multipliers),
        "psd_duals" => Dict(k => encode_matrix(v) for (k,v) in certificate.psd_duals),
        "projected_psd_duals" => Dict(k => encode_matrix(v) for (k,v) in certificate.projected_psd_duals),
        "stationarity_residuals" => Dict(k => encode_matrix(v) for (k,v) in certificate.stationarity_residuals),
        "minimum_dual_eigenvalue" => certificate.minimum_dual_eigenvalue,
        "maximum_stationarity_residual" => certificate.maximum_stationarity_residual,
        "residual_correction" => certificate.residual_correction,
        "corrected_lower_bound" => certificate.corrected_lower_bound,
        "trace_nonincreasing" => certificate.trace_nonincreasing,
        "trace_envelope" => certificate.trace_envelope,
        "coefficient_policy" => certificate.coefficient_policy,
        "map_fingerprint" => certificate.map_fingerprint,
        "classification" => certificate.classification)
end

function final_inequality_checks(result::KullSolverResult, certificate::KullDualCertificate;
        exact_energy::Real=EXACT_ENERGY, tolerance::Real=1e-7)
    Dict{String,Bool}(
        "corrected_le_raw" => certificate.corrected_lower_bound <= result.lower_bound_candidate + tolerance,
        "raw_le_exact" => result.lower_bound_candidate <= exact_energy + tolerance,
        "exact_le_vumps" => !isfinite(result.vumps_upper_endpoint) || exact_energy <= result.vumps_upper_endpoint + tolerance,
        "same_map_fingerprint" => certificate.map_fingerprint == result.map_fingerprint,
        "trace_nonincreasing" => certificate.trace_nonincreasing)
end

_accepted_termination(status::MOI.TerminationStatusCode) =
    status in (MOI.OPTIMAL, MOI.SLOW_PROGRESS)

function solve_kull_primal!(problem::KullPrimalProblem; clean_tolerance::Real=1e-7,
        require_local_feasible::Bool=true, print_inventory::Bool=true)
    inventory = problem.inventory
    print_inventory && println("resource_inventory psd_blocks=$(inventory.psd_block_dimensions) " *
        "real_variables=$(inventory.real_scalar_variables) equalities=$(inventory.linear_equalities) " *
        "coefficient_bytes=$(inventory.coefficient_storage_bytes) peak_bytes=$(inventory.peak_memory_bytes) " *
        "estimated_wall_seconds=$(inventory.estimated_wall_seconds) local_feasible=$(inventory.local_feasible)")
    flush(stdout)
    require_local_feasible && !inventory.local_feasible &&
        throw(ArgumentError("estimated solve exceeds the local 10 minute or 16 GiB budget"))
    optimize!(problem.model)
    problem.metadata["optimized"] = true
    termination = termination_status(problem.model)
    primal = primal_status(problem.model)
    dual = dual_status(problem.model)
    has_point = primal in (MOI.FEASIBLE_POINT, MOI.NEARLY_FEASIBLE_POINT)
    candidate = has_point ? objective_value(problem.model) : NaN
    gap = try MOI.get(problem.model, MOI.RelativeGap()) catch; NaN end
    runtime = try solve_time(problem.model) catch; NaN end
    residual = has_point ? _numeric_constraint_residual(problem) : Inf
    eigenvalues = has_point ? [eigvals(Hermitian(value.(problem.rho3)))] : Vector{Vector{Float64}}()
    has_point && append!(eigenvalues,
        [eigvals(Hermitian(value.(omega))) for omega in values(problem.omegas)])
    minimum_eigenvalue = has_point ? minimum(vcat(eigenvalues...)) : -Inf
    accepted_termination = _accepted_termination(termination)
    clean = accepted_termination && primal == MOI.FEASIBLE_POINT &&
        dual == MOI.FEASIBLE_POINT && residual <= clean_tolerance &&
        minimum_eigenvalue >= -clean_tolerance
    KullSolverResult(Float64(candidate), termination, primal, dual, Float64(gap),
        residual, Float64(minimum_eigenvalue), Float64(runtime),
        problem.metadata["map_fingerprint"], problem.metadata["vumps_upper_endpoint"],
        clean, clean ? "numerical-clean-accepted" : "diagnostic-only")
end

export Sx, Sy, Sz, HEISENBERG_H, EXACT_ENERGY, xxz_hamiltonian, blocked_xxz_hamiltonian
export U1Symmetry, SpinFlipSymmetry, permutation_matrix, validate_spin_flip, validate_charge_reversal
export product_charges, charge_sectors, equivariance_residual, mps_charge_residual
export product_flip, parity_basis, spin_flip_equivariance_residual, spin_flip_invariance_residual
export mps_spin_flip_residual, spin_flip_map_residuals, partial_trace_spin_flip_residual
export congruence_spin_flip_residual
export FrozenUniformMPS, frozen_fingerprint, product_frozen_mps, random_canonical_frozen_mps
export AXIS_CONTRACT, flatten_ket, unflatten_ket, matrix_to_named_operator, named_operator_to_matrix
export site_tensor, direct_Wm, W2, left_absorption, right_absorption, recursive_Wm
export boundary_extension, congruence, congruence_adjoint, forward_map, forward_map_adjoint
export partial_trace, partial_trace_adjoint
export bottom_bridge_operators, flow_operators, compress_physical_rdm
export KullResourceInventory, KullPrimalProblem, KullSolverResult, KullDualCertificate
export resource_inventory, author_default_k0, build_kull_primal, solve_kull_primal!
export coefficient_enclosure_policy, reconstruct_dual_certificate, dual_certificate_dict
export final_inequality_checks

end
