module MPSKitAdapter

using LinearAlgebra
using TensorKit
using MPSKit
if isdefined(parentmodule(@__MODULE__), :KullCGRDM)
    using ..KullCGRDM
else
    include("KullCGRDM.jl")
    using .KullCGRDM
end

"Convert AL with codomain virtual_left⊗physical and domain virtual_right."
function dense_left_physical_right(tensor)
    c = codomain(tensor)
    d = domain(tensor)
    length(c) == 2 || throw(DimensionMismatch("AL codomain must have left-virtual and physical factors"))
    length(d) == 1 || throw(DimensionMismatch("AL domain must have one right-virtual factor"))
    raw = convert(Array, tensor)
    dims = (dim(c[1]), dim(c[2]), dim(d[1]))
    size(raw) == dims || throw(DimensionMismatch("TensorKit storage does not match declared left/physical/right spaces"))
    copy(raw)
end

"Twice the U(1) charge of each dense TensorKit basis state, preserving storage order."
function dense_u1_charges(space)
    charges = Int[]
    for sector in blocksectors(space)
        charge = getfield(getfield(sector, :charge), :twice)
        append!(charges, fill(charge, dim(space, sector)))
    end
    length(charges) == dim(space) || error("U(1) charge metadata does not span the dense basis")
    charges
end

function _blocked_two_site_tensor(first_tensor, second_tensor)
    A = dense_left_physical_right(first_tensor)
    B = dense_left_physical_right(second_tensor)
    size(A, 3) == size(B, 1) || throw(DimensionMismatch("two-site virtual bond does not contract"))
    blocked = zeros(promote_type(eltype(A), eltype(B)), size(A, 1), size(A, 2) * size(B, 2), size(B, 3))
    combined = LinearIndices((size(A, 2), size(B, 2)))
    for second_physical in axes(B, 2), first_physical in axes(A, 2)
        blocked[:, combined[first_physical, second_physical], :] =
            A[:, first_physical, :] * B[:, second_physical, :]
    end
    blocked
end

function transfer_matrix(A::Array{T,3}) where T
    Dl, d, Dr = size(A)
    E = zeros(promote_type(T,ComplexF64), Dl^2, Dr^2)
    for s in 1:d
        As = @view A[:,s,:]
        E .+= kron(conj(As), As)
    end
    E
end

function _dominant_hermitian_fixed_point(operator::AbstractMatrix, dimension::Int)
    decomposition = eigen(operator)
    index = argmax(abs.(decomposition.values))
    eigenvalue = decomposition.values[index]
    matrix = reshape(decomposition.vectors[:, index], dimension, dimension)
    matrix = Matrix{ComplexF64}(Hermitian((matrix + matrix') / 2))
    real(tr(matrix)) < 0 && (matrix .*= -1)
    matrix ./= tr(matrix)
    eigenvalue, matrix, norm(operator * vec(matrix) - eigenvalue * vec(matrix))
end

function dominant_fixed_points(tensors::Vector{<:Array})
    Es = transfer_matrix.(tensors)
    cell = foldl(*, Es)
    lambda_cycle, _, right_residual =
        _dominant_hermitian_fixed_point(cell, size(first(tensors), 1))
    left_decomposition = eigen(adjoint(cell))
    left_index = argmin(abs.(left_decomposition.values .- conj(lambda_cycle)))
    left_vector = left_decomposition.vectors[:, left_index]
    left_residual = norm(cell' * left_vector - conj(lambda_cycle) * left_vector)
    right = Matrix{ComplexF64}[]
    for site in eachindex(tensors)
        ordered = [Es[mod1(site + offset, length(Es))] for offset in 1:length(Es)]
        _, fixed, _ = _dominant_hermitian_fixed_point(foldl(*, ordered), size(tensors[site], 3))
        push!(right, fixed)
    end
    left = [Matrix{ComplexF64}(I, size(A,1), size(A,1)) for A in tensors]
    gauge_residual = maximum(norm(sum((@view A[:,s,:])' * (@view A[:,s,:]) for s=1:size(A,2))-I) for A in tensors)
    residual = max(right_residual, left_residual, gauge_residual)
    return (; lambda=lambda_cycle^(1/length(tensors)), left, right, residual)
end

function dense_two_site_energy(frozen::FrozenUniformMPS, h)
    energies = Float64[]
    for i in eachindex(frozen.tensors)
        A = frozen.tensors[i]
        B = frozen.tensors[mod1(i+1, frozen.unit_cell_length)]
        pair_transfer = transfer_matrix(A) * transfer_matrix(B)
        _, r, residual = _dominant_hermitian_fixed_point(pair_transfer, size(B, 3))
        residual < 1e-10 || error("two-site transfer fixed point residual is $residual")
        rho = zeros(ComplexF64, frozen.physical_dimension^2, frozen.physical_dimension^2)
        for s in 1:frozen.physical_dimension, t in 1:frozen.physical_dimension,
            sp in 1:frozen.physical_dimension, tp in 1:frozen.physical_dimension
            M = (@view A[:,s,:]) * (@view B[:,t,:])
            Mp = (@view A[:,sp,:]) * (@view B[:,tp,:])
            rho[t + (s-1)*frozen.physical_dimension, tp + (sp-1)*frozen.physical_dimension] = tr(M*r*Mp')
        end
        rho ./= tr(rho)
        push!(energies, real(tr(h*rho)))
    end
    sum(energies)/length(energies)
end

function freeze_mpskit(state, record::Dict{String,Any})
    tensors = Array{ComplexF64,3}[dense_left_physical_right(t) for t in state.AL]
    diagnostics = dominant_fixed_points(tensors)
    FrozenUniformMPS(tensors; canonical_gauge=:left,
        left_fixed_points=diagnostics.left, right_fixed_points=diagnostics.right,
        canonical_residual=diagnostics.residual,
        normalization_residual=abs(diagnostics.lambda-1),
        source_energy=record["energy_per_site"], vumps_settings=copy(record))
end

"Block a two-site U(1) MPS cell and retain dense charge metadata for Kull."
function freeze_u1_blocked_mpskit(state, record::Dict{String,Any})
    get(record, "symmetry", nothing) == "u1" ||
        throw(ArgumentError("record must come from a U(1)-symmetric VUMPS run"))
    get(record, "unit_cell_length", nothing) == 2 ||
        throw(ArgumentError("U(1) blocking requires a recorded two-site unit cell"))
    length(state.AL) == 2 || throw(ArgumentError("U(1) blocking requires a two-site MPS unit cell"))
    first_tensor, second_tensor = state.AL[1], state.AL[2]
    left_space = codomain(first_tensor)[1]
    right_space = domain(second_tensor)[1]
    left_space == right_space || throw(DimensionMismatch("blocked cell must begin and end on the same U(1) bond space"))
    physical_charges = product_charges(
        dense_u1_charges(codomain(first_tensor)[2]),
        dense_u1_charges(codomain(second_tensor)[2]))
    virtual_charges = dense_u1_charges(left_space)
    blocked = _blocked_two_site_tensor(first_tensor, second_tensor)
    diagnostics = dominant_fixed_points([blocked])
    frozen = FrozenUniformMPS([blocked]; canonical_gauge=:left,
        left_fixed_points=diagnostics.left, right_fixed_points=diagnostics.right,
        canonical_residual=diagnostics.residual,
        normalization_residual=abs(diagnostics.lambda - 1),
        source_energy=2record["energy_per_site"], vumps_settings=copy(record))
    symmetry = U1Symmetry(physical_charges, virtual_charges)
    charge_residual = mps_charge_residual(frozen, symmetry)
    charge_residual <= 1e-12 ||
        error("blocked TensorKit MPS and extracted U(1) charges use inconsistent basis order")
    metadata = Dict{String,Any}(
        "physical_charges" => copy(physical_charges),
        "virtual_charges" => copy(virtual_charges),
        "charge_residual" => charge_residual,
        "blocked_physical_dimension" => size(blocked, 2),
        "coarse_bond_dimension" => size(blocked, 1),
    )
    return (; frozen, symmetry, metadata)
end

"Compare transfer, norm-density, and local-energy invariants after freezing."
function validate_adapter_invariants(state, record::Dict{String,Any};
        h=HEISENBERG_H, atol=1e-11)
    frozen = freeze_mpskit(state, record)
    diagnostics = dominant_fixed_points(frozen.tensors)
    dense_energy = dense_two_site_energy(frozen, h)
    transfer_error = abs(diagnostics.lambda - 1)
    norm_density_error = abs(abs(diagnostics.lambda) - 1)
    energy_error = abs(dense_energy - record["energy_per_site"])
    maximum((transfer_error, norm_density_error, energy_error,
        frozen.canonical_residual)) < atol ||
        error("MPSKit adapter changed a physical invariant: transfer=$transfer_error, norm=$norm_density_error, energy=$energy_error, canonical=$(frozen.canonical_residual)")
    return (; frozen, transfer_eigenvalue=diagnostics.lambda,
        norm_density=abs(diagnostics.lambda), dense_energy,
        transfer_error, norm_density_error, energy_error)
end

export dense_left_physical_right, dense_u1_charges, transfer_matrix, dominant_fixed_points
export dense_two_site_energy, freeze_mpskit, freeze_u1_blocked_mpskit
export validate_adapter_invariants
end
