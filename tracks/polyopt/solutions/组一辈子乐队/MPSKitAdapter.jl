module MPSKitAdapter

using LinearAlgebra
using TensorKit
using MPSKit
include("KullCGRDM.jl")
using .KullCGRDM

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

function transfer_matrix(A::Array{T,3}) where T
    Dl, d, Dr = size(A)
    E = zeros(promote_type(T,ComplexF64), Dl^2, Dr^2)
    for s in 1:d
        As = @view A[:,s,:]
        E .+= kron(conj(As), As)
    end
    E
end

function dominant_fixed_points(tensors::Vector{<:Array})
    Es = transfer_matrix.(tensors)
    cycle = foldl(*, reverse(Es))
    evr = eigen(cycle)
    i = argmax(abs.(evr.values)); lambda_cycle = evr.values[i]
    r0 = evr.vectors[:,i]
    evl = eigen(adjoint(cycle)); j = argmin(abs.(evl.values .- conj(lambda_cycle)))
    l0 = evl.vectors[:,j]
    right = Matrix{ComplexF64}[]; v = r0
    for (A,E) in zip(tensors,Es)
        push!(right, Matrix(Hermitian((reshape(v,size(A,1),size(A,1)) + reshape(v,size(A,1),size(A,1))')/2)))
        v = E*v
    end
    left = [Matrix{ComplexF64}(I, size(A,1), size(A,1)) for A in tensors]
    gauge_residual = maximum(norm(sum((@view A[:,s,:])' * (@view A[:,s,:]) for s=1:size(A,2))-I) for A in tensors)
    residual = max(norm(cycle*r0-lambda_cycle*r0), norm(cycle'*l0-conj(lambda_cycle)*l0), gauge_residual)
    return (; lambda=lambda_cycle^(1/length(tensors)), left, right, residual)
end

function dense_two_site_energy(frozen::FrozenUniformMPS, h)
    energies = Float64[]
    for i in eachindex(frozen.tensors)
        A = frozen.tensors[i]; B = frozen.tensors[mod1(i+1, frozen.unit_cell_length)]
        r = frozen.right_fixed_points[i]
        r ./= tr(r)
        rho = zeros(ComplexF64, frozen.physical_dimension^2, frozen.physical_dimension^2)
        for s in 1:frozen.physical_dimension, t in 1:frozen.physical_dimension,
            sp in 1:frozen.physical_dimension, tp in 1:frozen.physical_dimension
            M = (@view A[:,s,:]) * (@view B[:,t,:])
            Mp = (@view A[:,sp,:]) * (@view B[:,tp,:])
            rho[s + (t-1)*frozen.physical_dimension, sp + (tp-1)*frozen.physical_dimension] = tr(M*r*Mp')
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

export dense_left_physical_right, transfer_matrix, dominant_fixed_points, dense_two_site_energy, freeze_mpskit
export validate_adapter_invariants
end
