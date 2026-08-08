struct BoundaryMPSResult{T}
    value::T
    max_truncation_error::Float64
end

function double_layer(tensor::AbstractArray{<:Number,5}, operator::Union{Nothing,AbstractMatrix}=nothing)
    left_dim, top_dim, physical_dim, right_dim, bottom_dim = size(tensor)
    if operator === nothing
        @tensor raw[l, lb, t, tb, r, rb, b, bb] :=
            tensor[l, t, p, r, b] * conj(tensor[lb, tb, p, rb, bb])
    else
        size(operator) == (physical_dim, physical_dim) ||
            throw(DimensionMismatch("operator dimension does not match physical space"))
        @tensor raw[l, lb, t, tb, r, rb, b, bb] :=
            tensor[l, t, p, r, b] * conj(tensor[lb, tb, q, rb, bb]) * operator[q, p]
    end
    return reshape(raw, left_dim^2, top_dim^2, right_dim^2, bottom_dim^2)
end

function absorb_row(boundary::Vector{<:AbstractArray}, row::Vector{<:AbstractArray})
    length(boundary) == length(row) || throw(DimensionMismatch("boundary and row lengths differ"))
    result = Vector{Array}(undef, length(row))
    for x in eachindex(row)
        boundary_tensor = boundary[x]
        layer = row[x]
        size(boundary_tensor, 2) == size(layer, 2) ||
            throw(DimensionMismatch("boundary and row top dimensions differ at x=$x"))
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

function compress_boundary!(boundary::Vector{<:AbstractArray}, chi::Integer)
    chi >= 1 || throw(ArgumentError("chi must be positive"))
    max_error = 0.0
    for x in 1:(length(boundary) - 1)
        left_dim, physical_dim, right_dim = size(boundary[x])
        matrix = reshape(boundary[x], left_dim * physical_dim, right_dim)
        all(isfinite, matrix) || error("boundary MPS compression received non-finite entries")
        factorization = svd(matrix; alg=LinearAlgebra.QRIteration())
        kept = min(chi, length(factorization.S))
        total_weight = sum(abs2, factorization.S)
        discarded_weight = sum(abs2, @view factorization.S[(kept + 1):end])
        error = total_weight == 0 ? 0.0 : discarded_weight / total_weight
        max_error = max(max_error, error)
        boundary[x] = reshape(
            @view(factorization.U[:, 1:kept]),
            left_dim,
            physical_dim,
            kept,
        )
        carry = Diagonal(@view(factorization.S[1:kept])) * @view(factorization.Vt[1:kept, :])
        next_left, next_physical, next_right = size(boundary[x + 1])
        next_left == right_dim || throw(DimensionMismatch("neighboring boundary bonds do not match"))
        boundary[x + 1] = reshape(
            carry * reshape(boundary[x + 1], next_left, next_physical * next_right),
            kept,
            next_physical,
            next_right,
        )
    end
    return max_error
end

function close_boundary(boundary::Vector{<:AbstractArray})
    all(size(tensor, 2) == 1 for tensor in boundary) ||
        throw(DimensionMismatch("final boundary contains open physical legs"))
    transfer = boundary[1][:, 1, :]
    for x in 2:length(boundary)
        transfer = transfer * boundary[x][:, 1, :]
    end
    size(transfer) == (1, 1) || throw(DimensionMismatch("open horizontal boundary legs remain"))
    return transfer[1, 1]
end

function boundary_mps_contract(
    state::DenseFinitePEPS;
    chi::Integer,
    insertions::AbstractDict=Dict{CartesianIndex{2},Any}(),
)
    boundary = nothing
    max_error = 0.0
    for y in 1:state.Ly
        row = [
            double_layer(state[x, y], get(insertions, CartesianIndex(x, y), nothing))
            for x in 1:state.Lx
        ]
        if boundary === nothing
            boundary = [begin
                tensor = zeros(eltype(row[x]), 1, size(row[x], 2), 1)
                tensor[1, 1, 1] = one(eltype(tensor))
                tensor
            end for x in 1:state.Lx]
        end
        boundary = absorb_row(boundary, row)
        max_error = max(max_error, compress_boundary!(boundary, chi))
    end
    return BoundaryMPSResult(close_boundary(boundary), max_error)
end
